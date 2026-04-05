from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import safe_handler


@bot.on_message(filters.command("id"))
@safe_handler
async def id_handler(client: Client, message: Message) -> None:
    pass


@bot.on_message(filters.command("stickerid"))
@safe_handler
async def stickerid_handler(client: Client, message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.sticker:
        return
    await message.reply(f"Sticker ID: `{message.reply_to_message.sticker.file_id}`")


@bot.on_message(filters.command("fileid"))
@safe_handler
async def fileid_handler(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        return
    r = message.reply_to_message
    file_id = None
    if r.photo:
        file_id = r.photo.file_id
    elif r.video:
        file_id = r.video.file_id
    elif r.document:
        file_id = r.document.file_id
    elif r.audio:
        file_id = r.audio.file_id
    elif r.voice:
        file_id = r.voice.file_id
    elif r.animation:
        file_id = r.animation.file_id

    if file_id:
        await message.reply(f"File ID: `{file_id}`")
