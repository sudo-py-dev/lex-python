from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from src.db.models import Reminder
from src.utils.i18n import at

from ..repository import get_chat_settings, get_user_admin_groups


async def main_menu_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_cat_security"), callback_data="panel:category:security"
            ),
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_cat_moderation"),
                callback_data="panel:category:moderation",
            ),
        ],
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_cat_general"), callback_data="panel:category:general"
            ),
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_cat_scheduler"),
                callback_data="panel:category:scheduler",
            ),
        ],
        [
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_cat_ai"), callback_data="panel:category:ai"
            ),
        ],
    ]

    last_row = []
    if user_id:
        last_row.append(
            InlineKeyboardButton(
                await at(chat_id, "panel.btn_my_groups"), callback_data="panel:my_groups"
            )
        )

    last_row.append(
        InlineKeyboardButton(await at(chat_id, "panel.btn_close"), callback_data="panel:close")
    )
    buttons.append(last_row)

    return InlineKeyboardMarkup(buttons)


async def security_category_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_entityblock"), callback_data="panel:entityblock:0"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_raid"), callback_data="panel:raid"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_flood"), callback_data="panel:flood"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_captcha"), callback_data="panel:captcha"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_urlscanner"), callback_data="panel:urlscanner"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_ai_guard_toggle").split(":")[0],
                    callback_data="panel:ai_security",
                ),
            ],
            [InlineKeyboardButton(await at(chat_id, "panel.btn_back"), callback_data="panel:main")],
        ]
    )


async def moderation_category_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_warns"), callback_data="panel:warns"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_blacklist"), callback_data="panel:blacklist:0"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_slowmode"), callback_data="panel:slowmode"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_purge"),
                    callback_data="panel:input:purgeMessagesCount",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_logging"), callback_data="panel:logging"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_langblock"), callback_data="panel:langblock:0"
                ),
            ],
            [InlineKeyboardButton(await at(chat_id, "panel.btn_back"), callback_data="panel:main")],
        ]
    )


async def general_category_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_welcome"), callback_data="panel:welcome"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_rules"), callback_data="panel:rules"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_filters"), callback_data="panel:filters"
                ),
                InlineKeyboardButton(
                    await at(chat_id, "panel.btn_language"), callback_data="panel:language:group"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(chat_id, "common.service_cleaner"),
                    callback_data="panel:svc",
                ),
            ],
            [InlineKeyboardButton(await at(chat_id, "panel.btn_back"), callback_data="panel:main")],
        ]
    )


async def my_groups_kb(ctx, client, user_id: int) -> InlineKeyboardMarkup:
    groups = await get_user_admin_groups(ctx, client, user_id)
    buttons = []
    for chat_id, title in groups:
        buttons.append([InlineKeyboardButton(title, callback_data=f"panel:select_chat:{chat_id}")])
    buttons.append(
        [
            InlineKeyboardButton(
                await at(user_id, "panel.btn_language"), callback_data="panel:language:pm"
            ),
            InlineKeyboardButton(await at(user_id, "panel.btn_close"), callback_data="panel:close"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def flood_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
                    await at(at_id, "common.btn_action", action=settings.floodAction.capitalize()),
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


async def welcome_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:general"
                )
            ],
        ]
    )


async def rules_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:general"
                )
            ],
        ]
    )


async def filters_menu_kb(
    ctx, chat_id: int, page: int = 0, user_id: int | None = None
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    from src.db.repositories.filters import get_filters_count, get_filters_paginated

    page_size = 10
    total_count = await get_filters_count(ctx, chat_id)
    filters_list = await get_filters_paginated(ctx, chat_id, page, page_size)

    buttons = []

    # Add Filter Button
    buttons.append(
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_add_filter"), callback_data=f"panel:add_filter:{page}"
            )
        ]
    )

    for f in filters_list:
        buttons.append(
            [
                InlineKeyboardButton(
                    f"📜 {f.keyword}", callback_data=f"panel:edit_filter:{f.id}:{page}"
                ),
                InlineKeyboardButton(
                    "🗑️",
                    callback_data=f"panel:delete_filter:{f.id}:{page}",
                ),
            ]
        )

    # Pagination
    nav = await get_pager(page, total_count, page_size, "panel:filters")
    if nav:
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
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_back"), callback_data="panel:category:general"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def scheduler_menu_kb(chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_reminders"), callback_data="panel:reminders"
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_timezone"), callback_data="panel:timezone:0"
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock"), callback_data="panel:nightlock"
                ),
                InlineKeyboardButton(
                    await at(at_id, "common.service_cleaner"), callback_data="panel:cleaner"
                ),
            ],
            [InlineKeyboardButton(await at(at_id, "panel.btn_back"), callback_data="panel:main")],
        ]
    )


