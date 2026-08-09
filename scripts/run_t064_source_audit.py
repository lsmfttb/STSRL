#!/usr/bin/env python3
"""Run the frozen selected-source restore/context audit with 16 workers."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
import time
from typing import Any

from sts_combat_rl.commands.t064_curriculum import (
    finalize_source_audit,
    load_selected_source_pool,
)
from sts_combat_rl.sim.assisted_source_generation import (
    AssistedSourcePoolArtifact,
    assistance_schedule_by_level,
    verify_assisted_source_pool_restores,
)
from sts_combat_rl.sim.battle_start_pool import NaturalBattleStartPool
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


_POOL: NaturalBattleStartPool | None = None
_SELECTED: list[dict[str, Any]] = []


def _audit_one(index: int) -> dict[str, Any]:
    if _POOL is None:
        raise RuntimeError("T064 audit worker was not initialized")
    record = _POOL.records[index]
    descriptor = _SELECTED[index]
    component = str(descriptor["component"])
    artifact = AssistedSourcePoolArtifact(
        pool=NaturalBattleStartPool(
            source_run_count=1,
            terminal_run_count=1,
            truncated_run_count=0,
            source_controller_provenance=_POOL.source_controller_provenance,
            records=[record],
        ),
        assistance_level=component,
        assistance_schedule=assistance_schedule_by_level(component),
        policy_seed=42042,
    )
    report = verify_assisted_source_pool_restores(
        lambda: LightSpeedAdapter(seed=1, ascension=20),
        artifact,
    )
    return {
        "selected_index": index,
        "complete_identity_sha256": descriptor["complete_identity_sha256"],
        "status": "passed" if report.restore_ok else "failed",
        "problem": None if report.restore_ok else "; ".join(report.problems),
    }


def _parse_range(value: str, *, count: int) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("T064 shard range must use start:end")
    start, end = (int(part) for part in parts)
    if start < 0 or end < start or end > count:
        raise ValueError("T064 shard range is outside selected sources")
    return start, end


def _audit_shard(item: tuple[int, str]) -> dict[str, Any]:
    shard_index, record_range = item
    start, end = _parse_range(record_range, count=len(_SELECTED))
    started = time.perf_counter()
    results = [_audit_one(index) for index in range(start, end)]
    return {
        "shard_index": shard_index,
        "record_range": record_range,
        "workers": 1,
        "wall_clock_seconds": time.perf_counter() - started,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    if args.workers != 16:
        raise SystemExit("T064 source audit requires exactly 16 effective workers")
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    global _POOL, _SELECTED
    _POOL, _SELECTED = load_selected_source_pool(payload)
    ranges = payload.get("teacher_shard_ranges")
    if (
        not isinstance(ranges, list)
        or len(ranges) != 16
        or not all(isinstance(item, str) for item in ranges)
    ):
        raise SystemExit("T064 manifest has invalid frozen ranges")
    parsed_ranges = [_parse_range(item, count=len(_SELECTED)) for item in ranges]
    if (
        parsed_ranges[0][0] != 0
        or parsed_ranges[-1][1] != len(_SELECTED)
        or any(
            left[1] != right[0] for left, right in zip(parsed_ranges, parsed_ranges[1:])
        )
    ):
        raise SystemExit("T064 manifest shard ranges are not complete and contiguous")
    context = mp.get_context("fork")
    started = time.perf_counter()
    with context.Pool(processes=args.workers) as pool:
        shard_results = pool.map(_audit_shard, list(enumerate(ranges)), chunksize=1)
    wall = time.perf_counter() - started
    results = [result for shard in shard_results for result in shard["results"]]
    if [result["selected_index"] for result in results] != list(range(len(_SELECTED))):
        raise SystemExit(
            "T064 audit shards did not return each selected source exactly once"
        )
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"workers=16\nshards=16\nranges={','.join(ranges)}\n")
        stream.write(f"wall_clock_seconds={wall:.6f}\n")
        for shard in shard_results:
            stream.write(json.dumps(shard, sort_keys=True, separators=(",", ":")))
            stream.write("\n")
    finalized = finalize_source_audit(
        manifest_path=args.manifest,
        restore_results=results,
    )
    return 0 if finalized["complete_source_audit"]["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
