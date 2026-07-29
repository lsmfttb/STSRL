from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from sts_combat_rl.commands.t069_public_context_projection import (
    T069_DECISION_SCHEMA_ID,
    T069_FEASIBILITY_SCHEMA_ID,
    T069_SEMANTIC_SCHEMA_ID,
    build_t069_attribution_and_feasibility_report,
    build_t069_calibration_report,
    build_t069_decision_report,
    build_t069_precalibration_decision_report,
)


GUIDED = ("prior_only", "value_only", "prior_value")


def _load_t069_finalizer():
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "finalize_t069_artifacts.py"
    )
    specification = importlib.util.spec_from_file_location("t069_finalizer", script)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


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
        records = []
        for cohort_index in range(16):
            telemetry = {
                "oracle_search_native_simulator_steps": steps / 16,
                "oracle_search_model_calls": 0.0,
                "search_telemetry_summary": {
                    "wall_clock_time_s": {"total": wall / 16},
                },
            }
            if arm != "baseline":
                telemetry[cost_key] = cost
            records.append(
                {
                    "cohort_index": cohort_index,
                    "source_checkpoint_id": f"source-{cohort_index}",
                    "structural_metadata": {
                        "source_run_id": f"run-{cohort_index}",
                        "source_battle_index": cohort_index,
                    },
                    "termination_status": "loss",
                    "problems": [],
                    "outer_simulator_steps": 1.0,
                    "wall_clock_seconds": wall / 16,
                    "controller_compute_telemetry": telemetry,
                }
            )
        arms[arm] = {
            "record_count": 16,
            "errors": 0,
            "truncations": 0,
            "outer_simulator_steps": 16.0,
            "model_calls": 0.0,
            "records": records,
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
        "task_id": "T062",
        "report_kind": "merged_comparison",
        "command_passed": True,
        "problems": [],
        "worker_count": 16,
        "shard_count": 16,
        "shards": [f"shard-{index:02d}.json" for index in range(16)],
        "evaluated_record_count": 16,
        "expected_record_count": 16,
        "cohort_total_record_count": 93,
        "cohort_identity": "test-cohort",
        "action_space": {"preferred_kinds": ["card", "end_turn"]},
        "max_battle_steps": 200,
        "family": "wall_clock_normalized",
        "controller_provenance": provenance,
        "arms": arms,
        "paired_vs_baseline": {arm: {} for arm in GUIDED},
    }


def _set_arm_costs(report, arm, *, wall=None, steps=None):
    arm_report = report["arms"][arm]
    if wall is not None:
        arm_report["wall_clock_seconds"] = wall
        for record in arm_report["records"]:
            record["wall_clock_seconds"] = wall / 16
            record["controller_compute_telemetry"]["search_telemetry_summary"][
                "wall_clock_time_s"
            ]["total"] = wall / 16
    if steps is not None:
        arm_report["native_simulator_steps"] = steps
        for record in arm_report["records"]:
            record["controller_compute_telemetry"][
                "oracle_search_native_simulator_steps"
            ] = steps / 16


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
    _set_arm_costs(candidate, "prior_only", wall=200.0, steps=1.0)
    calibration = build_t069_calibration_report([candidate])
    decision = build_t069_decision_report(feasibility, calibration)

    assert calibration["all_required_locks_succeeded"] is False
    assert calibration["minimum_budget_infeasible_arms"] == ["prior_only"]
    assert calibration["calibration_complete"] is True
    assert calibration["continuation_required"] is False
    assert decision["decision_case"] == "B"
    assert decision["recommendation"] == "search-v2-no-promotion-outcome-canary"


def test_t069_budget_one_without_infeasibility_requires_continuation():
    feasibility = _feasibility()
    candidate = _comparison(projected=True, wall_after=100.0)

    calibration = build_t069_calibration_report([candidate])

    assert calibration["all_required_locks_succeeded"] is False
    assert calibration["minimum_budget_infeasible_arms"] == []
    assert calibration["calibration_complete"] is False
    assert calibration["continuation_required"] is True
    assert calibration["terminal_reason"] == (
        "candidate_sequence_continuation_required"
    )
    assert calibration["command_passed"] is False
    with pytest.raises(ValueError, match="sequence is not terminal"):
        build_t069_decision_report(feasibility, calibration)


def test_t069_calibration_validates_expansion_and_adjacent_refinement():
    feasibility = _feasibility()
    initial = _comparison(projected=True, wall_after=100.0)
    _set_arm_costs(initial, "prior_only", wall=50.0)
    budget_two = _comparison(projected=True, wall_after=100.0)
    budget_two["controller_provenance"]["prior_only"]["config"]["search_budget"][
        "simulations"
    ] = 2
    _set_arm_costs(budget_two, "prior_only", wall=60.0)
    budget_four = _comparison(projected=True, wall_after=100.0)
    budget_four["controller_provenance"]["prior_only"]["config"]["search_budget"][
        "simulations"
    ] = 4
    _set_arm_costs(budget_four, "prior_only", wall=120.0)

    crossing = build_t069_calibration_report([initial, budget_two, budget_four])

    prior_only = crossing["family_states"]["wall_clock_normalized"]["arms"][
        "prior_only"
    ]
    assert crossing["command_passed"] is False
    assert prior_only["status"] == "continuation_required"
    assert prior_only["next_candidate_budget"] == 3
    assert prior_only["lower_bracket"]["budget"] == 2
    assert prior_only["upper_bracket"]["budget"] == 4

    budget_three = _comparison(projected=True, wall_after=100.0)
    budget_three["controller_provenance"]["prior_only"]["config"]["search_budget"][
        "simulations"
    ] = 3
    _set_arm_costs(budget_three, "prior_only", wall=80.0)
    terminal = build_t069_calibration_report(
        [initial, budget_two, budget_four, budget_three]
    )
    decision = build_t069_decision_report(feasibility, terminal)

    assert terminal["minimum_budget_infeasible_arms"] == []
    assert terminal["proven_infeasible_arms"] == ["prior_only"]
    assert terminal["calibration_complete"] is True
    assert terminal["infeasibility_proofs"] == [
        {
            "family": "wall_clock_normalized",
            "arm": "prior_only",
            "proof_kind": "adjacent_integer_bracket",
            "lower_budget": 3,
            "lower_ratio": 0.8,
            "upper_budget": 4,
            "upper_ratio": 1.2,
            "reason": (
                "adjacent integer budgets fall below and above the tolerance "
                "interval, so no legal integer candidate can lock"
            ),
        }
    ]
    assert decision["decision_case"] == "B"


