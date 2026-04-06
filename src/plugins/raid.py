from pyrogram import Client, filters
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings, update_settings
from src.plugins.logging import log_event
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.permissions import RESTRICTED_PERMISSIONS


class RaidPlugin(Plugin):
    name = "raid"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("raid") & filters.group)
@safe_handler
@admin_only
async def raid_handler(client: Client, message: Message) -> None:
    if not message.from_user or len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")

    ctx = get_context()
    await update_settings(ctx, message.chat.id, raidEnabled=mode)
    await message.reply(await at(message.chat.id, f"raid.{'enabled' if mode else 'disabled'}"))


@bot.on_message(filters.group & filters.new_chat_members, group=11)
@safe_handler
async def raid_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.from_user.is_bot:
        return

    ctx = get_context()
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
            await log_event(
                ctx,
                client,
                message.chat.id,
                "raid_lock",
                "Group",
                client.me,
                reason=await at(
                    message.chat.id,
                    "logging.raid_reason",
                    threshold=settings.raidThreshold,
                    window=settings.raidWindow,
                ),
                chat_title=message.chat.title,
            )

        await message.reply(await at(message.chat.id, "raid.detected"))


register(RaidPlugin())
