"""Mock-only T092 paired-canary readiness and parity contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.battle_search_v2 import (
    BATTLE_SEARCH_V2_NATIVE_API,
    BATTLE_SEARCH_V2_PATCH_IDENTITY,
)
from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import (
    T092CanaryArmController,
    T092CanaryError,
    execute_t092_canary,
)
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_PATCH_IDENTITY,
)


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction("battle:11", "Strike", "card", {"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0}),
        SimulatorAction("battle:22", "End", "end_turn", {"scope": "battle", "bits": 22, "idx1": 0, "idx2": 0, "idx3": 0}),
    ]


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
    assert off.metadata["t092_canary_decision"]["native_report"] is None
    assert on.metadata["t092_canary_decision"]["native_report"]["teacher_config"] == T092_FROZEN_TEACHER_CONFIG


def test_pair_evidence_rejects_one_root_mismatch(monkeypatch) -> None:
    selected = tuple(T090SplitEntry(f"source-{index}", "ABC"[index % 3], "train", index) for index in range(12))
    monkeypatch.setattr("sts_combat_rl.sim.t092_canary.select_t092_canary_entries", lambda _manifest: selected)

    def runner(source: T090SplitEntry):
        decisions = [{"decision_identity": f"{source.source_identity}:battle-decision:0", "root_semantics": {"selected_action_identity": {"stable_id": "a"}}}]
        return {
            "source_identity": source.source_identity,
            "source_group": source.source_group,
            "split": source.split,
            "canonical_position": source.canonical_position,
            "native_identity": {"repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/planner/t092-internal-search-state-telemetry", "commit": "07e1770cf0710d8c26719c153383d09e3bfd7686"},
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "worker": {"stage_worker_count": 12, "worker_index": 0, "shard_count": 12, "shard_index": 0},
            "off": {"decision_records": decisions, "terminal": {"outcome": "PLAYER_VICTORY"}},
            "on": {"decision_records": deepcopy(decisions), "terminal": {"outcome": "PLAYER_VICTORY"}, "internal_occurrences": []},
        }

    assert execute_t092_canary(split_manifest={}, runner=runner)["semantic_parity"]["passed"] is True

    def mismatched(source: T090SplitEntry):
        record = runner(source)
        record["on"]["decision_records"][0]["root_semantics"] = {"selected_action_identity": {"stable_id": "b"}}
        return record

    with pytest.raises(T092CanaryError, match="SEMANTIC_PARITY_INVALID"):
        execute_t092_canary(split_manifest={}, runner=mismatched)
