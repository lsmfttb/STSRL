from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
    BATTLE_RESOURCE_OUTCOME_AVAILABLE,
    available_battle_resource_outcome,
    battle_resource_outcome_from_dict,
    battle_resource_outcome_problems,
    build_battle_resource_outcome,
    build_battle_resource_outcome_component_report,
)


def test_structured_battle_outcome_preserves_terminal_resources_and_deltas() -> None:
    start = _raw(
        current_hp=50,
        max_hp=80,
        gold=100,
        potion_names=["Strength Potion", "Dexterity Potion"],
        deck=[_card("Strike_R", "ATTACK")],
        relic_counter=5,
    )
    terminal = _raw(
        current_hp=45,
        max_hp=83,
        gold=125,
        potion_names=["Dexterity Potion", "Potion Slot"],
        deck=[_card("Strike_R", "ATTACK"), _card("Parasite", "CURSE")],
        relic_counter=6,
        outcome="PLAYER_VICTORY",
    )

    outcome = build_battle_resource_outcome(start, terminal)
    status, payload = available_battle_resource_outcome(outcome)
    loaded = battle_resource_outcome_from_dict(payload)

    assert status == BATTLE_RESOURCE_OUTCOME_AVAILABLE
    assert payload["schema_id"] == BATTLE_RESOURCE_OUTCOME_SCHEMA_ID
    assert loaded.battle_result.value == "PLAYER_VICTORY"
    assert loaded.battle_survived.value is True
    assert loaded.terminal_absolute_current_hp.value == 45
    assert loaded.terminal_max_hp.value == 83
    assert loaded.deltas["current_hp_delta"]["value"] == -5
    assert loaded.deltas["max_hp_delta"]["value"] == 3
    assert loaded.deltas["gold_delta"]["value"] == 25
    assert loaded.deltas["potion_slots_delta"]["removed"][0]["name"] == (
        "Strength Potion"
    )
    assert loaded.deltas["curse_delta"]["added"][0]["id"] == "Parasite"
    assert loaded.deltas["relic_counter_delta"]["changes"][0]["before"] == 5
    assert not battle_resource_outcome_problems(status, payload, label="row")


def test_structured_battle_outcome_keeps_missing_fields_explicit() -> None:
    outcome = build_battle_resource_outcome(
        {"battle_active": True, "cur_hp": 10},
        {
            "battle_active": False,
            "outcome": "PLAYER_LOSS",
            "completed_battle_outcome": "PLAYER_LOSS",
            "cur_hp": 0,
        },
    )
    status, payload = available_battle_resource_outcome(outcome)
    report = build_battle_resource_outcome_component_report([(status, payload)])

    assert outcome.battle_result.value == "PLAYER_LOSS"
    assert outcome.terminal_absolute_current_hp.value == 0
    assert outcome.terminal.max_hp.status == "missing"
    assert "terminal max_hp: missing any of max_hp, maxHp" in outcome.problems
    assert report.outcome_status_counts["available"] == 1
    assert report.component_presence_counts["max_hp"]["missing"] == 1
    assert report.problem_counts["terminal max_hp: missing any of max_hp, maxHp"] == 1


def _raw(
    *,
    current_hp: int,
    max_hp: int,
    gold: int,
    potion_names: list[str],
    deck: list[dict[str, object]],
    relic_counter: int,
    outcome: str = "UNDECIDED",
) -> dict[str, object]:
    return {
        "battle_active": outcome == "UNDECIDED",
        "outcome": outcome,
        "completed_battle_outcome": outcome,
        "cur_hp": current_hp,
        "max_hp": max_hp,
        "gold": gold,
        "potion_capacity": 2,
        "potions": [
            {"id": name, "name": name, "slot_index": index}
            for index, name in enumerate(potion_names)
        ],
        "deck": deck,
        "relics": [
            {
                "id": "Incense Burner",
                "name": "Incense Burner",
                "counter": relic_counter,
            }
        ],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }


def _card(card_id: str, card_type: str) -> dict[str, object]:
    return {"id": card_id, "name": card_id, "type": card_type}
