from src.cache.redis import get_redis
from src.core.context import AppContext
from src.db.models import GroupSettings

_CACHE_TTL = 3600


async def get_chat_lang(ctx: AppContext, chat_id: int) -> str:
    """Get chat language from Redis cache, falling back to DB."""
    r = get_redis()
    cache_key = f"lang:{chat_id}"

    cached = await r.get(cache_key)
    if cached:
        return cached

    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        lang = settings.language if settings else "en"

    await r.set(cache_key, lang, ex=_CACHE_TTL)
    return lang


async def set_chat_lang(ctx: AppContext, chat_id: int, lang: str) -> None:
    """Update chat language in DB and invalidate Redis cache."""
    async with ctx.db() as session:
        settings = await session.get(GroupSettings, chat_id)
        if settings:
            settings.language = lang
            session.add(settings)
        else:
            settings = GroupSettings(id=chat_id, language=lang)
            session.add(settings)
        await session.commit()

    r = get_redis()
    await r.delete(f"lang:{chat_id}")
