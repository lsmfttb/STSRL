"""Independent small graph oracles for T088; no native simulator execution."""

from __future__ import annotations

import math
from copy import deepcopy

import pytest

from sts_combat_rl.commands.t085_native_execution import (
    T085UnguidedBattleSearchV2Controller,
)
from sts_combat_rl.commands.t088_classical_combat_tournament import (
    build_t088_controller,
    t088_controller_definitions,
)
from sts_combat_rl.sim.classical_combat_search import (
    BeamH1Controller,
    ClassicalSearchUnavailableError,
    combat_handcrafted_h1,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)


def _raw(*, hp=50, enemies=None, turn=4, block=25):
    return {
        "battle_outcome": "UNDECIDED",
        "battle_player": {"current_hp": hp, "max_hp": 100, "block": block},
        "battle_turn": turn,
        "battle_monsters": (
            [{"current_hp": 50, "max_hp": 200, "targetable": True}]
            if enemies is None
            else enemies
        ),
    }


class _Graph:
    """An abstract labelled graph, not Slay the Spire mechanics or a cohort."""

    supports_checkpoint_restore = True

    def __init__(self, states, edges):
        self.states = states
        self.edges = edges
        self.current = "root"
        self.executed = []
        self.restored = []

    def snapshot(self):
        return SimulatorSnapshot((), self.states[self.current])

    def legal_actions(self, snapshot):
        assert snapshot.raw == self.states[self.current]
        return [
            SimulatorAction(
                # Deliberate duplicate public ids: positional identity matters.
                "duplicate",
                "action",
                kind,
                {"source": self.current, "destination": destination},
            )
            for destination, kind in self.edges.get(self.current, [])
        ]

    def capture_checkpoint(self, snapshot):
        assert snapshot.raw == self.states[self.current]
        return SimulatorCheckpoint("graph", self.current, self.current)

    def restore_checkpoint(self, checkpoint):
        self.current = checkpoint.payload
        self.restored.append(self.current)
        return self.snapshot()

    def step(self, action):
        assert action.raw["source"] == self.current
        self.executed.append((self.current, action.raw["destination"]))
        self.current = action.raw["destination"]
        return SimulatorTransition(self.snapshot(), False)


def _select(graph, *, step_index=0):
    return BeamH1Controller().select_action(
        graph, graph.snapshot(), graph.legal_actions(graph.snapshot()), None, step_index
    )


def test_h1_formula_components_and_active_enemy_semantics():
    raw = _raw(
        enemies=[
            {"current_hp": 20, "max_hp": 80, "targetable": True},
            {"current_hp": 30, "max_hp": 120, "targetable": True},
            # Escaped/half-dead positive-HP occurrences are not Battle-active.
            {"current_hp": 500, "max_hp": 500, "targetable": False},
        ]
    )
    value = combat_handcrafted_h1(raw)
    assert value.player_hp_fraction == 0.5
    assert value.active_enemy_hp_fraction == 0.25
    assert value.block_fraction == 0.2
    assert value.turn_fraction == 0.2
    assert value.h_raw == pytest.approx(0.58)
    assert value.value == pytest.approx(math.tanh(0.58))


@pytest.mark.parametrize(("turn", "fraction"), [(-9, 0), (0, 0), (10, 0.5), (999, 1)])
def test_h1_turn_clamp_and_empty_active_enemy_set(turn, fraction):
    value = combat_handcrafted_h1(_raw(turn=turn, enemies=[]))
    assert value.turn_fraction == fraction
    assert value.active_enemy_hp_fraction == 0


def test_h1_does_not_read_hidden_or_unrelated_fields():
    raw = _raw()
    original = combat_handcrafted_h1(raw)
    raw.update(
        {"rng_state": object(), "draw_order": object(), "hidden_act3_boss": object()}
    )
    raw["battle_player"]["relics"] = object()
    assert combat_handcrafted_h1(raw) == original


@pytest.mark.parametrize(
    ("container", "field", "value"),
    [
        ("battle_player", "max_hp", 0),
        ("battle_player", "current_hp", None),
        ("battle_player", "block", -1),
        ("battle_player", "block", float("inf")),
        ("battle_player", "current_hp", True),
        (None, "battle_turn", float("nan")),
        (None, "battle_monsters", [{"current_hp": 50, "max_hp": 100}]),
        (None, "battle_monsters", [{"targetable": "true"}]),
        (None, "battle_monsters", [{"targetable": True, "max_hp": 0, "current_hp": 0}]),
    ],
)
def test_h1_fails_closed_on_missing_or_invalid_fields(container, field, value):
    raw = _raw()
    (raw if container is None else raw[container])[field] = value
    with pytest.raises(ClassicalSearchUnavailableError):
        combat_handcrafted_h1(raw)


def test_beam_finishes_layer_and_uses_authoritative_victory_over_h1():
    graph = _Graph(
        {
            "root": _raw(),
            # Rewards/game outcome is undecided, Battle victory is authoritative.
            "win": {
                "completed_battle_outcome": "PLAYER_VICTORY",
                "outcome": "UNDECIDED",
            },
            "high_h1": _raw(hp=100, enemies=[]),
        },
        {"root": [("win", "card"), ("high_h1", "card")]},
    )
    decision = _select(graph)
    assert decision.selected_index == 0
    assert graph.executed == [("root", "win"), ("root", "high_h1")]
    assert decision.metadata["classical_search"]["selected_path_h1"] is None
    assert decision.metadata["classical_search"]["stop_reason"] == "victory"
    assert graph.current == "root"


