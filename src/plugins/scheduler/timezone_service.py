from loguru import logger
from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import GroupCleaner, GroupSettings, NightLock, Reminder


async def reschedule_group_jobs(ctx: AppContext, chat_id: int) -> None:
    """Reschedule all active jobs for a group using its current timezone."""
    from .service import apply_night_lock, execute_reminder, lift_night_lock, run_group_cleaner

    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            return

        tz = settings.timezone or "UTC"

        stmt = select(Reminder).where(Reminder.chatId == chat_id, Reminder.isActive)
        result = await session.execute(stmt)
        for rem in result.scalars().all():
            job_id = f"reminder:{rem.id}"
            ctx.scheduler.add_job(
                execute_reminder,
                trigger="interval",
                minutes=rem.intervalMins,
                args=[chat_id, rem.id],
                id=job_id,
                replace_existing=True,
                timezone=tz,
            )

        # 2. Night Lock
        lock = await session.get(NightLock, chat_id)
        if lock and lock.isEnabled:
            on_id = f"nightlock_on:{chat_id}"
            off_id = f"nightlock_off:{chat_id}"

            ctx.scheduler.add_job(
                apply_night_lock,
                trigger="cron",
                hour=lock.startTime.split(":")[0],
                minute=lock.startTime.split(":")[1],
                args=[chat_id],
                id=on_id,
                replace_existing=True,
                timezone=tz,
            )
            ctx.scheduler.add_job(
                lift_night_lock,
                trigger="cron",
                hour=lock.endTime.split(":")[0],
                minute=lock.endTime.split(":")[1],
                args=[chat_id],
                id=off_id,
                replace_existing=True,
                timezone=tz,
            )

        cleaner = await session.get(GroupCleaner, chat_id)
        if cleaner:
            ctx.scheduler.add_job(
                run_group_cleaner,
                trigger="cron",
                hour=4,
                minute=0,
                args=[chat_id],
                id=f"cleaner:{chat_id}",
                replace_existing=True,
                timezone=tz,
            )

    logger.debug(f"Rescheduled all jobs for group {chat_id} with timezone {tz}")
