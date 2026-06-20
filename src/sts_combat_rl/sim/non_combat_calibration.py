"""Calibration for the versioned stochastic non-combat driver.

The report stays separate from battle metrics because the driver determines the
incoming-state distribution; it is not a learned battle policy and its action
counts must remain auditable on their own.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import json
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig, action_space_for_screen
from sts_combat_rl.sim.battle_agent import collect_battle_agent_rollout
from sts_combat_rl.sim.contract import SimulatorAdapter
from sts_combat_rl.sim.online_controller import (
    NON_COMBAT_DRIVER_CONTROLLER_ROLE,
    PolicyController,
    is_battle_state,
)
from sts_combat_rl.sim.policy import (
    DecisionContext,
    DecisionPolicy,
    StochasticNonCombatDriver,
    non_combat_action_category,
)


REQUIRED_NON_COMBAT_DRIVER_V1_CATEGORIES = frozenset(
    {
        "ordinary_relic_take",
        "ordinary_relic_skip",
        "boss_relic_take",
        "boss_relic_skip",
        "treasure_open",
        "treasure_leave",
        "rest_heal",
        "rest_upgrade",
        "rest_other",
        "shop_card_remove",
        "shop_reward_card",
        "shop_reward_potion",
        "shop_reward_relic",
        "shop_skip",
        "game_potion_discard",
        "game_potion_use",
        "reward_key",
    }
)
"""Categories that document T010's required low-probability legal branches."""

STRUCTURAL_CATEGORIES_BY_SCREEN: Mapping[str, frozenset[str]] = {
    "BOSS_RELIC_REWARDS": frozenset({"boss_relic_take", "boss_relic_skip"}),
    "TREASURE_ROOM": frozenset({"treasure_open", "treasure_leave"}),
    "REST_ROOM": frozenset({"rest_heal", "rest_upgrade", "rest_other"}),
    "SHOP_ROOM": frozenset(
        {
            "shop_card_remove",
            "shop_reward_card",
            "shop_reward_potion",
            "shop_reward_relic",
            "shop_skip",
        }
    ),
    "REWARDS": frozenset({"ordinary_relic_take", "ordinary_relic_skip", "reward_key"}),
}
"""Required categories whose availability depends on reaching a screen type."""


