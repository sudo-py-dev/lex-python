import asyncio
import json
import uuid
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import PollType
from pyrogram.raw import types as raw_types
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.core.bot import bot
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.captcha_utils import (
    CAPTCHA_OBJECTS,
    generate_image_captcha,
    generate_math_captcha,
    generate_poll_captcha,
)
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    can_restrict_members,
)

from . import get_ctx


@bot.on_message(filters.new_chat_members & filters.group, group=-3)
async def captcha_join_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()

    try:
        settings = await get_chat_settings(ctx, message.chat.id)
    except Exception as e:
        logger.error(f"Captcha DB Error: {e}")
        return
    if not settings.captchaEnabled:
        logger.debug("Captcha disabled")
        return

    can_restrict = await can_restrict_members(client, message.chat.id)
    if not can_restrict:
        return

    restricted_any = False
    for new_member in message.new_chat_members:
        if new_member.id == client.me.id:
            logger.debug("Skipping self")
            continue
        try:
            await client.restrict_chat_member(
                message.chat.id,
                new_member.id,
                RESTRICTED_PERMISSIONS,
            )

            mode = settings.captchaMode.lower()
            captcha_msg = None
            answer = None

            if mode == "poll":
                question, options, correct_index = generate_poll_captcha(message.chat.id)
                captcha_msg = await client.send_poll(
                    message.chat.id,
                    question,
                    options,
                    is_anonymous=False,
                    type=PollType.QUIZ,
                    correct_option_id=correct_index,
                    explanation=await at(message.chat.id, "captcha.poll_explanation"),
                )
                answer = str(correct_index)

                await ctx.redis.set(
                    f"captcha_poll:{captcha_msg.poll.id}",
                    json.dumps({"chat_id": message.chat.id, "user_id": new_member.id}),
                    ex=settings.captchaTimeout,
                )
            elif mode == "math":
                problem, answer = generate_math_captcha()
                captcha_msg = await message.reply(
                    await at(
                        message.chat.id,
                        "captcha.math_prompt",
                        problem=problem,
                        mention=new_member.mention,
                    )
                )
            elif mode == "image":
                img_io, answer, options = generate_image_captcha()
                id_map = {uuid.uuid4().hex[:8]: opt for opt in options}
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                CAPTCHA_OBJECTS[opt],
                                callback_data=f"captcha_img_choice:{new_member.id}:{opt_id}",
                            )
                            for opt_id, opt in list(id_map.items())[:2]
                        ],
                        [
                            InlineKeyboardButton(
                                CAPTCHA_OBJECTS[opt],
                                callback_data=f"captcha_img_choice:{new_member.id}:{opt_id}",
                            )
                            for opt_id, opt in list(id_map.items())[2:]
                        ],
                    ]
                )
                captcha_msg = await client.send_photo(
                    message.chat.id,
                    img_io,
                    caption=await at(
                        message.chat.id, "captcha.image_prompt", mention=new_member.mention
                    ),
                    reply_markup=kb,
                )
            else:
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                await at(message.chat.id, "captcha.button"),
                                callback_data=f"captcha_verify:{new_member.id}",
                            )
                        ]
                    ]
                )
                captcha_msg = await message.reply(
                    await at(message.chat.id, "captcha.message", mention=new_member.mention),
                    reply_markup=kb,
                )

            if captcha_msg:
                key = f"captcha:{message.chat.id}:{new_member.id}"
                data = {
                    "msg_id": captcha_msg.id,
                    "mode": mode,
                    "first_name": new_member.first_name,
                    "username": new_member.username,
                    "chat_title": message.chat.title,
                }
                if answer is not None:
                    data["answer"] = answer
                if mode == "image":
                    data["id_map"] = id_map

                await ctx.redis.set(key, json.dumps(data), ex=settings.captchaTimeout)

                asyncio.create_task(
                    _enforce_captcha_timeout(
                        client,
                        ctx,
                        message.chat.id,
                        new_member.id,
                        captcha_msg.id,
                        settings.captchaTimeout,
                    )
                )
                restricted_any = True
        except Exception as e:
            logger.exception(f"Captcha error: {e}")

    if restricted_any:
        raise __import__("pyrogram").StopPropagation


async def _enforce_captcha_timeout(
    client: Client, ctx, chat_id: int, user_id: int, msg_id: int, timeout: int
) -> None:
    await asyncio.sleep(timeout)
    key = f"captcha:{chat_id}:{user_id}"
    if await ctx.redis.exists(key):
        await ctx.redis.delete(key)
        try:
            await client.ban_chat_member(
                chat_id, user_id, until_date=datetime.now() + timedelta(hours=7)
            )
            await client.delete_messages(chat_id, msg_id)
        except Exception:
            pass


