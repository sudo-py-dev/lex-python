from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, MessageEntityType, ParseMode
from pyrogram.types import Message

from src.cache.local_cache import get_cache
from src.core.bot import bot
from src.core.context import get_context
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input

from .repository import AIRepository
from .service import AIService
from .telegram_markdown import render_pyrogram_html


def _compact_history(
    messages: list[dict[str, str]],
    *,
    max_messages: int,
    max_chars: int,
) -> list[dict[str, str]]:
    if not messages:
        return []

    clipped = messages[-max_messages:]
    out: list[dict[str, str]] = []
    total = 0
    for m in reversed(clipped):
        content = str(m.get("content", ""))
        role = str(m.get("role", "user"))
        if not content:
            continue
        if total + len(content) > max_chars:
            remaining = max_chars - total
            if remaining <= 80:
                break
            content = content[-remaining:]
        out.append({"role": role, "content": content})
        total += len(content)
        if total >= max_chars:
            break
    return list(reversed(out))


def _is_request_too_large_error(err: Exception) -> bool:
    e = str(err).lower()
    return "request_too_large" in e or "413" in e or "request entity too large" in e


def _trim_text(value: str | None, max_chars: int) -> str | None:
    if not value:
        return value
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


@bot.on_message(filters.group & ~filters.service & ~filters.bot, group=100)
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

    if not text or text.startswith("/"):
        return

    ctx = get_context()
    cache = get_cache()

    logger.debug(f"AI [{chat_id}] Handler triggered. User: {user_name} ({user_id})")

    await AIRepository.add_message(ctx, chat_id, message.id, user_id, user_name, text)

    settings = await AIRepository.get_settings(ctx, chat_id)
    if not settings:
        return
    if not settings.isAssistantEnabled:
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

    provider = (settings.provider or "").lower()
    initial_max_messages = 16 if provider == "groq" else 24
    initial_max_chars = 7000 if provider == "groq" else 12000
    retry_max_messages = 6 if provider == "groq" else 8
    retry_max_chars = 2200 if provider == "groq" else 3000

    history = await AIRepository.get_context(ctx, chat_id, client.me.id)
    history = _compact_history(
        history, max_messages=initial_max_messages, max_chars=initial_max_chars
    )
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

        sys_prompt = _trim_text(sys_prompt, 3200) or ""
        custom_instruction = _trim_text(settings.customInstruction, 900)

        try:
            response_text = await AIService.call_ai(
                provider=settings.provider,
                api_key=settings.apiKey,
                model_id=settings.modelId or "gpt-3.5-turbo",
                system_prompt=sys_prompt,
                custom_instruction=custom_instruction,
                messages=history,
            )
        except Exception as first_error:
            if not _is_request_too_large_error(first_error):
                raise
            logger.warning(f"AI [{chat_id}] context too large, retrying with compact history")
            retry_history = _compact_history(
                history, max_messages=retry_max_messages, max_chars=retry_max_chars
            )
            response_text = await AIService.call_ai(
                provider=settings.provider,
                api_key=settings.apiKey,
                model_id=settings.modelId or "gpt-3.5-turbo",
                system_prompt=_trim_text(sys_prompt, 1800),
                custom_instruction=_trim_text(custom_instruction, 500),
                messages=retry_history,
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

            render_text = render_pyrogram_html(clean_response)
            try:
                sent_msg = await message.reply_text(render_text, parse_mode=ParseMode.HTML)
            except Exception as format_error:
                logger.warning(
                    f"AI [{chat_id}] html render failed, fallback to plain text: {format_error}"
                )
                sent_msg = await message.reply_text(clean_response, parse_mode=None)

            await AIRepository.add_message(
                ctx, chat_id, sent_msg.id, client.me.id, client.me.first_name, clean_response
            )
    except Exception as e:
        logger.error(f"AI Response failed for chat {chat_id}: {e}")

        if "rate_limit" in str(e).lower():
            error_msg = await at(chat_id, "ai.rate_limit")
        elif _is_request_too_large_error(e):
            await AIRepository.clear_context(ctx, chat_id)
            await cache.delete(session_key)
            error_msg = await at(chat_id, "ai.context_too_large")
        else:
            error_msg = await at(chat_id, "ai.error_prefix", error=str(e))

        import contextlib

        with contextlib.suppress(Exception):
            await message.reply_text(error_msg)


# --- Admin Panel Input Handlers ---

AI_FIELDS = ["aiApiKey", "aiModelId", "aiSystemPrompt", "aiInstruction"]


@bot.on_message(filters.private & is_waiting_for_input(AI_FIELDS), group=-100)
@safe_handler
async def ai_settings_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    field = state["field"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text or ""

    value_text = str(value).strip()
    if not value_text:
        await message.reply(await at(user_id, "panel.input_invalid_string"))
        return

    mapping = {
        "aiApiKey": "apiKey",
        "aiModelId": "modelId",
        "aiSystemPrompt": "systemPrompt",
        "aiInstruction": "customInstruction",
    }
    db_field = mapping.get(field, field)

    update_data = {db_field: value_text}
    await AIRepository.update_settings(ctx, chat_id, **update_data)

    from src.plugins.admin_panel.handlers.ai_kbs import ai_menu_kb

    kb = await ai_menu_kb(chat_id, user_id=user_id)

    s = await AIRepository.get_settings(ctx, chat_id)
    is_enabled = s.isAssistantEnabled if s else False
    provider = (s.provider if s else "openai").upper()
    model = (s.modelId if s else "N/A") or "N/A"
    api_key = "****" if (s and s.apiKey) else await at(user_id, "panel.not_set")

    status_text = await at(user_id, f"panel.status_{'enabled' if is_enabled else 'disabled'}")
    main_text = await at(
        user_id,
        "panel.ai_text",
        status=status_text,
        provider=provider,
        model=model,
        api_key=api_key,
    )

    success_text = await at(user_id, "panel.input_success")
    if field == "aiModelId":
        success_text = await at(user_id, "panel.ai_model_set", model=model)

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        main_text,
        kb,
        success_text=success_text,
    )
