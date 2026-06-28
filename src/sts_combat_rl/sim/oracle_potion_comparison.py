"""Fixed-cohort comparison for no-potion and potion-enabled Oracle search."""

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
    fixed_report_source_match_problems,
)
from sts_combat_rl.sim.search_telemetry import (
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    summarize_search_decision_telemetry_dicts,
)


ORACLE_POTION_FIXED_COMPARISON_SCHEMA_ID = "oracle-potion-fixed-comparison-v1"
ORACLE_POTION_FIXED_COMPARISON_FORMAT_VERSION = 1
ORACLE_NO_POTION_LABEL = "oracle_search_no_potion"
ORACLE_WITH_POTIONS_LABEL = "oracle_search_with_potions"
ORACLE_POTION_COMPARISON_EVIDENCE_BOUNDARY = (
    "full_simulator_state_oracle_like engineering comparison only; not "
    "normal-information, live-game, broad-training, or controller-promotion evidence"
)


@dataclass(frozen=True)
class OraclePotionFixedComparisonReport:
    """Versioned same-cohort report for potion-enabled search repair."""

    no_potion_report: FixedEvaluationReport
    potion_report: FixedEvaluationReport
    comparison_config: dict[str, Any]
    report_problems: list[str] = field(default_factory=list)
    schema_id: str = ORACLE_POTION_FIXED_COMPARISON_SCHEMA_ID
    format_version: int = ORACLE_POTION_FIXED_COMPARISON_FORMAT_VERSION
    evidence_boundary: str = ORACLE_POTION_COMPARISON_EVIDENCE_BOUNDARY

    @property
    def cohort_identity(self) -> str:
        if self.no_potion_report.cohort_identity == self.potion_report.cohort_identity:
            return self.no_potion_report.cohort_identity
        return (
            f"{self.no_potion_report.cohort_identity}|"
            f"{self.potion_report.cohort_identity}"
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
            self.no_potion_report,
            self.potion_report,
        )

    @property
    def problems(self) -> list[str]:
        return list(self.report_problems) + self.source_match_problems

    @property
    def evaluation_successful(self) -> bool:
        return (
            self.no_potion_report.evaluation_successful
            and self.potion_report.evaluation_successful
            and not self.problems
        )


def build_oracle_potion_fixed_comparison_report(
    *,
    no_potion_report: FixedEvaluationReport,
    potion_report: FixedEvaluationReport,
    comparison_config: Mapping[str, Any],
    report_problems: Sequence[str] = (),
) -> OraclePotionFixedComparisonReport:
    """Build a T041 no-potion vs potion-enabled comparison report."""

    return OraclePotionFixedComparisonReport(
        no_potion_report=no_potion_report,
        potion_report=potion_report,
        comparison_config=_json_safe_mapping(comparison_config),
        report_problems=list(report_problems),
    )


