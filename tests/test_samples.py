from __future__ import annotations

from pathlib import Path

from sts_combat_rl.samples import (
    analyze_sample_file,
    analyze_sample_paths,
    format_sample_analysis,
    sample_request_hints,
)


def test_analyze_sample_file_counts_commands_and_problems(tmp_path: Path) -> None:
    sample_file = tmp_path / "captured.jsonl"
    sample_file.write_text(
        "\n"
        '{"available_commands":["play","end","wait","state"],'
        '"game_state":{"screen_type":"NONE","room_phase":"COMBAT",'
        '"action_phase":"WAITING_ON_USER","combat_state":{"hand":['
        '{"name":"Strike","type":"ATTACK","is_playable":true}],'
        '"monsters":[{"name":"Cultist","current_hp":10}]}}}\n'
        '{"error":"Invalid command: end","ready_for_command":true}\n'
        "{not json}\n"
        "[1, 2]\n",
        encoding="utf-8",
    )

    analysis = analyze_sample_file(sample_file)

    assert analysis.total_lines == 5
    assert analysis.blank_lines == 1
    assert analysis.json_objects == 2
    assert analysis.invalid_json == 1
    assert analysis.non_object_json == 1
    assert analysis.communication_errors == 1
    assert analysis.communication_error_counts["Invalid command: end"] == 1
    assert analysis.parse_or_policy_failures == 0
    assert analysis.combat_states == 1
    assert analysis.command_counts["play 1 0"] == 1
    assert analysis.command_counts["state"] == 1
    assert analysis.screen_counts["NONE"] == 1
    assert analysis.screen_name_counts["(none)"] == 1
    assert analysis.room_phase_counts["COMBAT"] == 1
    assert analysis.top_level_key_counts["available_commands"] == 1
    assert analysis.game_state_key_counts["combat_state"] == 1
    assert analysis.combat_state_key_counts["hand"] == 1
    assert analysis.available_command_verb_counts["play"] == 1
    assert analysis.available_command_verb_counts["end"] == 1
    assert analysis.monster_count_counts["1"] == 1
    assert analysis.monster_name_counts["Cultist"] == 1
    assert analysis.card_type_counts["ATTACK"] == 1
    assert analysis.hand_card_id_counts["Strike"] == 1
    assert analysis.playable_card_type_counts["ATTACK"] == 1
    assert len(analysis.problems) == 3


def test_format_sample_analysis_includes_empty_sections(tmp_path: Path) -> None:
    sample_file = tmp_path / "empty.jsonl"
    sample_file.write_text("", encoding="utf-8")

    report = format_sample_analysis(analyze_sample_file(sample_file))

    assert "Sample replay summary" in report
    assert "commands:\n  (none)" in report
    assert "available command verbs:\n  (none)" in report
    assert "monster counts:\n  (none)" in report
    assert "sample requests:" in report
    assert "problem samples:\n  (none)" in report


def test_analyze_sample_paths_expands_directory_and_aggregates(tmp_path: Path) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    for name in ("a.jsonl", "b.jsonl"):
        (sample_dir / name).write_text(
            '{"available_commands":["play","end","wait","state"],'
            '"game_state":{"screen_type":"NONE","room_phase":"COMBAT",'
            '"action_phase":"WAITING_ON_USER","combat_state":{"hand":['
            '{"name":"Strike","type":"ATTACK","is_playable":true}],'
            '"monsters":[{"name":"Cultist","current_hp":10}]}}}\n',
            encoding="utf-8",
        )
    (sample_dir / "ignored.txt").write_text("not jsonl\n", encoding="utf-8")

    analysis = analyze_sample_paths([sample_dir])
    report = format_sample_analysis(analysis)

    assert analysis.total_lines == 2
    assert analysis.json_objects == 2
    assert analysis.command_counts["play 1 0"] == 2
    assert analysis.source_paths == [
        sample_dir / "a.jsonl",
        sample_dir / "b.jsonl",
    ]
    assert "paths: 2" in report
    assert "play 1 0: 2" in report


def test_sample_request_hints_are_conservative_for_small_samples(tmp_path: Path) -> None:
    sample_file = tmp_path / "captured.jsonl"
    sample_file.write_text(
        '{"available_commands":["play","end","wait","state"],'
        '"game_state":{"class":"IRONCLAD","act":1,"screen_type":"NONE",'
        '"room_phase":"COMBAT","combat_state":{"hand":[],'
        '"monsters":[{"name":"Cultist","current_hp":10}]}}}\n',
        encoding="utf-8",
    )

    requests = sample_request_hints(analyze_sample_file(sample_file))

    assert not any("SILENT" in request for request in requests)
    assert not any("DEFECT" in request for request in requests)
    assert not any("WATCHER" in request for request in requests)
    assert "capture Act 2 or Act 3 states after an act transition" in requests
