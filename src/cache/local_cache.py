import asyncio
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from loguru import logger


class AsyncSnapshotCache:
    """
    A high-performance, async-native memory cache with LRU eviction and snapshots.
    Uses collections.OrderedDict for O(1) LRU eviction and memory bounds.
    """

    def __init__(self, snapshot_path: str = "data/cache_snapshot.pkl", max_size: int = 10000):
        self.snapshot_path = Path(snapshot_path)
        self.max_size = max_size
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._expiries: dict[str, float] = {}
        self._lock = asyncio.Lock()

        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def get(self, key: str) -> Any | None:
        """Retrieves an item, updating its LRU position."""
        async with self._lock:
            if key not in self._data:
                self._misses += 1
                return None

            expiry = self._expiries.get(key)
            if expiry and time.time() > expiry:
                self._delete_internal(key)
                self._misses += 1
                return None

            self._data.move_to_end(key)
            self._hits += 1
            return self._data[key]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Sets an item with LRU eviction and optional TTL."""
        async with self._lock:
            if key in self._data:
                self._data.move_to_end(key)

            self._data[key] = value
            if ttl:
                self._expiries[key] = time.time() + ttl
            else:
                self._expiries.pop(key, None)

            while len(self._data) > self.max_size:
                self._evict_oldest()

            return True

    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        """Compatibility wrapper for standard cache setex."""
        return await self.set(key, value, ttl=ttl)

    async def incr(self, key: str) -> int:
        """Increments an integer key with LRU update."""
        async with self._lock:
            expiry = self._expiries.get(key)
            if expiry and time.time() > expiry:
                self._delete_internal(key)

            current = self._data.get(key, 0)
            if not isinstance(current, int):
                try:
                    current = int(current)
                except (ValueError, TypeError):
                    current = 0

            new_val = current + 1
            self._data[key] = new_val
            self._data.move_to_end(key)

            if len(self._data) > self.max_size:
                self._evict_oldest()

            return new_val

    async def expire(self, key: str, seconds: int) -> bool:
        """Sets/Updates TTL and marks key as recently used."""
        async with self._lock:
            if key not in self._data:
                return False
            self._expiries[key] = time.time() + seconds
            self._data.move_to_end(key)
            return True

    async def exists(self, key: str) -> bool:
        """Checks existence and updates LRU position."""
        async with self._lock:
            if key not in self._data:
                return False

            expiry = self._expiries.get(key)
            if expiry and time.time() > expiry:
                self._delete_internal(key)
                return False

            self._data.move_to_end(key)
            return True

    async def get_ttl(self, key: str) -> int:
        """Returns remaining TTL in seconds, or -1 if no TTL, -2 if not exists."""
        async with self._lock:
            if key not in self._data:
                return -2
            expiry = self._expiries.get(key)
            if not expiry:
                return -1
            remaining = int(expiry - time.time())
            return max(0, remaining)

    async def delete(self, key: str) -> bool:
        """Removes a key from cache."""
        async with self._lock:
            return self._delete_internal(key)

    def _delete_internal(self, key: str) -> bool:
        """Internal helper to delete a key without acquiring the lock."""
        self._expiries.pop(key, None)
        return self._data.pop(key, None) is not None

    def _evict_oldest(self) -> None:
        """Removes the least recently used item."""
        if not self._data:
            return
        key, _ = self._data.popitem(last=False)
        self._expiries.pop(key, None)
        self._evictions += 1
        logger.trace(f"Evicted LRU key: {key}")

    async def stats(self) -> dict[str, Any]:
        """Returns cache usage statistics."""
        async with self._lock:
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": f"{(self._hits / (self._hits + self._misses) * 100):.2f}%"
                if (self._hits + self._misses) > 0
                else "0%",
            }

    async def cleanup_expired(self) -> int:
        """Purges all expired keys."""
        async with self._lock:
            now = time.time()
            expired_keys = [k for k, exp in self._expiries.items() if now > exp]
            for k in expired_keys:
                self._delete_internal(k)
            return len(expired_keys)

    async def save_snapshot(self) -> bool:
        """Saves current cache state to disk atokically."""
        async with self._lock:
            try:
                self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.snapshot_path.with_suffix(".tmp")

                state = {
                    "data": dict(self._data),
                    "expiries": self._expiries,
                    "timestamp": time.time(),
                }

                with open(temp_path, "wb") as f:
                    pickle.dump(state, f)

                temp_path.replace(self.snapshot_path)
                logger.debug(f"Cache snapshot saved: {len(self._data)} items.")
                return True
            except Exception as e:
                logger.error(f"Failed to save cache snapshot: {e}")
                return False

    async def load_snapshot(self) -> bool:
        """Loads cache state and restores LRU order."""
        if not self.snapshot_path.exists():
            return False

        async with self._lock:
            try:
                with open(self.snapshot_path, "rb") as f:
                    state = pickle.load(f)

                self._data = OrderedDict(state.get("data", {}))
                self._expiries = state.get("expiries", {})

                now = time.time()
                expired_keys = [k for k, exp in self._expiries.items() if now > exp]
                for k in expired_keys:
                    self._data.pop(k, None)
                    self._expiries.pop(k, None)

                logger.debug(f"Loaded cache snapshot: {len(self._data)} items.")
                return True
            except Exception as e:
                logger.error(f"Failed to load cache snapshot: {e}")
                return False


_cache: AsyncSnapshotCache | None = None


def get_cache() -> AsyncSnapshotCache:
    """Returns the global AsyncSnapshotCache instance."""
    global _cache
    if _cache is None:
        _cache = AsyncSnapshotCache()
    return _cache
