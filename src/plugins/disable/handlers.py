from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import (
    disable_command,
    enable_command,
    get_disabled_commands,
    is_command_disabled,
)

NON_DISABLEABLE = {"enable", "disable", "disabled", "settings", "start", "help"}


@bot.on_message(filters.command("disable") & filters.group)
@safe_handler
@admin_only
async def disable_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    command = message.command[1].lower().replace("/", "")
    if command in NON_DISABLEABLE:
        await message.reply(await at(message.chat.id, "disable.not_disableable"))
        return

    await disable_command(get_ctx(), message.chat.id, command)
    await message.reply(await at(message.chat.id, "disable.done", command=command))


@bot.on_message(filters.command("enable") & filters.group)
@safe_handler
@admin_only
async def enable_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    command = message.command[1].lower().replace("/", "")
    await enable_command(get_ctx(), message.chat.id, command)
    await message.reply(await at(message.chat.id, "disable.enabled", command=command))


@bot.on_message(filters.command("disabled") & filters.group)
@safe_handler
async def list_disabled_handler(client: Client, message: Message) -> None:
    disabled = await get_disabled_commands(get_ctx(), message.chat.id)
    if not disabled:
        await message.reply(await at(message.chat.id, "disable.list_empty"))
        return

    text = await at(message.chat.id, "disable.list_header")
    for d in disabled:
        text += f"\n• `/{d.command}`"
    await message.reply(text)


@bot.on_message(filters.group & filters.command(list(NON_DISABLEABLE)), group=-2)
@safe_handler
async def disable_interceptor(client: Client, message: Message) -> None:

    if not message.command:
        return
    command = message.command[0].lower()
    if command in NON_DISABLEABLE:
        return

    if await is_command_disabled(get_ctx(), message.chat.id, command):
        message.stop_propagation()
