import contextlib
import hashlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.permissions import is_admin


class AntispamPlugin(Plugin):
    """Plugin to detect and delete duplicate text messages from the same user."""

    name = "antispam"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & filters.text, group=5)
@safe_handler
async def antispam_handler(client: Client, message: Message) -> None:
    """Detect duplicate text and delete if user is spamming within a short window."""
    if (
        not message.text
        or not message.from_user
        or message.from_user.is_bot
        or getattr(message, "command", None)
    ):
        return

    if await is_admin(client, message.chat.id, message.from_user.id):
        return

    ctx = get_context()
    text_hash = hashlib.md5(message.text.encode()).hexdigest()
    key = CacheKeys.antispam(message.chat.id, message.from_user.id)

    last_hash = await ctx.cache.get(key)
    if last_hash and last_hash == text_hash:
        with contextlib.suppress(Exception):
            await message.delete()
    else:
        await ctx.cache.set(key, text_hash, ttl=60)


register(AntispamPlugin())
