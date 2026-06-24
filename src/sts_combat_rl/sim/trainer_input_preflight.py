"""Offline preflight checks for exported trainer input JSONL.

This validates an already-exported trainer input artifact without touching the
simulator or PyTorch.  The optional broad-training gate is included so a user
can see whether a dataset is merely shape-valid or genuinely broad-trainable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.model_input import (
    ModelInputBatchSmokeReport,
    build_model_input_batch,
    build_model_input_batch_smoke_report,
)
from sts_combat_rl.sim.model_scoring import (
    BatchActionScorer,
    ModelScoreSmokeReport,
    score_model_input_batch,
)
from sts_combat_rl.sim.trainer_input import TrainerInputDataset
from sts_combat_rl.sim.training_gate import (
    TRAINING_GATE_OVERRIDE_NONE,
    TrainingGateReport,
    TrainingScaleGateConfig,
    build_training_gate_report,
    format_training_gate_report,
)


@dataclass(frozen=True)
class TrainerInputPreflightReport:
    """Offline readiness summary for one exported trainer input dataset."""

    path_label: str
    format_version: int
    reward_allocation: str
    source_rollout_count: int
    segment_count: int
    record_count: int
    snapshot_feature_size: int | None
    action_feature_size: int | None
    migration_source_version: int
    migration_target_version: int
    migration_losses: tuple[str, ...] = ()
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    has_records: bool = False
    model_input_report: ModelInputBatchSmokeReport | None = None
    score_report: ModelScoreSmokeReport | None = None
    training_gate_report: TrainingGateReport | None = None
    preflight_ok: bool = False
    problems: list[str] = field(default_factory=list)


def build_trainer_input_preflight_report(
    dataset: TrainerInputDataset,
    *,
    path_label: str = "(memory)",
    scorer: BatchActionScorer | None = None,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = TRAINING_GATE_OVERRIDE_NONE,
) -> TrainerInputPreflightReport:
    """Validate one loaded trainer input dataset without running training."""

    model_input_report = build_model_input_batch_smoke_report(dataset)
    model_batch = build_model_input_batch(dataset)
    score_report = score_model_input_batch(model_batch, scorer)
    gate_report = build_training_gate_report(
        dataset,
        gate_config,
        override=gate_override,
    )
    has_records = bool(dataset.records)
    checks = {
        "trainer records present": has_records,
        "model input packing": model_input_report.model_input_ok,
        "model context rebuild": model_input_report.context_rebuild_ok,
        "model score contract": score_report.scoring_ok,
    }
    problems = _check_problems(checks)
    _extend_unique(problems, (f"dataset: {problem}" for problem in dataset.problems))
    _extend_unique(
        problems,
        (f"model input: {problem}" for problem in model_input_report.problems),
    )
    _extend_unique(
        problems,
        (f"model score: {problem}" for problem in score_report.problems),
    )

    return TrainerInputPreflightReport(
        path_label=path_label,
        format_version=dataset.format_version,
        reward_allocation=dataset.reward_allocation,
        source_rollout_count=dataset.source_rollout_count,
        segment_count=dataset.segment_count,
        record_count=len(dataset.records),
        snapshot_feature_size=dataset.snapshot_feature_size,
        action_feature_size=dataset.action_feature_size,
        migration_source_version=dataset.migration_report.source_version,
        migration_target_version=dataset.migration_report.target_version,
        migration_losses=dataset.migration_report.losses,
        generation_metadata=dict(dataset.generation_metadata),
        has_records=has_records,
        model_input_report=model_input_report,
        score_report=score_report,
        training_gate_report=gate_report,
        preflight_ok=not problems,
        problems=problems,
    )


def format_trainer_input_preflight_report(
    report: TrainerInputPreflightReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format an offline trainer input preflight report for stderr."""

    model_report = report.model_input_report
    score_report = report.score_report
    lines = [
        "Trainer input preflight summary",
        (
            "scope: offline exported-dataset preflight only; no simulator, "
            "trainer, environment, or RL algorithm"
        ),
        f"path: {report.path_label}",
        f"preflight ok: {_yes_no(report.preflight_ok)}",
        f"format version: {report.format_version}",
        f"loaded artifact version: {report.migration_source_version}",
        f"in-memory artifact version: {report.migration_target_version}",
        f"reward allocation: {report.reward_allocation}",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"records: {report.record_count}",
        f"snapshot feature size: {_optional_int(report.snapshot_feature_size)}",
        f"action feature size: {_optional_int(report.action_feature_size)}",
        "checks:",
        f"  trainer records present: {_yes_no(report.has_records)}",
        f"  model input packing: {_yes_no(_model_input_ok(model_report))}",
        f"  model context rebuild: {_yes_no(_context_rebuild_ok(model_report))}",
        f"  model score contract: {_yes_no(_score_ok(score_report))}",
    ]

    _append_model_input_section(lines, model_report)
    _append_score_section(lines, score_report, detail_limit)
    _append_metadata(lines, report.generation_metadata)
    lines.append("migration losses:")
    if report.migration_losses:
        lines.extend(f"  {loss}" for loss in report.migration_losses)
    else:
        lines.append("  (none)")

    if report.training_gate_report is not None:
        lines.append("")
        lines.append(format_training_gate_report(report.training_gate_report))

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _append_model_input_section(
    lines: list[str],
    report: ModelInputBatchSmokeReport | None,
) -> None:
    lines.append("model input:")
    if report is None:
        lines.append("  (not built)")
        return
    lines.extend(
        [
            f"  examples: {report.example_count}",
            f"  snapshot rows: {report.snapshot_rows}",
            f"  action rows: {report.action_rows}",
            f"  action offsets: {report.action_offset_count}",
            f"  max legal actions: {report.max_legal_actions}",
            f"  max eligible actions: {report.max_eligible_actions}",
            f"  terminal_after_step records: {report.terminal_after_step_count}",
            f"  step reward total: {report.step_reward_total:.3f}",
            f"  return-to-go total: {report.return_to_go_total:.3f}",
        ]
    )
    _append_counter(lines, "  screen states", report.screen_state_counts)
    _append_counter(lines, "  collected action kinds", report.chosen_action_kind_counts)


