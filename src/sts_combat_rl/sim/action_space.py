"""Configurable simulator action-space filtering.

The first training pass can exclude potion-related actions without removing
them from parsing, feature encoding, or calibration reports. Later phases can
switch to `ActionSpaceConfig.include_all()` and reuse the same adapter surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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

    @classmethod
    def initial_no_potions(cls) -> "ActionSpaceConfig":
        """Default first-pass action space: ignore potion-related actions."""

        return cls(excluded_kinds=POTION_ACTION_KINDS)

    @classmethod
    def include_all(cls) -> "ActionSpaceConfig":
        """Future-compatible action space with no kind-level filtering."""

        return cls(excluded_kinds=frozenset())


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
    return [
        action
        for action in actions
        if action_is_eligible(action, active_config)
    ]


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
