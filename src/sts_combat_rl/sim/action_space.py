"""Configurable simulator action-space filtering.

The first training pass can exclude potion-related actions without removing
them from parsing, feature encoding, or calibration reports. Later phases can
switch to `ActionSpaceConfig.include_all()` and reuse the same adapter surface.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from sts_combat_rl.sim.contract import SimulatorAction


POTION_ACTION_KINDS = frozenset(
    {
        "potion",
        "potion_discard",
        "reward_potion",
        "shop_reward_potion",
        "game_potion_use",
        "game_potion_discard",
    }
)
DEFAULT_PREFERRED_ACTION_KINDS = ("card", "end_turn")


@dataclass(frozen=True)
class ActionSpaceConfig:
    """Filtering and deterministic fallback rules for simulator actions."""

    excluded_kinds: frozenset[str] = POTION_ACTION_KINDS
    preferred_kinds: tuple[str, ...] = DEFAULT_PREFERRED_ACTION_KINDS
    allow_excluded_fallback: bool = True
    include_non_combat_potions: bool = True

    @classmethod
    def initial_no_potions(cls) -> "ActionSpaceConfig":
        """Default first-pass action space: ignore potion-related actions."""

        return cls(excluded_kinds=POTION_ACTION_KINDS)

    @classmethod
    def include_all(cls) -> "ActionSpaceConfig":
        """Future-compatible action space with no kind-level filtering."""

        return cls(excluded_kinds=frozenset())

    def to_dict(self) -> dict[str, object]:
        """Serialize the action-space config for provenance and artifact storage."""

        return {
            "excluded_kinds": sorted(self.excluded_kinds),
            "preferred_kinds": list(self.preferred_kinds),
            "allow_excluded_fallback": self.allow_excluded_fallback,
            "include_non_combat_potions": self.include_non_combat_potions,
        }


def action_is_eligible(
    action: SimulatorAction,
    config: ActionSpaceConfig | None = None,
) -> bool:
    active_config = config or ActionSpaceConfig.initial_no_potions()
    return action.kind not in active_config.excluded_kinds


def filter_eligible_actions(
    actions: Sequence[SimulatorAction],
    config: ActionSpaceConfig | None = None,
) -> list[SimulatorAction]:
    active_config = config or ActionSpaceConfig.initial_no_potions()
    return [action for action in actions if action_is_eligible(action, active_config)]


def choose_deterministic_action(
    actions: Sequence[SimulatorAction],
    config: ActionSpaceConfig | None = None,
) -> SimulatorAction:
    """Choose a deterministic action under an action-space config."""

    if not actions:
        raise ValueError("cannot choose from an empty action list")

    active_config = config or ActionSpaceConfig.initial_no_potions()
    eligible = filter_eligible_actions(actions, active_config)
    for preferred_kind in active_config.preferred_kinds:
        for action in eligible:
            if action.kind == preferred_kind:
                return action

    if eligible:
        return eligible[0]

    if active_config.allow_excluded_fallback:
        return actions[0]

    raise ValueError("all legal actions are excluded by the action-space config")


def eligible_indices(
    actions: Sequence[SimulatorAction],
    config: ActionSpaceConfig | None = None,
) -> list[int]:
    """Return the positional indices of actions passing the action-space filter.

    This is the single canonical implementation that was previously duplicated
    in both ``rollout.py`` and ``battle_agent.py``. It uses ``id()`` matching
    against ``filter_eligible_actions`` to preserve object identity across the
    original action list.
    """

    active_config = config or ActionSpaceConfig.initial_no_potions()
    eligible_action_ids = {
        id(a) for a in filter_eligible_actions(actions, active_config)
    }
    return [
        index
        for index, action in enumerate(actions)
        if id(action) in eligible_action_ids
    ]


def action_space_for_screen(
    config: ActionSpaceConfig,
    *,
    screen_state: str,
    battle_active: bool,
) -> ActionSpaceConfig:
    """Return the effective filter for one decision state.

    The initial action-space pass suppresses potion actions for *battle* policy
    experiments only.  Natural non-combat drivers must keep their legal potion
    rewards, purchases, discards, and uses so those branches remain reachable.
    """

    if (
        config.include_non_combat_potions
        and not battle_active
        and screen_state != "BATTLE"
    ):
        return replace(
            config,
            excluded_kinds=frozenset(config.excluded_kinds - POTION_ACTION_KINDS),
        )
    return config


ActionChooser = Callable[[list[SimulatorAction], ActionSpaceConfig], SimulatorAction]
"""Legacy chooser callback: pick one action object given the candidates and config."""
