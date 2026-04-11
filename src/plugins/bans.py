import asyncio
import datetime as dt_module
from datetime import datetime

from loguru import logger
from pyrogram import Client, filters
from pyrogram.errors import (
    BadRequest,
    FloodWait,
    Forbidden,
    RPCError,
)
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.actions import create_timed_action, log_action
from src.plugins.scheduler.manager import SchedulerManager
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    Permission,
    has_permission,
)
from src.utils.time_parser import parse_time


class BansPlugin(Plugin):
    """Plugin to manage user bans, mutes, kicks, and timed restrictions."""

    name = "bans"
    priority = 20

    async def setup(self, client: Client, ctx) -> None:
        pass


async def _execute_restriction(
    client: Client,
    message: Message,
    u: User,
    action: str,
    p: Permission,
    until: datetime | None = None,
) -> None:
    """Helper for ban/mute/kick/tban/tmute."""
    cid = message.chat.id
    uid = u.id
    aid = message.from_user.id
    if not await has_permission(client, cid, p):
        return await message.reply(await at(cid, "error.no_permission"))
    ctx = get_context()
    try:
        if action in ("ban", "tban", "kick"):
            await client.ban_chat_member(cid, uid, until_date=until or 0)
        elif action in ("mute", "tmute"):
            await client.restrict_chat_member(cid, uid, RESTRICTED_PERMISSIONS)
        elif action == "unban":
            await client.unban_chat_member(cid, uid)
        elif action == "unmute":
            await client.restrict_chat_member(cid, uid, UNRESTRICTED_PERMISSIONS)

        await log_action(
            ctx,
            cid,
            aid,
            uid,
            action,
            duration=int((until - datetime.now()).total_seconds()) if until else 0,
            msg_link=message.link,
        )
        if action in ("tban", "tmute") and until:
            sec = (until - datetime.now()).total_seconds()
            await create_timed_action(ctx, cid, uid, action, until)
            SchedulerManager.schedule_timed_action(ctx, cid, uid, action, sec)
        await message.reply(
            await at(
                cid,
                f"{'t' if until and action != 'kick' else ''}{action}.success",
                mention=u.mention,
                duration=str(until - datetime.now()) if until else "",
            )
        )
    except (BadRequest, Forbidden, RPCError, FloodWait) as e:
        if isinstance(e, FloodWait):
            await asyncio.sleep(e.value + 1)
            return await _execute_restriction(client, message, u, action, p, until)
        logger.warning(f"{action} err in {cid}: {e}")
        await message.reply(
            await at(
                cid,
                "error.unauthorized_admin" if "admin" in str(e).lower() else "error.bot_not_admin",
            )
        )


@bot.on_message(filters.command(["ban", "unban", "kick", "mute", "unmute"]) & filters.group)
@safe_handler
@admin_only
@resolve_target
async def ban_mute_kick_handler(client: Client, message: Message, target_user: User) -> None:
    cmd = message.command[0]
    p = Permission.CAN_BAN if "ban" in cmd else Permission.CAN_RESTRICT
    await _execute_restriction(
        client,
        message,
        target_user,
        cmd,
        p,
        (datetime.now() + dt_module.timedelta(minutes=1)) if cmd == "kick" else None,
    )


@bot.on_message(filters.command(["tban", "tmute"]) & filters.group)
@safe_handler
@admin_only
@resolve_target
async def timed_restriction_handler(client: Client, message: Message, target_user: User) -> None:
    cmd = message.command[0]
    off = 1 if message.reply_to_message else 2
    sec = parse_time(message.command[off]) if len(message.command) > off else 0
    if sec <= 0:
        return
    p = Permission.CAN_BAN if "ban" in cmd else Permission.CAN_RESTRICT
    await _execute_restriction(
        client, message, target_user, cmd[1:], p, datetime.now() + dt_module.timedelta(seconds=sec)
    )


register(BansPlugin())
