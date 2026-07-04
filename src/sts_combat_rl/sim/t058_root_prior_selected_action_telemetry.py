"""T058 selected-action telemetry replay diagnostic.

This report consumes retained T057 evidence plus newly instrumented
root-prior comparison artifacts. It does not run a simulator, train a
checkpoint, tune allocation, promote a controller, or make natural A20 claims.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
    ROOT_PRIOR_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
)
from sts_combat_rl.sim.t057_existing_root_prior_telemetry_diagnostic import (
    T057ComparisonInput,
    T057ExistingRootPriorTelemetryDiagnosticReport,
    T057_SELECTED_NEXT_TASK,
    T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID,
    load_t057_root_prior_comparison_inputs,
)


T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID = (
    "t058-root-prior-selected-action-telemetry-diagnostic-report-v1"
)
T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION = 1
T058_REQUIRED_INPUT_ROLES = (
    "t057_telemetry_diagnostic_report",
    "t048_current_fixed_cohort",
    "t048_assist0_fixed_cohort",
    "t052_boss_later_act_fixed_cohort",
    "t043_assist0_smoke_checkpoint",
    "t043_runs1000_assist0_checkpoint",
    "t048_current_replay_comparison",
    "t048_assist0_replay_comparison",
    "t052_replay_comparison",
)
T058_COMPARISON_ROLES = (
    "t048_current_replay_comparison",
    "t048_assist0_replay_comparison",
    "t052_replay_comparison",
)
T058_COMPARISON_CONTRACTS: dict[str, dict[str, Any]] = {
    "t048_current_replay_comparison": {
        "cohort_label": "t048_current_t046_compatible",
        "evidence_family": "t048_positive_fixed_cohort_signal",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "cohort_role": "t048_current_fixed_cohort",
        "checkpoint_role": "t043_assist0_smoke_checkpoint",
        "required_worker_count": 8,
        "required_shard_count": 8,
    },
    "t048_assist0_replay_comparison": {
        "cohort_label": "t048_assist0_runs1000",
        "evidence_family": "t048_positive_fixed_cohort_signal",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "cohort_role": "t048_assist0_fixed_cohort",
        "checkpoint_role": "t043_runs1000_assist0_checkpoint",
        "required_worker_count": 16,
        "required_shard_count": 16,
    },
    "t052_replay_comparison": {
        "cohort_label": "t052_boss_later_act_diagnostic",
        "evidence_family": "t052_t053_later_act_boss_diagnostic",
        "cohort_identity": "68d0e5b10ebcb05d",
        "record_count": 93,
        "record_range": "0:93",
        "cohort_role": "t052_boss_later_act_fixed_cohort",
        "checkpoint_role": "t043_assist0_smoke_checkpoint",
        "required_worker_count": 16,
        "required_shard_count": 16,
    },
}
T058_ALLOWED_NEXT_PATHS = (
    "existing-root-prior complete-run reachability probe",
    "another fixed-cohort diagnostic",
    "root-prior allocation repair experiment",
    "assisted/de-assisted checkpoint, teacher, or distribution-repair diagnostic",
    "source-generation, reachability, or non-combat-driver branch",
    "publish a blocked path requiring maintainer decision",
)
T058_EVIDENCE_BOUNDARY = {
    "task_id": "T058",
    "scope": "selected-action telemetry replay diagnostic",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_controller_tuning": True,
    "not_guardrail_revival": True,
    "not_controller_promotion": True,
    "not_complete_run_reachability_evidence": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class T058RootPriorSelectedActionTelemetryReport:
    """Versioned T058 selected-action diagnostic report."""

    input_artifacts: list[dict[str, Any]]
    prerequisite_summary: dict[str, Any]
    cohort_summaries: dict[str, Any]
    subset_summaries: dict[str, Any]
    per_record_selected_action_diagnostics: list[dict[str, Any]]
    selected_action_availability: dict[str, Any]
    first_divergence_summary: dict[str, Any]
    recommendation: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID
    format_version: int = T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T058_EVIDENCE_BOUNDARY)
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
            "cohort_summaries": _json_safe_value(self.cohort_summaries),
            "subset_summaries": _json_safe_value(self.subset_summaries),
            "per_record_selected_action_diagnostics": _json_safe_value(
                self.per_record_selected_action_diagnostics
            ),
            "selected_action_availability": _json_safe_value(
                self.selected_action_availability
            ),
            "first_divergence_summary": _json_safe_value(self.first_divergence_summary),
            "recommendation": _json_safe_value(self.recommendation),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def load_t058_root_prior_comparison_inputs(
    stream: TextIO,
    *,
    role: str,
) -> T057ComparisonInput:
    """Load one instrumented root-prior comparison for T058."""

    return load_t057_root_prior_comparison_inputs(stream, role=role)


def build_t058_root_prior_selected_action_telemetry_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t057_report: T057ExistingRootPriorTelemetryDiagnosticReport,
    comparisons: Mapping[str, T057ComparisonInput],
) -> T058RootPriorSelectedActionTelemetryReport:
    """Build the offline T058 selected-action replay diagnostic."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        t057_report=t057_report,
        comparisons=comparisons,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    records = _existing_root_prior_records(comparisons)
    availability = _selected_action_availability(records)
    cohort_summaries = _cohort_summaries(records, comparisons)
    subset_summaries = _subset_summaries(records, t057_report=t057_report)
    first_divergence = _first_divergence_summary(records)
    unavailable = _unavailable_diagnostics(availability)
    recommendation = _recommendation(
        records=records,
        selected_action_availability=availability,
        first_divergence_summary=first_divergence,
    )
    return T058RootPriorSelectedActionTelemetryReport(
        input_artifacts=artifacts,
        prerequisite_summary=_prerequisite_summary(t057_report, availability),
        cohort_summaries=cohort_summaries,
        subset_summaries=subset_summaries,
        per_record_selected_action_diagnostics=records,
        selected_action_availability=availability,
        first_divergence_summary=first_divergence,
        recommendation=recommendation,
        unavailable_diagnostics=unavailable,
    )


