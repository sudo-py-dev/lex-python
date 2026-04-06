from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.group_settings import get_settings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.url_scanner import is_url_malicious


class UrlScannerPlugin(Plugin):
    """Plugin to detect and delete phishing/malicious links."""

    name = "url_scanner"
    priority = 50  # Run before most content filters

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & (filters.text | filters.caption), group=1)
@safe_handler
async def url_scanner_handler(client: Client, message: Message) -> None:
    """Intersects messages containing links and scans them if enabled."""
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return

    ctx = get_context()
    settings = await get_settings(ctx, message.chat.id)

    if not settings.urlScannerEnabled:
        return

    # Use group-specific API key
    api_key = settings.gsbKey
    if not api_key:
        return

    # Extract URLs from entities
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

    # Scan URLs
    lang = settings.language
    threat_text = await is_url_malicious(urls, api_key, lang=lang)

    if threat_text:
        # Delete malicious message
        try:
            await message.delete()
            # Send warning
            warn_msg = await at(
                message.chat.id,
                "url_scanner.malicious_detected",
                user=message.from_user.mention,
                threat=threat_text,
            )
            await client.send_message(message.chat.id, warn_msg)
        except Exception:
            pass


register(UrlScannerPlugin())
