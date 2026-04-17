import asyncio
import contextlib
import json
import uuid
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client, StopPropagation, filters
from pyrogram.enums import PollType
from pyrogram.errors import BadRequest, FloodWait, Forbidden, RPCError
from pyrogram.raw import base as raw_base
from pyrogram.raw import types as raw_types
from pyrogram.raw.types import User
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
from src.utils.moderation import _apply_punishment
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    Permission,
    has_permission,
)


class CaptchaPlugin(Plugin):
    """Plugin to handle user verification via various CAPTCHA methods."""

    name = "captcha"
    priority = 10

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.new_chat_members & filters.group, group=-80)
@safe_handler
async def captcha_join_handler(client: Client, message: Message) -> None:
    ctx = get_context()
    try:
        s = await get_settings(ctx, message.chat.id)
    except Exception as e:
        return logger.error(f"Captcha DB Error: {e}")
    if not s.captchaEnabled or not await has_permission(
        client, message.chat.id, Permission.CAN_BAN
    ):
        return

    res_any = False
    for m in message.new_chat_members:
        if m.id == client.me.id:
            continue
        try:
            await client.restrict_chat_member(message.chat.id, m.id, RESTRICTED_PERMISSIONS)
            mode, m_id, ans, id_map = s.captchaMode.lower(), None, None, None
            if mode == "poll":
                q, opts, cidx = await generate_poll_captcha(message.chat.id)
                msg = await client.send_poll(
                    message.chat.id,
                    q,
                    opts,
                    is_anonymous=False,
                    type=PollType.QUIZ,
                    correct_option_id=cidx,
                    explanation=await at(message.chat.id, "captcha.poll_explanation"),
                )
                ans, m_id = str(cidx), msg.id
                await ctx.cache.set(
                    CacheKeys.poll(str(msg.poll.id)),
                    json.dumps({"chat_id": message.chat.id, "user_id": m.id}),
                    ttl=s.captchaTimeout,
                )
            elif mode == "math":
                prob, ans = generate_math_captcha()
                msg = await message.reply(
                    await at(
                        message.chat.id, "captcha.math_prompt", problem=prob, mention=m.mention
                    )
                )
                m_id = msg.id
            elif mode == "image":
                img, ans, opts = generate_image_captcha(lang=await resolve_lang(message.chat.id))
                id_map = {uuid.uuid4().hex[:8]: o for o in opts}
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                CAPTCHA_OBJECTS[o], callback_data=f"captcha_img_choice:{m.id}:{i}"
                            )
                            for i, o in list(id_map.items())[x : x + 2]
                        ]
                        for x in (0, 2)
                    ]
                )
                msg = await client.send_photo(
                    message.chat.id,
                    img,
                    caption=await at(message.chat.id, "captcha.image_prompt", mention=m.mention),
                    reply_markup=kb,
                )
                m_id = msg.id
            else:
                kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                await at(message.chat.id, "captcha.button"),
                                callback_data=f"captcha_verify:{m.id}",
                            )
                        ]
                    ]
                )
                msg = await message.reply(
                    await at(message.chat.id, "captcha.message", mention=m.mention), reply_markup=kb
                )
                m_id = msg.id

            if m_id:
                d = {
                    "msg_id": m_id,
                    "mode": mode,
                    "first_name": m.first_name,
                    "username": m.username,
                    "chat_title": message.chat.title,
                    "timeout": s.captchaTimeout,
                    "action": s.captchaAction or "ban",
                }
                if ans is not None:
                    d["answer"] = ans
                if id_map:
                    d["id_map"] = id_map
                await ctx.cache.set(
                    CacheKeys.captcha(message.chat.id, m.id), json.dumps(d), ttl=s.captchaTimeout
                )
                asyncio.create_task(
                    _enforce_captcha_timeout(client, message.chat.id, m.id, m_id, s.captchaTimeout)
                )
                res_any = True
        except (BadRequest, RPCError, FloodWait, Forbidden):
            continue
        except Exception:
            logger.exception("Captcha logic err")
    if res_any:
        raise StopPropagation


async def _enforce_captcha_timeout(client: Client, cid: int, uid: int, mid: int, tout: int) -> None:
    await asyncio.sleep(tout)
    ctx, k = get_context(), CacheKeys.captcha(cid, uid)
    if await ctx.cache.exists(k):
        await ctx.cache.delete(k)
        try:
            await client.ban_chat_member(cid, uid, until_date=datetime.now() + timedelta(hours=7))
            await client.delete_messages(cid, mid)
        except (BadRequest, Forbidden):
            pass
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            with contextlib.suppress(Exception):
                await client.ban_chat_member(
                    cid, uid, until_date=datetime.now() + timedelta(hours=7)
                )
                await client.delete_messages(cid, mid)
        except Exception as e:
            logger.exception(f"Captcha timeout err: {e}")


