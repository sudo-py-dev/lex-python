from src.core.context import AppContext
from src.db.models import SlowmodeSetting


async def set_slowmode(ctx: AppContext, chat_id: int, interval: int) -> SlowmodeSetting:
    async with ctx.db() as session:
        obj = await session.get(SlowmodeSetting, chat_id)
        if obj:
            obj.interval = interval
            session.add(obj)
        else:
            obj = SlowmodeSetting(chatId=chat_id, interval=interval)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_slowmode(ctx: AppContext, chat_id: int) -> int:
    async with ctx.db() as session:
        setting = await session.get(SlowmodeSetting, chat_id)
        return setting.interval if setting else 0


async def clear_slowmode(ctx: AppContext, chat_id: int) -> bool:
    async with ctx.db() as session:
        obj = await session.get(SlowmodeSetting, chat_id)
        if obj:
            await session.delete(obj)
            await session.commit()
            return True
        return False
