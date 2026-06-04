"""Segment-level battle reward design drafts.

This module deliberately stays framework-neutral. It scores already-collected
battle segments for calibration only; it does not implement RL, a Gymnasium
environment, or a trainer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.battle_agent import (
    BattleAgentRollout,
    BattleSegment,
    build_battle_segment_report,
)


BATTLE_REWARD_PRESETS = ("battle-v0",)
_BATTLE_SUCCESS_PROXY_END_REASONS = frozenset(
    {"nonterminal_battle_exit", "terminal_victory"}
)
_REWARD_COMPONENT_ORDER = (
    "battle_success_proxy",
    "terminal_loss",
    "truncated",
    "hp_delta",
    "decision_count",
    "max_hp_delta",
    "gold_delta",
    "potion_count_delta",
)
_LONG_TERM_LEDGER_COMPONENTS = (
    "max_hp_delta",
    "gold_delta",
    "potion_count_delta",
)


@dataclass(frozen=True)
class BattleRewardWeights:
    """Weights for a segment-level battle reward draft."""

    name: str = "battle-v0"
    battle_success_proxy: float = 1.0
    terminal_loss: float = -1.0
    truncated: float = -0.25
    hp_delta: float = 0.01
    decision_count: float = -0.001
    max_hp_delta: float = 0.0
    gold_delta: float = 0.0
    potion_count_delta: float = 0.0
    notes: tuple[str, ...] = (
        "Segment-level draft only; no trainer or environment.",
        "HP delta includes any simulator-visible battle-end healing.",
        "Long-term resource deltas are ledgered but have zero default weight.",
    )

    @classmethod
    def battle_v0(cls) -> "BattleRewardWeights":
        """Return the first no-potion battle reward draft."""

        return cls()


@dataclass(frozen=True)
class BattleRewardScoreStats:
    """Aggregate score statistics for a reward draft."""

    samples: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class BattleRewardSegmentScore:
    """One scored battle segment with raw ledger components preserved."""

    rollout_index: int
    seed: int | None
    segment_index: int
    start_step_index: int
    end_step_index: int
    start_floor: float | None
    end_reason: str
    decision_count: int
    reward: float
    contributions: dict[str, float] = field(default_factory=dict)
    raw_components: dict[str, float | None] = field(default_factory=dict)
    action_kind_counts: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class BattleRewardDesignReport:
    """Aggregate calibration report for one reward draft."""

    weights: BattleRewardWeights
    source_rollout_count: int
    segment_count: int
    excluded_non_combat_driver_steps: int
    total_battle_decisions: int
    score_stats: BattleRewardScoreStats
    scores: list[BattleRewardSegmentScore] = field(default_factory=list)
    contribution_totals: Counter[str] = field(default_factory=Counter)
    long_term_ledger_totals: Counter[str] = field(default_factory=Counter)
    missing_component_counts: Counter[str] = field(default_factory=Counter)
    end_reason_counts: Counter[str] = field(default_factory=Counter)
    floor_counts: Counter[str] = field(default_factory=Counter)
    action_kind_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def battle_reward_weights_from_preset(preset: str) -> BattleRewardWeights:
    """Build reward weights for a named preset."""

    if preset == "battle-v0":
        return BattleRewardWeights.battle_v0()
    raise ValueError(f"unknown battle reward preset: {preset}")


def build_battle_reward_design_report(
    rollouts: list[BattleAgentRollout],
    weights: BattleRewardWeights | None = None,
) -> BattleRewardDesignReport:
    """Score battle segments with a draft reward, without running training."""

    active_weights = weights or BattleRewardWeights.battle_v0()
    segment_report = build_battle_segment_report(rollouts)
    scores: list[BattleRewardSegmentScore] = []
    contribution_totals: Counter[str] = Counter()
    long_term_ledger_totals: Counter[str] = Counter()
    missing_component_counts: Counter[str] = Counter()
    stats_builder = _ScoreStatsBuilder()

    for segment in segment_report.segments:
        score = _score_segment(segment, active_weights, missing_component_counts)
        scores.append(score)
        stats_builder.add(score.reward)
        contribution_totals.update(score.contributions)
        for name in _LONG_TERM_LEDGER_COMPONENTS:
            value = score.raw_components.get(name)
            if value is not None:
                long_term_ledger_totals[name] += value

    return BattleRewardDesignReport(
        weights=active_weights,
        source_rollout_count=segment_report.source_rollout_count,
        segment_count=len(segment_report.segments),
        excluded_non_combat_driver_steps=segment_report.excluded_autopilot_steps,
        total_battle_decisions=segment_report.total_battle_decisions,
        score_stats=stats_builder.finish(),
        scores=scores,
        contribution_totals=contribution_totals,
        long_term_ledger_totals=long_term_ledger_totals,
        missing_component_counts=missing_component_counts,
        end_reason_counts=segment_report.end_reason_counts,
        floor_counts=segment_report.floor_counts,
        action_kind_counts=segment_report.action_kind_counts,
        problems=segment_report.problems,
    )


def format_battle_reward_design_report(
    report: BattleRewardDesignReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format a reward design draft report for stderr."""

    average_reward = (
        report.score_stats.total / report.score_stats.samples
        if report.score_stats.samples
        else 0.0
    )
    lines = [
        "Battle reward design draft summary",
        "scope: segment-level reward draft only; no trainer or environment",
        f"reward preset: {report.weights.name}",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"excluded non-combat driver steps: {report.excluded_non_combat_driver_steps}",
        f"total battle decisions: {report.total_battle_decisions}",
        (
            "reward stats: "
            f"samples={report.score_stats.samples} "
            f"total={report.score_stats.total:.3f} "
            f"average={average_reward:.3f} "
            f"min={_optional_float(report.score_stats.minimum)} "
            f"max={_optional_float(report.score_stats.maximum)}"
        ),
        "weights:",
    ]

    for name in _REWARD_COMPONENT_ORDER:
        lines.append(f"  {name}: {_weight_value(report.weights, name):.4f}")

    _append_counter(lines, "contribution totals", report.contribution_totals)
    _append_counter(lines, "long-term ledger totals", report.long_term_ledger_totals)
    _append_counter(lines, "missing components", report.missing_component_counts)
    _append_counter(lines, "end reasons", report.end_reason_counts)
    _append_counter(lines, "segment start floors", report.floor_counts)
    _append_counter(lines, "battle action kinds", report.action_kind_counts)

    lines.append(f"lowest-reward segments (limit {detail_limit}):")
    _append_score_details(lines, _lowest_scores(report.scores), detail_limit)
    lines.append(f"highest-reward segments (limit {detail_limit}):")
    _append_score_details(lines, _highest_scores(report.scores), detail_limit)

    lines.append("notes:")
    if report.weights.notes:
        lines.extend(f"  {note}" for note in report.weights.notes)
    else:
        lines.append("  (none)")

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _score_segment(
    segment: BattleSegment,
    weights: BattleRewardWeights,
    missing_component_counts: Counter[str],
) -> BattleRewardSegmentScore:
    raw_components = {
        "battle_success_proxy": _indicator(
            segment.end_reason in _BATTLE_SUCCESS_PROXY_END_REASONS
        ),
        "terminal_loss": _indicator(segment.end_reason == "terminal_loss"),
        "truncated": _indicator(segment.end_reason == "truncated"),
        "hp_delta": segment.hp_delta,
        "decision_count": float(segment.decision_count),
        "max_hp_delta": segment.max_hp_delta,
        "gold_delta": segment.gold_delta,
        "potion_count_delta": segment.potion_count_delta,
    }
    contributions: dict[str, float] = {}
    reward = 0.0
    for name in _REWARD_COMPONENT_ORDER:
        value = raw_components[name]
        if value is None:
            missing_component_counts[name] += 1
            contributions[name] = 0.0
            continue

        contribution = _weight_value(weights, name) * value
        contributions[name] = contribution
        reward += contribution

    return BattleRewardSegmentScore(
        rollout_index=segment.rollout_index,
        seed=segment.seed,
        segment_index=segment.segment_index,
        start_step_index=segment.start_step_index,
        end_step_index=segment.end_step_index,
        start_floor=segment.start_floor,
        end_reason=segment.end_reason,
        decision_count=segment.decision_count,
        reward=reward,
        contributions=contributions,
        raw_components=raw_components,
        action_kind_counts=segment.action_kind_counts,
    )


