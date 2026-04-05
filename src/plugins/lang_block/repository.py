import json

from loguru import logger
from sqlalchemy import select

from src.core.context import AppContext
from src.db.models import BlockedLanguage, GroupSettings

from .service import is_supported

REDIS_KEY_PREFIX = "lex:lang_block:"


async def get_lang_blocks(ctx: AppContext, chat_id: int) -> list[BlockedLanguage]:
    key = f"{REDIS_KEY_PREFIX}{chat_id}"

    # Try Redis cache first
    cached = await ctx.redis.get(key)
    if cached:
        try:
            data = json.loads(cached)
            return [
                BlockedLanguage(
                    id=b["id"],
                    chatId=b["chatId"],
                    langCode=b["langCode"],
                    action=b["action"],
                )
                for b in data
            ]
        except Exception as e:
            logger.error(f"Failed to parse LangBlock cache for {chat_id}: {e}")
            await ctx.redis.delete(key)

    # Cache miss: fetch from DB
    async with ctx.db() as session:
        stmt = select(BlockedLanguage).where(BlockedLanguage.chatId == chat_id)
        result = await session.execute(stmt)
        blocks = list(result.scalars().all())

    try:
        data = [
            {
                "id": b.id,
                "chatId": b.chatId,
                "langCode": b.langCode,
                "action": b.action,
            }
            for b in blocks
        ]
        await ctx.redis.setex(key, 86400, json.dumps(data))
    except Exception as e:
        logger.error(f"Failed to cache LangBlocks for {chat_id}: {e}")

    return blocks


async def add_lang_block(
    ctx: AppContext, chat_id: int, lang_code: str, action: str = "delete"
) -> BlockedLanguage:
    lang_code = lang_code.lower().strip()
    if not is_supported(lang_code):
        raise ValueError(f"Language code '{lang_code}' is not supported by the detector.")

    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if not settings:
            settings = GroupSettings(id=chat_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        stmt = select(BlockedLanguage).where(
            BlockedLanguage.chatId == chat_id, BlockedLanguage.langCode == lang_code
        )
        result = await session.execute(stmt)
        res = result.scalars().first()

        if res:
            res.action = action
            session.add(res)
        else:
            res = BlockedLanguage(chatId=chat_id, langCode=lang_code, action=action)
            session.add(res)

        await session.commit()
        await session.refresh(res)

        await ctx.redis.delete(f"{REDIS_KEY_PREFIX}{chat_id}")
        return res


async def remove_lang_block(ctx: AppContext, chat_id: int, lang_code: str) -> None:
    async with ctx.db() as session:
        stmt = select(BlockedLanguage).where(
            BlockedLanguage.chatId == chat_id, BlockedLanguage.langCode == lang_code
        )
        result = await session.execute(stmt)
        objs = result.scalars().all()
        for obj in objs:
            await session.delete(obj)
        await session.commit()

    await ctx.redis.delete(f"{REDIS_KEY_PREFIX}{chat_id}")


async def cycle_lang_action(ctx: AppContext, chat_id: int, action: str) -> None:
    # Logic is usually handled in the admin panel by calling add_lang_block with the new action
    pass
