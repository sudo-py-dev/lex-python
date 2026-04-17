from datetime import datetime
from zoneinfo import ZoneInfo

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.context import get_context
from src.db.repositories.chats import get_chat_settings
from src.utils.hebcal import get_shabbat_events
from src.utils.i18n import at
from src.utils.permissions import is_admin


@Client.on_message(filters.command("shabbat") & filters.group)
async def shabbat_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    # Check if user is admin as requested
    if not await is_admin(client, chat_id, user_id):
        return

    ctx = get_context()
    settings = await get_chat_settings(ctx, chat_id)

    if not settings or not settings.shabbatLock:
        await message.reply(await at(chat_id, "shabbat.not_configured"))
        return

    tzid = settings.timezone or "Asia/Jerusalem"

    # Show loading message
    temp = await message.reply(await at(chat_id, "shabbat.calculating", timezone=tzid))

    try:
        start, end, _ = await get_shabbat_events(tzid)

        if not start or not end:
            await temp.edit(await at(chat_id, "shabbat.not_configured"))
            return

        target_tz = ZoneInfo(tzid)
        now = datetime.now(target_tz)
        is_active = start <= now <= end

        fmt = "%H:%M"
        if is_active:
            text = await at(
                chat_id,
                "shabbat.status_active",
                unlock_time=end.strftime(fmt),
                timezone=tzid,
            )
        else:
            text = await at(
                chat_id,
                "shabbat.status_inactive",
                lock_time=start.strftime(fmt),
                timezone=tzid,
            )

        await temp.edit(text)
    except Exception as e:
        await temp.edit(f"❌ Error calculating Shabbat times: {e}")
