from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import GroupCleaner, GroupSettings, NightLock, Reminder, TimedAction


class SchedulerRepository:
    @staticmethod
    async def get_all_group_settings(ctx: AppContext) -> dict[int, str]:
        """Fetch all chat IDs and their timezones."""
        async with ctx.db() as session:
            stmt = select(GroupSettings.id, GroupSettings.timezone)
            result = await session.execute(stmt)
            return {row[0]: row[1] or "UTC" for row in result.all()}

    @staticmethod
    async def get_active_timed_actions(ctx: AppContext, now):
        """Fetch all non-expired timed actions."""
        async with ctx.db() as session:
            stmt = select(TimedAction).where(TimedAction.expiresAt > now)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def get_active_reminders(ctx: AppContext):
        """Fetch all active reminders."""
        async with ctx.db() as session:
            stmt = select(Reminder).where(Reminder.isActive)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def get_active_night_locks(ctx: AppContext):
        """Fetch all enabled night locks."""
        async with ctx.db() as session:
            stmt = select(NightLock).where(NightLock.isEnabled)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def get_active_group_cleaners(ctx: AppContext):
        """Fetch all group cleaners (currently all are active if they exist)."""
        async with ctx.db() as session:
            stmt = select(GroupCleaner)
            result = await session.execute(stmt)
            return result.scalars().all()

    @staticmethod
    async def get_group_data(ctx: AppContext, chat_id: int):
        """Fetch all data for a single group for targeted rescheduling."""
        async with ctx.db() as session:
            settings = await session.get(GroupSettings, chat_id)
            if not settings:
                return None, None, None, None

            # Fetch related models
            stmt = select(Reminder).where(Reminder.chatId == chat_id, Reminder.isActive)
            reminders = (await session.execute(stmt)).scalars().all()

            stmt = select(NightLock).where(NightLock.chatId == chat_id, NightLock.isEnabled)
            night_lock = (await session.execute(stmt)).scalars().first()

            stmt = select(GroupCleaner).where(GroupCleaner.chatId == chat_id)
            cleaner = (await session.execute(stmt)).scalars().first()

            return settings.timezone or "UTC", reminders, night_lock, cleaner
