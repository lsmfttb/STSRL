"""Tests for controller contract, online controllers, and controlled-run executor.

Covers:
- ControllerProvenance identity, serialization, and round-trip
- ControllerDecision frozen fields
- PolicyController wrapping DecisionPolicy
- RoutedRunController battle vs non-combat routing
- ChooserController wrapping a callable chooser
- execute_controlled_run loop with before/after observers
- selected_index_problem validation
- eligible_indices deduplication
- is_battle_state routing signal
- Deterministic reproducibility of provenance identity
"""

from __future__ import annotations


import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import (
    CONTROLLER_PROVENANCE_SCHEMA_VERSION,
    ControllerDecision,
    ControllerProvenance,
    OnlineController,
    controller_provenance_from_dict,
    json_safe_mapping,
    legacy_policy_provenance,
    selected_index_problem,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    ControlledRunStep,
    build_decision_context,
    execute_controlled_run,
    format_controlled_run,
)
from sts_combat_rl.sim.online_controller import (
    ChooserController,
    NON_COMBAT_DRIVER_CONTROLLER_ROLE,
    BATTLE_AGENT_CONTROLLER_ROLE,
    PolicyController,
    RoutedRunController,
    deterministic_chooser_controller,
    is_battle_state,
)
from sts_combat_rl.sim.policy import (
    FirstEligiblePolicy,
    PreferredKindPolicy,
)


# ---------------------------------------------------------------------------
# ControllerProvenance
# ---------------------------------------------------------------------------


class TestControllerProvenance:
    def test_identity_is_content_addressed_prefix(self) -> None:
        p = ControllerProvenance(
            kind="test",
            name="alpha",
            config={"key": "value"},
        )
        # Identity is a structured prefix:sha256_hex (e.g. "test:alpha:a22e31a7a24a")
        assert ":" in p.identity
        assert len(p.identity) > 12

    def test_same_inputs_produce_same_identity(self) -> None:
        a = ControllerProvenance(kind="k", name="n", config={"a": 1})
        b = ControllerProvenance(kind="k", name="n", config={"a": 1})
        assert a.identity == b.identity

    def test_different_config_produces_different_identity(self) -> None:
        a = ControllerProvenance(kind="k", name="n", config={"a": 1})
        b = ControllerProvenance(kind="k", name="n", config={"a": 2})
        assert a.identity != b.identity

    def test_schema_version(self) -> None:
        p = ControllerProvenance(kind="k", name="n", config={})
        assert p.schema_version == CONTROLLER_PROVENANCE_SCHEMA_VERSION

    def test_reproducible_default_true(self) -> None:
        p = ControllerProvenance(kind="k", name="n", config={})
        assert p.reproducible is True

    def test_reproducible_explicit_false(self) -> None:
        p = ControllerProvenance(kind="k", name="n", config={"reproducible": False})
        assert p.reproducible is False

    def test_legacy_kind_not_reproducible(self) -> None:
        p = legacy_policy_provenance("some_policy")
        assert p.reproducible is False
        assert p.kind == "legacy_policy_name_only"
        assert p.name == "some_policy"
        assert p.config.get("reproducible") is False

    def test_to_dict_round_trip(self) -> None:
        p = ControllerProvenance(
            kind="test_kind",
            name="test_name",
            config={"int_val": 1, "str_val": "hello", "nested": {"a": True}},
        )
        d = p.to_dict()
        assert d["kind"] == "test_kind"
        assert d["name"] == "test_name"
        assert d["config"]["nested"]["a"] is True
        assert d["schema_version"] == p.schema_version
        loaded = controller_provenance_from_dict(d)
        assert loaded.identity == p.identity
        assert loaded == p

    def test_controller_provenance_from_dict_strict(self) -> None:
        with pytest.raises(ValueError, match="schema_version"):
            controller_provenance_from_dict({"kind": "k"})

    def test_to_json_round_trip(self) -> None:
        p = ControllerProvenance(kind="k", name="n", config={"x": 1})
        json_str = p.to_json()
        loaded = controller_provenance_from_dict(json.loads(json_str))
        assert loaded == p

    def test_frozen(self) -> None:
        p = ControllerProvenance(kind="k", name="n", config={})
        with pytest.raises(AttributeError):
            p.kind = "other"  # type: ignore[misc]

    def test_json_safe_mapping_coerces_unsafe_values(self) -> None:
        unsafe = object()
        result = json_safe_mapping({"a": 1, "b": "ok", "c": unsafe, "d": None})
        # json_safe_mapping keeps JSON-serializable values and coerces unsafe ones
        # to their str() representation (lossy but preserves presence).
        assert "a" in result
        assert result["a"] == 1
        assert result["b"] == "ok"
        assert result["d"] is None
        assert "c" in result
        assert isinstance(result["c"], str)
        assert result["c"] == str(unsafe)


