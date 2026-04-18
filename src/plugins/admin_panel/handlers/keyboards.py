import itertools

from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from src.config import config
from src.db.models import Reminder
from src.utils.i18n import at
from src.utils.media import parse_watermark_config

from ..repository import get_chat_settings, get_user_admin_chats
from ..validation import is_setting_allowed


async def main_menu_kb(
    chat_id: int, user_id: int | None = None, chat_type: ChatType | str | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    chat_type_str = "supergroup"
    if chat_type:
        chat_type_str = (
            chat_type.name.lower() if hasattr(chat_type, "name") else str(chat_type).lower()
        )

    buttons = []

    # Row 1: Safety & Moderation
    row1 = []
    if is_setting_allowed("security", chat_type_str):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_security"),
                callback_data="panel:category:security",
            )
        )
    if is_setting_allowed("moderation", chat_type_str):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_moderation"),
                callback_data="panel:category:moderation",
            )
        )
    if row1:
        buttons.append(row1)

    # Row 2: Greetings & Automation
    row2 = []
    if is_setting_allowed("greetings", chat_type_str):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_greetings"),
                callback_data="panel:category:greetings",
            )
        )
    if is_setting_allowed("automation", chat_type_str):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_scheduler"),
                callback_data="panel:category:automation",
            )
        )
    if row2:
        buttons.append(row2)

    # Row 3: AI & Settings
    row3 = []
    if is_setting_allowed("ai", chat_type_str):
        row3.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_ai"),
                callback_data="panel:category:ai",
            )
        )
    if is_setting_allowed("settings", chat_type_str):
        row3.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_cat_settings"),
                callback_data="panel:category:settings",
            )
        )
    if row3:
        buttons.append(row3)

    last_row = []
    if user_id:
        last_row.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_my_groups"),
                callback_data="panel:my_chats",
            )
        )

    last_row.append(
        InlineKeyboardButton(await at(at_id, "panel.btn_close"), callback_data="panel:close")
    )
    buttons.append(last_row)

    return InlineKeyboardMarkup(buttons)


async def my_chats_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_list_groups"), callback_data="panel:list_groups"
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_list_channels"),
                    callback_data="panel:list_channels",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_language"), callback_data="panel:language:user"
                ),
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_close"), callback_data="panel:close"
                ),
            ],
        ]
    )


