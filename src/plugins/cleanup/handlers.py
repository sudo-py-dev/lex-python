from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at


@bot.on_message(filters.command("cleanup") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def cleanup_handler(client: Client, message: Message, target_user: User) -> None:
    await client.delete_user_history(message.chat.id, target_user.id)
    await message.reply(await at(message.chat.id, "cleanup.done", mention=target_user.mention))


def get_ctx():
    from src.core.context import get_context

    return get_context()