class _ScoreStatsBuilder:
    def __init__(self) -> None:
        self.samples = 0
        self.total = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None

    def add(self, value: float) -> None:
        self.samples += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def finish(self) -> BattleRewardScoreStats:
        return BattleRewardScoreStats(
            samples=self.samples,
            total=self.total,
            minimum=self.minimum,
            maximum=self.maximum,
        )


def _lowest_scores(
    scores: list[BattleRewardSegmentScore],
) -> list[BattleRewardSegmentScore]:
    return sorted(scores, key=lambda score: score.reward)


def _highest_scores(
    scores: list[BattleRewardSegmentScore],
) -> list[BattleRewardSegmentScore]:
    return sorted(scores, key=lambda score: score.reward, reverse=True)


def _append_score_details(
    lines: list[str],
    scores: list[BattleRewardSegmentScore],
    detail_limit: int,
) -> None:
    if detail_limit <= 0:
        lines.append("  (disabled)")
        return
    if not scores:
        lines.append("  (none)")
        return

    for score in scores[:detail_limit]:
        lines.append(f"  {_format_score(score)}")
    remaining = len(scores) - detail_limit
    if remaining > 0:
        lines.append(f"  ... {remaining} more")


def _format_score(score: BattleRewardSegmentScore) -> str:
    top_contributions = ", ".join(
        f"{name}:{value:.3f}"
        for name, value in sorted(
            score.contributions.items(),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
        if value != 0.0
    )
    if not top_contributions:
        top_contributions = "(none)"
    return (
        f"rollout={score.rollout_index} seed={_optional_seed(score.seed)} "
        f"segment={score.segment_index} floor={_optional_float(score.start_floor)} "
        f"end={score.end_reason} decisions={score.decision_count} "
        f"reward={score.reward:.3f} contributions={top_contributions} "
        f"hp_delta={_optional_float(score.raw_components.get('hp_delta'))} "
        f"max_hp_delta={_optional_float(score.raw_components.get('max_hp_delta'))} "
        f"gold_delta={_optional_float(score.raw_components.get('gold_delta'))} "
        f"potion_count_delta={_optional_float(score.raw_components.get('potion_count_delta'))}"
    )


def _weight_value(weights: BattleRewardWeights, name: str) -> float:
    return float(getattr(weights, name))


def _indicator(value: bool) -> float:
    return 1.0 if value else 0.0


def _optional_seed(seed: int | None) -> str:
    return str(seed) if seed is not None else "(default)"


def _optional_float(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return str(value)


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        if isinstance(count, float):
            lines.append(f"  {key}: {count:.3f}")
        else:
            lines.append(f"  {key}: {count}")
