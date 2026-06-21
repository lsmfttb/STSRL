"""Smoke calibration helpers for simulator adapters.

This module exercises reset/legal_actions/step and feature encoding. It does
not implement a training loop, Gymnasium environment, action mask, replay
buffer, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.samples import expand_sample_paths
from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    action_space_for_screen,
    choose_deterministic_action,
    filter_eligible_actions,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    build_public_tactical_actions,
    build_public_tactical_state,
    communicationmod_battle_feature_size,
    encode_communicationmod_battle_snapshot,
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
    lightspeed_battle_feature_size,
    normalize_communicationmod_battle_snapshot,
    simulator_action_feature_size,
    tactical_action_problems,
    tactical_field_parity_rows,
    tactical_state_problems,
)


@dataclass
class SimulatorCalibrationReport:
    """Summary of one bounded simulator adapter smoke run."""

    seed: int | None
    requested_steps: int
    excluded_action_kinds: tuple[str, ...] = ()
    executed_steps: int = 0
    terminal: bool = False
    outcome: str = "UNKNOWN"
    battle_snapshots: int = 0
    non_battle_snapshots: int = 0
    observation_size_counts: Counter[str] = field(default_factory=Counter)
    battle_feature_size_counts: Counter[str] = field(default_factory=Counter)
    legal_action_count_counts: Counter[str] = field(default_factory=Counter)
    eligible_action_count_counts: Counter[str] = field(default_factory=Counter)
    action_feature_size_counts: Counter[str] = field(default_factory=Counter)
    legal_action_kind_counts: Counter[str] = field(default_factory=Counter)
    eligible_action_kind_counts: Counter[str] = field(default_factory=Counter)
    excluded_legal_action_kind_counts: Counter[str] = field(default_factory=Counter)
    legal_action_scope_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    screen_state_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


@dataclass
class CommunicationModFeatureCalibrationReport:
    """Feature-readiness summary for real CommunicationMod JSONL samples."""

    source_paths: list[Path] = field(default_factory=list)
    total_lines: int = 0
    json_objects: int = 0
    invalid_json: int = 0
    communication_errors: int = 0
    combat_states: int = 0
    non_combat_states: int = 0
    feature_size_counts: Counter[str] = field(default_factory=Counter)
    hand_size_counts: Counter[str] = field(default_factory=Counter)
    monster_count_counts: Counter[str] = field(default_factory=Counter)
    card_type_counts: Counter[str] = field(default_factory=Counter)
    monster_intent_counts: Counter[str] = field(default_factory=Counter)
    present_field_counts: Counter[str] = field(default_factory=Counter)
    missing_field_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


@dataclass
class TacticalFeatureCoverageReport:
    """Public-v2 feature audit usable for simulator and captured live inputs."""

    source: str
    feature_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID
    feature_schema_version: int = TACTICAL_FEATURE_SCHEMA_VERSION
    identity_vocabulary_version: str = IDENTITY_VOCABULARY_VERSION
    snapshot_count: int = 0
    legal_action_count: int = 0
    state_feature_size_counts: Counter[str] = field(default_factory=Counter)
    action_feature_size_counts: Counter[str] = field(default_factory=Counter)
    unknown_identity_counts: Counter[str] = field(default_factory=Counter)
    missing_field_counts: Counter[str] = field(default_factory=Counter)
    field_parity: list[dict[str, str]] = field(
        default_factory=tactical_field_parity_rows
    )
    problems: list[str] = field(default_factory=list)


def run_simulator_calibration(
    adapter: SimulatorAdapter,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> SimulatorCalibrationReport:
    """Run a bounded adapter smoke and summarize feature/action stability."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    report = SimulatorCalibrationReport(
        seed=seed,
        requested_steps=max_steps,
        excluded_action_kinds=tuple(sorted(active_action_space.excluded_kinds)),
    )
    snapshot = adapter.reset(seed=seed)

    for _ in range(max_steps + 1):
        _count_snapshot(report, snapshot)
        if report.terminal:
            break

        actions = list(adapter.legal_actions(snapshot))
        effective_action_space = action_space_for_screen(
            active_action_space,
            screen_state=str(snapshot.raw.get("screen_state", "(none)")),
            battle_active=bool(snapshot.raw.get("battle_active")),
        )
        _count_actions(report, actions, effective_action_space)
        if not actions:
            report.problems.append("no legal actions before terminal state")
            break

        if report.executed_steps >= max_steps:
            break

        action = choose_calibration_action(actions, effective_action_space)
        report.chosen_action_kind_counts[action.kind] += 1
        transition = adapter.step(action)
        report.executed_steps += 1
        snapshot = transition.snapshot
        report.terminal = transition.terminal

    report.outcome = str(snapshot.raw.get("outcome", report.outcome))
    _validate_expected_feature_sizes(report)
    return report


