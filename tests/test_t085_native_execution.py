from __future__ import annotations

import inspect
from dataclasses import dataclass, replace

import pytest

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeExecutionError,
    T085NativeTerminalSearchAdapter,
    T085UnguidedBattleSearchV2Controller,
    build_t085_native_arms,
    finalize_t085_native_root_edge_label,
    prepare_t085_native_root_edge_label,
    run_t085_native_paired_evaluation,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
)
from sts_combat_rl.sim.policy_contract import DecisionContext


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="End turn",
            kind="end_turn",
            raw={"scope": "battle", "bits": 22},
        ),
    ]


def _snapshot(*, battle_active: bool = True) -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=[1, 2, 3],
        raw={
            "screen_state": "BATTLE" if battle_active else "REWARDS",
            "battle_active": battle_active,
        },
    )


def _context() -> DecisionContext:
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[], []],
        legal_action_kinds=["card", "end_turn"],
        eligible_action_indices=[0, 1],
    )


def _row(
    bits: int,
    *,
    kind: str,
    label: str,
    visits: int,
    evaluation_sum: float | None,
    mean_value: float | None,
    edge_index: int,
) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": bits,
        "kind": kind,
        "label": label,
        "idx1": 0,
        "idx2": 0,
        "idx3": 0,
        "search_tree_present": True,
        "search_edge_index": edge_index,
        "visits": visits,
        "evaluation_sum": evaluation_sum,
        "mean_value": mean_value,
    }


def _raw_search(*, backend: str = "battle_search") -> dict[str, object]:
    if backend == "battle_search_v2":
        native_api = "StepSimulator.battle_search_v2.v1"
        patch_identity = "sts_lightspeed_battle_search_v2_tree_internal_v1"
    else:
        native_api = "StepSimulator.battle_search.v1"
        patch_identity = ORACLE_SEARCH_PATCH_IDENTITY
    raw: dict[str, object] = {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": native_api,
        "patch_identity": patch_identity,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": 100,
        "root_visits": 3,
        "include_potions": False,
        "native_simulator_steps": 2,
        "model_calls": None,
        "best_action_value": 0.5,
        "min_action_value": 0.1,
        "outcome_player_hp": 40,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": [
            _row(
                11,
                kind="card",
                label="Strike",
                visits=2,
                evaluation_sum=1.0,
                mean_value=0.5,
                edge_index=0,
            ),
            _row(
                22,
                kind="end_turn",
                label="End turn",
                visits=1,
                evaluation_sum=0.25,
                mean_value=0.25,
                edge_index=1,
            ),
        ],
    }
    if backend == "battle_search_v2":
        raw["tree_internal_telemetry"] = {
            "policy_prior_scope": "disabled",
            "leaf_value_boundary": "disabled",
            "policy_prior_calls": 0,
            "leaf_value_calls": 0,
        }
    return raw


def _terminal_transition(outcome: str = "PLAYER_VICTORY") -> SimulatorTransition:
    return SimulatorTransition(
        snapshot=SimulatorSnapshot(
            observation=[4, 5, 6],
            raw={
                "screen_state": "REWARDS",
                "battle_active": False,
                "completed_battle_outcome": outcome,
                "outcome": "UNDECIDED",
            },
        ),
        # LightSpeedAdapter exposes completed_battle_outcome in info even when
        # its generic terminal flag remains false for this transition.
        terminal=False,
        info={"completed_battle_outcome": outcome},
    )


class _SearchAdapter:
    def __init__(self, *, backend: str = "battle_search") -> None:
        self.backend = backend
        self.events: list[str] = []
        self.snapshot = _snapshot()

    def battle_search(self, snapshot, *, simulations, include_potions=False):
        assert self.backend == "battle_search"
        assert snapshot is self.snapshot
        assert simulations == 100
        assert include_potions is False
        self.events.append("search")
        return _raw_search()

    def battle_search_v2(
        self,
        snapshot,
        *,
        simulations,
        include_potions=False,
        policy_prior_callback=None,
        leaf_value_callback=None,
    ):
        assert self.backend == "battle_search_v2"
        assert snapshot is self.snapshot
        assert simulations == 100
        assert include_potions is False
        assert policy_prior_callback is None
        assert leaf_value_callback is None
        self.events.append("search_v2")
        return _raw_search(backend="battle_search_v2")


def test_terminal_utility_is_the_pre_action_selected_root_edge_mean() -> None:
    adapter = _SearchAdapter()
    actions = _actions()
    label = prepare_t085_native_root_edge_label(
        adapter,
        adapter.snapshot,
        actions,
        1,
        simulations=100,
    )

    finalized = finalize_t085_native_root_edge_label(
        label,
        _terminal_transition(),
        pre_action_snapshot=adapter.snapshot,
        pre_action_actions=actions,
        selected_action=actions[1],
    )

    assert finalized.mean_value == 0.25
    assert finalized.terminal_outcome == "PLAYER_VICTORY"
    assert finalized.selected_action_identity["label"] == "End turn"
    assert finalized.to_dict()["utility_source"] == (
        "pre_action_selected_root_edge_mean"
    )


