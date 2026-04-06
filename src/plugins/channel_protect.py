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
    """
    Update or create the channel protection configuration for a specific chat.

    This setting controls whether the bot should automatically delete messages
    sent from channels or anonymous accounts.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.
        anti_channel (bool, optional): Whether to block channel messages. Defaults to False.
        anti_anon (bool, optional): Whether to block anonymous messages. Defaults to False.

    Returns:
        ChannelProtect: The updated or newly created configuration object.
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

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.

    Returns:
        ChannelProtect | None: The configuration object, or None if not set.
    """
    async with ctx.db() as session:
        return await session.get(ChannelProtect, chat_id)


@bot.on_message(filters.command("antichannel") & filters.group)
@safe_handler
@admin_only
async def antichannel_handler(client: Client, message: Message) -> None:
    """
    Toggle the 'Anti-channel' protection mode in the current group.

    When enabled, the bot will delete any message sent from a channel.
    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Updates the chat's channel protection settings in the database.
        - Sends a confirmation message.
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

    When enabled, the bot will delete any message sent by an anonymous user
    (one who is not linked to a specific user profile).
    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Updates the chat's channel protection settings in the database.
        - Sends a confirmation message.
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


@bot.on_message(filters.group, group=13)
@safe_handler
async def channel_protect_interceptor(client: Client, message: Message) -> None:
    """
    Monitor and moderate incoming group messages based on sender type.

    Deletes messages from channels or anonymous accounts if the corresponding
    protection modes are active.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object to inspect.

    Side Effects:
        - Deletes the message if a violation of 'Anti-channel' or 'Anti-anon' is detected.
    """
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
