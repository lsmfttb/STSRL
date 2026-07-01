"""T047 root-prior guided fixed-cohort comparison reports."""

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
from sts_combat_rl.sim.model_guided_search_comparison import (
    fixed_report_sequence_source_match_problems,
)
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.search_telemetry import (
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    summarize_search_decision_telemetry_dicts,
)


ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID = "root-prior-guided-search-comparison-v1"
ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION = 1
BASELINE_ORACLE_LABEL = "baseline_oracle_search"
POST_SEARCH_MODEL_GUIDED_LABEL = "model_guided_oracle_search_v2"
ROOT_PRIOR_GUIDED_LABEL = "root_prior_guided_oracle_search"
REQUIRED_ROOT_PRIOR_COMPARISON_LABELS = (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
)
ROOT_PRIOR_GUIDED_EVIDENCE_BOUNDARY = (
    "root-prior guided fixed-cohort diagnostics only; all compared search arms "
    "remain full_simulator_state_oracle_like, and this is not "
    "normal-information, live-game, broad-training, natural A20 performance, "
    "controller-promotion, or final-agent evidence"
)
UNASSISTED_OR_MISSING = "unassisted_or_missing"
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class RootPriorGuidedComparisonArm:
    """One evaluated controller arm in the T047 comparison."""

    label: str
    role: str
    report: FixedEvaluationReport


@dataclass(frozen=True)
class RootPriorGuidedSearchComparisonReport:
    """Versioned same-cohort comparison for root-prior guided search."""

    arms: tuple[RootPriorGuidedComparisonArm, ...]
    comparison_config: dict[str, Any]
    report_problems: list[str] = field(default_factory=list)
    schema_id: str = ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID
    format_version: int = ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION
    evidence_boundary: str = ROOT_PRIOR_GUIDED_EVIDENCE_BOUNDARY

    @property
    def cohort_identity(self) -> str:
        identities = {arm.report.cohort_identity for arm in self.arms}
        if len(identities) == 1 and self.arms:
            return self.arms[0].report.cohort_identity
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
            [(arm.label, arm.report) for arm in self.arms]
        )

    @property
    def validation_problems(self) -> list[str]:
        return root_prior_guided_comparison_validation_problems(self)

    @property
    def problems(self) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    *self.report_problems,
                    *self.source_match_problems,
                    *self.validation_problems,
                ]
            )
        )

    @property
    def evaluation_successful(self) -> bool:
        return all(arm.report.evaluation_successful for arm in self.arms) and not (
            self.problems
        )


def build_root_prior_guided_search_comparison_report(
    *,
    arms: Sequence[tuple[str, str, FixedEvaluationReport]],
    comparison_config: Mapping[str, Any],
    report_problems: Sequence[str] = (),
) -> RootPriorGuidedSearchComparisonReport:
    """Build a T047 comparison from same-cohort fixed evaluation reports."""

    labels = [label for label, _, _ in arms]
    problems = list(report_problems)
    if len(set(labels)) != len(labels):
        problems.append("controller arm labels must be unique")
    if not arms:
        problems.append("at least one controller arm is required")
    return RootPriorGuidedSearchComparisonReport(
        arms=tuple(
            RootPriorGuidedComparisonArm(label=label, role=role, report=report)
            for label, role, report in arms
        ),
        comparison_config=_json_safe_mapping(comparison_config),
        report_problems=list(dict.fromkeys(problems)),
    )


