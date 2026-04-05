from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import GlobalBan, SudoUser


async def add_gban(ctx: AppContext, user_id: int, reason: str, banned_by: int) -> GlobalBan:
    async with ctx.db() as session:
        stmt = select(GlobalBan).where(GlobalBan.userId == user_id)
        result = await session.execute(stmt)
        gban = result.scalars().first()

        if gban:
            gban.reason = reason
            gban.bannedBy = banned_by
            session.add(gban)
        else:
            gban = GlobalBan(userId=user_id, reason=reason, bannedBy=banned_by)
            session.add(gban)

        await session.commit()
        await session.refresh(gban)
        return gban


async def remove_gban(ctx: AppContext, user_id: int) -> bool:
    async with ctx.db() as session:
        stmt = select(GlobalBan).where(GlobalBan.userId == user_id)
        result = await session.execute(stmt)
        gban = result.scalars().first()
        if gban:
            await session.delete(gban)
            await session.commit()
            return True
        return False


async def is_gbanned(ctx: AppContext, user_id: int) -> bool:
    async with ctx.db() as session:
        stmt = select(GlobalBan).where(GlobalBan.userId == user_id)
        result = await session.execute(stmt)
        gban = result.scalars().first()
        return gban is not None


async def get_all_gbans(ctx: AppContext) -> list[GlobalBan]:
    async with ctx.db() as session:
        stmt = select(GlobalBan)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def add_sudo(ctx: AppContext, user_id: int, added_by: int) -> SudoUser:
    async with ctx.db() as session:
        user = await session.get(SudoUser, user_id)
        if user:
            return user
        user = SudoUser(userId=user_id, addedBy=added_by)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def is_sudo(ctx: AppContext, user_id: int) -> bool:
    async with ctx.db() as session:
        user = await session.get(SudoUser, user_id)
        return user is not None
