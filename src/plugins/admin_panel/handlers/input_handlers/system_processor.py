import re

from pyrogram import Client
from pyrogram.types import Message

from src.core.context import AppContext
from src.db.models import GroupCleaner, NightLock
from src.plugins.admin_panel.handlers.keyboards import (
    cleaner_menu_kb,
    nightlock_menu_kb,
    timezone_picker_kb,
)
from src.plugins.admin_panel.handlers.moderation_kbs import langblock_kb, logging_kb
from src.utils.i18n import at

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(
    [
        "logChannelId",
        "langblockInput",
        "nightlockStart",
        "nightlockEnd",
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
        from src.plugins.lang_block.repository import add_lang_block
        from src.plugins.lang_block.service import is_supported, parse_iso_code

        parsed_iso = parse_iso_code(str(value))
        if not parsed_iso or not is_supported(parsed_iso):
            await message.reply(await at(user_id, "panel.langblock_invalid_input"))
            return
        await add_lang_block(ctx, chat_id, parsed_iso)
        kb = await langblock_kb(ctx, chat_id, page)
        text_id = "panel.langblock_text"

    elif field in ("nightlockStart", "nightlockEnd"):
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", str(value)):
            await message.reply(await at(user_id, "panel.input_invalid_time"))
            return
        await _handle_nightlock_save(ctx, chat_id, field, str(value))
        kb = await nightlock_menu_kb(ctx, chat_id)
        text_id = "panel.nightlock_text"

    elif field == "cleanerInactive":
        if not str(value).isdigit() or int(value) < 0:
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            return
        async with ctx.db() as session:
            cleaner = await session.get(GroupCleaner, chat_id)
            if not cleaner:
                cleaner = GroupCleaner(chatId=chat_id)
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
        client, message, user_id, prompt_msg_id, f"**{success_text}**\n\n{main_text}", kb
    )


async def _handle_nightlock_save(ctx, chat_id, field, time_value):
    async with ctx.db() as session:
        lock = await session.get(NightLock, chat_id)
        if not lock:
            lock = NightLock(chatId=chat_id)
        if field == "nightlockStart":
            lock.startTime = time_value
        else:
            lock.endTime = time_value
        session.add(lock)
        await session.commit()

        if lock.isEnabled:
            from src.plugins.scheduler.service import apply_night_lock, lift_night_lock

            ctx.scheduler.add_job(
                apply_night_lock,
                trigger="cron",
                hour=lock.startTime.split(":")[0],
                minute=lock.startTime.split(":")[1],
                args=[chat_id],
                id=f"nightlock_on:{chat_id}",
                replace_existing=True,
            )
            ctx.scheduler.add_job(
                lift_night_lock,
                trigger="cron",
                hour=lock.endTime.split(":")[0],
                minute=lock.endTime.split(":")[1],
                args=[chat_id],
                id=f"nightlock_off:{chat_id}",
                replace_existing=True,
            )
