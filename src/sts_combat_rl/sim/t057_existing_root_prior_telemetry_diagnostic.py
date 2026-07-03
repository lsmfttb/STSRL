"""Offline T057 diagnostic for existing root-prior allocation telemetry.

This module consumes retained current-schema artifacts only. It does not run a
simulator, tune root-prior allocation, revive the guardrail branch, train a
checkpoint, or promote a controller.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import math
from typing import Any, TextIO

from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
    ROOT_PRIOR_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053RootPriorFailureAnalysisReport,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055GuardrailedRootPriorScaleValidationReport,
)
from sts_combat_rl.sim.t056_post_t055_root_prior_path_selection import (
    T056PostT055RootPriorPathSelectionReport,
)


T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID = (
    "t057-existing-root-prior-allocation-telemetry-diagnostic-report-v1"
)
T057_TELEMETRY_DIAGNOSTIC_FORMAT_VERSION = 1
T057_REQUIRED_INPUT_ROLES = (
    "t056_path_selection_report",
    "t048_current_reference_comparison",
    "t048_assist0_reference_comparison",
    "t052_root_prior_guided_comparison",
    "t052_result_summary",
    "t053_failure_analysis_report",
    "t055_current_guardrailed_comparison",
    "t055_assist0_guardrailed_comparison",
    "t055_scale_validation_report",
)
T057_EXPECTED_JSON_SCHEMAS = {
    "t056_path_selection_report": (
        "t056-post-t055-root-prior-path-selection-report-v1"
    ),
    "t048_current_reference_comparison": ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    "t048_assist0_reference_comparison": ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    "t052_root_prior_guided_comparison": ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    "t053_failure_analysis_report": "t053-root-prior-allocation-failure-analysis-v1",
    "t055_current_guardrailed_comparison": ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    "t055_assist0_guardrailed_comparison": ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    "t055_scale_validation_report": (
        "t055-guardrailed-root-prior-scale-validation-report-v1"
    ),
}
T057_COMPARISON_CONTRACTS: dict[str, dict[str, Any]] = {
    "t048_current_reference_comparison": {
        "task_id": "T048",
        "cohort_label": "t048_current_t046_compatible",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "required_labels": REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
        "evidence_family": "t048_positive_fixed_cohort_signal",
    },
    "t048_assist0_reference_comparison": {
        "task_id": "T048",
        "cohort_label": "t048_assist0_runs1000",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "required_labels": REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
        "evidence_family": "t048_positive_fixed_cohort_signal",
    },
    "t052_root_prior_guided_comparison": {
        "task_id": "T052",
        "cohort_label": "t052_boss_later_act_diagnostic",
        "cohort_identity": "68d0e5b10ebcb05d",
        "record_count": 93,
        "required_labels": REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
        "evidence_family": "t052_t053_later_act_boss_diagnostic",
    },
    "t055_current_guardrailed_comparison": {
        "task_id": "T055",
        "cohort_label": "t055_current_t046_guardrail_context",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
        ),
        "evidence_family": "t055_guardrail_closure_context",
    },
    "t055_assist0_guardrailed_comparison": {
        "task_id": "T055",
        "cohort_label": "t055_assist0_runs1000_guardrail_context",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
        ),
        "evidence_family": "t055_guardrail_closure_context",
    },
}
T057_EXISTING_ROOT_PRIOR_COMPARISON_ROLES = (
    "t048_current_reference_comparison",
    "t048_assist0_reference_comparison",
    "t052_root_prior_guided_comparison",
)
T057_EVIDENCE_BOUNDARY = {
    "task_id": "T057",
    "scope": "offline existing-root-prior allocation telemetry diagnostic",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_new_simulator_execution": True,
    "not_controller_tuning": True,
    "not_guardrail_revival": True,
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}
T056_REQUIRED_RECOMMENDATION = "existing-root-prior allocation/telemetry diagnostic"
T057_SELECTED_NEXT_TASK = (
    "root-prior selected-action telemetry instrumentation or replay diagnostic"
)
T057_ALLOWED_NEXT_TASKS = (
    "root-prior selected-action telemetry instrumentation or replay diagnostic",
    "existing-root-prior complete-run reachability probe",
    "another fixed-cohort diagnostic",
    "assisted/de-assisted checkpoint, teacher, or distribution-repair diagnostic",
    "source-generation, reachability, or non-combat-driver branch",
    "publish a blocked path requiring maintainer decision",
)
T057_TAXONOMY_CATEGORIES = (
    "beneficial_allocation_signal",
    "harmful_allocation_signal",
    "no_outcome_change",
    "terminal_hp_only_change",
    "distribution_specific_conflict",
    "telemetry_insufficient_to_assign_cause",
)
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class T057ComparisonInput:
    """Compact streamed view of a root-prior comparison artifact."""

    role: str
    metadata: dict[str, Any]
    battle_comparisons: list[dict[str, Any]]
    results_by_label: dict[str, dict[int, dict[str, Any]]]


@dataclass(frozen=True)
class T057ExistingRootPriorTelemetryDiagnosticReport:
    """Versioned T057 report assembled from retained artifacts."""

    input_artifacts: list[dict[str, Any]]
    prerequisite_summary: dict[str, Any]
    evidence_family_summaries: dict[str, Any]
    cohort_summaries: dict[str, Any]
    subset_summaries: dict[str, Any]
    per_record_outcome_deltas: list[dict[str, Any]]
    allocation_telemetry_summary: dict[str, Any]
    selected_action_availability: dict[str, Any]
    diagnostic_taxonomy: dict[str, Any]
    recommendation: dict[str, Any]
    rejected_alternatives: list[dict[str, Any]]
    unavailable_diagnostics: list[dict[str, Any]]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID
    format_version: int = T057_TELEMETRY_DIAGNOSTIC_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T057_EVIDENCE_BOUNDARY)
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
            "prerequisite_summary": _json_safe_value(self.prerequisite_summary),
            "evidence_family_summaries": _json_safe_value(
                self.evidence_family_summaries
            ),
            "cohort_summaries": _json_safe_value(self.cohort_summaries),
            "subset_summaries": _json_safe_value(self.subset_summaries),
            "per_record_outcome_deltas": _json_safe_value(
                self.per_record_outcome_deltas
            ),
            "allocation_telemetry_summary": _json_safe_value(
                self.allocation_telemetry_summary
            ),
            "selected_action_availability": _json_safe_value(
                self.selected_action_availability
            ),
            "diagnostic_taxonomy": _json_safe_value(self.diagnostic_taxonomy),
            "recommendation": _json_safe_value(self.recommendation),
            "rejected_alternatives": _json_safe_value(self.rejected_alternatives),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def load_t057_root_prior_comparison_inputs(
    stream: TextIO,
    *,
    role: str,
) -> T057ComparisonInput:
    """Stream a comparison JSONL artifact into compact T057 inputs."""

    metadata: dict[str, Any] | None = None
    battle_comparisons: list[dict[str, Any]] = []
    results_by_label: dict[str, dict[int, dict[str, Any]]] = {}
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, Mapping):
            raise ValueError(f"line {line_number}: row must be an object")
        row_type = row.get("type")
        if row_type == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
            _validate_comparison_metadata(metadata)
        elif row_type == "battle_comparison":
            battle_comparisons.append(
                _require_mapping(row.get("comparison"), "comparison")
            )
        elif row_type == "controller_result":
            label = _require_non_empty_string(row.get("label"), "controller label")
            result = _require_mapping(row.get("result"), "result")
            index = _optional_int(result.get("cohort_index"))
            if index is None:
                raise ValueError(f"line {line_number}: result cohort_index missing")
            results_by_label.setdefault(label, {})[index] = _compact_result_summary(
                label,
                result,
            )
        else:
            raise ValueError(f"line {line_number}: unknown row type {row_type!r}")
    if metadata is None:
        raise ValueError("missing root-prior comparison metadata")
    return T057ComparisonInput(
        role=role,
        metadata=metadata,
        battle_comparisons=battle_comparisons,
        results_by_label=results_by_label,
    )


def build_t057_existing_root_prior_telemetry_diagnostic_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    path_selection_report: T056PostT055RootPriorPathSelectionReport,
    comparisons: Mapping[str, T057ComparisonInput],
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> T057ExistingRootPriorTelemetryDiagnosticReport:
    """Build and validate the offline T057 telemetry diagnostic report."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    result_summary = _json_safe_mapping(t052_result_summary)
    safe_comparisons = dict(comparisons)
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        path_selection_report=path_selection_report,
        comparisons=safe_comparisons,
        t052_result_summary=result_summary,
        t053_report=t053_report,
        t055_report=t055_report,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    existing_records = _existing_root_prior_records(safe_comparisons)
    cohort_summaries = _cohort_summaries(safe_comparisons)
    subset_summaries = _subset_summaries(
        records=existing_records,
        t053_report=t053_report,
    )
    allocation_summary = _allocation_telemetry_summary(
        records=existing_records,
        cohort_summaries=cohort_summaries,
    )
    action_availability = _selected_action_availability(existing_records)
    taxonomy = _diagnostic_taxonomy(
        records=existing_records,
        action_availability=action_availability,
        cohort_summaries=cohort_summaries,
    )
    prerequisite_summary = _prerequisite_summary(
        path_selection_report=path_selection_report,
        t053_report=t053_report,
        t055_report=t055_report,
        t052_result_summary=result_summary,
    )
    evidence_family_summaries = _evidence_family_summaries(
        cohort_summaries=cohort_summaries,
        subset_summaries=subset_summaries,
        t053_report=t053_report,
        t055_report=t055_report,
    )
    unavailable = _unavailable_diagnostics(
        selected_action_availability=action_availability,
        t053_report=t053_report,
        t055_report=t055_report,
    )
    recommendation = _recommendation(
        taxonomy=taxonomy,
        selected_action_availability=action_availability,
    )
    return T057ExistingRootPriorTelemetryDiagnosticReport(
        input_artifacts=artifacts,
        prerequisite_summary=prerequisite_summary,
        evidence_family_summaries=evidence_family_summaries,
        cohort_summaries=cohort_summaries,
        subset_summaries=subset_summaries,
        per_record_outcome_deltas=existing_records,
        allocation_telemetry_summary=allocation_summary,
        selected_action_availability=action_availability,
        diagnostic_taxonomy=taxonomy,
        recommendation=recommendation,
        rejected_alternatives=_rejected_alternatives(),
        unavailable_diagnostics=unavailable,
    )


