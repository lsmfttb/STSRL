"""T067 cost-attribution report builders.

The simulator execution remains the T062 fixed-cohort workflow.  This module
wraps its current-schema reports with a versioned T067 attribution surface and
fails closed when any of the four arms or required timing fields are missing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t062_battle_search_v2 import T062_ARM_LABELS


T067_COMPARISON_SCHEMA_ID = "t067-battle-search-v2-cost-comparison-v1"
T067_ATTRIBUTION_SCHEMA_ID = "t067-battle-search-v2-cost-attribution-v1"
T067_ATTRIBUTION_SCHEMA_VERSION = 1
T067_CALIBRATION_SCHEMA_ID = "t067-battle-search-v2-calibration-v1"
T067_DECISION_SCHEMA_ID = "t067-battle-search-v2-decision-v1"
T067_RETENTION_SCHEMA_ID = "t067-battle-search-v2-retention-manifest-v2"
T067_REPAIR_IDENTITY = "exact-public-node-inference-cache-v1"
T067_NEXT_RECOMMENDATION = "T068-native-boundary-batched-inference-feasibility"
T067_DETERMINISTIC_CANDIDATE_RULE = {
    "initial_budget": 1,
    "expansion_sequence": [1, 2, 4, 8, 16, 32, 64, 100, 128, 256, 512, 1024],
    "refinement": (
        "after first crossing, bisect the adjacent integer interval; choose the "
        "lower midpoint first until a tolerance lock or adjacent budgets remain"
    ),
    "outcome_independent": True,
}
T067_REQUIRED_COST_FIELDS = (
    "native_tree_search_excluding_python_callbacks_ms",
    "node_context_projection_ms",
    "checkpoint_feature_encoding_ms",
    "tensor_construction_ms",
    "policy_value_forward_pass_ms",
    "inference_result_postprocess_ms",
    "python_native_callback_overhead_ms",
    "cache_lookup_ms",
    "cache_lookup_count",
    "cache_hit_count",
    "cache_miss_count",
    "cache_eviction_count",
    "cache_eviction_ms",
    "policy_callback_count",
    "value_callback_count",
    "model_call_count",
)


def build_t067_cost_attribution_report(
    t062_report: Mapping[str, Any],
    *,
    input_identities: Mapping[str, Mapping[str, Any]],
    candidate_budget: Mapping[str, int],
    normalization_family: str,
    worker_count: int,
    shard_count: int,
    record_range: str,
) -> dict[str, Any]:
    """Validate one merged T062-shaped report and add T067 attribution."""

    if t062_report.get("schema_id") != "t062-battle-search-v2-comparison-v1":
        raise ValueError("T067 attribution requires current T062 comparison schema")
    if t062_report.get("report_kind") != "merged_comparison":
        raise ValueError("T067 attribution requires a merged comparison report")
    if worker_count != 16 or shard_count != 16:
        raise ValueError("T067 substantial calibration requires 16 workers and shards")
    if record_range != "0:16":
        raise ValueError("T067 calibration requires record range 0:16")
    arms = t062_report.get("arms")
    if not isinstance(arms, Mapping) or set(arms) != set(T062_ARM_LABELS):
        raise ValueError("T067 report must retain exactly the four T062 arms")
    provenance = t062_report.get("controller_provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != set(T062_ARM_LABELS):
        raise ValueError("T067 report has incomplete arm provenance")
    for label in T062_ARM_LABELS[1:]:
        arm_provenance = provenance[label]
        if not isinstance(arm_provenance, Mapping):
            raise ValueError(f"T067 {label} provenance is malformed")
        config = arm_provenance.get("config")
        if not isinstance(config, Mapping):
            raise ValueError(f"T067 {label} config is malformed")
        repair = config.get("cost_repair")
        if (
            config.get("task_id") != "T067"
            or not isinstance(repair, Mapping)
            or repair.get("repair_identity") != T067_REPAIR_IDENTITY
            or repair.get("inference_cache_enabled") is not True
        ):
            raise ValueError(f"T067 {label} does not use the accepted repair identity")

    attribution: dict[str, Any] = {}
    problems: list[str] = []
    for label in T062_ARM_LABELS:
        arm = arms[label]
        if not isinstance(arm, Mapping):
            raise ValueError(f"T067 arm {label} is malformed")
        records = arm.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise ValueError(f"T067 arm {label} must contain 16 records")
        rows = []
        for row in records:
            if not isinstance(row, Mapping):
                raise ValueError(f"T067 arm {label} has malformed record")
            telemetry = row.get("controller_compute_telemetry")
            if not isinstance(telemetry, Mapping):
                if label != "baseline":
                    raise ValueError(f"T067 guided arm {label} lacks telemetry")
                continue
            cost = telemetry.get("t067_cost_attribution")
            if not isinstance(cost, Mapping):
                if label != "baseline":
                    raise ValueError(f"T067 guided arm {label} lacks cost telemetry")
                continue
            missing = [
                field for field in T067_REQUIRED_COST_FIELDS if field not in cost
            ]
            if missing:
                raise ValueError(f"T067 {label} telemetry missing {missing}")
            if label != "baseline":
                model_calls = _number(cost["model_call_count"])
                cache_misses = _number(cost["cache_miss_count"])
                callbacks = _number(cost["policy_callback_count"]) + _number(
                    cost["value_callback_count"]
                )
                lookups = _number(cost["cache_lookup_count"])
                if model_calls != cache_misses:
                    raise ValueError(
                        f"T067 {label} model calls do not equal exact cache misses"
                    )
                if callbacks != lookups:
                    raise ValueError(
                        f"T067 {label} callback and cache lookup counts differ"
                    )
            rows.append({str(key): _number(value) for key, value in cost.items()})
        attribution[label] = _aggregate_rows(rows, label)
        if any(row.get("problems") for row in records if isinstance(row, Mapping)):
            problems.append(f"{label}: record problems present")

    report = {
        "schema_id": T067_COMPARISON_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "report_kind": "merged_cost_comparison",
        "normalization_family": normalization_family,
        "record_range": record_range,
        "evaluated_record_count": t062_report.get("evaluated_record_count"),
        "cohort_identity": t062_report.get("cohort_identity"),
        "cohort_total_record_count": t062_report.get("cohort_total_record_count"),
        "worker_count": worker_count,
        "shard_count": shard_count,
        "candidate_budget": {
            str(key): int(value) for key, value in candidate_budget.items()
        },
        "input_identities": {
            str(key): dict(value) for key, value in input_identities.items()
        },
        "native_integration": _native_identity(provenance),
        "controller_provenance": {
            str(key): dict(value) for key, value in provenance.items()
        },
        "arm_attribution": attribution,
        "t062_comparison": dict(t062_report),
        "problems": problems,
        "command_passed": not problems and bool(t062_report.get("command_passed")),
    }
    return report


def build_t067_calibration_manifest(
    candidate_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the published minimum-budget cost gate to one 16-record candidate.

    One required wall-clock arm above tolerance at budget 1 is a mathematical
    all-lock failure: no lower legal integer budget exists.  The report still
    records the initial simulator-step result and deterministic next candidate
    for every arm, but fail-closes before spending more simulator time on a
    calibration that cannot authorize the 93-record comparison.
    """

    if candidate_report.get("schema_id") != T067_COMPARISON_SCHEMA_ID:
        raise ValueError("T067 calibration requires current cost comparison schema")
    if not candidate_report.get("command_passed"):
        raise ValueError("T067 calibration candidate did not pass")
    if (
        candidate_report.get("record_range") != "0:16"
        or candidate_report.get("worker_count") != 16
        or candidate_report.get("shard_count") != 16
        or candidate_report.get("evaluated_record_count") != 16
    ):
        raise ValueError("T067 calibration candidate must be 0:16 with 16 workers")
    budgets = candidate_report.get("candidate_budget")
    if not isinstance(budgets, Mapping) or set(budgets) != set(T062_ARM_LABELS):
        raise ValueError("T067 calibration candidate budgets are incomplete")
    if int(budgets["baseline"]) != 100 or any(
        int(budgets[label]) != 1 for label in T062_ARM_LABELS[1:]
    ):
        raise ValueError("T067 initial candidate must be baseline 100 and guided 1")

    raw = candidate_report.get("t062_comparison")
    if not isinstance(raw, Mapping):
        raise ValueError("T067 calibration candidate lacks raw comparison")
    arms = raw.get("arms")
    if not isinstance(arms, Mapping) or set(arms) != set(T062_ARM_LABELS):
        raise ValueError("T067 calibration raw arms are incomplete")
    baseline_steps = _positive_arm_total(arms, "baseline", "native_simulator_steps")
    baseline_wall = _positive_arm_total(arms, "baseline", "wall_clock_seconds")

    families: dict[str, Any] = {
        "simulator_step_normalized": {
            "metric": "native_simulator_steps",
            "tolerance_fraction": 0.05,
            "baseline_budget": 100,
            "baseline_total": baseline_steps,
            "arms": {},
        },
        "wall_clock_normalized": {
            "metric": "wall_clock_seconds",
            "tolerance_fraction": 0.10,
            "baseline_budget": 100,
            "baseline_total": baseline_wall,
            "arms": {},
        },
    }
    proven_infeasible: list[str] = []
    for label in T062_ARM_LABELS[1:]:
        step_total = _non_negative_arm_total(arms, label, "native_simulator_steps")
        wall_total = _non_negative_arm_total(arms, label, "wall_clock_seconds")
        step_lock = _candidate_lock(
            label=label,
            budget=1,
            total=step_total,
            baseline_total=baseline_steps,
            tolerance=0.05,
        )
        wall_lock = _candidate_lock(
            label=label,
            budget=1,
            total=wall_total,
            baseline_total=baseline_wall,
            tolerance=0.10,
        )
        families["simulator_step_normalized"]["arms"][label] = step_lock
        families["wall_clock_normalized"]["arms"][label] = wall_lock
        if wall_lock["status"] == "proven_infeasible_at_minimum":
            proven_infeasible.append(label)

    if proven_infeasible:
        for family in families.values():
            for lock in family["arms"].values():
                if lock["status"] == "requires_higher_candidate":
                    lock["next_candidate_status"] = (
                        "not_run_after_decisive_minimum_wall_clock_infeasibility"
                    )
                    lock["next_candidate_budget"] = 2
        stop_reason = (
            "at least one required wall-clock arm exceeds the upper tolerance "
            "at minimum legal budget 1; no candidate sequence can produce all locks"
        )
    else:
        stop_reason = None

    all_locks = all(
        lock["status"] == "locked"
        for family in families.values()
        for lock in family["arms"].values()
    )
    return {
        "schema_id": T067_CALIBRATION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "repair_identity": T067_REPAIR_IDENTITY,
        "calibration_is_cost_only": True,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "candidate_rule": dict(T067_DETERMINISTIC_CANDIDATE_RULE),
        "executed_candidate_budgets": [1],
        "families": families,
        "proven_infeasible_arms": proven_infeasible,
        "early_exit_reason": stop_reason,
        "all_required_locks_succeeded": all_locks,
        "primary_comparison_authorized": all_locks,
        "primary_comparison_status": (
            "authorized" if all_locks else "not_authorized_calibration_infeasible"
        ),
        "no_outcome_aggregation_performed": not all_locks,
        "command_passed": True,
    }


