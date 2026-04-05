from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, MessageEntityType
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.utils.decorators import safe_handler

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

    if not is_mentioned and not is_session_active:

        return

    await cache.set(session_key, True, ttl=180)

    history = await AIRepository.get_context(ctx, chat_id)

    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)

        response_text = await AIService.call_ai(
            provider=settings.provider,
            api_key=settings.apiKey,
            model_id=settings.modelId or "gpt-3.5-turbo",
            system_prompt=settings.systemPrompt,
            custom_instruction=settings.customInstruction,
            messages=history,
        )

        if response_text:
            sent_msg = await message.reply_text(response_text)

            await AIRepository.add_message(
                ctx, chat_id, sent_msg.id, client.me.id, client.me.first_name, response_text
            )
    except Exception as e:
        logger.error(f"AI Response failed for chat {chat_id}: {e}")
        error_msg = f"❌ **AI Error**: {str(e)}"
        if "rate_limit" in str(e).lower():
            error_msg = "🐢 **Rate Limit Reached**: Please wait a few seconds before trying again."
        elif "request_too_large" in str(e).lower() or "413" in str(e):
            error_msg = "📦 **Context Too Large**: The conversation history is too big for this model. Try /clear_context."

        import contextlib

        with contextlib.suppress(Exception):
            await message.reply_text(error_msg)
