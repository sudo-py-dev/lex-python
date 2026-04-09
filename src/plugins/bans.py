import asyncio
import datetime as dt_module
from datetime import datetime

from loguru import logger
from pyrogram import Client, filters
from pyrogram.errors import (
    BadRequest,
    ChatAdminRequired,
    FloodWait,
    Forbidden,
    RPCError,
    UserNotParticipant,
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


@bot.on_message(filters.command("ban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def ban_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Permanently ban a user from the current chat.

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be banned (resolved by @resolve_target).

    Side Effects:
        - Bans the target user from the chat.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
    if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
    try:
        await client.ban_chat_member(message.chat.id, target_user.id)
        await log_action(
            ctx,
            message.chat.id,
            message.from_user.id,
            target_user.id,
            "ban",
            msg_link=message.link,
        )
        await message.reply(await at(message.chat.id, "ban.success", mention=target_user.mention))
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except UserNotParticipant:
        await message.reply(await at(message.chat.id, "error.user_not_found"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await ban_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Ban error in {message.chat.id}: {e}")
        await message.reply(await at(message.chat.id, "error.unauthorized_admin"))
    except Exception as e:
        logger.exception(f"Unexpected ban error: {e}")


@bot.on_message(filters.command("unban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unban_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Unban a previously banned user and allow them to rejoin.

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be unbanned (resolved by @resolve_target).

    Side Effects:
        - Unbans the target user from the chat.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
    if not await has_permission(client, message.chat.id, Permission.CAN_BAN):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
    try:
        await client.unban_chat_member(message.chat.id, target_user.id)
        await log_action(ctx, message.chat.id, message.from_user.id, target_user.id, "unban")
        await message.reply(
            await at(message.chat.id, "ban.unban_success", mention=target_user.mention)
        )
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await unban_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Unban error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected unban error: {e}")


@bot.on_message(filters.command("kick") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def kick_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Remove a user from the current chat. The user can rejoin immediately via link.

    Implemented by banning the user for 60 seconds.
    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be kicked (resolved by @resolve_target).

    Side Effects:
        - Temporarily bans (kicks) the target user from the chat.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
    try:
        await client.ban_chat_member(
            message.chat.id,
            target_user.id,
            until_date=datetime.now() + dt_module.timedelta(minutes=1),
        )
        await log_action(ctx, message.chat.id, message.from_user.id, target_user.id, "kick")
        await message.reply(await at(message.chat.id, "kick.success", mention=target_user.mention))
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except UserNotParticipant:
        await message.reply(await at(message.chat.id, "error.user_not_found"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await kick_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Kick error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected kick error: {e}")


@bot.on_message(filters.command("mute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def mute_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Restrict a user from sending any messages in the current chat.

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be muted (resolved by @resolve_target).

    Side Effects:
        - Restricts the target user's chat permissions.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
    try:
        await client.restrict_chat_member(message.chat.id, target_user.id, RESTRICTED_PERMISSIONS)
        await log_action(ctx, message.chat.id, message.from_user.id, target_user.id, "mute")
        await message.reply(await at(message.chat.id, "mute.success", mention=target_user.mention))
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except UserNotParticipant:
        await message.reply(await at(message.chat.id, "error.user_not_found"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await mute_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Mute error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected mute error: {e}")


@bot.on_message(filters.command("unmute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def unmute_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Allow a previously muted user to send messages again by restoring full permissions.

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be unmuted (resolved by @resolve_target).

    Side Effects:
        - Restores the target user's chat permissions.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
    if not await has_permission(client, message.chat.id, Permission.CAN_RESTRICT):
        await message.reply(await at(message.chat.id, "error.no_permission"))
        return

    ctx = get_context()
    try:
        await client.restrict_chat_member(
            message.chat.id,
            target_user.id,
            UNRESTRICTED_PERMISSIONS,
        )
        await log_action(ctx, message.chat.id, message.from_user.id, target_user.id, "unmute")
        await message.reply(
            await at(message.chat.id, "mute.unmute_success", mention=target_user.mention)
        )
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await unmute_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Unmute error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected unmute error: {e}")


@bot.on_message(filters.command("tban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def tban_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Temporarily ban a user for a specific duration (e.g., 1h, 1d).

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.
    The duration is automatically parsed and scheduled for unbanning.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be temporarily banned (resolved by @resolve_target).

    Side Effects:
        - Bans the target user from the chat.
        - Schedules an unban task in the database and SchedulerManager.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
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

    ctx = get_context()
    try:
        await client.ban_chat_member(message.chat.id, target_user.id)
        expires_at = datetime.now(dt_module.UTC) + dt_module.timedelta(seconds=delay_seconds)
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
        SchedulerManager.schedule_timed_action(
            ctx, message.chat.id, target_user.id, "tban", delay_seconds
        )
        await message.reply(
            await at(
                message.chat.id, "tban.success", mention=target_user.mention, duration=delay_str
            )
        )
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except UserNotParticipant:
        await message.reply(await at(message.chat.id, "error.user_not_found"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await tban_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Tban error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected tban error: {e}")


@bot.on_message(filters.command("tmute") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def tmute_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Temporarily mute a user for a specific duration (e.g., 30m, 12h).

    Requires the bot to have 'can_restrict_members' permission and the user to be an admin.
    The duration is automatically parsed and scheduled for unmuting.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be temporarily muted (resolved by @resolve_target).

    Side Effects:
        - Restricts the target user's chat permissions.
        - Schedules an unmute task in the database and SchedulerManager.
        - Logs the action in the database.
        - Sends a confirmation message.
    """
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

    ctx = get_context()
    try:
        await client.restrict_chat_member(message.chat.id, target_user.id, RESTRICTED_PERMISSIONS)
        expires_at = datetime.now(dt_module.UTC) + dt_module.timedelta(seconds=delay_seconds)
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
        SchedulerManager.schedule_timed_action(
            ctx, message.chat.id, target_user.id, "tmute", delay_seconds
        )
        await message.reply(
            await at(
                message.chat.id, "tmute.success", mention=target_user.mention, duration=delay_str
            )
        )
    except ChatAdminRequired:
        await message.reply(await at(message.chat.id, "error.bot_not_admin"))
    except UserNotParticipant:
        await message.reply(await at(message.chat.id, "error.user_not_found"))
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await tmute_handler(client, message, target_user)
    except (BadRequest, Forbidden, RPCError) as e:
        logger.warning(f"Tmute error in {message.chat.id}: {e}")
    except Exception as e:
        logger.exception(f"Unexpected tmute error: {e}")


register(BansPlugin())
