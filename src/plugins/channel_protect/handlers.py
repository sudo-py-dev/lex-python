import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import get_channel_protect, set_channel_protect


@bot.on_message(filters.command("antichannel") & filters.group)
@safe_handler
@admin_only
async def antichannel_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(get_ctx(), message.chat.id)
    await set_channel_protect(
        get_ctx(), message.chat.id, anti_channel=mode, anti_anon=cp.antiAnon if cp else False
    )
    await message.reply(
        await at(
            message.chat.id,
            "channel_protect.set",
            type="Anti-channel",
            mode="enabled" if mode else "disabled",
        )
    )


@bot.on_message(filters.command("antianon") & filters.group)
@safe_handler
@admin_only
async def antianon_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    mode = message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(get_ctx(), message.chat.id)
    await set_channel_protect(
        get_ctx(), message.chat.id, anti_channel=cp.antiChannel if cp else False, anti_anon=mode
    )
    await message.reply(
        await at(
            message.chat.id,
            "channel_protect.set",
            type="Anti-anon",
            mode="enabled" if mode else "disabled",
        )
    )


@bot.on_message(filters.group, group=13)
@safe_handler
async def channel_protect_interceptor(client: Client, message: Message) -> None:
    cp = await get_channel_protect(get_ctx(), message.chat.id)
    if not cp:
        return

    if cp.antiChannel and message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        with contextlib.suppress(Exception):
            await message.delete()

    if cp.antiAnon and not message.from_user and message.sender_chat:
        if message.sender_chat.id == message.chat.id:
            pass
        else:
            with contextlib.suppress(Exception):
                await message.delete()
