"""Local Cache-backed allowed channel list cache. Avoids per-message DB calls."""

from __future__ import annotations

import json

from loguru import logger

from src.cache.local_cache import get_cache
from src.core.constants import CacheKeys
from src.db.repositories.allowed_channels import get_allowed_channels

_TTL = 300  # 5 minutes


async def _fetch_and_cache_allowed_channels(chat_id: int) -> set[int]:
    """Fetch whitelisted channels from DB, store in Local Cache."""
    if chat_id is None:
        return set()

    try:
        from src.core.context import get_context

        ctx = get_context()
        allowed = await get_allowed_channels(ctx, chat_id)
        allowed_ids = {a.channelId for a in allowed}

        r = get_cache()
        await r.set(CacheKeys.allowlisted(chat_id), json.dumps(list(allowed_ids)), ttl=_TTL)
        logger.debug(f"Allowlist cache refreshed for chat {chat_id}: {len(allowed_ids)} channels")
        return allowed_ids
    except Exception as e:
        logger.warning(f"Failed to fetch allowed channels for chat {chat_id}: {e}")
        return set()


async def is_channel_allowed(chat_id: int | None, channel_id: int | None) -> bool:
    """Check if channel is whitelisted. Uses Local cache, falls back to DB."""
    if chat_id is None or channel_id is None:
        return False

    r = get_cache()
    cached = await r.get(CacheKeys.allowlisted(chat_id))
    if cached:
        try:
            return channel_id in json.loads(cached)
        except Exception:
            pass

    allowed_ids = await _fetch_and_cache_allowed_channels(chat_id)
    return channel_id in allowed_ids


async def invalidate_allowlist_cache(chat_id: int | None) -> None:
    """Call after /allowlist or /unallowlist to force refresh on next check."""
    if chat_id is None:
        return
    r = get_cache()
    await r.delete(CacheKeys.allowlisted(chat_id))
    logger.debug(f"Allowlist cache invalidated for chat {chat_id}")