# Need json import for the round-trip test
import json  # noqa: E402


# ---------------------------------------------------------------------------
# ControllerDecision
# ---------------------------------------------------------------------------


class TestControllerDecision:
    def test_frozen(self) -> None:
        prov = ControllerProvenance(kind="k", name="n", config={})
        d = ControllerDecision(
            selected_index=0,
            provenance=prov,
            reason="test",
            score=0.5,
        )
        with pytest.raises(AttributeError):
            d.selected_index = 1  # type: ignore[misc]

    def test_metadata_default_empty(self) -> None:
        prov = ControllerProvenance(kind="k", name="n", config={})
        d = ControllerDecision(selected_index=0, provenance=prov, reason="test")
        assert d.metadata == {}


# ---------------------------------------------------------------------------
# PolicyController
# ---------------------------------------------------------------------------


class TestPolicyController:
    def test_wraps_policy(self) -> None:
        policy = FirstEligiblePolicy()
        ctrl = PolicyController(policy)
        assert ctrl.provenance.name == "first_eligible"
        assert ctrl.provenance.kind == "decision_policy"

    def test_select_action_returns_controller_decision(self) -> None:
        policy = FirstEligiblePolicy()
        ctrl = PolicyController(policy)
        actions = [_make_action("end", "end_turn"), _make_action("card", "card")]
        snapshot = _battle_snapshot()
        ctx = build_decision_context(
            snapshot.raw, actions, ActionSpaceConfig.initial_no_potions()
        )
        decision = ctrl.select_action(None, snapshot, actions, ctx, 0)
        assert isinstance(decision, ControllerDecision)
        assert decision.selected_index == 0
        assert decision.provenance.name == "first_eligible"

    def test_passes_context_not_raw(self) -> None:
        """PolicyController passes sanitized context, not raw trio."""
        policy = FirstEligiblePolicy()
        ctrl = PolicyController(policy)
        actions = [_make_action("end", "end_turn"), _make_action("card", "card")]
        snapshot = _battle_snapshot()
        ctx = build_decision_context(
            snapshot.raw, actions, ActionSpaceConfig.initial_no_potions()
        )
        decision = ctrl.select_action(None, snapshot, actions, ctx, 0)
        assert isinstance(decision, ControllerDecision)

    def test_implements_protocol(self) -> None:
        ctrl = PolicyController(FirstEligiblePolicy())
        assert isinstance(ctrl, OnlineController)

    def test_provenance_merges_policy_config(self) -> None:
        policy = PreferredKindPolicy(preferred_kinds=["card", "skill"])
        ctrl = PolicyController(policy)
        assert ctrl.provenance.config.get("preferred_kinds") == ("card", "skill")


# ---------------------------------------------------------------------------
# RoutedRunController
# ---------------------------------------------------------------------------


