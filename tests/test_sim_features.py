from __future__ import annotations

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    build_public_tactical_actions,
    build_public_tactical_state,
    communicationmod_battle_feature_size,
    encode_communicationmod_battle_snapshot,
    encode_lightspeed_battle_snapshot,
    encode_simulator_action,
    encode_simulator_actions,
    lightspeed_battle_feature_size,
    normalize_communicationmod_battle_snapshot,
    simulator_action_feature_size,
    tactical_action_problems,
    tactical_state_problems,
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


def test_public_tactical_state_distinguishes_identity_intent_and_visible_resources() -> (
    None
):
    raw = {
        "battle_active": True,
        "ascension": 20,
        "battle_turn": 2,
        "battle_player": {
            "current_hp": 64,
            "max_hp": 80,
            "energy": 2,
            "block": 7,
            "powers": [{"id": "Strength", "amount": 3}],
        },
        "battle_hand": [
            {
                "id": "Strike_R",
                "type": "ATTACK",
                "upgraded": True,
                "upgrade_count": 1,
                "cost": 1,
            }
        ],
        "battle_discard_pile": [{"id": "Defend_R", "type": "SKILL"}],
        "battle_monsters": [
            {
                "id": "Cultist",
                "intent": "ATTACK",
                "move_id": 2,
                "last_move_id": 1,
                "current_hp": 48,
                "powers": [{"id": "Ritual", "amount": 3}],
            }
        ],
        "battle_potions": [{"id": "Fire Potion"}],
        "relics": [{"id": "Burning Blood", "counter": 0}],
    }
    changed = {
        **raw,
        "battle_hand": [{**raw["battle_hand"][0], "id": "Bash"}],
        "battle_monsters": [{**raw["battle_monsters"][0], "intent": "BUFF"}],
    }

    state = build_public_tactical_state(raw)

    assert state["schema_id"] == TACTICAL_FEATURE_SCHEMA_ID
    assert state["schema_version"] == TACTICAL_FEATURE_SCHEMA_VERSION
    assert state["scalars"]["ascension"] == 20.0
    assert state["cards"][0]["pile"] == "hand"
    assert state["cards"][1]["pile"] == "discard"
    assert state["cards"][0]["flags"]["upgraded"] is True
    assert state["monsters"][0]["state_machine"]["move_id"] == 2.0
    assert state["player"]["powers"][0]["identity"]["value"] == "Strength"
    assert state["potions"][0]["identity"]["value"] == "Fire Potion"
    assert state["relics"][0]["identity"]["value"] == "Burning Blood"
    assert encode_lightspeed_battle_snapshot(raw) != encode_lightspeed_battle_snapshot(
        changed
    )
    assert tactical_state_problems(state) == []


def test_discard_and_exhaust_members_are_not_collapsed_to_counts_or_empty() -> None:
    first = {
        "battle_discard_pile_size": 1,
        "battle_exhaust_pile_size": 1,
        "battle_discard_pile": [{"id": "Defend_R", "type": "SKILL"}],
        "battle_exhaust_pile": [{"id": "Bash", "type": "ATTACK"}],
    }
    second = {
        **first,
        "battle_discard_pile": [{"id": "Bash", "type": "ATTACK"}],
        "battle_exhaust_pile": [{"id": "Defend_R", "type": "SKILL"}],
    }

    first_state = build_public_tactical_state(first)
    second_state = build_public_tactical_state(second)
    unavailable = build_public_tactical_state(
        {
            "battle_discard_pile_size": 1,
            "battle_exhaust_pile_size": 1,
        }
    )

    assert first_state["cards"] != second_state["cards"]
    assert encode_lightspeed_battle_snapshot(
        first
    ) != encode_lightspeed_battle_snapshot(second)
    assert unavailable["cards"] == []
    assert unavailable["availability"]["discard_cards"] is False
    assert unavailable["availability"]["exhaust_cards"] is False
    assert "availability.discard_cards" in unavailable["missing_fields"]
    assert "availability.exhaust_cards" in unavailable["missing_fields"]


def test_relic_identity_and_counter_are_distinguishable_inputs() -> None:
    first = {"battle_relics": [{"id": "Burning Blood", "counter": 0}]}
    changed_identity = {"battle_relics": [{"id": "Vajra", "counter": 0}]}
    changed_counter = {"battle_relics": [{"id": "Burning Blood", "counter": 2}]}
    unavailable = build_public_tactical_state({})

    first_state = build_public_tactical_state(first)

    assert first_state["relics"][0]["identity"]["value"] == "Burning Blood"
    assert first_state["relics"][0]["counter"] == 0.0
    assert first_state["availability"]["relics"] is True
    assert encode_lightspeed_battle_snapshot(
        first
    ) != encode_lightspeed_battle_snapshot(changed_identity)
    assert encode_lightspeed_battle_snapshot(
        first
    ) != encode_lightspeed_battle_snapshot(changed_counter)
    assert unavailable["availability"]["relics"] is False
    assert "availability.relics" in unavailable["missing_fields"]


