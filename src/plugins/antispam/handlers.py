import contextlib
import hashlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.utils.decorators import safe_handler
from src.utils.permissions import is_admin


@bot.on_message(filters.group & filters.text, group=5)
@safe_handler
async def antispam_handler(client: Client, message: Message) -> None:
    if not message.text or not message.from_user or message.command:
        return

    if await is_admin(client, message.chat.id, message.from_user.id):
        return

    r = get_cache()
    text_hash = hashlib.md5(message.text.encode()).hexdigest()
    key = f"antispam:{message.chat.id}:{message.from_user.id}"

    last_hash = await r.get(key)
    if last_hash and last_hash == text_hash:
        with contextlib.suppress(Exception):
            await message.delete()
    else:
        await r.set(key, text_hash, ttl=60)
