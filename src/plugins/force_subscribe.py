import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ForceSub
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class ForceSubscribePlugin(Plugin):
    """Plugin to mandate channel subscription before participating in group chats."""

    name = "force_subscribe"
    priority = 25

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_forcesub(ctx, chat_id: int, target_id: int) -> ForceSub:
    """Set the mandatory channel for a specific group."""
    async with ctx.db() as session:
        obj = await session.get(ForceSub, chat_id)
        if obj:
            obj.channelId = target_id
            session.add(obj)
        else:
            obj = ForceSub(chatId=chat_id, channelId=target_id)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_forcesub(ctx, chat_id: int) -> ForceSub | None:
    """Retrieve the mandatory channel configuration for a group."""
    async with ctx.db() as session:
        return await session.get(ForceSub, chat_id)


async def remove_forcesub(ctx, chat_id: int) -> bool:
    """Remove mandatory channel subscription requirement for a group."""
    async with ctx.db() as session:
        obj = await session.get(ForceSub, chat_id)
        if obj:
            await session.delete(obj)
            await session.commit()
            return True
        return False


@bot.on_message(filters.command("forcesubscribe") & filters.group)
@safe_handler
@admin_only
async def forcesub_handler(client: Client, message: Message) -> None:
    """Configure or disable force subscription for the current group."""
    ctx = get_context()
    if len(message.command) < 2:
        fs = await get_forcesub(ctx, message.chat.id)
        if fs:
            await message.reply(await at(message.chat.id, "forcesub.current", channel=fs.channelId))
        else:
            await message.reply(await at(message.chat.id, "forcesub.none"))
        return
    target = message.command[1]
    if target.lower() in ("off", "none", "no"):
        await remove_forcesub(ctx, message.chat.id)
        await message.reply(await at(message.chat.id, "forcesub.off"))
        return
    try:
        chat = await client.get_chat(target)
        await set_forcesub(ctx, message.chat.id, chat.id)
        await message.reply(await at(message.chat.id, "forcesub.set", channel=chat.title))
    except Exception:
        await message.reply(await at(message.chat.id, "error.invalid_chat"))


@bot.on_message(filters.group & ~filters.service, group=10)
@safe_handler
async def forcesub_interceptor(client: Client, message: Message) -> None:
    """Interceptor to delete messages from members not subscribed to the mandated channel."""
    if not message.from_user or message.command:
        return
    ctx = get_context()
    fs = await get_forcesub(ctx, message.chat.id)
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


register(ForceSubscribePlugin())
