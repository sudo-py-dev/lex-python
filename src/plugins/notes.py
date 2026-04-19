from pyrogram import Client, StopPropagation, filters
from pyrogram.errors import Forbidden, RPCError, UserIsBlocked
from pyrogram.types import Message
from sqlalchemy import func, select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import Note
from src.utils.decorators import admin_permission_required, safe_handler
from src.utils.formatters import TelegramFormatter
from src.utils.i18n import at
from src.utils.permissions import Permission


class NotesPlugin(Plugin):
    """Plugin to manage custom notes (aliases) in group chats."""

    name = "notes"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


async def add_note(chat_id: int, name: str, content: str, is_p: bool = False) -> Note:
    ctx = get_context()
    async with ctx.db() as s:
        n = (
            (await s.execute(select(Note).where(Note.chatId == chat_id, Note.name == name)))
            .scalars()
            .first()
        )
        if n:
            n.content, n.isPrivate = content, is_p
        else:
            if (
                await s.execute(
                    select(func.count()).select_from(Note).where(Note.chatId == chat_id)
                )
            ).scalar() >= 1000:
                raise ValueError("limit")
            n = Note(chatId=chat_id, name=name, content=content, isPrivate=is_p)
            s.add(n)
        await s.commit()
        await s.refresh(n)
        return n


async def get_note(chat_id: int, name: str) -> Note | None:
    async with get_context().db() as s:
        return (
            (await s.execute(select(Note).where(Note.chatId == chat_id, Note.name == name)))
            .scalars()
            .first()
        )


async def send_note(c: Client, m: Message, n: Note, override_cid: int = None) -> None:
    cid = override_cid or m.chat.id
    p = TelegramFormatter.parse_message(
        text=n.content,
        user=m.from_user,
        chat_id=cid,
        chat_title=m.chat.title if m.chat else "",
        bot_username=c.me.username,
    )
    try:
        if n.isPrivate:
            await TelegramFormatter.send_parsed(c, m.from_user.id, p)
            if not override_cid:
                await m.reply(await at(cid, "note.sent_dm"))
        else:
            await TelegramFormatter.send_parsed(c, cid, p, reply_to_message_id=m.id)
    except (UserIsBlocked, Forbidden, RPCError):
        if n.isPrivate:
            await m.reply(await at(cid, "common.err_start_private"))


@bot.on_message(filters.command("save") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def save_note_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    name, content = message.command[1].lower(), ""
    if message.reply_to_message:
        content = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 2:
        content = message.text.split(None, 2)[2]
    if not content:
        return
    try:
        await add_note(message.chat.id, name, content)
        await message.reply(await at(message.chat.id, "note.saved", name=name))
    except ValueError:
        await message.reply(await at(message.chat.id, "note.limit_reached"))


@bot.on_message(filters.command(["get", "note"]) & filters.group)
@safe_handler
async def get_note_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    n = await get_note(message.chat.id, message.command[1].lower())
    if not n:
        return await message.reply(
            await at(message.chat.id, "note.not_found", name=message.command[1])
        )
    await send_note(client, message, n)


@bot.on_message(filters.command("notes") & filters.group)
@safe_handler
async def list_notes_handler(client: Client, message: Message) -> None:
    async with get_context().db() as s:
        notes = (
            (await s.execute(select(Note).where(Note.chatId == message.chat.id))).scalars().all()
        )
    if not notes:
        return await message.reply(await at(message.chat.id, "note.list_empty"))
    await message.reply(
        f"{await at(message.chat.id, 'note.list_header')}\n"
        + "\n".join(f"• `{n.name}`" for n in notes)
    )


@bot.on_message(filters.command("clear") & filters.group)
@safe_handler
@admin_permission_required(Permission.CAN_CHANGE_INFO)
async def clear_note_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    async with get_context().db() as s:
        n = (
            (await s.execute(select(Note).where(Note.chatId == message.chat.id, Note.name == name)))
            .scalars()
            .first()
        )
        if n:
            await s.delete(n)
            await s.commit()
    await message.reply(
        await at(message.chat.id, f"note.{'deleted' if n else 'not_found'}", name=name)
    )


@bot.on_message(filters.group & filters.regex(r"^#(\w+)$"), group=20)
@safe_handler
async def hash_note_handler(client: Client, message: Message) -> None:
    n = await get_note(message.chat.id, message.matches[0].group(1).lower())
    if n:
        await send_note(client, message, n)
        if not n.isPrivate:
            raise StopPropagation


@bot.on_message(filters.private & filters.regex(r"^/start note_(-?\d+)_(.+)$"), group=1)
@safe_handler
async def start_note_deeplink_handler(client: Client, message: Message) -> None:
    cid, name = int(message.matches[0].group(1)), message.matches[0].group(2).lower()
    n = await get_note(cid, name)
    if n:
        await send_note(client, message, n, override_cid=cid)


register(NotesPlugin())
