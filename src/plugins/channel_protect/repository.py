from src.core.context import AppContext
from src.db.models import ChannelProtect


async def set_channel_protect(
    ctx: AppContext, chat_id: int, anti_channel: bool = False, anti_anon: bool = False
) -> ChannelProtect:
    async with ctx.db() as session:
        obj = await session.get(ChannelProtect, chat_id)
        if obj:
            obj.antiChannel = anti_channel
            obj.antiAnon = anti_anon
            session.add(obj)
        else:
            obj = ChannelProtect(chatId=chat_id, antiChannel=anti_channel, antiAnon=anti_anon)
            session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_channel_protect(ctx: AppContext, chat_id: int) -> ChannelProtect | None:
    async with ctx.db() as session:
        return await session.get(ChannelProtect, chat_id)
