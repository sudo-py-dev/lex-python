import json
import time

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from src.cache.redis import get_redis
from src.core.bot import bot
from src.core.constants import RedisKeys
from src.utils.decorators import safe_handler
from src.utils.i18n import at


@bot.on_message(filters.command("afk") & filters.group)
@safe_handler
async def afk_handler(client: Client, message: Message) -> None:
    reason = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    user_id = message.from_user.id

    r = get_redis()
    afk_data = {"time": time.time(), "reason": reason, "name": message.from_user.first_name}

    await r.set(RedisKeys.afk(user_id), json.dumps(afk_data), ex=604800)
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
    if not message.from_user or message.command:
        return

    r = get_redis()
    user_id = message.from_user.id

    afk_key = RedisKeys.afk(user_id)
    afk_raw = await r.get(afk_key)
    if afk_raw:
        afk_data = json.loads(afk_raw)
        duration = int(time.time() - afk_data["time"])
        d_str = f"{duration // 60}m" if duration >= 60 else f"{duration}s"

        await r.delete(afk_key)
        await message.reply(
            await at(
                message.chat.id, "afk.returned", name=message.from_user.first_name, duration=d_str
            )
        )

    if message.entities:
        for ent in message.entities:
            user_id = None
            if ent.type == enums.MessageEntityType.TEXT_MENTION:
                user_id = ent.user.id

            if user_id:
                afk_raw = await r.get(RedisKeys.afk(user_id))
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
