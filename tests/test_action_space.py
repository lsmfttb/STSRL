from __future__ import annotations

import pytest

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    choose_deterministic_action,
    filter_eligible_actions,
)
from sts_combat_rl.sim.contract import SimulatorAction


def _action(kind: str) -> SimulatorAction:
    return SimulatorAction(
        action_id=kind,
        label=kind,
        kind=kind,
        raw={"scope": "battle"},
    )


def test_initial_action_space_filters_potion_actions() -> None:
    actions = [_action("potion"), _action("card"), _action("reward_potion")]

    eligible = filter_eligible_actions(actions, ActionSpaceConfig.initial_no_potions())

    assert [action.kind for action in eligible] == ["card"]
    assert choose_deterministic_action(actions).kind == "card"


def test_include_all_action_space_keeps_potions_available() -> None:
    actions = [_action("potion"), _action("card")]

    eligible = filter_eligible_actions(actions, ActionSpaceConfig.include_all())

    assert [action.kind for action in eligible] == ["potion", "card"]


def test_action_space_can_reject_all_excluded_without_fallback() -> None:
    config = ActionSpaceConfig(
        excluded_kinds=frozenset({"potion"}),
        allow_excluded_fallback=False,
    )

    with pytest.raises(ValueError, match="excluded"):
        choose_deterministic_action([_action("potion")], config)
