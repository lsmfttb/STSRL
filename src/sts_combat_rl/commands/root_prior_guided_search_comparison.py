"""Command helpers for T047 root-prior guided fixed-cohort comparison."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    load_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    RootPriorGuidedSearchComparisonReport,
    build_root_prior_guided_search_comparison_report,
    dump_root_prior_guided_search_comparison_jsonl,
)


ControllerArmSpec = tuple[str, str, OnlineController]


def run_root_prior_guided_search_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    controller_arms: Sequence[ControllerArmSpec],
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    run_scale: str,
    comparison_task_id: str = "T047",
    worker_count: int | None = None,
    shard_count: int | None = None,
    record_range: str | None = None,
) -> RootPriorGuidedSearchComparisonReport:
    """Evaluate every configured T047 arm on one immutable fixed cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    selected_records = _select_record_range(cohort.records, record_range)

    evaluated: list[tuple[str, str, FixedEvaluationReport]] = []
    for label, role, controller in controller_arms:
        evaluated.append(
            (
                label,
                role,
                _evaluate_with_cohort_counts(
                    adapter_factory=adapter_factory,
                    cohort=cohort,
                    cohort_records=selected_records,
                    controller=controller,
                    action_space=action_space,
                    max_battle_steps=max_battle_steps,
                    worker_count=worker_count,
                    shard_count=shard_count,
                ),
            )
        )

    return build_root_prior_guided_search_comparison_report(
        arms=evaluated,
        comparison_config={
            "task_id": comparison_task_id,
            "run_scale": run_scale,
            "cohort_path": str(cohort_path),
            "cohort_identity": cohort.identity,
            "cohort_total_record_count": len(cohort.records),
            "evaluated_record_count": len(selected_records),
            "record_range": record_range or "all",
            "cohort_source_distribution_summary": _cohort_distribution_summary(
                selected_records
            ),
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
            "worker_count": worker_count or 1,
            "shard_count": shard_count or 1,
        },
    )


def write_root_prior_guided_search_comparison_report(
    path: Path,
    report: RootPriorGuidedSearchComparisonReport,
) -> None:
    """Write a current-schema T047 comparison JSONL artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_root_prior_guided_search_comparison_jsonl(report, stream)


def _evaluate_with_cohort_counts(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort: FixedCohort,
    cohort_records: Sequence[FixedCohortRecord],
    controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    worker_count: int | None,
    shard_count: int | None,
) -> FixedEvaluationReport:
    workers = 1 if worker_count is None else int(worker_count)
    shards = 1 if shard_count is None else int(shard_count)
    if workers < 1:
        raise ValueError("root-prior comparison workers must be positive")
    if shards < 1:
        raise ValueError("root-prior comparison shard count must be positive")
    if not cohort_records:
        raise ValueError("root-prior comparison selected no cohort records")

    chunks = _record_chunks(cohort_records, shards)
    if workers == 1 or len(chunks) == 1:
        evaluation = evaluate_fixed_cohort(
            adapter_factory=adapter_factory,
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity=cohort.identity,
            source_pool_format_version=cohort.source_pool_format_version,
            selection_config=cohort.selection_config.to_dict(),
            action_space=action_space,
            max_battle_steps=max_battle_steps,
        )
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as executor:
            shard_reports = list(
                executor.map(
                    lambda records: evaluate_fixed_cohort(
                        adapter_factory=adapter_factory,
                        cohort_records=records,
                        controller=controller,
                        cohort_identity=cohort.identity,
                        source_pool_format_version=cohort.source_pool_format_version,
                        selection_config=cohort.selection_config.to_dict(),
                        action_space=action_space,
                        max_battle_steps=max_battle_steps,
                    ),
                    chunks,
                )
            )
        first = shard_reports[0]
        evaluation = FixedEvaluationReport(
            cohort_identity=first.cohort_identity,
            controller_provenance=first.controller_provenance,
            information_regime=first.information_regime,
            action_space_config=first.action_space_config,
            max_battle_steps=first.max_battle_steps,
            source_pool_format_version=first.source_pool_format_version,
            selection_config=first.selection_config,
            battle_results=sorted(
                [
                    result
                    for shard_report in shard_reports
                    for result in shard_report.battle_results
                ],
                key=lambda result: result.cohort_index,
            ),
            problems=[
                problem
                for shard_report in shard_reports
                for problem in shard_report.problems
            ],
        )
    per_stratum_counts = Counter(
        "/".join(str(value) for value in record.structural_stratum)
        for record in cohort_records
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


def _cohort_distribution_summary(
    cohort_records: Sequence[FixedCohortRecord],
) -> dict[str, Any]:
    distributions: Counter[str] = Counter()
    assistance_levels: Counter[str] = Counter()
    acts: Counter[str] = Counter()
    room_types: Counter[str] = Counter()
    encounters: Counter[str] = Counter()
    for record in cohort_records:
        metadata = record.structural_metadata
        distributions[str(metadata.get("distribution_kind") or "missing")] += 1
        assistance_levels[
            str(metadata.get("assistance_level") or "unassisted_or_missing")
        ] += 1
        acts[str(metadata.get("act") or "missing")] += 1
        room_types[str(metadata.get("room_type") or "missing")] += 1
        encounters[str(metadata.get("encounter_id") or "missing")] += 1
    return {
        "distribution_kind_counts": _counter_dict(distributions),
        "assistance_level_counts": _counter_dict(assistance_levels),
        "act_counts": _counter_dict(acts),
        "room_type_counts": _counter_dict(room_types),
        "encounter_id_counts": _counter_dict(encounters),
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


def _select_record_range(
    records: Sequence[FixedCohortRecord],
    record_range: str | None,
) -> list[FixedCohortRecord]:
    if record_range is None or record_range == "all":
        return list(records)
    parts = record_range.split(":", 1)
    if len(parts) != 2:
        raise ValueError("record range must use START:END")
    start = _parse_range_endpoint(parts[0], "record range start")
    end = _parse_range_endpoint(parts[1], "record range end")
    if start < 0 or end < start or end > len(records):
        raise ValueError("record range is outside cohort bounds")
    return list(records[start:end])


def _parse_range_endpoint(value: str, label: str) -> int:
    if not value:
        raise ValueError(f"{label} must be present")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    return parsed


def _record_chunks(
    records: Sequence[FixedCohortRecord],
    shard_count: int,
) -> list[list[FixedCohortRecord]]:
    effective_shards = max(1, min(shard_count, len(records)))
    chunks: list[list[FixedCohortRecord]] = [[] for _ in range(effective_shards)]
    for index, record in enumerate(records):
        chunks[index % effective_shards].append(record)
    return [chunk for chunk in chunks if chunk]
