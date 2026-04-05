from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import create_fed, fban_user, get_fed_by_chat, is_fbanned, join_fed


@bot.on_message(filters.command("newfed") & filters.private)
@safe_handler
async def newfed_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    name = " ".join(message.command[1:])
    fed = await create_fed(get_ctx(), name, message.from_user.id)
    await message.reply(await at(message.chat.id, "federation.created", name=fed.name, id=fed.id))


@bot.on_message(filters.command("joinfed") & filters.group)
@safe_handler
@admin_only
async def joinfed_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    fed_id = message.command[1]
    await join_fed(get_ctx(), fed_id, message.chat.id)
    await message.reply(await at(message.chat.id, "federation.joined"))


@bot.on_message(filters.command("fban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def fban_handler(client: Client, message: Message, target_user: User) -> None:
    fed = await get_fed_by_chat(get_ctx(), message.chat.id)
    if not fed:
        await message.reply(await at(message.chat.id, "federation.not_joined"))
        return

    reason = "No reason provided"
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])

    await fban_user(get_ctx(), fed.id, target_user.id, reason, message.from_user.id)
    await message.reply(
        await at(message.chat.id, "federation.banned", mention=target_user.mention, fed=fed.name)
    )


@bot.on_message(filters.group & filters.new_chat_members, group=12)
@safe_handler
async def federation_interceptor(client: Client, message: Message) -> None:
    fed = await get_fed_by_chat(get_ctx(), message.chat.id)
    if not fed:
        return

    for member in message.new_chat_members:
        if await is_fbanned(get_ctx(), fed.id, member.id):
            try:
                await client.ban_chat_member(message.chat.id, member.id)
                await message.reply(
                    await at(
                        message.chat.id, "federation.interceptor_banned", mention=member.mention
                    )
                )
            except Exception:
                pass
