import asyncio
import contextlib

from loguru import logger
from pyrogram import Client, filters
from pyrogram.errors import BadRequest, FloodWait, Forbidden
from pyrogram.types import Message, User
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import FedBan, FedChat, Federation
from src.utils.decorators import admin_only, resolve_target, safe_handler
from src.utils.i18n import at


class FederationPlugin(Plugin):
    """Plugin to manage global bans across multiple groups (Federations)."""

    name = "federation"
    priority = 40

    async def setup(self, client: Client, ctx) -> None:
        pass


async def create_fed(ctx, name: str, owner_id: int) -> Federation:
    """
    Create a new federation owned by a specific user.

    Args:
        ctx (Context): The application context.
        name (str): The name of the federation.
        owner_id (int): The ID of the user who will own the federation.

    Returns:
        Federation: The newly created federation object.
    """
    async with ctx.db() as session:
        fed = Federation(name=name, ownerId=owner_id)
        session.add(fed)
        await session.commit()
        await session.refresh(fed)
        return fed


async def join_fed(ctx, fed_id: str, chat_id: int) -> FedChat:
    """
    Join a group chat to a specific federation.

    Args:
        ctx (Context): The application context.
        fed_id (str): The unique ID of the federation.
        chat_id (int): The ID of the group chat joining the federation.

    Returns:
        FedChat: The newly created or updated federation-chat mapping.
    """
    async with ctx.db() as session:
        stmt = select(FedChat).where(FedChat.chatId == chat_id)
        result = await session.execute(stmt)
        chat = result.scalars().first()
        if chat:
            chat.fedId = fed_id
            session.add(chat)
        else:
            chat = FedChat(fedId=fed_id, chatId=chat_id)
            session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return chat


async def get_fed_by_chat(ctx, chat_id: int) -> Federation | None:
    """
    Retrieve the federation associated with a specific chat, if any.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.

    Returns:
        Federation | None: The federation object, or None if the chat is not in one.
    """
    async with ctx.db() as session:
        stmt = select(FedChat).where(FedChat.chatId == chat_id).options(selectinload(FedChat.fed))
        result = await session.execute(stmt)
        chat = result.scalars().first()
        return chat.fed if chat else None


async def fban_user(ctx, fed_id: str, user_id: int, reason: str, banned_by: int) -> FedBan:
    """
    Apply a federation ban to a user.

    The ban will be enforced in all group chats that are members of this federation.

    Args:
        ctx (Context): The application context.
        fed_id (str): The unique ID of the federation.
        user_id (int): The ID of the user to be banned from the federation.
        reason (str): The reason for the federation ban.
        banned_by (int): The ID of the admin issuing the ban.

    Returns:
        FedBan: The created or updated federation ban record.
    """
    async with ctx.db() as session:
        stmt = select(FedBan).where(FedBan.fedId == fed_id, FedBan.userId == user_id)
        result = await session.execute(stmt)
        ban = result.scalars().first()
        if ban:
            ban.reason = reason
            ban.bannedBy = banned_by
            session.add(ban)
        else:
            ban = FedBan(fedId=fed_id, userId=user_id, reason=reason, bannedBy=banned_by)
            session.add(ban)
        await session.commit()
        await session.refresh(ban)
        return ban


async def is_fbanned(ctx, fed_id: str, user_id: int) -> bool:
    """
    Check if a specific user is currently banned in a federation.

    Args:
        ctx (Context): The application context.
        fed_id (str): The unique ID of the federation.
        user_id (int): The ID of the user.

    Returns:
        bool: True if the user is banned, False otherwise.
    """
    async with ctx.db() as session:
        stmt = select(FedBan).where(FedBan.fedId == fed_id, FedBan.userId == user_id)
        result = await session.execute(stmt)
        ban = result.scalars().first()
        return ban is not None


@bot.on_message(filters.command("newfed") & filters.private)
@safe_handler
async def newfed_handler(client: Client, message: Message) -> None:
    """
    Create a new federation for the user in a private chat.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        Expected command format: /newfed <federation_name>

    Side Effects:
        - Inserts a new federation into the database.
        - Sends a confirmation message with the federation ID.
    """
    if len(message.command) < 2:
        return
    ctx = get_context()
    name = " ".join(message.command[1:])
    fed = await create_fed(ctx, name, message.from_user.id)
    await message.reply(await at(message.chat.id, "federation.created", name=fed.name, id=fed.id))


@bot.on_message(filters.command("joinfed") & filters.group)
@safe_handler
@admin_only
async def joinfed_handler(client: Client, message: Message) -> None:
    """
    Add the current group chat to an existing federation.

    Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        Expected command format: /joinfed <federation_id>

    Side Effects:
        - Updates the chat's federation mapping in the database.
        - Sends a confirmation message.
    """
    if len(message.command) < 2:
        return
    ctx = get_context()
    fed_id = message.command[1]
    await join_fed(ctx, fed_id, message.chat.id)
    await message.reply(await at(message.chat.id, "federation.joined"))


@bot.on_message(filters.command("fban") & filters.group)
@safe_handler
@admin_only
@resolve_target
async def fban_handler(client: Client, message: Message, target_user: User) -> None:
    """
    Issue a federation ban for a specific user in the current group.

    The user will be immediately banned from the current chat and all other chats
    within the same federation. Requires the user to be an admin.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object that triggered the handler.
        target_user (User): The user to be banned (resolved by @resolve_target).

    Side Effects:
        - Inserts/updates a federation ban record in the database.
        - Sends a confirmation message.
    """
    ctx = get_context()
    fed = await get_fed_by_chat(ctx, message.chat.id)
    if not fed:
        await message.reply(await at(message.chat.id, "federation.not_joined"))
        return
    reason = await at(message.chat.id, "common.no_reason")
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])
    await fban_user(ctx, fed.id, target_user.id, reason, message.from_user.id)
    await message.reply(
        await at(message.chat.id, "federation.banned", mention=target_user.mention, fed=fed.name)
    )


@bot.on_message(filters.group & filters.new_chat_members, group=-60)
@safe_handler
async def federation_interceptor(client: Client, message: Message) -> None:
    """
    Monitor new chat members and enforce federation bans.

    If a newly joined member is blacklisted in the federation the chat is joined to,
    they are automatically banned from the group.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object containing new chat members.

    Side Effects:
        - Bans the member if a federation ban is detected.
        - Sends a notification message if a ban occurs.
    """
    ctx = get_context()
    fed = await get_fed_by_chat(ctx, message.chat.id)
    if not fed:
        return
    for member in message.new_chat_members:
        if await is_fbanned(ctx, fed.id, member.id):
            try:
                await client.ban_chat_member(message.chat.id, member.id)
                await message.reply(
                    await at(
                        message.chat.id, "federation.interceptor_banned", mention=member.mention
                    )
                )
            except BadRequest:
                # User might have already left or already banned
                pass
            except Forbidden:
                logger.warning(
                    f"Federation ban failed in {message.chat.id}: Bot lacks ban permissions."
                )
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                # Retry once for federation join
                with contextlib.suppress(Exception):
                    await client.ban_chat_member(message.chat.id, member.id)
            except Exception as e:
                logger.exception(f"Unexpected error in federation_interceptor: {e}")


register(FederationPlugin())
