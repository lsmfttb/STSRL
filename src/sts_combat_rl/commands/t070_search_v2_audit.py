"""Fail-closed T070 fixed-cohort outcome and budget-sufficiency audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
import hashlib
from importlib import import_module
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys
import sysconfig
from typing import Any

from sts_combat_rl.artifact_paths import resolve_runtime_artifact_path
from sts_combat_rl.commands.t062_battle_search_v2 import (
    _evaluate_t062_arm,
    _fixed_report_summary,
    _merged_arm_summary,
    _paired_t062_summary,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    dump_fixed_cohort_jsonl,
    load_fixed_cohort_jsonl,
)


NATIVE_COMMIT = "fee272f1ae21c283ad2161f55293cfe6d714134a"
T069_RETENTION_SHA256 = (
    "cb34f8c0c4ce00f14e424120566a09a1d666051e6effc9cd39e77d678df9dc76"
)
T068_RETENTION_SHA256 = (
    "bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678"
)
T052_COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
T043_CHECKPOINT_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)
PRIMARY_RANGES = (
    "0:6",
    "6:12",
    "12:18",
    "18:24",
    "24:30",
    "30:36",
    "36:42",
    "42:48",
    "48:54",
    "54:60",
    "60:66",
    "66:72",
    "72:78",
    "78:83",
    "83:88",
    "88:93",
)
HIGH_BUDGET_RANGES = tuple(f"{index}:{index + 1}" for index in range(16))
PRIMARY_STAGE_CONFIGS = (
    ("baseline-0100", "baseline", "shared", 100),
    ("equal-prior-only-0100", "prior_only", "equal_nominal", 100),
    ("equal-value-only-0100", "value_only", "equal_nominal", 100),
    ("equal-prior-value-0100", "prior_value", "equal_nominal", 100),
    ("simstep-prior-only-0086", "prior_only", "simulator_step_normalized", 86),
    ("simstep-value-only-0408", "value_only", "simulator_step_normalized", 408),
    ("simstep-prior-value-0384", "prior_value", "simulator_step_normalized", 384),
    ("wall-prior-only-0001", "prior_only", "wall_clock_normalized", 1),
    ("wall-value-only-0001", "value_only", "wall_clock_normalized", 1),
    ("wall-prior-value-0002", "prior_value", "wall_clock_normalized", 2),
)
HIGH_BUDGET_STAGE_CONFIGS = tuple(
    (f"{arm.replace('_', '-')}-{budget:04d}", arm, "high_budget", budget)
    for arm in ("baseline", "prior_value")
    for budget in (100, 400, 1600)
)

NATIVE_PREFLIGHT_SCHEMA_ID = "t070-native-capability-preflight-v1"
FROZEN_MANIFEST_SCHEMA_ID = "t070-frozen-experiment-manifest-v1"
PRIMARY_REPORT_SCHEMA_ID = "t070-search-v2-primary-comparison-v1"
PRIMARY_CELL_SCHEMA_ID = "t070-search-v2-primary-arm-cell-v1"
SUBSET_MANIFEST_SCHEMA_ID = "t070-budget-subset-manifest-v1"
BUDGET_CURVE_SCHEMA_ID = "t070-search-v2-budget-curve-v1"
HIGH_BUDGET_CELL_SCHEMA_ID = "t070-search-v2-high-budget-arm-cell-v1"
GEOMETRY_REPORT_SCHEMA_ID = "t070-search-tree-geometry-report-v1"
DECISION_SCHEMA_ID = "t070-search-v2-decision-v1"
STAGE_SCHEMA_ID = "t070-stage-execution-v1"
STAGE_DETAIL_SCHEMA_ID = "t070-stage-execution-detail-v1"
RETENTION_SCHEMA_ID = "t070-retention-manifest-v1"
SHARD_SCHEMA_ID = "t070-single-arm-shard-v1"
MERGED_STAGE_SCHEMA_ID = "t070-single-arm-merged-stage-v1"
NATIVE_RUNTIME_SCHEMA_ID = "t070-native-runtime-identity-v1"


def build_frozen_manifests(
    *,
    cohort_path: Path,
    checkpoint_path: Path,
    t068_retention_path: Path,
    t069_retention_path: Path,
    source_manifest_path: Path,
    source_verifier_path: Path,
    code_commit: str,
    frozen_output_path: Path,
    subset_output_path: Path,
    subset_cohort_output_path: Path,
    expected_checkpoint_sha256: str = T043_CHECKPOINT_SHA256,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify immutable inputs and freeze both stage inventory and blind subset."""

    for output in (
        frozen_output_path,
        subset_output_path,
        subset_cohort_output_path,
    ):
        if output.exists():
            raise ValueError(f"T070 freeze refuses to overwrite output: {output}")
    inputs = {
        "t052_fixed_cohort": _identity(cohort_path, T052_COHORT_SHA256),
        "t043_checkpoint": _identity(checkpoint_path, expected_checkpoint_sha256),
        "t068_retention_manifest": _identity(
            t068_retention_path, T068_RETENTION_SHA256
        ),
        "t069_retention_manifest": _identity(
            t069_retention_path, T069_RETENTION_SHA256
        ),
        "sts_lightspeed_source_manifest": _identity(source_manifest_path, None),
        "sts_lightspeed_source_verifier": _identity(source_verifier_path, None),
    }
    source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source.get("integration", {}).get("commit") != NATIVE_COMMIT:
        raise ValueError("T070 source manifest does not pin the accepted native commit")
    retained = json.loads(t069_retention_path.read_text(encoding="utf-8"))
    if retained.get("command_passed") is not True:
        raise ValueError("T070 requires a passed T069 retention manifest")
    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    if len(cohort.records) != 93:
        raise ValueError("T070 primary cohort must contain exactly 93 records")
    subset, subset_manifest = _build_outcome_blind_subset(cohort, code_commit)
    subset_cohort_output_path.parent.mkdir(parents=True, exist_ok=True)
    with subset_cohort_output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(subset, stream)
    subset_manifest["subset_cohort"] = _identity(subset_cohort_output_path, None)
    _write_json(subset_output_path, subset_manifest)

    frozen = {
        "schema_id": FROZEN_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "code_commit": code_commit,
        "native_commit": NATIVE_COMMIT,
        "input_identities": inputs,
        "primary_cohort_identity": cohort.identity,
        "primary_record_count": 93,
        "primary_shard_ranges": list(PRIMARY_RANGES),
        "primary_worker_count": 16,
        "primary_stage_inventory": [
            {
                "stage_name": name,
                "arm": arm,
                "family": family,
                "native_budget": budget,
                "tree_geometry_enabled": False,
            }
            for name, arm, family, budget in PRIMARY_STAGE_CONFIGS
        ],
        "high_budget_subset_manifest": _identity(subset_output_path, None),
        "high_budget_subset_cohort": _identity(subset_cohort_output_path, None),
        "high_budget_record_count": 16,
        "high_budget_shard_ranges": list(HIGH_BUDGET_RANGES),
        "high_budget_worker_count": 16,
        "high_budget_stage_inventory": [
            {
                "stage_name": name,
                "arm": arm,
                "family": family,
                "native_budget": budget,
                "tree_geometry_enabled": arm == "prior_value",
            }
            for name, arm, family, budget in HIGH_BUDGET_STAGE_CONFIGS
        ],
        "projection_mode": "accepted_t069_search_scope_projection",
        "primary_geometry_disabled": True,
        "budgets_frozen_before_outcomes": True,
        "subset_frozen_before_outcomes": True,
        "command_passed": True,
    }
    _write_json(frozen_output_path, frozen)
    return frozen, subset_manifest


