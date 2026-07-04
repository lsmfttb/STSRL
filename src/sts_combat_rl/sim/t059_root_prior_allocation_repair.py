"""T059 root-prior allocation repair experiment report.

This module consumes the T058 selected-action diagnostic plus generated T059
four-arm fixed-cohort comparisons. It does not train, collect complete-run
sources, revive the T054/T055 guardrail path, or promote a controller.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search import (
    ROOT_PRIOR_ALLOCATION_REPAIR_STRATEGY,
    ROOT_PRIOR_ALLOCATION_REPAIR_VERSION,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
    ROOT_PRIOR_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
)
from sts_combat_rl.sim.t058_root_prior_selected_action_telemetry import (
    T058RootPriorSelectedActionTelemetryReport,
    T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID,
)


T059_REPAIR_REPORT_SCHEMA_ID = "t059-root-prior-allocation-repair-report-v1"
T059_REPAIR_REPORT_FORMAT_VERSION = 1
T059_RETENTION_MANIFEST_SCHEMA_ID = "t059-retention-manifest-v1"
T059_RETENTION_MANIFEST_FORMAT_VERSION = 1
T059_REPAIR_HYPOTHESIS = {
    "variant": T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME,
    "hypothesis": (
        "entropy-tempering public checkpoint priors before native root allocation "
        "can reduce harmful low-budget over-concentration while preserving the "
        "useful root-prior allocation signal"
    ),
    "pre_evaluation": True,
    "allocation_side_only": True,
    "final_selection": "native root statistics",
}
T059_REQUIRED_INPUT_ROLES = (
    "t058_selected_action_telemetry_report",
    "t058_retention_manifest",
    "t048_current_t058_comparison",
    "t048_assist0_t058_comparison",
    "t052_t058_comparison",
    "t048_current_fixed_cohort",
    "t048_assist0_fixed_cohort",
    "t052_boss_later_act_fixed_cohort",
    "t043_assist0_smoke_checkpoint",
    "t043_runs1000_assist0_checkpoint",
    "t059_current_repair_comparison",
    "t059_assist0_repair_comparison",
    "t059_t052_repair_comparison",
)
T059_COMPARISON_ROLES = (
    "t059_current_repair_comparison",
    "t059_assist0_repair_comparison",
    "t059_t052_repair_comparison",
)
T059_COMPARISON_CONTRACTS: dict[str, dict[str, Any]] = {
    "t059_current_repair_comparison": {
        "cohort_label": "t048_current_t046_compatible",
        "evidence_family": "t048_positive_fixed_cohort_signal",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "required_worker_count": 8,
        "required_shard_count": 8,
    },
    "t059_assist0_repair_comparison": {
        "cohort_label": "t048_assist0_runs1000",
        "evidence_family": "t048_positive_fixed_cohort_signal",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "required_worker_count": 16,
        "required_shard_count": 16,
    },
    "t059_t052_repair_comparison": {
        "cohort_label": "t052_boss_later_act_diagnostic",
        "evidence_family": "t052_t053_later_act_boss_diagnostic",
        "cohort_identity": "68d0e5b10ebcb05d",
        "record_count": 93,
        "record_range": "0:93",
        "accepted_merged_record_ranges": [
            "0:6",
            "6:12",
            "12:18",
            "18:24",
            "24:30",
            "30:36",
            "36:42",
            "42:48",
            "48:54",
            "54:60",
            "60:66",
            "66:72",
            "72:78",
            "78:83",
            "83:88",
            "88:93",
        ],
        "required_worker_count": 16,
        "required_shard_count": 16,
    },
}
T059_REQUIRED_COMPARISON_LABELS = (
    *REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
)
T059_ALLOWED_NEXT_TASKS = (
    "scale the repaired variant on additional fixed cohorts",
    "run a narrower diagnostic",
    "abandon the allocation-repair path",
    "run a bounded complete-run reachability probe for the repaired variant",
    "publish a blocked path requiring maintainer decision",
)
T059_EVIDENCE_BOUNDARY = {
    "task_id": "T059",
    "scope": "root-prior allocation repair fixed-cohort experiment",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
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
class T059ComparisonInput:
    """Compact streamed view of one generated T059 comparison artifact."""

    role: str
    metadata: dict[str, Any]
    battle_comparisons: list[dict[str, Any]]
    results_by_label: dict[str, dict[int, dict[str, Any]]]


@dataclass(frozen=True)
class T059RootPriorAllocationRepairReport:
    """Versioned T059 report assembled from retained and generated artifacts."""

    input_artifacts: list[dict[str, Any]]
    repair_hypothesis: dict[str, Any]
    prerequisite_summary: dict[str, Any]
    cohort_summaries: dict[str, Any]
    aggregate_summary: dict[str, Any]
    subset_summaries: dict[str, Any]
    per_record_repair_diagnostics: list[dict[str, Any]]
    selected_action_availability: dict[str, Any]
    allocation_telemetry_summary: dict[str, Any]
    recommendation: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T059_REPAIR_REPORT_SCHEMA_ID
    format_version: int = T059_REPAIR_REPORT_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T059_EVIDENCE_BOUNDARY)
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
            "repair_hypothesis": _json_safe_value(self.repair_hypothesis),
            "prerequisite_summary": _json_safe_value(self.prerequisite_summary),
            "cohort_summaries": _json_safe_value(self.cohort_summaries),
            "aggregate_summary": _json_safe_value(self.aggregate_summary),
            "subset_summaries": _json_safe_value(self.subset_summaries),
            "per_record_repair_diagnostics": _json_safe_value(
                self.per_record_repair_diagnostics
            ),
            "selected_action_availability": _json_safe_value(
                self.selected_action_availability
            ),
            "allocation_telemetry_summary": _json_safe_value(
                self.allocation_telemetry_summary
            ),
            "recommendation": _json_safe_value(self.recommendation),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def load_t059_root_prior_comparison_inputs(
    stream: TextIO,
    *,
    role: str,
) -> T059ComparisonInput:
    """Stream a T059 comparison JSONL artifact into compact report inputs."""

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
    return T059ComparisonInput(
        role=role,
        metadata=metadata,
        battle_comparisons=battle_comparisons,
        results_by_label=results_by_label,
    )


def build_t059_root_prior_allocation_repair_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t058_report: T058RootPriorSelectedActionTelemetryReport,
    comparisons: Mapping[str, T059ComparisonInput],
) -> T059RootPriorAllocationRepairReport:
    """Build and validate the offline T059 repair experiment report."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        t058_report=t058_report,
        comparisons=comparisons,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    records = _repair_records(comparisons, t058_report=t058_report)
    selected_action = _selected_action_availability(records)
    cohorts = _cohort_summaries(records)
    subsets = _subset_summaries(records, t058_report=t058_report)
    aggregate = _aggregate_summary(records, subsets)
    allocation = _allocation_telemetry_summary(records)
    recommendation = _recommendation(
        aggregate=aggregate,
        selected_action_availability=selected_action,
    )
    unavailable = _unavailable_diagnostics(selected_action)
    return T059RootPriorAllocationRepairReport(
        input_artifacts=artifacts,
        repair_hypothesis=dict(T059_REPAIR_HYPOTHESIS),
        prerequisite_summary=_prerequisite_summary(t058_report),
        cohort_summaries=cohorts,
        aggregate_summary=aggregate,
        subset_summaries=subsets,
        per_record_repair_diagnostics=records,
        selected_action_availability=selected_action,
        allocation_telemetry_summary=allocation,
        recommendation=recommendation,
        unavailable_diagnostics=unavailable,
    )


