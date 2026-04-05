import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


@bot.on_message(filters.command("purge") & filters.group)
@safe_handler
@admin_only
async def purge_handler(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply(await at(message.chat.id, "purge.usage"))
        return

    message_ids = []

    start_id = message.reply_to_message.id
    end_id = message.id

    # Pyrogram doesn't have a direct "range" delete easily with just IDs if many are missing,
    for msg_id in range(start_id, end_id + 1):
        message_ids.append(msg_id)
        if len(message_ids) >= 100:
            await client.delete_messages(message.chat.id, message_ids)
            message_ids = []
            await asyncio.sleep(0.5)

    if message_ids:
        await client.delete_messages(message.chat.id, message_ids)

    status = await message.reply(
        await at(message.chat.id, "purge.done", count=end_id - start_id + 1)
    )
    await asyncio.sleep(3)
    await status.delete()


@bot.on_message(filters.command("del") & filters.group)
@safe_handler
@admin_only
async def del_handler(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        return
    await asyncio.gather(message.delete(), message.reply_to_message.delete())


@bot.on_message(filters.command("purgeme") & filters.group)
@safe_handler
async def purgeme_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    try:
        n = int(message.command[1])
    except ValueError:
        return

    if n > 100:
        n = 100

    message_ids = []
    async for msg in client.get_chat_history(message.chat.id, limit=n + 10):
        if msg.from_user and msg.from_user.id == message.from_user.id:
            message_ids.append(msg.id)
            if len(message_ids) >= n:
                break

    if message_ids:
        await client.delete_messages(message.chat.id, message_ids)