@dataclass(frozen=True)
class NonCombatDriverCalibrationReport:
    """Category coverage from one named contiguous simulator-seed range."""

    seed_start: int | None
    seed_end: int | None
    episode_count: int
    max_steps: int
    driver_provenance: Mapping[str, Any]
    battle_controller_provenance: Mapping[str, Any]
    effective_action_space_config: Mapping[str, Any]
    simulator_config: Mapping[str, Any]
    non_combat_decisions: int = 0
    reached_screen_counts: Counter[str] = field(default_factory=Counter)
    category_opportunity_counts: Counter[str] = field(default_factory=Counter)
    selected_category_counts: Counter[str] = field(default_factory=Counter)
    action_kind_counts: Counter[str] = field(default_factory=Counter)
    outcome_counts: Counter[str] = field(default_factory=Counter)
    categories_without_natural_opportunity: list[str] = field(default_factory=list)
    unavailable_structural_categories: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether the driver/provenance experiment ran without an error.

        Natural coverage gaps are expected for a weak battle baseline and are
        reported separately. They do not turn an honest calibration into a
        false failure.
        """

        return not self.problems


def run_non_combat_driver_calibration(
    adapter: SimulatorAdapter,
    battle_policy: DecisionPolicy,
    *,
    seeds: Iterable[int],
    driver_seed: int,
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
    simulator_config: Mapping[str, Any] | None = None,
) -> NonCombatDriverCalibrationReport:
    """Report natural coverage separately from conditional driver reachability.

    One driver object is intentionally reused across episodes: its documented
    ``reset_for_run`` lifecycle proves that each run's random stream is derived
    from the driver seed and its own simulator seed rather than accidental
    sweep order.
    """

    seed_values = list(seeds)
    if not seed_values:
        raise ValueError("non-combat driver calibration requires at least one seed")
    if max_steps < 0:
        raise ValueError("non-combat driver calibration max_steps must be non-negative")
    if seed_values != list(range(min(seed_values), max(seed_values) + 1)):
        raise ValueError("non-combat driver calibration seeds must be contiguous")

    driver = StochasticNonCombatDriver(seed=driver_seed)
    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    reached_screen_counts: Counter[str] = Counter()
    category_opportunity_counts: Counter[str] = Counter()
    selected_category_counts: Counter[str] = Counter()
    action_kind_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    problems: list[str] = []
    non_combat_decisions = 0

    def record_opportunities(
        snapshot: object,
        actions: object,
        context: DecisionContext,
        step_index: int,
    ) -> None:
        del actions, step_index
        raw = getattr(snapshot, "raw", {})
        if is_battle_state(raw, context.screen_state):
            return
        screen = context.screen_state.upper()
        reached_screen_counts[screen] += 1
        available_categories = {
            non_combat_action_category(context, index)
            for index in context.eligible_action_indices
        }
        for category in available_categories:
            category_opportunity_counts[category] += 1

    for seed in seed_values:
        rollout = collect_battle_agent_rollout(
            adapter,
            battle_policy,
            seed=seed,
            max_steps=max_steps,
            action_space=active_action_space,
            autopilot_policy=driver,
            before_decision=record_opportunities,
        )
        outcome_counts[rollout.outcome] += 1
        problems.extend(f"seed {seed}: {problem}" for problem in rollout.problems)

        for step in rollout.steps:
            if step.controller_role != NON_COMBAT_DRIVER_CONTROLLER_ROLE:
                continue
            non_combat_decisions += 1
            action_kind_counts[step.chosen_action_kind] += 1
            category = _category_from_selection_reason(step.selection_reason, driver)
            if category is None:
                problems.append(
                    f"seed {seed} step {step.step_index}: unexpected non-combat "
                    f"selection reason {step.selection_reason!r}"
                )
                continue
            selected_category_counts[category] += 1

    no_opportunity = sorted(
        REQUIRED_NON_COMBAT_DRIVER_V1_CATEGORIES.difference(category_opportunity_counts)
    )
    unavailable_structural_categories = sorted(
        category
        for screen, categories in STRUCTURAL_CATEGORIES_BY_SCREEN.items()
        if not reached_screen_counts[screen]
        for category in categories
    )
    effective_action_space_config = {
        "configured": active_action_space.to_dict(),
        "battle": action_space_for_screen(
            active_action_space,
            screen_state="BATTLE",
            battle_active=True,
        ).to_dict(),
        "non_combat": action_space_for_screen(
            active_action_space,
            screen_state="REWARDS",
            battle_active=False,
        ).to_dict(),
        "selection_rule": "action_space_for_screen(screen_state, battle_active)",
    }
    effective_simulator_config = dict(simulator_config or {})
    effective_simulator_config.setdefault("adapter_class", type(adapter).__name__)
    problems.extend(_simulator_config_problems(effective_simulator_config))
    return NonCombatDriverCalibrationReport(
        seed_start=min(seed_values),
        seed_end=max(seed_values),
        episode_count=len(seed_values),
        max_steps=max_steps,
        driver_provenance=PolicyController(driver).provenance.to_dict(),
        battle_controller_provenance=PolicyController(
            battle_policy
        ).provenance.to_dict(),
        effective_action_space_config=effective_action_space_config,
        simulator_config=effective_simulator_config,
        non_combat_decisions=non_combat_decisions,
        reached_screen_counts=reached_screen_counts,
        category_opportunity_counts=category_opportunity_counts,
        selected_category_counts=selected_category_counts,
        action_kind_counts=action_kind_counts,
        outcome_counts=outcome_counts,
        categories_without_natural_opportunity=no_opportunity,
        unavailable_structural_categories=unavailable_structural_categories,
        problems=problems,
    )


def format_non_combat_driver_calibration_report(
    report: NonCombatDriverCalibrationReport,
) -> str:
    """Format the T010 calibration report for stderr and pull-request evidence."""

    seed_range = "(none)"
    if report.seed_start is not None and report.seed_end is not None:
        seed_range = f"{report.seed_start}..{report.seed_end}"

    lines = [
        "Stochastic non-combat driver calibration summary",
        f"driver: {report.driver_provenance.get('name', 'stochastic_non_combat_v1')}",
        f"driver version: {report.driver_provenance.get('config', {}).get('version', 1)}",
        f"seed range: {seed_range}",
        f"episodes: {report.episode_count}",
        f"max steps per episode: {report.max_steps}",
        f"non-combat decisions: {report.non_combat_decisions}",
        f"driver/provenance validation passed: {_bool_label(report.passed)}",
        "driver provenance: " + _compact_json(report.driver_provenance),
        "battle controller provenance: "
        + _compact_json(report.battle_controller_provenance),
        "effective action-space configuration: "
        + _compact_json(report.effective_action_space_config),
        "simulator configuration: " + _compact_json(report.simulator_config),
    ]
    config = report.driver_provenance.get("config", {})
    if isinstance(config, Mapping):
        normalization_rule = config.get("normalization_rule")
        if normalization_rule is not None:
            lines.append(f"normalization rule: {normalization_rule}")
        _append_weight_table(
            lines,
            "screen category relative weights",
            config.get("screen_category_relative_weights"),
        )
        _append_weight_table(
            lines,
            "global category relative weights",
            {"all screens": config.get("global_category_relative_weights", {})},
        )
        _append_weight_table(
            lines,
            "conditional category relative weights",
            config.get("conditional_category_relative_weights"),
        )
    _append_counter(lines, "reached screens", report.reached_screen_counts)
    _append_counter(
        lines,
        "category opportunities",
        report.category_opportunity_counts,
    )
    _append_counter(lines, "selected categories", report.selected_category_counts)
    _append_counter(lines, "selected action kinds", report.action_kind_counts)
    _append_counter(lines, "outcomes", report.outcome_counts)
    _append_values(
        lines,
        "categories without natural opportunity",
        report.categories_without_natural_opportunity,
    )
    _append_values(
        lines,
        "unavailable structural categories",
        report.unavailable_structural_categories,
    )
    _append_values(lines, "problems", report.problems)
    return "\n".join(lines)


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _simulator_config_problems(config: Mapping[str, Any]) -> list[str]:
    """Require explicit simulator provenance even for direct library callers."""

    ascension = config.get("ascension")
    if isinstance(ascension, bool) or not isinstance(ascension, int):
        return [
            "simulator configuration is missing a concrete integer ascension; "
            "pass simulator_config={'ascension': ...}"
        ]
    return []


def _category_from_selection_reason(
    reason: str,
    driver: StochasticNonCombatDriver,
) -> str | None:
    prefix = f"{driver.name}:"
    if not reason.startswith(prefix):
        return None
    category = reason.removeprefix(prefix)
    return category or None


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return
    for key in sorted(counter):
        lines.append(f"  {key}: {counter[key]}")


def _append_weight_table(
    lines: list[str],
    title: str,
    raw_table: object,
) -> None:
    lines.append(f"{title}:")
    if not isinstance(raw_table, Mapping) or not raw_table:
        lines.append("  (none)")
        return
    for screen in sorted(raw_table):
        categories = raw_table[screen]
        if not isinstance(categories, Mapping):
            lines.append(f"  {screen}: {categories}")
            continue
        values = ", ".join(
            f"{category}={categories[category]}" for category in sorted(categories)
        )
        lines.append(f"  {screen}: {values}")


def _append_values(lines: list[str], title: str, values: Iterable[str]) -> None:
    lines.append(f"{title}:")
    found = False
    for value in values:
        lines.append(f"  {value}")
        found = True
    if not found:
        lines.append("  (none)")


def _bool_label(value: bool) -> str:
    return "yes" if value else "no"
