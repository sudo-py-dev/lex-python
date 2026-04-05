from redis.asyncio import ConnectionPool, Redis

from src.config import config

_pool: ConnectionPool | None = None


def get_redis() -> Redis:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            config.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return Redis(connection_pool=_pool)
