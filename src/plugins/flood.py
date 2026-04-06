import contextlib
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.actions import log_action
from src.db.repositories.group_settings import get_settings, update_settings
from src.plugins.logging import log_event
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.moderation import resolve_sender
from src.utils.permissions import RESTRICTED_PERMISSIONS, can_restrict_members


class FloodPlugin(Plugin):
    """Plugin to detect and mitigate message flooding from users."""

    name = "flood"
    priority = 30

    async def setup(self, client: Client, ctx) -> None:
        pass


async def increment_flood(ctx, chat_id: int, user_id: int, window: int) -> int:
    """Increment the flood count for a user in a specific chat."""
    key = CacheKeys.flood(chat_id, user_id)
    count = await ctx.cache.incr(key)
    if count == 1:
        await ctx.cache.expire(key, window)
    return count


async def reset_flood(ctx, chat_id: int, user_id: int) -> None:
    """Reset the flood count for a user."""
    await ctx.cache.delete(CacheKeys.flood(chat_id, user_id))


@bot.on_message(filters.command("setflood") & filters.group)
@safe_handler
@admin_only
async def set_flood_handler(client: Client, message: Message) -> None:
    """Configure flood protection settings for the current group."""
    if len(message.command) < 4:
        return

    try:
        threshold = int(message.command[1])
        window = int(message.command[2])
    except ValueError:
        return

    action = message.command[3].lower()
    if action not in ("mute", "kick", "ban"):
        return

    ctx = get_context()
    await update_settings(
        ctx, message.chat.id, floodThreshold=threshold, floodWindow=window, floodAction=action
    )

    await message.reply(
        await at(message.chat.id, "flood.set", threshold=threshold, window=window, action=action)
    )


@bot.on_message(filters.group, group=-2)
@safe_handler
async def flood_interceptor(client: Client, message: Message) -> None:
    """Intercept messages and enforce flood protection."""
    if getattr(message, "command", None):
        return

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    try:
        settings = await get_settings(ctx, message.chat.id)
    except Exception:
        return

    if settings.floodThreshold <= 0:
        return

    count = await increment_flood(ctx, message.chat.id, user_id, settings.floodWindow)
    if count == settings.floodThreshold + 1:
        if not await can_restrict_members(client, message.chat.id):
            return

        action = settings.floodAction.lower()
        try:
            if action == "ban":
                await client.ban_chat_member(message.chat.id, user_id)
            elif action == "kick":
                await client.ban_chat_member(
                    message.chat.id,
                    user_id,
                    until_date=datetime.now() + timedelta(minutes=1),
                )
            else:
                await client.restrict_chat_member(message.chat.id, user_id, RESTRICTED_PERMISSIONS)

            await message.reply(
                await at(
                    message.chat.id,
                    "flood.triggered",
                    mention=mention,
                    action=action,
                )
            )

            await log_action(ctx, message.chat.id, client.me.id, user_id, f"flood_{action}")
            await log_event(
                ctx,
                client,
                message.chat.id,
                f"flood_{action}",
                user_id,
                client.me,
                reason=await at(
                    message.chat.id,
                    "logging.flood_reason",
                    threshold=settings.floodThreshold,
                    window=settings.floodWindow,
                ),
                chat_title=message.chat.title,
            )
        except Exception:
            pass

    if count > settings.floodThreshold:
        with contextlib.suppress(Exception):
            await message.delete()


register(FloodPlugin())
