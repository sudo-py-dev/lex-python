from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import UserConnection


async def set_active_chat(ctx: AppContext, user_id: int, chat_id: int | None) -> UserConnection:
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()

        if conn:
            conn.activeChatId = chat_id
            session.add(conn)
        else:
            conn = UserConnection(userId=user_id, activeChatId=chat_id)
            session.add(conn)

        await session.commit()
        await session.refresh(conn)
        return conn


async def get_active_chat(ctx: AppContext, user_id: int) -> int | None:
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        return int(conn.activeChatId) if conn and conn.activeChatId else None


async def clear_connection(ctx: AppContext, user_id: int) -> bool:
    async with ctx.db() as session:
        stmt = select(UserConnection).where(UserConnection.userId == user_id)
        result = await session.execute(stmt)
        conn = result.scalars().first()
        if conn:
            await session.delete(conn)
            await session.commit()
            return True
        return False
