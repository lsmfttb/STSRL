"""Reward labels for battle-only decision batches.

This keeps reward assignment as data calibration. It does not choose an RL
algorithm, build a Gymnasium environment, or train a policy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample
from sts_combat_rl.sim.battle_agent import (
    BATTLE_AGENT_CONTROLLER,
)
from sts_combat_rl.sim.controlled_run import ControlledRun, ControlledRunStep
from sts_combat_rl.sim.reward_design import (
    BattleRewardDesignReport,
    BattleRewardSegmentScore,
    BattleRewardWeights,
    build_battle_reward_design_report,
)


TERMINAL_STEP_REWARD_ALLOCATION = "terminal_step"


@dataclass(frozen=True)
class BattleDecisionRewardLabel:
    """Reward metadata aligned with one battle decision example."""

    rollout_index: int
    seed: int | None
    step_index: int
    segment_index: int
    segment_step_index: int
    segment_decision_count: int
    segment_end_reason: str
    is_segment_final_step: bool
    segment_reward: float
    step_reward: float
    return_to_go: float
    reward_contributions: dict[str, float] = field(default_factory=dict)
    raw_reward_components: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class RewardLabeledBattleDecisionBatch:
    """A battle decision batch with parallel reward labels."""

    decision_batch: DecisionBatch
    reward_labels: list[BattleDecisionRewardLabel] = field(default_factory=list)
    reward_design_report: BattleRewardDesignReport | None = None
    source_rollout_count: int = 0
    segment_count: int = 0
    excluded_non_combat_driver_steps: int = 0
    reward_allocation: str = TERMINAL_STEP_REWARD_ALLOCATION
    problems: list[str] = field(default_factory=list)


def build_reward_labeled_battle_decision_batch(
    rollouts: list[ControlledRun],
    weights: BattleRewardWeights | None = None,
) -> RewardLabeledBattleDecisionBatch:
    """Build battle decision examples with terminal-step segment reward labels."""

    reward_report = build_battle_reward_design_report(rollouts, weights)
    step_score_map, mapping_problems = _build_step_score_map(rollouts, reward_report)
    examples: list[DecisionExample] = []
    labels: list[BattleDecisionRewardLabel] = []
    problems: list[str] = []
    problems.extend(reward_report.problems)
    problems.extend(mapping_problems)
    snapshot_feature_size: int | None = None
    action_feature_size: int | None = None
    terminal_rollouts = 0
    excluded_non_combat_driver_steps = 0

    for rollout_index, rollout in enumerate(rollouts):
        if rollout.terminal:
            terminal_rollouts += 1

        for step in rollout.steps:
            if step.controller_role != BATTLE_AGENT_CONTROLLER:
                excluded_non_combat_driver_steps += 1
                continue

            key = (rollout_index, step.step_index)
            label_context = step_score_map.get(key)
            if label_context is None:
                problems.append(
                    f"rollout {rollout_index} step {step.step_index}: "
                    "missing segment reward label"
                )
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
            examples.append(_decision_example(rollout_index, rollout.seed, step))
            labels.append(
                _reward_label(rollout_index, rollout.seed, step, label_context)
            )

    if len(examples) != len(labels):
        problems.append(
            f"decision/label length mismatch: {len(examples)} examples, "
            f"{len(labels)} labels"
        )

    decision_batch = DecisionBatch(
        examples=examples,
        snapshot_feature_size=snapshot_feature_size,
        action_feature_size=action_feature_size,
        rollout_count=len(rollouts),
        terminal_rollouts=terminal_rollouts,
        problems=problems,
    )
    return RewardLabeledBattleDecisionBatch(
        decision_batch=decision_batch,
        reward_labels=labels,
        reward_design_report=reward_report,
        source_rollout_count=len(rollouts),
        segment_count=reward_report.segment_count,
        excluded_non_combat_driver_steps=excluded_non_combat_driver_steps,
        problems=problems,
    )


def format_reward_labeled_battle_decision_batch_report(
    batch: RewardLabeledBattleDecisionBatch,
) -> str:
    """Format a compact reward-label data-shape report for stderr."""

    decision_batch = batch.decision_batch
    label_count = len(batch.reward_labels)
    step_reward_total = sum(label.step_reward for label in batch.reward_labels)
    return_to_go_total = sum(label.return_to_go for label in batch.reward_labels)
    segment_reward_total = _segment_reward_total(batch.reward_labels)
    final_step_count = sum(
        1 for label in batch.reward_labels if label.is_segment_final_step
    )
    nonfinal_step_count = label_count - final_step_count
    label_end_reasons = Counter(
        label.segment_end_reason for label in batch.reward_labels
    )
    segment_decision_counts = Counter(
        str(label.segment_decision_count)
        for label in batch.reward_labels
        if label.is_segment_final_step
    )
    chosen_action_kinds = Counter(
        example.chosen_action_kind for example in decision_batch.examples
    )
    screen_states = Counter(example.screen_state for example in decision_batch.examples)

    lines = [
        "Reward-labeled battle decision batch summary",
        "scope: labels only; no trainer, environment, or RL algorithm",
        f"reward allocation: {batch.reward_allocation}",
        f"source rollouts: {batch.source_rollout_count}",
        f"segments: {batch.segment_count}",
        f"battle examples: {len(decision_batch.examples)}",
        f"reward labels: {label_count}",
        f"labels aligned: {_yes_no(len(decision_batch.examples) == label_count)}",
        f"excluded non-combat driver steps: {batch.excluded_non_combat_driver_steps}",
        f"terminal rollouts: {decision_batch.terminal_rollouts}",
        f"snapshot feature size: {_optional_int(decision_batch.snapshot_feature_size)}",
        f"action feature size: {_optional_int(decision_batch.action_feature_size)}",
        f"final-step labels: {final_step_count}",
        f"non-final-step labels: {nonfinal_step_count}",
        f"segment reward total: {segment_reward_total:.3f}",
        f"step reward total: {step_reward_total:.3f}",
        f"return-to-go total: {return_to_go_total:.3f}",
    ]
    _append_counter(lines, "screen states", screen_states)
    _append_counter(lines, "chosen action kinds", chosen_action_kinds)
    _append_counter(lines, "label end reasons", label_end_reasons)
    _append_counter(lines, "segment decision counts", segment_decision_counts)

    if batch.reward_design_report is not None:
        _append_counter(
            lines,
            "reward contribution totals",
            batch.reward_design_report.contribution_totals,
        )
        _append_counter(
            lines,
            "long-term ledger totals",
            batch.reward_design_report.long_term_ledger_totals,
        )

    lines.append("problems:")
    if batch.problems:
        lines.extend(f"  {problem}" for problem in batch.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


@dataclass(frozen=True)
class _StepRewardContext:
    score: BattleRewardSegmentScore
    segment_step_index: int
    is_segment_final_step: bool


def _build_step_score_map(
    rollouts: list[ControlledRun],
    reward_report: BattleRewardDesignReport,
) -> tuple[dict[tuple[int, int], _StepRewardContext], list[str]]:
    step_score_map: dict[tuple[int, int], _StepRewardContext] = {}
    problems: list[str] = []
    for score in reward_report.scores:
        if score.rollout_index >= len(rollouts):
            problems.append(
                f"score rollout {score.rollout_index} outside {len(rollouts)} rollouts"
            )
            continue

        segment_steps = [
            step
            for step in rollouts[score.rollout_index].steps
            if step.controller_role == BATTLE_AGENT_CONTROLLER
            and score.start_step_index <= step.step_index <= score.end_step_index
        ]
        if len(segment_steps) != score.decision_count:
            problems.append(
                f"rollout {score.rollout_index} segment {score.segment_index}: "
                f"expected {score.decision_count} battle steps, got {len(segment_steps)}"
            )
        for segment_step_index, step in enumerate(segment_steps):
            key = (score.rollout_index, step.step_index)
            if key in step_score_map:
                problems.append(
                    f"rollout {score.rollout_index} step {step.step_index}: "
                    "duplicate segment reward label"
                )
                continue
            step_score_map[key] = _StepRewardContext(
                score=score,
                segment_step_index=segment_step_index,
                is_segment_final_step=segment_step_index == len(segment_steps) - 1,
            )
    return step_score_map, problems


def _reward_label(
    rollout_index: int,
    seed: int | None,
    step: ControlledRunStep,
    context: _StepRewardContext,
) -> BattleDecisionRewardLabel:
    score = context.score
    step_reward = score.reward if context.is_segment_final_step else 0.0
    return BattleDecisionRewardLabel(
        rollout_index=rollout_index,
        seed=seed,
        step_index=step.step_index,
        segment_index=score.segment_index,
        segment_step_index=context.segment_step_index,
        segment_decision_count=score.decision_count,
        segment_end_reason=score.end_reason,
        is_segment_final_step=context.is_segment_final_step,
        segment_reward=score.reward,
        step_reward=step_reward,
        return_to_go=score.reward,
        reward_contributions=score.contributions,
        raw_reward_components=score.raw_components,
    )


def _decision_example(
    rollout_index: int,
    seed: int | None,
    step: ControlledRunStep,
) -> DecisionExample:
    return DecisionExample(
        rollout_index=rollout_index,
        seed=seed,
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
        tactical_state=dict(step.tactical_state),
        tactical_legal_actions=[dict(action) for action in step.tactical_legal_actions],
        feature_schema_id=step.feature_schema_id,
        public_run_context=dict(step.public_run_context),
    )


def _segment_reward_total(labels: list[BattleDecisionRewardLabel]) -> float:
    seen_segments: set[tuple[int, int]] = set()
    total = 0.0
    for label in labels:
        key = (label.rollout_index, label.segment_index)
        if key in seen_segments:
            continue
        seen_segments.add(key)
        total += label.segment_reward
    return total


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


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"
