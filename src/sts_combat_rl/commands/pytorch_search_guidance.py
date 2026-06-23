"""Focused T009 workflows for optional PyTorch search guidance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.trainer_input import load_trainer_input_dataset_jsonl
from sts_combat_rl.sim.trainer_input_preflight import (
    TrainerInputPreflightReport,
    build_trainer_input_preflight_report,
    format_trainer_input_preflight_report,
)
from sts_combat_rl.sim.training_gate import (
    TrainingGateReport,
    TrainingScaleGateConfig,
    build_training_gate_report,
    format_training_gate_report,
)


@dataclass(frozen=True)
class PytorchSearchGuidanceTrainingWorkflowReport:
    """One offline training attempt over an exported trainer-input dataset."""

    trainer_input_path: Path
    checkpoint_path: Path | None
    gate_report: TrainingGateReport
    checkpoint_written: bool
    training_report: Any | None = None
    problems: tuple[str, ...] = ()

    @property
    def command_ok(self) -> bool:
        return (
            self.gate_report.training_allowed
            and self.training_report is not None
            and bool(getattr(self.training_report, "training_ok", False))
            and self.checkpoint_written
            and not self.problems
        )


def build_trainer_input_preflight_from_path(
    path: Path,
    *,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> TrainerInputPreflightReport:
    """Load a trainer-input JSONL artifact and run offline preflight checks."""

    with path.open("r", encoding="utf-8") as stream:
        dataset = load_trainer_input_dataset_jsonl(stream)
    return build_trainer_input_preflight_report(
        dataset,
        path_label=str(path),
        gate_config=gate_config,
        gate_override=gate_override,
    )


def format_trainer_input_preflight_from_path_report(
    report: TrainerInputPreflightReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format an offline trainer-input preflight report."""

    return format_trainer_input_preflight_report(report, detail_limit=detail_limit)


def run_pytorch_search_guidance_training_from_path(
    trainer_input_path: Path,
    checkpoint_path: Path,
    *,
    training_config: Any,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> PytorchSearchGuidanceTrainingWorkflowReport:
    """Run the T009 gate and, only if allowed, train and save a checkpoint."""

    with trainer_input_path.open("r", encoding="utf-8") as stream:
        dataset = load_trainer_input_dataset_jsonl(stream)
    gate_report = build_training_gate_report(
        dataset,
        gate_config,
        override=gate_override,
    )
    if not gate_report.training_allowed:
        return PytorchSearchGuidanceTrainingWorkflowReport(
            trainer_input_path=trainer_input_path,
            checkpoint_path=checkpoint_path,
            gate_report=gate_report,
            checkpoint_written=False,
            problems=("training gate did not allow this dataset",),
        )

    from sts_combat_rl.sim.torch_policy_value import (
        save_torch_policy_value_checkpoint,
        train_torch_policy_value,
    )

    result = train_torch_policy_value(
        dataset,
        training_config,
        gate_report=gate_report,
    )
    problems: list[str] = []
    checkpoint_written = False
    if result.report.training_ok:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        save_torch_policy_value_checkpoint(
            result,
            str(checkpoint_path),
            training_data_provenance={
                "trainer_input_path": str(trainer_input_path),
                "trainer_input_format_version": dataset.format_version,
                "trainer_record_count": len(dataset.records),
                "source_rollout_count": dataset.source_rollout_count,
                "segment_count": dataset.segment_count,
                "generation_metadata": dict(dataset.generation_metadata),
                "gate_report": gate_report.to_dict(),
            },
            metadata={
                "task_id": "T009",
                "checkpoint_role": "search_guidance_policy_value",
            },
        )
        checkpoint_written = True
    else:
        problems.append("training report was not ok; checkpoint was not written")
    return PytorchSearchGuidanceTrainingWorkflowReport(
        trainer_input_path=trainer_input_path,
        checkpoint_path=checkpoint_path,
        gate_report=gate_report,
        checkpoint_written=checkpoint_written,
        training_report=result.report,
        problems=tuple(problems),
    )


def format_pytorch_search_guidance_training_workflow_report(
    report: PytorchSearchGuidanceTrainingWorkflowReport,
) -> str:
    """Format the offline T009 training workflow for stderr."""

    sections = [
        format_training_gate_report(report.gate_report),
        "PyTorch search-guidance workflow",
        f"trainer input: {report.trainer_input_path}",
        f"checkpoint path: {report.checkpoint_path or '(none)'}",
        f"checkpoint written: {_yes_no(report.checkpoint_written)}",
    ]
    if report.training_report is not None:
        from sts_combat_rl.sim.torch_policy_value import (
            format_torch_policy_value_training_report,
        )

        sections.append(
            format_torch_policy_value_training_report(report.training_report)
        )
    else:
        sections.extend(
            [
                "PyTorch search-guidance training summary",
                "training ok: no",
                "raw policy diagnostic: not_run",
                "search-guided fixed evaluation: not_run",
            ]
        )
    sections.append("workflow problems:")
    if report.problems:
        sections.extend(f"  {problem}" for problem in report.problems)
    else:
        sections.append("  (none)")
    return "\n\n".join(sections)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