def oracle_potion_controller_summaries(
    report: OraclePotionFixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return per-arm outcome and compute summaries."""

    return {
        ORACLE_NO_POTION_LABEL: _controller_summary(report.no_potion_report),
        ORACLE_WITH_POTIONS_LABEL: _controller_summary(report.potion_report),
    }


def oracle_potion_aggregate_outcomes(
    report: OraclePotionFixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Return aggregate outcome slices for both arms."""

    return {
        ORACLE_NO_POTION_LABEL: _aggregate_outcomes(report.no_potion_report),
        ORACLE_WITH_POTIONS_LABEL: _aggregate_outcomes(report.potion_report),
    }


def oracle_potion_budget_summary(
    report: OraclePotionFixedComparisonReport,
) -> dict[str, Any]:
    """Return equal-budget and action-space comparison metadata."""

    summaries = oracle_potion_controller_summaries(report)
    no_potion_budget = _configured_native_playouts(report.no_potion_report)
    potion_budget = _configured_native_playouts(report.potion_report)
    return {
        "equal_native_playout_budget": (
            no_potion_budget is not None
            and potion_budget is not None
            and no_potion_budget == potion_budget
        ),
        "configured_native_playouts": {
            ORACLE_NO_POTION_LABEL: no_potion_budget,
            ORACLE_WITH_POTIONS_LABEL: potion_budget,
        },
        "include_potions": {
            ORACLE_NO_POTION_LABEL: _include_potions(report.no_potion_report),
            ORACLE_WITH_POTIONS_LABEL: _include_potions(report.potion_report),
        },
        "wall_clock_control": "observed_only",
        "observed": {
            label: _observed_costs(summary) for label, summary in summaries.items()
        },
    }


def oracle_potion_delta_summary(
    report: OraclePotionFixedComparisonReport,
) -> dict[str, dict[str, Any]]:
    """Summarize structured potion inventory deltas for each arm."""

    return {
        ORACLE_NO_POTION_LABEL: _potion_delta_summary(report.no_potion_report),
        ORACLE_WITH_POTIONS_LABEL: _potion_delta_summary(report.potion_report),
    }


def build_oracle_potion_battle_comparisons(
    report: OraclePotionFixedComparisonReport,
) -> list[dict[str, Any]]:
    """Return per-battle source, outcome, and potion-delta comparisons."""

    rows: list[dict[str, Any]] = []
    count = max(
        report.no_potion_report.total_battles,
        report.potion_report.total_battles,
    )
    for index in range(count):
        no_potion = _optional_result(report.no_potion_report.battle_results, index)
        potion = _optional_result(report.potion_report.battle_results, index)
        problems: list[str] = []
        if no_potion is None:
            problems.append("missing no-potion result")
        if potion is None:
            problems.append("missing potion-enabled result")
        source_match = False
        if no_potion is not None and potion is not None:
            source_match = _source_key(no_potion) == _source_key(potion)
            if not source_match:
                problems.append("source battle mismatch")
        source = (
            _source_key(no_potion)
            if no_potion is not None
            else _source_key(potion)
            if potion is not None
            else {}
        )
        rows.append(
            {
                "comparison_index": index,
                "source_match": source_match,
                "source": source,
                "no_potion": _result_summary(no_potion),
                "potion_enabled": _result_summary(potion),
                "problems": problems,
            }
        )
    return rows


def dump_oracle_potion_fixed_comparison_jsonl(
    report: OraclePotionFixedComparisonReport,
    stream: TextIO,
) -> None:
    """Write a current-schema T041 comparison report to JSONL."""

    no_potion_metadata, no_potion_results = _fixed_report_manifest_rows(
        report.no_potion_report
    )
    potion_metadata, potion_results = _fixed_report_manifest_rows(report.potion_report)
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
        "controller_summaries": oracle_potion_controller_summaries(report),
        "aggregate_outcomes": oracle_potion_aggregate_outcomes(report),
        "budget_comparison": oracle_potion_budget_summary(report),
        "potion_inventory_delta_summary": oracle_potion_delta_summary(report),
        "no_potion_report_metadata": no_potion_metadata,
        "potion_report_metadata": potion_metadata,
        "battle_comparison_count": max(
            report.no_potion_report.total_battles,
            report.potion_report.total_battles,
        ),
        "evaluation_successful": report.evaluation_successful,
        "report_problems": list(report.report_problems),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for comparison in build_oracle_potion_battle_comparisons(report):
        _write_row(stream, {"type": "battle_comparison", "comparison": comparison})
    for result in no_potion_results:
        _write_row(stream, {"type": "no_potion_result", "result": result})
    for result in potion_results:
        _write_row(stream, {"type": "potion_result", "result": result})


def load_oracle_potion_fixed_comparison_jsonl(
    stream: TextIO,
) -> OraclePotionFixedComparisonReport:
    """Load a current-schema T041 fixed comparison report."""

    metadata: dict[str, Any] | None = None
    no_potion_results: list[dict[str, Any]] = []
    potion_results: list[dict[str, Any]] = []
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
        elif row_type == "no_potion_result":
            no_potion_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "potion_result":
            potion_results.append(_require_mapping(row.get("result"), "result"))
        elif row_type == "battle_comparison":
            _require_mapping(row.get("comparison"), "comparison")
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing Oracle potion comparison metadata")

    schema_id = metadata.get("schema_id")
    if schema_id != ORACLE_POTION_FIXED_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported Oracle potion comparison schema_id {schema_id!r}; "
            f"expected {ORACLE_POTION_FIXED_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != ORACLE_POTION_FIXED_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported Oracle potion comparison format_version "
            f"{format_version!r}; expected "
            f"{ORACLE_POTION_FIXED_COMPARISON_FORMAT_VERSION}"
        )

    no_potion_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("no_potion_report_metadata"),
            "no_potion_report_metadata",
        ),
        no_potion_results,
    )
    potion_report = _fixed_report_from_manifest_rows(
        _require_mapping(
            metadata.get("potion_report_metadata"),
            "potion_report_metadata",
        ),
        potion_results,
    )
    return OraclePotionFixedComparisonReport(
        no_potion_report=no_potion_report,
        potion_report=potion_report,
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
                ORACLE_POTION_COMPARISON_EVIDENCE_BOUNDARY,
            ),
            "evidence_boundary",
        ),
    )


