from loguru import logger
from pyrogram import Client
from pyrogram.types import User

from src.core.context import AppContext
from src.plugins.admin_panel.repository import get_chat_settings
from src.utils.i18n import at


async def log_event(
    ctx: AppContext,
    client: Client,
    chat_id: int,
    action: str,
    target: User,
    actor: User,
    reason: str | None = None,
) -> None:
    settings = await get_chat_settings(ctx, chat_id)
    if not settings.logChannelId:
        return

    chat = await client.get_chat(chat_id)
    text = await at(
        chat_id,
        "log.action",
        action=action.upper(),
        chat=chat.title,
        target=target.mention,
        actor=actor.mention,
        reason=f"\n📝 Reason: {reason}" if reason else "",
    )

    try:
        await client.send_message(settings.logChannelId, text)
    except Exception as e:
        logger.warning(f"Failed to send log to channel {settings.logChannelId}: {e}")
