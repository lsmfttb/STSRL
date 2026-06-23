from sts_combat_rl.commands.resource_outcome import (
    build_battle_resource_outcome_audit_report,
)
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
)
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


def test_structured_battle_outcome_reads_t018_native_identity_fields() -> None:
    start = {
        "battle_active": True,
        "cur_hp": 70,
        "max_hp": 80,
        "gold": 99,
        "battle_potion_capacity": 2,
        "battle_potions": [
            {
                "potion_index": 0,
                "id": 1,
                "id_label": "EMPTY_POTION_ID",
                "name": "EMPTY_POTION_SLOT",
            },
            {
                "potion_index": 1,
                "id": 42,
                "id_label": "WEAK_POTION",
                "name": "Weak Potion",
            },
        ],
        "deck": [
            _card("AscendersBane", "CURSE"),
            _card("Strike_R", "ATTACK"),
        ],
        "battle_relics": [
            {
                "relic_index": 0,
                "id": 86,
                "id_label": "Burning Blood",
                "name": "Burning Blood",
                "counter": 0,
            }
        ],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
    terminal = {
        **start,
        "battle_active": False,
        "outcome": "PLAYER_VICTORY",
        "completed_battle_outcome": "PLAYER_VICTORY",
        "cur_hp": 66,
        "potions": [
            {
                "potion_index": 0,
                "id": 1,
                "id_label": "EMPTY_POTION_ID",
                "name": "EMPTY_POTION_SLOT",
            },
            {
                "potion_index": 1,
                "id": 1,
                "id_label": "EMPTY_POTION_ID",
                "name": "EMPTY_POTION_SLOT",
            },
        ],
        "relics": start["battle_relics"],
    }

    outcome = build_battle_resource_outcome(start, terminal)

    assert outcome.start.potion_slots.source == "battle_potions"
    assert outcome.start.potion_slots.value[0]["is_empty"] is True
    assert outcome.start.relics.source == "battle_relics"
    assert outcome.start.curses.value[0]["id"] == "AscendersBane"
    assert outcome.terminal.keys.value == {
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
    assert outcome.deltas["potion_slots_delta"]["removed"][0]["name"] == "Weak Potion"


def test_require_available_demands_authoritative_terminal_result() -> None:
    missing_outcome = build_battle_resource_outcome(
        {"battle_active": True, "cur_hp": 5, "max_hp": 80},
        {"battle_active": False, "cur_hp": 0, "max_hp": 80},
    )
    status, payload = available_battle_resource_outcome(missing_outcome)

    assert battle_resource_outcome_problems(
        status,
        payload,
        label="missing",
        require_available=True,
    ) == ["missing: terminal battle result is unavailable"]

    nonterminal_outcome = build_battle_resource_outcome(
        {"battle_active": True, "cur_hp": 5, "max_hp": 80},
        {"battle_active": False, "cur_hp": 0, "max_hp": 80},
        battle_result="UNDECIDED",
    )
    status, payload = available_battle_resource_outcome(nonterminal_outcome)

    assert battle_resource_outcome_problems(
        status,
        payload,
        label="nonterminal",
        require_available=True,
    ) == ["nonterminal: terminal battle result is not authoritative"]


def test_resource_outcome_audit_fails_missing_t018_identity_components() -> None:
    outcome = build_battle_resource_outcome(
        {"battle_active": True, "cur_hp": 5, "max_hp": 80},
        {
            "battle_active": False,
            "cur_hp": 0,
            "max_hp": 80,
            "completed_battle_outcome": "PLAYER_LOSS",
        },
        battle_result="PLAYER_LOSS",
    )
    status, payload = available_battle_resource_outcome(outcome)
    pool = _pool_with_completed_outcome(status, payload)

    report = build_battle_resource_outcome_audit_report(
        pool,
        requested_seeds=(1,),
        max_steps=10,
    )

    assert report.passed is False
    assert report.identity_component_missing_counts["deck"] == 1
    assert any(
        "T018 identity-bearing component deck" in problem
        for problem in report.identity_component_problems
    )


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


def _pool_with_completed_outcome(
    status: str,
    payload: dict[str, object],
) -> NaturalBattleStartPool:
    record = BattleStartCheckpointRecord(
        record_index=0,
        source_checkpoint_id="checkpoint-0",
        source_run_id="run-0",
        source_seed=1,
        source_battle_index=0,
        structural_metadata={
            "ascension": 20,
            "act": 1,
            "room_type": "MONSTER",
            "encounter_id": "FakeEncounter",
        },
        source_controller_provenance={"name": "test"},
        source_battle_controller_provenance={"name": "battle"},
        source_non_combat_controller_provenance={"name": "non_combat"},
        action_trace=(),
        snapshot_observation=(),
        snapshot_raw={},
        battle_outcome="PLAYER_LOSS",
        battle_completed=True,
        completed_battle_resource_outcome_status=status,
        completed_battle_resource_outcome=payload,
    )
    return NaturalBattleStartPool(
        source_run_count=1,
        terminal_run_count=0,
        truncated_run_count=0,
        source_controller_provenance={"name": "test"},
        records=[record],
    )
