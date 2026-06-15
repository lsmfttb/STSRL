"""Reward-component calibration for battle-agent segments.

This module reports raw observable components only. It does not choose reward
weights, define an RL objective, or create a training environment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.battle_agent import (
    BattleSegment,
    BattleSegmentReport,
    build_battle_segment_report,
)
from sts_combat_rl.sim.controlled_run import ControlledRun


BATTLE_REWARD_COMPONENT_NAMES = (
    "battle_success_proxy",
    "terminal_victory",
    "terminal_loss",
    "truncated",
    "decision_count",
    "hp_delta",
    "hp_loss",
    "hp_gain",
    "max_hp_delta",
    "gold_delta",
    "potion_count_delta",
)

FUTURE_REWARD_SIGNAL_GAPS = (
    "relic_counter_delta: current sts_lightspeed snapshots do not expose relic counters",
    (
        "deck_or_reward_delta: post-combat card/relic/reward choices are outside "
        "the current battle-agent segment"
    ),
    (
        "potion_value_delta: the current baseline is no-potion, while potion "
        "actions stay available through action-space configuration"
    ),
)

_BATTLE_SUCCESS_PROXY_END_REASONS = frozenset(
    {"nonterminal_battle_exit", "terminal_victory"}
)
_HIGHLIGHT_PRIORITY = {
    "gold_delta": 0,
    "max_hp_delta": 1,
    "potion_count_delta": 2,
    "hp_gain": 3,
    "terminal_loss": 4,
    "terminal_victory": 5,
    "truncated": 6,
}


@dataclass(frozen=True)
class BattleRewardComponentStats:
    """Aggregate stats for one raw reward component candidate."""

    samples: int = 0
    missing: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    nonzero_count: int = 0


@dataclass(frozen=True)
class BattleRewardSegmentHighlight:
    """One segment worth inspecting before assigning reward weights."""

    rollout_index: int
    seed: int | None
    segment_index: int
    start_floor: float | None
    end_reason: str
    decision_count: int
    tags: tuple[str, ...] = ()
    hp_delta: float | None = None
    max_hp_delta: float | None = None
    gold_delta: float | None = None
    potion_count_delta: float | None = None
    action_kind_counts: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class BattleRewardComponentReport:
    """Aggregate raw reward-component calibration for battle segments."""

    source_rollout_count: int
    segment_count: int
    excluded_non_combat_driver_steps: int
    total_battle_decisions: int
    components: dict[str, BattleRewardComponentStats] = field(default_factory=dict)
    end_reason_counts: Counter[str] = field(default_factory=Counter)
    rollout_outcome_counts: Counter[str] = field(default_factory=Counter)
    floor_counts: Counter[str] = field(default_factory=Counter)
    action_kind_counts: Counter[str] = field(default_factory=Counter)
    highlight_counts: Counter[str] = field(default_factory=Counter)
    highlights: list[BattleRewardSegmentHighlight] = field(default_factory=list)
    future_signal_gaps: tuple[str, ...] = FUTURE_REWARD_SIGNAL_GAPS
    problems: list[str] = field(default_factory=list)


def build_battle_reward_component_report(
    rollouts: list[ControlledRun],
) -> BattleRewardComponentReport:
    """Summarize raw reward-component candidates without assigning weights."""

    segment_report = build_battle_segment_report(rollouts)
    builders = {
        name: _RewardComponentStatsBuilder() for name in BATTLE_REWARD_COMPONENT_NAMES
    }
    highlights: list[BattleRewardSegmentHighlight] = []
    highlight_counts: Counter[str] = Counter()

    for segment in segment_report.segments:
        builders["battle_success_proxy"].add(
            _indicator(segment.end_reason in _BATTLE_SUCCESS_PROXY_END_REASONS)
        )
        builders["terminal_victory"].add(
            _indicator(segment.end_reason == "terminal_victory")
        )
        builders["terminal_loss"].add(_indicator(segment.end_reason == "terminal_loss"))
        builders["truncated"].add(_indicator(segment.end_reason == "truncated"))
        builders["decision_count"].add(float(segment.decision_count))
        builders["hp_delta"].add(segment.hp_delta)
        builders["hp_loss"].add(_negative_part(segment.hp_delta))
        builders["hp_gain"].add(_positive_part(segment.hp_delta))
        builders["max_hp_delta"].add(segment.max_hp_delta)
        builders["gold_delta"].add(segment.gold_delta)
        builders["potion_count_delta"].add(segment.potion_count_delta)

        tags = _segment_highlight_tags(segment)
        highlight_counts.update(tags)
        if tags:
            highlights.append(
                BattleRewardSegmentHighlight(
                    rollout_index=segment.rollout_index,
                    seed=segment.seed,
                    segment_index=segment.segment_index,
                    start_floor=segment.start_floor,
                    end_reason=segment.end_reason,
                    decision_count=segment.decision_count,
                    tags=tags,
                    hp_delta=segment.hp_delta,
                    max_hp_delta=segment.max_hp_delta,
                    gold_delta=segment.gold_delta,
                    potion_count_delta=segment.potion_count_delta,
                    action_kind_counts=segment.action_kind_counts,
                )
            )

    return _from_segment_report(
        segment_report,
        builders,
        highlight_counts=highlight_counts,
        highlights=sorted(highlights, key=_highlight_sort_key),
    )


def format_battle_reward_component_report(
    report: BattleRewardComponentReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format raw reward-component calibration for stderr."""

    average_decisions = (
        report.total_battle_decisions / report.segment_count
        if report.segment_count
        else 0.0
    )
    lines = [
        "Battle reward component calibration summary",
        "scope: raw components only; no reward weights, trainer, or environment",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"excluded non-combat driver steps: {report.excluded_non_combat_driver_steps}",
        f"total battle decisions: {report.total_battle_decisions}",
        f"average battle decisions per segment: {average_decisions:.2f}",
        (
            "battle_success_proxy: 1 for nonterminal_battle_exit or "
            "terminal_victory, 0 otherwise"
        ),
        "components:",
    ]

    for name in BATTLE_REWARD_COMPONENT_NAMES:
        stats = report.components.get(name, BattleRewardComponentStats())
        lines.append(f"  {name}: {_format_component_stats(stats)}")

    _append_counter(lines, "end reasons", report.end_reason_counts)
    _append_counter(lines, "rollout outcomes", report.rollout_outcome_counts)
    _append_counter(lines, "segment start floors", report.floor_counts)
    _append_counter(lines, "battle action kinds", report.action_kind_counts)
    _append_counter(lines, "highlight tags", report.highlight_counts)

    lines.append(f"highlighted segments (limit {detail_limit}):")
    if detail_limit <= 0:
        lines.append("  (disabled)")
    elif not report.highlights:
        lines.append("  (none)")
    else:
        for highlight in report.highlights[:detail_limit]:
            lines.append(f"  {_format_highlight(highlight)}")
        remaining = len(report.highlights) - detail_limit
        if remaining > 0:
            lines.append(f"  ... {remaining} more")

    lines.append("future signal gaps:")
    if report.future_signal_gaps:
        lines.extend(f"  {gap}" for gap in report.future_signal_gaps)
    else:
        lines.append("  (none)")

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _from_segment_report(
    segment_report: BattleSegmentReport,
    builders: dict[str, "_RewardComponentStatsBuilder"],
    *,
    highlight_counts: Counter[str],
    highlights: list[BattleRewardSegmentHighlight],
) -> BattleRewardComponentReport:
    return BattleRewardComponentReport(
        source_rollout_count=segment_report.source_rollout_count,
        segment_count=len(segment_report.segments),
        excluded_non_combat_driver_steps=segment_report.excluded_autopilot_steps,
        total_battle_decisions=segment_report.total_battle_decisions,
        components={name: builder.finish() for name, builder in builders.items()},
        end_reason_counts=segment_report.end_reason_counts,
        rollout_outcome_counts=segment_report.rollout_outcome_counts,
        floor_counts=segment_report.floor_counts,
        action_kind_counts=segment_report.action_kind_counts,
        highlight_counts=highlight_counts,
        highlights=highlights,
        problems=segment_report.problems,
    )


