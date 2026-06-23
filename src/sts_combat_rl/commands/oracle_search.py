"""Focused T006 workflows for Oracle search teacher data and evaluation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import load_natural_battle_start_pool_jsonl
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
    format_fixed_evaluation_report,
)
from sts_combat_rl.sim.fixed_evaluation_set import FixedCohort, load_fixed_cohort_jsonl
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import (
    OracleTeacherDataset,
    build_oracle_teacher_dataset_report,
    collect_oracle_teacher_dataset_from_pool,
    dump_oracle_teacher_dataset_jsonl,
    format_oracle_teacher_dataset_report,
)


@dataclass(frozen=True)
class OracleFixedEvaluationComparison:
    """Same-cohort comparison for Oracle root-selection diagnostics."""

    primary_selection_rule: str
    highest_mean: FixedEvaluationReport
    most_visits: FixedEvaluationReport

    @property
    def primary_report(self) -> FixedEvaluationReport:
        if self.primary_selection_rule == "most_visits":
            return self.most_visits
        return self.highest_mean

    @property
    def evaluation_successful(self) -> bool:
        return (
            self.highest_mean.evaluation_successful
            and self.most_visits.evaluation_successful
        )


def collect_oracle_teacher_from_pool_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool_path: Path,
    controller: OracleSearchController,
    *,
    action_space: ActionSpaceConfig,
) -> OracleTeacherDataset:
    """Load a portable pool and collect current-schema Oracle teacher rows."""

    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    return collect_oracle_teacher_dataset_from_pool(
        adapter_factory,
        pool,
        controller,
        action_space=action_space,
    )


def write_oracle_teacher_dataset(path: Path, dataset: OracleTeacherDataset) -> None:
    """Write an Oracle teacher dataset JSONL artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_teacher_dataset_jsonl(dataset, stream)


def format_oracle_teacher_collection(dataset: OracleTeacherDataset) -> str:
    """Format teacher collection report."""

    return format_oracle_teacher_dataset_report(
        build_oracle_teacher_dataset_report(dataset)
    )


def run_oracle_fixed_evaluation_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    controller: OracleSearchController,
    *,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> FixedEvaluationReport:
    """Load an immutable fixed cohort and evaluate an Oracle controller."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    return _evaluate_oracle_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=controller,
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )


def run_oracle_fixed_evaluation_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    simulations: int,
    primary_selection_rule: str,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> OracleFixedEvaluationComparison:
    """Evaluate highest-mean and visit-count Oracle rules on one fixed cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    highest_mean = _evaluate_oracle_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=OracleSearchController(
            simulations=simulations,
            root_selection_rule="highest_mean",
            action_space=action_space,
        ),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    most_visits = _evaluate_oracle_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=OracleSearchController(
            simulations=simulations,
            root_selection_rule="most_visits",
            action_space=action_space,
        ),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    return OracleFixedEvaluationComparison(
        primary_selection_rule=primary_selection_rule,
        highest_mean=highest_mean,
        most_visits=most_visits,
    )


