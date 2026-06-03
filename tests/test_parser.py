from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.state.parser import parse_game_state


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open("r", encoding="utf-8") as file:
        raw = json.load(file)
    assert isinstance(raw, dict)
    return raw


def test_parse_basic_combat_state() -> None:
    state = parse_game_state(load_fixture("combat_basic.json"))

    assert state.in_combat is True
    assert state.screen_type == "COMBAT"
    assert state.turn == 1
    assert state.player is not None
    assert state.player.current_hp == 70
    assert state.player.energy == 3
    assert len(state.hand) == 2
    assert state.hand[0].name == "Strike"
    assert state.hand[0].card_id == "Strike_R"
    assert state.hand[0].type == "ATTACK"
    assert state.hand[0].playable is True
    assert len(state.monsters) == 1
    assert state.monsters[0].name == "Jaw Worm"
    assert state.monsters[0].alive is True
    assert state.raw["extra_field"] == "preserved in raw"


def test_parse_non_combat_state() -> None:
    state = parse_game_state(load_fixture("non_combat.json"))

    assert state.in_combat is False
    assert state.screen_type == "EVENT"
    assert state.turn is None
    assert state.hand == []
    assert state.monsters == []


def test_parse_missing_fields_uses_safe_defaults() -> None:
    state = parse_game_state(load_fixture("combat_missing_fields.json"))

    assert state.in_combat is True
    assert state.player is None
    assert state.turn is None
    assert state.hand[0].name == "Unknown Card"
    assert state.hand[0].card_id is None
    assert state.hand[0].cost is None
    assert state.hand[0].type is None
    assert state.hand[0].upgraded is False
    assert state.hand[0].playable is False
    assert state.hand[0].has_target is None
    assert state.monsters[0].name == "Unknown Monster"
    assert state.monsters[0].current_hp is None
    assert state.monsters[0].block == 0
    assert state.monsters[0].alive is True
    assert state.raw["unexpected_nested"]["kept"] is True


def test_parse_empty_hand_and_no_monsters() -> None:
    state = parse_game_state(
        {
            "screen_type": "COMBAT",
            "player": {"currentHp": "12", "maxHp": "80", "block": "3"},
            "hand": [],
            "monsters": [],
        }
    )

    assert state.in_combat is True
    assert state.player is not None
    assert state.player.current_hp == 12
    assert state.player.max_hp == 80
    assert state.player.block == 3
    assert state.hand == []
    assert state.monsters == []


def test_parse_unknown_card_does_not_crash() -> None:
    state = parse_game_state(
        {
            "screenType": "COMBAT",
            "handCards": [{"name": "A Card From A Mod", "canPlay": True}],
            "monsterList": [{"name": "Cultist", "hp": 10}],
        }
    )

    assert state.in_combat is True
    assert state.hand[0].name == "A Card From A Mod"
    assert state.hand[0].playable is True
    assert state.monsters[0].current_hp == 10
    assert state.monsters[0].alive is True


def test_parse_zero_energy_is_preserved() -> None:
    state = parse_game_state(
        {
            "screen_type": "COMBAT",
            "player": {"current_hp": 12, "max_hp": 80, "energy": 0},
            "hand": [],
            "monsters": [],
        }
    )

    assert state.player is not None
    assert state.player.energy == 0


def test_parse_nested_communication_mod_combat_state() -> None:
    state = parse_game_state(
        {
            "available_commands": ["play", "end", "key", "click", "wait", "state"],
            "ready_for_command": True,
            "in_game": True,
            "game_state": {
                "screen_type": "NONE",
                "action_phase": "WAITING_ON_USER",
                "room_phase": "COMBAT",
                "combat_state": {
                    "turn": 1,
                    "player": {
                        "current_hp": 68,
                        "max_hp": 75,
                        "block": 0,
                        "energy": 3,
                    },
                    "hand": [
                        {
                            "name": "打击",
                            "id": "Strike_R",
                            "type": "ATTACK",
                            "cost": 1,
                            "is_playable": True,
                            "has_target": True,
                            "upgrades": 0,
                            "uuid": "card-uuid",
                        }
                    ],
                    "monsters": [
                        {
                            "name": "酸液史莱姆（中）",
                            "id": "AcidSlime_M",
                            "current_hp": 32,
                            "max_hp": 32,
                            "block": 0,
                            "intent": "ATTACK",
                            "is_gone": False,
                        }
                    ],
                },
            },
        }
    )

    assert state.available_commands == ["play", "end", "key", "click", "wait", "state"]
    assert state.in_combat is True
    assert state.screen_type == "NONE"
    assert state.action_phase == "WAITING_ON_USER"
    assert state.turn == 1
    assert state.player is not None
    assert state.player.energy == 3
    assert state.hand[0].name == "打击"
    assert state.hand[0].card_id == "Strike_R"
    assert state.hand[0].playable is True
    assert state.hand[0].has_target is True
    assert state.hand[0].upgraded is False
    assert state.monsters[0].name == "酸液史莱姆（中）"
    assert state.monsters[0].monster_id == "AcidSlime_M"
    assert state.monsters[0].alive is True