@bot.on_callback_query(filters.regex(r"^captcha_verify:(\d+)"))
@safe_handler
async def captcha_verify_handler(client: Client, callback: CallbackQuery) -> None:
    if not callback.message:
        return
    cid, ctx, tuid = callback.message.chat.id, get_context(), int(callback.data.split(":")[1])
    if callback.from_user.id != tuid:
        return await callback.answer(await at(cid, "captcha.not_for_you"), show_alert=True)
    if not (raw := await ctx.cache.get(CacheKeys.captcha(cid, tuid))):
        return await callback.answer(await at(cid, "captcha.expired"), show_alert=True)
    d = json.loads(raw)
    if d.get("mode") != "button":
        return await callback.answer(await at(cid, "captcha.wrong_mode"), show_alert=True)
    await _handle_captcha_success(
        client, cid, callback.from_user, d["msg_id"], d.get("chat_title", "")
    )
    await callback.answer(await at(cid, "captcha.success"))


@bot.on_message(filters.group, group=-110)
@safe_handler
async def captcha_message_handler(client: Client, message: Message) -> None:
    if not message.from_user:
        return
    ctx = get_context()
    if not (raw := await ctx.cache.get(CacheKeys.captcha(message.chat.id, message.from_user.id))):
        return
    d = json.loads(raw)
    if d.get("mode") != "math":
        return
    await message.delete()
    if message.text and message.text.strip().upper() == d.get("answer", "").upper():
        await _handle_captcha_success(
            client, message.chat.id, message.from_user, d["msg_id"], d.get("chat_title", "")
        )


@bot.on_callback_query(filters.regex(r"^captcha_img_choice:(\d+):(.*)"))
@safe_handler
async def captcha_img_choice_handler(client: Client, callback: CallbackQuery) -> None:
    if not callback.message:
        return
    cid, ctx, tuid, choice = (
        callback.message.chat.id,
        get_context(),
        int(callback.data.split(":")[1]),
        callback.data.split(":")[2],
    )
    if callback.from_user.id != tuid:
        return await callback.answer(await at(cid, "captcha.not_for_you"), show_alert=True)
    if not (raw := await ctx.cache.get(CacheKeys.captcha(cid, tuid))):
        return await callback.answer(await at(cid, "captcha.expired"), show_alert=True)
    d = json.loads(raw)

    if d.get("failed"):
        return await callback.answer(await at(cid, "captcha.locked"), show_alert=True)

    if d.get("id_map", {}).get(choice, "").upper() == d.get("answer", "").upper():
        await _handle_captcha_success(
            client, cid, callback.from_user, d["msg_id"], d.get("chat_title", "")
        )
        await callback.answer(await at(cid, "captcha.success"))
    else:
        # Mark as failed and apply configured action after 1 wrong attempt
        d["failed"] = True
        await ctx.cache.set(CacheKeys.captcha(cid, tuid), json.dumps(d), ttl=d.get("timeout", 120))

        action = d.get("action", "ban")
        await callback.answer(await at(cid, f"captcha.wrong_choice_{action}"), show_alert=True)

        with contextlib.suppress(Exception):
            await _apply_punishment(client, cid, tuid, action)


@bot.on_raw_update(group=-100)
@safe_handler
async def captcha_poll_handler(
    client: Client, update: raw_base.Update, users: dict, chats: dict
) -> None:
    if not isinstance(update, raw_types.UpdateMessagePollVote):
        return
    ctx, pid = get_context(), str(update.poll_id)
    if not (raw_p := await ctx.cache.get(CacheKeys.poll(pid))):
        return
    pi = json.loads(raw_p)
    cid, uid = pi["chat_id"], pi["user_id"]
    if not isinstance(update.peer, raw_types.PeerUser) or update.peer.user_id != uid:
        return
    if not (raw_u := await ctx.cache.get(CacheKeys.captcha(cid, uid))):
        return
    ud = json.loads(raw_u)
    if (update.options[0][0] if update.options else -1) == int(ud["answer"]):
        u = users.get(uid) or User(
            id=uid,
            first_name=ud.get("first_name", "User"),
            username=ud.get("username"),
            client=client,
        )
        await _handle_captcha_success(client, cid, u, ud["msg_id"], ud.get("chat_title", ""))
        await ctx.cache.delete(CacheKeys.poll(pid))


async def _handle_captcha_success(client: Client, cid: int, user, mid: int, title: str) -> None:
    await get_context().cache.delete(CacheKeys.captcha(cid, user.id))
    try:
        await client.restrict_chat_member(cid, user.id, UNRESTRICTED_PERMISSIONS)
        await client.delete_messages(cid, mid)
        from src.plugins.welcome import send_welcome_goodbye

        await send_welcome_goodbye(client, cid, title, user, is_welcome=True)
    except (BadRequest, Forbidden):
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        with contextlib.suppress(Exception):
            await client.restrict_chat_member(cid, user.id, UNRESTRICTED_PERMISSIONS)
            await client.delete_messages(cid, mid)
    except Exception as e:
        logger.exception(f"Captcha success err: {e}")


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("captchaTimeout"), group=-50)
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
