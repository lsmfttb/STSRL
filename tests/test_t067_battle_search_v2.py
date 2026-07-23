from __future__ import annotations

from sts_combat_rl.commands.t067_battle_search_v2 import (
    T067_REQUIRED_COST_FIELDS,
    build_t067_cost_attribution_report,
)


def _cost_row(index: int) -> dict[str, object]:
    cost = {field: float(index + 1) for field in T067_REQUIRED_COST_FIELDS}
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
