import asyncio
import contextlib

from loguru import logger
from pyrogram import Client, ContinuePropagation, filters
from pyrogram.errors import FloodWait, MessageNotModified, QueryIdInvalid, RPCError
from pyrogram.types import CallbackQuery

from src.core.bot import bot
from src.plugins.admin_panel.decorators import AdminPanelContext, admin_panel_context
from src.plugins.admin_panel.handlers.callbacks.common import _panel_lang_id, _plain
from src.plugins.admin_panel.handlers.keyboards import flood_kb
from src.plugins.admin_panel.handlers.security_kbs import captcha_kb, raid_kb, url_scanner_kb
from src.plugins.admin_panel.repository import get_chat_settings, toggle_setting
from src.utils.actions import (
    CAPTCHA_MODES,
    FLOOD_ACTIONS,
    RAID_ACTIONS,
    SECURITY_ACTIONS,
    cycle_action,
)
from src.utils.i18n import at


@bot.on_callback_query(filters.regex(r"^panel:flood$"))
@admin_panel_context
async def on_flood_panel(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    s = await get_chat_settings(ap_ctx.ctx, chat_id)
    kb = await flood_kb(
        ap_ctx.ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None
    )
    status = await at(
        at_id, "panel.status_enabled" if s.floodThreshold > 0 else "panel.status_disabled"
    )
    try:
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.flood_text",
                status=status,
                threshold=s.floodThreshold,
                window=s.floodWindow,
                action=await at(at_id, f"action.{s.floodAction.lower()}"),
            ),
            reply_markup=kb,
        )
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await on_flood_panel(_, callback, ap_ctx)
    except (RPCError, Exception) as e:
        logger.debug(f"Flood panel UI update failed: {e}")

    with contextlib.suppress(QueryIdInvalid):
        await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:raid$"))
