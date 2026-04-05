from src.core.context import AppContext
from src.db.models import GroupSettings


async def get_settings(ctx: AppContext, chat_id: int) -> GroupSettings:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def set_flood_settings(
    ctx: AppContext, chat_id: int, threshold: int, window: int, action: str
) -> GroupSettings:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if settings:
            settings.floodThreshold = threshold
            settings.floodWindow = window
            settings.floodAction = action
            session.add(settings)
        else:
            settings = GroupSettings(
                id=chat_id,
                floodThreshold=threshold,
                floodWindow=window,
                floodAction=action,
            )
            session.add(settings)
        await session.commit()
        await session.refresh(settings)
        return settings
