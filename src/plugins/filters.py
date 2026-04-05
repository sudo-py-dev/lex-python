import re

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.filters import (
    add_filter,
    get_all_filters,
    get_filters_for_chat,
    remove_filter,
)
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class FiltersPlugin(Plugin):
    """Plugin to manage custom auto-replies (filters) in groups."""

    name = "filters"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("filter") & filters.group)
@safe_handler
@admin_only
async def add_filter_handler(client: Client, message: Message) -> None:
    """Add a new auto-reply filter to the current group."""
    if len(message.command) < 3:
        return

    ctx = get_context()
    keyword = message.command[1].lower()
    response = message.text.split(None, 2)[2]

    await add_filter(ctx, message.chat.id, keyword, response)
    await message.reply(await at(message.chat.id, "filter.added", keyword=keyword))


@bot.on_message(filters.command("stop") & filters.group)
@safe_handler
@admin_only
async def stop_filter_handler(client: Client, message: Message) -> None:
    """Remove a previously added filter from the current group."""
    if len(message.command) < 2:
        return

    ctx = get_context()
    keyword = message.command[1].lower()
    success = await remove_filter(ctx, message.chat.id, keyword)
    if success:
        await message.reply(await at(message.chat.id, "filter.removed", keyword=keyword))
    else:
        await message.reply(await at(message.chat.id, "filter.not_found"))


@bot.on_message(filters.command("filters") & filters.group)
@safe_handler
async def list_filters_handler(client: Client, message: Message) -> None:
    """List all active filters for the current group."""
    ctx = get_context()
    all_filters = await get_all_filters(ctx, message.chat.id)
    if not all_filters:
        await message.reply(await at(message.chat.id, "filter.list_empty"))
        return

    text = await at(message.chat.id, "filter.list_header")
    for f in all_filters:
        text += f"\n• `{f.keyword}`"
    await message.reply(text)


@bot.on_message(filters.group & filters.text, group=4)
@safe_handler
async def filters_interceptor(client: Client, message: Message) -> None:
    """Intercept messages and check if any filter keywords are triggered."""
    if not message.text or getattr(message, "command", None):
        return

    ctx = get_context()
    all_filters = await get_filters_for_chat(ctx, message.chat.id)
    if not all_filters:
        return

    text = message.text.lower()
    for f in all_filters:
        pattern = rf"\b{re.escape(f.keyword)}\b"
        if re.search(pattern, text):
            await message.reply(f.responseData)
            break


register(FiltersPlugin())
