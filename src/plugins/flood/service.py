from src.core.constants import CacheKeys
from src.core.context import AppContext


async def increment_flood(ctx: AppContext, chat_id: int, user_id: int, window: int) -> int:
    key = CacheKeys.flood(chat_id, user_id)
    count = await ctx.cache.incr(key)
    if count == 1:
        await ctx.cache.expire(key, window)
    return count


async def reset_flood(ctx: AppContext, chat_id: int, user_id: int) -> None:
    await ctx.cache.delete(CacheKeys.flood(chat_id, user_id))
