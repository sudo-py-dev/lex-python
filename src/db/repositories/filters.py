from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import Filter


async def add_filter(
    ctx: AppContext,
    chat_id: int,
    keyword: str,
    response_data: str,
    response_type: str = "text",
    match_mode: str = "contains",
    case_sensitive: bool = False,
) -> Filter:
    """Add or update a filter for a chat."""
    async with ctx.db() as session:
        stmt = select(Filter).where(Filter.chatId == chat_id, Filter.keyword == keyword)
        result = await session.execute(stmt)
        filter_obj = result.scalars().first()

        if filter_obj:
            filter_obj.responseData = response_data
            filter_obj.responseType = response_type
            filter_obj.matchMode = match_mode
            filter_obj.caseSensitive = case_sensitive
            session.add(filter_obj)
        else:
            filter_obj = Filter(
                chatId=chat_id,
                keyword=keyword,
                responseData=response_data,
                responseType=response_type,
                matchMode=match_mode,
                caseSensitive=case_sensitive,
            )
            session.add(filter_obj)

        await session.commit()
        await session.refresh(filter_obj)
        return filter_obj


async def remove_filter(ctx: AppContext, chat_id: int, keyword: str) -> bool:
    """Remove a filter from a chat."""
    async with ctx.db() as session:
        stmt = select(Filter).where(Filter.chatId == chat_id, Filter.keyword == keyword)
        result = await session.execute(stmt)
        filter_obj = result.scalars().first()
        if filter_obj:
            await session.delete(filter_obj)
            await session.commit()
            return True
        return False


async def remove_filter_by_id(ctx: AppContext, filter_id: int) -> bool:
    """Remove a filter by its ID."""
    async with ctx.db() as session:
        filter_obj = await session.get(Filter, filter_id)
        if filter_obj:
            await session.delete(filter_obj)
            await session.commit()
            return True
        return False


async def remove_all_filters(ctx: AppContext, chat_id: int) -> int:
    """Remove all filters from a chat. Returns the number of removed filters."""
    async with ctx.db() as session:
        from sqlalchemy import delete
        stmt = delete(Filter).where(Filter.chatId == chat_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def get_all_filters(ctx: AppContext, chat_id: int) -> list[Filter]:
    """Get all filters for a specific chat."""
    async with ctx.db() as session:
        stmt = select(Filter).where(Filter.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_filters_for_chat(ctx: AppContext, chat_id: int) -> list[Filter]:
    """Get all filters for a specific chat (alias)."""
    return await get_all_filters(ctx, chat_id)
