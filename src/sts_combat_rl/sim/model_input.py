"""Framework-neutral model input packing for variable-action battle data.

This module converts trainer input records into a compact batch shape that a
future action scorer can consume. It does not implement a trainer, replay
buffer, Gymnasium environment, RL algorithm, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
import math
from typing import Any

from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.trainer_input import TrainerInputDataset


MODEL_INPUT_BATCH_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ModelInputExampleRef:
    """Metadata that maps one packed model example back to its source decision."""

    example_index: int
    rollout_index: int
    seed: int | None
    step_index: int
    segment_index: int
    segment_step_index: int
    segment_decision_count: int
    segment_end_reason: str


@dataclass(frozen=True)
class ModelInputBatch:
    """Packed variable-action batch for a future model scorer."""

    format_version: int
    reward_allocation: str
    snapshot_feature_size: int | None
    action_feature_size: int | None
    example_refs: list[ModelInputExampleRef] = field(default_factory=list)
    screen_states: list[str] = field(default_factory=list)
    snapshot_features: list[list[float]] = field(default_factory=list)
    action_features: list[list[float]] = field(default_factory=list)
    action_offsets: list[int] = field(default_factory=lambda: [0])
    action_kinds: list[list[str]] = field(default_factory=list)
    eligible_action_indices: list[list[int]] = field(default_factory=list)
    eligible_action_rows: list[list[int]] = field(default_factory=list)
    chosen_action_indices: list[int] = field(default_factory=list)
    chosen_action_rows: list[int] = field(default_factory=list)
    chosen_action_kinds: list[str] = field(default_factory=list)
    terminal_after_step: list[bool] = field(default_factory=list)
    step_rewards: list[float] = field(default_factory=list)
    return_to_go: list[float] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModelInputBatchSmokeReport:
    """Shape report for model-input packing."""

    format_version: int
    reward_allocation: str
    model_input_ok: bool
    context_rebuild_ok: bool
    example_count: int
    snapshot_rows: int
    action_rows: int
    action_offset_count: int
    snapshot_feature_size: int | None
    action_feature_size: int | None
    max_legal_actions: int
    max_eligible_actions: int
    terminal_after_step_count: int
    step_reward_total: float
    return_to_go_total: float
    screen_state_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def build_model_input_batch(dataset: TrainerInputDataset) -> ModelInputBatch:
    """Pack a trainer input dataset into flattened variable-action rows."""

    example_refs: list[ModelInputExampleRef] = []
    screen_states: list[str] = []
    snapshot_features: list[list[float]] = []
    action_features: list[list[float]] = []
    action_offsets: list[int] = [0]
    action_kinds: list[list[str]] = []
    eligible_action_indices: list[list[int]] = []
    eligible_action_rows: list[list[int]] = []
    chosen_action_indices: list[int] = []
    chosen_action_rows: list[int] = []
    chosen_action_kinds: list[str] = []
    terminal_after_step: list[bool] = []
    step_rewards: list[float] = []
    return_to_go: list[float] = []

    for record in dataset.records:
        action_start = len(action_features)
        legal_action_count = len(record.legal_action_features)
        example_refs.append(
            ModelInputExampleRef(
                example_index=record.example_index,
                rollout_index=record.rollout_index,
                seed=record.seed,
                step_index=record.step_index,
                segment_index=record.segment_index,
                segment_step_index=record.segment_step_index,
                segment_decision_count=record.segment_decision_count,
                segment_end_reason=record.segment_end_reason,
            )
        )
        screen_states.append(record.screen_state)
        snapshot_features.append(list(record.snapshot_features))
        action_features.extend(
            list(features) for features in record.legal_action_features
        )
        action_offsets.append(action_start + legal_action_count)
        action_kinds.append(list(record.legal_action_kinds))
        eligible_action_indices.append(list(record.eligible_action_indices))
        eligible_action_rows.append(
            [action_start + index for index in record.eligible_action_indices]
        )
        chosen_action_indices.append(record.chosen_action_index)
        chosen_action_rows.append(action_start + record.chosen_action_index)
        chosen_action_kinds.append(record.chosen_action_kind)
        terminal_after_step.append(record.terminal_after_step)
        step_rewards.append(record.step_reward)
        return_to_go.append(record.return_to_go)

    batch = ModelInputBatch(
        format_version=MODEL_INPUT_BATCH_FORMAT_VERSION,
        reward_allocation=dataset.reward_allocation,
        snapshot_feature_size=dataset.snapshot_feature_size,
        action_feature_size=dataset.action_feature_size,
        example_refs=example_refs,
        screen_states=screen_states,
        snapshot_features=snapshot_features,
        action_features=action_features,
        action_offsets=action_offsets,
        action_kinds=action_kinds,
        eligible_action_indices=eligible_action_indices,
        eligible_action_rows=eligible_action_rows,
        chosen_action_indices=chosen_action_indices,
        chosen_action_rows=chosen_action_rows,
        chosen_action_kinds=chosen_action_kinds,
        terminal_after_step=terminal_after_step,
        step_rewards=step_rewards,
        return_to_go=return_to_go,
        problems=list(dataset.problems),
    )
    return replace(
        batch,
        problems=list(batch.problems) + _model_input_shape_problems(batch),
    )


def build_model_input_batch_smoke_report(
    dataset: TrainerInputDataset,
) -> ModelInputBatchSmokeReport:
    """Build and validate a model-input batch without training."""

    batch = build_model_input_batch(dataset)
    context_problems = _context_rebuild_problems(batch)
    problems = list(batch.problems) + context_problems
    legal_action_counts = [
        batch.action_offsets[index + 1] - batch.action_offsets[index]
        for index in range(len(batch.snapshot_features))
        if index + 1 < len(batch.action_offsets)
    ]
    return ModelInputBatchSmokeReport(
        format_version=batch.format_version,
        reward_allocation=batch.reward_allocation,
        model_input_ok=not batch.problems,
        context_rebuild_ok=not context_problems,
        example_count=len(batch.example_refs),
        snapshot_rows=len(batch.snapshot_features),
        action_rows=len(batch.action_features),
        action_offset_count=len(batch.action_offsets),
        snapshot_feature_size=batch.snapshot_feature_size,
        action_feature_size=batch.action_feature_size,
        max_legal_actions=max(legal_action_counts, default=0),
        max_eligible_actions=max(
            (len(indices) for indices in batch.eligible_action_indices),
            default=0,
        ),
        terminal_after_step_count=sum(
            1 for value in batch.terminal_after_step if value
        ),
        step_reward_total=sum(batch.step_rewards),
        return_to_go_total=sum(batch.return_to_go),
        screen_state_counts=Counter(batch.screen_states),
        chosen_action_kind_counts=Counter(batch.chosen_action_kinds),
        problems=problems,
    )


def format_model_input_batch_smoke_report(
    report: ModelInputBatchSmokeReport,
) -> str:
    """Format a compact model-input smoke report for stderr."""

    lines = [
        "Model input batch smoke summary",
        "scope: model input packaging only; no trainer, environment, or RL algorithm",
        f"format version: {report.format_version}",
        f"reward allocation: {report.reward_allocation}",
        f"model input ok: {_yes_no(report.model_input_ok)}",
        f"context rebuild ok: {_yes_no(report.context_rebuild_ok)}",
        f"examples: {report.example_count}",
        f"snapshot rows: {report.snapshot_rows}",
        f"action rows: {report.action_rows}",
        f"action offset count: {report.action_offset_count}",
        f"snapshot feature size: {_optional_int(report.snapshot_feature_size)}",
        f"action feature size: {_optional_int(report.action_feature_size)}",
        f"max legal actions: {report.max_legal_actions}",
        f"max eligible actions: {report.max_eligible_actions}",
        f"terminal_after_step records: {report.terminal_after_step_count}",
        f"step reward total: {report.step_reward_total:.3f}",
        f"return-to-go total: {report.return_to_go_total:.3f}",
    ]
    _append_counter(lines, "screen states", report.screen_state_counts)
    _append_counter(lines, "chosen action kinds", report.chosen_action_kind_counts)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def decision_context_from_model_input_batch(
    batch: ModelInputBatch,
    example_index: int,
) -> DecisionContext:
    """Rebuild a policy/scorer context from one packed model-input example."""

    if example_index < 0 or example_index >= len(batch.snapshot_features):
        raise IndexError(f"example index {example_index} outside model input batch")
    action_start = batch.action_offsets[example_index]
    action_end = batch.action_offsets[example_index + 1]
    return DecisionContext(
        screen_state=batch.screen_states[example_index],
        snapshot_features=batch.snapshot_features[example_index],
        legal_action_features=batch.action_features[action_start:action_end],
        legal_action_kinds=batch.action_kinds[example_index],
        eligible_action_indices=batch.eligible_action_indices[example_index],
    )


def _model_input_shape_problems(batch: ModelInputBatch) -> list[str]:
    problems: list[str] = []
    example_count = len(batch.snapshot_features)
    if batch.format_version != MODEL_INPUT_BATCH_FORMAT_VERSION:
        problems.append(
            f"unsupported model input format version: {batch.format_version}"
        )
    if len(batch.action_offsets) != example_count + 1:
        problems.append(
            f"action offset count {len(batch.action_offsets)} does not match "
            f"{example_count + 1} expected offsets"
        )
    elif batch.action_offsets:
        _validate_offsets(batch.action_offsets, len(batch.action_features), problems)

    _validate_parallel_length(
        "example refs",
        len(batch.example_refs),
        example_count,
        problems,
    )
    for label, observed in (
        ("screen states", len(batch.screen_states)),
        ("action kind lists", len(batch.action_kinds)),
        ("eligible action index lists", len(batch.eligible_action_indices)),
        ("eligible action row lists", len(batch.eligible_action_rows)),
        ("chosen action indices", len(batch.chosen_action_indices)),
        ("chosen action rows", len(batch.chosen_action_rows)),
        ("chosen action kinds", len(batch.chosen_action_kinds)),
        ("terminal flags", len(batch.terminal_after_step)),
        ("step rewards", len(batch.step_rewards)),
        ("return-to-go labels", len(batch.return_to_go)),
    ):
        _validate_parallel_length(label, observed, example_count, problems)

    for index, snapshot_features in enumerate(batch.snapshot_features):
        _validate_feature_row(
            f"example {index} snapshot",
            snapshot_features,
            batch.snapshot_feature_size,
            problems,
        )
        if index + 1 >= len(batch.action_offsets):
            continue
        action_start = batch.action_offsets[index]
        action_end = batch.action_offsets[index + 1]
        legal_count = action_end - action_start
        _validate_example_actions(index, action_start, legal_count, batch, problems)
        for action_index, action_features in enumerate(
            batch.action_features[action_start:action_end]
        ):
            _validate_feature_row(
                f"example {index} action {action_index}",
                action_features,
                batch.action_feature_size,
                problems,
            )

    for index, value in enumerate(batch.step_rewards):
        _validate_finite(value, f"example {index} step_reward", problems)
    for index, value in enumerate(batch.return_to_go):
        _validate_finite(value, f"example {index} return_to_go", problems)

    return problems


def _validate_offsets(
    offsets: list[int],
    action_row_count: int,
    problems: list[str],
) -> None:
    if offsets[0] != 0:
        problems.append(f"first action offset must be 0, got {offsets[0]}")
    if offsets[-1] != action_row_count:
        problems.append(
            f"last action offset {offsets[-1]} does not match "
            f"{action_row_count} action rows"
        )
    for index, (left, right) in enumerate(zip(offsets, offsets[1:])):
        if left > right:
            problems.append(
                f"action offsets must be nondecreasing: offset {index}={left}, "
                f"offset {index + 1}={right}"
            )


def _validate_example_actions(
    example_index: int,
    action_start: int,
    legal_count: int,
    batch: ModelInputBatch,
    problems: list[str],
) -> None:
    if legal_count <= 0:
        problems.append(f"example {example_index}: no legal actions")
    action_kinds = _item(batch.action_kinds, example_index, [])
    if len(action_kinds) != legal_count:
        problems.append(
            f"example {example_index}: {len(action_kinds)} action kinds but "
            f"{legal_count} action rows"
        )

    eligible_indices = _item(batch.eligible_action_indices, example_index, [])
    if not eligible_indices:
        problems.append(f"example {example_index}: empty eligible action indices")
    if len(set(eligible_indices)) != len(eligible_indices):
        problems.append(f"example {example_index}: duplicate eligible action indices")
    invalid_eligible = [
        index for index in eligible_indices if index < 0 or index >= legal_count
    ]
    if invalid_eligible:
        problems.append(
            f"example {example_index}: eligible action index "
            f"{invalid_eligible[0]} outside {legal_count} legal actions"
        )

    expected_eligible_rows = [action_start + index for index in eligible_indices]
    observed_eligible_rows = _item(batch.eligible_action_rows, example_index, [])
    if observed_eligible_rows != expected_eligible_rows:
        problems.append(
            f"example {example_index}: eligible action rows do not match offsets"
        )

    chosen_index = _item(batch.chosen_action_indices, example_index, -1)
    if chosen_index < 0 or chosen_index >= legal_count:
        problems.append(
            f"example {example_index}: chosen action index {chosen_index} "
            f"outside {legal_count} legal actions"
        )
    elif chosen_index not in eligible_indices:
        problems.append(
            f"example {example_index}: chosen action index {chosen_index} is not eligible"
        )

    observed_chosen_row = _item(batch.chosen_action_rows, example_index, -1)
    if observed_chosen_row != action_start + chosen_index:
        problems.append(
            f"example {example_index}: chosen action row does not match offset"
        )

    chosen_kind = _item(batch.chosen_action_kinds, example_index, "")
    if (
        0 <= chosen_index < len(action_kinds)
        and chosen_kind != action_kinds[chosen_index]
    ):
        problems.append(
            f"example {example_index}: chosen action kind {chosen_kind!r} does not "
            f"match legal action kind {action_kinds[chosen_index]!r}"
        )


def _context_rebuild_problems(batch: ModelInputBatch) -> list[str]:
    problems: list[str] = []
    for example_index in range(len(batch.snapshot_features)):
        try:
            context = decision_context_from_model_input_batch(batch, example_index)
        except (IndexError, ValueError) as exc:
            problems.append(
                f"example {example_index}: failed to rebuild context: {exc}"
            )
            continue
        legal_count = len(context.legal_action_features)
        if len(context.legal_action_kinds) != legal_count:
            problems.append(
                f"example {example_index}: rebuilt context has "
                f"{len(context.legal_action_kinds)} kinds for {legal_count} actions"
            )
        for eligible_index in context.eligible_action_indices:
            if eligible_index < 0 or eligible_index >= legal_count:
                problems.append(
                    f"example {example_index}: rebuilt eligible index "
                    f"{eligible_index} outside {legal_count} legal actions"
                )
                break
    return problems


def _validate_feature_row(
    label: str,
    features: list[float],
    expected_size: int | None,
    problems: list[str],
) -> None:
    if expected_size is not None and len(features) != expected_size:
        problems.append(
            f"{label}: feature size {len(features)} does not match {expected_size}"
        )
    for feature_index, value in enumerate(features):
        _validate_finite(value, f"{label} feature {feature_index}", problems)


def _validate_finite(value: float, label: str, problems: list[str]) -> None:
    if not math.isfinite(float(value)):
        problems.append(f"{label} is not finite: {value!r}")


def _validate_parallel_length(
    label: str,
    observed: int,
    expected: int,
    problems: list[str],
) -> None:
    if observed != expected:
        problems.append(f"{label} length {observed} does not match {expected} examples")


def _item(values: list[Any], index: int, default: Any) -> Any:
    if index < 0 or index >= len(values):
        return default
    return values[index]


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"
