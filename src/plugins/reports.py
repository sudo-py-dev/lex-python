import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ReportSetting
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.i18n import at
from src.utils.permissions import Permission


class ReportsPlugin(Plugin):
    """Plugin enabling users to report messages to chat administrators."""

    name = "reports"
    priority = 60

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_report_enabled(ctx, chat_id: int, enabled: bool) -> ReportSetting:
    """Enable or disable the report system in a specific chat."""
    async with ctx.db() as session:
        obj = await session.get(ReportSetting, chat_id)
        if obj:
            obj.enabled = enabled
            session.add(obj)
        else:
            obj = ReportSetting(chatId=chat_id, enabled=enabled)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def is_report_enabled(ctx, chat_id: int) -> bool:
    """Check if the report system is enabled for a specific chat."""
    async with ctx.db() as session:
        setting = await session.get(ReportSetting, chat_id)
        return setting.enabled if setting else True


@bot.on_message(filters.command("report") & filters.group)
@safe_handler
async def report_handler(client: Client, message: Message) -> None:
    """Report the replied-to message to all active administrators."""
    ctx = get_context()
    if not await is_report_enabled(ctx, message.chat.id):
        return
    if not message.reply_to_message:
        await message.reply(await at(message.chat.id, "report.no_reply"))
        return

    from src.utils.admin_cache import get_chat_admins

    admin_ids = await get_chat_admins(client, message.chat.id)
    for admin_id in admin_ids:
        if admin_id == client.me.id:
            continue
        with contextlib.suppress(Exception):
            await client.send_message(
                admin_id,
                await at(
                    message.chat.id,
                    "report.alert",
                    chat=message.chat.title,
                    reporter=message.from_user.mention,
                    target=message.reply_to_message.from_user.mention,
                    preview=message.reply_to_message.text[:100]
                    if message.reply_to_message.text
                    else "Media",
                    link=message.reply_to_message.link,
                ),
            )
    await message.reply(await at(message.chat.id, "report.sent"))


@bot.on_message(filters.regex(r"(?i)@admin") & filters.group)
@safe_handler
async def at_admin_handler(client: Client, message: Message) -> None:
    """Alias for /report triggering when an admin is tagged."""
    await report_handler(client, message)


@bot.on_message(filters.command("reports") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def toggle_reports_handler(client: Client, message: Message) -> None:
    """Toggle the report functionality on or off in the current chat."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    mode = message.command[1].lower() in ("on", "yes", "true")
    await set_report_enabled(ctx, message.chat.id, mode)
    await message.reply(await at(message.chat.id, f"report.{'enabled' if mode else 'disabled'}"))


register(ReportsPlugin())
