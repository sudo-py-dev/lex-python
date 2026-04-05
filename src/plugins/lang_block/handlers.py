from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender

from . import get_ctx
from .repository import get_lang_blocks
from .service import detect_language_with_confidence


@bot.on_message(filters.group & (filters.text | filters.caption), group=-105)
@safe_handler
async def lang_block_interceptor(client: Client, message: Message) -> None:
    text = message.text or message.caption
    if not text or len(text) < 2:
        return

    user_id, _, is_adm = await resolve_sender(client, message)
    if not user_id or is_adm:
        return

    ctx = get_ctx()
    blocks = await get_lang_blocks(ctx, message.chat.id)
    if not blocks:
        return

    detections = detect_language_with_confidence(text)
    if not detections:
        return

    blocked_codes = {b.langCode: b for b in blocks}

    violated_block = None
    for code, prob in detections:
        if prob > 0.5 and code in blocked_codes:
            violated_block = blocked_codes[code]
            break

    if not violated_block:
        return

    reason = await at(message.chat.id, "reason.blocked_language", lang=violated_block.langCode)
    await execute_moderation_action(
        client=client,
        message=message,
        action=violated_block.action,
        reason=reason,
        log_tag="LangBlock",
        violation_key="langblock.violation",
        lang=violated_block.langCode.upper(),
    )
    await message.stop_propagation()
