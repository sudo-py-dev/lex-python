from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx


@bot.on_message(filters.command("setlog") & filters.group)
@safe_handler
@admin_only
async def set_log_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        if message.reply_to_message and message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            return
    else:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            return

    await get_ctx().db.groupsettings.update(
        where={"id": message.chat.id}, data={"logChannelId": channel_id}
    )
    await message.reply(await at(message.chat.id, "log.set"))


@bot.on_message(filters.command("unsetlog") & filters.group)
@safe_handler
@admin_only
async def unset_log_handler(client: Client, message: Message) -> None:
    await get_ctx().db.groupsettings.update(
        where={"id": message.chat.id}, data={"logChannelId": None}
    )
    await message.reply(await at(message.chat.id, "log.unset"))
