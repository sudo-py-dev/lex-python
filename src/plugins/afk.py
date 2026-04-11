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
    if not message.from_user:
        return
    ctx, r = get_context(), " ".join(message.command[1:]) if len(message.command) > 1 else ""
    uid, name = message.from_user.id, message.from_user.first_name
    await ctx.cache.set(
        CacheKeys.afk(uid), json.dumps({"time": time.time(), "reason": r, "name": name}), ttl=604800
    )
    if message.from_user.username:
        await ctx.cache.set(
            CacheKeys.afk_username(message.from_user.username), str(uid), ttl=604800
        )
    await message.reply(
        await at(message.chat.id, "afk.set", name=name, reason=f": {r}" if r else "")
    )


@bot.on_message(filters.group, group=30)
@safe_handler
async def afk_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return
    ctx, uid = get_context(), message.from_user.id
    if raw := await ctx.cache.get(CacheKeys.afk(uid)):
        data = json.loads(raw)
        dt = int(time.time() - data["time"])
        await ctx.cache.delete(CacheKeys.afk(uid))
        if message.from_user.username:
            await ctx.cache.delete(CacheKeys.afk_username(message.from_user.username))
        await message.reply(
            await at(
                message.chat.id,
                "afk.returned",
                name=message.from_user.first_name,
                duration=f"{dt // 60}m" if dt >= 60 else f"{dt}s",
            )
        )

    ents = message.entities or message.caption_entities
    if not ents:
        return
    txt, seen = message.text or message.caption or "", set()
    for e in ents:
        tid = None
        if e.type == enums.MessageEntityType.TEXT_MENTION:
            tid = e.user.id
        elif e.type == enums.MessageEntityType.MENTION and (
            uid_raw := await ctx.cache.get(
                CacheKeys.afk_username(txt[e.offset : e.offset + e.length].lstrip("@"))
            )
        ):
            tid = int(uid_raw)
        if tid and tid not in seen:
            seen.add(tid)
            if raw := await ctx.cache.get(CacheKeys.afk(tid)):
                d = json.loads(raw)
                await message.reply(
                    await at(message.chat.id, "afk.mention", name=d["name"], reason=d["reason"])
                )


register(AFKPlugin())
