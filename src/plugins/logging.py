from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message, User

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.plugins.admin_panel.repository import get_chat_settings, update_chat_setting
from src.utils.decorators import admin_only, safe_handler
from src.utils.i18n import at


class LoggingPlugin(Plugin):
    """Plugin to send administrative audit logs to a designated channel."""

    name = "logging"
    priority = 90

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.command("setlog") & filters.group)
@safe_handler
@admin_only
async def set_log_handler(client: Client, message: Message) -> None:
    """Designate a channel to receive moderation logs for the current group."""
    if len(message.command) < 2:
        if message.reply_to_message and message.reply_to_message.forward_from_chat:
            channel_id = message.reply_to_message.forward_from_chat.id
        else:
            return
    else:
        try:
            channel_id = int(message.command[1])
        except ValueError:
            return
    ctx = get_context()
    await update_chat_setting(ctx, message.chat.id, "logChannelId", channel_id)
    await message.reply(await at(message.chat.id, "log.set"))


@bot.on_message(filters.command("unsetlog") & filters.group)
@safe_handler
@admin_only
async def unset_log_handler(client: Client, message: Message) -> None:
    """Remove the designated logging channel for the current group."""
    ctx = get_context()
    await update_chat_setting(ctx, message.chat.id, "logChannelId", None)
    await message.reply(await at(message.chat.id, "log.unset"))


async def log_event(
    ctx,
    client: Client,
    chat_id: int,
    action: str,
    target: User,
    actor: User,
    reason: str | None = None,
) -> None:
    """Helper method used by other plugins to push events to the designated log channel."""
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


register(LoggingPlugin())
