import re

from pyrogram import Client
from pyrogram.types import Message

from src.core.context import AppContext
from src.db.models import ChatCleaner, ChatNightLock
from src.plugins.admin_panel.handlers.keyboards import (
    chatnightlock_menu_kb,
    cleaner_menu_kb,
    timezone_picker_kb,
)
from src.plugins.admin_panel.handlers.moderation_kbs import langblock_kb, logging_kb
from src.utils.i18n import at

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(
    [
        "logChannelId",
        "langblockInput",
        "chatnightlockStart",
        "chatnightlockEnd",
        "cleanerInactive",
        "timezoneSearch",
    ]
)
async def system_settings_processor(
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

    if field == "logChannelId":
        if not str(value).lstrip("-").isdigit():
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            return
        from src.plugins.admin_panel.repository import update_chat_setting

        await update_chat_setting(ctx, chat_id, field, int(value))
        kb = await logging_kb(ctx, chat_id)
        text_id = "panel.logging_text"

    elif field == "langblockInput":
        from src.plugins.lang_block import add_lang_block, is_supported

        parsed_iso = str(value).lower().strip()
        if not parsed_iso or not is_supported(parsed_iso):
            await message.reply(await at(user_id, "panel.langblock_invalid_input"))
            return
        await add_lang_block(ctx, chat_id, parsed_iso)
        kb = await langblock_kb(ctx, chat_id, page)
        text_id = "panel.langblock_text"

    elif field in ("chatnightlockStart", "chatnightlockEnd"):
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", str(value)):
            await message.reply(await at(user_id, "panel.input_invalid_time"))
            return
        await _handle_chatnightlock_save(ctx, chat_id, field, str(value))
        kb = await chatnightlock_menu_kb(ctx, chat_id)
        text_id = "panel.nightlock_text"

    elif field == "cleanerInactive":
        if not str(value).isdigit() or int(value) < 0:
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            return
        async with ctx.db() as session:
            cleaner = await session.get(ChatCleaner, chat_id)
            if not cleaner:
                cleaner = ChatCleaner(chatId=chat_id)
            cleaner.cleanInactiveDays = int(value)
            session.add(cleaner)
            await session.commit()
        kb = await cleaner_menu_kb(ctx, chat_id)
        text_id = "panel.cleaner_text"

    elif field == "timezoneSearch":
        kb = await timezone_picker_kb(ctx, chat_id, user_id=user_id, filter_query=str(value))
        text_id = "panel.timezone_search_results_text"

    main_text = await at(
        chat_id,
        text_id,
        query=value if field == "timezoneSearch" else None,
        channel=value if field == "logChannelId" else None,
    )
    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client, message, user_id, prompt_msg_id, main_text, kb, success_text=success_text
    )


async def _handle_chatnightlock_save(ctx, chat_id, field, time_value):
    async with ctx.db() as session:
        lock = await session.get(ChatNightLock, chat_id)
        if not lock:
            lock = ChatNightLock(chatId=chat_id)
        if field == "chatnightlockStart":
            lock.startTime = time_value
        else:
            lock.endTime = time_value
        session.add(lock)
        await session.commit()

        if lock.isEnabled:
            from src.plugins.scheduler.manager import SchedulerManager

            await SchedulerManager.sync_group(ctx, chat_id)