@bot.on_callback_query(filters.regex(r"^captcha_verify:(\d+)"))
async def captcha_verify_handler(client: Client, callback: CallbackQuery) -> None:
    if not callback.message:
        return
    chat_id = callback.message.chat.id
    ctx = get_ctx()
    target_user_id = int(callback.data.split(":")[1])
    if callback.from_user.id != target_user_id:
        await callback.answer(await at(chat_id, "captcha.not_for_you"), show_alert=True)
        return
    key = f"captcha:{callback.message.chat.id}:{target_user_id}"
    raw_data = await ctx.redis.get(key)
    if not raw_data:
        await callback.answer(await at(chat_id, "captcha.expired"), show_alert=True)
        return

    data = json.loads(raw_data)
    if data.get("mode") != "button":
        await callback.answer(await at(chat_id, "captcha.wrong_mode"), show_alert=True)
        return

    await _handle_captcha_success(
        client, ctx, chat_id, callback.from_user, data["msg_id"], data.get("chat_title", "")
    )
    await callback.answer(await at(chat_id, "captcha.success"))


@bot.on_message(filters.group, group=-2)
async def captcha_message_handler(client: Client, message: Message) -> None:
    """Handles text input for math and image captchas."""
    if not message.from_user:
        return
    ctx = get_ctx()
    key = f"captcha:{message.chat.id}:{message.from_user.id}"
    raw_data = await ctx.redis.get(key)
    if not raw_data:
        return

    data = json.loads(raw_data)
    mode = data.get("mode")
    if mode != "math":
        return

    await message.delete()

    correct_answer = data.get("answer")
    if message.text and message.text.strip().upper() == correct_answer.upper():
        await _handle_captcha_success(
            client,
            ctx,
            message.chat.id,
            message.from_user,
            data["msg_id"],
            data.get("chat_title", ""),
        )
    else:
        # Optionally notify wrong answer, but usually just wait for timeout or retry
        pass


@bot.on_callback_query(filters.regex(r"^captcha_img_choice:(\d+):(.*)"))
async def captcha_img_choice_handler(client: Client, callback: CallbackQuery) -> None:
    """Handles button selection for Image CAPTCHA."""
    if not callback.message:
        return

    chat_id = callback.message.chat.id
    ctx = get_ctx()
    data = callback.data.split(":")
    target_user_id = int(data[1])
    choice = data[2]

    if callback.from_user.id != target_user_id:
        await callback.answer(await at(chat_id, "captcha.not_for_you"), show_alert=True)
        return

    key = f"captcha:{chat_id}:{target_user_id}"
    raw_data = await ctx.redis.get(key)
    if not raw_data:
        await callback.answer(await at(chat_id, "captcha.expired"), show_alert=True)
        return

    import json

    data = json.loads(raw_data)
    id_map = data.get("id_map", {})
    chosen_name = id_map.get(choice, "")

    if chosen_name.upper() == data.get("answer", "").upper():
        await _handle_captcha_success(
            client, ctx, chat_id, callback.from_user, data["msg_id"], data.get("chat_title", "")
        )
        await callback.answer(await at(chat_id, "captcha.success"))
    else:
        await callback.answer(await at(chat_id, "captcha.wrong_choice"), show_alert=True)


@bot.on_raw_update(group=-2)
async def captcha_poll_handler(
    client: Client, update: raw_types.Update, users: dict, chats: dict
) -> None:
    """Handles poll answers for captcha via raw updates."""
    if not isinstance(update, raw_types.UpdateMessagePollVote):
        return

    ctx = get_ctx()
    poll_id = str(update.poll_id)
    key_poll = f"captcha_poll:{poll_id}"
    raw_poll_info = await ctx.redis.get(key_poll)
    if not raw_poll_info:
        return

    import json

    poll_info = json.loads(raw_poll_info)
    chat_id = poll_info["chat_id"]
    user_id = poll_info["user_id"]

    if isinstance(update.peer, raw_types.PeerUser):
        current_user_id = update.peer.user_id
    else:
        # Fallback if peer is something else
        return

    if current_user_id != user_id:
        return

    key_user = f"captcha:{chat_id}:{user_id}"
    raw_user_data = await ctx.redis.get(key_user)
    if not raw_user_data:
        return

    user_data = json.loads(raw_user_data)
    correct_option_index = int(user_data["answer"])

    chosen_option = update.options[0][0] if update.options else -1

    if chosen_option == correct_option_index:
        user = users.get(user_id)
        if not user:
            from pyrogram.types import User

            user = User(
                id=user_id,
                first_name=user_data.get("first_name", "User"),
                username=user_data.get("username"),
                client=client,
            )

        await _handle_captcha_success(
            client, ctx, chat_id, user, user_data["msg_id"], user_data.get("chat_title", "")
        )
        await ctx.redis.delete(key_poll)


async def _handle_captcha_success(
    client: Client, ctx, chat_id: int, user, msg_id: int, chat_title: str
) -> None:
    key = f"captcha:{chat_id}:{user.id}"
    await ctx.redis.delete(key)
    try:
        await client.restrict_chat_member(chat_id, user.id, UNRESTRICTED_PERMISSIONS)
        await client.delete_messages(chat_id, msg_id)

        from src.plugins.welcome.handlers import send_welcome

        await send_welcome(client, chat_id, chat_title, user)
    except Exception as e:
        logger.error(f"Captcha success handler error: {e}")
