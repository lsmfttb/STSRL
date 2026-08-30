"""Run the T078 restore-only audit over the exact retained T075 cohort."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.non_combat_learning import file_sha256
from sts_combat_rl.sim.t077_continuation import (
    T075_SELECTED_STATES,
    artifact_path,
    iter_selected_states_strict,
    validate_selected_states_320,
    verify_artifact_identity,
)
from sts_combat_rl.sim.t078_restore_fidelity import audit_restore_fidelity_shard

T078_TASK_ID = "T078"
T078_APPROVED_SPEC = "727023c6bc90e0e49538534f9758e466f6becf7b"


def _worker(payload: tuple[tuple[Any, ...], bool]) -> dict[str, Any]:
    states, exercise_branch_restore = payload
    return audit_restore_fidelity_shard(
        states, exercise_branch_restore=exercise_branch_restore
    )


def run_t078_restore_fidelity_audit(
    repository_root: Path,
    output_path: Path,
    *,
    worker_count: int = 16,
    exercise_branch_restore: bool = False,
) -> dict[str, Any]:
    """Audit all retained source states without target continuation work."""

    if worker_count < 1 or worker_count > 16:
        raise ValueError("T078 worker_count must be in 1..16")
    root = Path(repository_root).resolve()
    selected_path = artifact_path(root, T075_SELECTED_STATES)
    verify_artifact_identity(root, T075_SELECTED_STATES)
    cohort = validate_selected_states_320(selected_path)
    states = tuple(iter_selected_states_strict(selected_path))
    if len(states) != 320:
        raise ValueError("T078 retained cohort must contain exactly 320 states")
    if tuple(state.selected_state_index for state in states) != tuple(range(320)):
        raise ValueError("T078 retained cohort indices must be 0..319")
    if 320 % worker_count:
        raise ValueError("T078 worker_count must divide the retained cohort")

    shard_size = 320 // worker_count
    payloads = tuple(
        (
            states[offset : offset + shard_size],
            exercise_branch_restore,
        )
        for offset in range(0, len(states), shard_size)
    )
    started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=worker_count, mp_context=mp.get_context("spawn")
    ) as executor:
        shards = tuple(executor.map(_worker, payloads))
    observed_pids = sorted({int(shard["pid"]) for shard in shards})
    rows = [row for shard in shards for row in shard["rows"]]
    failures = [row for row in rows if not row["passed"]]
    report = {
        "schema_id": "t078-restore-fidelity-audit-v1",
        "schema_version": 1,
        "task_id": T078_TASK_ID,
        "approved_spec": T078_APPROVED_SPEC,
        "audit_kind": "restore_only",
        "counterfactual_continuation_executed": False,
        "candidate_replacement_performed": False,
        "retained_selected_states": {
            "path": T075_SELECTED_STATES.path,
            "sha256": T075_SELECTED_STATES.sha256,
            "size_bytes": T075_SELECTED_STATES.size_bytes,
            "cohort": cohort,
        },
        "worker_count": worker_count,
        "effective_process_count": len(observed_pids),
        "worker_pids": observed_pids,
        "shards": [
            {
                key: shard[key]
                for key in (
                    "pid",
                    "cpu_seconds",
                    "selected_state_start",
                    "selected_state_end",
                )
            }
            for shard in shards
        ],
        "exercise_branch_restore": exercise_branch_restore,
        "state_count": len(rows),
        "mismatch_count": len(failures),
        "failures": failures,
        "wall_clock_seconds": time.perf_counter() - started,
        "passed": not failures and len(observed_pids) == worker_count,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report["artifact"] = {
        "path": str(output_path),
        "sha256": file_sha256(output_path),
        "size_bytes": output_path.stat().st_size,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--exercise-branch-restore", action="store_true")
    args = parser.parse_args(argv)
    report = run_t078_restore_fidelity_audit(
        args.repository_root,
        args.output,
        worker_count=args.workers,
        exercise_branch_restore=args.exercise_branch_restore,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
