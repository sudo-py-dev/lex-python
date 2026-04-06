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


async def set_active_chat(ctx, user_id: int, chat_id: int | None) -> UserConnection:
    """Set the active group connection for a user."""
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        if conn:
            conn.activeChatId = chat_id
            session.add(conn)
        else:
            conn = UserConnection(userId=user_id, activeChatId=chat_id)
            session.add(conn)
        await session.commit()
        await session.refresh(conn)
        return conn


async def get_active_chat(ctx, user_id: int) -> int | None:
    """Retrieve the current active group chat ID for a user."""
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        return int(conn.activeChatId) if conn and conn.activeChatId else None


async def clear_connection(ctx, user_id: int) -> bool:
    """Remove a user's active group connection."""
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
    """Connect a group to the user's private session for remote management."""
    ctx = get_context()
    await set_active_chat(ctx, message.from_user.id, message.chat.id)
    await message.reply(await at(message.chat.id, "connection.connected", chat=message.chat.title))


@bot.on_message(filters.command("disconnect") & filters.private)
@safe_handler
async def disconnect_handler(client: Client, message: Message) -> None:
    """Disconnect the current active group from the private session."""
    ctx = get_context()
    await set_active_chat(ctx, message.from_user.id, None)
    await message.reply(await at(message.chat.id, "connection.disconnected"))


@bot.on_message(filters.command("connection") & filters.private)
@safe_handler
async def connection_handler(client: Client, message: Message) -> None:
    """Check the current active group connection status."""
    ctx = get_context()
    chat_id = await get_active_chat(ctx, message.from_user.id)
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
    """Open the settings panel for the currently connected group."""
    ctx = get_context()
    chat_id = await get_active_chat(ctx, message.from_user.id)
    if not chat_id:
        await message.reply(await at(message.chat.id, "connection.none"))
        return
    from src.plugins.admin_panel.handlers import open_settings_panel

    await open_settings_panel(client, message, chat_id)


register(ConnectionsPlugin())