def test_simulator_and_communicationmod_share_intent_category_not_exact_move() -> None:
    simulator_raw = {
        "battle_monsters": [
            {
                "id": "Cultist",
                "intent_category": "ATTACK",
                "current_move": "CULTIST_DARK_STRIKE",
            }
        ]
    }
    live_raw = {
        "game_state": {
            "combat_state": {
                "monsters": [{"id": "Cultist", "intent": "ATTACK_DEBUFF"}],
            }
        }
    }

    normalized_live = normalize_communicationmod_battle_snapshot(live_raw)
    simulator_state = build_public_tactical_state(simulator_raw)
    live_state = build_public_tactical_state(normalized_live)
    simulator_monster = simulator_state["monsters"][0]
    live_monster = live_state["monsters"][0]

    assert normalized_live["battle_monsters"][0]["intent_category"] == "ATTACK"
    assert simulator_monster["intent_category"] == live_monster["intent_category"]
    assert simulator_monster["state_machine"]["current_move"] == "CULTIST_DARK_STRIKE"
    assert live_monster["state_machine"]["current_move"] is None
    assert (
        "monsters.state_machine.current_move" not in simulator_state["missing_fields"]
    )
    assert "monsters.state_machine.current_move" in live_state["missing_fields"]


def test_public_tactical_actions_keep_duplicate_ids_and_targets_distinct() -> None:
    raw = {
        "battle_hand": [{"id": "Strike_R", "type": "ATTACK", "requires_target": True}],
        "battle_monsters": [
            {"id": "Cultist", "intent": "ATTACK"},
            {"id": "JawWorm", "intent": "BUFF"},
        ],
    }
    actions = [
        SimulatorAction(
            action_id="card:Strike_R",
            label="Strike Cultist",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="card:Strike_R",
            label="Strike Jaw Worm",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 1, "idx3": 0},
        ),
    ]

    structured = build_public_tactical_actions(actions, raw)
    encoded = encode_simulator_actions(actions, raw)

    assert (
        structured[0]["identity"]["stable_id"] != structured[1]["identity"]["stable_id"]
    )
    assert structured[0]["parameters"]["target_index"] == 0
    assert structured[1]["parameters"]["target_index"] == 1
    assert structured[0]["selected_target"]["identity"]["value"] == "Cultist"
    assert structured[1]["selected_target"]["identity"]["value"] == "JawWorm"
    assert encoded[0] != encoded[1]


def test_public_tactical_actions_exclude_simulator_native_action_identity() -> None:
    raw = {
        "battle_hand": [{"id": "Strike_R", "type": "ATTACK"}],
        "battle_monsters": [{"id": "Cultist", "intent": "ATTACK"}],
    }
    first = SimulatorAction(
        action_id="battle:123",
        label="Strike",
        kind="card",
        raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0, "bits": 123},
    )
    second = SimulatorAction(
        action_id="battle:456",
        label="Strike",
        kind="card",
        raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0, "bits": 456},
    )

    first_structured = build_public_tactical_actions([first], raw)
    second_structured = build_public_tactical_actions([second], raw)

    assert first_structured == second_structured
    assert "action_id" not in first_structured[0]["identity"]
    assert encode_simulator_action(first, raw) == encode_simulator_action(second, raw)
    unsafe = {**first_structured[0], "identity": dict(first_structured[0]["identity"])}
    unsafe["identity"]["action_id"] = "battle:123"
    assert any(
        "simulator-native replay action_id" in problem
        for problem in tactical_action_problems([unsafe])
    )


def test_hidden_draw_order_and_rng_do_not_reach_public_tactical_contract() -> None:
    visible = {
        "battle_active": True,
        "ascension": 20,
        "battle_player": {
            "current_hp": 80,
            "max_hp": 80,
            "energy": 3,
            "block": 0,
        },
        "battle_hand": [{"id": "Strike_R", "type": "ATTACK"}],
        "battle_draw_pile_size": 4,
    }
    hidden_changed = {
        **visible,
        "battle_draw_pile": ["Bash", "Strike_R", "Defend_R"],
        "rng_state": "different",
        "future_monster_move": "ATTACK_DEBUFF",
        "hidden_act_3_boss": "Awakened One",
    }

    assert build_public_tactical_state(visible) == build_public_tactical_state(
        hidden_changed
    )
    assert encode_lightspeed_battle_snapshot(
        visible
    ) == encode_lightspeed_battle_snapshot(hidden_changed)


def test_unknown_visible_identity_is_explicitly_preserved_and_counted() -> None:
    state = build_public_tactical_state(
        {
            "battle_hand": [{"id": "FutureCard", "type": "SKILL"}],
            "battle_monsters": [{"id": "FutureMonster", "intent": "MAGIC"}],
        }
    )

    assert state["cards"][0]["identity"] == {
        "value": "FutureCard",
        "status": "unknown",
        "vocabulary_version": "public-identity-v1",
    }
    assert state["unknown_identity_counts"]["card"] == 1
    assert state["unknown_identity_counts"]["monster"] == 1