def run_tactical_feature_coverage_audit(
    adapter: SimulatorAdapter,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> TacticalFeatureCoverageReport:
    """Audit v2 public state/action coverage over real simulator snapshots."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    report = TacticalFeatureCoverageReport(source="sts_lightspeed")
    snapshot = adapter.reset(seed=seed)
    executed_steps = 0
    for _ in range(max_steps + 1):
        raw = snapshot.raw
        if bool(raw.get("battle_active")):
            actions = list(adapter.legal_actions(snapshot))
            _count_tactical_snapshot(report, raw, actions)
        if str(raw.get("outcome")) != "UNDECIDED" or executed_steps >= max_steps:
            break
        actions = list(adapter.legal_actions(snapshot))
        if not actions:
            report.problems.append("no legal actions before terminal state")
            break
        effective_action_space = action_space_for_screen(
            active_action_space,
            screen_state=str(raw.get("screen_state", "(none)")),
            battle_active=bool(raw.get("battle_active")),
        )
        try:
            action = choose_calibration_action(actions, effective_action_space)
        except ValueError as exc:
            report.problems.append(str(exc))
            break
        snapshot = adapter.step(action).snapshot
        executed_steps += 1
    _validate_tactical_report(report)
    return report


def run_communicationmod_tactical_feature_audit(
    paths: Iterable[Path],
    *,
    max_problems: int = 10,
) -> TacticalFeatureCoverageReport:
    """Audit captured live combat snapshots against the shared v2 contract."""

    sample_paths = expand_sample_paths(paths)
    if not sample_paths:
        raise FileNotFoundError("no JSONL sample files found")
    report = TacticalFeatureCoverageReport(source="communicationmod_capture")
    for path in sample_paths:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    _add_problem(
                        report.problems,
                        max_problems,
                        f"{path}: line {line_number}: invalid JSON: {exc.msg}",
                    )
                    continue
                raw = _mapping(value)
                if not raw or "error" in raw:
                    continue
                game = (
                    _mapping(raw.get("game_state"))
                    or _mapping(raw.get("gameState"))
                    or raw
                )
                combat = _mapping(game.get("combat_state")) or _mapping(
                    game.get("combatState")
                )
                if not combat:
                    continue
                _count_tactical_snapshot(
                    report,
                    normalize_communicationmod_battle_snapshot(raw),
                    [],
                )
    _validate_tactical_report(report)
    return report


def run_communicationmod_feature_calibration(
    paths: Iterable[Path],
    *,
    max_problems: int = 10,
) -> CommunicationModFeatureCalibrationReport:
    """Summarize whether live samples fit the first fixed-size feature encoder."""

    sample_paths = expand_sample_paths(paths)
    if not sample_paths:
        raise FileNotFoundError("no JSONL sample files found")

    report = CommunicationModFeatureCalibrationReport(source_paths=sample_paths)
    for sample_path in sample_paths:
        _count_communicationmod_sample_file(report, sample_path, max_problems)

    expected_feature_size = str(communicationmod_battle_feature_size())
    if report.feature_size_counts and set(report.feature_size_counts) != {
        expected_feature_size
    }:
        report.problems.append(
            "unexpected CommunicationMod feature sizes: "
            + ", ".join(sorted(report.feature_size_counts))
        )

    return report


def choose_calibration_action(
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig | None = None,
) -> SimulatorAction:
    """Pick a deterministic non-potion action for adapter smoke runs."""

    return choose_deterministic_action(actions, action_space)


def format_simulator_calibration_report(report: SimulatorCalibrationReport) -> str:
    """Format a simulator calibration report for stderr."""

    lines = [
        "Simulator calibration summary",
        f"seed: {report.seed if report.seed is not None else '(default)'}",
        f"requested steps: {report.requested_steps}",
        "configured battle excluded action kinds: "
        + (
            ", ".join(report.excluded_action_kinds)
            if report.excluded_action_kinds
            else "(none)"
        ),
        f"executed steps: {report.executed_steps}",
        f"terminal: {_bool_label(report.terminal)}",
        f"outcome: {report.outcome}",
        f"battle snapshots: {report.battle_snapshots}",
        f"non-battle snapshots: {report.non_battle_snapshots}",
    ]
    _append_counter(lines, "observation sizes", report.observation_size_counts)
    _append_counter(lines, "battle feature sizes", report.battle_feature_size_counts)
    _append_counter(lines, "legal action counts", report.legal_action_count_counts)
    _append_counter(
        lines, "eligible action counts", report.eligible_action_count_counts
    )
    _append_counter(lines, "action feature sizes", report.action_feature_size_counts)
    _append_counter(lines, "screen states", report.screen_state_counts)
    _append_counter(lines, "legal action scopes", report.legal_action_scope_counts)
    _append_counter(lines, "legal action kinds", report.legal_action_kind_counts)
    _append_counter(lines, "eligible action kinds", report.eligible_action_kind_counts)
    _append_counter(
        lines,
        "excluded legal action kinds",
        report.excluded_legal_action_kind_counts,
    )
    _append_counter(lines, "chosen action kinds", report.chosen_action_kind_counts)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_communicationmod_feature_calibration_report(
    report: CommunicationModFeatureCalibrationReport,
) -> str:
    """Format live sample feature-readiness report for stderr."""

    lines = [
        "CommunicationMod feature calibration summary",
        f"paths: {len(report.source_paths)}",
    ]
    lines.extend(f"  {source_path}" for source_path in report.source_paths)
    lines.extend(
        [
            f"lines: {report.total_lines}",
            f"json objects: {report.json_objects}",
            f"invalid json: {report.invalid_json}",
            f"CommunicationMod errors: {report.communication_errors}",
            f"combat states: {report.combat_states}",
            f"non-combat states: {report.non_combat_states}",
        ]
    )
    _append_counter(lines, "feature sizes", report.feature_size_counts)
    _append_counter(lines, "hand sizes", report.hand_size_counts)
    _append_counter(lines, "monster counts", report.monster_count_counts)
    _append_counter(lines, "card types", report.card_type_counts)
    _append_counter(lines, "monster intents", report.monster_intent_counts)
    _append_counter(lines, "present fields", report.present_field_counts)
    _append_counter(lines, "missing fields", report.missing_field_counts)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_tactical_feature_coverage_report(
    report: TacticalFeatureCoverageReport,
) -> str:
    """Format schema, coverage, unknown/missing, and parity audit evidence."""

    lines = [
        "Tactical feature coverage audit",
        f"source: {report.source}",
        f"feature schema: {report.feature_schema_id} v{report.feature_schema_version}",
        f"identity vocabulary: {report.identity_vocabulary_version}",
        f"battle snapshots: {report.snapshot_count}",
        f"legal actions: {report.legal_action_count}",
    ]
    _append_counter(lines, "state feature sizes", report.state_feature_size_counts)
    _append_counter(lines, "action feature sizes", report.action_feature_size_counts)
    _append_counter(lines, "unknown identities", report.unknown_identity_counts)
    _append_counter(lines, "missing public fields", report.missing_field_counts)
    lines.append("simulator/live field parity:")
    for row in report.field_parity:
        lines.append(
            "  "
            + f"{row['field']}: {row['classification']} "
            + f"(missing={row['missing_value_behavior']})"
        )
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _count_communicationmod_sample_file(
    report: CommunicationModFeatureCalibrationReport,
    sample_path: Path,
    max_problems: int,
) -> None:
    with sample_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            report.total_lines += 1
            raw_line = line.strip()
            if not raw_line:
                continue

            try:
                raw = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                report.invalid_json += 1
                _add_problem(
                    report.problems,
                    max_problems,
                    f"{sample_path}: line {line_number}: invalid JSON: {exc.msg}",
                )
                continue

            if not isinstance(raw, Mapping):
                _add_problem(
                    report.problems,
                    max_problems,
                    f"{sample_path}: line {line_number}: JSON value is not an object",
                )
                continue

            report.json_objects += 1
            if "error" in raw:
                report.communication_errors += 1
                continue

            game = (
                _mapping(raw.get("game_state")) or _mapping(raw.get("gameState")) or raw
            )
            combat = _mapping(game.get("combat_state")) or _mapping(
                game.get("combatState")
            )
            if not combat:
                report.non_combat_states += 1
                continue

            report.combat_states += 1
            report.feature_size_counts[
                str(len(encode_communicationmod_battle_snapshot(raw)))
            ] += 1
            _count_live_combat_shape(report, game, combat)


def _count_live_combat_shape(
    report: CommunicationModFeatureCalibrationReport,
    game: Mapping[str, Any],
    combat: Mapping[str, Any],
) -> None:
    player = _mapping(combat.get("player"))
    hand = _sequence(combat.get("hand"))
    monsters = _sequence(combat.get("monsters"))

    report.hand_size_counts[str(len(hand))] += 1
    report.monster_count_counts[str(len(monsters))] += 1

    _count_field(report, "game.act", game, "act")
    _count_field(report, "game.floor", game, "floor")
    _count_field(report, "game.current_hp", game, "current_hp")
    _count_field(report, "game.max_hp", game, "max_hp")
    _count_field(report, "game.gold", game, "gold")
    _count_field(report, "combat.turn", combat, "turn")
    _count_field(report, "combat.draw_pile", combat, "draw_pile")
    _count_field(report, "combat.discard_pile", combat, "discard_pile")
    _count_field(report, "combat.exhaust_pile", combat, "exhaust_pile")
    _count_field(report, "player.current_hp", player, "current_hp")
    _count_field(report, "player.max_hp", player, "max_hp")
    _count_field(report, "player.energy", player, "energy")
    _count_field(report, "player.block", player, "block")

    for card in hand:
        card_raw = _mapping(card)
        _count_scalar(report.card_type_counts, card_raw.get("type"))
        for field_name in (
            "id",
            "name",
            "type",
            "cost",
            "is_playable",
            "has_target",
            "exhausts",
            "ethereal",
        ):
            _count_field(report, f"card.{field_name}", card_raw, field_name)

    for monster in monsters:
        monster_raw = _mapping(monster)
        _count_scalar(report.monster_intent_counts, monster_raw.get("intent"))
        for field_name in (
            "id",
            "name",
            "current_hp",
            "max_hp",
            "block",
            "intent",
            "move_base_damage",
            "move_hits",
            "powers",
        ):
            _count_field(report, f"monster.{field_name}", monster_raw, field_name)


def _count_field(
    report: CommunicationModFeatureCalibrationReport,
    label: str,
    data: Mapping[str, Any],
    key: str,
) -> None:
    if key in data and data.get(key) is not None:
        report.present_field_counts[label] += 1
    else:
        report.missing_field_counts[label] += 1


def _count_snapshot(
    report: SimulatorCalibrationReport,
    snapshot: SimulatorSnapshot,
) -> None:
    raw = snapshot.raw
    report.observation_size_counts[str(len(snapshot.observation))] += 1
    report.battle_feature_size_counts[
        str(len(encode_lightspeed_battle_snapshot(raw)))
    ] += 1
    report.screen_state_counts[str(raw.get("screen_state", "(none)"))] += 1

    if raw.get("battle_active"):
        report.battle_snapshots += 1
    else:
        report.non_battle_snapshots += 1


def _count_tactical_snapshot(
    report: TacticalFeatureCoverageReport,
    raw: Mapping[str, Any],
    actions: list[SimulatorAction],
) -> None:
    state = build_public_tactical_state(raw)
    report.snapshot_count += 1
    report.state_feature_size_counts[
        str(len(encode_lightspeed_battle_snapshot(raw)))
    ] += 1
    for category, count in _mapping(state.get("unknown_identity_counts")).items():
        report.unknown_identity_counts[str(category)] += int(count)
    for field_name in _sequence(state.get("missing_fields")):
        report.missing_field_counts[str(field_name)] += 1
    report.problems.extend(tactical_state_problems(state))
    structured_actions = build_public_tactical_actions(actions, raw)
    report.legal_action_count += len(structured_actions)
    for encoded in encode_simulator_actions(actions, raw):
        report.action_feature_size_counts[str(len(encoded))] += 1
    report.problems.extend(tactical_action_problems(structured_actions))
    if len(structured_actions) != len(actions):
        report.problems.append(
            "tactical action count does not match legal action count"
        )


def _validate_tactical_report(report: TacticalFeatureCoverageReport) -> None:
    if report.snapshot_count == 0:
        report.problems.append("no battle snapshots were available for tactical audit")
    expected_state_size = str(lightspeed_battle_feature_size())
    if report.state_feature_size_counts and set(report.state_feature_size_counts) != {
        expected_state_size
    }:
        report.problems.append("unexpected tactical state feature sizes")
    expected_action_size = str(simulator_action_feature_size())
    if report.action_feature_size_counts and set(report.action_feature_size_counts) != {
        expected_action_size
    }:
        report.problems.append("unexpected tactical action feature sizes")
    if report.source == "sts_lightspeed":
        required_projection_fields = (
            ("availability.discard_cards", "discard-pile card members"),
            ("availability.exhaust_cards", "exhaust-pile card members"),
            ("monsters.intent_category", "canonical monster intent category"),
            ("monsters.state_machine.current_move", "exact monster current move"),
        )
        for field_name, label in required_projection_fields:
            missing_count = report.missing_field_counts[field_name]
            if missing_count:
                report.problems.append(
                    f"required {label} is absent from {missing_count} simulator "
                    "battle snapshots; update the authoritative public simulator "
                    "projection"
                )
    report.problems[:] = list(dict.fromkeys(report.problems))


def _count_actions(
    report: SimulatorCalibrationReport,
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig,
) -> None:
    report.legal_action_count_counts[str(len(actions))] += 1
    eligible_actions = filter_eligible_actions(actions, action_space)
    eligible_action_ids = {id(action) for action in eligible_actions}
    report.eligible_action_count_counts[str(len(eligible_actions))] += 1
    for features in encode_simulator_actions(actions):
        report.action_feature_size_counts[str(len(features))] += 1

    for action in actions:
        report.legal_action_kind_counts[action.kind] += 1
        report.legal_action_scope_counts[str(action.raw.get("scope", "(none)"))] += 1
        if id(action) in eligible_action_ids:
            report.eligible_action_kind_counts[action.kind] += 1
        else:
            report.excluded_legal_action_kind_counts[action.kind] += 1


def _validate_expected_feature_sizes(report: SimulatorCalibrationReport) -> None:
    expected_snapshot_size = str(lightspeed_battle_feature_size())
    if set(report.battle_feature_size_counts) != {expected_snapshot_size}:
        report.problems.append(
            "unexpected battle feature sizes: "
            + ", ".join(sorted(report.battle_feature_size_counts))
        )

    expected_action_size = str(simulator_action_feature_size())
    if report.action_feature_size_counts and set(report.action_feature_size_counts) != {
        expected_action_size
    }:
        report.problems.append(
            "unexpected action feature sizes: "
            + ", ".join(sorted(report.action_feature_size_counts))
        )


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _count_scalar(counter: Counter[str], value: Any) -> None:
    counter[_scalar_label(value)] += 1


def _scalar_label(value: Any) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _add_problem(
    problems: list[str],
    max_problems: int,
    message: str,
) -> None:
    if len(problems) >= max_problems:
        return
    problems.append(message)


def _bool_label(value: Any) -> str:
    return "true" if value else "false"
