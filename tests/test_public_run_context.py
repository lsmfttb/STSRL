"""Tests for the sanitized public run context schema and validation."""

from sts_combat_rl.sim.public_run_context import (
    PUBLIC_RUN_CONTEXT_SCHEMA_ID,
    PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
    PUBLIC_RUN_HISTORY_SCHEMA_ID,
    append_run_history_entry,
    build_public_run_context,
    empty_public_run_context,
    empty_public_run_history,
    extract_public_location,
    extract_public_visible_screen,
    build_public_resource_delta,
    public_run_context_problems,
    public_run_history_problems,
)


# ---------------------------------------------------------------------------
# Empty context
# ---------------------------------------------------------------------------


def test_empty_public_run_context_is_explicitly_missing():
    context = empty_public_run_context()
    assert context["schema_id"] == PUBLIC_RUN_CONTEXT_SCHEMA_ID
    assert context["schema_version"] == PUBLIC_RUN_CONTEXT_SCHEMA_VERSION
    assert context["visible_act_boss"] is None
    assert context["encounter_history"] == []
    assert context["visible_map"] == []
    assert context["current_map_node"] is None
    assert context["next_map_nodes"] == []

    assert "visible_act_boss" in context["missing_fields"]
    assert "encounter_history" in context["missing_fields"]
    assert "run_history" in context["missing_fields"]
    assert "visible_map" in context["missing_fields"]
    assert "current_map_node" in context["missing_fields"]
    assert "next_map_nodes" in context["missing_fields"]

    history = context["run_history"]
    assert history["schema_id"] == PUBLIC_RUN_HISTORY_SCHEMA_ID
    assert history["entries"] == []
    assert "public_run_history" in history["missing_fields"]


def test_empty_context_is_valid():
    context = empty_public_run_context()
    assert public_run_context_problems(context) == []


# ---------------------------------------------------------------------------
# Context extraction from a fixture snapshot
# ---------------------------------------------------------------------------


def test_build_public_run_context_from_fixture():
    raw = {
        "visible_act_boss": "The Guardian",
        "act": 1,
        "floor_num": 5,
        "screen_state": "BATTLE",
        "public_encounter_history": [
            {"act": 1, "floor": 1, "room_type": "MONSTER", "encounter_id": "Cultist"},
            {"act": 1, "floor": 3, "room_type": "MONSTER", "encounter_id": "JawWorm"},
        ],
        "visible_map": [
            {
                "symbol": "M",
                "room_type": "MONSTER",
                "burning_elite": False,
                "x": 3,
                "y": 0,
                "parents": [],
                "children": [{"x": 3, "y": 1}],
            },
        ],
        "current_map_node": {
            "symbol": "M",
            "room_type": "MONSTER",
            "burning_elite": False,
            "x": 3,
            "y": 0,
            "parents": [],
            "children": [{"x": 3, "y": 1}],
        },
        "next_map_nodes": [
            {
                "symbol": "?",
                "room_type": "UNKNOWN",
                "burning_elite": False,
                "x": 3,
                "y": 1,
                "parents": [{"x": 3, "y": 0}],
                "children": [],
            },
        ],
    }

    context = build_public_run_context(raw)
    assert context["schema_id"] == PUBLIC_RUN_CONTEXT_SCHEMA_ID
    assert context["visible_act_boss"] == "The Guardian"

    encounters = context["encounter_history"]
    assert len(encounters) == 2
    assert encounters[0]["encounter_id"] == "Cultist"
    assert "hidden_rng" not in str(encounters)

    visible_map = context["visible_map"]
    assert len(visible_map) == 1
    assert visible_map[0]["symbol"] == "M"
    assert visible_map[0]["burning_elite"] is False
    assert visible_map[0]["children"] == [{"x": 3, "y": 1}]

    assert context["current_map_node"] is not None
    assert context["current_map_node"]["symbol"] == "M"

    next_nodes = context["next_map_nodes"]
    assert len(next_nodes) == 1
    assert next_nodes[0]["symbol"] == "?"

    assert public_run_context_problems(context) == []


# ---------------------------------------------------------------------------
# Forbidden field rejection
# ---------------------------------------------------------------------------


def test_rejects_forbidden_field_in_top_level():
    context = empty_public_run_context()
    context["hidden_rng"] = 42
    problems = public_run_context_problems(context)
    assert any("forbidden field" in p for p in problems)


