#!/usr/bin/env python3
"""Collect the bounded T084 native internal-leaf candidate pool.

This is the executable native collection stage, not successor generation or
training.  It restores the exact T064 roots by their accepted seed/action
traces, runs each of the three frozen Search v2 arms for 100 simulations, and
retains the callback-boundary provenance emitted by the T084 native surface.
The continuation/calibration stage remains a separate, explicit input to the
audit runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import sys
import time
from collections.abc import Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
)
from sts_combat_rl.sim.battle_start_pool import (
    record_from_manifest,
    restore_battle_start_record,
)
from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueGuidanceScorer
from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    ARMS,
    COLLECTOR_SCHEMA_ID,
    EXPECTED_STATIC_CHECKPOINTS,
    WORKER_COUNT,
)

_ROOT_ROWS: list[dict[str, Any]] = []
_NATIVE_COMMIT = ""
_NATIVE_MODULE: Any | None = None
_SCORERS: dict[str, TorchPolicyValueGuidanceScorer] = {}
_CHECKPOINT_PATHS: dict[str, str] = {}


def _iter_json_values(path: Path) -> Iterable[object]:
    """Stream concatenated JSON values, including very long retained rows."""

    decoder = json.JSONDecoder()
    buffer = ""
    eof = False
    with path.open("r", encoding="utf-8", buffering=4 * 1024 * 1024) as stream:
        while True:
            if not eof:
                chunk = stream.read(4 * 1024 * 1024)
                if chunk:
                    buffer += chunk
                else:
                    eof = True
            position = 0
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position == len(buffer):
                    buffer = ""
                    break
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if eof:
                        raise ValueError(f"{path}: truncated or invalid JSON value")
                    buffer = buffer[position:]
                    break
                yield value
                position = end
            if eof and not buffer:
                return


def _source_path(raw: str) -> Path:
    return Path(raw.replace("D:\\", "/mnt/d/").replace("\\", "/"))


def _load_selected_roots(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = manifest.get("selected_sources")
    if not isinstance(selected, list) or len(selected) != 460:
        raise ValueError("T064 manifest must contain exactly 460 selected sources")
    wanted: dict[Path, set[int]] = {}
    for row in selected:
        if not isinstance(row, Mapping):
            raise TypeError("T064 selected source row is malformed")
        path = _source_path(str(row["source_path"]))
        wanted.setdefault(path, set()).add(int(row["source_record_index"]))

    found: dict[tuple[Path, int], dict[str, Any]] = {}
    for path, indexes in wanted.items():
        record_index = -1
        for value in _iter_json_values(path):
            if not isinstance(value, Mapping) or value.get("type") != "record":
                continue
            record = value.get("record")
            if not isinstance(record, Mapping):
                raise TypeError(f"{path}: record value is malformed")
            record_index += 1
            if record_index in indexes:
                found[(path, record_index)] = dict(record)
            if len(found) >= sum(len(items) for items in wanted.values()):
                break
    roots: list[dict[str, Any]] = []
    for selected_row in selected:
        path = _source_path(str(selected_row["source_path"]))
        index = int(selected_row["source_record_index"])
        raw = found.get((path, index))
        if raw is None:
            raise ValueError(f"missing selected T064 source record: {path}:{index}")
        roots.append(raw)
    return roots


def _native_actions(raw_actions: object) -> list[SimulatorAction]:
    if not isinstance(raw_actions, list):
        raise TypeError("native callback legal actions are not a list")
    actions: list[SimulatorAction] = []
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, Mapping):
            raise TypeError(f"native callback action {index} is malformed")
        scope, bits, kind = raw.get("scope"), raw.get("bits"), raw.get("kind")
        if (
            not isinstance(scope, str)
            or not isinstance(bits, int)
            or not isinstance(kind, str)
        ):
            raise TypeError(f"native callback action {index} lacks identity fields")
        actions.append(
            SimulatorAction(
                action_id=f"{scope}:{bits}",
                label=str(raw.get("label", "")),
                kind=kind,
                raw={
                    "scope": scope,
                    "bits": bits,
                    "idx1": raw.get("idx1"),
                    "idx2": raw.get("idx2"),
                    "idx3": raw.get("idx3"),
                },
            )
        )
    if not actions:
        raise ValueError("native callback exposed no legal actions")
    return actions


def _public_input(
    raw: Mapping[str, Any], actions: list[SimulatorAction], context: Any
) -> list[float | int | bool]:
    values = list(context.snapshot_features) + list(context.legal_action_features)
    if not all(isinstance(value, (bool, int, float)) for value in values):
        raise ValueError("native callback public model input contains non-scalars")
    return values


def _scorer_for_arm(arm: str) -> TorchPolicyValueGuidanceScorer | None:
    if arm == ARMS[0]:
        return None
    scorer = _SCORERS.get(arm)
    if scorer is None:
        path = _CHECKPOINT_PATHS[arm]
        scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(path)
        _SCORERS[arm] = scorer
    return scorer


def _work_one(task: tuple[int, str]) -> dict[str, Any]:
    root_index, arm = task
    started = time.monotonic()
    root_raw = _ROOT_ROWS[root_index]
    root = record_from_manifest(
        root_raw,
        label=f"T084 root {root_index}",
        allowed_distribution_kinds=frozenset({ASSISTED_RUN_DISTRIBUTION_KIND}),
        allow_assistance_history=True,
    )
    adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    snapshot, restore_method = restore_battle_start_record(adapter, root)
    source_identity = str(root_raw.get("source_complete_identity_sha256", ""))
    if not source_identity:
        source_identity = hashlib.sha256(
            json.dumps(root_raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    candidates: list[dict[str, Any]] = []
    scorer = _scorer_for_arm(arm)

    def policy_callback(raw: object, native_actions: object) -> list[float]:
        if scorer is None:
            raise AssertionError("unguided arm must not invoke a policy callback")
        actions = _native_actions(native_actions)
        if not isinstance(raw, Mapping):
            raise TypeError("native policy callback snapshot is malformed")
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        return [float(value) for value in scorer.score_actions(context)]

    def collect(
        checkpoint: object,
        raw: object,
        native_actions: object,
        depth: int,
        ordinal: int,
        path_fingerprint: str,
        digest: str,
        payload: str,
        rng: object,
    ) -> None:
        del checkpoint
        if not isinstance(raw, Mapping) or not isinstance(rng, Mapping):
            raise TypeError("native collector callback omitted structured state/RNG")
        actions = _native_actions(native_actions)
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        payload_value: object = payload
        try:
            decoded = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, Mapping):
            payload_value = dict(decoded)
        leaf_seed = "|".join(
            (source_identity, arm, digest, str(ordinal), path_fingerprint)
        )
        leaf_identity = hashlib.sha256(leaf_seed.encode()).hexdigest()
        candidates.append(
            {
                "sampling_arm": arm,
                "act": int(raw.get("act", root.snapshot_raw.get("act", 0))),
                "root_identity": source_identity,
                "exact_leaf_identity": f"t084-leaf-{leaf_identity}",
                "exact_hidden_state_payload": {
                    "canonical_native_payload": payload_value,
                    "retention_boundary": "opaque native checkpoint was captured at callback boundary and is process-local",
                    "restoration_status": "available_only_during_native_collector_callback",
                },
                "exact_state_digest": digest,
                "public_projection": dict(raw),
                "public_model_input": _public_input(raw, actions, context),
                "legal_actions": [
                    {"stable_id": action.action_id, "occurrence": index}
                    for index, action in enumerate(actions)
                ],
                "source_complete_identity_sha256": source_identity,
                "depth": depth,
                "callback_ordinal": ordinal,
                "path_fingerprint": path_fingerprint,
                "rng_provenance": dict(rng),
            }
        )

    result = adapter.battle_search_v2_with_leaf_collection(
        snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
        collector_config={
            "schema_id": COLLECTOR_SCHEMA_ID,
            "sampling_arm": arm,
            "native_commit": _NATIVE_COMMIT,
        },
        leaf_collector_callback=collect,
    )
    row = {
        "sampling_arm": arm,
        "root_index": root_index,
        "root_identity": source_identity,
        "source_complete_identity_sha256": source_identity,
        "simulations": 100,
        "status": "complete",
        "restore_method": restore_method,
        "candidate_count": len(candidates),
        "root_action": result.get("root_action"),
        "root_statistics": result.get("root_statistics"),
        "candidate_rows": candidates,
        "native_commit": _NATIVE_COMMIT,
        "wall_clock_seconds": time.monotonic() - started,
    }
    return row


def _worker_init(
    roots: list[dict[str, Any]], native_commit: str, checkpoint_paths: dict[str, str]
) -> None:
    global _ROOT_ROWS, _NATIVE_COMMIT, _NATIVE_MODULE, _CHECKPOINT_PATHS
    _ROOT_ROWS = roots
    _NATIVE_COMMIT = native_commit
    _CHECKPOINT_PATHS = checkpoint_paths
    import slaythespire

    _NATIVE_MODULE = slaythespire


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t064-manifest", type=Path, required=True)
    parser.add_argument("--native-build", type=Path, required=True)
    parser.add_argument("--native-commit", required=True)
    parser.add_argument("--static-64001", type=Path, required=True)
    parser.add_argument("--static-64002", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=WORKER_COUNT)
    args = parser.parse_args()
    if args.workers != WORKER_COUNT:
        raise SystemExit("T084 collector requires exactly 16 workers")
    if not args.native_build.is_dir():
        raise SystemExit(f"native build directory is missing: {args.native_build}")
    sys.path.insert(0, str(args.native_build))
    roots = _load_selected_roots(args.t064_manifest)
    checkpoint_paths = {
        "prior_only_static_64001": str(args.static_64001),
        "prior_only_static_64002": str(args.static_64002),
    }
    tasks = [(root_index, arm) for root_index in range(len(roots)) for arm in ARMS]
    started = time.monotonic()
    root_runs: list[dict[str, Any]] = []
    failures: list[str] = []
    context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=args.workers,
        mp_context=context,
        initializer=_worker_init,
        initargs=(roots, args.native_commit, checkpoint_paths),
    ) as pool:
        futures = {pool.submit(_work_one, task): task for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            root_index, arm = futures[future]
            try:
                root_runs.append(future.result())
            except Exception as exc:  # noqa: BLE001 - retained as per-root evidence
                failures.append(f"{arm}/root{root_index}: {type(exc).__name__}: {exc}")
            if completed % 16 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "completed": completed,
                            "total": len(tasks),
                            "failures": len(failures),
                            "wall_clock_seconds": time.monotonic() - started,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    root_runs.sort(
        key=lambda row: (str(row.get("sampling_arm")), int(row.get("root_index", -1)))
    )
    candidate_rows = [
        candidate for run in root_runs for candidate in run.get("candidate_rows", [])
    ]
    execution = {
        "schema_id": COLLECTOR_SCHEMA_ID,
        "generation_mode": "native_runtime_collector",
        "native_commit": args.native_commit,
        "search_simulations_per_root": 100,
        "worker_count": args.workers,
        "effective_worker_count": args.workers,
        "root_runs": [
            {key: value for key, value in run.items() if key != "candidate_rows"}
            for run in root_runs
        ],
        "candidate_rows": candidate_rows,
        "calibration_rows": [],
        "formal_rows": [],
        "arm_configs": {
            "unguided_search_v2": {
                "policy_prior": False,
                "leaf_value": False,
                "checkpoint_sha256": None,
            },
            "prior_only_static_64001": {
                "policy_prior": True,
                "leaf_value": False,
                "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                    "prior_only_static_64001"
                ][0],
            },
            "prior_only_static_64002": {
                "policy_prior": True,
                "leaf_value": False,
                "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                    "prior_only_static_64002"
                ][0],
            },
        },
        "parity": {
            "available": False,
            "passed": False,
            "reason": "collector candidate stage does not substitute for the required deterministic off/on 16-root parity preflight",
        },
        "failures": failures,
        "shards": [
            {
                "worker_count": args.workers,
                "task_count": len(tasks),
                "task_ranges": "root indices 0..459 x three arms",
                "wall_clock_seconds": time.monotonic() - started,
            }
        ],
        "wall_clock_seconds": time.monotonic() - started,
    }
    _write_json(args.output, execution)
    return 0 if not failures and len(root_runs) == len(tasks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
