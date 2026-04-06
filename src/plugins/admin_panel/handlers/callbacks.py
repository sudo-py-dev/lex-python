import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.db.models import GroupCleaner, NightLock, Reminder
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at

from .. import get_ctx
from ..decorators import AdminPanelContext, admin_panel_context
from ..repository import get_chat_settings, toggle_service_type, toggle_setting
from .ai_kbs import ai_menu_kb, model_selection_kb
from .keyboards import (
    cleaner_menu_kb,
    flood_kb,
    general_category_kb,
    main_menu_kb,
    moderation_category_kb,
    my_groups_kb,
    nightlock_menu_kb,
    reminders_menu_kb,
    rules_kb,
    scheduler_menu_kb,
    security_category_kb,
    welcome_kb,
)
from .moderation_kbs import logging_kb, slowmode_kb, user_warns_kb, warns_kb
from .security_kbs import captcha_kb, raid_kb, url_scanner_kb
from .service_cleaner import service_cleaner_kb, service_cleaner_types_kb


@bot.on_callback_query(filters.regex(r"^panel:(.*)"))
async def panel_callback_handler(client: Client, callback: CallbackQuery) -> None:
    if not callback.message:
        return

    data = callback.data.split(":")
    action = data[1]
    ctx = get_ctx()
    user_id = callback.from_user.id

    if action == "close":
        await callback.message.delete()
        await callback.answer()
        return

    if action == "my_groups":
        kb = await my_groups_kb(ctx, client, user_id)
        await callback.message.edit_text(
            await at(user_id, "panel.my_groups_title"), reply_markup=kb
        )
        await callback.answer()
        return

    if action == "select_chat":
        from src.plugins.connections import set_active_chat

        if len(data) >= 3:
            new_chat_id = int(data[2])
            await set_active_chat(ctx, user_id, new_chat_id)
            is_pm = callback.message.chat.type == ChatType.PRIVATE
            at_id = user_id if is_pm else new_chat_id
            await callback.message.edit_text(
                await at(at_id, "panel.main_text"),
                reply_markup=await main_menu_kb(new_chat_id, user_id=user_id if is_pm else None),
            )
            await callback.answer(await at(at_id, "panel.switch_chat"))
        return

    if action == "language":
        target = data[2] if len(data) > 2 else None
        if target == "pm":
            from src.plugins.language import language_picker_kb

            await callback.message.edit_text(
                await at(user_id, "language.user_picker_header"),
                reply_markup=await language_picker_kb(ctx, user_id, is_pm=True),
            )
            await callback.answer()
            return

    if action == "set_lang":
        target_id = int(data[3]) if len(data) > 3 and data[3] != "None" else None
        if target_id is None:
            new_lang = data[2]
            from src.plugins.language import set_chat_lang

            await set_chat_lang(ctx, user_id, new_lang)
            kb = await my_groups_kb(ctx, client, user_id)
            await callback.message.edit_text(
                await at(user_id, "panel.my_groups_title"), reply_markup=kb
            )
            await callback.answer(await at(user_id, "panel.user_lang_set", lang=new_lang.upper()))
            return

    await protected_panel_callback_handler(client, callback)


