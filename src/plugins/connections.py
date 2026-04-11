from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import UserConnection
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class ConnectionsPlugin(Plugin):
    """Plugin to manage private-to-group administrative connections."""

    name = "connections"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


async def set_active_chat(
    ctx, user_id: int, chat_id: int | None, chat_type: str | None = None
) -> UserConnection:
    """
    Set the active group connection for an administrator.

    This enables the user to manage a specific group through private messages
    with the bot.

    Args:
        ctx (Context): The application context.
        user_id (int): The ID of the administrator.
        chat_id (int | None): The ID of the group chat to connect to, or None to disconnect.
        chat_type (str | None): The type of the chat (e.g., 'supergroup', 'channel').

    Returns:
        UserConnection: The updated or created connection record.
    """
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        if conn:
            conn.activeChatId = chat_id
            conn.chatType = chat_type
            session.add(conn)
        else:
            conn = UserConnection(userId=user_id, activeChatId=chat_id, chatType=chat_type)
            session.add(conn)
        await session.commit()
        await session.refresh(conn)
        return conn


async def get_active_chat(ctx, user_id: int) -> tuple[int | None, str | None]:
    """
    Retrieve the ID and Type of the chat currently connected to the user's private session.
    """
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        if not conn or not conn.activeChatId:
            return None, None
        return int(conn.activeChatId), conn.chatType


async def clear_connection(ctx, user_id: int) -> bool:
    """
    Completely remove a user's active group connection from the database.

    Args:
        ctx (Context): The application context.
        user_id (int): The ID of the administrator.

    Returns:
        bool: True if a connection was found and deleted, False otherwise.
    """
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        if conn:
            await session.delete(conn)
            await session.commit()
            return True
        return False


@bot.on_message(filters.command("connect") & filters.group)
@safe_handler
@admin_only
async def connect_handler(client: Client, message: Message) -> None:
    """
    Establish a connection between the current group and the administrator's private session.

    Once connected, the admin can use commands and access settings for this group
    directly in their private chat with the bot. Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Updates the user's active connection in the database.
        - Sends a confirmation message.
    """
    ctx = get_context()
    await set_active_chat(
        ctx, message.from_user.id, message.chat.id, message.chat.type.name.lower()
    )
    await message.reply(await at(message.chat.id, "connection.connected", chat=message.chat.title))


@bot.on_message(filters.command("disconnect") & filters.private)
@safe_handler
async def disconnect_handler(client: Client, message: Message) -> None:
    """
    Terminate the active group connection in the user's private session.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Removes the active chat ID from the user's connection record in the database.
        - Sends a confirmation message.
    """
    ctx = get_context()
    await set_active_chat(ctx, message.from_user.id, None)
    await message.reply(await at(message.chat.id, "connection.disconnected"))


@bot.on_message(filters.command("connection") & filters.private)
@safe_handler
async def connection_handler(client: Client, message: Message) -> None:
    """
    Report the status and name of the currently connected group.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Queries the database and Telegram API for chat information.
        - Sends a message with the connection details.
    """
    ctx = get_context()
    chat_id, _ = await get_active_chat(ctx, message.from_user.id)
    if not chat_id:
        await message.reply(await at(message.chat.id, "connection.none"))
        return
    try:
        chat = await client.get_chat(chat_id)
        await message.reply(await at(message.chat.id, "connection.current", chat=chat.title))
    except Exception:
        await message.reply(await at(message.chat.id, "connection.none"))


@bot.on_message(filters.private & filters.command("settings"))
@safe_handler
async def pm_settings_handler(client: Client, message: Message) -> None:
    """
    Open the administrative settings panel for the group currently connected via PM.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.

    Side Effects:
        - Triggers the visual settings panel in the private chat.
    """
    ctx = get_context()
    chat_id, chat_type = await get_active_chat(ctx, message.from_user.id)
    if not chat_id:
        await message.reply(await at(message.chat.id, "connection.none"))
        return
    from src.plugins.admin_panel.handlers import open_settings_panel

    await open_settings_panel(client, message, chat_id, chat_type=chat_type)


register(ConnectionsPlugin())