def dump_t059_root_prior_allocation_repair_report_json(
    report: T059RootPriorAllocationRepairReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T059 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t059_root_prior_allocation_repair_report_json(
    stream: TextIO,
) -> T059RootPriorAllocationRepairReport:
    """Load and validate a T059 report JSON artifact."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T059 repair report JSON") from exc
    return t059_root_prior_allocation_repair_report_from_dict(raw)


def t059_root_prior_allocation_repair_report_from_dict(
    raw: Mapping[str, Any],
) -> T059RootPriorAllocationRepairReport:
    """Validate a current-schema T059 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T059 repair report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T059_REPAIR_REPORT_SCHEMA_ID:
        raise ValueError(
            f"unsupported T059 repair report schema_id {schema_id!r}; "
            f"expected {T059_REPAIR_REPORT_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T059_REPAIR_REPORT_FORMAT_VERSION:
        raise ValueError(
            "unsupported T059 repair report format_version "
            f"{format_version!r}; expected {T059_REPAIR_REPORT_FORMAT_VERSION}"
        )
    return T059RootPriorAllocationRepairReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        repair_hypothesis=_require_mapping(
            raw.get("repair_hypothesis"),
            "repair_hypothesis",
        ),
        prerequisite_summary=_require_mapping(
            raw.get("prerequisite_summary"),
            "prerequisite_summary",
        ),
        cohort_summaries=_require_mapping(
            raw.get("cohort_summaries"),
            "cohort_summaries",
        ),
        aggregate_summary=_require_mapping(
            raw.get("aggregate_summary"),
            "aggregate_summary",
        ),
        subset_summaries=_require_mapping(
            raw.get("subset_summaries"),
            "subset_summaries",
        ),
        per_record_repair_diagnostics=_require_list_of_mappings(
            raw.get("per_record_repair_diagnostics"),
            "per_record_repair_diagnostics",
        ),
        selected_action_availability=_require_mapping(
            raw.get("selected_action_availability"),
            "selected_action_availability",
        ),
        allocation_telemetry_summary=_require_mapping(
            raw.get("allocation_telemetry_summary"),
            "allocation_telemetry_summary",
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
            raw.get("evidence_boundary", T059_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t059_root_prior_allocation_repair_report(
    report: T059RootPriorAllocationRepairReport,
) -> str:
    """Format concise T059 diagnostics for stderr and PR summaries."""

    aggregate = report.aggregate_summary
    recommendation = report.recommendation
    lines = [
        "T059 root-prior allocation repair report",
        (
            "scope: restored-battle allocation repair diagnostic only; no "
            "controller promotion, complete-run reachability evidence, live-game, "
            "natural A20, broad-training, normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "repair variant: "
            + str(report.repair_hypothesis.get("variant", MISSING_VALUE))
        ),
        (
            "evaluated records: "
            + str(aggregate.get("all_records", {}).get("record_count", 0))
        ),
        (
            "all-record repair vs existing root-prior: "
            + _delta_text(aggregate.get("repair_vs_existing_root_prior"))
        ),
        (
            "all-record repair vs baseline: "
            + _delta_text(aggregate.get("repair_vs_baseline"))
        ),
        (
            "all-record repair vs post-search: "
            + _delta_text(aggregate.get("repair_vs_post_search"))
        ),
        (
            "T048 signal: "
            + str(aggregate.get("t048_positive_signal_status", MISSING_VALUE))
        ),
        (
            "T052 Act-2+ repair status: "
            + str(aggregate.get("t052_act2_plus_repair_status", MISSING_VALUE))
        ),
        (
            "T053 disagreement repair status: "
            + str(aggregate.get("t053_disagreement_repair_status", MISSING_VALUE))
        ),
        "cohorts:",
    ]
    for label, summary in sorted(report.cohort_summaries.items()):
        outcomes = _mapping(summary.get("arm_outcomes"))
        lines.append(
            "  "
            + label
            + ": records="
            + str(summary.get("record_count", 0))
            + ", repair="
            + _win_loss_text(outcomes.get(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL))
            + ", root-prior="
            + _win_loss_text(outcomes.get(ROOT_PRIOR_GUIDED_LABEL))
        )
    lines.append(
        "selected-action availability: "
        f"{report.selected_action_availability.get('available_record_count', 0)} "
        "available / "
        f"{report.selected_action_availability.get('unavailable_record_count', 0)} "
        "unavailable"
    )
    lines.append(
        "recommended next task: "
        + str(recommendation.get("recommended_next_task", MISSING_VALUE))
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


def build_t059_retention_manifest_payload(
    *,
    artifact_specs: Sequence[Mapping[str, Any]],
    command_specs: Sequence[Mapping[str, str]] = (),
    stage_specs: Sequence[Mapping[str, Any]] = (),
    note_items: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Build a lightweight T059 artifact retention manifest."""

    if not artifact_specs:
        raise ValueError("T059 retention manifest requires at least one artifact")
    return {
        "schema_id": T059_RETENTION_MANIFEST_SCHEMA_ID,
        "format_version": T059_RETENTION_MANIFEST_FORMAT_VERSION,
        "task_id": "T059",
        "evidence_boundary": dict(T059_EVIDENCE_BOUNDARY),
        "retention_reason": (
            "preserve T059 repair comparisons, report, logs, and review evidence "
            "for maintainer review and the exactly one recommended follow-up task"
        ),
        "downstream_consumers": [
            "main maintainer review of T059",
            "the exactly one follow-up task recommended in the T059 report",
        ],
        "deletion_conditions": (
            "raw local artifacts may be deleted after T059 review is complete "
            "and the maintainer has recorded any retained identities needed by "
            "the next task"
        ),
        "artifacts": [_json_safe_mapping(spec) for spec in artifact_specs],
        "commands": [_json_safe_mapping(spec) for spec in command_specs],
        "runtime_stages": [_json_safe_mapping(spec) for spec in stage_specs],
        "notes": {str(key): str(value) for key, value in note_items},
    }


def dump_t059_retention_manifest_json(
    payload: Mapping[str, Any], stream: TextIO
) -> None:
    """Write deterministic T059 retention manifest JSON."""

    json.dump(_json_safe_mapping(payload), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_t059_retention_manifest(payload: Mapping[str, Any]) -> str:
    """Format the T059 retention manifest for stderr."""

    artifacts = _sequence(payload.get("artifacts"))
    stages = _sequence(payload.get("runtime_stages"))
    lines = [
        "T059 retention manifest",
        f"artifact count: {len(artifacts)}",
        f"runtime stage count: {len(stages)}",
        "artifacts:",
    ]
    for artifact in artifacts:
        mapping = _mapping(artifact)
        lines.append(
            "  "
            + str(mapping.get("role", "(missing)"))
            + ": sha256="
            + str(mapping.get("sha256", "(missing)"))
            + ", bytes="
            + str(mapping.get("byte_count", "(missing)"))
        )
    if not artifacts:
        lines.append("  (none)")
    return "\n".join(lines)


def _validation_problems(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t058_report: T058RootPriorSelectedActionTelemetryReport,
    comparisons: Mapping[str, T059ComparisonInput],
) -> list[str]:
    problems: list[str] = []
    roles = [str(artifact.get("role") or "") for artifact in input_artifacts]
    if sorted(roles) != sorted(T059_REQUIRED_INPUT_ROLES):
        problems.append(
            "T059 input artifact roles must match "
            + ", ".join(T059_REQUIRED_INPUT_ROLES)
        )
    if len(set(roles)) != len(roles):
        problems.append("duplicate T059 input artifact roles")
    for artifact in input_artifacts:
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{artifact.get('role', 'artifact')}: sha256 not verified")
    if t058_report.schema_id != T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID:
        problems.append("T058 selected-action report schema mismatch")
    if not t058_report.command_passed:
        problems.append("T058 selected-action report command did not pass")
    t058_next = t058_report.recommendation.get("selected_next_path")
    if t058_next != "root-prior allocation repair experiment":
        problems.append("T058 selected next path does not authorize T059")
    availability = _mapping(t058_report.selected_action_availability)
    if _as_int(availability.get("record_count")) != 122:
        problems.append("T058 selected-action report must cover 122 records")
    if _as_int(availability.get("unavailable_record_count")) != 0:
        problems.append("T058 selected-action report has unavailable records")
    if availability.get("exact_step_level_comparison_feasible_all") is not True:
        problems.append("T058 exact step-level comparison is not feasible for all")
    for role in T059_COMPARISON_ROLES:
        comparison = comparisons.get(role)
        if comparison is None:
            problems.append(f"missing T059 comparison input {role}")
            continue
        problems.extend(_comparison_validation_problems(role, comparison))
    return list(dict.fromkeys(problems))


def _comparison_validation_problems(
    role: str,
    comparison: T059ComparisonInput,
) -> list[str]:
    contract = T059_COMPARISON_CONTRACTS[role]
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
    if config.get("task_id") != "T059":
        problems.append(f"{role}: comparison task_id must be 'T059'")
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
    if not _record_range_matches(config, contract):
        problems.append(f"{role}: record_range mismatch")
    if _as_int(config.get("worker_count")) != contract["required_worker_count"]:
        problems.append(f"{role}: worker_count mismatch")
    if _as_int(config.get("shard_count")) != contract["required_shard_count"]:
        problems.append(f"{role}: shard_count mismatch")
    labels = set(_controller_labels(metadata))
    missing_labels = sorted(set(T059_REQUIRED_COMPARISON_LABELS) - labels)
    if missing_labels:
        problems.append(f"{role}: missing required arms {', '.join(missing_labels)}")
    for label in T059_REQUIRED_COMPARISON_LABELS:
        regime = _arm_information_regime(metadata, label)
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{role}:{label}: information regime {regime!r} is not "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
    budgets = _mapping(
        _mapping(metadata.get("budget_comparison")).get("configured_native_playouts")
    )
    budget_values = [budgets.get(label) for label in T059_REQUIRED_COMPARISON_LABELS]
    if (
        any(_optional_int(value) is None for value in budget_values)
        or len({_as_int(value) for value in budget_values}) != 1
    ):
        problems.append(f"{role}: required arms do not share equal native budget")
    repair_config = _repair_controller_config(metadata)
    if repair_config.get("controller_version") != (
        T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
    ):
        problems.append(f"{role}: T059 repair controller version mismatch")
    allocation = _mapping(repair_config.get("root_prior_allocation"))
    repair = _mapping(allocation.get("repair"))
    if repair.get("version") != ROOT_PRIOR_ALLOCATION_REPAIR_VERSION:
        problems.append(f"{role}: T059 repair version mismatch")
    if repair.get("strategy") != ROOT_PRIOR_ALLOCATION_REPAIR_STRATEGY:
        problems.append(f"{role}: T059 repair strategy mismatch")
    if allocation.get("guardrail") is not None or allocation.get("guardrail_revived"):
        problems.append(f"{role}: T059 comparison appears to revive guardrail")
    for label in T059_REQUIRED_COMPARISON_LABELS:
        result_count = len(comparison.results_by_label.get(label, {}))
        if result_count != int(contract["record_count"]):
            problems.append(f"{role}:{label}: controller result count mismatch")
    return problems


def _record_range_matches(
    config: Mapping[str, Any], contract: Mapping[str, Any]
) -> bool:
    actual = str(config.get("record_range") or "")
    if actual == contract["record_range"]:
        return True
    accepted_ranges = contract.get("accepted_merged_record_ranges")
    if not isinstance(accepted_ranges, list) or not accepted_ranges:
        return False
    expected = [str(item) for item in accepted_ranges]
    if actual != "merged:" + ",".join(expected):
        return False
    merged_from = config.get("merged_from_record_ranges")
    if not isinstance(merged_from, list):
        return False
    return [str(item) for item in merged_from] == expected


def _repair_records(
    comparisons: Mapping[str, T059ComparisonInput],
    *,
    t058_report: T058RootPriorSelectedActionTelemetryReport,
) -> list[dict[str, Any]]:
    t053_indices = set(_t053_disagreement_indices(t058_report))
    records: list[dict[str, Any]] = []
    for role in T059_COMPARISON_ROLES:
        comparison = comparisons[role]
        contract = T059_COMPARISON_CONTRACTS[role]
        for item in comparison.battle_comparisons:
            index = _as_int(item.get("comparison_index"))
            arms = {
                label: _json_safe_mapping(
                    _mapping(comparison.results_by_label.get(label, {}).get(index))
                )
                for label in T059_REQUIRED_COMPARISON_LABELS
            }
            source = _source_identity(
                comparison=item,
                preferred_result=arms.get(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL, {}),
            )
            record = {
                "comparison_role": role,
                "cohort_label": contract["cohort_label"],
                "evidence_family": contract["evidence_family"],
                "cohort_index": index,
                "source_identity": source,
                "subset": _subset_label(source),
                "t053_disagreement_record": (
                    contract["cohort_label"] == "t052_boss_later_act_diagnostic"
                    and index in t053_indices
                ),
                "arms": arms,
                "outcome_delta": _record_outcome_delta(
                    repair=arms.get(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL, {}),
                    root=arms.get(ROOT_PRIOR_GUIDED_LABEL, {}),
                    baseline=arms.get(BASELINE_ORACLE_LABEL, {}),
                    post=arms.get(POST_SEARCH_MODEL_GUIDED_LABEL, {}),
                ),
                "selected_action_comparison": _selected_action_comparison(arms),
                "allocation_telemetry": {
                    "existing_root_prior": _mapping(
                        arms.get(ROOT_PRIOR_GUIDED_LABEL, {})
                    ).get("root_prior_allocation", {}),
                    "t059_repair": _mapping(
                        arms.get(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL, {})
                    ).get("root_prior_allocation", {}),
                },
            }
            records.append(_json_safe_mapping(record))
    return records


def _cohort_summaries(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        label: _record_group_summary(
            [record for record in records if record.get("cohort_label") == label],
            group_label=label,
        )
        for label in (
            "t048_current_t046_compatible",
            "t048_assist0_runs1000",
            "t052_boss_later_act_diagnostic",
        )
    }


def _subset_summaries(
    records: Sequence[Mapping[str, Any]],
    *,
    t058_report: T058RootPriorSelectedActionTelemetryReport,
) -> dict[str, Any]:
    t053_indices = set(_t053_disagreement_indices(t058_report))
    specs = {
        "t048_positive_fixed_cohorts": lambda record: (
            record.get("evidence_family") == "t048_positive_fixed_cohort_signal"
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
            and _as_int(record.get("cohort_index")) in t053_indices
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
            for arm in T059_REQUIRED_COMPARISON_LABELS
        },
        "selected_action_availability": _selected_action_availability(records),
        "repair_vs_existing_root_prior": _aggregate_outcome_delta(
            records,
            left_label=T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
            right_label=ROOT_PRIOR_GUIDED_LABEL,
        ),
        "repair_vs_baseline": _aggregate_outcome_delta(
            records,
            left_label=T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
            right_label=BASELINE_ORACLE_LABEL,
        ),
        "repair_vs_post_search": _aggregate_outcome_delta(
            records,
            left_label=T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
            right_label=POST_SEARCH_MODEL_GUIDED_LABEL,
        ),
    }


def _aggregate_summary(
    records: Sequence[Mapping[str, Any]],
    subsets: Mapping[str, Any],
) -> dict[str, Any]:
    all_records = _record_group_summary(records, group_label="all_records")
    t048 = _mapping(subsets.get("t048_positive_fixed_cohorts"))
    act2 = _mapping(subsets.get("t052_act2_plus"))
    disagreement = _mapping(subsets.get("t053_disagreement_records"))
    return {
        "all_records": all_records,
        "repair_vs_existing_root_prior": all_records["repair_vs_existing_root_prior"],
        "repair_vs_baseline": all_records["repair_vs_baseline"],
        "repair_vs_post_search": all_records["repair_vs_post_search"],
        "t048_positive_signal_status": _t048_signal_status(t048),
        "t052_act2_plus_repair_status": _status_value(
            act2.get("repair_vs_existing_root_prior")
        ),
        "t053_disagreement_repair_status": _status_value(
            disagreement.get("repair_vs_existing_root_prior")
        ),
        "preserved_t048_positive_signal": _preserved_t048_signal(t048),
        "repaired_or_tied_t052_act2_plus": _not_regressed_vs_root(act2),
        "repaired_or_tied_t053_disagreement": _not_regressed_vs_root(disagreement),
        "improved_t052_act2_plus": _status_value(
            act2.get("repair_vs_existing_root_prior")
        )
        == "improved",
        "improved_t053_disagreement": _status_value(
            disagreement.get("repair_vs_existing_root_prior")
        )
        == "improved",
    }


def _selected_action_availability(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unavailable_records = []
    exact_full = 0
    for record in records:
        comparison = _mapping(record.get("selected_action_comparison"))
        if comparison.get("status") == "available":
            if comparison.get("exact_full_battle_path_comparison"):
                exact_full += 1
            continue
        unavailable_records.append(
            {
                "cohort_label": record.get("cohort_label"),
                "cohort_index": record.get("cohort_index"),
                "reason": comparison.get("reason", MISSING_VALUE),
            }
        )
    unavailable_count = len(unavailable_records)
    return {
        "record_count": len(records),
        "available_record_count": len(records) - unavailable_count,
        "unavailable_record_count": unavailable_count,
        "exact_full_record_count": exact_full,
        "exact_step_level_comparison_feasible_all": unavailable_count == 0,
        "unavailable_records": unavailable_records[:200],
    }


def _selected_action_comparison(
    arms: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    repair = _mapping(arms.get(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL))
    root = _mapping(arms.get(ROOT_PRIOR_GUIDED_LABEL))
    baseline = _mapping(arms.get(BASELINE_ORACLE_LABEL))
    post = _mapping(arms.get(POST_SEARCH_MODEL_GUIDED_LABEL))
    action_lists = {
        T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: _list_of_mappings(
            repair.get("selected_actions")
        ),
        ROOT_PRIOR_GUIDED_LABEL: _list_of_mappings(root.get("selected_actions")),
        BASELINE_ORACLE_LABEL: _list_of_mappings(baseline.get("selected_actions")),
        POST_SEARCH_MODEL_GUIDED_LABEL: _list_of_mappings(post.get("selected_actions")),
    }
    missing = []
    for label, arm in (
        (T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL, repair),
        (ROOT_PRIOR_GUIDED_LABEL, root),
        (BASELINE_ORACLE_LABEL, baseline),
        (POST_SEARCH_MODEL_GUIDED_LABEL, post),
    ):
        reason = arm.get("selected_action_missing_reason")
        if reason is not None:
            missing.append(f"{label}:{reason}")
        elif not action_lists[label]:
            missing.append(f"{label}:selected action identity unavailable")
    if missing:
        return {
            "status": "unavailable",
            "reason": "; ".join(missing),
            "missing_reasons": missing,
            "exact_step_level_matching": False,
            "exact_full_battle_path_comparison": False,
            "decision_counts": {
                label: len(actions) for label, actions in action_lists.items()
            },
        }
    counts = [len(actions) for actions in action_lists.values()]
    full_path = len(set(counts)) == 1 and counts[0] > 0
    repair_actions = action_lists[T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL]
    return {
        "status": "available",
        "exact_step_level_matching": True,
        "exact_full_battle_path_comparison": full_path,
        "comparable_decision_count": min(counts),
        "decision_counts": {
            label: len(actions) for label, actions in action_lists.items()
        },
        "repair_first_actions": repair_actions[:5],
        "root_prior_first_actions": action_lists[ROOT_PRIOR_GUIDED_LABEL][:5],
        "baseline_first_actions": action_lists[BASELINE_ORACLE_LABEL][:5],
        "post_search_first_actions": action_lists[POST_SEARCH_MODEL_GUIDED_LABEL][:5],
        "first_difference_vs_baseline": _first_action_difference(
            repair_actions,
            action_lists[BASELINE_ORACLE_LABEL],
        ),
        "first_difference_vs_post_search": _first_action_difference(
            repair_actions,
            action_lists[POST_SEARCH_MODEL_GUIDED_LABEL],
        ),
        "first_difference_vs_existing_root_prior": _first_action_difference(
            repair_actions,
            action_lists[ROOT_PRIOR_GUIDED_LABEL],
        ),
        "repair_matches_baseline_action_count": _matching_action_count(
            repair_actions,
            action_lists[BASELINE_ORACLE_LABEL],
        ),
        "repair_matches_post_search_action_count": _matching_action_count(
            repair_actions,
            action_lists[POST_SEARCH_MODEL_GUIDED_LABEL],
        ),
        "repair_matches_existing_root_prior_action_count": _matching_action_count(
            repair_actions,
            action_lists[ROOT_PRIOR_GUIDED_LABEL],
        ),
    }


def _allocation_telemetry_summary(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "existing_root_prior": _allocation_summary_for_label(
            records,
            ROOT_PRIOR_GUIDED_LABEL,
        ),
        "t059_repair": _allocation_summary_for_label(
            records,
            T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
        ),
    }


def _allocation_summary_for_label(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, Any]:
    decision_count = 0
    malformed = 0
    selected_identity_available = 0
    missing_repair_config = 0
    missing_repair_summary = 0
    strategy_counts: Counter[str] = Counter()
    version_counts: Counter[str] = Counter()
    changed_prior_count = 0
    l1_delta = 0.0
    max_pre: list[float] = []
    max_post: list[float] = []
    for record in records:
        arm = _mapping(_mapping(record.get("arms")).get(label))
        allocation = _mapping(arm.get("root_prior_allocation"))
        decision_count += _as_int(allocation.get("decision_count"))
        malformed += _as_int(allocation.get("malformed_allocation_metadata_count"))
        selected_identity_available += _as_int(
            allocation.get("selected_action_identity_available_count")
        )
        if label != T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL:
            continue
        repair = _mapping(allocation.get("repair_telemetry"))
        missing_repair_config += _as_int(repair.get("missing_repair_config_count"))
        missing_repair_summary += _as_int(repair.get("missing_repair_summary_count"))
        changed_prior_count += _as_int(repair.get("changed_prior_count"))
        l1_delta += _as_float(repair.get("l1_prior_delta_total")) or 0.0
        for strategy, count in _mapping(repair.get("repair_strategy_counts")).items():
            strategy_counts[str(strategy)] += _as_int(count)
        for version, count in _mapping(repair.get("repair_version_counts")).items():
            version_counts[str(version)] += _as_int(count)
        pre = _as_float(repair.get("max_pre_repair_prior_probability"))
        post = _as_float(repair.get("max_post_repair_prior_probability"))
        if pre is not None:
            max_pre.append(pre)
        if post is not None:
            max_post.append(post)
    payload = {
        "decision_count": decision_count,
        "malformed_allocation_metadata_count": malformed,
        "selected_action_identity_available_count": selected_identity_available,
    }
    if label == T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL:
        payload["repair_telemetry"] = {
            "missing_repair_config_count": missing_repair_config,
            "missing_repair_summary_count": missing_repair_summary,
            "changed_prior_count": changed_prior_count,
            "l1_prior_delta_total": l1_delta,
            "max_pre_repair_prior_probability": max(max_pre) if max_pre else None,
            "max_post_repair_prior_probability": max(max_post) if max_post else None,
            "repair_strategy_counts": _counter_dict(strategy_counts),
            "repair_version_counts": _counter_dict(version_counts),
        }
    return payload


def _recommendation(
    *,
    aggregate: Mapping[str, Any],
    selected_action_availability: Mapping[str, Any],
) -> dict[str, Any]:
    unavailable = _as_int(selected_action_availability.get("unavailable_record_count"))
    if unavailable:
        selected = "publish a blocked path requiring maintainer decision"
        reason = (
            "one or more retained T059 records lack comparable selected-action "
            "identity, so the report fails closed"
        )
    elif not bool(aggregate.get("preserved_t048_positive_signal")):
        selected = "abandon the allocation-repair path"
        reason = "the repair failed to preserve the T048 positive fixed-cohort signal"
    elif (
        bool(aggregate.get("improved_t052_act2_plus"))
        and bool(aggregate.get("improved_t053_disagreement"))
        and _status_value(aggregate.get("repair_vs_existing_root_prior")) != "regressed"
    ):
        selected = (
            "run a bounded complete-run reachability probe for the repaired variant"
        )
        reason = (
            "the repair preserved the retained T048 signal and improved the "
            "T052 Act-2+ and T053 disagreement subsets versus existing root-prior"
        )
    elif (
        _status_value(aggregate.get("repair_vs_existing_root_prior")) == "regressed"
        or _status_value(aggregate.get("t052_act2_plus_repair_status")) == "regressed"
        or _status_value(aggregate.get("t053_disagreement_repair_status"))
        == "regressed"
    ):
        selected = "abandon the allocation-repair path"
        reason = (
            "the repair regressed versus existing root-prior overall or on a "
            "required harmful subset"
        )
    elif (
        _status_value(aggregate.get("t052_act2_plus_repair_status")) == "tied"
        and _status_value(aggregate.get("t053_disagreement_repair_status")) == "tied"
    ):
        selected = "abandon the allocation-repair path"
        reason = (
            "the single allocation-side repair preserved T048 but did not reduce "
            "the known T052 Act-2+ or T053 disagreement regressions"
        )
    else:
        selected = "run a narrower diagnostic"
        reason = (
            "the repair preserved some signal but left subset conflict or "
            "insufficiently clear evidence before reachability"
        )
    return {
        "recommendation_count": 1,
        "selected_next_path": selected,
        "recommended_next_task": selected,
        "allowed_recommendation_set": list(T059_ALLOWED_NEXT_TASKS),
        "reason": reason,
        "evidence_support": {
            "selected_action_unavailable_record_count": unavailable,
            "preserved_t048_positive_signal": bool(
                aggregate.get("preserved_t048_positive_signal")
            ),
            "repaired_or_tied_t052_act2_plus": bool(
                aggregate.get("repaired_or_tied_t052_act2_plus")
            ),
            "repaired_or_tied_t053_disagreement": bool(
                aggregate.get("repaired_or_tied_t053_disagreement")
            ),
            "improved_t052_act2_plus": bool(aggregate.get("improved_t052_act2_plus")),
            "improved_t053_disagreement": bool(
                aggregate.get("improved_t053_disagreement")
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
    rows = [
        {
            "diagnostic": "allocation_causal_counterfactual",
            "reason": (
                "selected-action telemetry makes chosen-action divergence "
                "auditable but does not expose paired within-decision native "
                "counterfactual search trees"
            ),
        },
        {
            "diagnostic": "normal_information_strength",
            "reason": (
                f"all T059 search evidence remains {NATIVE_SEARCH_INFORMATION_REGIME}"
            ),
        },
    ]
    if _as_int(selected_action_availability.get("unavailable_record_count")):
        rows.append(
            {
                "diagnostic": "exact_all_arm_step_level_selected_action_comparison",
                "reason": "one or more required retained records lack selected actions",
                "unavailable_records": _json_safe_value(
                    selected_action_availability.get("unavailable_records", [])
                ),
            }
        )
    return rows


def _prerequisite_summary(
    t058_report: T058RootPriorSelectedActionTelemetryReport,
) -> dict[str, Any]:
    availability = _mapping(t058_report.selected_action_availability)
    recommendation = _mapping(t058_report.recommendation)
    return {
        "t058_schema_id": t058_report.schema_id,
        "t058_command_passed": t058_report.command_passed,
        "t058_selected_next_path": recommendation.get("selected_next_path"),
        "t058_record_count": availability.get("record_count"),
        "t058_available_record_count": availability.get("available_record_count"),
        "t058_unavailable_record_count": availability.get("unavailable_record_count"),
        "t058_exact_full_record_count": availability.get("exact_full_record_count"),
        "t058_exact_step_level_comparison_feasible_all": availability.get(
            "exact_step_level_comparison_feasible_all"
        ),
    }


def _compact_result_summary(label: str, result: Mapping[str, Any]) -> dict[str, Any]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
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
        "selected_actions": selected_actions,
        "selected_action_missing_reason": selected_reason,
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL}:
        summary["root_prior_allocation"] = _root_prior_allocation_summary_for_result(
            result,
            include_repair=(label == T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL),
        )
    summary["model_calls"] = _model_call_count(telemetry, label)
    return summary


def _root_prior_allocation_summary_for_result(
    result: Mapping[str, Any],
    *,
    include_repair: bool,
) -> dict[str, Any]:
    reports = _root_prior_decision_reports(result)
    malformed = 0
    selected_actions: list[dict[str, Any]] = []
    selected_action_identity_available = 0
    repair_rows: list[dict[str, Any]] = []
    for index, decision in enumerate(reports):
        metadata = _mapping(decision.get("allocation_metadata"))
        if (
            metadata.get("schema_id") != NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
            or metadata.get("allocation_strategy")
            != NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY
        ):
            malformed += 1
        target = _mapping(decision.get("target"))
        selected = _optional_int(target.get("legal_action_index"))
        if selected is not None:
            action = {
                "decision_index": index,
                "selected_index": selected,
                "target": _target_summary(target),
            }
            if _mapping(target.get("action_identity")):
                selected_action_identity_available += 1
            selected_actions.append(action)
        if include_repair:
            repair_rows.append(
                {
                    "config": _json_safe_mapping(
                        _mapping(decision.get("repair_config"))
                    ),
                    "summary": _json_safe_mapping(
                        _mapping(decision.get("repair_summary"))
                    ),
                }
            )
    payload = {
        "decision_count": len(reports),
        "selected_actions": selected_actions,
        "selected_action_identity_available_count": selected_action_identity_available,
        "malformed_allocation_metadata_count": malformed,
    }
    if include_repair:
        payload["repair_telemetry"] = _repair_telemetry_summary(repair_rows)
    return payload


def _repair_telemetry_summary(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    missing_config = 0
    missing_summary = 0
    changed_prior_count = 0
    l1_delta = 0.0
    strategies: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    max_pre: list[float] = []
    max_post: list[float] = []
    for row in rows:
        config = _mapping(row.get("config"))
        summary = _mapping(row.get("summary"))
        if not config:
            missing_config += 1
        if not summary:
            missing_summary += 1
        strategies[str(config.get("strategy") or MISSING_VALUE)] += 1
        versions[str(config.get("version") or MISSING_VALUE)] += 1
        changed_prior_count += _as_int(summary.get("changed_prior_count"))
        l1_delta += _as_float(summary.get("l1_prior_delta")) or 0.0
        pre = _as_float(summary.get("pre_repair_max_prior_probability"))
        post = _as_float(summary.get("post_repair_max_prior_probability"))
        if pre is not None:
            max_pre.append(pre)
        if post is not None:
            max_post.append(post)
    return {
        "decision_count": len(rows),
        "missing_repair_config_count": missing_config,
        "missing_repair_summary_count": missing_summary,
        "changed_prior_count": changed_prior_count,
        "l1_prior_delta_total": l1_delta,
        "max_pre_repair_prior_probability": max(max_pre) if max_pre else None,
        "max_post_repair_prior_probability": max(max_post) if max_post else None,
        "repair_strategy_counts": _counter_dict(strategies),
        "repair_version_counts": _counter_dict(versions),
    }


def _selected_actions_for_result(
    label: str,
    result: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    if label in {ROOT_PRIOR_GUIDED_LABEL, T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL}:
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
            actions.append({"selected_index": selected_index, "action_identity": {}})
            missing_identity = True
            continue
        missing_identity = True
    if actions:
        reason = "some selected action identities missing" if missing_identity else None
        return actions, reason
    return [], "selected action identity unavailable in retained telemetry"


def _record_outcome_delta(
    *,
    repair: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline: Mapping[str, Any],
    post: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "repair_vs_existing_root_prior": _outcome_delta(repair, root),
        "repair_vs_baseline": _outcome_delta(repair, baseline),
        "repair_vs_post_search": _outcome_delta(repair, post),
        "all_outcomes_identical": (
            _outcome_signature(repair)
            == _outcome_signature(root)
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


def _t048_signal_status(summary: Mapping[str, Any]) -> str:
    if not summary:
        return "unavailable"
    repair_vs_baseline = _status_value(summary.get("repair_vs_baseline"))
    repair_vs_post = _status_value(summary.get("repair_vs_post_search"))
    if repair_vs_baseline == "regressed" or repair_vs_post == "regressed":
        return "not_preserved"
    repair_vs_root = _status_value(summary.get("repair_vs_existing_root_prior"))
    if repair_vs_root == "improved":
        return "improved_vs_existing_root_prior"
    if repair_vs_root == "tied":
        return "preserved"
    return "weakened_vs_existing_root_prior"


def _preserved_t048_signal(summary: Mapping[str, Any]) -> bool:
    return _t048_signal_status(summary) in {
        "improved_vs_existing_root_prior",
        "preserved",
        "weakened_vs_existing_root_prior",
    }


def _not_regressed_vs_root(summary: Mapping[str, Any]) -> bool:
    if not summary:
        return False
    return _status_value(summary.get("repair_vs_existing_root_prior")) != "regressed"


def _status_delta(left_win: bool, right_win: bool) -> str:
    if left_win and not right_win:
        return "improved"
    if not left_win and right_win:
        return "regressed"
    return "same"


def _outcome_signature(arm: Mapping[str, Any]) -> tuple[Any, Any]:
    return arm.get("termination_status"), arm.get("terminal_absolute_hp")


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
        "t052_selection_reasons": _json_safe_value(
            structural.get("t052_selection_reasons", [])
        ),
    }


def _source_identity_from_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cohort_index": result.get("cohort_index"),
        "source_checkpoint_id": result.get("source_checkpoint_id"),
        "source_seed": result.get("source_seed"),
        "source_run_id": result.get("source_run_id"),
        "source_battle_index": result.get("source_battle_index"),
    }


def _subset_label(source: Mapping[str, Any]) -> str:
    act = _optional_int(source.get("act"))
    if act is not None and act >= 2:
        return "act2_plus"
    room_type = str(source.get("room_type") or "").lower()
    if "boss" in room_type:
        return "boss_only"
    reasons = {
        str(item).lower()
        for item in [
            *_sequence(source.get("selection_reasons")),
            *_sequence(source.get("t052_selection_reasons")),
        ]
    }
    if "act2_plus" in reasons:
        return "act2_plus"
    if "act1_boss" in reasons:
        return "boss_only"
    return "other"


def _t053_disagreement_indices(
    t058_report: T058RootPriorSelectedActionTelemetryReport,
) -> list[int]:
    subset = _mapping(t058_report.subset_summaries.get("t053_disagreement_records"))
    return [
        parsed
        for value in _sequence(subset.get("cohort_indices"))
        if (parsed := _optional_int(value)) is not None
    ]


def _repair_controller_config(metadata: Mapping[str, Any]) -> dict[str, Any]:
    for arm in _sequence(metadata.get("controller_arms")):
        mapping = _mapping(arm)
        if mapping.get("label") != T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL:
            continue
        report = _mapping(mapping.get("report_metadata"))
        provenance = _mapping(report.get("controller_provenance"))
        return _mapping(provenance.get("config"))
    return {}


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


def _model_call_count(telemetry: Mapping[str, Any], label: str) -> int | float | None:
    search = _mapping(telemetry.get("search_telemetry_summary"))
    value = _telemetry_total(search, "model_calls")
    if value is not None:
        return value
    if label in {ROOT_PRIOR_GUIDED_LABEL, T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL}:
        return _optional_int(telemetry.get("root_prior_guided_model_calls"))
    return _optional_int(telemetry.get("oracle_search_model_calls"))


def _telemetry_total(search_summary: Mapping[str, Any], key: str) -> float | None:
    metric = _mapping(search_summary.get(key))
    value = metric.get("total")
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _root_prior_decision_reports(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    return _flatten_mappings(telemetry.get("root_prior_guided_decision_reports"))


def _flatten_mappings(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _collect_mapping_rows(value, rows)
    return rows


def _collect_mapping_rows(value: Any, rows: list[dict[str, Any]]) -> None:
    if isinstance(value, Mapping):
        rows.append({str(key): item for key, item in value.items()})
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _collect_mapping_rows(item, rows)


def _target_summary(target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selected_index": target.get("legal_action_index"),
        "selected_legal_action_index": target.get("legal_action_index"),
        "action_identity": _json_safe_mapping(_mapping(target.get("action_identity"))),
        "selection_rule": target.get("selection_rule"),
        "visits": target.get("visits"),
        "mean_value": target.get("mean_value"),
        "score": target.get("score"),
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


def _restore_status(result: Mapping[str, Any]) -> str:
    if result.get("termination_status") == "error":
        return "error"
    if result.get("restoration_method"):
        return "restored"
    return "unavailable"


def _status_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(_mapping(value).get("status") or MISSING_VALUE)


def _delta_text(value: Any) -> str:
    mapping = _mapping(value)
    if not mapping:
        return "missing"
    return (
        str(mapping.get("status", MISSING_VALUE))
        + " (delta="
        + str(mapping.get("win_delta", MISSING_VALUE))
        + ")"
    )


def _win_loss_text(value: Any) -> str:
    mapping = _mapping(value)
    if not mapping:
        return "missing"
    return (
        f"{_as_int(mapping.get('authoritative_wins'))}W/"
        f"{_as_int(mapping.get('losses'))}L"
    )


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


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    return [_mapping(item) for item in _sequence(value) if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _sequence(value)]


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


def _as_int(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
