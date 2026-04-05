from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings, update_settings
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Raid plugin not initialized")
    return _ctx


class RaidPlugin(Plugin):
    name = "raid"
    priority = 100

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx


@bot.on_message(filters.command("raid") & filters.group)
@safe_handler
@admin_only
async def raid_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")

    await update_settings(get_ctx(), message.chat.id, raidEnabled=mode)
    await message.reply(await at(message.chat.id, f"raid.{'enabled' if mode else 'disabled'}"))


@bot.on_message(filters.group & filters.new_chat_members, group=11)
@safe_handler
async def raid_interceptor(client: Client, message: Message) -> None:
    ctx = get_ctx()
    settings = await get_settings(ctx, message.chat.id)
    if not settings.raidEnabled:
        return

    r = get_cache()
    key = f"raid_joins:{message.chat.id}"

    count = await r.incr(key)
    if count == 1:
        await r.expire(key, settings.raidWindow)

    if count >= settings.raidThreshold:
        if settings.raidAction == "lock":
            await client.set_chat_permissions(message.chat.id, RESTRICTED_PERMISSIONS)

        await message.reply(await at(message.chat.id, "raid.detected"))


register(RaidPlugin())