@admin_panel_context
async def on_raid_panel(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    s = await get_chat_settings(ap_ctx.ctx, chat_id)
    kb = await raid_kb(ap_ctx.ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
    status = await at(at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled")
    try:
        await callback.message.edit_text(
            await at(
                at_id,
                "panel.raid_text",
                status=status,
                threshold=s.raidThreshold,
                window=s.raidWindow,
                time=s.raidTime,
                actiontime=s.raidActionTime,
                action=await at(at_id, f"action.{s.raidAction.lower()}"),
            ),
            reply_markup=kb,
        )
    except MessageNotModified:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await on_raid_panel(_, callback, ap_ctx)
    except (RPCError, Exception) as e:
        logger.debug(f"Raid panel UI update failed: {e}")

    with contextlib.suppress(QueryIdInvalid):
        await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:captcha$"))
@admin_panel_context
async def on_captcha_panel(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    s = await get_chat_settings(ap_ctx.ctx, chat_id)
    kb = await captcha_kb(
        ap_ctx.ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None
    )
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


@bot.on_callback_query(filters.regex(r"^panel:urlscanner$"))
@admin_panel_context
async def on_urlscanner_panel(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    s = await get_chat_settings(ap_ctx.ctx, chat_id)
    kb = await url_scanner_kb(
        ap_ctx.ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None
    )
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


@bot.on_callback_query(filters.regex(r"^panel:toggle_flood_action$"))
@admin_panel_context
async def on_toggle_flood_action(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx

    async with ctx.db() as session:
        from src.db.models import ChatSettings

        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)

        next_action = cycle_action(settings.floodAction, FLOOD_ACTIONS, default_action="mute")
        settings.floodAction = next_action
        await session.commit()
        # Refresh to get updated values for UI
        await session.refresh(settings)
    kb = await flood_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
    status = await at(
        at_id, "panel.status_enabled" if settings.floodThreshold > 0 else "panel.status_disabled"
    )
    await callback.message.edit_text(
        await at(
            at_id,
            "panel.flood_text",
            status=status,
            threshold=settings.floodThreshold,
            window=settings.floodWindow,
            action=await at(at_id, f"action.{settings.floodAction.lower()}"),
        ),
        reply_markup=kb,
    )
    await callback.answer(
        await at(at_id, "panel.action_updated", action=await at(at_id, f"action.{next_action}"))
    )


@bot.on_callback_query(filters.regex(r"^panel:tgs:(\w+)$"))
@admin_panel_context
async def on_security_tgs(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    field = callback.matches[0].group(1)
    if field not in ("raidEnabled", "captchaEnabled", "urlScannerEnabled"):
        # Fall through to other handlers
        raise ContinuePropagation

    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx

    await toggle_setting(ctx, chat_id, field)

    if field == "raidEnabled":
        kb = await raid_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
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
                time=s.raidTime,
                actiontime=s.raidActionTime,
                action=await at(at_id, f"action.{s.raidAction.lower()}"),
            ),
            reply_markup=kb,
        )
    elif field == "captchaEnabled":
        kb = await captcha_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
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
    elif field == "urlScannerEnabled":
        s = await get_chat_settings(ctx, chat_id)
        if not s.gsbKey and not s.urlScannerEnabled:
            await callback.answer(await at(at_id, "panel.urlscanner_key_required"), show_alert=True)
            return
        kb = await url_scanner_kb(
            ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None
        )
        status = await at(
            at_id, "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled"
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

    await callback.answer(_plain(await at(at_id, "panel.setting_updated")))


@bot.on_callback_query(filters.regex(r"^panel:cycle:raidAction$"))
@admin_panel_context
async def on_cycle_raid_action(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx

    logger.debug(f"on_cycle_raid_action triggered for chat {chat_id}")

    try:
        from src.plugins.admin_panel.repository import (
            get_chat_settings,
            update_chat_setting,
        )

        s = await get_chat_settings(ctx, chat_id)
        old_action = s.raidAction
        next_action = cycle_action(old_action, RAID_ACTIONS, default_action="lock")

        logger.info(f"Raid action cycle: {chat_id} | {old_action} -> {next_action}")
        await update_chat_setting(ctx, chat_id, "raidAction", next_action)

        s = await get_chat_settings(ctx, chat_id)
        kb = await raid_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
        status = await at(
            at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
        )

        text = await at(
            at_id,
            "panel.raid_text",
            status=status,
            threshold=s.raidThreshold,
            window=s.raidWindow,
            time=s.raidTime,
            actiontime=s.raidActionTime,
            action=await at(at_id, f"action.{s.raidAction.lower()}"),
        )

        with contextlib.suppress(MessageNotModified):
            await callback.message.edit_text(text, reply_markup=kb)

    except QueryIdInvalid:
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        return await on_cycle_raid_action(_, callback, ap_ctx)
    except Exception as e:
        logger.exception(f"CRITICAL ERROR in on_cycle_raid_action for chat {chat_id}: {e}")
        with contextlib.suppress(QueryIdInvalid):
            await callback.answer(f"UI Error: {e}", show_alert=True)
    finally:
        with contextlib.suppress(QueryIdInvalid):
            await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:cycle:captchaMode$"))
@admin_panel_context
async def on_cycle_captcha_mode(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx

    async with ctx.db() as session:
        s = await get_chat_settings(ctx, chat_id)
        s.captchaMode = cycle_action(s.captchaMode, CAPTCHA_MODES, default_action="button")
        session.add(s)
        await session.commit()
    kb = await captcha_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
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


@bot.on_callback_query(filters.regex(r"^panel:cycle:urlScannerAction$"))
@admin_panel_context
async def on_cycle_url_scanner_action(
    _: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext
):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx

    async with ctx.db() as session:
        from src.db.models import ChatSettings

        s = await session.get(ChatSettings, chat_id)
        if not s:
            s = ChatSettings(id=chat_id)
            session.add(s)

        s.urlScannerAction = cycle_action(
            s.urlScannerAction, SECURITY_ACTIONS, default_action="delete"
        )
        await session.commit()
        await session.refresh(s)
    kb = await url_scanner_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
    status = await at(
        at_id, "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled"
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
