from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import safe_handler
from src.utils.i18n import at


@bot.on_message(filters.command("privacy") & filters.private)
@safe_handler
async def privacy_handler(client: Client, message: Message) -> None:
    await message.reply(await at(message.chat.id, "privacy.main"))


@bot.on_message(filters.command("exportdata") & filters.private)
@safe_handler
async def export_data_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    await message.reply(await at(message.chat.id, "privacy.export_preparing", id=user_id))


@bot.on_message(filters.command("deletedata") & filters.private)
@safe_handler
async def delete_data_handler(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    ctx = get_ctx()
    await ctx.db.userconnection.delete_many(where={"userId": user_id})
    await message.reply(await at(message.chat.id, "privacy.deleted"))


def get_ctx():
    from src.core.context import get_context

    return get_context()
