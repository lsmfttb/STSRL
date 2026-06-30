"""T044 de-assisted fixed-cohort comparison reports."""

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
from sts_combat_rl.sim.search_telemetry import (
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    summarize_search_decision_telemetry_dicts,
)


DE_ASSISTED_FIXED_COHORT_COMPARISON_SCHEMA_ID = "de-assisted-fixed-cohort-comparison-v1"
DE_ASSISTED_FIXED_COHORT_COMPARISON_FORMAT_VERSION = 1
BASELINE_ORACLE_LABEL = "baseline_oracle_search"
MODEL_GUIDED_ORACLE_V2_LABEL = "model_guided_oracle_search_v2"
RAW_CHECKPOINT_POLICY_LABEL = "checkpoint_raw_policy"
SCRIPTED_POLICY_LABEL = "scripted_action_kind_prior_policy"
DE_ASSISTED_FIXED_COHORT_EVIDENCE_BOUNDARY = (
    "de-assisted fixed-cohort diagnostics only; Oracle-like search arms remain "
    "full_simulator_state_oracle_like, raw checkpoint policy arms are "
    "normal_public_policy diagnostics, and this is not controller-promotion, "
    "live-game, natural A20 performance, or broad-training evidence"
)
UNASSISTED_OR_MISSING = "unassisted_or_missing"
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class DeAssistedFixedCohortArm:
    """One evaluated controller arm in the T044 comparison."""

    label: str
    role: str
    report: FixedEvaluationReport


@dataclass(frozen=True)
class DeAssistedFixedCohortComparisonReport:
    """Versioned same-cohort comparison for de-assisted evaluation."""

    arms: tuple[DeAssistedFixedCohortArm, ...]
    comparison_config: dict[str, Any]
    report_problems: list[str] = field(default_factory=list)
    schema_id: str = DE_ASSISTED_FIXED_COHORT_COMPARISON_SCHEMA_ID
    format_version: int = DE_ASSISTED_FIXED_COHORT_COMPARISON_FORMAT_VERSION
    evidence_boundary: str = DE_ASSISTED_FIXED_COHORT_EVIDENCE_BOUNDARY

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
    def problems(self) -> list[str]:
        return list(dict.fromkeys([*self.report_problems, *self.source_match_problems]))

    @property
    def evaluation_successful(self) -> bool:
        return all(arm.report.evaluation_successful for arm in self.arms) and not (
            self.problems
        )


def build_de_assisted_fixed_cohort_comparison_report(
    *,
    arms: Sequence[tuple[str, str, FixedEvaluationReport]],
    comparison_config: Mapping[str, Any],
    report_problems: Sequence[str] = (),
) -> DeAssistedFixedCohortComparisonReport:
    """Build a T044 report from same-cohort fixed evaluation reports."""

    labels = [label for label, _, _ in arms]
    problems = list(report_problems)
    if len(set(labels)) != len(labels):
        problems.append("controller arm labels must be unique")
    if not arms:
        problems.append("at least one controller arm is required")
    return DeAssistedFixedCohortComparisonReport(
        arms=tuple(
            DeAssistedFixedCohortArm(label=label, role=role, report=report)
            for label, role, report in arms
        ),
        comparison_config=_json_safe_mapping(comparison_config),
        report_problems=list(dict.fromkeys(problems)),
    )


