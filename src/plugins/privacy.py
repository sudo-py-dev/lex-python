from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import safe_handler
from src.utils.i18n import at


class PrivacyPlugin(Plugin):
    """Plugin handling data management and GDPR-compliance queries."""

    name = "privacy"
    priority = 120

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("privacy") & filters.private)
@safe_handler
async def privacy_handler(client: Client, message: Message) -> None:
    """Provide a copy of the bot's privacy policy."""
    await message.reply(await at(message.chat.id, "privacy.main"))


register(PrivacyPlugin())