class TestRoutedRunController:
    def test_routes_battle_to_battle_controller(self) -> None:
        battle = PolicyController(FirstEligiblePolicy())
        non_combat = PolicyController(FirstEligiblePolicy())
        routed = RoutedRunController(battle, non_combat)
        actions = [_make_action("card", "card")]
        snapshot = _battle_snapshot()
        ctx = build_decision_context(
            snapshot.raw, actions, ActionSpaceConfig.initial_no_potions()
        )
        decision = routed.select_action(None, snapshot, actions, ctx, 0)
        assert decision.metadata.get("controller_role") == BATTLE_AGENT_CONTROLLER_ROLE

    def test_routes_non_combat_to_non_combat_controller(self) -> None:
        battle = PolicyController(FirstEligiblePolicy())
        non_combat = PolicyController(FirstEligiblePolicy())
        routed = RoutedRunController(battle, non_combat)
        actions = [_make_action("skip", "skip")]
        snapshot = _non_battle_snapshot()
        ctx = build_decision_context(
            snapshot.raw, actions, ActionSpaceConfig.initial_no_potions()
        )
        decision = routed.select_action(None, snapshot, actions, ctx, 0)
        assert (
            decision.metadata.get("controller_role")
            == NON_COMBAT_DRIVER_CONTROLLER_ROLE
        )

    def test_provenance_composites_children(self) -> None:
        battle = PolicyController(FirstEligiblePolicy())
        non_combat = PolicyController(PreferredKindPolicy())
        routed = RoutedRunController(battle, non_combat)
        assert routed.provenance.kind == "routed_run"
        assert "battle" in routed.provenance.config
        assert "non_combat" in routed.provenance.config

    def test_implements_protocol(self) -> None:
        routed = RoutedRunController(
            PolicyController(FirstEligiblePolicy()),
            PolicyController(FirstEligiblePolicy()),
        )
        assert isinstance(routed, OnlineController)


# ---------------------------------------------------------------------------
# ChooserController
# ---------------------------------------------------------------------------


class TestChooserController:
    def test_wraps_callable(self) -> None:
        def chooser(actions: list, action_space) -> object:  # noqa: ANN001
            return actions[0]

        ctrl = ChooserController(chooser)
        actions = [_make_action("card", "card")]
        snapshot = _battle_snapshot()
        decision = ctrl.select_action(None, snapshot, actions, None, 0)
        assert decision.selected_index == 0
        assert decision.provenance.kind == "chooser"

    def test_deterministic_factory(self) -> None:
        ctrl = deterministic_chooser_controller()
        actions = [_make_action("end", "end_turn"), _make_action("card", "card")]
        snapshot = _battle_snapshot()
        decision = ctrl.select_action(None, snapshot, actions, None, 0)
        # preferred_kinds = ("card", "end_turn"), so card at index 1 wins
        assert decision.selected_index == 1


# ---------------------------------------------------------------------------
# is_battle_state
# ---------------------------------------------------------------------------


class TestIsBattleState:
    def test_battle_screen_state(self) -> None:
        assert is_battle_state(None, "BATTLE") is True

    def test_non_battle_screen_state(self) -> None:
        assert is_battle_state(None, "REWARDS") is False
        assert is_battle_state(None, "MAP") is False

    def test_battle_active_raw(self) -> None:
        assert is_battle_state({"battle_active": True}, None) is True
        assert is_battle_state({"battle_active": False}, None) is False

    def test_battle_hand_only_is_not_battle(self) -> None:
        """battle_hand without battle_active or BATTLE screen is not battle."""
        assert is_battle_state({"battle_hand": []}, None) is False


# ---------------------------------------------------------------------------
# selected_index_problem
# ---------------------------------------------------------------------------


class TestSelectedIndexProblem:
    def test_valid_index(self) -> None:
        assert selected_index_problem(0, 2, [0, 1], "test") is None
        assert selected_index_problem(1, 2, [0, 1], "test") is None

    def test_negative_index(self) -> None:
        assert (
            selected_index_problem(-1, 5, [0, 1, 2, 3, 4], "ctrl")
            == "ctrl selected action index -1 outside 5 legal actions"
        )

    def test_out_of_range(self) -> None:
        assert (
            selected_index_problem(5, 3, [0, 1, 2], "ctrl")
            == "ctrl selected action index 5 outside 3 legal actions"
        )

    def test_empty_actions(self) -> None:
        result = selected_index_problem(0, 0, [], "ctrl")
        assert result is not None
        assert "0 outside 0" in result

    def test_index_outside_eligible(self) -> None:
        result = selected_index_problem(1, 3, [0, 2], "ctrl")
        assert result is not None
        assert "outside the active action space" in result


# ---------------------------------------------------------------------------
# eligible_indices
# ---------------------------------------------------------------------------


class TestEligibleIndices:
    def test_basic_eligibility(self) -> None:
        from sts_combat_rl.sim.action_space import eligible_indices, ActionSpaceConfig

        actions = [
            _make_action("potion", "potion"),
            _make_action("card", "card"),
        ]
        config = ActionSpaceConfig.initial_no_potions()
        indices = eligible_indices(actions, config)
        assert indices == [1]

    def test_include_all(self) -> None:
        from sts_combat_rl.sim.action_space import eligible_indices, ActionSpaceConfig

        actions = [
            _make_action("potion", "potion"),
            _make_action("card", "card"),
        ]
        config = ActionSpaceConfig.include_all()
        indices = eligible_indices(actions, config)
        assert indices == [0, 1]


