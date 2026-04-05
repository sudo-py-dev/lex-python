from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.repositories.gban import (
    add_gban,
    add_sudo,
    is_gbanned,
    is_sudo,
    remove_gban,
)
from src.utils.decorators import resolve_target, safe_handler
from src.utils.i18n import at

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Gban plugin not initialized")
    return _ctx


class GbanPlugin(Plugin):
    name = "gban"
    priority = 60

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx


@bot.on_message(filters.command("gban") & filters.private)
@safe_handler
@resolve_target
async def gban_handler(client: Client, message: Message, target_user: User) -> None:
    if not await is_sudo(get_ctx(), message.from_user.id):
        return

    reason = "No reason provided"
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])

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


register(GbanPlugin())