def test_beam_excludes_potions_and_preserves_duplicate_action_occurrences():
    graph = _Graph(
        {
            "root": _raw(),
            "potion_win": {"completed_battle_outcome": "PLAYER_VICTORY"},
            "loss": {"completed_battle_outcome": "PLAYER_LOSS"},
            "win": {"completed_battle_outcome": "PLAYER_VICTORY"},
        },
        {"root": [("potion_win", "potion"), ("loss", "card"), ("win", "card")]},
    )
    decision = _select(graph)
    assert decision.selected_index == 2
    assert (
        decision.metadata["classical_search"]["selected_action_identity"]["occurrence"]
        == 2
    )
    assert graph.executed == [("root", "loss"), ("root", "win")]


def test_beam_width_32_prunes_lowest_nonterminal_before_next_layer():
    states = {"root": _raw(), "loss": {"completed_battle_outcome": "PLAYER_LOSS"}}
    states["win"] = {"completed_battle_outcome": "PLAYER_VICTORY"}
    states.update({str(i): _raw(hp=i + 1) for i in range(33)})
    edges = {"root": [(str(i), "card") for i in range(33)]}
    edges.update({str(i): [("win" if i == 0 else "loss", "card")] for i in range(33)})
    graph = _Graph(states, edges)
    decision = _select(graph)
    assert ("0", "win") not in graph.executed
    # Every retained two-action path loses: exact lexicographic indices break ties.
    assert decision.metadata["classical_search"]["selected_action_indices"] == [1, 0]
    assert len(graph.executed) == 65


def test_beam_global_transition_budget_and_deterministic_replay():
    graph = _Graph({"root": _raw()}, {"root": [("root", "card")] * 40})
    first = _select(graph)
    assert len(graph.executed) == 400
    evidence = first.metadata["classical_search"]
    assert evidence["successor_transition_count"] == 400
    assert evidence["action_execution_count"] == 400
    assert evidence["tree_node_expansion_count"] == 10
    assert evidence["selected_action_indices"] == [0, 0]
    assert evidence["stop_reason"] == "transition_budget"
    assert evidence["model_calls"] == evidence["rollout_count"] == 0
    assert evidence["native_simulator_steps"] is None
    assert math.isfinite(evidence["wall_clock_seconds"])
    assert evidence["wall_clock_seconds"] >= 0
    second = _select(graph)
    assert len(graph.executed) == 800
    without_time = lambda d: {k: v for k, v in d.items() if k != "wall_clock_seconds"}
    assert without_time(evidence) == without_time(second.metadata["classical_search"])


def test_beam_respects_remaining_controlled_actions():
    graph = _Graph({"root": _raw()}, {"root": [("root", "card")]})
    decision = _select(graph, step_index=199)
    assert len(graph.executed) == 1
    assert decision.metadata["classical_search"]["selected_action_indices"] == [0]
    assert (
        decision.metadata["classical_search"]["stop_reason"]
        == "controlled_action_boundary"
    )


def test_beam_shorter_terminal_path_wins_tie_after_deeper_loss():
    graph = _Graph(
        {
            "root": _raw(),
            "next": _raw(),
            "loss": {"completed_battle_outcome": "PLAYER_LOSS"},
        },
        {"root": [("next", "card"), ("loss", "card")], "next": [("loss", "card")]},
    )
    # A terminal loss ranks below an undecided node, then wins the shorter-path
    # tie when the remaining branch also loses on its second action.
    decision = _select(graph)
    assert decision.selected_index == 1
    assert decision.metadata["classical_search"]["selected_action_indices"] == [1]
    assert len(graph.executed) == 3


def test_beam_restores_root_after_invalid_successor_evidence():
    bad = deepcopy(_raw())
    del bad["battle_player"]["block"]
    graph = _Graph({"root": _raw(), "bad": bad}, {"root": [("bad", "card")]})
    with pytest.raises(ClassicalSearchUnavailableError, match="block"):
        _select(graph)
    assert graph.current == "root"
    assert graph.restored[-1] == "root"


@pytest.mark.parametrize("step_index", [-1, 200, True])
def test_beam_rejects_invalid_remaining_action_boundary_before_transition(step_index):
    graph = _Graph({"root": _raw()}, {"root": [("root", "card")]})
    with pytest.raises(
        ClassicalSearchUnavailableError, match="controlled action boundary"
    ):
        _select(graph, step_index=step_index)
    assert graph.executed == []


def test_four_arm_construction_keeps_accepted_ab_and_fails_closed_for_d():
    baseline = build_t088_controller("A")
    scaling = build_t088_controller("B")
    assert type(baseline) is type(scaling) is T085UnguidedBattleSearchV2Controller
    assert baseline.simulations == 100
    assert scaling.simulations == 400
    for controller in (baseline, scaling):
        config = controller.provenance.config
        assert config["policy_prior_callback"] is None
        assert config["leaf_value_callback"] is None
        assert config["root_selection_rule"] == "highest_mean"
        assert config["information_regime"] == "full_simulator_state_oracle_like"
    assert isinstance(build_t088_controller("C"), BeamH1Controller)
    with pytest.raises(ClassicalSearchUnavailableError, match="governed native"):
        build_t088_controller("D")
    with pytest.raises(ValueError, match="unknown T088 arm"):
        build_t088_controller("E")
    definitions = t088_controller_definitions()
    assert definitions["arm_order"] == ["A", "B", "C", "D"]
    assert definitions["tournament_execution_ready"] is False
    assert definitions["arms"]["D"]["progressive_bias_weight"] == 0.5
