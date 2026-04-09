import contextlib
import json
import re

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
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
from src.utils.input import (
    capture_next_input,
    finalize_input_capture,
    is_waiting_for_input,
)
from src.utils.permissions import is_admin
from src.utils.telegram_storage import extract_message_data


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
    if len(message.command) < 2:
        return

    text_after_cmd = message.text.split(None, 1)[1] if " " in message.text else ""
    keyword = ""
    response = ""

    if text_after_cmd.startswith('"') or text_after_cmd.startswith("'"):
        quote_char = text_after_cmd[0]
        end_idx = text_after_cmd.find(quote_char, 1)
        if end_idx != -1:
            keyword = text_after_cmd[1:end_idx].lower()
            response = text_after_cmd[end_idx + 1 :].strip()
        else:
            keyword = message.command[1].lower()
            response = message.text.split(None, 2)[2] if len(message.command) > 2 else ""
    else:
        keyword = message.command[1].lower()
        response = message.text.split(None, 2)[2] if len(message.command) > 2 else ""

    response_type = "text"
    file_id = None

    if message.reply_to_message:
        reply = message.reply_to_message

        media_obj = (
            reply.photo
            or reply.video
            or reply.document
            or reply.animation
            or reply.sticker
            or reply.audio
            or reply.voice
            or reply.video_note
        )

        if media_obj:
            file_id = getattr(media_obj, "file_id", None)
            if reply.photo:
                response_type = "photo"
            elif reply.video:
                response_type = "video"
            elif reply.document:
                response_type = "document"
            elif reply.animation:
                response_type = "animation"
            elif reply.sticker:
                response_type = "sticker"
            elif reply.audio:
                response_type = "audio"
            elif reply.voice:
                response_type = "voice"
            elif reply.video_note:
                response_type = "video_note"

            if not response:
                response = reply.caption or ""
        else:
            if not response:
                response = reply.text or ""

    if not response and not file_id:
        return

    limit = 64
    if len(keyword) > limit:
        await message.reply(await at(message.chat.id, "filter.keyword_too_long", limit=limit))
        return

    ctx = get_context()
    try:
        await add_filter(ctx, message.chat.id, keyword, response, response_type, file_id)
        await message.reply(await at(message.chat.id, "filter.added", keyword=keyword))
    except ValueError as e:
        if str(e) == "filter_limit_reached":
            await message.reply(await at(message.chat.id, "filter.limit_reached"))
        elif str(e) == "filter_already_exists":
            await message.reply(await at(message.chat.id, "filter.err_already_exists"))
        else:
            raise e


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


@bot.on_message(filters.group & filters.text, group=10)
@safe_handler
async def filters_interceptor(client: Client, message: Message) -> None:
    """Intercept messages and check if any filter keywords are triggered."""
    if not message.text or getattr(message, "command", None):
        return

    ctx = get_context()
    all_filters = await get_filters_for_chat(ctx, message.chat.id)
    if not all_filters:
        return

    text = message.text
    user_is_admin = None

    for f in all_filters:
        settings = f.settings or {}
        match_mode = settings.get("matchMode", "contains")
        case_sensitive = settings.get("caseSensitive", False)
        is_admin_only = settings.get("isAdminOnly", False)

        if is_admin_only:
            if user_is_admin is None:
                user_is_admin = await is_admin(client, message.chat.id, message.from_user.id)

            if not user_is_admin:
                continue

        kw = f.keyword if case_sensitive else f.keyword.lower()
        t = text if case_sensitive else text.lower()

        is_match = t == kw if match_mode == "full" else re.search(rf"\b{re.escape(kw)}\b", t)

        if is_match:
            parsed = TelegramFormatter.parse_message(
                text=f.text,
                user=message.from_user,
                chat_id=message.chat.id,
                chat_title=message.chat.title,
                bot_username=client.me.username,
            )

            if f.fileId:
                await TelegramFormatter.send_media_parsed(
                    client,
                    message.chat.id,
                    f.responseType,
                    f.fileId,
                    parsed,
                    reply_to_message_id=message.id,
                )
            else:
                await TelegramFormatter.send_parsed(
                    client, message.chat.id, parsed, reply_to_message_id=message.id
                )

            await message.stop_propagation()
            break


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("filterKeyword"), group=-50)
@safe_handler
async def filter_keyword_handler(client: Client, message: Message) -> None:
    state = message.input_state
    user_id = message.from_user.id
    chat_id = state["chat_id"]
    page = state["page"]
    prompt_msg_id = state["prompt_msg_id"]
    value = message.text

    keyword = str(value).lower().strip()
    if not keyword:
        await message.reply(await at(user_id, "panel.input_invalid_string"))
        return

    limit = 64
    if len(keyword) > limit:
        await message.reply(await at(user_id, "filter.keyword_too_long", limit=limit))
        return

    r = get_cache()
    await r.set(f"temp_filter_kw:{user_id}", keyword, ttl=300)

    await capture_next_input(user_id, chat_id, "filterResponse", prompt_msg_id, page)

    prompt_text = await at(user_id, "panel.input_prompt_filterResponse", keyword=keyword)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "common.btn_cancel"), callback_data=f"panel:filters:{page}"
                )
            ]
        ]
    )

    if prompt_msg_id:
        await client.edit_message_text(user_id, prompt_msg_id, prompt_text, reply_markup=kb)
    else:
        await message.reply(prompt_text, reply_markup=kb)

    with contextlib.suppress(Exception):
        await message.delete()


@bot.on_message(filters.private & is_waiting_for_input("filterResponse"), group=-50)
@safe_handler
async def filter_response_handler(client: Client, message: Message) -> None:
    state = message.input_state
    user_id = message.from_user.id
    chat_id = state["chat_id"]
    page = state["page"]
    prompt_msg_id = state["prompt_msg_id"]
    ctx = get_context()

    r = get_cache()
    keyword = await r.get(f"temp_filter_kw:{user_id}")
    if not keyword:
        return

    all_fs = await get_all_filters(ctx, chat_id)
    if keyword not in [f.keyword for f in all_fs] and len(all_fs) >= 150:
        await message.reply(await at(user_id, "filter.limit_reached"))
        await r.delete(f"temp_filter_kw:{user_id}")
        return

    data = await extract_message_data(message)
    await r.set(f"temp_filter_resp:{user_id}", json.dumps(data), ttl=600)

    settings = {"matchMode": "contains", "caseSensitive": False, "isAdminOnly": False}
    await r.set(f"temp_filter_settings:{user_id}", json.dumps(settings), ttl=600)

    from src.plugins.admin_panel.handlers.keyboards import filter_options_kb

    kb = await filter_options_kb(ctx, chat_id, user_id, page)
    prompt_text = await at(user_id, "panel.filter_options_header", keyword=keyword)

    await finalize_input_capture(client, message, user_id, prompt_msg_id, prompt_text, kb)


register(FiltersPlugin())
