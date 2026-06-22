from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.native_public_projection import (
    NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
    NATIVE_PUBLIC_PROJECTION_PATCH_ID,
    NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
    parse_native_public_projection,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.public_run_context import (
    PUBLIC_RUN_CONTEXT_SCHEMA_ID,
    forbidden_public_context_problems,
    sanitize_public_run_context,
)


def _available(value: object, source: str = "native::source") -> dict[str, object]:
    return {"availability": "available", "source": source, "value": value}


def _unavailable(reason: str = "not exposed") -> dict[str, object]:
    return {"availability": "unavailable", "reason": reason}


def _unsupported(reason: str = "not supported") -> dict[str, object]:
    return {"availability": "unsupported", "reason": reason}


def _candidate(action: SimulatorAction) -> dict[str, object]:
    return {
        "scope": str(action.raw.get("scope", "battle")),
        "bits": int(action.raw.get("bits", 0)),
        "kind": action.kind,
        "label": action.label,
        "idx1": int(action.raw.get("idx1", 0)),
        "idx2": int(action.raw.get("idx2", 0)),
        "idx3": int(action.raw.get("idx3", 0)),
    }


def _projection_raw(
    snapshot: SimulatorSnapshot,
    actions: list[SimulatorAction],
) -> dict[str, object]:
    raw = snapshot.raw
    resources = {
        "current_hp": _available(raw["cur_hp"], "GameContext::curHp"),
        "max_hp": _available(raw["max_hp"], "GameContext::maxHp"),
        "gold": _available(raw["gold"], "GameContext::gold"),
        "potion_count": _available(raw["potion_count"], "GameContext::potionCount"),
        "potion_capacity": _available(
            raw["potion_capacity"],
            "GameContext::potionCapacity",
        ),
        "deck": _unavailable(),
        "relics": _unavailable(),
        "potion_identities": _unavailable(),
        "keys": _unavailable(),
    }
    return {
        "schema_id": NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
        "external_base_commit": NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
        "patch_identity": NATIVE_PUBLIC_PROJECTION_PATCH_ID,
        "screen_identity": _available(raw["screen_state"], "GameContext::screenState"),
        "visible_act_boss": _unavailable(),
        "visible_map_graph": _unavailable(),
        "current_map_node": _unavailable(),
        "immediately_legal_routes": _unavailable(),
        "persistent_resources": _available(resources, "GameContext"),
        "screen_payload": _unsupported(),
        "candidate_actions": _available(
            [_candidate(action) for action in actions],
            "StepSimulator::legalActions",
        ),
    }


class PublicContextAdapter:
    def __init__(self, *, inject_unknown_projection_key: bool = False) -> None:
        self._index = 0
        self._inject_unknown_projection_key = inject_unknown_projection_key

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self._index = 0
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        screen = str(snapshot.raw["screen_state"])
        if screen == "REWARDS":
            return [
                _action("game", 2, "reward_gold", "take gold"),
                _action("game", 2, "reward_gold", "take gold"),
            ]
        return [
            _action("battle", 1, "end_turn", "end turn"),
            _action("battle", 1, "end_turn", "end turn"),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        self._index += 1
        terminal = self._index >= 2
        return SimulatorTransition(
            snapshot=self._snapshot(),
            terminal=terminal,
            info={},
        )

    def public_projection(self, snapshot: SimulatorSnapshot) -> dict[str, object]:
        raw = _projection_raw(snapshot, self.legal_actions(snapshot))
        if self._inject_unknown_projection_key:
            raw["surprise"] = {"availability": "available", "value": 1}
        return deepcopy(raw)

    def _snapshot(self) -> SimulatorSnapshot:
        snapshots = [
            {
                "screen_state": "BATTLE",
                "outcome": "UNDECIDED",
                "battle_active": True,
                "act": 1,
                "floor_num": 1,
                "room_type": "MONSTER",
                "cur_hp": 80,
                "max_hp": 80,
                "gold": 100,
                "potion_count": 1,
                "potion_capacity": 3,
            },
            {
                "screen_state": "REWARDS",
                "outcome": "UNDECIDED",
                "battle_active": False,
                "act": 1,
                "floor_num": 1,
                "room_type": "REWARDS",
                "cur_hp": 75,
                "max_hp": 80,
                "gold": 105,
                "potion_count": 1,
                "potion_capacity": 3,
                "completed_battle_outcome": "PLAYER_VICTORY",
            },
            {
                "screen_state": "BATTLE",
                "outcome": "PLAYER_VICTORY",
                "battle_active": False,
                "act": 1,
                "floor_num": 2,
                "room_type": "MONSTER",
                "cur_hp": 75,
                "max_hp": 80,
                "gold": 105,
                "potion_count": 1,
                "potion_capacity": 3,
            },
        ]
        raw = dict(snapshots[min(self._index, len(snapshots) - 1)])
        return SimulatorSnapshot(observation=[self._index], raw=raw)


class CapturingController:
    def __init__(self, *, selected_index: int = 0) -> None:
        self.selected_index = selected_index
        self.contexts: list[DecisionContext] = []

    @property
    def provenance(self) -> ControllerProvenance:
        return ControllerProvenance(
            kind="test",
            name="capture",
            config={"selected_index": self.selected_index},
        )

    def select_action(
        self,
        adapter: object,
        snapshot: SimulatorSnapshot,
        actions: list[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del adapter, snapshot, actions, step_index
        self.contexts.append(context)
        return ControllerDecision(
            selected_index=self.selected_index,
            provenance=self.provenance,
            reason="capture",
        )


def test_public_context_rejects_forbidden_fields_recursively() -> None:
    with pytest.raises(ValueError, match="hidden_rng_state"):
        sanitize_public_run_context(
            {
                "schema_id": PUBLIC_RUN_CONTEXT_SCHEMA_ID,
                "nested": {"hidden_rng_state": 123},
            }
        )

    assert forbidden_public_context_problems(
        {"ok": [{"draw_pile_order": ["Strike", "Defend"]}]}
    )


def test_raw_projection_conformance_rejects_unknown_nested_keys() -> None:
    adapter = PublicContextAdapter()
    snapshot = adapter.reset(seed=1)
    raw = adapter.public_projection(snapshot)
    candidate = raw["candidate_actions"]["value"][0]  # type: ignore[index]
    candidate["native"] = object()  # type: ignore[index]

    with pytest.raises(ValueError, match="candidate action 0 has unknown key"):
        parse_native_public_projection(raw)


def test_controlled_run_attaches_sanitized_context_and_contiguous_history() -> None:
    adapter = PublicContextAdapter()
    controller = CapturingController(selected_index=0)

    run = execute_controlled_run(adapter, controller, seed=1, max_steps=2)

    assert run.problems == []
    assert len(run.steps) == 2
    assert [entry["history_index"] for entry in run.public_history] == [0, 1]
    assert len(controller.contexts) == 2
    first_context = controller.contexts[0].public_run_context
    second_context = controller.contexts[1].public_run_context
    assert first_context["schema_id"] == PUBLIC_RUN_CONTEXT_SCHEMA_ID
    assert first_context["history"] == []
    assert len(second_context["history"]) == 1
    assert forbidden_public_context_problems(first_context) == []

    first_candidates = first_context["candidate_actions"]["items"]
    assert [candidate["identity"]["occurrence"] for candidate in first_candidates] == [
        0,
        1,
    ]
    assert "action_id" not in first_candidates[0]["identity"]

    first_entry = run.public_history[0]
    assert first_entry["selected_action"]["identity"] == first_candidates[0]["identity"]
    assert first_entry["post_decision"]["screen"]["value"] == "REWARDS"
    assert first_entry["resource_change"]["current_hp"]["delta"] == -5
    assert first_entry["resource_change"]["gold"]["delta"] == 5

    missing = set(first_context["missing_fields"])
    assert "$.visible_act_boss" in missing
    assert "$.map.visible_map_graph" in missing
    assert "$.persistent_resources.fields.keys" in missing


def test_failed_selection_appends_no_public_history() -> None:
    adapter = PublicContextAdapter()
    controller = CapturingController(selected_index=99)

    run = execute_controlled_run(adapter, controller, seed=1, max_steps=2)

    assert run.steps == []
    assert run.public_history == []
    assert "selected action index 99" in run.problems[0]


def test_raw_projection_conformance_error_stops_before_controller_history() -> None:
    adapter = PublicContextAdapter(inject_unknown_projection_key=True)
    controller = CapturingController(selected_index=0)

    run = execute_controlled_run(adapter, controller, seed=1, max_steps=2)

    assert run.steps == []
    assert run.public_history == []
    assert controller.contexts == []
    assert any("unknown key 'surprise'" in problem for problem in run.problems)


def _action(scope: str, bits: int, kind: str, label: str) -> SimulatorAction:
    return SimulatorAction(
        action_id=f"{scope}:{bits}",
        label=label,
        kind=kind,
        raw={
            "scope": scope,
            "bits": bits,
            "idx1": 0,
            "idx2": 0,
            "idx3": 0,
        },
    )
