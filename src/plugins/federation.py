from pyrogram import Client, filters
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
    """Create a new federation owned by a user."""
    async with ctx.db() as session:
        fed = Federation(name=name, ownerId=owner_id)
        session.add(fed)
        await session.commit()
        await session.refresh(fed)
        return fed


async def join_fed(ctx, fed_id: str, chat_id: int) -> FedChat:
    """Join a group chat to a specific federation."""
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
    """Retrieve the federation settings for a specific chat."""
    async with ctx.db() as session:
        stmt = select(FedChat).where(FedChat.chatId == chat_id).options(selectinload(FedChat.fed))
        result = await session.execute(stmt)
        chat = result.scalars().first()
        return chat.fed if chat else None


async def fban_user(ctx, fed_id: str, user_id: int, reason: str, banned_by: int) -> FedBan:
    """Ban a user from a specific federation."""
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
    """Check if a user is banned in a specific federation."""
    async with ctx.db() as session:
        stmt = select(FedBan).where(FedBan.fedId == fed_id, FedBan.userId == user_id)
        result = await session.execute(stmt)
        ban = result.scalars().first()
        return ban is not None


@bot.on_message(filters.command("newfed") & filters.private)
@safe_handler
async def newfed_handler(client: Client, message: Message) -> None:
    """Initialize a new federation (private only)."""
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
    """Join the current group to a federation."""
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
    """Ban a user from the currently joined federation."""
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


@bot.on_message(filters.group & filters.new_chat_members, group=12)
@safe_handler
async def federation_interceptor(client: Client, message: Message) -> None:
    """Interceptor to ban incoming members who are blacklisted in the federation."""
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
            except Exception:
                pass


register(FederationPlugin())
