from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import StickerBlock


async def add_blocked_sticker_set(ctx: AppContext, chat_id: int, set_name: str) -> bool:
    """Add a sticker set to the block list. Returns False if already exists."""
    async with ctx.db() as session:
        stmt = select(StickerBlock).where(
            StickerBlock.chatId == chat_id, StickerBlock.setName == set_name
        )
        result = await session.execute(stmt)
        if result.scalars().first():
            return False  # Already blocked

        session.add(StickerBlock(chatId=chat_id, setName=set_name))
        await session.commit()
        return True


async def remove_blocked_sticker_set(ctx: AppContext, chat_id: int, set_name: str) -> bool:
    """Remove a sticker set from the block list. Returns True if removed."""
    async with ctx.db() as session:
        stmt = select(StickerBlock).where(
            StickerBlock.chatId == chat_id, StickerBlock.setName == set_name
        )
        result = await session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            await session.delete(obj)
            await session.commit()
            return True
        return False


async def is_sticker_set_blocked(ctx: AppContext, chat_id: int, set_name: str) -> bool:
    """Check if a sticker set is in the block list for this chat."""
    async with ctx.db() as session:
        stmt = select(StickerBlock).where(
            StickerBlock.chatId == chat_id, StickerBlock.setName == set_name
        )
        result = await session.execute(stmt)
        return result.scalars().first() is not None


async def get_blocked_sticker_sets(ctx: AppContext, chat_id: int) -> list[StickerBlock]:
    """Get all blocked sticker sets for a chat."""
    async with ctx.db() as session:
        stmt = select(StickerBlock).where(StickerBlock.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())
