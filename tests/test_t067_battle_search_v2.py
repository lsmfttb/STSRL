from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from sts_combat_rl.commands.t067_battle_search_v2 import (
    T067_CALIBRATION_SCHEMA_ID,
    T067_DECISION_SCHEMA_ID,
    T067_REQUIRED_COST_FIELDS,
    build_t067_calibration_manifest,
    build_t067_cost_attribution_report,
    build_t067_decision_report,
)


def _finalizer_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "finalize_t067_artifacts.py"
    )
    specification = importlib.util.spec_from_file_location(
        "t067_artifact_finalizer", script_path
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


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


def test_t067_retention_rejects_disposable_regeneration_source() -> None:
    finalizer = _finalizer_module()
    source_repository = Path("/mnt/d/DeadlycatCoding/STSRL")
    accepted = (
        source_repository
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
        / "accepted"
    )
    source_checkout = source_repository / ".claude" / "worktrees" / "t067"
    output = (
        source_repository
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
        / "reproduction"
    )

    with pytest.raises(SystemExit, match=r"disposable \.claude/worktrees"):
        finalizer._validate_regeneration_roles(
            accepted_root=accepted,
            source_repository_root=source_repository,
            source_checkout_root=source_checkout,
            output_root=output,
        )


def test_t067_retention_rejects_accepted_or_populated_regeneration_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finalizer = _finalizer_module()
    source_repository = Path("/mnt/d/DeadlycatCoding/STSRL")
    namespace = (
        Path("/mnt/d/DeadlycatCoding/STSRL")
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
    )
    accepted = namespace / "accepted"
    source_checkout = namespace / "source"

    with pytest.raises(SystemExit, match="must differ from the accepted root"):
        finalizer._validate_regeneration_roles(
            accepted_root=accepted,
            source_repository_root=source_repository,
            source_checkout_root=source_checkout,
            output_root=accepted,
        )

    populated = namespace / "reproduction"
    monkeypatch.setattr(Path, "exists", lambda self: self == populated)
    with pytest.raises(SystemExit, match="fresh absent root"):
        finalizer._validate_regeneration_roles(
            accepted_root=accepted,
            source_repository_root=source_repository,
            source_checkout_root=source_checkout,
            output_root=populated,
        )


def test_t067_regeneration_sequence_pins_source_and_fresh_output() -> None:
    finalizer = _finalizer_module()
    commit = "a" * 40
    source_repository = Path("/mnt/d/DeadlycatCoding/STSRL")
    source_checkout = (
        source_repository
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
        / f"source-{commit[:7]}"
    )
    accepted = (
        source_repository
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
        / "accepted"
    )
    output = (
        source_repository
        / "artifacts"
        / "t067-battle-search-v2-inference-cost-repair"
        / f"reproduction-{commit[:7]}"
    )
    commands = finalizer._regeneration_commands(
        source_repository_root=source_repository,
        source_checkout_root=source_checkout,
        accepted_root=accepted,
        output_root=output,
        input_root=source_repository / "artifacts",
        code_commit=commit,
    )

    finalizer._validate_regeneration_commands(
        commands=commands,
        code_commit=commit,
        source_checkout_root=source_checkout,
        accepted_root=accepted,
        output_root=output,
    )
    assert len(commands) == 6
    assert "worktree add --detach" in commands[0]
    assert commit in commands[0]
    assert 'test ! -e "$output_root"' in commands[0]
    assert all(".claude/worktrees" not in command for command in commands)
    assert all(str(source_checkout) in command for command in commands[1:])
    assert all(str(output) in command for command in commands)
    assert all(str(accepted) not in command for command in commands)
