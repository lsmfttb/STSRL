from __future__ import annotations

from collections.abc import Sequence

import pytest

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controlled_run import (
    build_decision_context,
    execute_controlled_run,
)
from sts_combat_rl.sim.non_combat_calibration import (
    REQUIRED_NON_COMBAT_DRIVER_V1_CATEGORIES,
    format_non_combat_driver_calibration_report,
    run_non_combat_driver_calibration,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import (
    DecisionContext,
    FirstEligiblePolicy,
    StochasticNonCombatDriver,
    non_combat_action_category,
)


def _context(
    screen_state: str,
    kinds: Sequence[str],
    *,
    idx1: Sequence[int | None] | None = None,
    potion_count: int | None = None,
    potion_capacity: int | None = None,
) -> DecisionContext:
    metadata = [
        {} if value is None else {"idx1": value}
        for value in (idx1 or [None] * len(kinds))
    ]
    snapshot_metadata: dict[str, int] = {}
    if potion_count is not None:
        snapshot_metadata["potion_count"] = potion_count
    if potion_capacity is not None:
        snapshot_metadata["potion_capacity"] = potion_capacity
    return DecisionContext(
        screen_state=screen_state,
        snapshot_features=[],
        legal_action_features=[[] for _ in kinds],
        legal_action_kinds=list(kinds),
        eligible_action_indices=list(range(len(kinds))),
        snapshot_metadata=snapshot_metadata,
        legal_action_metadata=metadata,
    )


def _selected_categories(context: DecisionContext, *, limit: int = 500) -> set[str]:
    selected: set[str] = set()
    for seed in range(limit):
        driver = StochasticNonCombatDriver(seed=11)
        driver.reset_for_run(seed)
        decision = driver.select_action(context)
        selected.add(decision.reason.removeprefix(f"{driver.name}:"))
    return selected


def test_stochastic_non_combat_driver_repeats_for_same_driver_and_simulator_seed() -> (
    None
):
    contexts = [
        _context("TREASURE_ROOM", ["treasure_open", "treasure_leave"]),
        _context("REST_ROOM", ["rest", "rest", "rest"], idx1=[0, 1, 2]),
        _context("REWARDS", ["reward_card", "reward_relic", "skip"]),
    ]
    first = StochasticNonCombatDriver(seed=17)
    second = StochasticNonCombatDriver(seed=17)
    first.reset_for_run(101)
    second.reset_for_run(101)

    first_decisions = [first.select_action(context) for context in contexts]
    second_decisions = [second.select_action(context) for context in contexts]

    assert first_decisions == second_decisions
    assert first.provenance_config["reproducible"] is True
    assert first.provenance_config["version"] == 1


def test_driver_categories_preserve_ordinary_and_boss_relic_branches() -> None:
    ordinary = _context("REWARDS", ["reward_relic", "skip"])
    boss = _context("BOSS_RELIC_REWARDS", ["boss_relic", "boss_relic"], idx1=[0, 3])

    assert non_combat_action_category(ordinary, 0) == "ordinary_relic_take"
    assert non_combat_action_category(ordinary, 1) == "ordinary_relic_skip"
    assert non_combat_action_category(boss, 0) == "boss_relic_take"
    assert non_combat_action_category(boss, 1) == "boss_relic_skip"


def test_conditional_contexts_make_all_required_rare_categories_reachable() -> None:
    contexts = [
        _context("REWARDS", ["reward_relic", "skip", "reward_key"]),
        _context("BOSS_RELIC_REWARDS", ["boss_relic", "boss_relic"], idx1=[0, 3]),
        _context("TREASURE_ROOM", ["treasure_open", "treasure_leave"]),
        _context("REST_ROOM", ["rest", "rest", "rest"], idx1=[0, 1, 2]),
        _context(
            "SHOP_ROOM",
            [
                "shop_card_remove",
                "shop_reward_card",
                "shop_reward_potion",
                "shop_reward_relic",
                "shop_skip",
                "game_potion_use",
            ],
            potion_count=1,
            potion_capacity=3,
        ),
        _context(
            "REWARDS",
            ["reward_potion", "game_potion_discard"],
            potion_count=3,
            potion_capacity=3,
        ),
    ]

    selected = set().union(*(_selected_categories(context) for context in contexts))

    assert REQUIRED_NON_COMBAT_DRIVER_V1_CATEGORIES.issubset(selected)


def test_default_battle_potion_exclusion_keeps_non_combat_potion_actions() -> None:
    actions = [
        SimulatorAction(action_id="use", label="use", kind="game_potion_use"),
        SimulatorAction(action_id="skip", label="skip", kind="skip"),
    ]
    rewards_context = build_decision_context(
        {"screen_state": "REWARDS", "battle_active": False},
        actions,
        ActionSpaceConfig.initial_no_potions(),
    )
    battle_context = build_decision_context(
        {"screen_state": "BATTLE", "battle_active": True},
        actions,
        ActionSpaceConfig.initial_no_potions(),
    )

    assert rewards_context.eligible_action_indices == [0, 1]
    assert battle_context.eligible_action_indices == [1]


def test_driver_fails_explicitly_when_legal_potion_actions_lack_visible_slots() -> None:
    context = _context("REWARDS", ["game_potion_use", "skip"])

    with pytest.raises(ValueError, match="potion_count and potion_capacity"):
        StochasticNonCombatDriver(seed=1).select_action(context)


class _TreasureAdapter:
    def __init__(self) -> None:
        self._stepped = False

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self._stepped = False
        return SimulatorSnapshot(
            observation=[],
            raw={"screen_state": "TREASURE_ROOM", "battle_active": False},
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(action_id="open", label="open", kind="treasure_open"),
            SimulatorAction(action_id="leave", label="leave", kind="treasure_leave"),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self._stepped = True
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[],
                raw={"screen_state": "MAP_SCREEN", "outcome": "PLAYER_LOSS"},
            ),
            terminal=True,
            info={"action": action.action_id},
        )


