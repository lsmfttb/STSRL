"""Future trainer input contract checks.

This validates the shape and alignment of reward-labeled battle decisions. It
does not implement a trainer, Gymnasium environment, RL algorithm, or replay
buffer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
from typing import Any

from sts_combat_rl.sim.batching import DecisionExample
from sts_combat_rl.sim.reward_labeling import (
    BattleDecisionRewardLabel,
    RewardLabeledBattleDecisionBatch,
    TERMINAL_STEP_REWARD_ALLOCATION,
)


_TOLERANCE = 1e-9


@dataclass(frozen=True)
class TrainerInputContractReport:
    """Contract validation report for a reward-labeled battle batch."""

    source_rollout_count: int
    segment_count: int
    example_count: int
    reward_label_count: int
    reward_allocation: str
    labels_aligned: bool
    contract_ok: bool
    snapshot_feature_size: int | None = None
    action_feature_size: int | None = None
    final_step_labels: int = 0
    nonfinal_step_labels: int = 0
    segment_reward_total: float = 0.0
    step_reward_total: float = 0.0
    return_to_go_total: float = 0.0
    snapshot_feature_size_counts: Counter[str] = field(default_factory=Counter)
    action_feature_size_counts: Counter[str] = field(default_factory=Counter)
    legal_action_count_counts: Counter[str] = field(default_factory=Counter)
    eligible_action_count_counts: Counter[str] = field(default_factory=Counter)
    screen_state_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    label_end_reason_counts: Counter[str] = field(default_factory=Counter)
    terminal_after_step_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def build_trainer_input_contract_report(
    batch: RewardLabeledBattleDecisionBatch,
) -> TrainerInputContractReport:
    """Validate fields a future trainer would consume from a battle batch."""

    examples = batch.decision_batch.examples
    labels = batch.reward_labels
    problems = list(batch.problems)
    snapshot_feature_size_counts: Counter[str] = Counter()
    action_feature_size_counts: Counter[str] = Counter()
    legal_action_count_counts: Counter[str] = Counter()
    eligible_action_count_counts: Counter[str] = Counter()
    screen_state_counts: Counter[str] = Counter()
    chosen_action_kind_counts: Counter[str] = Counter()
    label_end_reason_counts: Counter[str] = Counter()
    terminal_after_step_counts: Counter[str] = Counter()

    if len(examples) != len(labels):
        problems.append(
            f"example/label length mismatch: {len(examples)} examples, "
            f"{len(labels)} labels"
        )
    if examples and batch.decision_batch.snapshot_feature_size is None:
        problems.append("snapshot feature size is missing")
    if examples and batch.decision_batch.action_feature_size is None:
        problems.append("action feature size is missing")
    if batch.reward_allocation != TERMINAL_STEP_REWARD_ALLOCATION:
        problems.append(f"unsupported reward allocation: {batch.reward_allocation}")

    for index, example in enumerate(examples):
        snapshot_feature_size_counts[str(len(example.snapshot_features))] += 1
        legal_action_count_counts[str(len(example.legal_action_features))] += 1
        eligible_action_count_counts[str(len(example.eligible_action_indices))] += 1
        screen_state_counts[example.screen_state] += 1
        chosen_action_kind_counts[example.chosen_action_kind] += 1
        terminal_after_step_counts[str(example.terminal_after_step).lower()] += 1
        _validate_example(
            index,
            example,
            batch.decision_batch.snapshot_feature_size,
            batch.decision_batch.action_feature_size,
            action_feature_size_counts,
            problems,
        )

    for index, label in enumerate(labels):
        label_end_reason_counts[label.segment_end_reason] += 1
        _validate_label(index, label, problems)

    for index, (example, label) in enumerate(zip(examples, labels)):
        _validate_example_label_alignment(index, example, label, problems)

    final_step_labels = sum(1 for label in labels if label.is_segment_final_step)
    nonfinal_step_labels = len(labels) - final_step_labels
    segment_reward_total = _segment_reward_total(labels)
    step_reward_total = sum(label.step_reward for label in labels)
    return_to_go_total = sum(label.return_to_go for label in labels)
    if final_step_labels != batch.segment_count:
        problems.append(
            f"final-step label count {final_step_labels} does not match "
            f"segment count {batch.segment_count}"
        )
    if not _close(step_reward_total, segment_reward_total):
        problems.append(
            f"step reward total {step_reward_total:.6f} does not match "
            f"segment reward total {segment_reward_total:.6f}"
        )

    return TrainerInputContractReport(
        source_rollout_count=batch.source_rollout_count,
        segment_count=batch.segment_count,
        example_count=len(examples),
        reward_label_count=len(labels),
        reward_allocation=batch.reward_allocation,
        labels_aligned=len(examples) == len(labels),
        contract_ok=not problems,
        snapshot_feature_size=batch.decision_batch.snapshot_feature_size,
        action_feature_size=batch.decision_batch.action_feature_size,
        final_step_labels=final_step_labels,
        nonfinal_step_labels=nonfinal_step_labels,
        segment_reward_total=segment_reward_total,
        step_reward_total=step_reward_total,
        return_to_go_total=return_to_go_total,
        snapshot_feature_size_counts=snapshot_feature_size_counts,
        action_feature_size_counts=action_feature_size_counts,
        legal_action_count_counts=legal_action_count_counts,
        eligible_action_count_counts=eligible_action_count_counts,
        screen_state_counts=screen_state_counts,
        chosen_action_kind_counts=chosen_action_kind_counts,
        label_end_reason_counts=label_end_reason_counts,
        terminal_after_step_counts=terminal_after_step_counts,
        problems=problems,
    )


def format_trainer_input_contract_report(
    report: TrainerInputContractReport,
) -> str:
    """Format trainer input contract validation for stderr."""

    lines = [
        "Trainer input contract summary",
        "scope: input contract only; no trainer, environment, or RL algorithm",
        f"contract ok: {_yes_no(report.contract_ok)}",
        f"reward allocation: {report.reward_allocation}",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"battle examples: {report.example_count}",
        f"reward labels: {report.reward_label_count}",
        f"labels aligned: {_yes_no(report.labels_aligned)}",
        f"snapshot feature size: {_optional_int(report.snapshot_feature_size)}",
        f"action feature size: {_optional_int(report.action_feature_size)}",
        f"final-step labels: {report.final_step_labels}",
        f"non-final-step labels: {report.nonfinal_step_labels}",
        f"segment reward total: {report.segment_reward_total:.3f}",
        f"step reward total: {report.step_reward_total:.3f}",
        f"return-to-go total: {report.return_to_go_total:.3f}",
    ]
    _append_counter(lines, "screen states", report.screen_state_counts)
    _append_counter(lines, "chosen action kinds", report.chosen_action_kind_counts)
    _append_counter(
        lines,
        "snapshot feature sizes",
        report.snapshot_feature_size_counts,
    )
    _append_counter(lines, "action feature sizes", report.action_feature_size_counts)
    _append_counter(lines, "legal action counts", report.legal_action_count_counts)
    _append_counter(
        lines,
        "eligible action counts",
        report.eligible_action_count_counts,
    )
    _append_counter(lines, "label end reasons", report.label_end_reason_counts)
    _append_counter(
        lines,
        "terminal_after_step flags",
        report.terminal_after_step_counts,
    )

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _validate_example(
    index: int,
    example: DecisionExample,
    expected_snapshot_feature_size: int | None,
    expected_action_feature_size: int | None,
    action_feature_size_counts: Counter[str],
    problems: list[str],
) -> None:
    if example.screen_state != "BATTLE":
        problems.append(
            f"example {index}: expected BATTLE screen, got {example.screen_state}"
        )
    if not example.snapshot_features:
        problems.append(f"example {index}: empty snapshot features")
    if (
        expected_snapshot_feature_size is not None
        and len(example.snapshot_features) != expected_snapshot_feature_size
    ):
        problems.append(
            f"example {index}: snapshot feature size {len(example.snapshot_features)} "
            f"does not match {expected_snapshot_feature_size}"
        )
    if not example.legal_action_features:
        problems.append(f"example {index}: empty legal action list")
    if len(example.legal_action_features) != len(example.legal_action_kinds):
        problems.append(
            f"example {index}: {len(example.legal_action_features)} action feature rows "
            f"but {len(example.legal_action_kinds)} action kinds"
        )
    for action_index, action_features in enumerate(example.legal_action_features):
        action_feature_size_counts[str(len(action_features))] += 1
        if (
            expected_action_feature_size is not None
            and len(action_features) != expected_action_feature_size
        ):
            problems.append(
                f"example {index} action {action_index}: action feature size "
                f"{len(action_features)} does not match {expected_action_feature_size}"
            )
    legal_count = len(example.legal_action_features)
    if example.chosen_action_index < 0 or example.chosen_action_index >= legal_count:
        problems.append(
            f"example {index}: chosen action index {example.chosen_action_index} "
            f"outside {legal_count} legal actions"
        )
    if not example.eligible_action_indices:
        problems.append(f"example {index}: empty eligible action indices")
    if len(set(example.eligible_action_indices)) != len(
        example.eligible_action_indices
    ):
        problems.append(f"example {index}: duplicate eligible action indices")
    for eligible_index in example.eligible_action_indices:
        if eligible_index < 0 or eligible_index >= legal_count:
            problems.append(
                f"example {index}: eligible action index {eligible_index} "
                f"outside {legal_count} legal actions"
            )
    if (
        0 <= example.chosen_action_index < legal_count
        and example.chosen_action_index not in example.eligible_action_indices
    ):
        problems.append(
            f"example {index}: chosen action index {example.chosen_action_index} "
            "is not eligible"
        )


def _validate_label(
    index: int,
    label: BattleDecisionRewardLabel,
    problems: list[str],
) -> None:
    if label.segment_index < 0:
        problems.append(f"label {index}: negative segment index")
    if label.segment_decision_count < 1:
        problems.append(f"label {index}: segment decision count must be positive")
    if label.segment_step_index < 0:
        problems.append(f"label {index}: negative segment step index")
    if label.segment_step_index >= label.segment_decision_count:
        problems.append(
            f"label {index}: segment step index {label.segment_step_index} "
            f"outside {label.segment_decision_count} segment decisions"
        )
    expected_final = label.segment_step_index == label.segment_decision_count - 1
    if label.is_segment_final_step != expected_final:
        problems.append(
            f"label {index}: final-step flag {label.is_segment_final_step} "
            f"does not match segment position {label.segment_step_index}/"
            f"{label.segment_decision_count}"
        )
    _validate_finite(label.segment_reward, f"label {index}: segment_reward", problems)
    _validate_finite(label.step_reward, f"label {index}: step_reward", problems)
    _validate_finite(label.return_to_go, f"label {index}: return_to_go", problems)
    if label.is_segment_final_step:
        if not _close(label.step_reward, label.segment_reward):
            problems.append(
                f"label {index}: final step reward {label.step_reward:.6f} "
                f"does not match segment reward {label.segment_reward:.6f}"
            )
    elif not _close(label.step_reward, 0.0):
        problems.append(
            f"label {index}: non-final step reward {label.step_reward:.6f} is not zero"
        )
    if not _close(label.return_to_go, label.segment_reward):
        problems.append(
            f"label {index}: return_to_go {label.return_to_go:.6f} "
            f"does not match segment reward {label.segment_reward:.6f}"
        )
    for name, value in label.reward_contributions.items():
        _validate_finite(value, f"label {index}: contribution {name}", problems)
    for name, value in label.raw_reward_components.items():
        if value is not None:
            _validate_finite(value, f"label {index}: raw component {name}", problems)


def _validate_example_label_alignment(
    index: int,
    example: DecisionExample,
    label: BattleDecisionRewardLabel,
    problems: list[str],
) -> None:
    if example.rollout_index != label.rollout_index:
        problems.append(
            f"example/label {index}: rollout mismatch "
            f"{example.rollout_index} != {label.rollout_index}"
        )
    if example.seed != label.seed:
        problems.append(
            f"example/label {index}: seed mismatch {example.seed} != {label.seed}"
        )
    if example.step_index != label.step_index:
        problems.append(
            f"example/label {index}: step mismatch "
            f"{example.step_index} != {label.step_index}"
        )
    if (
        label.is_segment_final_step
        and label.segment_end_reason.startswith("terminal_")
        and not example.terminal_after_step
    ):
        problems.append(
            f"example/label {index}: terminal segment end without terminal step flag"
        )
    if example.terminal_after_step and not label.segment_end_reason.startswith(
        "terminal_"
    ):
        problems.append(
            f"example/label {index}: terminal step flag on non-terminal segment end"
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


def _validate_finite(value: float, label: str, problems: list[str]) -> None:
    if not math.isfinite(value):
        problems.append(f"{label} is not finite: {value!r}")


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE)


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
