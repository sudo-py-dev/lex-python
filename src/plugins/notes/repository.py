from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import Note


async def add_note(
    ctx: AppContext, chat_id: int, name: str, content: str, is_private: bool = False
) -> Note:
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id, Note.name == name)
        result = await session.execute(stmt)
        note = result.scalars().first()

        if note:
            note.content = content
            note.isPrivate = is_private
            session.add(note)
        else:
            note = Note(chatId=chat_id, name=name, content=content, isPrivate=is_private)
            session.add(note)

        await session.commit()
        await session.refresh(note)
        return note


async def remove_note(ctx: AppContext, chat_id: int, name: str) -> bool:
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id, Note.name == name)
        result = await session.execute(stmt)
        note = result.scalars().first()
        if note:
            await session.delete(note)
            await session.commit()
            return True
        return False


async def clear_all_notes(ctx: AppContext, chat_id: int) -> int:
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id)
        result = await session.execute(stmt)
        notes = result.scalars().all()
        count = len(notes)
        for note in notes:
            await session.delete(note)
        await session.commit()
        return count


async def get_note(ctx: AppContext, chat_id: int, name: str) -> Note | None:
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id, Note.name == name)
        result = await session.execute(stmt)
        return result.scalars().first()


async def get_all_notes(ctx: AppContext, chat_id: int) -> list[Note]:
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())
