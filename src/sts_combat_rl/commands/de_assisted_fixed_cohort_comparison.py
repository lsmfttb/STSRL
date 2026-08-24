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
    record_range: str | None = None,
) -> DeAssistedFixedCohortComparisonReport:
    """Evaluate every configured arm on one immutable fixed cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)

    start, end = _validated_record_range(record_range, len(cohort.records))
    selected_records = cohort.records[start:end]
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
            "record_range": f"{start}:{end}",
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
    cohort_records: Sequence[Any] | None = None,
    controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> FixedEvaluationReport:
    evaluation = evaluate_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort_records=(cohort.records if cohort_records is None else cohort_records),
        controller=controller,
        cohort_identity=cohort.identity,
        source_pool_format_version=cohort.source_pool_format_version,
        selection_config=cohort.selection_config.to_dict(),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    per_stratum_counts = Counter(
        "/".join(str(value) for value in record.structural_stratum)
        for record in (cohort.records if cohort_records is None else cohort_records)
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


def merge_de_assisted_fixed_cohort_comparison_shards(
    *,
    cohort_path: Path,
    shards: Sequence[DeAssistedFixedCohortComparisonReport],
    expected_ranges: Sequence[str],
) -> DeAssistedFixedCohortComparisonReport:
    """Merge range/subset T044 reports in original cohort order."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    if len(shards) != len(expected_ranges) or not shards:
        raise ValueError("T044 shard merge requires every expected range")
    expected_labels = tuple(arm.label for arm in shards[0].arms)
    expected_roles = tuple(arm.role for arm in shards[0].arms)
    if not expected_labels:
        raise ValueError("T044 shard merge requires at least one controller arm")
    reports_by_label: dict[str, list[FixedEvaluationReport]] = {
        label: [] for label in expected_labels
    }
    common_config = dict(shards[0].comparison_config)
    for shard, record_range in zip(shards, expected_ranges, strict=True):
        if shard.comparison_config.get("record_range") != record_range:
            raise ValueError("T044 shard merge range/order mismatch")
        if tuple(arm.label for arm in shard.arms) != expected_labels:
            raise ValueError("T044 shard merge controller labels differ")
        if tuple(arm.role for arm in shard.arms) != expected_roles:
            raise ValueError("T044 shard merge persisted roles differ")
        for key in (
            "cohort_identity",
            "cohort_record_count",
            "action_space",
            "max_battle_steps",
            "controller_roles",
            "controller_provenance",
            "checkpoint_provenance",
        ):
            if shard.comparison_config.get(key) != common_config.get(key):
                raise ValueError(f"T044 shard merge configuration differs: {key}")
        for arm in shard.arms:
            reports_by_label[arm.label].append(arm.report)

    merged_arms: list[tuple[str, str, FixedEvaluationReport]] = []
    for label, role in zip(expected_labels, expected_roles, strict=True):
        reports = reports_by_label[label]
        first = reports[0]
        for report in reports[1:]:
            for field in (
                "cohort_identity",
                "controller_provenance",
                "information_regime",
                "action_space_config",
                "max_battle_steps",
                "source_pool_format_version",
                "selection_config",
            ):
                if getattr(report, field) != getattr(first, field):
                    raise ValueError(f"T044 fixed report configuration differs: {field}")
        results = [result for report in reports for result in report.battle_results]
        if [result.cohort_index for result in results] != list(range(len(cohort.records))):
            raise ValueError("T044 shard merge does not cover original cohort order")
        counts = Counter(
            "/".join(str(value) for value in record.structural_stratum)
            for record in cohort.records
        )
        merged_arms.append(
            (
                label,
                role,
                FixedEvaluationReport(
                    cohort_identity=first.cohort_identity,
                    controller_provenance=first.controller_provenance,
                    information_regime=first.information_regime,
                    action_space_config=first.action_space_config,
                    max_battle_steps=first.max_battle_steps,
                    source_pool_format_version=first.source_pool_format_version,
                    selection_config=first.selection_config,
                    per_stratum_source_counts=dict(counts),
                    battle_results=results,
                    problems=[problem for report in reports for problem in report.problems],
                ),
            )
        )
    common_config["record_range"] = f"0:{len(cohort.records)}"
    common_config["shard_ranges"] = list(expected_ranges)
    common_config["shard_count"] = len(expected_ranges)
    return build_de_assisted_fixed_cohort_comparison_report(
        arms=merged_arms,
        comparison_config=common_config,
    )


def _validated_record_range(value: str | None, count: int) -> tuple[int, int]:
    if value is None:
        return 0, count
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("T044 record range must use start:end")
    start, end = (int(part) for part in parts)
    if start < 0 or end < start or end > count:
        raise ValueError("T044 record range is outside the cohort")
    return start, end


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
