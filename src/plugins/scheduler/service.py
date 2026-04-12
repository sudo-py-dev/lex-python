from datetime import UTC, datetime, timedelta

from loguru import logger
from pyrogram.enums import ChatMemberStatus
from sqlalchemy import select

from src.core.bot import bot
from src.db.models import ChatCleaner, ChatNightLock, Reminder, TimedAction
from src.utils.i18n import at
from src.utils.permissions import (
    RESTRICTED_PERMISSIONS,
    UNRESTRICTED_PERMISSIONS,
    deserialize_permissions,
    serialize_permissions,
)
from src.utils.telegram_storage import send_stored_message


async def _execute_lift_action(chat_id: int, user_id: int, action: str) -> None:
    from src.core.context import get_context

    ctx = get_context()
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
        logger.error("Failed to lift {}: {}", action, e)


async def execute_reminder(chat_id: int, reminder_id: int) -> None:
    from src.core.context import get_context

    ctx = get_context()
    async with ctx.db() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder or not reminder.isActive:
            return

        try:
            await send_stored_message(
                bot,
                chat_id,
                message_type=reminder.messageType,
                text=reminder.text,
                file_id=reminder.fileId,
                additional_data=reminder.additionalData,
            )
        except Exception as e:
            logger.error("Failed to send reminder {} in {}: {}", reminder_id, chat_id, e)


async def apply_night_lock(chat_id: int) -> None:
    from src.core.context import get_context

    ctx = get_context()
    async with ctx.db() as session:
        lock = await session.get(ChatNightLock, chat_id)
        if not lock or not lock.isEnabled:
            return

        try:
            chat = await bot.get_chat(chat_id)
            if hasattr(chat, "permissions") and chat.permissions:
                lock.lastPermissions = serialize_permissions(chat.permissions)
                session.add(lock)
                await session.commit()

            await bot.set_chat_permissions(chat_id, RESTRICTED_PERMISSIONS)
            await bot.send_message(chat_id, await at(chat_id, "scheduler.chatnightlock_engaged"))
        except Exception as e:
            logger.error("Failed to apply night lock in {}: {}", chat_id, e)


async def lift_night_lock(chat_id: int) -> None:
    from src.core.context import get_context

    ctx = get_context()
    async with ctx.db() as session:
        lock = await session.get(ChatNightLock, chat_id)
        if not lock or not lock.isEnabled:
            return

        try:
            if lock.lastPermissions:
                perms = deserialize_permissions(lock.lastPermissions)
            else:
                perms = UNRESTRICTED_PERMISSIONS

            await bot.set_chat_permissions(chat_id, perms)
            await bot.send_message(chat_id, await at(chat_id, "scheduler.chatnightlock_lifted"))
        except Exception as e:
            logger.error("Failed to lift night lock in {}: {}", chat_id, e)


async def run_group_cleaner(chat_id: int) -> None:
    from src.core.context import get_context

    ctx = get_context()
    async with ctx.db() as session:
        cleaner = await session.get(ChatCleaner, chat_id)
        if not cleaner:
            return

        try:
            kicked_deleted = 0
            kicked_fake = 0
            kicked_inactive = 0

            async for member in bot.get_chat_members(chat_id):
                user = member.user
                if (
                    user.is_self
                    or user.is_bot
                    or member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
                ):
                    continue

                if member.joined_date:
                    join_delta = datetime.now(UTC) - member.joined_date.replace(tzinfo=UTC)
                    if join_delta.days < 14:
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
                        logger.debug("Failed to kick user {} in {}: {}", user.id, chat_id, e)

            if any([kicked_deleted, kicked_fake, kicked_inactive]):
                summary = await at(
                    chat_id,
                    "scheduler.cleanup_summary",
                    deleted=kicked_deleted,
                    fakes=kicked_fake,
                    inactive=kicked_inactive,
                )
                await bot.send_message(chat_id, summary)

            cleaner.lastRunDate = datetime.now(UTC)
            session.add(cleaner)
            await session.commit()
        except Exception as e:
            logger.error("Group cleaner error in {}: {}", chat_id, e)


async def invalidate_all_admins_task() -> None:
    """Scheduled task to invalidate admin caches for all active chats."""
    from src.core.context import get_context
    from src.db.models import ChatSettings
    from src.db.repositories.admins import clear_chat_admins
    from src.utils.admin_cache import invalidate_cache

    ctx = get_context()
    async with ctx.db() as session:
        stmt = select(ChatSettings.id).where(ChatSettings.isActive, ChatSettings.id < 0)
        result = await session.execute(stmt)
        chat_ids = result.scalars().all()

    logger.debug(f"Invalidating admin caches for {len(chat_ids)} chats...")
    for chat_id in chat_ids:
        try:
            # 1. Clear local cache (Redis/Memory)
            await invalidate_cache(chat_id)

            # 2. Clear database admin list to force Tier 3 fallback on next check
            await clear_chat_admins(ctx, chat_id)

            # 3. Clear bot privileges in settings
            async with ctx.db() as session:
                settings = await session.get(ChatSettings, chat_id)
                if settings:
                    settings.botPrivileges = None
                    session.add(settings)
                    await session.commit()

        except Exception as e:
            logger.error(f"Failed to invalidate admin cache for chat {chat_id}: {e}")
    logger.debug("Admin cache invalidation complete.")
