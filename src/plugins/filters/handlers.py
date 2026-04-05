import re

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import add_filter, get_all_filters, remove_filter


@bot.on_message(filters.command("filter") & filters.group)
@safe_handler
@admin_only
async def filter_add_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return

    keyword = message.command[1].lower()
    response_data = ""
    response_type = "text"

    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.text:
            response_data = reply.text
            response_type = "text"
        elif reply.sticker:
            response_data = reply.sticker.file_id
            response_type = "sticker"
        elif reply.photo:
            response_data = reply.photo.file_id
            response_type = "photo"
        elif reply.video:
            response_data = reply.video.file_id
            response_type = "video"
        elif reply.document:
            response_data = reply.document.file_id
            response_type = "document"
        elif reply.animation:
            response_data = reply.animation.file_id
            response_type = "gif"
    else:
        if len(message.command) < 3:
            return
        response_data = message.text.split(None, 2)[2]
        response_type = "text"

    await add_filter(get_ctx(), message.chat.id, keyword, response_data, response_type)
    await message.reply(await at(message.chat.id, "filter.added", keyword=keyword))


@bot.on_message(filters.command(["stopfilter", "stop"]) & filters.group)
@safe_handler
@admin_only
async def filter_stop_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    keyword = message.command[1].lower()
    success = await remove_filter(get_ctx(), message.chat.id, keyword)
    if success:
        await message.reply(await at(message.chat.id, "filter.removed", keyword=keyword))
    else:
        await message.reply(await at(message.chat.id, "filter.not_found", keyword=keyword))


@bot.on_message(filters.command("filters") & filters.group)
@safe_handler
async def filters_list_handler(client: Client, message: Message) -> None:
    all_filters = await get_all_filters(get_ctx(), message.chat.id)
    if not all_filters:
        await message.reply(await at(message.chat.id, "filter.list_empty"))
        return

    text = await at(message.chat.id, "filter.list_header")
    for f in all_filters:
        text += f"\n• `{f.keyword}` ({f.responseType})"
    await message.reply(text)


@bot.on_message(filters.group & filters.text, group=1)
@safe_handler
async def filter_interceptor(client: Client, message: Message) -> None:
    if not message.text or message.command:
        return

    all_filters = await get_all_filters(get_ctx(), message.chat.id)
    if not all_filters:
        return

    text = message.text.lower()
    for f in all_filters:
        keyword = f.keyword.lower()
        match = False

        if (
            f.matchMode == "exact"
            and text == keyword
            or f.matchMode == "contains"
            and keyword in text
        ):
            match = True
        elif f.matchMode == "regex":
            try:
                flags = 0 if f.caseSensitive else re.IGNORECASE
                if re.search(f.keyword, message.text, flags):
                    match = True
            except Exception:
                pass

        if match:
            if f.responseType == "text":
                await message.reply(f.responseData)
            elif f.responseType == "sticker":
                await message.reply_sticker(f.responseData)
            elif f.responseType == "photo":
                await message.reply_photo(f.responseData)
            elif f.responseType == "video":
                await message.reply_video(f.responseData)
            elif f.responseType == "document":
                await message.reply_document(f.responseData)
            elif f.responseType == "gif":
                await message.reply_animation(f.responseData)
            break
