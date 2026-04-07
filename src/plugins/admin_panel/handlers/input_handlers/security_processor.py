from typing import Any

from pyrogram import Client
from pyrogram.types import Message

from src.core.context import AppContext
from src.plugins.admin_panel.handlers.keyboards import flood_kb
from src.plugins.admin_panel.handlers.moderation_kbs import slowmode_kb, warns_kb
from src.plugins.admin_panel.handlers.security_kbs import captcha_kb, raid_kb, url_scanner_kb
from src.plugins.admin_panel.repository import (
    get_chat_settings,
    resolve_chat_type,
    update_chat_setting,
)
from src.plugins.admin_panel.validation import is_setting_allowed
from src.utils.i18n import at

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(
    [
        "floodThreshold",
        "floodWindow",
        "warnLimit",
        "raidThreshold",
        "raidWindow",
        "captchaTimeout",
        "slowmode",
        "purgeMessagesCount",
    ]
)
async def numeric_security_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    chat_id: int,
    field: str,
    value: Any,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id

    if not str(value).isdigit() or int(value) < 0:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    # Validation Guard
    chat_type = await resolve_chat_type(ctx, chat_id)
    if not is_setting_allowed(field, chat_type.name.lower()):
        await message.reply(await at(user_id, "panel.setting_not_allowed_for_type"))
        return

    num_value = int(value)
    if field == "warnLimit" and num_value < 1:
        num_value = 1

    if field == "slowmode":
        from src.db.repositories.slowmode import clear_slowmode, set_slowmode

        if num_value > 0:
            await set_slowmode(ctx, chat_id, num_value)
        else:
            await clear_slowmode(ctx, chat_id)
    elif field == "purgeMessagesCount":
        await _handle_purge(client, chat_id, num_value)
    else:
        # Update database for numeric fields like warnLimit, floodThreshold, etc.
        await update_chat_setting(ctx, chat_id, field, num_value)
    kb, text_id = await _get_security_ui(ctx, chat_id, field, page, user_id)
    main_text = await _format_security_text(ctx, chat_id, user_id, text_id, num_value)

    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client,
        message,
        user_id,
        prompt_msg_id,
        main_text,
        kb,
        success_text=success_text,
    )


@input_registry.register(["gsbKey", "groqKey"])
async def string_security_processor(
    client: Client,
    message: Message,
    ctx: AppContext,
    chat_id: int,
    field: str,
    value: Any,
    prompt_msg_id: int | None,
    page: int,
) -> None:
    user_id = message.from_user.id
    str_value = str(value).strip()

    if str_value.lower() == "reset":
        if field == "gsbKey":
            await update_chat_setting(ctx, chat_id, "gsbKey", None)
            await update_chat_setting(ctx, chat_id, "urlScannerEnabled", False)
        elif field == "groqKey":
            from src.db.repositories.ai_guard import update_ai_guard_settings

            await update_ai_guard_settings(ctx, chat_id, apiKey=None, isEnabled=False)
        str_value = None
    elif not str_value:
        await message.reply(await at(user_id, "panel.input_invalid_string"))
        return
    else:
        # Validation Guard
        chat_type = await resolve_chat_type(ctx, chat_id)
        if not is_setting_allowed(field, chat_type.name.lower()):
            await message.reply(await at(user_id, "panel.setting_not_allowed_for_type"))
            return
        if field == "gsbKey":
            await update_chat_setting(ctx, chat_id, field, str_value)
        elif field == "groqKey":
            from src.db.repositories.ai_guard import update_ai_guard_settings

            await update_ai_guard_settings(ctx, chat_id, apiKey=str_value)

    kb, text_id = await _get_security_ui(ctx, chat_id, field, page, user_id)
    main_text = await _format_security_text(ctx, chat_id, user_id, text_id, str_value)

    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client,
        message,
        user_id,
        prompt_msg_id,
        main_text,
        kb,
        success_text=success_text,
    )


async def _handle_purge(client: Client, chat_id: int, count: int):
    import asyncio
    import contextlib

    async def do_purge():
        try:
            dummy = await client.send_message(chat_id, await at(chat_id, "panel.purge_in_progress"))
            top_id = dummy.id
            await asyncio.sleep(2)
            await dummy.delete()

            for i in range(top_id, top_id - count - 1, -100):
                batch_ids = list(range(i, max(i - 100, top_id - count - 1), -1))
                with contextlib.suppress(Exception):
                    await client.delete_messages(chat_id, batch_ids)
                await asyncio.sleep(0.5)
        except Exception:
            pass

    asyncio.create_task(do_purge())


async def _get_security_ui(ctx: AppContext, chat_id: int, field: str, page: int, user_id: int):
    if field.startswith("flood"):
        return await flood_kb(ctx, chat_id, user_id=user_id), "panel.flood_text"
    if field.startswith("raid"):
        return await raid_kb(ctx, chat_id, user_id=user_id), "panel.raid_text"
    if field.startswith("captcha"):
        return await captcha_kb(ctx, chat_id, user_id=user_id), "panel.captcha_text"
    if field == "slowmode":
        return await slowmode_kb(ctx, chat_id, user_id=user_id), "panel.slowmode_text"
    if field == "gsbKey":
        return await url_scanner_kb(ctx, chat_id, user_id=user_id), "panel.urlscanner_text"
    if field == "groqKey":
        from ..keyboards import ai_security_kb

        return await ai_security_kb(ctx, chat_id, user_id), "panel.ai_guard_text"
    if field == "warnLimit":
        return await warns_kb(ctx, chat_id, user_id=user_id), "panel.warns_text"
    if field == "purgeMessagesCount":
        from src.plugins.admin_panel.handlers.keyboards import moderation_category_kb

        return await moderation_category_kb(chat_id, user_id=user_id), "panel.moderation_text"
    return None, None


async def _format_security_text(
    ctx: AppContext, chat_id: int, user_id: int, text_id: str | None, value: Any
):
    at_id = user_id if user_id else chat_id
    if text_id is None:
        return ""

    if text_id == "panel.warns_text":
        s = await get_chat_settings(ctx, chat_id)
        return await at(
            at_id,
            text_id,
            limit=s.warnLimit,
            action=s.warnAction.capitalize(),
            expiry=s.warnExpiry.capitalize(),
        )
    if text_id == "panel.slowmode_text":
        return await at(at_id, text_id, interval=value)
    if text_id == "panel.raid_text":
        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            at_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
        )
        return await at(
            at_id,
            text_id,
            status=status,
            threshold=s.raidThreshold,
            window=s.raidWindow,
            action=s.raidAction.capitalize(),
        )
    if text_id == "panel.captcha_text":
        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            at_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
        )
        return await at(
            at_id,
            text_id,
            status=status,
            mode=s.captchaMode.capitalize(),
            timeout=s.captchaTimeout,
            action=await at(at_id, "action.ban"),
        )
    if text_id == "panel.urlscanner_text":
        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            at_id, "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled"
        )
        return await at(
            at_id,
            text_id,
            status=status,
            key="********" if s.gsbKey else await at(at_id, "panel.not_set"),
        )
    if text_id == "panel.ai_guard_text":
        from src.db.repositories.ai_guard import get_ai_guard_settings

        s = await get_ai_guard_settings(ctx, chat_id)
        status_label = await at(at_id, f"panel.status_{'enabled' if s.isEnabled else 'disabled'}")
        action_label = await at(at_id, f"action.{s.action}")

        return await at(
            at_id,
            text_id,
            status=status_label,
            action=action_label,
            model=s.modelId,
        )
    return await at(at_id, text_id) if text_id else ""
