import contextlib
import hashlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.moderation import resolve_sender


class AntispamPlugin(Plugin):
    """Plugin to detect and delete duplicate text messages from the same user."""

    name = "antispam"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & filters.text, group=-30)
@safe_handler
async def antispam_handler(client: Client, message: Message) -> None:
    if not message.text or getattr(message, "command", None):
        return
    uid, _, white = await resolve_sender(client, message)
    if not uid or white:
        return
    ctx, h, k = (
        get_context(),
        hashlib.md5(message.text.encode()).hexdigest(),
        CacheKeys.antispam(message.chat.id, uid),
    )
    if (await ctx.cache.get(k)) == h:
        with contextlib.suppress(Exception):
            await message.delete()
        await message.stop_propagation()
    else:
        await ctx.cache.set(k, h, ttl=60)


register(AntispamPlugin())
