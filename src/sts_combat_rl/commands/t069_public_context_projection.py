"""Strict T069 projection feasibility, calibration, and decision reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from sts_combat_rl.commands.t062_battle_search_v2 import (
    T062_ARM_LABELS,
    T062_COMPARISON_SCHEMA_ID,
)
from sts_combat_rl.sim.public_context_feature_projection import (
    T069_PROJECTION_IMPLEMENTATION_ID,
)
from sts_combat_rl.sim.t069_feature_identity import (
    T069_FEATURE_IDENTITY_SCHEMA_ID,
)


T069_GUIDED_ARMS = ("prior_only", "value_only", "prior_value")
T069_ATTRIBUTION_SCHEMA_ID = "t069-feature-component-attribution-v1"
T069_SEMANTIC_SCHEMA_ID = "t069-projection-semantic-equivalence-v1"
T069_FEASIBILITY_SCHEMA_ID = "t069-public-context-projection-feasibility-v1"
T069_CALIBRATION_SCHEMA_ID = "t069-search-v2-cost-calibration-v1"
T069_DECISION_SCHEMA_ID = "t069-public-context-projection-decision-v1"
T069_STAGE_SCHEMA_ID = "t069-stage-execution-v1"
T069_RETENTION_SCHEMA_ID = "t069-retention-manifest-v1"
T069_ACCEPTED_T068_FEATURE_ENCODING_MS = {
    "prior_only": 46012.216903999724,
    "value_only": 48498.62396400033,
    "prior_value": 63462.21188099877,
}
T069_PUBLIC_CONTEXT_SHARE_MINIMUM = 0.50
T069_FEATURE_REDUCTION_MINIMUM = 0.50
T069_SEARCH_WALL_REDUCTION_MINIMUM = 0.05
T069_STEP_TOLERANCE = 0.05
T069_WALL_TOLERANCE = 0.10
T069_CANDIDATE_SEQUENCE = (1, 2, 4, 8, 16, 32, 64, 100, 128, 256, 512, 1024)


def build_t069_attribution_and_feasibility_report(
    *,
    unprojected: Mapping[str, Any],
    projected: Mapping[str, Any],
    unprojected_identity_records: Sequence[Mapping[str, Any]],
    projected_identity_records: Sequence[Mapping[str, Any]],
    semantic_report: Mapping[str, Any],
    input_identities: Mapping[str, Mapping[str, Any]],
    code_commit: str,
    native_commit: str,
) -> dict[str, Any]:
    """Validate paired 0:16 reports and evaluate the published feasibility gate."""

    _validate_comparison(unprojected, projected=False)
    _validate_comparison(projected, projected=True)
    if semantic_report.get("schema_id") != T069_SEMANTIC_SCHEMA_ID:
        raise ValueError("T069 feasibility requires current semantic report")
    if semantic_report.get("command_passed") is not True:
        raise ValueError("T069 feasibility semantic gate did not pass")
    for label, identity in input_identities.items():
        if not isinstance(identity, Mapping) or not identity.get("sha256"):
            raise ValueError(f"T069 input identity {label} is incomplete")

    pairs = _pair_identity_records(
        unprojected_identity_records,
        projected_identity_records,
    )
    costs: dict[str, Any] = {}
    for arm in T069_GUIDED_ARMS:
        before = _arm_cost(unprojected, arm, "t067_cost_attribution")
        after = _arm_cost(projected, arm, "t069_cost_attribution")
        accepted_feature_ms = T069_ACCEPTED_T068_FEATURE_ENCODING_MS[arm]
        public_ms = before["public_context_feature_encoding_ms"]
        public_share = public_ms / accepted_feature_ms
        feature_reduction = _reduction(
            before["checkpoint_feature_encoding_ms"],
            after["checkpoint_feature_encoding_ms"],
        )
        wall_reduction = _reduction(
            before["search_wall_clock_seconds"],
            after["search_wall_clock_seconds"],
        )
        costs[arm] = {
            "accepted_t068_checkpoint_feature_encoding_ms": accepted_feature_ms,
            "unprojected": before,
            "projected": after,
            "public_context_share_of_accepted_t068_feature_encoding": public_share,
            "checkpoint_feature_encoding_reduction_fraction": feature_reduction,
            "search_wall_clock_reduction_fraction": wall_reduction,
        }

    prior_value = costs["prior_value"]
    public_share_passed = (
        prior_value["public_context_share_of_accepted_t068_feature_encoding"]
        >= T069_PUBLIC_CONTEXT_SHARE_MINIMUM
    )
    feature_reduction_passed = (
        prior_value["checkpoint_feature_encoding_reduction_fraction"]
        >= T069_FEATURE_REDUCTION_MINIMUM
    )
    prior_value_wall_passed = (
        prior_value["search_wall_clock_reduction_fraction"]
        >= T069_SEARCH_WALL_REDUCTION_MINIMUM
    )
    diagnostic_wall_passed = any(
        costs[arm]["search_wall_clock_reduction_fraction"]
        >= T069_SEARCH_WALL_REDUCTION_MINIMUM
        for arm in ("prior_only", "value_only")
    )
    exactness_passed = bool(pairs) and all(
        pair["exact_complete_scorer_input"] for pair in pairs
    )
    material_passed = (
        public_share_passed
        and feature_reduction_passed
        and prior_value_wall_passed
        and diagnostic_wall_passed
    )
    baseline_wall = _positive_arm_total(projected, "baseline", "wall_clock_seconds")
    forecast = {
        arm: {
            "budget": _arm_budget(projected, arm),
            "wall_clock_ratio_to_baseline": (
                _positive_arm_total(projected, arm, "wall_clock_seconds")
                / baseline_wall
            ),
        }
        for arm in T069_GUIDED_ARMS
    }
    for value in forecast.values():
        value["within_1_10_ceiling"] = value["wall_clock_ratio_to_baseline"] <= 1.10

    passed = exactness_passed and material_passed
    return {
        "schema_id": T069_FEASIBILITY_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": code_commit,
        "native_commit": native_commit,
        "projection_implementation_id": T069_PROJECTION_IMPLEMENTATION_ID,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "input_identities": {
            str(label): dict(identity) for label, identity in input_identities.items()
        },
        "semantic_report": dict(semantic_report),
        "feature_identity_pair_count": len(pairs),
        "feature_identity_pairs": pairs,
        "component_attribution": costs,
        "gates": {
            "semantic_equivalence": True,
            "exact_complete_scorer_inputs": exactness_passed,
            "prior_value_public_context_share_at_least_0_50": public_share_passed,
            "prior_value_feature_reduction_at_least_0_50": (feature_reduction_passed),
            "prior_value_search_wall_reduction_at_least_0_05": (
                prior_value_wall_passed
            ),
            "prior_only_or_value_only_wall_reduction_at_least_0_05": (
                diagnostic_wall_passed
            ),
            "material_improvement": material_passed,
        },
        "minimum_budget_wall_forecast": forecast,
        "all_guided_arms_forecast_within_1_10": all(
            value["within_1_10_ceiling"] for value in forecast.values()
        ),
        "production_projection_integration_authorized": passed,
        "conditional_calibration_authorized": passed,
        "command_passed": passed,
        "problems": [] if passed else _gate_problems(exactness_passed, material_passed),
    }


def build_t069_calibration_report(
    candidate_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate executed candidates without inventing unmeasured budgets."""

    if not candidate_reports:
        raise ValueError("T069 calibration requires executed candidate reports")
    candidates: list[dict[str, Any]] = []
    for report in candidate_reports:
        _validate_comparison(report, projected=True)
        family = report.get("family")
        if family not in {
            "simulator_step_normalized",
            "wall_clock_normalized",
        }:
            raise ValueError("T069 calibration candidate family is invalid")
        budgets = {arm: _arm_budget(report, arm) for arm in T062_ARM_LABELS}
        baseline_steps = _positive_arm_total(
            report, "baseline", "native_simulator_steps"
        )
        baseline_wall = _positive_arm_total(report, "baseline", "wall_clock_seconds")
        arms: dict[str, Any] = {}
        for arm in T069_GUIDED_ARMS:
            step_ratio = (
                _positive_arm_total(report, arm, "native_simulator_steps")
                / baseline_steps
            )
            wall_ratio = (
                _positive_arm_total(report, arm, "wall_clock_seconds") / baseline_wall
            )
            arms[arm] = {
                "budget": budgets[arm],
                "simulator_step_ratio": step_ratio,
                "simulator_step_locked": abs(step_ratio - 1.0) <= T069_STEP_TOLERANCE,
                "wall_clock_ratio": wall_ratio,
                "wall_clock_locked": abs(wall_ratio - 1.0) <= T069_WALL_TOLERANCE,
                "wall_clock_proven_infeasible_at_minimum": (
                    budgets[arm] == 1 and wall_ratio > 1.0 + T069_WALL_TOLERANCE
                ),
            }
        candidates.append(
            {
                "family": family,
                "budgets": budgets,
                "arms": arms,
            }
        )
    final_locks = {
        arm: {
            "simulator_step": any(
                candidate["family"] == "simulator_step_normalized"
                and candidate["arms"][arm]["simulator_step_locked"]
                for candidate in candidates
            ),
            "wall_clock": any(
                candidate["family"] == "wall_clock_normalized"
                and candidate["arms"][arm]["wall_clock_locked"]
                for candidate in candidates
            ),
        }
        for arm in T069_GUIDED_ARMS
    }
    all_locks = all(
        values["simulator_step"] and values["wall_clock"]
        for values in final_locks.values()
    )
    return {
        "schema_id": T069_CALIBRATION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "projection_implementation_id": T069_PROJECTION_IMPLEMENTATION_ID,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "candidate_sequence": list(T069_CANDIDATE_SEQUENCE),
        "executed_candidates": candidates,
        "final_locks": final_locks,
        "all_required_locks_succeeded": all_locks,
        "minimum_budget_infeasible_arms": sorted(
            {
                arm
                for candidate in candidates
                for arm in T069_GUIDED_ARMS
                if candidate["family"] == "wall_clock_normalized"
                and candidate["arms"][arm]["wall_clock_proven_infeasible_at_minimum"]
            }
        ),
        "calibration_is_cost_only": True,
        "no_93_record_outcome_aggregation_performed": True,
        "command_passed": True,
    }


