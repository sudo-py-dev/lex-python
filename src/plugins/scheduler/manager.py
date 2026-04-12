import contextlib
import re
from datetime import UTC, datetime

from loguru import logger

from src.core.context import AppContext

from .repository import SchedulerRepository
from .service import (
    _execute_lift_action,
    apply_night_lock,
    execute_reminder,
    lift_night_lock,
    run_group_cleaner,
)


class SchedulerManager:
    TIME_PATTERN = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")

    @classmethod
    async def sync_all(cls, ctx: AppContext) -> None:
        """Initial sync for all scheduled items on bot startup."""
        try:
            logger.info("Scheduler: Syncing all jobs...")
            now = datetime.now(UTC).replace(tzinfo=None)

            tz_map = await SchedulerRepository.get_all_group_settings(ctx)

            # 1. Timed Actions (Temp bans/mutes)
            actions = await SchedulerRepository.get_active_timed_actions(ctx, now)
            for action in actions:
                delay = (action.expiresAt - now).total_seconds()
                cls.schedule_timed_action(ctx, action.chatId, action.userId, action.action, delay)

            # 2. Reminders
            reminders = await SchedulerRepository.get_active_reminders(ctx)
            for rem in reminders:
                tz = tz_map.get(rem.chatId, "UTC")
                cls.schedule_reminder(ctx, rem.chatId, rem.id, rem.sendTime, tz)

            # 3. Night Locks
            locks = await SchedulerRepository.get_active_night_locks(ctx)
            for lock in locks:
                tz = tz_map.get(lock.chatId, "UTC")
                cls.schedule_night_lock(ctx, lock.chatId, lock.startTime, lock.endTime, tz)

            # 4. Group Cleaners
            cleaners = await SchedulerRepository.get_active_group_cleaners(ctx)
            for cleaner in cleaners:
                tz = tz_map.get(cleaner.chatId, "UTC")
                cls.schedule_cleaner(ctx, cleaner.chatId, tz, cleaner.cleanerRunTime)

            from .service import invalidate_all_admins_task

            ctx.scheduler.add_job(
                invalidate_all_admins_task,
                trigger="interval",
                hours=3,
                id="global_admin_refresh",
                replace_existing=True,
            )

            logger.info("Scheduler: Successfully synced all jobs.")
        except Exception as e:
            logger.error("Scheduler: Fatal error during sync_all: {}", e)

    @classmethod
    async def sync_group(cls, ctx: AppContext, chat_id: int) -> None:
        """Reload all jobs for a specific chat (e.g., after timezone or settings change)."""
        tz, reminders, night_lock, cleaner = await SchedulerRepository.get_group_data(ctx, chat_id)
        if tz is None:
            return

        cls.clear_group_jobs(ctx, chat_id)

        if reminders:
            for rem in reminders:
                cls.schedule_reminder(ctx, chat_id, rem.id, rem.sendTime, tz)

        if night_lock:
            cls.schedule_night_lock(ctx, chat_id, night_lock.startTime, night_lock.endTime, tz)

        if cleaner:
            cls.schedule_cleaner(ctx, chat_id, tz, cleaner.cleanerRunTime)

    @classmethod
    def schedule_timed_action(
        cls, ctx: AppContext, chat_id: int, user_id: int, action: str, delay_seconds: float
    ) -> None:
        if delay_seconds <= 0:
            return
        run_at = datetime.now(UTC).replace(tzinfo=None).timestamp() + delay_seconds
        job_id = f"lift_{action}:{chat_id}:{user_id}"
        try:
            ctx.scheduler.add_job(
                _execute_lift_action,
                trigger="date",
                run_date=datetime.fromtimestamp(run_at, UTC),
                args=[chat_id, user_id, action],
                id=job_id,
                replace_existing=True,
            )
        except Exception as e:
            logger.error("Scheduler: Failed to schedule timed action {}: {}", job_id, e)

    @classmethod
    def schedule_reminder(
        cls, ctx: AppContext, chat_id: int, reminder_id: int, time_str: str, tz: str
    ) -> None:
        hour, minute = cls._parse_time(time_str)
        if hour is None:
            return

        job_id = f"reminder:{reminder_id}"
        try:
            ctx.scheduler.add_job(
                execute_reminder,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[chat_id, reminder_id],
                id=job_id,
                replace_existing=True,
                timezone=tz,
            )
        except Exception as e:
            logger.error("Scheduler: Failed to schedule reminder {}: {}", job_id, e)

    @classmethod
    def schedule_night_lock(
        cls, ctx: AppContext, chat_id: int, start_time: str, end_time: str, tz: str
    ) -> None:
        s_hour, s_min = cls._parse_time(start_time)
        e_hour, e_min = cls._parse_time(end_time)

        if s_hour is None or e_hour is None:
            return

        try:
            ctx.scheduler.add_job(
                apply_night_lock,
                trigger="cron",
                hour=s_hour,
                minute=s_min,
                args=[chat_id],
                id=f"chatnightlock_on:{chat_id}",
                replace_existing=True,
                timezone=tz,
            )
            ctx.scheduler.add_job(
                lift_night_lock,
                trigger="cron",
                hour=e_hour,
                minute=e_min,
                args=[chat_id],
                id=f"chatnightlock_off:{chat_id}",
                replace_existing=True,
                timezone=tz,
            )
        except Exception as e:
            logger.error("Scheduler: Failed to schedule night lock for {}: {}", chat_id, e)

    @classmethod
    def schedule_cleaner(
        cls, ctx: AppContext, chat_id: int, tz: str, run_time: str | None = None
    ) -> None:
        hour, minute = cls._parse_time(run_time) if run_time else (4, 0)
        if hour is None:
            hour, minute = 4, 0
        try:
            ctx.scheduler.add_job(
                run_group_cleaner,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[chat_id],
                id=f"cleaner:{chat_id}",
                replace_existing=True,
                timezone=tz,
            )
        except Exception as e:
            logger.error("Scheduler: Failed to schedule cleaner for {}: {}", chat_id, e)

    @classmethod
    def clear_group_jobs(cls, ctx: AppContext, chat_id: int) -> None:
        """Remove all jobs associated with a specific chat_id."""
        target_ids = []
        for job in ctx.scheduler.get_jobs():
            if (
                f":{chat_id}" in job.id
                or job.id.startswith(f"chatnightlock_on:{chat_id}")
                or job.id.startswith(f"chatnightlock_off:{chat_id}")
                or job.id.startswith(f"cleaner:{chat_id}")
            ):
                target_ids.append(job.id)

        for jid in target_ids:
            with contextlib.suppress(Exception):
                ctx.scheduler.remove_job(jid)

    @staticmethod
    def _parse_time(time_str: str) -> tuple[int | None, int | None]:
        """Safely parse HH:MM strings."""
        if not time_str:
            return None, None
        match = SchedulerManager.TIME_PATTERN.match(time_str)
        if not match:
            logger.warning("Scheduler: Invalid time format '{}'. Expected HH:MM.", time_str)
            return None, None
        return int(match.group(1)), int(match.group(2))
