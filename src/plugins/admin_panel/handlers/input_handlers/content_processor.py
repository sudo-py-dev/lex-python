import contextlib
import json
import re

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
from src.config import config
from src.core.context import AppContext
from src.db.models import Reminder
from src.plugins.admin_panel.handlers.keyboards import reminders_menu_kb, rules_kb, welcome_kb
from src.plugins.admin_panel.handlers.moderation_kbs import blacklist_kb
from src.plugins.admin_panel.repository import resolve_chat_type, update_chat_setting
from src.plugins.admin_panel.validation import is_setting_allowed
from src.utils.i18n import at
from src.utils.telegram_storage import extract_message_data

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(["rulesText", "blacklistInput", "reminderText", "reminderTime", "welcomeText"])
async def content_settings_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    chat_id: int,
    field: str,
    value: str,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id

    # Validation Guard
    chat_type = await resolve_chat_type(ctx, chat_id)
    if not is_setting_allowed(field, chat_type.name.lower()):
        await message.reply(await at(user_id, "panel.setting_not_allowed_for_type"))
        return

    if field == "rulesText":
        from src.db.repositories.rules import set_rules

        await set_rules(ctx, chat_id, str(value))
        kb = await rules_kb(chat_id, user_id=user_id)
        text_id = "panel.rules_text"

    elif field == "blacklistInput":
        from src.db.repositories.blacklist import add_blacklist, get_blacklist_count
        from src.plugins.blacklist import detect_pattern_type

        pattern_raw = str(value).lower()
        is_regex, is_wildcard, pattern = detect_pattern_type(pattern_raw)

        if is_regex:
            try:
                re.compile(pattern)
            except re.error:
                await message.reply(await at(user_id, "panel.blacklist_invalid_regex"))
                return

        count = await get_blacklist_count(ctx, chat_id)
        if count >= 150:
            await message.reply(await at(user_id, "panel.blacklist_limit_reached"))
            return
        await add_blacklist(ctx, chat_id, pattern, is_regex=is_regex, is_wildcard=is_wildcard)

        kb = await blacklist_kb(ctx, chat_id, page, user_id=user_id)
        text_id = "panel.blacklist_text"

    elif field == "reminderText":
        await _handle_reminder_message_capture(
            client, message, user_id, chat_id, value, prompt_msg_id, page
        )
        return

    elif field == "reminderTime":
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", str(value)):
            await message.reply(await at(user_id, "panel.input_invalid_time"))
            return
        await _handle_reminder_time_save(ctx, user_id, chat_id, str(value))
        kb = await reminders_menu_kb(ctx, chat_id, user_id=user_id)
        text_id = "panel.reminder_text"
    elif field == "welcomeText":
        await update_chat_setting(ctx, chat_id, "welcomeText", str(value))
        await update_chat_setting(ctx, chat_id, "welcomeEnabled", True)
        kb = await welcome_kb(ctx, chat_id, user_id=user_id)
        text_id = "panel.welcome_text"

    main_text = await at(user_id, text_id)
    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client, message, user_id, prompt_msg_id, main_text, kb, success_text=success_text
    )


async def _handle_reminder_message_capture(
    client, message, user_id, chat_id, value, prompt_msg_id, page
):
    r = get_cache()
    data = await extract_message_data(message)

    await r.set(f"temp_rem_data:{user_id}", json.dumps(data), ttl=300)
    await r.set(f"panel_input:{user_id}", f"{chat_id}:reminderTime:{prompt_msg_id}:{page}", ttl=300)

    prompt_text = await at(user_id, "panel.input_prompt_reminderTime")
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    await at(user_id, "common.btn_cancel"),
                    callback_data="panel:cancel_input",
                )
            ]
        ]
    )
    if prompt_msg_id:
        await client.edit_message_text(user_id, prompt_msg_id, prompt_text, reply_markup=kb)
    else:
        await message.reply(prompt_text, reply_markup=kb)

    with contextlib.suppress(Exception):
        await message.delete()


