import io
import json

from loguru import logger
from pyrogram import Client, filters
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
    name, priority = "ai_guard", 80

    async def setup(self, client: Client, ctx) -> None:
        pass


@bot.on_message(filters.group & (filters.text | filters.caption), group=-20)
@safe_handler
async def ai_guard_handler(client: Client, message: Message):
    if not (text := message.text or message.caption) or getattr(message, "command", None):
        return
    uid, _, white = await resolve_sender(client, message)
    if not uid or white:
        return

    ctx = get_context()
    s = await get_ai_guard_settings(ctx, message.chat.id)
    if not s.isTextEnabled or not s.apiKey:
        return

    try:
        resp = await AIService.call_ai(
            "groq",
            s.apiKey,
            config.AI_GUARD_MODEL,
            AI_GUARD_SYSTEM_PROMPT,
            None,
            [{"role": "user", "content": AI_GUARD_TASK_PROMPT.format(user_input=text)}],
            {"type": "json_object"},
        )
        res = json.loads(resp)
        cls, conf, rea = (
            str(res.get("classification", "HAM")).upper(),
            float(res.get("confidence", 0)),
            res.get("reason", "ai_detection"),
        )

        if cls in ("SPAM", "INJECTION") and conf >= 0.7:
            logger.debug(f"AI Guard: {cls} in {message.chat.id} ({conf})")
            await execute_moderation_action(
                client,
                message,
                s.action,
                rea,
                log_tag="AI_GUARD",
                violation_key="ai_guard.spam_detected",
            )
            await message.stop_propagation()
    except AIServiceError as e:
        if "authentication" in str(e).lower():
            await update_ai_guard_settings(
                ctx, message.chat.id, isTextEnabled=False, isImageEnabled=False, apiKey=None
            )
    except Exception as e:
        logger.debug(f"AI Guard Fail: {e}")


@bot.on_message(filters.group & (filters.photo | filters.document), group=-20)
@safe_handler
async def ai_image_guard_handler(client: Client, message: Message):
    if message.document and (
        not message.document.mime_type or not message.document.mime_type.startswith("image/")
    ):
        return
    fobj = message.photo or message.document
    if fobj and fobj.file_size > (config.AI_GUARD_MAX_IMAGE_SIZE_MB * 1024 * 1024):
        return
    uid, _, white = await resolve_sender(client, message)
    if not uid or white:
        return

    ctx = get_context()
    s = await get_ai_guard_settings(ctx, message.chat.id)
    if not s.isImageEnabled or not s.apiKey:
        return

    try:
        bio = io.BytesIO()
        await message.download(file_name=bio)
        resp = await AIService.call_ai(
            "groq",
            s.apiKey,
            config.AI_GUARD_VISION_MODEL,
            AI_IMAGE_GUARD_SYSTEM_PROMPT,
            None,
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": AI_IMAGE_GUARD_TASK_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encode_image_to_base64(bio)}"
                            },
                        },
                    ],
                }
            ],
            {"type": "json_object"},
        )
        res = json.loads(resp)
        cls, conf, rea = (
            str(res.get("classification", "HAM")).upper(),
            float(res.get("confidence", 0)),
            res.get("reason", "ai_image_detection"),
        )

        if cls == "SPAM" and conf >= 0.7:
            await execute_moderation_action(
                client,
                message,
                s.action,
                rea,
                log_tag="AI_IMAGE_GUARD",
                violation_key="ai_guard.spam_detected",
            )
            await message.stop_propagation()
    except Exception as e:
        logger.debug(f"AI Vision Fail: {e}")


@bot.on_message(filters.private & is_waiting_for_input("groqKey"), group=-50)
@safe_handler
async def ai_guard_settings_input_handler(client: Client, message: Message):
    st = message.input_state
    cid, uid, ctx, val = (
        st["chat_id"],
        message.from_user.id,
        get_context(),
        (message.text or "").strip(),
    )
    if val.lower() == "reset":
        await update_ai_guard_settings(
            ctx, cid, apiKey=None, isTextEnabled=False, isImageEnabled=False
        )
        val = None
    elif not val:
        return await message.reply(await at(uid, "panel.input_invalid_string"))
    else:
        await update_ai_guard_settings(ctx, cid, apiKey=val)

    s = await get_ai_guard_settings(ctx, cid)
    txt = await at(
        uid,
        "panel.ai_guard_text",
        text_status=await at(uid, f"panel.status_{'enabled' if s.isTextEnabled else 'disabled'}"),
        media_status=await at(uid, f"panel.status_{'enabled' if s.isImageEnabled else 'disabled'}"),
        action=await at(uid, f"action.{s.action}"),
        model=config.AI_GUARD_MODEL,
        api_key="****" if s.apiKey else await at(uid, "panel.not_set"),
    )
    await finalize_input_capture(
        client,
        message,
        uid,
        st["prompt_msg_id"],
        txt,
        await ai_security_kb(ctx, cid, uid),
        success_text=await at(uid, "panel.input_success"),
    )


register(AIGuardPlugin())
