import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.redis import get_redis
from src.core.bot import bot
from src.core.constants import RedisKeys
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.permissions import is_admin
from src.utils.time_parser import parse_time

from . import get_ctx
from .repository import clear_slowmode, get_slowmode, set_slowmode


@bot.on_message(filters.command("slowmode") & filters.group)
@safe_handler
@admin_only
async def slowmode_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        interval = await get_slowmode(get_ctx(), message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.current", duration=f"{interval}s"))
        return

    duration_str = message.command[1].lower()
    if duration_str in ("off", "none", "0"):
        await clear_slowmode(get_ctx(), message.chat.id)
        await message.reply(await at(message.chat.id, "slowmode.off"))
        return

    interval = int(parse_time(duration_str))
    if interval <= 0:
        return

    await set_slowmode(get_ctx(), message.chat.id, interval)
    await message.reply(await at(message.chat.id, "slowmode.set", duration=f"{interval}s"))


@bot.on_message(filters.group, group=8)
@safe_handler
async def slowmode_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.command:
        return

    ctx = get_ctx()
    interval = await get_slowmode(ctx, message.chat.id)
    if interval <= 0:
        return

    if await is_admin(client, message.chat.id, message.from_user.id):
        return

    r = get_redis()
    key = RedisKeys.slowmode(message.chat.id, message.from_user.id)

    if await r.get(key):
        with contextlib.suppress(Exception):
            await message.delete()
    else:
        await r.set(key, "1", ex=interval)
