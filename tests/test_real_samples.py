from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.comm.protocol import format_command
from sts_combat_rl.decision import choose_command_for_state
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.samples import analyze_sample_file, sample_request_hints
from sts_combat_rl.state.parser import parse_game_state


REAL_SAMPLES = Path(__file__).parent / "fixtures" / "real_samples"
CLEAN_SAMPLE = REAL_SAMPLES / "capture_20260603_125604_6376.jsonl"
ACT2_SAMPLE = REAL_SAMPLES / "capture_20260603_160306_27436.jsonl"
VICTORY_SAMPLE = REAL_SAMPLES / "capture_20260603_161408_20736.jsonl"


def test_clean_communication_mod_sample_replays_without_errors() -> None:
    analysis = analyze_sample_file(CLEAN_SAMPLE)

    assert analysis.total_lines == 368
    assert analysis.invalid_json == 0
    assert analysis.non_object_json == 0
    assert analysis.communication_errors == 0
    assert analysis.parse_or_policy_failures == 0
    assert analysis.problems == []
    assert analysis.combat_states == 85
    assert analysis.screen_counts["MAP"] > 0
    assert analysis.screen_counts["CARD_REWARD"] > 0
    assert analysis.screen_counts["COMBAT_REWARD"] > 0
    assert analysis.screen_counts["SHOP_SCREEN"] > 0
    assert analysis.screen_counts["GAME_OVER"] > 0
    assert analysis.room_type_counts["MonsterRoomBoss"] > 0
    assert analysis.room_type_counts["MonsterRoomElite"] > 0
    assert analysis.room_type_counts["ShopRoom"] > 0
    assert analysis.room_type_counts["RestRoom"] > 0
    assert analysis.room_type_counts["TreasureRoom"] > 0
    assert analysis.available_command_verb_counts["play"] > 0
    assert analysis.available_command_verb_counts["end"] > 0
    assert analysis.available_command_verb_counts["choose"] > 0
    assert analysis.available_command_verb_counts["proceed"] > 0
    assert analysis.available_command_verb_counts["skip"] > 0
    assert analysis.available_command_verb_counts["leave"] > 0
    assert analysis.available_command_verb_counts["confirm"] > 0
    assert analysis.available_command_verb_counts["cancel"] > 0
    assert analysis.available_command_verb_counts["potion"] > 0
    assert analysis.monster_count_counts["2"] > 0
    assert analysis.monster_count_counts["3"] > 0
    assert analysis.playable_card_target_counts["ATTACK has_target=false"] > 0
    assert analysis.playable_card_target_counts["ATTACK has_target=true"] > 0
    assert analysis.potion_can_use_counts["true"] > 0
    assert analysis.potion_requires_target_counts["true"] > 0


def test_clean_sample_preserves_zero_energy() -> None:
    for raw in _iter_sample_objects(CLEAN_SAMPLE):
        state = parse_game_state(raw)
        if state.player is not None and state.player.raw.get("energy") == 0:
            assert state.player.energy == 0
            return

    raise AssertionError("expected a real sample with player energy 0")


def test_clean_sample_omits_targets_for_no_target_attacks() -> None:
    policy = ScriptedCombatPolicy()
    saw_no_target_attack = False

    for raw in _iter_sample_objects(CLEAN_SAMPLE):
        state = parse_game_state(raw)
        command = choose_command_for_state(state, policy)
        if command.command_type != "play_card" or command.card_index is None:
            continue

        card = state.hand[command.card_index]
        if card.has_target is False and card.type == "ATTACK":
            saw_no_target_attack = True
            assert command.target_index is None
            assert format_command(command) == f"play {command.card_index + 1}"

    assert saw_no_target_attack is True


def test_manual_act2_sample_replays_without_errors_and_covers_boss_reward() -> None:
    analysis = analyze_sample_file(ACT2_SAMPLE)
    requests = sample_request_hints(analysis)

    assert analysis.total_lines == 844
    assert analysis.invalid_json == 0
    assert analysis.non_object_json == 0
    assert analysis.communication_errors == 0
    assert analysis.parse_or_policy_failures == 0
    assert analysis.problems == []
    assert analysis.combat_states == 386
    assert analysis.non_combat_states == 458
    assert analysis.class_counts["IRONCLAD"] > 0
    assert analysis.act_counts["2"] > 0
    assert analysis.screen_counts["BOSS_REWARD"] > 0
    assert analysis.room_type_counts["TreasureRoomBoss"] > 0
    assert analysis.monster_name_counts["Hexaghost"] > 0
    assert analysis.monster_name_counts["Chosen"] > 0
    assert not any("Act 2" in request for request in requests)
    assert not any("boss reward" in request for request in requests)


def test_manual_victory_sample_replays_without_errors_and_covers_act4() -> None:
    analysis = analyze_sample_file(VICTORY_SAMPLE)
    requests = sample_request_hints(analysis)

    assert analysis.total_lines == 3977
    assert analysis.invalid_json == 0
    assert analysis.non_object_json == 0
    assert analysis.communication_errors == 0
    assert analysis.parse_or_policy_failures == 0
    assert analysis.problems == []
    assert analysis.combat_states == 2715
    assert analysis.non_combat_states == 1262
    assert analysis.class_counts["IRONCLAD"] > 0
    assert analysis.act_counts["4"] > 0
    assert analysis.screen_counts["GAME_OVER"] > 0
    assert analysis.game_over_victory_counts["true"] > 0
    assert analysis.room_type_counts["TrueVictoryRoom"] > 0
    assert analysis.monster_name_counts["CorruptHeart"] > 0
    assert analysis.monster_name_counts["SpireShield"] > 0
    assert analysis.monster_name_counts["SpireSpear"] > 0
    assert not any("victory=true" in request for request in requests)


def _iter_sample_objects(path: Path) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            raw = json.loads(line)
            assert isinstance(raw, dict)
            objects.append(raw)
    return objects
