import json

from loguru import logger
from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import BlockedEntity, GroupSettings

REDIS_KEY_PREFIX = "lex:entity_block:"


async def get_blocked_entities(ctx: AppContext, chat_id: int) -> list[BlockedEntity]:
    key = f"{REDIS_KEY_PREFIX}{chat_id}"

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
    ctx: AppContext, chat_id: int, entity_type: str, action: str = "delete"
) -> BlockedEntity:
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
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

        await ctx.cache.delete(f"{REDIS_KEY_PREFIX}{chat_id}")
        return res


async def remove_blocked_entity(ctx: AppContext, chat_id: int, entity_type: str) -> None:
    async with ctx.db() as session:
        stmt = select(BlockedEntity).where(
            BlockedEntity.chatId == chat_id, BlockedEntity.entityType == entity_type
        )
        result = await session.execute(stmt)
        objs = result.scalars().all()
        for obj in objs:
            await session.delete(obj)
        await session.commit()

    await ctx.cache.delete(f"{REDIS_KEY_PREFIX}{chat_id}")