def expected_checkpoint_identity_from_stage_manifest(
    path: Path, *, t064_selection: str | None = None
) -> dict[str, Any]:
    """Read the evaluated checkpoint identity while preserving T070 manifests."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("stage manifest must be an object")
    if payload.get("schema_id") == FROZEN_MANIFEST_SCHEMA_ID:
        inputs = payload.get("input_identities")
        identity = (
            inputs.get("t043_checkpoint") if isinstance(inputs, Mapping) else None
        )
    elif payload.get("schema_id") == "t064-curriculum-manifest-v1":
        stage = payload.get("t070_stage_manifest")
        if not isinstance(stage, Mapping):
            identity = None
        elif t064_selection is None:
            identity = stage.get("checkpoint")
        else:
            selections = stage.get("checkpoint_selections")
            selected = (
                selections.get(t064_selection)
                if isinstance(selections, Mapping)
                else None
            )
            identity = (
                selected.get("checkpoint") if isinstance(selected, Mapping) else None
            )
    else:
        raise ValueError("unsupported frozen stage manifest schema")
    if not isinstance(identity, Mapping):
        raise ValueError("stage manifest lacks checkpoint identity")
    sha256 = identity.get("sha256")
    expected_bytes = identity.get("bytes")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("stage manifest checkpoint SHA-256 is invalid")
    if (
        isinstance(expected_bytes, bool)
        or not isinstance(expected_bytes, int)
        or expected_bytes < 0
    ):
        raise ValueError("stage manifest checkpoint byte count is invalid")
    runtime_identity = resolve_runtime_artifact_path(identity.get("path"))
    runtime_path = Path(runtime_identity["runtime_path"])
    if _sha256(runtime_path) != sha256 or runtime_path.stat().st_size != expected_bytes:
        raise ValueError("stage manifest checkpoint runtime identity mismatch")
    return {
        "path": identity.get("path"),
        "sha256": sha256,
        "bytes": expected_bytes,
    }


def _t070_frozen_contract_from_stage_manifest(
    path: Path, *, t064_selection: str | None = None
) -> tuple[dict[str, Any], str | None]:
    """Resolve a T070 manifest or the T064 wrapper that substitutes only a checkpoint.

    The wrapper carries an identity-bound copy of the old frozen manifest; this
    deliberately keeps the old stage inventory, cohort, ranges, and failure
    policy authoritative while allowing T064 to evaluate a newly trained
    checkpoint.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("stage manifest must be an object")
    if payload.get("schema_id") == FROZEN_MANIFEST_SCHEMA_ID:
        return dict(payload), None
    if payload.get("schema_id") != "t064-curriculum-manifest-v1":
        raise ValueError("unsupported frozen stage manifest schema")
    stage = payload.get("t070_stage_manifest")
    if not isinstance(stage, Mapping):
        raise ValueError("T064 stage manifest is missing")
    frozen_identity = stage.get("frozen_t070_manifest")
    if not isinstance(frozen_identity, Mapping):
        raise ValueError("T064 stage manifest lacks frozen T070 identity")
    frozen_path = frozen_identity.get("path")
    expected_sha256 = frozen_identity.get("sha256")
    expected_bytes = frozen_identity.get("bytes")
    if (
        not isinstance(frozen_path, str)
        or not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or isinstance(expected_bytes, bool)
        or not isinstance(expected_bytes, int)
        or expected_bytes < 0
    ):
        raise ValueError("T064 frozen T070 identity is invalid")
    outer_code_commit = payload.get("code_commit")
    if not isinstance(outer_code_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", outer_code_commit
    ):
        raise ValueError("T064 stage manifest code commit is invalid")
    runtime_identity = resolve_runtime_artifact_path(frozen_path)
    resolved = Path(runtime_identity["runtime_path"])
    if (
        not resolved.is_file()
        or _sha256(resolved) != expected_sha256
        or resolved.stat().st_size != expected_bytes
    ):
        raise ValueError("T064 frozen T070 manifest identity mismatch")
    frozen = _load_schema(resolved, FROZEN_MANIFEST_SCHEMA_ID)
    historical_code_commit = frozen.get("code_commit")
    if not isinstance(historical_code_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", historical_code_commit
    ):
        raise ValueError("historical frozen T070 code commit is invalid")
    return frozen, outer_code_commit


def run_single_arm_shard(
    *,
    cohort_path: Path,
    adapter_factory,
    controller: BattleSearchV2Controller,
    stage_name: str,
    arm: str,
    family: str,
    record_range: str,
    shard_index: int,
    expected_ranges: Sequence[str],
    code_commit: str,
    native_runtime_identity: Mapping[str, Any],
    output_path: Path,
    max_battle_steps: int = 200,
) -> dict[str, Any]:
    if shard_index not in range(16) or record_range != expected_ranges[shard_index]:
        raise ValueError("T070 shard index/range does not match frozen inventory")
    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    start, end = (int(value) for value in record_range.split(":"))
    records = cohort.records[start:end]
    report = _evaluate_t062_arm(
        adapter_factory=adapter_factory,
        cohort=cohort,
        records=records,
        controller=controller,
        action_space=ActionSpaceConfig.initial_no_potions(),
        max_battle_steps=max_battle_steps,
        worker_count=1,
        shard_count=1,
    )
    payload = {
        "schema_id": SHARD_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "code_commit": code_commit,
        "native_commit": NATIVE_COMMIT,
        "native_runtime_identity": dict(native_runtime_identity),
        "stage_name": stage_name,
        "arm": arm,
        "family": family,
        "native_budget": controller.simulations,
        "record_range": record_range,
        "shard_index": shard_index,
        "cohort_identity": cohort.identity,
        "cohort_record_count": len(cohort.records),
        "controller_provenance": controller.provenance.to_dict(),
        "arm_report": _fixed_report_summary(report),
        "command_passed": report.evaluation_successful,
    }
    _write_json(output_path, payload)
    return payload


def merge_single_arm_stage(
    *,
    shard_paths: Sequence[Path],
    expected_ranges: Sequence[str],
    expected_record_count: int,
    output_path: Path,
) -> dict[str, Any]:
    if len(shard_paths) != 16 or len(expected_ranges) != 16:
        raise ValueError("T070 merged stage requires exactly 16 shards")
    shards = [_load_schema(path, SHARD_SCHEMA_ID) for path in shard_paths]
    first = shards[0]
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    for index, shard in enumerate(shards):
        for key in (
            "code_commit",
            "native_commit",
            "stage_name",
            "arm",
            "family",
            "native_budget",
            "cohort_identity",
            "cohort_record_count",
            "controller_provenance",
            "native_runtime_identity",
        ):
            if shard.get(key) != first.get(key):
                problems.append(f"shard {index}: {key} differs")
        if shard.get("shard_index") != index:
            problems.append(f"shard {index}: shard_index differs")
        if shard.get("record_range") != expected_ranges[index]:
            problems.append(f"shard {index}: record_range differs")
        if shard.get("command_passed") is not True:
            problems.append(f"shard {index}: command failed")
        arm_report = shard.get("arm_report")
        if not isinstance(arm_report, Mapping):
            problems.append(f"shard {index}: arm report missing")
            continue
        values = arm_report.get("records")
        if not isinstance(values, list):
            problems.append(f"shard {index}: records missing")
            continue
        rows.extend(dict(row) for row in values if isinstance(row, Mapping))
    indices = [row.get("cohort_index") for row in rows]
    if indices != list(range(expected_record_count)):
        problems.append("merged rows do not cover ordered cohort exactly once")
    arm_summary = _merged_arm_summary(rows)
    if arm_summary["record_count"] != expected_record_count:
        problems.append("merged stage record count mismatch")
    payload = {
        "schema_id": MERGED_STAGE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        **{
            key: first[key]
            for key in (
                "code_commit",
                "native_commit",
                "stage_name",
                "arm",
                "family",
                "native_budget",
                "cohort_identity",
                "cohort_record_count",
                "controller_provenance",
                "native_runtime_identity",
            )
        },
        "expected_record_count": expected_record_count,
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "shard_ranges": list(expected_ranges),
        "shards": [str(path) for path in shard_paths],
        "arm_report": arm_summary,
        "problems": list(dict.fromkeys(problems)),
        "command_passed": not problems,
    }
    _write_json(output_path, payload)
    return payload


