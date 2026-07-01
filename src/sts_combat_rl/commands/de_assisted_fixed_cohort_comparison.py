"""Command helpers for T044 de-assisted fixed-cohort comparison."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    DeAssistedFixedCohortComparisonReport,
    build_de_assisted_fixed_cohort_comparison_report,
    dump_de_assisted_fixed_cohort_comparison_jsonl,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
)
from sts_combat_rl.sim.fixed_evaluation_set import FixedCohort, load_fixed_cohort_jsonl


ControllerArmSpec = tuple[str, str, OnlineController]


def run_de_assisted_fixed_cohort_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    controller_arms: Sequence[ControllerArmSpec],
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    run_scale: str,
) -> DeAssistedFixedCohortComparisonReport:
    """Evaluate every configured arm on one immutable fixed cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)

    evaluated: list[tuple[str, str, FixedEvaluationReport]] = []
    for label, role, controller in controller_arms:
        evaluated.append(
            (
                label,
                role,
                _evaluate_with_cohort_counts(
                    adapter_factory=adapter_factory,
                    cohort=cohort,
                    controller=controller,
                    action_space=action_space,
                    max_battle_steps=max_battle_steps,
                ),
            )
        )

    return build_de_assisted_fixed_cohort_comparison_report(
        arms=evaluated,
        comparison_config={
            "task_id": "T044",
            "run_scale": run_scale,
            "cohort_path": str(cohort_path),
            "cohort_identity": cohort.identity,
            "cohort_record_count": len(cohort.records),
            "cohort_source_distribution_summary": _cohort_distribution_summary(cohort),
            "action_space": action_space.to_dict(),
            "max_battle_steps": max_battle_steps,
            "controller_roles": {label: role for label, role, _ in controller_arms},
            "controller_provenance": {
                label: controller.provenance.to_dict()
                for label, _, controller in controller_arms
            },
            "checkpoint_provenance": {
                label: _checkpoint_provenance(controller)
                for label, _, controller in controller_arms
                if _checkpoint_provenance(controller)
            },
        },
    )


def write_de_assisted_fixed_cohort_comparison_report(
    path: Path,
    report: DeAssistedFixedCohortComparisonReport,
) -> None:
    """Write a current-schema T044 comparison JSONL artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_de_assisted_fixed_cohort_comparison_jsonl(report, stream)


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


def _cohort_distribution_summary(cohort: FixedCohort) -> dict[str, Any]:
    distributions: Counter[str] = Counter()
    assistance_levels: Counter[str] = Counter()
    acts: Counter[str] = Counter()
    room_types: Counter[str] = Counter()
    for record in cohort.records:
        metadata = record.structural_metadata
        distributions[str(metadata.get("distribution_kind") or "missing")] += 1
        assistance_levels[
            str(metadata.get("assistance_level") or "unassisted_or_missing")
        ] += 1
        acts[str(metadata.get("act") or "missing")] += 1
        room_types[str(metadata.get("room_type") or "missing")] += 1
    return {
        "distribution_kind_counts": _counter_dict(distributions),
        "assistance_level_counts": _counter_dict(assistance_levels),
        "act_counts": _counter_dict(acts),
        "room_type_counts": _counter_dict(room_types),
    }


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


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter)}