def _evaluate_oracle_fixed_cohort(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort: FixedCohort,
    controller: OracleSearchController,
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


def format_oracle_fixed_evaluation_report(report: FixedEvaluationReport) -> str:
    """Format Oracle fixed-evaluation output with source identity."""

    return "\n\n".join(
        [
            format_lightspeed_source_identity(),
            _format_oracle_evaluation_telemetry(report),
            format_fixed_evaluation_report(report),
        ]
    )


def format_oracle_fixed_evaluation_comparison(
    comparison: OracleFixedEvaluationComparison,
) -> str:
    """Format same-cohort highest-mean vs most-visits Oracle evaluation."""

    return "\n\n".join(
        [
            format_lightspeed_source_identity(),
            "Oracle fixed evaluation comparison",
            f"primary selection rule: {comparison.primary_selection_rule}",
            "highest_mean",
            _format_oracle_evaluation_telemetry(comparison.highest_mean),
            format_fixed_evaluation_report(comparison.highest_mean),
            "most_visits diagnostic",
            _format_oracle_evaluation_telemetry(comparison.most_visits),
            format_fixed_evaluation_report(comparison.most_visits),
        ]
    )


def _format_oracle_evaluation_telemetry(report: FixedEvaluationReport) -> str:
    decision_reports = list(_iter_oracle_decision_reports(report))
    mean_values: list[float] = []
    best_values: list[float] = []
    min_values: list[float] = []
    for decision_report in decision_reports:
        best = _optional_float(decision_report.get("best_action_value"))
        if best is not None:
            best_values.append(best)
        minimum = _optional_float(decision_report.get("min_action_value"))
        if minimum is not None:
            min_values.append(minimum)
        root_actions = decision_report.get("root_actions")
        if isinstance(root_actions, list):
            for action in root_actions:
                if isinstance(action, dict):
                    mean = _optional_float(action.get("mean_value"))
                    if mean is not None:
                        mean_values.append(mean)

    return "\n".join(
        [
            "Oracle search compute telemetry",
            (
                "decisions: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_decision_count",
                    )
                )
            ),
            (
                "simulations requested: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_simulations",
                    )
                )
            ),
            (
                "root visits: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_root_visits",
                    )
                )
            ),
            (
                "native simulator steps: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_native_simulator_steps",
                    )
                )
            ),
            f"model calls: {_format_model_calls(report)}",
            (
                "wall-clock seconds: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_wall_clock_time_s",
                    ),
                    precision=6,
                )
            ),
            (
                "root rows: "
                + _format_optional_number(
                    _sum_numeric_telemetry(report, "oracle_search_root_row_count")
                )
            ),
            (
                "unmapped root rows: "
                + _format_optional_number(
                    _sum_numeric_telemetry(report, "oracle_search_unmapped_root_rows")
                )
            ),
            (
                "unsearched legal actions: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_unsearched_legal_actions",
                    )
                )
            ),
            (
                "unmapped search edges: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_unmapped_search_edges",
                    )
                )
            ),
            (
                "root mapping failures: "
                + _format_optional_number(
                    _sum_numeric_telemetry(
                        report,
                        "oracle_search_root_mapping_failures",
                    )
                )
            ),
            f"root mean values: {_format_range(mean_values)}",
            f"best root values: {_format_range(best_values)}",
            f"min root values: {_format_range(min_values)}",
        ]
    )


def _sum_numeric_telemetry(report: FixedEvaluationReport, key: str) -> float | None:
    total = 0.0
    seen = False
    for result in report.battle_results:
        telemetry = result.controller_compute_telemetry or {}
        value = telemetry.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total += float(value)
            seen = True
    return total if seen else None


def _format_model_calls(report: FixedEvaluationReport) -> str:
    numeric = _sum_numeric_telemetry(report, "oracle_search_model_calls")
    if numeric is not None:
        return _format_optional_number(numeric)
    values: list[Any] = []
    for result in report.battle_results:
        telemetry = result.controller_compute_telemetry or {}
        value = telemetry.get("oracle_search_model_calls")
        if isinstance(value, list):
            values.extend(value)
        elif value is not None:
            values.append(value)
    if not values or all(value is None for value in values):
        return "none (native search)"
    return ", ".join(str(value) for value in values)


def _iter_oracle_decision_reports(
    report: FixedEvaluationReport,
) -> list[dict[str, Any]]:
    decision_reports: list[dict[str, Any]] = []
    for result in report.battle_results:
        telemetry = result.controller_compute_telemetry or {}
        value = telemetry.get("oracle_search_decision_reports")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    decision_reports.append(item)
                elif isinstance(item, list):
                    decision_reports.extend(
                        nested for nested in item if isinstance(nested, dict)
                    )
    return decision_reports


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _format_optional_number(value: float | None, *, precision: int = 0) -> str:
    if value is None:
        return "(missing)"
    if precision:
        return f"{value:.{precision}f}"
    if value.is_integer():
        return str(int(value))
    return f"{value:.3f}"


def _format_range(values: list[float]) -> str:
    if not values:
        return "(missing)"
    return f"min={min(values):.6f}, max={max(values):.6f}"
