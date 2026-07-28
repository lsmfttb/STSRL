from __future__ import annotations

from sts_combat_rl.commands.t069_public_context_projection import (
    T069_DECISION_SCHEMA_ID,
    T069_FEASIBILITY_SCHEMA_ID,
    T069_SEMANTIC_SCHEMA_ID,
    build_t069_attribution_and_feasibility_report,
    build_t069_calibration_report,
    build_t069_decision_report,
)


GUIDED = ("prior_only", "value_only", "prior_value")


def _comparison(*, projected: bool, wall_after: float = 75.0):
    arms = {}
    provenance = {}
    for arm in ("baseline", *GUIDED):
        cost_key = "t069_cost_attribution" if projected else "t067_cost_attribution"
        cost = {
            "checkpoint_feature_encoding_ms": (5000.0 if projected else 50000.0),
            "public_context_schema_validation_encoding_ms": (
                0.0 if projected else 50000.0
            ),
            "public_context_feature_encoding_ms": (0.0 if projected else 50000.0),
            "snapshot_action_schema_validation_ms": 1.0,
            "projected_state_vector_assembly_ms": 1.0,
            "state_tensor_construction_ms": 1.0,
            "legal_action_tensor_construction_ms": 1.0,
            "tensor_construction_ms": 2.0,
            "policy_value_forward_pass_ms": 3.0,
            "inference_result_postprocess_ms": 1.0,
            "public_context_projection_construction_ms": (1.0 if projected else 0.0),
            "public_context_projection_validation_ms": (2.0 if projected else 0.0),
            "t069_input_identity_observer_ms": 1.0,
            "model_call_count": 1.0,
        }
        wall = 100.0 if arm == "baseline" else (wall_after if projected else 100.0)
        steps = 100.0
        telemetry = {
            "search_telemetry_summary": {
                "wall_clock_time_s": {"total": wall},
            }
        }
        if arm != "baseline":
            telemetry[cost_key] = cost
        arms[arm] = {
            "records": [
                {
                    "controller_compute_telemetry": telemetry,
                }
            ],
            "wall_clock_seconds": wall,
            "native_simulator_steps": steps,
        }
        provenance[arm] = {
            "config": {
                "task_id": (
                    "T062" if arm == "baseline" else ("T069" if projected else "T067")
                ),
                "search_budget": {"simulations": 100 if arm == "baseline" else 1},
            }
        }
    return {
        "schema_id": "t062-battle-search-v2-comparison-v1",
        "command_passed": True,
        "worker_count": 16,
        "shard_count": 16,
        "evaluated_record_count": 16,
        "family": "wall_clock_normalized",
        "controller_provenance": provenance,
        "arms": arms,
    }


def _identities(*, projected: bool):
    rows = []
    for arm in GUIDED:
        rows.append(
            {
                "schema_id": "t069-scorer-input-identity-v1",
                "arm": arm,
                "projected": projected,
                "cohort_index": 0,
                "search_scope_index": 0,
                "request_index": 0,
                "request_id": f"{arm}-{'p' if projected else 'u'}",
                "complete_public_context_sha256": "context",
                "complete_public_context_byte_count": 100,
                "public_context_feature_schema_id": "public-context-model-input-v1",
                "public_context_feature_schema_version": 1,
                "public_context_feature_names": ["a"],
                "public_context_feature_size": 1,
                "public_context_feature_sha256": "public",
                "tactical_feature_schema_id": "public-tactical-v2",
                "snapshot_feature_size": 1,
                "snapshot_feature_sha256": "snapshot",
                "state_feature_size": 2,
                "state_feature_sha256": "state",
                "ordered_legal_action_count": 1,
                "ordered_legal_action_row_sizes": [1],
                "ordered_legal_action_feature_sha256": "action",
                "ordered_legal_action_identities": [
                    {"stable_id": "x", "occurrence": 0}
                ],
                "eligible_action_indices": [0],
            }
        )
    return rows


def _feasibility(*, wall_after: float = 75.0):
    return build_t069_attribution_and_feasibility_report(
        unprojected=_comparison(projected=False),
        projected=_comparison(projected=True, wall_after=wall_after),
        unprojected_identity_records=_identities(projected=False),
        projected_identity_records=_identities(projected=True),
        semantic_report={
            "schema_id": T069_SEMANTIC_SCHEMA_ID,
            "command_passed": True,
        },
        input_identities={"t068_manifest": {"sha256": "abc"}},
        code_commit="a" * 40,
        native_commit="b" * 40,
    )


def test_t069_exact_material_projection_enters_calibration_and_case_a():
    feasibility = _feasibility()
    step_candidate = _comparison(projected=True, wall_after=100.0)
    step_candidate["family"] = "simulator_step_normalized"
    calibration = build_t069_calibration_report(
        [
            _comparison(projected=True, wall_after=100.0),
            step_candidate,
        ]
    )
    decision = build_t069_decision_report(feasibility, calibration)

    assert feasibility["schema_id"] == T069_FEASIBILITY_SCHEMA_ID
    assert feasibility["command_passed"] is True
    assert feasibility["feature_identity_pair_count"] == 3
    assert calibration["all_required_locks_succeeded"] is True
    assert decision["schema_id"] == T069_DECISION_SCHEMA_ID
    assert decision["decision_case"] == "A"
    assert decision["recommendation"] == ("T062-original-93-record-outcome-comparison")


def test_t069_material_projection_with_open_lock_selects_case_b():
    feasibility = _feasibility()
    candidate = _comparison(projected=True)
    candidate["arms"]["prior_only"]["native_simulator_steps"] = 1.0
    candidate["arms"]["prior_only"]["wall_clock_seconds"] = 200.0
    calibration = build_t069_calibration_report([candidate])
    decision = build_t069_decision_report(feasibility, calibration)

    assert calibration["all_required_locks_succeeded"] is False
    assert calibration["minimum_budget_infeasible_arms"] == ["prior_only"]
    assert decision["decision_case"] == "B"
    assert decision["recommendation"] == "search-v2-no-promotion-outcome-canary"


def test_t069_immaterial_projection_fails_closed_to_case_c():
    feasibility = _feasibility(wall_after=99.0)
    decision = build_t069_decision_report(feasibility, None)

    assert feasibility["command_passed"] is False
    assert decision["decision_case"] == "C"
    assert decision["recommendation"] == (
        "T064-simulator-generated-later-act-curriculum"
    )


def test_t069_feature_identity_mismatch_is_not_exact():
    right = _identities(projected=True)
    right[0] = {**right[0], "state_feature_sha256": "different"}
    report = build_t069_attribution_and_feasibility_report(
        unprojected=_comparison(projected=False),
        projected=_comparison(projected=True),
        unprojected_identity_records=_identities(projected=False),
        projected_identity_records=right,
        semantic_report={
            "schema_id": T069_SEMANTIC_SCHEMA_ID,
            "command_passed": True,
        },
        input_identities={"t068_manifest": {"sha256": "abc"}},
        code_commit="a" * 40,
        native_commit="b" * 40,
    )

    assert report["gates"]["exact_complete_scorer_inputs"] is False
    assert report["command_passed"] is False
