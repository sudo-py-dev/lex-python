import io
import json

from loguru import logger
from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from src.config import config
from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.ai_guard import get_ai_guard_settings, update_ai_guard_settings
from src.plugins.admin_panel.handlers.keyboards import ai_security_kb
from src.plugins.ai_assistant.prompts import (
    AI_GUARD_SYSTEM_PROMPT,
    AI_GUARD_TASK_PROMPT,
    AI_IMAGE_GUARD_SYSTEM_PROMPT,
    AI_IMAGE_GUARD_TASK_PROMPT,
)
from src.plugins.ai_assistant.service import AIService, AIServiceError
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.input import finalize_input_capture, is_waiting_for_input
from src.utils.media import encode_image_to_base64
from src.utils.moderation import execute_moderation_action, resolve_sender


class AIGuardPlugin(Plugin):
    """Plugin for AI-powered spam detection using Groq (Llama 3.1)."""

    name = "ai_guard"
    priority = 80

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & (filters.text | filters.caption), group=2)
@safe_handler
async def ai_guard_handler(client: Client, message: Message) -> None:
    """Analyze incoming messages for spam using AI."""
    if not message.text and not message.caption:
        return

    if getattr(message, "command", None):
        return

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    s = await get_ai_guard_settings(ctx, message.chat.id)

    if not s.isTextEnabled or not s.apiKey:
        return

    text = message.text or message.caption

    try:
        response_text = await AIService.call_ai(
            provider="groq",
            api_key=s.apiKey,
            model_id=config.AI_GUARD_MODEL,
            system_prompt=AI_GUARD_SYSTEM_PROMPT,
            custom_instruction=None,
            messages=[{"role": "user", "content": AI_GUARD_TASK_PROMPT.format(user_input=text)}],
            response_format={"type": "json_object"},
        )

        result = json.loads(response_text)
        classification = str(result.get("classification", "HAM")).upper()
        confidence = float(result.get("confidence_score", 0))
        reason = result.get("reason") or "ai_detection"

        if classification == "SPAM" and confidence >= 0.7:
            logger.debug(f"AI Guard: Spam detected in {message.chat.id}. Score: {confidence}")
            await execute_moderation_action(
                client=client,
                message=message,
                action=s.action,
                reason=reason,
                log_tag="AI_GUARD",
                violation_key="ai_guard.spam_detected",
            )
            await message.stop_propagation()

    except AIServiceError as e:
        if "authentication" in str(e).lower():
            logger.warning(f"AI Guard: Auth failed for chat {message.chat.id}. Disabling.")
            await update_ai_guard_settings(ctx, message.chat.id, isTextEnabled=False, apiKey=None)
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("AI Guard: Failed to parse AI response.")
    except StopPropagation:
        raise
    except Exception as e:
        logger.error(f"AI Guard: Unexpected error in {message.chat.id}: {e}")


@bot.on_message(filters.group & (filters.photo | filters.document), group=3)
@safe_handler
async def ai_image_guard_handler(client: Client, message: Message) -> None:
    """Analyze incoming photos/images for spam using AI Vision."""
    # Only process documents if they are images
    if message.document and (
        not message.document.mime_type or not message.document.mime_type.startswith("image/")
    ):
        return

    # File size safety check
    file_obj = message.photo or message.document
    if file_obj and file_obj.file_size > (config.AI_GUARD_MAX_IMAGE_SIZE_MB * 1024 * 1024):
        logger.debug(
            f"AI Image Guard: Skipping large file ({file_obj.file_size} bytes) in {message.chat.id}"
        )
        return

    user_id, mention, is_white = await resolve_sender(client, message)
    if not user_id or is_white:
        return

    ctx = get_context()
    s = await get_ai_guard_settings(ctx, message.chat.id)

    if not s.isImageEnabled or not s.apiKey:
        return

    try:
        # Download image into memory
        bio = io.BytesIO()
        await message.download(file_name=bio)
        base64_image = encode_image_to_base64(bio)

        response_text = await AIService.call_ai(
            provider="groq",
            api_key=s.apiKey,
            model_id=config.AI_GUARD_VISION_MODEL,
            system_prompt=AI_IMAGE_GUARD_SYSTEM_PROMPT,
            custom_instruction=None,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": AI_IMAGE_GUARD_TASK_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response_text)
        classification = str(result.get("classification", "HAM")).upper()
        confidence = float(result.get("confidence_score", 0))
        reason = result.get("reason") or "ai_image_detection"

        if classification == "SPAM" and confidence >= 0.7:
            logger.debug(f"AI Image Guard: Spam in {message.chat.id}. Score: {confidence}")
            await execute_moderation_action(
                client=client,
                message=message,
                action=s.action,
                reason=reason,
                log_tag="AI_IMAGE_GUARD",
                violation_key="ai_guard.spam_detected",
            )
            await message.stop_propagation()

    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("AI Image Guard: Failed to parse AI response.")
    except AIServiceError as e:
        logger.error(f"AI Image Guard Service Error: {e}")
    except Exception as e:
        logger.error(f"AI Image Guard: Unexpected error: {e}")


# --- Admin Panel Input Handlers ---


@bot.on_message(filters.private & is_waiting_for_input("groqKey"), group=-100)
@safe_handler
async def ai_guard_settings_input_handler(client: Client, message: Message) -> None:
    state = message.input_state
    chat_id = state["chat_id"]
    user_id = message.from_user.id
    ctx = get_context()
    value = message.text or ""
    str_value = str(value).strip()

    if str_value.lower() == "reset":
        await update_ai_guard_settings(ctx, chat_id, apiKey=None, isTextEnabled=False)
        str_value = None
    elif not str_value:
        await message.reply(await at(user_id, "panel.input_invalid_string"))
        return
    else:
        await update_ai_guard_settings(ctx, chat_id, apiKey=str_value)

    kb = await ai_security_kb(ctx, chat_id, user_id)

    s = await get_ai_guard_settings(ctx, chat_id)
    text_status = await at(user_id, f"panel.status_{'enabled' if s.isTextEnabled else 'disabled'}")
    media_status = await at(
        user_id, f"panel.status_{'enabled' if s.isImageEnabled else 'disabled'}"
    )
    action_label = await at(user_id, f"action.{s.action}")

    api_key_status = "****" if s.apiKey else await at(user_id, "panel.not_set")
    text = await at(
        user_id,
        "panel.ai_guard_text",
        text_status=text_status,
        media_status=media_status,
        action=action_label,
        model=config.AI_GUARD_MODEL,
        api_key=api_key_status,
    )

    await finalize_input_capture(
        client,
        message,
        user_id,
        state["prompt_msg_id"],
        text,
        kb,
        success_text=await at(user_id, "panel.input_success"),
    )


register(AIGuardPlugin())
