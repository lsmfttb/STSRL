"""Offline analysis for captured CommunicationMod JSONL samples."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.comm.protocol import Command, format_command
from sts_combat_rl.decision import choose_command_for_state
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.state.parser import parse_game_state


DEFAULT_MAX_PROBLEMS = 10
SUPPORTED_CLASSES = {"IRONCLAD"}


@dataclass
class SampleAnalysis:
    path: Path
    source_paths: list[Path] = field(default_factory=list)
    total_lines: int = 0
    blank_lines: int = 0
    json_objects: int = 0
    invalid_json: int = 0
    non_object_json: int = 0
    communication_errors: int = 0
    parse_or_policy_failures: int = 0
    combat_states: int = 0
    non_combat_states: int = 0
    command_counts: Counter[str] = field(default_factory=Counter)
    communication_error_counts: Counter[str] = field(default_factory=Counter)
    screen_counts: Counter[str] = field(default_factory=Counter)
    screen_name_counts: Counter[str] = field(default_factory=Counter)
    action_phase_counts: Counter[str] = field(default_factory=Counter)
    class_counts: Counter[str] = field(default_factory=Counter)
    act_counts: Counter[str] = field(default_factory=Counter)
    floor_counts: Counter[str] = field(default_factory=Counter)
    room_phase_counts: Counter[str] = field(default_factory=Counter)
    room_type_counts: Counter[str] = field(default_factory=Counter)
    top_level_key_counts: Counter[str] = field(default_factory=Counter)
    game_state_key_counts: Counter[str] = field(default_factory=Counter)
    combat_state_key_counts: Counter[str] = field(default_factory=Counter)
    screen_state_key_counts: Counter[str] = field(default_factory=Counter)
    event_id_counts: Counter[str] = field(default_factory=Counter)
    game_over_victory_counts: Counter[str] = field(default_factory=Counter)
    rest_option_counts: Counter[str] = field(default_factory=Counter)
    available_command_verb_counts: Counter[str] = field(default_factory=Counter)
    available_command_counts: Counter[str] = field(default_factory=Counter)
    choice_count_counts: Counter[str] = field(default_factory=Counter)
    choice_label_counts: Counter[str] = field(default_factory=Counter)
    map_next_node_symbol_counts: Counter[str] = field(default_factory=Counter)
    monster_count_counts: Counter[str] = field(default_factory=Counter)
    monster_name_counts: Counter[str] = field(default_factory=Counter)
    monster_intent_counts: Counter[str] = field(default_factory=Counter)
    card_type_counts: Counter[str] = field(default_factory=Counter)
    hand_card_id_counts: Counter[str] = field(default_factory=Counter)
    playable_card_type_counts: Counter[str] = field(default_factory=Counter)
    playable_card_target_counts: Counter[str] = field(default_factory=Counter)
    potion_count_counts: Counter[str] = field(default_factory=Counter)
    potion_id_counts: Counter[str] = field(default_factory=Counter)
    potion_can_use_counts: Counter[str] = field(default_factory=Counter)
    potion_requires_target_counts: Counter[str] = field(default_factory=Counter)
    potion_can_discard_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def analyze_sample_file(
    path: Path,
    policy: ScriptedCombatPolicy | None = None,
    max_problems: int = DEFAULT_MAX_PROBLEMS,
) -> SampleAnalysis:
    """Read a captured JSONL file and summarize parser/policy behavior."""

    analysis = SampleAnalysis(path=path)
    analysis.source_paths.append(path)
    active_policy = policy or ScriptedCombatPolicy()

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            analysis.total_lines += 1
            raw_line = line.strip()
            if not raw_line:
                analysis.blank_lines += 1
                continue

            try:
                raw = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                analysis.invalid_json += 1
                _add_problem(
                    analysis,
                    max_problems,
                    line_number,
                    f"invalid JSON: {exc.msg}",
                )
                continue

            if not isinstance(raw, dict):
                analysis.non_object_json += 1
                _add_problem(analysis, max_problems, line_number, "JSON value is not an object")
                continue

            analysis.json_objects += 1
            if "error" in raw:
                analysis.communication_errors += 1
                error_message = _stringify(raw.get("error"))
                analysis.communication_error_counts[error_message] += 1
                analysis.command_counts[format_command(Command.state("sample error"))] += 1
                _add_problem(
                    analysis,
                    max_problems,
                    line_number,
                    f"CommunicationMod error: {error_message}",
                )
                continue

            try:
                state = parse_game_state(raw)
                command = choose_command_for_state(state, active_policy)
            except Exception as exc:
                analysis.parse_or_policy_failures += 1
                _add_problem(
                    analysis,
                    max_problems,
                    line_number,
                    f"parse/policy failure: {exc.__class__.__name__}: {exc}",
                )
                continue

            if state.in_combat:
                analysis.combat_states += 1
            else:
                analysis.non_combat_states += 1

            analysis.command_counts[format_command(command)] += 1
            analysis.screen_counts[state.screen_type or "(none)"] += 1
            analysis.action_phase_counts[state.action_phase or "(none)"] += 1
            available = ", ".join(state.available_commands) if state.available_commands else "(none)"
            analysis.available_command_counts[available] += 1
            _count_state_coverage(analysis, raw, state)

    return analysis


def analyze_sample_paths(
    paths: Iterable[Path],
    policy: ScriptedCombatPolicy | None = None,
    max_problems: int = DEFAULT_MAX_PROBLEMS,
) -> SampleAnalysis:
    """Read one or more JSONL files or directories and summarize them together."""

    sample_paths = expand_sample_paths(paths)
    if not sample_paths:
        raise FileNotFoundError("no JSONL sample files found")

    active_policy = policy or ScriptedCombatPolicy()
    if len(sample_paths) == 1:
        return analyze_sample_file(
            sample_paths[0],
            policy=active_policy,
            max_problems=max_problems,
        )

    analysis = SampleAnalysis(path=Path("<multiple samples>"))
    analysis.source_paths.extend(sample_paths)
    for sample_path in sample_paths:
        sample_analysis = analyze_sample_file(
            sample_path,
            policy=active_policy,
            max_problems=max_problems,
        )
        _merge_analysis(analysis, sample_analysis, max_problems)

    return analysis


def expand_sample_paths(paths: Iterable[Path]) -> list[Path]:
    """Expand sample file and directory arguments into sorted JSONL files."""

    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(candidate for candidate in path.rglob("*.jsonl")))
        else:
            expanded.append(path)
    return sorted(expanded)


def format_sample_analysis(analysis: SampleAnalysis) -> str:
    """Format an offline sample analysis report."""

    lines = ["Sample replay summary"]
    if len(analysis.source_paths) <= 1:
        lines.append(f"path: {analysis.path}")
    else:
        lines.append(f"paths: {len(analysis.source_paths)}")
        lines.extend(f"  {source_path}" for source_path in analysis.source_paths)

    lines.extend(
        [
            f"lines: {analysis.total_lines}",
            f"blank lines: {analysis.blank_lines}",
            f"json objects: {analysis.json_objects}",
            f"invalid json: {analysis.invalid_json}",
            f"non-object json: {analysis.non_object_json}",
            f"CommunicationMod errors: {analysis.communication_errors}",
            f"parse/policy failures: {analysis.parse_or_policy_failures}",
            f"combat states: {analysis.combat_states}",
            f"non-combat states: {analysis.non_combat_states}",
        ]
    )
    _append_counter(
        lines,
        "CommunicationMod error messages",
        analysis.communication_error_counts,
    )
    _append_counter(lines, "commands", analysis.command_counts)
    _append_counter(lines, "screens", analysis.screen_counts)
    _append_counter(lines, "screen names", analysis.screen_name_counts)
    _append_counter(lines, "action phases", analysis.action_phase_counts)
    _append_counter(lines, "classes", analysis.class_counts)
    _append_counter(lines, "acts", analysis.act_counts)
    _append_counter(lines, "floors", analysis.floor_counts)
    _append_counter(lines, "room phases", analysis.room_phase_counts)
    _append_counter(lines, "room types", analysis.room_type_counts)
    _append_counter(lines, "top-level keys", analysis.top_level_key_counts)
    _append_counter(lines, "game_state keys", analysis.game_state_key_counts)
    _append_counter(lines, "combat_state keys", analysis.combat_state_key_counts)
    _append_counter(lines, "screen_state keys", analysis.screen_state_key_counts)
    _append_counter(lines, "event ids", analysis.event_id_counts)
    _append_counter(lines, "game over victory flags", analysis.game_over_victory_counts)
    _append_counter(lines, "rest options", analysis.rest_option_counts)
    _append_counter(lines, "available command verbs", analysis.available_command_verb_counts)
    _append_counter(lines, "available command sets", analysis.available_command_counts)
    _append_counter(lines, "choice counts", analysis.choice_count_counts)
    _append_counter(lines, "choice labels", analysis.choice_label_counts)
    _append_counter(lines, "map next node symbols", analysis.map_next_node_symbol_counts)
    _append_counter(lines, "monster counts", analysis.monster_count_counts)
    _append_counter(lines, "monster names", analysis.monster_name_counts)
    _append_counter(lines, "monster intents", analysis.monster_intent_counts)
    _append_counter(lines, "hand card types", analysis.card_type_counts)
    _append_counter(lines, "hand card ids", analysis.hand_card_id_counts)
    _append_counter(lines, "playable card types", analysis.playable_card_type_counts)
    _append_counter(lines, "playable card target flags", analysis.playable_card_target_counts)
    _append_counter(lines, "potion counts", analysis.potion_count_counts)
    _append_counter(lines, "potion ids", analysis.potion_id_counts)
    _append_counter(lines, "potion can_use flags", analysis.potion_can_use_counts)
    _append_counter(lines, "potion requires_target flags", analysis.potion_requires_target_counts)
    _append_counter(lines, "potion can_discard flags", analysis.potion_can_discard_counts)

    lines.append("sample requests:")
    requests = sample_request_hints(analysis)
    if requests:
        lines.extend(f"  {request}" for request in requests)
    else:
        lines.append("  (none)")

    lines.append("problem samples:")
    if analysis.problems:
        lines.extend(f"  {problem}" for problem in analysis.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _merge_analysis(
    target: SampleAnalysis,
    source: SampleAnalysis,
    max_problems: int,
) -> None:
    for field_info in fields(SampleAnalysis):
        name = field_info.name
        if name in {"path", "source_paths", "problems"}:
            continue

        target_value = getattr(target, name)
        source_value = getattr(source, name)
        if isinstance(target_value, Counter) and isinstance(source_value, Counter):
            target_value.update(source_value)
        elif isinstance(target_value, int) and isinstance(source_value, int):
            setattr(target, name, target_value + source_value)

    remaining_problem_slots = max_problems - len(target.problems)
    if remaining_problem_slots <= 0:
        return

    for problem in source.problems[:remaining_problem_slots]:
        target.problems.append(f"{source.path}: {problem}")


def sample_request_hints(analysis: SampleAnalysis) -> list[str]:
    """Return conservative sample requests for protocol calibration gaps."""

    requests: list[str] = []

    seen_classes = {key for key in analysis.class_counts if key != "(none)"}
    missing_classes = sorted(SUPPORTED_CLASSES - seen_classes)
    if missing_classes:
        requests.append(
            "capture supported character states: "
            + ", ".join(missing_classes)
        )

    if not _has_numeric_key_at_least(analysis.act_counts, 2):
        requests.append("capture Act 2 or Act 3 states after an act transition")

    if analysis.game_over_victory_counts["true"] == 0:
        requests.append("capture a victory=true GAME_OVER or post-boss win state")

    if (
        analysis.screen_counts["BOSS_REWARD"] == 0
        and analysis.screen_name_counts["BOSS_REWARD"] == 0
    ):
        requests.append("capture the boss reward / act transition screen")

    return requests


def _has_numeric_key_at_least(counter: Counter[str], threshold: int) -> bool:
    for key in counter:
        try:
            if int(key) >= threshold:
                return True
        except ValueError:
            continue
    return False


def _count_state_coverage(
    analysis: SampleAnalysis,
    raw: dict[str, Any],
    state: Any,
) -> None:
    game_raw = _mapping_value(raw, "game_state") or _mapping_value(raw, "gameState") or raw
    combat_raw = _mapping_value(game_raw, "combat_state") or _mapping_value(
        game_raw,
        "combatState",
    )
    screen_state_raw = _mapping_value(game_raw, "screen_state") or _mapping_value(
        game_raw,
        "screenState",
    )

    for key in raw:
        analysis.top_level_key_counts[key] += 1
    for key in game_raw:
        analysis.game_state_key_counts[key] += 1
    if combat_raw is not None:
        for key in combat_raw:
            analysis.combat_state_key_counts[key] += 1
    if screen_state_raw is not None:
        for key in screen_state_raw:
            analysis.screen_state_key_counts[key] += 1

    _count_scalar(analysis.screen_name_counts, game_raw.get("screen_name"))
    _count_scalar(analysis.class_counts, game_raw.get("class"))
    _count_scalar(analysis.act_counts, game_raw.get("act"))
    _count_scalar(analysis.floor_counts, game_raw.get("floor"))
    _count_scalar(analysis.room_phase_counts, game_raw.get("room_phase"))
    _count_scalar(analysis.room_type_counts, game_raw.get("room_type"))

    for command in state.available_commands:
        analysis.available_command_verb_counts[command] += 1

    choice_items = _sequence_value(game_raw, "choice_list")
    if choice_items is not None:
        analysis.choice_count_counts[str(len(choice_items))] += 1
        for choice in choice_items:
            _count_scalar(analysis.choice_label_counts, choice)

    if screen_state_raw is not None:
        if "event_id" in screen_state_raw:
            _count_scalar(analysis.event_id_counts, screen_state_raw.get("event_id"))
        if "victory" in screen_state_raw:
            _count_bool(analysis.game_over_victory_counts, screen_state_raw.get("victory"))

        for node in _sequence_value(screen_state_raw, "next_nodes") or []:
            if isinstance(node, Mapping):
                _count_scalar(analysis.map_next_node_symbol_counts, node.get("symbol"))

        for option in _sequence_value(screen_state_raw, "options") or []:
            if isinstance(option, Mapping):
                label = option.get("label") if "label" in option else option.get("text")
                _count_scalar(analysis.choice_label_counts, label)

        for rest_option in _sequence_value(screen_state_raw, "rest_options") or []:
            _count_scalar(analysis.rest_option_counts, rest_option)

    analysis.monster_count_counts[str(len(state.monsters))] += 1
    for monster in state.monsters:
        _count_scalar(analysis.monster_name_counts, monster.monster_id or monster.name)
        _count_scalar(analysis.monster_intent_counts, monster.intent)

    for card in state.hand:
        card_type = card.type or "(none)"
        analysis.card_type_counts[card_type] += 1
        _count_scalar(analysis.hand_card_id_counts, card.card_id or card.name)
        if card.playable:
            analysis.playable_card_type_counts[card_type] += 1
            target_flag = _bool_label(card.has_target)
            analysis.playable_card_target_counts[f"{card_type} has_target={target_flag}"] += 1

    potions = _sequence_value(game_raw, "potions")
    if potions is not None:
        analysis.potion_count_counts[str(len(potions))] += 1
        for potion in potions:
            if not isinstance(potion, Mapping):
                continue
            _count_scalar(analysis.potion_id_counts, potion.get("id") or potion.get("name"))
            _count_bool(analysis.potion_can_use_counts, potion.get("can_use"))
            _count_bool(analysis.potion_requires_target_counts, potion.get("requires_target"))
            _count_bool(analysis.potion_can_discard_counts, potion.get("can_discard"))


def _mapping_value(data: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = data.get(key)
    return value if isinstance(value, Mapping) else None


def _sequence_value(data: Mapping[str, Any], key: str) -> list[Any] | None:
    value = data.get(key)
    return value if isinstance(value, list) else None


def _count_scalar(counter: Counter[str], value: Any) -> None:
    counter[_scalar_label(value)] += 1


def _count_bool(counter: Counter[str], value: Any) -> None:
    counter[_bool_label(value)] += 1


def _scalar_label(value: Any) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _bool_label(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "(none)"
    return _scalar_label(value)


def _add_problem(
    analysis: SampleAnalysis,
    max_problems: int,
    line_number: int,
    message: str,
) -> None:
    if len(analysis.problems) >= max_problems:
        return
    analysis.problems.append(f"line {line_number}: {message}")


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True)