def build_primary_report(
    stages: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = {
        name: (arm, family, budget)
        for name, arm, family, budget in PRIMARY_STAGE_CONFIGS
    }
    if set(stages) != set(expected):
        raise ValueError("T070 primary stage inventory is incomplete")
    for name, report in stages.items():
        arm, family, budget = expected[name]
        _validate_merged_stage(
            report,
            stage_name=name,
            arm=arm,
            family=family,
            budget=budget,
            records=93,
        )
    baseline = stages["baseline-0100"]["arm_report"]
    family_names = (
        ("equal_nominal", "equal"),
        ("simulator_step_normalized", "simstep"),
        ("wall_clock_normalized", "wall"),
    )
    families: dict[str, Any] = {}
    for family, prefix in family_names:
        arms = {"baseline": dict(baseline)}
        for arm in ("prior_only", "value_only", "prior_value"):
            stage = next(
                report
                for name, report in stages.items()
                if report["family"] == family and report["arm"] == arm
            )
            arms[arm] = dict(stage["arm_report"])
        paired = {
            arm: _paired_t062_summary(
                baseline=arms["baseline"]["records"],
                guided=arms[arm]["records"],
                bootstrap_resamples=2_000,
                bootstrap_seed=7000 + len(families) * 10 + offset,
            )
            for offset, arm in enumerate(
                ("prior_only", "value_only", "prior_value"), start=1
            )
        }
        paired["baseline"] = _paired_t062_summary(
            baseline=arms["baseline"]["records"],
            guided=arms["baseline"]["records"],
            bootstrap_resamples=2_000,
            bootstrap_seed=7000 + len(families) * 10,
        )
        cells = {
            stratum: {
                arm: _build_outcome_compute_cell(
                    rows=_stratum_rows(arms[arm]["records"], stratum),
                    expected_count=expected_count,
                    budget=_family_arm_budget(stages, family, arm),
                    arm=arm,
                    schema_id=PRIMARY_CELL_SCHEMA_ID,
                    stratum=stratum,
                    paired_vs_baseline=paired[arm][stratum],
                )
                for arm in ("baseline", "prior_only", "value_only", "prior_value")
            }
            for stratum, expected_count in (
                ("overall", 93),
                ("boss_only", 88),
                ("act2_plus", 5),
            )
        }
        families[family] = {
            "arms": arms,
            "cells": cells,
            "paired_vs_baseline": {
                arm: value for arm, value in paired.items() if arm != "baseline"
            },
            "failure_counts": {
                arm: cells["overall"][arm]["failure_counts"] for arm in arms
            },
            "first_selected_action_divergence": {
                stratum: {
                    arm: _first_action_divergence(
                        _stratum_rows(arms["baseline"]["records"], stratum),
                        _stratum_rows(arms[arm]["records"], stratum),
                    )
                    for arm in ("prior_only", "value_only", "prior_value")
                }
                for stratum in ("overall", "boss_only", "act2_plus")
            },
            "cell_inventory": {
                "schema_id": PRIMARY_CELL_SCHEMA_ID,
                "strata": ["overall", "boss_only", "act2_plus"],
                "arms": ["baseline", "prior_only", "value_only", "prior_value"],
                "expected_cell_count": 12,
                "actual_cell_count": sum(len(value) for value in cells.values()),
                "command_passed": (
                    sum(len(value) for value in cells.values()) == 12
                    and all(
                        cell["command_passed"]
                        for stratum_cells in cells.values()
                        for cell in stratum_cells.values()
                    )
                ),
            },
        }
    failures = [
        f"{family}/{stratum}/{arm}/{kind}={count}"
        for family, payload in families.items()
        for stratum, cells in payload["cells"].items()
        for arm, cell in cells.items()
        for kind, count in cell["failure_counts"].items()
        if count
    ]
    incomplete_cells = [
        f"{family}/{stratum}/{arm}"
        for family, payload in families.items()
        for stratum, cells in payload["cells"].items()
        for arm, cell in cells.items()
        if not cell["command_passed"]
    ]
    return {
        "schema_id": PRIMARY_REPORT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "record_count": 93,
        "strata": {"overall": 93, "boss_only": 88, "act2_plus": 5},
        "families": families,
        "family_order": [
            "equal_nominal",
            "simulator_step_normalized",
            "wall_clock_normalized",
        ],
        "arm_order": ["baseline", "prior_only", "value_only", "prior_value"],
        "stratum_order": ["overall", "boss_only", "act2_plus"],
        "unique_stage_count": 10,
        "stage_inventory": {name: dict(value) for name, value in stages.items()},
        "failure_problems": failures,
        "incomplete_cells": incomplete_cells,
        "command_passed": not failures and not incomplete_cells,
    }


def build_budget_curve_and_geometry(
    stages: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = {
        name: (arm, family, budget)
        for name, arm, family, budget in HIGH_BUDGET_STAGE_CONFIGS
    }
    if set(stages) != set(expected):
        raise ValueError("T070 high-budget stage inventory is incomplete")
    by_arm_budget: dict[str, dict[int, Mapping[str, Any]]] = {
        "baseline": {},
        "prior_value": {},
    }
    for name, report in stages.items():
        arm, family, budget = expected[name]
        _validate_merged_stage(
            report,
            stage_name=name,
            arm=arm,
            family=family,
            budget=budget,
            records=16,
        )
        by_arm_budget[arm][budget] = report["arm_report"]
    comparisons: dict[str, Any] = {}
    for budget in (100, 400, 1600):
        comparisons[str(budget)] = _paired_t062_summary(
            baseline=by_arm_budget["baseline"][budget]["records"],
            guided=by_arm_budget["prior_value"][budget]["records"],
            bootstrap_resamples=2_000,
            bootstrap_seed=7100 + budget,
        )
    pv_growth = _paired_t062_summary(
        baseline=by_arm_budget["prior_value"][100]["records"],
        guided=by_arm_budget["prior_value"][1600]["records"],
        bootstrap_resamples=2_000,
        bootstrap_seed=8700,
    )
    geometry_rows: dict[str, list[dict[str, Any]]] = {}
    for budget in (100, 400, 1600):
        geometry_rows[str(budget)] = [
            _geometry_record(row, budget)
            for row in by_arm_budget["prior_value"][budget]["records"]
        ]
    insufficient, sufficiency_evidence = _budget_sufficiency(geometry_rows)
    high_signal, high_signal_evidence = _high_budget_signal(
        pv_growth=pv_growth,
        pv_vs_baseline_1600=comparisons["1600"],
    )
    budget_cells = {
        arm: {
            str(budget): _build_outcome_compute_cell(
                rows=report["records"],
                expected_count=16,
                budget=budget,
                arm=arm,
                schema_id=HIGH_BUDGET_CELL_SCHEMA_ID,
                stratum="frozen_budget_subset",
                paired_vs_baseline=(
                    comparisons[str(budget)]["overall"]
                    if arm == "prior_value"
                    else _paired_t062_summary(
                        baseline=report["records"],
                        guided=report["records"],
                        bootstrap_resamples=2_000,
                        bootstrap_seed=7200 + budget,
                    )["overall"]
                ),
            )
            for budget, report in sorted(by_arm_budget[arm].items())
        }
        for arm in by_arm_budget
    }
    curve = {
        "schema_id": BUDGET_CURVE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "record_count": 16,
        "arms": budget_cells,
        "prior_value_vs_baseline": comparisons,
        "prior_value_1600_vs_100": pv_growth,
        "budget_100_not_sufficient": insufficient,
        "budget_sufficiency_evidence": sufficiency_evidence,
        "high_budget_guidance_signal": high_signal,
        "high_budget_guidance_evidence": high_signal_evidence,
        "cell_schema_id": HIGH_BUDGET_CELL_SCHEMA_ID,
        "command_passed": all(
            cell["command_passed"]
            for cells in budget_cells.values()
            for cell in cells.values()
        ),
    }
    geometry = {
        "schema_id": GEOMETRY_REPORT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "metric_scope": "empirical_exposed_edge_coverage_not_global_game_tree",
        "metric_definitions": {
            "effective_branching_factor": (
                "discovered_child_edges(d) / max(expanded_nodes(d), 1)"
            ),
            "visited_edge_coverage_next_depth": (
                "visited_child_edges(d) / max(discovered_child_edges(d), 1)"
            ),
            "expanded_node_coverage_next_depth": (
                "expanded_nodes(d + 1) / max(discovered_child_edges(d), 1)"
            ),
        },
        "budgets": geometry_rows,
        "command_passed": all(
            len(rows) == 16 and all(row["command_passed"] for row in rows)
            for rows in geometry_rows.values()
        ),
    }
    return curve, geometry


def build_decision_report(
    primary: Mapping[str, Any],
    curve: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        primary.get("schema_id") != PRIMARY_REPORT_SCHEMA_ID
        or curve.get("schema_id") != BUDGET_CURVE_SCHEMA_ID
        or geometry.get("schema_id") != GEOMETRY_REPORT_SCHEMA_ID
    ):
        raise ValueError("T070 decision inputs use unsupported schemas")
    if not all(
        report.get("command_passed") is True for report in (primary, curve, geometry)
    ):
        raise ValueError("T070 decision requires complete valid evidence")
    promotion = _primary_promotion(primary)
    if promotion["passed"]:
        case = "A"
        recommendation = (
            "T071 Battle Search v2 Bounded Complete-Run Reachability Evaluation"
        )
    elif curve.get("high_budget_guidance_signal") is True:
        case = "B"
        recommendation = "T063 Oracle-guided public battle learning"
    else:
        case = "C"
        recommendation = "T064 simulator-generated later-act curriculum"
    return {
        "schema_id": DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "decision_case": case,
        "primary_promotion_gate": promotion,
        "budget_100_not_sufficient": bool(curve.get("budget_100_not_sufficient")),
        "high_budget_guidance_signal": bool(curve.get("high_budget_guidance_signal")),
        "recommendation": recommendation,
        "exactly_one_planner_recommendation": True,
        "successor_published": False,
        "command_passed": True,
    }


def build_retention_manifest(
    *,
    artifact_root: Path,
    retained_paths: Sequence[Path],
    regeneration_commands: Mapping[str, str],
    code_commit: str,
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    required_command_kinds = {"preflight", "freeze", "stage", "finalize"}
    if set(regeneration_commands) != required_command_kinds or any(
        not value for value in regeneration_commands.values()
    ):
        raise ValueError(
            "T070 retention manifest requires preflight/freeze/stage/finalize commands"
        )
    root = artifact_root.resolve()
    entries = []
    for path in sorted({value.resolve() for value in retained_paths}):
        if not path.is_file():
            raise ValueError(f"T070 retained path is missing: {path}")
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"T070 retained path is outside artifact root: {path}"
            ) from exc
        top = relative.parts[0]
        command_kind = (
            "preflight"
            if top == "native-preflight"
            else "freeze"
            if top in {"frozen-manifest", "budget-subset"}
            else "stage"
            if top in {"primary", "high-budget"}
            else "finalize"
        )
        entries.append(
            {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "schema_id": _json_schema(path),
                "source_identity": {
                    "code_commit": code_commit,
                    "native_commit": NATIVE_COMMIT,
                },
                "regeneration_command": regeneration_commands[command_kind],
                "compatibility_requirements": (
                    "current T070 schema readers only; exact STSRL/native identities "
                    "must match; legacy or missing provenance fails closed without guessing"
                ),
                "retention_reason": "T070 accepted audit or reproducibility evidence",
                "downstream_consumer": decision["recommendation"],
                "deletion_condition": (
                    "after T070 is merged, the planner has received the maintainer "
                    "result report, and the named downstream task is closed or the "
                    "artifact is independently regenerated"
                ),
            }
        )
    return {
        "schema_id": RETENTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "artifact_root": str(artifact_root.resolve()),
        "code_commit": code_commit,
        "native_commit": NATIVE_COMMIT,
        "retained_artifacts": entries,
        "regeneration_commands": dict(regeneration_commands),
        "compatibility_requirements": (
            "writers emit current schemas only; readers reject incomplete, mixed, legacy, "
            "or identity-mismatched evidence without inferred provenance"
        ),
        "raw_artifacts_may_be_deleted_when": (
            "merged identities and row counts pass audit; raw hashes, sizes, "
            "schemas and commands are retained; T070 is merged; planner has "
            "received the maintainer result report; downstream retention is closed"
        ),
        "command_passed": True,
    }


def validate_t070_preflight(
    preflight_path: Path,
    *,
    code_commit: str,
    source_manifest_path: Path,
    source_verifier_path: Path,
    native_checkout: Path | None = None,
    native_build_root: Path | None = None,
) -> dict[str, Any]:
    preflight = _load_schema(preflight_path, NATIVE_PREFLIGHT_SCHEMA_ID)
    if (
        preflight.get("stsrl_code_commit") != code_commit
        or preflight.get("native_commit") != NATIVE_COMMIT
        or preflight.get("semantic_parity_result") is not True
        or preflight.get("runtime_api_smoke_passed") is not True
        or preflight.get("runtime_geometry_passed") is not True
        or preflight.get("return_codes") != [0, 0, 0, 0, 0]
        or preflight.get("return_code") != 0
        or preflight.get("worker_count") != 16
        or preflight.get("command_passed") is not True
        or preflight.get("source_manifest_sha256") != _sha256(source_manifest_path)
        or preflight.get("source_verifier_sha256") != _sha256(source_verifier_path)
        or preflight.get("verifier_clean_worktree_mode")
        != "temporary_detached_exact_commit_worktree"
        or preflight.get("verifier_clean_worktree_scope")
        != "clean_source_verifier_only"
        or preflight.get("runtime_source_mode")
        != "exact_head_tracked_clean_stable_checkout"
        or preflight.get("build_jobs") != 16
        or not isinstance(preflight.get("cmake_identity"), str)
        or not preflight["cmake_identity"]
        or preflight.get("manifest_build_directory") != "build-stsrl-source-py"
        or preflight.get("manifest_cmake_target") != "slaythespire"
    ):
        raise ValueError("T070 native preflight is missing, stale, or failed")
    command_rows = preflight.get("commands")
    expected_command_names = [
        "clean_source_verifier",
        "runtime_cmake_configure",
        "runtime_cmake_build",
        "runtime_api_smoke",
        "runtime_geometry",
    ]
    if (
        not isinstance(command_rows, list)
        or [
            row.get("name") if isinstance(row, Mapping) else None
            for row in command_rows
        ]
        != expected_command_names
        or any(
            not isinstance(row.get("argv"), list) or not row["argv"]
            for row in command_rows
            if isinstance(row, Mapping)
        )
    ):
        raise ValueError("T070 native preflight command evidence is incomplete")
    required_log_fields = (
        "stdout",
        "stderr",
        "runtime_build_stdout",
        "runtime_build_stderr",
        "runtime_api_smoke_stdout",
        "runtime_api_smoke_stderr",
        "runtime_geometry_stdout",
        "runtime_geometry_stderr",
    )
    if any(
        not isinstance(preflight.get(field), str)
        or not Path(preflight[field]).is_file()
        for field in required_log_fields
    ):
        raise ValueError("T070 native preflight log evidence is incomplete")
    expected_runtime = preflight.get("native_runtime_identity")
    if not isinstance(expected_runtime, Mapping):
        raise ValueError("T070 native preflight lacks runtime extension identity")
    cmake_python = preflight.get("cmake_python_identity")
    if (
        not isinstance(cmake_python, Mapping)
        or cmake_python.get("cmake_python_executable")
        != expected_runtime.get("python_executable")
        or cmake_python.get("runner_python_executable")
        != expected_runtime.get("python_executable")
        or cmake_python.get("runner_python_extension_suffix")
        != expected_runtime.get("python_extension_suffix")
        or cmake_python.get("matching_extension_path")
        != expected_runtime.get("native_extension_path")
    ):
        raise ValueError("T070 native preflight CMake Python identity is inconsistent")
    if native_checkout is not None or native_build_root is not None:
        if native_checkout is None or native_build_root is None:
            raise ValueError(
                "T070 native runtime validation requires checkout and build root"
            )
        observed_runtime = probe_t070_native_runtime_identity(
            native_checkout=native_checkout,
            native_build_root=native_build_root,
        )
        if dict(expected_runtime) != observed_runtime:
            raise ValueError(
                "T070 outcome runtime extension differs from native preflight"
            )
    return preflight


def _runtime_configure_command(
    *,
    native_checkout: Path,
    native_build_root: Path,
    cmake_policy_version_minimum: str,
    python_executable: Path,
) -> list[str]:
    """Configure pybind11 with the exact Python that will run the audit."""

    return [
        "cmake",
        "-S",
        str(native_checkout),
        "-B",
        str(native_build_root),
        f"-DCMAKE_POLICY_VERSION_MINIMUM={cmake_policy_version_minimum}",
        "-DPYBIND11_FINDPYTHON=ON",
        f"-DPython_EXECUTABLE={python_executable}",
    ]


def _runtime_verification_commands(
    *,
    native_checkout: Path,
    native_build_root: Path,
    python_executable: Path,
) -> tuple[list[str], list[str]]:
    """Run native acceptance checks under the exact outcome Python runtime."""

    api_smoke = [
        str(python_executable),
        str(native_checkout / "scripts" / "stsrl_api_smoke.py"),
        "--build-dir",
        str(native_build_root),
    ]
    geometry = [
        str(python_executable),
        str(native_checkout / "scripts" / "test_battle_search_v2_tree_geometry.py"),
        "--build-dir",
        str(native_build_root),
    ]
    return api_smoke, geometry


def _validate_cmake_python_identity(
    *, native_build_root: Path, python_executable: Path
) -> dict[str, str]:
    """Fail closed unless CMake and the generated extension use the runner ABI."""

    cache_path = native_build_root / "CMakeCache.txt"
    if not cache_path.is_file():
        raise ValueError("T070 runtime build omitted CMakeCache.txt")
    cache_values: dict[str, str] = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("//", "#")) or "=" not in line:
            continue
        key_and_type, value = line.split("=", 1)
        key = key_and_type.split(":", 1)[0]
        cache_values[key] = value
    configured = cache_values.get("Python_EXECUTABLE")
    if configured is None:
        raise ValueError("T070 runtime CMake cache omitted Python_EXECUTABLE")
    configured_path = Path(configured).resolve()
    runner_path = python_executable.resolve()
    if configured_path != runner_path:
        raise ValueError(
            "T070 runtime CMake selected a different Python executable: "
            f"{configured_path} != {runner_path}"
        )
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not isinstance(suffix, str) or not suffix:
        raise ValueError("T070 runtime Python EXT_SUFFIX is unavailable")
    extension_path = (native_build_root / f"slaythespire{suffix}").resolve()
    if not extension_path.is_file():
        raise ValueError(
            "T070 runtime extension suffix does not match the runner ABI: "
            f"missing {extension_path}"
        )
    return {
        "cmake_python_executable": str(configured_path),
        "runner_python_executable": str(runner_path),
        "runner_python_extension_suffix": suffix,
        "matching_extension_path": str(extension_path),
    }


def probe_t070_native_runtime_identity(
    *,
    native_checkout: Path,
    native_build_root: Path,
) -> dict[str, Any]:
    """Bind the imported extension to an exact native checkout and Python ABI."""

    checkout = native_checkout.resolve()
    build_root = native_build_root.resolve()
    try:
        build_root.relative_to(checkout)
    except ValueError as exc:
        raise ValueError(
            "T070 native build root must be inside its source checkout"
        ) from exc
    head = _git_output(checkout, "rev-parse", "HEAD")
    if head != NATIVE_COMMIT:
        raise ValueError(f"T070 native checkout is {head}, expected {NATIVE_COMMIT}")
    tracked_status = _git_output(checkout, "status", "--short", "--untracked-files=no")
    if tracked_status:
        raise ValueError("T070 native checkout has tracked modifications")
    module = import_module("slaythespire")
    origin_value = getattr(module, "__file__", None)
    if not isinstance(origin_value, str) or not origin_value:
        raise ValueError("T070 native module has no extension path")
    extension = Path(origin_value).resolve()
    try:
        extension.relative_to(build_root)
    except ValueError as exc:
        raise ValueError(
            "T070 imported native extension is outside the declared build root"
        ) from exc
    extension_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not isinstance(extension_suffix, str) or not extension.name.endswith(
        extension_suffix
    ):
        raise ValueError("T070 native extension does not match the Python ABI suffix")
    return {
        "schema_id": NATIVE_RUNTIME_SCHEMA_ID,
        "schema_version": 1,
        "native_commit": NATIVE_COMMIT,
        "native_source_checkout": str(checkout),
        "native_source_head": head,
        "native_source_tracked_clean": True,
        "native_build_root": str(build_root),
        "native_extension_path": str(extension),
        "native_extension_sha256": _sha256(extension),
        "native_extension_size_bytes": extension.stat().st_size,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_cache_tag": sys.implementation.cache_tag,
        "python_soabi": sysconfig.get_config_var("SOABI"),
        "python_extension_suffix": extension_suffix,
    }


def _git_output(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "T070 native checkout identity command failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
    return completed.stdout.strip()


def validate_t070_frozen_stage(
    frozen_path: Path,
    *,
    code_commit: str,
    stage_name: str,
    arm: str,
    family: str,
    budget: int,
    range_kind: str,
    tree_geometry: bool,
    cohort_path: Path,
    checkpoint_path: Path,
    source_manifest_path: Path,
    source_verifier_path: Path,
    t064_selection: str | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    frozen, wrapper_code_commit = _t070_frozen_contract_from_stage_manifest(
        frozen_path, t064_selection=t064_selection
    )
    if (
        (wrapper_code_commit is None and frozen.get("code_commit") != code_commit)
        or (wrapper_code_commit is not None and wrapper_code_commit != code_commit)
        or frozen.get("native_commit") != NATIVE_COMMIT
        or frozen.get("command_passed") is not True
    ):
        raise ValueError("T070 frozen manifest identity is invalid")
    if range_kind == "primary":
        inventory_key = "primary_stage_inventory"
        ranges_key = "primary_shard_ranges"
        worker_key = "primary_worker_count"
        expected_ranges = PRIMARY_RANGES
        expected_input = frozen["input_identities"]["t052_fixed_cohort"]
    elif range_kind == "high_budget":
        inventory_key = "high_budget_stage_inventory"
        ranges_key = "high_budget_shard_ranges"
        worker_key = "high_budget_worker_count"
        expected_ranges = HIGH_BUDGET_RANGES
        expected_input = frozen["high_budget_subset_cohort"]
    else:
        raise ValueError("T070 stage range kind is invalid")
    expected_tuple = {
        "stage_name": stage_name,
        "arm": arm,
        "family": family,
        "native_budget": budget,
        "tree_geometry_enabled": tree_geometry,
    }
    inventory = frozen.get(inventory_key)
    if not isinstance(inventory, list) or expected_tuple not in inventory:
        raise ValueError("T070 stage tuple is not present in frozen inventory")
    if frozen.get(ranges_key) != list(expected_ranges) or frozen.get(worker_key) != 16:
        raise ValueError("T070 frozen shard/worker topology is invalid")
    for path, expected, label in (
        (cohort_path, expected_input, "cohort"),
        (
            checkpoint_path,
            expected_checkpoint_identity_from_stage_manifest(
                frozen_path, t064_selection=t064_selection
            ),
            "checkpoint",
        ),
        (
            source_manifest_path,
            frozen["input_identities"]["sts_lightspeed_source_manifest"],
            "source manifest",
        ),
        (
            source_verifier_path,
            frozen["input_identities"]["sts_lightspeed_source_verifier"],
            "source verifier",
        ),
    ):
        if (
            not path.is_file()
            or _sha256(path) != expected.get("sha256")
            or path.stat().st_size != expected.get("bytes")
        ):
            raise ValueError(f"T070 frozen {label} identity mismatch")
    return frozen, expected_ranges


def _build_outcome_blind_subset(
    cohort: FixedCohort,
    code_commit: str,
) -> tuple[FixedCohort, dict[str, Any]]:
    candidates = []
    act2 = []
    for record in cohort.records:
        identity = _canonical_source_identity(record)
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        item = (digest, record, identity)
        if _as_int(record.structural_metadata.get("act")) >= 2:
            act2.append(item)
        elif record.structural_metadata.get("room_type") == "BOSS":
            candidates.append(item)
    if len(act2) != 5:
        raise ValueError("T070 subset requires exactly five Act-2+ records")
    selected = sorted(act2, key=lambda item: item[1].cohort_index)
    selected.extend(sorted(candidates, key=lambda item: item[0])[:11])
    if len(selected) != 16:
        raise ValueError("T070 subset requires eleven Boss-only records")
    records = [
        replace(item[1], cohort_index=index) for index, item in enumerate(selected)
    ]
    subset = FixedCohort(
        source_pool_format_version=cohort.source_pool_format_version,
        source_pool_controller_provenance=cohort.source_pool_controller_provenance,
        selection_config=cohort.selection_config,
        records=records,
    )
    manifest = {
        "schema_id": SUBSET_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "code_commit": code_commit,
        "source_cohort_identity": cohort.identity,
        "source_record_count": len(cohort.records),
        "selected_record_count": 16,
        "selection_rule": (
            "all five Act-2+ in source order, then eleven Boss-only by ascending "
            "SHA-256 of complete canonical source identity"
        ),
        "selection_allowed_fields": [
            "source_pool_record_index",
            "source_checkpoint_id",
            "source_run_id",
            "source_seed",
            "source_battle_index",
            "structural_stratum",
            "structural_metadata",
            "source_distribution_kind",
            "checkpoint_information_regime",
        ],
        "selection_forbidden_fields": [
            "outcomes",
            "selected_actions",
            "disagreement_labels",
            "terminal_resources",
        ],
        "outcome_blind": True,
        "records": [
            {
                "subset_index": index,
                "source_cohort_index": item[1].cohort_index,
                "stratum": (
                    "act2_plus"
                    if _as_int(item[1].structural_metadata.get("act")) >= 2
                    else "boss_only"
                ),
                "canonical_source_identity": item[2],
                "canonical_source_identity_sha256": item[0],
            }
            for index, item in enumerate(selected)
        ],
        "subset_identity": subset.identity,
        "command_passed": True,
    }
    return subset, manifest


def _canonical_source_identity(record: FixedCohortRecord) -> dict[str, Any]:
    return {
        "source_pool_record_index": record.source_pool_record_index,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_run_id": record.source_run_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "structural_stratum": list(record.structural_stratum),
        "structural_metadata": record.structural_metadata,
        "source_distribution_kind": record.source_distribution_kind,
        "checkpoint_information_regime": record.checkpoint_information_regime,
    }


def _validate_merged_stage(
    report: Mapping[str, Any],
    *,
    stage_name: str,
    arm: str,
    family: str,
    budget: int,
    records: int,
) -> None:
    if (
        report.get("schema_id") != MERGED_STAGE_SCHEMA_ID
        or report.get("command_passed") is not True
        or report.get("stage_name") != stage_name
        or report.get("arm") != arm
        or report.get("family") != family
        or report.get("native_budget") != budget
        or report.get("expected_record_count") != records
        or report.get("worker_count") != 16
        or report.get("shard_count") != 16
        or report.get("effective_parallel_workers") != 16
    ):
        raise ValueError(f"T070 stage {arm}/{family}/{budget} is invalid")


def _family_arm_budget(
    stages: Mapping[str, Mapping[str, Any]], family: str, arm: str
) -> int:
    if arm == "baseline":
        return 100
    matches = [
        int(report["native_budget"])
        for report in stages.values()
        if report.get("family") == family and report.get("arm") == arm
    ]
    if len(matches) != 1:
        raise ValueError(f"T070 cannot resolve budget for {family}/{arm}")
    return matches[0]


def _stratum_rows(
    rows: Sequence[Mapping[str, Any]], stratum: str
) -> list[dict[str, Any]]:
    predicates = {
        "overall": lambda row: True,
        "boss_only": lambda row: (
            row.get("structural_metadata", {}).get("room_type") == "BOSS"
        ),
        "act2_plus": lambda row: (
            _numeric(row.get("structural_metadata", {}).get("act")) >= 2
        ),
        "frozen_budget_subset": lambda row: True,
    }
    if stratum not in predicates:
        raise ValueError(f"T070 unknown report stratum {stratum!r}")
    return [dict(row) for row in rows if predicates[stratum](row)]


def _build_outcome_compute_cell(
    *,
    rows: Sequence[Mapping[str, Any]],
    expected_count: int,
    budget: int,
    arm: str,
    schema_id: str,
    stratum: str,
    paired_vs_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one complete, versioned T070 outcome/compute cell.

    The cell intentionally retains occurrence-safe selected actions and exact
    structured battle-end resources per record. Aggregates never replace those
    non-scalar outcomes.
    """

    values = [dict(row) for row in rows]
    indices = [row.get("cohort_index") for row in values]
    problems: list[str] = []
    if len(values) != expected_count:
        problems.append(
            f"record_count={len(values)} does not match expected {expected_count}"
        )
    if (
        not all(
            isinstance(index, int) and not isinstance(index, bool) for index in indices
        )
        or len(set(indices)) != len(indices)
        or indices != sorted(indices)
    ):
        problems.append("cohort indices are not unique ordered integers")
    statuses = ("win", "loss", "truncated", "error")
    status_counts = {
        status: sum(row.get("termination_status") == status for row in values)
        for status in statuses
    }
    unknown_statuses = sorted(
        {
            str(row.get("termination_status"))
            for row in values
            if row.get("termination_status") not in statuses
        }
    )
    if unknown_statuses:
        problems.append(f"unknown termination statuses: {unknown_statuses}")

    hp_values: list[float] = []
    resource_rows: list[dict[str, Any]] = []
    potion_rows: list[dict[str, Any]] = []
    selected_actions: list[dict[str, Any]] = []
    for row in values:
        index = row.get("cohort_index")
        hp = row.get("terminal_absolute_hp")
        if isinstance(hp, (int, float)) and not isinstance(hp, bool):
            hp_values.append(float(hp))
        else:
            problems.append(f"record {index}: terminal absolute HP missing")
        outcome = row.get("structured_battle_outcome")
        if (
            not isinstance(outcome, Mapping)
            or outcome.get("schema_id") != "structured-battle-outcome-v1"
            or not isinstance(outcome.get("terminal"), Mapping)
            or not isinstance(outcome.get("deltas"), Mapping)
        ):
            problems.append(f"record {index}: structured battle outcome incomplete")
            outcome = {}
        terminal = outcome.get("terminal", {})
        deltas = outcome.get("deltas", {})
        start = outcome.get("start", {})
        resource_rows.append(
            {
                "cohort_index": index,
                "schema_id": outcome.get("schema_id"),
                "terminal": terminal,
                "deltas": deltas,
                "outcome_problems": outcome.get("problems"),
            }
        )
        potion_rows.append(
            {
                "cohort_index": index,
                "start_potion_slots": (
                    start.get("potion_slots") if isinstance(start, Mapping) else None
                ),
                "terminal_potion_slots": (
                    terminal.get("potion_slots")
                    if isinstance(terminal, Mapping)
                    else None
                ),
                "potion_slots_delta": (
                    deltas.get("potion_slots_delta")
                    if isinstance(deltas, Mapping)
                    else None
                ),
            }
        )
        first = _first_search_decision(row)
        identity = _selected_identity(first)
        if not _occurrence_safe_identity(identity):
            problems.append(
                f"record {index}: first selected action identity is not occurrence-safe"
            )
        selected_actions.append(
            {
                "cohort_index": index,
                "decision_step_index": first.get("decision_step_index"),
                "selected_action_identity": identity,
            }
        )

    summary = _merged_arm_summary(values)
    failures = _failure_counts(summary)
    compute = {
        "native_simulator_steps": summary["native_simulator_steps"],
        "outer_simulator_steps": summary["outer_simulator_steps"],
        "model_calls": summary["model_calls"],
        "wall_clock_seconds": summary["wall_clock_seconds"],
        "projection_construction_count": _attribution_total(
            values, "public_context_projection_construction_count"
        ),
        "projection_reuse_count": _attribution_total(
            values, "public_context_projection_reuse_count"
        ),
    }
    for metric, value in compute.items():
        if not _is_finite_nonnegative(value):
            problems.append(f"{metric} is missing or non-finite")
    if arm != "baseline" and any(
        not isinstance(
            row.get("controller_compute_telemetry", {}).get("t069_cost_attribution"),
            Mapping,
        )
        for row in values
    ):
        problems.append("guided arm lacks T069 projection attribution")
    paired = dict(paired_vs_baseline)
    if paired.get("record_count") != expected_count:
        problems.append("paired summary record count differs from cell")
    if not (
        isinstance(paired.get("paired_win_delta_bootstrap_95ci"), list)
        and len(paired["paired_win_delta_bootstrap_95ci"]) == 2
    ):
        problems.append("paired bootstrap interval is missing")
    return {
        "schema_id": schema_id,
        "schema_version": 1,
        "task_id": "T070",
        "arm": arm,
        "stratum": stratum,
        "budget": budget,
        "expected_record_count": expected_count,
        "record_count": len(values),
        "cohort_indices": indices,
        "wins": status_counts["win"],
        "losses": status_counts["loss"],
        "termination_status_counts": {
            **status_counts,
            "unknown": len(unknown_statuses),
        },
        "terminal_absolute_current_hp": {
            "available_count": len(hp_values),
            "missing_count": len(values) - len(hp_values),
            "sum": sum(hp_values),
            "mean": statistics.fmean(hp_values) if hp_values else None,
            "median": statistics.median(hp_values) if hp_values else None,
            "minimum": min(hp_values, default=None),
            "maximum": max(hp_values, default=None),
            "values_by_record": [
                {
                    "cohort_index": row.get("cohort_index"),
                    "value": row.get("terminal_absolute_hp"),
                }
                for row in values
            ],
        },
        "structured_battle_end_resources": resource_rows,
        "potion_outcomes": potion_rows,
        "first_selected_root_actions": selected_actions,
        "paired_vs_baseline": paired,
        "compute": compute,
        "failure_counts": failures,
        "problems": problems,
        "command_passed": not problems and not any(failures.values()),
    }


def _occurrence_safe_identity(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return (
        isinstance(value.get("stable_id"), str)
        and bool(value["stable_id"])
        and isinstance(value.get("occurrence"), int)
        and not isinstance(value.get("occurrence"), bool)
    )


def _attribution_total(rows: Sequence[Mapping[str, Any]], metric: str) -> float:
    total = 0.0
    for row in rows:
        telemetry = row.get("controller_compute_telemetry")
        attribution = (
            telemetry.get("t069_cost_attribution")
            if isinstance(telemetry, Mapping)
            else None
        )
        if not isinstance(attribution, Mapping):
            continue
        total += _numeric(attribution.get(metric))
    return total


def _numeric(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _is_finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _failure_counts(arm: Mapping[str, Any]) -> dict[str, int]:
    records = arm.get("records")
    if not isinstance(records, Sequence):
        raise ValueError("T070 arm records are missing")
    problem_text = [
        str(problem).lower()
        for row in records
        if isinstance(row, Mapping)
        for problem in row.get("problems", [])
    ]
    mapping = {
        "restore": ("restore", "restoration"),
        "action_mapping": ("mapping", "unmapped"),
        "checkpoint": ("checkpoint",),
        "missing_value": ("missing", "value head"),
        "fallback": ("fallback",),
        "controller": ("controller",),
        "truncation": ("truncat",),
        "worker": ("worker",),
        "mixed_provenance": ("provenance",),
    }
    counts = {
        name: sum(any(token in text for token in tokens) for text in problem_text)
        for name, tokens in mapping.items()
    }
    records = arm.get("records", [])
    if isinstance(records, Sequence):
        counts["action_mapping"] += int(
            sum(
                _telemetry_failure_total(row)
                for row in records
                if isinstance(row, Mapping)
            )
        )
    counts["truncation"] += int(arm.get("truncations", 0))
    counts["controller"] += int(arm.get("errors", 0))
    return counts


def _telemetry_failure_total(row: Mapping[str, Any]) -> float:
    telemetry = row.get("controller_compute_telemetry")
    if not isinstance(telemetry, Mapping):
        return 0.0
    return sum(
        _numeric(telemetry.get(key))
        for key in (
            "oracle_search_root_mapping_failures",
            "oracle_search_unmapped_search_edges",
        )
    )


def _first_action_divergence(
    baseline: Sequence[Mapping[str, Any]],
    guided: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    left = {int(row["cohort_index"]): row for row in baseline}
    right = {int(row["cohort_index"]): row for row in guided}
    divergent = []
    for index in sorted(left):
        a = _first_search_decision(left[index])
        b = _first_search_decision(right[index])
        if _selected_identity(a) != _selected_identity(b):
            divergent.append(
                {
                    "cohort_index": index,
                    "baseline": _selected_identity(a),
                    "guided": _selected_identity(b),
                }
            )
    return {
        "divergent_record_count": len(divergent),
        "records": divergent,
    }


def _first_search_decision(row: Mapping[str, Any]) -> Mapping[str, Any]:
    telemetry = row.get("controller_compute_telemetry")
    if not isinstance(telemetry, Mapping):
        return {}
    reports = telemetry.get("oracle_search_decision_reports")
    for value in _flatten(reports):
        if isinstance(value, Mapping) and "selected_action_identity" in value:
            return value
    return {}


def _selected_identity(report: Mapping[str, Any]) -> Any:
    return report.get("selected_action_identity")


def _geometry_record(row: Mapping[str, Any], budget: int) -> dict[str, Any]:
    telemetry = row.get("controller_compute_telemetry")
    if not isinstance(telemetry, Mapping):
        raise ValueError("T070 geometry record lacks controller telemetry")
    values = [
        value
        for value in _flatten(telemetry.get("t070_tree_geometry_records"))
        if isinstance(value, Mapping)
        and value.get("schema_id") == "t070-search-tree-geometry-decision-v1"
    ]
    if not values:
        raise ValueError("T070 prior_value record has no geometry decisions")
    decisions = [_geometry_decision(value) for value in values]
    return {
        "cohort_index": row["cohort_index"],
        "budget": budget,
        "decision_count": len(decisions),
        "first_decision": decisions[0],
        "decisions": decisions,
        "record_max_expanded_depth": max(
            decision["maximum_expanded_depth"] for decision in decisions
        ),
        "command_passed": True,
    }


def _geometry_decision(value: Mapping[str, Any]) -> dict[str, Any]:
    geometry = value.get("native_geometry")
    roots = value.get("root_actions")
    if not isinstance(geometry, Mapping) or not isinstance(roots, Sequence):
        raise ValueError("T070 geometry decision is incomplete")
    depth_rows = []
    branch_factors = []
    native_rows = geometry.get("depth_rows")
    if not isinstance(native_rows, Sequence):
        raise ValueError("T070 geometry depth rows are missing")
    for index, raw in enumerate(native_rows):
        if not isinstance(raw, Mapping) or raw.get("depth") != index:
            raise ValueError("T070 geometry depth rows are not ordered")
        expanded = _as_int(raw.get("expanded_node_count"))
        discovered = _as_int(raw.get("discovered_child_edge_count"))
        visited = _as_int(raw.get("visited_child_edge_count"))
        histogram = raw.get("branching_histogram")
        if not isinstance(histogram, Sequence):
            raise ValueError("T070 geometry branching histogram is missing")
        factors = [
            _as_int(bucket["child_count"])
            for bucket in histogram
            if isinstance(bucket, Mapping)
            for _ in range(_as_int(bucket.get("node_count")))
        ]
        branch_factors.extend(factors)
        next_expanded = (
            _as_int(native_rows[index + 1].get("expanded_node_count"))
            if index + 1 < len(native_rows)
            and isinstance(native_rows[index + 1], Mapping)
            else 0
        )
        depth_rows.append(
            {
                **dict(raw),
                "effective_branching_factor": discovered / max(expanded, 1),
                "visited_edge_coverage_next_depth": visited / max(discovered, 1),
                "expanded_node_coverage_next_depth": (
                    next_expanded / max(discovered, 1)
                ),
            }
        )
    visits = sorted(
        (_as_int(root.get("visits")) for root in roots if isinstance(root, Mapping)),
        reverse=True,
    )
    total_visits = sum(visits)
    entropy = (
        -sum(
            (count / total_visits) * math.log(count / total_visits)
            for count in visits
            if count > 0
        )
        if total_visits
        else 0.0
    )
    return {
        "decision_step_index": value.get("decision_step_index"),
        "expanded_nodes_by_depth": [row["expanded_node_count"] for row in depth_rows],
        "discovered_edges_by_depth": [
            row["discovered_child_edge_count"] for row in depth_rows
        ],
        "visited_edges_by_depth": [
            row["visited_child_edge_count"] for row in depth_rows
        ],
        "depth_rows": depth_rows,
        "branch_factor_summary": {
            "mean": statistics.fmean(branch_factors) if branch_factors else 0.0,
            "median": statistics.median(branch_factors) if branch_factors else 0.0,
            "p90": _percentile(branch_factors, 0.90),
            "maximum": max(branch_factors, default=0),
        },
        "maximum_expanded_depth": geometry.get("max_expanded_depth"),
        "root_legal_action_count": value.get("root_legal_action_count"),
        "root_visit_entropy": entropy,
        "root_top1_minus_top2_visit_gap": (
            visits[0] - visits[1] if len(visits) > 1 else (visits[0] if visits else 0)
        ),
        "root_visit_leader_identity": _root_visit_leader(roots),
        "selected_root_action": value.get("selected_action_identity"),
        "native_simulator_steps": value.get("native_simulator_steps"),
        "model_calls": value.get("model_calls"),
        "wall_clock_seconds": value.get("wall_clock_seconds"),
    }


def _budget_sufficiency(
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[bool, dict[str, Any]]:
    at100 = {int(row["cohort_index"]): row["first_decision"] for row in rows["100"]}
    at1600 = {int(row["cohort_index"]): row["first_decision"] for row in rows["1600"]}
    selected_changes = sum(
        at100[index]["selected_root_action"] != at1600[index]["selected_root_action"]
        for index in at100
    )
    leader_changes = sum(
        at100[index]["root_visit_leader_identity"]
        != at1600[index]["root_visit_leader_identity"]
        for index in at100
    )
    depth100 = [value["maximum_expanded_depth"] for value in at100.values()]
    depth1600 = [value["maximum_expanded_depth"] for value in at1600.values()]
    depth_growth = statistics.median(depth1600) - statistics.median(depth100)
    depth2_coverage = [
        _depth_coverage(value, 1, "expanded_node_coverage_next_depth")
        for value in at100.values()
    ]
    low_depth2 = statistics.median(depth2_coverage) < 0.25
    continuing = statistics.median(depth1600) > statistics.median(depth100)
    conditions = {
        "selected_actions_change_at_least_4": selected_changes >= 4,
        "root_visit_leaders_change_at_least_4": leader_changes >= 4,
        "median_max_depth_grows_at_least_2": depth_growth >= 2,
        "low_depth2_coverage_and_depth_continues": low_depth2 and continuing,
    }
    return any(conditions.values()), {
        "selected_action_change_count": selected_changes,
        "root_visit_leader_change_count": leader_changes,
        "median_max_depth_100": statistics.median(depth100),
        "median_max_depth_1600": statistics.median(depth1600),
        "median_max_depth_growth": depth_growth,
        "median_depth2_expanded_node_coverage_100": statistics.median(depth2_coverage),
        "conditions": conditions,
    }


def _high_budget_signal(
    *,
    pv_growth: Mapping[str, Any],
    pv_vs_baseline_1600: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    overall_growth = pv_growth["overall"]
    versus = pv_vs_baseline_1600
    tied_hp = overall_growth["mean_terminal_hp_delta_among_outcome_ties"]
    values = {
        "prior_value_1600_vs_100_paired_win_delta": overall_growth["paired_win_delta"],
        "prior_value_1600_vs_baseline_1600_paired_win_delta": versus["overall"][
            "paired_win_delta"
        ],
        "prior_value_1600_vs_100_mean_tied_terminal_hp_delta": tied_hp,
        "prior_value_1600_vs_100_act2_plus_paired_win_delta": pv_growth["act2_plus"][
            "paired_win_delta"
        ],
    }
    conditions = {
        "paired_win_growth_at_least_2": values[
            "prior_value_1600_vs_100_paired_win_delta"
        ]
        >= 2,
        "nonnegative_vs_baseline_1600": values[
            "prior_value_1600_vs_baseline_1600_paired_win_delta"
        ]
        >= 0,
        "nonnegative_tied_terminal_hp": tied_hp is not None and tied_hp >= 0,
        "no_act2_plus_win_regression": values[
            "prior_value_1600_vs_100_act2_plus_paired_win_delta"
        ]
        >= 0,
    }
    return all(conditions.values()), {"values": values, "conditions": conditions}


def _primary_promotion(primary: Mapping[str, Any]) -> dict[str, Any]:
    families = primary["families"]
    equal = families["equal_nominal"]["paired_vs_baseline"]["prior_value"]
    simstep = families["simulator_step_normalized"]["paired_vs_baseline"]["prior_value"]
    wall = families["wall_clock_normalized"]["paired_vs_baseline"]["prior_value"]
    zero_failures = not primary.get("failure_problems")
    equal_gate = (
        equal["overall"]["paired_win_delta"] > 0
        and equal["overall"]["paired_win_delta_bootstrap_95ci"][0] >= 0
        and equal["boss_only"]["paired_win_delta"] >= 0
        and equal["act2_plus"]["paired_win_delta"] >= 0
    )
    normalized = all(
        pair[stratum]["paired_win_delta"] >= 0
        for pair in (simstep, wall)
        for stratum in ("overall", "boss_only", "act2_plus")
    ) and (
        simstep["overall"]["paired_win_delta"] > 0
        or wall["overall"]["paired_win_delta"] > 0
    )
    tied_hp = all(
        pair[stratum]["mean_terminal_hp_delta_among_outcome_ties"] is not None
        and pair[stratum]["mean_terminal_hp_delta_among_outcome_ties"] >= 0
        for pair in (equal, simstep, wall)
        for stratum in ("overall", "boss_only", "act2_plus")
    )
    sim_ratio = simstep["overall"]["cost_ratio_guided_over_baseline"][
        "native_simulator_steps"
    ]
    wall_ratio = wall["overall"]["cost_ratio_guided_over_baseline"][
        "wall_clock_seconds"
    ]
    cost = (
        sim_ratio is not None
        and abs(sim_ratio - 1.0) <= 0.05
        and wall_ratio is not None
        and abs(wall_ratio - 1.0) <= 0.10
    )
    gates = {
        "zero_failures": zero_failures,
        "equal_nominal_prior_value": equal_gate,
        "compute_normalized_prior_value": normalized,
        "tied_terminal_hp": tied_hp,
        "matched_cost": cost,
    }
    return {
        "gates": gates,
        "passed": all(gates.values()),
        "simulator_step_cost_ratio": sim_ratio,
        "wall_clock_cost_ratio": wall_ratio,
    }


def _root_visit_leader(roots: Sequence[Any]) -> Any:
    candidates = [root for root in roots if isinstance(root, Mapping)]
    if not candidates:
        return None
    leader = max(
        candidates,
        key=lambda row: (
            _as_int(row.get("visits")),
            -_as_int(row.get("legal_action_index")),
        ),
    )
    return leader.get("action_identity")


def _depth_coverage(value: Mapping[str, Any], depth: int, key: str) -> float:
    rows = value.get("depth_rows")
    if not isinstance(rows, Sequence) or depth >= len(rows):
        return 0.0
    row = rows[depth]
    return float(row.get(key, 0.0)) if isinstance(row, Mapping) else 0.0


def _percentile(values: Sequence[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil(quantile * len(ordered)) - 1
    return float(ordered[max(0, min(index, len(ordered) - 1))])


def _flatten(value: Any):
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            yield from _flatten(item)
    else:
        yield value


def _identity(path: Path, expected_sha256: str | None) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"T070 input is missing: {path}")
    actual = _sha256(path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise ValueError(f"T070 input hash mismatch: {path}")
    return {
        "path": str(path.resolve()),
        "sha256": actual,
        "bytes": path.stat().st_size,
        "schema_id": _json_schema(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_schema(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value.get("schema_id") if isinstance(value, Mapping) else None


def _load_schema(path: Path, schema_id: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_id") != schema_id:
        raise ValueError(f"unsupported T070 schema in {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"T070 writer refuses to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _as_int(value: Any) -> int:
    return (
        int(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else 0
    )