def dump_t058_root_prior_selected_action_telemetry_report_json(
    report: T058RootPriorSelectedActionTelemetryReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T058 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t058_root_prior_selected_action_telemetry_report_json(
    stream: TextIO,
) -> T058RootPriorSelectedActionTelemetryReport:
    """Load and validate a T058 report JSON artifact."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T058 selected-action telemetry report JSON") from exc
    return t058_root_prior_selected_action_telemetry_report_from_dict(raw)


def t058_root_prior_selected_action_telemetry_report_from_dict(
    raw: Mapping[str, Any],
) -> T058RootPriorSelectedActionTelemetryReport:
    """Validate a current-schema T058 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T058 selected-action telemetry report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID:
        raise ValueError(
            f"unsupported T058 selected-action telemetry schema_id {schema_id!r}; "
            f"expected {T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION:
        raise ValueError(
            "unsupported T058 selected-action telemetry format_version "
            f"{format_version!r}; expected "
            f"{T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION}"
        )
    return T058RootPriorSelectedActionTelemetryReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        prerequisite_summary=_require_mapping(
            raw.get("prerequisite_summary"),
            "prerequisite_summary",
        ),
        cohort_summaries=_require_mapping(
            raw.get("cohort_summaries"),
            "cohort_summaries",
        ),
        subset_summaries=_require_mapping(
            raw.get("subset_summaries"),
            "subset_summaries",
        ),
        per_record_selected_action_diagnostics=_require_list_of_mappings(
            raw.get("per_record_selected_action_diagnostics"),
            "per_record_selected_action_diagnostics",
        ),
        selected_action_availability=_require_mapping(
            raw.get("selected_action_availability"),
            "selected_action_availability",
        ),
        first_divergence_summary=_require_mapping(
            raw.get("first_divergence_summary"),
            "first_divergence_summary",
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
            raw.get("evidence_boundary", T058_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t058_root_prior_selected_action_telemetry_report(
    report: T058RootPriorSelectedActionTelemetryReport,
) -> str:
    """Format concise T058 diagnostics for stderr and PR summaries."""

    prereq = report.prerequisite_summary
    availability = report.selected_action_availability
    recommendation = report.recommendation
    lines = [
        "T058 root-prior selected-action telemetry replay diagnostic",
        (
            "scope: retained fixed-cohort replay diagnostic only; no controller "
            "tuning, guardrail revival, complete-run reachability evidence, "
            "controller promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "T057 selected-action availability before T058: "
            f"{prereq.get('t057_available_record_count', 0)} available / "
            f"{prereq.get('t057_unavailable_record_count', 0)} unavailable"
        ),
        (
            "T058 selected-action availability: "
            f"{availability.get('available_record_count', 0)} available / "
            f"{availability.get('unavailable_record_count', 0)} unavailable; "
            f"exact full-path records: {availability.get('exact_full_record_count', 0)}"
        ),
        (
            "exact all-arm comparison feasible for every retained record: "
            + _yes_no(
                bool(availability.get("exact_step_level_comparison_feasible_all"))
            )
        ),
        (
            "first divergence vs baseline records: "
            f"{report.first_divergence_summary.get('root_prior_vs_baseline', {}).get('record_count_with_divergence', 0)}"
        ),
        (
            "first divergence vs post-search records: "
            f"{report.first_divergence_summary.get('root_prior_vs_post_search', {}).get('record_count_with_divergence', 0)}"
        ),
        (
            "selected next path: "
            + str(recommendation.get("selected_next_path", MISSING_VALUE))
        ),
        "cohorts:",
    ]
    for label, summary in sorted(report.cohort_summaries.items()):
        action = _mapping(summary.get("selected_action_availability"))
        lines.append(
            "  "
            f"{label}: records={summary.get('record_count')} "
            f"available={action.get('available_record_count', 0)} "
            f"unavailable={action.get('unavailable_record_count', 0)}"
        )
    lines.append("subset summaries:")
    for label, summary in sorted(report.subset_summaries.items()):
        action = _mapping(summary.get("selected_action_availability"))
        lines.append(
            "  "
            f"{label}: records={summary.get('record_count')} "
            f"exact={action.get('exact_full_record_count', 0)} "
            f"unavailable={action.get('unavailable_record_count', 0)}"
        )
    lines.append("unavailable diagnostics:")
    if report.unavailable_diagnostics:
        lines.extend(
            "  - "
            + str(item.get("diagnostic", MISSING_VALUE))
            + ": "
            + str(item.get("reason", MISSING_VALUE))
            for item in report.unavailable_diagnostics
        )
    else:
        lines.append("  (none)")
    if report.validation_problems:
        lines.append("validation problems:")
        lines.extend(f"  - {problem}" for problem in report.validation_problems)
    return "\n".join(lines)


def _validation_problems(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t057_report: T057ExistingRootPriorTelemetryDiagnosticReport,
    comparisons: Mapping[str, T057ComparisonInput],
) -> list[str]:
    problems: list[str] = []
    roles = [str(artifact.get("role") or "") for artifact in input_artifacts]
    if sorted(roles) != sorted(T058_REQUIRED_INPUT_ROLES):
        problems.append(
            "T058 input artifact roles must match "
            + ", ".join(T058_REQUIRED_INPUT_ROLES)
        )
    if len(set(roles)) != len(roles):
        problems.append("duplicate T058 input artifact roles")
    if t057_report.schema_id != T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID:
        problems.append("T057 report schema mismatch")
    if not t057_report.command_passed:
        problems.append("T057 report command did not pass")
    t057_next = t057_report.recommendation.get("selected_next_path")
    if t057_next != T057_SELECTED_NEXT_TASK:
        problems.append("T057 selected next path does not authorize T058")
    t057_availability = _mapping(t057_report.selected_action_availability)
    if _as_int(t057_availability.get("record_count")) != 122:
        problems.append("T057 selected-action baseline must cover 122 records")
    for role in T058_COMPARISON_ROLES:
        comparison = comparisons.get(role)
        if comparison is None:
            problems.append(f"missing T058 comparison input {role}")
            continue
        problems.extend(_comparison_validation_problems(role, comparison))
    return list(dict.fromkeys(problems))


def _comparison_validation_problems(
    role: str,
    comparison: T057ComparisonInput,
) -> list[str]:
    contract = T058_COMPARISON_CONTRACTS[role]
    metadata = comparison.metadata
    config = _mapping(metadata.get("comparison_config"))
    problems: list[str] = []
    if metadata.get("schema_id") != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID:
        problems.append(f"{role}: unsupported comparison schema")
    if (
        metadata.get("format_version")
        != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION
    ):
        problems.append(f"{role}: unsupported comparison format version")
    if config.get("task_id") != "T058":
        problems.append(f"{role}: comparison task_id must be 'T058'")
    if metadata.get("cohort_identity") != contract["cohort_identity"]:
        problems.append(f"{role}: cohort identity mismatch")
    if _as_int(metadata.get("battle_comparison_count")) != int(
        contract["record_count"]
    ):
        problems.append(f"{role}: battle_comparison_count mismatch")
    if metadata.get("source_match_status") != "matched":
        problems.append(f"{role}: source_match_status must be matched")
    if metadata.get("evaluation_successful") is not True:
        problems.append(f"{role}: evaluation_successful must be true")
    for key in (
        "source_match_problems",
        "report_problems",
        "validation_problems",
        "problems",
    ):
        values = metadata.get(key)
        if not isinstance(values, list):
            problems.append(f"{role}: metadata {key} must be a list")
        elif values:
            problems.append(f"{role}: metadata {key} must be empty")
    if not _record_range_matches(config, str(contract["record_range"])):
        problems.append(f"{role}: record_range mismatch")
    if _as_int(config.get("worker_count")) != contract["required_worker_count"]:
        problems.append(f"{role}: worker_count mismatch")
    if _as_int(config.get("shard_count")) != contract["required_shard_count"]:
        problems.append(f"{role}: shard_count mismatch")
    expected = int(contract["record_count"])
    if len(comparison.battle_comparisons) != expected:
        problems.append(f"{role}: battle comparison count mismatch")
    labels = set(_controller_labels(metadata))
    missing_labels = sorted(set(REQUIRED_ROOT_PRIOR_COMPARISON_LABELS) - labels)
    if missing_labels:
        problems.append(f"{role}: missing required arms {', '.join(missing_labels)}")
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        regime = _arm_information_regime(metadata, label)
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{role}:{label}: information regime {regime!r} is not "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
        rows = comparison.results_by_label.get(label, {})
        missing_indices = [index for index in range(expected) if index not in rows]
        if missing_indices:
            problems.append(
                f"{role}:{label}: missing controller_result indices "
                + ", ".join(str(index) for index in missing_indices[:10])
            )
    for row in comparison.battle_comparisons:
        index = _optional_int(row.get("comparison_index"))
        label = f"{role}:battle_comparison[{index if index is not None else '?'}]"
        if row.get("source_match") is not True:
            problems.append(f"{label}: source_match must be true")
        row_problems = row.get("problems")
        if not isinstance(row_problems, list):
            problems.append(f"{label}: problems must be a list")
        elif row_problems:
            problems.append(f"{label}: problems must be empty")
    return problems


def _record_range_matches(config: Mapping[str, Any], expected: str) -> bool:
    if config.get("record_range") == expected:
        return True
    merged = [str(item) for item in _sequence(config.get("merged_from_record_ranges"))]
    if not merged:
        return False
    return _range_coverage(merged) == _range_coverage([expected])


def _range_coverage(values: Sequence[str]) -> list[int]:
    indices: list[int] = []
    for value in values:
        parts = value.split(":", 1)
        if len(parts) != 2:
            return []
        start = _optional_int_from_string(parts[0])
        end = _optional_int_from_string(parts[1])
        if start is None or end is None or end < start:
            return []
        indices.extend(range(start, end))
    return sorted(indices)


def _existing_root_prior_records(
    comparisons: Mapping[str, T057ComparisonInput],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for role in T058_COMPARISON_ROLES:
        comparison = comparisons[role]
        contract = T058_COMPARISON_CONTRACTS[role]
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
        root = _mapping(arms.get(ROOT_PRIOR_GUIDED_LABEL))
        baseline = _mapping(arms.get(BASELINE_ORACLE_LABEL))
        post = _mapping(arms.get(POST_SEARCH_MODEL_GUIDED_LABEL))
        source = _source_identity(
            comparison=row,
            preferred_result=root or baseline or post,
        )
        action_comparison = _selected_action_comparison(arms)
        outcome = _record_outcome_delta(root=root, baseline=baseline, post=post)
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
                "root_prior_allocation": _json_safe_mapping(
                    _mapping(root.get("root_prior_allocation"))
                ),
                "selected_action_comparison": action_comparison,
            }
        )
    return records


def _cohort_summaries(
    records: Sequence[Mapping[str, Any]],
    comparisons: Mapping[str, T057ComparisonInput],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    by_label = _records_by(records, "cohort_label")
    for role in T058_COMPARISON_ROLES:
        contract = T058_COMPARISON_CONTRACTS[role]
        label = str(contract["cohort_label"])
        group = by_label.get(label, [])
        config = _mapping(comparisons[role].metadata.get("comparison_config"))
        output[label] = {
            "role": role,
            "task_id": config.get("task_id"),
            "evidence_family": contract["evidence_family"],
            "cohort_identity": comparisons[role].metadata.get("cohort_identity"),
            "record_count": len(group),
            "record_range": config.get("record_range"),
            "worker_count": config.get("worker_count"),
            "shard_count": config.get("shard_count"),
            "cohort_input_role": contract["cohort_role"],
            "checkpoint_input_role": contract["checkpoint_role"],
            "arm_outcomes": {
                arm: _arm_outcomes_for_records(group, arm)
                for arm in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
            },
            "selected_action_availability": _selected_action_availability(group),
            "first_divergence_summary": _first_divergence_summary(group),
        }
    return output


def _subset_summaries(
    records: Sequence[Mapping[str, Any]],
    *,
    t057_report: T057ExistingRootPriorTelemetryDiagnosticReport,
) -> dict[str, Any]:
    t053_indices = {
        _optional_int(index)
        for index in _sequence(
            _mapping(t057_report.subset_summaries.get("t053_disagreement_records")).get(
                "cohort_indices"
            )
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
        label: _record_group_summary(
            [record for record in records if predicate(record)],
            group_label=label,
        )
        for label, predicate in specs.items()
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
            arm: _arm_outcomes_for_records(records, arm)
            for arm in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
        },
        "selected_action_availability": _selected_action_availability(records),
        "first_divergence_summary": _first_divergence_summary(records),
        "root_prior_vs_baseline": _aggregate_outcome_delta(
            records,
            left_label=ROOT_PRIOR_GUIDED_LABEL,
            right_label=BASELINE_ORACLE_LABEL,
        ),
        "root_prior_vs_post_search": _aggregate_outcome_delta(
            records,
            left_label=ROOT_PRIOR_GUIDED_LABEL,
            right_label=POST_SEARCH_MODEL_GUIDED_LABEL,
        ),
    }


def _selected_action_comparison(
    arms: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    action_lists = {
        label: [
            _action_public_summary(index, action)
            for index, action in enumerate(
                _list_of_mappings(_mapping(arms.get(label)).get("selected_actions"))
            )
        ]
        for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
    }
    missing: list[dict[str, Any]] = []
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        arm = _mapping(arms.get(label))
        actions = action_lists[label]
        reason = arm.get("selected_action_missing_reason")
        if reason is not None:
            missing.append(_missing_action_field(label, str(reason)))
        elif not actions:
            missing.append(
                _missing_action_field(label, "selected action identity unavailable")
            )
        else:
            missing.extend(
                _missing_action_field(
                    label,
                    "selected action identity unavailable",
                    decision_index=_optional_int(action.get("decision_index")),
                )
                for action in actions
                if not _mapping(action.get("action_identity"))
            )
    if missing:
        return {
            "status": "unavailable",
            "reason": "; ".join(f"{item['arm']}:{item['reason']}" for item in missing),
            "missing_fields": missing,
            "exact_step_level_matching": False,
            "exact_full_battle_path_comparison": False,
            **_first_action_samples(action_lists),
        }
    root_actions = action_lists[ROOT_PRIOR_GUIDED_LABEL]
    baseline_actions = action_lists[BASELINE_ORACLE_LABEL]
    post_actions = action_lists[POST_SEARCH_MODEL_GUIDED_LABEL]
    comparable_count = min(len(root_actions), len(baseline_actions), len(post_actions))
    full_path = comparable_count > 0 and len(root_actions) == len(
        baseline_actions
    ) == len(post_actions)
    return {
        "status": "available",
        "exact_step_level_matching": True,
        "exact_full_battle_path_comparison": full_path,
        "comparable_decision_count": comparable_count,
        **_first_action_samples(action_lists),
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


def _selected_action_availability(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter()
    missing_counts = Counter()
    available = 0
    exact_full = 0
    partial = 0
    unavailable_records: list[dict[str, Any]] = []
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
            continue
        cohort = str(record.get("cohort_label") or MISSING_VALUE)
        index = _as_int(record.get("cohort_index"))
        affected.setdefault(cohort, []).append(index)
        missing_fields = _list_of_mappings(diagnostic.get("missing_fields"))
        for item in missing_fields:
            key = f"{item.get('arm', MISSING_VALUE)}:{item.get('field', MISSING_VALUE)}"
            missing_counts[key] += 1
        unavailable_records.append(
            {
                "cohort_label": cohort,
                "cohort_index": index,
                "missing_fields": missing_fields,
            }
        )
    return {
        "record_count": len(records),
        "available_record_count": available,
        "partial_record_count": partial,
        "exact_full_record_count": exact_full,
        "unavailable_record_count": len(records) - available,
        "status_counts": _counter_dict(status_counts),
        "missing_field_or_reason_counts": _counter_dict(missing_counts),
        "affected_cohorts": {
            key: sorted(set(value))[:200] for key, value in sorted(affected.items())
        },
        "unavailable_records": unavailable_records[:200],
        "exact_step_level_comparison_feasible_all": (
            bool(records) and available == len(records)
        ),
        "exact_full_battle_path_comparison_all": (
            bool(records) and exact_full == len(records)
        ),
    }


def _first_divergence_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "root_prior_vs_baseline": _divergence_side_summary(
            records,
            field_name="first_difference_vs_baseline",
        ),
        "root_prior_vs_post_search": _divergence_side_summary(
            records,
            field_name="first_difference_vs_post_search",
        ),
    }


def _divergence_side_summary(
    records: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
) -> dict[str, Any]:
    samples = []
    count = 0
    for record in records:
        comparison = _mapping(record.get("selected_action_comparison"))
        diff = _mapping(comparison.get(field_name))
        if not diff:
            continue
        count += 1
        if len(samples) < 20:
            samples.append(
                {
                    "cohort_label": record.get("cohort_label"),
                    "cohort_index": record.get("cohort_index"),
                    "decision_index": diff.get("decision_index"),
                    "left": _json_safe_value(diff.get("left")),
                    "right": _json_safe_value(diff.get("right")),
                    "outcome_delta": _json_safe_mapping(
                        _mapping(record.get("outcome_delta"))
                    ),
                }
            )
    return {
        "record_count": len(records),
        "record_count_with_divergence": count,
        "record_count_without_divergence": len(records) - count,
        "samples": samples,
    }


def _prerequisite_summary(
    t057_report: T057ExistingRootPriorTelemetryDiagnosticReport,
    availability: Mapping[str, Any],
) -> dict[str, Any]:
    before = _mapping(t057_report.selected_action_availability)
    return {
        "t057_schema_id": t057_report.schema_id,
        "t057_command_passed": t057_report.command_passed,
        "t057_selected_next_path": t057_report.recommendation.get("selected_next_path"),
        "t057_record_count": before.get("record_count"),
        "t057_available_record_count": before.get("available_record_count"),
        "t057_unavailable_record_count": before.get("unavailable_record_count"),
        "t057_exact_full_record_count": before.get("exact_full_record_count"),
        "t058_record_count": availability.get("record_count"),
        "t058_available_record_count": availability.get("available_record_count"),
        "t058_unavailable_record_count": availability.get("unavailable_record_count"),
        "selected_action_available_record_delta": (
            _as_int(availability.get("available_record_count"))
            - _as_int(before.get("available_record_count"))
        ),
        "selected_action_unavailable_record_delta": (
            _as_int(availability.get("unavailable_record_count"))
            - _as_int(before.get("unavailable_record_count"))
        ),
    }


def _recommendation(
    *,
    records: Sequence[Mapping[str, Any]],
    selected_action_availability: Mapping[str, Any],
    first_divergence_summary: Mapping[str, Any],
) -> dict[str, Any]:
    unavailable = _as_int(selected_action_availability.get("unavailable_record_count"))
    if unavailable:
        selected = "publish a blocked path requiring maintainer decision"
        reason = (
            "one or more retained records still lack exact all-arm "
            "selected-action identity comparison, so T058 must fail closed "
            "instead of recommending reachability or promotion-adjacent work"
        )
    else:
        harmful_with_divergence = _harmful_divergence_count(records)
        if harmful_with_divergence:
            selected = "root-prior allocation repair experiment"
            reason = (
                "selected-action telemetry is now auditable and includes "
                "root-prior harmful outcome deltas with selected-action "
                "divergence, so the next bounded path is allocation repair"
            )
        elif _as_int(
            _mapping(first_divergence_summary.get("root_prior_vs_baseline")).get(
                "record_count_with_divergence"
            )
        ):
            selected = "another fixed-cohort diagnostic"
            reason = (
                "selected-action telemetry is auditable, but the retained "
                "records do not isolate a harmful repair target strongly enough "
                "for reachability"
            )
        else:
            selected = "existing-root-prior complete-run reachability probe"
            reason = (
                "selected-action telemetry is auditable for all retained records "
                "and no harmful selected-action divergence remains in this "
                "diagnostic"
            )
    return {
        "recommendation_count": 1,
        "selected_next_path": selected,
        "recommended_next_task": selected,
        "allowed_recommendation_set": list(T058_ALLOWED_NEXT_PATHS),
        "reason": reason,
        "evidence_support": {
            "selected_action_unavailable_record_count": unavailable,
            "exact_step_level_comparison_feasible_all_records": bool(
                selected_action_availability.get(
                    "exact_step_level_comparison_feasible_all"
                )
            ),
            "harmful_selected_action_divergence_count": _harmful_divergence_count(
                records
            ),
        },
        "forbidden_claims": {
            "controller_promotion": False,
            "root_prior_complete_run_reachability": False,
            "live_game_strength": False,
            "natural_a20_performance": False,
            "broad_training_readiness": False,
            "normal_information_strength": False,
            "final_agent_status": False,
        },
    }


def _unavailable_diagnostics(
    selected_action_availability: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
                "unavailable_records": _json_safe_value(
                    selected_action_availability.get("unavailable_records", [])
                ),
            }
        )
    rows.append(
        {
            "diagnostic": "allocation_causal_counterfactual",
            "reason": (
                "selected-action telemetry makes chosen-action divergence "
                "auditable but does not expose paired within-decision native "
                "counterfactual search trees"
            ),
        }
    )
    return rows


def _harmful_divergence_count(records: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for record in records:
        outcome = _mapping(record.get("outcome_delta"))
        harmful = (
            _mapping(outcome.get("root_prior_vs_baseline")).get(
                "termination_status_delta"
            )
            == "regressed"
            or _mapping(outcome.get("root_prior_vs_post_search")).get(
                "termination_status_delta"
            )
            == "regressed"
        )
        comparison = _mapping(record.get("selected_action_comparison"))
        diverged = bool(comparison.get("first_difference_vs_baseline")) or bool(
            comparison.get("first_difference_vs_post_search")
        )
        if harmful and diverged:
            count += 1
    return count


def _action_public_summary(
    decision_index: int,
    action: Mapping[str, Any],
) -> dict[str, Any]:
    identity = _mapping(action.get("action_identity"))
    return {
        "decision_index": decision_index,
        "selected_index": action.get("selected_index"),
        "selected_legal_action_index": action.get("selected_legal_action_index"),
        "action_identity": _json_safe_mapping(identity),
        "action_kind": identity.get("kind") or action.get("action_kind"),
        "action_label": identity.get("label") or action.get("action_label"),
        "selection_rule": action.get("selection_rule"),
        "visits": action.get("visits") or action.get("selected_visits"),
        "mean_value": action.get("mean_value") or action.get("selected_mean_value"),
        "score": action.get("score"),
    }


def _missing_action_field(
    arm: str,
    reason: str,
    *,
    decision_index: int | None = None,
) -> dict[str, Any]:
    if arm == ROOT_PRIOR_GUIDED_LABEL:
        field = (
            "controller_compute_telemetry.root_prior_guided_decision_reports"
            "[].target.action_identity"
        )
    else:
        field = (
            "controller_compute_telemetry.oracle_search_decision_reports"
            "[].selected_action_identity"
        )
    return {
        "arm": arm,
        "field": field,
        "decision_index": decision_index,
        "reason": reason,
    }


def _first_action_samples(
    action_lists: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    return {
        "root_prior_decision_count": len(action_lists.get(ROOT_PRIOR_GUIDED_LABEL, [])),
        "baseline_decision_count": len(action_lists.get(BASELINE_ORACLE_LABEL, [])),
        "post_search_decision_count": len(
            action_lists.get(POST_SEARCH_MODEL_GUIDED_LABEL, [])
        ),
        "root_prior_first_actions": _json_safe_value(
            list(action_lists.get(ROOT_PRIOR_GUIDED_LABEL, []))[:5]
        ),
        "baseline_first_actions": _json_safe_value(
            list(action_lists.get(BASELINE_ORACLE_LABEL, []))[:5]
        ),
        "post_search_first_actions": _json_safe_value(
            list(action_lists.get(POST_SEARCH_MODEL_GUIDED_LABEL, []))[:5]
        ),
    }


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
    if not identity:
        return ""
    return json.dumps(_json_safe_mapping(identity), sort_keys=True)


def _arm_public_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _json_safe_value(result.get(key))
        for key in (
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
            "selected_actions",
            "selected_action_missing_reason",
        )
    }


def _record_outcome_delta(
    *,
    root: Mapping[str, Any],
    baseline: Mapping[str, Any],
    post: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "root_prior_vs_baseline": _outcome_delta(root, baseline),
        "root_prior_vs_post_search": _outcome_delta(root, post),
        "all_outcomes_identical": (
            _outcome_signature(root)
            == _outcome_signature(baseline)
            == _outcome_signature(post)
        ),
    }


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


def _status_delta(left_win: bool, right_win: bool) -> str:
    if left_win and not right_win:
        return "improved"
    if not left_win and right_win:
        return "regressed"
    return "same"


def _outcome_signature(arm: Mapping[str, Any]) -> tuple[Any, Any]:
    return arm.get("termination_status"), arm.get("terminal_absolute_hp")


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


def _aggregate_outcome_delta(
    records: Sequence[Mapping[str, Any]],
    *,
    left_label: str,
    right_label: str,
) -> dict[str, Any]:
    left = _arm_outcomes_for_records(records, left_label)
    right = _arm_outcomes_for_records(records, right_label)
    left_wins = _as_int(left.get("authoritative_wins"))
    right_wins = _as_int(right.get("authoritative_wins"))
    delta = left_wins - right_wins
    return {
        "status": "improved" if delta > 0 else "regressed" if delta < 0 else "tied",
        "win_delta": delta,
        "left_wins": left_wins,
        "right_wins": right_wins,
    }


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


def _records_by(
    records: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, list[Mapping[str, Any]]]:
    output: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        output.setdefault(str(record.get(key) or MISSING_VALUE), []).append(record)
    return output


def _controller_labels(metadata: Mapping[str, Any]) -> list[str]:
    return [
        str(_mapping(arm).get("label") or "")
        for arm in _sequence(metadata.get("controller_arms"))
        if isinstance(arm, Mapping)
    ]


def _arm_information_regime(metadata: Mapping[str, Any], label: str) -> str | None:
    for arm in _sequence(metadata.get("controller_arms")):
        mapping = _mapping(arm)
        if mapping.get("label") != label:
            continue
        report = _mapping(mapping.get("report_metadata"))
        value = report.get("information_regime")
        return str(value) if value else None
    return None


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter)}


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
    rows = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{label}[{index}] must be an object")
        rows.append({str(key): child for key, child in item.items()})
    return rows


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


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


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_int_from_string(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _as_int(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
