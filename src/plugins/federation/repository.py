from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.context import AppContext
from src.db.models import FedBan, FedChat, Federation


async def create_fed(ctx: AppContext, name: str, owner_id: int) -> Federation:
    async with ctx.db() as session:
        fed = Federation(name=name, ownerId=owner_id)
        session.add(fed)
        await session.commit()
        await session.refresh(fed)
        return fed


async def join_fed(ctx: AppContext, fed_id: str, chat_id: int) -> FedChat:
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


async def get_fed_by_chat(ctx: AppContext, chat_id: int) -> Federation | None:
    async with ctx.db() as session:
        stmt = select(FedChat).where(FedChat.chatId == chat_id).options(selectinload(FedChat.fed))
        result = await session.execute(stmt)
        chat = result.scalars().first()
        return chat.fed if chat else None


async def fban_user(
    ctx: AppContext, fed_id: str, user_id: int, reason: str, banned_by: int
) -> FedBan:
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


async def is_fbanned(ctx: AppContext, fed_id: str, user_id: int) -> bool:
    async with ctx.db() as session:
        stmt = select(FedBan).where(FedBan.fedId == fed_id, FedBan.userId == user_id)
        result = await session.execute(stmt)
        ban = result.scalars().first()
        return ban is not None
