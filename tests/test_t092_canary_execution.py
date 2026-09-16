"""Mock-only authorization boundary checks for the dormant T092 launcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import T092_PUBLICATION_NATIVE_IDENTITY
from sts_combat_rl.sim.t092_canary_execution import (
    T092CanaryExecutionError,
    build_t092_canary_authorization_template,
    execute_t092_authorized_canary_shard,
)
from sts_combat_rl.sim.t092_canary_process import (
    T092CanaryProcessError,
    execute_t092_isolated_arm,
)
from sts_combat_rl.commands.t092_canary_runtime import T092_CANARY_ARM_PROCESS_SPECS
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_IDENTITY,
)


def _selected() -> tuple[T090SplitEntry, ...]:
    return tuple(T090SplitEntry(f"source-{index}", "A", "train", index) for index in range(12))


def _pair(source: T090SplitEntry) -> dict[str, object]:
    semantics = {
        "ordered_root_actions": [{
            "action_identity": {"stable_id": "a"}, "visits": 400,
            "evaluation_sum": 0.0, "mean_value": 0.0,
        }], "root_visits": 400, "native_simulator_steps": 1,
        "best_action_value": 0.0, "min_action_value": 0.0, "outcome_player_hp": 50,
        "selected_action_identity": {"stable_id": "a"}, "selection_rule": "highest_mean",
    }
    arm = {
        "restore_method": "checkpoint_restore", "restored_snapshot_present": True,
        "restore_public_legal_parity": True,
        "decision_records": [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": semantics}],
        "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 1},
        "internal_occurrences": [], "cost": {"wall_clock_time_s": 0.0},
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
    }
    def complete(arm_name: str, native: dict[str, object], pid: int) -> dict[str, object]:
        return {
            "schema_id": "t092-paired-canary-arm-record-v1", "schema_version": 1,
            "task_id": "T092", "arm": arm_name, "source_identity": source.source_identity,
            "source_group": source.source_group, "split": source.split,
            "canonical_position": source.canonical_position,
            "restore_binding": {"selection_identity": source.source_identity, "source_checkpoint_id": source.source_identity, "source_run_identity": "run", "source_seed": 1, "source_battle_index": 0},
            "implementation_head": "a" * 40, "native_identity": native,
            "native_binary": {"path": f"/{arm_name}.so", "sha256": ("a" if arm_name == "OFF" else "b") * 64, "size_bytes": 1},
            "native_api": "StepSimulator.battle_search_v2_with_internal_teacher_telemetry.v1" if arm_name == "ON" else "StepSimulator.battle_search_v2.v1",
            "process_identity": {"pid": pid, "python_executable": "/usr/bin/python3.14"},
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            **arm,
        }
    return {
        "source_identity": source.source_identity, "source_group": source.source_group,
        "split": source.split, "canonical_position": source.canonical_position,
        "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY},
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
        "arm_artifacts": {"OFF": {"path": "/off.json", "sha256": "a" * 64, "size_bytes": 1, "schema_id": "t092-paired-canary-arm-record-v1"}, "ON": {"path": "/on.json", "sha256": "b" * 64, "size_bytes": 1, "schema_id": "t092-paired-canary-arm-record-v1"}},
        "off": complete("OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
        "on": complete("ON", T092_NATIVE_IDENTITY, 102),
    }


def test_authorization_failure_cannot_invoke_t092_runner(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: _selected())
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary_execution.select_t092_canary_entries", lambda _manifest: _selected())
    invoked = False

    def runner(_source: T090SplitEntry):
        nonlocal invoked
        invoked = True
        raise AssertionError("must not run")

    with pytest.raises(T092CanaryExecutionError, match="authorization is required"):
        execute_t092_authorized_canary_shard(
            authorization=None, implementation_head="a" * 40, split_manifest={},
            runtime_input_identities={"restore_maps": "fixed"}, output_root=tmp_path,
            shard_index=0, shard_count=12, worker_count=12, runner=runner,
        )
    assert invoked is False


def test_authorized_t092_shard_binds_one_exact_start(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: _selected())
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary_execution.select_t092_canary_entries", lambda _manifest: _selected())
    prepared = build_t092_canary_authorization_template(
        implementation_head="a" * 40, split_manifest={},
        runtime_input_identities={"restore_maps": "fixed"}, output_root=tmp_path,
    )
    authorization = dict(prepared["authorization_template"])
    authorization.update({"authorized": True, "authorization_id": "mock-maintainer-auth"})
    shard = execute_t092_authorized_canary_shard(
        authorization=authorization, implementation_head="a" * 40, split_manifest={},
        runtime_input_identities={"restore_maps": "fixed"}, output_root=tmp_path,
        shard_index=0, shard_count=12, worker_count=12, runner=_pair,
    )
    assert shard["pair"]["source_identity"] == "source-0"
    assert shard["topology"]["assignment"] == "canonical-selected-ordinal-v1"


def test_native_mismatch_cannot_spawn_an_isolated_arm(monkeypatch, tmp_path) -> None:
    """The parent rejects the binary before a child could build a simulator."""

    extension = tmp_path / "slaythespire.so"
    extension.write_bytes(b"not-the-pinned-extension")
    invoked = False

    def forbidden(*_args, **_kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("subprocess must not start")

    monkeypatch.setattr("sts_combat_rl.sim.t092_canary_process.subprocess.run", forbidden)
    source = _selected()[0]
    with pytest.raises(T092CanaryProcessError, match="identity/binary"):
        execute_t092_isolated_arm(
            arm="OFF",
            spec={
                "python_executable": "/usr/bin/python3.14",
                "extension_path": str(extension), "extension_sha256": "0" * 64,
                "extension_size_bytes": extension.stat().st_size,
                "native_identity": T092_PUBLICATION_NATIVE_IDENTITY,
                "stsrl_source_root": str(Path(__file__).parents[1]),
            },
            source=source, selected=object(), canonical=object(),
            worker={"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            implementation_head="a" * 40, output_path=tmp_path / "arm.json",
        )
    assert invoked is False


def test_source_root_head_mismatch_cannot_spawn_an_isolated_arm(monkeypatch, tmp_path) -> None:
    invoked = False

    def guarded(command, *_args, **_kwargs):
        nonlocal invoked
        if command[:3] == ["git", "-C", T092_CANARY_ARM_PROCESS_SPECS["OFF"]["stsrl_source_root"]]:
            return __import__("subprocess").CompletedProcess(command, 0, stdout="0" * 40 + "\n")
        invoked = True
        raise AssertionError("child process must not start")

    monkeypatch.setattr("sts_combat_rl.sim.t092_canary_process.subprocess.run", guarded)
    source = _selected()[0]
    with pytest.raises(T092CanaryProcessError, match="Git head does not match"):
        execute_t092_isolated_arm(
            arm="OFF", spec=T092_CANARY_ARM_PROCESS_SPECS["OFF"], source=source,
            selected=object(), canonical=object(),
            worker={"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            implementation_head="a" * 40, output_path=tmp_path / "arm.json",
        )
    assert invoked is False