def dump_t057_existing_root_prior_telemetry_diagnostic_report_json(
    report: T057ExistingRootPriorTelemetryDiagnosticReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T057 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t057_existing_root_prior_telemetry_diagnostic_report_json(
    stream: TextIO,
) -> T057ExistingRootPriorTelemetryDiagnosticReport:
    """Load and validate a current-schema T057 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T057 telemetry diagnostic report JSON") from exc
    return t057_existing_root_prior_telemetry_diagnostic_report_from_dict(raw)


def t057_existing_root_prior_telemetry_diagnostic_report_from_dict(
    raw: Mapping[str, Any],
) -> T057ExistingRootPriorTelemetryDiagnosticReport:
    """Validate a current-schema T057 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T057 telemetry diagnostic report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID:
        raise ValueError(
            f"unsupported T057 telemetry diagnostic schema_id {schema_id!r}; "
            f"expected {T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T057_TELEMETRY_DIAGNOSTIC_FORMAT_VERSION:
        raise ValueError(
            "unsupported T057 telemetry diagnostic format_version "
            f"{format_version!r}; expected "
            f"{T057_TELEMETRY_DIAGNOSTIC_FORMAT_VERSION}"
        )
    return T057ExistingRootPriorTelemetryDiagnosticReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        prerequisite_summary=_require_mapping(
            raw.get("prerequisite_summary"),
            "prerequisite_summary",
        ),
        evidence_family_summaries=_require_mapping(
            raw.get("evidence_family_summaries"),
            "evidence_family_summaries",
        ),
        cohort_summaries=_require_mapping(
            raw.get("cohort_summaries"),
            "cohort_summaries",
        ),
        subset_summaries=_require_mapping(
            raw.get("subset_summaries"),
            "subset_summaries",
        ),
        per_record_outcome_deltas=_require_list_of_mappings(
            raw.get("per_record_outcome_deltas"),
            "per_record_outcome_deltas",
        ),
        allocation_telemetry_summary=_require_mapping(
            raw.get("allocation_telemetry_summary"),
            "allocation_telemetry_summary",
        ),
        selected_action_availability=_require_mapping(
            raw.get("selected_action_availability"),
            "selected_action_availability",
        ),
        diagnostic_taxonomy=_require_mapping(
            raw.get("diagnostic_taxonomy"),
            "diagnostic_taxonomy",
        ),
        recommendation=_require_mapping(raw.get("recommendation"), "recommendation"),
        rejected_alternatives=_require_list_of_mappings(
            raw.get("rejected_alternatives", []),
            "rejected_alternatives",
        ),
        unavailable_diagnostics=_require_list_of_mappings(
            raw.get("unavailable_diagnostics", []),
            "unavailable_diagnostics",
        ),
        validation_problems=_require_string_list(
            raw.get("validation_problems", []),
            "validation_problems",
        ),
        evidence_boundary=_require_mapping(
            raw.get("evidence_boundary", T057_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t057_existing_root_prior_telemetry_diagnostic_report(
    report: T057ExistingRootPriorTelemetryDiagnosticReport,
) -> str:
    """Format concise T057 diagnostics for stderr and PR summaries."""

    prereq = report.prerequisite_summary
    action = report.selected_action_availability
    taxonomy = report.diagnostic_taxonomy
    recommendation = report.recommendation
    allocation = report.allocation_telemetry_summary.get("all_existing_root_prior", {})
    lines = [
        "T057 existing root-prior allocation telemetry diagnostic",
        (
            "scope: offline retained-artifact diagnostic only; no simulator, "
            "training, controller tuning, guardrail revival, controller "
            "promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "T056 selected path: "
            + str(prereq.get("t056_selected_next_path", "missing"))
        ),
        (
            "guardrail branch closed: "
            + _yes_no(bool(prereq.get("guardrail_branch_closed")))
        ),
        (
            "existing root-prior decisions summarized: "
            + str(allocation.get("decision_count", 0))
        ),
        (
            "selected-action exact comparison feasible for all records: "
            + _yes_no(bool(action.get("exact_step_level_comparison_feasible_all")))
        ),
        (
            "selected-action availability: available="
            + str(action.get("available_record_count", 0))
            + ", unavailable="
            + str(action.get("unavailable_record_count", 0))
        ),
        "taxonomy:",
    ]
    for category in T057_TAXONOMY_CATEGORIES:
        item = _mapping(taxonomy.get(category))
        lines.append(
            "  "
            + category
            + ": status="
            + str(item.get("status", "missing"))
            + ", count="
            + str(item.get("evidence_count", "missing"))
        )
    lines.append(
        "selected next path: "
        + str(recommendation.get("selected_next_path", "missing"))
    )
    lines.append("rejected alternatives:")
    lines.extend(
        "  - "
        + str(item.get("path", "missing"))
        + ": "
        + str(item.get("reason", "missing"))
        for item in report.rejected_alternatives
    )
    if not report.rejected_alternatives:
        lines.append("  (none)")
    lines.append("unavailable diagnostics:")
    if report.unavailable_diagnostics:
        lines.extend(
            "  - "
            + str(item.get("diagnostic", "missing"))
            + ": "
            + str(item.get("reason", "missing"))
            for item in report.unavailable_diagnostics
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
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    path_selection_report: T056PostT055RootPriorPathSelectionReport,
    comparisons: Mapping[str, T057ComparisonInput],
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> list[str]:
    problems: list[str] = []
    roles = [str(item.get("role") or "") for item in input_artifacts]
    for role in T057_REQUIRED_INPUT_ROLES:
        if role not in roles:
            problems.append(f"missing required T057 input artifact role {role}")
    if len(set(roles)) != len(roles):
        problems.append("duplicate T057 input artifact roles")
    for artifact in input_artifacts:
        role = str(artifact.get("role") or "artifact")
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{role}: sha256 not verified")
        expected_schema = T057_EXPECTED_JSON_SCHEMAS.get(role)
        if expected_schema is None:
            continue
        detected = artifact.get("detected_schema_id")
        if detected not in {expected_schema, None, "unavailable"}:
            problems.append(
                f"{role}: detected schema_id {detected!r} is not {expected_schema!r}"
            )

    _extend_path_selection_problems(problems, path_selection_report)
    _extend_loaded_report_problems(
        problems,
        label="T053 failure-analysis report",
        command_passed=t053_report.command_passed,
    )
    _extend_loaded_report_problems(
        problems,
        label="T055 guardrail scale-validation report",
        command_passed=t055_report.command_passed,
    )
    if t055_report.recommendation.get("recommended_next_task") != (
        "abandon the guardrail path"
    ):
        problems.append("T055 report does not abandon the guardrail path")
    _extend_t052_result_summary_problems(problems, t052_result_summary)
    for role, contract in T057_COMPARISON_CONTRACTS.items():
        comparison = comparisons.get(role)
        if comparison is None:
            problems.append(f"missing loaded comparison for role {role}")
            continue
        _extend_comparison_problems(
            problems,
            role=role,
            comparison=comparison,
            contract=contract,
        )
    return list(dict.fromkeys(problems))


def _validate_comparison_metadata(metadata: Mapping[str, Any]) -> None:
    schema_id = metadata.get("schema_id")
    if schema_id != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID:
        raise ValueError(
            f"unsupported root-prior comparison schema_id {schema_id!r}; "
            f"expected {ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID!r}"
        )
    format_version = metadata.get("format_version")
    if format_version != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION:
        raise ValueError(
            "unsupported root-prior comparison format_version "
            f"{format_version!r}; expected "
            f"{ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION}"
        )


def _extend_path_selection_problems(
    problems: list[str],
    report: T056PostT055RootPriorPathSelectionReport,
) -> None:
    if not report.command_passed:
        problems.append("T056 path-selection report did not pass")
    selected = report.recommendation.get("selected_next_path")
    if selected != T056_REQUIRED_RECOMMENDATION:
        problems.append(
            f"T056 selected path is not {T056_REQUIRED_RECOMMENDATION!r}: {selected!r}"
        )
    if not report.guardrail_branch_closure.get("closed_for_now"):
        problems.append("T056 report does not close the guardrail branch")
    if report.guardrail_branch_closure.get("exact_t055_recommendation") != (
        "abandon the guardrail path"
    ):
        problems.append("T056 report does not preserve the T055 abandon decision")


def _extend_loaded_report_problems(
    problems: list[str],
    *,
    label: str,
    command_passed: bool,
) -> None:
    if not command_passed:
        problems.append(f"{label} did not pass")


def _extend_t052_result_summary_problems(
    problems: list[str],
    summary: Mapping[str, Any],
) -> None:
    config = _mapping(summary.get("comparison_config"))
    if config.get("task_id") != "T052":
        problems.append("T052 result summary comparison_config.task_id is not T052")
    if _as_int(config.get("evaluated_record_count")) != 93:
        problems.append("T052 result summary evaluated_record_count is not 93")
    for section in ("overall", "boss_only", "act2_plus"):
        values = _mapping(summary.get(section))
        if not values:
            problems.append(f"T052 result summary missing {section}")
            continue
        for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
            if not isinstance(values.get(label), Mapping):
                problems.append(f"T052 result summary {section} missing {label}")


def _extend_comparison_problems(
    problems: list[str],
    *,
    role: str,
    comparison: T057ComparisonInput,
    contract: Mapping[str, Any],
) -> None:
    metadata = comparison.metadata
    config = _mapping(metadata.get("comparison_config"))
    if metadata.get("schema_id") != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID:
        problems.append(f"{role}: unsupported schema_id {metadata.get('schema_id')!r}")
    if config.get("task_id") != contract.get("task_id"):
        problems.append(
            f"{role}: task_id {config.get('task_id')!r} is not "
            f"{contract.get('task_id')!r}"
        )
    expected_identity = contract.get("cohort_identity")
    if metadata.get("cohort_identity") != expected_identity:
        problems.append(
            f"{role}: cohort_identity {metadata.get('cohort_identity')!r} is "
            f"not {expected_identity!r}"
        )
    expected_records = _as_int(contract.get("record_count"))
    if _as_int(metadata.get("battle_comparison_count")) != expected_records:
        problems.append(f"{role}: battle_comparison_count is not {expected_records}")
    if len(comparison.battle_comparisons) != expected_records:
        problems.append(f"{role}: streamed battle_comparison count mismatch")
    expected_range = contract.get("record_range")
    if expected_range is not None and config.get("record_range") != expected_range:
        problems.append(
            f"{role}: record_range {config.get('record_range')!r} is not "
            f"{expected_range!r}"
        )
    labels = _controller_labels(metadata)
    for label in _sequence(contract.get("required_labels")):
        if str(label) not in labels:
            problems.append(f"{role}: missing required arm {label}")
        if str(label) not in comparison.results_by_label:
            problems.append(f"{role}: missing controller_result rows for {label}")
    if len(set(labels)) != len(labels):
        problems.append(f"{role}: duplicate arm labels")
    if metadata.get("source_match_status") != "matched":
        problems.append(f"{role}: source_match_status is not matched")
    for label in labels:
        regime = _arm_information_regime(metadata, label)
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{role}:{label}: information regime {regime!r} is not "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
    for key in ("report_problems", "validation_problems", "problems"):
        values = metadata.get(key)
        if isinstance(values, list) and values:
            problems.append(f"{role}: metadata {key} is non-empty")
    root_rows = comparison.results_by_label.get(ROOT_PRIOR_GUIDED_LABEL, {})
    missing_root = [
        index for index in range(expected_records) if index not in root_rows
    ]
    if missing_root:
        problems.append(
            f"{role}: root-prior controller_result rows missing indices "
            + ", ".join(str(index) for index in missing_root[:10])
        )


def _existing_root_prior_records(
    comparisons: Mapping[str, T057ComparisonInput],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for role in T057_EXISTING_ROOT_PRIOR_COMPARISON_ROLES:
        comparison = comparisons[role]
        contract = T057_COMPARISON_CONTRACTS[role]
        records.extend(
            _comparison_records(
                comparison,
                role=role,
                cohort_label=str(contract["cohort_label"]),
                evidence_family=str(contract["evidence_family"]),
            )
        )
    return records


def _comparison_records(
    comparison: T057ComparisonInput,
    *,
    role: str,
    cohort_label: str,
    evidence_family: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in comparison.battle_comparisons:
        index = _optional_int(row.get("comparison_index"))
        if index is None:
            continue
        arms = {
            label: comparison.results_by_label.get(label, {}).get(index, {})
            for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
        }
        source = _source_identity(
            comparison=row,
            preferred_result=(
                arms.get(ROOT_PRIOR_GUIDED_LABEL)
                or arms.get(BASELINE_ORACLE_LABEL)
                or arms.get(POST_SEARCH_MODEL_GUIDED_LABEL)
                or {}
            ),
        )
        root = _mapping(arms.get(ROOT_PRIOR_GUIDED_LABEL))
        baseline = _mapping(arms.get(BASELINE_ORACLE_LABEL))
        post = _mapping(arms.get(POST_SEARCH_MODEL_GUIDED_LABEL))
        action_comparison = _selected_action_comparison(arms)
        outcome = _record_outcome_delta(root=root, baseline=baseline, post=post)
        allocation = _mapping(root.get("root_prior_allocation"))
        records.append(
            {
                "role": role,
                "evidence_family": evidence_family,
                "cohort_label": cohort_label,
                "cohort_identity": comparison.metadata.get("cohort_identity"),
                "cohort_index": index,
                "subset": _subset_label(source),
                "source_identity": source,
                "source_match": bool(row.get("source_match")),
                "outcome_delta": outcome,
                "arms": {
                    BASELINE_ORACLE_LABEL: _arm_public_summary(baseline),
                    POST_SEARCH_MODEL_GUIDED_LABEL: _arm_public_summary(post),
                    ROOT_PRIOR_GUIDED_LABEL: _arm_public_summary(root),
                },
                "root_prior_allocation": _record_allocation_public_summary(allocation),
                "selected_action_comparison": action_comparison,
                "taxonomy_labels": _record_taxonomy_labels(
                    outcome=outcome,
                    allocation=allocation,
                    action_comparison=action_comparison,
                ),
            }
        )
    return records


def _cohort_summaries(
    comparisons: Mapping[str, T057ComparisonInput],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for role, comparison in comparisons.items():
        contract = T057_COMPARISON_CONTRACTS[role]
        labels = [str(label) for label in _sequence(contract["required_labels"])]
        records = _comparison_records(
            comparison,
            role=role,
            cohort_label=str(contract["cohort_label"]),
            evidence_family=str(contract["evidence_family"]),
        )
        output[str(contract["cohort_label"])] = {
            "role": role,
            "task_id": _mapping(comparison.metadata.get("comparison_config")).get(
                "task_id"
            ),
            "evidence_family": contract["evidence_family"],
            "cohort_identity": comparison.metadata.get("cohort_identity"),
            "record_count": len(records),
            "record_range": _mapping(comparison.metadata.get("comparison_config")).get(
                "record_range"
            ),
            "worker_count": _mapping(comparison.metadata.get("comparison_config")).get(
                "worker_count"
            ),
            "shard_count": _mapping(comparison.metadata.get("comparison_config")).get(
                "shard_count"
            ),
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "arm_outcomes": {
                label: _outcome_counts(
                    comparison.results_by_label.get(label, {}).values()
                )
                for label in labels
            },
            "root_prior_vs_baseline": _aggregate_win_delta(
                records,
                left_label=ROOT_PRIOR_GUIDED_LABEL,
                right_label=BASELINE_ORACLE_LABEL,
            ),
            "root_prior_vs_post_search": _aggregate_win_delta(
                records,
                left_label=ROOT_PRIOR_GUIDED_LABEL,
                right_label=POST_SEARCH_MODEL_GUIDED_LABEL,
            ),
            "existing_root_prior_allocation": _aggregate_allocation(
                [_mapping(record.get("root_prior_allocation")) for record in records]
            ),
            "selected_action_availability": _selected_action_availability(records),
            "checkpoint_provenance": _checkpoint_provenance_by_label(
                comparison.metadata,
            ),
            "source_distribution_summary": _json_safe_mapping(
                _mapping(comparison.metadata.get("source_distribution_summary"))
            ),
        }
    return output


def _subset_summaries(
    *,
    records: Sequence[Mapping[str, Any]],
    t053_report: T053RootPriorFailureAnalysisReport,
) -> dict[str, Any]:
    t053_indices = {
        _optional_int(record.get("cohort_index"))
        for record in t053_report.disagreement_records
    }
    if not any(index is not None for index in t053_indices):
        t053_indices = {
            _optional_int(index)
            for index in _sequence(
                t053_report.disagreement_summary.get("cohort_indices")
            )
        }
    t053_indices.discard(None)
    specs = {
        "t048_current_t046_compatible": lambda record: (
            record.get("cohort_label") == "t048_current_t046_compatible"
        ),
        "t048_assist0_runs1000": lambda record: (
            record.get("cohort_label") == "t048_assist0_runs1000"
        ),
        "t052_boss_only": lambda record: (
            record.get("cohort_label") == "t052_boss_later_act_diagnostic"
            and record.get("subset") == "boss_only"
        ),
        "t052_act2_plus": lambda record: (
            record.get("cohort_label") == "t052_boss_later_act_diagnostic"
            and record.get("subset") == "act2_plus"
        ),
        "t053_disagreement_records": lambda record: (
            record.get("cohort_label") == "t052_boss_later_act_diagnostic"
            and _optional_int(record.get("cohort_index")) in t053_indices
        ),
    }
    return {
        name: _record_group_summary(
            [record for record in records if predicate(record)],
            group_label=name,
        )
        for name, predicate in specs.items()
    }


def _record_group_summary(
    records: Sequence[Mapping[str, Any]],
    *,
    group_label: str,
) -> dict[str, Any]:
    return {
        "group_label": group_label,
        "record_count": len(records),
        "cohort_indices": [record.get("cohort_index") for record in records[:200]],
        "arm_outcomes": {
            label: _arm_outcomes_for_records(records, label)
            for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
        },
        "root_prior_vs_baseline": _aggregate_win_delta(
            records,
            left_label=ROOT_PRIOR_GUIDED_LABEL,
            right_label=BASELINE_ORACLE_LABEL,
        ),
        "root_prior_vs_post_search": _aggregate_win_delta(
            records,
            left_label=ROOT_PRIOR_GUIDED_LABEL,
            right_label=POST_SEARCH_MODEL_GUIDED_LABEL,
        ),
        "allocation_telemetry": _aggregate_allocation(
            [_mapping(record.get("root_prior_allocation")) for record in records]
        ),
        "selected_action_availability": _selected_action_availability(records),
        "taxonomy_counts": _taxonomy_counts(records),
    }


def _allocation_telemetry_summary(
    *,
    records: Sequence[Mapping[str, Any]],
    cohort_summaries: Mapping[str, Any],
) -> dict[str, Any]:
    t048_records = [
        record
        for record in records
        if record.get("evidence_family") == "t048_positive_fixed_cohort_signal"
    ]
    t052_records = [
        record
        for record in records
        if record.get("evidence_family") == "t052_t053_later_act_boss_diagnostic"
    ]
    return {
        "all_existing_root_prior": _aggregate_allocation(
            [_mapping(record.get("root_prior_allocation")) for record in records]
        ),
        "t048_positive_fixed_cohort_signal": _aggregate_allocation(
            [_mapping(record.get("root_prior_allocation")) for record in t048_records]
        ),
        "t052_t053_later_act_boss_diagnostic": _aggregate_allocation(
            [_mapping(record.get("root_prior_allocation")) for record in t052_records]
        ),
        "by_cohort": {
            label: _mapping(summary).get("existing_root_prior_allocation", {})
            for label, summary in cohort_summaries.items()
            if label
            in {
                "t048_current_t046_compatible",
                "t048_assist0_runs1000",
                "t052_boss_later_act_diagnostic",
            }
        },
    }


def _selected_action_availability(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter()
    missing_counts = Counter()
    available = 0
    exact_full = 0
    partial = 0
    affected: dict[str, list[int]] = {}
    for record in records:
        diagnostic = _mapping(record.get("selected_action_comparison"))
        status = str(diagnostic.get("status") or MISSING_VALUE)
        status_counts[status] += 1
        if status == "available":
            available += 1
            if diagnostic.get("exact_full_battle_path_comparison"):
                exact_full += 1
            else:
                partial += 1
        else:
            cohort = str(record.get("cohort_label") or MISSING_VALUE)
            affected.setdefault(cohort, []).append(_as_int(record.get("cohort_index")))
            for reason in _sequence(diagnostic.get("missing_reasons")):
                missing_counts[str(reason)] += 1
            if not diagnostic.get("missing_reasons") and diagnostic.get("reason"):
                missing_counts[str(diagnostic.get("reason"))] += 1
    unavailable = len(records) - available
    return {
        "record_count": len(records),
        "available_record_count": available,
        "partial_record_count": partial,
        "exact_full_record_count": exact_full,
        "unavailable_record_count": unavailable,
        "status_counts": _counter_dict(status_counts),
        "missing_field_or_reason_counts": _counter_dict(missing_counts),
        "affected_cohorts": {
            key: sorted(set(value))[:200] for key, value in sorted(affected.items())
        },
        "exact_step_level_comparison_feasible_all": (
            bool(records) and exact_full == len(records)
        ),
        "interpretation": (
            "exact all-arm step-level selected-action comparison is available "
            "only when every required arm reports comparable selected action "
            "identities for every decision in each matched record"
        ),
    }


def _diagnostic_taxonomy(
    *,
    records: Sequence[Mapping[str, Any]],
    action_availability: Mapping[str, Any],
    cohort_summaries: Mapping[str, Any],
) -> dict[str, Any]:
    counts = _taxonomy_counts(records)
    output: dict[str, Any] = {}
    for category in T057_TAXONOMY_CATEGORIES:
        count = _as_int(counts.get(category))
        output[category] = {
            "status": "supported" if count else "not_observed",
            "evidence_count": count,
            "record_count": len(records),
            "evidence_proportion": _rate(count, len(records)),
            "cohort_indices": [
                {
                    "cohort_label": record.get("cohort_label"),
                    "cohort_index": record.get("cohort_index"),
                }
                for record in records
                if category in _sequence(record.get("taxonomy_labels"))
            ][:200],
        }
    conflict = _distribution_conflict_summary(cohort_summaries)
    conflict_item = output["distribution_specific_conflict"]
    conflict_item.update(conflict)
    if conflict.get("status") == "supported":
        conflict_item["evidence_count"] = 1
    telemetry_item = output["telemetry_insufficient_to_assign_cause"]
    unavailable = _as_int(action_availability.get("unavailable_record_count"))
    if unavailable:
        telemetry_item["status"] = "supported"
        telemetry_item["evidence_count"] = max(
            _as_int(telemetry_item.get("evidence_count")),
            unavailable,
        )
        telemetry_item["reason"] = (
            "selected-action identities or exact all-arm step-level comparison "
            "fields are unavailable for at least one retained record"
        )
    return output


def _taxonomy_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for record in records:
        for label in _sequence(record.get("taxonomy_labels")):
            counts[str(label)] += 1
    return _counter_dict(counts)


def _prerequisite_summary(
    *,
    path_selection_report: T056PostT055RootPriorPathSelectionReport,
    t053_report: T053RootPriorFailureAnalysisReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
    t052_result_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "t056_schema_id": path_selection_report.schema_id,
        "t056_command_passed": path_selection_report.command_passed,
        "t056_selected_next_path": path_selection_report.recommendation.get(
            "selected_next_path"
        ),
        "t056_required_next_path_matched": (
            path_selection_report.recommendation.get("selected_next_path")
            == T056_REQUIRED_RECOMMENDATION
        ),
        "guardrail_branch_closed": bool(
            path_selection_report.guardrail_branch_closure.get("closed_for_now")
        ),
        "t055_exact_recommendation": t055_report.recommendation.get(
            "recommended_next_task"
        ),
        "t053_disagreement_summary": _json_safe_mapping(
            t053_report.disagreement_summary
        ),
        "t053_action_comparison_diagnostics": _json_safe_mapping(
            t053_report.action_comparison_diagnostics
        ),
        "t052_result_summary": {
            "comparison_config": _json_safe_mapping(
                _mapping(t052_result_summary.get("comparison_config"))
            ),
            "overall": _t052_counts(t052_result_summary.get("overall")),
            "boss_only": _t052_counts(t052_result_summary.get("boss_only")),
            "act2_plus": _t052_counts(t052_result_summary.get("act2_plus")),
        },
        "no_new_simulator_execution": True,
    }


def _evidence_family_summaries(
    *,
    cohort_summaries: Mapping[str, Any],
    subset_summaries: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> dict[str, Any]:
    t048_labels = ("t048_current_t046_compatible", "t048_assist0_runs1000")
    t048_summaries = [_mapping(cohort_summaries.get(label)) for label in t048_labels]
    return {
        "t048_positive_fixed_cohort_signal": {
            "cohort_labels": list(t048_labels),
            "aggregate_outcomes": _aggregate_group_outcomes(t048_summaries),
            "allocation_telemetry": _aggregate_allocation(
                [
                    _mapping(summary.get("existing_root_prior_allocation"))
                    for summary in t048_summaries
                ]
            ),
            "interpretation": (
                "retained T048 cohorts remain positive fixed-cohort evidence "
                "for the existing root-prior arm only"
            ),
        },
        "t052_t053_later_act_boss_diagnostic": {
            "cohort_label": "t052_boss_later_act_diagnostic",
            "t052_boss_only": _json_safe_mapping(
                _mapping(subset_summaries.get("t052_boss_only"))
            ),
            "t052_act2_plus": _json_safe_mapping(
                _mapping(subset_summaries.get("t052_act2_plus"))
            ),
            "t053_disagreement_records": _json_safe_mapping(
                _mapping(subset_summaries.get("t053_disagreement_records"))
            ),
            "t053_failure_taxonomy": _json_safe_mapping(t053_report.failure_taxonomy),
            "interpretation": (
                "T052/T053 later-act and Boss evidence conflicts with the "
                "positive retained T048 signal and keeps causal allocation "
                "diagnosis unresolved"
            ),
        },
        "t055_guardrail_closure_context": {
            "recommendation": _json_safe_mapping(t055_report.recommendation),
            "aggregate_summary": _json_safe_mapping(t055_report.aggregate_summary),
            "cohort_labels": [
                "t055_current_t046_guardrail_context",
                "t055_assist0_runs1000_guardrail_context",
            ],
            "interpretation": (
                "guardrailed root-prior evidence is abandoned-branch context "
                "only and is not the selected next implementation path"
            ),
        },
    }


def _recommendation(
    *,
    taxonomy: Mapping[str, Any],
    selected_action_availability: Mapping[str, Any],
) -> dict[str, Any]:
    unavailable = _as_int(selected_action_availability.get("unavailable_record_count"))
    telemetry = _mapping(taxonomy.get("telemetry_insufficient_to_assign_cause"))
    return {
        "recommendation_count": 1,
        "selected_next_path": T057_SELECTED_NEXT_TASK,
        "recommended_next_task": T057_SELECTED_NEXT_TASK,
        "allowed_recommendation_set": list(T057_ALLOWED_NEXT_TASKS),
        "reason": (
            "retained artifacts can summarize existing-root-prior allocation "
            "and outcome deltas, but exact all-arm selected-action comparison "
            "is not feasible for every required record; the next branch should "
            "instrument or replay selected-action telemetry before reachability, "
            "training repair, or another fixed-cohort branch"
        ),
        "evidence_support": {
            "selected_action_unavailable_record_count": unavailable,
            "telemetry_insufficient_count": telemetry.get("evidence_count"),
            "exact_step_level_comparison_feasible_all_records": bool(
                selected_action_availability.get(
                    "exact_step_level_comparison_feasible_all"
                )
            ),
            "t056_selected_existing_root_prior_diagnostic": True,
            "guardrail_path_closed": True,
        },
        "forbidden_claims": {
            "controller_promotion": False,
            "live_game_strength": False,
            "natural_a20_performance": False,
            "broad_training_readiness": False,
            "normal_information_strength": False,
            "final_agent_status": False,
        },
    }


def _rejected_alternatives() -> list[dict[str, Any]]:
    return [
        {
            "path": "existing-root-prior complete-run reachability probe",
            "reason": (
                "the retained fixed-cohort artifacts still lack exact all-arm "
                "selected-action telemetry, so reachability would skip the "
                "blocking diagnostic gap"
            ),
        },
        {
            "path": "another fixed-cohort diagnostic",
            "reason": (
                "another comparison would generate more outcomes without first "
                "making selected-action causality auditable"
            ),
        },
        {
            "path": (
                "assisted/de-assisted checkpoint, teacher, or "
                "distribution-repair diagnostic"
            ),
            "reason": (
                "T057 is scoped to existing-root-prior allocation telemetry, "
                "and retained evidence points to a telemetry/replay gap before "
                "new training or distribution work"
            ),
        },
        {
            "path": "source-generation, reachability, or non-combat-driver branch",
            "reason": (
                "T050/T051 reachability remains context, but this diagnostic "
                "does not authorize a new source-generation or non-combat branch"
            ),
        },
        {
            "path": "publish a blocked path requiring maintainer decision",
            "reason": (
                "the retained artifacts support exactly one concrete next task "
                "inside the allowed T057 set"
            ),
        },
    ]


def _unavailable_diagnostics(
    *,
    selected_action_availability: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        _json_safe_mapping(item) for item in t053_report.unavailable_diagnostics
    )
    rows.extend(
        _json_safe_mapping(item) for item in t055_report.unavailable_diagnostics
    )
    if _as_int(selected_action_availability.get("unavailable_record_count")):
        rows.append(
            {
                "diagnostic": "exact_all_arm_step_level_selected_action_comparison",
                "reason": (
                    "one or more required retained records lack comparable "
                    "selected action identities across baseline, post-search, "
                    "and existing root-prior arms"
                ),
                "affected_cohorts": _json_safe_mapping(
                    _mapping(selected_action_availability.get("affected_cohorts"))
                ),
            }
        )
    rows.append(
        {
            "diagnostic": "normal_information_strength",
            "reason": (
                "all T048/T052/T055 search evidence remains "
                f"{NATIVE_SEARCH_INFORMATION_REGIME}"
            ),
        }
    )
    rows.append(
        {
            "diagnostic": "allocation_causal_counterfactual",
            "reason": (
                "retained artifacts do not contain paired within-decision "
                "counterfactual native search trees for alternate allocations"
            ),
        }
    )
    return _dedupe_unavailable(rows)


def _compact_result_summary(label: str, result: Mapping[str, Any]) -> dict[str, Any]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    search_summary = _mapping(telemetry.get("search_telemetry_summary"))
    selected_actions, selected_reason = _selected_actions_for_result(label, result)
    summary = {
        "cohort_index": result.get("cohort_index"),
        "source_identity": _source_identity_from_result(result),
        "structural_metadata": _json_safe_mapping(
            _mapping(result.get("structural_metadata"))
        ),
        "termination_status": result.get("termination_status"),
        "terminal_absolute_hp": result.get("terminal_absolute_hp"),
        "hp_loss": result.get("hp_loss"),
        "decision_count": result.get("decision_count"),
        "simulator_step_count": result.get("simulator_step_count"),
        "wall_clock_time_s": result.get("wall_clock_time_s"),
        "restoration_method": result.get("restoration_method"),
        "restore_status": _restore_status(result),
        "truncation_status": (
            "truncated" if result.get("termination_status") == "truncated" else "none"
        ),
        "controller_problem_count": len(_sequence(result.get("problems"))),
        "controller_problems": _string_list(result.get("problems")),
        "information_regime": result.get("information_regime"),
        "public_context_status": result.get("public_context_status"),
        "public_context_replay_status": result.get("public_context_replay_status"),
        "structured_battle_outcome_status": result.get(
            "structured_battle_outcome_status"
        ),
        "structured_resource_status": result.get("structured_battle_outcome_status"),
        "model_calls": _telemetry_total(search_summary, "model_calls")
        or _optional_int(telemetry.get("root_prior_guided_model_calls"))
        or _optional_int(telemetry.get("oracle_search_model_calls")),
        "native_search_simulator_steps": _telemetry_total(
            search_summary,
            "native_simulator_steps",
        ),
        "root_mapping_failures": _telemetry_total(
            search_summary,
            "root_mapping_failure_count",
        ),
        "unsearched_legal_action_count": _telemetry_total(
            search_summary,
            "unsearched_legal_action_count",
        ),
        "root_visits": _telemetry_total(search_summary, "root_visits"),
        "selected_actions": selected_actions,
        "selected_action_missing_reason": selected_reason,
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        summary["root_prior_allocation"] = _root_prior_allocation_summary_for_result(
            result
        )
    return summary


def _root_prior_allocation_summary_for_result(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    reports = _root_prior_decision_reports(result)
    malformed = 0
    positive_prior_total = 0
    provided_prior_total = 0
    missing_prior_decision_count = 0
    root_mapping_failures = 0
    unsearched_legal_actions = 0
    selected_indices: Counter[str] = Counter()
    selected_actions: list[dict[str, Any]] = []
    selected_action_identity_available = 0
    visit_totals: Counter[str] = Counter()
    positive_prior_selected_count = 0
    allocated_to_positive_prior_total = 0
    allocated_to_zero_prior_total = 0
    root_visit_distribution: list[dict[str, Any]] = []
    for index, decision in enumerate(reports):
        metadata = _mapping(decision.get("allocation_metadata"))
        if (
            metadata.get("schema_id") != NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
            or metadata.get("allocation_strategy")
            != NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY
        ):
            malformed += 1
        prior = _mapping(decision.get("prior_summary"))
        positive_prior_total += _as_int(prior.get("positive_prior_count"))
        provided_prior_total += _as_int(prior.get("provided_prior_count"))
        if _as_int(prior.get("positive_prior_count")) <= 0:
            missing_prior_decision_count += 1
        target = _mapping(decision.get("target"))
        selected = _optional_int(target.get("legal_action_index"))
        if selected is not None:
            selected_indices[str(selected)] += 1
            action = {
                "decision_index": index,
                "selected_index": selected,
                "target": _target_summary(target),
            }
            if _mapping(target.get("action_identity")):
                selected_action_identity_available += 1
            selected_actions.append(action)
        rows = [
            _mapping(row)
            for row in _sequence(decision.get("allocation_rows"))
            if isinstance(row, Mapping)
        ]
        selected_row = _row_for_selected_index(rows, selected)
        if selected_row and _optional_float_value(selected_row.get("root_prior")):
            positive_prior_selected_count += 1
        for row in rows:
            visits = _as_int(row.get("visits"))
            allocated = _as_int(row.get("allocated_root_visits"))
            prior_value = _optional_float_value(row.get("root_prior")) or 0.0
            if visits <= 0:
                unsearched_legal_actions += 1
            if prior_value > 0.0:
                allocated_to_positive_prior_total += allocated
            else:
                allocated_to_zero_prior_total += allocated
            visit_totals[_action_bucket(row)] += visits
        root_visit_distribution.append(
            {
                "decision_index": index,
                "root_action_count": len(rows),
                "visited_action_count": sum(
                    1 for row in rows if _as_int(row.get("visits")) > 0
                ),
                "unsearched_legal_action_count": sum(
                    1 for row in rows if _as_int(row.get("visits")) <= 0
                ),
                "max_visits": max(
                    (_as_int(row.get("visits")) for row in rows),
                    default=0,
                ),
                "max_allocated_root_visits": max(
                    (_as_int(row.get("allocated_root_visits")) for row in rows),
                    default=0,
                ),
                "positive_prior_action_count": sum(
                    1
                    for row in rows
                    if (_optional_float_value(row.get("root_prior")) or 0.0) > 0.0
                ),
            }
        )
        oracle = _mapping(decision.get("oracle_search_report"))
        root_mapping_failures += _as_int(oracle.get("root_mapping_failure_count"))
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    search_summary = _mapping(telemetry.get("search_telemetry_summary"))
    root_mapping_failures += _as_int(
        _telemetry_total(search_summary, "root_mapping_failure_count")
    )
    unsearched_legal_actions += _as_int(
        _telemetry_total(search_summary, "unsearched_legal_action_count")
    )
    return {
        "decision_count": len(reports),
        "selected_actions": selected_actions,
        "selected_action_identity_available_count": selected_action_identity_available,
        "selected_index_counts": _counter_dict(selected_indices),
        "positive_prior_count": positive_prior_total,
        "provided_prior_count": provided_prior_total,
        "missing_prior_decision_count": missing_prior_decision_count,
        "malformed_allocation_metadata_count": malformed,
        "root_mapping_failure_count": root_mapping_failures,
        "unsearched_legal_action_count": unsearched_legal_actions,
        "positive_prior_selected_count": positive_prior_selected_count,
        "positive_prior_selected_rate": _rate(
            positive_prior_selected_count,
            len(reports),
        ),
        "allocated_visits_to_positive_prior": allocated_to_positive_prior_total,
        "allocated_visits_to_zero_prior": allocated_to_zero_prior_total,
        "visit_distribution_by_action_bucket": _counter_dict(visit_totals),
        "root_visit_distribution": root_visit_distribution,
        "first_decision": _decision_detail(reports[0]) if reports else {},
        "last_decision": _decision_detail(reports[-1]) if reports else {},
    }


def _selected_action_comparison(
    arms: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    root = _mapping(arms.get(ROOT_PRIOR_GUIDED_LABEL))
    baseline = _mapping(arms.get(BASELINE_ORACLE_LABEL))
    post = _mapping(arms.get(POST_SEARCH_MODEL_GUIDED_LABEL))
    root_actions = _list_of_mappings(root.get("selected_actions"))
    baseline_actions = _list_of_mappings(baseline.get("selected_actions"))
    post_actions = _list_of_mappings(post.get("selected_actions"))
    missing_reasons = []
    for label, arm, actions in (
        (BASELINE_ORACLE_LABEL, baseline, baseline_actions),
        (POST_SEARCH_MODEL_GUIDED_LABEL, post, post_actions),
        (ROOT_PRIOR_GUIDED_LABEL, root, root_actions),
    ):
        reason = arm.get("selected_action_missing_reason")
        if reason is not None:
            missing_reasons.append(f"{label}:{reason}")
        elif not actions:
            missing_reasons.append(f"{label}:selected action identity unavailable")
    if missing_reasons:
        return {
            "status": "unavailable",
            "reason": "; ".join(missing_reasons),
            "missing_reasons": missing_reasons,
            "exact_step_level_matching": False,
            "exact_full_battle_path_comparison": False,
            "root_prior_decision_count": len(root_actions),
            "baseline_decision_count": len(baseline_actions),
            "post_search_decision_count": len(post_actions),
            "root_prior_first_actions": root_actions[:5],
            "baseline_first_actions": baseline_actions[:5],
            "post_search_first_actions": post_actions[:5],
        }
    comparable_count = min(len(root_actions), len(baseline_actions), len(post_actions))
    full_path = (
        len(root_actions) == len(baseline_actions) == len(post_actions)
        and comparable_count > 0
    )
    return {
        "status": "available",
        "exact_step_level_matching": True,
        "exact_full_battle_path_comparison": full_path,
        "comparable_decision_count": comparable_count,
        "root_prior_decision_count": len(root_actions),
        "baseline_decision_count": len(baseline_actions),
        "post_search_decision_count": len(post_actions),
        "root_prior_first_actions": root_actions[:5],
        "baseline_first_actions": baseline_actions[:5],
        "post_search_first_actions": post_actions[:5],
        "first_difference_vs_baseline": _first_action_difference(
            root_actions,
            baseline_actions,
        ),
        "first_difference_vs_post_search": _first_action_difference(
            root_actions,
            post_actions,
        ),
        "root_prior_matches_baseline_action_count": _matching_action_count(
            root_actions,
            baseline_actions,
        ),
        "root_prior_matches_post_search_action_count": _matching_action_count(
            root_actions,
            post_actions,
        ),
    }


def _selected_actions_for_result(
    label: str,
    result: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        reports = _root_prior_decision_reports(result)
    else:
        reports = _flatten_mappings(telemetry.get("oracle_search_decision_reports"))
        if not reports:
            reports = _flatten_mappings(telemetry.get("search_decision_telemetry"))
    actions: list[dict[str, Any]] = []
    missing_identity = False
    for report in reports:
        target = _mapping(report.get("target"))
        if target:
            actions.append(_target_summary(target))
            continue
        identity = _mapping(report.get("selected_action_identity"))
        if identity:
            actions.append(
                {
                    "selected_index": report.get("selected_legal_action_index"),
                    "action_identity": _json_safe_mapping(identity),
                }
            )
            continue
        selected_index = _optional_int(report.get("selected_legal_action_index"))
        if selected_index is not None:
            actions.append(
                {
                    "selected_index": selected_index,
                    "action_identity": {},
                }
            )
            missing_identity = True
            continue
        missing_identity = True
    if actions:
        reason = "some selected action identities missing" if missing_identity else None
        return actions, reason
    return [], "selected action identity unavailable in retained telemetry"


def _record_outcome_delta(
    *,
    root: Mapping[str, Any],
    baseline: Mapping[str, Any],
    post: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "root_prior_vs_baseline": _outcome_delta(root, baseline),
        "root_prior_vs_post_search": _outcome_delta(root, post),
        "root_prior_harmful_vs_any": _is_harmful(root, baseline)
        or _is_harmful(root, post),
        "root_prior_beneficial_vs_any": _is_harmful(baseline, root)
        or _is_harmful(post, root),
        "same_win_status_all_arms": _same_win_status(root, baseline)
        and _same_win_status(root, post),
        "terminal_hp_only_difference": (
            _same_win_status(root, baseline)
            and _same_win_status(root, post)
            and (
                _optional_int(root.get("terminal_absolute_hp"))
                != _optional_int(baseline.get("terminal_absolute_hp"))
                or _optional_int(root.get("terminal_absolute_hp"))
                != _optional_int(post.get("terminal_absolute_hp"))
            )
        ),
        "all_outcomes_identical": (
            _outcome_signature(root)
            == _outcome_signature(baseline)
            == _outcome_signature(post)
        ),
    }


def _record_taxonomy_labels(
    *,
    outcome: Mapping[str, Any],
    allocation: Mapping[str, Any],
    action_comparison: Mapping[str, Any],
) -> list[str]:
    labels: list[str] = []
    if outcome.get("root_prior_beneficial_vs_any"):
        labels.append("beneficial_allocation_signal")
    if outcome.get("root_prior_harmful_vs_any"):
        labels.append("harmful_allocation_signal")
    if outcome.get("all_outcomes_identical"):
        labels.append("no_outcome_change")
    if outcome.get("terminal_hp_only_difference"):
        labels.append("terminal_hp_only_change")
    if (
        action_comparison.get("status") != "available"
        or _as_int(allocation.get("decision_count")) <= 0
        or _as_int(allocation.get("malformed_allocation_metadata_count")) > 0
    ):
        labels.append("telemetry_insufficient_to_assign_cause")
    return list(dict.fromkeys(labels))


def _aggregate_allocation(
    allocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    totals = Counter()
    selected_indices = Counter()
    visit_buckets = Counter()
    root_action_count = 0
    visited_action_count = 0
    unsearched_action_count = 0
    max_visits = 0
    max_allocated = 0
    samples: list[dict[str, Any]] = []
    first_decisions: list[dict[str, Any]] = []
    for allocation in allocations:
        totals["decision_count"] += _as_int(allocation.get("decision_count"))
        totals["positive_prior_count"] += _as_int(
            allocation.get("positive_prior_count")
        )
        totals["provided_prior_count"] += _as_int(
            allocation.get("provided_prior_count")
        )
        totals["missing_prior_decision_count"] += _as_int(
            allocation.get("missing_prior_decision_count")
        )
        totals["malformed_allocation_metadata_count"] += _as_int(
            allocation.get("malformed_allocation_metadata_count")
        )
        totals["root_mapping_failure_count"] += _as_int(
            allocation.get("root_mapping_failure_count")
        )
        totals["unsearched_legal_action_count"] += _as_int(
            allocation.get("unsearched_legal_action_count")
        )
        totals["positive_prior_selected_count"] += _as_int(
            allocation.get("positive_prior_selected_count")
        )
        totals["allocated_visits_to_positive_prior"] += _as_int(
            allocation.get("allocated_visits_to_positive_prior")
        )
        totals["allocated_visits_to_zero_prior"] += _as_int(
            allocation.get("allocated_visits_to_zero_prior")
        )
        for key, value in _mapping(allocation.get("selected_index_counts")).items():
            selected_indices[str(key)] += _as_int(value)
        for key, value in _mapping(
            allocation.get("visit_distribution_by_action_bucket")
        ).items():
            visit_buckets[str(key)] += _as_int(value)
        for item in _list_of_mappings(allocation.get("root_visit_distribution")):
            root_action_count += _as_int(item.get("root_action_count"))
            visited_action_count += _as_int(item.get("visited_action_count"))
            unsearched_action_count += _as_int(
                item.get("unsearched_legal_action_count")
            )
            max_visits = max(max_visits, _as_int(item.get("max_visits")))
            max_allocated = max(
                max_allocated,
                _as_int(item.get("max_allocated_root_visits")),
            )
        samples.extend(_list_of_mappings(allocation.get("selected_actions"))[:2])
        if allocation.get("first_decision"):
            first_decisions.append(
                _json_safe_mapping(_mapping(allocation["first_decision"]))
            )
    decision_count = totals["decision_count"]
    return {
        **_counter_dict(totals),
        "selected_index_counts": _counter_dict(selected_indices),
        "visit_distribution_by_action_bucket": _counter_dict(visit_buckets),
        "positive_prior_selected_rate": _rate(
            totals["positive_prior_selected_count"],
            decision_count,
        ),
        "missing_prior_decision_rate": _rate(
            totals["missing_prior_decision_count"],
            decision_count,
        ),
        "malformed_allocation_metadata_rate": _rate(
            totals["malformed_allocation_metadata_count"],
            decision_count,
        ),
        "root_visit_distribution_summary": {
            "decision_count": decision_count,
            "root_action_count_total": root_action_count,
            "visited_action_count_total": visited_action_count,
            "unsearched_action_count_total": unsearched_action_count,
            "max_visits_observed": max_visits,
            "max_allocated_root_visits_observed": max_allocated,
        },
        "selected_action_samples": [_json_safe_mapping(item) for item in samples[:20]],
        "first_decision_samples": first_decisions[:5],
    }


def _record_allocation_public_summary(
    allocation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "decision_count": allocation.get("decision_count"),
        "positive_prior_count": allocation.get("positive_prior_count"),
        "provided_prior_count": allocation.get("provided_prior_count"),
        "missing_prior_decision_count": allocation.get("missing_prior_decision_count"),
        "malformed_allocation_metadata_count": allocation.get(
            "malformed_allocation_metadata_count"
        ),
        "root_mapping_failure_count": allocation.get("root_mapping_failure_count"),
        "unsearched_legal_action_count": allocation.get(
            "unsearched_legal_action_count"
        ),
        "positive_prior_selected_count": allocation.get(
            "positive_prior_selected_count"
        ),
        "selected_index_counts": _json_safe_mapping(
            _mapping(allocation.get("selected_index_counts"))
        ),
        "selected_actions": _json_safe_value(allocation.get("selected_actions", [])),
        "root_visit_distribution": _json_safe_value(
            allocation.get("root_visit_distribution", [])
        ),
    }


def _decision_detail(decision: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        _mapping(row)
        for row in _sequence(decision.get("allocation_rows"))
        if isinstance(row, Mapping)
    ]
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            -_as_int(row.get("visits")),
            -(_optional_float_value(row.get("mean_value")) or float("-inf")),
            str(row.get("label") or ""),
        ),
    )
    return {
        "target": _target_summary(_mapping(decision.get("target"))),
        "prior_summary": _json_safe_mapping(_mapping(decision.get("prior_summary"))),
        "allocation_metadata": _allocation_metadata_summary(
            _mapping(decision.get("allocation_metadata"))
        ),
        "top_root_rows_by_visits": [
            _allocation_row_summary(row) for row in ordered_rows[:5]
        ],
    }


def _allocation_metadata_summary(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": metadata.get("schema_id"),
        "allocation_strategy": metadata.get("allocation_strategy"),
        "allocated_root_visits": metadata.get("allocated_root_visits"),
        "eligible_root_action_count": metadata.get("eligible_root_action_count"),
        "legal_action_prior_count": metadata.get("legal_action_prior_count"),
        "matched_prior_mass": metadata.get("matched_prior_mass"),
        "min_visits_per_legal_action": metadata.get("min_visits_per_legal_action"),
        "prior_allocation_weight": metadata.get("prior_allocation_weight"),
        "prior_temperature": metadata.get("prior_temperature"),
        "allocation_plan_count": len(_sequence(metadata.get("allocation_plan"))),
    }


def _allocation_row_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label": row.get("label"),
        "kind": row.get("kind"),
        "search_edge_index": row.get("search_edge_index"),
        "root_prior": row.get("root_prior"),
        "allocated_root_visits": row.get("allocated_root_visits"),
        "visits": row.get("visits"),
        "mean_value": row.get("mean_value"),
        "search_tree_present": row.get("search_tree_present"),
    }


def _target_summary(target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selected_index": target.get("legal_action_index"),
        "visits": target.get("visits"),
        "mean_value": target.get("mean_value"),
        "score": target.get("score"),
        "selection_rule": target.get("selection_rule"),
        "action_identity": _json_safe_mapping(_mapping(target.get("action_identity"))),
    }


def _arm_public_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "termination_status",
        "terminal_absolute_hp",
        "hp_loss",
        "decision_count",
        "simulator_step_count",
        "wall_clock_time_s",
        "restoration_method",
        "restore_status",
        "truncation_status",
        "controller_problem_count",
        "controller_problems",
        "information_regime",
        "public_context_status",
        "public_context_replay_status",
        "structured_resource_status",
        "model_calls",
        "native_search_simulator_steps",
        "root_mapping_failures",
        "unsearched_legal_action_count",
        "root_visits",
    )
    return {key: _json_safe_value(result.get(key)) for key in keys}


def _source_identity(
    *,
    comparison: Mapping[str, Any],
    preferred_result: Mapping[str, Any],
) -> dict[str, Any]:
    source = _mapping(comparison.get("source"))
    result_source = _mapping(preferred_result.get("source_identity"))
    structural = _mapping(preferred_result.get("structural_metadata"))
    return {
        **_json_safe_mapping(source),
        **_json_safe_mapping(result_source),
        "act": structural.get("act"),
        "room_type": structural.get("room_type"),
        "encounter_id": structural.get("encounter_id"),
        "distribution_kind": structural.get("distribution_kind"),
        "assistance_level": structural.get("assistance_level"),
        "selection_reasons": _json_safe_value(structural.get("selection_reasons", [])),
    }


def _source_identity_from_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cohort_index": result.get("cohort_index"),
        "source_checkpoint_id": result.get("source_checkpoint_id"),
        "source_seed": result.get("source_seed"),
        "source_run_id": result.get("source_run_id"),
        "source_battle_index": result.get("source_battle_index"),
        "structural_stratum": _json_safe_value(result.get("structural_stratum", [])),
    }


def _subset_label(source: Mapping[str, Any]) -> str:
    act = _optional_int(source.get("act"))
    if act is not None and act >= 2:
        return "act2_plus"
    room_type = str(source.get("room_type") or "").lower()
    if "boss" in room_type:
        return "boss_only"
    reasons = {str(item).lower() for item in _sequence(source.get("selection_reasons"))}
    if "act2_plus" in reasons:
        return "act2_plus"
    if "act1_boss" in reasons:
        return "boss_only"
    return "other"


def _distribution_conflict_summary(
    cohort_summaries: Mapping[str, Any],
) -> dict[str, Any]:
    t048 = [
        _mapping(cohort_summaries.get("t048_current_t046_compatible")),
        _mapping(cohort_summaries.get("t048_assist0_runs1000")),
    ]
    t052 = _mapping(cohort_summaries.get("t052_boss_later_act_diagnostic"))
    t048_delta = sum(
        _as_int(_mapping(item.get("root_prior_vs_baseline")).get("win_delta"))
        for item in t048
    )
    t052_delta = _as_int(_mapping(t052.get("root_prior_vs_baseline")).get("win_delta"))
    supported = t048_delta > 0 and t052_delta < 0
    return {
        "status": "supported" if supported else "not_observed",
        "reason": (
            "T048 retained cohorts are positive while T052 later-act/Boss "
            "diagnostic is negative for existing root-prior versus baseline"
            if supported
            else "aggregate retained cohorts do not show a positive-vs-negative split"
        ),
        "t048_root_prior_vs_baseline_win_delta": t048_delta,
        "t052_root_prior_vs_baseline_win_delta": t052_delta,
        "evidence_families": [
            "t048_positive_fixed_cohort_signal",
            "t052_t053_later_act_boss_diagnostic",
        ],
    }


def _aggregate_group_outcomes(
    cohort_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    labels = (
        BASELINE_ORACLE_LABEL,
        POST_SEARCH_MODEL_GUIDED_LABEL,
        ROOT_PRIOR_GUIDED_LABEL,
    )
    totals = {
        label: {
            "record_count": 0,
            "authoritative_wins": 0,
            "losses": 0,
            "truncations": 0,
            "errors": 0,
        }
        for label in labels
    }
    for summary in cohort_summaries:
        outcomes = _mapping(summary.get("arm_outcomes"))
        for label in labels:
            item = _mapping(outcomes.get(label))
            for key in totals[label]:
                totals[label][key] += _as_int(item.get(key))
    return {
        "arm_outcomes": totals,
        "root_prior_vs_baseline": _win_delta(
            totals[ROOT_PRIOR_GUIDED_LABEL],
            totals[BASELINE_ORACLE_LABEL],
        ),
        "root_prior_vs_post_search": _win_delta(
            totals[ROOT_PRIOR_GUIDED_LABEL],
            totals[POST_SEARCH_MODEL_GUIDED_LABEL],
        ),
        "metric": "authoritative_win_count",
    }


def _aggregate_win_delta(
    records: Sequence[Mapping[str, Any]],
    *,
    left_label: str,
    right_label: str,
) -> dict[str, Any]:
    left = _arm_outcomes_for_records(records, left_label)
    right = _arm_outcomes_for_records(records, right_label)
    return _win_delta(left, right)


def _win_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_wins = _as_int(left.get("authoritative_wins"))
    right_wins = _as_int(right.get("authoritative_wins"))
    delta = left_wins - right_wins
    return {
        "status": "improved" if delta > 0 else "regressed" if delta < 0 else "tied",
        "win_delta": delta,
        "left_wins": left_wins,
        "right_wins": right_wins,
    }


def _outcome_counts(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(results)
    status_counts = Counter(
        str(_mapping(result).get("termination_status")) for result in values
    )
    return {
        "record_count": len(values),
        "authoritative_wins": status_counts.get("win", 0),
        "losses": status_counts.get("loss", 0),
        "truncations": status_counts.get("truncated", 0),
        "errors": status_counts.get("error", 0),
    }


def _arm_outcomes_for_records(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, int]:
    status_counts = Counter()
    for record in records:
        arm = _mapping(_mapping(record.get("arms")).get(label))
        status_counts[str(arm.get("termination_status") or MISSING_VALUE)] += 1
    return {
        "record_count": len(records),
        "authoritative_wins": status_counts.get("win", 0),
        "losses": status_counts.get("loss", 0),
        "truncations": status_counts.get("truncated", 0),
        "errors": status_counts.get("error", 0),
        "missing": status_counts.get(MISSING_VALUE, 0),
    }


def _t052_counts(value: Any) -> dict[str, Any]:
    section = _mapping(value)
    return {
        label: {
            "battle_count": _as_int(_mapping(section.get(label)).get("battle_count")),
            "win_count": _as_int(_mapping(section.get(label)).get("win_count")),
            "loss_count": _as_int(_mapping(section.get(label)).get("loss_count")),
            "truncated_count": _as_int(
                _mapping(section.get(label)).get("truncated_count")
            ),
            "error_count": _as_int(_mapping(section.get(label)).get("error_count")),
            "win_rate": _mapping(section.get(label)).get("win_rate"),
        }
        for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
        if isinstance(section.get(label), Mapping)
    }


def _checkpoint_provenance_by_label(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    output = {}
    for arm in _sequence(metadata.get("controller_arms")):
        mapping = _mapping(arm)
        label = str(mapping.get("label") or MISSING_VALUE)
        report = _mapping(mapping.get("report_metadata"))
        controller = _mapping(report.get("controller_provenance"))
        config = _mapping(controller.get("config"))
        guidance = _mapping(config.get("guidance_scorer"))
        checkpoint = _mapping(guidance.get("checkpoint_provenance"))
        if checkpoint:
            output[label] = _json_safe_mapping(checkpoint)
    return output


def _arm_information_regime(metadata: Mapping[str, Any], label: str) -> str | None:
    for arm in _sequence(metadata.get("controller_arms")):
        mapping = _mapping(arm)
        if mapping.get("label") != label:
            continue
        report = _mapping(mapping.get("report_metadata"))
        value = report.get("information_regime")
        return str(value) if value else None
    return None


def _controller_labels(metadata: Mapping[str, Any]) -> list[str]:
    return [
        str(_mapping(arm).get("label") or "")
        for arm in _sequence(metadata.get("controller_arms"))
        if isinstance(arm, Mapping)
    ]


def _root_prior_decision_reports(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    return _flatten_mappings(telemetry.get("root_prior_guided_decision_reports"))


def _row_for_selected_index(
    rows: Sequence[Mapping[str, Any]],
    selected: int | None,
) -> dict[str, Any]:
    if selected is None:
        return {}
    for row in rows:
        if _optional_int(row.get("legal_action_index")) == selected:
            return dict(row)
    target_label = None
    for row in rows:
        if _optional_int(row.get("search_edge_index")) == selected:
            return dict(row)
        if target_label is None and _optional_int(row.get("idx1")) == selected:
            target_label = dict(row)
    return target_label or {}


def _action_bucket(row: Mapping[str, Any]) -> str:
    kind = str(row.get("kind") or MISSING_VALUE)
    label = str(row.get("label") or "")
    if kind != MISSING_VALUE:
        return kind
    if "end turn" in label.lower():
        return "end_turn"
    return MISSING_VALUE


def _first_action_difference(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    count = min(len(left), len(right))
    for index in range(count):
        if _action_identity_key(left[index]) != _action_identity_key(right[index]):
            return {
                "decision_index": index,
                "left": _json_safe_mapping(left[index]),
                "right": _json_safe_mapping(right[index]),
            }
    if len(left) != len(right):
        return {
            "decision_index": count,
            "left": "missing"
            if count >= len(left)
            else _json_safe_mapping(left[count]),
            "right": (
                "missing" if count >= len(right) else _json_safe_mapping(right[count])
            ),
        }
    return {}


def _matching_action_count(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> int:
    count = min(len(left), len(right))
    return sum(
        1
        for index in range(count)
        if _action_identity_key(left[index]) == _action_identity_key(right[index])
    )


def _action_identity_key(action: Mapping[str, Any]) -> str:
    identity = _mapping(action.get("action_identity"))
    if identity:
        return json.dumps(_json_safe_mapping(identity), sort_keys=True)
    return json.dumps(_json_safe_mapping(action), sort_keys=True)


def _outcome_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_win = left.get("termination_status") == "win"
    right_win = right.get("termination_status") == "win"
    left_hp = _optional_int(left.get("terminal_absolute_hp"))
    right_hp = _optional_int(right.get("terminal_absolute_hp"))
    return {
        "termination_status_delta": _status_delta(left_win, right_win),
        "terminal_absolute_hp_delta": (
            None if left_hp is None or right_hp is None else left_hp - right_hp
        ),
        "left_outcome": {
            "termination_status": left.get("termination_status"),
            "terminal_absolute_hp": left_hp,
        },
        "right_outcome": {
            "termination_status": right.get("termination_status"),
            "terminal_absolute_hp": right_hp,
        },
    }


def _outcome_signature(arm: Mapping[str, Any]) -> tuple[Any, Any]:
    return arm.get("termination_status"), arm.get("terminal_absolute_hp")


def _same_win_status(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return (left.get("termination_status") == "win") == (
        right.get("termination_status") == "win"
    )


def _is_harmful(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return (
        left.get("termination_status") != "win"
        and right.get("termination_status") == "win"
    )


def _status_delta(left_win: bool, right_win: bool) -> str:
    if left_win and not right_win:
        return "improved"
    if not left_win and right_win:
        return "regressed"
    return "same"


def _restore_status(result: Mapping[str, Any]) -> str:
    if not result:
        return "missing"
    if result.get("termination_status") == "error":
        return "error"
    if result.get("restoration_method"):
        return "restored"
    return "unavailable"


def _telemetry_total(summary: Mapping[str, Any], key: str) -> int | float | None:
    metric = _mapping(summary.get(key))
    value = metric.get("total")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _flatten_mappings(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        rows.append({str(key): item for key, item in value.items()})
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            rows.extend(_flatten_mappings(item))
    return rows


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    return [_mapping(item) for item in _sequence(value) if isinstance(item, Mapping)]


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _mapping(value: Any) -> dict[str, Any]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, Mapping)
        else {}
    )


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _sequence(value)]


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_int(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _optional_float_value(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    return parsed


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _counter_dict(counter: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter, key=str)}


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
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
    return [_require_mapping(item, f"{label} item") for item in value]


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


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


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
