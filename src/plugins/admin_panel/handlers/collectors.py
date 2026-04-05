from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.db.models import GroupCleaner, NightLock, Reminder
from src.utils.i18n import at
from src.utils.permissions import is_admin

from .. import get_ctx


@bot.on_message(filters.private & filters.text & ~filters.regex(r"^/.*"))
async def admin_panel_input_collector(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    r = get_cache()
    state = await r.get(f"panel_input:{user_id}")
    if not state:
        return

    parts = state.split(":")
    if len(parts) >= 3:
        chat_id = int(parts[0])
        field = parts[1]
        prompt_msg_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    elif len(parts) == 2:
        chat_id = int(parts[0])
        field = parts[1]
        prompt_msg_id = None
        page = 0
    else:
        return

    value: int | str = message.text

    if field in (
        "floodThreshold",
        "floodWindow",
        "warnLimit",
        "raidThreshold",
        "raidWindow",
        "captchaTimeout",
        "slowmode",
        "purgeMessagesCount",
    ):
        if not value.isdigit() or int(value) < 0:
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            import contextlib

            with contextlib.suppress(Exception):
                await message.delete()
            return
        value = int(value)
        if field == "warnLimit" and value < 1:
            value = 1

        value = int(value)

    elif field == "logChannelId":
        if not value.lstrip("-").isdigit():
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            import contextlib

            with contextlib.suppress(Exception):
                await message.delete()
            return
        value = int(value)

    elif field == "langblockInput":
        from src.plugins.lang_block.service import is_supported, parse_iso_code

        parsed_iso = parse_iso_code(str(value))
        if not parsed_iso or not is_supported(parsed_iso):
            await message.reply(await at(user_id, "panel.langblock_invalid_input"))
            import contextlib

            with contextlib.suppress(Exception):
                await message.delete()
            return
        value = parsed_iso

    elif field == "blacklistInput":
        from src.plugins.blacklist.handlers import detect_pattern_type

        pattern_raw = str(value).lower()
        is_regex, is_wildcard, pattern = detect_pattern_type(pattern_raw)

        if is_regex:
            import re

            try:
                re.compile(pattern)
            except re.error:
                await message.reply(await at(user_id, "panel.blacklist_invalid_regex"))
                return

        value = (pattern, is_regex, is_wildcard)

    elif field == "reminderTime" or field in ("nightlockStart", "nightlockEnd"):
        import re

        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", str(value)):
            await message.reply(await at(user_id, "panel.input_invalid_time"))
            return
        value = str(value)

    elif field == "cleanerInactive":
        if not value.isdigit() or int(value) < 0:
            await message.reply(await at(user_id, "panel.input_invalid_number"))
            return
        value = int(value)

    elif field == "timezoneSearch":
        value = str(value)

    await r.delete(f"panel_input:{user_id}")

    if not await is_admin(client, chat_id, user_id):
        await message.reply(await at(user_id, "panel.error_not_admin"))
        return

    ctx = get_ctx()
    from ..repository import update_chat_setting

    if field == "langblockInput":
        from src.plugins.lang_block.repository import add_lang_block

        try:
            await add_lang_block(ctx, chat_id, str(value))
        except Exception:
            await message.reply(await at(user_id, "panel.error_generic"))
            return
    elif field == "slowmode":
        from src.plugins.slowmode.repository import clear_slowmode, set_slowmode

        if value > 0:
            await set_slowmode(ctx, chat_id, value)
        else:
            await clear_slowmode(ctx, chat_id)
    elif field == "blacklistInput":
        from src.plugins.blacklist.repository import add_blacklist, get_blacklist_count

        pattern, is_regex, is_wildcard = value
        count = await get_blacklist_count(ctx, chat_id)
        if count >= 150:
            await message.reply(await at(chat_id, "panel.blacklist_limit_reached"))
            return
        await add_blacklist(ctx, chat_id, pattern, is_regex=is_regex, is_wildcard=is_wildcard)

    elif field == "purgeMessagesCount":
        count = int(value)

        async def do_purge():
            import contextlib

            try:
                dummy = await client.send_message(
                    chat_id, await at(chat_id, "panel.purge_in_progress")
                )
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

        import asyncio

        asyncio.create_task(do_purge())

    elif field == "rulesText":
        from src.plugins.rules.repository import set_rules

        await set_rules(ctx, chat_id, str(value))
    elif field == "reminderText":
        await r.set(f"temp_rem_text:{user_id}", str(value), ttl=300)
        await r.set(
            f"panel_input:{user_id}", f"{chat_id}:reminderTime:{prompt_msg_id}:{page}", ttl=300
        )
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
        return

    elif field == "reminderTime":
        text = await r.get(f"temp_rem_text:{user_id}")
        if not text:
            await message.reply("❌ Failed to retrieve reminder text. Please try again.")
            return
        async with ctx.db() as session:
            rem = Reminder(chatId=chat_id, text=text, sendTime=str(value))
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

    elif field in ("nightlockStart", "nightlockEnd"):
        async with ctx.db() as session:
            lock = await session.get(NightLock, chat_id)
            if not lock:
                lock = NightLock(chatId=chat_id)
            if field == "nightlockStart":
                lock.startTime = str(value)
            else:
                lock.endTime = str(value)
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

    elif field == "cleanerInactive":
        async with ctx.db() as session:
            cleaner = await session.get(GroupCleaner, chat_id)
            if not cleaner:
                cleaner = GroupCleaner(chatId=chat_id)
            cleaner.cleanInactiveDays = int(value)
            session.add(cleaner)
            await session.commit()

    else:
        await update_chat_setting(ctx, chat_id, field, value)

    if field.startswith("flood"):
        from .keyboards import flood_kb

        kb = await flood_kb(ctx, chat_id)
        text_id = "panel.flood_text"
    elif field.startswith("welcome"):
        from .keyboards import welcome_kb

        kb = await welcome_kb(ctx, chat_id)
        text_id = "panel.welcome_text"
    elif field == "slowmode":
        from .moderation_kbs import slowmode_kb

        kb = await slowmode_kb(ctx, chat_id)
        text_id = "panel.slowmode_text"
    elif field == "langblockInput":
        from .moderation_kbs import langblock_kb

        kb = await langblock_kb(ctx, chat_id, page)
        text_id = "panel.langblock_text"
    elif field == "warnLimit":
        from .moderation_kbs import warns_kb

        kb = await warns_kb(ctx, chat_id)
        text_id = "panel.warns_text"
    elif field == "logChannelId":
        from .moderation_kbs import logging_kb

        kb = await logging_kb(ctx, chat_id)
        text_id = "panel.logging_text"
    elif field.startswith("raid"):
        from .security_kbs import raid_kb

        kb = await raid_kb(ctx, chat_id)
        text_id = "panel.raid_text"
    elif field.startswith("captcha"):
        from .security_kbs import captcha_kb

        kb = await captcha_kb(ctx, chat_id)
        text_id = "panel.captcha_text"
    elif field == "rulesText":
        from .keyboards import rules_kb

        kb = await rules_kb(chat_id)
        text_id = "panel.rules_text"
    elif field == "blacklistInput":
        from .moderation_kbs import blacklist_kb

        kb = await blacklist_kb(ctx, chat_id, page)
        text_id = "panel.blacklist_text"
    elif field.startswith("reminder"):
        from .keyboards import reminders_menu_kb

        kb = await reminders_menu_kb(ctx, chat_id)
        text_id = "panel.reminder_text"
    elif field.startswith("nightlock"):
        from .keyboards import nightlock_menu_kb

        kb = await nightlock_menu_kb(ctx, chat_id)
        text_id = "panel.nightlock_text"
    elif field == "cleanerInactive":
        from .keyboards import cleaner_menu_kb

        kb = await cleaner_menu_kb(ctx, chat_id)
        text_id = "panel.cleaner_text"
    elif field == "purgeMessagesCount":
        from .keyboards import moderation_category_kb

        kb = await moderation_category_kb(chat_id)
        text_id = "panel.moderation_text"
    elif field == "timezoneSearch":
        from .keyboards import timezone_picker_kb

        kb = await timezone_picker_kb(ctx, chat_id, user_id=user_id, filter_query=str(value))
        text_id = "panel.timezone_search_results_text"
    else:
        from .keyboards import main_menu_kb

        kb = await main_menu_kb(chat_id, True)
        text_id = "panel.main_text"

    if text_id == "panel.warns_text":
        from ..repository import get_chat_settings

        s = await get_chat_settings(ctx, chat_id)
        main_text = await at(
            chat_id,
            text_id,
            limit=s.warnLimit,
            action=s.warnAction.capitalize(),
            expiry=s.warnExpiry.capitalize(),
        )
    elif text_id == "panel.slowmode_text":
        from src.plugins.slowmode.repository import get_slowmode

        i = await get_slowmode(ctx, chat_id)
        main_text = await at(chat_id, text_id, interval=i)
    elif text_id == "panel.logging_text":
        main_text = await at(chat_id, text_id, channel=value)
    elif text_id == "panel.raid_text":
        from ..repository import get_chat_settings

        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            chat_id, "panel.status_enabled" if s.raidEnabled else "panel.status_disabled"
        )
        main_text = await at(
            chat_id,
            text_id,
            status=status,
            threshold=s.raidThreshold,
            window=s.raidWindow,
            action=s.raidAction.capitalize(),
        )
    elif text_id == "panel.captcha_text":
        from ..repository import get_chat_settings

        s = await get_chat_settings(ctx, chat_id)
        status = await at(
            chat_id, "panel.status_enabled" if s.captchaEnabled else "panel.status_disabled"
        )
        main_text = await at(
            chat_id,
            text_id,
            status=status,
            mode=s.captchaMode.capitalize(),
            timeout=s.captchaTimeout,
            action=await at(chat_id, "action.ban"),
        )
    elif text_id == "panel.timezone_search_results_text":
        main_text = await at(chat_id, text_id, query=value)
    else:
        main_text = await at(chat_id, text_id)

    import contextlib

    with contextlib.suppress(Exception):
        await message.delete()

    success_text = await at(user_id, "panel.input_success")
    combined_text = f"**{success_text}**\n\n{main_text}"

    if prompt_msg_id:
        try:
            await client.edit_message_text(
                chat_id=user_id, message_id=prompt_msg_id, text=combined_text, reply_markup=kb
            )
        except Exception:
            await message.reply(combined_text, reply_markup=kb)
    else:
        await message.reply(combined_text, reply_markup=kb)


async def start_collector(
    user_id: int, chat_id: int, field: str, prompt_msg_id: int | None = None, page: int = 0
) -> None:
    """Sets the state for the input collector in Local Cache."""
    r = get_cache()
    msg_id = prompt_msg_id or 0
    await r.set(f"panel_input:{user_id}", f"{chat_id}:{field}:{msg_id}:{page}", ttl=300)
