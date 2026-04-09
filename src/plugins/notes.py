import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import func, select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import Note
from src.utils.decorators import admin_only, safe_handler
from src.utils.formatters import TelegramFormatter
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
            count_stmt = select(func.count()).select_from(Note).where(Note.chatId == chat_id)
            count_result = await session.execute(count_stmt)
            count = count_result.scalar()
            if count >= 1000:
                raise ValueError("note_limit_reached")

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

    try:
        await add_note(message.chat.id, name, content)
        await message.reply(await at(message.chat.id, "note.saved", name=name))
    except ValueError as e:
        if str(e) == "note_limit_reached":
            await message.reply(await at(message.chat.id, "note.limit_reached"))
        else:
            raise e


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
            parsed = TelegramFormatter.parse_message(
                text=note.content,
                user=message.from_user,
                chat_id=message.chat.id,
                chat_title=message.chat.title,
                bot_username=client.me.username,
            )
            await TelegramFormatter.send_parsed(client, message.from_user.id, parsed)
            await message.reply(await at(message.chat.id, "note.sent_dm"))
        except Exception:
            await message.reply(await at(message.chat.id, "common.err_start_private"))
    else:
        parsed = TelegramFormatter.parse_message(
            text=note.content,
            user=message.from_user,
            chat_id=message.chat.id,
            chat_title=message.chat.title,
            bot_username=client.me.username,
        )
        await TelegramFormatter.send_parsed(
            client, message.chat.id, parsed, reply_to_message_id=message.id
        )


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


@bot.on_message(filters.group & filters.regex(r"^#(\w+)$"), group=20)
@safe_handler
async def hash_note_handler(client: Client, message: Message) -> None:
    """Trigger notes via hashtag (#note_name)."""
    name = message.matches[0].group(1).lower()
    note = await get_note(message.chat.id, name)
    if not note:
        return

    if note.isPrivate:
        with contextlib.suppress(Exception):
            parsed = TelegramFormatter.parse_message(
                text=note.content,
                user=message.from_user,
                chat_id=message.chat.id,
                chat_title=message.chat.title,
                bot_username=client.me.username,
            )
            await TelegramFormatter.send_parsed(client, message.from_user.id, parsed)
    else:
        parsed = TelegramFormatter.parse_message(
            text=note.content,
            user=message.from_user,
            chat_id=message.chat.id,
            chat_title=message.chat.title,
            bot_username=client.me.username,
        )
        await TelegramFormatter.send_parsed(
            client, message.chat.id, parsed, reply_to_message_id=message.id
        )
        await message.stop_propagation()


@bot.on_message(filters.private & filters.regex(r"^/start note_(-?\d+)_(.+)$"), group=1)
@safe_handler
async def start_note_deeplink_handler(client: Client, message: Message) -> None:
    """Intercept deep-links pointing to notes from inline buttons."""
    chat_id = int(message.matches[0].group(1))
    note_name = message.matches[0].group(2).lower()
    note = await get_note(chat_id, note_name)
    if not note:
        return
    parsed = TelegramFormatter.parse_message(
        text=note.content,
        user=message.from_user,
        chat_id=chat_id,
        bot_username=client.me.username,
    )
    await TelegramFormatter.send_parsed(client, message.from_user.id, parsed)


register(NotesPlugin())
