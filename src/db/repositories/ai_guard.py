from src.core.context import AppContext
from src.db.models.ai import AIGuardSettings


async def get_ai_guard_settings(ctx: AppContext, chat_id: int) -> AIGuardSettings:
    """Get or create AIGuardSettings for a chat."""
    async with ctx.db() as session:
        settings = await session.get(AIGuardSettings, chat_id)
        if not settings:
            settings = AIGuardSettings(chatId=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def update_ai_guard_settings(ctx: AppContext, chat_id: int, **kwargs) -> AIGuardSettings:
    """Update specific fields in AIGuardSettings."""
    async with ctx.db() as session:
        settings = await session.get(AIGuardSettings, chat_id)
        if not settings:
            settings = AIGuardSettings(chatId=chat_id, **kwargs)
            session.add(settings)
        else:
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            session.add(settings)

        await session.commit()
        await session.refresh(settings)
        return settings
