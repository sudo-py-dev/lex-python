from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, MessageEntityType
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.utils.decorators import safe_handler
from src.utils.i18n import at

from . import get_ctx
from .repository import AIRepository
from .service import AIService


@bot.on_message(filters.group & ~filters.service & ~filters.bot, group=-1)
@safe_handler
async def ai_message_handler(client: Client, message: Message):
    """
    Main handler for AI messages.
    - Logs all messages to chat context.
    - Responds if mentioned or within the 3-minute session window.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Unknown"
    text = message.text or message.caption

    if not client.me:
        logger.warning("AI Handler: client.me is not populated yet!")
        return

    if not text:
        return

    ctx = get_ctx()
    cache = get_cache()

    logger.debug(f"AI [{chat_id}] Handler triggered. User: {user_name} ({user_id})")

    await AIRepository.add_message(ctx, chat_id, message.id, user_id, user_name, text)

    settings = await AIRepository.get_settings(ctx, chat_id)
    if not settings:
        return
    if not settings.isEnabled:
        return
    if not settings.apiKey:
        return

    is_mentioned = False
    if message.entities:
        for entity in message.entities:
            if entity.type in (MessageEntityType.MENTION, MessageEntityType.BOT_COMMAND):
                mention_text = text[entity.offset : entity.offset + entity.length]
                if f"@{client.me.username}".lower() in mention_text.lower():
                    is_mentioned = True

                    break

    if not is_mentioned and f"@{client.me.username}".lower() in text.lower():
        is_mentioned = True

    if (
        not is_mentioned
        and message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == client.me.id
    ):
        is_mentioned = True

    session_key = f"ai_session:{chat_id}"
    is_session_active = await cache.exists(session_key)

    logger.debug(f"AI [{chat_id}] Mentioned: {is_mentioned}, Active: {is_session_active}")

    if not is_mentioned and not is_session_active:
        return

    await cache.set(session_key, True, ttl=180)

    history = await AIRepository.get_context(ctx, chat_id, client.me.id)
    logger.debug(f"AI [{chat_id}] History: {len(history)} messages. Calling LLM...")

    from .prompts import BASE_PROMPT, OPERATIONAL_RULES

    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)

        sys_prompt = settings.systemPrompt if settings.systemPrompt else BASE_PROMPT
        sys_prompt = (
            f"IDENTITY: You are @{client.me.username} ({client.me.first_name})\n\n{sys_prompt}"
        )

        if settings.systemPrompt:
            sys_prompt += OPERATIONAL_RULES

        response_text = await AIService.call_ai(
            provider=settings.provider,
            api_key=settings.apiKey,
            model_id=settings.modelId or "gpt-3.5-turbo",
            system_prompt=sys_prompt,
            custom_instruction=settings.customInstruction,
            messages=history,
        )

        if response_text:
            clean_response = response_text.strip()
            token_match = (
                clean_response.upper()
                .replace("[", "")
                .replace("]", "")
                .replace("IGNORE", "IGNORE")
                .strip()
            )

            logger.debug(
                f"AI [{chat_id}] response: {clean_response[:20]}... (Token: {token_match})"
            )

            if "IGNORE" in token_match and len(token_match) < 10:
                logger.debug(f"AI [{chat_id}] decision: IGNORE")
                return

            if token_match == "CLOSE" or clean_response.upper().startswith("[CLOSE]"):
                await AIRepository.clear_context(ctx, chat_id)
                await cache.delete(session_key)
                await message.reply_text(await at(chat_id, "ai.session_closed"))
                return

            sent_msg = await message.reply_text(response_text)

            await AIRepository.add_message(
                ctx, chat_id, sent_msg.id, client.me.id, client.me.first_name, response_text
            )
    except Exception as e:
        logger.error(f"AI Response failed for chat {chat_id}: {e}")

        if "rate_limit" in str(e).lower():
            error_msg = await at(chat_id, "ai.rate_limit")
        elif "request_too_large" in str(e).lower() or "413" in str(e):
            error_msg = await at(chat_id, "ai.context_too_large")
        else:
            error_msg = await at(chat_id, "ai.error_prefix", error=str(e))

        import contextlib

        with contextlib.suppress(Exception):
            await message.reply_text(error_msg)