def build_t069_decision_report(
    feasibility: Mapping[str, Any],
    calibration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Select exactly one published terminal case and next recommendation."""

    if feasibility.get("schema_id") != T069_FEASIBILITY_SCHEMA_ID:
        raise ValueError("T069 decision requires current feasibility schema")
    material = feasibility.get("gates", {}).get("material_improvement") is True
    exact = feasibility.get("gates", {}).get("exact_complete_scorer_inputs") is True
    semantic = feasibility.get("gates", {}).get("semantic_equivalence") is True
    if not (material and exact and semantic):
        case = "C"
        recommendation = "T064-simulator-generated-later-act-curriculum"
        reason = "projection exactness or published material-improvement gate failed"
    else:
        if calibration is None or calibration.get("schema_id") != (
            T069_CALIBRATION_SCHEMA_ID
        ):
            raise ValueError("T069 material projection requires calibration report")
        if calibration.get("all_required_locks_succeeded") is True:
            case = "A"
            recommendation = "T062-original-93-record-outcome-comparison"
            reason = "all simulator-step and wall-clock calibration locks passed"
        else:
            case = "B"
            recommendation = "search-v2-no-promotion-outcome-canary"
            reason = (
                "projection was exact and material but at least one calibration "
                "lock remained open"
            )
    return {
        "schema_id": T069_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "decision_case": case,
        "reason": reason,
        "recommendation": recommendation,
        "exactly_one_next_recommendation": True,
        "current_semantics_preserving_cost_repair_line_closed": case in {"B", "C"},
        "no_second_cache_projection_or_component_micro_optimization": True,
        "no_93_record_outcome_aggregation_performed": True,
        "no_promotion_claim": True,
        "command_passed": True,
    }


def _validate_comparison(report: Mapping[str, Any], *, projected: bool) -> None:
    if report.get("schema_id") != T062_COMPARISON_SCHEMA_ID:
        raise ValueError("T069 requires current T062 comparison schema")
    if report.get("command_passed") is not True:
        raise ValueError("T069 comparison did not pass")
    if report.get("worker_count") != 16 or report.get("shard_count") != 16:
        raise ValueError("T069 substantial comparison requires 16 workers/shards")
    if report.get("evaluated_record_count") != 16:
        raise ValueError("T069 comparison must evaluate record range 0:16")
    provenance = report.get("controller_provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != set(T062_ARM_LABELS):
        raise ValueError("T069 comparison arm provenance is incomplete")
    for arm in T069_GUIDED_ARMS:
        config = provenance[arm].get("config", {})
        if projected:
            if config.get("task_id") != "T069":
                raise ValueError(f"T069 projected {arm} provenance is wrong")
        elif config.get("task_id") != "T067":
            raise ValueError(f"T069 unprojected {arm} is not accepted T068/T067")


def _pair_identity_records(
    unprojected: Sequence[Mapping[str, Any]],
    projected: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    left = {_identity_key(row): row for row in unprojected}
    right = {_identity_key(row): row for row in projected}
    if len(left) != len(unprojected) or len(right) != len(projected):
        raise ValueError("T069 feature identity request ids are duplicated")
    if set(left) != set(right):
        raise ValueError("T069 projected and unprojected request occurrences differ")
    pairs: list[dict[str, Any]] = []
    exact_fields = (
        "complete_public_context_sha256",
        "complete_public_context_byte_count",
        "public_context_feature_schema_id",
        "public_context_feature_schema_version",
        "public_context_feature_names",
        "public_context_feature_size",
        "public_context_feature_sha256",
        "tactical_feature_schema_id",
        "snapshot_feature_size",
        "snapshot_feature_sha256",
        "state_feature_size",
        "state_feature_sha256",
        "ordered_legal_action_count",
        "ordered_legal_action_row_sizes",
        "ordered_legal_action_feature_sha256",
        "ordered_legal_action_identities",
        "eligible_action_indices",
    )
    for key in sorted(left):
        a, b = left[key], right[key]
        exact = all(a.get(field) == b.get(field) for field in exact_fields)
        pairs.append(
            {
                "arm": key[0],
                "cohort_index": key[1],
                "search_scope_index": key[2],
                "request_index": key[3],
                "exact_complete_scorer_input": exact,
                "unprojected_request_id": a.get("request_id"),
                "projected_request_id": b.get("request_id"),
            }
        )
    return pairs


def _identity_key(row: Mapping[str, Any]) -> tuple[str, int, int, int]:
    if row.get("schema_id") != T069_FEATURE_IDENTITY_SCHEMA_ID:
        raise ValueError("T069 feature identity record schema is wrong")
    arm = row.get("arm")
    cohort = row.get("cohort_index")
    scope = row.get("search_scope_index")
    request = row.get("request_index")
    if (
        arm not in T069_GUIDED_ARMS
        or not isinstance(cohort, int)
        or isinstance(cohort, bool)
        or not isinstance(scope, int)
        or isinstance(scope, bool)
        or not isinstance(request, int)
        or isinstance(request, bool)
    ):
        raise ValueError("T069 feature identity occurrence is malformed")
    return str(arm), cohort, scope, request


def _arm_cost(
    report: Mapping[str, Any],
    arm: str,
    telemetry_key: str,
) -> dict[str, float]:
    fields = (
        "checkpoint_feature_encoding_ms",
        "public_context_schema_validation_encoding_ms",
        "public_context_feature_encoding_ms",
        "snapshot_action_schema_validation_ms",
        "projected_state_vector_assembly_ms",
        "state_tensor_construction_ms",
        "legal_action_tensor_construction_ms",
        "tensor_construction_ms",
        "policy_value_forward_pass_ms",
        "inference_result_postprocess_ms",
        "public_context_projection_construction_ms",
        "public_context_projection_validation_ms",
        "t069_input_identity_observer_ms",
        "model_call_count",
    )
    totals = {field: 0.0 for field in fields}
    records = report["arms"][arm]["records"]
    for record in records:
        telemetry = record.get("controller_compute_telemetry", {})
        cost = telemetry.get(telemetry_key, {})
        if not isinstance(cost, Mapping):
            raise ValueError(f"T069 {arm} lacks {telemetry_key}")
        for field in fields:
            value = cost.get(field, 0.0)
            if not _finite_nonnegative(value):
                raise ValueError(f"T069 {arm} has invalid cost field {field}")
            totals[field] += float(value)
    totals["search_wall_clock_seconds"] = _search_wall_seconds(records)
    totals["native_simulator_steps"] = _positive_arm_total(
        report, arm, "native_simulator_steps"
    )
    return totals


def _search_wall_seconds(records: Sequence[Mapping[str, Any]]) -> float:
    total = 0.0
    for record in records:
        summary = record.get("controller_compute_telemetry", {}).get(
            "search_telemetry_summary", {}
        )
        value = summary.get("wall_clock_time_s", {}).get("total")
        if not _finite_nonnegative(value):
            raise ValueError("T069 record lacks search wall-clock telemetry")
        total += float(value)
    if total <= 0:
        raise ValueError("T069 search wall-clock total must be positive")
    return total


def _arm_budget(report: Mapping[str, Any], arm: str) -> int:
    value = report["controller_provenance"][arm]["config"]["search_budget"][
        "simulations"
    ]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"T069 {arm} budget is invalid")
    return value


def _positive_arm_total(report: Mapping[str, Any], arm: str, field: str) -> float:
    value = report["arms"][arm].get(field)
    if not _finite_nonnegative(value) or float(value) <= 0:
        raise ValueError(f"T069 {arm} {field} must be positive")
    return float(value)


def _reduction(before: float, after: float) -> float:
    if before <= 0 or after < 0:
        raise ValueError("T069 reduction inputs are invalid")
    return (before - after) / before


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _gate_problems(exact: bool, material: bool) -> list[str]:
    problems: list[str] = []
    if not exact:
        problems.append("projected and unprojected complete scorer inputs differ")
    if not material:
        problems.append("published material-improvement thresholds were not met")
    return problems
