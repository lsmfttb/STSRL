"""Training-readiness checks for the battle-agent data path.

This module decides whether the current data plumbing is ready for a first
trainer implementation. It does not implement a trainer, replay buffer,
Gymnasium environment, RL algorithm, or game mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.controlled_run import ControlledRun
from sts_combat_rl.sim.lightspeed_source import (
    format_lightspeed_source_identity,
    lightspeed_source_identity_dict,
)
from sts_combat_rl.sim.model_input import (
    build_model_input_batch,
    build_model_input_batch_smoke_report,
)
from sts_combat_rl.sim.model_scoring import (
    BatchActionScorer,
    score_model_input_batch,
)
from sts_combat_rl.sim.reward_design import BattleRewardWeights
from sts_combat_rl.sim.reward_labeling import (
    build_reward_labeled_battle_decision_batch,
)
from sts_combat_rl.sim.trainer_input import (
    build_trainer_input_dataset,
    build_trainer_input_dataset_smoke_report,
)
from sts_combat_rl.sim.trainer_input_contract import (
    build_trainer_input_contract_report,
)


TRAINING_READINESS_LIMITATIONS = (
    "scope is Ironclad battle-agent training input only",
    "default action space still excludes potion actions for the first pass",
    "battle-v0 reward keeps long-term ledger fields but gives them zero default weight",
    "non-combat decisions are driven separately and are not part of the battle agent",
    "readiness is an interface check, not evidence that the first trained policy is strong",
)


@dataclass(frozen=True)
class TrainingReadinessReport:
    """End-to-end pre-trainer readiness summary."""

    ready_for_first_training: bool
    source_rollout_count: int
    segment_count: int
    battle_example_count: int
    reward_label_count: int
    trainer_record_count: int
    model_example_count: int
    action_row_count: int
    score_count: int
    snapshot_feature_size: int | None
    action_feature_size: int | None
    has_battle_examples: bool
    reward_labels_aligned: bool
    trainer_contract_ok: bool
    trainer_dataset_round_trip_ok: bool
    model_input_ok: bool
    model_context_rebuild_ok: bool
    model_scoring_ok: bool
    problems: list[str] = field(default_factory=list)
    limitations: tuple[str, ...] = TRAINING_READINESS_LIMITATIONS
    source_identity: dict[str, Any] = field(
        default_factory=lightspeed_source_identity_dict
    )


def build_training_readiness_report(
    rollouts: list[ControlledRun],
    *,
    weights: BattleRewardWeights | None = None,
    scorer: BatchActionScorer | None = None,
) -> TrainingReadinessReport:
    """Run no-training checks across the full future trainer data path."""

    labeled_batch = build_reward_labeled_battle_decision_batch(rollouts, weights)
    trainer_contract = build_trainer_input_contract_report(labeled_batch)
    trainer_dataset_report = build_trainer_input_dataset_smoke_report(labeled_batch)
    trainer_dataset = build_trainer_input_dataset(labeled_batch)
    model_input_report = build_model_input_batch_smoke_report(trainer_dataset)
    model_batch = build_model_input_batch(trainer_dataset)
    score_report = score_model_input_batch(model_batch, scorer)

    battle_example_count = len(labeled_batch.decision_batch.examples)
    reward_label_count = len(labeled_batch.reward_labels)
    has_battle_examples = battle_example_count > 0
    reward_labels_aligned = battle_example_count == reward_label_count
    checks = {
        "battle examples present": has_battle_examples,
        "reward labels aligned": reward_labels_aligned,
        "trainer input contract": trainer_contract.contract_ok,
        "trainer dataset JSONL round trip": trainer_dataset_report.round_trip_ok,
        "model input packing": model_input_report.model_input_ok,
        "model context rebuild": model_input_report.context_rebuild_ok,
        "model score contract": score_report.scoring_ok,
    }
    problems = _readiness_problems(checks)
    problems.extend(f"reward batch: {problem}" for problem in labeled_batch.problems)
    problems.extend(
        f"trainer contract: {problem}" for problem in trainer_contract.problems
    )
    problems.extend(
        f"trainer dataset: {problem}" for problem in trainer_dataset_report.problems
    )
    problems.extend(
        f"model input: {problem}" for problem in model_input_report.problems
    )
    problems.extend(f"model score: {problem}" for problem in score_report.problems)

    return TrainingReadinessReport(
        ready_for_first_training=not problems,
        source_rollout_count=labeled_batch.source_rollout_count,
        segment_count=labeled_batch.segment_count,
        battle_example_count=battle_example_count,
        reward_label_count=reward_label_count,
        trainer_record_count=trainer_dataset_report.record_count,
        model_example_count=model_input_report.example_count,
        action_row_count=model_input_report.action_rows,
        score_count=score_report.score_count,
        snapshot_feature_size=labeled_batch.decision_batch.snapshot_feature_size,
        action_feature_size=labeled_batch.decision_batch.action_feature_size,
        has_battle_examples=has_battle_examples,
        reward_labels_aligned=reward_labels_aligned,
        trainer_contract_ok=trainer_contract.contract_ok,
        trainer_dataset_round_trip_ok=trainer_dataset_report.round_trip_ok,
        model_input_ok=model_input_report.model_input_ok,
        model_context_rebuild_ok=model_input_report.context_rebuild_ok,
        model_scoring_ok=score_report.scoring_ok,
        problems=problems,
    )


def format_training_readiness_report(report: TrainingReadinessReport) -> str:
    """Format training-readiness checks for stderr."""

    lines = [
        "Training readiness summary",
        "scope: first battle-agent trainer readiness only; no training is run",
        format_lightspeed_source_identity(report.source_identity),
        f"ready for first training: {_yes_no(report.ready_for_first_training)}",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"battle examples: {report.battle_example_count}",
        f"reward labels: {report.reward_label_count}",
        f"trainer records: {report.trainer_record_count}",
        f"model examples: {report.model_example_count}",
        f"action rows: {report.action_row_count}",
        f"scores: {report.score_count}",
        f"snapshot feature size: {_optional_int(report.snapshot_feature_size)}",
        f"action feature size: {_optional_int(report.action_feature_size)}",
        "checks:",
        f"  battle examples present: {_yes_no(report.has_battle_examples)}",
        f"  reward labels aligned: {_yes_no(report.reward_labels_aligned)}",
        f"  trainer input contract: {_yes_no(report.trainer_contract_ok)}",
        (
            "  trainer dataset JSONL round trip: "
            f"{_yes_no(report.trainer_dataset_round_trip_ok)}"
        ),
        f"  model input packing: {_yes_no(report.model_input_ok)}",
        f"  model context rebuild: {_yes_no(report.model_context_rebuild_ok)}",
        f"  model score contract: {_yes_no(report.model_scoring_ok)}",
    ]

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    lines.append("limitations:")
    lines.extend(f"  {limitation}" for limitation in report.limitations)
    return "\n".join(lines)


def _readiness_problems(checks: dict[str, bool]) -> list[str]:
    return [f"check failed: {name}" for name, passed in checks.items() if not passed]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_int(value: object) -> str:
    return str(value) if value is not None else "(none)"
