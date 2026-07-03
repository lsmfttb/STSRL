"""T054 guardrailed root-prior allocation repair report.

This module consumes retained T052/T053 evidence plus a new T054 four-arm
fixed-cohort comparison. It does not train, collect complete-run sources,
change controller defaults, or make promotion claims.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search import (
    GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME,
    GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
    ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY,
    ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    RootPriorGuidedSearchComparisonReport,
    root_prior_allocation_summary,
    root_prior_guided_budget_summary,
    root_prior_guided_controller_summaries,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053RootPriorFailureAnalysisReport,
)


T054_REPAIR_REPORT_SCHEMA_ID = "t054-guardrailed-root-prior-repair-report-v1"
T054_REPAIR_REPORT_FORMAT_VERSION = 1
T054_RETENTION_MANIFEST_SCHEMA_ID = "t054-retention-manifest-v1"
T054_RETENTION_MANIFEST_FORMAT_VERSION = 1
T054_REQUIRED_COMPARISON_LABELS = (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
)
T054_REQUIRED_INPUT_ROLES = (
    "t052_retention_manifest",
    "t052_fixed_cohort",
    "t052_root_prior_guided_comparison",
    "t052_result_summary",
    "t053_failure_analysis",
    "t054_guardrailed_comparison",
)
T054_REQUIRED_DISAGREEMENT_INDICES = (53, 54, 55, 87)
T054_EXPECTED_COHORT_RECORD_COUNT = 93
T054_EVIDENCE_BOUNDARY = {
    "task_id": "T054",
    "scope": "guardrailed root-prior allocation repair diagnostics",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}


@dataclass(frozen=True)
class T054GuardrailedRootPriorRepairReport:
    """Versioned T054 report assembled from retained and generated artifacts."""

    input_artifacts: list[dict[str, Any]]
    t052_comparison_summary: dict[str, Any]
    t052_result_summary: dict[str, Any]
    t053_reference_summary: dict[str, Any]
    t054_comparison_summary: dict[str, Any]
    guardrail_configuration: dict[str, Any]
    aggregate_outcome_comparison: dict[str, Any]
    subset_summaries: dict[str, dict[str, Any]]
    disagreement_index_results: list[dict[str, Any]]
    allocation_telemetry_summary: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]]
    recommendation: dict[str, Any]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T054_REPAIR_REPORT_SCHEMA_ID
    format_version: int = T054_REPAIR_REPORT_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T054_EVIDENCE_BOUNDARY)
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
            "t052_comparison_summary": _json_safe_value(self.t052_comparison_summary),
            "t052_result_summary": _json_safe_value(self.t052_result_summary),
            "t053_reference_summary": _json_safe_value(self.t053_reference_summary),
            "t054_comparison_summary": _json_safe_value(self.t054_comparison_summary),
            "guardrail_configuration": _json_safe_value(self.guardrail_configuration),
            "aggregate_outcome_comparison": _json_safe_value(
                self.aggregate_outcome_comparison
            ),
            "subset_summaries": _json_safe_value(self.subset_summaries),
            "disagreement_index_results": _json_safe_value(
                self.disagreement_index_results
            ),
            "allocation_telemetry_summary": _json_safe_value(
                self.allocation_telemetry_summary
            ),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "recommendation": _json_safe_value(self.recommendation),
            "validation_problems": list(self.validation_problems),
        }


def build_t054_guardrailed_root_prior_repair_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t052_comparison: RootPriorGuidedSearchComparisonReport,
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_comparison: RootPriorGuidedSearchComparisonReport,
) -> T054GuardrailedRootPriorRepairReport:
    """Build and validate the T054 guardrail repair report."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        t052_comparison=t052_comparison,
        t053_report=t053_report,
        t054_comparison=t054_comparison,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    aggregate = _aggregate_outcome_comparison(t054_comparison)
    subsets = _subset_summaries(t054_comparison)
    disagreement_rows = _disagreement_index_results(t054_comparison, t053_report)
    allocation = _allocation_telemetry_summary(t054_comparison)
    unavailable = _unavailable_diagnostics(t054_comparison, allocation)
    recommendation = _recommendation(
        aggregate=aggregate,
        disagreement_rows=disagreement_rows,
    )
    return T054GuardrailedRootPriorRepairReport(
        input_artifacts=artifacts,
        t052_comparison_summary=_comparison_summary(t052_comparison),
        t052_result_summary=_json_safe_mapping(t052_result_summary),
        t053_reference_summary=_t053_reference_summary(t053_report),
        t054_comparison_summary=_comparison_summary(t054_comparison),
        guardrail_configuration=_guardrail_configuration(t054_comparison),
        aggregate_outcome_comparison=aggregate,
        subset_summaries=subsets,
        disagreement_index_results=disagreement_rows,
        allocation_telemetry_summary=allocation,
        unavailable_diagnostics=unavailable,
        recommendation=recommendation,
    )


