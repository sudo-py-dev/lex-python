from sqlalchemy import func, select

from src.core.context import AppContext
from src.db.models import UserWarn


async def add_warn(
    ctx: AppContext, chat_id: int, user_id: int, actor_id: int, reason: str | None = None
) -> int:
    """Add a warning to a user and return the new total count."""
    async with ctx.db() as session:
        warn = UserWarn(chatId=chat_id, userId=user_id, actorId=actor_id, reason=reason)
        session.add(warn)
        await session.commit()

        stmt = select(func.count(UserWarn.id)).where(
            UserWarn.chatId == chat_id, UserWarn.userId == user_id
        )
        result = await session.execute(stmt)
        return result.scalar()


async def get_warn_count(ctx: AppContext, chat_id: int, user_id: int) -> int:
    """Get the current warning count for a user."""
    async with ctx.db() as session:
        stmt = select(func.count(UserWarn.id)).where(
            UserWarn.chatId == chat_id, UserWarn.userId == user_id
        )
        result = await session.execute(stmt)
        return result.scalar()


async def reset_warns(ctx: AppContext, chat_id: int, user_id: int) -> None:
    """Delete all warnings for a specific user in a chat."""
    async with ctx.db() as session:
        stmt = select(UserWarn).where(UserWarn.chatId == chat_id, UserWarn.userId == user_id)
        result = await session.execute(stmt)
        objs = result.scalars().all()
        for obj in objs:
            await session.delete(obj)
        await session.commit()


async def get_warns(ctx: AppContext, chat_id: int, user_id: int) -> list[UserWarn]:
    """Get all warning objects for a user."""
    async with ctx.db() as session:
        stmt = select(UserWarn).where(UserWarn.chatId == chat_id, UserWarn.userId == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def reset_all_chat_warns(ctx: AppContext, chat_id: int) -> int:
    """Delete all warnings for all users in a chat."""
    async with ctx.db() as session:
        stmt = select(UserWarn).where(UserWarn.chatId == chat_id)
        result = await session.execute(stmt)
        warns = result.scalars().all()
        count = len(warns)
        for warn in warns:
            await session.delete(warn)
        await session.commit()
        return count


async def get_users_with_warns(ctx: AppContext, chat_id: int) -> list[int]:
    """Get a list of user IDs who have warnings in a chat."""
    async with ctx.db() as session:
        stmt = select(UserWarn.userId).where(UserWarn.chatId == chat_id).distinct()
        result = await session.execute(stmt)
        return list(result.scalars().all())
