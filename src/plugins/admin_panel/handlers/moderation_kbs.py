from pyrogram.enums import MessageEntityType
from pyrogram.types import (
    ChatPrivileges,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
)

from src.utils.i18n import at

from ..repository import get_chat_settings
from .keyboards import get_pager


async def warns_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_warn_limit", limit=settings.warnLimit),
                    callback_data="panel:input:warnLimit",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "common.btn_action",
                        action=await at(at_id, f"action.{settings.warnAction.lower()}"),
                    ),
                    callback_data="panel:cycle:warnAction",
                ),
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "panel.btn_warn_expiry",
                        expiry=await at(at_id, f"expiry.{settings.warnExpiry.lower()}"),
                    ),
                    callback_data="panel:cycle:warnExpiry",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_view_user_warns"),
                    callback_data="panel:user_warns:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_warn_reset_all"),
                    callback_data="panel:reset_warns",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def slowmode_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    from src.db.repositories.slowmode import get_slowmode

    interval = await get_slowmode(ctx, chat_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_slowmode_interval", interval=interval),
                    callback_data="panel:input:slowmode",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def logging_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    settings = await get_chat_settings(ctx, chat_id)
    channel_display = (
        settings.logChannelId if settings.logChannelId else await at(at_id, "panel.not_set")
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_logging_channel", channel=channel_display),
                    callback_data="panel:logging_picker:0",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
                )
            ],
        ]
    )


async def langblock_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
                    callback_data="panel:noop",
                ),
                InlineKeyboardButton(
                    f"⚖️ {await at(at_id, f'action.{b.action.lower()}')}",
                    callback_data=f"panel:cycle_langblock_action:{b.id}:{page}",
                ),
                InlineKeyboardButton("❌", callback_data=f"panel:lang_remove:{b.langCode}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(blocks), PAGE_SIZE, "panel:langblock")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_add_langblock"),
                callback_data=f"panel:input:langblockInput:{page}",
            )
        ]
    )

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def entityblock_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
            action_label = await at(at_id, f"action.{block.action.lower()}")
            type_label = await at(at_id, f"lock.{entity}", default=entity.replace("_", " ").title())
            btn_text = f"{icon} {type_label} ({action_label})"
        else:
            icon = "❌"
            type_label = await at(at_id, f"lock.{entity}", default=entity.replace("_", " ").title())
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
                await at(at_id, "panel.btn_back"), callback_data="panel:category:security"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def blacklist_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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

    action_label = await at(at_id, f"action.{action_type}")

    kb.append(
        [
            InlineKeyboardButton(
                await at(
                    at_id,
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
        badge = await at(at_id, badge_key)
        kb.append(
            [
                InlineKeyboardButton(
                    f"{badge} {(b.pattern[:30] + '...') if len(b.pattern) > 30 else b.pattern}",
                    callback_data="panel:noop",
                ),
                InlineKeyboardButton("❌", callback_data=f"panel:blacklist_remove:{b.id}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(blocks), PAGE_SIZE, "panel:blacklist")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_blacklist_blocks"),
                callback_data=f"panel:blacklist_blocks:{page}",
            ),
            InlineKeyboardButton(
                await at(at_id, "panel.btn_add_blacklist"),
                callback_data=f"panel:input:blacklistInput:{page}",
            ),
        ]
    )

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)


async def blacklist_defaults_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_blacklist_level_low"),
                    callback_data=f"panel:blacklist_inject:low:{page}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_blacklist_level_medium"),
                    callback_data=f"panel:blacklist_inject:medium:{page}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_blacklist_level_hard"),
                    callback_data=f"panel:blacklist_inject:hard:{page}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data=f"panel:blacklist:{page}"
                )
            ],
        ]
    )


async def user_warns_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
                    await at(at_id, "panel.warn_item", id=uid, count=count),
                    callback_data=f"panel:user_warn_info:{uid}:{page}",
                ),
                InlineKeyboardButton("❌", callback_data=f"panel:user_warn_reset:{uid}:{page}"),
            ]
        )

    nav_row = await get_pager(page, len(user_ids), PAGE_SIZE, "panel:user_warns")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:warns")]
    )

    return InlineKeyboardMarkup(kb)


async def log_channel_picker_kb(
    ctx, chat_id: int, user_id: int | None = None
) -> ReplyKeyboardMarkup:
    """Returns a ReplyKeyboardMarkup to request a logging channel from the user."""
    at_id = user_id if user_id else chat_id

    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    await at(at_id, "panel.btn_select_log_channel"),
                    request_chat=KeyboardButtonRequestChat(
                        button_id=4,
                        chat_is_channel=True,
                        bot_is_member=True,
                        user_administrator_rights=ChatPrivileges(
                            can_edit_messages=True,
                            can_post_messages=True,
                            can_invite_users=True,
                        ),
                        bot_administrator_rights=ChatPrivileges(
                            can_edit_messages=True,
                            can_post_messages=True,
                            can_invite_users=True,
                        ),
                    ),
                ),
            ],
            [KeyboardButton(await at(at_id, "common.btn_cancel"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def stickers_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    from src.db.repositories.stickers import get_blocked_sticker_sets

    settings = await get_chat_settings(ctx, chat_id)
    blocked_sets = await get_blocked_sticker_sets(ctx, chat_id)
    kb = []

    action_type = (settings.stickerAction or "delete").lower()
    action_icon = {
        "delete": "🗑️",
        "mute": "🔇",
        "kick": "👢",
        "ban": "🔨",
        "warn": "⚠️",
    }.get(action_type, "🗑️")
    action_label = await at(at_id, f"action.{action_type}")

    kb.append(
        [
            InlineKeyboardButton(
                await at(
                    at_id,
                    "panel.btn_sticker_action",
                    action=action_label,
                    icon=action_icon,
                ),
                callback_data=f"panel:cycle_sticker_action:{page}",
            )
        ]
    )

    PAGE_SIZE = 8
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_sets = blocked_sets[start:end]

    for s in current_sets:
        kb.append(
            [
                InlineKeyboardButton(
                    f"🚫 {s.setName}",
                    callback_data=f"panel:sticker_noop:{page}",
                ),
                InlineKeyboardButton(
                    "❌", callback_data=f"panel:sticker_remove:{s.setName}:{page}"
                ),
            ]
        )

    nav_row = await get_pager(page, len(blocked_sets), PAGE_SIZE, "panel:stickers")
    if nav_row:
        kb.append(nav_row)

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_add_sticker"),
                callback_data=f"panel:input:stickerInput:{page}",
            )
        ]
    )

    kb.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_back"), callback_data="panel:category:moderation"
            )
        ]
    )

    return InlineKeyboardMarkup(kb)
