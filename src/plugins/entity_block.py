import json

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import Message
from sqlalchemy import select

from src.core.bot import bot
from src.core.context import get_context
from src.core.plugin import Plugin, register
from src.db.models import BlockedEntity, ChatSettings
from src.utils.decorators import safe_handler
from src.utils.i18n import at
from src.utils.moderation import execute_moderation_action, resolve_sender

CACHE_KEY_PREFIX = "lex:entity_block:"


class EntityBlockPlugin(Plugin):
    """Plugin to block specific message entities (links, stickers, media, etc.) in groups."""

    name = "entity_block"
    priority = 50

    async def setup(self, client: Client, ctx) -> None:
        pass


async def get_blocked_entities(ctx, chat_id: int) -> list[BlockedEntity]:
    """
    Retrieve the list of blocked entity types for a specific chat.

    Uses an asynchronous memory cache (with a 24h TTL) to minimize database lookups
     for every message.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.

    Returns:
        list[BlockedEntity]: A list of blocked entity objects.
    """
    key = f"{CACHE_KEY_PREFIX}{chat_id}"
    cached = await ctx.cache.get(key)
    if cached:
        try:
            data = json.loads(cached)
            return [
                BlockedEntity(
                    id=b["id"],
                    chatId=b["chatId"],
                    entityType=b["entityType"],
                    action=b["action"],
                )
                for b in data
            ]
        except Exception as e:
            logger.error(f"Failed to parse EntityBlock cache for {chat_id}: {e}")
            await ctx.cache.delete(key)
    async with ctx.db() as session:
        stmt = select(BlockedEntity).where(BlockedEntity.chatId == chat_id)
        result = await session.execute(stmt)
        blocks = list(result.scalars().all())
    try:
        data = [
            {
                "id": b.id,
                "chatId": b.chatId,
                "entityType": b.entityType,
                "action": b.action,
            }
            for b in blocks
        ]
        await ctx.cache.setex(key, 86400, json.dumps(data))
    except Exception as e:
        logger.error(f"Failed to cache EntityBlocks for {chat_id}: {e}")
    return blocks


async def add_blocked_entity(
    ctx, chat_id: int, entity_type: str, action: str = "delete"
) -> BlockedEntity:
    """
    Block a specific entity type (or media category) in a chat.

    If the entity type is already blocked, its action is updated.
    Invalidates the chat's entity block cache after modification.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.
        entity_type (str): The identifier for the entity type (e.g., 'url', 'sticker').
        action (str, optional): The moderation action to take (e.g., 'delete', 'ban', 'mute'). Defaults to "delete".

    Returns:
        BlockedEntity: The created or updated blocked entity entry.
    """
    async with ctx.db() as session:
        settings = await session.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(id=chat_id)
            session.add(settings)
            await session.commit()
        stmt = select(BlockedEntity).where(
            BlockedEntity.chatId == chat_id, BlockedEntity.entityType == entity_type
        )
        result = await session.execute(stmt)
        res = result.scalars().first()
        if res:
            res.action = action
            session.add(res)
        else:
            res = BlockedEntity(chatId=chat_id, entityType=entity_type, action=action)
            session.add(res)
        await session.commit()
        await session.refresh(res)
        await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{chat_id}")
        return res


async def remove_blocked_entity(ctx, chat_id: int, entity_type: str) -> None:
    """
    Unblock an entity type in a chat.

    Removes all database entries for the specified entity type in the chat
    and invalidates the cache.

    Args:
        ctx (Context): The application context.
        chat_id (int): The ID of the chat.
        entity_type (str): The identifier for the entity type.
    """
    async with ctx.db() as session:
        stmt = select(BlockedEntity).where(
            BlockedEntity.chatId == chat_id, BlockedEntity.entityType == entity_type
        )
        result = await session.execute(stmt)
        objs = result.scalars().all()
        for obj in objs:
            await session.delete(obj)
        await session.commit()
    await ctx.cache.delete(f"{CACHE_KEY_PREFIX}{chat_id}")


@bot.on_message(filters.group, group=-110)
@safe_handler
async def entity_block_interceptor(client: Client, message: Message) -> None:
    """
    Check all incoming group messages for restricted content (entities, media, forwards).

    Cross-references the message content against the chat's blocked entities list.
    If a violation is found, it executes a moderation action (deletion, restriction,
     or banning) and stops further processing of the message.

    Args:
        client (Client): The Pyrogram client instance.
        message (Message): The message object to inspect.

    Side Effects:
        - Deletes the message if a violation is found.
        - May mute, kick, or ban the sender according to the block settings.
        - Stops message propagation on violation.
    """
    if not message.from_user or message.from_user.is_bot or getattr(message, "command", None):
        return

    user_id, _, is_adm = await resolve_sender(client, message)
    if not user_id or is_adm:
        return
    ctx = get_context()
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
    acted = await execute_moderation_action(
        client=client,
        message=message,
        action=violated_block.action,
        reason=reason,
        log_tag="EntityBlock",
        violation_key="entityblock.violation",
        type=type_label,
    )
    if acted:
        await message.stop_propagation()


register(EntityBlockPlugin())
