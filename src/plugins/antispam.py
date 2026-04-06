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


@bot.on_message(filters.group & filters.text, group=3)
@safe_handler
async def antispam_handler(client: Client, message: Message) -> None:
    """
    Detect duplicate text messages from a user and delete them if they occur within a short window.

    Calculates an MD5 hash of the message text and compares it with the last
    sent message hash stored in the cache for that user in the specific chat.
    If it matches, the message is deleted and propagation is stopped.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Deletes the duplicate message.
        - Stops message propagation to other handlers.
        - Updates the user's last message hash in the cache (TTL: 60s).
    """
    if not message.text or getattr(message, "command", None):
        return

    user_id, _, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    text_hash = hashlib.md5(message.text.encode()).hexdigest()
    key = CacheKeys.antispam(message.chat.id, user_id)

    last_hash = await ctx.cache.get(key)
    if last_hash and last_hash == text_hash:
        with contextlib.suppress(Exception):
            await message.delete()
        await message.stop_propagation()
    else:
        await ctx.cache.set(key, text_hash, ttl=60)


register(AntispamPlugin())
