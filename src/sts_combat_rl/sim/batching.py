"""Framework-neutral batching for simulator rollout decision points.

The batch format keeps variable legal-action lists intact instead of forcing a
fixed action mask or a specific RL framework interface. This preserves enough
metadata to add potion actions later by changing the action-space config rather
than replacing the data pipeline.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.controlled_run import ControlledRun, ControlledRunStep
from sts_combat_rl.sim.decision_record import DECISION_RECORD_SCHEMA_VERSION


@dataclass(frozen=True)
class DecisionExample:
    """One framework-neutral decision example from a simulator rollout."""

    rollout_index: int
    seed: int | None
    step_index: int
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    chosen_action_index: int
    chosen_action_kind: str
    terminal_after_step: bool
    chosen_action_id: int | str | None = None
    record_schema_version: int = DECISION_RECORD_SCHEMA_VERSION
    legal_action_identities: list[dict[str, Any]] = field(default_factory=list)
    chosen_action_identity: dict[str, Any] = field(default_factory=dict)
    controller_provenance: dict[str, Any] = field(default_factory=dict)
    source_metadata: dict[str, Any] = field(default_factory=dict)
    tactical_state: dict[str, Any] = field(default_factory=dict)
    tactical_legal_actions: list[dict[str, Any]] = field(default_factory=list)
    feature_schema_id: str = "public-tactical-v2"


@dataclass(frozen=True)
class DecisionBatch:
    """A collection of variable-action decision examples."""

    examples: list[DecisionExample] = field(default_factory=list)
    snapshot_feature_size: int | None = None
    action_feature_size: int | None = None
    rollout_count: int = 0
    terminal_rollouts: int = 0
    problems: list[str] = field(default_factory=list)


def build_decision_batch(rollouts: list[ControlledRun]) -> DecisionBatch:
    """Build a validated decision batch from one or more rollout batches."""

    examples: list[DecisionExample] = []
    problems: list[str] = []
    snapshot_feature_size: int | None = None
    action_feature_size: int | None = None
    terminal_rollouts = 0

    for rollout_index, rollout in enumerate(rollouts):
        if rollout.terminal:
            terminal_rollouts += 1
        problems.extend(
            f"rollout {rollout_index}: {problem}" for problem in rollout.problems
        )

        for step in rollout.steps:
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

    return DecisionBatch(
        examples=examples,
        snapshot_feature_size=snapshot_feature_size,
        action_feature_size=action_feature_size,
        rollout_count=len(rollouts),
        terminal_rollouts=terminal_rollouts,
        problems=problems,
    )


def format_decision_batch_report(batch: DecisionBatch) -> str:
    """Format a compact batch-shape report for stderr."""

    screen_states = Counter(example.screen_state for example in batch.examples)
    legal_action_counts = Counter(
        str(len(example.legal_action_features)) for example in batch.examples
    )
    eligible_action_counts = Counter(
        str(len(example.eligible_action_indices)) for example in batch.examples
    )
    chosen_action_kinds = Counter(
        example.chosen_action_kind for example in batch.examples
    )

    lines = [
        "Decision batch summary",
        f"rollouts: {batch.rollout_count}",
        f"terminal rollouts: {batch.terminal_rollouts}",
        f"examples: {len(batch.examples)}",
        f"snapshot feature size: {_optional_int(batch.snapshot_feature_size)}",
        f"action feature size: {_optional_int(batch.action_feature_size)}",
    ]
    _append_counter(lines, "screen states", screen_states)
    _append_counter(lines, "legal action counts", legal_action_counts)
    _append_counter(lines, "eligible action counts", eligible_action_counts)
    _append_counter(lines, "chosen action kinds", chosen_action_kinds)

    lines.append("problems:")
    if batch.problems:
        lines.extend(f"  {problem}" for problem in batch.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


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
    )


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
        lines.append(f"  {key}: {count}")


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"