def test_controlled_runs_reset_driver_and_record_selection_reason() -> None:
    controller = RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(StochasticNonCombatDriver(seed=9)),
    )
    adapter = _TreasureAdapter()

    first = execute_controlled_run(adapter, controller, seed=5, max_steps=1)
    second = execute_controlled_run(adapter, controller, seed=5, max_steps=1)

    assert first.steps[0].chosen_action_id == second.steps[0].chosen_action_id
    assert first.steps[0].selection_reason == second.steps[0].selection_reason
    assert first.steps[0].selection_reason.startswith("stochastic_non_combat_v1:")
    assert first.steps[0].provenance.reproducible is True


def test_calibration_report_separates_natural_coverage_gaps_from_failures() -> None:
    report = run_non_combat_driver_calibration(
        _TreasureAdapter(),
        FirstEligiblePolicy(),
        seeds=[10, 11],
        driver_seed=3,
        max_steps=1,
        simulator_config={"ascension": 20, "player_class": "IRONCLAD"},
    )
    text = format_non_combat_driver_calibration_report(report)

    assert report.seed_start == 10
    assert report.seed_end == 11
    assert report.episode_count == 2
    assert report.reached_screen_counts["TREASURE_ROOM"] == 2
    assert report.category_opportunity_counts["treasure_open"] == 2
    assert report.selected_category_counts
    assert report.passed is True
    assert "boss_relic_take" in report.categories_without_natural_opportunity
    assert "boss_relic_take" in report.unavailable_structural_categories
    assert report.battle_controller_provenance["name"] == "first_eligible"
    assert report.simulator_config["ascension"] == 20
    assert report.effective_action_space_config["battle"]["excluded_kinds"]
    assert report.effective_action_space_config["non_combat"]["excluded_kinds"] == []
    assert "Stochastic non-combat driver calibration summary" in text
    assert "screen category relative weights:" in text
    assert "category opportunities:" in text
    assert "categories without natural opportunity:" in text
    assert "unavailable structural categories:" in text


@pytest.mark.parametrize("simulator_config", [None, {"ascension": None}])
def test_calibration_rejects_missing_or_unknown_ascension_provenance(
    simulator_config: dict[str, int | None] | None,
) -> None:
    report = run_non_combat_driver_calibration(
        _TreasureAdapter(),
        FirstEligiblePolicy(),
        seeds=[10, 11],
        driver_seed=3,
        max_steps=1,
        simulator_config=simulator_config,
    )

    assert report.passed is False
    assert report.simulator_config.get("ascension") is None
    assert "concrete integer ascension" in report.problems[0]
