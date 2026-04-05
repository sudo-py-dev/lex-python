from src.core.context import AppContext


async def increment_flood(ctx: AppContext, chat_id: int, user_id: int, window: int) -> int:
    key = f"flood:{chat_id}:{user_id}"
    count = await ctx.redis.incr(key)
    if count == 1:
        await ctx.redis.expire(key, window)
    return count


async def reset_flood(ctx: AppContext, chat_id: int, user_id: int) -> None:
    await ctx.redis.delete(f"flood:{chat_id}:{user_id}")
