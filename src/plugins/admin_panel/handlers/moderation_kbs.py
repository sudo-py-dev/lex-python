from pyrogram.enums import MessageEntityType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import at

from ..repository import get_chat_settings
from .keyboards import get_pager


async def warns_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    settings = await get_chat_settings(ctx, chat_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_warn_limit", limit=settings.warnLimit),
                    callback_data="panel:input:warnLimit",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        chat_id,
                        "panel.btn_warn_action",
                        action=await at(chat_id, f"action.{settings.warnAction.lower()}"),
                    ),
                    callback_data="panel:cycle:warnAction",
                ),
                InlineKeyboardButton(
                    await at(
                        chat_id,
                        "panel.btn_warn_expiry",
                        expiry=await at(chat_id, f"expiry.{settings.warnExpiry.lower()}"),
                    ),
                    callback_data="panel:cycle:warnExpiry",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_view_user_warns"),
                    callback_data="panel:user_warns:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_warn_reset_all"),
                    callback_data="panel:reset_warns",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def slowmode_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    from src.db.repositories.slowmode import get_slowmode

    interval = await get_slowmode(ctx, chat_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_slowmode_interval", interval=interval),
                    callback_data="panel:input:slowmodeInterval",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def logging_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    settings = await get_chat_settings(ctx, chat_id)
    channel_display = (
        settings.logChannelId
        if settings.logChannelId
        else await at(chat_id, "panel.not_set")
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_logging_channel", channel=channel_display),
                    callback_data="panel:logging_picker:0",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def langblock_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    from sqlalchemy import select

    from src.db.models import BlockedLanguage

    async with ctx.db() as session:
        stmt = select(BlockedLanguage).where(BlockedLanguage.chatId == chat_id)
        res = await session.execute(stmt)
        blocks = list(res.scalars().all())

    kb = []
    PAGE_SIZE = 10
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_page_blocks = blocks[start:end]

    for b in current_page_blocks:
        kb.append(
            [
                InlineKeyboardButton(
                    f"🗣️ {b.langCode.upper()}",
                    callback_data="none",
                ),
                InlineKeyboardButton(
                    f"⚖️ {await at(chat_id, f'action.{b.action.lower()}')}",
                    callback_data=f"panel:cycle_langblock_action:{b.id}:{page}",
                ),
                InlineKeyboardButton("❌", callback_data=f"panel:langblock_remove:{b.id}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(blocks), PAGE_SIZE, "panel:langblock")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_add_langblock"),
                callback_data=f"panel:input:langblockInput:{page}",
            )
        ]
    )

    kb.append(
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_back"), callback_data="panel:category:moderation"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def entityblock_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    from src.plugins.entity_block import get_blocked_entities

    blocks = await get_blocked_entities(ctx, chat_id)

    ALL_ENTITIES = sorted(
        [
            e.name.lower()
            for e in MessageEntityType
            if e.name.lower() not in ("unsupported", "unknown")
        ]
        + ["poll", "contact", "location", "sticker", "gif", "media", "forward", "message"]
    )

    kb = []

    PAGE_SIZE = 10
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    entities_slice = ALL_ENTITIES[start:end]

    row = []
    for entity in entities_slice:
        block = next((b for b in blocks if b.entityType == entity), None)
        if block:
            icon = "✅"
            action_label = await at(chat_id, f"action.{block.action.lower()}")
            type_label = await at(
                chat_id, f"lock.{entity}", default=entity.replace("_", " ").title()
            )
            btn_text = f"{icon} {type_label} ({action_label})"
        else:
            icon = "❌"
            type_label = await at(
                chat_id, f"lock.{entity}", default=entity.replace("_", " ").title()
            )
            btn_text = f"{icon} {type_label}"

        row.append(
            InlineKeyboardButton(btn_text, callback_data=f"panel:toggle_entity:{entity}:{page}")
        )
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    nav_row = await get_pager(page, len(ALL_ENTITIES), PAGE_SIZE, "panel:entityblock")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_back"), callback_data="panel:category:security"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def blacklist_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    from src.db.repositories.blacklist import get_all_blacklist

    settings = await get_chat_settings(ctx, chat_id)
    blocks = await get_all_blacklist(ctx, chat_id)
    kb = []

    action_type = settings.blacklistAction.lower()
    action_icon = {
        "delete": "🗑️",
        "mute": "🔇",
        "kick": "👢",
        "ban": "🔨",
        "warn": "⚠️",
    }.get(action_type, "🗑️")

    action_label = await at(chat_id, f"action.{action_type}")

    kb.append(
        [
            InlineKeyboardButton(
                await at(
                    chat_id,
                    "panel.btn_blacklist_global_action",
                    action=action_label,
                    icon=action_icon,
                ),
                callback_data=f"panel:cycle_blacklist_action:{page}",
            )
        ]
    )

    PAGE_SIZE = 8
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_page_blocks = blocks[start:end]

    for b in current_page_blocks:
        badge_key = (
            "panel.blacklist_badge_regex"
            if b.isRegex
            else (
                "panel.blacklist_badge_wildcard"
                if b.isWildcard
                else "panel.blacklist_badge_literal"
            )
        )
        badge = await at(chat_id, badge_key)
        kb.append(
            [
                InlineKeyboardButton(f"{badge} {b.pattern}", callback_data="none"),
                InlineKeyboardButton("❌", callback_data=f"panel:blacklist_remove:{b.id}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(blocks), PAGE_SIZE, "panel:blacklist")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_add_blacklist"),
                callback_data=f"panel:input:blacklistInput:{page}",
            )
        ]
    )

    kb.append(
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_back"), callback_data="panel:category:moderation"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def user_warns_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    from src.db.repositories.warns import get_users_with_warns, get_warn_count

    user_ids = await get_users_with_warns(ctx, chat_id)
    kb = []

    PAGE_SIZE = 8
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_ids = user_ids[start:end]

    for uid in slice_ids:
        count = await get_warn_count(ctx, chat_id, uid)
        kb.append(
            [
                InlineKeyboardButton(
                    f"ID: {uid} | {count} Warns",
                    callback_data=f"panel:user_warn_info:{uid}:{page}",
                ),
                InlineKeyboardButton("❌", callback_data=f"panel:user_warn_reset:{uid}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(user_ids), PAGE_SIZE, "panel:user_warns")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [InlineKeyboardButton(await at(chat_id, "panel.btn_back"), callback_data="panel:warns")]
    )


async def log_channel_picker_kb(
    ctx, client, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    from pyrogram.enums import ChatType

    at_id = user_id if user_id else chat_id
    
    # Get dialogs (limited to avoid performance issues)
    dialogs = []
    async for dialog in client.get_dialogs(limit=100):
        if dialog.chat.type in (ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP):
            # For simplicity, we show all chats the bot is in.
            # Usually the user wants their own channels.
            dialogs.append((dialog.chat.id, dialog.chat.title))

    PAGE_SIZE = 10
    total_count = len(dialogs)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = dialogs[start:end]

    buttons = []
    for cid, title in chunk:
        buttons.append(
            [InlineKeyboardButton(title, callback_data=f"panel:logging_set:{cid}")]
        )

    nav = await get_pager(page, total_count, PAGE_SIZE, "panel:logging_picker")
    if nav:
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:logging")]
    )
    return InlineKeyboardMarkup(buttons)
