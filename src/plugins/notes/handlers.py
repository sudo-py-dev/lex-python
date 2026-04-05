import contextlib

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import add_note, get_all_notes, get_note, remove_note


@bot.on_message(filters.command("save") & filters.group)
@safe_handler
@admin_only
async def save_note_handler(client: Client, message: Message) -> None:
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

    await add_note(get_ctx(), message.chat.id, name, content)
    await message.reply(await at(message.chat.id, "note.saved", name=name))


@bot.on_message(filters.command(["get", "note"]) & filters.group)
@safe_handler
async def get_note_handler(client: Client, message: Message) -> None:
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    note = await get_note(get_ctx(), message.chat.id, name)
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
    notes = await get_all_notes(get_ctx(), message.chat.id)
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
    if len(message.command) < 2:
        return
    name = message.command[1].lower()
    success = await remove_note(get_ctx(), message.chat.id, name)
    if success:
        await message.reply(await at(message.chat.id, "note.deleted", name=name))
    else:
        await message.reply(await at(message.chat.id, "note.not_found", name=name))


@bot.on_message(filters.group & filters.regex(r"^#(\w+)$"), group=2)
@safe_handler
async def hash_note_handler(client: Client, message: Message) -> None:

    name = message.matches[0].group(1).lower()
    note = await get_note(get_ctx(), message.chat.id, name)
    if not note:
        return

    if note.isPrivate:
        with contextlib.suppress(Exception):
            await client.send_message(message.from_user.id, note.content)
    else:
        await message.reply(note.content)
