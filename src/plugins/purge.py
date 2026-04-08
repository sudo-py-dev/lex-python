import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.plugin import Plugin, register
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input


class PurgePlugin(Plugin):
    """Plugin to delete large amounts of messages (purge) in a chat."""

    name = "purge"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("purge") & filters.group)
@safe_handler
@admin_only
async def purge_handler(client: Client, message: Message) -> None:
    """Purge messages between the replied message and the /purge command."""
    if not message.reply_to_message:
        await message.reply(await at(message.chat.id, "purge.usage"))
        return

    message_ids = []
    start_id = message.reply_to_message.id
    end_id = message.id

    for msg_id in range(start_id, end_id + 1):
        message_ids.append(msg_id)
        if len(message_ids) >= 100:
            await client.delete_messages(message.chat.id, message_ids)
            message_ids = []
            await asyncio.sleep(0.5)

    if message_ids:
        await client.delete_messages(message.chat.id, message_ids)

    status = await message.reply(
        await at(message.chat.id, "purge.done", count=end_id - start_id + 1)
    )
    await asyncio.sleep(3)
    await status.delete()


@bot.on_message(filters.command("del") & filters.group)
@safe_handler
@admin_only
async def del_handler(client: Client, message: Message) -> None:
    """Delete a single message that is replied to."""
    if not message.reply_to_message:
        return
    await asyncio.gather(message.delete(), message.reply_to_message.delete())


@bot.on_message(filters.command("purgeme") & filters.group)
@safe_handler
async def purgeme_handler(client: Client, message: Message) -> None:
    """Purge the last N messages sent by the user themselves."""
    if len(message.command) < 2:
        return
    try:
        n = int(message.command[1])
    except ValueError:
        return

    if n > 100:
        n = 100

    message_ids = []
    async for msg in client.get_chat_history(message.chat.id, limit=n + 10):
        if msg.from_user and msg.from_user.id == message.from_user.id:
            message_ids.append(msg.id)
            if len(message_ids) >= n:
                break

    if message_ids:
        await client.delete_messages(message.chat.id, message_ids)


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("purgeMessagesCount"), group=-100)
@safe_handler
async def purge_messages_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    value = message.text

    if not str(value).isdigit() or int(value) < 1:
        await message.reply(await at(user_id, "panel.input_invalid_number"))
        return

    count = int(value)

    # Start background purge task
    async def do_purge():
        try:
            dummy = await client.send_message(chat_id, await at(chat_id, "panel.purge_in_progress"))
            top_id = dummy.id
            await asyncio.sleep(2)
            await dummy.delete()

            for i in range(top_id, top_id - count - 1, -100):
                batch_ids = list(range(i, max(i - 100, top_id - count - 1), -1))
                with __import__("contextlib").suppress(Exception):
                    await client.delete_messages(chat_id, batch_ids)
                await asyncio.sleep(0.5)
        except Exception:
            pass

    asyncio.create_task(do_purge())

    from src.plugins.admin_panel.handlers.keyboards import moderation_category_kb

    kb = await moderation_category_kb(chat_id, user_id=user_id)

    text = await at(user_id, "panel.moderation_text")

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(PurgePlugin())
