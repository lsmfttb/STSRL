"""Focused T005 workflows for fixed structural battle evaluation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
    load_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.fixed_evaluation_set import (
    CohortCoverageReport,
    FixedCohort,
    dump_fixed_cohort_jsonl,
    load_fixed_cohort_jsonl,
    select_fixed_cohort,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    dump_fixed_evaluation_report_jsonl,
    evaluate_fixed_cohort,
    load_fixed_evaluation_report_jsonl,
)


def run_fixed_evaluation(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool: NaturalBattleStartPool,
    controller: OnlineController,
    *,
    selection_seed: int,
    stratum_quota: int = 1,
    action_space: ActionSpaceConfig | None = None,
    max_battle_steps: int = 200,
) -> tuple[FixedCohort, CohortCoverageReport, FixedEvaluationReport]:
    """Select a cohort from a pool and evaluate the given controller.

    This is the primary T005 workflow: it deterministically selects a
    structural cohort, restores each record in a fresh adapter, and plays
    one bounded battle per record with the supplied controller.

    Returns the cohort, its coverage report, and the evaluation report.
    Truncations, restore failures, and illegal selections make the evaluation
    fail.
    """

    cohort, coverage = select_fixed_cohort(
        pool,
        selection_seed=selection_seed,
        stratum_quota=stratum_quota,
    )

    evaluation = evaluate_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort_records=cohort.records,
        controller=controller,
        cohort_identity=cohort.identity,
        source_pool_format_version=pool.format_version,
        selection_config=cohort.selection_config.to_dict(),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )

    return cohort, coverage, evaluation


def run_fixed_evaluation_from_pool_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool_path: Path,
    controller: OnlineController,
    *,
    selection_seed: int,
    stratum_quota: int = 1,
    action_space: ActionSpaceConfig | None = None,
    max_battle_steps: int = 200,
) -> tuple[FixedCohort, CohortCoverageReport, FixedEvaluationReport]:
    """Load a portable pool, select a cohort, and evaluate."""

    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)

    return run_fixed_evaluation(
        adapter_factory=adapter_factory,
        pool=pool,
        controller=controller,
        selection_seed=selection_seed,
        stratum_quota=stratum_quota,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )


def write_fixed_cohort(path: Path, cohort: FixedCohort) -> None:
    """Write a current-schema fixed cohort to the requested path."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(cohort, stream)


def write_fixed_evaluation_report(
    path: Path,
    report: FixedEvaluationReport,
) -> None:
    """Write a current-schema evaluation report to the requested path."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_evaluation_report_jsonl(report, stream)


def load_cohort_from_path(path: Path) -> FixedCohort:
    """Load a portable fixed cohort from a JSONL file."""

    with path.open("r", encoding="utf-8") as stream:
        return load_fixed_cohort_jsonl(stream)


def load_evaluation_report_from_path(path: Path) -> FixedEvaluationReport:
    """Load a portable evaluation report from a JSONL file."""

    with path.open("r", encoding="utf-8") as stream:
        return load_fixed_evaluation_report_jsonl(stream)