def format_oracle_potion_fixed_comparison_report(
    report: OraclePotionFixedComparisonReport,
) -> str:
    """Format a T041 comparison report for stderr."""

    lines = [
        format_lightspeed_source_identity(),
        "",
        "Oracle potion fixed-cohort comparison",
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
        _format_potion_delta_summary(report),
        "",
        _format_aggregate_comparison(report),
        "",
        _format_search_telemetry(
            report.no_potion_report,
            title="No-potion Oracle search compute telemetry",
        ),
        "",
        _format_search_telemetry(
            report.potion_report,
            title="Potion-enabled Oracle search compute telemetry",
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
            "No-potion Oracle evaluation",
            format_fixed_evaluation_report(report.no_potion_report),
            "",
            "Potion-enabled Oracle evaluation",
            format_fixed_evaluation_report(report.potion_report),
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


def _format_budget_comparison(report: OraclePotionFixedComparisonReport) -> str:
    summary = oracle_potion_budget_summary(report)
    configured = summary["configured_native_playouts"]
    include_potions = summary["include_potions"]
    observed = summary["observed"]
    lines = [
        "Budget and action-space comparison",
        (
            "equal native playout budget: "
            f"{'yes' if summary['equal_native_playout_budget'] else 'no'}"
        ),
        "configured native playouts:",
    ]
    for label in (ORACLE_NO_POTION_LABEL, ORACLE_WITH_POTIONS_LABEL):
        lines.append(f"  {label}: {_format_optional_number(configured[label])}")
    lines.append("include potions:")
    for label in (ORACLE_NO_POTION_LABEL, ORACLE_WITH_POTIONS_LABEL):
        lines.append(f"  {label}: {'yes' if include_potions[label] else 'no'}")
    lines.append("observed costs and mapping:")
    for label in (ORACLE_NO_POTION_LABEL, ORACLE_WITH_POTIONS_LABEL):
        values = observed[label]
        lines.append(
            "  "
            + label
            + ": native_steps="
            + _format_optional_number(values["native_search_simulator_steps"])
            + ", model_calls="
            + _format_optional_number(values["model_calls"])
            + ", root_mapping_failures="
            + _format_optional_number(values["root_mapping_failures"])
            + ", unmapped_search_edges="
            + _format_optional_number(values["unmapped_search_edges"])
        )
    return "\n".join(lines)


def _format_controller_summaries(report: OraclePotionFixedComparisonReport) -> str:
    summaries = oracle_potion_controller_summaries(report)
    lines = ["Controller summaries"]
    for label in (ORACLE_NO_POTION_LABEL, ORACLE_WITH_POTIONS_LABEL):
        summary = summaries[label]
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
            ]
        )
    return "\n".join(lines)


def _format_potion_delta_summary(report: OraclePotionFixedComparisonReport) -> str:
    summaries = oracle_potion_delta_summary(report)
    lines = ["Potion inventory deltas"]
    for label in (ORACLE_NO_POTION_LABEL, ORACLE_WITH_POTIONS_LABEL):
        summary = summaries[label]
        lines.append(
            "  "
            + label
            + ": available_battles="
            + str(summary["available_battle_count"])
            + ", missing_battles="
            + str(summary["missing_battle_count"])
            + ", added_items="
            + str(summary["added_potion_slot_items"])
            + ", removed_items="
            + str(summary["removed_potion_slot_items"])
        )
    return "\n".join(lines)


def _format_aggregate_comparison(report: OraclePotionFixedComparisonReport) -> str:
    no_potion = build_evaluation_aggregates(
        report.no_potion_report,
        per_stratum_source_counts=report.no_potion_report.per_stratum_source_counts,
    )
    potion = build_evaluation_aggregates(
        report.potion_report,
        per_stratum_source_counts=report.potion_report.per_stratum_source_counts,
    )
    lines = [
        "Aggregate outcome comparison",
        (
            "natural-weighted win rate: "
            f"no-potion={_format_rate(no_potion.natural_weighted.win_rate)}, "
            f"potion-enabled={_format_rate(potion.natural_weighted.win_rate)}"
        ),
        (
            "natural-weighted mean HP loss: "
            f"no-potion={_format_rate(no_potion.natural_weighted.mean_hp_loss)}, "
            f"potion-enabled={_format_rate(potion.natural_weighted.mean_hp_loss)}"
        ),
    ]
    return "\n".join(lines)


def _observed_costs(summary: Mapping[str, Any]) -> dict[str, Any]:
    search_mapping = summary.get("search_telemetry_summary")
    search_summary = search_mapping if isinstance(search_mapping, Mapping) else {}
    return {
        "battle_wall_clock_time_s": summary.get("battle_wall_clock_time_s"),
        "native_search_simulator_steps": _metric_total(
            search_summary,
            "native_simulator_steps",
        ),
        "model_calls": _metric_total(search_summary, "model_calls"),
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


def _include_potions(report: FixedEvaluationReport) -> bool | None:
    config = report.controller_provenance.get("config")
    if not isinstance(config, Mapping):
        return None
    value = config.get("include_potions")
    return value if isinstance(value, bool) else None


def _stratum_label(value: Sequence[Any]) -> str:
    return "/".join(str(item) for item in value)


def _format_run_scale(report: OraclePotionFixedComparisonReport) -> str:
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
