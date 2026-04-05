from src.core.context import AppContext
from src.db.models import MediaFilter


async def set_media_filter(ctx: AppContext, chat_id: int, **kwargs) -> MediaFilter:
    async with ctx.db() as session:
        obj = await session.get(MediaFilter, chat_id)
        if obj:
            for key, value in kwargs.items():
                setattr(obj, key, value)
            session.add(obj)
        else:
            obj = MediaFilter(chatId=chat_id, **kwargs)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_media_filter(ctx: AppContext, chat_id: int) -> MediaFilter | None:
    async with ctx.db() as session:
        return await session.get(MediaFilter, chat_id)
