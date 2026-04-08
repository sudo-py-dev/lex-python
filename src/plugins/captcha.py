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
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.utils.captcha_utils import (
    CAPTCHA_OBJECTS,
    generate_image_captcha,
    generate_math_captcha,
    generate_poll_captcha,
)
from src.utils.decorators import safe_handler
from src.utils.i18n import at, resolve_lang
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    can_restrict_members,
)


class CaptchaPlugin(Plugin):
    """Plugin to handle user verification via various CAPTCHA methods."""

    name = "captcha"
    priority = 10

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.new_chat_members & filters.group, group=-3)
@safe_handler
async def captcha_join_handler(client: Client, message: Message) -> None:
    """
    Detect new chat members and initiate the CAPTCHA verification process if enabled.

    Restricts the new member's permissions and sends a CAPTCHA challenge
    based on the chat's configuration (poll, math, image, or button).
    Stores the challenge data in the cache and starts a timeout task.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object containing the new chat members.

    Side Effects:
        - Restricts new members' chat permissions.
        - Sends a CAPTCHA challenge message (poll, photo, or text).
        - Sets CAPTCHA data in the cache.
        - Spawns a background task to enforce the timeout.
        - Stops message propagation if any member is restricted.
    """
    ctx = get_context()

    try:
        settings = await get_settings(ctx, message.chat.id)
    except Exception as e:
        logger.error(f"Captcha DB Error: {e}")
        return

    if not settings.captchaEnabled:
        return

    can_restrict = await can_restrict_members(client, message.chat.id)
    if not can_restrict:
        return

    restricted_any = False
    for new_member in message.new_chat_members:
        if new_member.id == client.me.id:
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
                question, options, correct_index = await generate_poll_captcha(message.chat.id)
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

                poll_key = CacheKeys.captcha_poll(str(captcha_msg.poll.id))
                await ctx.cache.set(
                    poll_key,
                    json.dumps({"chat_id": message.chat.id, "user_id": new_member.id}),
                    ttl=settings.captchaTimeout,
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
                lang = await resolve_lang(message.chat.id)
                img_io, answer, options = generate_image_captcha(lang=lang)
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
                key = CacheKeys.captcha(message.chat.id, new_member.id)
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

                await ctx.cache.set(key, json.dumps(data), ttl=settings.captchaTimeout)

                asyncio.create_task(
                    _enforce_captcha_timeout(
                        client,
                        message.chat.id,
                        new_member.id,
                        captcha_msg.id,
                        settings.captchaTimeout,
                    )
                )
                restricted_any = True
        except Exception:
            logger.exception("Captcha execution error")

    if restricted_any:
        raise __import__("pyrogram").StopPropagation


async def _enforce_captcha_timeout(
    client: Client, chat_id: int, user_id: int, msg_id: int, timeout: int
) -> None:
    """
    Background task to enforce the CAPTCHA timeout.

    If the user does not complete the challenge within the specified time,
    they are banned and the challenge message is deleted.

    Args:
        client (Client): The Pyrogram client instance.
        chat_id (int): The ID of the chat.
        user_id (int): The ID of the user being verified.
        msg_id (int): The ID of the CAPTCHA message to delete.
        timeout (int): The duration to wait before timeout (in seconds).

    Side Effects:
        - Deletes CAPTCHA data from the cache.
        - Bans the user if the challenge is still active.
        - Deletes the CAPTCHA message.
    """
    await asyncio.sleep(timeout)
    ctx = get_context()
    key = CacheKeys.captcha(chat_id, user_id)
    if await ctx.cache.exists(key):
        await ctx.cache.delete(key)
        try:
            await client.ban_chat_member(
                chat_id, user_id, until_date=datetime.now() + timedelta(hours=7)
            )
            await client.delete_messages(chat_id, msg_id)
        except Exception:
            pass


@bot.on_callback_query(filters.regex(r"^captcha_verify:(\d+)"))
@safe_handler
async def captcha_verify_handler(client: Client, callback: CallbackQuery) -> None:
    """
    Handle verification for button-based CAPTCHA.

    Verifies that the user clicking the button is the one being challenged
     and that the session has not expired.

    Args:
        client (Client): The Pyrogram client instance.
        callback (CallbackQuery): The callback query from the 'Verify' button.

    Side Effects:
        - Clears restriction and deletes CAPTCHA message on success.
        - Triggers the welcome message on success.
        - Answers the callback query.
    """
    if not callback.message:
        return
    chat_id = callback.message.chat.id
    ctx = get_context()
    target_user_id = int(callback.data.split(":")[1])

    if callback.from_user.id != target_user_id:
        await callback.answer(await at(chat_id, "captcha.not_for_you"), show_alert=True)
        return

    key = CacheKeys.captcha(chat_id, target_user_id)
    raw_data = await ctx.cache.get(key)
    if not raw_data:
        await callback.answer(await at(chat_id, "captcha.expired"), show_alert=True)
        return

    data = json.loads(raw_data)
    if data.get("mode") != "button":
        await callback.answer(await at(chat_id, "captcha.wrong_mode"), show_alert=True)
        return

    await _handle_captcha_success(
        client, chat_id, callback.from_user, data["msg_id"], data.get("chat_title", "")
    )
    await callback.answer(await at(chat_id, "captcha.success"))


@bot.on_message(filters.group, group=-100)
@safe_handler
async def captcha_message_handler(client: Client, message: Message) -> None:
    """
    Handle text input for math-based CAPTCHA.

    Deletes all messages from users currently undergoing math CAPTCHA and
    verifies if the input matches the stored numeric answer.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message sent by the user.

    Side Effects:
        - Deletes the user's message regardless of answer correctness.
        - Clears restriction and triggers success handler if the answer is correct.
    """
    if not message.from_user:
        return
    ctx = get_context()
    key = CacheKeys.captcha(message.chat.id, message.from_user.id)
    raw_data = await ctx.cache.get(key)
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
            message.chat.id,
            message.from_user,
            data["msg_id"],
            data.get("chat_title", ""),
        )


