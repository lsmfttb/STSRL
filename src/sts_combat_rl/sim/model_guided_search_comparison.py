"""Fixed-cohort comparison for baseline and model-guided Oracle search.

The comparison layer does not advance simulator state itself. It validates and
packages two fixed-evaluation reports produced from the same cohort: the native
Oracle-like baseline and the T028 model-guided Oracle-like controller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import io
import json
from typing import Any, TextIO

from sts_combat_rl.sim.fixed_battle_evaluation import (
    AggregateSlice,
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
    build_evaluation_aggregates,
    dump_fixed_evaluation_report_jsonl,
    format_fixed_evaluation_report,
    load_fixed_evaluation_report_jsonl,
)
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity
from sts_combat_rl.sim.search_telemetry import (
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    summarize_search_decision_telemetry_dicts,
)


MODEL_GUIDED_SEARCH_FIXED_COMPARISON_SCHEMA_ID = (
    "model-guided-search-fixed-comparison-v1"
)
MODEL_GUIDED_SEARCH_FIXED_COMPARISON_FORMAT_VERSION = 1
MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_SCHEMA_ID = (
    "model-guided-search-fixed-comparison-v2"
)
MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_FORMAT_VERSION = 1
BASELINE_ORACLE_LABEL = "baseline_oracle_search"
MODEL_GUIDED_ORACLE_LABEL = "model_guided_oracle_search"
MODEL_GUIDED_ORACLE_V1_LABEL = "model_guided_oracle_search_v1"
MODEL_GUIDED_ORACLE_V2_LABEL = "model_guided_oracle_search_v2"
MODEL_GUIDED_SEARCH_COMPARISON_EVIDENCE_BOUNDARY = (
    "full_simulator_state_oracle_like diagnostics only; not normal-information, "
    "live-game, broad-training, or controller-strength evidence"
)


@dataclass(frozen=True)
class ModelGuidedSearchFixedComparisonReport:
    """Versioned comparison report for two same-cohort search evaluations."""

    baseline_report: FixedEvaluationReport
    model_guided_report: FixedEvaluationReport
    comparison_config: dict[str, Any]
    report_problems: list[str] = field(default_factory=list)
    schema_id: str = MODEL_GUIDED_SEARCH_FIXED_COMPARISON_SCHEMA_ID
    format_version: int = MODEL_GUIDED_SEARCH_FIXED_COMPARISON_FORMAT_VERSION
    evidence_boundary: str = MODEL_GUIDED_SEARCH_COMPARISON_EVIDENCE_BOUNDARY

    @property
    def cohort_identity(self) -> str:
        if (
            self.baseline_report.cohort_identity
            == self.model_guided_report.cohort_identity
        ):
            return self.baseline_report.cohort_identity
        return (
            f"{self.baseline_report.cohort_identity}|"
            f"{self.model_guided_report.cohort_identity}"
        )

    @property
    def run_scale(self) -> str:
        value = self.comparison_config.get("run_scale", "smoke")
        return str(value) if value else "smoke"

    @property
    def smoke_scale(self) -> bool:
        return self.run_scale == "smoke"

    @property
    def source_match_problems(self) -> list[str]:
        return fixed_report_source_match_problems(
            self.baseline_report,
            self.model_guided_report,
        )

    @property
    def problems(self) -> list[str]:
        return list(self.report_problems) + self.source_match_problems

    @property
    def evaluation_successful(self) -> bool:
        return (
            self.baseline_report.evaluation_successful
            and self.model_guided_report.evaluation_successful
            and not self.problems
        )


@dataclass(frozen=True)
class ModelGuidedSearchV2FixedComparisonReport:
    """T035 comparison report for baseline, T028/v1, and T035/v2 controllers."""

    baseline_report: FixedEvaluationReport
    model_guided_v1_report: FixedEvaluationReport
    model_guided_v2_report: FixedEvaluationReport
    comparison_config: dict[str, Any]
    report_problems: list[str] = field(default_factory=list)
    schema_id: str = MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_SCHEMA_ID
    format_version: int = MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_FORMAT_VERSION
    evidence_boundary: str = MODEL_GUIDED_SEARCH_COMPARISON_EVIDENCE_BOUNDARY

    @property
    def cohort_identity(self) -> str:
        identities = {
            self.baseline_report.cohort_identity,
            self.model_guided_v1_report.cohort_identity,
            self.model_guided_v2_report.cohort_identity,
        }
        if len(identities) == 1:
            return self.baseline_report.cohort_identity
        return "|".join(sorted(identities))

    @property
    def run_scale(self) -> str:
        value = self.comparison_config.get("run_scale", "smoke")
        return str(value) if value else "smoke"

    @property
    def smoke_scale(self) -> bool:
        return self.run_scale == "smoke"

    @property
    def source_match_problems(self) -> list[str]:
        return fixed_report_sequence_source_match_problems(
            (
                (BASELINE_ORACLE_LABEL, self.baseline_report),
                (MODEL_GUIDED_ORACLE_V1_LABEL, self.model_guided_v1_report),
                (MODEL_GUIDED_ORACLE_V2_LABEL, self.model_guided_v2_report),
            )
        )

    @property
    def problems(self) -> list[str]:
        return list(self.report_problems) + self.source_match_problems

    @property
    def evaluation_successful(self) -> bool:
        return (
            self.baseline_report.evaluation_successful
            and self.model_guided_v1_report.evaluation_successful
            and self.model_guided_v2_report.evaluation_successful
            and not self.problems
        )


def build_model_guided_search_fixed_comparison_report(
    *,
    baseline_report: FixedEvaluationReport,
    model_guided_report: FixedEvaluationReport,
    comparison_config: Mapping[str, Any],
    report_problems: Sequence[str] = (),
) -> ModelGuidedSearchFixedComparisonReport:
    """Build a comparison report from two fixed-evaluation reports."""

    return ModelGuidedSearchFixedComparisonReport(
        baseline_report=baseline_report,
        model_guided_report=model_guided_report,
        comparison_config=_json_safe_mapping(comparison_config),
        report_problems=list(report_problems),
    )


def build_model_guided_search_v2_fixed_comparison_report(
    *,
    baseline_report: FixedEvaluationReport,
    model_guided_v1_report: FixedEvaluationReport,
    model_guided_v2_report: FixedEvaluationReport,
    comparison_config: Mapping[str, Any],
    report_problems: Sequence[str] = (),
) -> ModelGuidedSearchV2FixedComparisonReport:
    """Build the T035 three-controller fixed comparison report."""

    return ModelGuidedSearchV2FixedComparisonReport(
        baseline_report=baseline_report,
        model_guided_v1_report=model_guided_v1_report,
        model_guided_v2_report=model_guided_v2_report,
        comparison_config=_json_safe_mapping(comparison_config),
        report_problems=list(report_problems),
    )


def fixed_report_source_match_problems(
    baseline_report: FixedEvaluationReport,
    model_guided_report: FixedEvaluationReport,
) -> list[str]:
    """Return source-alignment problems between two fixed-evaluation reports."""

    problems: list[str] = []
    if baseline_report.cohort_identity != model_guided_report.cohort_identity:
        problems.append(
            "cohort identity mismatch: "
            f"{baseline_report.cohort_identity!r} != "
            f"{model_guided_report.cohort_identity!r}"
        )
    if (
        baseline_report.source_pool_format_version
        != model_guided_report.source_pool_format_version
    ):
        problems.append(
            "source pool format version mismatch: "
            f"{baseline_report.source_pool_format_version} != "
            f"{model_guided_report.source_pool_format_version}"
        )
    if baseline_report.selection_config != model_guided_report.selection_config:
        problems.append("fixed-cohort selection config mismatch")
    if baseline_report.total_battles != model_guided_report.total_battles:
        problems.append(
            "battle result count mismatch: "
            f"{baseline_report.total_battles} != {model_guided_report.total_battles}"
        )

    paired_count = min(
        baseline_report.total_battles,
        model_guided_report.total_battles,
    )
    for index in range(paired_count):
        baseline_key = _source_key(baseline_report.battle_results[index])
        model_key = _source_key(model_guided_report.battle_results[index])
        if baseline_key != model_key:
            problems.append(
                f"cohort index {index}: source battle mismatch "
                f"{baseline_key!r} != {model_key!r}"
            )
    return problems


def fixed_report_sequence_source_match_problems(
    reports: Sequence[tuple[str, FixedEvaluationReport]],
) -> list[str]:
    """Return source-alignment problems for a same-cohort report sequence."""

    if not reports:
        return ["no fixed evaluation reports configured"]
    baseline_label, baseline_report = reports[0]
    problems: list[str] = []
    for label, report in reports[1:]:
        pair_problems = fixed_report_source_match_problems(
            baseline_report,
            report,
        )
        problems.extend(
            f"{baseline_label} vs {label}: {problem}" for problem in pair_problems
        )
    return problems


def comparison_controller_summaries(
    report: ModelGuidedSearchFixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return per-controller outcome and compute-cost summaries."""

    return {
        BASELINE_ORACLE_LABEL: _controller_summary(report.baseline_report),
        MODEL_GUIDED_ORACLE_LABEL: _controller_summary(report.model_guided_report),
    }


