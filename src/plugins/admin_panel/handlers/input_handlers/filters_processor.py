import contextlib

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
from src.core.context import AppContext
from src.utils.i18n import at
from src.utils.telegram_storage import extract_message_data

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(["filterKeyword", "filterResponse"])
async def filters_settings_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    chat_id: int,
    field: str,
    value: str,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id

    if field == "filterKeyword":
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
        await r.set(
            f"panel_input:{user_id}", f"{chat_id}:filterResponse:{prompt_msg_id}:{page}", ttl=300
        )

        prompt_text = await at(user_id, "panel.input_prompt_filterResponse", keyword=keyword)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        await at(user_id, "common.btn_cancel"),
                        callback_data=f"panel:filters:{page}",
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
        return

    elif field == "filterResponse":
        r = get_cache()
        keyword = await r.get(f"temp_filter_kw:{user_id}")
        if not keyword:
            return

        from src.db.repositories.filters import get_all_filters

        # Final check for limit before proceeding
        all_fs = await get_all_filters(ctx, chat_id)
        if keyword not in [f.keyword for f in all_fs] and len(all_fs) >= 150:
            await message.reply(await at(user_id, "filter.limit_reached"))
            await r.delete(f"temp_filter_kw:{user_id}")
            return

        import json

        data = await extract_message_data(message)
        # Store response data and default settings in cache
        await r.set(f"temp_filter_resp:{user_id}", json.dumps(data), ttl=600)
        settings = {"matchMode": "contains", "caseSensitive": False, "isAdminOnly": False}
        await r.set(f"temp_filter_settings:{user_id}", json.dumps(settings), ttl=600)

        # Transition to options menu
        from src.plugins.admin_panel.handlers.keyboards import filter_options_kb

        kb = await filter_options_kb(ctx, chat_id, user_id, page)
        prompt_text = await at(user_id, "panel.filter_options_header", keyword=keyword)

        await finalize_input_capture(client, message, user_id, prompt_msg_id, prompt_text, kb)
