import contextlib
import json

from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import AppContext, get_context
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.decorators import safe_handler


def get_ctx() -> AppContext:
    return get_context()


@bot.on_message(filters.service & filters.group, group=4)
@safe_handler
async def service_msg_handler(client: Client, message: Message) -> None:
    ctx = get_ctx()
    settings = await get_chat_settings(ctx, message.chat.id)

    should_delete = False

    if (
        settings.cleanAllServices
        or message.service
        and message.service.name
        in (json.loads(settings.cleanServiceTypes) if settings.cleanServiceTypes else [])
        or (
            message.new_chat_members
            and settings.cleanJoin
            or message.left_chat_member
            and settings.cleanLeave
            or message.pinned_message
            and settings.cleanPinned
        )
    ):
        should_delete = True

    if should_delete:
        with contextlib.suppress(Exception):
            await message.delete()