def de_assisted_controller_summaries(
    report: DeAssistedFixedCohortComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return per-controller outcome, failure, and cost summaries."""

    return {arm.label: _controller_summary(arm.report) for arm in report.arms}


def de_assisted_aggregate_outcomes(
    report: DeAssistedFixedCohortComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return aggregate outcomes for every T044 controller arm."""

    return {arm.label: _aggregate_outcomes(arm.report) for arm in report.arms}


def de_assisted_budget_summary(
    report: DeAssistedFixedCohortComparisonReport,
) -> dict[str, Any]:
    """Return equal-search-budget and observed-cost metadata."""

    summaries = de_assisted_controller_summaries(report)
    configured = {
        arm.label: _configured_native_playouts(arm.report) for arm in report.arms
    }
    search_budgets = {
        label: value for label, value in configured.items() if value is not None
    }
    return {
        "equal_configured_native_playout_budget_for_search_arms": (
            len(search_budgets) >= 2 and len(set(search_budgets.values())) == 1
        ),
        "configured_native_playouts": configured,
        "non_search_arms": [
            label for label, value in configured.items() if value is None
        ],
        "wall_clock_control": "observed_only",
        "observed": {
            label: _observed_costs(summary) for label, summary in summaries.items()
        },
    }


def de_assisted_source_distribution_summary(
    report: DeAssistedFixedCohortComparisonReport,
) -> dict[str, Any]:
    """Summarize source distribution, assistance, and act labels in the cohort."""

    baseline = report.arms[0].report if report.arms else None
    if baseline is None:
        return {
            "distribution_kind_counts": {},
            "assistance_level_counts": {},
            "act_counts": {},
            "room_type_counts": {},
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
        "room_type_counts": _metadata_counts(
            baseline.battle_results,
            "room_type",
        ),
        "record_count": baseline.total_battles,
    }


def build_de_assisted_battle_comparisons(
    report: DeAssistedFixedCohortComparisonReport,
) -> list[dict[str, Any]]:
    """Return per-battle source, outcome, and failure rows."""

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


def dump_de_assisted_fixed_cohort_comparison_jsonl(
    report: DeAssistedFixedCohortComparisonReport,
    stream: TextIO,
) -> None:
    """Write a current-schema T044 comparison artifact."""

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
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "source_match_problems": list(report.source_match_problems),
        "source_distribution_summary": de_assisted_source_distribution_summary(report),
        "controller_summaries": de_assisted_controller_summaries(report),
        "aggregate_outcomes": de_assisted_aggregate_outcomes(report),
        "budget_comparison": de_assisted_budget_summary(report),
        "battle_comparison_count": max(
            (arm.report.total_battles for arm in report.arms),
            default=0,
        ),
        "evaluation_successful": report.evaluation_successful,
        "report_problems": list(report.report_problems),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for comparison in build_de_assisted_battle_comparisons(report):
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


def load_de_assisted_fixed_cohort_comparison_jsonl(
    stream: TextIO,
) -> DeAssistedFixedCohortComparisonReport:
    """Load a current-schema T044 comparison artifact."""

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
        raise ValueError("missing de-assisted comparison metadata")

    schema_id = metadata.get("schema_id")
    if schema_id != DE_ASSISTED_FIXED_COHORT_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported de-assisted comparison schema_id {schema_id!r}; expected "
            f"{DE_ASSISTED_FIXED_COHORT_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != DE_ASSISTED_FIXED_COHORT_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported de-assisted comparison format_version "
            f"{format_version!r}; expected "
            f"{DE_ASSISTED_FIXED_COHORT_COMPARISON_FORMAT_VERSION}"
        )

    arms_raw = metadata.get("controller_arms")
    if not isinstance(arms_raw, list):
        raise ValueError("controller_arms must be a list")
    arms: list[DeAssistedFixedCohortArm] = []
    for index, arm_raw in enumerate(arms_raw):
        arm_mapping = _require_mapping(arm_raw, f"controller_arms[{index}]")
        label = _require_non_empty_string(arm_mapping.get("label"), "arm label")
        role = _require_non_empty_string(arm_mapping.get("role"), "arm role")
        report_metadata = _require_mapping(
            arm_mapping.get("report_metadata"),
            f"{label} report_metadata",
        )
        arms.append(
            DeAssistedFixedCohortArm(
                label=label,
                role=role,
                report=_fixed_report_from_manifest_rows(
                    report_metadata,
                    results_by_label.get(label, []),
                ),
            )
        )

    return DeAssistedFixedCohortComparisonReport(
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
                DE_ASSISTED_FIXED_COHORT_EVIDENCE_BOUNDARY,
            ),
            "evidence_boundary",
        ),
    )


