"""Independent acceptance fixtures for the frozen T075/T065 boundary.

These fixtures intentionally spell out the values from the approved contracts
instead of asking production builders or validators to define their own
expected values.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.non_combat_learning import (
    T075_PLANNER_BASELINE,
    T075_RETENTION_MANIFEST_SCHEMA_ID,
    T075_STABLE_ARTIFACT_ROOT,
    T075_TASK_ID,
    T075_TERMINAL_DECISION_SCHEMA_ID,
    T075WorkflowError,
    _code_head_for_artifact_root,
    _handle_t075_case_d,
    _t075_command_matches_contract,
    _t075_normalize_artifact_path,
    _t075_stage_retention_records,
    _t075_stage6_report_is_valid,
    _t075_terminal_finalize_argv,
    _t075_terminal_finalize_command,
    _t075_write_stage6_failure_report,
)
from sts_combat_rl.sim.non_combat_learning import (
    T065_STAGE6_SEED_RANGE,
    T065_MAX_WORKERS,
    stage6_shard_ranges,
)


FROZEN_EXECUTION_STAGES = (
    "stage0-preflight",
    "stage0-reuse",
    "stage1-selection-replay",
    "stage2-target",
    "stage4-train",
    "stage5-gate",
    "stage6-eval",
)
FROZEN_ROOT = (
    "D:/DeadlycatCoding/STSRL/artifacts/t075-leakage-safe-non-combat-cohort-repair"
)
FROZEN_STAGE6_SHARDS = tuple(
    (index, 651001 + index * 16, 651001 + index * 16 + 15) for index in range(16)
)


def _frozen_stage6_records() -> tuple[list[dict[str, int]], list[dict[str, int]]]:
    """Return ordinary per-run rows/events, including one valid zero row."""

    rows = [
        {
            "simulator_seed": seed,
            "learned_decision_count": 0 if seed == 651001 else 1,
        }
        for seed in range(651001, 651257)
    ]
    events = [
        {"simulator_seed": seed, "status": "learned_success"}
        for seed in range(651002, 651257)
    ]
    return rows, events


def test_t075_case_d_writes_exact_reached_skipped_prefix(tmp_path) -> None:
    expected_skipped = {
        stage: list(FROZEN_EXECUTION_STAGES[index + 1 :])
        for index, stage in enumerate(FROZEN_EXECUTION_STAGES)
    }
    for index, stage in enumerate(FROZEN_EXECUTION_STAGES):
        decision_path = tmp_path / f"decision-{index}.json"
        args = SimpleNamespace(
            command="evaluate",
            decision_report=decision_path,
            retention_manifest=None,
            _command_argv=(),
            _t075_execution_start_utc="2026-08-28T00:00:00+00:00",
        )
        _handle_t075_case_d(args, T075WorkflowError(stage, ["acceptance failure"]))
        report = json.loads(decision_path.read_text(encoding="utf-8"))
        assert report["schema_id"] == T075_TERMINAL_DECISION_SCHEMA_ID
        assert report["terminal_case"] == "D"
        assert report["terminal_stage"] == stage
        assert report["reached_stages"] == list(FROZEN_EXECUTION_STAGES[: index + 1])
        assert report["skipped_stages"] == expected_skipped[stage]


def test_t075_case_matrix_and_first_valid_contract_are_literal() -> None:
    expected = {
        "A": ("stage6-eval", list(FROZEN_EXECUTION_STAGES), []),
        "B": ("stage6-eval", list(FROZEN_EXECUTION_STAGES), []),
        "C": ("stage5-gate", list(FROZEN_EXECUTION_STAGES[:6]), ["stage6-eval"]),
        "D": (
            "stage2-target",
            list(FROZEN_EXECUTION_STAGES[:4]),
            list(FROZEN_EXECUTION_STAGES[4:]),
        ),
    }
    for case, (terminal_stage, reached, skipped) in expected.items():
        assert terminal_stage in FROZEN_EXECUTION_STAGES
        assert reached + skipped == list(FROZEN_EXECUTION_STAGES)
        assert case in {"A", "B", "C", "D"}


def test_t075_stable_root_and_terminal_finalize_command_are_exact() -> None:
    assert str(T075_STABLE_ARTIFACT_ROOT).replace("\\", "/") == FROZEN_ROOT
    expected_argv = (
        "finalize",
        "--artifact-root",
        str(T075_STABLE_ARTIFACT_ROOT),
        "--decision-report",
        str(T075_STABLE_ARTIFACT_ROOT / "terminal-decision-report.json"),
        "--retention-manifest",
        str(T075_STABLE_ARTIFACT_ROOT / "t075-retention-manifest.json"),
    )
    assert _t075_terminal_finalize_argv() == expected_argv
    command = _t075_terminal_finalize_command()
    assert command.startswith("wsl.exe -d Ubuntu -e bash -lc ")
    assert "set -euo pipefail" in command
    assert "cd /mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/" in command
    assert _t075_command_matches_contract(command, "terminal-finalize")
    assert not _t075_command_matches_contract(
        command.replace(
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/t075-",
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/other-",
        ),
        "terminal-finalize",
    )
    assert _t075_normalize_artifact_path(FROZEN_ROOT) == (
        "artifacts/t075-leakage-safe-non-combat-cohort-repair"
    )


def test_t075_retention_cannot_supply_decision_skipped_stage(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    root = tmp_path / "artifacts"
    monkeypatch.setattr(command_module, "T075_STABLE_ARTIFACT_ROOT", root)
    stage = "stage5-gate"
    command = command_module._t075_command_string(
        SimpleNamespace(),
        command_argv=command_module._t075_frozen_stage_argv(SimpleNamespace(), stage),
    )
    code_head = _code_head_for_artifact_root(SimpleNamespace())
    stage_record = {
        "command": command,
        "executed": False,
        "status": "skipped",
        "code_head": code_head,
        "start_time_utc": "2026-08-28T00:00:00+00:00",
        "end_time_utc": "2026-08-28T00:00:00+00:00",
        "exit_code": None,
        "terminal": False,
        "wall_clock_seconds": 0.0,
        "shard_count": 0,
        "worker_count": 0,
        "ranges": [],
        "parent_identities": {},
        "output_identities": [],
        "artifact_roles": [],
        "skip_reason": "decision skipped this stage",
    }
    retention = root / "stale.retention.json"
    retention.parent.mkdir(parents=True)
    retention.write_text(
        json.dumps(
            {
                "schema_id": T075_RETENTION_MANIFEST_SCHEMA_ID,
                "schema_version": 1,
                "task_id": T075_TASK_ID,
                "approved_t075_spec_commit": command_module.T075_APPROVED_SPEC_COMMIT,
                "planner_baseline": T075_PLANNER_BASELINE,
                "stage_commands": {stage: stage_record},
                "stage_evidence": {stage: stage_record},
                "reused_artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(T075WorkflowError, match="decision-skipped"):
        _t075_stage_retention_records(root, {"skipped_stages": [stage]})


def test_t075_stage6_literal_ranges_and_per_run_missing_record_boundary(
    tmp_path,
) -> None:
    expected = [
        {
            "arm": "stochastic",
            "shard_index": index,
            "seed_start": start,
            "seed_end": end,
            "seed_count": 16,
            "worker_count": 16,
        }
        for index, start, end in FROZEN_STAGE6_SHARDS
    ]
    assert stage6_shard_ranges(
        arm="stochastic", worker_count=T065_MAX_WORKERS
    ) == tuple(expected)
    assert T065_STAGE6_SEED_RANGE == (651001, 651256)

    rows, events = _frozen_stage6_records()
    row_seeds = {row["simulator_seed"] for row in rows}
    event_seeds = {event["simulator_seed"] for event in events}
    assert row_seeds == set(range(651001, 651257))
    assert 651001 not in event_seeds
    assert len(event_seeds) == 255
    assert rows[0]["learned_decision_count"] == 0
    assert event_seeds == {
        row["simulator_seed"] for row in rows if row["learned_decision_count"] > 0
    }
    truncated_events = events[:-1]
    missing_seeds = {
        row["simulator_seed"] for row in rows if row["learned_decision_count"] > 0
    } - {event["simulator_seed"] for event in truncated_events}
    assert missing_seeds == {651256}

    # This is an ordinary incomplete worker record: materialize the frozen
    # failure report instead of adding a new identity/proof field to the run.
    failure_path = tmp_path / "stage6-missing-record.json"
    _t075_write_stage6_failure_report(
        failure_path,
        T075WorkflowError(
            "stage6-eval",
            [f"missing decision record for seed {seed}" for seed in missing_seeds],
            failure_ids=("stage6:missing-decision-record",),
        ),
    )
    failure_report = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure_report["valid"] is False
    assert failure_report["execution_evidence"]["failure_stage"] == "stage6-eval"


def test_t075_partial_worker_failure_preserves_spawn_evidence(tmp_path) -> None:
    per_shard = [
        {
            "shard_index": index,
            "seed_start": start,
            "seed_end": end,
            "seed_count": 16,
            "requested_seeds": list(range(start, end + 1)),
            "completed_seeds": list(range(start, end + 1)) if index == 0 else [],
            "process_id": 12000 + index,
            "worker_kind": "spawn-process",
            "started": True,
            "status": "passed" if index == 0 else "failed",
            "exit_code": 0 if index == 0 else 1,
        }
        for index, start, end in FROZEN_STAGE6_SHARDS
    ]
    path = tmp_path / "stage6-complete-run-report.json"
    failure = T075WorkflowError(
        "stage6",
        ["worker exited before merge"],
        failure_ids=("stage6:worker-failure",),
        execution_evidence={
            "partial_spawn_failure": True,
            "shard_count": 16,
            "worker_count": 16,
            "ranges": per_shard,
            "per_shard": per_shard,
        },
    )
    _t075_write_stage6_failure_report(path, failure)
    evidence = json.loads(path.read_text(encoding="utf-8"))["execution_evidence"]
    assert _t075_stage6_report_is_valid(path, artifact_root=tmp_path)
    assert evidence["partial_spawn_failure"] is True
    assert len(evidence["per_shard"]) == 16
    assert {item["process_id"] for item in evidence["per_shard"]} == set(
        range(12000, 12016)
    )
    assert all(
        item["seed_end"] - item["seed_start"] == 15 for item in evidence["ranges"]
    )
    assert evidence["failure_counts"]["failure_count"] == 1
