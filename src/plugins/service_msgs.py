import contextlib
import json

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.admin_panel import get_chat_settings, update_chat_title
from src.utils.decorators import safe_handler


class ServiceMsgsPlugin(Plugin):
    """Plugin to handle group service actions like renames, joins, and cleaning."""

    name = "service_msgs"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.service & filters.group, group=4)
@safe_handler
async def service_msg_handler(client: Client, message: Message) -> None:
    """Consolidated handler to synchronize chat info and clean service messages."""
    ctx = get_context()

    if message.new_chat_title:
        await update_chat_title(ctx, message.chat.id, message.new_chat_title)

    if message.new_chat_members:
        await update_chat_title(ctx, message.chat.id, message.chat.title)

    settings = await get_chat_settings(ctx, message.chat.id)
    should_delete = False

    if settings.cleanAllServices:
        should_delete = True
    elif settings.cleanServiceTypes:
        try:
            service_map = {
                "new_chat_members": "NEW_CHAT_MEMBERS",
                "left_chat_member": "LEFT_CHAT_MEMBER",
                "new_chat_title": "NEW_CHAT_TITLE",
                "pinned_message": "PINNED_MESSAGE",
                "new_chat_photo": "NEW_CHAT_PHOTO",
                "delete_chat_photo": "DELETE_CHAT_PHOTO",
                "group_chat_created": "GROUP_CHAT_CREATED",
                "supergroup_chat_created": "SUPERGROUP_CHAT_CREATED",
                "channel_chat_created": "CHANNEL_CHAT_CREATED",
                "migrate_to_chat_id": "MIGRATE_TO_CHAT_ID",
                "migrate_from_chat_id": "MIGRATE_FROM_CHAT_ID",
            }

            types = json.loads(settings.cleanServiceTypes)
            for attr, label in service_map.items():
                if getattr(message, attr, None) and label in types:
                    should_delete = True
                    break
        except (json.JSONDecodeError, TypeError):
            pass

    if not should_delete and (
        (message.new_chat_members and settings.cleanJoin)
        or (message.left_chat_member and settings.cleanLeave)
        or (message.pinned_message and settings.cleanPinned)
    ):
        should_delete = True

    if should_delete:
        with contextlib.suppress(Exception):
            await message.delete()


register(ServiceMsgsPlugin())
