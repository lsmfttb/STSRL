from __future__ import annotations

from sts_combat_rl.commands.t067_battle_search_v2 import (
    T067_CALIBRATION_SCHEMA_ID,
    T067_DECISION_SCHEMA_ID,
    T067_REQUIRED_COST_FIELDS,
    build_t067_calibration_manifest,
    build_t067_cost_attribution_report,
    build_t067_decision_report,
)


def _cost_row(index: int) -> dict[str, object]:
    cost = {field: float(index + 1) for field in T067_REQUIRED_COST_FIELDS}
    cost["policy_callback_count"] = float(index + 1)
    cost["value_callback_count"] = 0.0
    cost["cache_lookup_count"] = float(index + 1)
    cost["cache_miss_count"] = float(index + 1)
    cost["model_call_count"] = float(index + 1)
    return {
        "cohort_index": index,
        "controller_compute_telemetry": {"t067_cost_attribution": cost},
        "problems": [],
    }


def _provenance(label: str) -> dict[str, object]:
    return {
        "config": {
            "search_budget": {"simulations": 100 if label == "baseline" else 1},
            "native_source_identity": {
                "integration_commit": "3cb9ebecb87c38044b34aa0e013d42b222a04087"
            },
            "task_id": "T067" if label != "baseline" else "T062",
            "cost_repair": (
                {
                    "repair_identity": "exact-public-node-inference-cache-v1",
                    "inference_cache_enabled": True,
                }
                if label != "baseline"
                else None
            ),
        }
    }


def test_t067_attribution_preserves_all_arms_and_time_distributions() -> None:
    arms = {
        label: {"records": [_cost_row(index) for index in range(16)]}
        for label in ("baseline", "prior_only", "value_only", "prior_value")
    }
    report = build_t067_cost_attribution_report(
        {
            "schema_id": "t062-battle-search-v2-comparison-v1",
            "report_kind": "merged_comparison",
            "command_passed": True,
            "evaluated_record_count": 16,
            "cohort_identity": "cohort",
            "cohort_total_record_count": 93,
            "arms": arms,
            "controller_provenance": {
                label: _provenance(label)
                for label in ("baseline", "prior_only", "value_only", "prior_value")
            },
        },
        input_identities={"t052_fixed_cohort": {"sha256": "cohort"}},
        candidate_budget={
            "baseline": 100,
            "prior_only": 1,
            "value_only": 1,
            "prior_value": 1,
        },
        normalization_family="wall_clock",
        worker_count=16,
        shard_count=16,
        record_range="0:16",
    )
    assert report["command_passed"] is True
    assert set(report["arm_attribution"]) == {
        "baseline",
        "prior_only",
        "value_only",
        "prior_value",
    }
    timing = report["arm_attribution"]["prior_value"]["timings"]
    assert timing["model_call_count"]["count"] == 16
    assert timing["model_call_count"]["total"] == 136.0
    assert timing["model_call_count"]["p95"] == 16.0


def test_t067_minimum_wall_infeasibility_fails_closed_before_primary() -> None:
    report = {
        "schema_id": "t067-battle-search-v2-cost-comparison-v1",
        "command_passed": True,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "evaluated_record_count": 16,
        "candidate_budget": {
            "baseline": 100,
            "prior_only": 1,
            "value_only": 1,
            "prior_value": 1,
        },
        "t062_comparison": {
            "arms": {
                "baseline": {
                    "native_simulator_steps": 1000.0,
                    "wall_clock_seconds": 100.0,
                },
                "prior_only": {
                    "native_simulator_steps": 10.0,
                    "wall_clock_seconds": 111.0,
                },
                "value_only": {
                    "native_simulator_steps": 20.0,
                    "wall_clock_seconds": 101.0,
                },
                "prior_value": {
                    "native_simulator_steps": 30.0,
                    "wall_clock_seconds": 99.0,
                },
            }
        },
    }
    calibration = build_t067_calibration_manifest(report)
    assert calibration["schema_id"] == T067_CALIBRATION_SCHEMA_ID
    assert calibration["primary_comparison_authorized"] is False
    assert calibration["proven_infeasible_arms"] == ["prior_only"]
    steps = calibration["families"]["simulator_step_normalized"]["arms"]
    assert all(
        row["next_candidate_status"]
        == "not_run_after_decisive_minimum_wall_clock_infeasibility"
        for row in steps.values()
    )
    decision = build_t067_decision_report(calibration)
    assert decision["schema_id"] == T067_DECISION_SCHEMA_ID
    assert decision["recommendation_count"] == 1
    assert decision["primary_comparison_status"] == "not_run_not_authorized"
