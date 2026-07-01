"""Offline T045 analysis for post-T044 model-guidance failures.

This module consumes current-schema T044 de-assisted fixed-cohort comparison
artifacts. It does not run the simulator, train a checkpoint, choose actions,
or promote a controller.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import math
from typing import Any, TextIO

from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    BASELINE_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_V2_LABEL,
    RAW_CHECKPOINT_POLICY_LABEL,
    SCRIPTED_POLICY_LABEL,
    DeAssistedFixedCohortComparisonReport,
    de_assisted_aggregate_outcomes,
    de_assisted_controller_summaries,
    de_assisted_source_distribution_summary,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.online_controller import (
    NATIVE_SEARCH_INFORMATION_REGIME,
    PUBLIC_POLICY_INFORMATION_REGIME,
)
from sts_combat_rl.sim.search_telemetry import (
    iter_search_decision_telemetry_dicts,
)


POST_T044_FAILURE_ANALYSIS_SCHEMA_ID = "post-t044-failure-analysis-report-v1"
POST_T044_FAILURE_ANALYSIS_FORMAT_VERSION = 1
POST_T044_FAILURE_ANALYSIS_EVIDENCE_BOUNDARY = {
    "task_id": "T045",
    "scope": "offline post-T044 diagnostics",
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
}
REQUIRED_CONTROLLER_ARMS = (
    BASELINE_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_V2_LABEL,
    RAW_CHECKPOINT_POLICY_LABEL,
    SCRIPTED_POLICY_LABEL,
)
EXPECTED_INFORMATION_REGIMES = {
    BASELINE_ORACLE_LABEL: NATIVE_SEARCH_INFORMATION_REGIME,
    MODEL_GUIDED_ORACLE_V2_LABEL: NATIVE_SEARCH_INFORMATION_REGIME,
    RAW_CHECKPOINT_POLICY_LABEL: PUBLIC_POLICY_INFORMATION_REGIME,
    SCRIPTED_POLICY_LABEL: PUBLIC_POLICY_INFORMATION_REGIME,
}
STRUCTURAL_KEYS = (
    "assistance_level",
    "distribution_kind",
    "act",
    "room_type",
    "encounter_id",
    "room_category",
)
UNASSISTED_OR_MISSING = "unassisted_or_missing"
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class PostT044FailureAnalysisReport:
    """Versioned T045 report assembled from T044 comparison artifacts."""

    input_artifacts: list[dict[str, Any]]
    linked_artifacts: list[dict[str, Any]]
    comparison_summaries: list[dict[str, Any]]
    source_coverage: dict[str, Any]
    override_diagnostics: dict[str, Any]
    outcome_delta_diagnostics: dict[str, Any]
    raw_policy_diagnostics: dict[str, Any]
    model_alignment_diagnostics: dict[str, Any]
    stratified_summaries: dict[str, Any]
    failure_taxonomy: dict[str, Any]
    recommendation: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = POST_T044_FAILURE_ANALYSIS_SCHEMA_ID
    format_version: int = POST_T044_FAILURE_ANALYSIS_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(POST_T044_FAILURE_ANALYSIS_EVIDENCE_BOUNDARY)
    )

    @property
    def command_passed(self) -> bool:
        return not self.validation_problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "command_passed": self.command_passed,
            "evidence_boundary": _json_safe_value(self.evidence_boundary),
            "input_artifacts": _json_safe_value(self.input_artifacts),
            "linked_artifacts": _json_safe_value(self.linked_artifacts),
            "comparison_summaries": _json_safe_value(self.comparison_summaries),
            "source_coverage": _json_safe_value(self.source_coverage),
            "override_diagnostics": _json_safe_value(self.override_diagnostics),
            "outcome_delta_diagnostics": _json_safe_value(
                self.outcome_delta_diagnostics
            ),
            "raw_policy_diagnostics": _json_safe_value(self.raw_policy_diagnostics),
            "model_alignment_diagnostics": _json_safe_value(
                self.model_alignment_diagnostics
            ),
            "stratified_summaries": _json_safe_value(self.stratified_summaries),
            "failure_taxonomy": _json_safe_value(self.failure_taxonomy),
            "recommendation": _json_safe_value(self.recommendation),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def build_post_t044_failure_analysis_report(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
    *,
    linked_artifacts: Sequence[Mapping[str, Any]] = (),
) -> PostT044FailureAnalysisReport:
    """Build a deterministic T045 diagnostic report from T044 artifacts."""

    if not comparisons:
        raise ValueError("post-T044 failure analysis requires at least one comparison")

    artifacts = [_json_safe_mapping(identity) for identity, _ in comparisons]
    linked = [_json_safe_mapping(identity) for identity in linked_artifacts]
    validation_problems = _validation_problems(comparisons)
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    comparison_summaries = [
        _comparison_summary(identity, report) for identity, report in comparisons
    ]
    unavailable: list[dict[str, Any]] = []
    source_coverage = _source_coverage(comparisons)
    override = _override_diagnostics(comparisons, unavailable)
    outcome = _outcome_delta_diagnostics(comparisons, unavailable)
    raw_policy = _raw_policy_diagnostics(comparisons, unavailable)
    model_alignment = _model_alignment_diagnostics(comparisons, linked, unavailable)
    stratified = _stratified_summaries(comparisons)
    taxonomy = _failure_taxonomy(
        override=override,
        outcome=outcome,
        raw_policy=raw_policy,
        model_alignment=model_alignment,
        comparisons=comparison_summaries,
    )
    recommendation = _recommendation(taxonomy)
    return PostT044FailureAnalysisReport(
        input_artifacts=artifacts,
        linked_artifacts=linked,
        comparison_summaries=comparison_summaries,
        source_coverage=source_coverage,
        override_diagnostics=override,
        outcome_delta_diagnostics=outcome,
        raw_policy_diagnostics=raw_policy,
        model_alignment_diagnostics=model_alignment,
        stratified_summaries=stratified,
        failure_taxonomy=taxonomy,
        recommendation=recommendation,
        unavailable_diagnostics=_dedupe_unavailable(unavailable),
    )


def dump_post_t044_failure_analysis_report_json(
    report: PostT044FailureAnalysisReport,
    stream: TextIO,
) -> None:
    """Write a deterministic current-schema T045 JSON artifact."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_post_t044_failure_analysis_report_json(
    stream: TextIO,
) -> PostT044FailureAnalysisReport:
    """Load and validate a current-schema T045 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid post-T044 failure analysis JSON") from exc
    return post_t044_failure_analysis_report_from_dict(raw)


def post_t044_failure_analysis_report_from_dict(
    raw: Mapping[str, Any],
) -> PostT044FailureAnalysisReport:
    """Validate a current-schema T045 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("post-T044 failure analysis report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != POST_T044_FAILURE_ANALYSIS_SCHEMA_ID:
        raise ValueError(
            f"unsupported post-T044 failure analysis schema_id {schema_id!r}; "
            f"expected {POST_T044_FAILURE_ANALYSIS_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != POST_T044_FAILURE_ANALYSIS_FORMAT_VERSION:
        raise ValueError(
            "unsupported post-T044 failure analysis format_version "
            f"{format_version!r}; expected "
            f"{POST_T044_FAILURE_ANALYSIS_FORMAT_VERSION}"
        )
    return PostT044FailureAnalysisReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        linked_artifacts=_require_list_of_mappings(
            raw.get("linked_artifacts", []),
            "linked_artifacts",
        ),
        comparison_summaries=_require_list_of_mappings(
            raw.get("comparison_summaries"),
            "comparison_summaries",
        ),
        source_coverage=_require_mapping(raw.get("source_coverage"), "source_coverage"),
        override_diagnostics=_require_mapping(
            raw.get("override_diagnostics"),
            "override_diagnostics",
        ),
        outcome_delta_diagnostics=_require_mapping(
            raw.get("outcome_delta_diagnostics"),
            "outcome_delta_diagnostics",
        ),
        raw_policy_diagnostics=_require_mapping(
            raw.get("raw_policy_diagnostics"),
            "raw_policy_diagnostics",
        ),
        model_alignment_diagnostics=_require_mapping(
            raw.get("model_alignment_diagnostics"),
            "model_alignment_diagnostics",
        ),
        stratified_summaries=_require_mapping(
            raw.get("stratified_summaries"),
            "stratified_summaries",
        ),
        failure_taxonomy=_require_mapping(
            raw.get("failure_taxonomy"),
            "failure_taxonomy",
        ),
        recommendation=_require_mapping(raw.get("recommendation"), "recommendation"),
        unavailable_diagnostics=_require_list_of_mappings(
            raw.get("unavailable_diagnostics", []),
            "unavailable_diagnostics",
        ),
        validation_problems=_require_string_list(
            raw.get("validation_problems", []),
            "validation_problems",
        ),
        evidence_boundary=_require_mapping(
            raw.get("evidence_boundary", POST_T044_FAILURE_ANALYSIS_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_post_t044_failure_analysis_report(
    report: PostT044FailureAnalysisReport,
) -> str:
    """Format concise T045 diagnostics for stderr and PR summaries."""

    override = report.override_diagnostics
    outcome = report.outcome_delta_diagnostics
    raw_policy = report.raw_policy_diagnostics
    alignment = report.model_alignment_diagnostics
    taxonomy = report.failure_taxonomy
    recommendation = report.recommendation
    lines = [
        "Post-T044 failure analysis",
        (
            "scope: offline diagnostics only; no controller, simulator, "
            "training, live-game, broad-training, A20 performance, or promotion claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        f"input comparisons: {len(report.input_artifacts)}",
        (
            "unique source starts: "
            f"{report.source_coverage.get('unique_source_count', 0)} "
            f"(battle rows={report.source_coverage.get('battle_row_count', 0)}, "
            f"decision rows={report.source_coverage.get('decision_row_count', 0)})"
        ),
        (
            "model-guided overrides: "
            f"{override.get('override_decision_count', 0)}/"
            f"{override.get('comparable_decision_count', 0)} "
            f"({_optional_rate(override.get('override_rate'))})"
        ),
        (
            "model-guided outcome deltas: "
            f"better={outcome.get('model_guided_better_battle_count', 0)}, "
            f"worse={outcome.get('model_guided_worse_battle_count', 0)}, "
            f"same={outcome.get('same_outcome_battle_count', 0)}"
        ),
        (
            "raw checkpoint policy vs scripted: "
            f"worse={raw_policy.get('raw_worse_battle_count', 0)}, "
            f"better={raw_policy.get('raw_better_battle_count', 0)}, "
            f"same={raw_policy.get('same_outcome_battle_count', 0)}"
        ),
        (
            "model/native root alignment: "
            f"top1={alignment.get('model_top_native_top1_count', 0)}/"
            f"{alignment.get('evaluated_decision_count', 0)}, "
            f"top3={alignment.get('model_top_native_top3_count', 0)}/"
            f"{alignment.get('evaluated_decision_count', 0)}, "
            f"mean entropy={_optional_float(alignment.get('mean_policy_entropy'))}"
        ),
        "failure taxonomy:",
    ]
    for key in (
        "model-too-weak",
        "integration-too-late",
        "teacher-label-noisy",
        "distribution-mismatch",
        "action-space/fallback-issue",
    ):
        item = _mapping(taxonomy.get(key))
        lines.append(
            "  "
            + key
            + ": status="
            + str(item.get("status", "missing"))
            + ", count="
            + str(item.get("evidence_count", "missing"))
            + ", proportion="
            + _optional_rate(item.get("evidence_proportion"))
        )
    lines.append("recommended next paths:")
    for path in recommendation.get("recommended_paths", []):
        if isinstance(path, Mapping):
            lines.append(
                f"  - {path.get('path', 'missing')}: {path.get('reason', 'missing')}"
            )
    if not recommendation.get("recommended_paths"):
        lines.append("  (none)")
    lines.append("unavailable diagnostics:")
    if report.unavailable_diagnostics:
        for item in report.unavailable_diagnostics:
            lines.append(
                f"  - {item.get('diagnostic', 'missing')}: "
                f"{item.get('missing_field', 'missing')}"
            )
    else:
        lines.append("  (none)")
    lines.append("validation problems:")
    if report.validation_problems:
        lines.extend(f"  - {problem}" for problem in report.validation_problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _validation_problems(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
) -> list[str]:
    problems: list[str] = []
    for identity, report in comparisons:
        label = str(identity.get("path") or identity.get("artifact_id") or "artifact")
        labels = [arm.label for arm in report.arms]
        for required in REQUIRED_CONTROLLER_ARMS:
            if required not in labels:
                problems.append(f"{label}: missing required controller arm {required}")
        if len(set(labels)) != len(labels):
            problems.append(f"{label}: duplicate controller arm labels")
        for problem in report.source_match_problems:
            problems.append(f"{label}: source/cohort mismatch: {problem}")
        checkpoint_provenance = report.comparison_config.get("checkpoint_provenance")
        if checkpoint_provenance is not None and not isinstance(
            checkpoint_provenance,
            Mapping,
        ):
            problems.append(f"{label}: malformed checkpoint_provenance")
        for arm in report.arms:
            expected = EXPECTED_INFORMATION_REGIMES.get(arm.label)
            if expected is None:
                continue
            regimes = {arm.report.information_regime}
            regimes.update(
                result.information_regime for result in arm.report.battle_results
            )
            if regimes != {expected}:
                problems.append(
                    f"{label}: mixed information regimes for {arm.label}: "
                    + ", ".join(sorted(regimes))
                    + f"; expected {expected}"
                )
    return list(dict.fromkeys(problems))


def _comparison_summary(
    identity: Mapping[str, Any],
    report: DeAssistedFixedCohortComparisonReport,
) -> dict[str, Any]:
    checkpoint_provenance = report.comparison_config.get("checkpoint_provenance")
    checkpoint_status = (
        "available" if isinstance(checkpoint_provenance, Mapping) else "unavailable"
    )
    return {
        "artifact_identity": _json_safe_mapping(identity),
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "evidence_boundary": report.evidence_boundary,
        "controller_labels": [arm.label for arm in report.arms],
        "controller_summaries": de_assisted_controller_summaries(report),
        "aggregate_outcomes": de_assisted_aggregate_outcomes(report),
        "source_distribution_summary": de_assisted_source_distribution_summary(report),
        "checkpoint_provenance_status": checkpoint_status,
        "checkpoint_provenance": (
            _json_safe_mapping(checkpoint_provenance)
            if isinstance(checkpoint_provenance, Mapping)
            else {}
        ),
        "comparison_config": _json_safe_mapping(report.comparison_config),
        "source_match_status": "matched",
    }


def _source_coverage(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
) -> dict[str, Any]:
    source_ids: set[str] = set()
    missing = 0
    battle_rows = 0
    decision_rows = 0
    source_counts = Counter()
    for _, report in comparisons:
        baseline = _required_arm(report, BASELINE_ORACLE_LABEL).report
        for result in baseline.battle_results:
            battle_rows += 1
            decision_rows += result.decision_count
            source = _source_identity(result)
            if source is None:
                missing += 1
                continue
            source_ids.add(source)
            source_counts[source] += 1
    return {
        "unique_source_count": len(source_ids),
        "battle_row_count": battle_rows,
        "decision_row_count": decision_rows,
        "missing_source_identity_count": missing,
        "repeated_battle_row_count": sum(
            max(count - 1, 0) for count in source_counts.values()
        ),
    }


def _override_diagnostics(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    comparable = 0
    overrides = 0
    battle_count = 0
    battles_with_override = 0
    by_strata = _empty_strata_counters()
    unavailable_counts = Counter()
    for identity, report in comparisons:
        baseline = _required_arm(report, BASELINE_ORACLE_LABEL).report
        model = _required_arm(report, MODEL_GUIDED_ORACLE_V2_LABEL).report
        for index, base_result, model_result in _paired_results(baseline, model):
            battle_count += 1
            base_records = _search_records(base_result)
            model_records = _search_records(model_result)
            reason = _override_unavailable_reason(base_records, model_records)
            if reason is not None:
                unavailable_counts[reason] += 1
                _add_unavailable(
                    unavailable,
                    diagnostic="model_guided_override_accounting",
                    missing_field=reason,
                    artifact=identity,
                    cohort_index=index,
                )
                continue
            battle_override_count = 0
            for base_record, model_record in zip(base_records, model_records):
                base_index = _optional_int(
                    base_record.get("selected_legal_action_index")
                )
                model_index = _optional_int(
                    model_record.get("selected_legal_action_index")
                )
                if base_index is None or model_index is None:
                    reason = "search_decision_telemetry.selected_legal_action_index"
                    unavailable_counts[reason] += 1
                    _add_unavailable(
                        unavailable,
                        diagnostic="model_guided_override_accounting",
                        missing_field=reason,
                        artifact=identity,
                        cohort_index=index,
                    )
                    continue
                comparable += 1
                if base_index != model_index:
                    overrides += 1
                    battle_override_count += 1
                    _increment_strata(by_strata, base_result, "override_decision_count")
                _increment_strata(by_strata, base_result, "comparable_decision_count")
            if battle_override_count:
                battles_with_override += 1
    return {
        "status": "available" if comparable else "unavailable",
        "battle_count": battle_count,
        "comparable_decision_count": comparable,
        "override_decision_count": overrides,
        "override_rate": _rate(overrides, comparable),
        "battles_with_override_count": battles_with_override,
        "unavailable_counts": _counter_dict(unavailable_counts),
        "stratified": _finalize_strata_rates(
            by_strata,
            numerator="override_decision_count",
            denominator="comparable_decision_count",
            rate_name="override_rate",
        ),
    }


def _outcome_delta_diagnostics(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    hp_deltas: list[int] = []
    better = 0
    worse = 0
    same = 0
    structured_pairs = Counter()
    potion_added_delta = 0
    potion_removed_delta = 0
    by_strata = _empty_strata_counters()
    for identity, report in comparisons:
        baseline = _required_arm(report, BASELINE_ORACLE_LABEL).report
        model = _required_arm(report, MODEL_GUIDED_ORACLE_V2_LABEL).report
        for index, base_result, model_result in _paired_results(baseline, model):
            base_win = _win_value(base_result)
            model_win = _win_value(model_result)
            outcome_delta = model_win - base_win
            if outcome_delta > 0:
                better += 1
            elif outcome_delta < 0:
                worse += 1
            else:
                same += 1
            hp_delta = _hp_delta(model_result, base_result)
            if hp_delta is None:
                _add_unavailable(
                    unavailable,
                    diagnostic="model_guided_outcome_delta",
                    missing_field="terminal_absolute_hp",
                    artifact=identity,
                    cohort_index=index,
                )
            else:
                hp_deltas.append(hp_delta)
            base_potion = _potion_delta_counts(base_result)
            model_potion = _potion_delta_counts(model_result)
            if (
                base_potion["status"] == "available"
                and model_potion["status"] == "available"
            ):
                potion_added_delta += model_potion["added"] - base_potion["added"]
                potion_removed_delta += model_potion["removed"] - base_potion["removed"]
            else:
                _add_unavailable(
                    unavailable,
                    diagnostic="model_guided_potion_delta",
                    missing_field="structured_battle_outcome.deltas.potion_slots_delta",
                    artifact=identity,
                    cohort_index=index,
                )
            status_pair = (
                base_result.structured_battle_outcome_status,
                model_result.structured_battle_outcome_status,
            )
            structured_pairs[f"{status_pair[0]}->{status_pair[1]}"] += 1
            _increment_strata(by_strata, base_result, "battle_count")
            if outcome_delta > 0:
                _increment_strata(by_strata, base_result, "model_guided_better")
            elif outcome_delta < 0:
                _increment_strata(by_strata, base_result, "model_guided_worse")
            rows.append(
                {
                    "artifact_id": identity.get("artifact_id"),
                    "cohort_index": base_result.cohort_index,
                    "source_identity": _source_identity(base_result) or "missing",
                    "baseline_status": base_result.termination_status,
                    "model_guided_status": model_result.termination_status,
                    "win_delta": outcome_delta,
                    "terminal_absolute_hp_delta": hp_delta,
                    "baseline_potion_delta": base_potion,
                    "model_guided_potion_delta": model_potion,
                    "structured_battle_outcome_status_pair": {
                        "baseline": status_pair[0],
                        "model_guided": status_pair[1],
                    },
                    "structural_metadata": _metadata_summary(base_result),
                }
            )
    battle_count = len(rows)
    return {
        "status": "available" if battle_count else "unavailable",
        "matched_battle_count": battle_count,
        "model_guided_better_battle_count": better,
        "model_guided_worse_battle_count": worse,
        "same_outcome_battle_count": same,
        "mean_terminal_absolute_hp_delta": _mean(hp_deltas),
        "potion_slots_added_delta_total": potion_added_delta,
        "potion_slots_removed_delta_total": potion_removed_delta,
        "structured_battle_outcome_status_pairs": _counter_dict(structured_pairs),
        "battle_deltas": rows,
        "stratified": _finalize_strata_rates(
            by_strata,
            numerator="model_guided_better",
            denominator="battle_count",
            rate_name="model_guided_better_rate",
        ),
    }


def _raw_policy_diagnostics(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    better = 0
    worse = 0
    same = 0
    hp_deltas: list[int] = []
    failure_groups = _empty_strata_counters()
    action_groups: dict[str, Counter[str]] = {
        "action_kind": Counter(),
        "card_or_action_category": Counter(),
        "target_usage": Counter(),
        "end_turn_choice": Counter(),
        "potion_action": Counter(),
        "block_attack_scaling_proxy": Counter(),
    }
    missing_action_details = 0
    battle_count = 0
    for identity, report in comparisons:
        raw = _required_arm(report, RAW_CHECKPOINT_POLICY_LABEL).report
        scripted = _required_arm(report, SCRIPTED_POLICY_LABEL).report
        for index, raw_result, scripted_result in _paired_results(raw, scripted):
            battle_count += 1
            _increment_strata(failure_groups, raw_result, "battle_count")
            raw_win = _win_value(raw_result)
            scripted_win = _win_value(scripted_result)
            delta = raw_win - scripted_win
            if delta > 0:
                better += 1
            elif delta < 0:
                worse += 1
                _increment_strata(failure_groups, raw_result, "raw_worse_count")
            else:
                same += 1
            hp_delta = _hp_delta(raw_result, scripted_result)
            if hp_delta is None:
                _add_unavailable(
                    unavailable,
                    diagnostic="raw_policy_vs_scripted_hp_delta",
                    missing_field="terminal_absolute_hp",
                    artifact=identity,
                    cohort_index=index,
                )
            else:
                hp_deltas.append(hp_delta)
            selected_scores = _selected_policy_scores(raw_result)
            if not selected_scores:
                missing_action_details += 1
                _add_unavailable(
                    unavailable,
                    diagnostic="raw_policy_action_grouping",
                    missing_field=(
                        "controller_compute_telemetry."
                        "search_guidance_policy_decision_reports.selected_score"
                    ),
                    artifact=identity,
                    cohort_index=index,
                )
                continue
            for selected in selected_scores:
                groups = _action_group_labels(selected)
                for key, value in groups.items():
                    action_groups[key][value] += 1
    return {
        "status": "available" if battle_count else "unavailable",
        "matched_battle_count": battle_count,
        "raw_better_battle_count": better,
        "raw_worse_battle_count": worse,
        "same_outcome_battle_count": same,
        "mean_terminal_absolute_hp_delta": _mean(hp_deltas),
        "missing_action_detail_battle_count": missing_action_details,
        "action_group_counts": {
            key: _counter_dict(counter) for key, counter in action_groups.items()
        },
        "raw_worse_stratified": _finalize_strata_rates(
            failure_groups,
            numerator="raw_worse_count",
            denominator="battle_count",
            rate_name="raw_worse_rate",
        ),
    }


def _model_alignment_diagnostics(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
    linked_artifacts: Sequence[Mapping[str, Any]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = 0
    top1 = 0
    top3 = 0
    native_member = 0
    entropies: list[float] = []
    unvisited_mass: list[float] = []
    low_value_mass: list[float] = []
    unavailable_counts = Counter()
    for identity, report in comparisons:
        model = _required_arm(report, MODEL_GUIDED_ORACLE_V2_LABEL).report
        for result in model.battle_results:
            records = _model_guided_decision_records(result)
            if not records:
                reason = (
                    "controller_compute_telemetry.model_guidance_inference/"
                    "model_guided_oracle_root_scores"
                )
                unavailable_counts[reason] += 1
                _add_unavailable(
                    unavailable,
                    diagnostic="model_search_alignment",
                    missing_field=reason,
                    artifact=identity,
                    cohort_index=result.cohort_index,
                )
                continue
            for record in records:
                guidance = _mapping(record.get("guidance"))
                root_scores = _list_of_mappings(record.get("root_scores"))
                action_scores = _list_of_mappings(guidance.get("action_scores"))
                if not root_scores or not action_scores:
                    reason = "model_guidance_inference.action_scores/root_scores"
                    unavailable_counts[reason] += 1
                    _add_unavailable(
                        unavailable,
                        diagnostic="model_search_alignment",
                        missing_field=reason,
                        artifact=identity,
                        cohort_index=result.cohort_index,
                    )
                    continue
                model_top = _model_top_action_index(action_scores)
                native_top = _native_top_indices(root_scores, limit=3)
                if model_top is None or not native_top:
                    reason = "model_top_action_or_native_root_values"
                    unavailable_counts[reason] += 1
                    _add_unavailable(
                        unavailable,
                        diagnostic="model_search_alignment",
                        missing_field=reason,
                        artifact=identity,
                        cohort_index=result.cohort_index,
                    )
                    continue
                evaluated += 1
                if model_top == native_top[0]:
                    top1 += 1
                if model_top in set(native_top):
                    top3 += 1
                root_indices = {
                    _optional_int(score.get("legal_action_index"))
                    for score in root_scores
                }
                if model_top in root_indices:
                    native_member += 1
                probabilities = _eligible_probabilities(action_scores)
                entropy = _entropy(probabilities)
                if entropy is not None:
                    entropies.append(entropy)
                unvisited_mass.append(
                    _probability_mass_by_root_state(
                        action_scores, root_scores, "unvisited"
                    )
                )
                low_value_mass.append(
                    _probability_mass_by_root_state(
                        action_scores, root_scores, "low_value"
                    )
                )
    calibration = _linked_calibration_summary(linked_artifacts)
    if calibration["status"] == "unavailable":
        _add_unavailable(
            unavailable,
            diagnostic="teacher_calibration_alignment",
            missing_field="linked_artifacts.teacher_guidance_calibration_report",
            artifact={},
            cohort_index=None,
        )
    return {
        "status": "available" if evaluated else "unavailable",
        "evaluated_decision_count": evaluated,
        "model_top_native_top1_count": top1,
        "model_top_native_top1_rate": _rate(top1, evaluated),
        "model_top_native_top3_count": top3,
        "model_top_native_top3_rate": _rate(top3, evaluated),
        "model_top_native_root_member_count": native_member,
        "model_top_native_root_member_rate": _rate(native_member, evaluated),
        "mean_policy_entropy": _mean(entropies),
        "mean_model_probability_on_unvisited_root_actions": _mean(unvisited_mass),
        "mean_model_probability_on_low_value_root_actions": _mean(low_value_mass),
        "teacher_calibration": calibration,
        "unavailable_counts": _counter_dict(unavailable_counts),
    }


def _stratified_summaries(
    comparisons: Sequence[
        tuple[Mapping[str, Any], DeAssistedFixedCohortComparisonReport]
    ],
) -> dict[str, Any]:
    counters = _empty_strata_counters()
    for _, report in comparisons:
        baseline = _required_arm(report, BASELINE_ORACLE_LABEL).report
        model = _required_arm(report, MODEL_GUIDED_ORACLE_V2_LABEL).report
        raw = _required_arm(report, RAW_CHECKPOINT_POLICY_LABEL).report
        scripted = _required_arm(report, SCRIPTED_POLICY_LABEL).report
        for _, base_result, model_result in _paired_results(baseline, model):
            _increment_strata(counters, base_result, "battle_count")
            if _win_value(model_result) > _win_value(base_result):
                _increment_strata(counters, base_result, "model_guided_better")
            if _win_value(model_result) < _win_value(base_result):
                _increment_strata(counters, base_result, "model_guided_worse")
        for _, raw_result, scripted_result in _paired_results(raw, scripted):
            if _win_value(raw_result) < _win_value(scripted_result):
                _increment_strata(counters, raw_result, "raw_worse")
    return _finalize_strata_rates(
        counters,
        numerator="model_guided_better",
        denominator="battle_count",
        rate_name="model_guided_better_rate",
    )


def _failure_taxonomy(
    *,
    override: Mapping[str, Any],
    outcome: Mapping[str, Any],
    raw_policy: Mapping[str, Any],
    model_alignment: Mapping[str, Any],
    comparisons: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    battle_count = int(outcome.get("matched_battle_count") or 0)
    decision_count = int(model_alignment.get("evaluated_decision_count") or 0)
    raw_worse = int(raw_policy.get("raw_worse_battle_count") or 0)
    model_worse = int(outcome.get("model_guided_worse_battle_count") or 0)
    top3_misses = max(
        decision_count - int(model_alignment.get("model_top_native_top3_count") or 0),
        0,
    )
    low_value_mass = model_alignment.get(
        "mean_model_probability_on_low_value_root_actions"
    )
    integration_count = _integration_unavailable_count(comparisons)
    action_issue_count = _action_space_issue_count(comparisons)
    distribution_count = _distribution_mismatch_count(comparisons)
    calibration = _mapping(model_alignment.get("teacher_calibration"))
    teacher_count = int(calibration.get("problem_or_skip_count") or 0)
    return {
        "model-too-weak": {
            "status": "available" if battle_count or decision_count else "unavailable",
            "evidence_count": raw_worse + top3_misses,
            "evidence_denominator": raw_policy.get("matched_battle_count", 0)
            + decision_count,
            "evidence_proportion": _rate(
                raw_worse + top3_misses,
                int(raw_policy.get("matched_battle_count") or 0) + decision_count,
            ),
            "signals": {
                "raw_policy_worse_than_scripted_battles": raw_worse,
                "model_top_missed_native_top3_decisions": top3_misses,
                "mean_low_value_root_probability": low_value_mass,
            },
        },
        "integration-too-late": {
            "status": "available"
            if integration_count or decision_count
            else "unavailable",
            "evidence_count": integration_count,
            "evidence_denominator": max(decision_count, integration_count),
            "evidence_proportion": _rate(
                integration_count,
                max(decision_count, integration_count),
            ),
            "signals": {
                "root_only_unavailable_field_decisions": integration_count,
                "override_rate": override.get("override_rate"),
                "model_guided_worse_battles": model_worse,
            },
        },
        "teacher-label-noisy": {
            "status": calibration.get("status", "unavailable"),
            "evidence_count": teacher_count,
            "evidence_denominator": calibration.get("evaluated_record_count", 0),
            "evidence_proportion": _rate(
                teacher_count,
                int(calibration.get("evaluated_record_count") or 0),
            ),
            "signals": calibration,
        },
        "distribution-mismatch": {
            "status": "available" if battle_count else "unavailable",
            "evidence_count": distribution_count,
            "evidence_denominator": battle_count,
            "evidence_proportion": _rate(distribution_count, battle_count),
            "signals": {
                "de_assisted_or_unassisted_evaluation_battles": distribution_count,
                "comparison_source_distributions": [
                    item.get("source_distribution_summary", {}) for item in comparisons
                ],
            },
        },
        "action-space/fallback-issue": {
            "status": "available" if comparisons else "unavailable",
            "evidence_count": action_issue_count,
            "evidence_denominator": battle_count,
            "evidence_proportion": _rate(action_issue_count, battle_count),
            "signals": {
                "root_mapping_failures_controller_errors_or_unmapped_edges": (
                    action_issue_count
                )
            },
        },
    }


def _recommendation(taxonomy: Mapping[str, Any]) -> dict[str, Any]:
    paths: list[dict[str, Any]] = []
    integration = _mapping(taxonomy.get("integration-too-late"))
    action_issue = _mapping(taxonomy.get("action-space/fallback-issue"))
    model = _mapping(taxonomy.get("model-too-weak"))
    distribution = _mapping(taxonomy.get("distribution-mismatch"))
    teacher = _mapping(taxonomy.get("teacher-label-noisy"))

    if _proportion(integration) >= 0.5 and _proportion(action_issue) < 0.1:
        paths.append(
            {
                "path": "native root-prior allocation surface",
                "reason": (
                    "T044 guidance is observed only after native search; root-only "
                    "unavailable fields dominate while action-space failures are low"
                ),
            }
        )
        paths.append(
            {
                "path": "root-prior guided comparison",
                "reason": (
                    "compare equal-source/equal-budget search once native allocation "
                    "can consume public model priors"
                ),
            }
        )
    if _proportion(model) >= 0.25:
        paths.append(
            {
                "path": "assisted training repair",
                "reason": (
                    "raw checkpoint policy or model/native root alignment indicates "
                    "weak public model guidance"
                ),
            }
        )
    if _proportion(distribution) >= 0.5:
        paths.append(
            {
                "path": "de-assisted training distribution repair",
                "reason": (
                    "evaluation starts are mostly unassisted or low-assistance while "
                    "the checkpoint provenance is assisted-diagnostic"
                ),
            }
        )
    if teacher.get("status") == "available" and _proportion(teacher) >= 0.25:
        paths.append(
            {
                "path": "teacher-label noise audit",
                "reason": "linked calibration evidence shows skipped/problematic teacher rows",
            }
        )
    if _proportion(action_issue) >= 0.1:
        paths.append(
            {
                "path": "action-space and fallback repair",
                "reason": (
                    "root mapping, unmapped edge, controller error, or fallback "
                    "signals are high enough to explain outcome noise"
                ),
            }
        )
    if not paths:
        paths.append(
            {
                "path": "native root-prior allocation surface",
                "reason": (
                    "available evidence does not support promotion; the current "
                    "root-only integration remains the clearest next search boundary"
                ),
            }
        )
    return {
        "recommended_paths": paths,
        "non_claims": [
            "no follow-up is marked implemented",
            "no controller is promoted",
            "no normal-information or live-game performance is claimed",
        ],
    }


def _required_arm(
    report: DeAssistedFixedCohortComparisonReport,
    label: str,
):
    for arm in report.arms:
        if arm.label == label:
            return arm
    raise ValueError(f"missing required controller arm {label}")


def _paired_results(
    left: FixedEvaluationReport,
    right: FixedEvaluationReport,
) -> list[tuple[int, SingleBattleEvaluationResult, SingleBattleEvaluationResult]]:
    count = min(len(left.battle_results), len(right.battle_results))
    return [
        (index, left.battle_results[index], right.battle_results[index])
        for index in range(count)
    ]


def _search_records(result: SingleBattleEvaluationResult) -> list[dict[str, Any]]:
    return iter_search_decision_telemetry_dicts(
        result.controller_compute_telemetry or {}
    )


def _override_unavailable_reason(
    baseline_records: Sequence[Mapping[str, Any]],
    model_records: Sequence[Mapping[str, Any]],
) -> str | None:
    if not baseline_records:
        return "baseline_oracle_search.controller_compute_telemetry.search_decision_telemetry"
    if not model_records:
        return "model_guided_oracle_search_v2.controller_compute_telemetry.search_decision_telemetry"
    if len(baseline_records) != len(model_records):
        return "search_decision_telemetry.decision_count_mismatch"
    return None


def _model_guided_decision_records(
    result: SingleBattleEvaluationResult,
) -> list[dict[str, Any]]:
    telemetry = result.controller_compute_telemetry or {}
    guidances = _flatten_mappings(telemetry.get("model_guidance_inference"))
    root_score_groups = _flatten_root_score_groups(
        telemetry.get("model_guided_oracle_root_scores")
    )
    if not guidances or not root_score_groups:
        return []
    count = min(len(guidances), len(root_score_groups))
    return [
        {"guidance": guidances[index], "root_scores": root_score_groups[index]}
        for index in range(count)
    ]


def _flatten_root_score_groups(value: Any) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if _is_list_of_mappings(item):
                groups.append(_list_of_mappings(item))
            else:
                groups.extend(_flatten_root_score_groups(item))
    return groups


def _selected_policy_scores(
    result: SingleBattleEvaluationResult,
) -> list[dict[str, Any]]:
    reports = _flatten_mappings(
        (result.controller_compute_telemetry or {}).get(
            "search_guidance_policy_decision_reports"
        )
    )
    selected: list[dict[str, Any]] = []
    for report in reports:
        score = report.get("selected_score")
        if isinstance(score, Mapping):
            selected.append({str(key): value for key, value in score.items()})
    return selected


def _action_group_labels(selected_score: Mapping[str, Any]) -> dict[str, str]:
    identity = _mapping(selected_score.get("action_identity"))
    action_kind = _string(selected_score.get("action_kind")) or _string(
        identity.get("kind")
    )
    action_kind = action_kind or "missing"
    category = (
        _string(identity.get("card_id"))
        or _string(identity.get("action_id"))
        or _string(identity.get("stable_id"))
        or action_kind
    )
    target_usage = "targeted" if _has_target(identity) else "untargeted_or_missing"
    end_turn = _is_end_turn(action_kind, identity)
    potion = action_kind == "potion" or "potion" in category.lower()
    return {
        "action_kind": action_kind,
        "card_or_action_category": category,
        "target_usage": target_usage,
        "end_turn_choice": "end_turn" if end_turn else "not_end_turn",
        "potion_action": "potion" if potion else "not_potion",
        "block_attack_scaling_proxy": _block_attack_scaling_proxy(category),
    }


def _model_top_action_index(action_scores: Sequence[Mapping[str, Any]]) -> int | None:
    candidates: list[tuple[float, float, int]] = []
    for score in action_scores:
        if score.get("eligible") is False:
            continue
        index = _optional_int(score.get("legal_action_index"))
        probability = _optional_float_value(score.get("policy_probability"))
        logit = _optional_float_value(score.get("policy_logit")) or 0.0
        if index is None or probability is None:
            continue
        candidates.append((probability, logit, -index))
    if not candidates:
        return None
    return -max(candidates)[2]


def _native_top_indices(
    root_scores: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> list[int]:
    candidates: list[tuple[float, int, int]] = []
    for score in root_scores:
        if score.get("eligible") is False:
            continue
        index = _optional_int(score.get("legal_action_index"))
        value = _optional_float_value(
            score.get("native_mean_value", score.get("mean_value"))
        )
        visits = _optional_int(score.get("native_visits", score.get("visits"))) or 0
        if index is None or value is None or visits <= 0:
            continue
        candidates.append((value, visits, -index))
    return [-item[2] for item in sorted(candidates, reverse=True)[:limit]]


def _eligible_probabilities(action_scores: Sequence[Mapping[str, Any]]) -> list[float]:
    values: list[float] = []
    for score in action_scores:
        if score.get("eligible") is False:
            continue
        probability = _optional_float_value(score.get("policy_probability"))
        if probability is not None and probability >= 0.0:
            values.append(probability)
    return values


def _probability_mass_by_root_state(
    action_scores: Sequence[Mapping[str, Any]],
    root_scores: Sequence[Mapping[str, Any]],
    state: str,
) -> float:
    probabilities = {
        _optional_int(score.get("legal_action_index")): _optional_float_value(
            score.get("policy_probability")
        )
        for score in action_scores
    }
    native_values = [
        value
        for value in (
            _optional_float_value(root.get("native_mean_value", root.get("mean_value")))
            for root in root_scores
        )
        if value is not None
    ]
    median_value = _median(native_values)
    total = 0.0
    for root in root_scores:
        index = _optional_int(root.get("legal_action_index"))
        probability = probabilities.get(index)
        if probability is None:
            continue
        visits = _optional_int(root.get("native_visits", root.get("visits"))) or 0
        value = _optional_float_value(
            root.get("native_mean_value", root.get("mean_value"))
        )
        if state == "unvisited" and visits <= 0:
            total += probability
        elif (
            state == "low_value"
            and median_value is not None
            and value is not None
            and value < median_value
        ):
            total += probability
    return total


def _linked_calibration_summary(
    linked_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reports = [
        _mapping(item.get("calibration_summary"))
        for item in linked_artifacts
        if item.get("role") in {"calibration", "teacher_calibration"}
        or item.get("schema_id") == "teacher-guidance-calibration-report-v1"
    ]
    reports = [report for report in reports if report]
    if not reports:
        return {
            "status": "unavailable",
            "reason": "no linked teacher-guidance calibration report",
        }
    evaluated = sum(
        int(report.get("evaluated_record_count") or 0) for report in reports
    )
    skipped = sum(int(report.get("skipped_record_count") or 0) for report in reports)
    problems = sum(int(report.get("problem_count") or 0) for report in reports)
    top1 = sum(int(report.get("top1_agreement_count") or 0) for report in reports)
    topk = sum(int(report.get("top_k_agreement_count") or 0) for report in reports)
    ece_values = [
        value
        for value in (
            _optional_float_value(report.get("expected_calibration_error"))
            for report in reports
        )
        if value is not None
    ]
    return {
        "status": "available",
        "linked_report_count": len(reports),
        "evaluated_record_count": evaluated,
        "skipped_record_count": skipped,
        "problem_count": problems,
        "problem_or_skip_count": skipped + problems,
        "top1_agreement_count": top1,
        "top1_agreement_rate": _rate(top1, evaluated),
        "top_k_agreement_count": topk,
        "top_k_agreement_rate": _rate(topk, evaluated),
        "mean_expected_calibration_error": _mean(ece_values),
    }


def _integration_unavailable_count(comparisons: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for comparison in comparisons:
        summaries = _mapping(comparison.get("controller_summaries"))
        model_summary = _mapping(summaries.get(MODEL_GUIDED_ORACLE_V2_LABEL))
        telemetry = _mapping(model_summary.get("search_telemetry_summary"))
        unavailable_fields = _mapping(telemetry.get("unavailable_field_counts"))
        for key, value in unavailable_fields.items():
            if str(key).startswith("model_guided_"):
                count += int(value)
    return count


def _action_space_issue_count(comparisons: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for comparison in comparisons:
        summaries = _mapping(comparison.get("controller_summaries"))
        for summary in summaries.values():
            values = _mapping(summary)
            count += int(values.get("errors") or 0)
            telemetry = _mapping(values.get("search_telemetry_summary"))
            count += _metric_total(telemetry, "root_mapping_failure_count")
            count += _metric_total(telemetry, "unmapped_search_edge_count")
            count += len(values.get("search_telemetry_problems") or [])
    return count


def _distribution_mismatch_count(comparisons: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for comparison in comparisons:
        source = _mapping(comparison.get("source_distribution_summary"))
        assistance = _mapping(source.get("assistance_level_counts"))
        for label, value in assistance.items():
            if str(label) in {
                UNASSISTED_OR_MISSING,
                "assist_0",
                "assist_hp25",
                "assist_hp50",
            }:
                count += int(value)
    return count


def _metric_total(telemetry_summary: Mapping[str, Any], key: str) -> int:
    metric = _mapping(telemetry_summary.get(key))
    value = metric.get("total")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return 0


def _empty_strata_counters() -> dict[str, dict[str, Counter[str]]]:
    return {key: {} for key in STRUCTURAL_KEYS}


def _increment_strata(
    strata: dict[str, dict[str, Counter[str]]],
    result: SingleBattleEvaluationResult,
    metric: str,
) -> None:
    metadata = _metadata_summary(result)
    for key in STRUCTURAL_KEYS:
        label = str(metadata.get(key, MISSING_VALUE))
        strata.setdefault(key, {}).setdefault(label, Counter())[metric] += 1


def _finalize_strata_rates(
    strata: Mapping[str, Mapping[str, Counter[str]]],
    *,
    numerator: str,
    denominator: str,
    rate_name: str,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key, values in strata.items():
        output[key] = {}
        for label, counter in sorted(values.items()):
            denominator_value = int(counter.get(denominator) or 0)
            numerator_value = int(counter.get(numerator) or 0)
            output[key][label] = {
                **_counter_dict(counter),
                rate_name: _rate(numerator_value, denominator_value),
            }
    return output


def _metadata_summary(result: SingleBattleEvaluationResult) -> dict[str, str]:
    metadata = result.structural_metadata
    return {
        "assistance_level": _string(metadata.get("assistance_level"))
        or UNASSISTED_OR_MISSING,
        "distribution_kind": _string(metadata.get("distribution_kind"))
        or MISSING_VALUE,
        "act": str(metadata.get("act") or MISSING_VALUE),
        "room_type": _string(metadata.get("room_type")) or MISSING_VALUE,
        "encounter_id": _string(metadata.get("encounter_id")) or MISSING_VALUE,
        "room_category": _room_category(metadata),
    }


def _room_category(metadata: Mapping[str, Any]) -> str:
    explicit = _string(metadata.get("room_category"))
    if explicit:
        return explicit
    room_type = (_string(metadata.get("room_type")) or "").lower()
    if "boss" in room_type:
        return "boss"
    if "elite" in room_type:
        return "elite"
    if "monster" in room_type or "normal" in room_type:
        return "ordinary"
    return MISSING_VALUE


def _source_identity(result: SingleBattleEvaluationResult) -> str | None:
    if result.source_checkpoint_id:
        return f"source_checkpoint_id:{result.source_checkpoint_id}"
    if result.source_run_id and result.source_battle_index is not None:
        return f"source_run_battle:{result.source_run_id}:{result.source_battle_index}"
    return None


def _win_value(result: SingleBattleEvaluationResult) -> int:
    return 1 if result.termination_status == "win" else 0


def _hp_delta(
    left: SingleBattleEvaluationResult,
    right: SingleBattleEvaluationResult,
) -> int | None:
    if left.terminal_absolute_hp is None or right.terminal_absolute_hp is None:
        return None
    return left.terminal_absolute_hp - right.terminal_absolute_hp


def _potion_delta_counts(result: SingleBattleEvaluationResult) -> dict[str, Any]:
    outcome = result.structured_battle_outcome
    deltas = _mapping(outcome.get("deltas"))
    delta = _mapping(deltas.get("potion_slots_delta"))
    if result.structured_battle_outcome_status != "available" or not delta:
        return {"status": "unavailable", "added": 0, "removed": 0}
    return {
        "status": "available",
        "added": len(_sequence(delta.get("added"))),
        "removed": len(_sequence(delta.get("removed"))),
    }


def _has_target(identity: Mapping[str, Any]) -> bool:
    for key in ("target", "target_monster_index", "target_index", "monster_index"):
        value = identity.get(key)
        if value not in (None, "", -1):
            return True
    return False


def _is_end_turn(action_kind: str, identity: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        str(value).lower()
        for value in (
            action_kind,
            identity.get("action_id"),
            identity.get("stable_id"),
            identity.get("card_id"),
        )
        if value is not None
    )
    return "end" in haystack and "turn" in haystack


def _block_attack_scaling_proxy(category: str) -> str:
    lowered = category.lower()
    if any(token in lowered for token in ("block", "defend", "defence", "defense")):
        return "block_proxy"
    if any(token in lowered for token in ("strike", "attack", "damage", "bash")):
        return "attack_proxy"
    if any(token in lowered for token in ("power", "strength", "dexterity", "scaling")):
        return "scaling_proxy"
    return "unclassified_public_identity"


def _flatten_mappings(value: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        values.append({str(key): item for key, item in value.items()})
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            values.extend(_flatten_mappings(item))
    return values


def _is_list_of_mappings(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and all(isinstance(item, Mapping) for item in value)
    )


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        {str(key): item for key, item in item.items()}
        for item in value
        if isinstance(item, Mapping)
    ]


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _entropy(probabilities: Sequence[float]) -> float | None:
    values = [value for value in probabilities if value > 0.0]
    if not values:
        return None
    return -sum(value * math.log(value) for value in values)


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _mean(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _proportion(item: Mapping[str, Any]) -> float:
    value = item.get("evidence_proportion")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _mapping(value: Any) -> dict[str, Any]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, Mapping)
        else {}
    )


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_float_value(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value)


def _counter_dict(counter: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter, key=str)}


def _add_unavailable(
    unavailable: list[dict[str, Any]],
    *,
    diagnostic: str,
    missing_field: str,
    artifact: Mapping[str, Any],
    cohort_index: int | None,
) -> None:
    unavailable.append(
        {
            "diagnostic": diagnostic,
            "missing_field": missing_field,
            "artifact_id": artifact.get("artifact_id") if artifact else None,
            "path": artifact.get("path") if artifact else None,
            "cohort_index": cohort_index,
        }
    )


def _dedupe_unavailable(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for value in values:
        safe = _json_safe_mapping(value)
        key = json.dumps(safe, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        output.append(safe)
    return output


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_list_of_mappings(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        output.append(_require_mapping(item, f"{label}[{index}]"))
    return output


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _optional_float(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.6f}"


def _optional_rate(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.3f}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
