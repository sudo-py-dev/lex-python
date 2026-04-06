from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import Filter


async def add_filter(
    ctx: AppContext,
    chat_id: int,
    keyword: str,
    text: str,
    response_type: str = "text",
    file_id: str | None = None,
    settings: dict | None = None,
) -> Filter:
    """Add or update a filter for a chat."""
    async with ctx.db() as session:
        stmt = select(Filter).where(Filter.chatId == chat_id, Filter.keyword == keyword)
        result = await session.execute(stmt)
        filter_obj = result.scalars().first()

        if filter_obj:
            filter_obj.text = text
            filter_obj.responseType = response_type
            filter_obj.fileId = file_id
            if settings is not None:
                filter_obj.settings = settings
            session.add(filter_obj)
        else:
            # Check limit
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(Filter).where(Filter.chatId == chat_id)
            count_result = await session.execute(count_stmt)
            count = count_result.scalar()
            if count >= 200:
                raise ValueError("filter_limit_reached")

            filter_obj = Filter(
                chatId=chat_id,
                keyword=keyword,
                text=text,
                responseType=response_type,
                fileId=file_id,
                settings=settings or {},
            )
            session.add(filter_obj)

        await session.commit()
        await session.refresh(filter_obj)
        return filter_obj


async def update_filter_by_id(
    ctx: AppContext,
    filter_id: int,
    keyword: str,
    text: str,
    response_type: str = "text",
    file_id: str | None = None,
    settings: dict | None = None,
) -> bool:
    """Update an existing filter by its ID."""
    async with ctx.db() as session:
        filter_obj = await session.get(Filter, filter_id)
        if not filter_obj:
            return False

        filter_obj.keyword = keyword
        filter_obj.text = text
        filter_obj.responseType = response_type
        filter_obj.fileId = file_id
        if settings is not None:
            filter_obj.settings = settings

        session.add(filter_obj)
        await session.commit()
        return True


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


async def get_filters_paginated(
    ctx: AppContext, chat_id: int, page: int, page_size: int
) -> list[Filter]:
    """Get a paginated list of filters for a specific chat."""
    async with ctx.db() as session:
        stmt = (
            select(Filter)
            .where(Filter.chatId == chat_id)
            .order_by(Filter.keyword)
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_filters_count(ctx: AppContext, chat_id: int) -> int:
    """Get the total count of filters for a specific chat."""
    async with ctx.db() as session:
        from sqlalchemy import func

        stmt = select(func.count()).where(Filter.chatId == chat_id)
        result = await session.execute(stmt)
        return result.scalar() or 0


async def get_filters_for_chat(ctx: AppContext, chat_id: int) -> list[Filter]:
    """Get all filters for a specific chat (alias)."""
    return await get_all_filters(ctx, chat_id)