async def _handle_reminder_time_save(ctx, user_id, chat_id, time_value):
    import json

    r = get_cache()
    data_str = await r.get(f"temp_rem_data:{user_id}")
    if not data_str:
        return
    data = json.loads(data_str)
    async with ctx.db() as session:
        rem = Reminder(
            chatId=chat_id,
            messageType=data["type"],
            text=data.get("text"),
            fileId=data.get("file_id"),
            additionalData=data.get("additional_data"),
            sendTime=time_value,
        )
        session.add(rem)
        await session.commit()
        from src.plugins.scheduler.manager import SchedulerManager

        await SchedulerManager.sync_group(ctx, chat_id)
    await r.delete(f"temp_rem_data:{user_id}")


@input_registry.register(["reactions", "watermarkText", "signatureText"])
async def channel_settings_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    channel_id: int,
    field: str,
    value: str,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id
    from src.db.repositories.chats import get_chat_settings as get_channel_settings
    from src.db.repositories.chats import update_chat_setting as update_channel_setting
    from src.plugins.admin_panel.handlers.keyboards import channel_settings_kb, channel_watermark_kb
    from src.utils.media import build_watermark_config, parse_watermark_config

    if field == "reactions":
        import emoji

        # Extract only emojis from the input
        emojis = [c for c in str(value) if emoji.is_emoji(c)]
        if not emojis:
            # If no direct emojis, try splitting by space and checking
            emojis = [word for word in str(value).split() if any(emoji.is_emoji(c) for c in word)]

        cleaned_reactions = " ".join(emojis) if emojis else "👍"
        await update_channel_setting(ctx, channel_id, "reactions", cleaned_reactions)

    elif field == "watermarkText":
        s = await get_channel_settings(ctx, channel_id)
        cfg = parse_watermark_config(s.watermarkText)
        cfg.text = str(value).strip()
        await update_channel_setting(
            ctx,
            channel_id,
            "watermarkText",
            build_watermark_config(
                cfg.text,
                color=cfg.color,
                style=cfg.style,
                video_enabled=cfg.video_enabled,
                video_quality=cfg.video_quality,
                video_motion=cfg.video_motion,
            ),
        )

    elif field == "signatureText":
        await update_channel_setting(ctx, channel_id, "signatureText", str(value))

    s = await get_channel_settings(ctx, channel_id)
    title = s.title or f"Channel {channel_id}"
    kb = await channel_settings_kb(ctx, channel_id, user_id)

    success_text = await at(user_id, "panel.input_success")
    if field == "watermarkText":
        cfg = parse_watermark_config(s.watermarkText)
        status = await at(user_id, "panel.status_enabled" if s.watermarkEnabled else "panel.status_disabled")
        main_text = await at(
            user_id,
            "panel.channel_watermark_text",
            status=status,
            text=cfg.text or "-",
            color=await at(user_id, f"panel.wm_color_{cfg.color}"),
            style=await at(user_id, f"panel.wm_style_{cfg.style}"),
            video_status=await at(
                user_id, "panel.status_enabled" if cfg.video_enabled else "panel.status_disabled"
            ),
            video_quality=await at(user_id, f"panel.wm_quality_{cfg.video_quality}"),
            video_motion=await at(user_id, f"panel.wm_motion_{cfg.video_motion}"),
            video_available=await at(
                user_id,
                "panel.wm_video_available_yes"
                if config.ENABLE_VIDEO_WATERMARK
                else "panel.wm_video_available_no",
            ),
            video_limit_note=(
                await at(
                    user_id,
                    "panel.wm_video_limit_note",
                    size_mb=config.VIDEO_WATERMARK_MAX_SIZE_MB,
                )
                if config.ENABLE_VIDEO_WATERMARK
                else ""
            ),
        )
        kb = await channel_watermark_kb(ctx, channel_id, user_id)
    else:
        main_text = await at(user_id, "panel.channel_settings_text", title=title, id=channel_id)

    await finalize_input_capture(
        client, message, user_id, prompt_msg_id, main_text, kb, success_text=success_text
    )
