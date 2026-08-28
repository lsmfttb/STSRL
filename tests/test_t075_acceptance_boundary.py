"""Independent acceptance fixtures for the frozen T075/T065 boundary.

These fixtures intentionally spell out the values from the approved contracts
instead of asking production builders or validators to define their own
expected values.
"""

from __future__ import annotations

import json
import os
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
    _run_t075_finalize,
    _run_t075_evaluate,
    _t075_command_matches_contract,
    _t075_normalize_artifact_path,
    _t075_stage_retention_records,
    _t075_stage6_report_is_valid,
    _t075_terminal_decision_is_valid,
    _t075_terminal_finalize_argv,
    _t075_terminal_finalize_command,
    _t075_write_stage6_failure_report,
)
from sts_combat_rl.sim.non_combat_learning import (
    T065_STAGE6_SEED_RANGE,
    T065CaseD,
    T065_MAX_WORKERS,
    file_sha256,
    _run_spawn_process_batch,
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


def _acceptance_worker_with_one_crash(payload):
    """Pickleable process worker with one deterministic no-return shard."""

    if payload["shard_index"] == 1:
        os._exit(7)
    return {
        "shard_index": payload["shard_index"],
        "process_id": os.getpid(),
        "worker_kind": "spawn-process",
        "status": "passed",
        "exit_code": 0,
    }


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


def _write_independent_case_d_fixture(root, decision_path, retention_path) -> None:
    """Write a small real-retention Case-D fixture for finalizer tests."""

    import sts_combat_rl.commands.non_combat_learning as command_module

    parent_path = root / "failure-evidence.json"
    parent_path.write_text("stage0 failure\n", encoding="utf-8")
    parent = {
        "role": "failure_evidence",
        "path": str(parent_path),
        "sha256": file_sha256(parent_path),
        "size_bytes": parent_path.stat().st_size,
    }
    stage = "stage0-preflight"
    args = SimpleNamespace()
    command = command_module._t075_command_string(
        args,
        command_argv=command_module._t075_frozen_stage_argv(args, stage),
    )
    code_head = _code_head_for_artifact_root(args)
    stage_record = {
        "command": command,
        "executed": True,
        "status": "failed",
        "code_head": code_head,
        "start_time_utc": "2026-08-28T00:00:00+00:00",
        "end_time_utc": "2026-08-28T00:00:01+00:00",
        "exit_code": 1,
        "terminal": False,
        "wall_clock_seconds": 1.0,
        "shard_count": 0,
        "worker_count": 0,
        "ranges": [],
        "parent_identities": {},
        "output_identities": [parent],
        "artifact_roles": ["failure_evidence"],
        "problems": ["stage0 failure"],
    }
    retention_path.write_text(
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
    skipped = list(FROZEN_EXECUTION_STAGES[1:])
    skipped_commands = {}
    skipped_evidence = {}
    for skipped_stage in skipped:
        skipped_command = command_module._t075_command_string(
            args,
            command_argv=command_module._t075_frozen_stage_argv(args, skipped_stage),
        )
        skipped_commands[skipped_stage] = skipped_command
        skipped_evidence[skipped_stage] = {
            **stage_record,
            "command": skipped_command,
            "executed": False,
            "status": "skipped",
            "exit_code": None,
            "terminal": False,
            "wall_clock_seconds": 0.0,
            "output_identities": [],
            "artifact_roles": [],
            "parent_identities": {},
            "ranges": [],
            "shard_count": 0,
            "worker_count": 0,
            "problems": [],
            "skip_reason": "not reached by terminal decision",
        }
    decision_path.write_text(
        json.dumps(
            {
                "schema_id": command_module.T075_TERMINAL_DECISION_SCHEMA_ID,
                "schema_version": 1,
                "task_id": T075_TASK_ID,
                "approved_t075_spec_commit": command_module.T075_APPROVED_SPEC_COMMIT,
                "planner_baseline": T075_PLANNER_BASELINE,
                "code_head": code_head,
                "terminal_case": "D",
                "terminal_stage": stage,
                "failure_stage": stage,
                "reason_code": "frozen-contract-failure",
                "summary": "stage0 failure",
                "reached_stages": [stage],
                "skipped_stages": skipped,
                "skipped_stage_commands": skipped_commands,
                "skipped_stage_evidence": skipped_evidence,
                "parent_artifact_identities": {"failure_evidence": parent},
                "stage3_validation_status": "not_reached",
                "stage5_gate_status": "not_reached",
                "stage6_status": "not_reached",
                "recommendation": "repair",
                "failure_ids": ["stage0-failure"],
                "failure_counts": {"failure_count": 1},
                "failure_details": [],
                "problems": ["stage0 failure"],
            }
        ),
        encoding="utf-8",
    )


def test_t075_case_d_fixture_finalizes_and_first_valid_wins(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(command_module, "T075_STABLE_ARTIFACT_ROOT", root)
    decision_path = root / "terminal-decision-report.json"
    retention_path = root / "t075-retention-manifest.json"
    _write_independent_case_d_fixture(
        root, decision_path, root / "stage0.retention.json"
    )
    args = SimpleNamespace(
        artifact_root=root,
        decision_report=decision_path,
        retention_manifest=retention_path,
        _command_argv=(),
    )
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert _t075_terminal_decision_is_valid(
        decision, artifact_root=root, retention_path=root / "stage0.retention.json"
    )
    retention_path.write_text("{}\n", encoding="utf-8")
    assert _run_t075_finalize(args) == 0
    original = decision_path.read_bytes()
    _handle_t075_case_d(
        SimpleNamespace(
            command="evaluate",
            decision_report=decision_path,
            retention_manifest=retention_path,
            _command_argv=(),
            _t075_execution_start_utc="2026-08-28T00:00:00+00:00",
        ),
        T075WorkflowError("stage0-preflight", ["later failure"]),
    )
    assert decision_path.read_bytes() == original


@pytest.mark.parametrize(
    ("case", "terminal_stage", "stage5_status", "stage6_status"),
    (
        ("A", "stage6-eval", "passed", "completed"),
        ("B", "stage6-eval", "passed", "completed"),
        ("C", "stage5-gate", "failed", "skipped"),
    ),
)
def test_t075_finalize_rejects_incomplete_non_d_case_fixture(
    tmp_path, monkeypatch, case, terminal_stage, stage5_status, stage6_status
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setattr(command_module, "T075_STABLE_ARTIFACT_ROOT", root)
    decision_path = root / "terminal-decision-report.json"
    retention_path = root / "t075-retention-manifest.json"
    reached_index = FROZEN_EXECUTION_STAGES.index(terminal_stage)
    skipped = list(FROZEN_EXECUTION_STAGES[reached_index + 1 :])
    decision_path.write_text(
        json.dumps(
            {
                "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
                "schema_version": 1,
                "task_id": T075_TASK_ID,
                "approved_t075_spec_commit": command_module.T075_APPROVED_SPEC_COMMIT,
                "planner_baseline": T075_PLANNER_BASELINE,
                "code_head": _code_head_for_artifact_root(SimpleNamespace()),
                "terminal_case": case,
                "terminal_stage": terminal_stage,
                "reason_code": "frozen-contract-failure",
                "summary": "incomplete acceptance fixture",
                "reached_stages": list(FROZEN_EXECUTION_STAGES[: reached_index + 1]),
                "skipped_stages": skipped,
                "stage5_gate_status": stage5_status,
                "stage6_status": stage6_status,
                "stage3_validation_status": "passed",
                "recommendation": "accept" if case == "A" else "repair",
                "parent_artifact_identities": {},
                "problems": [] if case != "D" else ["failure"],
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        artifact_root=root,
        decision_report=decision_path,
        retention_manifest=retention_path,
        _command_argv=(),
    )
    with pytest.raises(T075WorkflowError):
        _run_t075_finalize(args)


def test_t075_stable_root_and_terminal_finalize_command_are_exact() -> None:
    assert str(T075_STABLE_ARTIFACT_ROOT).replace("\\", "/") == FROZEN_ROOT
    frozen_code = (
        "/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/"
        "t075-leakage-safe-non-combat-cohort-repair"
    )
    frozen_python = "/home/lsmft/stsrl-spikes/py313-torch/bin/python"
    frozen_native = "/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch"
    frozen_src = f"{frozen_code}/src"
    frozen_root = (
        "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
        "t075-leakage-safe-non-combat-cohort-repair"
    )
    expected_inner = (
        "set -euo pipefail; "
        f"cd {frozen_code}; "
        f"export PYTHONPATH={frozen_native}:{frozen_src}; "
        f"{frozen_python} -m sts_combat_rl.commands.non_combat_learning "
        "finalize "
        f"--artifact-root {frozen_root} "
        f"--decision-report {frozen_root}/terminal-decision-report.json "
        f"--retention-manifest {frozen_root}/t075-retention-manifest.json"
    )
    expected_command = "wsl.exe -d Ubuntu -e bash -lc '" + expected_inner + "'"
    command = _t075_terminal_finalize_command()
    assert command == expected_command
    assert _t075_terminal_finalize_argv() == (
        "finalize",
        "--artifact-root",
        str(T075_STABLE_ARTIFACT_ROOT),
        "--decision-report",
        str(T075_STABLE_ARTIFACT_ROOT / "terminal-decision-report.json"),
        "--retention-manifest",
        str(T075_STABLE_ARTIFACT_ROOT / "t075-retention-manifest.json"),
    )
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
    for arm in ("stochastic", "expert", "learned"):
        expected = [
            {
                "arm": arm,
                "shard_index": index,
                "seed_start": start,
                "seed_end": end,
                "seed_count": 16,
                "worker_count": 16,
            }
            for index, start, end in FROZEN_STAGE6_SHARDS
        ]
        assert stage6_shard_ranges(arm=arm, worker_count=T065_MAX_WORKERS) == tuple(
            expected
        )
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


def test_t075_stage6_validator_rejects_truncated_decision_record(tmp_path) -> None:
    """Exercise the complete report reader without adding a new identity field."""

    import importlib.util

    fixture_path = (
        __file__[: -len("test_t075_acceptance_boundary.py")]
        + "test_non_combat_learning.py"
    )
    fixture_spec = importlib.util.spec_from_file_location(
        "t075_existing_test_fixture", fixture_path
    )
    assert fixture_spec is not None and fixture_spec.loader is not None
    fixture_module = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture_module)

    path = tmp_path / "stage6-complete-run-report.json"
    fixture_module._write_valid_t075_stage6_fixture(path)
    assert _t075_stage6_report_is_valid(path, artifact_root=tmp_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    learned = report["execution_evidence"]["arms"]["learned"]
    learned_report = learned["report"]
    removed = learned_report["decision_events"].pop()
    removed_seed = removed["simulator_seed"]
    removed_row = next(
        row for row in learned_report["rows"] if row["simulator_seed"] == removed_seed
    )
    removed_row["learned_decision_count"] = 0
    learned["decision_count"] -= 1
    report["coverage"].update({"D": 255, "L": 255, "M": 255})
    path.write_text(json.dumps(report), encoding="utf-8")
    assert not _t075_stage6_report_is_valid(path, artifact_root=tmp_path)

    # The independent ordinary-record fixture has one legitimate zero-learned
    # seed; that seed is not itself a missing-record condition.
    rows, events = _frozen_stage6_records()
    assert rows[0]["learned_decision_count"] == 0
    assert 651001 not in {event["simulator_seed"] for event in events}


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
    per_shard[-1]["started"] = False
    per_shard[-1]["process_id"] = None
    per_shard[-1]["status"] = "not-started"
    per_shard[-1]["exit_code"] = None
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
    started = [item for item in evidence["per_shard"] if item["started"]]
    unstarted = [item for item in evidence["per_shard"] if not item["started"]]
    assert {item["process_id"] for item in started} == set(range(12000, 12015))
    assert len(unstarted) == 1
    assert unstarted[0]["process_id"] is None
    assert unstarted[0]["status"] == "not-started"
    assert all(
        item["seed_end"] - item["seed_start"] == 15 for item in evidence["ranges"]
    )
    assert evidence["failure_counts"]["failure_count"] == 1


def test_t075_spawn_batch_failure_carries_actual_partial_process_evidence() -> None:
    payloads = [
        {"shard_index": 0, "seeds": list(range(651001, 651017))},
        {"shard_index": 1, "seeds": list(range(651017, 651033))},
    ]
    with pytest.raises(T065CaseD) as raised:
        _run_spawn_process_batch(
            _acceptance_worker_with_one_crash,
            payloads,
            stage="stage6-eval",
            worker_count=2,
        )
    evidence = raised.value.execution_evidence
    assert evidence["partial_spawn_failure"] is True
    assert evidence["shard_count"] == 2
    assert evidence["worker_count"] == 2
    per_shard = evidence["per_shard"]
    assert len(per_shard) == 2
    assert {entry["shard_index"] for entry in per_shard} == {0, 1}
    assert len({entry["process_id"] for entry in per_shard}) == 2
    assert all(entry["started"] is True for entry in per_shard)
    assert per_shard[0]["status"] == "passed"
    assert per_shard[1]["status"] == "missing"
    assert per_shard[1]["exit_code"] == 7
    assert per_shard[0]["requested_seeds"] == list(range(651001, 651017))
    assert per_shard[1]["requested_seeds"] == list(range(651017, 651033))
    assert raised.value.failure_counts["shards_returned"] == 1


def test_t075_stage6_does_not_rewrite_supplied_stage5_parent(
    tmp_path, monkeypatch
) -> None:
    """Stage 6 must consume, rather than regenerate, its Stage-5 parent."""

    import sts_combat_rl.commands.non_combat_learning as command_module

    root = tmp_path / "artifacts"
    root.mkdir()
    stage5_path = root / "stage5-heldout-report.json"
    stage5_path.write_text(
        json.dumps(
            {
                "schema_id": "t075-stage5-gate-report-v1",
                "schema_version": 1,
                "task_id": "T075",
                "approved_t075_spec_commit": "e204c5d28cc0bee8013853e8680e8966f5c930a8",
                "parent_target_table_sha256": "literal-parent",
                "stage5": {"passed": True, "marker": "supplied-stage5"},
                "passed": True,
                "problems": [],
            }
        ),
        encoding="utf-8",
    )
    before = stage5_path.read_bytes()
    target_table = root / "stage2-target-table.json"
    target_table.write_text("target fixture\n", encoding="utf-8")
    checkpoint_directory = root / "stage4-checkpoints"
    checkpoint_directory.mkdir()
    (checkpoint_directory / "model-653001.pt").write_bytes(b"model 653001\n")
    (checkpoint_directory / "model-653002.pt").write_bytes(b"model 653002\n")
    args = SimpleNamespace(
        command="evaluate",
        stage5_report=stage5_path,
        target_table=target_table,
        checkpoint_directory=checkpoint_directory,
        output=root / "stage6-complete-run-report.json",
        run_stage6=True,
        stage6_shard_count=16,
        stage6_worker_count=16,
        preflight=root / "stage0-preflight.json",
        preceding_manifest=root / "stage5.retention.json",
        retention_manifest=root / "stage6.retention.json",
        decision_report=root / "terminal-decision-report.json",
        _t075_execution_start_utc="2026-08-28T00:00:00+00:00",
    )
    monkeypatch.setattr(
        command_module, "_t075_has_terminal_decision", lambda _args: False
    )
    monkeypatch.setattr(
        command_module,
        "_t075_preceding_manifest_path",
        lambda *_args, **_kwargs: root / "stage5.retention.json",
    )
    monkeypatch.setattr(
        command_module, "_t075_require_parent_retention", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        command_module,
        "read_target_table",
        lambda _path: SimpleNamespace(states=(), targets=()),
    )
    monkeypatch.setattr(
        command_module,
        "load_non_combat_checkpoint",
        lambda _path: SimpleNamespace(model_seed=653001),
    )
    monkeypatch.setattr(
        command_module,
        "build_stage5_report",
        lambda _runs, _table: SimpleNamespace(
            passed=True,
            selected_model_seed=653001,
            problems=(),
            to_dict=lambda: {"passed": True, "marker": "regenerated-stage5"},
        ),
    )

    def stop_before_scientific_stage6(*_args, **_kwargs):
        raise RuntimeError("bounded acceptance stop before Stage 6 simulation")

    monkeypatch.setattr(
        command_module, "run_stage6_experiment", stop_before_scientific_stage6
    )
    with pytest.raises(RuntimeError, match="bounded acceptance stop"):
        _run_t075_evaluate(args)
    assert stage5_path.read_bytes() == before
