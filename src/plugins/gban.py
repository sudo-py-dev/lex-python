import asyncio
import contextlib

from loguru import logger
from pyrogram import Client, filters
from pyrogram.errors import BadRequest, FloodWait, Forbidden
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
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


class GbanPlugin(Plugin):
    name = "gban"
    priority = 60

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("gban") & filters.private)
@safe_handler
@resolve_target
async def gban_handler(client: Client, message: Message, target_user: User) -> None:
    """Global ban a user from all groups."""
    if not message.from_user:
        return

    ctx = get_context()
    if not await is_sudo(ctx, message.from_user.id):
        return

    reason = await at(message.chat.id, "common.no_reason")
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])

    await add_gban(ctx, target_user.id, reason, message.from_user.id)
    await message.reply(
        await at(message.chat.id, "gban.success", mention=target_user.mention, reason=reason)
    )


@bot.on_message(filters.command("ungban") & filters.private)
@safe_handler
@resolve_target
async def ungban_handler(client: Client, message: Message, target_user: User) -> None:
    """Remove a global ban from a user."""
    if not message.from_user:
        return

    ctx = get_context()
    if not await is_sudo(ctx, message.from_user.id):
        return
    success = await remove_gban(ctx, target_user.id)
    if success:
        await message.reply(
            await at(message.chat.id, "gban.ungban_success", mention=target_user.mention)
        )


@bot.on_message(filters.command("addsudo") & filters.private)
@safe_handler
@resolve_target
async def addsudo_handler(client: Client, message: Message, target_user: User) -> None:
    """Add a user to the sudoers list."""
    if not message.from_user:
        return

    ctx = get_context()
    await add_sudo(ctx, target_user.id, message.from_user.id)
    await message.reply(await at(message.chat.id, "gban.addsudo", mention=target_user.mention))


@bot.on_message(filters.group & filters.new_chat_members, group=-50)
@safe_handler
async def gban_interceptor(client: Client, message: Message) -> None:
    """Intercept new chat members and ban if gbanned."""
    if not message.from_user or message.from_user.is_bot:
        return

    ctx = get_context()
    for member in message.new_chat_members:
        if await is_gbanned(ctx, member.id):
            try:
                await client.ban_chat_member(message.chat.id, member.id)
                await message.reply(
                    await at(message.chat.id, "gban.joined", mention=member.mention)
                )
            except BadRequest:
                pass
            except Forbidden:
                logger.warning(f"Gban failed in {message.chat.id}: Bot lacks ban permissions.")
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                with contextlib.suppress(Exception):
                    await client.ban_chat_member(message.chat.id, member.id)
            except Exception as e:
                logger.exception(f"Unexpected error in gban_interceptor: {e}")


register(GbanPlugin())
