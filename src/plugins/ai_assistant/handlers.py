import re
import time

from loguru import logger
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, MessageEntityType, ParseMode
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.local_cache import get_cache

from .repository import AIRepository
from .service import AIService
from .telegram_markdown import render_pyrogram_html


def _compact_history(
    messages: list[dict[str, str]], *, max_messages: int, max_chars: int
) -> list[dict[str, str]]:
    if not messages:
        return []
    out, total = [], 0
    for m in reversed(messages[-max_messages:]):
        content, role = str(m.get("content", "")), str(m.get("role", "user"))
        if not content:
            continue
        if total + len(content) > max_chars:
            if (rem := max_chars - total) <= 80:
                break
            content = content[-rem:]
        out.append({"role": role, "content": content})
        if (total := total + len(content)) >= max_chars:
            break
    return list(reversed(out))


def _is_request_too_large_error(err: Exception) -> bool:
    e = str(err).lower()
    return any(x in e for x in ("request_too_large", "413", "request entity too large"))


def _trim_text(v: str | None, max_c: int) -> str | None:
    return v.strip()[-max_c:] if v and len(v.strip()) > max_c else (v.strip() if v else v)


@bot.on_message(filters.group & ~filters.service & ~filters.bot, group=100)
@safe_handler
async def ai_message_handler(client: Client, message: Message):
    """Main AI handler: log msg & respond if mentioned or in session."""
    chat_id, user_id = message.chat.id, message.from_user.id if message.from_user else 0
    t = message.text or message.caption
    if not client.me or not t or t.startswith("/"):
        return

    ctx, cache = get_context(), get_cache()
    await AIRepository.add_message(
        ctx,
        chat_id,
        message.id,
        user_id,
        message.from_user.first_name if message.from_user else "Unknown",
        t,
    )

    s = await AIRepository.get_settings(ctx, chat_id)
    if not s or not s.isAssistantEnabled or not s.apiKey:
        return

    is_m = False
    me_tag = f"@{client.me.username}".lower()
    if message.entities:
        is_m = any(
            me_tag in t[e.offset : e.offset + e.length].lower()
            for e in message.entities
            if e.type in (MessageEntityType.MENTION, MessageEntityType.BOT_COMMAND)
        )
    if not is_m:
        is_m = me_tag in t.lower() or (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == client.me.id
        )

    s_key = f"ai_session:{chat_id}"
    is_active = await cache.exists(s_key)
    if not is_m and not is_active:
        return

    await cache.set(s_key, True, ttl=180)
    p = (s.provider or "openai").lower()
    max_m, max_c = (16, 7000) if p == "groq" else (24, 12000)
    retry_max_m, retry_max_c = (6, 2200) if p == "groq" else (8, 3000)

    history = _compact_history(
        await AIRepository.get_context(ctx, chat_id, client.me.id),
        max_messages=max_m,
        max_chars=max_c,
    )
    logger.debug(f"AI [{chat_id}] History: {len(history)} messages. Calling LLM...")

    from .prompts import BASE_PROMPT, OPERATIONAL_RULES

    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)

        sys_prompt = s.systemPrompt if s.systemPrompt else BASE_PROMPT
        sys_prompt = sys_prompt.format(
            bot_name=client.me.first_name, bot_username=client.me.username
        )

        sys_prompt = (
            f"IDENTITY: You are @{client.me.username} ({client.me.first_name})\n\n{sys_prompt}"
        )

        if s.systemPrompt:
            sys_prompt += OPERATIONAL_RULES

        sys_prompt = _trim_text(sys_prompt, 3200) or ""
        custom_instruction = _trim_text(s.customInstruction, 900)

        try:
            start_time = time.time()
            response_text = await AIService.call_ai(
                provider=s.provider,
                api_key=s.apiKey,
                model_id=s.modelId or "gpt-3.5-turbo",
                system_prompt=sys_prompt,
                custom_instruction=custom_instruction,
                messages=history,
            )
            duration = time.time() - start_time
        except Exception as first_error:
            if not _is_request_too_large_error(first_error):
                raise
            logger.warning(f"AI [{chat_id}] context too large, retrying with compact history")
            retry_history = _compact_history(
                history, max_messages=retry_max_m, max_chars=retry_max_c
            )
            start_time = time.time()
            response_text = await AIService.call_ai(
                provider=s.provider,
                api_key=s.apiKey,
                model_id=s.modelId or "gpt-3.5-turbo",
                system_prompt=_trim_text(sys_prompt, 1800),
                custom_instruction=_trim_text(custom_instruction, 500),
                messages=retry_history,
            )
            duration = time.time() - start_time

        if response_text:
            clean_response = response_text.strip()
            latency_text = await at(chat_id, "ai.latency_fmt", duration=f"{duration:.1f}")
            clean_response += latency_text

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
                await cache.delete(s_key)
                await message.reply_text(await at(chat_id, "ai.session_closed"))
                return

            render_text = render_pyrogram_html(clean_response)
            try:
                sent_msg = await message.reply_text(render_text, parse_mode=ParseMode.HTML)
            except ValueError as format_error:
                logger.warning(
                    f"AI [{chat_id}] html render failed, fallback to plain text: {format_error}"
                )
                sent_msg = await message.reply_text(clean_response, parse_mode=None)

            await AIRepository.add_message(
                ctx, chat_id, sent_msg.id, client.me.id, client.me.first_name, clean_response
            )
    except Exception as e:
        logger.debug(f"AI Response failed for chat {chat_id}: {e}")

        if "rate_limit" in str(e).lower():
            # Try to extract wait time (e.g., "try again in 5.7s")
            wait_time = "a few"
            if match := re.search(r"in ([\d\.]+)s", str(e)):
                wait_time = match.group(1)
            error_msg = await at(chat_id, "ai.rate_limit")
            if "{seconds}" in error_msg:
                error_msg = error_msg.format(seconds=wait_time)
            elif wait_time != "a few":
                error_msg += f" ({wait_time}s)"
        elif _is_request_too_large_error(e):
            await AIRepository.clear_context(ctx, chat_id)
            await cache.delete(s_key)
            error_msg = await at(chat_id, "ai.context_too_large")
        elif "decommissioned" in str(e).lower() or "deprecated" in str(e).lower():
            error_msg = await at(chat_id, "ai.model_decommissioned")
        else:
            error_msg = await at(chat_id, "ai.error_prefix", error=str(e))

        import contextlib

        with contextlib.suppress(Exception):
            await message.reply_text(error_msg)


# --- Admin Panel Input Handlers ---

AI_FIELDS = ["aiApiKey", "aiModelId", "aiSystemPrompt", "aiInstruction"]


@bot.on_message(filters.private & is_waiting_for_input(AI_FIELDS), group=-50)
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
