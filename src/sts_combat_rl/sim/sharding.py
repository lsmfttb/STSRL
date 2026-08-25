"""Small neutral helpers for deterministic record-range partitioning."""

from __future__ import annotations


def contiguous_ranges(count: int, shards: int = 16) -> tuple[str, ...]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("record count must be a non-negative integer")
    if isinstance(shards, bool) or not isinstance(shards, int) or shards <= 0:
        raise ValueError("shard count must be positive")
    base, remainder = divmod(count, shards)
    ranges: list[str] = []
    start = 0
    for index in range(shards):
        end = start + base + (1 if index < remainder else 0)
        ranges.append(f"{start}:{end}")
        start = end
    return tuple(ranges)
