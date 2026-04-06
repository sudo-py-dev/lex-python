from sqlalchemy import func, select

from src.core.context import AppContext
from src.db.models import Approval


async def add_approval(ctx: AppContext, chat_id: int, user_id: int, granted_by: int) -> Approval:
    """Add a user to the approved list for a chat."""
    async with ctx.db() as session:
        stmt = select(Approval).where(Approval.chatId == chat_id, Approval.userId == user_id)
        result = await session.execute(stmt)
        approval = result.scalars().first()

        if approval:
            approval.grantedBy = granted_by
            session.add(approval)
        else:

            count_stmt = select(func.count()).select_from(Approval).where(Approval.chatId == chat_id)
            count_result = await session.execute(count_stmt)
            count = count_result.scalar() or 0
            if count >= 1000:
                raise ValueError("approval_limit_reached")

            approval = Approval(chatId=chat_id, userId=user_id, grantedBy=granted_by)
            session.add(approval)

        await session.commit()
        await session.refresh(approval)
        return approval


async def remove_approval(ctx: AppContext, chat_id: int, user_id: int) -> bool:
    """Remove a user from the approved list."""
    async with ctx.db() as session:
        stmt = select(Approval).where(Approval.chatId == chat_id, Approval.userId == user_id)
        result = await session.execute(stmt)
        approval = result.scalars().first()
        if approval:
            await session.delete(approval)
            await session.commit()
            return True
        return False


async def is_user_approved(ctx: AppContext, chat_id: int, user_id: int) -> bool:
    """Check if a user is approved in a chat."""
    async with ctx.db() as session:
        stmt = select(Approval).where(Approval.chatId == chat_id, Approval.userId == user_id)
        result = await session.execute(stmt)
        approval = result.scalars().first()
        return approval is not None


async def get_all_approved(ctx: AppContext, chat_id: int) -> list[Approval]:
    """Get all approved users in a chat."""
    async with ctx.db() as session:
        stmt = select(Approval).where(Approval.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def clear_all_approvals(ctx: AppContext, chat_id: int) -> int:
    """Remove all approved users from a chat's list."""
    async with ctx.db() as session:
        stmt = select(Approval).where(Approval.chatId == chat_id)
        result = await session.execute(stmt)
        approvals = result.scalars().all()
        count = len(approvals)
        for approval in approvals:
            await session.delete(approval)
        await session.commit()
        return count