# ---------------------------------------------------------------------------
# execute_controlled_run
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Minimal adapter for testing the executor loop.

    ``phases[i]`` describes the transition *after* step i:
    - screen_state for the post-step snapshot
    - terminal flag for the post-step transition

    The initial snapshot always uses ``phases[0]`` screen_state (non-terminal).
    """

    def __init__(self, phases: list[tuple[str, bool]] | None = None) -> None:
        self.phases = phases or [("BATTLE", True)]
        self._step_idx = 0
        self.action_log: list[str] = []

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self._step_idx = 0
        self.action_log = []
        return self._snapshot_for(0)

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            _make_action("end", "end_turn"),
            _make_action("card", "card"),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.action_log.append(action.kind)
        idx = min(self._step_idx, len(self.phases) - 1)
        self._step_idx += 1
        screen, terminal = self.phases[idx]
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[idx + 1],
                raw={
                    "screen_state": screen,
                    "outcome": "PLAYER_VICTORY" if terminal else "UNDECIDED",
                    "battle_active": screen == "BATTLE" and not terminal,
                    "floor_num": idx + 2,
                    "cur_hp": 80 - (idx + 1) * 5,
                    "max_hp": 80,
                    "gold": 100,
                    "potion_count": 0,
                },
            ),
            terminal=terminal,
            info={},
        )

    def _snapshot_for(self, idx: int) -> SimulatorSnapshot:
        screen, _ = self.phases[min(idx, len(self.phases) - 1)]
        return SimulatorSnapshot(
            observation=[0],
            raw={
                "screen_state": screen,
                "outcome": "UNDECIDED",
                "battle_active": screen == "BATTLE",
                "floor_num": 1,
                "cur_hp": 80,
                "max_hp": 80,
                "gold": 100,
                "potion_count": 0,
            },
        )


class AlwaysFirstController:
    """A simple controller that always picks the first action."""

    def __init__(self, role: str = "test") -> None:
        self._role = role

    @property
    def provenance(self) -> ControllerProvenance:
        return ControllerProvenance(
            kind="test",
            name="always_first",
            config={"role": self._role},
        )

    def select_action(
        self,
        adapter: object,
        snapshot: SimulatorSnapshot,
        actions: list[SimulatorAction],
        context: object,
        step_index: int,
    ) -> ControllerDecision:
        return ControllerDecision(
            selected_index=0,
            provenance=self.provenance,
            reason="always first",
            metadata={"controller_role": self._role},
        )


class TestExecuteControlledRun:
    def test_basic_execution(self) -> None:
        adapter = FakeAdapter([("BATTLE", False), ("BATTLE", True)])
        ctrl = AlwaysFirstController()

        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=10)

        assert isinstance(result, ControlledRun)
        assert result.seed == 1
        assert len(result.steps) == 2
        assert result.terminal is True
        assert result.outcome == "PLAYER_VICTORY"
        assert result.problems == []

    def test_max_steps_limit(self) -> None:
        adapter = FakeAdapter([("BATTLE", False)] * 20)
        ctrl = AlwaysFirstController()

        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=3)

        assert len(result.steps) == 3
        assert result.terminal is False

    def test_step_fields(self) -> None:
        adapter = FakeAdapter([("BATTLE", True)])
        ctrl = AlwaysFirstController()

        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=10)

        step = result.steps[0]
        assert step.step_index == 0
        assert step.controller_role == "test"
        assert step.chosen_action_kind == "end_turn"
        assert step.chosen_action_index == 0
        assert step.terminal_after_step is True
        assert step.floor == 1.0
        assert step.player_hp == 80.0

    def test_controller_provenance_recorded(self) -> None:
        adapter = FakeAdapter([("BATTLE", True)])
        ctrl = AlwaysFirstController()

        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=10)

        assert result.controller_provenance["kind"] == "test"
        assert result.controller_provenance["name"] == "always_first"
        step = result.steps[0]
        assert step.provenance is not None
        assert step.provenance.identity == ctrl.provenance.identity

    def test_before_observer_called(self) -> None:
        adapter = FakeAdapter([("BATTLE", True)])
        ctrl = AlwaysFirstController()
        calls: list[int] = []

        def before(
            snapshot: SimulatorSnapshot,
            actions: list[SimulatorAction],
            context: object,
            step_index: int,
        ) -> None:
            calls.append(step_index)

        execute_controlled_run(
            adapter, ctrl, seed=1, max_steps=10, before_decision=before
        )

        assert calls == [0]

    def test_after_observer_called(self) -> None:
        adapter = FakeAdapter([("BATTLE", True)])
        ctrl = AlwaysFirstController()
        calls: list[int] = []

        def after(step: ControlledRunStep) -> None:
            calls.append(step.step_index)

        execute_controlled_run(
            adapter, ctrl, seed=1, max_steps=10, after_transition=after
        )

        assert calls == [0]

    def test_invalid_selected_index_reports_problem(self) -> None:
        adapter = FakeAdapter([("BATTLE", False), ("BATTLE", True)])

        class BadController:
            @property
            def provenance(self) -> ControllerProvenance:
                return ControllerProvenance(kind="bad", name="bad", config={})

            def select_action(
                self, *args: object, **kwargs: object
            ) -> ControllerDecision:
                return ControllerDecision(
                    selected_index=99,
                    provenance=self.provenance,
                    reason="bad",
                    metadata={"controller_role": "test"},
                )

        result = execute_controlled_run(adapter, BadController(), seed=1, max_steps=10)

        assert len(result.steps) == 0
        assert len(result.problems) > 0
        assert "99" in result.problems[0]

    def test_format_controlled_run(self) -> None:
        adapter = FakeAdapter([("BATTLE", True)])
        ctrl = AlwaysFirstController()
        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=10)
        text = format_controlled_run(result)
        assert "Controlled run summary" in text
        assert "steps: 1" in text

    def test_multi_step_with_resource_tracking(self) -> None:
        adapter = FakeAdapter([("BATTLE", False), ("BATTLE", False), ("BATTLE", True)])
        ctrl = AlwaysFirstController()
        result = execute_controlled_run(adapter, ctrl, seed=1, max_steps=10)

        assert len(result.steps) == 3
        assert result.steps[0].player_hp == 80.0
        assert result.steps[1].player_hp == 75.0
        assert result.steps[2].player_hp == 70.0


# ---------------------------------------------------------------------------
# Determinism / Reproducibility
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_seed_same_steps(self) -> None:
        adapter = FakeAdapter([("BATTLE", False), ("BATTLE", True)])
        ctrl = AlwaysFirstController()

        a = execute_controlled_run(adapter, ctrl, seed=42, max_steps=10)
        b = execute_controlled_run(adapter, ctrl, seed=42, max_steps=10)

        assert len(a.steps) == len(b.steps)
        for sa, sb in zip(a.steps, b.steps):
            assert sa.chosen_action_index == sb.chosen_action_index
            assert sa.chosen_action_kind == sb.chosen_action_kind

    def test_provenance_identity_stable(self) -> None:
        prov = ControllerProvenance(kind="k", name="n", config={"v": 1})
        assert (
            prov.identity
            == ControllerProvenance(kind="k", name="n", config={"v": 1}).identity
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(action_id: str, kind: str) -> SimulatorAction:
    return SimulatorAction(
        action_id=action_id,
        label=action_id,
        kind=kind,
        raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
    )


def _battle_snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=[0],
        raw={
            "screen_state": "BATTLE",
            "outcome": "UNDECIDED",
            "battle_active": True,
            "battle_hand": [{"type": "ATTACK", "playable": True}],
            "battle_monsters": [{"current_hp": 10, "targetable": True}],
            "floor_num": 1,
            "cur_hp": 80,
            "max_hp": 80,
            "gold": 100,
            "potion_count": 0,
        },
    )


def _non_battle_snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=[0],
        raw={
            "screen_state": "REWARDS",
            "outcome": "UNDECIDED",
            "battle_active": False,
            "floor_num": 1,
            "cur_hp": 80,
            "max_hp": 80,
            "gold": 100,
            "potion_count": 0,
        },
    )