def comparison_aggregate_outcomes(
    report: ModelGuidedSearchFixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return aggregate outcome slices for each compared controller."""

    return {
        BASELINE_ORACLE_LABEL: _aggregate_outcomes(report.baseline_report),
        MODEL_GUIDED_ORACLE_LABEL: _aggregate_outcomes(report.model_guided_report),
    }


def comparison_budget_summary(
    report: ModelGuidedSearchFixedComparisonReport,
) -> dict[str, Any]:
    """Return equal-budget and observed-cost comparison metadata."""

    controller_summaries = comparison_controller_summaries(report)
    baseline_budget = _configured_native_playouts(report.baseline_report)
    model_budget = _configured_native_playouts(report.model_guided_report)
    return {
        "equal_native_playout_budget": (
            baseline_budget is not None
            and model_budget is not None
            and baseline_budget == model_budget
        ),
        "baseline_configured_native_playouts": baseline_budget,
        "model_guided_configured_native_playouts": model_budget,
        "wall_clock_control": "observed_only",
        "wall_clock_note": (
            "the current command controls native playout budget; wall-clock is "
            "measured after each run rather than forced equal"
        ),
        "baseline_observed": _observed_costs(
            controller_summaries[BASELINE_ORACLE_LABEL]
        ),
        "model_guided_observed": _observed_costs(
            controller_summaries[MODEL_GUIDED_ORACLE_LABEL]
        ),
    }


def comparison_v2_controller_summaries(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return per-controller summaries for the T035 three-way comparison."""

    return {
        BASELINE_ORACLE_LABEL: _controller_summary(report.baseline_report),
        MODEL_GUIDED_ORACLE_V1_LABEL: _controller_summary(
            report.model_guided_v1_report
        ),
        MODEL_GUIDED_ORACLE_V2_LABEL: _controller_summary(
            report.model_guided_v2_report
        ),
    }


def comparison_v2_aggregate_outcomes(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return aggregate outcome slices for every T035 compared controller."""

    return {
        BASELINE_ORACLE_LABEL: _aggregate_outcomes(report.baseline_report),
        MODEL_GUIDED_ORACLE_V1_LABEL: _aggregate_outcomes(
            report.model_guided_v1_report
        ),
        MODEL_GUIDED_ORACLE_V2_LABEL: _aggregate_outcomes(
            report.model_guided_v2_report
        ),
    }


def comparison_v2_budget_summary(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> dict[str, Any]:
    """Return equal-budget and observed-cost metadata for the T035 comparison."""

    summaries = comparison_v2_controller_summaries(report)
    configured = {
        BASELINE_ORACLE_LABEL: _configured_native_playouts(report.baseline_report),
        MODEL_GUIDED_ORACLE_V1_LABEL: _configured_native_playouts(
            report.model_guided_v1_report
        ),
        MODEL_GUIDED_ORACLE_V2_LABEL: _configured_native_playouts(
            report.model_guided_v2_report
        ),
    }
    configured_values = list(configured.values())
    return {
        "equal_native_playout_budget": (
            all(value is not None for value in configured_values)
            and len(set(configured_values)) == 1
        ),
        "configured_native_playouts": configured,
        "wall_clock_control": "observed_only",
        "wall_clock_note": (
            "the current command controls native playout budget; wall-clock is "
            "measured after each run rather than forced equal"
        ),
        "observed": {
            label: _observed_costs(summary) for label, summary in summaries.items()
        },
    }


def build_battle_comparisons(
    report: ModelGuidedSearchFixedComparisonReport,
) -> list[dict[str, Any]]:
    """Return per-battle source and outcome comparisons."""

    rows: list[dict[str, Any]] = []
    count = max(
        report.baseline_report.total_battles,
        report.model_guided_report.total_battles,
    )
    for index in range(count):
        baseline = _optional_result(report.baseline_report.battle_results, index)
        model_guided = _optional_result(
            report.model_guided_report.battle_results,
            index,
        )
        problems: list[str] = []
        if baseline is None:
            problems.append("missing baseline result")
        if model_guided is None:
            problems.append("missing model-guided result")
        source_match = False
        if baseline is not None and model_guided is not None:
            source_match = _source_key(baseline) == _source_key(model_guided)
            if not source_match:
                problems.append("source battle mismatch")
        source = (
            _source_key(baseline)
            if baseline is not None
            else _source_key(model_guided)
            if model_guided is not None
            else {}
        )
        rows.append(
            {
                "comparison_index": index,
                "source_match": source_match,
                "source": source,
                "baseline": _result_summary(baseline),
                "model_guided": _result_summary(model_guided),
                "problems": problems,
            }
        )
    return rows


def build_v2_battle_comparisons(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> list[dict[str, Any]]:
    """Return per-battle source and outcome rows for the T035 comparison."""

    rows: list[dict[str, Any]] = []
    count = max(
        report.baseline_report.total_battles,
        report.model_guided_v1_report.total_battles,
        report.model_guided_v2_report.total_battles,
    )
    reports = {
        BASELINE_ORACLE_LABEL: report.baseline_report.battle_results,
        MODEL_GUIDED_ORACLE_V1_LABEL: report.model_guided_v1_report.battle_results,
        MODEL_GUIDED_ORACLE_V2_LABEL: report.model_guided_v2_report.battle_results,
    }
    for index in range(count):
        results = {
            label: _optional_result(values, index) for label, values in reports.items()
        }
        present_keys = {
            label: _source_key(result)
            for label, result in results.items()
            if result is not None
        }
        problems = [
            f"missing {label} result"
            for label, result in results.items()
            if result is None
        ]
        source_match = (
            bool(present_keys)
            and len(
                {json.dumps(value, sort_keys=True) for value in present_keys.values()}
            )
            == 1
        )
        if not source_match:
            problems.append("source battle mismatch")
        source = next(iter(present_keys.values()), {})
        rows.append(
            {
                "comparison_index": index,
                "source_match": source_match,
                "source": source,
                "baseline": _result_summary(results[BASELINE_ORACLE_LABEL]),
                "model_guided_v1": _result_summary(
                    results[MODEL_GUIDED_ORACLE_V1_LABEL]
                ),
                "model_guided_v2": _result_summary(
                    results[MODEL_GUIDED_ORACLE_V2_LABEL]
                ),
                "problems": problems,
            }
        )
    return rows


def dump_model_guided_search_fixed_comparison_jsonl(
    report: ModelGuidedSearchFixedComparisonReport,
    stream: TextIO,
) -> None:
    """Write a current-schema fixed comparison report to JSONL."""

    baseline_metadata, baseline_results = _fixed_report_manifest_rows(
        report.baseline_report
    )
    model_metadata, model_results = _fixed_report_manifest_rows(
        report.model_guided_report
    )
    metadata = {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "smoke_scale": report.smoke_scale,
        "evidence_boundary": report.evidence_boundary,
        "comparison_config": _json_safe_mapping(report.comparison_config),
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "source_match_problems": list(report.source_match_problems),
        "controller_summaries": comparison_controller_summaries(report),
        "aggregate_outcomes": comparison_aggregate_outcomes(report),
        "budget_comparison": comparison_budget_summary(report),
        "baseline_report_metadata": baseline_metadata,
        "model_guided_report_metadata": model_metadata,
        "battle_comparison_count": max(
            report.baseline_report.total_battles,
            report.model_guided_report.total_battles,
        ),
        "evaluation_successful": report.evaluation_successful,
        "report_problems": list(report.report_problems),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for comparison in build_battle_comparisons(report):
        _write_row(stream, {"type": "battle_comparison", "comparison": comparison})
    for result in baseline_results:
        _write_row(stream, {"type": "baseline_result", "result": result})
    for result in model_results:
        _write_row(stream, {"type": "model_guided_result", "result": result})


def dump_model_guided_search_v2_fixed_comparison_jsonl(
    report: ModelGuidedSearchV2FixedComparisonReport,
    stream: TextIO,
) -> None:
    """Write a current-schema T035 three-way comparison report to JSONL."""

    baseline_metadata, baseline_results = _fixed_report_manifest_rows(
        report.baseline_report
    )
    v1_metadata, v1_results = _fixed_report_manifest_rows(report.model_guided_v1_report)
    v2_metadata, v2_results = _fixed_report_manifest_rows(report.model_guided_v2_report)
    metadata = {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "smoke_scale": report.smoke_scale,
        "evidence_boundary": report.evidence_boundary,
        "comparison_config": _json_safe_mapping(report.comparison_config),
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "source_match_problems": list(report.source_match_problems),
        "controller_summaries": comparison_v2_controller_summaries(report),
        "aggregate_outcomes": comparison_v2_aggregate_outcomes(report),
        "budget_comparison": comparison_v2_budget_summary(report),
        "baseline_report_metadata": baseline_metadata,
        "model_guided_v1_report_metadata": v1_metadata,
        "model_guided_v2_report_metadata": v2_metadata,
        "battle_comparison_count": max(
            report.baseline_report.total_battles,
            report.model_guided_v1_report.total_battles,
            report.model_guided_v2_report.total_battles,
        ),
        "evaluation_successful": report.evaluation_successful,
        "report_problems": list(report.report_problems),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for comparison in build_v2_battle_comparisons(report):
        _write_row(stream, {"type": "battle_comparison", "comparison": comparison})
    for result in baseline_results:
        _write_row(stream, {"type": "baseline_result", "result": result})
    for result in v1_results:
        _write_row(stream, {"type": "model_guided_v1_result", "result": result})
    for result in v2_results:
        _write_row(stream, {"type": "model_guided_v2_result", "result": result})


def load_model_guided_search_fixed_comparison_jsonl(
    stream: TextIO,
) -> ModelGuidedSearchFixedComparisonReport:
    """Load a current-schema fixed comparison report."""

    metadata: dict[str, Any] | None = None
    baseline_results: list[dict[str, Any]] = []
    model_results: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        row_type = row.get("type")
        if row_type == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
        elif row_type == "baseline_result":
            baseline_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "model_guided_result":
            model_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "battle_comparison":
            _require_mapping(row.get("comparison"), "comparison")
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing fixed comparison metadata")

    schema_id = metadata.get("schema_id")
    if schema_id != MODEL_GUIDED_SEARCH_FIXED_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported fixed comparison schema_id {schema_id!r}; expected "
            f"{MODEL_GUIDED_SEARCH_FIXED_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != MODEL_GUIDED_SEARCH_FIXED_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported fixed comparison format_version "
            f"{format_version!r}; expected "
            f"{MODEL_GUIDED_SEARCH_FIXED_COMPARISON_FORMAT_VERSION}"
        )

    baseline_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("baseline_report_metadata"),
            "baseline_report_metadata",
        ),
        baseline_results,
    )
    model_guided_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("model_guided_report_metadata"),
            "model_guided_report_metadata",
        ),
        model_results,
    )
    return ModelGuidedSearchFixedComparisonReport(
        baseline_report=baseline_report,
        model_guided_report=model_guided_report,
        comparison_config=_require_mapping(
            metadata.get("comparison_config"),
            "comparison_config",
        ),
        report_problems=_require_string_list(
            metadata.get("report_problems", []),
            "report_problems",
        ),
        evidence_boundary=_require_non_empty_string(
            metadata.get(
                "evidence_boundary", MODEL_GUIDED_SEARCH_COMPARISON_EVIDENCE_BOUNDARY
            ),
            "evidence_boundary",
        ),
    )


def load_model_guided_search_v2_fixed_comparison_jsonl(
    stream: TextIO,
) -> ModelGuidedSearchV2FixedComparisonReport:
    """Load a current-schema T035 three-way fixed comparison report."""

    metadata: dict[str, Any] | None = None
    baseline_results: list[dict[str, Any]] = []
    v1_results: list[dict[str, Any]] = []
    v2_results: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        row_type = row.get("type")
        if row_type == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
        elif row_type == "baseline_result":
            baseline_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "model_guided_v1_result":
            v1_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "model_guided_v2_result":
            v2_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "battle_comparison":
            _require_mapping(row.get("comparison"), "comparison")
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing fixed comparison metadata")

    schema_id = metadata.get("schema_id")
    if schema_id != MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported fixed comparison schema_id {schema_id!r}; expected "
            f"{MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported fixed comparison format_version "
            f"{format_version!r}; expected "
            f"{MODEL_GUIDED_SEARCH_V2_FIXED_COMPARISON_FORMAT_VERSION}"
        )

    baseline_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("baseline_report_metadata"),
            "baseline_report_metadata",
        ),
        baseline_results,
    )
    v1_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("model_guided_v1_report_metadata"),
            "model_guided_v1_report_metadata",
        ),
        v1_results,
    )
    v2_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("model_guided_v2_report_metadata"),
            "model_guided_v2_report_metadata",
        ),
        v2_results,
    )
    return ModelGuidedSearchV2FixedComparisonReport(
        baseline_report=baseline_report,
        model_guided_v1_report=v1_report,
        model_guided_v2_report=v2_report,
        comparison_config=_require_mapping(
            metadata.get("comparison_config"),
            "comparison_config",
        ),
        report_problems=_require_string_list(
            metadata.get("report_problems", []),
            "report_problems",
        ),
        evidence_boundary=_require_non_empty_string(
            metadata.get(
                "evidence_boundary", MODEL_GUIDED_SEARCH_COMPARISON_EVIDENCE_BOUNDARY
            ),
            "evidence_boundary",
        ),
    )


def format_model_guided_search_fixed_comparison_report(
    report: ModelGuidedSearchFixedComparisonReport,
) -> str:
    """Format a T029 fixed-cohort comparison report for stderr."""

    lines = [
        format_lightspeed_source_identity(),
        "",
        "Model-guided search fixed-cohort comparison",
        f"schema: {report.schema_id} v{report.format_version}",
        f"cohort identity: {report.cohort_identity}",
        f"run scale: {_format_run_scale(report)}",
        f"evidence boundary: {report.evidence_boundary}",
        (
            "source starts matched: "
            f"{'yes' if not report.source_match_problems else 'no'}"
        ),
        f"evaluation successful: {'yes' if report.evaluation_successful else 'no'}",
        "",
        _format_budget_comparison(report),
        "",
        _format_controller_summaries(report),
        "",
        _format_aggregate_comparison(report),
        "",
        _format_search_telemetry(
            report.baseline_report,
            title="Baseline Oracle search compute telemetry",
        ),
        "",
        _format_search_telemetry(
            report.model_guided_report,
            title="Model-guided Oracle search compute telemetry",
        ),
        "",
        "problems:",
    ]
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    lines.extend(
        [
            "",
            "Baseline Oracle evaluation",
            format_fixed_evaluation_report(report.baseline_report),
            "",
            "Model-guided Oracle evaluation",
            format_fixed_evaluation_report(report.model_guided_report),
        ]
    )
    return "\n".join(lines)


def format_model_guided_search_v2_fixed_comparison_report(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> str:
    """Format a T035 three-controller fixed-cohort comparison for stderr."""

    lines = [
        format_lightspeed_source_identity(),
        "",
        "Model-guided Oracle search v2 fixed-cohort comparison",
        f"schema: {report.schema_id} v{report.format_version}",
        f"cohort identity: {report.cohort_identity}",
        f"run scale: {_format_v2_run_scale(report)}",
        f"evidence boundary: {report.evidence_boundary}",
        (
            "source starts matched: "
            f"{'yes' if not report.source_match_problems else 'no'}"
        ),
        f"evaluation successful: {'yes' if report.evaluation_successful else 'no'}",
        "",
        _format_v2_budget_comparison(report),
        "",
        _format_v2_controller_summaries(report),
        "",
        _format_v2_aggregate_comparison(report),
        "",
        _format_search_telemetry(
            report.baseline_report,
            title="Baseline Oracle search compute telemetry",
        ),
        "",
        _format_search_telemetry(
            report.model_guided_v1_report,
            title="T028 model-guided Oracle search compute telemetry",
        ),
        "",
        _format_search_telemetry(
            report.model_guided_v2_report,
            title="T035 model-guided Oracle search v2 compute telemetry",
        ),
        "",
        "problems:",
    ]
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    lines.extend(
        [
            "",
            "Baseline Oracle evaluation",
            format_fixed_evaluation_report(report.baseline_report),
            "",
            "T028 model-guided Oracle evaluation",
            format_fixed_evaluation_report(report.model_guided_v1_report),
            "",
            "T035 model-guided Oracle v2 evaluation",
            format_fixed_evaluation_report(report.model_guided_v2_report),
        ]
    )
    return "\n".join(lines)


def _controller_summary(report: FixedEvaluationReport) -> dict[str, Any]:
    telemetry_summary, telemetry_problems = _search_telemetry_summary_dict(report)
    return {
        "controller_name": str(report.controller_provenance.get("name", "(unknown)")),
        "controller_kind": str(report.controller_provenance.get("kind", "(unknown)")),
        "controller_provenance": _json_safe_mapping(report.controller_provenance),
        "information_regime": report.information_regime,
        "battle_count": report.total_battles,
        "authoritative_wins": report.authoritative_wins,
        "losses": report.losses,
        "truncations": report.truncations,
        "errors": report.errors,
        "restore_failures": sum(
            1
            for result in report.battle_results
            if result.restoration_method == "failed"
        ),
        "decision_count": sum(
            result.decision_count for result in report.battle_results
        ),
        "simulator_step_count": sum(
            result.simulator_step_count for result in report.battle_results
        ),
        "battle_wall_clock_time_s": sum(
            result.wall_clock_time_s for result in report.battle_results
        ),
        "search_telemetry_summary": telemetry_summary,
        "search_telemetry_problems": telemetry_problems,
    }


def _aggregate_outcomes(report: FixedEvaluationReport) -> dict[str, Any]:
    aggregates = build_evaluation_aggregates(
        report,
        per_stratum_source_counts=report.per_stratum_source_counts,
    )
    return {
        "natural_weighted": _slice_to_dict(aggregates.natural_weighted),
        "encounter_macro": {
            str(key): _slice_to_dict(value)
            for key, value in sorted(aggregates.encounter_macro.items())
        },
        "room_type_macro": {
            str(key): _slice_to_dict(value)
            for key, value in sorted(aggregates.room_type_macro.items())
        },
        "per_stratum": {
            _stratum_label(key): _slice_to_dict(value)
            for key, value in sorted(
                aggregates.per_stratum.items(),
                key=lambda item: repr(item[0]),
            )
        },
    }


def _slice_to_dict(value: AggregateSlice) -> dict[str, Any]:
    return {
        "battle_count": value.battle_count,
        "win_count": value.win_count,
        "loss_count": value.loss_count,
        "truncated_count": value.truncated_count,
        "error_count": value.error_count,
        "win_rate": value.win_rate,
        "mean_hp_loss": value.mean_hp_loss,
        "total_decision_count": value.total_decision_count,
        "total_wall_clock_time_s": value.total_wall_clock_time_s,
        "result_indices": list(value.result_indices),
        "weighted_wins": value.weighted_wins,
        "weighted_losses": value.weighted_losses,
        "weighted_resolved": value.weighted_resolved,
        "weighted_hp_loss_sum": value.weighted_hp_loss_sum,
        "weighted_hp_loss_weight": value.weighted_hp_loss_weight,
    }


def _observed_costs(summary: Mapping[str, Any]) -> dict[str, Any]:
    search_summary = summary.get("search_telemetry_summary")
    search_mapping = search_summary if isinstance(search_summary, Mapping) else {}
    return {
        "battle_wall_clock_time_s": summary.get("battle_wall_clock_time_s"),
        "decision_count": summary.get("decision_count"),
        "simulator_step_count": summary.get("simulator_step_count"),
        "native_search_simulator_steps": _metric_total(
            search_mapping,
            "native_simulator_steps",
        ),
        "model_calls": _metric_total(search_mapping, "model_calls"),
        "search_wall_clock_time_s": _metric_total(
            search_mapping,
            "wall_clock_time_s",
        ),
        "root_mapping_failures": _metric_total(
            search_mapping,
            "root_mapping_failure_count",
        ),
        "restore_failures": summary.get("restore_failures"),
        "truncations": summary.get("truncations"),
        "errors": summary.get("errors"),
    }


def _metric_total(search_summary: Mapping[str, Any], key: str) -> float | None:
    metric = search_summary.get(key)
    if not isinstance(metric, Mapping):
        return None
    value = metric.get("total")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _configured_native_playouts(report: FixedEvaluationReport) -> int | None:
    config = report.controller_provenance.get("config")
    if not isinstance(config, Mapping):
        return None
    budget = config.get("search_budget")
    if not isinstance(budget, Mapping):
        return None
    value = budget.get("simulations")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _search_telemetry_summary_dict(
    report: FixedEvaluationReport,
) -> tuple[dict[str, Any] | None, list[str]]:
    records = _search_telemetry_records(report)
    if not records:
        return None, []
    try:
        return summarize_search_decision_telemetry_dicts(records).to_dict(), []
    except ValueError as exc:
        return None, [str(exc)]


def _search_telemetry_records(report: FixedEvaluationReport) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in report.battle_results:
        records.extend(
            iter_search_decision_telemetry_dicts(
                result.controller_compute_telemetry or {}
            )
        )
    return records


def _format_search_telemetry(report: FixedEvaluationReport, *, title: str) -> str:
    records = _search_telemetry_records(report)
    if not records:
        return f"{title}\n(no telemetry records)"
    try:
        return format_search_telemetry_summary(
            summarize_search_decision_telemetry_dicts(records),
            title=title,
        )
    except ValueError as exc:
        return "\n".join([title, f"versioned telemetry summary error: {exc}"])


def _format_budget_comparison(
    report: ModelGuidedSearchFixedComparisonReport,
) -> str:
    summary = comparison_budget_summary(report)
    baseline = summary["baseline_observed"]
    model_guided = summary["model_guided_observed"]
    return "\n".join(
        [
            "Budget and cost comparison",
            (
                "equal native playout budget: "
                f"{'yes' if summary['equal_native_playout_budget'] else 'no'}"
            ),
            (
                "configured native playouts: "
                f"baseline={_format_optional_number(summary['baseline_configured_native_playouts'])}, "
                f"model-guided={_format_optional_number(summary['model_guided_configured_native_playouts'])}"
            ),
            f"wall-clock control: {summary['wall_clock_control']}",
            (
                "battle wall-clock seconds: "
                f"baseline={_format_optional_number(baseline['battle_wall_clock_time_s'], precision=6)}, "
                f"model-guided={_format_optional_number(model_guided['battle_wall_clock_time_s'], precision=6)}"
            ),
            (
                "native search simulator steps: "
                f"baseline={_format_optional_number(baseline['native_search_simulator_steps'])}, "
                f"model-guided={_format_optional_number(model_guided['native_search_simulator_steps'])}"
            ),
            (
                "model calls: "
                f"baseline={_format_optional_number(baseline['model_calls'])}, "
                f"model-guided={_format_optional_number(model_guided['model_calls'])}"
            ),
            (
                "restore/truncation/error counts: "
                f"baseline={baseline['restore_failures']}/"
                f"{baseline['truncations']}/{baseline['errors']}, "
                f"model-guided={model_guided['restore_failures']}/"
                f"{model_guided['truncations']}/{model_guided['errors']}"
            ),
        ]
    )


def _format_controller_summaries(
    report: ModelGuidedSearchFixedComparisonReport,
) -> str:
    summaries = comparison_controller_summaries(report)
    lines = ["Controller summaries"]
    for label in (BASELINE_ORACLE_LABEL, MODEL_GUIDED_ORACLE_LABEL):
        summary = summaries[label]
        observed = _observed_costs(summary)
        lines.extend(
            [
                f"{label}:",
                f"  controller: {summary['controller_name']}",
                f"  information regime: {summary['information_regime']}",
                (
                    "  outcomes: "
                    f"{summary['authoritative_wins']}W/"
                    f"{summary['losses']}L, "
                    f"truncations={summary['truncations']}, "
                    f"errors={summary['errors']}"
                ),
                f"  decisions: {summary['decision_count']}",
                (
                    "  native search simulator steps: "
                    f"{_format_optional_number(observed['native_search_simulator_steps'])}"
                ),
                (f"  model calls: {_format_optional_number(observed['model_calls'])}"),
            ]
        )
    return "\n".join(lines)


def _format_aggregate_comparison(
    report: ModelGuidedSearchFixedComparisonReport,
) -> str:
    baseline = build_evaluation_aggregates(
        report.baseline_report,
        per_stratum_source_counts=report.baseline_report.per_stratum_source_counts,
    )
    model_guided = build_evaluation_aggregates(
        report.model_guided_report,
        per_stratum_source_counts=report.model_guided_report.per_stratum_source_counts,
    )
    lines = [
        "Aggregate outcome comparison",
        (
            "natural-weighted win rate: "
            f"baseline={_format_rate(baseline.natural_weighted.win_rate)}, "
            f"model-guided={_format_rate(model_guided.natural_weighted.win_rate)}"
        ),
        (
            "natural-weighted mean HP loss: "
            f"baseline={_format_rate(baseline.natural_weighted.mean_hp_loss)}, "
            f"model-guided={_format_rate(model_guided.natural_weighted.mean_hp_loss)}"
        ),
        "encounter-macro win rates:",
    ]
    for key in sorted(
        set(baseline.encounter_macro).union(model_guided.encounter_macro)
    ):
        lines.append(
            f"  {key}: baseline={_format_rate(_slice_win_rate(baseline.encounter_macro, key))}, "
            f"model-guided={_format_rate(_slice_win_rate(model_guided.encounter_macro, key))}"
        )
    if not baseline.encounter_macro and not model_guided.encounter_macro:
        lines.append("  (none)")
    lines.append("room-type-macro win rates:")
    for key in sorted(
        set(baseline.room_type_macro).union(model_guided.room_type_macro)
    ):
        lines.append(
            f"  {key}: baseline={_format_rate(_slice_win_rate(baseline.room_type_macro, key))}, "
            f"model-guided={_format_rate(_slice_win_rate(model_guided.room_type_macro, key))}"
        )
    if not baseline.room_type_macro and not model_guided.room_type_macro:
        lines.append("  (none)")
    lines.append("per-stratum win rates:")
    for key in sorted(
        set(baseline.per_stratum).union(model_guided.per_stratum),
        key=repr,
    ):
        lines.append(
            f"  {_stratum_label(key)}: baseline={_format_rate(_slice_win_rate(baseline.per_stratum, key))}, "
            f"model-guided={_format_rate(_slice_win_rate(model_guided.per_stratum, key))}"
        )
    if not baseline.per_stratum and not model_guided.per_stratum:
        lines.append("  (none)")
    return "\n".join(lines)


def _format_v2_budget_comparison(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> str:
    summary = comparison_v2_budget_summary(report)
    configured = summary["configured_native_playouts"]
    observed = summary["observed"]
    lines = [
        "Budget and cost comparison",
        (
            "equal native playout budget: "
            f"{'yes' if summary['equal_native_playout_budget'] else 'no'}"
        ),
        "configured native playouts:",
    ]
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        lines.append(f"  {label}: {_format_optional_number(configured[label])}")
    lines.extend(
        [
            f"wall-clock control: {summary['wall_clock_control']}",
            "battle wall-clock seconds:",
        ]
    )
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        lines.append(
            f"  {label}: "
            f"{_format_optional_number(observed[label]['battle_wall_clock_time_s'], precision=6)}"
        )
    lines.append("native search simulator steps:")
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        lines.append(
            f"  {label}: "
            f"{_format_optional_number(observed[label]['native_search_simulator_steps'])}"
        )
    lines.append("model calls:")
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        lines.append(
            f"  {label}: {_format_optional_number(observed[label]['model_calls'])}"
        )
    lines.append("restore/truncation/error counts:")
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        values = observed[label]
        lines.append(
            f"  {label}: {values['restore_failures']}/"
            f"{values['truncations']}/{values['errors']}"
        )
    return "\n".join(lines)


def _format_v2_controller_summaries(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> str:
    summaries = comparison_v2_controller_summaries(report)
    lines = ["Controller summaries"]
    for label in (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    ):
        summary = summaries[label]
        observed = _observed_costs(summary)
        lines.extend(
            [
                f"{label}:",
                f"  controller: {summary['controller_name']}",
                f"  information regime: {summary['information_regime']}",
                (
                    "  outcomes: "
                    f"{summary['authoritative_wins']}W/"
                    f"{summary['losses']}L, "
                    f"truncations={summary['truncations']}, "
                    f"errors={summary['errors']}"
                ),
                f"  decisions: {summary['decision_count']}",
                (
                    "  native search simulator steps: "
                    f"{_format_optional_number(observed['native_search_simulator_steps'])}"
                ),
                (f"  model calls: {_format_optional_number(observed['model_calls'])}"),
            ]
        )
    return "\n".join(lines)


def _format_v2_aggregate_comparison(
    report: ModelGuidedSearchV2FixedComparisonReport,
) -> str:
    aggregates = {
        BASELINE_ORACLE_LABEL: build_evaluation_aggregates(
            report.baseline_report,
            per_stratum_source_counts=report.baseline_report.per_stratum_source_counts,
        ),
        MODEL_GUIDED_ORACLE_V1_LABEL: build_evaluation_aggregates(
            report.model_guided_v1_report,
            per_stratum_source_counts=(
                report.model_guided_v1_report.per_stratum_source_counts
            ),
        ),
        MODEL_GUIDED_ORACLE_V2_LABEL: build_evaluation_aggregates(
            report.model_guided_v2_report,
            per_stratum_source_counts=(
                report.model_guided_v2_report.per_stratum_source_counts
            ),
        ),
    }
    labels = (
        BASELINE_ORACLE_LABEL,
        MODEL_GUIDED_ORACLE_V1_LABEL,
        MODEL_GUIDED_ORACLE_V2_LABEL,
    )
    lines = [
        "Aggregate outcome comparison",
        "natural-weighted win rate:",
    ]
    for label in labels:
        lines.append(
            f"  {label}: {_format_rate(aggregates[label].natural_weighted.win_rate)}"
        )
    lines.append("natural-weighted mean HP loss:")
    for label in labels:
        lines.append(
            f"  {label}: "
            f"{_format_rate(aggregates[label].natural_weighted.mean_hp_loss)}"
        )
    lines.append("encounter-macro win rates:")
    encounter_keys = sorted(
        set().union(*(aggregate.encounter_macro for aggregate in aggregates.values()))
    )
    for key in encounter_keys:
        parts = [
            f"{label}={_format_rate(_slice_win_rate(aggregates[label].encounter_macro, key))}"
            for label in labels
        ]
        lines.append(f"  {key}: " + ", ".join(parts))
    if not encounter_keys:
        lines.append("  (none)")
    lines.append("room-type-macro win rates:")
    room_keys = sorted(
        set().union(*(aggregate.room_type_macro for aggregate in aggregates.values()))
    )
    for key in room_keys:
        parts = [
            f"{label}={_format_rate(_slice_win_rate(aggregates[label].room_type_macro, key))}"
            for label in labels
        ]
        lines.append(f"  {key}: " + ", ".join(parts))
    if not room_keys:
        lines.append("  (none)")
    lines.append("per-stratum win rates:")
    stratum_keys = sorted(
        set().union(*(aggregate.per_stratum for aggregate in aggregates.values())),
        key=repr,
    )
    for key in stratum_keys:
        parts = [
            f"{label}={_format_rate(_slice_win_rate(aggregates[label].per_stratum, key))}"
            for label in labels
        ]
        lines.append(f"  {_stratum_label(key)}: " + ", ".join(parts))
    if not stratum_keys:
        lines.append("  (none)")
    return "\n".join(lines)


def _slice_win_rate(
    values: Mapping[Any, AggregateSlice],
    key: Any,
) -> float | None:
    value = values.get(key)
    return None if value is None else value.win_rate


def _source_key(result: SingleBattleEvaluationResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "cohort_index": result.cohort_index,
        "source_checkpoint_id": result.source_checkpoint_id,
        "source_seed": result.source_seed,
        "source_run_id": result.source_run_id,
        "source_battle_index": result.source_battle_index,
        "structural_stratum": list(result.structural_stratum),
    }


def _result_summary(result: SingleBattleEvaluationResult | None) -> dict[str, Any]:
    if result is None:
        return {"present": False}
    return {
        "present": True,
        "termination_status": result.termination_status,
        "terminal_absolute_hp": result.terminal_absolute_hp,
        "hp_loss": result.hp_loss,
        "decision_count": result.decision_count,
        "simulator_step_count": result.simulator_step_count,
        "wall_clock_time_s": result.wall_clock_time_s,
        "restoration_method": result.restoration_method,
        "problem_count": len(result.problems),
        "problems": list(result.problems),
    }


def _fixed_report_manifest_rows(
    report: FixedEvaluationReport,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    buffer = io.StringIO()
    dump_fixed_evaluation_report_jsonl(report, buffer)
    metadata: dict[str, Any] | None = None
    results: list[dict[str, Any]] = []
    for raw_line in buffer.getvalue().splitlines():
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if row.get("type") == "metadata":
            metadata = _require_mapping(row.get("metadata"), "fixed report metadata")
        elif row.get("type") == "result":
            results.append(_require_mapping(row.get("result"), "fixed report result"))
    if metadata is None:
        raise ValueError("fixed evaluation serializer emitted no metadata")
    return metadata, results


def _fixed_report_from_manifest_rows(
    metadata: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> FixedEvaluationReport:
    buffer = io.StringIO()
    _write_row(buffer, {"type": "metadata", "metadata": dict(metadata)})
    for result in results:
        _write_row(buffer, {"type": "result", "result": dict(result)})
    buffer.seek(0)
    return load_fixed_evaluation_report_jsonl(buffer)


def _optional_result(
    values: Sequence[SingleBattleEvaluationResult],
    index: int,
) -> SingleBattleEvaluationResult | None:
    if index < 0 or index >= len(values):
        return None
    return values[index]


def _stratum_label(value: Sequence[Any]) -> str:
    return "/".join(str(item) for item in value)


def _format_run_scale(report: ModelGuidedSearchFixedComparisonReport) -> str:
    if report.smoke_scale:
        return "smoke-scale"
    return report.run_scale


def _format_v2_run_scale(report: ModelGuidedSearchV2FixedComparisonReport) -> str:
    if report.smoke_scale:
        return "smoke-scale"
    return report.run_scale


def _format_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"


def _format_optional_number(value: Any, *, precision: int = 0) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    converted = float(value)
    if precision:
        return f"{converted:.{precision}f}"
    if converted.is_integer():
        return str(int(converted))
    return f"{converted:.3f}"


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"comparison value is not JSON-safe: {type(value).__name__}")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    stream.write(json.dumps(row, sort_keys=True, allow_nan=False))
    stream.write("\n")
