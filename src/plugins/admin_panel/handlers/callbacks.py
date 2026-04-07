import contextlib
import json

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import get_context
from src.db.models import ChatCleaner, ChatNightLock, Reminder
from src.plugins.ai_assistant.repository import AIRepository
from src.utils.i18n import at
from src.utils.permissions import is_admin

from ..decorators import AdminPanelContext, admin_panel_context
from ..repository import (
    get_chat_info,
    get_chat_settings,
    resolve_chat_type,
    set_active_chat,
    toggle_service_type,
    toggle_setting,
)
from ..validation import is_setting_allowed
from .ai_kbs import ai_menu_kb, model_selection_kb
from .input_handlers import capture_next_input
from .keyboards import (
    ai_security_kb,
    channel_settings_kb,
    channel_watermark_kb,
    channels_menu_kb,
    chatnightlock_menu_kb,
    cleaner_menu_kb,
    filters_menu_kb,
    flood_kb,
    general_category_kb,
    main_menu_kb,
    moderation_category_kb,
    my_chats_menu_kb,
    my_groups_kb,
    reminders_menu_kb,
    rules_kb,
    scheduler_menu_kb,
    security_category_kb,
    welcome_kb,
)
from .moderation_kbs import logging_kb, slowmode_kb, user_warns_kb, warns_kb
from .security_kbs import (
    captcha_kb,
    raid_kb,
    url_scanner_kb,
)
from .service_cleaner import service_cleaner_kb, service_cleaner_types_kb


AI_PROVIDERS = ["openai", "gemini", "deepseek", "groq", "qwen", "anthropic"]
AI_PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "deepseek": "deepseek-chat",
    "groq": "llama3-8b-8192",
    "qwen": "qwen-plus",
    "anthropic": "claude-3-haiku-20240307",
}


async def _render_ai_panel(callback: CallbackQuery, ctx, chat_id: int, at_id: int, user_id: int) -> None:
    s = await AIRepository.get_settings(ctx, chat_id)
    provider = (s.provider if s else "openai").upper()
    is_enabled = s.isEnabled if s else False
    model = (s.modelId if s else "N/A") or "N/A"
    status_text = await at(at_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}")
    kb = await ai_menu_kb(chat_id, user_id=user_id)
    await callback.message.edit_text(
        await at(at_id, "panel.ai_text", status=status_text, provider=provider, model=model),
        reply_markup=kb,
    )


async def _render_ai_guard_panel(
    callback: CallbackQuery, ctx, chat_id: int, at_id: int, user_id: int
) -> str:
    from src.db.repositories.ai_guard import get_ai_guard_settings

    s = await get_ai_guard_settings(ctx, chat_id)
    status_label = await at(at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}")
    action_label = await at(at_id, f"action.{s.action}")
    await callback.message.edit_text(
        await at(
            at_id,
            "panel.ai_guard_text",
            status=status_label,
            action=action_label,
            model=s.modelId,
        ),
        reply_markup=await ai_security_kb(ctx, chat_id, user_id),
    )
    return action_label


def _next_ai_provider(current_provider: str) -> str:
    try:
        return AI_PROVIDERS[(AI_PROVIDERS.index(current_provider) + 1) % len(AI_PROVIDERS)]
    except ValueError:
        return AI_PROVIDERS[0]


def _panel_lang_id(is_pm: bool, user_id: int, chat_id: int) -> int:
    return user_id if is_pm else chat_id


def _plain(text: str) -> str:
    """Remove markdown-style markers for callback answers."""
    return (
        text.replace("**", "")
        .replace("__", "")
        .replace("`", "")
        .replace("||", "")
        .replace("[", "")
        .replace("]", "")
    )