@admin_panel_context
async def protected_panel_callback_handler(
    client: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext
) -> None:
    data = callback.data.split(":")
    action = data[1]
    user_id = callback.from_user.id
    chat_id = ap_ctx.chat_id
    at_id = ap_ctx.at_id
    ctx = ap_ctx.ctx
    is_pm = ap_ctx.is_pm

    if action == "main":
        await callback.message.edit_text(
            await at(at_id, "panel.main_text"),
            reply_markup=await main_menu_kb(chat_id, user_id=user_id if is_pm else None),
        )
        await callback.answer()
    elif action == "category":
        if len(data) >= 3:
            cat = data[2]
            if cat == "security":
                kb = await security_category_kb(chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.security_text"), reply_markup=kb
                )
            elif cat == "moderation":
                kb = await moderation_category_kb(chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.moderation_text"), reply_markup=kb
                )
            elif cat == "general":
                kb = await general_category_kb(chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.general_text"), reply_markup=kb
                )
            elif cat == "scheduler":
                kb = await scheduler_menu_kb(chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.scheduler_text"), reply_markup=kb
                )
            elif cat == "ai":
                kb = await ai_menu_kb(chat_id, user_id=user_id if is_pm else None)
                s = await AIRepository.get_settings(ctx, chat_id)
                provider = s.provider.upper() if s else "OPENAI"
                is_enabled = s.isEnabled if s else False
                model = (s.modelId if s else "N/A") or "N/A"
                status_text = await at(
                    at_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}"
                )
                await callback.message.edit_text(
                    await at(
                        at_id, "panel.ai_text", status=status_text, provider=provider, model=model
                    ),
                    reply_markup=kb,
                )
            await callback.answer()

    elif action == "langblock":
        page = int(data[2]) if len(data) > 2 else 0
        from .moderation_kbs import langblock_kb

        kb = await langblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.langblock_text"),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "entityblock":
        page = int(data[2]) if len(data) > 2 else 0
        from .moderation_kbs import entityblock_kb

        kb = await entityblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.entityblock_text"),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "blacklist":
        page = int(data[2]) if len(data) > 2 else 0
        from .moderation_kbs import blacklist_kb

        kb = await blacklist_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.blacklist_text"),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "blacklist_remove":
        if len(data) >= 3:
            bid = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            async with ctx.db() as session:
                from src.db.models import Blacklist

                obj = await session.get(Blacklist, bid)
                if obj:
                    await session.delete(obj)
                    await session.commit()
                    await callback.answer(await at(at_id, "panel.blacklist_removed_success"))
                else:
                    await callback.answer(
                        await at(at_id, "panel.blacklist_not_found"), show_alert=True
                    )

            from .moderation_kbs import blacklist_kb

            kb = await blacklist_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "cycle_blacklist_action":
        page = int(data[2]) if len(data) > 2 else 0
        settings = await get_chat_settings(ctx, chat_id)

        actions = ["delete", "mute", "kick", "ban", "warn"]
        cur = settings.blacklistAction.lower()
        try:
            nxt = actions[(actions.index(cur) + 1) % len(actions)]
        except ValueError:
            nxt = "delete"

        async with ctx.db() as session:
            from src.db.models import GroupSettings

            gs = await session.get(GroupSettings, chat_id)
            if gs:
                gs.blacklistAction = nxt
                session.add(gs)
                await session.commit()

        await callback.answer(
            await at(at_id, "panel.blacklist_action_set", action=await at(at_id, f"action.{nxt}")),
            show_alert=True,
        )
        from .moderation_kbs import blacklist_kb

        kb = await blacklist_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "cycle_langblock_action":
        if len(data) >= 3:
            bid = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0

            actions = ["delete", "mute", "kick", "ban", "warn"]

            async with ctx.db() as session:
                from src.db.models import BlockedLanguage

                obj = await session.get(BlockedLanguage, bid)
                if obj:
                    cur = obj.action.lower()
                    try:
                        nxt = actions[(actions.index(cur) + 1) % len(actions)]
                    except ValueError:
                        nxt = "delete"

                    obj.action = nxt
                    session.add(obj)
                    await session.commit()

                    await callback.answer(
                        await at(
                            at_id,
                            "panel.langblock_action_set",
                            action=await at(at_id, f"action.{nxt}"),
                        )
                    )
                else:
                    await callback.answer(await at(at_id, "panel.error_generic"), show_alert=True)

            from .moderation_kbs import langblock_kb

            kb = await langblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "language":
        from src.plugins.language import language_picker_kb

        await callback.message.edit_text(
            await at(at_id, "language.group_picker_header"),
            reply_markup=await language_picker_kb(ctx, chat_id, is_pm=False),
        )
        await callback.answer()
    elif action == "set_lang":
        if len(data) >= 3:
            new_lang = data[2]
            target_id = int(data[3]) if len(data) > 3 and data[3] != "None" else None

            if target_id is not None:
                from src.plugins.language import set_chat_lang

                await set_chat_lang(ctx, target_id, new_lang)
                kb = await main_menu_kb(target_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.main_text"), reply_markup=kb
                )
                await callback.answer(
                    await at(at_id, "panel.group_lang_set", lang=new_lang.upper())
                )

    elif action == "flood":
        kb = await flood_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.flood_text"), reply_markup=kb)
        await callback.answer()
    elif action == "welcome":
        kb = await welcome_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.welcome_text"), reply_markup=kb)
        await callback.answer()
    elif action == "rules":
        kb = await rules_kb(chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.rules_text"), reply_markup=kb)
        await callback.answer()
    elif action == "raid":
        s = await get_chat_settings(ctx, chat_id)
        kb = await raid_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        status = await at(
            at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
        )
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.raid_text",
                status=status,
                action=await at(at_id, f"action.{s.raidAction.lower()}"),
            ),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "captcha":
        s = await get_chat_settings(ctx, chat_id)
        kb = await captcha_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        status = await at(
            at_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
        )
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.captcha_text",
                status=status,
                mode=await at(at_id, f"mode.{s.captchaMode.lower()}"),
                timeout=s.captchaTimeout,
                action=await at(at_id, "action.ban"),
            ),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "urlscanner":
        s = await get_chat_settings(ctx, chat_id)
        kb = await url_scanner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        status = await at(
            at_id, "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled"
        )
        with contextlib.suppress(MessageNotModified):
            await callback.message.edit_text(
                await at(
                    at_id,
                    "panel.urlscanner_text",
                    status=status,
                    key="********" if s.gsbKey else await at(at_id, "panel.not_set"),
                ),
                reply_markup=kb,
            )
        await callback.answer()
    elif action == "warns":
        s = await get_chat_settings(ctx, chat_id)
        kb = await warns_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.warns_text",
                limit=s.warnLimit,
                action=await at(at_id, f"action.{s.warnAction.lower()}"),
                expiry=await at(at_id, f"expiry.{s.warnExpiry.lower()}"),
            ),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "slowmode":
        from src.db.repositories.slowmode import get_slowmode

        i = await get_slowmode(ctx, chat_id)
        kb = await slowmode_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.slowmode_text", interval=i), reply_markup=kb
        )
        await callback.answer()
    elif action == "logging":
        s = await get_chat_settings(ctx, chat_id)
        kb = await logging_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.logging_text",
                channel=s.logChannelId or await at(at_id, "panel.not_set"),
            ),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "logging_picker":
        from .moderation_kbs import log_channel_picker_kb

        kb = await log_channel_picker_kb(ctx, chat_id, user_id=user_id if is_pm else None)

        cache = get_cache()
        await cache.set(f"ap:logging_picker:{user_id}", chat_id, ttl=300)

        await client.send_message(
            user_id if is_pm else callback.message.chat.id,
            await at(at_id, "panel.logging_picker_text"),
            reply_markup=kb,
        )
        await callback.message.delete()
        await callback.answer()
    elif action == "logging_set":
        from ..repository import update_chat_setting

        new_log_id = int(data[2])
        await update_chat_setting(ctx, chat_id, "logChannelId", new_log_id)
        await callback.answer(await at(at_id, "panel.setting_updated"))

        s = await get_chat_settings(ctx, chat_id)
        kb = await logging_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.logging_text",
                channel=s.logChannelId or await at(at_id, "panel.not_set"),
            ),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "langblock":
        page = int(data[2]) if len(data) > 2 else 0
        from .moderation_kbs import langblock_kb

        kb = await langblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.langblock_text"),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "rem_langblock":
        if len(data) >= 3:
            code = data[2]
            from src.plugins.lang_block import remove_lang_block

            await remove_lang_block(ctx, chat_id, code)

            from .moderation_kbs import langblock_kb

            kb = await langblock_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(await at(at_id, "panel.langblock_removed", code=code.upper()))
    elif action == "cycle_lang_action":
        if len(data) >= 3:
            code = data[2]
            page = int(data[3]) if len(data) > 3 else 0
            from src.plugins.lang_block import add_lang_block, get_lang_blocks

            blocks = {b.langCode: b for b in await get_lang_blocks(ctx, chat_id)}
            if code in blocks:
                current_action = blocks[code].action.lower()
                actions_cycle = ["delete", "mute", "kick", "ban"]
                try:
                    next_idx = (actions_cycle.index(current_action) + 1) % len(actions_cycle)
                except ValueError:
                    next_idx = 0
                next_action = actions_cycle[next_idx]

                await add_lang_block(ctx, chat_id, code, next_action)

                from .moderation_kbs import langblock_kb

                kb = await langblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
                await callback.message.edit_reply_markup(reply_markup=kb)
                await callback.answer(
                    await at(at_id, "panel.langblock_action_set", action=next_action.capitalize())
                )
    elif action == "svc":
        if len(data) >= 3 and data[2] == "types":
            page = int(data[3])
            kb = await service_cleaner_types_kb(
                ctx, chat_id, page, user_id=user_id if ap_ctx.is_pm else None
            )
            total = __import__("math").ceil(
                len(
                    [
                        e.name
                        for e in __import__("pyrogram").enums.MessageServiceType
                        if e.name != "UNSUPPORTED"
                    ]
                )
                / 10
            )
            text = await at(
                at_id, "panel.service_cleaner_types_text", page=page + 1, total=max(1, total)
            )
            await callback.message.edit_text(text, reply_markup=kb)
        else:
            kb = await service_cleaner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_text(
                await at(at_id, "panel.service_cleaner_text"), reply_markup=kb
            )
        await callback.answer()
    elif action == "tst":
        if len(data) >= 4:
            service_type = data[2]
            page = int(data[3])
            await toggle_service_type(ctx, chat_id, service_type)
            kb = await service_cleaner_types_kb(
                ctx, chat_id, page, user_id=user_id if ap_ctx.is_pm else None
            )
            with contextlib.suppress(MessageNotModified):
                await callback.message.edit_reply_markup(reply_markup=kb)
            label_key = f"panel.service_type_{service_type}"
            localized_type = await at(at_id, label_key)
            if localized_type == label_key:
                localized_type = service_type.replace("_", " ").title()

            await callback.answer(
                await at(at_id, "panel.service_cleaner_toggled", type=localized_type)
            )
    elif action == "tgs":
        if len(data) >= 3:
            field = data[2]
            await toggle_setting(ctx, chat_id, field)

            if field == "cleanAllServices":
                kb = await service_cleaner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            elif field in ("raidEnabled",):
                kb = await raid_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                s = await get_chat_settings(ctx, chat_id)
                status = await at(
                    at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.raid_text",
                        status=status,
                        threshold=s.raidThreshold,
                        window=s.raidWindow,
                        action=await at(at_id, f"action.{s.raidAction.lower()}"),
                    ),
                    reply_markup=kb,
                )
                return
            elif field in ("captchaEnabled",):
                kb = await captcha_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                s = await get_chat_settings(ctx, chat_id)
                status = await at(
                    at_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.captcha_text",
                        status=status,
                        mode=await at(at_id, f"mode.{s.captchaMode.lower()}"),
                        timeout=s.captchaTimeout,
                        action=await at(at_id, "action.ban"),
                    ),
                    reply_markup=kb,
                )
                return
            elif field == "urlScannerEnabled":
                kb = await url_scanner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                s = await get_chat_settings(ctx, chat_id)
                status = await at(
                    at_id,
                    "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled",
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.urlscanner_text",
                        status=status,
                        key="********" if s.gsbKey else "None",
                    ),
                    reply_markup=kb,
                )
                return
            else:
                kb = await welcome_kb(ctx, chat_id, user_id=user_id if is_pm else None)

            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(await at(at_id, "panel.setting_updated"))
    elif action == "toggle_private_rules":
        from src.db.repositories.rules import get_rules, toggle_private_rules

        rules = await get_rules(ctx, chat_id)
        new_state = not (rules.privateMode if rules else False)
        await toggle_private_rules(ctx, chat_id, new_state)

        kb = await rules_kb(chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer(await at(at_id, "panel.setting_updated"))
    elif action == "cycle":
        if len(data) >= 3:
            field = data[2]
            async with ctx.db() as session:
                s = await get_chat_settings(ctx, chat_id)
                if field == "warnAction":
                    nxt = {"kick": "ban", "ban": "mute", "mute": "kick"}[s.warnAction]
                    s.warnAction = nxt
                    session.add(s)
                    await session.commit()
                    kb = await warns_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_text(
                        await at(
                            at_id,
                            "panel.warns_text",
                            limit=s.warnLimit,
                            action=await at(at_id, f"action.{nxt}"),
                            expiry=await at(at_id, f"expiry.{s.warnExpiry.lower()}"),
                        ),
                        reply_markup=kb,
                    )
                elif field == "warnExpiry":
                    nxt = {"never": "24h", "24h": "7d", "7d": "30d", "30d": "never"}[s.warnExpiry]
                    s.warnExpiry = nxt
                    session.add(s)
                    await session.commit()
                    kb = await warns_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_text(
                        await at(
                            at_id,
                            "panel.warns_text",
                            limit=s.warnLimit,
                            action=await at(at_id, f"action.{s.warnAction.lower()}"),
                            expiry=await at(at_id, f"expiry.{nxt}"),
                        ),
                        reply_markup=kb,
                    )
                elif field == "raidAction":
                    nxt = {"lock": "kick", "kick": "ban", "ban": "lock"}[s.raidAction]
                    s.raidAction = nxt
                    session.add(s)
                    await session.commit()
                    kb = await raid_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    status = await at(
                        at_id,
                        "panel.status_enabled" if s.raidEnabled else "panel.status_disabled",
                    )
                    await callback.message.edit_text(
                        await at(
                            at_id,
                            "panel.raid_text",
                            status=status,
                            threshold=s.raidThreshold,
                            window=s.raidWindow,
                            action=await at(at_id, f"action.{s.raidAction.lower()}"),
                        ),
                        reply_markup=kb,
                    )
                elif field == "captchaMode":
                    nxt = {"button": "math", "math": "poll", "poll": "image", "image": "button"}[
                        s.captchaMode.lower()
                    ]
                    s.captchaMode = nxt
                    session.add(s)
                    await session.commit()
                    kb = await captcha_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    status = await at(
                        at_id,
                        "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled",
                    )
                    await callback.message.edit_text(
                        await at(
                            at_id,
                            "panel.captcha_text",
                            status=status,
                            mode=await at(at_id, f"mode.{s.captchaMode.lower()}"),
                            timeout=s.captchaTimeout,
                            action=await at(at_id, "action.ban"),
                        ),
                        reply_markup=kb,
                    )
                await callback.answer()
    elif action == "lang_cycle_action":
        if len(data) >= 3:
            lang_code = data[2]
            from src.plugins.lang_block import add_lang_block, get_lang_blocks

            blocks = await get_lang_blocks(ctx, chat_id)
            block = next((b for b in blocks if b.langCode == lang_code), None)
            if block:
                nxt = {"delete": "mute", "mute": "kick", "kick": "ban", "ban": "delete"}[
                    block.action.lower()
                ]
                await add_lang_block(ctx, chat_id, lang_code, nxt)
                from .moderation_kbs import langblock_kb

                kb = await langblock_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_reply_markup(reply_markup=kb)
                await callback.answer(
                    await at(
                        at_id, "panel.langblock_action_set", action=await at(at_id, f"action.{nxt}")
                    )
                )
    elif action == "toggle_entity":
        if len(data) >= 3:
            etype = data[2]
            page = int(data[3]) if len(data) > 3 else 0
            from src.plugins.entity_block import (
                add_blocked_entity,
                get_blocked_entities,
                remove_blocked_entity,
            )

            blocks = await get_blocked_entities(ctx, chat_id)
            block = next((b for b in blocks if b.entityType == etype), None)

            if not block:
                await add_blocked_entity(ctx, chat_id, etype, "delete")
                next_action = "DELETE"
            else:
                cycle_map = {
                    "delete": "warn",
                    "warn": "mute",
                    "mute": "kick",
                    "kick": "ban",
                    "ban": None,
                }
                nxt = cycle_map.get(block.action.lower())
                if nxt:
                    await add_blocked_entity(ctx, chat_id, etype, nxt)
                    next_action = nxt.upper()
                else:
                    await remove_blocked_entity(ctx, chat_id, etype)
                    next_action = "OFF"

            res_msg = await at(
                at_id, "panel.entity_block_updated", type=etype.upper(), status=next_action
            )
            from .moderation_kbs import entityblock_kb

            kb = await entityblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(res_msg)
    elif action == "lang_remove":
        if len(data) >= 3:
            lang_code = data[2]
            from src.plugins.lang_block import remove_lang_block

            await remove_lang_block(ctx, chat_id, lang_code)
            from .moderation_kbs import langblock_kb

            kb = await langblock_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(
                await at(at_id, "panel.langblock_removed_item", lang=lang_code.upper())
            )
    elif action == "reset_warns":
        from src.db.repositories.warns import reset_all_chat_warns

        await reset_all_chat_warns(ctx, chat_id)
        await callback.answer(await at(at_id, "panel.warns_reset_success"), show_alert=True)
    elif action == "toggle_flood_action":
        async with ctx.db() as session:
            settings = await get_chat_settings(ctx, chat_id)
            next_action = {"mute": "kick", "kick": "ban", "ban": "mute"}[settings.floodAction]
            settings.floodAction = next_action
            session.add(settings)
            await session.commit()
            kb = await flood_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(
                await at(
                    at_id, "panel.action_updated", action=await at(at_id, f"action.{next_action}")
                )
            )
    elif action == "noop":
        await callback.answer(await at(at_id, "panel.noop_alert"), show_alert=True)
    elif action == "user_warns":
        page = int(data[2]) if len(data) > 2 else 0
        kb = await user_warns_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.user_warns_text"),
            reply_markup=kb,
        )
        await callback.answer()
    elif action == "user_warn_reset":
        if len(data) >= 3:
            target_uid = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            from src.db.repositories.warns import reset_warns

            await reset_warns(ctx, chat_id, target_uid)
            kb = await user_warns_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(await at(at_id, "panel.user_warns_reset_success"))
    elif action == "user_warn_info":
        if len(data) >= 3:
            target_uid = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            from src.db.repositories.warns import get_warns

            warns = await get_warns(ctx, chat_id, target_uid)

            if not warns:
                await callback.answer(await at(at_id, "warns.no_warns"), show_alert=True)
                return

            reasons = "\n".join(
                [f"- {w.reason or await at(at_id, 'common.no_reason')}" for w in warns]
            )
            await callback.answer(
                f"{await at(at_id, 'common.user_id_label')} {target_uid}\n{await at(at_id, 'panel.user_warns_header')}\n{reasons}",
                show_alert=True,
            )

    elif action == "timezone":
        page = int(data[2]) if len(data) > 2 else 0
        from .keyboards import timezone_picker_kb

        settings = await get_chat_settings(ctx, chat_id)
        kb = await timezone_picker_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(
            await at(at_id, "panel.timezone_text", timezone=settings.timezone),
            reply_markup=kb,
        )
        await callback.answer()

    elif action == "timezone_region":
        region = data[2]
        page = int(data[3]) if len(data) > 3 else 0
        from .keyboards import timezone_picker_kb

        kb = await timezone_picker_kb(
            ctx, chat_id, page, user_id=user_id if is_pm else None, region=region
        )
        await callback.message.edit_text(
            await at(at_id, "panel.timezone_region_text", region=region), reply_markup=kb
        )
        await callback.answer()

    elif action == "timezone_filter":
        q = data[2]
        page = int(data[3]) if len(data) > 3 else 0
        from .keyboards import timezone_picker_kb

        kb = await timezone_picker_kb(
            ctx, chat_id, page, user_id=user_id if is_pm else None, filter_query=q
        )
        await callback.message.edit_text(
            await at(at_id, "panel.timezone_search_results_text", query=q), reply_markup=kb
        )
        await callback.answer()

    elif action == "timezone_search":
        from .input_handlers import capture_next_input

        await capture_next_input(user_id, chat_id, "timezoneSearch")
        await callback.message.edit_text(await at(at_id, "panel.timezone_search_prompt"))
        await callback.answer()

    elif action == "set_tz":
        if len(data) >= 3:
            new_tz = data[2]
            from src.db.models import GroupSettings
            from src.plugins.scheduler.manager import SchedulerManager

            async with ctx.db() as session:
                gs = await session.get(GroupSettings, chat_id)
                if gs:
                    gs.timezone = new_tz
                    session.add(gs)
                    await session.commit()
                    await SchedulerManager.sync_group(ctx, chat_id)

            await callback.answer(await at(at_id, "panel.timezone_set_success", tz=new_tz))
            kb = await scheduler_menu_kb(chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_text(
                await at(at_id, "panel.scheduler_text"), reply_markup=kb
            )

    elif action == "reminders":
        kb = await reminders_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.reminder_text"), reply_markup=kb)
        await callback.answer()

    elif action == "ai":
        if len(data) >= 3:
            sub = data[2]
            if sub == "toggle":
                s = await AIRepository.get_settings(ctx, chat_id)
                cur = s.isEnabled if s else False
                await AIRepository.update_settings(ctx, chat_id, isEnabled=not cur)
                kb = await ai_menu_kb(chat_id, user_id=user_id if is_pm else None)
                s = await AIRepository.get_settings(ctx, chat_id)
                status_text = await at(
                    at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}"
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.ai_text",
                        status=status_text,
                        provider=s.provider.upper(),
                        model=s.modelId or "N/A",
                    ),
                    reply_markup=kb,
                )
            elif sub == "cycle_provider":
                s = await AIRepository.get_settings(ctx, chat_id)
                providers = ["openai", "gemini", "deepseek", "groq", "qwen", "anthropic"]
                defaults = {
                    "openai": "gpt-4o-mini",
                    "gemini": "gemini-1.5-flash",
                    "deepseek": "deepseek-chat",
                    "groq": "llama3-8b-8192",
                    "qwen": "qwen-plus",
                    "anthropic": "claude-3-haiku-20240307",
                }
                cur = s.provider if s else "openai"
                try:
                    nxt = providers[(providers.index(cur) + 1) % len(providers)]
                except ValueError:
                    nxt = "openai"

                await AIRepository.update_settings(
                    ctx, chat_id, provider=nxt, modelId=defaults[nxt]
                )
                kb = await ai_menu_kb(chat_id, user_id=user_id if is_pm else None)
                s = await AIRepository.get_settings(ctx, chat_id)
                status_text = await at(
                    at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}"
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.ai_text",
                        status=status_text,
                        provider=s.provider.upper(),
                        model=s.modelId or "N/A",
                    ),
                    reply_markup=kb,
                )
            elif sub == "model_list":
                s = await AIRepository.get_settings(ctx, chat_id)
                provider = s.provider if s else "openai"
                kb = await model_selection_kb(provider, chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_text(
                    await at(at_id, "panel.ai_select_model_text", provider=provider.upper()),
                    reply_markup=kb,
                )
            elif sub == "set_model":
                if len(data) >= 4:
                    model_id = data[3]
                    await AIRepository.update_settings(ctx, chat_id, modelId=model_id)
                    await callback.answer(await at(at_id, "panel.ai_model_set", model=model_id))

                    kb = await ai_menu_kb(chat_id, user_id=user_id if is_pm else None)
                    s = await AIRepository.get_settings(ctx, chat_id)
                    status_text = await at(
                        at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}"
                    )
                    await callback.message.edit_text(
                        await at(
                            at_id,
                            "panel.ai_text",
                            status=status_text,
                            provider=s.provider.upper(),
                            model=s.modelId or "N/A",
                        ),
                        reply_markup=kb,
                    )
            elif sub == "clear_ctx":
                await AIRepository.clear_context(ctx, chat_id)
                await callback.answer(await at(at_id, "panel.ai_ctx_cleared"))
        return

    elif action == "nightlock":
        kb = await nightlock_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.nightlock_text"), reply_markup=kb)
        await callback.answer()

    elif action == "cleaner":
        kb = await cleaner_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.cleaner_text"), reply_markup=kb)
        await callback.answer()

    elif action == "toggle_reminder":
        if len(data) >= 3:
            rid = int(data[2])
            async with ctx.db() as session:
                rem = await session.get(Reminder, rid)
                if rem:
                    rem.isActive = not rem.isActive
                    session.add(rem)
                    await session.commit()

                    from src.plugins.scheduler.manager import SchedulerManager

                    await SchedulerManager.sync_group(ctx, chat_id)

                    await callback.answer(await at(at_id, "panel.setting_updated"))
                    kb = await reminders_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "delete_reminder":
        if len(data) >= 3:
            rid = int(data[2])
            async with ctx.db() as session:
                rem = await session.get(Reminder, rid)
                if rem:
                    await session.delete(rem)
                    await session.commit()
                    from src.plugins.scheduler.manager import SchedulerManager

                    await SchedulerManager.sync_group(ctx, chat_id)
                    await callback.answer(await at(at_id, "panel.setting_updated"))
                    kb = await reminders_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "toggle_nightlock":
        async with ctx.db() as session:
            lock = await session.get(NightLock, chat_id)
            if lock:
                lock.isEnabled = not lock.isEnabled
                session.add(lock)
                await session.commit()

                from src.plugins.scheduler.manager import SchedulerManager

                await SchedulerManager.sync_group(ctx, chat_id)

                await callback.answer(await at(at_id, "panel.setting_updated"))
                kb = await nightlock_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "toggle_cleaner":
        if len(data) >= 3:
            ctype = data[2]
            async with ctx.db() as session:
                cleaner = await session.get(GroupCleaner, chat_id)
                if cleaner:
                    if ctype == "deleted":
                        cleaner.cleanDeleted = not cleaner.cleanDeleted
                    elif ctype == "fake":
                        cleaner.cleanFake = not cleaner.cleanFake
                    session.add(cleaner)
                    await session.commit()

                    from src.plugins.scheduler.manager import SchedulerManager

                    await SchedulerManager.sync_group(ctx, chat_id)

                    await callback.answer(await at(at_id, "panel.setting_updated"))
                    kb = await cleaner_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "input":
        if len(data) >= 3:
            field = data[2]
            page = data[3] if len(data) > 3 else 0
            from .input_handlers import capture_next_input

            await capture_next_input(user_id, chat_id, field, callback.message.id, page)

            prompt_key = f"panel.input_prompt_{field}"
            prompt_text = await at(user_id, prompt_key)

            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            await at(user_id, "panel.btn_cancel_input"),
                            callback_data="panel:cancel_input",
                        )
                    ]
                ]
            )
            await callback.message.edit_text(prompt_text, reply_markup=kb)
            await callback.answer()
    elif action == "cancel_input":
        r = get_cache()
        await r.delete(f"panel_input:{user_id}")
        await callback.answer(await at(user_id, "panel.input_cancelled"), show_alert=True)
        await callback.message.edit_text(
            await at(at_id, "panel.main_text"),
            reply_markup=await main_menu_kb(chat_id, user_id=user_id if is_pm else None),
        )
