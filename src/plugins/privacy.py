from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import delete

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import UserConnection
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class PrivacyPlugin(Plugin):
    """Plugin handling data management, export, and GDPR-compliance queries."""

    name = "privacy"
    priority = 120

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("privacy") & filters.private)
@safe_handler
async def privacy_handler(client: Client, message: Message) -> None:
    """Provide a copy of the bot's privacy policy."""
    await message.reply(await at(message.chat.id, "privacy.main"))


@bot.on_message(filters.command("exportdata") & filters.private)
@safe_handler
async def export_data_handler(client: Client, message: Message) -> None:
    """Initiate a data export routine for the requesting user."""
    user_id = message.from_user.id
    await message.reply(await at(message.chat.id, "privacy.export_preparing", id=user_id))


@bot.on_message(filters.command("deletedata") & filters.private)
@safe_handler
async def delete_data_handler(client: Client, message: Message) -> None:
    """Delete the requesting user's non-essential stored data (like connections)."""
    user_id = message.from_user.id
    ctx = get_context()
    async with ctx.db() as session:
        stmt = delete(UserConnection).where(UserConnection.userId == user_id)
        await session.execute(stmt)
        await session.commit()
    await message.reply(await at(message.chat.id, "privacy.deleted"))


register(PrivacyPlugin())
