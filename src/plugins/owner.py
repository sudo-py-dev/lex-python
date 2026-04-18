
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message
import asyncio

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.config import config
from src.utils.decorators import safe_handler
from src.plugins.admin_sync import ensure_chat_identity

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
        async for dialog in client.get_dialogs():
            if dialog.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                try:
                    # ensure_chat_identity handles identity and linked channel
                    await ensure_chat_identity(ctx, dialog.chat)
                    synced += 1
                    
                    if synced % 5 == 0:
                        await status_msg.edit_text(f"⏳ Syncing... {synced} chats processed.")
                    
                    # Small delay to avoid FloodWait during intensive DB/API operations
                    await asyncio.sleep(0.05)
                except Exception:
                    errors += 1
                    continue
                    
        await status_msg.edit_text(
            f"✅ **Sync complete!**\n\n"
            f"• Total Synced: `{synced}`\n"
            f"• Errors: `{errors}`\n"
            f"\nLinked channels are now tracked for all active groups."
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ **Sync failed:** `{e}`")

register(OwnerPlugin())