def build_t067_decision_report(
    calibration_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Emit the single fail-closed T067 recommendation."""

    if calibration_manifest.get("schema_id") != T067_CALIBRATION_SCHEMA_ID:
        raise ValueError("T067 decision requires current calibration schema")
    if not calibration_manifest.get("command_passed"):
        raise ValueError("T067 calibration manifest did not pass")
    primary_authorized = bool(calibration_manifest.get("primary_comparison_authorized"))
    if primary_authorized:
        raise ValueError(
            "T067 complete-run recommendation requires executed 93-record reports"
        )
    infeasible = calibration_manifest.get("proven_infeasible_arms")
    if not isinstance(infeasible, list) or not infeasible:
        raise ValueError("T067 early exit requires a proven infeasible arm")
    return {
        "schema_id": T067_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "repair_identity": T067_REPAIR_IDENTITY,
        "decision_path": "calibration_infeasibility_early_exit",
        "primary_comparison_authorized": False,
        "primary_comparison_status": "not_run_not_authorized",
        "fixed_cohort_outcome_claims": "not_authorized_not_reported",
        "controller_promotion_authorized": False,
        "current_search_v2_direction": "closed_after_semantic_cache_cost_repair",
        "proven_infeasible_arms": list(infeasible),
        "recommendation": T067_NEXT_RECOMMENDATION,
        "recommendation_count": 1,
        "recommendation_scope": (
            "one bounded feasibility task for batching public-node inference "
            "across the native callback boundary; no model or search change"
        ),
        "claims_excluded": [
            "normal_information_strength",
            "natural_a20_strength",
            "live_game_validation",
            "final_agent_evidence",
        ],
        "command_passed": True,
    }


def write_t067_report(path: Path, report: Mapping[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _aggregate_rows(rows: Sequence[Mapping[str, float]], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "record_count": len(rows),
        "timings": {},
    }
    for field in T067_REQUIRED_COST_FIELDS:
        values = [float(row.get(field, 0.0)) for row in rows]
        result["timings"][field] = _distribution(values)
    return result


def _candidate_lock(
    *,
    label: str,
    budget: int,
    total: float,
    baseline_total: float,
    tolerance: float,
) -> dict[str, Any]:
    ratio = total / baseline_total
    lower = 1.0 - tolerance
    upper = 1.0 + tolerance
    if lower <= ratio <= upper:
        status = "locked"
        reason = None
    elif ratio > upper and budget == 1:
        status = "proven_infeasible_at_minimum"
        reason = (
            f"{label}: budget 1 ratio {ratio:.12f} exceeds upper tolerance "
            f"{upper:.2f}; no lower legal integer budget exists"
        )
    else:
        status = "requires_higher_candidate"
        reason = (
            f"{label}: budget {budget} ratio {ratio:.12f} is below lower "
            f"tolerance {lower:.2f}"
            if ratio < lower
            else (
                f"{label}: budget {budget} ratio {ratio:.12f} crossed above "
                f"upper tolerance {upper:.2f}; deterministic refinement required"
            )
        )
    return {
        "budget": budget,
        "candidate_total": total,
        "baseline_total": baseline_total,
        "ratio_guided_over_baseline": ratio,
        "lower_tolerance": lower,
        "upper_tolerance": upper,
        "status": status,
        "reason": reason,
    }


def _positive_arm_total(arms: Mapping[str, Any], label: str, metric: str) -> float:
    value = _non_negative_arm_total(arms, label, metric)
    if value <= 0.0:
        raise ValueError(f"T067 {label} {metric} must be positive")
    return value


def _non_negative_arm_total(arms: Mapping[str, Any], label: str, metric: str) -> float:
    arm = arms.get(label)
    if not isinstance(arm, Mapping):
        raise ValueError(f"T067 arm {label} is missing")
    value = arm.get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"T067 arm {label} lacks numeric {metric}")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"T067 arm {label} has invalid {metric}")
    return number


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    finite = [value for value in values if math.isfinite(value) and value >= 0.0]
    if len(finite) != len(values):
        raise ValueError("T067 telemetry contains non-finite or negative values")
    ordered = sorted(finite)
    if not ordered:
        return {
            "count": 0,
            "total": 0.0,
            "minimum": None,
            "maximum": None,
            "mean": None,
            "p50": None,
            "p95": None,
        }
    return {
        "count": len(ordered),
        "total": sum(ordered),
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "mean": sum(ordered) / len(ordered),
        "p50": _quantile(ordered, 0.50),
        "p95": _quantile(ordered, 0.95),
    }


def _quantile(values: Sequence[float], quantile: float) -> float:
    index = min(len(values) - 1, max(0, int(math.ceil(quantile * len(values)) - 1)))
    return float(values[index])


def _native_identity(provenance: Mapping[str, Any]) -> dict[str, Any]:
    values = []
    for label in T062_ARM_LABELS:
        config = provenance[label].get("config", {})
        identity = config.get("native_source_identity")
        if isinstance(identity, Mapping):
            values.append(dict(identity))
    if not values or any(identity != values[0] for identity in values[1:]):
        raise ValueError("T067 arm native source identities differ or are missing")
    return values[0]


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("T067 cost telemetry values must be numeric")
    return float(value)
