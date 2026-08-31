"""Execution helpers for the T079 fixed-cohort state-utilization stages."""

from __future__ import annotations

import multiprocessing
import os
import queue
import time
from collections.abc import Callable
from dataclasses import asdict
from multiprocessing.context import BaseContext
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.fixed_battle_evaluation import evaluate_fixed_cohort
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohortRecord,
    load_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.t079_state_utilization import (
    T079_BUDGETS,
    T079_RECORD_COUNT,
    T079_WORKER_COUNT,
    validate_stage_inventory,
)

ControllerFactory = Callable[[int], OnlineController]
AdapterFactory = Callable[[], CheckpointingSimulatorAdapter]

_WORK_ITEM: (
    tuple[
        FixedCohortRecord,
        int,
        ControllerFactory,
        AdapterFactory,
        ActionSpaceConfig,
        int,
        str,
        int,
        dict[str, Any],
        Any,
    ]
    | None
) = None


def run_t079_stage(
    *,
    cohort_path: Path,
    budget: int,
    controller_factory: ControllerFactory,
    adapter_factory: AdapterFactory,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    worker_count: int = T079_WORKER_COUNT,
    shard_count: int = T079_RECORD_COUNT,
    context: BaseContext | None = None,
) -> dict[str, Any]:
    """Run one T079 budget with one forked process per retained record.

    The native simulator and checkpoint handles are process-local, so each
    worker constructs its own adapter and controller after fork.  This helper
    deliberately requires the WSL/Linux ``fork`` context used by native stages;
    configured worker counts are never accepted as proof of execution.
    """

    if budget not in T079_BUDGETS:
        raise ValueError(f"unsupported T079 budget: {budget}")
    if worker_count != T079_WORKER_COUNT or shard_count != T079_RECORD_COUNT:
        raise ValueError("T079 requires exactly 16 workers and 16 one-record shards")
    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    if len(cohort.records) != T079_RECORD_COUNT:
        raise ValueError("T079 cohort must contain exactly 16 retained records")

    mp_context = context or multiprocessing.get_context()
    if mp_context.get_start_method() != "fork":
        raise RuntimeError("T079 native stage requires a fork-capable WSL context")
    result_queue: Any = mp_context.Queue()
    processes: list[Any] = []
    global _WORK_ITEM
    for record in cohort.records:
        _WORK_ITEM = (
            record,
            budget,
            controller_factory,
            adapter_factory,
            action_space,
            max_battle_steps,
            cohort.identity,
            cohort.source_pool_format_version,
            cohort.selection_config.to_dict(),
            result_queue,
        )
        process = mp_context.Process(target=_run_one_record)
        process.start()
        processes.append(process)
    _WORK_ITEM = None

    payloads: dict[int, dict[str, Any]] = {}
    for process in processes:
        process.join()
    for _ in processes:
        try:
            payload = result_queue.get(timeout=10)
        except queue.Empty as exc:
            raise RuntimeError(
                "T079 worker exited without an evidence payload"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("record_index"), int
        ):
            raise TypeError("T079 worker evidence payload is malformed")
        payloads[payload["record_index"]] = payload

    if sorted(payloads) != list(range(T079_RECORD_COUNT)):
        raise RuntimeError("T079 stage did not return every ordered cohort record")
    stage_rows = [payloads[index] for index in range(T079_RECORD_COUNT)]
    for row in stage_rows:
        row.update(
            {
                "worker_count": worker_count,
                "effective_worker_count": len(
                    {item["worker_pid"] for item in stage_rows}
                ),
                "shard_count": shard_count,
                "shard_index": row["record_index"],
                "shard_range": [row["record_index"], row["record_index"] + 1],
            }
        )
    starts = [float(row["worker_started_monotonic"]) for row in stage_rows]
    ends = [float(row["worker_finished_monotonic"]) for row in stage_rows]
    peak = _interval_peak(starts, ends)
    for row in stage_rows:
        row["observed_peak_concurrency"] = peak
    validate_stage_inventory(stage_rows, worker_count=worker_count)
    return {
        "schema_id": "t079-stage-execution-v1",
        "task_id": "T079",
        "budget": budget,
        "cohort_identity": cohort.identity,
        "record_count": len(stage_rows),
        "worker_count": worker_count,
        "shard_count": shard_count,
        "effective_worker_count": len({row["worker_pid"] for row in stage_rows}),
        "observed_peak_concurrency": peak,
        "records": stage_rows,
    }


def _run_one_record() -> None:
    if _WORK_ITEM is None:
        raise RuntimeError("T079 worker configuration was not inherited")
    (
        record,
        budget,
        controller_factory,
        adapter_factory,
        action_space,
        max_battle_steps,
        cohort_identity,
        source_pool_format_version,
        selection_config,
        result_queue,
    ) = _WORK_ITEM
    started = time.monotonic()
    try:
        controller = controller_factory(budget)
        report = evaluate_fixed_cohort(
            adapter_factory=adapter_factory,
            cohort_records=[record],
            controller=controller,
            cohort_identity=cohort_identity,
            source_pool_format_version=source_pool_format_version,
            selection_config=selection_config,
            action_space=action_space,
            max_battle_steps=max_battle_steps,
        )
        if len(report.battle_results) != 1:
            raise RuntimeError("T079 one-record worker returned the wrong result count")
        result = report.battle_results[0]
        payload = {
            "record_index": record.cohort_index,
            "worker_pid": os.getpid(),
            "worker_started_monotonic": started,
            "worker_finished_monotonic": time.monotonic(),
            "status": "completed" if result.termination_status != "error" else "error",
            "result": asdict(result),
            "problems": list(report.problems),
        }
    except Exception as exc:  # noqa: BLE001
        payload = {
            "record_index": record.cohort_index,
            "worker_pid": os.getpid(),
            "worker_started_monotonic": started,
            "worker_finished_monotonic": time.monotonic(),
            "status": "error",
            "result": None,
            "problems": [f"{type(exc).__name__}: {exc}"],
        }
    result_queue.put(payload)


def _interval_peak(starts: list[float], ends: list[float]) -> int:
    events = sorted([(start, 1) for start in starts] + [(end, -1) for end in ends])
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    return peak
