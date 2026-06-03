"""Battle-agent-only simulator sweep helpers.

The battle agent only selects actions in battle states. Non-combat states are
advanced by a scripted autopilot so simulator rollouts can reach more battles
without making map/reward/shop navigation part of the agent contract.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig, filter_eligible_actions
from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorAdapter
from sts_combat_rl.sim.features import (
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.policy import DecisionContext, DecisionPolicy, PreferredKindPolicy


BATTLE_AGENT_CONTROLLER = "battle_agent"
AUTOPILOT_CONTROLLER = "autopilot"


@dataclass(frozen=True)
class BattleAgentRolloutStep:
    """One simulator step tagged by the controller that selected the action."""

    step_index: int
    controller: str
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    chosen_action_index: int
    chosen_action_id: int | str
    chosen_action_kind: str
    terminal_after_step: bool


@dataclass(frozen=True)
class BattleAgentRollout:
    """A bounded rollout with battle-agent and autopilot decisions separated."""

    seed: int | None
    requested_steps: int
    steps: list[BattleAgentRolloutStep] = field(default_factory=list)
    terminal: bool = False
    outcome: str = "UNKNOWN"
    problems: list[str] = field(default_factory=list)
    initial_raw: Mapping[str, Any] = field(default_factory=dict)
    final_raw: Mapping[str, Any] = field(default_factory=dict)


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


def collect_battle_agent_rollout(
    adapter: SimulatorAdapter,
    battle_policy: DecisionPolicy,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    autopilot_policy: DecisionPolicy | None = None,
) -> BattleAgentRollout:
    """Collect a bounded rollout where only battle states use battle_policy."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    active_autopilot = autopilot_policy or PreferredKindPolicy()
    snapshot = adapter.reset(seed=seed)
    initial_raw = dict(snapshot.raw)
    steps: list[BattleAgentRolloutStep] = []
    problems: list[str] = []
    terminal = False

    for step_index in range(max_steps):
        actions = list(adapter.legal_actions(snapshot))
        if not actions:
            problems.append("no legal actions before terminal state")
            break

        context = build_decision_context(snapshot.raw, actions, active_action_space)
        controller = (
            BATTLE_AGENT_CONTROLLER
            if _is_battle_state(snapshot.raw, context.screen_state)
            else AUTOPILOT_CONTROLLER
        )
        policy = battle_policy if controller == BATTLE_AGENT_CONTROLLER else active_autopilot

        try:
            selected_index = policy.select_action(context).legal_action_index
        except ValueError as exc:
            problems.append(f"{controller}: {exc}")
            break

        validation_problem = _selected_index_problem(
            selected_index,
            len(actions),
            context.eligible_action_indices,
            controller,
        )
        if validation_problem is not None:
            problems.append(validation_problem)
            break

        chosen_action = actions[selected_index]
        transition = adapter.step(chosen_action)
        terminal = transition.terminal
        steps.append(
            BattleAgentRolloutStep(
                step_index=step_index,
                controller=controller,
                screen_state=context.screen_state,
                snapshot_features=context.snapshot_features,
                legal_action_features=context.legal_action_features,
                legal_action_kinds=context.legal_action_kinds,
                eligible_action_indices=context.eligible_action_indices,
                chosen_action_index=selected_index,
                chosen_action_id=chosen_action.action_id,
                chosen_action_kind=chosen_action.kind,
                terminal_after_step=terminal,
            )
        )

        snapshot = transition.snapshot
        if terminal:
            break

    return BattleAgentRollout(
        seed=seed,
        requested_steps=max_steps,
        steps=steps,
        terminal=terminal,
        outcome=str(snapshot.raw.get("outcome", "UNKNOWN")),
        problems=problems,
        initial_raw=initial_raw,
        final_raw=dict(snapshot.raw),
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
    """Run a battle-agent-only seed sweep without training."""

    active_autopilot = autopilot_policy or PreferredKindPolicy()
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
            autopilot_policy=active_autopilot,
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
        battle_legal_action_count_counts.update(summary.battle_legal_action_count_counts)
        battle_eligible_action_count_counts.update(
            summary.battle_eligible_action_count_counts
        )
        battle_snapshot_feature_size_counts.update(
            summary.battle_snapshot_feature_size_counts
        )
        battle_action_feature_size_counts.update(summary.battle_action_feature_size_counts)
        if summary.terminal:
            terminal_episodes += 1
        problems.extend(
            f"seed {_seed_label(seed)}: {problem}" for problem in summary.problems
        )

    return BattleAgentSweepReport(
        battle_policy_name=battle_policy.name,
        autopilot_policy_name=active_autopilot.name,
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
    rollouts: list[BattleAgentRollout],
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
            if step.controller != BATTLE_AGENT_CONTROLLER:
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
                    chosen_action_kind=step.chosen_action_kind,
                    terminal_after_step=step.terminal_after_step,
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


def summarize_battle_agent_episode(
    rollout: BattleAgentRollout,
) -> BattleAgentEpisodeSummary:
    """Summarize battle-agent decisions from one bounded rollout."""

    initial_raw = _mapping(rollout.initial_raw)
    final_raw = _mapping(rollout.final_raw)
    battle_steps = [
        step for step in rollout.steps if step.controller == BATTLE_AGENT_CONTROLLER
    ]
    autopilot_steps = [
        step for step in rollout.steps if step.controller == AUTOPILOT_CONTROLLER
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
        f"autopilot policy: {report.autopilot_policy_name}",
        f"episodes: {episode_count}",
        f"requested steps per episode: {report.requested_steps_per_episode}",
        f"terminal episodes: {report.terminal_episodes}",
        f"total collected steps: {report.total_steps}",
        f"total battle decisions: {report.total_battle_decisions}",
        f"total autopilot decisions: {report.total_autopilot_decisions}",
        f"average collected steps: {average_steps:.2f}",
        f"average battle decisions: {average_battle_decisions:.2f}",
        f"average autopilot decisions: {average_autopilot_decisions:.2f}",
    ]
    _append_counter(lines, "outcomes", report.outcome_counts)
    _append_counter(lines, "final screen states", report.final_screen_state_counts)
    _append_counter(lines, "final floors", report.final_floor_counts)
    _append_counter(lines, "battle action kinds", report.battle_action_kind_counts)
    _append_counter(lines, "autopilot action kinds", report.autopilot_action_kind_counts)
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


def format_battle_decision_batch_report(batch: BattleDecisionBatch) -> str:
    """Format a battle-only decision batch report for stderr."""

    decision_batch = batch.decision_batch
    screen_states = Counter(
        example.screen_state for example in decision_batch.examples
    )
    legal_action_counts = Counter(
        str(len(example.legal_action_features))
        for example in decision_batch.examples
    )
    eligible_action_counts = Counter(
        str(len(example.eligible_action_indices))
        for example in decision_batch.examples
    )
    chosen_action_kinds = Counter(
        example.chosen_action_kind for example in decision_batch.examples
    )

    lines = [
        "Battle decision batch summary",
        f"source rollouts: {batch.source_rollout_count}",
        f"terminal rollouts: {decision_batch.terminal_rollouts}",
        f"battle examples: {len(decision_batch.examples)}",
        f"excluded autopilot steps: {batch.excluded_autopilot_steps}",
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


def build_decision_context(
    raw_snapshot: object,
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig,
) -> DecisionContext:
    """Build the policy input for the current simulator candidate list."""

    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    return DecisionContext(
        screen_state=str(raw.get("screen_state", "(none)")),
        snapshot_features=encode_lightspeed_battle_snapshot(raw),
        legal_action_features=encode_simulator_actions(actions),
        legal_action_kinds=[action.kind for action in actions],
        eligible_action_indices=_eligible_indices(actions, action_space),
    )


def _is_battle_state(
    raw_snapshot: object,
    screen_state: str,
) -> bool:
    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    return bool(raw.get("battle_active")) or screen_state == "BATTLE"


def _selected_index_problem(
    selected_index: int,
    legal_count: int,
    eligible_indices: list[int],
    controller: str,
) -> str | None:
    if selected_index < 0 or selected_index >= legal_count:
        return (
            f"{controller} selected action index {selected_index} "
            f"outside {legal_count} legal actions"
        )
    if selected_index not in eligible_indices:
        return (
            f"{controller} selected action index {selected_index} "
            "outside the active action space"
        )
    return None


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
    step: BattleAgentRolloutStep,
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


def _eligible_indices(
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig,
) -> list[int]:
    eligible_action_ids = {
        id(action)
        for action in filter_eligible_actions(actions, action_space)
    }
    return [
        index
        for index, action in enumerate(actions)
        if id(action) in eligible_action_ids
    ]


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


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
