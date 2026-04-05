"""Redis-backed admin list cache. Avoids per-message get_chat_member API calls."""

from __future__ import annotations

import json

from loguru import logger
from pyrogram import Client, enums

from src.cache.redis import get_redis

_TTL = 300


async def _fetch_and_cache(client: Client, chat_id: int) -> set[int]:
    """Fetch admin list from Telegram, store in Redis."""
    if chat_id is None:
        return set()
    if chat_id > 0:
        return {chat_id}

    try:
        admin_ids = set()
        async for m in client.get_chat_members(
            chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
        ):
            if m.user:
                admin_ids.add(m.user.id)
        r = get_redis()
        await r.set(f"admins:{chat_id}", json.dumps(list(admin_ids)), ex=_TTL)
        logger.debug(f"Admin cache refreshed for chat {chat_id}: {len(admin_ids)} admins")
        return admin_ids
    except Exception as e:
        logger.warning(f"Failed to fetch admins for chat {chat_id}: {e}")
        return set()


async def is_admin(client: Client, chat_id: int | None, user_id: int | None) -> bool:
    """Check if user is admin. Uses Redis cache, falls back to API."""
    if chat_id is None or user_id is None:
        return False
    if chat_id > 0:
        return chat_id == user_id

    r = get_redis()
    cached = await r.get(f"admins:{chat_id}")
    if cached:
        return user_id in json.loads(cached)
    admin_ids = await _fetch_and_cache(client, chat_id)
    return user_id in admin_ids


async def invalidate_cache(chat_id: int | None) -> None:
    """Call after /promote or /demote to force refresh on next check."""
    if chat_id is None:
        return
    r = get_redis()
    await r.delete(f"admins:{chat_id}")
    logger.debug(f"Admin cache invalidated for chat {chat_id}")


async def force_refresh(client: Client, chat_id: int | None) -> set[int]:
    """Invalidate and immediately re-fetch."""
    if chat_id is None:
        return set()
    await invalidate_cache(chat_id)
    return await _fetch_and_cache(client, chat_id)
