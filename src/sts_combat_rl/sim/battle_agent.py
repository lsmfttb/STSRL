"""Battle-agent-only simulator sweep helpers.

The battle agent only selects actions in battle states. Non-combat states are
advanced by a separate driver so simulator rollouts can reach more battles
without making map/reward/shop navigation part of the agent contract.

The authoritative controlled-run executor in ``controlled_run.py`` owns the
select/validate/step loop. This module provides the routed controller that
separates battle from non-combat decisions, and batch/segment/report builders
that consume :class:`ControlledRun` results.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    ControlledRunStep,
    execute_controlled_run,
)
from sts_combat_rl.sim.contract import SimulatorAdapter
from sts_combat_rl.sim.online_controller import (
    PolicyController,
    RoutedRunController,
)
from sts_combat_rl.sim.policy import DecisionPolicy


BATTLE_AGENT_CONTROLLER = "battle_agent"
NON_COMBAT_DRIVER_CONTROLLER = "non_combat_driver"
AUTOPILOT_CONTROLLER = NON_COMBAT_DRIVER_CONTROLLER


@dataclass(frozen=True)
class BattleAgentEpisodeSummary:
    """Battle-only summary for one bounded simulator episode."""

    seed: int | None
    requested_steps: int
    collected_steps: int
    terminal: bool
    outcome: str
    start_screen_state: str
    final_screen_state: str
    battle_decisions: int
    autopilot_decisions: int
    final_floor: float | None = None
    battle_action_kind_counts: Counter[str] = field(default_factory=Counter)
    autopilot_action_kind_counts: Counter[str] = field(default_factory=Counter)
    battle_legal_action_count_counts: Counter[str] = field(default_factory=Counter)
    battle_eligible_action_count_counts: Counter[str] = field(default_factory=Counter)
    battle_snapshot_feature_size_counts: Counter[str] = field(default_factory=Counter)
    battle_action_feature_size_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BattleAgentSweepReport:
    """Aggregate battle-agent-only seed sweep report."""

    battle_policy_name: str
    autopilot_policy_name: str
    requested_steps_per_episode: int
    episodes: list[BattleAgentEpisodeSummary] = field(default_factory=list)
    terminal_episodes: int = 0
    total_steps: int = 0
    total_battle_decisions: int = 0
    total_autopilot_decisions: int = 0
    outcome_counts: Counter[str] = field(default_factory=Counter)
    final_screen_state_counts: Counter[str] = field(default_factory=Counter)
    final_floor_counts: Counter[str] = field(default_factory=Counter)
    battle_action_kind_counts: Counter[str] = field(default_factory=Counter)
    autopilot_action_kind_counts: Counter[str] = field(default_factory=Counter)
    battle_legal_action_count_counts: Counter[str] = field(default_factory=Counter)
    battle_eligible_action_count_counts: Counter[str] = field(default_factory=Counter)
    battle_snapshot_feature_size_counts: Counter[str] = field(default_factory=Counter)
    battle_action_feature_size_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BattleDecisionBatch:
    """Framework-neutral decision batch containing only battle-agent steps."""

    decision_batch: DecisionBatch
    source_rollout_count: int
    excluded_autopilot_steps: int = 0


@dataclass(frozen=True)
class BattleSegment:
    """One contiguous battle-agent-controlled combat segment."""

    rollout_index: int
    seed: int | None
    segment_index: int
    start_step_index: int
    end_step_index: int
    decision_count: int
    end_reason: str
    rollout_outcome: str
    start_floor: float | None = None
    end_floor: float | None = None
    start_hp: float | None = None
    end_hp: float | None = None
    hp_delta: float | None = None
    start_max_hp: float | None = None
    end_max_hp: float | None = None
    max_hp_delta: float | None = None
    start_gold: float | None = None
    end_gold: float | None = None
    gold_delta: float | None = None
    start_potion_count: float | None = None
    end_potion_count: float | None = None
    potion_count_delta: float | None = None
    action_kind_counts: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class BattleSegmentReport:
    """Aggregate combat-segment boundary calibration report."""

    source_rollout_count: int
    segments: list[BattleSegment] = field(default_factory=list)
    excluded_autopilot_steps: int = 0
    total_battle_decisions: int = 0
    end_reason_counts: Counter[str] = field(default_factory=Counter)
    rollout_outcome_counts: Counter[str] = field(default_factory=Counter)
    decision_count_counts: Counter[str] = field(default_factory=Counter)
    floor_counts: Counter[str] = field(default_factory=Counter)
    action_kind_counts: Counter[str] = field(default_factory=Counter)
    hp_delta_total: float = 0.0
    hp_delta_count: int = 0
    problems: list[str] = field(default_factory=list)


def collect_battle_agent_rollout(
    adapter: SimulatorAdapter,
    battle_policy: DecisionPolicy,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    autopilot_policy: DecisionPolicy | None = None,
) -> ControlledRun:
    """Collect a bounded rollout where only battle states use battle_policy.

    ``autopilot_policy`` must be supplied explicitly. A dataset helper may not
    silently construct a default battle or non-combat controller.

    Each call constructs fresh ``PolicyController`` instances so that each run
    gets independent provenance. Stateful policies (e.g. ``RandomEligiblePolicy``)
    publish their starting RNG state in provenance, so the same policy object
    reused across sweep iterations gets a different identity per run.
    """

    if autopilot_policy is None:
        raise ValueError(
            "autopilot_policy is required; pass an explicit non-combat driver "
            "policy (e.g. PreferredKindPolicy())"
        )
    # Construct fresh controllers per run so provenance captures current
    # stateful-policy state (e.g. starting RNG position).
    controller = RoutedRunController(
        battle=PolicyController(battle_policy),
        non_combat=PolicyController(autopilot_policy),
    )
    return execute_controlled_run(
        adapter,
        controller,
        seed=seed,
        max_steps=max_steps,
        action_space=action_space,
    )


def run_battle_agent_sweep(
    adapter: SimulatorAdapter,
    battle_policy: DecisionPolicy,
    *,
    seeds: Iterable[int | None],
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    autopilot_policy: DecisionPolicy | None = None,
) -> BattleAgentSweepReport:
    """Run a battle-agent-only seed sweep without training.

    ``autopilot_policy`` must be supplied explicitly. A dataset helper may not
    silently construct a default battle or non-combat controller.
    """

    if autopilot_policy is None:
        raise ValueError(
            "autopilot_policy is required; pass an explicit non-combat driver "
            "policy (e.g. PreferredKindPolicy())"
        )
    summaries: list[BattleAgentEpisodeSummary] = []
    problems: list[str] = []
    terminal_episodes = 0
    total_steps = 0
    total_battle_decisions = 0
    total_autopilot_decisions = 0
    outcome_counts: Counter[str] = Counter()
    final_screen_state_counts: Counter[str] = Counter()
    final_floor_counts: Counter[str] = Counter()
    battle_action_kind_counts: Counter[str] = Counter()
    autopilot_action_kind_counts: Counter[str] = Counter()
    battle_legal_action_count_counts: Counter[str] = Counter()
    battle_eligible_action_count_counts: Counter[str] = Counter()
    battle_snapshot_feature_size_counts: Counter[str] = Counter()
    battle_action_feature_size_counts: Counter[str] = Counter()

    for seed in seeds:
        rollout = collect_battle_agent_rollout(
            adapter,
            battle_policy,
            seed=seed,
            max_steps=max_steps,
            action_space=action_space,
            autopilot_policy=autopilot_policy,
        )
        summary = summarize_battle_agent_episode(rollout)
        summaries.append(summary)
        total_steps += summary.collected_steps
        total_battle_decisions += summary.battle_decisions
        total_autopilot_decisions += summary.autopilot_decisions
        outcome_counts[summary.outcome] += 1
        final_screen_state_counts[summary.final_screen_state] += 1
        final_floor_counts[_optional_number_label(summary.final_floor)] += 1
        battle_action_kind_counts.update(summary.battle_action_kind_counts)
        autopilot_action_kind_counts.update(summary.autopilot_action_kind_counts)
        battle_legal_action_count_counts.update(
            summary.battle_legal_action_count_counts
        )
        battle_eligible_action_count_counts.update(
            summary.battle_eligible_action_count_counts
        )
        battle_snapshot_feature_size_counts.update(
            summary.battle_snapshot_feature_size_counts
        )
        battle_action_feature_size_counts.update(
            summary.battle_action_feature_size_counts
        )
        if summary.terminal:
            terminal_episodes += 1
        problems.extend(
            f"seed {_seed_label(seed)}: {problem}" for problem in summary.problems
        )

    return BattleAgentSweepReport(
        battle_policy_name=battle_policy.name,
        autopilot_policy_name=autopilot_policy.name,
        requested_steps_per_episode=max_steps,
        episodes=summaries,
        terminal_episodes=terminal_episodes,
        total_steps=total_steps,
        total_battle_decisions=total_battle_decisions,
        total_autopilot_decisions=total_autopilot_decisions,
        outcome_counts=outcome_counts,
        final_screen_state_counts=final_screen_state_counts,
        final_floor_counts=final_floor_counts,
        battle_action_kind_counts=battle_action_kind_counts,
        autopilot_action_kind_counts=autopilot_action_kind_counts,
        battle_legal_action_count_counts=battle_legal_action_count_counts,
        battle_eligible_action_count_counts=battle_eligible_action_count_counts,
        battle_snapshot_feature_size_counts=battle_snapshot_feature_size_counts,
        battle_action_feature_size_counts=battle_action_feature_size_counts,
        problems=problems,
    )


def build_battle_decision_batch(
    rollouts: list[ControlledRun],
) -> BattleDecisionBatch:
    """Build a validated decision batch from only battle-agent decisions."""

    examples: list[DecisionExample] = []
    problems: list[str] = []
    snapshot_feature_size: int | None = None
    action_feature_size: int | None = None
    terminal_rollouts = 0
    excluded_autopilot_steps = 0

    for rollout_index, rollout in enumerate(rollouts):
        if rollout.terminal:
            terminal_rollouts += 1
        problems.extend(
            f"rollout {rollout_index}: {problem}" for problem in rollout.problems
        )

        for step in rollout.steps:
            if step.controller_role != BATTLE_AGENT_CONTROLLER:
                excluded_autopilot_steps += 1
                continue

            snapshot_feature_size = _stable_size(
                snapshot_feature_size,
                len(step.snapshot_features),
                f"rollout {rollout_index} step {step.step_index} snapshot",
                problems,
            )
            for action_index, action_features in enumerate(step.legal_action_features):
                action_feature_size = _stable_size(
                    action_feature_size,
                    len(action_features),
                    (
                        f"rollout {rollout_index} step {step.step_index} "
                        f"action {action_index}"
                    ),
                    problems,
                )
            _validate_step_indices(rollout_index, step, problems)
            examples.append(
                DecisionExample(
                    rollout_index=rollout_index,
                    seed=rollout.seed,
                    step_index=step.step_index,
                    screen_state=step.screen_state,
                    snapshot_features=step.snapshot_features,
                    legal_action_features=step.legal_action_features,
                    legal_action_kinds=step.legal_action_kinds,
                    eligible_action_indices=step.eligible_action_indices,
                    chosen_action_index=step.chosen_action_index,
                    chosen_action_id=step.chosen_action_id,
                    legal_action_identities=list(step.legal_action_identities),
                    chosen_action_identity=dict(step.chosen_action_identity),
                    chosen_action_kind=step.chosen_action_kind,
                    terminal_after_step=step.terminal_after_step,
                    controller_provenance=(
                        step.provenance.to_dict() if step.provenance is not None else {}
                    ),
                    source_metadata=dict(step.source_metadata),
                )
            )

    return BattleDecisionBatch(
        decision_batch=DecisionBatch(
            examples=examples,
            snapshot_feature_size=snapshot_feature_size,
            action_feature_size=action_feature_size,
            rollout_count=len(rollouts),
            terminal_rollouts=terminal_rollouts,
            problems=problems,
        ),
        source_rollout_count=len(rollouts),
        excluded_autopilot_steps=excluded_autopilot_steps,
    )


def build_battle_segment_report(
    rollouts: list[ControlledRun],
) -> BattleSegmentReport:
    """Build combat-segment summaries without choosing a reward function."""

    segments: list[BattleSegment] = []
    problems: list[str] = []
    excluded_autopilot_steps = 0
    total_battle_decisions = 0
    end_reason_counts: Counter[str] = Counter()
    rollout_outcome_counts: Counter[str] = Counter()
    decision_count_counts: Counter[str] = Counter()
    floor_counts: Counter[str] = Counter()
    action_kind_counts: Counter[str] = Counter()
    hp_delta_total = 0.0
    hp_delta_count = 0

    for rollout_index, rollout in enumerate(rollouts):
        problems.extend(
            f"rollout {rollout_index}: {problem}" for problem in rollout.problems
        )
        active_steps: list[ControlledRunStep] = []
        segment_index = 0
        for step in rollout.steps:
            if step.controller_role == BATTLE_AGENT_CONTROLLER:
                active_steps.append(step)
                if step.terminal_after_step:
                    segment = _battle_segment(
                        rollout_index,
                        rollout,
                        segment_index,
                        active_steps,
                        _terminal_end_reason(rollout.outcome),
                    )
                    segments.append(segment)
                    segment_index += 1
                    active_steps = []
                continue

            excluded_autopilot_steps += 1
            if active_steps:
                segment = _battle_segment(
                    rollout_index,
                    rollout,
                    segment_index,
                    active_steps,
                    "nonterminal_battle_exit",
                )
                segments.append(segment)
                segment_index += 1
                active_steps = []

        if active_steps:
            segment = _battle_segment(
                rollout_index,
                rollout,
                segment_index,
                active_steps,
                "truncated",
            )
            segments.append(segment)

    for segment in segments:
        total_battle_decisions += segment.decision_count
        end_reason_counts[segment.end_reason] += 1
        rollout_outcome_counts[segment.rollout_outcome] += 1
        decision_count_counts[str(segment.decision_count)] += 1
        floor_counts[_optional_number_label(segment.start_floor)] += 1
        action_kind_counts.update(segment.action_kind_counts)
        if segment.hp_delta is not None:
            hp_delta_total += segment.hp_delta
            hp_delta_count += 1

    return BattleSegmentReport(
        source_rollout_count=len(rollouts),
        segments=segments,
        excluded_autopilot_steps=excluded_autopilot_steps,
        total_battle_decisions=total_battle_decisions,
        end_reason_counts=end_reason_counts,
        rollout_outcome_counts=rollout_outcome_counts,
        decision_count_counts=decision_count_counts,
        floor_counts=floor_counts,
        action_kind_counts=action_kind_counts,
        hp_delta_total=hp_delta_total,
        hp_delta_count=hp_delta_count,
        problems=problems,
    )


def summarize_battle_agent_episode(
    rollout: ControlledRun,
) -> BattleAgentEpisodeSummary:
    """Summarize battle-agent decisions from one bounded rollout."""

    initial_raw = _mapping(rollout.initial_raw)
    final_raw = _mapping(rollout.final_raw)
    battle_steps = [
        step
        for step in rollout.steps
        if step.controller_role == BATTLE_AGENT_CONTROLLER
    ]
    autopilot_steps = [
        step for step in rollout.steps if step.controller_role == AUTOPILOT_CONTROLLER
    ]
    battle_action_feature_size_counts: Counter[str] = Counter(
        str(len(features))
        for step in battle_steps
        for features in step.legal_action_features
    )

    return BattleAgentEpisodeSummary(
        seed=rollout.seed,
        requested_steps=rollout.requested_steps,
        collected_steps=len(rollout.steps),
        terminal=rollout.terminal,
        outcome=rollout.outcome,
        start_screen_state=str(initial_raw.get("screen_state", "(none)")),
        final_screen_state=str(final_raw.get("screen_state", "(none)")),
        battle_decisions=len(battle_steps),
        autopilot_decisions=len(autopilot_steps),
        final_floor=_first_number(final_raw, "floor_num", "floor"),
        battle_action_kind_counts=Counter(
            step.chosen_action_kind for step in battle_steps
        ),
        autopilot_action_kind_counts=Counter(
            step.chosen_action_kind for step in autopilot_steps
        ),
        battle_legal_action_count_counts=Counter(
            str(len(step.legal_action_features)) for step in battle_steps
        ),
        battle_eligible_action_count_counts=Counter(
            str(len(step.eligible_action_indices)) for step in battle_steps
        ),
        battle_snapshot_feature_size_counts=Counter(
            str(len(step.snapshot_features)) for step in battle_steps
        ),
        battle_action_feature_size_counts=battle_action_feature_size_counts,
        problems=list(rollout.problems),
    )


def format_battle_agent_sweep_report(report: BattleAgentSweepReport) -> str:
    """Format a battle-agent-only seed sweep report for stderr."""

    episode_count = len(report.episodes)
    average_steps = report.total_steps / episode_count if episode_count else 0.0
    average_battle_decisions = (
        report.total_battle_decisions / episode_count if episode_count else 0.0
    )
    average_autopilot_decisions = (
        report.total_autopilot_decisions / episode_count if episode_count else 0.0
    )

    lines = [
        "Battle agent seed sweep summary",
        f"battle policy: {report.battle_policy_name}",
        f"non-combat driver policy: {report.autopilot_policy_name}",
        f"episodes: {episode_count}",
        f"requested steps per episode: {report.requested_steps_per_episode}",
        f"terminal episodes: {report.terminal_episodes}",
        f"total collected steps: {report.total_steps}",
        f"total battle decisions: {report.total_battle_decisions}",
        f"total non-combat driver decisions: {report.total_autopilot_decisions}",
        f"average collected steps: {average_steps:.2f}",
        f"average battle decisions: {average_battle_decisions:.2f}",
        f"average non-combat driver decisions: {average_autopilot_decisions:.2f}",
    ]
    _append_counter(lines, "outcomes", report.outcome_counts)
    _append_counter(lines, "final screen states", report.final_screen_state_counts)
    _append_counter(lines, "final floors", report.final_floor_counts)
    _append_counter(lines, "battle action kinds", report.battle_action_kind_counts)
    _append_counter(
        lines,
        "non-combat driver action kinds",
        report.autopilot_action_kind_counts,
    )
    _append_counter(
        lines,
        "battle legal action counts",
        report.battle_legal_action_count_counts,
    )
    _append_counter(
        lines,
        "battle eligible action counts",
        report.battle_eligible_action_count_counts,
    )
    _append_counter(
        lines,
        "battle snapshot feature sizes",
        report.battle_snapshot_feature_size_counts,
    )
    _append_counter(
        lines,
        "battle action feature sizes",
        report.battle_action_feature_size_counts,
    )

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_battle_segment_report(report: BattleSegmentReport) -> str:
    """Format combat-segment boundary calibration for stderr."""

    segment_count = len(report.segments)
    average_decisions = (
        report.total_battle_decisions / segment_count if segment_count else 0.0
    )
    average_hp_delta = (
        report.hp_delta_total / report.hp_delta_count if report.hp_delta_count else 0.0
    )

    lines = [
        "Battle segment calibration summary",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {segment_count}",
        f"excluded non-combat driver steps: {report.excluded_autopilot_steps}",
        f"total battle decisions: {report.total_battle_decisions}",
        f"average battle decisions per segment: {average_decisions:.2f}",
        f"hp delta samples: {report.hp_delta_count}",
        f"average hp delta: {average_hp_delta:.2f}",
    ]
    _append_counter(lines, "end reasons", report.end_reason_counts)
    _append_counter(lines, "rollout outcomes", report.rollout_outcome_counts)
    _append_counter(lines, "segment decision counts", report.decision_count_counts)
    _append_counter(lines, "segment start floors", report.floor_counts)
    _append_counter(lines, "battle action kinds", report.action_kind_counts)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_battle_decision_batch_report(batch: BattleDecisionBatch) -> str:
    """Format a battle-only decision batch report for stderr."""

    decision_batch = batch.decision_batch
    screen_states = Counter(example.screen_state for example in decision_batch.examples)
    legal_action_counts = Counter(
        str(len(example.legal_action_features)) for example in decision_batch.examples
    )
    eligible_action_counts = Counter(
        str(len(example.eligible_action_indices)) for example in decision_batch.examples
    )
    chosen_action_kinds = Counter(
        example.chosen_action_kind for example in decision_batch.examples
    )

    lines = [
        "Battle decision batch summary",
        f"source rollouts: {batch.source_rollout_count}",
        f"terminal rollouts: {decision_batch.terminal_rollouts}",
        f"battle examples: {len(decision_batch.examples)}",
        f"excluded non-combat driver steps: {batch.excluded_autopilot_steps}",
        f"snapshot feature size: {_optional_int(decision_batch.snapshot_feature_size)}",
        f"action feature size: {_optional_int(decision_batch.action_feature_size)}",
    ]
    _append_counter(lines, "screen states", screen_states)
    _append_counter(lines, "legal action counts", legal_action_counts)
    _append_counter(lines, "eligible action counts", eligible_action_counts)
    _append_counter(lines, "chosen action kinds", chosen_action_kinds)

    lines.append("problems:")
    if decision_batch.problems:
        lines.extend(f"  {problem}" for problem in decision_batch.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _battle_segment(
    rollout_index: int,
    rollout: ControlledRun,
    segment_index: int,
    steps: list[ControlledRunStep],
    end_reason: str,
) -> BattleSegment:
    first_step = steps[0]
    last_step = steps[-1]
    start_hp = first_step.player_hp
    end_hp = (
        last_step.next_player_hp
        if last_step.next_player_hp is not None
        else last_step.player_hp
    )
    start_max_hp = first_step.player_max_hp
    end_max_hp = (
        last_step.next_player_max_hp
        if last_step.next_player_max_hp is not None
        else last_step.player_max_hp
    )
    start_gold = first_step.gold
    end_gold = (
        last_step.next_gold if last_step.next_gold is not None else last_step.gold
    )
    start_potion_count = first_step.potion_count
    end_potion_count = (
        last_step.next_potion_count
        if last_step.next_potion_count is not None
        else last_step.potion_count
    )
    return BattleSegment(
        rollout_index=rollout_index,
        seed=rollout.seed,
        segment_index=segment_index,
        start_step_index=first_step.step_index,
        end_step_index=last_step.step_index,
        decision_count=len(steps),
        end_reason=end_reason,
        rollout_outcome=rollout.outcome,
        start_floor=first_step.floor,
        end_floor=last_step.next_floor
        if last_step.next_floor is not None
        else last_step.floor,
        start_hp=start_hp,
        end_hp=end_hp,
        hp_delta=_delta(start_hp, end_hp),
        start_max_hp=start_max_hp,
        end_max_hp=end_max_hp,
        max_hp_delta=_delta(start_max_hp, end_max_hp),
        start_gold=start_gold,
        end_gold=end_gold,
        gold_delta=_delta(start_gold, end_gold),
        start_potion_count=start_potion_count,
        end_potion_count=end_potion_count,
        potion_count_delta=_delta(start_potion_count, end_potion_count),
        action_kind_counts=Counter(step.chosen_action_kind for step in steps),
    )


def _terminal_end_reason(outcome: str) -> str:
    normalized = str(outcome).upper()
    if normalized in {"PLAYER_LOSS", "LOSS", "DEFEAT", "PLAYER_DEFEAT"}:
        return "terminal_loss"
    if normalized in {"PLAYER_VICTORY", "VICTORY", "WIN", "PLAYER_WIN"}:
        return "terminal_victory"
    return "terminal"


def _stable_size(
    current: int | None,
    observed: int,
    label: str,
    problems: list[str],
) -> int:
    if current is None:
        return observed
    if current != observed:
        problems.append(
            f"inconsistent feature size for {label}: expected {current}, got {observed}"
        )
    return current


def _validate_step_indices(
    rollout_index: int,
    step: ControlledRunStep,
    problems: list[str],
) -> None:
    legal_count = len(step.legal_action_features)
    if step.chosen_action_index < 0 or step.chosen_action_index >= legal_count:
        problems.append(
            f"rollout {rollout_index} step {step.step_index}: "
            f"chosen action index {step.chosen_action_index} outside {legal_count} actions"
        )
    for index in step.eligible_action_indices:
        if index < 0 or index >= legal_count:
            problems.append(
                f"rollout {rollout_index} step {step.step_index}: "
                f"eligible action index {index} outside {legal_count} actions"
            )


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


def _delta(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return end - start


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


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
