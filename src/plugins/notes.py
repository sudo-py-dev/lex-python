import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import Note
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class NotesPlugin(Plugin):
    """Plugin to manage custom notes (aliases) in group chats."""

    name = "notes"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def add_note(chat_id: int, name: str, content: str, is_private: bool = False) -> Note:
    """Add or update a note for a chat."""
    ctx = get_context()
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


async def remove_note(chat_id: int, name: str) -> bool:
    """Remove a note by name."""
    ctx = get_context()
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id, Note.name == name)
        result = await session.execute(stmt)
        note = result.scalars().first()
        if note:
            await session.delete(note)
            await session.commit()
            return True
        return False


async def get_note(chat_id: int, name: str) -> Note | None:
    """Retrieve a specific note by name."""
    ctx = get_context()
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id, Note.name == name)
        result = await session.execute(stmt)
        return result.scalars().first()


async def get_all_notes(chat_id: int) -> list[Note]:
    """Retrieve all notes for a chat."""
    ctx = get_context()
    async with ctx.db() as session:
        stmt = select(Note).where(Note.chatId == chat_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


@bot.on_message(filters.command("save") & filters.group)
@safe_handler
@admin_only
async def save_note_handler(client: Client, message: Message) -> None:
    """Save a new note or update an existing one."""
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    content = ""
    if message.reply_to_message:
        content = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 2:
        content = message.text.split(None, 2)[2]

    if not content:
        return

    await add_note(message.chat.id, name, content)
    await message.reply(await at(message.chat.id, "note.saved", name=name))


@bot.on_message(filters.command(["get", "note"]) & filters.group)
@safe_handler
async def get_note_handler(client: Client, message: Message) -> None:
    """Retrieve and send a specific note."""
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    note = await get_note(message.chat.id, name)
    if not note:
        await message.reply(await at(message.chat.id, "note.not_found", name=name))
        return

    if note.isPrivate:
        try:
            await client.send_message(message.from_user.id, note.content)
            await message.reply(await at(message.chat.id, "note.sent_dm"))
        except Exception:
            await message.reply(await at(message.chat.id, "note.start_private"))
    else:
        await message.reply(note.content)


@bot.on_message(filters.command("notes") & filters.group)
@safe_handler
async def list_notes_handler(client: Client, message: Message) -> None:
    """List all notes available in the current group."""
    notes = await get_all_notes(message.chat.id)
    if not notes:
        await message.reply(await at(message.chat.id, "note.list_empty"))
        return

    text = await at(message.chat.id, "note.list_header")
    for n in notes:
        text += f"\n• `{n.name}`"
    await message.reply(text)


@bot.on_message(filters.command("clear") & filters.group)
@safe_handler
@admin_only
async def clear_note_handler(client: Client, message: Message) -> None:
    """Delete a specific note."""
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    success = await remove_note(message.chat.id, name)
    if success:
        await message.reply(await at(message.chat.id, "note.deleted", name=name))
    else:
        await message.reply(await at(message.chat.id, "note.not_found", name=name))


@bot.on_message(filters.group & filters.regex(r"^#(\w+)$"), group=2)
@safe_handler
async def hash_note_handler(client: Client, message: Message) -> None:
    """Trigger notes via hashtag (#note_name)."""
    name = message.matches[0].group(1).lower()
    note = await get_note(message.chat.id, name)
    if not note:
        return

    if note.isPrivate:
        with contextlib.suppress(Exception):
            await client.send_message(message.from_user.id, note.content)
    else:
        await message.reply(note.content)


register(NotesPlugin())
