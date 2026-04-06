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
    remove_all_filters,
    remove_filter,
)
from src.utils.decorators import admin_only, safe_handler
from src.utils.formatters import TelegramFormatter
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

    text_after_cmd = message.text.split(None, 1)[1]
    if text_after_cmd.startswith('"') or text_after_cmd.startswith("'"):
        quote_char = text_after_cmd[0]
        end_idx = text_after_cmd.find(quote_char, 1)
        if end_idx != -1:
            keyword = text_after_cmd[1:end_idx].lower()
            response = text_after_cmd[end_idx+1:].strip()
        else:
            keyword = message.command[1].lower()
            response = message.text.split(None, 2)[2]
    else:
        keyword = message.command[1].lower()
        response = message.text.split(None, 2)[2]

    if not response:
        return

    ctx = get_context()
    await add_filter(ctx, message.chat.id, keyword, response)
    await message.reply(await at(message.chat.id, "filter.added", keyword=keyword))
    await message.stop_propagation()


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
        await message.reply(await at(message.chat.id, "filter.not_found", keyword=keyword))
    await message.stop_propagation()


@bot.on_message(filters.command("stopall") & filters.group)
@safe_handler
@admin_only
async def stopall_filters_handler(client: Client, message: Message) -> None:
    """Stop ALL filters in the current chat."""
    ctx = get_context()
    count = await remove_all_filters(ctx, message.chat.id)
    if count > 0:
        await message.reply(await at(message.chat.id, "filter.stopall_done", count=count))
    else:
        await message.reply(await at(message.chat.id, "filter.stopall_empty"))
    await message.stop_propagation()


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
    await message.stop_propagation()


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
            parsed = TelegramFormatter.parse_message(
                text=f.responseData,
                user=message.from_user,
                chat_id=message.chat.id,
                chat_title=message.chat.title,
                bot_username=client.me.username
            )
            await TelegramFormatter.send_parsed(client, message.chat.id, parsed, reply_to_message_id=message.id)
            await message.stop_propagation()
            break


register(FiltersPlugin())