async def security_category_kb(
    chat_id: int, user_id: int | None = None, chat_type: str = "supergroup"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    buttons = []

    # Row 1: Flood & Raid
    row1 = []
    if is_setting_allowed("flood", chat_type):
        row1.append(
            InlineKeyboardButton(await at(at_id, "panel.btn_flood"), callback_data="panel:flood")
        )
    if is_setting_allowed("raid", chat_type):
        row1.append(
            InlineKeyboardButton(await at(at_id, "panel.btn_raid"), callback_data="panel:raid")
        )
    if row1:
        buttons.append(row1)

    # Row 2: Captcha & URL Scanner
    row2 = []
    if is_setting_allowed("captcha", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_captcha"), callback_data="panel:captcha"
            )
        )
    if is_setting_allowed("urlscanner", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_urlscanner"), callback_data="panel:urlscanner"
            )
        )
    if row2:
        buttons.append(row2)

    # Row 3: AI Guard
    if is_setting_allowed("ai_security", chat_type):
        buttons.append(
            [
                InlineKeyboardButton(
                    (await at(at_id, "panel.btn_ai_guard_toggle")).split(":")[0],
                    callback_data="panel:category:ai_security",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def moderation_category_kb(
    chat_id: int, user_id: int | None = None, chat_type: str = "supergroup"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    buttons = []

    # Row 1: Warns & Blacklist
    row1 = []
    if is_setting_allowed("warns", chat_type):
        row1.append(
            InlineKeyboardButton(await at(at_id, "panel.btn_warns"), callback_data="panel:warns")
        )
    if is_setting_allowed("blacklist", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_blacklist"), callback_data="panel:blacklist:0"
            )
        )
    if row1:
        buttons.append(row1)

    # Row 2: Stickers & Entity Block
    row2 = []
    if is_setting_allowed("stickers", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_stickers"), callback_data="panel:stickers:0"
            )
        )
    if is_setting_allowed("entityblock", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_entityblock"), callback_data="panel:entityblock:0"
            )
        )
    if row2:
        buttons.append(row2)

    # Row 3: Langblock & Slowmode
    row3 = []
    if is_setting_allowed("langblock", chat_type):
        row3.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_langblock"), callback_data="panel:langblock:0"
            )
        )
    if is_setting_allowed("slowmode", chat_type):
        row3.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_slowmode"), callback_data="panel:slowmode"
            )
        )
    if row3:
        buttons.append(row3)

    # Row 4: Purge
    if is_setting_allowed("purgeMessagesCount", chat_type):
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_purge"),
                    callback_data="panel:input:purgeMessagesCount",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def greetings_category_kb(
    chat_id: int, user_id: int | None = None, chat_type: str = "supergroup"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    buttons = []

    # Row 1: Welcome & Rules
    row1 = []
    if is_setting_allowed("welcome", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_welcome"), callback_data="panel:welcome"
            )
        )
    if is_setting_allowed("rules", chat_type):
        row1.append(
            InlineKeyboardButton(await at(at_id, "panel.btn_rules"), callback_data="panel:rules")
        )
    if row1:
        buttons.append(row1)

    # Row 2: Filters
    if is_setting_allowed("filters", chat_type):
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_filters"), callback_data="panel:filters"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def settings_category_kb(
    chat_id: int, user_id: int | None = None, chat_type: str = "supergroup"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    buttons = []

    # Row 1: Language & Timezone
    row1 = []
    if is_setting_allowed("language", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_language"), callback_data="panel:language:chat"
            )
        )
    if is_setting_allowed("timezone", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_timezone"), callback_data="panel:timezone:0"
            )
        )
    if row1:
        buttons.append(row1)

    # Row 2: Logging & Service Cleaner
    row2 = []
    if is_setting_allowed("logging", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_logging"), callback_data="panel:logging"
            )
        )
    if is_setting_allowed("svc", chat_type):
        row2.append(
            InlineKeyboardButton(
                await at(at_id, "common.service_cleaner"), callback_data="panel:svc:settings"
            )
        )
    if row2:
        buttons.append(row2)

    # Row 3: Admin Management
    buttons.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_admins_mgmt"), callback_data="panel:admins_mgmt"
            )
        ]
    )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def my_groups_kb(ctx, client, user_id: int) -> InlineKeyboardMarkup:
    groups = await get_user_admin_chats(
        ctx, client, user_id, chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]
    )
    buttons = [
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_add_to_group"),
                url=f"https://t.me/{client.me.username}?startgroup=true",
            )
        ]
    ]

    for chat_id, title in groups:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.chat_list_item", title=title),
                    callback_data=f"panel:select_chat:{chat_id}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_back"), callback_data="panel:my_chats"
            ),
            InlineKeyboardButton(await at(user_id, "panel.btn_close"), callback_data="panel:close"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def flood_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    settings = await get_chat_settings(ctx, chat_id)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_threshold", n=settings.floodThreshold),
                    callback_data="panel:input:floodThreshold",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_window", n=settings.floodWindow),
                    callback_data="panel:input:floodWindow",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "common.btn_action",
                        action=await at(at_id, f"action.{settings.floodAction.lower()}"),
                    ),
                    callback_data="panel:toggle_flood_action",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:security"
                )
            ],
        ]
    )


async def welcome_kb(
    ctx, chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:greetings"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    settings = await get_chat_settings(ctx, chat_id)
    sw = await at(
        at_id, "panel.status_enabled" if settings.welcomeEnabled else "panel.status_disabled"
    )
    sg = await at(
        at_id, "panel.status_enabled" if settings.goodbyeEnabled else "panel.status_disabled"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_welcome_toggle", status=sw),
                    callback_data="panel:tgs:welcomeEnabled",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_goodbye_toggle", status=sg),
                    callback_data="panel:tgs:goodbyeEnabled",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_set_welcome"),
                    callback_data="panel:input:welcomeText",
                ),
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)],
        ]
    )


