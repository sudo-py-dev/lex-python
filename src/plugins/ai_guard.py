import json

from loguru import logger
from pyrogram import Client, StopPropagation, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.repositories.ai_guard import get_ai_guard_settings, update_ai_guard_settings
from src.plugins.ai_assistant.prompts import AI_GUARD_SYSTEM_PROMPT, AI_GUARD_TASK_PROMPT
from src.plugins.ai_assistant.service import AIService, AIServiceError
from src.utils.decorators import safe_handler
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

    if not s.isEnabled or not s.apiKey:
        return

    text = message.text or message.caption

    try:
        response_text = await AIService.call_ai(
            provider="groq",
            api_key=s.apiKey,
            model_id=s.modelId,
            system_prompt=AI_GUARD_SYSTEM_PROMPT,
            custom_instruction=None,
            messages=[{"role": "user", "content": AI_GUARD_TASK_PROMPT.format(user_input=text)}],
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response_text)
            classification = str(result.get("classification", "HAM")).upper()
            confidence = float(result.get("confidence_score", 0))
            reason = result.get("reason", "Unknown AI Detection")
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(
                f"AI Guard: Invalid JSON response from AI: {e}. Defaulting to HAM to avoid false positives."
            )
            classification = "HAM"
            confidence = 0.0
            reason = "ai_parse_error"

        if classification == "SPAM" and confidence >= 0.7:
            logger.debug(
                f"AI Guard: Spam detected in {message.chat.id} from {user_id}. Reason: {reason}"
            )

            acted = await execute_moderation_action(
                client=client,
                message=message,
                action=s.action,
                reason=reason,
                log_tag="AI_GUARD",
                violation_key="ai_guard.spam_detected",
            )
            if acted:
                await message.stop_propagation()

    except AIServiceError as e:
        error_str = str(e) or repr(e)
        logger.exception(
            f"AI Guard Service Error in chat={message.chat.id} user={user_id}: {error_str}"
        )

        if "authentication" in error_str.lower():
            logger.debug(f"AI Guard: Authentication failed in {message.chat.id}. Disabling guard.")
            await update_ai_guard_settings(ctx, message.chat.id, isEnabled=False, apiKey=None)

    except StopPropagation:
        # Expected control-flow exception from Pyrogram.
        raise

    except Exception as e:
        error_str = str(e) or repr(e)
        logger.exception(
            f"AI Guard Unexpected Error in chat={message.chat.id} user={user_id}: {error_str}"
        )


register(AIGuardPlugin())
