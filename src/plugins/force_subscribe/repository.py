from src.core.context import AppContext
from src.db.models import ForceSub


async def set_forcesub(ctx: AppContext, chat_id: int, target_id: int) -> ForceSub:
    async with ctx.db() as session:
        obj = await session.get(ForceSub, chat_id)
        if obj:
            obj.channelId = target_id
            session.add(obj)
        else:
            obj = ForceSub(chatId=chat_id, channelId=target_id)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_forcesub(ctx: AppContext, chat_id: int) -> ForceSub | None:
    async with ctx.db() as session:
        return await session.get(ForceSub, chat_id)


async def remove_forcesub(ctx: AppContext, chat_id: int) -> bool:
    async with ctx.db() as session:
        obj = await session.get(ForceSub, chat_id)
        if obj:
            await session.delete(obj)
            await session.commit()
            return True
        return False
