from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.plugins.admin_panel.handlers import open_settings_panel
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import get_active_chat, set_active_chat


@bot.on_message(filters.command("connect") & filters.group)
@safe_handler
@admin_only
async def connect_handler(client: Client, message: Message) -> None:
    await set_active_chat(get_ctx(), message.from_user.id, message.chat.id)
    await message.reply(await at(message.chat.id, "connection.connected", chat=message.chat.title))


@bot.on_message(filters.command("disconnect") & filters.private)
@safe_handler
async def disconnect_handler(client: Client, message: Message) -> None:
    await set_active_chat(get_ctx(), message.from_user.id, None)
    await message.reply(await at(message.chat.id, "connection.disconnected"))


@bot.on_message(filters.command("connection") & filters.private)
@safe_handler
async def connection_handler(client: Client, message: Message) -> None:
    chat_id = await get_active_chat(get_ctx(), message.from_user.id)
    if not chat_id:
        await message.reply(await at(message.chat.id, "connection.none"))
        return

    try:
        chat = await client.get_chat(chat_id)
        await message.reply(await at(message.chat.id, "connection.current", chat=chat.title))
    except Exception:
        await message.reply(await at(message.chat.id, "connection.none"))


@bot.on_message(filters.private & filters.command("settings"))
@safe_handler
async def pm_settings_handler(client: Client, message: Message) -> None:
    chat_id = await get_active_chat(get_ctx(), message.from_user.id)
    if not chat_id:
        await message.reply(await at(message.chat.id, "connection.none"))
        return
    await open_settings_panel(client, message, chat_id)


@bot.on_message(filters.private & filters.command(["filters", "notes", "rules"]), group=-3)
@safe_handler
async def connection_interceptor(client: Client, message: Message) -> None:
    chat_id = await get_active_chat(get_ctx(), message.from_user.id)
    if chat_id:
        pass
