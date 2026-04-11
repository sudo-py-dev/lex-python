import itertools
import json
import math

import pyrogram
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import at

from ..repository import get_chat_settings


def get_available_service_types(chat_type: str) -> list[str]:
    """Return service types available for a specific chat type using Pyrogram enums."""
    all_types = [e.name for e in pyrogram.enums.MessageServiceType if e.name != "UNSUPPORTED"]
    if chat_type != "channel":
        return all_types

    excluded = {
        "NEW_CHAT_MEMBERS",
        "LEFT_CHAT_MEMBER",
        "CHAT_OWNER_LEFT",
        "CHAT_OWNER_CHANGED",
        "GROUP_CHAT_CREATED",
        "SUPERGROUP_CHAT_CREATED",
        "MIGRATE_TO_CHAT_ID",
        "MIGRATE_FROM_CHAT_ID",
        "FORUM_TOPIC_CREATED",
        "FORUM_TOPIC_CLOSED",
        "FORUM_TOPIC_REOPENED",
        "FORUM_TOPIC_EDITED",
        "GENERAL_FORUM_TOPIC_HIDDEN",
        "GENERAL_FORUM_TOPIC_UNHIDDEN",
    }
    return [t for t in all_types if t not in excluded]


async def service_cleaner_kb(
    ctx,
    chat_id: int,
    user_id: int | None = None,
    back_callback: str = "panel:main",
    types_callback: str = "panel:svc:types:0",
    toggle_callback: str = "panel:tgs:cleanAllServices",
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    settings = await get_chat_settings(ctx, chat_id)
    status = await at(
        at_id, f"panel.status_{'enabled' if settings.cleanAllServices else 'disabled'}"
    )

    buttons = [
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_clean_all", status=status), callback_data=toggle_callback
            )
        ]
    ]

    if not settings.cleanAllServices:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_manage_types"), callback_data=types_callback
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)]
    )
    return InlineKeyboardMarkup(buttons)


async def service_cleaner_types_kb(
    ctx,
    chat_id: int,
    page: int = 0,
    user_id: int | None = None,
    page_callback_prefix: str = "panel:svc:types",
    toggle_callback_prefix: str = "panel:tst",
    back_callback: str = "panel:svc",
    toggle_mode: str = "name",
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    settings = await get_chat_settings(ctx, chat_id)
    try:
        enabled_types = set(json.loads(settings.cleanServiceTypes or "[]"))
    except (json.JSONDecodeError, TypeError):
        enabled_types = set()

    all_types = get_available_service_types(settings.chatType or "supergroup")
    items_per_page = 10
    total_pages = math.ceil(len(all_types) / items_per_page)
    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0

    start_idx = page * items_per_page
    current_page_types = all_types[start_idx : start_idx + items_per_page]

    buttons = []
    for i, row_types in enumerate(itertools.batched(current_page_types, 2)):
        row = []
        for offset, t in enumerate(row_types):
            icon = "🟢" if t in enabled_types else "🔴"
            label = await at(at_id, f"panel.service_type_{t}")
            if label == f"panel.service_type_{t}":
                label = t.replace("_", " ").title()

            idx = start_idx + (i * 2) + offset
            cb = f"{toggle_callback_prefix}:{idx if toggle_mode == 'index' else t}:{page}"
            row.append(InlineKeyboardButton(f"{icon} {label}", callback_data=cb))
        buttons.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"{page_callback_prefix}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="panel:noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"{page_callback_prefix}:{page + 1}"))

    if nav:
        buttons.append(nav)
    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)]
    )

    return InlineKeyboardMarkup(buttons)
