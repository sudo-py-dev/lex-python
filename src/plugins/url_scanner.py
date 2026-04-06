from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender
from src.utils.url_scanner import is_url_malicious


class UrlScannerPlugin(Plugin):
    """Plugin to detect and delete phishing/malicious links."""

    name = "url_scanner"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & (filters.text | filters.caption), group=1)
@safe_handler
async def url_scanner_handler(client: Client, message: Message) -> None:
    """Intersects messages containing links and scans them if enabled."""
    if getattr(message, "command", None):
        return

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)

    if not settings.urlScannerEnabled:
        return

    api_key = settings.gsbKey
    if not api_key:
        logger.warning("URL Scanner: No API key found for chat {}", message.chat.id)
        return
    urls = []
    entities = message.entities or message.caption_entities or []
    text = message.text or message.caption or ""

    for entity in entities:
        if entity.type == MessageEntityType.URL:
            urls.append(text[entity.offset : entity.offset + entity.length])
        elif entity.type == MessageEntityType.TEXT_LINK:
            urls.append(entity.url)

    if not urls:
        return

    lang = settings.language
    threat_text = await is_url_malicious(urls, api_key, lang=lang)

    if threat_text:
        acted = await execute_moderation_action(
            client=client,
            message=message,
            action="delete",
            reason=await at(message.chat.id, "url_scanner.malicious_reason"),
            violation_key="url_scanner.malicious_detected",
            type=threat_text,
        )
        if acted:
            await message.stop_propagation()


register(UrlScannerPlugin())