async def rules_kb(
    chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:greetings"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from src.core.context import get_context
    from src.db.repositories.rules import get_rules

    ctx = get_context()
    rules = await get_rules(ctx, chat_id)
    private_mode = rules.privateMode if rules else False

    status_key = "panel.status_enabled" if private_mode else "panel.status_disabled"
    status = await at(at_id, status_key)

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_rules_private_toggle", status=status),
                    callback_data="panel:toggle_private_rules",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_set_rules"),
                    callback_data="panel:input:rulesText",
                ),
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)],
        ]
    )


async def filters_menu_kb(
    ctx,
    chat_id: int,
    page: int = 0,
    user_id: int | None = None,
    back_callback: str = "panel:category:greetings",
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from src.db.repositories.filters import get_filters_count, get_filters_paginated

    page_size = 10
    total_count = await get_filters_count(ctx, chat_id)
    filters_list = await get_filters_paginated(ctx, chat_id, page, page_size)

    buttons = [
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_add_filter"), callback_data=f"panel:add_filter:{page}"
            )
        ]
    ]

    buttons.extend(
        [
            InlineKeyboardButton(
                f"📜 {f.keyword}", callback_data=f"panel:edit_filter:{f.id}:{page}"
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=f"panel:delete_filter:{f.id}:{page}",
            ),
        ]
        for f in filters_list
    )

    if nav := await get_pager(page, total_count, page_size, "panel:filters"):
        buttons.append(nav)

    if total_count > 0:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_clear_filters"), callback_data="panel:clear_filters"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)]
    )
    return InlineKeyboardMarkup(buttons)


async def automation_category_kb(
    chat_id: int, user_id: int | None = None, chat_type: str = "supergroup"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    buttons = []

    # Row 1: Reminders & Night Lock
    row1 = []
    if is_setting_allowed("reminders", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_reminders"), callback_data="panel:reminders"
            )
        )
    if is_setting_allowed("chatnightlock", chat_type):
        row1.append(
            InlineKeyboardButton(
                await at(at_id, "panel.btn_nightlock"), callback_data="panel:chatnightlock"
            )
        )
    if row1:
        buttons.append(row1)

    # Row 2: Shabbat Lock
    if is_setting_allowed("chatshabbatlock", chat_type):
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_shabbatlock"), callback_data="panel:chatshabbatlock"
                )
            ]
        )

    # Row 3: Group Cleaner
    if is_setting_allowed("cleaner", chat_type):
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_group_cleaner"), callback_data="panel:cleaner"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")]
    )
    return InlineKeyboardMarkup(buttons)


