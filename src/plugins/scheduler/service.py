from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import AppContext
from src.db.models import GroupCleaner, NightLock, Reminder, TimedAction
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    deserialize_permissions,
    serialize_permissions,
)


def schedule_timed_action(
    ctx: AppContext, chat_id: int, user_id: int, action: str, delay_seconds: float
) -> None:
    if delay_seconds <= 0:
        return
    run_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    ctx.scheduler.add_job(
        _execute_lift_action,
        trigger="date",
        run_date=run_at,
        args=[chat_id, user_id, action],
        id=f"lift_{action}:{chat_id}:{user_id}",
        replace_existing=True,
    )


async def _execute_lift_action(chat_id: int, user_id: int, action: str) -> None:
    from . import get_ctx

    ctx = get_ctx()
    try:
        if action == "tban":
            await bot.unban_chat_member(chat_id, user_id)
        elif action == "tmute":
            await bot.restrict_chat_member(
                chat_id,
                user_id,
                UNRESTRICTED_PERMISSIONS,
            )
        async with ctx.db() as session:
            stmt = select(TimedAction).where(
                TimedAction.chatId == chat_id,
                TimedAction.userId == user_id,
                TimedAction.action == action,
            )
            result = await session.execute(stmt)
            objs = result.scalars().all()
            for obj in objs:
                await session.delete(obj)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to lift {action}: {e}")


async def execute_reminder(chat_id: int, reminder_id: int) -> None:
    from . import get_ctx

    ctx = get_ctx()
    async with ctx.db() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder or not reminder.isActive:
            return

        try:
            await bot.send_message(chat_id, reminder.text)
        except Exception as e:
            logger.error(f"Failed to send reminder {reminder_id} in {chat_id}: {e}")


async def apply_night_lock(chat_id: int) -> None:
    from . import get_ctx

    ctx = get_ctx()
    async with ctx.db() as session:
        lock = await session.get(NightLock, chat_id)
        if not lock or not lock.isEnabled:
            return

        try:
            chat = await bot.get_chat(chat_id)
            if hasattr(chat, "permissions") and chat.permissions:
                lock.lastPermissions = serialize_permissions(chat.permissions)
                session.add(lock)
                await session.commit()

            await bot.set_chat_permissions(chat_id, RESTRICTED_PERMISSIONS)
            await bot.send_message(
                chat_id, "🌑 **Night Lock Engaged.** The group is now muted until morning."
            )
        except Exception as e:
            logger.error(f"Failed to apply night lock in {chat_id}: {e}")


async def lift_night_lock(chat_id: int) -> None:
    from . import get_ctx

    ctx = get_ctx()
    async with ctx.db() as session:
        lock = await session.get(NightLock, chat_id)
        if not lock or not lock.isEnabled:
            return

        try:
            if lock.lastPermissions:
                perms = deserialize_permissions(lock.lastPermissions)
            else:
                perms = UNRESTRICTED_PERMISSIONS

            await bot.set_chat_permissions(chat_id, perms)
            await bot.send_message(chat_id, "☀️ **Night Lock Lifted.** The group is now open.")
        except Exception as e:
            logger.error(f"Failed to lift night lock in {chat_id}: {e}")


async def run_group_cleaner(chat_id: int) -> None:
    from . import get_ctx

    ctx = get_ctx()
    async with ctx.db() as session:
        cleaner = await session.get(GroupCleaner, chat_id)
        if not cleaner:
            return

        try:
            kicked_deleted = 0
            kicked_fake = 0
            kicked_inactive = 0

            async for member in bot.get_chat_members(chat_id):
                user = member.user
                if user.is_self or user.is_bot:
                    continue

                should_kick = False

                if cleaner.cleanDeleted and user.is_deleted:
                    should_kick = True
                    kicked_deleted += 1
                elif cleaner.cleanFake and (user.is_fake or user.is_scam):
                    should_kick = True
                    kicked_fake += 1
                elif cleaner.cleanInactiveDays > 0:
                    last_seen = user.last_online_date
                    if last_seen:
                        delta = datetime.now(UTC) - last_seen.replace(tzinfo=UTC)
                        if delta.days >= cleaner.cleanInactiveDays:
                            should_kick = True
                            kicked_inactive += 1

                if should_kick:
                    try:
                        await bot.ban_chat_member(
                            chat_id, user.id, until_date=datetime.now(UTC) + timedelta(hours=1)
                        )
                    except Exception as e:
                        logger.debug(f"Failed to kick user {user.id} in {chat_id}: {e}")

            if any([kicked_deleted, kicked_fake, kicked_inactive]):
                summary = f"🧹 **Daily Cleanup Complete!**\n\n- Deleted: {kicked_deleted}\n- Fakes: {kicked_fake}\n- Inactive: {kicked_inactive}"
                await bot.send_message(chat_id, summary)

            cleaner.lastRunDate = datetime.now(UTC)
            session.add(cleaner)
            await session.commit()
        except Exception as e:
            logger.error(f"Group cleaner error in {chat_id}: {e}")