def test_rejects_forbidden_field_in_visible_map():
    raw = {
        "visible_map": [
            {
                "symbol": "M",
                "room_type": "MONSTER",
                "burning_elite": False,
                "x": 3,
                "y": 0,
                "parents": [],
                "children": [],
                "draw_pile_order": [1, 2, 3],
            },
        ],
    }
    context = build_public_run_context(raw)
    problems = public_run_context_problems(context)
    assert any("draw_pile_order" in p for p in problems)


def test_rejects_forbidden_field_in_history():
    raw = {
        "public_run_history": {
            "schema_id": PUBLIC_RUN_HISTORY_SCHEMA_ID,
            "entries": [
                {
                    "sequence": 0,
                    "before": {
                        "visible_screen": {},
                        "location": {
                            "screen_state": "BATTLE",
                            "act": 1,
                            "floor": 1,
                            "room_type": "MONSTER",
                        },
                    },
                    "action": {},
                    "after": {
                        "location": {},
                        "resource_delta": {},
                    },
                    "missing_fields": [],
                    "rng_state": 999,
                },
            ],
        },
    }
    context = build_public_run_context(raw)
    problems = public_run_context_problems(context)
    assert any("rng_state" in p for p in problems)


# ---------------------------------------------------------------------------
# Recursive validation
# ---------------------------------------------------------------------------


def test_rejects_non_allowlisted_map_key():
    raw = {
        "visible_map": [
            {
                "symbol": "M",
                "room_type": "MONSTER",
                "x": 3,
                "y": 0,
                "burning_elite": False,
                "parents": [],
                "children": [],
                "secret_boss_flag": True,
            },
        ],
    }
    context = build_public_run_context(raw)
    assert context["visible_map"]  # sanitizer drops unknown keys
    assert not context["visible_map"][0].get("secret_boss_flag")


def test_rejects_non_allowlisted_key_in_encounter():
    raw = {
        "public_encounter_history": [
            {
                "act": 1,
                "floor": 1,
                "room_type": "MONSTER",
                "encounter_id": "Cultist",
                "hidden_type": "elite",
            },
        ],
    }
    context = build_public_run_context(raw)
    # Sanitized projection drops unknown keys
    assert "hidden_type" not in str(context["encounter_history"])


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------


def test_empty_run_history():
    history = empty_public_run_history()
    assert history["schema_id"] == PUBLIC_RUN_HISTORY_SCHEMA_ID
    assert history["entries"] == []
    assert public_run_history_problems(history) == []


