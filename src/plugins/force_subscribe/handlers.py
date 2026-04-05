import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import get_forcesub, remove_forcesub, set_forcesub


@bot.on_message(filters.command("forcesubscribe") & filters.group)
@safe_handler
@admin_only
async def forcesub_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        fs = await get_forcesub(get_ctx(), message.chat.id)
        if fs:
            await message.reply(await at(message.chat.id, "forcesub.current", channel=fs.channelId))
        else:
            await message.reply(await at(message.chat.id, "forcesub.none"))
        return

    target = message.command[1]
    if target.lower() in ("off", "none", "no"):
        await remove_forcesub(get_ctx(), message.chat.id)
        await message.reply(await at(message.chat.id, "forcesub.off"))
        return

    try:
        chat = await client.get_chat(target)
        await set_forcesub(get_ctx(), message.chat.id, chat.id)
        await message.reply(await at(message.chat.id, "forcesub.set", channel=chat.title))
    except Exception:
        await message.reply(await at(message.chat.id, "error.invalid_chat"))


@bot.on_message(filters.group & ~filters.service, group=10)
@safe_handler
async def forcesub_interceptor(client: Client, message: Message) -> None:
    if not message.from_user or message.command:
        return

    fs = await get_forcesub(get_ctx(), message.chat.id)
    if not fs:
        return

    with contextlib.suppress(Exception):
        member = await client.get_chat_member(fs.channelId, message.from_user.id)
        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return

    with contextlib.suppress(Exception):
        await message.delete()