def dump_t054_guardrailed_root_prior_repair_report_json(
    report: T054GuardrailedRootPriorRepairReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T054 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t054_guardrailed_root_prior_repair_report_json(
    stream: TextIO,
) -> T054GuardrailedRootPriorRepairReport:
    """Load and validate a current-schema T054 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T054 guardrailed repair report JSON") from exc
    return t054_guardrailed_root_prior_repair_report_from_dict(raw)


def t054_guardrailed_root_prior_repair_report_from_dict(
    raw: Mapping[str, Any],
) -> T054GuardrailedRootPriorRepairReport:
    """Validate a current-schema T054 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T054 guardrailed repair report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T054_REPAIR_REPORT_SCHEMA_ID:
        raise ValueError(
            f"unsupported T054 repair report schema_id {schema_id!r}; "
            f"expected {T054_REPAIR_REPORT_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T054_REPAIR_REPORT_FORMAT_VERSION:
        raise ValueError(
            "unsupported T054 repair report format_version "
            f"{format_version!r}; expected {T054_REPAIR_REPORT_FORMAT_VERSION}"
        )
    return T054GuardrailedRootPriorRepairReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        t052_comparison_summary=_require_mapping(
            raw.get("t052_comparison_summary"),
            "t052_comparison_summary",
        ),
        t052_result_summary=_require_mapping(
            raw.get("t052_result_summary"),
            "t052_result_summary",
        ),
        t053_reference_summary=_require_mapping(
            raw.get("t053_reference_summary"),
            "t053_reference_summary",
        ),
        t054_comparison_summary=_require_mapping(
            raw.get("t054_comparison_summary"),
            "t054_comparison_summary",
        ),
        guardrail_configuration=_require_mapping(
            raw.get("guardrail_configuration"),
            "guardrail_configuration",
        ),
        aggregate_outcome_comparison=_require_mapping(
            raw.get("aggregate_outcome_comparison"),
            "aggregate_outcome_comparison",
        ),
        subset_summaries=_require_mapping(
            raw.get("subset_summaries"), "subset_summaries"
        ),
        disagreement_index_results=_require_list_of_mappings(
            raw.get("disagreement_index_results"),
            "disagreement_index_results",
        ),
        allocation_telemetry_summary=_require_mapping(
            raw.get("allocation_telemetry_summary"),
            "allocation_telemetry_summary",
        ),
        unavailable_diagnostics=_require_list_of_mappings(
            raw.get("unavailable_diagnostics", []),
            "unavailable_diagnostics",
        ),
        recommendation=_require_mapping(raw.get("recommendation"), "recommendation"),
        validation_problems=_require_string_list(
            raw.get("validation_problems", []),
            "validation_problems",
        ),
        evidence_boundary=_require_mapping(
            raw.get("evidence_boundary", T054_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t054_guardrailed_root_prior_repair_report(
    report: T054GuardrailedRootPriorRepairReport,
) -> str:
    """Format concise T054 diagnostics for stderr and PR summaries."""

    aggregate = report.aggregate_outcome_comparison
    recommendation = report.recommendation
    lines = [
        "T054 guardrailed root-prior repair report",
        (
            "scope: restored-battle guardrail diagnostic only; no controller "
            "promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "cohort identity: "
            + str(report.t054_comparison_summary.get("cohort_identity", "missing"))
        ),
        (
            "evaluated records: "
            + str(report.t054_comparison_summary.get("evaluated_record_count", 0))
        ),
        "all-record guardrail outcome:",
        (
            "  vs existing root-prior: "
            + str(aggregate.get("guardrail_vs_root_prior", {}).get("status"))
            + " (delta="
            + _format_optional_number(
                aggregate.get("guardrail_vs_root_prior", {}).get("win_delta")
            )
            + ")"
        ),
        (
            "  vs baseline: "
            + str(aggregate.get("guardrail_vs_baseline", {}).get("status"))
            + " (delta="
            + _format_optional_number(
                aggregate.get("guardrail_vs_baseline", {}).get("win_delta")
            )
            + ")"
        ),
        (
            "  vs post-search: "
            + str(aggregate.get("guardrail_vs_post_search", {}).get("status"))
            + " (delta="
            + _format_optional_number(
                aggregate.get("guardrail_vs_post_search", {}).get("win_delta")
            )
            + ")"
        ),
        "subset records:",
    ]
    for name in ("t053_disagreement_indices", "boss_only", "act2_plus"):
        subset = report.subset_summaries.get(name, {})
        lines.append(
            "  "
            + name
            + ": records="
            + str(subset.get("record_count", 0))
            + ", guardrail="
            + _win_loss_text(
                subset.get("arm_outcomes", {}).get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
            )
            + ", root-prior="
            + _win_loss_text(
                subset.get("arm_outcomes", {}).get(ROOT_PRIOR_GUIDED_LABEL)
            )
        )
    lines.append("T053 disagreement indices:")
    for row in report.disagreement_index_results:
        lines.append(
            "  "
            + str(row.get("cohort_index"))
            + ": "
            + str(row.get("repair_classification"))
            + ", guardrail_vs_root="
            + str(row.get("guardrail_vs_root_prior", {}).get("status"))
        )
    lines.append(
        "recommended next task: "
        + str(recommendation.get("recommended_next_task", "missing"))
    )
    lines.append("unavailable diagnostics:")
    if report.unavailable_diagnostics:
        for item in report.unavailable_diagnostics:
            lines.append(
                f"  - {item.get('diagnostic', 'missing')}: "
                f"{item.get('reason', 'missing')}"
            )
    else:
        lines.append("  (none)")
    lines.append("validation problems:")
    if report.validation_problems:
        lines.extend(f"  - {problem}" for problem in report.validation_problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def build_t054_retention_manifest_payload(
    *,
    artifact_specs: Sequence[Mapping[str, Any]],
    command_specs: Sequence[Mapping[str, str]] = (),
    stage_specs: Sequence[Mapping[str, Any]] = (),
    note_items: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Build a lightweight T054 artifact retention manifest."""

    if not artifact_specs:
        raise ValueError("T054 retention manifest requires at least one artifact")
    return {
        "schema_id": T054_RETENTION_MANIFEST_SCHEMA_ID,
        "format_version": T054_RETENTION_MANIFEST_FORMAT_VERSION,
        "task_id": "T054",
        "evidence_boundary": dict(T054_EVIDENCE_BOUNDARY),
        "retention_reason": (
            "preserve T054 guardrailed repair comparison, report, logs, and "
            "review evidence for maintainer review and the exactly one "
            "recommended follow-up task"
        ),
        "downstream_consumers": [
            "main maintainer review of T054",
            "the exactly one follow-up task recommended in the T054 report",
        ],
        "deletion_conditions": (
            "raw local artifacts may be deleted after T054 review is complete "
            "and the maintainer has recorded any retained identities needed by "
            "the next task"
        ),
        "artifacts": [_json_safe_mapping(spec) for spec in artifact_specs],
        "commands": [_json_safe_mapping(spec) for spec in command_specs],
        "runtime_stages": [_json_safe_mapping(spec) for spec in stage_specs],
        "notes": {str(key): str(value) for key, value in note_items},
    }


def dump_t054_retention_manifest_json(
    payload: Mapping[str, Any], stream: TextIO
) -> None:
    """Write deterministic T054 retention manifest JSON."""

    json.dump(_json_safe_mapping(payload), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_t054_retention_manifest(payload: Mapping[str, Any]) -> str:
    """Format the T054 retention manifest for stderr."""

    artifacts = _sequence(payload.get("artifacts"))
    stages = _sequence(payload.get("runtime_stages"))
    lines = [
        "T054 retention manifest",
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
    t052_comparison: RootPriorGuidedSearchComparisonReport,
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_comparison: RootPriorGuidedSearchComparisonReport,
) -> list[str]:
    problems: list[str] = []
    roles = [str(item.get("role") or "") for item in input_artifacts]
    for role in T054_REQUIRED_INPUT_ROLES:
        if role not in roles:
            problems.append(f"missing required T054 input artifact role {role}")
    if len(set(roles)) != len(roles):
        problems.append("duplicate T054 input artifact roles")
    for artifact in input_artifacts:
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{artifact.get('role', 'artifact')}: sha256 not verified")

    if t052_comparison.cohort_identity != t054_comparison.cohort_identity:
        problems.append("T052 and T054 comparison cohort identities differ")
    if t052_comparison.source_match_problems:
        problems.append("T052 comparison source/cohort match status is not clean")
    if t054_comparison.source_match_problems:
        problems.append("T054 comparison source/cohort match status is not clean")
    if not t054_comparison.evaluation_successful:
        problems.extend(
            f"T054 comparison problem: {problem}"
            for problem in t054_comparison.problems
        )

    arms = _arms_by_label(t054_comparison)
    for label in T054_REQUIRED_COMPARISON_LABELS:
        if label not in arms:
            problems.append(f"missing required T054 comparison arm {label!r}")
    evaluated_count = _evaluated_record_count(t054_comparison)
    if evaluated_count != T054_EXPECTED_COHORT_RECORD_COUNT:
        problems.append(
            "T054 comparison evaluated record count mismatch: expected "
            f"{T054_EXPECTED_COHORT_RECORD_COUNT}, got {evaluated_count}"
        )
    if not _equal_configured_budget(t054_comparison):
        problems.append("T054 search arms do not share equal native root budget")

    t053_indices = {
        _as_int(record.get("cohort_index"))
        for record in t053_report.disagreement_records
    }
    for index in T054_REQUIRED_DISAGREEMENT_INDICES:
        if index not in t053_indices:
            problems.append(f"T053 report missing required disagreement index {index}")
        for label, arm in arms.items():
            if _result_by_index(arm.report, index) is None:
                problems.append(f"{label}: missing T053 disagreement index {index}")

    guardrail = arms.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
    if guardrail is not None:
        provenance = guardrail.report.controller_provenance
        config = _mapping(provenance.get("config"))
        if config.get("controller_version") != (
            GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
        ):
            problems.append("guardrailed arm has unexpected controller version")
        if GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME not in str(
            provenance.get("name", "")
        ):
            problems.append("guardrailed arm has unexpected controller name")
        telemetry = _guardrail_telemetry_summary(guardrail.report)
        if telemetry["decision_count"] == 0:
            problems.append("guardrailed arm has no root-prior decision telemetry")
        if telemetry["missing_guardrail_config_count"]:
            problems.append("guardrailed arm has missing guardrail config telemetry")
        if telemetry["missing_guardrail_summary_count"]:
            problems.append("guardrailed arm has missing guardrail summary telemetry")
        if telemetry["unexpected_guardrail_strategy_count"]:
            problems.append(
                "guardrailed arm has malformed guardrail strategy telemetry"
            )

    return list(dict.fromkeys(problems))


def _comparison_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    summaries = root_prior_guided_controller_summaries(report)
    return {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "evaluated_record_count": _evaluated_record_count(report),
        "record_range": report.comparison_config.get("record_range", "missing"),
        "worker_count": report.comparison_config.get("worker_count"),
        "shard_count": report.comparison_config.get("shard_count"),
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "evaluation_successful": report.evaluation_successful,
        "controller_summaries": _json_safe_mapping(summaries),
        "budget_summary": _json_safe_mapping(root_prior_guided_budget_summary(report)),
        "problems": list(report.problems),
    }


def _t053_reference_summary(
    report: T053RootPriorFailureAnalysisReport,
) -> dict[str, Any]:
    return {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "command_passed": report.command_passed,
        "disagreement_indices": [
            _as_int(record.get("cohort_index"))
            for record in report.disagreement_records
        ],
        "disagreement_summary": _json_safe_mapping(report.disagreement_summary),
        "failure_taxonomy": _json_safe_mapping(report.failure_taxonomy),
        "recommendation": _json_safe_mapping(report.recommendation),
    }


def _aggregate_outcome_comparison(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    arms = _arms_by_label(report)
    outcomes = {
        label: _outcome_counts(arm.report.battle_results)
        for label, arm in arms.items()
        if label in T054_REQUIRED_COMPARISON_LABELS
    }
    guardrail = outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL, {})
    root = outcomes.get(ROOT_PRIOR_GUIDED_LABEL, {})
    baseline = outcomes.get(BASELINE_ORACLE_LABEL, {})
    post = outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL, {})
    return {
        "metric": "authoritative_win_count",
        "arm_outcomes": outcomes,
        "guardrail_vs_root_prior": _aggregate_delta(guardrail, root),
        "guardrail_vs_baseline": _aggregate_delta(guardrail, baseline),
        "guardrail_vs_post_search": _aggregate_delta(guardrail, post),
        "promotion_boundary": (
            "diagnostic restored-battle result only; no controller-promotion claim"
        ),
    }


def _subset_summaries(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, dict[str, Any]]:
    return {
        "all_records": _subset_summary(report, None),
        "t053_disagreement_indices": _subset_summary(
            report,
            set(T054_REQUIRED_DISAGREEMENT_INDICES),
        ),
        "boss_only": _subset_summary(report, None, subset_label="boss_only"),
        "act2_plus": _subset_summary(report, None, subset_label="act2_plus"),
    }


def _subset_summary(
    report: RootPriorGuidedSearchComparisonReport,
    indices: set[int] | None,
    *,
    subset_label: str | None = None,
) -> dict[str, Any]:
    arms = _arms_by_label(report)
    selected_by_label: dict[str, list[SingleBattleEvaluationResult]] = {}
    selected_indices: set[int] = set()
    for label, arm in arms.items():
        values = []
        for result in arm.report.battle_results:
            if indices is not None and result.cohort_index not in indices:
                continue
            if subset_label is not None and _subset_label(result) != subset_label:
                continue
            values.append(result)
            selected_indices.add(result.cohort_index)
        selected_by_label[label] = values
    outcomes = {
        label: _outcome_counts(values)
        for label, values in selected_by_label.items()
        if label in T054_REQUIRED_COMPARISON_LABELS
    }
    guardrail = outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL, {})
    return {
        "record_count": len(selected_indices),
        "cohort_indices": sorted(selected_indices),
        "arm_outcomes": outcomes,
        "guardrail_vs_root_prior": _aggregate_delta(
            guardrail,
            outcomes.get(ROOT_PRIOR_GUIDED_LABEL, {}),
        ),
        "guardrail_vs_baseline": _aggregate_delta(
            guardrail,
            outcomes.get(BASELINE_ORACLE_LABEL, {}),
        ),
        "guardrail_vs_post_search": _aggregate_delta(
            guardrail,
            outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL, {}),
        ),
    }


def _disagreement_index_results(
    report: RootPriorGuidedSearchComparisonReport,
    t053_report: T053RootPriorFailureAnalysisReport,
) -> list[dict[str, Any]]:
    arms = _arms_by_label(report)
    t053_by_index = {
        _as_int(record.get("cohort_index")): record
        for record in t053_report.disagreement_records
    }
    rows: list[dict[str, Any]] = []
    for index in T054_REQUIRED_DISAGREEMENT_INDICES:
        results = {
            label: _result_by_index(arm.report, index)
            for label, arm in arms.items()
            if label in T054_REQUIRED_COMPARISON_LABELS
        }
        summaries = {
            label: _result_summary(result) for label, result in results.items()
        }
        guardrail = summaries.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL, {})
        root = summaries.get(ROOT_PRIOR_GUIDED_LABEL, {})
        baseline = summaries.get(BASELINE_ORACLE_LABEL, {})
        post = summaries.get(POST_SEARCH_MODEL_GUIDED_LABEL, {})
        row = {
            "cohort_index": index,
            "subset": _subset_label(
                results.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
                or results.get(ROOT_PRIOR_GUIDED_LABEL)
            ),
            "t053_taxonomy_labels": list(
                _sequence(t053_by_index.get(index, {}).get("taxonomy_labels"))
            ),
            "t053_outcome_delta": _json_safe_mapping(
                _mapping(t053_by_index.get(index, {}).get("outcome_delta"))
            ),
            "arms": summaries,
            "guardrail_vs_root_prior": _result_delta(guardrail, root),
            "guardrail_vs_baseline": _result_delta(guardrail, baseline),
            "guardrail_vs_post_search": _result_delta(guardrail, post),
            "repair_classification": _repair_classification(
                guardrail=guardrail,
                root=root,
                baseline=baseline,
                post=post,
            ),
            "root_prior_allocation": _allocation_for_result(
                results.get(ROOT_PRIOR_GUIDED_LABEL)
            ),
            "guardrailed_allocation": _allocation_for_result(
                results.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
            ),
        }
        rows.append(row)
    return rows


def _allocation_telemetry_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    arms = _arms_by_label(report)
    root = arms.get(ROOT_PRIOR_GUIDED_LABEL)
    guardrail = arms.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
    return {
        "root_prior_arm": (
            root_prior_allocation_summary(root.report) if root is not None else {}
        ),
        "guardrailed_arm": (
            root_prior_allocation_summary(guardrail.report)
            if guardrail is not None
            else {}
        ),
        "guardrail_telemetry": (
            _guardrail_telemetry_summary(guardrail.report)
            if guardrail is not None
            else {}
        ),
    }


def _guardrail_configuration(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    arm = _arms_by_label(report).get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
    if arm is None:
        return {}
    config = _mapping(arm.report.controller_provenance.get("config"))
    allocation = _mapping(config.get("root_prior_allocation"))
    return {
        "controller_name": arm.report.controller_provenance.get("name"),
        "controller_kind": arm.report.controller_provenance.get("kind"),
        "controller_version": config.get("controller_version"),
        "root_prior_allocation": _json_safe_mapping(allocation),
        "guardrail": _json_safe_mapping(_mapping(allocation.get("guardrail"))),
    }


def _guardrail_telemetry_summary(report: FixedEvaluationReport) -> dict[str, Any]:
    decision_count = 0
    missing_config = 0
    missing_summary = 0
    unexpected_strategy = 0
    changed_prior_count = 0
    l1_delta = 0.0
    strategy_counts: Counter[str] = Counter()
    version_counts: Counter[str] = Counter()
    max_pre: list[float] = []
    max_post: list[float] = []
    for result in report.battle_results:
        for decision in _decision_reports(result):
            decision_count += 1
            config = _mapping(decision.get("guardrail_config"))
            summary = _mapping(decision.get("guardrail_summary"))
            if not config:
                missing_config += 1
            if not summary:
                missing_summary += 1
            strategy = str(config.get("strategy") or "missing")
            version = str(config.get("version") or "missing")
            strategy_counts[strategy] += 1
            version_counts[version] += 1
            if strategy != ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY:
                unexpected_strategy += 1
            if version != ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION:
                unexpected_strategy += 1
            changed_prior_count += _as_int(summary.get("changed_prior_count"))
            l1_delta += _as_float(summary.get("l1_prior_delta")) or 0.0
            pre = _as_float(summary.get("pre_guardrail_max_prior_probability"))
            post = _as_float(summary.get("post_guardrail_max_prior_probability"))
            if pre is not None:
                max_pre.append(pre)
            if post is not None:
                max_post.append(post)
    return {
        "decision_count": decision_count,
        "missing_guardrail_config_count": missing_config,
        "missing_guardrail_summary_count": missing_summary,
        "unexpected_guardrail_strategy_count": unexpected_strategy,
        "changed_prior_count": changed_prior_count,
        "l1_prior_delta_total": l1_delta,
        "max_pre_guardrail_prior_probability": max(max_pre) if max_pre else None,
        "max_post_guardrail_prior_probability": max(max_post) if max_post else None,
        "guardrail_strategy_counts": dict(sorted(strategy_counts.items())),
        "guardrail_version_counts": dict(sorted(version_counts.items())),
    }


def _unavailable_diagnostics(
    report: RootPriorGuidedSearchComparisonReport,
    allocation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    unavailable = [
        {
            "diagnostic": "guardrail_causal_effect",
            "reason": (
                "T054 compares separate restored-battle arms but native telemetry "
                "does not expose a paired within-decision counterfactual tree"
            ),
        },
        {
            "diagnostic": "step_level_selected_action_equivalence",
            "reason": (
                "selected action identities are reported when present, but T052 "
                "already marked exact all-arm step-level comparison unavailable"
            ),
        },
    ]
    guardrail = _mapping(allocation.get("guardrail_telemetry"))
    if _as_int(guardrail.get("missing_guardrail_config_count")):
        unavailable.append(
            {
                "diagnostic": "guardrail_config",
                "reason": "one or more guardrail decisions lacked guardrail config",
            }
        )
    if report.problems:
        unavailable.append(
            {
                "diagnostic": "comparison_validation",
                "reason": "; ".join(report.problems),
            }
        )
    return unavailable


def _recommendation(
    *,
    aggregate: Mapping[str, Any],
    disagreement_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    status_vs_root = str(
        _mapping(aggregate.get("guardrail_vs_root_prior")).get("status")
    )
    classifications = {
        str(row.get("repair_classification")) for row in disagreement_rows
    }
    if (
        status_vs_root == "improved"
        and "worsened_vs_existing_root_prior" not in classifications
    ):
        next_task = "scale the repaired variant"
    elif status_vs_root == "regressed":
        next_task = "abandon the repair path"
    else:
        next_task = "run another diagnostic"
    return {
        "recommendation_count": 1,
        "recommended_next_task": next_task,
        "allowed_recommendation_set": [
            "scale the repaired variant",
            "run another diagnostic",
            "abandon the repair path",
            "publish a different blocked path",
        ],
        "reason": (
            "selected from T054 all-record result and T053 disagreement-index "
            "repair classifications without making a promotion claim"
        ),
        "forbidden_claims": {
            "controller_promotion": False,
            "live_game_strength": False,
            "natural_a20_performance": False,
            "broad_training_readiness": False,
            "normal_information_strength": False,
            "final_agent_status": False,
        },
    }


def _arms_by_label(report: RootPriorGuidedSearchComparisonReport) -> dict[str, Any]:
    return {arm.label: arm for arm in report.arms}


def _evaluated_record_count(report: RootPriorGuidedSearchComparisonReport) -> int:
    value = report.comparison_config.get("evaluated_record_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return max((arm.report.total_battles for arm in report.arms), default=0)


def _equal_configured_budget(report: RootPriorGuidedSearchComparisonReport) -> bool:
    budgets = []
    arms = _arms_by_label(report)
    for label in T054_REQUIRED_COMPARISON_LABELS:
        arm = arms.get(label)
        if arm is None:
            return False
        value = _configured_native_playouts(arm.report)
        if value is None:
            return False
        budgets.append(value)
    return len(set(budgets)) == 1


def _configured_native_playouts(report: FixedEvaluationReport) -> int | None:
    config = _mapping(report.controller_provenance.get("config"))
    budget = _mapping(config.get("search_budget"))
    value = budget.get("simulations")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _outcome_counts(
    results: Sequence[SingleBattleEvaluationResult],
) -> dict[str, Any]:
    return {
        "record_count": len(results),
        "authoritative_wins": sum(
            1 for result in results if result.termination_status == "win"
        ),
        "losses": sum(1 for result in results if result.termination_status == "loss"),
        "truncations": sum(
            1 for result in results if result.termination_status == "truncated"
        ),
        "errors": sum(1 for result in results if result.termination_status == "error"),
    }


def _aggregate_delta(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    left_wins = _as_int(left.get("authoritative_wins"))
    right_wins = _as_int(right.get("authoritative_wins"))
    delta = left_wins - right_wins
    return {
        "status": _delta_status(delta),
        "win_delta": delta,
        "left_wins": left_wins,
        "right_wins": right_wins,
    }


def _result_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_win = left.get("termination_status") == "win"
    right_win = right.get("termination_status") == "win"
    left_hp = _optional_int(left.get("terminal_absolute_hp"))
    right_hp = _optional_int(right.get("terminal_absolute_hp"))
    return {
        "status": _result_status(left_win, right_win),
        "terminal_status_delta": _result_status(left_win, right_win),
        "terminal_absolute_hp_delta": (
            None if left_hp is None or right_hp is None else left_hp - right_hp
        ),
    }


def _result_status(left_win: bool, right_win: bool) -> str:
    if left_win and not right_win:
        return "improved"
    if not left_win and right_win:
        return "regressed"
    return "tied"


def _delta_status(delta: int) -> str:
    if delta > 0:
        return "improved"
    if delta == 0:
        return "tied"
    return "regressed"


def _repair_classification(
    *,
    guardrail: Mapping[str, Any],
    root: Mapping[str, Any],
    baseline: Mapping[str, Any],
    post: Mapping[str, Any],
) -> str:
    if _outcome_signature(guardrail) == _outcome_signature(root):
        return "unchanged_vs_existing_root_prior"
    guard_vs_root = _result_delta(guardrail, root)["status"]
    if guard_vs_root == "regressed":
        return "worsened_vs_existing_root_prior"
    guard_vs_baseline = _result_delta(guardrail, baseline)["status"]
    guard_vs_post = _result_delta(guardrail, post)["status"]
    if (
        guard_vs_root == "improved"
        and guard_vs_baseline != "regressed"
        and guard_vs_post != "regressed"
    ):
        return "fixed_or_improved_vs_root_prior"
    return "changed_mixed"


def _outcome_signature(result: Mapping[str, Any]) -> tuple[Any, Any]:
    return result.get("termination_status"), result.get("terminal_absolute_hp")


def _result_summary(
    result: SingleBattleEvaluationResult | None,
) -> dict[str, Any]:
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
        "restore_status": _restore_status(result),
        "truncation_status": (
            "truncated" if result.termination_status == "truncated" else "none"
        ),
        "controller_problem_count": len(result.problems),
        "controller_problems": list(result.problems),
        "information_regime": result.information_regime,
        "public_context_status": result.public_context_status,
        "public_context_replay_status": result.public_context_replay_status,
        "structured_battle_outcome_status": result.structured_battle_outcome_status,
        "structured_resource_status": result.structured_battle_outcome_status,
    }


def _allocation_for_result(
    result: SingleBattleEvaluationResult | None,
) -> dict[str, Any]:
    if result is None:
        return {"decision_count": 0}
    reports = _decision_reports(result)
    if not reports:
        return {"decision_count": 0}
    selected_indices: Counter[str] = Counter()
    guardrail_changed = 0
    for decision in reports:
        target = _mapping(decision.get("target"))
        selected = target.get("legal_action_index")
        if isinstance(selected, int) and not isinstance(selected, bool):
            selected_indices[str(selected)] += 1
        summary = _mapping(decision.get("guardrail_summary"))
        guardrail_changed += _as_int(summary.get("changed_prior_count"))
    return {
        "decision_count": len(reports),
        "selected_index_counts": dict(sorted(selected_indices.items())),
        "guardrail_changed_prior_count": guardrail_changed,
    }


def _result_by_index(
    report: FixedEvaluationReport,
    index: int,
) -> SingleBattleEvaluationResult | None:
    for result in report.battle_results:
        if result.cohort_index == index:
            return result
    return None


def _decision_reports(result: SingleBattleEvaluationResult) -> list[dict[str, Any]]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    _collect_mapping_rows(telemetry.get("root_prior_guided_decision_reports"), rows)
    return rows


def _collect_mapping_rows(value: Any, rows: list[dict[str, Any]]) -> None:
    if isinstance(value, Mapping):
        rows.append({str(key): item for key, item in value.items()})
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _collect_mapping_rows(item, rows)


def _subset_label(result: SingleBattleEvaluationResult | None) -> str:
    if result is None:
        return "missing"
    metadata = result.structural_metadata
    act = _optional_int(metadata.get("act"))
    if act is not None and act >= 2:
        return "act2_plus"
    room_type = str(metadata.get("room_type") or "").lower()
    if "boss" in room_type:
        return "boss_only"
    reasons = {
        str(item).lower() for item in _sequence(metadata.get("t052_selection_reasons"))
    }
    if "act2_plus" in reasons:
        return "act2_plus"
    if "act1_boss" in reasons:
        return "boss_only"
    return "other"


def _restore_status(result: SingleBattleEvaluationResult) -> str:
    if result.termination_status == "error":
        return "error"
    if result.restoration_method:
        return "restored"
    return "unavailable"


def _win_loss_text(value: Any) -> str:
    mapping = _mapping(value)
    if not mapping:
        return "missing"
    return (
        f"{_as_int(mapping.get('authoritative_wins'))}W/"
        f"{_as_int(mapping.get('losses'))}L"
    )


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_number(value: Any) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    converted = float(value)
    if converted.is_integer():
        return str(int(converted))
    return f"{converted:.3f}"


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_int(value: Any) -> int:
    parsed = _optional_int(value)
    return 0 if parsed is None else parsed


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


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


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    return str(value)