@bot.on_callback_query(filters.regex(r"^panel:(.*)"))
async def panel_callback_handler(client: Client, callback: CallbackQuery) -> None:
    if not callback.message:
        return

    data = callback.data.split(":")
    action = data[1]
    ctx = get_context()
    user_id = callback.from_user.id
    ui_id = user_id

    # ── Flow A: User-level actions — no active chat required ──────────────────

    if action == "close":
        await callback.message.delete()
        await callback.answer()
        return

    if action == "my_chats":
        await callback.message.edit_text(
            await at(ui_id, "panel.main_text_user", user_id=user_id),
            reply_markup=await my_chats_menu_kb(user_id),
        )
        await callback.answer()
        return

    if action == "list_groups":
        kb = await my_groups_kb(ctx, client, user_id)
        await callback.message.edit_text(
            await at(ui_id, "panel.groups_list_title"), reply_markup=kb
        )
        await callback.answer()
        return

    if action == "list_channels":
        kb = await channels_menu_kb(ctx, client, user_id)
        await callback.message.edit_text(
            await at(ui_id, "panel.channels_list_title"), reply_markup=kb
        )
        await callback.answer()
        return

    if action == "select_chat":
        # Group selection: persists as active group, shows group panel
        if len(data) >= 3:
            new_chat_id = int(data[2])
            await set_active_chat(ctx, user_id, new_chat_id)
            is_pm = callback.message.chat.type == ChatType.PRIVATE
            at_id = _panel_lang_id(is_pm, user_id, new_chat_id)
            chat_type, chat_title = await get_chat_info(ctx, new_chat_id)
            await callback.message.edit_text(
                await at(at_id, "panel.main_text", user_id=user_id, title=chat_title),
                reply_markup=await main_menu_kb(
                    new_chat_id,
                    user_id=user_id if is_pm else None,
                    chat_type=chat_type,
                ),
            )
            await callback.answer(_plain(await at(at_id, "panel.switch_chat", user_id=user_id)))
        return

    if action == "select_channel":
        # Channel selection: bypasses main menu and goes straight to channel settings since channels don't use categories
        if len(data) >= 3:
            channel_id = int(data[2])
            s = await get_chat_settings(ctx, channel_id)
            title = s.title or f"Channel {channel_id}"
            kb = await channel_settings_kb(ctx, channel_id, user_id)
            await callback.message.edit_text(
                await at(ui_id, "panel.channel_settings_text", title=title, id=channel_id),
                reply_markup=kb,
            )
            await callback.answer(_plain(await at(ui_id, "panel.switch_chat", user_id=user_id)))
        return

    if action == "language" and len(data) >= 3 and data[2] == "user":
        # User personal language picker — no active chat needed
        from src.plugins.language import language_picker_kb

        await callback.message.edit_text(
            await at(ui_id, "language.user_picker_header"),
            reply_markup=await language_picker_kb(ctx, user_id, scope="user"),
        )
        await callback.answer()
        return

    if action == "set_lang" and len(data) >= 5 and data[2] == "user":
        # Apply user personal language — no active chat needed
        new_lang = data[4]
        from src.plugins.language import set_user_lang

        await set_user_lang(ctx, int(data[3]), new_lang)
        await callback.message.edit_text(
            await at(ui_id, "panel.main_text_user", user_id=user_id),
            reply_markup=await my_chats_menu_kb(user_id),
        )
        await callback.answer(_plain(await at(ui_id, "panel.user_lang_set", lang=new_lang.upper())))
        return

    # ── Flow C: Channel-level actions — channel_id is embedded in callback data ──
    # These never touch active_chat; admin check is done inline per-action.

    if action == "channel_settings":
        if len(data) >= 3:
            channel_id = int(data[2])
            if not await is_admin(client, channel_id, user_id):
                await callback.answer(
                    await at(ui_id, "error.no_membership_admin"), show_alert=True
                )
                return
            s = await get_chat_settings(ctx, channel_id)
            title = s.title or f"Channel {channel_id}"
            kb = await channel_settings_kb(ctx, channel_id, user_id)
            await callback.message.edit_text(
                await at(ui_id, "panel.channel_settings_text", title=title, id=channel_id),
                reply_markup=kb,
            )
            await callback.answer()
        return

    if action == "channel_watermark":
        if len(data) >= 3:
            channel_id = int(data[2])
            if not await is_admin(client, channel_id, user_id):
                await callback.answer(
                    await at(ui_id, "error.no_membership_admin"), show_alert=True
                )
                return
            s = await get_chat_settings(ctx, channel_id)
            cfg = {}
            if s.watermarkText and str(s.watermarkText).lstrip().startswith("{"):
                with contextlib.suppress(Exception):
                    cfg = json.loads(s.watermarkText)
            wm_text = (cfg.get("text") if isinstance(cfg, dict) else None) or s.watermarkText or "-"
            wm_type = (cfg.get("type") if isinstance(cfg, dict) else None) or "text"
            wm_color = (cfg.get("color") if isinstance(cfg, dict) else None) or "white"
            wm_style = (cfg.get("style") if isinstance(cfg, dict) else None) or "shadow"
            status = await at(ui_id, "panel.status_enabled" if s.watermarkEnabled else "panel.status_disabled")
            await callback.message.edit_text(
                await at(
                    ui_id,
                    "panel.channel_watermark_text",
                    status=status,
                    text=wm_text,
                    type=await at(ui_id, f"panel.wm_type_{wm_type}"),
                    color=await at(ui_id, f"panel.wm_color_{wm_color}"),
                    style=await at(ui_id, f"panel.wm_style_{wm_style}"),
                ),
                reply_markup=await channel_watermark_kb(ctx, channel_id, user_id),
            )
            await callback.answer()
        return

    if action == "toggle_ch":
        if len(data) >= 4:
            field = data[2]
            channel_id = int(data[3])
            if not await is_admin(client, channel_id, user_id):
                await callback.answer(
                    await at(ui_id, "error.no_membership_admin"), show_alert=True
                )
                return
            from src.db.repositories.chats import (
                get_chat_settings as get_ch_settings,
            )
            from src.db.repositories.chats import (
                toggle_setting as toggle_ch_setting,
            )
            from src.db.repositories.chats import (
                update_chat_setting as update_ch_setting,
            )

            if field == "reactionMode":
                s = await get_ch_settings(ctx, channel_id)
                new_mode = "random" if s.reactionMode == "all" else "all"
                await update_ch_setting(ctx, channel_id, field, new_mode)
            else:
                await toggle_ch_setting(ctx, channel_id, field)

            kb = await channel_settings_kb(ctx, channel_id, user_id)
            with contextlib.suppress(MessageNotModified):
                await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(_plain(await at(ui_id, "panel.setting_updated")))
        return

    if action == "cycle_wm":
        if len(data) >= 4:
            mode = data[2]
            channel_id = int(data[3])
            if not await is_admin(client, channel_id, user_id):
                await callback.answer(
                    await at(ui_id, "error.no_membership_admin"), show_alert=True
                )
                return
            from src.db.repositories.chats import (
                get_chat_settings as get_ch_settings,
            )
            from src.db.repositories.chats import (
                update_chat_setting as update_ch_setting,
            )

            s = await get_ch_settings(ctx, channel_id)
            cfg = {"text": s.watermarkText or "", "type": "text", "color": "white", "style": "shadow"}
            if s.watermarkText and str(s.watermarkText).lstrip().startswith("{"):
                with contextlib.suppress(Exception):
                    loaded = json.loads(s.watermarkText)
                    if isinstance(loaded, dict):
                        cfg.update({k: str(v) for k, v in loaded.items() if k in cfg})

            if mode == "type":
                cycle = ["text", "username"]
            elif mode == "color":
                cycle = ["white", "black", "red", "blue", "gold"]
            else:
                cycle = ["shadow", "outline", "plain"]

            current = cfg.get(mode if mode in ("type", "color", "style") else "style", cycle[0])
            try:
                nxt = cycle[(cycle.index(current) + 1) % len(cycle)]
            except ValueError:
                nxt = cycle[0]
            cfg[mode if mode in ("type", "color", "style") else "style"] = nxt
            await update_ch_setting(ctx, channel_id, "watermarkText", json.dumps(cfg))

            s = await get_chat_settings(ctx, channel_id)
            status = await at(ui_id, "panel.status_enabled" if s.watermarkEnabled else "panel.status_disabled")
            await callback.message.edit_text(
                await at(
                    ui_id,
                    "panel.channel_watermark_text",
                    status=status,
                    text=cfg.get("text") or "-",
                    type=await at(ui_id, f"panel.wm_type_{cfg.get('type', 'text')}"),
                    color=await at(ui_id, f"panel.wm_color_{cfg.get('color', 'white')}"),
                    style=await at(ui_id, f"panel.wm_style_{cfg.get('style', 'shadow')}"),
                ),
                reply_markup=await channel_watermark_kb(ctx, channel_id, user_id),
            )
            await callback.answer()
        return

    # ── Flow B: Group-level actions — requires an active connected chat ────────
    await protected_panel_callback_handler(client, callback)


