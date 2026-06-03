from __future__ import annotations

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.features import (
    communicationmod_battle_feature_size,
    encode_communicationmod_battle_snapshot,
    encode_lightspeed_battle_snapshot,
    encode_simulator_action,
    encode_simulator_actions,
    lightspeed_battle_feature_size,
    simulator_action_feature_size,
)


def test_lightspeed_battle_snapshot_encoder_has_stable_size() -> None:
    raw = {
        "battle_active": True,
        "act": 1,
        "floor_num": 1,
        "cur_hp": 80,
        "max_hp": 80,
        "gold": 99,
        "battle_player": {
            "current_hp": 80,
            "max_hp": 80,
            "energy": 3,
            "energy_per_turn": 3,
            "block": 0,
            "strength": 0,
            "dexterity": 0,
            "artifact": 0,
            "focus": 0,
            "vulnerable": 0,
            "weak": 0,
            "frail": 0,
            "cards_played_this_turn": 0,
            "attacks_played_this_turn": 0,
            "skills_played_this_turn": 0,
            "cards_discarded_this_turn": 0,
            "times_damaged_this_combat": 0,
        },
        "battle_turn": 0,
        "battle_hand_size": 1,
        "battle_draw_pile_size": 6,
        "battle_discard_pile_size": 0,
        "battle_exhaust_pile_size": 0,
        "battle_monster_count": 1,
        "battle_monsters_alive": 1,
        "battle_potion_count": 0,
        "battle_potion_capacity": 3,
        "battle_hand": [
            {
                "type": "ATTACK",
                "cost": 1,
                "cost_for_turn": 1,
                "playable": True,
                "requires_target": True,
                "upgraded": False,
                "upgrade_count": 0,
                "exhausts": False,
                "ethereal": False,
            }
        ],
        "battle_monsters": [
            {
                "current_hp": 51,
                "max_hp": 51,
                "block": 0,
                "alive": True,
                "targetable": True,
                "attacking": False,
                "move_base_damage": 0,
                "move_hits": 0,
                "strength": 0,
                "vulnerable": 0,
                "weak": 0,
                "artifact": 0,
                "poison": 0,
                "metallicize": 0,
                "plated_armor": 0,
                "regen": 0,
                "half_dead": False,
            }
        ],
        "battle_potions": [
            {"id": 1},
            {"id": 1},
            {"id": 1},
        ],
    }

    features = encode_lightspeed_battle_snapshot(raw)
    empty_features = encode_lightspeed_battle_snapshot({})

    assert len(features) == lightspeed_battle_feature_size()
    assert len(empty_features) == len(features)
    assert features[0] == 1.0
    assert empty_features[0] == 0.0
    assert max(features) > 1.0


def test_communicationmod_battle_snapshot_encoder_matches_feature_size() -> None:
    raw = {
        "game_state": {
            "act": 1,
            "floor": 1,
            "current_hp": 80,
            "max_hp": 80,
            "gold": 99,
            "combat_state": {
                "draw_pile": [],
                "discard_pile": [],
                "exhaust_pile": [],
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
                "turn": 1,
                "player": {
                    "current_hp": 80,
                    "max_hp": 80,
                    "energy": 3,
                    "block": 0,
                },
                "hand": [
                    {
                        "id": "Strike_R",
                        "name": "Strike",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                        "upgrades": 0,
                        "exhausts": False,
                        "ethereal": False,
                    }
                ],
                "monsters": [
                    {
                        "id": "Cultist",
                        "name": "Cultist",
                        "current_hp": 48,
                        "max_hp": 48,
                        "block": 0,
                        "intent": "ATTACK",
                        "move_base_damage": 6,
                        "move_hits": 1,
                        "powers": [],
                    }
                ],
            },
            "potions": [{"id": "Potion Slot"}],
        }
    }

    features = encode_communicationmod_battle_snapshot(raw)

    assert len(features) == communicationmod_battle_feature_size()
    assert len(features) == len(encode_lightspeed_battle_snapshot({}))
    assert features[0] == 1.0
    assert max(features) > 1.0


def test_simulator_action_encoder_has_stable_size() -> None:
    card_action = SimulatorAction(
        action_id="battle:123",
        label="card",
        kind="card",
        raw={"scope": "battle", "idx1": 2, "idx2": 1, "idx3": 0},
    )
    end_action = SimulatorAction(
        action_id="battle:456",
        label="end",
        kind="end_turn",
        raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
    )

    encoded = encode_simulator_action(card_action)
    encoded_actions = encode_simulator_actions([card_action, end_action])

    assert len(encoded) == simulator_action_feature_size()
    assert encoded[-3:] == [2.0, 1.0, 0.0]
    assert len(encoded_actions) == 2
    assert len(encoded_actions[0]) == len(encoded_actions[1])
