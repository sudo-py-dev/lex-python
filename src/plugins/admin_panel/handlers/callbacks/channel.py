import contextlib
import math

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery

from src.config import config
from src.core.bot import bot
from src.core.context import get_context
from src.plugins.admin_panel.handlers.callbacks.common import (
    _plain,
    _render_channel_watermark_panel,
)
from src.plugins.admin_panel.handlers.keyboards import channel_settings_kb
from src.plugins.admin_panel.handlers.service_cleaner import (
    get_available_service_types,
    service_cleaner_kb,
    service_cleaner_types_kb,
)
from src.plugins.admin_panel.repository import (
    get_chat_settings,
    toggle_service_type,
    update_chat_setting,
)
from src.utils.i18n import at
from src.utils.media import build_watermark_config, parse_watermark_config
from src.utils.permissions import is_admin


@bot.on_callback_query(filters.regex(r"^panel:channel_settings:(-?\d+)$"))
async def on_channel_settings(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    s = await get_chat_settings(ctx, channel_id)
    title = s.title or f"Channel {channel_id}"
    kb = await channel_settings_kb(ctx, channel_id, user_id)

    await callback.message.edit_text(
        await at(user_id, "panel.channel_settings_text", title=title, id=channel_id),
        reply_markup=kb,
    )
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:channel_watermark:(-?\d+)$"))
async def on_channel_watermark(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    await _render_channel_watermark_panel(callback, ctx, channel_id, user_id, user_id)
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:chs:(-?\d+)$"))
async def on_channel_service_cleaner(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    kb = await service_cleaner_kb(
        ctx,
        channel_id,
        user_id=user_id,
        back_callback=f"panel:channel_settings:{channel_id}",
        types_callback=f"panel:chsp:{channel_id}:0",
        toggle_callback=f"panel:chsg:{channel_id}",
    )
    await callback.message.edit_text(
        await at(user_id, "panel.service_cleaner_text"), reply_markup=kb
    )
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:chsg:(-?\d+)$"))
async def on_channel_service_cleaner_toggle_all(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    from src.db.repositories.chats import toggle_setting as toggle_ch_setting

    await toggle_ch_setting(ctx, channel_id, "cleanAllServices")

    kb = await service_cleaner_kb(
        ctx,
        channel_id,
        user_id=user_id,
        back_callback=f"panel:channel_settings:{channel_id}",
        types_callback=f"panel:chsp:{channel_id}:0",
        toggle_callback=f"panel:chsg:{channel_id}",
    )
    with contextlib.suppress(MessageNotModified):
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(_plain(await at(user_id, "panel.setting_updated")))


@bot.on_callback_query(filters.regex(r"^panel:chsp:(-?\d+):(\d+)$"))
async def on_channel_service_cleaner_types(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))
    page = int(callback.matches[0].group(2))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    kb = await service_cleaner_types_kb(
        ctx,
        channel_id,
        page,
        user_id=user_id,
        page_callback_prefix=f"panel:chsp:{channel_id}",
        toggle_callback_prefix=f"panel:chst:{channel_id}",
        back_callback=f"panel:chs:{channel_id}",
        toggle_mode="index",
    )
    total = math.ceil(len(get_available_service_types("channel")) / 10)
    text = await at(user_id, "panel.service_cleaner_types_text", page=page + 1, total=max(1, total))
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:chst:(-?\d+):(\d+):(\d+)$"))
async def on_channel_service_cleaner_toggle_type(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))
    service_idx = int(callback.matches[0].group(2))
    page = int(callback.matches[0].group(3))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    settings = await get_chat_settings(ctx, channel_id)
    all_types = get_available_service_types(settings.chatType or "channel")
    if service_idx < 0 or service_idx >= len(all_types):
        await callback.answer(_plain(await at(user_id, "panel.error_generic")), show_alert=True)
        return

    service_type = all_types[service_idx]
    await toggle_service_type(ctx, channel_id, service_type)

    kb = await service_cleaner_types_kb(
        ctx,
        channel_id,
        page,
        user_id=user_id,
        page_callback_prefix=f"panel:chsp:{channel_id}",
        toggle_callback_prefix=f"panel:chst:{channel_id}",
        back_callback=f"panel:chs:{channel_id}",
        toggle_mode="index",
    )
    with contextlib.suppress(MessageNotModified):
        await callback.message.edit_reply_markup(reply_markup=kb)

    label_key = f"panel.service_type_{service_type}"
    localized_type = await at(user_id, label_key)
    if localized_type == label_key:
        localized_type = service_type.replace("_", " ").title()
    await callback.answer(_plain(await at(user_id, "common.btn_action", type=localized_type)))


@bot.on_callback_query(filters.regex(r"^panel:toggle_ch:(\w+):(-?\d+)$"))
async def on_channel_toggle_setting(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    field = callback.matches[0].group(1)
    channel_id = int(callback.matches[0].group(2))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
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
    await callback.answer(_plain(await at(user_id, "panel.setting_updated")))


@bot.on_callback_query(filters.regex(r"^panel:cycle_wm:(\w+):(-?\d+)$"))
async def on_channel_cycle_watermark(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    mode = callback.matches[0].group(1)
    channel_id = int(callback.matches[0].group(2))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    from src.db.repositories.chats import get_chat_settings as get_ch_settings

    s = await get_ch_settings(ctx, channel_id)
    cfg = parse_watermark_config(s.watermarkText)

    if mode == "color":
        cycle = ["white", "black", "red", "blue", "gold"]
        current = cfg.color
    elif mode == "video_quality":
        cycle = ["high", "medium", "low"]
        current = cfg.video_quality
    elif mode == "video_motion":
        cycle = ["static", "float", "scroll_lr", "scroll_rl"]
        current = cfg.video_motion
    else:
        cycle = ["soft_shadow", "outline", "clean", "pattern_grid", "pattern_diagonal"]
        current = cfg.style

    try:
        nxt = cycle[(cycle.index(current) + 1) % len(cycle)]
    except ValueError:
        nxt = cycle[0]

    if mode == "color":
        cfg.color = nxt
    elif mode == "video_quality":
        cfg.video_quality = nxt
    elif mode == "video_motion":
        cfg.video_motion = nxt
    else:
        cfg.style = nxt

    await update_chat_setting(
        ctx,
        channel_id,
        "watermarkText",
        build_watermark_config(
            cfg.text,
            color=cfg.color,
            style=cfg.style,
            image_enabled=cfg.image_enabled,
            video_enabled=cfg.video_enabled,
            video_quality=cfg.video_quality,
            video_motion=cfg.video_motion,
        ),
    )
    await _render_channel_watermark_panel(callback, ctx, channel_id, user_id, user_id)
    await callback.answer()


@bot.on_callback_query(filters.regex(r"^panel:toggle_wm_image:(-?\d+)$"))
async def on_channel_toggle_wm_image(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    s = await get_chat_settings(ctx, channel_id)
    cfg = parse_watermark_config(s.watermarkText)
    cfg.image_enabled = not cfg.image_enabled

    await update_chat_setting(
        ctx,
        channel_id,
        "watermarkText",
        build_watermark_config(
            cfg.text,
            color=cfg.color,
            style=cfg.style,
            image_enabled=cfg.image_enabled,
            video_enabled=cfg.video_enabled,
            video_quality=cfg.video_quality,
            video_motion=cfg.video_motion,
        ),
    )
    await _render_channel_watermark_panel(callback, ctx, channel_id, user_id, user_id)
    await callback.answer(await at(user_id, "panel.setting_updated"))


@bot.on_callback_query(filters.regex(r"^panel:toggle_wm_video:(-?\d+)$"))
async def on_channel_toggle_wm_video(client: Client, callback: CallbackQuery):
    ctx = get_context()
    user_id = callback.from_user.id
    channel_id = int(callback.matches[0].group(1))

    if not await is_admin(client, channel_id, user_id):
        await callback.answer(await at(user_id, "error.no_membership_admin"), show_alert=True)
        return

    if not config.ENABLE_VIDEO_WATERMARK:
        await callback.answer(await at(user_id, "panel.wm_video_unavailable"), show_alert=True)
        return

    s = await get_chat_settings(ctx, channel_id)
    cfg = parse_watermark_config(s.watermarkText)
    cfg.video_enabled = not cfg.video_enabled

    await update_chat_setting(
        ctx,
        channel_id,
        "watermarkText",
        build_watermark_config(
            cfg.text,
            color=cfg.color,
            style=cfg.style,
            image_enabled=cfg.image_enabled,
            video_enabled=cfg.video_enabled,
            video_quality=cfg.video_quality,
            video_motion=cfg.video_motion,
        ),
    )
    await _render_channel_watermark_panel(callback, ctx, channel_id, user_id, user_id)
    await callback.answer(await at(user_id, "panel.setting_updated"))