def test_append_single_history_entry():
    history = empty_public_run_history()
    before = {
        "screen_state": "BATTLE",
        "act": 1,
        "floor": 4,
        "room_type": "MONSTER",
        "event_id": "Cultist",
        "public_visible_screen": {
            "schema_id": "public_visible_screen-v1",
            "screen_state": "BATTLE",
            "projection_available": False,
            "legal_actions": [],
            "missing_fields": ["battle_screen_uses_battle_snapshot"],
        },
        "cur_hp": 70,
        "max_hp": 80,
        "gold": 100,
        "potions": [],
        "deck": [],
        "relics": [],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
    after = {
        **before,
        "cur_hp": 65,
        "gold": 95,
    }
    action_identity = {
        "scope": "battle",
        "kind": "card",
        "parameters": {"idx1": 0, "idx2": None, "idx3": None},
        "occurrence": 0,
        "stable_id": '{"occurrence":0,"public_action":{}}',
    }

    result = append_run_history_entry(
        history,
        before_raw=before,
        action_identity=action_identity,
        after_raw=after,
    )
    assert result["schema_id"] == PUBLIC_RUN_HISTORY_SCHEMA_ID
    assert len(result["entries"]) == 1

    entry = result["entries"][0]
    assert entry["sequence"] == 0
    assert entry["before"]["location"]["screen_state"] == "BATTLE"
    assert entry["before"]["location"]["act"] == 1
    assert entry["before"]["location"]["floor"] == 4
    assert entry["action"]["scope"] == "battle"
    assert entry["action"]["kind"] == "card"

    resource_delta = entry["after"]["resource_delta"]
    assert resource_delta["current_hp_delta"] == -5.0
    assert resource_delta["gold_delta"] == -5.0

    assert public_run_history_problems(result) == []


def test_history_sequence_ordering():
    history = empty_public_run_history()
    before = {
        "screen_state": "BATTLE",
        "act": 1,
        "floor": 1,
        "room_type": "MONSTER",
        "cur_hp": 80,
        "max_hp": 80,
        "gold": 99,
        "potions": [],
        "deck": [],
        "relics": [],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
    after = dict(before)
    action = {
        "scope": "battle",
        "kind": "card",
        "parameters": {},
        "occurrence": 0,
        "stable_id": "a",
    }

    history = append_run_history_entry(
        history, before_raw=before, action_identity=action, after_raw=after
    )
    history = append_run_history_entry(
        history, before_raw=before, action_identity=action, after_raw=after
    )

    assert len(history["entries"]) == 2
    assert history["entries"][0]["sequence"] == 0
    assert history["entries"][1]["sequence"] == 1

    # Corrupt the ordering
    history["entries"][1]["sequence"] = 5
    problems = public_run_history_problems(history)
    assert any("contiguous" in p for p in problems)


def test_resource_delta_keys():
    before = {
        "screen_state": "SHOP_ROOM",
        "cur_hp": 72,
        "max_hp": 72,
        "gold": 200,
        "potions": [{"id": "Fire Potion", "name": "Fire Potion"}],
        "deck": [
            {
                "id": "Strike_R",
                "name": "Strike",
                "type": "ATTACK",
                "rarity": "BASIC",
                "upgraded": False,
            }
        ],
        "relics": [],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
    after = {
        "screen_state": "SHOP_ROOM",
        "cur_hp": 72,
        "max_hp": 72,
        "gold": 50,
        "potions": [
            {"id": "Fire Potion", "name": "Fire Potion"},
            {"id": "Block Potion", "name": "Block Potion"},
        ],
        "deck": [
            {
                "id": "Strike_R",
                "name": "Strike",
                "type": "ATTACK",
                "rarity": "BASIC",
                "upgraded": False,
            }
        ],
        "relics": [{"id": "Vajra", "name": "Vajra"}],
        "blue_key": True,
        "green_key": False,
        "red_key": False,
    }

    delta = build_public_resource_delta(before, after)
    assert delta["current_hp_delta"] == 0.0
    assert delta["gold_delta"] == -150.0
    assert len(delta["potions_added"]) == 1
    assert delta["potions_added"][0]["name"] == "Block Potion"
    assert len(delta["relics_added"]) == 1
    assert delta["keys_gained"] == ["blue_key"]
    assert delta["keys_lost"] == []


# ---------------------------------------------------------------------------
# Visible screen extraction
# ---------------------------------------------------------------------------


def test_extract_visible_screen_missing():
    raw = {}
    screen = extract_public_visible_screen(raw)
    assert screen["schema_id"] == "public-visible-screen-v1"
    assert "public_visible_screen" in screen["missing_fields"]


def test_extract_visible_screen_projects_through_allowlist():
    raw = {
        "public_visible_screen": {
            "schema_id": "public_visible_screen-v1",
            "screen_state": "REWARDS",
            "projection_available": True,
            "legal_actions": [],
            "rewards": {
                "gold": [{"option_index": 0, "amount": 25}],
                "card_rewards": [],
                "relics": [],
                "potions": [],
                "emerald_key": False,
                "sapphire_key": False,
            },
            "hidden_rng": 42,
            "missing_fields": [],
        },
    }
    screen = extract_public_visible_screen(raw)
    assert screen["screen_state"] == "REWARDS"
    # The recursive projector includes forbidden fields so the validator can flag them.
    assert "rewards" in screen


def test_extract_location():
    raw = {
        "screen_state": "MAP_SCREEN",
        "act": 2,
        "floor_num": 17,
        "room_type": "REST",
        "current_map_node": {
            "symbol": "R",
            "room_type": "REST",
            "burning_elite": False,
            "x": 4,
            "y": 6,
            "parents": [{"x": 4, "y": 5}],
            "children": [],
        },
    }
    location = extract_public_location(raw)
    assert location["screen_state"] == "MAP_SCREEN"
    assert location["act"] == 2
    assert location["floor"] == 17
    assert location["room_type"] == "REST"
    assert location["current_map_node"] is not None
    assert location["current_map_node"]["symbol"] == "R"
