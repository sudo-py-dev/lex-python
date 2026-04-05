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
    """Set the user's AFK status with an optional reason."""
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


@bot.on_message(filters.group, group=7)
@safe_handler
async def afk_interceptor(client: Client, message: Message) -> None:
    """Intercept messages to detect users returning from AFK or mentioning AFK users."""
    if not message.from_user or getattr(message, "command", None):
        return

    ctx = get_context()
    user_id = message.from_user.id

    # Check if the sender is returning from AFK
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

    # Check for mentions of AFK users
    if message.entities:
        for ent in message.entities:
            target_id = None
            if ent.type == enums.MessageEntityType.TEXT_MENTION:
                target_id = ent.user.id
            elif ent.type == enums.MessageEntityType.MENTION:
                username = message.text[ent.offset : ent.offset + ent.length].lstrip("@")
                target_id_raw = await ctx.cache.get(CacheKeys.afk_username(username))
                if target_id_raw:
                    target_id = int(target_id_raw)

            if target_id:
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