def test_t069_calibration_rejects_skipped_expansion_candidate():
    initial = _comparison(projected=True, wall_after=50.0)
    skipped = _comparison(projected=True, wall_after=60.0)
    for arm in GUIDED:
        skipped["controller_provenance"][arm]["config"]["search_budget"][
            "simulations"
        ] = 4

    with pytest.raises(ValueError, match="expected candidate budget 2, got 4"):
        build_t069_calibration_report([initial, skipped])


def test_t069_calibration_rejects_candidate_source_identity_drift():
    initial = _comparison(projected=True, wall_after=100.0)
    step_candidate = _comparison(projected=True, wall_after=100.0)
    step_candidate["family"] = "simulator_step_normalized"
    for arm in ("baseline", *GUIDED):
        step_candidate["arms"][arm]["records"][7]["source_checkpoint_id"] = (
            "different-source"
        )

    with pytest.raises(ValueError, match="same cohort.*0:16 source identities"):
        build_t069_calibration_report([initial, step_candidate])


def test_t069_prototype_case_b_cannot_preempt_independent_case_a():
    feasibility = _feasibility()
    prototype = _comparison(projected=True, wall_after=200.0)
    prototype_calibration = build_t069_calibration_report([prototype])
    assert set(prototype_calibration["minimum_budget_infeasible_arms"]) == set(GUIDED)

    assert build_t069_precalibration_decision_report(feasibility) is None

    wall_candidate = _comparison(projected=True, wall_after=100.0)
    step_candidate = _comparison(projected=True, wall_after=100.0)
    step_candidate["family"] = "simulator_step_normalized"
    independent_calibration = build_t069_calibration_report(
        [wall_candidate, step_candidate]
    )
    independent_decision = build_t069_decision_report(
        feasibility,
        independent_calibration,
    )

    assert independent_calibration["all_required_locks_succeeded"] is True
    assert independent_decision["decision_case"] == "A"


@pytest.mark.parametrize(
    ("arm", "budget"),
    [
        ("baseline", 99),
        ("prior_only", 2),
        ("value_only", 2),
        ("prior_value", 2),
    ],
)
def test_t069_calibration_validates_initial_budget_one_candidate(arm, budget):
    candidate = _comparison(projected=True, wall_after=100.0)
    candidate["controller_provenance"][arm]["config"]["search_budget"][
        "simulations"
    ] = budget

    with pytest.raises(ValueError, match="baseline.*budget|must start"):
        build_t069_calibration_report([candidate])


def test_t069_immaterial_projection_fails_closed_to_case_c():
    feasibility = _feasibility(wall_after=99.0)
    decision = build_t069_precalibration_decision_report(feasibility)

    assert decision is not None
    assert feasibility["command_passed"] is False
    assert decision["decision_case"] == "C"
    assert decision["recommendation"] == (
        "T064-simulator-generated-later-act-curriculum"
    )


def test_t069_finalizer_case_c_runs_without_calibration(tmp_path, monkeypatch):
    finalizer = _load_t069_finalizer()
    root = (
        tmp_path
        / "artifacts"
        / "t069-public-node-feature-encoding-projection-feasibility"
        / "case-c"
    )
    root.mkdir(parents=True)
    source_root = Path(tmp_path.anchor) / "t069-stable-source"
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    (root / "t069-feasibility.json").write_text(
        json.dumps(_feasibility(wall_after=99.0)),
        encoding="utf-8",
    )
    (root / "t069-stage-execution.json").write_text(
        json.dumps(
            {
                "schema_id": "t069-stage-execution-v1",
                "command_passed": True,
                "projection_attribution": {"worker_count": 16},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "finalize_t069_artifacts.py",
            "--artifact-root",
            str(root),
            "--source-root",
            str(source_root),
            "--input-root",
            str(input_root),
            "--code-commit",
            "c" * 40,
        ],
    )

    assert finalizer.main() == 0

    decision = json.loads((root / "t069-decision.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (root / "t069-retention-manifest.json").read_text(encoding="utf-8")
    )
    assert decision["decision_case"] == "C"
    assert not (root / "t069-calibration.json").exists()
    assert manifest["calibration"] == {
        "status": "not_run",
        "reason": "feasibility_did_not_authorize_calibration",
    }
    finalizer_command = manifest["regeneration_commands"][-1]
    assert "finalize_t069_artifacts.py" in finalizer_command
    assert "--candidate-report" not in finalizer_command


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