async def timezone_picker_kb(
    ctx,
    chat_id: int,
    page: int = 0,
    user_id: int | None = None,
    region: str | None = None,
    filter_query: str | None = None,
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from zoneinfo import available_timezones

    settings = await get_chat_settings(ctx, chat_id)
    current_tz = settings.timezone

    if filter_query:
        import difflib

        q = filter_query.strip().lower().replace(" ", "_")
        scored_tzs = []

        for tz in available_timezones():
            if not ("/" in tz or tz == "UTC"):
                continue

            tz_lower = tz.lower()
            city = tz.split("/")[-1].lower()
            score = 0

            if q == city:
                score = 100
            elif city.startswith(q):
                score = 80
            elif q in city:
                score = 60
            elif q in tz_lower:
                score = 40
            else:
                ratio = difflib.SequenceMatcher(None, q, city).ratio()
                if ratio > 0.6:
                    score = int(ratio * 35)

            if score > 0:
                scored_tzs.append((score, tz))

        scored_tzs.sort(key=lambda x: (-x[0], x[1]))
        tzs = [tz for score, tz in scored_tzs]
    elif region:
        tzs = [
            tz
            for tz in available_timezones()
            if tz.startswith(f"{region}/") or (region == "UTC" and tz == "UTC")
        ]
        tzs.sort()
    else:
        regions = list({tz.split("/")[0] for tz in available_timezones() if "/" in tz})
        if "UTC" not in regions:
            regions.append("UTC")
        regions.sort()

        buttons = [
            [
                InlineKeyboardButton(
                    await at(at_id, "common.btn_search"),
                    callback_data="panel:timezone_search",
                )
            ]
        ]

        buttons.extend(
            [InlineKeyboardButton(r, callback_data=f"panel:timezone_region:{r}:0") for r in row]
            for row in itertools.batched(regions, 2)
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:settings"
                )
            ]
        )
        return InlineKeyboardMarkup(buttons)

    page_size = 20
    start = page * page_size
    end = start + page_size
    chunk = tzs[start:end]

    buttons = []
    buttons.append(
        [
            InlineKeyboardButton(
                await at(at_id, "common.btn_search"), callback_data="panel:timezone_search"
            )
        ]
    )

    buttons.extend(
        [
            InlineKeyboardButton(
                (f"✅ {tz.split('/')[-1].replace('_', ' ')}" if "/" in tz else tz)
                if tz == current_tz
                else (tz.split("/")[-1].replace("_", " ") if "/" in tz else tz),
                callback_data=f"panel:set_tz:{tz}",
            )
            for tz in row
        ]
        for row in itertools.batched(chunk, 3)
    )

    cb_prefix = (
        f"panel:timezone_region:{region}" if region else f"panel:timezone_filter:{filter_query}"
    )
    nav = await get_pager(page, len(tzs), page_size, cb_prefix)
    if nav:
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:timezone:0")]
    )
    return InlineKeyboardMarkup(buttons)


async def reminders_menu_kb(
    ctx, chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:automation"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    async with ctx.db() as session:
        result = await session.execute(select(Reminder).where(Reminder.chatId == chat_id))
        reminders = result.scalars().all()

    buttons = [
        [
            InlineKeyboardButton(
                await at(
                    at_id,
                    "panel.btn_reminder_item",
                    id=rem.id,
                    time=rem.sendTime,
                    status=await at(
                        at_id, "panel.status_enabled" if rem.isActive else "panel.status_disabled"
                    ),
                ),
                callback_data=f"panel:toggle_reminder:{rem.id}",
            ),
            InlineKeyboardButton(
                await at(at_id, "common.btn_delete"),
                callback_data=f"panel:delete_reminder:{rem.id}",
            ),
        ]
        for rem in reminders
    ]

    if len(reminders) < 3:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_add_reminder"),
                    callback_data="panel:input:reminderText",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)]
    )
    return InlineKeyboardMarkup(buttons)


async def chatnightlock_menu_kb(
    ctx, chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:automation"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from src.db.models import ChatNightLock

    async with ctx.db() as session:
        lock = await session.get(ChatNightLock, chat_id)
        if not lock:
            lock = ChatNightLock(chatId=chat_id)
            session.add(lock)
            await session.commit()

    status = await at(at_id, "panel.status_enabled" if lock.isEnabled else "panel.status_disabled")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_toggle", status=status),
                    callback_data="panel:toggle_chatnightlock",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_start", time=lock.startTime),
                    callback_data="panel:input:chatnightlockStart",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_end", time=lock.endTime),
                    callback_data="panel:input:chatnightlockEnd",
                ),
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)],
        ]
    )


async def chatshabbatlock_menu_kb(
    ctx, chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:automation"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from src.db.models import ChatShabbatLock

    async with ctx.db() as session:
        lock = await session.get(ChatShabbatLock, chat_id)
        if not lock:
            lock = ChatShabbatLock(chatId=chat_id)
            session.add(lock)
            await session.commit()

    status = await at(at_id, "panel.status_enabled" if lock.isEnabled else "panel.status_disabled")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_shabbatlock_toggle", status=status),
                    callback_data="panel:toggle_chatshabbatlock",
                )
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)],
        ]
    )