def root_prior_guided_comparison_validation_problems(
    report: RootPriorGuidedSearchComparisonReport,
) -> list[str]:
    """Return T047-specific comparison contract problems."""

    problems: list[str] = []
    arms = {arm.label: arm for arm in report.arms}
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        if label not in arms:
            problems.append(f"missing required arm {label!r}")

    regimes = {
        arm.label: arm.report.information_regime
        for arm in report.arms
        if arm.report.information_regime
    }
    for label, regime in regimes.items():
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{label}: information regime {regime!r} is not "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
    if len(set(regimes.values())) > 1:
        problems.append("mixed information regimes across compared search arms")

    budget = root_prior_guided_budget_summary(report)
    if not budget["equal_configured_native_playout_budget_for_required_arms"]:
        problems.append("required search arms do not share equal native root budget")

    checkpoints = {
        label: _checkpoint_provenance(arms[label].report)
        for label in (POST_SEARCH_MODEL_GUIDED_LABEL, ROOT_PRIOR_GUIDED_LABEL)
        if label in arms
    }
    for label, checkpoint in checkpoints.items():
        if not checkpoint:
            problems.append(f"{label}: missing checkpoint provenance")
    if len(checkpoints) == 2:
        values = {
            json.dumps(value, sort_keys=True) for value in checkpoints.values() if value
        }
        if len(values) > 1:
            problems.append("checkpoint provenance mismatch between guided arms")

    if ROOT_PRIOR_GUIDED_LABEL in arms:
        allocation = root_prior_allocation_summary(arms[ROOT_PRIOR_GUIDED_LABEL].report)
        if allocation["decision_count"] == 0:
            problems.append("root-prior arm has no allocation decision reports")
        if allocation["malformed_metadata_count"]:
            problems.append("root-prior arm has malformed allocation metadata")
    return list(dict.fromkeys(problems))