@bot.on_callback_query(filters.regex(r"^captcha_img_choice:(\d+):(.*)"))
@safe_handler
async def captcha_img_choice_handler(client: Client, callback: CallbackQuery) -> None:
    """
    Handle selection for image-based CAPTCHA.

    Verifies if the object chosen by the user matches the hidden answer
    associated with the generated CAPTCHA image.

    Args:
        client (Client): The Pyrogram client instance.
        callback (CallbackQuery): The callback query from the object icons.

    Side Effects:
        - Clears restriction and deletes CAPTCHA photo on success.
        - Answers the callback query.
    """
    if not callback.message:
        return

    chat_id = callback.message.chat.id
    ctx = get_context()
    data_parts = callback.data.split(":")
    target_user_id = int(data_parts[1])
    choice = data_parts[2]

    if callback.from_user.id != target_user_id:
        await callback.answer(await at(chat_id, "captcha.not_for_you"), show_alert=True)
        return

    key = CacheKeys.captcha(chat_id, target_user_id)
    raw_data = await ctx.cache.get(key)
    if not raw_data:
        await callback.answer(await at(chat_id, "captcha.expired"), show_alert=True)
        return

    data = json.loads(raw_data)
    id_map = data.get("id_map", {})
    chosen_name = id_map.get(choice, "")

    if chosen_name.upper() == data.get("answer", "").upper():
        await _handle_captcha_success(
            client, chat_id, callback.from_user, data["msg_id"], data.get("chat_title", "")
        )
        await callback.answer(await at(chat_id, "captcha.success"))
    else:
        await callback.answer(await at(chat_id, "captcha.wrong_choice"), show_alert=True)


@bot.on_raw_update(group=-100)
@safe_handler
async def captcha_poll_handler(
    client: Client, update: raw_types.Update, users: dict, chats: dict
) -> None:
    """
    Handle poll/quiz answers for poll-based CAPTCHA.

    Uses raw updates to detect user participation in a quiz and checks if the
    user selected the correct option ID.

    Args:
        client (Client): The Pyrogram client instance.
        update (raw_types.Update): The raw update containing poll vote data.
        users (dict): A dictionary of user objects involved in the update.
        chats (dict): A dictionary of chat objects involved in the update.

    Side Effects:
        - Clears restriction and deletes poll message on success.
    """
    if not isinstance(update, raw_types.UpdateMessagePollVote):
        return

    ctx = get_context()
    poll_id = str(update.poll_id)
    poll_key = CacheKeys.captcha_poll(poll_id)
    raw_poll_info = await ctx.cache.get(poll_key)
    if not raw_poll_info:
        return

    poll_info = json.loads(raw_poll_info)
    chat_id = poll_info["chat_id"]
    user_id = poll_info["user_id"]

    if not isinstance(update.peer, raw_types.PeerUser) or update.peer.user_id != user_id:
        return

    user_key = CacheKeys.captcha(chat_id, user_id)
    raw_user_data = await ctx.cache.get(user_key)
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
            client, chat_id, user, user_data["msg_id"], user_data.get("chat_title", "")
        )
        await ctx.cache.delete(poll_key)


async def _handle_captcha_success(
    client: Client, chat_id: int, user, msg_id: int, chat_title: str
) -> None:
    """
    Common logic executed when a user successfully completes any CAPTCHA challenge.

    Removes user restrictions, deletes the challenge message, and triggers
     the custom welcome message for the group.

    Args:
        client (Client): The Pyrogram client instance.
        chat_id (int): The ID of the chat.
        user (User): The user who successfully verified.
        msg_id (int): The ID of the CAPTCHA message to delete.
        chat_title (str): The title of the chat (for the welcome message).

    Side Effects:
        - Restores full permissions to the user.
        - Deletes the CAPTCHA message.
        - Clears CAPTCHA data from the cache.
        - Sends a welcome message.
    """
    ctx = get_context()
    key = CacheKeys.captcha(chat_id, user.id)
    await ctx.cache.delete(key)
    try:
        await client.restrict_chat_member(chat_id, user.id, UNRESTRICTED_PERMISSIONS)
        await client.delete_messages(chat_id, msg_id)

        from src.plugins.welcome import send_welcome

        await send_welcome(client, chat_id, chat_title, user)
    except Exception as e:
        logger.error(f"Captcha success handler error: {e}")


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("captchaTimeout"), group=-100)
@safe_handler
async def captcha_timeout_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text

    if not str(value).isdigit() or int(value) < 10:
        await message.reply(await at(user_id, "panel.input_invalid_number_min", min=10))
        return

    from src.plugins.admin_panel.repository import update_chat_setting

    await update_chat_setting(ctx, chat_id, "captchaTimeout", int(value))

    from src.plugins.admin_panel.handlers.security_kbs import captcha_kb

    kb = await captcha_kb(ctx, chat_id, user_id=user_id)

    s = await get_settings(ctx, chat_id)
    status = await at(
        user_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
    )
    text = await at(
        user_id,
        "panel.captcha_text",
        status=status,
        mode=s.captchaMode.capitalize(),
        timeout=s.captchaTimeout,
        action=await at(user_id, "action.ban"),
    )

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(CaptchaPlugin())