def _append_score_section(
    lines: list[str],
    report: ModelScoreSmokeReport | None,
    detail_limit: int,
) -> None:
    lines.append("model scores:")
    if report is None:
        lines.append("  (not scored)")
        return
    denominator = report.selection_count if report.selection_count else 0
    lines.extend(
        [
            f"  scorer: {report.scorer_name}",
            f"  action rows: {report.action_rows}",
            f"  scores: {report.score_count}",
            f"  selections: {report.selection_count}",
            (
                "  agreement with collected actions: "
                f"{report.chosen_action_agreement}/{denominator}"
            ),
            f"  min score: {_optional_score(report.min_score)}",
            f"  max score: {_optional_score(report.max_score)}",
        ]
    )
    _append_counter(
        lines, "  selected action kinds", report.selected_action_kind_counts
    )
    _append_counter(lines, "  selected score values", report.selected_score_counts)
    _append_selection_examples(lines, report, detail_limit)


def _append_selection_examples(
    lines: list[str],
    report: ModelScoreSmokeReport,
    detail_limit: int,
) -> None:
    lines.append(f"  selection examples (limit {detail_limit}):")
    if detail_limit <= 0:
        lines.append("    (disabled)")
        return
    if not report.selections:
        lines.append("    (none)")
        return
    for selection in report.selections[:detail_limit]:
        lines.append(
            "    "
            f"example={selection.example_index} "
            f"selected={selection.selected_action_kind}"
            f"[{selection.selected_action_index}] "
            f"score={selection.selected_score:.3f} "
            f"collected={selection.chosen_action_kind}"
            f"[{selection.chosen_action_index}] "
            f"match={_yes_no(selection.matches_chosen_action)}"
        )


def _append_metadata(lines: list[str], metadata: dict[str, Any]) -> None:
    lines.append("generation metadata:")
    if not metadata:
        lines.append("  (none)")
        return
    for key in sorted(metadata):
        lines.append(f"  {key}: {metadata[key]}")


def _append_counter(
    lines: list[str],
    title: str,
    counter: Counter[str],
) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("    (none)")
        return
    for key, count in counter.most_common():
        lines.append(f"    {key}: {count}")


def _check_problems(checks: dict[str, bool]) -> list[str]:
    return [f"check failed: {name}" for name, passed in checks.items() if not passed]


def _extend_unique(problems: list[str], values: Iterable[str]) -> None:
    for value in values:
        if value not in problems:
            problems.append(value)


def _model_input_ok(report: ModelInputBatchSmokeReport | None) -> bool:
    return bool(report and report.model_input_ok)


def _context_rebuild_ok(report: ModelInputBatchSmokeReport | None) -> bool:
    return bool(report and report.context_rebuild_ok)


def _score_ok(report: ModelScoreSmokeReport | None) -> bool:
    return bool(report and report.scoring_ok)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_int(value: object) -> str:
    return str(value) if value is not None else "(none)"


def _optional_score(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "(none)"
