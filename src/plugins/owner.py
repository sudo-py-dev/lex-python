import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from src.config import config
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_all_active_chats
from src.plugins.admin_sync import ensure_chat_identity
from src.utils.decorators import safe_handler


class OwnerPlugin(Plugin):
    """Plugin for bot owner maintenance and debug commands."""

    name = "owner"
    priority = 10

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("syncalllinks") & filters.private & filters.user(config.OWNER_ID))
@safe_handler
async def sync_all_links_handler(client: Client, message: Message):
    ctx = get_context()
    status_msg = await message.reply("📡 Starting bulk sync of linked channels...")

    synced = 0
    errors = 0

    try:
        active_chats = await get_all_active_chats(ctx)
        total_to_sync = len(active_chats)

        for s in active_chats:
            try:
                chat = await client.get_chat(s.id)
                if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                    await ensure_chat_identity(ctx, chat)
                    synced += 1

                if synced % 5 == 0:
                    await status_msg.edit_text(
                        f"⏳ Syncing... {synced}/{total_to_sync} chats processed."
                    )

                await asyncio.sleep(0.1)
            except Exception:
                errors += 1
                continue

        await status_msg.edit_text(
            f"✅ **Sync complete!**\n\n"
            f"• Total Processed: `{total_to_sync}`\n"
            f"• Successfully Synced: `{synced}`\n"
            f"• Errors/Skipped: `{errors}`\n"
            f"\nLinked channels are now tracked for all active groups."
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ **Sync failed:** `{e}`")


register(OwnerPlugin())
