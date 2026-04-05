import asyncio
import time

from src.cache.local_cache import AsyncSnapshotCache


async def benchmark_cache():

    cache = AsyncSnapshotCache(max_size=100000)
    num_ops = 50000

    print(f"--- Benchmarking AsyncSnapshotCache with {num_ops} ops ---")

    start = time.perf_counter()
    for i in range(num_ops):
        await cache.set(f"key{i}", i)
    end = time.perf_counter()
    duration = end - start
    ops_per_sec = num_ops / duration
    print(f"Sequential Writes: {ops_per_sec:,.0f} OPS ({duration:.3f}s total)")

    start = time.perf_counter()
    for i in range(num_ops):
        await cache.get(f"key{i}")
    end = time.perf_counter()
    duration = end - start
    ops_per_sec = num_ops / duration
    print(f"Sequential Reads: {ops_per_sec:,.0f} OPS ({duration:.3f}s total)")

    start = time.perf_counter()
    tasks = [cache.get(f"key{i % num_ops}") for i in range(num_ops)]
    await asyncio.gather(*tasks)
    end = time.perf_counter()
    duration = end - start
    ops_per_sec = num_ops / duration
    print(f"Concurrent Reads: {ops_per_sec:,.0f} OPS ({duration:.3f}s total)")

    start = time.perf_counter()
    await cache.save_snapshot()
    end = time.perf_counter()
    duration = end - start
    print(f"Snapshot (50k items): {duration:.3f}s total")

    start = time.perf_counter()
    await cache.load_snapshot()
    end = time.perf_counter()
    duration = end - start
    print(f"Load (50k items): {duration:.3f}s total")

    stats = await cache.stats()
    print(f"Final Count: {stats['size']}")


if __name__ == "__main__":
    asyncio.run(benchmark_cache())
