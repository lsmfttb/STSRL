"""Pre-training simulator episode evaluation.

This module runs bounded policy rollouts and summarizes simulator-exposed
outcomes. It does not implement RL, a trainer, a Gymnasium environment, or
Slay the Spire mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import SimulatorAdapter
from sts_combat_rl.sim.policy import DecisionPolicy
from sts_combat_rl.sim.policy_rollout import collect_policy_simulator_rollout
from sts_combat_rl.sim.controlled_run import ControlledRun


@dataclass(frozen=True)
class EpisodeSummary:
    """One bounded simulator episode summary."""

    seed: int | None
    requested_steps: int
    collected_steps: int
    terminal: bool
    outcome: str
    outcome_value: float
    start_screen_state: str
    final_screen_state: str
    start_floor: float | None = None
    final_floor: float | None = None
    start_hp: float | None = None
    final_hp: float | None = None
    start_gold: float | None = None
    final_gold: float | None = None
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyEpisodeEvaluationReport:
    """Aggregate summary for several bounded policy episodes."""

    policy_name: str
    requested_steps_per_episode: int
    episodes: list[EpisodeSummary] = field(default_factory=list)
    terminal_episodes: int = 0
    total_steps: int = 0
    outcome_value_total: float = 0.0
    outcome_counts: Counter[str] = field(default_factory=Counter)
    final_screen_state_counts: Counter[str] = field(default_factory=Counter)
    final_floor_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def run_policy_episode_evaluation(
    adapter: SimulatorAdapter,
    policy: DecisionPolicy,
    *,
    seeds: Iterable[int | None],
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> PolicyEpisodeEvaluationReport:
    """Run bounded policy episodes and aggregate outcome/progress statistics."""

    episode_summaries: list[EpisodeSummary] = []
    problems: list[str] = []
    terminal_episodes = 0
    total_steps = 0
    outcome_value_total = 0.0
    outcome_counts: Counter[str] = Counter()
    final_screen_state_counts: Counter[str] = Counter()
    final_floor_counts: Counter[str] = Counter()
    chosen_action_kind_counts: Counter[str] = Counter()

    for seed in seeds:
        rollout = collect_policy_simulator_rollout(
            adapter,
            policy,
            seed=seed,
            max_steps=max_steps,
            action_space=action_space,
        )
        summary = summarize_rollout_episode(rollout)
        episode_summaries.append(summary)
        total_steps += summary.collected_steps
        outcome_value_total += summary.outcome_value
        outcome_counts[summary.outcome] += 1
        final_screen_state_counts[summary.final_screen_state] += 1
        final_floor_counts[_optional_number_label(summary.final_floor)] += 1
        chosen_action_kind_counts.update(summary.chosen_action_kind_counts)
        if summary.terminal:
            terminal_episodes += 1
        problems.extend(
            f"seed {_seed_label(seed)}: {problem}" for problem in summary.problems
        )

    return PolicyEpisodeEvaluationReport(
        policy_name=policy.name,
        requested_steps_per_episode=max_steps,
        episodes=episode_summaries,
        terminal_episodes=terminal_episodes,
        total_steps=total_steps,
        outcome_value_total=outcome_value_total,
        outcome_counts=outcome_counts,
        final_screen_state_counts=final_screen_state_counts,
        final_floor_counts=final_floor_counts,
        chosen_action_kind_counts=chosen_action_kind_counts,
        problems=problems,
    )


def summarize_rollout_episode(rollout: ControlledRun) -> EpisodeSummary:
    """Convert one policy rollout into an episode summary."""

    initial_raw = _mapping(rollout.initial_raw)
    final_raw = _mapping(rollout.final_raw)
    chosen_action_kind_counts = Counter(
        step.chosen_action_kind for step in rollout.steps
    )

    return EpisodeSummary(
        seed=rollout.seed,
        requested_steps=rollout.requested_steps,
        collected_steps=len(rollout.steps),
        terminal=rollout.terminal,
        outcome=rollout.outcome,
        outcome_value=outcome_value(rollout.outcome),
        start_screen_state=str(initial_raw.get("screen_state", "(none)")),
        final_screen_state=str(final_raw.get("screen_state", "(none)")),
        start_floor=_first_number(initial_raw, "floor_num", "floor"),
        final_floor=_first_number(final_raw, "floor_num", "floor"),
        start_hp=_first_number(initial_raw, "cur_hp", "current_hp"),
        final_hp=_first_number(final_raw, "cur_hp", "current_hp"),
        start_gold=_first_number(initial_raw, "gold"),
        final_gold=_first_number(final_raw, "gold"),
        chosen_action_kind_counts=chosen_action_kind_counts,
        problems=list(rollout.problems),
    )


def outcome_value(outcome: object) -> float:
    """Map simulator terminal outcome labels into a narrow evaluation value."""

    normalized = str(outcome).upper()
    if normalized in {"PLAYER_VICTORY", "VICTORY", "WIN", "PLAYER_WIN"}:
        return 1.0
    if normalized in {"PLAYER_LOSS", "LOSS", "DEFEAT", "PLAYER_DEFEAT"}:
        return -1.0
    return 0.0


def format_policy_episode_evaluation_report(
    report: PolicyEpisodeEvaluationReport,
) -> str:
    """Format episode statistics for stderr."""

    episode_count = len(report.episodes)
    average_steps = report.total_steps / episode_count if episode_count else 0.0
    average_outcome_value = (
        report.outcome_value_total / episode_count if episode_count else 0.0
    )

    lines = [
        "Policy episode evaluation summary",
        f"policy: {report.policy_name}",
        f"episodes: {episode_count}",
        f"requested steps per episode: {report.requested_steps_per_episode}",
        f"terminal episodes: {report.terminal_episodes}",
        f"total collected steps: {report.total_steps}",
        f"average collected steps: {average_steps:.2f}",
        f"outcome value total: {report.outcome_value_total:.2f}",
        f"average outcome value: {average_outcome_value:.2f}",
    ]
    _append_counter(lines, "outcomes", report.outcome_counts)
    _append_counter(lines, "final screen states", report.final_screen_state_counts)
    _append_counter(lines, "final floors", report.final_floor_counts)
    _append_counter(lines, "chosen action kinds", report.chosen_action_kind_counts)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _first_number(
    data: Mapping[str, Any],
    *keys: str,
) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_number_label(value: float | None) -> str:
    if value is None:
        return "(none)"
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _seed_label(seed: int | None) -> str:
    return str(seed) if seed is not None else "(default)"


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
