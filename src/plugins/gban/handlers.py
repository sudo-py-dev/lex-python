from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.utils.decorators import resolve_target, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import add_gban, add_sudo, is_gbanned, is_sudo, remove_gban


@bot.on_message(filters.command("gban") & filters.private)
@safe_handler
@resolve_target
async def gban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await is_sudo(get_ctx(), message.from_user.id):
        return

    reason = "No reason provided"
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])
    elif not message.reply_to_message and len(message.command) > 1:
        pass

    await add_gban(get_ctx(), target_user.id, reason, message.from_user.id)
    await message.reply(
        await at(message.chat.id, "gban.success", mention=target_user.mention, reason=reason)
    )


@bot.on_message(filters.command("ungban") & filters.private)
@safe_handler
@resolve_target
async def ungban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await is_sudo(get_ctx(), message.from_user.id):
        return
    success = await remove_gban(get_ctx(), target_user.id)
    if success:
        await message.reply(
            await at(message.chat.id, "gban.ungban_success", mention=target_user.mention)
        )


@bot.on_message(filters.command("addsudo") & filters.private)
@safe_handler
@resolve_target
async def addsudo_handler(client: Client, message: Message, target_user: User) -> None:
    await add_sudo(get_ctx(), target_user.id, message.from_user.id)
    await message.reply(await at(message.chat.id, "gban.addsudo", mention=target_user.mention))


@bot.on_message(filters.group & filters.new_chat_members, group=6)
@safe_handler
async def gban_interceptor(client: Client, message: Message) -> None:
    for member in message.new_chat_members:
        if await is_gbanned(get_ctx(), member.id):
            try:
                await client.ban_chat_member(message.chat.id, member.id)
                await message.reply(
                    await at(message.chat.id, "gban.joined", mention=member.mention)
                )
            except Exception:
                pass
