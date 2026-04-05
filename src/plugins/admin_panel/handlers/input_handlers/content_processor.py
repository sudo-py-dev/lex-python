import re

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
from src.core.context import AppContext
from src.db.models import Reminder
from src.plugins.admin_panel.handlers.keyboards import reminders_menu_kb, rules_kb
from src.plugins.admin_panel.handlers.moderation_kbs import blacklist_kb
from src.utils.i18n import at

from .dispatch_logic import finalize_input_capture, input_registry


@input_registry.register(["rulesText", "blacklistInput", "reminderText", "reminderTime"])
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

    if field == "rulesText":
        from src.db.repositories.rules import set_rules

        await set_rules(ctx, chat_id, str(value))
        kb = await rules_kb(chat_id)
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
            await message.reply(await at(chat_id, "panel.blacklist_limit_reached"))
            return
        await add_blacklist(ctx, chat_id, pattern, is_regex=is_regex, is_wildcard=is_wildcard)

        kb = await blacklist_kb(ctx, chat_id, page)
        text_id = "panel.blacklist_text"

    elif field == "reminderText":
        await _handle_reminder_text_capture(
            client, message, user_id, chat_id, value, prompt_msg_id, page
        )
        return

    elif field == "reminderTime":
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", str(value)):
            await message.reply(await at(user_id, "panel.input_invalid_time"))
            return
        await _handle_reminder_time_save(ctx, user_id, chat_id, str(value))
        kb = await reminders_menu_kb(ctx, chat_id)
        text_id = "panel.reminder_text"

    main_text = await at(chat_id, text_id)
    success_text = await at(user_id, "panel.input_success")
    await finalize_input_capture(
        client, message, user_id, prompt_msg_id, f"**{success_text}**\n\n{main_text}", kb
    )


async def _handle_reminder_text_capture(
    client, message, user_id, chat_id, value, prompt_msg_id, page
):
    r = get_cache()
    await r.set(f"temp_rem_text:{user_id}", str(value), ttl=300)
    await r.set(f"panel_input:{user_id}", f"{chat_id}:reminderTime:{prompt_msg_id}:{page}", ttl=300)
    prompt_text = await at(user_id, "panel.input_prompt_reminderTime")
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
    if prompt_msg_id:
        await client.edit_message_text(user_id, prompt_msg_id, prompt_text, reply_markup=kb)
    else:
        await message.reply(prompt_text, reply_markup=kb)
    import contextlib

    with contextlib.suppress(Exception):
        await message.delete()


async def _handle_reminder_time_save(ctx, user_id, chat_id, time_value):
    r = get_cache()
    from loguru import logger

    text = await r.get(f"temp_rem_text:{user_id}")
    if not text:
        return
    async with ctx.db() as session:
        rem = Reminder(chatId=chat_id, text=text, sendTime=time_value)
        session.add(rem)
        await session.commit()
        from src.plugins.scheduler.service import execute_reminder

        try:
            hour, minute = rem.sendTime.split(":")
            ctx.scheduler.add_job(
                execute_reminder,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[chat_id, rem.id],
                id=f"reminder:{rem.id}",
                replace_existing=True,
            )
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid sendTime for reminder {rem.id}: {rem.sendTime} - {e}")
    await r.delete(f"temp_rem_text:{user_id}")
