import contextlib

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import ChannelProtect
from src.db.repositories.allowed_channels import (
    add_allowed_channel,
    get_allowed_channels,
    remove_allowed_channel,
)
from src.utils.allowlist_cache import (
    invalidate_allowlist_cache,
)
from src.utils.allowlist_cache import (
    is_channel_allowed as cached_is_channel_allowed,
)
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
    """
    Update or create the channel protection configuration for a specific chat.
    """
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
    """
    Retrieve the current channel protection configuration for a chat.
    """
    async with ctx.db() as session:
        return await session.get(ChannelProtect, chat_id)


@bot.on_message(filters.command("antichannel") & filters.group)
@safe_handler
@admin_only
async def antichannel_handler(client: Client, message: Message) -> None:
    """
    Toggle the 'Anti-channel' protection mode in the current group.
    """
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
    """
    Toggle the 'Anti-anonymous' protection mode in the current group.
    """
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


@bot.on_message(filters.command("allowlist") & filters.group)
@safe_handler
@admin_only
async def allowlist_handler(client: Client, message: Message) -> None:
    """
    Whitelist a channel for the current group.
    Format: /allowlist [channel_id | reply to channel message]
    """
    target_id = None
    if message.reply_to_message and message.reply_to_message.sender_chat:
        target_id = message.reply_to_message.sender_chat.id
    elif len(message.command) > 1:
        with contextlib.suppress(ValueError):
            target_id = int(message.command[1])

    if not target_id:
        return

    ctx = get_context()
    try:
        await add_allowed_channel(ctx, message.chat.id, target_id)
        await invalidate_allowlist_cache(message.chat.id)
        await message.reply(await at(message.chat.id, "allowlist.added", channel_id=target_id))
    except ValueError as e:
        if str(e) == "allowlist_limit_reached":
            await message.reply(await at(message.chat.id, "allowlist.limit_reached"))
        else:
            raise e


@bot.on_message(filters.command("unallowlist") & filters.group)
@safe_handler
@admin_only
async def unallowlist_handler(client: Client, message: Message) -> None:
    """Remove a channel from the whitelist."""
    target_id = None
    if message.reply_to_message and message.reply_to_message.sender_chat:
        target_id = message.reply_to_message.sender_chat.id
    elif len(message.command) > 1:
        with contextlib.suppress(ValueError):
            target_id = int(message.command[1])

    if not target_id:
        return

    ctx = get_context()
    if await remove_allowed_channel(ctx, message.chat.id, target_id):
        await invalidate_allowlist_cache(message.chat.id)
        await message.reply(await at(message.chat.id, "allowlist.removed", channel_id=target_id))
    else:
        await message.reply(await at(message.chat.id, "allowlist.not_found"))


@bot.on_message(filters.command("allowlisted") & filters.group)
@safe_handler
async def list_allowed_handler(client: Client, message: Message) -> None:
    """List all whitelisted channels."""
    ctx = get_context()
    allowed = await get_allowed_channels(ctx, message.chat.id)
    if not allowed:
        await message.reply(await at(message.chat.id, "allowlist.empty"))
        return

    text = await at(message.chat.id, "allowlist.header")
    for a in allowed:
        text += f"\n• `{a.channelId}`"
    await message.reply(text)


@bot.on_message(filters.group, group=13)
@safe_handler
async def channel_protect_interceptor(client: Client, message: Message) -> None:
    """
    Monitor and moderate incoming group messages based on sender type.
    """
    # Skip if whitelisted channel
    if (
        message.sender_chat
        and message.sender_chat.type == ChatType.CHANNEL
        and await cached_is_channel_allowed(message.chat.id, message.sender_chat.id)
    ):
        return

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
