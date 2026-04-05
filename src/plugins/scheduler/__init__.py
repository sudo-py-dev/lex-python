from datetime import UTC, datetime

from loguru import logger
from pyrogram import Client
from sqlalchemy import select

from src.core.context import AppContext
from src.core.plugin import Plugin, register
from src.db.models import GroupCleaner, NightLock, Reminder, TimedAction

_ctx: AppContext | None = None


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("Scheduler plugin not initialized")
    return _ctx


class SchedulerPlugin(Plugin):
    name = "scheduler"
    priority = 90

    async def setup(self, client: Client, ctx: AppContext) -> None:
        global _ctx
        _ctx = ctx

        from src.db.models import GroupSettings

        from .service import (
            apply_night_lock,
            execute_reminder,
            lift_night_lock,
            run_group_cleaner,
            schedule_timed_action,
        )

        try:
            async with ctx.db() as session:
                now = datetime.now(UTC).replace(tzinfo=None)

                # Load group settings for timezone mapping
                stmt = select(GroupSettings.id, GroupSettings.timezone)
                result = await session.execute(stmt)
                tz_map = {row[0]: row[1] for row in result.all()}

                # 1. Existing Timed Actions (Bans/Mutes) - Always UTC
                stmt = select(TimedAction).where(TimedAction.expiresAt > now)
                result = await session.execute(stmt)
                for action in result.scalars().all():
                    delay = (action.expiresAt - now).total_seconds()
                    schedule_timed_action(ctx, action.chatId, action.userId, action.action, delay)

                # 2. Reminders
                stmt = select(Reminder).where(Reminder.isActive)
                result = await session.execute(stmt)
                for rem in result.scalars().all():
                    tz = tz_map.get(rem.chatId, "UTC")
                    try:
                        hour, minute = rem.sendTime.split(":")
                        ctx.scheduler.add_job(
                            execute_reminder,
                            trigger="cron",
                            hour=hour,
                            minute=minute,
                            args=[rem.chatId, rem.id],
                            id=f"reminder:{rem.id}",
                            replace_existing=True,
                            timezone=tz,
                        )
                    except (ValueError, AttributeError) as e:
                        logger.error(
                            f"Invalid sendTime for reminder {rem.id}: {rem.sendTime} - {e}"
                        )

                # 3. Night Lock
                stmt = select(NightLock).where(NightLock.isEnabled)
                result = await session.execute(stmt)
                for lock in result.scalars().all():
                    tz = tz_map.get(lock.chatId, "UTC")
                    # Apply job
                    ctx.scheduler.add_job(
                        apply_night_lock,
                        trigger="cron",
                        hour=lock.startTime.split(":")[0],
                        minute=lock.startTime.split(":")[1],
                        args=[lock.chatId],
                        id=f"nightlock_on:{lock.chatId}",
                        replace_existing=True,
                        timezone=tz,
                    )
                    # Lift job
                    ctx.scheduler.add_job(
                        lift_night_lock,
                        trigger="cron",
                        hour=lock.endTime.split(":")[0],
                        minute=lock.endTime.split(":")[1],
                        args=[lock.chatId],
                        id=f"nightlock_off:{lock.chatId}",
                        replace_existing=True,
                        timezone=tz,
                    )

                # 4. Group Cleaner (Daily at 04:00 AM local time)
                stmt = select(GroupCleaner)
                result = await session.execute(stmt)
                for cleaner in result.scalars().all():
                    tz = tz_map.get(cleaner.chatId, "UTC")
                    ctx.scheduler.add_job(
                        run_group_cleaner,
                        trigger="cron",
                        hour=4,
                        minute=0,
                        args=[cleaner.chatId],
                        id=f"cleaner:{cleaner.chatId}",
                        replace_existing=True,
                        timezone=tz,
                    )

        except Exception as e:
            logger.error(f"Failed to load scheduled items: {e}")


register(SchedulerPlugin())