async def cleaner_menu_kb(
    ctx, chat_id: int, user_id: int | None = None, back_callback: str = "panel:category:automation"
) -> InlineKeyboardMarkup:
    at_id = user_id or chat_id
    from src.db.models import ChatCleaner

    async with ctx.db() as session:
        cleaner = await session.get(ChatCleaner, chat_id)
        if not cleaner:
            cleaner = ChatCleaner(chatId=chat_id)
            session.add(cleaner)
            await session.commit()

    s_del = await at(
        at_id, "panel.status_enabled" if cleaner.cleanDeleted else "panel.status_disabled"
    )
    s_fake = await at(
        at_id, "panel.status_enabled" if cleaner.cleanFake else "panel.status_disabled"
    )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_clean_deleted", status=s_del),
                    callback_data="panel:toggle_cleaner:deleted",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_clean_fake", status=s_fake),
                    callback_data="panel:toggle_cleaner:fake",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_clean_inactive", days=cleaner.cleanInactiveDays),
                    callback_data="panel:input:cleanerInactive",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_clean_time", time=cleaner.cleanerRunTime),
                    callback_data="panel:input:cleanerRunTime",
                ),
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data=back_callback)],
        ]
    )


async def ai_security_kb(
    ctx, chat_id: int, user_id: int, back_callback: str = "panel:category:security"
) -> InlineKeyboardMarkup:
    """Keyboard for AI Security settings."""
    from src.db.repositories.ai_guard import get_ai_guard_settings

    s = await get_ai_guard_settings(ctx, chat_id)
    status_icon = "✅" if s.isTextEnabled else "❌"
    img_status_icon = "✅" if s.isImageEnabled else "❌"
    action_label = await at(user_id, f"action.{s.action}")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_ai_guard_toggle", status=status_icon),
                    callback_data="panel:toggle_ai_guard",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_ai_image_guard_toggle", status=img_status_icon),
                    callback_data="panel:toggle_ai_image_guard",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_set_groq_key"),
                    callback_data="panel:set_groq_key",
                ),
                InlineKeyboardButton(
                    await at(user_id, "common.btn_action", action=action_label),
                    callback_data="panel:cycle_ai_guard_action",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_ai_guard_setup"),
                    callback_data="panel:ai_guard_setup",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_back"), callback_data=back_callback
                )
            ],
        ]
    )


async def filter_options_kb(ctx, chat_id: int, user_id: int, page: int) -> InlineKeyboardMarkup:
    """Keyboard for the third step of the filter creation wizard (Settings)."""
    from src.utils.local_cache import get_cache

    r = get_cache()
    settings_raw = await r.get(f"temp_filter_settings:{user_id}")
    import json

    settings = json.loads(settings_raw) if settings_raw else {}

    match_mode = settings.get("matchMode", "contains")
    case_sensitive = settings.get("caseSensitive", False)
    is_admin_only = settings.get("isAdminOnly", False)

    buttons = []

    admin_btn_key = (
        "panel.btn_filter_admins_only" if is_admin_only else "panel.btn_filter_all_users"
    )
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, admin_btn_key),
                callback_data=f"panel:toggle_filter:admin:{page}",
            )
        ]
    )

    # Case Sensitive Toggle
    case_btn_key = (
        "panel.btn_filter_case_sensitive" if case_sensitive else "panel.btn_filter_case_insensitive"
    )
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, case_btn_key),
                callback_data=f"panel:toggle_filter:case:{page}",
            )
        ]
    )

    # Match Mode Toggle
    match_btn_key = (
        "panel.btn_filter_match_full" if match_mode == "full" else "panel.btn_filter_match_contains"
    )
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, match_btn_key), callback_data=f"panel:toggle_filter:match:{page}"
            )
        ]
    )

    # Save & Cancel
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "common.btn_save"), callback_data=f"panel:save_filter:{page}"
            ),
            InlineKeyboardButton(
                await at(user_id, "common.btn_cancel"), callback_data=f"panel:filters:{page}"
            ),
        ]
    )

    return InlineKeyboardMarkup(buttons)


