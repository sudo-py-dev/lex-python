import asyncio
from datetime import datetime, timedelta

from loguru import logger
from pyrogram import Client, filters
from pyrogram.errors import BadRequest, ChatAdminRequired, FloodWait, Forbidden, RPCError
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import AppContext, get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.db.repositories.warns import (
    add_warn,
    get_warns,
    reset_all_chat_warns,
    reset_warns,
)
from src.plugins.logging import log_event
from src.utils.decorators import admin_permission_required, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.permissions import RESTRICTED_PERMISSIONS, Permission, has_permission


class WarnsPlugin(Plugin):
    name = "warns"
    priority = 40

    async def setup(self, client: Client, ctx: AppContext) -> None:
        pass


@bot.on_message(filters.command("warn") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
@resolve_target
async def warn_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))

    # Safety Check: Do not moderate self or other admins
    from src.utils.permissions import is_admin
    if target_user.id == client.me.id:
        return await message.reply(await at(message.chat.id, "error.cant_restrict_self"))
    if await is_admin(client, message.chat.id, target_user.id):
        return await message.reply(await at(message.chat.id, "error.target_is_admin"))

    ctx, off = get_context(), 1 if message.reply_to_message else 2
    res = " ".join(message.command[off:]) if len(message.command) > off else None
    count = await add_warn(ctx, message.chat.id, target_user.id, message.from_user.id, res)
    s = await get_settings(ctx, message.chat.id)

    if count >= s.warnLimit:
        a = s.warnAction.lower()
        try:
            if a == "ban":
                await client.ban_chat_member(message.chat.id, target_user.id)
            elif a == "kick":
                await client.ban_chat_member(
                    message.chat.id,
                    target_user.id,
                    until_date=datetime.now() + timedelta(minutes=1),
                )
            elif a == "mute":
                await client.restrict_chat_member(
                    message.chat.id, target_user.id, RESTRICTED_PERMISSIONS
                )
            await reset_warns(ctx, message.chat.id, target_user.id)
            await log_event(
                ctx,
                client,
                message.chat.id,
                f"warn_limit_{a}",
                target_user,
                client.me,
                reason=await at(message.chat.id, "logging.warn_limit_reason", limit=s.warnLimit),
                chat_title=message.chat.title,
            )
            await message.reply(
                await at(
                    message.chat.id,
                    "warn.limit_reached",
                    mention=target_user.mention,
                    action=await at(message.chat.id, f"action.{a}"),
                )
            )
        except (BadRequest, Forbidden, RPCError) as e:
            if isinstance(e, FloodWait):
                await asyncio.sleep(e.value + 1)
            logger.warning(f"Warn limit err: {e}")
            await message.reply(
                await at(
                    message.chat.id,
                    "error.bot_not_admin"
                    if isinstance(e, ChatAdminRequired)
                    else "error.unauthorized_admin",
                )
            )
    else:
        await message.reply(
            await at(
                message.chat.id,
                "warn.added",
                mention=target_user.mention,
                count=count,
                limit=s.warnLimit,
            )
        )
        await log_event(
            ctx,
            client,
            message.chat.id,
            "warn",
            target_user,
            message.from_user,
            reason=res,
            chat_title=message.chat.title,
        )


@bot.on_message(filters.command("unwarn") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_RESTRICT)
@resolve_target
async def unwarn_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        return await message.reply(await at(message.chat.id, "error.bot_no_permission"))
    await reset_warns(get_context(), message.chat.id, target_user.id)
    await message.reply(await at(message.chat.id, "warn.reset", mention=target_user.mention))


@bot.on_message(filters.command(["warns", "warnings"]) & filters.group)
@safe_handler
@resolve_target
async def warns_handler(client: Client, message: Message, target_user: User) -> None:
    ctx = get_context()
    if not (ws := await get_warns(ctx, message.chat.id, target_user.id)):
        return await message.reply(
            await at(message.chat.id, "warn.none", mention=target_user.mention)
        )
    s = await get_settings(ctx, message.chat.id)
    txt, nr = (
        await at(
            message.chat.id,
            "warn.list_header",
            mention=target_user.mention,
            count=len(ws),
            limit=s.warnLimit,
        ),
        await at(message.chat.id, "common.no_reason"),
    )
    await message.reply(
        txt
        + "\n"
        + "\n".join(
            await at(
                message.chat.id, "warn.list_entry", num=i, reason=w.reason or nr, actor=w.actorId
            )
            for i, w in enumerate(ws, 1)
        )
    )


@bot.on_message(filters.command("resetallwarns") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_BAN)
async def reset_all_warns_handler(client: Client, message: Message) -> None:
    await message.reply(
        await at(
            message.chat.id,
            "warn.cleared_all",
            count=await reset_all_chat_warns(get_context(), message.chat.id),
        )
    )


@bot.on_message(filters.private & is_waiting_for_input("warnLimit"), group=-50)
@safe_handler
async def warn_limit_input_handler(client: Client, message: Message) -> None:
    s = message.input_state
    uid, cid, v = message.from_user.id, s["chat_id"], message.text
    if not str(v).isdigit() or int(v) < 1:
        return await message.reply(await at(uid, "panel.input_invalid_number"))
    ctx = get_context()
    from src.plugins.admin_panel.repository import update_chat_setting

    await update_chat_setting(ctx, cid, "warnLimit", int(v))
    from src.plugins.admin_panel.handlers.moderation_kbs import warns_kb

    st = await get_settings(ctx, cid)
    txt = await at(
        uid,
        "panel.warns_text",
        limit=st.warnLimit,
        action=st.warnAction.capitalize(),
        expiry=st.warnExpiry.capitalize(),
    )
    await finalize_input_capture(
        client,
        message,
        uid,
        s["prompt_msg_id"],
        txt,
        await warns_kb(ctx, cid, user_id=uid),
        success_text=await at(uid, "panel.input_success"),
    )


register(WarnsPlugin())
