import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import is_report_enabled, set_report_enabled


@bot.on_message(filters.command("report") & filters.group)
@safe_handler
async def report_handler(client: Client, message: Message) -> None:
    if not await is_report_enabled(get_ctx(), message.chat.id):
        return

    if not message.reply_to_message:
        await message.reply(await at(message.chat.id, "report.no_reply"))
        return

    async for admin in client.get_chat_members(message.chat.id, filter="administrators"):
        if admin.user.is_bot:
            continue
        with contextlib.suppress(Exception):
            await client.send_message(
                admin.user.id,
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
    await report_handler(client, message)


@bot.on_message(filters.command("reports") & filters.group)
@safe_handler
@admin_only
async def toggle_reports_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")
    await set_report_enabled(get_ctx(), message.chat.id, mode)
    await message.reply(await at(message.chat.id, f"report.{'enabled' if mode else 'disabled'}"))
