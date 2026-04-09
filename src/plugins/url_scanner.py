from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.chats import get_chat_settings as get_settings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.moderation import execute_moderation_action, resolve_sender
from src.utils.url_scanner import is_url_malicious


class UrlScannerPlugin(Plugin):
    """Plugin to detect and delete phishing/malicious links."""

    name = "url_scanner"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & (filters.text | filters.caption), group=-40)
@safe_handler
async def url_scanner_handler(client: Client, message: Message) -> None:
    """
    Monitor incoming messages for malicious URLs (phishing, malware).

    Scans both text and caption entities for URLs. If the Google Safe Browsing
    scan is enabled and an API key is available, it checks the links.
    If a threat is detected, it executes the configured moderation action.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object to inspect.

    Side Effects:
        - Scans URLs using an external API (GSB).
        - Deletes the message if a threat is found.
        - May mute, kick, or ban the sender based on settings.
        - Logs the detection in the audit log channel.
        - Stops message propagation on violation.
    """
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
        logger.debug("URL Scanner: No API key found for chat {}", message.chat.id)
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
            action=settings.urlScannerAction,
            reason=await at(message.chat.id, "url_scanner.malicious_reason"),
            violation_key="url_scanner.malicious_detected",
            type=threat_text,
        )
        if acted:
            await message.stop_propagation()


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("gsbKey"), group=-50)
@safe_handler
async def url_scanner_settings_input_handler(client: Client, message: Message) -> None:
    logger.debug(f"Input Handler: url_scanner received message from {message.from_user.id}")
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text or ""
    str_value = str(value).strip()

    from src.plugins.admin_panel.repository import update_chat_setting

    if str_value.lower() == "reset":
        await update_chat_setting(ctx, chat_id, "gsbKey", None)
        await update_chat_setting(ctx, chat_id, "urlScannerEnabled", False)
        str_value = None
    elif not str_value:
        await message.reply(await at(user_id, "panel.input_invalid_string"))
        return
    else:
        logger.debug(f"Input Handler: Updating gsbKey for chat {chat_id}")
        await update_chat_setting(ctx, chat_id, "gsbKey", str_value)
        logger.debug(f"Input Handler: Database update complete for chat {chat_id}")

    from src.plugins.admin_panel.handlers.security_kbs import url_scanner_kb

    kb = await url_scanner_kb(ctx, chat_id, user_id=user_id)

    s = await get_settings(ctx, chat_id)
    status = await at(
        user_id, "panel.status_enabled" if s.urlScannerEnabled else "panel.status_disabled"
    )
    text = await at(
        user_id,
        "panel.urlscanner_text",
        status=status,
        key="********" if s.gsbKey else await at(user_id, "panel.not_set"),
    )

    logger.debug(f"Input Handler: Progress - Preparing to finalize for user {user_id}")
    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )
    logger.debug(f"Input Handler: Finalized for user {user_id}")


register(UrlScannerPlugin())
