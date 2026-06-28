"""Command helpers for T029 fixed-cohort search comparison."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
)
from sts_combat_rl.sim.fixed_evaluation_set import FixedCohort, load_fixed_cohort_jsonl
from sts_combat_rl.sim.model_guided_search_comparison import (
    ModelGuidedSearchFixedComparisonReport,
    ModelGuidedSearchV2FixedComparisonReport,
    build_model_guided_search_fixed_comparison_report,
    build_model_guided_search_v2_fixed_comparison_report,
    dump_model_guided_search_fixed_comparison_jsonl,
    dump_model_guided_search_v2_fixed_comparison_jsonl,
)


def run_model_guided_search_fixed_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    baseline_controller: OnlineController,
    model_guided_controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    run_scale: str,
) -> ModelGuidedSearchFixedComparisonReport:
    """Evaluate both search controllers on one immutable fixed cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)

    baseline_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=baseline_controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    model_guided_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=model_guided_controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    return build_model_guided_search_fixed_comparison_report(
        baseline_report=baseline_report,
        model_guided_report=model_guided_report,
        comparison_config={
            "run_scale": run_scale,
            "cohort_path": str(cohort_path),
            "cohort_identity": cohort.identity,
            "cohort_record_count": len(cohort.records),
            "baseline_role": "baseline_oracle_search",
            "model_guided_role": "model_guided_oracle_search",
            "action_space": action_space.to_dict(),
            "max_battle_steps": max_battle_steps,
            "baseline_controller_provenance": (
                baseline_controller.provenance.to_dict()
            ),
            "model_guided_controller_provenance": (
                model_guided_controller.provenance.to_dict()
            ),
            "model_guided_checkpoint_provenance": _checkpoint_provenance(
                model_guided_controller
            ),
        },
    )


def run_model_guided_search_v2_fixed_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    baseline_controller: OnlineController,
    model_guided_v1_controller: OnlineController,
    model_guided_v2_controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    run_scale: str,
) -> ModelGuidedSearchV2FixedComparisonReport:
    """Evaluate baseline, T028/v1, and T035/v2 controllers on one cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)

    baseline_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=baseline_controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    v1_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=model_guided_v1_controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    v2_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=model_guided_v2_controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    return build_model_guided_search_v2_fixed_comparison_report(
        baseline_report=baseline_report,
        model_guided_v1_report=v1_report,
        model_guided_v2_report=v2_report,
        comparison_config={
            "task_id": "T035",
            "run_scale": run_scale,
            "cohort_path": str(cohort_path),
            "cohort_identity": cohort.identity,
            "cohort_record_count": len(cohort.records),
            "baseline_role": "baseline_oracle_search",
            "model_guided_v1_role": "model_guided_oracle_search_v1",
            "model_guided_v2_role": "model_guided_oracle_search_v2",
            "action_space": action_space.to_dict(),
            "max_battle_steps": max_battle_steps,
            "baseline_controller_provenance": (
                baseline_controller.provenance.to_dict()
            ),
            "model_guided_v1_controller_provenance": (
                model_guided_v1_controller.provenance.to_dict()
            ),
            "model_guided_v2_controller_provenance": (
                model_guided_v2_controller.provenance.to_dict()
            ),
            "model_guided_v1_checkpoint_provenance": _checkpoint_provenance(
                model_guided_v1_controller
            ),
            "model_guided_v2_checkpoint_provenance": _checkpoint_provenance(
                model_guided_v2_controller
            ),
        },
    )


def write_model_guided_search_fixed_comparison_report(
    path: Path,
    report: ModelGuidedSearchFixedComparisonReport,
) -> None:
    """Write a current-schema T029 comparison JSONL artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_model_guided_search_fixed_comparison_jsonl(report, stream)


def write_model_guided_search_v2_fixed_comparison_report(
    path: Path,
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> None:
    """Write a current-schema T035 three-controller comparison artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_model_guided_search_v2_fixed_comparison_jsonl(report, stream)


def _evaluate_with_cohort_counts(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort: FixedCohort,
    controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> FixedEvaluationReport:
    evaluation = evaluate_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort_records=cohort.records,
        controller=controller,
        cohort_identity=cohort.identity,
        source_pool_format_version=cohort.source_pool_format_version,
        selection_config=cohort.selection_config.to_dict(),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    per_stratum_counts = Counter(
        "/".join(str(value) for value in record.structural_stratum)
        for record in cohort.records
    )
    return FixedEvaluationReport(
        cohort_identity=evaluation.cohort_identity,
        controller_provenance=evaluation.controller_provenance,
        information_regime=evaluation.information_regime,
        action_space_config=evaluation.action_space_config,
        max_battle_steps=evaluation.max_battle_steps,
        source_pool_format_version=evaluation.source_pool_format_version,
        selection_config=evaluation.selection_config,
        per_stratum_source_counts=dict(per_stratum_counts),
        battle_results=evaluation.battle_results,
        problems=evaluation.problems,
    )


def _checkpoint_provenance(controller: OnlineController) -> dict[str, Any]:
    value = getattr(controller, "checkpoint_provenance", None)
    if value is None:
        return {}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    if isinstance(value, dict):
        return dict(value)
    return {"unavailable": type(value).__name__}
