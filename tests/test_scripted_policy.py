from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.comm.protocol import format_command
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.state.parser import parse_game_state


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open("r", encoding="utf-8") as file:
        raw = json.load(file)
    assert isinstance(raw, dict)
    return raw


def act_text(raw: dict[str, Any]) -> str:
    policy = ScriptedCombatPolicy()
    command = policy.act(parse_game_state(raw))
    return format_command(command)


def test_policy_plays_first_attack_into_first_alive_monster() -> None:
    assert act_text(load_fixture("combat_basic.json")) == "play 1 0"


def test_policy_ends_turn_outside_combat() -> None:
    assert act_text(load_fixture("non_combat.json")) == "end"


def test_policy_ends_turn_with_empty_hand() -> None:
    assert (
        act_text(
            {
                "screen_type": "COMBAT",
                "hand": [],
                "monsters": [{"name": "Cultist", "current_hp": 20}],
            }
        )
        == "end"
    )


def test_policy_plays_defend_when_no_attack_target_exists() -> None:
    assert (
        act_text(
            {
                "screen_type": "COMBAT",
                "hand": [
                    {
                        "name": "Defend",
                        "card_id": "Defend_R",
                        "type": "SKILL",
                        "playable": True,
                    }
                ],
                "monsters": [],
            }
        )
        == "play 1"
    )


def test_policy_ends_turn_with_no_monsters_and_no_defend() -> None:
    assert (
        act_text(
            {
                "screen_type": "COMBAT",
                "hand": [
                    {
                        "name": "Strike",
                        "card_id": "Strike_R",
                        "type": "ATTACK",
                        "playable": True,
                    }
                ],
                "monsters": [],
            }
        )
        == "end"
    )


def test_policy_ends_turn_for_missing_fields_fixture() -> None:
    assert act_text(load_fixture("combat_missing_fields.json")) == "end"


def test_policy_ends_turn_for_unknown_playable_card() -> None:
    assert (
        act_text(
            {
                "screen_type": "COMBAT",
                "hand": [{"name": "Mystery Card", "playable": True}],
                "monsters": [{"name": "Cultist", "current_hp": 10}],
            }
        )
        == "end"
    )


def test_policy_omits_target_for_explicit_no_target_attack() -> None:
    assert (
        act_text(
            {
                "screen_type": "COMBAT",
                "hand": [
                    {
                        "name": "Cleave",
                        "card_id": "Cleave",
                        "type": "ATTACK",
                        "playable": True,
                        "has_target": False,
                    }
                ],
                "monsters": [{"name": "Cultist", "current_hp": 10}],
            }
        )
        == "play 1"
    )