def test_terminal_label_fails_closed_without_terminal_proof() -> None:
    adapter = _SearchAdapter()
    actions = _actions()
    label = prepare_t085_native_root_edge_label(
        adapter,
        adapter.snapshot,
        actions,
        1,
        simulations=100,
    )
    nonterminal = SimulatorTransition(
        snapshot=_snapshot(),
        terminal=False,
        info={"completed_battle_outcome": "UNDECIDED"},
    )

    with pytest.raises(T085NativeExecutionError, match="not proven terminal"):
        finalize_t085_native_root_edge_label(
            label,
            nonterminal,
            pre_action_snapshot=adapter.snapshot,
            pre_action_actions=actions,
            selected_action=actions[1],
        )


def test_unvisited_selected_edge_fails_closed_at_terminal_boundary() -> None:
    adapter = _SearchAdapter()
    actions = _actions()
    raw = _raw_search()
    raw["root_rows"][1]["visits"] = 0
    raw["root_rows"][1]["evaluation_sum"] = None
    raw["root_rows"][1]["mean_value"] = None
    raw["root_visits"] = 2
    adapter.battle_search = lambda *args, **kwargs: raw
    label = prepare_t085_native_root_edge_label(
        adapter,
        adapter.snapshot,
        actions,
        1,
        simulations=100,
    )

    with pytest.raises(T085NativeExecutionError, match="no visited simulations"):
        finalize_t085_native_root_edge_label(
            label,
            _terminal_transition(),
            pre_action_snapshot=adapter.snapshot,
            pre_action_actions=actions,
            selected_action=actions[1],
        )


def test_nonfinite_native_edge_fails_closed_before_labeling() -> None:
    adapter = _SearchAdapter()
    raw = _raw_search()
    raw["root_rows"][1]["mean_value"] = float("nan")
    adapter.battle_search = lambda *args, **kwargs: raw

    with pytest.raises(T085NativeExecutionError, match="root report is malformed"):
        prepare_t085_native_root_edge_label(
            adapter,
            adapter.snapshot,
            _actions(),
            1,
            simulations=100,
        )


def test_native_edge_mean_mismatch_fails_closed_at_terminal_boundary() -> None:
    adapter = _SearchAdapter()
    actions = _actions()
    raw = _raw_search()
    raw["root_rows"][1]["evaluation_sum"] = 0.1
    adapter.battle_search = lambda *args, **kwargs: raw
    label = prepare_t085_native_root_edge_label(
        adapter,
        adapter.snapshot,
        actions,
        1,
        simulations=100,
    )

    with pytest.raises(T085NativeExecutionError, match="disagrees with mean"):
        finalize_t085_native_root_edge_label(
            label,
            _terminal_transition(),
            pre_action_snapshot=adapter.snapshot,
            pre_action_actions=actions,
            selected_action=actions[1],
        )


def test_finalize_rejects_stale_snapshot_or_changed_selected_action() -> None:
    adapter = _SearchAdapter()
    actions = _actions()
    label = prepare_t085_native_root_edge_label(
        adapter,
        adapter.snapshot,
        actions,
        1,
        simulations=100,
    )
    with pytest.raises(T085NativeExecutionError, match="pre-action snapshot"):
        finalize_t085_native_root_edge_label(
            label,
            _terminal_transition(),
            pre_action_snapshot=_snapshot(),
            pre_action_actions=actions,
            selected_action=actions[1],
        )
    with pytest.raises(T085NativeExecutionError, match="selected action"):
        finalize_t085_native_root_edge_label(
            label,
            _terminal_transition(),
            pre_action_snapshot=adapter.snapshot,
            pre_action_actions=actions,
            selected_action=SimulatorAction(
                action_id="battle:999",
                label="not selected",
                kind="card",
            ),
        )


@dataclass
class _ProxyBaseAdapter:
    events: list[str]

    def __post_init__(self) -> None:
        self.snapshot = _snapshot()
        self.actions = _actions()

    def reset(self, seed=None):
        del seed
        self.events.append("reset")
        return self.snapshot

    def legal_actions(self, snapshot):
        assert snapshot is self.snapshot
        self.events.append("legal")
        return self.actions

    def battle_search(self, snapshot, *, simulations, include_potions=False):
        assert snapshot is self.snapshot
        self.events.append("search")
        return _raw_search()

    def step(self, action):
        assert action is self.actions[1]
        self.events.append("step")
        return _terminal_transition("PLAYER_LOSS")


