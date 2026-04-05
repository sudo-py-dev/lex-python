import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ChannelProtect
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class ChannelProtectPlugin(Plugin):
    """Plugin to prevent messages from channels and anonymous senders in groups."""

    name = "channel_protect"
    priority = 18

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_channel_protect(
    ctx, chat_id: int, anti_channel: bool = False, anti_anon: bool = False
) -> ChannelProtect:
    """Update or create channel protection settings for a chat."""
    async with ctx.db() as session:
        obj = await session.get(ChannelProtect, chat_id)
        if obj:
            obj.antiChannel = anti_channel
            obj.antiAnon = anti_anon
            session.add(obj)
        else:
            obj = ChannelProtect(chatId=chat_id, antiChannel=anti_channel, antiAnon=anti_anon)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_channel_protect(ctx, chat_id: int) -> ChannelProtect | None:
    """Retrieve channel protection settings for a chat."""
    async with ctx.db() as session:
        return await session.get(ChannelProtect, chat_id)


@bot.on_message(filters.command("antichannel") & filters.group)
@safe_handler
@admin_only
async def antichannel_handler(client: Client, message: Message) -> None:
    """Toggle anti-channel protection in a group."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    mode = message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(ctx, message.chat.id)
    await set_channel_protect(
        ctx, message.chat.id, anti_channel=mode, anti_anon=cp.antiAnon if cp else False
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
    """Toggle anti-anonymous protection in a group."""
    if len(message.command) < 2:
        return
    ctx = get_context()
    mode = message.command[1].lower() in ("on", "yes", "true")
    cp = await get_channel_protect(ctx, message.chat.id)
    await set_channel_protect(
        ctx, message.chat.id, anti_channel=cp.antiChannel if cp else False, anti_anon=mode
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
    """Interceptor to delete messages from unauthorized sources."""
    ctx = get_context()
    cp = await get_channel_protect(ctx, message.chat.id)
    if not cp:
        return
    if cp.antiChannel and message.sender_chat and message.sender_chat.type == ChatType.CHANNEL:
        with contextlib.suppress(Exception):
            await message.delete()
    if (
        cp.antiAnon
        and not message.from_user
        and message.sender_chat
        and message.sender_chat.id != message.chat.id
    ):
        with contextlib.suppress(Exception):
            await message.delete()


register(ChannelProtectPlugin())