class _RewardComponentStatsBuilder:
    def __init__(self) -> None:
        self.samples = 0
        self.missing = 0
        self.total = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None
        self.nonzero_count = 0

    def add(self, value: float | None) -> None:
        if value is None:
            self.missing += 1
            return

        self.samples += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        if value != 0.0:
            self.nonzero_count += 1

    def finish(self) -> BattleRewardComponentStats:
        return BattleRewardComponentStats(
            samples=self.samples,
            missing=self.missing,
            total=self.total,
            minimum=self.minimum,
            maximum=self.maximum,
            nonzero_count=self.nonzero_count,
        )


def _indicator(value: bool) -> float:
    return 1.0 if value else 0.0


def _positive_part(value: float | None) -> float | None:
    if value is None:
        return None
    return max(value, 0.0)


def _negative_part(value: float | None) -> float | None:
    if value is None:
        return None
    return max(-value, 0.0)


def _segment_highlight_tags(segment: BattleSegment) -> tuple[str, ...]:
    tags: list[str] = []
    end_reason = str(getattr(segment, "end_reason", ""))
    if end_reason in {"terminal_loss", "terminal_victory", "truncated"}:
        tags.append(end_reason)
    if _nonzero(getattr(segment, "gold_delta", None)):
        tags.append("gold_delta")
    if _nonzero(getattr(segment, "max_hp_delta", None)):
        tags.append("max_hp_delta")
    if _nonzero(getattr(segment, "potion_count_delta", None)):
        tags.append("potion_count_delta")

    hp_delta = getattr(segment, "hp_delta", None)
    if isinstance(hp_delta, (int, float)) and hp_delta > 0:
        tags.append("hp_gain")
    return tuple(tags)