async def get_pager(
    current_page: int, total_count: int, page_size: int, callback_prefix: str
) -> list[InlineKeyboardButton]:
    """Reusable pagination row for the admin panel."""
    nav_row = []
    if current_page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"{callback_prefix}:{current_page - 1}")
        )

    total_pages = (total_count + page_size - 1) // page_size
    if total_pages > 1:
        nav_row.append(
            InlineKeyboardButton(f"{current_page + 1} / {total_pages}", callback_data="panel:noop")
        )

    if (current_page + 1) * page_size < total_count:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}:{current_page + 1}")
        )
    return nav_row


async def channels_menu_kb(ctx, client, user_id: int) -> InlineKeyboardMarkup:
    """List of channels where both user and bot are admins."""
    channels = await get_user_admin_chats(ctx, client, user_id, chat_type=[ChatType.CHANNEL])
    buttons = [
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_add_to_channel"),
                url=f"https://t.me/{client.me.username}?startchannel=true",
            )
        ]
    ]

    for ch_id, title in channels:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.channel_list_item", title=title),
                    callback_data=f"panel:select_channel:{ch_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_back"), callback_data="panel:my_chats"
            ),
            InlineKeyboardButton(await at(user_id, "panel.btn_close"), callback_data="panel:close"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def channel_settings_kb(ctx, channel_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Keyboard for specific channel settings."""
    wm_menu_label = await at(user_id, "panel.btn_watermark_menu")
    if wm_menu_label == "panel.btn_watermark_menu":
        # Backward-compatible fallback for locales that don't have the new menu-only key yet.
        wm_menu_label = await at(user_id, "panel.btn_watermark")
        wm_menu_label = wm_menu_label.strip().rstrip(":").rstrip("：").strip()

    return InlineKeyboardMarkup(
        [
            # Row 1: Reactions & Signature
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_cat_reactions"),
                    callback_data=f"panel:channel_reactions:{channel_id}",
                ),
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_signature_menu"),
                    callback_data=f"panel:channel_signature:{channel_id}",
                ),
            ],
            # Row 2: Watermark & Buttons
            [
                InlineKeyboardButton(
                    wm_menu_label,
                    callback_data=f"panel:channel_watermark:{channel_id}",
                ),
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_buttons"),
                    callback_data=f"panel:channel_buttons:{channel_id}",
                ),
            ],
            # Row 3: Service Cleaner
            [
                InlineKeyboardButton(
                    await at(user_id, "common.service_cleaner"),
                    callback_data=f"panel:chs:{channel_id}",
                )
            ],
            # Row 4: Back
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_back"), callback_data="panel:list_channels"
                )
            ],
        ]
    )


async def channel_reactions_kb(ctx, channel_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Keyboard for reaction settings."""
    from src.db.repositories.chats import get_chat_settings as get_channel_settings

    s = await get_channel_settings(ctx, channel_id)

    status = "✅" if s.reactionsEnabled else "❌"
    mode_label = await at(user_id, f"reaction_mode_{s.reactionMode}")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_reactions_status", status=status),
                    callback_data=f"panel:toggle_ch:reactionsEnabled:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_reaction_mode", mode=mode_label),
                    callback_data=f"panel:toggle_ch:reactionMode:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_edit_emojis"),
                    callback_data=f"panel:input:reactions:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_back"),
                    callback_data=f"panel:channel_settings:{channel_id}",
                )
            ],
        ]
    )