async def timezone_picker_kb(
    ctx,
    chat_id: int,
    page: int = 0,
    user_id: int | None = None,
    region: str | None = None,
    filter_query: str | None = None,
) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
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
        tzs = sorted(
            [
                tz
                for tz in available_timezones()
                if tz.startswith(f"{region}/") or (region == "UTC" and tz == "UTC")
            ]
        )
    else:
        regions = sorted(list(set([tz.split("/")[0] for tz in available_timezones() if "/" in tz])))
        if "UTC" not in regions:
            regions.append("UTC")
        regions.sort()

        buttons = [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_timezone_search"),
                    callback_data="panel:timezone_search",
                )
            ]
        ]
        row = []
        for r in regions:
            row.append(InlineKeyboardButton(r, callback_data=f"panel:timezone_region:{r}:0"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append(
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:scheduler"
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
                await at(at_id, "panel.btn_timezone_search"), callback_data="panel:timezone_search"
            )
        ]
    )

    row = []
    for tz in chunk:
        display_name = tz.split("/")[-1].replace("_", " ") if "/" in tz else tz
        btn_text = f"✅ {display_name}" if tz == current_tz else display_name
        row.append(InlineKeyboardButton(btn_text, callback_data=f"panel:set_tz:{tz}"))
        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

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


async def reminders_menu_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    async with ctx.db() as session:
        result = await session.execute(select(Reminder).where(Reminder.chatId == chat_id))
        reminders = result.scalars().all()

    buttons = []
    for rem in reminders:
        status = await at(
            at_id, "panel.status_enabled" if rem.isActive else "panel.status_disabled"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    await at(
                        at_id,
                        "panel.btn_reminder_item",
                        id=rem.id,
                        time=rem.sendTime,
                        status=status,
                    ),
                    callback_data=f"panel:toggle_reminder:{rem.id}",
                ),
                InlineKeyboardButton(
                    await at(at_id, "common.btn_delete"),
                    callback_data=f"panel:delete_reminder:{rem.id}",
                ),
            ]
        )

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
        [
            InlineKeyboardButton(
                await at(at_id, "panel.btn_back"), callback_data="panel:category:scheduler"
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


async def nightlock_menu_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    from src.db.models import NightLock

    async with ctx.db() as session:
        lock = await session.get(NightLock, chat_id)
        if not lock:
            lock = NightLock(chatId=chat_id)
            session.add(lock)
            await session.commit()

    status = await at(at_id, "panel.status_enabled" if lock.isEnabled else "panel.status_disabled")

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_toggle", status=status),
                    callback_data="panel:toggle_nightlock",
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_start", time=lock.startTime),
                    callback_data="panel:input:nightlockStart",
                ),
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_nightlock_end", time=lock.endTime),
                    callback_data="panel:input:nightlockEnd",
                ),
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:scheduler"
                )
            ],
        ]
    )


async def cleaner_menu_kb(ctx, chat_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    at_id = user_id if user_id else chat_id
    from src.db.models import GroupCleaner

    async with ctx.db() as session:
        cleaner = await session.get(GroupCleaner, chat_id)
        if not cleaner:
            cleaner = GroupCleaner(chatId=chat_id)
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
                )
            ],
            [
                InlineKeyboardButton(
                    await at(at_id, "panel.btn_back"), callback_data="panel:category:scheduler"
                )
            ],
        ]
    )


async def ai_security_kb(ctx, chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Keyboard for AI Security settings."""
    from src.db.repositories.ai_guard import get_ai_guard_settings

    s = await get_ai_guard_settings(ctx, chat_id)
    status_icon = "✅" if s.isEnabled else "❌"
    action_label = await at(chat_id, f"action.{s.action}")

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
            [InlineKeyboardButton(await at(user_id, "panel.btn_back"), callback_data="panel:category:security")],
        ]
    )


async def filter_options_kb(ctx, chat_id: int, user_id: int, page: int) -> InlineKeyboardMarkup:
    """Keyboard for the third step of the filter creation wizard (Settings)."""
    from src.cache.local_cache import get_cache

    r = get_cache()
    settings_raw = await r.get(f"temp_filter_settings:{user_id}")
    import json

    settings = json.loads(settings_raw) if settings_raw else {}

    # Defaults from settings dict
    match_mode = settings.get("matchMode", "contains")
    case_sensitive = settings.get("caseSensitive", False)
    is_admin_only = settings.get("isAdminOnly", False)

    buttons = []

    # Admin Only Toggle
    admin_btn_key = (
        "panel.btn_filter_admins_only" if is_admin_only else "panel.btn_filter_all_users"
    )
    buttons.append(
        [
            InlineKeyboardButton(
                f"{await at(user_id, admin_btn_key)}: ✅",
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
                f"{await at(user_id, case_btn_key)}: ✅",
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
            InlineKeyboardButton(f"{current_page + 1} / {total_pages}", callback_data="none")
        )

    if (current_page + 1) * page_size < total_count:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}:{current_page + 1}")
        )
    return nav_row