def _highlight_sort_key(
    highlight: BattleRewardSegmentHighlight,
) -> tuple[int, int, int]:
    priority = min(
        (_HIGHLIGHT_PRIORITY.get(tag, 99) for tag in highlight.tags),
        default=99,
    )
    return (priority, highlight.rollout_index, highlight.segment_index)


def _format_highlight(highlight: BattleRewardSegmentHighlight) -> str:
    actions = ", ".join(
        f"{kind}:{count}" for kind, count in highlight.action_kind_counts.most_common()
    )
    if not actions:
        actions = "(none)"
    seed = str(highlight.seed) if highlight.seed is not None else "(default)"
    return (
        f"rollout={highlight.rollout_index} seed={seed} "
        f"segment={highlight.segment_index} floor={_optional_float(highlight.start_floor)} "
        f"end={highlight.end_reason} decisions={highlight.decision_count} "
        f"tags={','.join(highlight.tags)} hp_delta={_optional_float(highlight.hp_delta)} "
        f"max_hp_delta={_optional_float(highlight.max_hp_delta)} "
        f"gold_delta={_optional_float(highlight.gold_delta)} "
        f"potion_count_delta={_optional_float(highlight.potion_count_delta)} "
        f"actions={actions}"
    )


def _nonzero(value: object) -> bool:
    return isinstance(value, (int, float)) and float(value) != 0.0


def _format_component_stats(stats: BattleRewardComponentStats) -> str:
    average = stats.total / stats.samples if stats.samples else 0.0
    return (
        f"samples={stats.samples} missing={stats.missing} "
        f"total={stats.total:.2f} average={average:.2f} "
        f"min={_optional_float(stats.minimum)} max={_optional_float(stats.maximum)} "
        f"nonzero={stats.nonzero_count}"
    )


def _optional_float(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value)


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
