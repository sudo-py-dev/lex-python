import datetime as dt_module
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.plugins.scheduler.service import schedule_timed_action
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    Permission,
    has_permission,
)
from src.utils.time_parser import parse_time

from . import get_ctx
from .repository import create_timed_action, log_action


@bot.on_message(filters.command("ban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def ban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    try:
        await client.ban_chat_member(message.chat.id, target_user.id)
        await log_action(
            get_ctx(),
            message.chat.id,
            message.from_user.id,
            target_user.id,
            "ban",
            msg_link=message.link,
        )
        await message.reply(await at(message.chat.id, "ban.success", mention=target_user.mention))
    except Exception:
        pass


@bot.on_message(filters.command("unban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    try:
        await client.unban_chat_member(message.chat.id, target_user.id)
        await log_action(get_ctx(), message.chat.id, message.from_user.id, target_user.id, "unban")
        await message.reply(
            await at(message.chat.id, "ban.unban_success", mention=target_user.mention)
        )
    except Exception:
        pass


@bot.on_message(filters.command("kick") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def kick_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    try:
        await client.ban_chat_member(message.chat.id, target_user.id)
        await client.unban_chat_member(message.chat.id, target_user.id)
        await log_action(get_ctx(), message.chat.id, message.from_user.id, target_user.id, "kick")
        await message.reply(await at(message.chat.id, "kick.success", mention=target_user.mention))
    except Exception:
        pass


@bot.on_message(filters.command("mute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def mute_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    try:
        await client.restrict_chat_member(message.chat.id, target_user.id, RESTRICTED_PERMISSIONS)
        await log_action(get_ctx(), message.chat.id, message.from_user.id, target_user.id, "mute")
        await message.reply(await at(message.chat.id, "mute.success", mention=target_user.mention))
    except Exception:
        pass


@bot.on_message(filters.command("unmute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unmute_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    try:
        await client.restrict_chat_member(
            message.chat.id,
            target_user.id,
            UNRESTRICTED_PERMISSIONS,
        )
        await log_action(get_ctx(), message.chat.id, message.from_user.id, target_user.id, "unmute")
        await message.reply(
            await at(message.chat.id, "mute.unmute_success", mention=target_user.mention)
        )
    except Exception:
        pass


@bot.on_message(filters.command("tban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def tban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    delay_str = "0"
    if message.reply_to_message and len(message.command) > 1:
        delay_str = message.command[1]
    elif len(message.command) > 2:
        delay_str = message.command[2]

    delay_seconds = parse_time(delay_str)
    if delay_seconds <= 0:
        return

    try:
        await client.ban_chat_member(message.chat.id, target_user.id)
        expires_at = datetime.now(dt_module.UTC) + dt_module.timedelta(seconds=delay_seconds)
        ctx = get_ctx()
        await log_action(
            ctx,
            message.chat.id,
            message.from_user.id,
            target_user.id,
            "tban",
            duration=int(delay_seconds),
            msg_link=message.link,
        )
        await create_timed_action(ctx, message.chat.id, target_user.id, "tban", expires_at)
        schedule_timed_action(ctx, message.chat.id, target_user.id, "tban", delay_seconds)
        await message.reply(
            await at(
                message.chat.id, "tban.success", mention=target_user.mention, duration=delay_str
            )
        )
    except Exception:
        pass


@bot.on_message(filters.command("tmute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def tmute_handler(client: Client, message: Message, target_user: User) -> None:
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    delay_str = "0"
    if message.reply_to_message and len(message.command) > 1:
        delay_str = message.command[1]
    elif len(message.command) > 2:
        delay_str = message.command[2]

    delay_seconds = parse_time(delay_str)
    if delay_seconds <= 0:
        return

    try:
        await client.restrict_chat_member(message.chat.id, target_user.id, RESTRICTED_PERMISSIONS)
        expires_at = datetime.now(dt_module.UTC) + dt_module.timedelta(seconds=delay_seconds)
        ctx = get_ctx()
        await log_action(
            ctx,
            message.chat.id,
            message.from_user.id,
            target_user.id,
            "tmute",
            duration=int(delay_seconds),
            msg_link=message.link,
        )
        await create_timed_action(ctx, message.chat.id, target_user.id, "tmute", expires_at)
        schedule_timed_action(ctx, message.chat.id, target_user.id, "tmute", delay_seconds)
        await message.reply(
            await at(
                message.chat.id, "tmute.success", mention=target_user.mention, duration=delay_str
            )
        )
    except Exception:
        pass