def test_adapter_searches_before_step_and_retains_native_terminal_label() -> None:
    events: list[str] = []
    proxy = T085NativeTerminalSearchAdapter(
        _ProxyBaseAdapter(events),
        search_simulations=100,
    )
    snapshot = proxy.reset(seed=85001)
    actions = proxy.legal_actions(snapshot)
    transition = proxy.step(actions[1])

    assert events == ["reset", "legal", "search", "step"]
    assert transition.info["completed_battle_outcome"] == "PLAYER_LOSS"
    assert len(proxy.native_terminal_labels) == 1
    assert proxy.native_terminal_labels[0].terminal_outcome == "PLAYER_LOSS"


def test_adapter_rejects_duplicate_terminal_labels() -> None:
    events: list[str] = []
    base = _ProxyBaseAdapter(events)
    proxy = T085NativeTerminalSearchAdapter(base, search_simulations=100)
    snapshot = proxy.reset(seed=85001)
    actions = proxy.legal_actions(snapshot)
    proxy.step(actions[1])
    # Re-presenting a battle snapshot after a terminal label must not silently
    # produce a second retained label.
    proxy.legal_actions(base.snapshot)
    with pytest.raises(T085NativeExecutionError, match="duplicate terminal labels"):
        proxy.step(actions[1])


def test_unguided_v2_controller_passes_both_callbacks_as_none() -> None:
    adapter = _SearchAdapter(backend="battle_search_v2")
    controller = T085UnguidedBattleSearchV2Controller(simulations=100)
    decision = controller.select_action(
        adapter,
        adapter.snapshot,
        _actions(),
        _context(),
        step_index=0,
    )

    assert decision.selected_index == 0
    assert decision.provenance.config["native_leaf_value"] == (
        "BattleScumSearcher2::evaluateEndState"
    )
    assert decision.provenance.config["information_regime"] == (
        NATIVE_SEARCH_INFORMATION_REGIME
    )
    assert adapter.events == ["search_v2"]


def test_unguided_v2_controller_rejects_callback_telemetry() -> None:
    adapter = _SearchAdapter(backend="battle_search_v2")
    raw = _raw_search(backend="battle_search_v2")
    raw["tree_internal_telemetry"]["leaf_value_calls"] = 1
    adapter.battle_search_v2 = lambda *args, **kwargs: raw
    controller = T085UnguidedBattleSearchV2Controller(simulations=100)

    with pytest.raises(T085NativeExecutionError, match="leaf_value_calls"):
        controller.select_action(
            adapter,
            adapter.snapshot,
            _actions(),
            _context(),
            step_index=0,
        )


def test_terminal_labeler_does_not_accept_a_callback_search_report() -> None:
    adapter = _SearchAdapter(backend="battle_search_v2")
    raw = _raw_search(backend="battle_search_v2")
    raw["tree_internal_telemetry"]["leaf_value_calls"] = 1
    adapter.battle_search_v2 = lambda *args, **kwargs: raw

    with pytest.raises(T085NativeExecutionError, match="leaf_value_calls"):
        prepare_t085_native_root_edge_label(
            adapter,
            adapter.snapshot,
            _actions(),
            0,
            simulations=100,
            backend="battle_search_v2",
        )


def test_v2_controller_rejects_non_no_potion_action_space() -> None:
    action_space = replace(
        ActionSpaceConfig.initial_no_potions(),
        preferred_kinds=("card",),
    )
    with pytest.raises(T085NativeExecutionError, match="initial_no_potions"):
        T085UnguidedBattleSearchV2Controller(action_space=action_space)


def test_t085_runner_has_no_result_injection_boundary() -> None:
    parameters = inspect.signature(run_t085_native_paired_evaluation).parameters
    assert "execute_record" not in parameters
    assert "restore_record" not in parameters
    assert "controller_factory" not in parameters


def test_t085_arm_builder_makes_baselines_explicit_native_v2_no_callback() -> None:
    callback = lambda *_args, **_kwargs: 0.0
    arms = build_t085_native_arms(
        old_checkpoint_64001="old-1",
        corrected_checkpoint_85001="new-1",
        old_checkpoint_64002="old-2",
        corrected_checkpoint_85002="new-2",
        old_value_callback_64001=callback,
        corrected_value_callback_85001=callback,
        old_value_callback_64002=callback,
        corrected_value_callback_85002=callback,
        prior_callback_64001=callback,
        prior_callback_64002=callback,
    )
    for name in ("baseline", "baseline@400"):
        assert arms[name].policy_prior_callback is None
        assert arms[name].leaf_value_callback is None
        assert arms[name].provenance["native_search_api"] == (
            "StepSimulator.battle_search_v2.v1"
        )


def test_outcome_parser_keeps_absolute_hp_and_structured_resources_separate() -> None:
    from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
        T085OutcomeRecord,
    )

    row = T085OutcomeRecord.from_mapping(
        {
            "cohort": "A",
            "record_identity": "r",
            "arm": "baseline",
            "battle_survived": True,
            "terminal_native_utility": 1.5,
            "terminal_current_hp": 42,
            "structured_battle_resource_outcome": {"gold_delta": 9},
        }
    )
    assert row.terminal_current_hp == 42
    assert row.structured_battle_resource_outcome == {"gold_delta": 9}
