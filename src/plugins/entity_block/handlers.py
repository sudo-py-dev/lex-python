from pyrogram import Client, filters
from pyrogram.types import Message

from src.core.bot import bot
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender

from . import get_ctx
from .repository import get_blocked_entities


@bot.on_message(filters.group, group=-110)
@safe_handler
async def entity_block_interceptor(client: Client, message: Message) -> None:
    user_id, _, is_adm = await resolve_sender(client, message)
    if not user_id or is_adm:
        return

    ctx = get_ctx()
    blocks = await get_blocked_entities(ctx, message.chat.id)
    if not blocks:
        return

    blocked_types = {b.entityType: b for b in blocks}

    entities = (message.entities or []) + (message.caption_entities or [])
    violated_block = None

    for ent in entities:
        e_type_str = str(ent.type).split(".")[-1].lower()
        if e_type_str in blocked_types:
            violated_block = blocked_types[e_type_str]
            break

    if not violated_block:
        if message.poll and "poll" in blocked_types:
            violated_block = blocked_types["poll"]
        elif message.contact and "contact" in blocked_types:
            violated_block = blocked_types["contact"]
        elif (message.location or message.venue) and "location" in blocked_types:
            violated_block = blocked_types["location"]
        elif message.sticker and "sticker" in blocked_types:
            violated_block = blocked_types["sticker"]
        elif message.animation and "gif" in blocked_types:
            violated_block = blocked_types["gif"]
        elif (
            message.photo
            or message.video
            or message.audio
            or message.voice
            or message.document
            or message.video_note
        ) and "media" in blocked_types:
            violated_block = blocked_types["media"]
        elif message.forward_origin and "forward" in blocked_types:
            violated_block = blocked_types["forward"]
        elif message.text and message.text.startswith("/") and "command" in blocked_types:
            violated_block = blocked_types["command"]
        elif message.text and not message.text.startswith("/") and "message" in blocked_types:
            violated_block = blocked_types["message"]

    if not violated_block:
        return

    type_label = await at(message.chat.id, f"lock.{violated_block.entityType}")
    reason = await at(message.chat.id, "reason.blocked_entity", type=type_label)
    await execute_moderation_action(
        client=client,
        message=message,
        action=violated_block.action,
        reason=reason,
        log_tag="EntityBlock",
        violation_key="entityblock.violation",
        type=type_label,
    )
    await message.stop_propagation()
