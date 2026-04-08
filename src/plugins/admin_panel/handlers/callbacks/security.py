import contextlib

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery

from src.core.bot import bot
from src.plugins.admin_panel.decorators import AdminPanelContext, admin_panel_context
from src.plugins.admin_panel.handlers.callbacks.common import _panel_lang_id, _plain
from src.plugins.admin_panel.handlers.keyboards import flood_kb
from src.plugins.admin_panel.handlers.security_kbs import captcha_kb, raid_kb, url_scanner_kb
from src.plugins.admin_panel.repository import get_chat_settings, toggle_setting
from src.utils.i18n import at


@bot.on_callback_query(filters.regex(r"^panel:flood$"))
@admin_panel_context
async def on_flood_panel(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, ap_ctx.chat_id)
    kb = await flood_kb(
        ap_ctx.ctx, ap_ctx.chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None
    )
    await callback.message.edit_text(await at(at_id, "panel.flood_text"), reply_markup=kb)
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
        settings = await get_chat_settings(ctx, chat_id)
        next_action = {"mute": "kick", "kick": "ban", "ban": "mute"}[settings.floodAction]
        settings.floodAction = next_action
        session.add(settings)
        await session.commit()
    kb = await flood_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(
        await at(at_id, "panel.action_updated", action=await at(at_id, f"action.{next_action}"))
    )


@bot.on_callback_query(filters.regex(r"^panel:tgs:(\w+)$"))
@admin_panel_context
async def on_security_tgs(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    field = callback.matches[0].group(1)
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
    else:
        await callback.answer(_plain(await at(at_id, "panel.setting_updated")))
        return
    await callback.answer(_plain(await at(at_id, "panel.setting_updated")))


@bot.on_callback_query(filters.regex(r"^panel:cycle:raidAction$"))
@admin_panel_context
async def on_cycle_raid_action(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx
    async with ctx.db() as session:
        s = await get_chat_settings(ctx, chat_id)
        nxt = {"lock": "kick", "kick": "ban", "ban": "lock"}[s.raidAction]
        s.raidAction = nxt
        session.add(s)
        await session.commit()
    kb = await raid_kb(ctx, chat_id, user_id=callback.from_user.id if ap_ctx.is_pm else None)
    status = await at(at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled")
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
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:cycle:captchaMode$"))
@admin_panel_context
async def on_cycle_captcha_mode(_: Client, callback: CallbackQuery, ap_ctx: AdminPanelContext):
    chat_id = ap_ctx.chat_id
    at_id = _panel_lang_id(ap_ctx.is_pm, callback.from_user.id, chat_id)
    ctx = ap_ctx.ctx
    async with ctx.db() as session:
        s = await get_chat_settings(ctx, chat_id)
        nxt = {"button": "math", "math": "poll", "poll": "image", "image": "button"}[
            s.captchaMode.lower()
        ]
        s.captchaMode = nxt
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
        s = await get_chat_settings(ctx, chat_id)
        nxt = {"delete": "warn", "warn": "mute", "mute": "kick", "kick": "ban", "ban": "delete"}[
            s.urlScannerAction
        ]
        s.urlScannerAction = nxt
        session.add(s)
        await session.commit()
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
