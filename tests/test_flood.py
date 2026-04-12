import pytest

from src.core.constants import CacheKeys
from src.core.context import AppContext
from src.plugins.flood import increment_flood
from src.utils.local_cache import AsyncSnapshotCache


@pytest.fixture
def test_cache():
    return AsyncSnapshotCache()


@pytest.fixture
def mock_ctx(test_cache, mocker):
    ctx = mocker.Mock(spec=AppContext)
    ctx.cache = test_cache
    return ctx


@pytest.mark.asyncio
async def test_flood_threshold_reached(mock_ctx):
    chat_id = -100123
    user_id = 999
    window = 5
    counts = []
    for _ in range(4):
        counts.append(await increment_flood(mock_ctx, chat_id, user_id, window))
    assert counts == [1, 2, 3, 4]
    ttl = await mock_ctx.cache.get_ttl(CacheKeys.flood(chat_id, user_id))
    assert 0 < ttl <= window


@pytest.mark.asyncio
async def test_flood_expires(mock_ctx):
    import asyncio

    chat_id = -100123
    user_id = 999
    window = 1
    count1 = await increment_flood(mock_ctx, chat_id, user_id, window)
    assert count1 == 1
    await asyncio.sleep(1.1)
    count2 = await increment_flood(mock_ctx, chat_id, user_id, window)
    assert count2 == 1
