import json
import math

import pyrogram
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import at

from ..repository import get_chat_settings


async def service_cleaner_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    status_key = "panel.status_enabled" if settings.cleanAllServices else "panel.status_disabled"
    status = await at(at_id, status_key)

    buttons = [
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_clean_all", status=status),
                callback_data="panel:tgs:cleanAllServices",
            )
        ],
    ]

    if not settings.cleanAllServices:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_manage_types"),
                    callback_data="panel:svc:types:0",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def service_cleaner_types_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    try:
        enabled_types = set(json.loads(settings.cleanServiceTypes))
    except (json.JSONDecodeError, TypeError):
        enabled_types = set()

    all_types = [e.name for e in pyrogram.enums.MessageServiceType if e.name != "UNSUPPORTED"]

    items_per_page = 10
    total_pages = math.ceil(len(all_types) / items_per_page)

    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0

    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_page_types = all_types[start_idx:end_idx]

    buttons = []

    for i in range(0, len(current_page_types), 2):
        row = []
        for t in current_page_types[i : i + 2]:
            is_enabled = t in enabled_types
            icon = "🟢" if is_enabled else "🔴"

            label_key = f"panel.service_type_{t}"
            label = await at(at_id, label_key)
            if label == label_key:
                label = t.replace("_", " ").title()

            display_str = f"{icon} {label}"
            row.append(InlineKeyboardButton(display_str, callback_data=f"panel:tst:{t}:{page}"))
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"panel:svc:types:{page - 1}"))

    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="panel:noop"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"panel:svc:types:{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:svc")]
    )

    return InlineKeyboardMarkup(buttons)
