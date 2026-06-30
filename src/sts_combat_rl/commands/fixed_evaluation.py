"""Focused T005 workflows for fixed structural battle evaluation."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import TextIO

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_SOURCE_POOL_SCHEMA_ID,
    load_assisted_source_pool_jsonl,
)
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

    # Attach per-stratum source counts for natural weighting.
    evaluation = FixedEvaluationReport(
        cohort_identity=evaluation.cohort_identity,
        controller_provenance=evaluation.controller_provenance,
        information_regime=evaluation.information_regime,
        action_space_config=evaluation.action_space_config,
        max_battle_steps=evaluation.max_battle_steps,
        source_pool_format_version=evaluation.source_pool_format_version,
        selection_config=evaluation.selection_config,
        per_stratum_source_counts={
            "/".join(str(v) for v in s): c
            for s, c in coverage.per_stratum_source_counts.items()
        },
        battle_results=evaluation.battle_results,
        problems=evaluation.problems,
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
        pool = _load_source_pool_jsonl(stream)

    return run_fixed_evaluation(
        adapter_factory=adapter_factory,
        pool=pool,
        controller=controller,
        selection_seed=selection_seed,
        stratum_quota=stratum_quota,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )


def _load_source_pool_jsonl(stream: TextIO) -> NaturalBattleStartPool:
    schema_id = _peek_metadata_schema_id(stream)
    stream.seek(0)
    if schema_id == ASSISTED_SOURCE_POOL_SCHEMA_ID:
        return load_assisted_source_pool_jsonl(stream).pool
    return load_natural_battle_start_pool_jsonl(stream)


def _peek_metadata_schema_id(stream: TextIO) -> str | None:
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        if row.get("type") != "metadata":
            return None
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        schema_id = metadata.get("schema_id")
        return str(schema_id) if isinstance(schema_id, str) else None
    return None


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
