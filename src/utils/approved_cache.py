"""Local Cache-backed approved user list cache. Avoids per-message DB calls."""

from __future__ import annotations

import json

from loguru import logger

from src.cache.local_cache import get_cache
from src.core.constants import CacheKeys
from src.db.repositories.approvals import get_all_approved

_TTL = 600  # 10 minutes


async def _fetch_and_cache_approved(chat_id: int) -> set[int]:
    """Fetch approved users from DB, store in Local Cache."""
    if chat_id is None:
        return set()
    
    try:
        from src.core.context import get_context
        ctx = get_context()
        approvals = await get_all_approved(ctx, chat_id)
        approved_ids = {a.userId for a in approvals}
        
        r = get_cache()
        await r.set(CacheKeys.approved(chat_id), json.dumps(list(approved_ids)), ttl=_TTL)
        logger.debug(f"Approved cache refreshed for chat {chat_id}: {len(approved_ids)} users")
        return approved_ids
    except Exception as e:
        logger.warning(f"Failed to fetch approved users for chat {chat_id}: {e}")
        return set()


async def is_approved(chat_id: int | None, user_id: int | None) -> bool:
    """Check if user is approved. Uses Local cache, falls back to DB."""
    if chat_id is None or user_id is None:
        return False
    
    if chat_id > 0:
        return False

    r = get_cache()
    cached = await r.get(CacheKeys.approved(chat_id))
    if cached:
        try:
            return user_id in json.loads(cached)
        except Exception:
            pass
            
    approved_ids = await _fetch_and_cache_approved(chat_id)
    return user_id in approved_ids


async def invalidate_approved_cache(chat_id: int | None) -> None:
    """Call after /approve or /unapprove to force refresh on next check."""
    if chat_id is None:
        return
    r = get_cache()
    await r.delete(CacheKeys.approved(chat_id))
    logger.debug(f"Approved cache invalidated for chat {chat_id}")