def format_de_assisted_fixed_cohort_comparison_report(
    report: DeAssistedFixedCohortComparisonReport,
) -> str:
    """Format a T044 comparison report for stderr."""

    lines = [
        format_lightspeed_source_identity(),
        "",
        "De-assisted fixed-cohort comparison",
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
        _format_aggregate_comparison(report),
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
    raw_model_calls = _raw_policy_model_call_count(report)
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
        "raw_policy_model_calls": raw_model_calls,
        "model_calls": _model_call_total(telemetry_summary, raw_model_calls),
        "potion_inventory_delta_summary": _potion_delta_summary(report),
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
        "act_level": _grouped_slices(
            report,
            lambda result: _metadata_label(result, "act"),
        ),
        "assistance_level": _grouped_slices(
            report,
            lambda result: _metadata_label(
                result,
                "assistance_level",
                default=UNASSISTED_OR_MISSING,
            ),
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


def _grouped_slices(
    report: FixedEvaluationReport,
    key_fn,
) -> dict[str, dict[str, Any]]:
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


def _potion_delta_summary(report: FixedEvaluationReport) -> dict[str, Any]:
    available = 0
    missing = 0
    added = 0
    removed = 0
    changed_indices: list[int] = []
    for result in report.battle_results:
        delta = _potion_slots_delta(result)
        if not delta or delta.get("status") != "available":
            missing += 1
            continue
        available += 1
        added_count = _sequence_count(delta.get("added"))
        removed_count = _sequence_count(delta.get("removed"))
        added += added_count
        removed += removed_count
        if added_count or removed_count:
            changed_indices.append(result.cohort_index)
    return {
        "available_battle_count": available,
        "missing_battle_count": missing,
        "added_potion_slot_items": added,
        "removed_potion_slot_items": removed,
        "changed_cohort_indices": changed_indices,
    }


def _potion_slots_delta(
    result: SingleBattleEvaluationResult,
) -> dict[str, Any] | None:
    outcome = result.structured_battle_outcome
    if not isinstance(outcome, Mapping):
        return None
    deltas = outcome.get("deltas")
    if not isinstance(deltas, Mapping):
        return None
    delta = deltas.get("potion_slots_delta")
    return dict(delta) if isinstance(delta, Mapping) else None


def _sequence_count(value: Any) -> int:
    return (
        len(value) if isinstance(value, Sequence) and not isinstance(value, str) else 0
    )


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
        "potion_slots_delta": _json_safe_mapping(_potion_slots_delta(result) or {}),
        "public_context_status": result.public_context_status,
        "public_context_replay_status": result.public_context_replay_status,
        "structured_battle_outcome_status": result.structured_battle_outcome_status,
        "problem_count": len(result.problems),
        "problems": list(result.problems),
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


def _raw_policy_model_call_count(report: FixedEvaluationReport) -> float:
    count = 0.0
    for result in report.battle_results:
        telemetry = result.controller_compute_telemetry
        if not isinstance(telemetry, Mapping):
            continue
        value = telemetry.get("search_guidance_policy_model_calls")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            count += float(value)
    return count


def _model_call_total(
    search_summary: Mapping[str, Any] | None,
    raw_policy_model_calls: float,
) -> float | int | None:
    search_calls = _metric_total(search_summary or {}, "model_calls")
    if search_calls is not None:
        return search_calls + raw_policy_model_calls
    if raw_policy_model_calls:
        return raw_policy_model_calls
    return None


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


def _format_source_distribution_summary(
    report: DeAssistedFixedCohortComparisonReport,
) -> str:
    summary = de_assisted_source_distribution_summary(report)
    lines = ["Source distribution summary"]
    _append_mapping_counts(lines, "distribution kinds", summary)
    _append_mapping_counts(lines, "assistance levels", summary)
    _append_mapping_counts(lines, "acts", summary)
    _append_mapping_counts(lines, "room types", summary)
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
    report: DeAssistedFixedCohortComparisonReport,
) -> str:
    summary = de_assisted_budget_summary(report)
    observed = summary["observed"]
    lines = [
        "Budget and cost comparison",
        (
            "equal configured native playout budget for search arms: "
            + (
                "yes"
                if summary["equal_configured_native_playout_budget_for_search_arms"]
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
    report: DeAssistedFixedCohortComparisonReport,
) -> str:
    summaries = de_assisted_controller_summaries(report)
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


def _format_aggregate_comparison(
    report: DeAssistedFixedCohortComparisonReport,
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
    lines.append("natural-weighted mean HP loss:")
    for label in labels:
        lines.append(
            f"  {label}: {_format_rate(aggregates[label].natural_weighted.mean_hp_loss)}"
        )
    lines.append("assistance-level win rates:")
    outcome_payload = de_assisted_aggregate_outcomes(report)
    assistance_keys = sorted(
        set().union(
            *(
                payload["assistance_level"].keys()
                for payload in outcome_payload.values()
            )
        )
    )
    for key in assistance_keys:
        parts = [
            f"{label}={_format_rate(outcome_payload[label]['assistance_level'].get(key, {}).get('win_rate'))}"
            for label in labels
        ]
        lines.append(f"  {key}: " + ", ".join(parts))
    if not assistance_keys:
        lines.append("  (none)")
    lines.append("act-level win rates:")
    act_keys = sorted(
        set().union(
            *(payload["act_level"].keys() for payload in outcome_payload.values())
        )
    )
    for key in act_keys:
        parts = [
            f"{label}={_format_rate(outcome_payload[label]['act_level'].get(key, {}).get('win_rate'))}"
            for label in labels
        ]
        lines.append(f"  {key}: " + ", ".join(parts))
    if not act_keys:
        lines.append("  (none)")
    return "\n".join(lines)


def _stratum_label(value: Sequence[Any]) -> str:
    return "/".join(str(item) for item in value)


def _format_run_scale(report: DeAssistedFixedCohortComparisonReport) -> str:
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
