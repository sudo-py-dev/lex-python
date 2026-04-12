import json
from datetime import UTC, datetime

from sqlalchemy import delete, select

from src.core.context import AppContext
from src.db.models.chats import ChatAdmin


async def upsert_admin(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    status: str,
    first_name: str,
    username: str | None = None,
    privileges: dict[str, bool] | None = None,
) -> None:
    """Add or update an admin in the database."""
    async with ctx.db() as session:
        admin = await session.get(ChatAdmin, (chat_id, user_id))
        if not admin:
            admin = ChatAdmin(
                chatId=chat_id,
                userId=user_id,
                status=status,
                firstName=first_name,
                username=username,
                privileges=json.dumps(privileges) if privileges else None,
            )
            session.add(admin)
        else:
            admin.status = status
            admin.firstName = first_name
            admin.username = username
            admin.privileges = json.dumps(privileges) if privileges else None
            admin.updatedAt = datetime.now(UTC)
            session.add(admin)
        await session.commit()


async def remove_admin(ctx: AppContext, chat_id: int, user_id: int) -> None:
    """Remove an admin from the database."""
    async with ctx.db() as session:
        admin = await session.get(ChatAdmin, (chat_id, user_id))
        if admin:
            await session.delete(admin)
            await session.commit()


async def get_admins_for_chat(ctx: AppContext, chat_id: int) -> list[ChatAdmin]:
    """Retrieve all cached admins for a specific chat."""
    async with ctx.db() as session:
        stmt = select(ChatAdmin).where(ChatAdmin.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_admin_from_db(ctx: AppContext, chat_id: int, user_id: int) -> ChatAdmin | None:
    """Retrieve a specific admin from the database."""
    async with ctx.db() as session:
        return await session.get(ChatAdmin, (chat_id, user_id))


async def clear_chat_admins(ctx: AppContext, chat_id: int) -> None:
    """Remove all cached admins for a chat (used before a full refresh)."""
    async with ctx.db() as session:
        stmt = delete(ChatAdmin).where(ChatAdmin.chatId == chat_id)
        await session.execute(stmt)
        await session.commit()
