#!/usr/bin/env python3
"""Collect the bounded T084 native internal-leaf candidate pool.

This is the executable native collection stage, not successor generation or
training.  It restores the exact T064 roots by their accepted seed/action
traces, runs each of the three frozen Search v2 arms for 100 simulations, and
retains the callback-boundary provenance emitted by the T084 native surface.
The selected-leaf replay is a second pass in this same executable: the first
pass retains an occupancy pool, then selected occurrence keys are replayed and
their callback-boundary checkpoints are consumed immediately for continuation
targets.  No process-local checkpoint from the first pass is serialized or
used by the second pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import sys
import time
from collections import Counter
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
from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    ARMS,
    COLLECTOR_SCHEMA_ID,
    EXPECTED_STATIC_CHECKPOINTS,
    WORKER_COUNT,
    derive_replicate_seed,
    select_repetition_count,
    validate_replicate,
)

_ROOT_ROWS: list[dict[str, Any]] = []
_NATIVE_COMMIT = ""
_NATIVE_MODULE: Any | None = None
_SCORERS: dict[str, Any] = {}
_CHECKPOINT_PATHS: dict[str, str] = {}
_PASS_MODE = "candidate"
_TARGET_SPECS: dict[str, dict[str, Any]] = {}
_SELECTION_POLICY = "canonical-hidden-payload-v1-root-first-hash-v1"


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


def _iter_selected_record_lines(
    path: Path, selected_indices: set[int]
) -> Iterable[tuple[int, Mapping[str, Any]]]:
    """Scan accepted JSONL bytes but decode only the bounded selected rows."""

    found: set[int] = set()
    record_index = -1
    with path.open("rb", buffering=4 * 1024 * 1024) as stream:
        for line in stream:
            if b'"type": "record"' not in line:
                continue
            record_index += 1
            if record_index not in selected_indices:
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping) or value.get("type") != "record":
                raise ValueError(f"{path}: selected record line is malformed")
            record = value.get("record")
            if not isinstance(record, Mapping):
                raise TypeError(f"{path}: selected record payload is malformed")
            found.add(record_index)
            yield record_index, record
            if found == selected_indices:
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
    wanted_count = sum(len(items) for items in wanted.values())
    for path, indexes in wanted.items():
        for record_index, record in _iter_selected_record_lines(path, indexes):
            selected_identity = next(
                item["complete_identity_sha256"]
                for item in selected
                if _source_path(str(item["source_path"])) == path
                and int(item["source_record_index"]) == record_index
            )
            found[(path, record_index)] = {
                **dict(record),
                "_t084_source_identity": selected_identity,
            }
        if len(found) >= wanted_count:
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


def _scorer_for_arm(arm: str) -> Any | None:
    if arm == ARMS[0]:
        return None
    scorer = _SCORERS.get(arm)
    if scorer is None:
        from sts_combat_rl.sim.torch_policy_value import (
            TorchPolicyValueGuidanceScorer,
        )

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
    source_identity = str(root_raw.get("_t084_source_identity", ""))
    if not source_identity:
        source_identity = hashlib.sha256(
            json.dumps(root_raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    candidates: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    consumed_target_ids: set[str] = set()
    callback_count = 0
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
        nonlocal callback_count
        callback_count += 1
        if not isinstance(raw, Mapping) or not isinstance(rng, Mapping):
            raise TypeError("native collector callback omitted structured state/RNG")
        if not isinstance(payload, str) or not payload:
            raise ValueError(
                "native collector callback omitted canonical hidden payload"
            )
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
        # The native canonical payload is the formal hidden-state identity.  The
        # native digest is only an index; validate_collector_execution performs
        # the digest-bucket collision check.  Ordinal/path remain occupancy
        # provenance and must not create independent formal states.
        leaf_identity = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        exact_identity = f"t084-hidden-state-{leaf_identity}"
        occurrence_seed = "|".join(
            (source_identity, arm, digest, str(ordinal), path_fingerprint)
        )
        occurrence_key = hashlib.sha256(occurrence_seed.encode()).hexdigest()
        base_row = {
            "sampling_arm": arm,
            "act": int(raw.get("act", root.snapshot_raw.get("act", 0))),
            "root_identity": source_identity,
            "exact_leaf_identity": exact_identity,
            "exact_hidden_state_payload": {
                "canonical_native_payload": payload_value,
                "canonical_native_payload_json": payload,
                "identity_definition": "sha256(canonical_native_payload UTF-8 bytes)",
                "occupancy_duplicate": False,
                "retention_boundary": "opaque native checkpoint captured at callback boundary",
                "restoration_status": "candidate_only_until_selected",
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
            "occurrence_key": occurrence_key,
            "occupancy": {
                "native_digest_index": digest,
                "callback_ordinal": ordinal,
                "path_fingerprint": path_fingerprint,
            },
            "rng_provenance": dict(rng),
        }
        if _PASS_MODE == "candidate":
            candidates.append(base_row)
            return
        target_spec = _selected_target_for_occurrence(
            _TARGET_SPECS, exact_identity, occurrence_key, consumed_target_ids
        )
        if target_spec is None:
            return
        consumed_target_ids.add(exact_identity)
        base_row["exact_hidden_state_payload"]["restoration_status"] = (
            "consumed_in_callback_for_continuation_replicates"
        )
        replicates: list[dict[str, Any]] = []
        for replicate_index in range(1, 257):
            seed_provenance = derive_replicate_seed(
                _NATIVE_COMMIT,
                source_identity,
                arm,
                exact_identity,
                replicate_index,
            )
            continuation = adapter.evaluate_leaf_continuation(
                checkpoint,
                search_action_seed=seed_provenance["seed"],
                max_transitions=2048,
                include_potions=False,
            )
            replicates.append(
                {
                    **dict(continuation),
                    "replicate_index": replicate_index,
                    "seed_provenance": seed_provenance,
                    "terminal": continuation.get("terminal") is True,
                    "cap_hit": continuation.get("cap_hit") is True,
                    "transition_count": continuation.get("transition_count"),
                    "terminal_evaluate_end_state": continuation.get(
                        "terminal_evaluate_end_state"
                    ),
                }
            )
        base_row["target_kind"] = target_spec["target_kind"]
        base_row["replicates"] = replicates
        base_row["selected_repetition_count"] = 256
        target_rows.append(base_row)

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
        "worker_pid": os.getpid(),
        "sampling_arm": arm,
        "root_index": root_index,
        "source_root_index": root_raw.get("_t084_parity_source_index", root_index),
        "root_identity": source_identity,
        "source_complete_identity_sha256": source_identity,
        "simulations": 100,
        "status": "complete",
        "restore_method": restore_method,
        "candidate_count": callback_count,
        "root_action": result.get("root_action"),
        "root_statistics": result.get("root_rows"),
        "native_root_statistics": result.get("root_rows"),
        "candidate_rows": candidates,
        "target_rows": target_rows,
        "native_commit": _NATIVE_COMMIT,
        "wall_clock_seconds": time.monotonic() - started,
    }
    return row


def _worker_init(
    roots: list[dict[str, Any]],
    native_commit: str,
    checkpoint_paths: dict[str, str],
    pass_mode: str,
    target_specs: dict[str, dict[str, Any]],
) -> None:
    global _ROOT_ROWS, _NATIVE_COMMIT, _NATIVE_MODULE, _CHECKPOINT_PATHS
    global _PASS_MODE, _TARGET_SPECS
    _ROOT_ROWS = roots
    _NATIVE_COMMIT = native_commit
    _CHECKPOINT_PATHS = checkpoint_paths
    _PASS_MODE = pass_mode
    _TARGET_SPECS = target_specs
    import slaythespire

    _NATIVE_MODULE = slaythespire


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _run_pass(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
    pass_mode: str,
    target_specs: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], float, dict[str, Any]]:
    tasks = [(root_index, arm) for root_index in range(len(roots)) for arm in ARMS]
    started = time.monotonic()
    root_runs: list[dict[str, Any]] = []
    failures: list[str] = []
    context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_worker_init,
        initargs=(roots, native_commit, checkpoint_paths, pass_mode, target_specs),
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
                            "pass": pass_mode,
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
    worker_pids = sorted(
        {
            int(row["worker_pid"])
            for row in root_runs
            if isinstance(row.get("worker_pid"), int)
        }
    )
    worker_evidence = {
        "configured_worker_count": workers,
        "observed_worker_count": len(worker_pids),
        "effective_worker_count": len(worker_pids),
        "worker_pids": worker_pids,
        "host_logical_cpu_count": os.cpu_count(),
    }
    return root_runs, failures, time.monotonic() - started, worker_evidence


def _work_parity_one(task: tuple[int, str]) -> dict[str, Any]:
    root_index, arm = task
    root_raw = _ROOT_ROWS[root_index]
    root = record_from_manifest(
        root_raw,
        label=f"T084 parity root {root_index}",
        allowed_distribution_kinds=frozenset({ASSISTED_RUN_DISTRIBUTION_KIND}),
        allow_assistance_history=True,
    )
    source_identity = str(root_raw["_t084_source_identity"])
    scorer = _scorer_for_arm(arm)

    def policy_callback(raw: object, native_actions: object) -> list[float]:
        if scorer is None:
            raise AssertionError("unguided arm must not invoke a policy callback")
        actions = _native_actions(native_actions)
        if not isinstance(raw, Mapping):
            raise TypeError("native parity policy snapshot is malformed")
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        return [float(value) for value in scorer.score_actions(context)]

    off_adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    off_snapshot, _ = restore_battle_start_record(off_adapter, root)
    on_adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    on_snapshot, _ = restore_battle_start_record(on_adapter, root)
    observed_rng: list[dict[str, Any]] = []

    def collect_rng(*values: object) -> None:
        if values and isinstance(values[-1], Mapping):
            observed_rng.append(dict(values[-1]))

    off = off_adapter.battle_search_v2(
        off_snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
    )
    on = on_adapter.battle_search_v2_with_leaf_collection(
        on_snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
        collector_config={
            "schema_id": COLLECTOR_SCHEMA_ID,
            "sampling_arm": arm,
            "native_commit": _NATIVE_COMMIT,
            "parity_preflight": True,
        },
        leaf_collector_callback=collect_rng,
    )
    expected_rng = {
        "battle_context_seed": root.source_seed,
        "battle_context_floor_num": int(off_snapshot.raw["floor_num"]),
        "search_action_rng_seed_rule": (
            "BattleScumSearcher2::randGen seeded from BattleContext.seed+floorNum"
        ),
    }
    rng_equal = bool(observed_rng) and all(
        value == expected_rng for value in observed_rng
    )
    return {
        "root_index": root_index,
        "worker_pid": os.getpid(),
        "root_identity": source_identity,
        "sampling_arm": arm,
        "act": int(root_raw["act"]),
        "root_action_equal": off.get("root_action") == on.get("root_action"),
        "root_statistics_equal": off.get("root_rows") == on.get("root_rows"),
        "native_root_statistics_equal": off.get("root_rows") == on.get("root_rows"),
        "rng_semantics_equal": rng_equal,
        "off_native_root_statistics": off.get("root_rows"),
        "on_native_root_statistics": on.get("root_rows"),
        "material_outputs_equal": (
            off.get("root_action") == on.get("root_action")
            and off.get("root_rows") == on.get("root_rows")
            and rng_equal
        ),
        "off_root_action": off.get("root_action"),
        "on_root_action": on.get("root_action"),
        "observed_rng_count": len(observed_rng),
        "expected_rng": expected_rng,
    }


def _run_parity(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
) -> tuple[dict[str, Any], list[str], float]:
    source_indices = _select_parity_root_indices(roots)
    parity_roots = [roots[index] for index in source_indices]
    for parity_index, source_index in enumerate(source_indices):
        parity_roots[parity_index] = {
            **parity_roots[parity_index],
            "_t084_parity_source_index": source_index,
        }
    tasks = [
        (root_index, arm) for root_index in range(len(parity_roots)) for arm in ARMS
    ]
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_worker_init,
        initargs=(parity_roots, native_commit, checkpoint_paths, "parity", {}),
    ) as pool:
        futures = {pool.submit(_work_parity_one, task): task for task in tasks}
        for future in as_completed(futures):
            root_index, arm = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - retained as stage evidence
                failures.append(f"{arm}/root{root_index}: {type(exc).__name__}: {exc}")
    rows.sort(key=lambda row: (str(row["sampling_arm"]), int(row["root_index"])))
    worker_pids = sorted(
        {
            int(row["worker_pid"])
            for row in rows
            if isinstance(row.get("worker_pid"), int)
        }
    )
    worker_evidence = {
        "configured_worker_count": workers,
        "observed_worker_count": len(worker_pids),
        "effective_worker_count": len(worker_pids),
        "worker_pids": worker_pids,
        "host_logical_cpu_count": os.cpu_count(),
    }
    parity = {
        "available": not failures,
        "passed": (
            not failures
            and len(rows) == len(tasks)
            and all(row["material_outputs_equal"] for row in rows)
        ),
        "checked_root_count": len({row["root_index"] for row in rows}),
        "arms": sorted({row["sampling_arm"] for row in rows}),
        "acts": sorted({row["act"] for row in rows}),
        "worker_count": workers,
        "effective_worker_count": len(worker_pids),
        "worker_evidence": worker_evidence,
        "task_count": len(tasks),
        "task_ranges": "first eight Act1 and first eight Act2 source roots x three arms",
        "root_identities": [row["root_identity"] for row in rows],
        "act_counts": {
            str(act): sum(1 for row in rows if row["act"] == act) for act in (1, 2)
        },
        "material_outputs_equal": bool(rows)
        and all(row["material_outputs_equal"] for row in rows),
        "root_action_equal": bool(rows)
        and all(row["root_action_equal"] for row in rows),
        "root_statistics_equal": bool(rows)
        and all(row["root_statistics_equal"] for row in rows),
        "rng_semantics_equal": bool(rows)
        and all(row["rng_semantics_equal"] for row in rows),
        "rows": rows,
        "failures": failures,
        "wall_clock_seconds": time.monotonic() - started,
    }
    return parity, failures, time.monotonic() - started


def _select_parity_root_indices(roots: list[dict[str, Any]]) -> list[int]:
    """Choose a stable 8+8 Act parity subset, independent of source ordering."""

    act1 = [index for index, root in enumerate(roots) if int(root.get("act", 0)) == 1]
    act2 = [index for index, root in enumerate(roots) if int(root.get("act", 0)) == 2]
    if len(act1) < 8 or len(act2) < 8:
        raise ValueError("T084 parity requires at least eight roots from each Act")
    return act1[:8] + act2[:8]


def _leaf_rank(row: Mapping[str, Any]) -> str:
    value = "|".join(
        (
            str(row["source_complete_identity_sha256"]),
            str(row["sampling_arm"]),
            str(row["exact_leaf_identity"]),
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_payload(row: Mapping[str, Any]) -> str:
    hidden = row.get("exact_hidden_state_payload")
    if not isinstance(hidden, Mapping):
        raise TypeError("candidate lacks exact hidden state payload")
    payload = hidden.get("canonical_native_payload_json")
    if not isinstance(payload, str) or not payload:
        raise ValueError("candidate lacks retained canonical native payload bytes")
    expected_identity = (
        f"t084-hidden-state-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
    )
    if str(row.get("exact_leaf_identity")) != expected_identity:
        raise ValueError(
            "candidate exact hidden identity is not derived from canonical payload"
        )
    return payload


def _selected_target_for_occurrence(
    target_specs: Mapping[str, Mapping[str, Any]],
    exact_identity: str,
    occurrence_key: str,
    consumed_target_ids: set[str],
) -> Mapping[str, Any] | None:
    """Return a target only for its selected occurrence, once per replay."""

    spec = target_specs.get(exact_identity)
    if (
        not isinstance(spec, Mapping)
        or spec.get("occurrence_key") != occurrence_key
        or exact_identity in consumed_target_ids
    ):
        return None
    return spec


def _ordered_cell_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique states in deterministic root-first then hash order."""

    by_identity: dict[str, list[dict[str, Any]]] = {}
    digest_payloads: dict[str, str] = {}
    for row in rows:
        identity = str(row["exact_leaf_identity"])
        payload = _canonical_payload(row)
        digest = str(row.get("exact_state_digest", ""))
        previous_payload = digest_payloads.setdefault(digest, payload)
        if previous_payload != payload:
            raise ValueError(f"native digest collision for {digest}")
        by_identity.setdefault(identity, []).append(row)

    remaining = set(by_identity)
    chosen: list[dict[str, Any]] = []
    used_roots: set[str] = set()
    while remaining:
        candidates = [
            (identity, row)
            for identity in remaining
            for row in by_identity[identity]
            if str(row.get("root_identity", "")) not in used_roots
        ]
        if not candidates:
            candidates = [
                (identity, row)
                for identity in remaining
                for row in by_identity[identity]
            ]
        identity, row = min(
            candidates,
            key=lambda item: (
                _leaf_rank(item[1]),
                str(item[1].get("root_identity", "")),
                item[0],
            ),
        )
        chosen.append(row)
        remaining.remove(identity)
        used_roots.add(str(row.get("root_identity", "")))
    return chosen


