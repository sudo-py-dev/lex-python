from typing import Any

from pyrogram import Client
from pyrogram.types import Message

from src.core.context import AppContext
from src.plugins.admin_panel.handlers.keyboards import flood_kb
from src.plugins.admin_panel.handlers.moderation_kbs import slowmode_kb, warns_kb
from src.plugins.admin_panel.handlers.security_kbs import captcha_kb, raid_kb
from src.plugins.admin_panel.repository import get_chat_settings, update_chat_setting
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
        await update_chat_setting(ctx, chat_id, field, num_value)

    kb, text_id = await _get_security_ui(ctx, chat_id, field, page)
    main_text = await _format_security_text(ctx, chat_id, text_id, num_value)

    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client,
        message,
        user_id,
        prompt_msg_id,
        f"**{success_text}**\n\n{main_text}",
        kb,
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


async def _get_security_ui(ctx: AppContext, chat_id: int, field: str, page: int):
    if field.startswith("flood"):
        return await flood_kb(ctx, chat_id), "panel.flood_text"
    if field.startswith("raid"):
        return await raid_kb(ctx, chat_id), "panel.raid_text"
    if field.startswith("captcha"):
        return await captcha_kb(ctx, chat_id), "panel.captcha_text"
    if field == "slowmode":
        return await slowmode_kb(ctx, chat_id), "panel.slowmode_text"
    if field == "warnLimit":
        return await warns_kb(ctx, chat_id), "panel.warns_text"
    if field == "purgeMessagesCount":
        from src.plugins.admin_panel.handlers.keyboards import moderation_category_kb

        return await moderation_category_kb(chat_id), "panel.moderation_text"
    return None, None


async def _format_security_text(ctx: AppContext, chat_id: int, text_id: str, value: Any):
    if text_id == "panel.warns_text":
        s = await get_chat_settings(ctx, chat_id)
        return await at(
            chat_id,
            text_id,
            limit=s.warnLimit,
            action=s.warnAction.capitalize(),
            expiry=s.warnExpiry.capitalize(),
        )
    if text_id == "panel.slowmode_text":
        return await at(chat_id, text_id, interval=value)
    if text_id == "panel.raid_text":
        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            chat_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
        )
        return await at(
            chat_id,
            text_id,
            status=status,
            threshold=s.raidThreshold,
            window=s.raidWindow,
            action=s.raidAction.capitalize(),
        )
    if text_id == "panel.captcha_text":
        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            chat_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
        )
        return await at(
            chat_id,
            text_id,
            status=status,
            mode=s.captchaMode.capitalize(),
            timeout=s.captchaTimeout,
            action=await at(chat_id, "action.ban"),
        )
    return await at(chat_id, text_id)
