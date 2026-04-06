from sqlalchemy import func, select

from src.core.context import AppContext
from src.db.models import AllowedChannel


async def add_allowed_channel(ctx: AppContext, chat_id: int, channel_id: int) -> AllowedChannel:
    """Whitelist a channel in a group chat."""
    async with ctx.db() as session:
        stmt = select(AllowedChannel).where(
            AllowedChannel.chatId == chat_id, AllowedChannel.channelId == channel_id
        )
        result = await session.execute(stmt)
        allowed = result.scalars().first()

        if allowed:
            return allowed

        # Check limit
        count_stmt = select(func.count()).select_from(AllowedChannel).where(AllowedChannel.chatId == chat_id)
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0
        if count >= 50:
            raise ValueError("allowlist_limit_reached")

        allowed = AllowedChannel(chatId=chat_id, channelId=channel_id)
        session.add(allowed)
        await session.commit()
        await session.refresh(allowed)
        return allowed


async def remove_allowed_channel(ctx: AppContext, chat_id: int, channel_id: int) -> bool:
    """Remove a channel from the whitelist."""
    async with ctx.db() as session:
        stmt = select(AllowedChannel).where(
            AllowedChannel.chatId == chat_id, AllowedChannel.channelId == channel_id
        )
        result = await session.execute(stmt)
        allowed = result.scalars().first()
        if allowed:
            await session.delete(allowed)
            await session.commit()
            return True
        return False


async def is_channel_allowed(ctx: AppContext, chat_id: int, channel_id: int) -> bool:
    """Check if a channel is whitelisted in a group chat."""
    async with ctx.db() as session:
        stmt = select(AllowedChannel).where(
            AllowedChannel.chatId == chat_id, AllowedChannel.channelId == channel_id
        )
        result = await session.execute(stmt)
        return result.scalars().first() is not None


async def get_allowed_channels(ctx: AppContext, chat_id: int) -> list[AllowedChannel]:
    """Get all whitelisted channels for a group chat."""
    async with ctx.db() as session:
        stmt = select(AllowedChannel).where(AllowedChannel.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())
