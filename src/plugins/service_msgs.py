import contextlib
import json

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.admin_panel import get_chat_settings
from src.utils.decorators import safe_handler


class ServiceMsgsPlugin(Plugin):
    """Plugin to clean up service messages (join/leave/pinned) in groups."""

    name = "service_msgs"
    priority = 100

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.service & filters.group, group=4)
@safe_handler
async def service_msg_handler(client: Client, message: Message) -> None:
    """Intercept service messages and delete them based on group settings."""
    ctx = get_context()
    settings = await get_chat_settings(ctx, message.chat.id)

    should_delete = False

    # Check for general service cleaning settings
    if settings.cleanAllServices:
        should_delete = True
    elif settings.cleanServiceTypes:
        try:
            types = json.loads(settings.cleanServiceTypes)
            if message.service and message.service.name in types:
                should_delete = True
        except (json.JSONDecodeError, TypeError):
            pass

    # Check for specific event cleaning settings
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
