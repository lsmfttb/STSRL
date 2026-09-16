"""Mock-only authorization boundary checks for the dormant T092 launcher."""

from __future__ import annotations

import pytest

from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import T092_PUBLICATION_NATIVE_IDENTITY
from sts_combat_rl.sim.t092_canary_execution import (
    T092CanaryExecutionError,
    build_t092_canary_authorization_template,
    execute_t092_authorized_canary_shard,
)
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
    return {
        "source_identity": source.source_identity, "source_group": source.source_group,
        "split": source.split, "canonical_position": source.canonical_position,
        "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY},
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
        "off": {**arm, "arm": "OFF", "native_identity": T092_PUBLICATION_NATIVE_IDENTITY},
        "on": {**arm, "arm": "ON", "native_identity": T092_NATIVE_IDENTITY},
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