async def channel_signature_kb(ctx, channel_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Keyboard for signature settings."""
    from src.db.repositories.chats import get_chat_settings as get_channel_settings

    s = await get_channel_settings(ctx, channel_id)

    status = "✅" if s.signatureEnabled else "❌"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_signature_status", status=status),
                    callback_data=f"panel:toggle_ch:signatureEnabled:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_edit_signature"),
                    callback_data=f"panel:input:signatureText:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_back"),
                    callback_data=f"panel:channel_settings:{channel_id}",
                )
            ],
        ]
    )


async def channel_watermark_kb(ctx, channel_id: int, user_id: int) -> InlineKeyboardMarkup:
    from src.db.repositories.chats import get_chat_settings as get_channel_settings

    s = await get_channel_settings(ctx, channel_id)
    cfg = parse_watermark_config(s.watermarkText)
    wm_color = cfg.color
    wm_style = cfg.style

    # Status icons
    image_status = "✅" if cfg.image_enabled else "❌"
    video_status = "✅" if cfg.video_enabled else "❌"

    buttons = [
        # Media Toggles
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_wm_image", status=image_status),
                callback_data=f"panel:toggle_wm_image:{channel_id}",
            )
        ],
    ]

    if config.ENABLE_VIDEO_WATERMARK:
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_wm_video", status=video_status),
                    callback_data=f"panel:toggle_wm_video:{channel_id}",
                )
            ]
        )

    buttons.extend(
        [
            # Text Setting
            [
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_set_watermark"),
                    callback_data=f"panel:input:watermarkText:{channel_id}",
                ),
                InlineKeyboardButton(
                    await at(user_id, "panel.btn_clear_text"),
                    callback_data=f"panel:clear_wm_text:{channel_id}",
                ),
            ],
            # Color & Style
            [
                InlineKeyboardButton(
                    await at(
                        user_id,
                        "panel.btn_wm_color",
                        value=await at(user_id, f"panel.wm_color_{wm_color}"),
                    ),
                    callback_data=f"panel:cycle_wm:color:{channel_id}",
                ),
                InlineKeyboardButton(
                    await at(
                        user_id,
                        "panel.btn_wm_style",
                        value=await at(user_id, f"panel.wm_style_{wm_style}"),
                    ),
                    callback_data=f"panel:cycle_wm:style:{channel_id}",
                ),
            ],
        ]
    )

    if config.ENABLE_VIDEO_WATERMARK:
        # Video Quality & Motion
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(
                        user_id,
                        "panel.btn_wm_video_quality",
                        value=await at(user_id, f"panel.wm_quality_{cfg.video_quality}"),
                    ),
                    callback_data=f"panel:cycle_wm:video_quality:{channel_id}",
                ),
                InlineKeyboardButton(
                    await at(
                        user_id,
                        "panel.btn_wm_video_motion",
                        value=await at(user_id, f"panel.wm_motion_{cfg.video_motion}"),
                    ),
                    callback_data=f"panel:cycle_wm:video_motion:{channel_id}",
                ),
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_back"),
                callback_data=f"panel:channel_settings:{channel_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def channel_buttons_kb(ctx, channel_id: int, user_id: int) -> InlineKeyboardMarkup:
    from src.db.repositories.chats import get_chat_settings

    s = await get_chat_settings(ctx, channel_id)
    import json

    try:
        rows = json.loads(s.buttons or "[]")
    except Exception:
        rows = []

    buttons = []
    # List each button with controls
    for r_idx, row in enumerate(rows):
        for b_idx, btn in enumerate(row):
            label = btn.get("text", "Button")
            style_str = btn.get("style", "default")

            # Localized style name
            style_name = await at(user_id, f"panel.btn_button_style_{style_str}")
            if style_name == f"panel.btn_button_style_{style_str}":
                style_name = style_str.title()

            buttons.append(
                [
                    InlineKeyboardButton(label, url=btn.get("url", "https://t.me")),
                    InlineKeyboardButton(
                        f"🎨 {style_name}",
                        callback_data=f"panel:cycle_ch_btn_style:{channel_id}:{r_idx}:{b_idx}",
                    ),
                    InlineKeyboardButton(
                        "🗑️", callback_data=f"panel:delete_ch_btn:{channel_id}:{r_idx}:{b_idx}"
                    ),
                ]
            )

    # Add button
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_add_button"),
                callback_data=f"panel:input:buttonsText:{channel_id}",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_back"),
                callback_data=f"panel:channel_settings:{channel_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def admins_management_kb(
    ctx, chat_id: int, user_id: int, admins: list
) -> InlineKeyboardMarkup:
    """Keyboard for viewing the admin list with manual refresh option."""
    # Note: admins is a list of ChatAdmin objects
    buttons = []
    # Row 1: Manual Refresh
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_refresh_admins"),
                callback_data=f"panel:admins_refresh:{chat_id}",
            )
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_back"), callback_data="panel:category:settings"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)
