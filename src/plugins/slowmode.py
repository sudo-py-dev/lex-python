import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.slowmode import clear_slowmode, get_slowmode, set_slowmode
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.moderation import resolve_sender
from src.utils.time_parser import parse_time


class SlowmodePlugin(Plugin):
    """Plugin to manage message frequency for non-admin users."""

    name = "slowmode"
    priority = 80

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("slowmode") & filters.group)
@safe_handler
@admin_only
async def slowmode_handler(client: Client, message: Message) -> None:
    """Toggle or set slowmode interval for the current chat."""
    ctx = get_context()
    if len(message.command) < 2:
        interval = await get_slowmode(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.current", duration=f"{interval}s"))
        return

    duration_str = message.command[1].lower()
    if duration_str in ("off", "none", "0"):
        await clear_slowmode(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.off"))
        return

    interval = int(parse_time(duration_str))
    if interval <= 0:
        return

    await set_slowmode(ctx, message.chat.id, interval)
    await message.reply(await at(message.chat.id, "slowmode.set", duration=f"{interval}s"))


@bot.on_message(filters.group, group=8)
@safe_handler
async def slowmode_interceptor(client: Client, message: Message) -> None:
    """Intercept messages and enforce slowmode if enabled."""
    if getattr(message, "command", None):
        return

    user_id, _, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    interval = await get_slowmode(ctx, message.chat.id)
    if interval <= 0:
        return

    key = CacheKeys.slowmode(message.chat.id, user_id)

    if await ctx.cache.get(key):
        with contextlib.suppress(Exception):
            await message.delete()
        await message.stop_propagation()
    else:
        await ctx.cache.set(key, "1", ttl=interval)


register(SlowmodePlugin())
