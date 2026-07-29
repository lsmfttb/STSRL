from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from sts_combat_rl.commands.t070_search_v2_audit import (
    BUDGET_CURVE_SCHEMA_ID,
    DECISION_SCHEMA_ID,
    GEOMETRY_REPORT_SCHEMA_ID,
    MERGED_STAGE_SCHEMA_ID,
    PRIMARY_REPORT_SCHEMA_ID,
    PRIMARY_RANGES,
    _build_outcome_blind_subset,
    build_decision_report,
    merge_single_arm_stage,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
)


def _record(index: int, *, act: int, room_type: str) -> FixedCohortRecord:
    return FixedCohortRecord(
        cohort_index=index,
        source_pool_record_index=1000 + index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_run_id=f"run-{index // 3}",
        source_seed=index,
        source_battle_index=index,
        structural_stratum=(20, act, room_type, index),
        structural_metadata={
            "ascension": 20,
            "act": act,
            "room_type": room_type,
            "encounter_id": index,
        },
        source_controller_provenance={},
        source_battle_controller_provenance={},
        source_non_combat_controller_provenance={},
        action_trace=(),
    )


def test_t070_subset_is_structural_outcome_blind_and_exact() -> None:
    records = [
        *[_record(index, act=2, room_type="MONSTER") for index in range(5)],
        *[_record(index, act=1, room_type="BOSS") for index in range(5, 93)],
    ]
    cohort = FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance={},
        selection_config=FixedCohortSelectionConfig(selection_seed=1),
        records=records,
    )
    subset, manifest = _build_outcome_blind_subset(cohort, "a" * 40)

    assert len(subset.records) == 16
    assert [record.cohort_index for record in subset.records] == list(range(16))
    assert sum(row["stratum"] == "act2_plus" for row in manifest["records"]) == 5
    assert sum(row["stratum"] == "boss_only" for row in manifest["records"]) == 11
    assert manifest["outcome_blind"] is True
    assert "outcomes" in manifest["selection_forbidden_fields"]
    assert all(
        set(row["canonical_source_identity"]).isdisjoint(
            {"outcomes", "selected_actions", "terminal_resources"}
        )
        for row in manifest["records"]
    )


def _pair(delta: int, *, ci_lower: float = 0.0, hp: float = 0.0, ratio: float = 1.0):
    return {
        name: {
            "record_count": 93
            if name == "overall"
            else (88 if name == "boss_only" else 5),
            "paired_win_delta": delta,
            "paired_win_delta_mean": delta / 93,
            "paired_win_delta_bootstrap_95ci": [ci_lower, 0.1],
            "mean_terminal_hp_delta_among_outcome_ties": hp,
            "cost_ratio_guided_over_baseline": {
                "native_simulator_steps": ratio,
                "wall_clock_seconds": ratio,
            },
        }
        for name in ("overall", "boss_only", "act2_plus")
    }


def _primary(*, promote: bool):
    equal = _pair(1 if promote else 0)
    normalized = _pair(1 if promote else 0)
    return {
        "schema_id": PRIMARY_REPORT_SCHEMA_ID,
        "command_passed": True,
        "failure_problems": [],
        "families": {
            "equal_nominal": {"paired_vs_baseline": {"prior_value": equal}},
            "simulator_step_normalized": {
                "paired_vs_baseline": {"prior_value": normalized}
            },
            "wall_clock_normalized": {
                "paired_vs_baseline": {"prior_value": normalized}
            },
        },
    }


@pytest.mark.parametrize(
    ("promote", "high_signal", "case", "recommendation"),
    [
        (
            True,
            False,
            "A",
            "T071 Battle Search v2 Bounded Complete-Run Reachability Evaluation",
        ),
        (False, True, "B", "T063 Oracle-guided public battle learning"),
        (False, False, "C", "T064 simulator-generated later-act curriculum"),
    ],
)
def test_t070_complete_decision_truth_table(
    promote: bool, high_signal: bool, case: str, recommendation: str
) -> None:
    curve = {
        "schema_id": BUDGET_CURVE_SCHEMA_ID,
        "command_passed": True,
        "budget_100_not_sufficient": True,
        "high_budget_guidance_signal": high_signal,
    }
    geometry = {
        "schema_id": GEOMETRY_REPORT_SCHEMA_ID,
        "command_passed": True,
    }
    decision = build_decision_report(_primary(promote=promote), curve, geometry)
    assert decision["schema_id"] == DECISION_SCHEMA_ID
    assert decision["decision_case"] == case
    assert decision["recommendation"] == recommendation
    assert decision["exactly_one_planner_recommendation"] is True
    assert decision["successor_published"] is False


def test_t070_decision_fails_closed_on_incomplete_geometry() -> None:
    with pytest.raises(ValueError, match="complete valid evidence"):
        build_decision_report(
            _primary(promote=False),
            {
                "schema_id": BUDGET_CURVE_SCHEMA_ID,
                "command_passed": True,
            },
            {
                "schema_id": GEOMETRY_REPORT_SCHEMA_ID,
                "command_passed": False,
            },
        )


def test_t070_merge_requires_exact_ordered_stage_inventory(tmp_path: Path) -> None:
    shard_paths = []
    for index, record_range in enumerate(PRIMARY_RANGES):
        start, end = (int(value) for value in record_range.split(":"))
        path = tmp_path / f"shard-{index:02d}.json"
        rows = [
            {
                "cohort_index": cohort_index,
                "termination_status": "win",
                "outer_simulator_steps": 1,
                "wall_clock_seconds": 1.0,
                "controller_compute_telemetry": {
                    "oracle_search_native_simulator_steps": 1,
                    "oracle_search_model_calls": 0,
                },
                "problems": [],
            }
            for cohort_index in range(start, end)
        ]
        path.write_text(
            __import__("json").dumps(
                {
                    "schema_id": "t070-single-arm-shard-v1",
                    "code_commit": "a" * 40,
                    "native_commit": "fee272f1ae21c283ad2161f55293cfe6d714134a",
                    "arm": "baseline",
                    "family": "shared",
                    "native_budget": 100,
                    "cohort_identity": "cohort",
                    "cohort_record_count": 93,
                    "controller_provenance": {},
                    "record_range": record_range,
                    "shard_index": index,
                    "arm_report": {"records": rows},
                    "command_passed": True,
                }
            ),
            encoding="utf-8",
        )
        shard_paths.append(path)
    merged = merge_single_arm_stage(
        shard_paths=shard_paths,
        expected_ranges=PRIMARY_RANGES,
        expected_record_count=93,
        output_path=tmp_path / "merged.json",
    )
    assert merged["schema_id"] == MERGED_STAGE_SCHEMA_ID
    assert merged["arm_report"]["record_count"] == 93
    assert merged["effective_parallel_workers"] == 16
    assert merged["command_passed"] is True


@pytest.mark.parametrize(
    "script",
    [
        "freeze_t070_experiment.py",
        "run_t070_search_stage_shard.py",
        "orchestrate_t070_search_stage.py",
        "orchestrate_t070_native_preflight.py",
        "finalize_t070_artifacts.py",
    ],
)
def test_t070_script_cli_smoke(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path("scripts") / script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
