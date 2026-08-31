#!/usr/bin/env python3
"""Run the retained T079 three-budget diagnostic and write compact evidence."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t079_state_utilization import run_t079_stage
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.t079_state_utilization import (
    T079_BUDGETS,
    build_search_call_identity,
    classify_t079,
    compare_prefix_sequences,
    flatten_t079_call_records,
    sha256_file,
    summarize_state_utilization,
    write_json,
)

T070_SUBSET_MANIFEST_SHA256 = (
    "ec9201b87abb9921decdc337689b7a08e84899d4f01fd8b04172d21c9db8207c"
)
T070_SUBSET_COHORT_SHA256 = (
    "2d21a79dcbb393e4691e5aaf15f66c87fa20ba3e274bfa19baa30693cb2f029d"
)
T043_CHECKPOINT_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--subset-manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--native-build", type=Path, required=True)
    parser.add_argument(
        "--preflight",
        type=Path,
        help="passing T079 real-native preflight artifact (default: output-root/preflight.json)",
    )
    parser.add_argument("--max-battle-steps", type=int, default=200)
    parser.add_argument("--sim-seed", type=int, default=1)
    args = parser.parse_args()

    _verify_inputs(args.cohort, args.subset_manifest, args.checkpoint)
    args.output_root.mkdir(parents=True, exist_ok=True)
    preflight_path = args.preflight or args.output_root / "preflight.json"
    preflight = _verify_preflight(
        preflight_path,
        cohort=args.cohort,
        subset_manifest=args.subset_manifest,
        checkpoint=args.checkpoint,
        native_build=args.native_build,
    )
    if str(args.native_build.resolve()) not in sys.path:
        sys.path.insert(0, str(args.native_build.resolve()))
    source_identity = lightspeed_source_identity_dict()
    stage_command = shlex.join(
        [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    )
    execution_identity = {
        "preflight": _preflight_identity(preflight_path, preflight),
        "native_source_identity": source_identity,
        "native_build_directory": str(args.native_build.resolve()),
        "native_runtime_identity": preflight["native_runtime_identity"],
        "stage_command": stage_command,
    }
    experiment = {
        "schema_id": "t079-experiment-manifest-v1",
        "task_id": "T079",
        "subset_manifest_sha256": sha256_file(args.subset_manifest),
        "subset_cohort_sha256": sha256_file(args.cohort),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "native_source_identity": source_identity,
        "native_build_directory": str(args.native_build.resolve()),
        "native_runtime_identity": preflight["native_runtime_identity"],
        "preflight_identity": execution_identity["preflight"],
        "stage_command": stage_command,
        "information_regime": "full_simulator_state_oracle_like",
        "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
        "root_selection": "highest_mean",
        "arm": "prior_value",
        "budgets": list(T079_BUDGETS),
        "worker_count": 16,
        "shard_count": 16,
        "topology": "forked WSL process per one-record shard",
        "telemetry_mode": "read_only_exact_state_observation",
        "thresholds": {
            "median_definition": "average of sorted sample indices 7 and 8",
            "material_duplicate_fraction_median": 0.20,
            "material_marginal_unique_yield_median_max": 0.80,
            "weak_duplicate_fraction_median_max": 0.05,
            "weak_marginal_unique_yield_median_min": 0.90,
        },
    }
    write_json(args.output_root / "experiment-manifest.json", experiment)

    stages: dict[int, dict[str, object]] = {}
    action_space = ActionSpaceConfig.initial_no_potions()

    def adapter_factory() -> LightSpeedAdapter:
        return LightSpeedAdapter(seed=args.sim_seed, ascension=20)

    def controller_factory(budget: int) -> BattleSearchV2Controller:
        from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueGuidanceScorer

        scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(args.checkpoint)
        return BattleSearchV2Controller(
            simulations=budget,
            scorer=scorer,
            ablation="prior_value",
            root_selection_rule="highest_mean",
            action_space=action_space,
            inference_cache_enabled=True,
            public_context_projection_enabled=True,
            state_utilization_enabled=True,
            native_source_identity=source_identity,
        )

    for budget in T079_BUDGETS:
        started = time.monotonic()
        stage = run_t079_stage(
            cohort_path=args.cohort,
            budget=budget,
            controller_factory=controller_factory,
            adapter_factory=adapter_factory,
            action_space=action_space,
            max_battle_steps=args.max_battle_steps,
        )
        stage["wall_clock_seconds"] = time.monotonic() - started
        stage["execution_identity"] = execution_identity
        stage["first_root"] = _first_root_summary(stage)
        stage["all_search_calls"] = _all_call_summary(stage)
        stages[budget] = stage
        write_json(args.output_root / f"stage-s{budget}.json", stage)

    prefix = _prefix_report(stages)
    terminal = _terminal_classification(stages, prefix)
    write_json(args.output_root / "first-root-prefix-comparison.json", prefix)
    write_json(
        args.output_root / "aggregate-state-utilization.json",
        {
            "schema_id": "t079-aggregate-state-utilization-v1",
            "execution_identity": execution_identity,
            "budgets": {
                str(budget): {
                    "first_root": {
                        "aggregate": _population_aggregate(
                            stages[budget]["first_root"]
                        ),
                        "per_record": stages[budget]["first_root"],
                    },
                    "all_calls": {
                        "aggregate": _population_aggregate(
                            stages[budget]["all_search_calls"]["per_call"]
                        ),
                        "per_call": stages[budget]["all_search_calls"]["per_call"],
                        "failure_aggregate": stages[budget]["all_search_calls"][
                            "failure_aggregate"
                        ],
                    },
                }
                for budget in T079_BUDGETS
            },
        },
    )
    prefix["execution_identity"] = execution_identity
    terminal["execution_identity"] = execution_identity
    write_json(args.output_root / "first-root-prefix-comparison.json", prefix)
    write_json(args.output_root / "terminal-classification.json", terminal)
    retention = {
        "schema_id": "t079-retention-manifest-v1",
        "task_id": "T079",
        "retention_root": str(args.output_root),
        "execution_identity": execution_identity,
        "inputs": {
            "subset_manifest": {
                "path": str(args.subset_manifest),
                "sha256": sha256_file(args.subset_manifest),
            },
            "subset_cohort": {
                "path": str(args.cohort),
                "sha256": sha256_file(args.cohort),
            },
            "checkpoint": {
                "path": str(args.checkpoint),
                "sha256": sha256_file(args.checkpoint),
            },
            "preflight": _preflight_identity(preflight_path, preflight),
        },
        "outputs": {
            path.name: {"path": str(path), "sha256": sha256_file(path)}
            for path in sorted(args.output_root.glob("*.json"))
        },
        "regeneration_command": shlex.join(
            [
                "env",
                f"PYTHONPATH={os.environ.get('PYTHONPATH', '')}",
                "TMP=/tmp",
                "TEMP=/tmp",
                "TMPDIR=/tmp",
                sys.executable,
                str(Path(__file__).resolve()),
                "--cohort",
                str(args.cohort.resolve()),
                "--subset-manifest",
                str(args.subset_manifest.resolve()),
                "--checkpoint",
                str(args.checkpoint.resolve()),
                "--output-root",
                str(args.output_root.resolve()),
                "--native-build",
                str(args.native_build.resolve()),
                "--preflight",
                str(preflight_path.resolve()),
            ]
        ),
        "raw_hidden_state_payloads_retained": False,
    }
    write_json(args.output_root / "retention-manifest.json", retention)
    print(json.dumps({"classification": terminal, "retention": retention}, indent=2))
    return 0


def _verify_inputs(cohort: Path, manifest: Path, checkpoint: Path) -> None:
    expected = (
        (manifest, T070_SUBSET_MANIFEST_SHA256),
        (cohort, T070_SUBSET_COHORT_SHA256),
        (checkpoint, T043_CHECKPOINT_SHA256),
    )
    for path, digest in expected:
        actual = sha256_file(path)
        if actual != digest:
            raise SystemExit(f"T079 frozen input hash mismatch: {path}: {actual}")


def _verify_preflight(
    path: Path,
    *,
    cohort: Path,
    subset_manifest: Path,
    checkpoint: Path,
    native_build: Path,
) -> Mapping[str, Any]:
    """Require the real native parity/restore gate before any stage starts."""

    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"T079 preflight artifact is unavailable or invalid: {path}"
        ) from exc
    if (
        not isinstance(artifact, Mapping)
        or artifact.get("schema_id") != "t079-preflight-v1"
    ):
        raise SystemExit("T079 science requires schema t079-preflight-v1")
    if artifact.get("passed") is not True:
        raise SystemExit("T079 science requires a passing real-native preflight")
    runtime = artifact.get("native_runtime_identity")
    if not isinstance(runtime, Mapping):
        raise SystemExit("T079 preflight has no native runtime identity")
    if runtime.get("native_build_directory") != str(native_build.resolve()):
        raise SystemExit("T079 preflight native build does not match stage input")
    if not isinstance(runtime.get("module_file"), str) or not isinstance(
        runtime.get("module_sha256"), str
    ):
        raise SystemExit("T079 preflight has no exact native module identity")
    source = artifact.get("native_source_identity")
    if not isinstance(source, Mapping):
        raise SystemExit("T079 preflight has no native source identity")
    if (
        source.get("integration_branch") != "stsrl/main"
        or source.get("integration_ref") != "refs/heads/stsrl/main"
        or source.get("integration_commit")
        != "1555348535d66e3035aac80933a60949d4bd850f"
    ):
        raise SystemExit(
            "T079 preflight native source identity is not the active final ref"
        )
    inputs = artifact.get("inputs")
    if not isinstance(inputs, Mapping):
        raise SystemExit("T079 preflight has no frozen input identity")
    expected_inputs = {
        "subset_manifest": (subset_manifest, T070_SUBSET_MANIFEST_SHA256),
        "subset_cohort": (cohort, T070_SUBSET_COHORT_SHA256),
        "checkpoint": (checkpoint, T043_CHECKPOINT_SHA256),
    }
    for key, (input_path, digest) in expected_inputs.items():
        entry = inputs.get(key)
        if not isinstance(entry, Mapping) or entry.get("sha256") != digest:
            raise SystemExit(f"T079 preflight frozen input identity is invalid: {key}")
        if sha256_file(input_path) != digest:
            raise SystemExit(f"T079 preflight input changed since gate: {input_path}")
    parity = artifact.get("parity")
    restore = artifact.get("t078_restore_fidelity")
    if not isinstance(parity, Mapping) or parity.get("passed") is not True:
        raise SystemExit("T079 preflight parity did not pass")
    if not isinstance(restore, Mapping) or restore.get("passed") is not True:
        raise SystemExit("T079 preflight T078 restore fidelity did not pass")
    code = artifact.get("code_identity")
    if not isinstance(code, Mapping):
        raise SystemExit("T079 preflight has no code identity")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if code.get("head") != head or code.get("worktree_clean") is not True:
        raise SystemExit("T079 preflight code identity is stale or dirty")
    return artifact


def _preflight_identity(path: Path, artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "schema_id": artifact.get("schema_id"),
        "code_identity": artifact.get("code_identity"),
        "native_source_identity": artifact.get("native_source_identity"),
        "native_runtime_identity": artifact.get("native_runtime_identity"),
        "inputs": artifact.get("inputs"),
        "parity_passed": artifact.get("parity", {}).get("passed")
        if isinstance(artifact.get("parity"), Mapping)
        else False,
        "restore_fidelity_passed": artifact.get("t078_restore_fidelity", {}).get(
            "passed"
        )
        if isinstance(artifact.get("t078_restore_fidelity"), Mapping)
        else False,
    }


def _record_payloads(stage: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows = stage.get("records")
    if not isinstance(rows, list):
        raise TypeError("T079 stage records are missing")
    if len(rows) != 16:
        raise ValueError("T079 stage must retain exactly 16 record rows")
    if any(not isinstance(row, Mapping) for row in rows):
        raise TypeError("T079 stage contains a malformed record row")
    return list(rows)


def _telemetry_calls(stage_row: Mapping[str, object]) -> list[Mapping[str, object]]:
    result = stage_row.get("result")
    if not isinstance(result, Mapping):
        raise TypeError("T079 stage result is missing")
    telemetry = result.get("controller_compute_telemetry")
    if not isinstance(telemetry, Mapping):
        raise TypeError("T079 controller telemetry is missing")
    calls = telemetry.get("t079_state_utilization_records")
    if not isinstance(calls, list) or not calls:
        raise ValueError("T079 state-utilization call records are missing")
    return flatten_t079_call_records(calls)


def _first_root_call(stage_row: Mapping[str, object]) -> Mapping[str, object]:
    calls = _telemetry_calls(stage_row)
    roots = [call for call in calls if call.get("decision_step_index") == 0]
    if len(roots) != 1:
        raise ValueError(
            "T079 stage must contain exactly one explicitly identified first-root "
            f"call, found {len(roots)}"
        )
    return roots[0]


def _first_root_summary(stage: Mapping[str, object]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for row in _record_payloads(stage):
        call = _first_root_call(row)
        native = call.get("native_state_utilization")
        if not isinstance(native, Mapping):
            raise TypeError("T079 first-root native telemetry is missing")
        geometry = call.get("native_geometry")
        reduced = summarize_state_utilization(
            native,
            geometry=geometry if isinstance(geometry, Mapping) else None,
            compute={
                key: call[key]
                for key in (
                    "native_simulator_steps",
                    "model_calls",
                    "wall_clock_seconds",
                )
                if key in call
            },
        )
        reduced["record_index"] = row["record_index"]
        reduced["decision_step_index"] = 0
        reduced["call_role"] = "first_root"
        raw_identity = call.get("search_call_identity")
        if not isinstance(raw_identity, Mapping):
            raise TypeError("T079 first-root search-call identity is missing")
        reduced["search_call_identity"] = build_search_call_identity(
            raw_identity,
            cohort_identity=str(stage["cohort_identity"]),
            record_index=int(row["record_index"]),
            decision_step_index=0,
        )
        reduced["native_state_utilization"] = _retained_native_payload(native, reduced)
        reduced["native_geometry"] = geometry
        _add_call_evidence(reduced, call)
        reduced["controller_provenance"] = (
            row.get("result", {}).get("controller_provenance")
            if isinstance(row.get("result"), Mapping)
            else None
        )
        summary.append(reduced)
    return summary


def _all_call_summary(stage: Mapping[str, object]) -> dict[str, object]:
    calls: list[dict[str, object]] = []
    for row in _record_payloads(stage):
        result = row.get("result")
        if not isinstance(result, Mapping):
            raise TypeError("T079 stage result is missing")
        for call in _telemetry_calls(row):
            native = call.get("native_state_utilization")
            if not isinstance(native, Mapping):
                raise TypeError("T079 native telemetry is missing")
            geometry = call.get("native_geometry")
            reduced = summarize_state_utilization(
                native,
                geometry=geometry if isinstance(geometry, Mapping) else None,
                compute={
                    key: call[key]
                    for key in (
                        "native_simulator_steps",
                        "model_calls",
                        "wall_clock_seconds",
                    )
                    if key in call
                },
            )
            decision_step_index = call.get("decision_step_index")
            if (
                isinstance(decision_step_index, bool)
                or not isinstance(decision_step_index, int)
                or decision_step_index < 0
            ):
                raise ValueError("T079 call decision_step_index is invalid")
            reduced.update(
                {
                    "record_index": row["record_index"],
                    "decision_step_index": decision_step_index,
                    "call_role": (
                        "first_root" if decision_step_index == 0 else "continuation"
                    ),
                    "native_state_utilization": _retained_native_payload(
                        native, reduced
                    ),
                    "native_geometry": geometry,
                    "controller_provenance": result.get("controller_provenance"),
                    "selected_action_identity": call.get("selected_action_identity"),
                }
            )
            raw_identity = call.get("search_call_identity")
            if not isinstance(raw_identity, Mapping):
                raise TypeError("T079 search-call identity is missing")
            reduced["search_call_identity"] = build_search_call_identity(
                raw_identity,
                cohort_identity=str(stage["cohort_identity"]),
                record_index=int(row["record_index"]),
                decision_step_index=decision_step_index,
            )
            _add_call_evidence(reduced, call)
            calls.append(reduced)
    failure_status_counts: dict[str, int] = {}
    failure_count = 0
    for call in calls:
        count = int(call["failure_count"])
        failure_count += count
        status = str(call["search_status"])
        if count:
            failure_status_counts[status] = failure_status_counts.get(status, 0) + count
    return {
        "call_count": len(calls),
        "expanded_path_nodes": sum(int(call["expanded_path_nodes"]) for call in calls),
        "unique_exact_states": sum(int(call["unique_exact_states"]) for call in calls),
        "exact_duplicate_path_nodes": sum(
            int(call["exact_duplicate_path_nodes"]) for call in calls
        ),
        "failure_aggregate": {
            "failure_count": failure_count,
            "failure_status_counts": failure_status_counts,
        },
        "per_call": calls,
    }


def _add_call_evidence(target: dict[str, object], call: Mapping[str, object]) -> None:
    required = (
        "native_simulator_steps",
        "model_calls",
        "wall_clock_seconds",
        "search_status",
        "search_failure_count",
    )
    if any(key not in call for key in required):
        raise ValueError("T079 search-call evidence is incomplete")
    steps = call["native_simulator_steps"]
    models = call["model_calls"]
    failures = call["search_failure_count"]
    wall = call["wall_clock_seconds"]
    if (
        isinstance(steps, bool)
        or not isinstance(steps, int)
        or steps < 0
        or isinstance(models, bool)
        or not isinstance(models, int)
        or models < 0
        or isinstance(failures, bool)
        or not isinstance(failures, int)
        or failures < 0
        or not isinstance(call["search_status"], str)
        or not isinstance(wall, (int, float))
        or isinstance(wall, bool)
        or wall < 0
    ):
        raise ValueError("T079 search-call evidence has invalid values")
    target.update(
        {
            "native_simulator_steps": steps,
            "model_calls": models,
            "wall_clock_seconds": wall,
            "search_status": call["search_status"],
            "failure_count": failures,
        }
    )


def _retained_native_payload(
    native: Mapping[str, object], reduced: Mapping[str, object]
) -> dict[str, object]:
    """Retain the normalized partition, never the raw opaque digest claims."""

    payload = dict(native)
    payload["expanded_states"] = reduced["expanded_states"]
    payload["identity_evidence_class_counts"] = {
        "exact_comparable": reduced["comparable_nodes"],
        "opaque": reduced["opaque_nodes"],
    }
    return payload


def _population_aggregate(rows: object) -> dict[str, object]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("T079 aggregate population is empty")
    mappings = [row for row in rows if isinstance(row, Mapping)]
    if len(mappings) != len(rows):
        raise TypeError("T079 aggregate population contains a malformed row")
    duplicate_fractions = [float(row["exact_duplicate_fraction"]) for row in mappings]
    yields = [float(row["unique_state_yield"]) for row in mappings]
    duplicate_lower = [
        float(
            row.get("exact_duplicate_fraction_lower", row["exact_duplicate_fraction"])
        )
        for row in mappings
    ]
    duplicate_upper = [
        float(
            row.get("exact_duplicate_fraction_upper", row["exact_duplicate_fraction"])
        )
        for row in mappings
    ]
    yield_lower = [
        float(row.get("unique_state_yield_lower", row["unique_state_yield"]))
        for row in mappings
    ]
    yield_upper = [
        float(row.get("unique_state_yield_upper", row["unique_state_yield"]))
        for row in mappings
    ]
    duplicate_groups = [int(row["duplicate_group_count"]) for row in mappings]
    distinct_groups = [
        int(row["distinct_path_duplicate_group_count"]) for row in mappings
    ]
    distinct_fractions = [
        float(row["distinct_path_duplicate_group_fraction"]) for row in mappings
    ]
    multiplicities = {
        metric: [float(row["paths_per_exact_state"][metric]) for row in mappings]
        for metric in ("mean", "median", "p90", "max")
    }
    depth_totals = {
        field: _sum_depth_distributions(mappings, field)
        for field in (
            "duplicate_expansions_by_depth",
            "first_seen_depth",
            "duplicate_depth",
        )
    }
    geometry = _geometry_aggregate(mappings)
    return {
        "row_count": len(mappings),
        "record_count": len({row["record_index"] for row in mappings}),
        "expanded_path_nodes": sum(int(row["expanded_path_nodes"]) for row in mappings),
        "unique_exact_states": sum(int(row["unique_exact_states"]) for row in mappings),
        "exact_duplicate_path_nodes": sum(
            int(row["exact_duplicate_path_nodes"]) for row in mappings
        ),
        "mean_exact_duplicate_fraction": sum(duplicate_fractions) / len(mappings),
        "mean_unique_state_yield": sum(yields) / len(mappings),
        "comparable_nodes": sum(int(row["comparable_nodes"]) for row in mappings),
        "opaque_nodes": sum(int(row["opaque_nodes"]) for row in mappings),
        "mean_exact_duplicate_fraction_lower": sum(duplicate_lower) / len(mappings),
        "mean_exact_duplicate_fraction_upper": sum(duplicate_upper) / len(mappings),
        "mean_unique_state_yield_lower": sum(yield_lower) / len(mappings),
        "mean_unique_state_yield_upper": sum(yield_upper) / len(mappings),
        "duplicate_group_count": _numeric_aggregate(duplicate_groups),
        "paths_per_exact_state": {
            metric: _numeric_aggregate(values)
            for metric, values in multiplicities.items()
        },
        "distinct_path_duplicate_group_count": _numeric_aggregate(distinct_groups),
        "distinct_path_duplicate_group_fraction": _numeric_aggregate(
            distinct_fractions
        ),
        "depth_distributions": depth_totals,
        "t070_geometry": geometry,
        "native_simulator_steps": sum(
            int(
                row.get(
                    "native_simulator_steps",
                    row.get("compute", {}).get("native_simulator_steps", 0),
                )
            )
            for row in mappings
        ),
        "model_calls": sum(
            int(row.get("model_calls", row.get("compute", {}).get("model_calls", 0)))
            for row in mappings
        ),
        "wall_clock_seconds": sum(
            float(
                row.get(
                    "wall_clock_seconds",
                    row.get("compute", {}).get("wall_clock_seconds", 0.0),
                )
            )
            for row in mappings
        ),
        "failure_count": sum(int(row.get("failure_count", 0)) for row in mappings),
        "search_status_counts": {
            status: sum(1 for row in mappings if row.get("search_status") == status)
            for status in sorted({str(row.get("search_status")) for row in mappings})
        },
    }


def _numeric_aggregate(values: list[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("T079 numeric aggregate cannot be empty")
    ordered = sorted(float(value) for value in values)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2.0
    )
    p90_index = max(0, (9 * len(ordered) + 9) // 10 - 1)
    return {
        "count": len(ordered),
        "total": sum(ordered),
        "mean": sum(ordered) / len(ordered),
        "median": median,
        "p90": ordered[p90_index],
        "max": max(ordered),
    }


def _sum_depth_distributions(
    rows: list[Mapping[str, object]], field: str
) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        distribution = row.get(field)
        if not isinstance(distribution, Mapping):
            raise TypeError(f"T079 {field} distribution is missing")
        for depth, count in distribution.items():
            if (
                not isinstance(depth, str)
                or isinstance(count, bool)
                or not isinstance(count, int)
            ):
                raise TypeError(f"T079 {field} distribution is malformed")
            totals[depth] = totals.get(depth, 0) + count
    return dict(sorted(totals.items()))


def _geometry_aggregate(rows: list[Mapping[str, object]]) -> dict[str, object]:
    geometry_rows = []
    for row in rows:
        geometry = row.get("tree_geometry")
        if not isinstance(geometry, Mapping):
            geometry = row.get("native_geometry")
        if not isinstance(geometry, Mapping):
            continue
        geometry_rows.append(geometry)
    numeric_fields = (
        "root_depth",
        "total_expanded_node_count",
        "total_discovered_child_edge_count",
        "total_visited_child_edge_count",
        "max_expanded_depth",
    )
    numeric: dict[str, dict[str, float | int]] = {}
    for field in numeric_fields:
        values = [geometry[field] for geometry in geometry_rows if field in geometry]
        if values:
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in values
            ):
                raise ValueError(f"T079 T070 geometry field is malformed: {field}")
            numeric[field] = _numeric_aggregate(values)
    depth_rows: dict[str, dict[str, int]] = {}
    for geometry in geometry_rows:
        rows_at_depth = geometry.get("depth_rows", [])
        if not isinstance(rows_at_depth, list):
            raise TypeError("T079 T070 geometry depth rows are malformed")
        for depth_row in rows_at_depth:
            if not isinstance(depth_row, Mapping):
                raise TypeError("T079 T070 geometry depth row is malformed")
            depth = str(depth_row.get("depth"))
            aggregate = depth_rows.setdefault(
                depth,
                {
                    "expanded_node_count": 0,
                    "discovered_child_edge_count": 0,
                    "visited_child_edge_count": 0,
                },
            )
            for field in aggregate:
                value = depth_row.get(field)
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError("T079 T070 geometry depth count is malformed")
                aggregate[field] += value
    return {
        "available_count": len(geometry_rows),
        "missing_count": len(rows) - len(geometry_rows),
        "schema_id_counts": {
            schema: sum(1 for row in geometry_rows if row.get("schema_id") == schema)
            for schema in sorted({str(row.get("schema_id")) for row in geometry_rows})
        },
        "numeric": numeric,
        "depth_rows": dict(sorted(depth_rows.items())),
    }


def _prefix_report(stages: Mapping[int, Mapping[str, object]]) -> dict[str, object]:
    by_record: list[dict[str, object]] = []
    for index in range(16):
        sequences: dict[int, list[str]] = {}
        for budget in T079_BUDGETS:
            stage_row = _record_payloads(stages[budget])[index]
            call = _first_root_call(stage_row)
            native = call["native_state_utilization"]
            reduced = summarize_state_utilization(native)
            sequences[budget] = reduced["expanded_states"]
        comparison = compare_prefix_sequences(sequences)
        comparison["record_index"] = index
        by_record.append(comparison)
    return {
        "schema_id": "t079-first-root-prefix-comparison-v1",
        "records": by_record,
        "comparable_first_root_count": sum(
            1 for row in by_record if row["prefix_comparable"]
        ),
    }


def _terminal_classification(
    stages: Mapping[int, Mapping[str, object]], prefix: Mapping[str, object]
) -> dict[str, object]:
    comparable = int(prefix["comparable_first_root_count"])
    rows: list[dict[str, object]] = []
    prefix_rows = prefix["records"]
    for index, root in enumerate(stages[1600]["first_root"]):
        comparison = prefix_rows[index]
        marginal = comparison["400_1600"]["marginal_unique_yield"]
        rows.append(
            {
                "exact_duplicate_fraction_lower": root[
                    "exact_duplicate_fraction_lower"
                ],
                "exact_duplicate_fraction_upper": root[
                    "exact_duplicate_fraction_upper"
                ],
                "marginal_unique_yield_lower": comparison["400_1600"].get(
                    "marginal_unique_yield_lower"
                ),
                "marginal_unique_yield_upper": comparison["400_1600"].get(
                    "marginal_unique_yield_upper"
                ),
                # Kept as a named compatibility field for threshold-input
                # readers; the frozen bands use the explicit bound fields.
                "marginal_unique_yield_400_1600": marginal,
                "distinct_path_duplicate_group_count": root[
                    "distinct_path_duplicate_group_count"
                ],
            }
        )
    threshold_summary = _threshold_summary(rows, comparable)
    if comparable < 12 or any(
        row["marginal_unique_yield_400_1600"] is None for row in rows
    ):
        return {
            "schema_id": "t079-terminal-diagnostic-classification-v1",
            "classification": "AMBIGUOUS",
            "comparable_first_root_count": comparable,
            "reason": "literal 16-sample threshold inputs are incomplete",
            "threshold_inputs": rows,
            "threshold_summary": threshold_summary,
        }
    report = classify_t079(rows, comparable_count=comparable)
    report["threshold_inputs"] = rows
    report["threshold_summary"] = threshold_summary
    return report


def _threshold_summary(
    rows: list[Mapping[str, object]], comparable_count: int
) -> dict[str, object]:
    def metric(
        row: Mapping[str, object], preferred: str, fallback: str
    ) -> float | None:
        value = row.get(preferred)
        if value is None:
            value = row.get(fallback)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"T079 threshold metric is malformed: {preferred}")
        return float(value)

    material_fractions = [
        value
        for row in rows
        if (
            value := metric(
                row, "exact_duplicate_fraction_lower", "exact_duplicate_fraction"
            )
        )
        is not None
    ]
    weak_fractions = [
        value
        for row in rows
        if (
            value := metric(
                row, "exact_duplicate_fraction_upper", "exact_duplicate_fraction"
            )
        )
        is not None
    ]
    material_marginals = [
        value
        for row in rows
        if (
            value := metric(
                row,
                "marginal_unique_yield_upper",
                "marginal_unique_yield_400_1600",
            )
        )
        is not None
    ]
    weak_marginals = [
        value
        for row in rows
        if (
            value := metric(
                row,
                "marginal_unique_yield_lower",
                "marginal_unique_yield_400_1600",
            )
        )
        is not None
    ]
    distinct_count = sum(
        int(row["distinct_path_duplicate_group_count"]) > 0 for row in rows
    )
    complete = (
        len(rows) == 16 and len(material_marginals) == 16 and len(weak_marginals) == 16
    )
    material_median_fraction = (
        _literal_median(material_fractions) if len(material_fractions) == 16 else None
    )
    weak_median_fraction = (
        _literal_median(weak_fractions) if len(weak_fractions) == 16 else None
    )
    material_median_marginal = _literal_median(material_marginals) if complete else None
    weak_median_marginal = _literal_median(weak_marginals) if complete else None
    fraction_ge_015 = sum(value >= 0.15 for value in material_fractions)
    fraction_le_010 = sum(value <= 0.10 for value in weak_fractions)
    fraction_gt_020 = sum(value > 0.20 for value in weak_fractions)
    material = {
        "median_duplicate_fraction_ge_0.20": (
            None
            if material_median_fraction is None
            else material_median_fraction >= 0.20
        ),
        "median_marginal_unique_yield_le_0.80": (
            None
            if material_median_marginal is None
            else material_median_marginal <= 0.80
        ),
        "duplicate_fraction_ge_0.15_count_ge_8": fraction_ge_015 >= 8,
        "distinct_path_group_count_ge_8": distinct_count >= 8,
    }
    weak = {
        "median_duplicate_fraction_le_0.05": (
            None if weak_median_fraction is None else weak_median_fraction <= 0.05
        ),
        "duplicate_fraction_le_0.10_count_ge_12": fraction_le_010 >= 12,
        "median_marginal_unique_yield_ge_0.90": (
            None if weak_median_marginal is None else weak_median_marginal >= 0.90
        ),
        "duplicate_fraction_gt_0.20_count_le_2": fraction_gt_020 <= 2,
    }
    return {
        "comparable_first_root_count": comparable_count,
        "comparable_minimum": 12,
        "comparable_pass": comparable_count >= 12,
        "sample_count": len(rows),
        "median_duplicate_fraction_lower": material_median_fraction,
        "median_duplicate_fraction_upper": weak_median_fraction,
        "median_marginal_unique_yield_lower_400_1600": weak_median_marginal,
        "median_marginal_unique_yield_upper_400_1600": material_median_marginal,
        "duplicate_fraction_ge_0.15_count": fraction_ge_015,
        "duplicate_fraction_le_0.10_count": fraction_le_010,
        "duplicate_fraction_gt_0.20_count": fraction_gt_020,
        "distinct_path_duplicate_group_count": distinct_count,
        "material_band": material,
        "material_band_pass": complete
        and all(value is True for value in material.values()),
        "weak_band": weak,
        "weak_band_pass": complete and all(value is True for value in weak.values()),
    }


def _literal_median(values: list[float]) -> float:
    ordered = sorted(values)
    return (ordered[7] + ordered[8]) / 2.0


if __name__ == "__main__":
    sys.exit(main())
