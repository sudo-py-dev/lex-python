from src.core.context import AppContext
from src.db.models import GroupSettings


async def get_settings(ctx: AppContext, chat_id: int) -> GroupSettings:
    """Get or create GroupSettings for a chat."""
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def update_settings(ctx: AppContext, chat_id: int, **kwargs) -> GroupSettings:
    """Update specific fields in GroupSettings."""
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id, **kwargs)
            session.add(settings)
        else:
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            session.add(settings)

        await session.commit()
        await session.refresh(settings)
        return settings
