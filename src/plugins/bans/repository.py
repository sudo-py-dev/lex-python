from datetime import datetime

from src.core.context import AppContext
from src.db.models import ActionLog, TimedAction


async def log_action(
    ctx: AppContext,
    chat_id: int,
    actor_id: int,
    target_id: int,
    action: str,
    reason: str | None = None,
    duration: int | None = None,
    msg_link: str | None = None,
) -> None:
    async with ctx.db() as session:
        log = ActionLog(
            chatId=chat_id,
            actorId=actor_id,
            targetId=target_id,
            action=action,
            reason=reason,
            duration=duration,
            msgLink=msg_link,
        )
        session.add(log)
        await session.commit()


async def create_timed_action(
    ctx: AppContext, chat_id: int, user_id: int, action: str, expires_at: datetime
) -> None:
    async with ctx.db() as session:
        obj = TimedAction(chatId=chat_id, userId=user_id, action=action, expiresAt=expires_at)
        session.add(obj)
        await session.commit()