def _select_cell(
    rows: list[dict[str, Any]],
    count: int,
    selected: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select unique hidden states with distinct source roots as the first phase."""

    ordered = [
        row
        for row in _ordered_cell_rows(rows)
        if str(row["exact_leaf_identity"]) not in selected
    ]
    chosen = ordered[:count]
    used_roots = {str(row.get("root_identity", "")) for row in chosen}
    for row in chosen:
        selected[str(row["exact_leaf_identity"])] = {
            "target_kind": "pending",
            "occurrence_key": str(row["occurrence_key"]),
            "root_identity": str(row["root_identity"]),
            "sampling_arm": str(row["sampling_arm"]),
            "act": int(row["act"]),
        }
    return chosen, {
        "requested": count,
        "selected": len(chosen),
        "distinct_source_roots": len(used_roots),
        "root_first_phase_completed": len(used_roots) == len(chosen),
        "hash_tie_break": "sha256(source_complete_identity_sha256|sampling_arm|exact_leaf_identity)",
    }


def _select_target_specs_with_policy(
    candidate_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Select calibration/formal identities, never counting occupancy duplicates."""

    selected: dict[str, dict[str, Any]] = {}
    cells: list[dict[str, Any]] = []
    for arm in ARMS:
        for act, count, kind in ((1, 18, "calibration"), (2, 14, "calibration")):
            chosen, detail = _select_cell(
                [
                    row
                    for row in candidate_rows
                    if row.get("sampling_arm") == arm and row.get("act") == act
                ],
                count,
                selected,
            )
            for row in chosen:
                identity = str(row["exact_leaf_identity"])
                selected[identity] = {**selected[identity], "target_kind": kind}
            cells.append({"arm": arm, "act": act, "kind": kind, **detail})
        for act, count in ((1, 178), (2, 142)):
            chosen, detail = _select_cell(
                [
                    row
                    for row in candidate_rows
                    if row.get("sampling_arm") == arm and row.get("act") == act
                ],
                count,
                selected,
            )
            for row in chosen:
                identity = str(row["exact_leaf_identity"])
                selected[identity] = {**selected[identity], "target_kind": "formal"}
            cells.append({"arm": arm, "act": act, "kind": "formal", **detail})
    return selected, {
        "schema_id": _SELECTION_POLICY,
        "identity": "sha256(canonical_native_payload UTF-8 bytes)",
        "digest_role": "index-only-with-canonical-payload-collision-check",
        "occupancy_duplicates": "retained in candidate_rows, excluded from identity counts and target selection",
        "root_policy": "distinct source roots first, then versioned hash ranking",
        "selected_occurrences": [
            {
                "exact_leaf_identity": identity,
                "target_kind": spec["target_kind"],
                "occurrence_key": spec["occurrence_key"],
                "root_identity": spec["root_identity"],
            }
            for identity, spec in sorted(selected.items())
        ],
        "cells": cells,
    }


def _select_target_specs(candidate_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Compatibility wrapper for focused callers."""

    selected, _ = _select_target_specs_with_policy(candidate_rows)
    return {identity: str(spec["target_kind"]) for identity, spec in selected.items()}


def _target_row_has_full_replicates(row: Mapping[str, Any]) -> bool:
    replicates = row.get("replicates")
    return (
        isinstance(replicates, list)
        and len(replicates) == 256
        and all(
            isinstance(replica, Mapping) and validate_replicate(replica)
            for replica in replicates
        )
    )


def _target_spec_for_row(row: Mapping[str, Any], target_kind: str) -> dict[str, Any]:
    return {
        "target_kind": target_kind,
        "occurrence_key": str(row["occurrence_key"]),
        "root_identity": str(row["root_identity"]),
        "sampling_arm": str(row["sampling_arm"]),
        "act": int(row["act"]),
    }


def _backfill_specs(
    candidate_rows: list[dict[str, Any]],
    attempted_ids: set[str],
    accepted_by_cell: Mapping[tuple[str, int, str], list[dict[str, Any]]],
    reserved_ids: set[str],
) -> dict[str, dict[str, Any]]:
    quotas = {
        **{
            (arm, act, "calibration"): count
            for arm in ARMS
            for act, count in ((1, 18), (2, 14))
        },
        **{
            (arm, act, "formal"): count
            for arm in ARMS
            for act, count in ((1, 178), (2, 142))
        },
    }
    specs: dict[str, dict[str, Any]] = {}
    for (arm, act, target_kind), quota in quotas.items():
        deficit = quota - len(accepted_by_cell.get((arm, act, target_kind), []))
        if deficit <= 0:
            continue
        cell_rows = _ordered_cell_rows(
            [
                row
                for row in candidate_rows
                if row.get("sampling_arm") == arm and row.get("act") == act
            ]
        )
        for row in cell_rows:
            identity = str(row["exact_leaf_identity"])
            if identity in attempted_ids or identity in reserved_ids:
                continue
            specs[identity] = _target_spec_for_row(row, target_kind)
            reserved_ids.add(identity)
            if (
                len(
                    [
                        spec
                        for spec in specs.values()
                        if spec["sampling_arm"] == arm
                        and spec["act"] == act
                        and spec["target_kind"] == target_kind
                    ]
                )
                >= deficit
            ):
                break
    return specs


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
    candidate_runs, candidate_failures, candidate_wall, candidate_workers = _run_pass(
        roots,
        checkpoint_paths,
        args.native_commit,
        args.workers,
        "candidate",
        {},
    )
    candidate_rows = [
        candidate
        for run in candidate_runs
        for candidate in run.get("candidate_rows", [])
    ]
    occupancy_counts = Counter(
        str(row.get("exact_leaf_identity")) for row in candidate_rows
    )
    for row in candidate_rows:
        hidden = row.get("exact_hidden_state_payload")
        if isinstance(hidden, dict):
            identity = str(row.get("exact_leaf_identity"))
            hidden["occupancy_duplicate"] = occupancy_counts[identity] > 1
            hidden["occupancy_count"] = occupancy_counts[identity]
    target_specs, selection_policy = _select_target_specs_with_policy(candidate_rows)
    target_runs: list[dict[str, Any]] = []
    target_failures: list[str] = []
    target_wall = 0.0
    replay_passes: list[dict[str, Any]] = []
    target_worker_evidence: list[dict[str, Any]] = []
    attempted_ids: set[str] = set()
    accepted_by_cell: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    accepted_ids: set[str] = set()
    target_attempts: list[dict[str, Any]] = []
    current_specs = target_specs
    while current_specs:
        scheduled_ids = set(current_specs)
        pass_started = time.monotonic()
        pass_runs, pass_failures, pass_wall, pass_workers = _run_pass(
            roots,
            checkpoint_paths,
            args.native_commit,
            args.workers,
            "selected_leaf_continuation",
            current_specs,
        )
        target_runs = pass_runs
        target_failures.extend(pass_failures)
        target_wall += pass_wall
        attempted_ids.update(scheduled_ids)
        target_worker_evidence.append(pass_workers)
        pass_rows = [
            target for run in pass_runs for target in run.get("target_rows", [])
        ]
        returned_ids = {str(row["exact_leaf_identity"]) for row in pass_rows}
        for identity, spec in current_specs.items():
            if identity in returned_ids:
                continue
            target_attempts.append(
                {
                    "exact_leaf_identity": identity,
                    "occurrence_key": spec.get("occurrence_key"),
                    "root_identity": spec.get("root_identity"),
                    "sampling_arm": spec.get("sampling_arm"),
                    "act": spec.get("act"),
                    "target_kind": spec.get("target_kind"),
                    "valid_256_replicates": False,
                    "replay_pass": len(replay_passes) + 1,
                    "backfill_used": len(replay_passes) > 0,
                    "error": "scheduled occurrence produced no target row; see pass failures",
                }
            )
        for row in pass_rows:
            identity = str(row["exact_leaf_identity"])
            cell = (
                str(row["sampling_arm"]),
                int(row["act"]),
                str(row["target_kind"]),
            )
            attempted_ids.add(identity)
            usable = _target_row_has_full_replicates(row)
            target_attempts.append(
                {
                    "exact_leaf_identity": identity,
                    "occurrence_key": row.get("occurrence_key"),
                    "root_identity": row.get("root_identity"),
                    "sampling_arm": row.get("sampling_arm"),
                    "act": row.get("act"),
                    "target_kind": row.get("target_kind"),
                    "valid_256_replicates": usable,
                    "replay_pass": len(replay_passes) + 1,
                    "backfill_used": len(replay_passes) > 0,
                }
            )
            if usable and identity not in accepted_ids:
                accepted_by_cell.setdefault(cell, []).append(row)
                accepted_ids.add(identity)
        replay_passes.append(
            {
                "pass_index": len(replay_passes) + 1,
                "candidate_occurrence_count": len(current_specs),
                "worker_count": args.workers,
                "task_count": len(roots) * len(ARMS),
                "task_ranges": "root indices 0..459 x three arms",
                "wall_clock_seconds": time.monotonic() - pass_started,
                "worker_evidence": pass_workers,
                "valid_rows": sum(
                    1 for row in pass_rows if _target_row_has_full_replicates(row)
                ),
                "invalid_rows": sum(
                    1 for row in pass_rows if not _target_row_has_full_replicates(row)
                ),
            }
        )
        reserved_ids: set[str] = set()
        current_specs = _backfill_specs(
            candidate_rows, attempted_ids, accepted_by_cell, reserved_ids
        )
    calibration_rows = [
        row
        for rows in accepted_by_cell.values()
        for row in rows
        if row.get("target_kind") == "calibration"
    ]
    formal_rows = [
        row
        for rows in accepted_by_cell.values()
        for row in rows
        if row.get("target_kind") == "formal"
    ]
    calibration = (
        select_repetition_count(calibration_rows)
        if len(calibration_rows) == 96
        else {"qualified": False, "reason": "exact 96 calibration rows unavailable"}
    )
    selected_n = calibration.get("selected_repetition_count")
    if isinstance(selected_n, int):
        for row in formal_rows:
            row["selected_repetition_count"] = selected_n
            row["replicates"] = row["replicates"][:selected_n]
    parity, parity_failures, parity_wall = _run_parity(
        roots, checkpoint_paths, args.native_commit, args.workers
    )
    root_runs = target_runs
    failures = candidate_failures + target_failures
    total_wall = candidate_wall + target_wall + parity_wall
    tasks = len(roots) * len(ARMS)
    selected_worker_summary = {
        "configured_worker_count": args.workers,
        "observed_worker_count": min(
            [item["observed_worker_count"] for item in target_worker_evidence] or [0]
        ),
        "effective_worker_count": min(
            [item["effective_worker_count"] for item in target_worker_evidence] or [0]
        ),
        "worker_pids": sorted(
            {pid for item in target_worker_evidence for pid in item["worker_pids"]}
        ),
        "host_logical_cpu_count": os.cpu_count(),
    }
    execution = {
        "schema_id": COLLECTOR_SCHEMA_ID,
        "generation_mode": "native_runtime_collector",
        "native_commit": args.native_commit,
        "search_simulations_per_root": 100,
        "worker_count": args.workers,
        "effective_worker_count": min(
            [candidate_workers["effective_worker_count"]]
            + [item["effective_worker_count"] for item in target_worker_evidence]
            + [parity["effective_worker_count"]]
        ),
        "root_runs": [
            {
                key: value
                for key, value in run.items()
                if key not in ("candidate_rows", "target_rows")
            }
            for run in root_runs
        ],
        "candidate_rows": candidate_rows,
        "calibration_rows": calibration_rows,
        "formal_rows": formal_rows,
        "calibration": calibration,
        "generation_passes": {
            "candidate": {
                "worker_count": args.workers,
                "effective_worker_count": candidate_workers["effective_worker_count"],
                "worker_evidence": candidate_workers,
                "task_count": tasks,
                "wall_clock_seconds": candidate_wall,
            },
            "selected_leaf_continuation": {
                "worker_count": args.workers,
                "task_count": tasks * max(1, len(replay_passes)),
                "tasks_per_pass": tasks,
                "wall_clock_seconds": target_wall,
                "target_identity_count": len(target_specs),
                "worker_evidence": target_worker_evidence,
                "replay_passes": replay_passes,
                "target_attempts": target_attempts,
            },
            "parity_preflight": {
                "worker_count": args.workers,
                "effective_worker_count": parity["effective_worker_count"],
                "worker_evidence": parity["worker_evidence"],
                "task_count": 16 * len(ARMS),
                "task_ranges": "first eight Act1 and first eight Act2 source roots x three arms",
                "wall_clock_seconds": parity_wall,
            },
            "selection_policy": selection_policy,
            "backfill": {
                "policy": "same arm/Act cell; next root-first/canonical candidate only after 256-replicate failure",
                "target_attempts": target_attempts,
            },
        },
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
        "parity": parity,
        "failures": failures + parity_failures,
        "shards": [
            {
                "worker_count": args.workers,
                "effective_worker_count": candidate_workers["effective_worker_count"],
                "task_count": tasks,
                "task_ranges": "candidate pass: root indices 0..459 x three arms",
                "wall_clock_seconds": candidate_wall,
                "worker_evidence": candidate_workers,
            },
            {
                "worker_count": args.workers,
                "effective_worker_count": min(
                    item["effective_worker_count"] for item in target_worker_evidence
                )
                if target_worker_evidence
                else 0,
                "task_count": tasks * max(1, len(replay_passes)),
                "task_ranges": "selected_leaf_continuation pass: root indices 0..459 x three arms",
                "wall_clock_seconds": target_wall,
                "worker_evidence": selected_worker_summary,
            },
            {
                "worker_count": args.workers,
                "effective_worker_count": parity["effective_worker_count"],
                "task_count": 16 * len(ARMS),
                "task_ranges": "parity_preflight: first eight Act1 and first eight Act2 source roots x three arms",
                "wall_clock_seconds": parity_wall,
                "worker_evidence": parity["worker_evidence"],
            },
        ],
        "wall_clock_seconds": total_wall,
    }
    _write_json(args.output, execution)
    return 0 if not failures and len(root_runs) == len(tasks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