def root_prior_guided_controller_summaries(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return per-controller outcome, failure, and compute summaries."""

    return {arm.label: _controller_summary(arm.report) for arm in report.arms}


def root_prior_guided_aggregate_outcomes(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return aggregate outcomes for every T047 controller arm."""

    return {arm.label: _aggregate_outcomes(arm.report) for arm in report.arms}


def root_prior_guided_budget_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    """Return equal-search-budget and observed-cost metadata."""

    summaries = root_prior_guided_controller_summaries(report)
    configured = {
        arm.label: _configured_native_playouts(arm.report) for arm in report.arms
    }
    required = {
        label: configured.get(label) for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
    }
    required_values = list(required.values())
    return {
        "equal_configured_native_playout_budget_for_required_arms": (
            all(value is not None for value in required_values)
            and len(set(required_values)) == 1
        ),
        "configured_native_playouts": configured,
        "required_native_playouts": required,
        "wall_clock_control": "observed_only",
        "wall_clock_note": (
            "the command controls native playout budget; wall-clock is measured "
            "after each arm rather than forced equal"
        ),
        "observed": {
            label: _observed_costs(summary) for label, summary in summaries.items()
        },
    }


def root_prior_guided_source_distribution_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    """Summarize source distribution, assistance, act, room, and encounter labels."""

    baseline = report.arms[0].report if report.arms else None
    if baseline is None:
        return {
            "distribution_kind_counts": {},
            "assistance_level_counts": {},
            "act_counts": {},
            "room_type_counts": {},
            "encounter_id_counts": {},
            "record_count": 0,
        }
    return {
        "distribution_kind_counts": _metadata_counts(
            baseline.battle_results,
            "distribution_kind",
            default=MISSING_VALUE,
        ),
        "assistance_level_counts": _metadata_counts(
            baseline.battle_results,
            "assistance_level",
            default=UNASSISTED_OR_MISSING,
        ),
        "act_counts": _metadata_counts(baseline.battle_results, "act"),
        "room_type_counts": _metadata_counts(baseline.battle_results, "room_type"),
        "encounter_id_counts": _metadata_counts(
            baseline.battle_results,
            "encounter_id",
        ),
        "record_count": baseline.total_battles,
    }


def root_prior_allocation_summary(report: FixedEvaluationReport) -> dict[str, Any]:
    """Summarize allocation metadata and public-prior diagnostics for an arm."""

    decision_reports = list(_iter_root_prior_decision_reports(report))
    malformed = 0
    strategies: dict[str, int] = {}
    positive_prior_count = 0
    provided_prior_count = 0
    selected_indices: dict[str, int] = {}
    for decision in decision_reports:
        metadata = decision.get("allocation_metadata")
        if not isinstance(metadata, Mapping):
            malformed += 1
        elif (
            metadata.get("schema_id") != NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
            or metadata.get("allocation_strategy")
            != NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY
        ):
            malformed += 1
        else:
            strategy = str(metadata.get("allocation_strategy"))
            strategies[strategy] = strategies.get(strategy, 0) + 1
        prior_summary = decision.get("prior_summary")
        if isinstance(prior_summary, Mapping):
            positive_prior_count += _as_int(prior_summary.get("positive_prior_count"))
            provided_prior_count += _as_int(prior_summary.get("provided_prior_count"))
        target = decision.get("target")
        if isinstance(target, Mapping):
            selected = target.get("legal_action_index")
            if isinstance(selected, int) and not isinstance(selected, bool):
                key = str(selected)
                selected_indices[key] = selected_indices.get(key, 0) + 1
    return {
        "decision_count": len(decision_reports),
        "malformed_metadata_count": malformed,
        "allocation_strategy_counts": dict(sorted(strategies.items())),
        "positive_prior_count": positive_prior_count,
        "provided_prior_count": provided_prior_count,
        "selected_index_counts": dict(sorted(selected_indices.items())),
    }


def root_prior_guided_outcome_comparison(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    """Compare root-prior outcomes against baseline and post-search guidance."""

    summaries = root_prior_guided_controller_summaries(report)
    root = summaries.get(ROOT_PRIOR_GUIDED_LABEL, {})
    baseline = summaries.get(BASELINE_ORACLE_LABEL, {})
    post = summaries.get(POST_SEARCH_MODEL_GUIDED_LABEL, {})
    root_wins = _summary_wins(root)
    baseline_wins = _summary_wins(baseline)
    post_wins = _summary_wins(post)
    return {
        "metric": "authoritative_win_count",
        "root_prior_guided_wins": root_wins,
        "baseline_wins": baseline_wins,
        "post_search_model_guided_wins": post_wins,
        "status_vs_baseline": _delta_status(root_wins, baseline_wins),
        "status_vs_post_search_model_guided": _delta_status(root_wins, post_wins),
        "delta_vs_baseline": (
            None
            if root_wins is None or baseline_wins is None
            else root_wins - baseline_wins
        ),
        "delta_vs_post_search_model_guided": (
            None if root_wins is None or post_wins is None else root_wins - post_wins
        ),
        "promotion_boundary": (
            "diagnostic fixed-cohort result only; no controller-promotion claim"
        ),
    }


def build_root_prior_guided_battle_comparisons(
    report: RootPriorGuidedSearchComparisonReport,
) -> list[dict[str, Any]]:
    """Return per-battle source, outcome, and T047 diagnostic rows."""

    count = max((arm.report.total_battles for arm in report.arms), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        results = {
            arm.label: _optional_result(arm.report.battle_results, index)
            for arm in report.arms
        }
        present_keys = {
            label: _source_key(result)
            for label, result in results.items()
            if result is not None
        }
        source_match = (
            bool(present_keys)
            and len(
                {json.dumps(value, sort_keys=True) for value in present_keys.values()}
            )
            == 1
        )
        problems = [
            f"missing {label} result"
            for label, result in results.items()
            if result is None
        ]
        if not source_match:
            problems.append("source battle mismatch")
        rows.append(
            {
                "comparison_index": index,
                "source_match": source_match,
                "source": next(iter(present_keys.values()), {}),
                "arms": {
                    label: _result_summary(result) for label, result in results.items()
                },
                "problems": problems,
            }
        )
    return rows


def dump_root_prior_guided_search_comparison_jsonl(
    report: RootPriorGuidedSearchComparisonReport,
    stream: TextIO,
) -> None:
    """Write a current-schema T047 comparison artifact."""

    manifest_rows = {
        arm.label: _fixed_report_manifest_rows(arm.report) for arm in report.arms
    }
    metadata = {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "smoke_scale": report.smoke_scale,
        "evidence_boundary": report.evidence_boundary,
        "comparison_config": _json_safe_mapping(report.comparison_config),
        "controller_arms": [
            {
                "label": arm.label,
                "role": arm.role,
                "report_metadata": manifest_rows[arm.label][0],
            }
            for arm in report.arms
        ],
        "required_arms": list(REQUIRED_ROOT_PRIOR_COMPARISON_LABELS),
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "source_match_problems": list(report.source_match_problems),
        "source_distribution_summary": (
            root_prior_guided_source_distribution_summary(report)
        ),
        "controller_summaries": root_prior_guided_controller_summaries(report),
        "aggregate_outcomes": root_prior_guided_aggregate_outcomes(report),
        "budget_comparison": root_prior_guided_budget_summary(report),
        "root_prior_allocation_summary": (
            root_prior_allocation_summary(
                _arm_by_label(report, ROOT_PRIOR_GUIDED_LABEL).report
            )
            if _has_arm(report, ROOT_PRIOR_GUIDED_LABEL)
            else {}
        ),
        "outcome_comparison": root_prior_guided_outcome_comparison(report),
        "battle_comparison_count": max(
            (arm.report.total_battles for arm in report.arms),
            default=0,
        ),
        "evaluation_successful": report.evaluation_successful,
        "report_problems": list(report.report_problems),
        "validation_problems": list(report.validation_problems),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for comparison in build_root_prior_guided_battle_comparisons(report):
        _write_row(stream, {"type": "battle_comparison", "comparison": comparison})
    for arm in report.arms:
        for result in manifest_rows[arm.label][1]:
            _write_row(
                stream,
                {
                    "type": "controller_result",
                    "label": arm.label,
                    "result": result,
                },
            )


def load_root_prior_guided_search_comparison_jsonl(
    stream: TextIO,
) -> RootPriorGuidedSearchComparisonReport:
    """Load a current-schema T047 comparison artifact."""

    metadata: dict[str, Any] | None = None
    results_by_label: dict[str, list[dict[str, Any]]] = {}
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
        elif row_type == "controller_result":
            label = _require_non_empty_string(row.get("label"), "controller label")
            results_by_label.setdefault(label, []).append(
                _require_mapping(row.get("result"), "result")
            )
        elif row_type == "battle_comparison":
            _require_mapping(row.get("comparison"), "comparison")
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing root-prior guided comparison metadata")

    schema_id = metadata.get("schema_id")
    if schema_id != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported root-prior guided comparison schema_id {schema_id!r}; "
            f"expected {ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported root-prior guided comparison format_version "
            f"{format_version!r}; expected "
            f"{ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION}"
        )

    arms_raw = metadata.get("controller_arms")
    if not isinstance(arms_raw, list):
        raise ValueError("controller_arms must be a list")
    arms: list[RootPriorGuidedComparisonArm] = []
    for index, arm_raw in enumerate(arms_raw):
        arm_mapping = _require_mapping(arm_raw, f"controller_arms[{index}]")
        label = _require_non_empty_string(arm_mapping.get("label"), "arm label")
        role = _require_non_empty_string(arm_mapping.get("role"), "arm role")
        report_metadata = _require_mapping(
            arm_mapping.get("report_metadata"),
            f"{label} report_metadata",
        )
        arms.append(
            RootPriorGuidedComparisonArm(
                label=label,
                role=role,
                report=_fixed_report_from_manifest_rows(
                    report_metadata,
                    results_by_label.get(label, []),
                ),
            )
        )

    return RootPriorGuidedSearchComparisonReport(
        arms=tuple(arms),
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
                "evidence_boundary",
                ROOT_PRIOR_GUIDED_EVIDENCE_BOUNDARY,
            ),
            "evidence_boundary",
        ),
    )


def format_root_prior_guided_search_comparison_report(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    """Format a compact T047 comparison report for stderr and PR evidence."""

    lines = [
        format_lightspeed_source_identity(),
        "",
        "Root-prior guided search comparison",
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
        _format_source_distribution_summary(report),
        "",
        _format_budget_comparison(report),
        "",
        _format_controller_summaries(report),
        "",
        _format_outcome_comparison(report),
        "",
        _format_aggregate_comparison(report),
        "",
        _format_allocation_summary(report),
        "",
        "Search telemetry by arm",
    ]
    for arm in report.arms:
        lines.append(
            _format_search_telemetry(
                arm.report,
                title=f"{arm.label} compute telemetry",
            )
        )
    lines.extend(["", "problems:"])
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    for arm in report.arms:
        lines.extend(
            [
                "",
                f"{arm.label} fixed evaluation",
                format_fixed_evaluation_report(arm.report),
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
        "model_calls": _metric_total(telemetry_summary or {}, "model_calls"),
        "root_prior_allocation_summary": root_prior_allocation_summary(report),
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
        "assistance_level": _grouped_slices(
            report,
            lambda result: _metadata_label(
                result,
                "assistance_level",
                default=UNASSISTED_OR_MISSING,
            ),
        ),
        "act": _grouped_slices(report, lambda result: _metadata_label(result, "act")),
        "room_type": _grouped_slices(
            report,
            lambda result: _metadata_label(result, "room_type"),
        ),
        "encounter_id": _grouped_slices(
            report,
            lambda result: _metadata_label(result, "encounter_id"),
        ),
        "distribution_kind": _grouped_slices(
            report,
            lambda result: _metadata_label(
                result,
                "distribution_kind",
                default=MISSING_VALUE,
            ),
        ),
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


def _grouped_slices(report: FixedEvaluationReport, key_fn) -> dict[str, dict[str, Any]]:
    indices_by_key: dict[str, list[int]] = {}
    for index, result in enumerate(report.battle_results):
        indices_by_key.setdefault(str(key_fn(result)), []).append(index)
    return {
        key: _slice_to_dict(_slice_for_indices(report, indices))
        for key, indices in sorted(indices_by_key.items())
    }


def _slice_for_indices(
    report: FixedEvaluationReport,
    indices: Sequence[int],
) -> AggregateSlice:
    results = [report.battle_results[index] for index in indices]
    hp_values = [
        result.hp_loss
        for result in results
        if isinstance(result.hp_loss, int) and not isinstance(result.hp_loss, bool)
    ]
    return AggregateSlice(
        battle_count=len(results),
        win_count=sum(result.termination_status == "win" for result in results),
        loss_count=sum(result.termination_status == "loss" for result in results),
        truncated_count=sum(
            result.termination_status == "truncated" for result in results
        ),
        error_count=sum(result.termination_status == "error" for result in results),
        total_hp_loss=sum(hp_values) if hp_values else None,
        total_decision_count=sum(result.decision_count for result in results),
        total_wall_clock_time_s=sum(result.wall_clock_time_s for result in results),
        result_indices=list(indices),
    )


def _metadata_counts(
    results: Sequence[SingleBattleEvaluationResult],
    key: str,
    *,
    default: str = MISSING_VALUE,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        label = _metadata_label(result, key, default=default)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _metadata_label(
    result: SingleBattleEvaluationResult,
    key: str,
    *,
    default: str = MISSING_VALUE,
) -> str:
    value = result.structural_metadata.get(key, default)
    if value in (None, ""):
        return default
    return str(value)


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
        "structural_metadata": _json_safe_mapping(result.structural_metadata),
        "public_context_status": result.public_context_status,
        "public_context_replay_status": result.public_context_replay_status,
        "structured_battle_outcome_status": result.structured_battle_outcome_status,
        "structured_battle_outcome": _json_safe_mapping(
            result.structured_battle_outcome
        ),
        "root_prior_guidance": _root_prior_result_summary(result),
        "problem_count": len(result.problems),
        "problems": list(result.problems),
    }


def _root_prior_result_summary(result: SingleBattleEvaluationResult) -> dict[str, Any]:
    decision_reports = list(_iter_nested_decision_reports(result))
    if not decision_reports:
        return {"decision_count": 0}
    malformed = 0
    selected: list[int] = []
    positive_prior_count = 0
    provided_prior_count = 0
    for decision in decision_reports:
        metadata = decision.get("allocation_metadata")
        if not isinstance(metadata, Mapping):
            malformed += 1
        prior_summary = decision.get("prior_summary")
        if isinstance(prior_summary, Mapping):
            positive_prior_count += _as_int(prior_summary.get("positive_prior_count"))
            provided_prior_count += _as_int(prior_summary.get("provided_prior_count"))
        target = decision.get("target")
        if isinstance(target, Mapping):
            index = target.get("legal_action_index")
            if isinstance(index, int) and not isinstance(index, bool):
                selected.append(index)
    return {
        "decision_count": len(decision_reports),
        "malformed_allocation_metadata_count": malformed,
        "positive_prior_count": positive_prior_count,
        "provided_prior_count": provided_prior_count,
        "selected_legal_action_indices": selected,
    }


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


def _optional_result(
    values: Sequence[SingleBattleEvaluationResult],
    index: int,
) -> SingleBattleEvaluationResult | None:
    if index < 0 or index >= len(values):
        return None
    return values[index]


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


def _observed_costs(summary: Mapping[str, Any]) -> dict[str, Any]:
    search_mapping = summary.get("search_telemetry_summary")
    search_summary = search_mapping if isinstance(search_mapping, Mapping) else {}
    return {
        "battle_wall_clock_time_s": summary.get("battle_wall_clock_time_s"),
        "battle_simulator_steps": summary.get("simulator_step_count"),
        "native_search_simulator_steps": _metric_total(
            search_summary,
            "native_simulator_steps",
        ),
        "root_visits": _metric_total(search_summary, "root_visits"),
        "model_calls": summary.get("model_calls"),
        "search_wall_clock_time_s": _metric_total(
            search_summary,
            "wall_clock_time_s",
        ),
        "root_mapping_failures": _metric_total(
            search_summary,
            "root_mapping_failure_count",
        ),
        "unmapped_search_edges": _metric_total(
            search_summary,
            "unmapped_search_edge_count",
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


def _checkpoint_provenance(report: FixedEvaluationReport) -> dict[str, Any]:
    config = report.controller_provenance.get("config")
    if not isinstance(config, Mapping):
        return {}
    guidance = config.get("guidance_scorer")
    if not isinstance(guidance, Mapping):
        return {}
    checkpoint = guidance.get("checkpoint_provenance")
    return dict(checkpoint) if isinstance(checkpoint, Mapping) else {}


def _iter_root_prior_decision_reports(
    report: FixedEvaluationReport,
) -> Sequence[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for result in report.battle_results:
        rows.extend(_iter_nested_decision_reports(result))
    return rows


def _iter_nested_decision_reports(
    result: SingleBattleEvaluationResult,
) -> Sequence[Mapping[str, Any]]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        return []
    raw = telemetry.get("root_prior_guided_decision_reports")
    rows: list[Mapping[str, Any]] = []
    _collect_mapping_rows(raw, rows)
    return rows


def _collect_mapping_rows(value: Any, rows: list[Mapping[str, Any]]) -> None:
    if isinstance(value, Mapping):
        rows.append(value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _collect_mapping_rows(item, rows)


def _summary_wins(summary: Mapping[str, Any]) -> int | None:
    value = summary.get("authoritative_wins")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _delta_status(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return "unavailable"
    if left > right:
        return "improved"
    if left == right:
        return "tied"
    return "regressed"


def _as_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0


def _arm_by_label(
    report: RootPriorGuidedSearchComparisonReport,
    label: str,
) -> RootPriorGuidedComparisonArm:
    for arm in report.arms:
        if arm.label == label:
            return arm
    raise KeyError(label)


def _has_arm(report: RootPriorGuidedSearchComparisonReport, label: str) -> bool:
    return any(arm.label == label for arm in report.arms)


def _format_source_distribution_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    summary = root_prior_guided_source_distribution_summary(report)
    lines = ["Source distribution summary"]
    _append_mapping_counts(lines, "distribution kinds", summary)
    _append_mapping_counts(lines, "assistance levels", summary)
    _append_mapping_counts(lines, "acts", summary)
    _append_mapping_counts(lines, "room types", summary)
    _append_mapping_counts(lines, "encounter ids", summary)
    return "\n".join(lines)


def _append_mapping_counts(
    lines: list[str],
    title: str,
    summary: Mapping[str, Any],
) -> None:
    key = title.replace(" ", "_")[:-1] + "_counts"
    counts = summary.get(key)
    lines.append(f"{title}:")
    if not isinstance(counts, Mapping) or not counts:
        lines.append("  (none)")
        return
    for label, count in sorted(counts.items()):
        lines.append(f"  {label}: {count}")


def _format_budget_comparison(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    summary = root_prior_guided_budget_summary(report)
    observed = summary["observed"]
    lines = [
        "Budget and cost comparison",
        (
            "equal configured native playout budget for required arms: "
            + (
                "yes"
                if summary["equal_configured_native_playout_budget_for_required_arms"]
                else "no"
            )
        ),
        "configured native playouts:",
    ]
    for label, value in summary["configured_native_playouts"].items():
        lines.append(f"  {label}: {_format_optional_number(value)}")
    lines.append(f"wall-clock control: {summary['wall_clock_control']}")
    lines.append("observed costs and failures:")
    for label, values in observed.items():
        lines.append(
            "  "
            + label
            + ": root_visits="
            + _format_optional_number(values["root_visits"])
            + ", native_search_steps="
            + _format_optional_number(values["native_search_simulator_steps"])
            + ", battle_steps="
            + _format_optional_number(values["battle_simulator_steps"])
            + ", model_calls="
            + _format_optional_number(values["model_calls"])
            + ", root_mapping_failures="
            + _format_optional_number(values["root_mapping_failures"])
            + ", restore/truncation/error="
            + f"{values['restore_failures']}/{values['truncations']}/{values['errors']}"
        )
    return "\n".join(lines)


def _format_controller_summaries(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    summaries = root_prior_guided_controller_summaries(report)
    lines = ["Controller summaries"]
    for arm in report.arms:
        summary = summaries[arm.label]
        lines.extend(
            [
                f"{arm.label}:",
                f"  role: {arm.role}",
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
                f"  model calls: {_format_optional_number(summary['model_calls'])}",
            ]
        )
    return "\n".join(lines)


def _format_outcome_comparison(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    outcome = root_prior_guided_outcome_comparison(report)
    return "\n".join(
        [
            "Root-prior outcome comparison",
            f"metric: {outcome['metric']}",
            (
                "root-prior vs baseline: "
                f"{outcome['status_vs_baseline']} "
                f"(delta={_format_optional_number(outcome['delta_vs_baseline'])})"
            ),
            (
                "root-prior vs post-search model-guided: "
                f"{outcome['status_vs_post_search_model_guided']} "
                + "("
                + "delta="
                + _format_optional_number(outcome["delta_vs_post_search_model_guided"])
                + ")"
            ),
            f"promotion boundary: {outcome['promotion_boundary']}",
        ]
    )


def _format_aggregate_comparison(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    aggregates = {
        arm.label: build_evaluation_aggregates(
            arm.report,
            per_stratum_source_counts=arm.report.per_stratum_source_counts,
        )
        for arm in report.arms
    }
    labels = [arm.label for arm in report.arms]
    lines = [
        "Aggregate outcome comparison",
        "natural-weighted win rate:",
    ]
    for label in labels:
        lines.append(
            f"  {label}: {_format_rate(aggregates[label].natural_weighted.win_rate)}"
        )
    outcome_payload = root_prior_guided_aggregate_outcomes(report)
    for title, key in (
        ("assistance-level win rates", "assistance_level"),
        ("act win rates", "act"),
        ("room-type win rates", "room_type"),
        ("encounter-id win rates", "encounter_id"),
    ):
        lines.append(f"{title}:")
        group_keys = sorted(
            set().union(*(payload[key].keys() for payload in outcome_payload.values()))
        )
        for group_key in group_keys:
            parts = [
                f"{label}={_format_rate(outcome_payload[label][key].get(group_key, {}).get('win_rate'))}"
                for label in labels
            ]
            lines.append(f"  {group_key}: " + ", ".join(parts))
        if not group_keys:
            lines.append("  (none)")
    return "\n".join(lines)


def _format_allocation_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> str:
    if not _has_arm(report, ROOT_PRIOR_GUIDED_LABEL):
        return "Root-prior allocation summary\n  (missing root-prior arm)"
    summary = root_prior_allocation_summary(
        _arm_by_label(report, ROOT_PRIOR_GUIDED_LABEL).report
    )
    lines = [
        "Root-prior allocation summary",
        f"decisions: {summary['decision_count']}",
        f"malformed allocation metadata: {summary['malformed_metadata_count']}",
        f"positive priors: {summary['positive_prior_count']}",
        f"provided priors: {summary['provided_prior_count']}",
        "allocation strategies:",
    ]
    strategies = summary["allocation_strategy_counts"]
    if strategies:
        for label, count in strategies.items():
            lines.append(f"  {label}: {count}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _stratum_label(value: Sequence[Any]) -> str:
    return "/".join(str(item) for item in value)


def _format_run_scale(report: RootPriorGuidedSearchComparisonReport) -> str:
    if report.smoke_scale:
        return "smoke-scale"
    return report.run_scale


def _format_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}"


def _format_optional_number(value: Any) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    converted = float(value)
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
