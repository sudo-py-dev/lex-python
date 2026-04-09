import json
import time

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.constants import CacheKeys
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class AFKPlugin(Plugin):
    """Plugin to manage user AFK (Away From Keyboard) status."""

    name = "afk"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("afk") & filters.group)
@safe_handler
async def afk_handler(client: Client, message: Message) -> None:
    """
    Set the user's AFK (Away From Keyboard) status with an optional reason.

    Stores the AFK timestamp, reason, and user's first name in the cache. Also
    maps the username to the user ID for mention detection.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Sets multiple keys in the cache (AFK data and username mapping).
        - Sends a confirmation message that the user is now AFK.
    """
    if not message.from_user:
        return

    ctx = get_context()
    reason = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    user_id = message.from_user.id

    afk_data = {
        "time": time.time(),
        "reason": reason,
        "name": message.from_user.first_name,
    }

    await ctx.cache.set(CacheKeys.afk(user_id), json.dumps(afk_data), ttl=604800)
    if message.from_user.username:
        await ctx.cache.set(
            CacheKeys.afk_username(message.from_user.username), str(user_id), ttl=604800
        )

    await message.reply(
        await at(
            message.chat.id,
            "afk.set",
            name=message.from_user.first_name,
            reason=f": {reason}" if reason else "",
        )
    )


@bot.on_message(filters.group, group=30)
@safe_handler
async def afk_interceptor(client: Client, message: Message) -> None:
    """
    Intercept all group messages to detect user returns from AFK and mentions of AFK users.

    If the sender was AFK, it clears their AFK status and notifies the group.
    If the message mentions an AFK user (via text mention or @username), it
    replies with that user's AFK reason and duration.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Clears AFK keys from the cache when a user returns.
        - Sends a 'returned' message when an AFK user speaks.
        - Sends a 'mention' message when an AFK user is tagged.
    """
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return

    ctx = get_context()
    user_id = message.from_user.id

    afk_key = CacheKeys.afk(user_id)
    afk_raw = await ctx.cache.get(afk_key)
    if afk_raw:
        afk_data = json.loads(afk_raw)
        duration = int(time.time() - afk_data["time"])
        d_str = f"{duration // 60}m" if duration >= 60 else f"{duration}s"

        await ctx.cache.delete(afk_key)
        if message.from_user.username:
            await ctx.cache.delete(CacheKeys.afk_username(message.from_user.username))

        await message.reply(
            await at(
                message.chat.id, "afk.returned", name=message.from_user.first_name, duration=d_str
            )
        )

    entities = message.entities or message.caption_entities
    if entities:
        text = message.text or message.caption or ""
        mentioned_ids = set()

        for ent in entities:
            target_id = None
            if ent.type == enums.MessageEntityType.TEXT_MENTION:
                target_id = ent.user.id
            elif ent.type == enums.MessageEntityType.MENTION:
                username = text[ent.offset : ent.offset + ent.length].lstrip("@")
                target_id_raw = await ctx.cache.get(CacheKeys.afk_username(username))
                if target_id_raw:
                    target_id = int(target_id_raw)

            if target_id and target_id not in mentioned_ids:
                mentioned_ids.add(target_id)
                afk_raw = await ctx.cache.get(CacheKeys.afk(target_id))
                if afk_raw:
                    afk_data = json.loads(afk_raw)
                    await message.reply(
                        await at(
                            message.chat.id,
                            "afk.mention",
                            name=afk_data["name"],
                            reason=afk_data["reason"],
                        )
                    )


register(AFKPlugin())
