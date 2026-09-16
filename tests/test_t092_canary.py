"""Mock-only T092 paired-canary readiness and parity contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.battle_search_v2 import (
    BATTLE_SEARCH_V2_NATIVE_API,
    BATTLE_SEARCH_V2_PATCH_IDENTITY,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import (
    T092CanaryArmController,
    T092_CANARY_EXECUTION_CONFIG,
    T092CanaryError,
    T092_PUBLICATION_NATIVE_IDENTITY,
    _RestoredAdapter,
    execute_t092_canary,
)
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
    T092_NATIVE_PATCH_IDENTITY,
    T092_SCHEMA_ID,
    T092_SCHEMA_VERSION,
)


def _root_semantics() -> dict[str, object]:
    return {
        "ordered_root_actions": [
            {
                "action_identity": {"stable_id": "a"},
                "visits": 400,
                "evaluation_sum": 100.0,
                "mean_value": 0.25,
            }
        ],
        "root_visits": 400,
        "native_simulator_steps": 100,
        "best_action_value": 0.25,
        "min_action_value": 0.25,
        "outcome_player_hp": 50,
        "selected_action_identity": {"stable_id": "a"},
        "selection_rule": "highest_mean",
    }


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction("battle:11", "Strike", "card", {"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0}),
        SimulatorAction("battle:22", "End", "end_turn", {"scope": "battle", "bits": 22, "idx1": 0, "idx2": 0, "idx3": 0}),
    ]


def _complete_arm(
    source: T090SplitEntry, base: dict[str, object], arm: str,
    native: dict[str, object], pid: int,
) -> dict[str, object]:
    return {
        "schema_id": "t092-paired-canary-arm-record-v1", "schema_version": 1,
        "task_id": "T092", "arm": arm, "source_identity": source.source_identity,
        "source_group": source.source_group, "split": source.split,
        "canonical_position": source.canonical_position,
        "restore_binding": {"selection_identity": source.source_identity, "source_checkpoint_id": source.source_identity, "source_run_identity": "run", "source_seed": 1, "source_battle_index": 0},
        "implementation_head": "a" * 40, "native_identity": native,
        "native_binary": {"path": f"/{arm}.so", "sha256": ("a" if arm == "OFF" else "b") * 64, "size_bytes": 1},
        "native_api": T092_NATIVE_API if arm == "ON" else BATTLE_SEARCH_V2_NATIVE_API,
        "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
        "process_identity": {"pid": pid, "python_executable": "/usr/bin/python3.14"},
        "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
        **base,
    }


def _arm_artifacts() -> dict[str, object]:
    return {
        "OFF": {"path": "/off.json", "sha256": "a" * 64, "size_bytes": 1, "schema_id": "t092-paired-canary-arm-record-v1"},
        "ON": {"path": "/on.json", "sha256": "b" * 64, "size_bytes": 1, "schema_id": "t092-paired-canary-arm-record-v1"},
    }


def _raw(*, telemetry: bool) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_id": "native-battle-search-root-v1",
        "native_api": T092_NATIVE_API if telemetry else BATTLE_SEARCH_V2_NATIVE_API,
        "patch_identity": T092_NATIVE_PATCH_IDENTITY if telemetry else BATTLE_SEARCH_V2_PATCH_IDENTITY,
        "information_regime": "full_simulator_state_oracle_like",
        "simulations_requested": 400,
        "root_visits": 400,
        "include_potions": False,
        "native_simulator_steps": 100,
        "model_calls": 0,
        "best_action_value": 0.8,
        "min_action_value": 0.3,
        "outcome_player_hp": 50,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": [
            {"scope": "battle", "bits": 11, "kind": "card", "label": "Strike", "idx1": 0, "idx2": 0, "idx3": 0, "search_tree_present": True, "search_edge_index": 0, "visits": 300, "evaluation_sum": 240.0, "mean_value": 0.8},
            {"scope": "battle", "bits": 22, "kind": "end_turn", "label": "End", "idx1": 0, "idx2": 0, "idx3": 0, "search_tree_present": True, "search_edge_index": 1, "visits": 100, "evaluation_sum": 30.0, "mean_value": 0.3},
        ],
    }
    if telemetry:
        report["teacher_config"] = dict(T092_FROZEN_TEACHER_CONFIG)
        report["tree_internal_telemetry"] = {
            "internal_teacher_telemetry": {
                "schema_id": "native-battle-search-v2-internal-teacher-telemetry-v1",
                "schema_version": 1,
                "collection_phase": "post_search_private_state_replay",
                "search_rng_or_counter_mutated": False,
                "raw_private_state_exported": False,
                "telemetry_extraction_transition_count": 0,
                "candidate_count": 0,
                "rows": [],
            }
        }
    return report


class _Adapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def battle_search_v2(self, *_args, **_kwargs):
        self.calls.append("OFF")
        return _raw(telemetry=False)

    def battle_search_v2_with_internal_teacher_telemetry(self, *_args, **_kwargs):
        self.calls.append("ON")
        return _raw(telemetry=True)


def test_pair_arm_uses_exactly_one_native_api_per_decision() -> None:
    adapter = _Adapter()
    context = DecisionContext("BATTLE", [], [[], []], ["card", "end_turn"], [0, 1])
    off = T092CanaryArmController(telemetry_enabled=False).select_action(adapter, object(), _actions(), context, 0)
    on = T092CanaryArmController(telemetry_enabled=True).select_action(adapter, object(), _actions(), context, 0)

    assert adapter.calls == ["OFF", "ON"]
    assert off.selected_index == on.selected_index == 0
    assert off.provenance.config["native_identity"] == T092_PUBLICATION_NATIVE_IDENTITY
    assert on.provenance.config["native_identity"]["commit"] == "07e1770cf0710d8c26719c153383d09e3bfd7686"
    assert off.metadata["t092_canary_decision"]["native_report"] is None
    assert on.metadata["t092_canary_decision"]["native_report"]["teacher_config"] == T092_FROZEN_TEACHER_CONFIG


@pytest.mark.parametrize("outcome", ("PLAYER_VICTORY", "PLAYER_LOSS"))
def test_restored_adapter_promotes_completed_battle_outcome_to_terminal(outcome: str) -> None:
    """A completed Battle ends T092 before rewards/non-Battle routing."""

    class Adapter:
        def __init__(self) -> None:
            self.step_calls = 0

        def step(self, _action: object) -> SimulatorTransition:
            self.step_calls += 1
            return SimulatorTransition(
                snapshot=SimulatorSnapshot(
                    observation=[],
                    raw={
                        "screen_state": "REWARDS",
                        "battle_active": False,
                        "completed_battle_outcome": outcome,
                        "outcome": "UNDECIDED",
                    },
                ),
                terminal=False,
                info={"completed_battle_outcome": outcome},
            )

    adapter = Adapter()
    transition = _RestoredAdapter(adapter, object()).step(object())

    assert adapter.step_calls == 1
    assert transition.terminal is True
    assert transition.snapshot.raw["completed_battle_outcome"] == outcome


def test_pair_evidence_rejects_one_root_mismatch(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "ABC"[index % 3], "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def runner(source: T090SplitEntry):
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": _root_semantics()}]
        arm_base = {
            "restore_method": "checkpoint_restore",
            "restored_snapshot_present": True,
            "restore_public_legal_parity": True,
            "decision_records": decisions,
            "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 1},
            "internal_occurrences": [],
            "cost": {"wall_clock_time_s": 0.1},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        }
        return {
            "source_identity": source.source_identity,
            "source_group": source.source_group,
            "split": source.split,
            "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": {"repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/planner/t092-internal-search-state-telemetry", "commit": "07e1770cf0710d8c26719c153383d09e3bfd7686"}},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "arm_artifacts": _arm_artifacts(),
            "off": _complete_arm(source, arm_base, "OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
            "on": _complete_arm(source, {**arm_base, "decision_records": deepcopy(decisions)}, "ON", T092_NATIVE_IDENTITY, 102),
        }

    assert execute_t092_canary(split_manifest={}, runner=runner)["semantic_parity"]["passed"] is True

    def mismatched(source: T090SplitEntry):
        record = runner(source)
        record["on"]["decision_records"][0]["root_semantics"]["selected_action_identity"] = {"stable_id": "b"}
        return record

    with pytest.raises(T092CanaryError, match="SEMANTIC_PARITY_INVALID"):
        execute_t092_canary(split_manifest={}, runner=mismatched)


def test_pair_evidence_fails_closed_on_restore_or_arm_provenance(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "A", "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def malformed(source: T090SplitEntry):
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": _root_semantics()}]
        base = {
            "restore_method": "checkpoint_restore", "restored_snapshot_present": True,
            "restore_public_legal_parity": True, "decision_records": decisions,
            "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 1},
            "internal_occurrences": [], "cost": {"wall_clock_time_s": 0.1},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        }
        return {
            "source_identity": source.source_identity, "source_group": source.source_group,
            "split": source.split, "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": {"repository": "wrong"}},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "arm_artifacts": _arm_artifacts(),
            "off": _complete_arm(source, base, "OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
            "on": _complete_arm(source, {**base, "restore_public_legal_parity": False}, "ON", {"repository": "wrong"}, 102),
        }

    with pytest.raises(T092CanaryError, match="pair provenance mismatch"):
        execute_t092_canary(split_manifest={}, runner=malformed)


def test_pair_evidence_rejects_hidden_or_malformed_retained_occurrence(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "A", "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def runner(source: T090SplitEntry):
        root = _root_semantics()
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": root}]
        arm = {
            "restore_method": "checkpoint_restore", "restored_snapshot_present": True,
            "restore_public_legal_parity": True, "decision_records": decisions,
            "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 1},
            "internal_occurrences": [], "cost": {"wall_clock_time_s": 0.1},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        }
        occurrence = {
            "schema_id": T092_SCHEMA_ID, "schema_version": T092_SCHEMA_VERSION,
            "native_identity": dict(T092_NATIVE_IDENTITY), "frozen_teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "source_identity": source.source_identity, "source_group": source.source_group, "split": source.split,
            "parent_root_decision_identity": decisions[0]["decision_identity"], "occurrence_identity": "internal-1",
            "tree_depth": 1, "expansion_ordinal": 1,
            "public_battle_projection": {"rng_state": "hidden"}, "input_state": "PLAYER_NORMAL", "searchable_actions": [], "excluded_actions": [],
            "search_work": {"root_visits": 400, "native_simulator_steps": 1, "simulations_requested": 400},
            "telemetry_cost": {"telemetry_extraction_transition_count": 0, "collection_phase": "post_search_private_state_replay"},
        }
        return {
            "source_identity": source.source_identity, "source_group": source.source_group,
            "split": source.split, "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "arm_artifacts": _arm_artifacts(),
            "off": _complete_arm(source, arm, "OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
            "on": _complete_arm(source, {**arm, "internal_occurrences": [occurrence]}, "ON", T092_NATIVE_IDENTITY, 102),
        }

    with pytest.raises(T092CanaryError, match="occurrence violates retained schema/firewall"):
        execute_t092_canary(split_manifest={}, runner=runner)


def test_pair_evidence_rejects_nonfinite_root_values(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "A", "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def runner(source: T090SplitEntry):
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": _root_semantics()}]
        decisions[0]["root_semantics"]["ordered_root_actions"][0]["mean_value"] = float("nan")
        arm = {
            "restore_method": "checkpoint_restore", "restored_snapshot_present": True,
            "restore_public_legal_parity": True, "decision_records": decisions,
            "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 1},
            "internal_occurrences": [], "cost": {"wall_clock_time_s": 0.1},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        }
        return {
            "source_identity": source.source_identity, "source_group": source.source_group,
            "split": source.split, "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "arm_artifacts": _arm_artifacts(),
            "off": _complete_arm(source, arm, "OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
            "on": _complete_arm(source, arm, "ON", T092_NATIVE_IDENTITY, 102),
        }

    with pytest.raises(T092CanaryError, match="root action values are invalid"):
        execute_t092_canary(split_manifest={}, runner=runner)


def test_pair_evidence_rejects_terminal_decision_count_mismatch(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "A", "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def runner(source: T090SplitEntry):
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": _root_semantics()}]
        arm = {
            "restore_method": "checkpoint_restore", "restored_snapshot_present": True,
            "restore_public_legal_parity": True, "decision_records": decisions,
            "terminal": {"outcome": "PLAYER_VICTORY", "terminal_current_hp": 50, "battle_decision_count": 2},
            "internal_occurrences": [], "cost": {"wall_clock_time_s": 0.1},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        }
        return {
            "source_identity": source.source_identity, "source_group": source.source_group,
            "split": source.split, "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "arm_artifacts": _arm_artifacts(),
            "off": _complete_arm(source, arm, "OFF", T092_PUBLICATION_NATIVE_IDENTITY, 101),
            "on": _complete_arm(source, arm, "ON", T092_NATIVE_IDENTITY, 102),
        }

    with pytest.raises(T092CanaryError, match="decision count disagrees"):
        execute_t092_canary(split_manifest={}, runner=runner)
