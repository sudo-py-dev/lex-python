from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import Blacklist


async def add_blacklist(
    ctx: AppContext,
    chat_id: int,
    pattern: str,
    action: str = "delete",
    is_regex: bool = False,
    is_wildcard: bool = False,
) -> Blacklist | None:
    """Add a pattern to the blacklist for a chat. Limits to 150 entries."""
    async with ctx.db() as session:
        count_stmt = select(Blacklist).where(Blacklist.chatId == chat_id)
        res = await session.execute(count_stmt)
        if len(res.scalars().all()) >= 150:
            return None

        blacklist = Blacklist(
            chatId=chat_id,
            pattern=pattern,
            action=action,
            isRegex=is_regex,
            isWildcard=is_wildcard,
        )
        session.add(blacklist)
        await session.commit()
        await session.refresh(blacklist)
        return blacklist


async def remove_blacklist(ctx: AppContext, chat_id: int, pattern: str) -> bool:
    """Remove a pattern from the blacklist."""
    async with ctx.db() as session:
        stmt = select(Blacklist).where(Blacklist.chatId == chat_id, Blacklist.pattern == pattern)
        result = await session.execute(stmt)
        objs = result.scalars().all()
        if not objs:
            return False
        for obj in objs:
            await session.delete(obj)
        await session.commit()
        return True


async def get_all_blacklist(ctx: AppContext, chat_id: int) -> list[Blacklist]:
    """Get all blacklisted patterns for a chat."""
    async with ctx.db() as session:
        stmt = select(Blacklist).where(Blacklist.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_blacklist_count(ctx: AppContext, chat_id: int) -> int:
    """Get the count of blacklisted patterns for a chat."""
    async with ctx.db() as session:
        stmt = select(Blacklist).where(Blacklist.chatId == chat_id)
        result = await session.execute(stmt)
        return len(result.scalars().all())
