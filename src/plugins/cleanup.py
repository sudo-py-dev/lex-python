from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at


class CleanupPlugin(Plugin):
    """Plugin to remove message history of a specific user in a group."""

    name = "cleanup"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("cleanup") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def cleanup_handler(client: Client, message: Message, target_user: User) -> None:
    """Delete all messages from a specific user in the current chat."""
    await client.delete_user_history(message.chat.id, target_user.id)
    await message.reply(await at(message.chat.id, "cleanup.done", mention=target_user.mention))


register(CleanupPlugin())