@admin_panel_context
async def protected_panel_callback_handler(
    client: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext
) -> None:
    data = callback.data.split(":")
    action = data[1]
    user_id = callback.from_user.id
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, user_id, chat_id)
    ctx = ap_ctx.ctx
    is_pm = ap_ctx.is_pm

    if action == "main":
        if ap_ctx.chat_type == ChatType.CHANNEL:
            from src.db.repositories.chats import get_chat_settings as get_ch_settings

            from .keyboards import channel_settings_kb

            s = await get_ch_settings(ctx, chat_id)
            title = s.title or f"Channel {chat_id}"
            kb = await channel_settings_kb(ctx, chat_id, user_id)
            await callback.message.edit_text(
                await at(at_id, "panel.channel_settings_text", title=title, id=chat_id),
                reply_markup=kb,
            )
        else:
            await callback.message.edit_text(
                await at(at_id, "panel.main_text", user_id=user_id, title=ap_ctx.chat_title),
                reply_markup=await main_menu_kb(
                    chat_id, user_id=user_id if is_pm else None, chat_type=ap_ctx.chat_type
                ),
            )
        await callback.answer()
    elif action == "category":
        if len(data) >= 3:
            cat = data[2]
            chat_type = ap_ctx.chat_type.name.lower() if ap_ctx.chat_type else "supergroup"
            if cat == "security":
                kb = await security_category_kb(
                    chat_id, user_id=user_id if is_pm else None, chat_type=chat_type
                )
                title_key = (
                    "panel.security_text_channel"
                    if chat_type == "channel"
                    else "panel.security_text"
                )
                await callback.message.edit_text(await at(at_id, title_key), reply_markup=kb)
            elif cat == "moderation":
                kb = await moderation_category_kb(
                    chat_id, user_id=user_id if is_pm else None, chat_type=chat_type
                )
                title_key = (
                    "panel.moderation_text_channel"
                    if chat_type == "channel"
                    else "panel.moderation_text"
                )
                await callback.message.edit_text(await at(at_id, title_key), reply_markup=kb)
            elif cat == "general":
                kb = await general_category_kb(
                    chat_id, user_id=user_id if is_pm else None, chat_type=chat_type
                )
                title_key = (
                    "panel.general_text_channel" if chat_type == "channel" else "panel.general_text"
                )
                await callback.message.edit_text(await at(at_id, title_key), reply_markup=kb)
            elif cat == "scheduler":
                kb = await scheduler_menu_kb(
                    chat_id, user_id=user_id if is_pm else None, chat_type=chat_type
                )
                title_key = (
                    "panel.scheduler_text_channel"
                    if chat_type == "channel"
                    else "panel.scheduler_text"
                )
                await callback.message.edit_text(await at(at_id, title_key), reply_markup=kb)
            elif cat == "ai":
                await _render_ai_panel(callback, ctx, chat_id, at_id, user_id)
            elif cat == "ai_security":
                await _render_ai_guard_panel(callback, ctx, chat_id, at_id, user_id)

            await callback.answer()

    elif action == "toggle_ai_guard":
        from src.db.repositories.ai_guard import get_ai_guard_settings, update_ai_guard_settings

        s = await get_ai_guard_settings(ctx, chat_id)

        if not s.isEnabled and not s.apiKey:
            await callback.answer(
                _plain(await at(user_id, "panel.ai_guard_key_required")), show_alert=True
            )
            return

        await update_ai_guard_settings(ctx, chat_id, isEnabled=not s.isEnabled)
        await _render_ai_guard_panel(callback, ctx, chat_id, at_id, user_id)
        await callback.answer()

    elif action == "cycle_ai_guard_action":
        from src.db.repositories.ai_guard import get_ai_guard_settings, update_ai_guard_settings

        actions = ["delete", "warn", "mute", "ban"]
        s = await get_ai_guard_settings(ctx, chat_id)
        current_idx = actions.index(s.action) if s.action in actions else 0
        next_action = actions[(current_idx + 1) % len(actions)]

        await update_ai_guard_settings(ctx, chat_id, action=next_action)
        action_label = await _render_ai_guard_panel(callback, ctx, chat_id, at_id, user_id)
        await callback.answer(
            _plain(await at(user_id, "panel.ai_guard_action_set", action=action_label))
        )

    elif action == "set_groq_key":

        await capture_next_input(user_id, chat_id, "groqKey", prompt_msg_id=callback.message.id)
        await callback.message.edit_text(
            await at(at_id, "panel.input_prompt_groqKey"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            await at(at_id, "common.btn_cancel"),
                            callback_data="panel:category:ai_security",
                        )
                    ]
                ]
            ),
        )
        await callback.answer()

    elif action == "ai_guard_setup":
        await callback.message.edit_text(
            await at(at_id, "panel.ai_guard_setup_guide"),
            reply_markup=await ai_security_kb(ctx, chat_id, user_id),
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
                    await callback.answer(_plain(await at(at_id, "panel.blacklist_removed_success")))
                else:
                    await callback.answer(
                        await at(at_id, "panel.blacklist_not_found"), show_alert=True
                    )

            kb = await blacklist_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
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
            from src.db.models import ChatSettings

            gs = await session.get(ChatSettings, chat_id)
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
                    await callback.answer(_plain(await at(at_id, "panel.error_generic")), show_alert=True)

            from .moderation_kbs import langblock_kb

            kb = await langblock_kb(ctx, chat_id, page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "language":
        # Only chat scope reaches here; user scope is intercepted in the unprotected handler
        from src.plugins.language import language_picker_kb

        await callback.message.edit_text(
            await at(at_id, "language.group_picker_header"),
            reply_markup=await language_picker_kb(ctx, chat_id, scope="chat"),
        )
        await callback.answer()

    elif action == "set_lang":
        # Only chat scope reaches here; user scope is intercepted in the unprotected handler
        if len(data) >= 5 and data[2] == "chat":
            new_lang = data[4]
            from src.plugins.language import set_chat_lang

            await set_chat_lang(ctx, chat_id, new_lang)
            await callback.answer(
                _plain(await at(at_id, "panel.group_lang_set", lang=new_lang.upper()))
            )
            chat_type_ext = ap_ctx.chat_type.name.lower() if ap_ctx.chat_type else "supergroup"
            kb = await general_category_kb(
                chat_id, user_id=user_id if is_pm else None, chat_type=chat_type_ext
            )
            title_key = (
                "panel.general_text_channel" if chat_type_ext == "channel" else "panel.general_text"
            )
            await callback.message.edit_text(await at(at_id, title_key), reply_markup=kb)

    elif action == "flood":
        kb = await flood_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.flood_text"), reply_markup=kb)
        await callback.answer()
    elif action == "welcome":
        kb = await welcome_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.welcome_text"), reply_markup=kb)
        await callback.answer()
    elif action == "filters":
        page = int(data[2]) if len(data) > 2 else 0
        kb = await filters_menu_kb(ctx, chat_id, page=page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.filters_text"), reply_markup=kb)
        await callback.answer()
    elif action == "add_filter":
        from src.db.repositories.filters import get_filters_count

        count = await get_filters_count(ctx, chat_id)
        if count >= 150:
            await callback.answer(_plain(await at(at_id, "filter.limit_reached")), show_alert=True)
            return


        page = int(data[2]) if len(data) > 2 else 0
        await capture_next_input(
            user_id, chat_id, "filterKeyword", prompt_msg_id=callback.message.id, page=page
        )
        await callback.message.edit_text(
            await at(at_id, "panel.input_prompt_filterKeyword"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            await at(at_id, "common.btn_cancel"),
                            callback_data=f"panel:filters:{page}",
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
    elif action == "edit_filter":
        if len(data) >= 3:
            f_id = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            from src.db.models import Filter

            async with ctx.db() as session:
                f_obj = await session.get(Filter, f_id)
                if not f_obj:
                    await callback.answer(_plain(await at(at_id, "panel.error_generic")), show_alert=True)
                    return

                r = get_cache()
                import json

                # Pre-fill cache with existing data
                await r.set(f"temp_filter_kw:{user_id}", f_obj.keyword, ttl=600)
                await r.set(
                    f"temp_filter_resp:{user_id}",
                    json.dumps(
                        {
                            "text": f_obj.text,
                            "type": f_obj.responseType,
                            "file_id": f_obj.fileId,
                        }
                    ),
                    ttl=600,
                )
                await r.set(f"temp_filter_settings:{user_id}", json.dumps(f_obj.settings), ttl=600)
                await r.set(f"temp_filter_edit_id:{user_id}", str(f_id), ttl=600)


                await capture_next_input(
                    user_id, chat_id, "filterResponse", prompt_msg_id=callback.message.id, page=page
                )

                await callback.message.edit_text(
                    await at(at_id, "panel.input_prompt_filterResponse", keyword=f_obj.keyword),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    await at(at_id, "common.btn_cancel"),
                                    callback_data=f"panel:filters:{page}",
                                )
                            ]
                        ]
                    ),
                )
                await callback.answer()
    elif action == "rules":
        kb = await rules_kb(chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.rules_text"), reply_markup=kb)
        await callback.answer()
    elif action == "delete_filter":
        if len(data) >= 3:
            f_id = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            from src.db.repositories.filters import remove_filter_by_id

            success = await remove_filter_by_id(ctx, f_id)
            if success:
                await callback.answer(_plain(await at(at_id, "common.done")))
            else:
                await callback.answer(_plain(await at(at_id, "panel.error_generic")), show_alert=True)
            kb = await filters_menu_kb(ctx, chat_id, page=page, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "clear_filters":
        from src.db.repositories.filters import remove_all_filters

        await remove_all_filters(ctx, chat_id)
        await callback.answer(_plain(await at(at_id, "common.done")))
        kb = await filters_menu_kb(ctx, chat_id, page=0, user_id=user_id if is_pm else None)
        await callback.message.edit_reply_markup(reply_markup=kb)
    elif action == "toggle_filter":
        if len(data) >= 4:
            mode = data[2]
            page = int(data[3])
            r = get_cache()
            settings_raw = await r.get(f"temp_filter_settings:{user_id}")
            import json

            settings = json.loads(settings_raw) if settings_raw else {}

            if mode == "admin":
                settings["isAdminOnly"] = not settings.get("isAdminOnly", False)
            elif mode == "case":
                settings["caseSensitive"] = not settings.get("caseSensitive", False)
            elif mode == "match":
                settings["matchMode"] = (
                    "full" if settings.get("matchMode") == "contains" else "contains"
                )

            await r.set(f"temp_filter_settings:{user_id}", json.dumps(settings), ttl=600)
            from .keyboards import filter_options_kb

            kb = await filter_options_kb(ctx, chat_id, user_id, page)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer()
    elif action == "save_filter":
        page = int(data[2])
        r = get_cache()
        keyword = await r.get(f"temp_filter_kw:{user_id}")
        resp_raw = await r.get(f"temp_filter_resp:{user_id}")
        settings_raw = await r.get(f"temp_filter_settings:{user_id}")

        if not keyword or not resp_raw:
            await callback.answer(_plain(await at(at_id, "panel.error_generic")), show_alert=True)
            return

        import json

        resp_data = json.loads(resp_raw)
        settings = json.loads(settings_raw) if settings_raw else {}

        from src.db.repositories.filters import add_filter, update_filter_by_id

        edit_id_raw = await r.get(f"temp_filter_edit_id:{user_id}")
        if edit_id_raw:
            edit_id = int(edit_id_raw)
            await update_filter_by_id(
                ctx,
                edit_id,
                keyword,
                text=resp_data.get("text") or "",
                response_type=resp_data["type"],
                file_id=resp_data.get("file_id"),
                settings=settings,
            )
        else:
            await add_filter(
                ctx,
                chat_id,
                keyword,
                text=resp_data.get("text") or "",
                response_type=resp_data["type"],
                file_id=resp_data.get("file_id"),
                settings=settings,
            )

        # Cleanup
        await r.delete(f"temp_filter_kw:{user_id}")
        await r.delete(f"temp_filter_resp:{user_id}")
        await r.delete(f"temp_filter_settings:{user_id}")
        await r.delete(f"temp_filter_edit_id:{user_id}")

        await callback.answer(_plain(await at(at_id, "panel.input_success")))
        kb = await filters_menu_kb(ctx, chat_id, page=page, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.filters_text"), reply_markup=kb)
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
        await callback.answer(_plain(await at(at_id, "panel.setting_updated")))

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
    elif action == "lang_remove":
        if len(data) >= 3:
            code = data[2]
            from src.plugins.lang_block import remove_lang_block

            await remove_lang_block(ctx, chat_id, code)

            from .moderation_kbs import langblock_kb

            kb = await langblock_kb(ctx, chat_id, user_id=user_id if is_pm else None)
            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(
                await at(at_id, "panel.langblock_removed_item", lang=code.upper())
            )
    elif action == "lang_cycle_action":
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

            await callback.answer(_plain(await at(at_id, "common.btn_action", type=localized_type)))
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
            elif field in ("isEnabled",):
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
                s = await get_chat_settings(ctx, chat_id)
                if not s.gsbKey and not s.urlScannerEnabled:
                    await callback.answer(
                        await at(at_id, "panel.urlscanner_key_required"), show_alert=True
                    )
                    return

                kb = await url_scanner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                status = await at(
                    at_id,
                    "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled",
                )
                await callback.message.edit_text(
                    await at(
                        at_id,
                        "panel.urlscanner_text",
                        status=status,
                        key="********" if s.gsbKey else await at(at_id, "panel.not_set"),
                    ),
                    reply_markup=kb,
                )
                return
            else:
                kb = await welcome_kb(ctx, chat_id, user_id=user_id if is_pm else None)

            await callback.message.edit_reply_markup(reply_markup=kb)
            await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
    elif action == "toggle_private_rules":
        from src.db.repositories.rules import get_rules, toggle_private_rules

        rules = await get_rules(ctx, chat_id)
        new_state = not (rules.privateMode if rules else False)
        await toggle_private_rules(ctx, chat_id, new_state)

        kb = await rules_kb(chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
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
                elif field == "urlScannerAction":
                    nxt = {
                        "delete": "warn",
                        "warn": "mute",
                        "mute": "kick",
                        "kick": "ban",
                        "ban": "delete",
                    }[s.urlScannerAction]
                    s.urlScannerAction = nxt
                    session.add(s)
                    await session.commit()
                    kb = await url_scanner_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    status = await at(
                        at_id,
                        "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled",
                    )
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
    elif action == "reset_warns":
        from src.db.repositories.warns import reset_all_chat_warns

        await reset_all_chat_warns(ctx, chat_id)
        await callback.answer(_plain(await at(at_id, "panel.warns_reset_success")), show_alert=True)
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
        await callback.answer()
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
            await callback.answer(_plain(await at(at_id, "panel.user_warns_reset_success")))
    elif action == "user_warn_info":
        if len(data) >= 3:
            target_uid = int(data[2])
            page = int(data[3]) if len(data) > 3 else 0
            from src.db.repositories.warns import get_warns

            warns = await get_warns(ctx, chat_id, target_uid)

            if not warns:
                await callback.answer(_plain(await at(at_id, "warns.no_warns")), show_alert=True)
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

        await capture_next_input(user_id, chat_id, "timezoneSearch")
        await callback.message.edit_text(await at(at_id, "panel.timezone_search_prompt"))
        await callback.answer()

    elif action == "set_tz":
        if len(data) >= 3:
            new_tz = data[2]
            from src.db.models import ChatSettings
            from src.plugins.scheduler.manager import SchedulerManager

            async with ctx.db() as session:
                gs = await session.get(ChatSettings, chat_id)
                if gs:
                    gs.timezone = new_tz
                    session.add(gs)
                    await session.commit()
                    await SchedulerManager.sync_group(ctx, chat_id)

            await callback.answer(_plain(await at(at_id, "panel.timezone_set_success", tz=new_tz)))
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
                await _render_ai_panel(callback, ctx, chat_id, at_id, user_id)
            elif sub == "cycle_provider":
                s = await AIRepository.get_settings(ctx, chat_id)
                cur = s.provider if s else "openai"
                nxt = _next_ai_provider(cur)

                await AIRepository.update_settings(
                    ctx, chat_id, provider=nxt, modelId=AI_PROVIDER_DEFAULT_MODELS[nxt]
                )
                await _render_ai_panel(callback, ctx, chat_id, at_id, user_id)
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
                    await callback.answer(_plain(await at(at_id, "panel.ai_model_set", model=model_id)))
                    await _render_ai_panel(callback, ctx, chat_id, at_id, user_id)
            elif sub == "clear_ctx":
                await AIRepository.clear_context(ctx, chat_id)
                await callback.answer(_plain(await at(at_id, "panel.ai_ctx_cleared")))
        return

    elif action == "chatnightlock":
        kb = await chatnightlock_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
        await callback.message.edit_text(await at(at_id, "panel.nightlock_text"), reply_markup=kb)
        await callback.answer()

    elif action == "cleaner":
        kb = await cleaner_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
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
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.cleaner_text",
                s_del=s_del,
                s_fake=s_fake,
                days=cleaner.cleanInactiveDays,
            ),
            reply_markup=kb,
        )
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

                    await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
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
                    await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
                    kb = await reminders_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "toggle_chatnightlock":
        async with ctx.db() as session:
            lock = await session.get(ChatNightLock, chat_id)
            if lock:
                lock.isEnabled = not lock.isEnabled
                session.add(lock)
                await session.commit()

                from src.plugins.scheduler.manager import SchedulerManager

                await SchedulerManager.sync_group(ctx, chat_id)

                await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
                kb = await chatnightlock_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "toggle_cleaner":
        if len(data) >= 3:
            ctype = data[2]
            async with ctx.db() as session:
                cleaner = await session.get(ChatCleaner, chat_id)
                if cleaner:
                    if ctype == "deleted":
                        cleaner.cleanDeleted = not cleaner.cleanDeleted
                    elif ctype == "fake":
                        cleaner.cleanFake = not cleaner.cleanFake
                    session.add(cleaner)
                    await session.commit()

                    from src.plugins.scheduler.manager import SchedulerManager

                    await SchedulerManager.sync_group(ctx, chat_id)

                    await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
                    kb = await cleaner_menu_kb(ctx, chat_id, user_id=user_id if is_pm else None)
                    with contextlib.suppress(MessageNotModified):
                        await callback.message.edit_reply_markup(reply_markup=kb)

    elif action == "input":
        if len(data) >= 3:
            field = data[2]
            target_id = data[3] if len(data) > 3 else "0"
            is_channel_field = field in ("reactions", "watermarkText", "signatureText")

            # Validation Guard
            validate_chat_id = int(target_id) if is_channel_field else chat_id
            chat_type = await resolve_chat_type(ctx, validate_chat_id)
            if not is_setting_allowed(field, chat_type.name.lower()):
                await callback.answer(
                    await at(user_id, "panel.setting_not_allowed_for_type"), show_alert=True
                )
                return

            # For channel settings, target_id is the channel_id
            if is_channel_field:
                channel_id = int(target_id)
                await capture_next_input(
                    user_id, channel_id, field, prompt_msg_id=callback.message.id
                )
                cancel_cb = f"panel:channel_settings:{channel_id}"
            else:
                page = int(target_id) if target_id.isdigit() else 0
                await capture_next_input(
                    user_id, chat_id, field, prompt_msg_id=callback.message.id, page=page
                )
                cancel_cb = "panel:main"

            prompt_key = f"panel.input_prompt_{field}"
            prompt_text = await at(user_id, prompt_key)

            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            await at(user_id, "common.btn_cancel"),
                            callback_data=cancel_cb,
                        )
                    ]
                ]
            )
            await callback.message.edit_text(prompt_text, reply_markup=kb)
            await callback.answer()
    elif action == "cancel_input":
        r = get_cache()
        await r.delete(f"panel_input:{user_id}")
        await callback.answer(_plain(await at(user_id, "panel.input_cancelled")), show_alert=True)
        await callback.message.edit_text(
            await at(at_id, "panel.main_text"),
            reply_markup=await main_menu_kb(chat_id, user_id=user_id if is_pm else None),
        )
