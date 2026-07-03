"""Offline T056 synthesis after the T055 guardrail scale result.

This module consumes retained T048/T050/T051/T052/T053/T054/T055 evidence.
It does not run the simulator, change a controller, train a checkpoint, or
promote any search policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.fixed_battle_evaluation import (
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    RootPriorGuidedSearchComparisonReport,
    root_prior_allocation_summary,
    root_prior_guided_budget_summary,
    root_prior_guided_controller_summaries,
    root_prior_guided_source_distribution_summary,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053RootPriorFailureAnalysisReport,
)
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    T054GuardrailedRootPriorRepairReport,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055GuardrailedRootPriorScaleValidationReport,
)


T056_PATH_SELECTION_REPORT_SCHEMA_ID = (
    "t056-post-t055-root-prior-path-selection-report-v1"
)
T056_PATH_SELECTION_REPORT_FORMAT_VERSION = 1
T056_REQUIRED_INPUT_ROLES = (
    "t055_scale_validation_report",
    "t055_retention_manifest",
    "t055_current_guardrailed_comparison",
    "t055_assist0_guardrailed_comparison",
    "t048_current_reference_comparison",
    "t048_assist0_reference_comparison",
    "t052_result_summary",
    "t053_failure_analysis_report",
    "t054_guardrailed_repair_report",
    "t050_reachability_report",
    "t050_retention_manifest",
    "t051_reachability_report",
    "t051_retention_manifest",
)
T056_EXPECTED_JSON_SCHEMAS = {
    "t055_scale_validation_report": (
        "t055-guardrailed-root-prior-scale-validation-report-v1"
    ),
    "t055_retention_manifest": "t055-retention-manifest-v1",
    "t053_failure_analysis_report": "t053-root-prior-allocation-failure-analysis-v1",
    "t054_guardrailed_repair_report": "t054-guardrailed-root-prior-repair-report-v1",
    "t050_reachability_report": "a20-search-controlled-reachability-report-v1",
    "t050_retention_manifest": ("t050-root-prior-reachability-retention-manifest-v1"),
    "t051_reachability_report": "a20-search-controlled-reachability-report-v1",
    "t051_retention_manifest": (
        "t051-search-controlled-later-act-retention-manifest-v1"
    ),
}
T056_COMPARISON_CONTRACTS: dict[str, dict[str, Any]] = {
    "t048_current_reference_comparison": {
        "task_id": "T048",
        "cohort_key": "current_t046_full8",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
        ),
        "require_guardrail": False,
    },
    "t048_assist0_reference_comparison": {
        "task_id": "T048",
        "cohort_key": "assist0_runs1000_full21",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
        ),
        "require_guardrail": False,
    },
    "t055_current_guardrailed_comparison": {
        "task_id": "T055",
        "cohort_key": "current_t046_full8",
        "cohort_identity": "875ea52e3df4cb93",
        "record_count": 8,
        "record_range": "0:8",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
        ),
        "require_guardrail": True,
    },
    "t055_assist0_guardrailed_comparison": {
        "task_id": "T055",
        "cohort_key": "assist0_runs1000_full21",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_count": 21,
        "record_range": "0:21",
        "required_labels": (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
        ),
        "require_guardrail": True,
    },
}
T056_EVIDENCE_BOUNDARY = {
    "task_id": "T056",
    "scope": "offline post-T055 path-selection synthesis",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}
T056_SELECTED_NEXT_PATH = "existing-root-prior allocation/telemetry diagnostic"


@dataclass(frozen=True)
class T056PostT055RootPriorPathSelectionReport:
    """Versioned T056 synthesis report assembled from retained artifacts."""

    input_artifacts: list[dict[str, Any]]
    evidence_ledger: dict[str, Any]
    guardrail_branch_closure: dict[str, Any]
    recommendation: dict[str, Any]
    rejected_alternatives: list[dict[str, Any]]
    unavailable_diagnostics: list[dict[str, Any]]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T056_PATH_SELECTION_REPORT_SCHEMA_ID
    format_version: int = T056_PATH_SELECTION_REPORT_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T056_EVIDENCE_BOUNDARY)
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
            "evidence_ledger": _json_safe_value(self.evidence_ledger),
            "guardrail_branch_closure": _json_safe_value(self.guardrail_branch_closure),
            "recommendation": _json_safe_value(self.recommendation),
            "rejected_alternatives": _json_safe_value(self.rejected_alternatives),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def build_t056_post_t055_root_prior_path_selection_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t048_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_report: T054GuardrailedRootPriorRepairReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
    t055_retention_manifest: Mapping[str, Any],
    t050_reachability_report: Mapping[str, Any],
    t050_retention_manifest: Mapping[str, Any],
    t051_reachability_report: Mapping[str, Any],
    t051_retention_manifest: Mapping[str, Any],
) -> T056PostT055RootPriorPathSelectionReport:
    """Build and validate the T056 path-selection report."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    json_inputs = {
        "t052_result_summary": _json_safe_mapping(t052_result_summary),
        "t055_retention_manifest": _json_safe_mapping(t055_retention_manifest),
        "t050_reachability_report": _json_safe_mapping(t050_reachability_report),
        "t050_retention_manifest": _json_safe_mapping(t050_retention_manifest),
        "t051_reachability_report": _json_safe_mapping(t051_reachability_report),
        "t051_retention_manifest": _json_safe_mapping(t051_retention_manifest),
    }
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        t048_comparisons=t048_comparisons,
        t055_comparisons=t055_comparisons,
        t052_result_summary=json_inputs["t052_result_summary"],
        t053_report=t053_report,
        t054_report=t054_report,
        t055_report=t055_report,
        t055_retention_manifest=json_inputs["t055_retention_manifest"],
        t050_reachability_report=json_inputs["t050_reachability_report"],
        t050_retention_manifest=json_inputs["t050_retention_manifest"],
        t051_reachability_report=json_inputs["t051_reachability_report"],
        t051_retention_manifest=json_inputs["t051_retention_manifest"],
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    evidence_ledger = _evidence_ledger(
        t048_comparisons=t048_comparisons,
        t055_comparisons=t055_comparisons,
        t052_result_summary=json_inputs["t052_result_summary"],
        t053_report=t053_report,
        t054_report=t054_report,
        t055_report=t055_report,
        t055_retention_manifest=json_inputs["t055_retention_manifest"],
        t050_reachability_report=json_inputs["t050_reachability_report"],
        t050_retention_manifest=json_inputs["t050_retention_manifest"],
        t051_reachability_report=json_inputs["t051_reachability_report"],
        t051_retention_manifest=json_inputs["t051_retention_manifest"],
    )
    closure = _guardrail_branch_closure(t055_report)
    recommendation = _recommendation(evidence_ledger, closure)
    return T056PostT055RootPriorPathSelectionReport(
        input_artifacts=artifacts,
        evidence_ledger=evidence_ledger,
        guardrail_branch_closure=closure,
        recommendation=recommendation,
        rejected_alternatives=_rejected_alternatives(),
        unavailable_diagnostics=_unavailable_diagnostics(
            t053_report=t053_report,
            t054_report=t054_report,
            t055_report=t055_report,
        ),
    )


def dump_t056_post_t055_root_prior_path_selection_report_json(
    report: T056PostT055RootPriorPathSelectionReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T056 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t056_post_t055_root_prior_path_selection_report_json(
    stream: TextIO,
) -> T056PostT055RootPriorPathSelectionReport:
    """Load and validate a current-schema T056 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T056 path-selection report JSON") from exc
    return t056_post_t055_root_prior_path_selection_report_from_dict(raw)


def t056_post_t055_root_prior_path_selection_report_from_dict(
    raw: Mapping[str, Any],
) -> T056PostT055RootPriorPathSelectionReport:
    """Validate a current-schema T056 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T056 path-selection report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T056_PATH_SELECTION_REPORT_SCHEMA_ID:
        raise ValueError(
            f"unsupported T056 path-selection schema_id {schema_id!r}; "
            f"expected {T056_PATH_SELECTION_REPORT_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T056_PATH_SELECTION_REPORT_FORMAT_VERSION:
        raise ValueError(
            "unsupported T056 path-selection format_version "
            f"{format_version!r}; expected "
            f"{T056_PATH_SELECTION_REPORT_FORMAT_VERSION}"
        )
    return T056PostT055RootPriorPathSelectionReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        evidence_ledger=_require_mapping(
            raw.get("evidence_ledger"),
            "evidence_ledger",
        ),
        guardrail_branch_closure=_require_mapping(
            raw.get("guardrail_branch_closure"),
            "guardrail_branch_closure",
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
            raw.get("evidence_boundary", T056_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t056_post_t055_root_prior_path_selection_report(
    report: T056PostT055RootPriorPathSelectionReport,
) -> str:
    """Format concise T056 diagnostics for stderr and PR summaries."""

    ledger = report.evidence_ledger
    t048 = _mapping(ledger.get("positive_t048_fixed_cohort_root_prior_signal"))
    t055 = _mapping(ledger.get("t055_guardrail_scale_validation_regression"))
    reachability = _mapping(ledger.get("t050_t051_complete_run_reachability"))
    recommendation = report.recommendation
    lines = [
        "T056 post-T055 root-prior path-selection report",
        (
            "scope: offline synthesis only; no simulator, training, controller "
            "promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        "guardrail branch closed: "
        + _yes_no(bool(report.guardrail_branch_closure.get("closed_for_now"))),
        (
            "T055 recommendation: "
            + str(report.guardrail_branch_closure.get("exact_t055_recommendation"))
        ),
        (
            "T048 retained-cohort root-prior aggregate: "
            + _format_arm_wins(_mapping(t048.get("aggregate_outcomes")))
        ),
        (
            "T055 guardrail scale aggregate: "
            + str(
                _mapping(t055.get("aggregate_summary")).get(
                    "t048_advantage_status",
                    "missing",
                )
            )
        ),
        (
            "reachability status: best later-act arm="
            + str(reachability.get("t051_best_later_act_arm", "missing"))
            + ", broad training allowed any arm="
            + _yes_no(bool(reachability.get("broad_training_allowed_any_arm")))
        ),
        (
            "selected next path: "
            + str(recommendation.get("selected_next_path", "missing"))
        ),
        "rejected alternatives:",
    ]
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
    t048_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_report: T054GuardrailedRootPriorRepairReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
    t055_retention_manifest: Mapping[str, Any],
    t050_reachability_report: Mapping[str, Any],
    t050_retention_manifest: Mapping[str, Any],
    t051_reachability_report: Mapping[str, Any],
    t051_retention_manifest: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    roles = [str(item.get("role") or "") for item in input_artifacts]
    for role in T056_REQUIRED_INPUT_ROLES:
        if role not in roles:
            problems.append(f"missing required T056 input artifact role {role}")
    if len(set(roles)) != len(roles):
        problems.append("duplicate T056 input artifact roles")
    for artifact in input_artifacts:
        role = str(artifact.get("role") or "artifact")
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{role}: sha256 not verified")
        expected_schema = T056_EXPECTED_JSON_SCHEMAS.get(role)
        if expected_schema is None:
            continue
        detected = artifact.get("detected_schema_id")
        if detected not in {expected_schema, None, "unavailable"}:
            problems.append(
                f"{role}: detected schema_id {detected!r} is not {expected_schema!r}"
            )

    for role, report in t048_comparisons.items():
        _extend_comparison_problems(
            problems,
            role=role,
            report=report,
            contract=T056_COMPARISON_CONTRACTS[role],
        )
    for role, report in t055_comparisons.items():
        _extend_comparison_problems(
            problems,
            role=role,
            report=report,
            contract=T056_COMPARISON_CONTRACTS[role],
        )

    _extend_t052_result_summary_problems(problems, t052_result_summary)
    _extend_loaded_report_problems(
        problems,
        label="T053 failure-analysis report",
        command_passed=t053_report.command_passed,
        recommendation=t053_report.recommendation,
        expected_recommendation="guardrailed root-prior allocation repair experiment",
    )
    _extend_loaded_report_problems(
        problems,
        label="T054 guardrail repair report",
        command_passed=t054_report.command_passed,
        recommendation=t054_report.recommendation,
        expected_recommendation="scale the repaired variant",
    )
    _extend_loaded_report_problems(
        problems,
        label="T055 guardrail scale-validation report",
        command_passed=t055_report.command_passed,
        recommendation=t055_report.recommendation,
        expected_recommendation="abandon the guardrail path",
    )
    _extend_t055_retention_manifest_problems(
        problems,
        manifest=t055_retention_manifest,
    )

    _extend_reachability_problems(
        problems,
        role="t050_reachability_report",
        report=t050_reachability_report,
        expected_followup_hint="broader_search_controlled_source_collection_before_t032",
    )
    _extend_reachability_problems(
        problems,
        role="t051_reachability_report",
        report=t051_reachability_report,
        expected_followup_hint="broader_search_controlled_source_collection",
    )
    _extend_retention_manifest_problems(
        problems,
        role="t050_retention_manifest",
        manifest=t050_retention_manifest,
    )
    _extend_retention_manifest_problems(
        problems,
        role="t051_retention_manifest",
        manifest=t051_retention_manifest,
    )
    return list(dict.fromkeys(problems))


def _extend_comparison_problems(
    problems: list[str],
    *,
    role: str,
    report: RootPriorGuidedSearchComparisonReport,
    contract: Mapping[str, Any],
) -> None:
    if report.schema_id != "root-prior-guided-search-comparison-v1":
        problems.append(f"{role}: unsupported comparison schema {report.schema_id!r}")
    if report.format_version != 1:
        problems.append(f"{role}: unsupported comparison format version")
    if report.comparison_config.get("task_id") != contract["task_id"]:
        problems.append(f"{role}: task_id is not {contract['task_id']}")
    if report.cohort_identity != contract["cohort_identity"]:
        problems.append(f"{role}: cohort identity mismatch")
    if _evaluated_record_count(report) != contract["record_count"]:
        problems.append(f"{role}: evaluated record count mismatch")
    if str(report.comparison_config.get("record_range")) != contract["record_range"]:
        problems.append(f"{role}: record range mismatch")
    labels = {arm.label for arm in report.arms}
    for label in contract["required_labels"]:
        if label not in labels:
            problems.append(f"{role}: missing required arm {label!r}")
    if (
        contract["require_guardrail"]
        and GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL not in labels
    ):
        problems.append(f"{role}: missing guardrailed root-prior arm")
    if report.source_match_problems:
        problems.append(f"{role}: source/cohort mismatch")
    if not report.evaluation_successful:
        problems.append(f"{role}: comparison did not pass")
    regimes = {
        result.information_regime
        for arm in report.arms
        for result in arm.report.battle_results
        if result.information_regime
    }
    regimes.update(
        arm.report.information_regime
        for arm in report.arms
        if arm.report.information_regime
    )
    if regimes != {NATIVE_SEARCH_INFORMATION_REGIME}:
        problems.append(f"{role}: mixed or non-native information regimes")


def _extend_t052_result_summary_problems(
    problems: list[str],
    summary: Mapping[str, Any],
) -> None:
    required_sections = ("overall", "boss_only", "act2_plus", "comparison_config")
    for section in required_sections:
        if not isinstance(summary.get(section), Mapping):
            problems.append(f"T052 result summary missing {section}")
    config = _mapping(summary.get("comparison_config"))
    if config.get("task_id") != "T052":
        problems.append("T052 result summary task_id is not T052")
    if config.get("evaluated_record_count") != 93:
        problems.append("T052 result summary evaluated record count is not 93")
    if summary.get("evaluation_successful") is not True:
        problems.append("T052 result summary was not successful")
    if summary.get("problems") not in ([], (), None):
        problems.append("T052 result summary has problems")


def _extend_loaded_report_problems(
    problems: list[str],
    *,
    label: str,
    command_passed: bool,
    recommendation: Mapping[str, Any],
    expected_recommendation: str,
) -> None:
    if not command_passed:
        problems.append(f"{label} did not pass")
    if recommendation.get("recommendation_count") != 1:
        problems.append(f"{label} does not contain exactly one recommendation")
    if recommendation.get("recommended_next_task") != expected_recommendation:
        problems.append(f"{label} recommendation is not {expected_recommendation!r}")


def _extend_reachability_problems(
    problems: list[str],
    *,
    role: str,
    report: Mapping[str, Any],
    expected_followup_hint: str,
) -> None:
    if report.get("schema_id") != "a20-search-controlled-reachability-report-v1":
        problems.append(f"{role}: unsupported reachability schema")
    if report.get("format_version") != 1:
        problems.append(f"{role}: unsupported reachability format version")
    if report.get("command_passed") is not True:
        problems.append(f"{role}: command did not pass")
    if report.get("command_problems") not in ([], (), None):
        problems.append(f"{role}: command problems are present")
    if report.get("followup_hint") != expected_followup_hint:
        problems.append(f"{role}: unexpected followup hint")
    arms = report.get("arms")
    if not isinstance(arms, list) or not arms:
        problems.append(f"{role}: missing reachability arms")
    comparison = _mapping(report.get("comparison"))
    if comparison.get("broad_training_allowed_any_arm") is not False:
        problems.append(f"{role}: broad-training gate status is not closed")


def _extend_retention_manifest_problems(
    problems: list[str],
    *,
    role: str,
    manifest: Mapping[str, Any],
) -> None:
    expected_schema = T056_EXPECTED_JSON_SCHEMAS[role]
    if manifest.get("schema_id") != expected_schema:
        problems.append(f"{role}: unsupported retention manifest schema")
    if not manifest.get("retention_path"):
        problems.append(f"{role}: missing retention_path")
    if "regeneration" not in manifest:
        problems.append(f"{role}: missing regeneration contract")


def _extend_t055_retention_manifest_problems(
    problems: list[str],
    *,
    manifest: Mapping[str, Any],
) -> None:
    if manifest.get("schema_id") != "t055-retention-manifest-v1":
        problems.append(
            "t055_retention_manifest: unsupported retention manifest schema"
        )
    if manifest.get("format_version") != 1:
        problems.append("t055_retention_manifest: unsupported format version")
    if manifest.get("task_id") != "T055":
        problems.append("t055_retention_manifest: task_id is not T055")
    if not isinstance(manifest.get("artifacts"), list) or not manifest.get("artifacts"):
        problems.append("t055_retention_manifest: missing retained artifact list")
    if not isinstance(manifest.get("commands"), list) or not manifest.get("commands"):
        problems.append("t055_retention_manifest: missing command list")
    if not isinstance(manifest.get("runtime_stages"), list) or not manifest.get(
        "runtime_stages"
    ):
        problems.append("t055_retention_manifest: missing runtime stage list")
    if not manifest.get("retention_reason"):
        problems.append("t055_retention_manifest: missing retention_reason")


def _evidence_ledger(
    *,
    t048_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t052_result_summary: Mapping[str, Any],
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_report: T054GuardrailedRootPriorRepairReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
    t055_retention_manifest: Mapping[str, Any],
    t050_reachability_report: Mapping[str, Any],
    t050_retention_manifest: Mapping[str, Any],
    t051_reachability_report: Mapping[str, Any],
    t051_retention_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    t048_summaries = [
        _comparison_summary(role, report)
        for role, report in sorted(t048_comparisons.items())
    ]
    t055_comparison_summaries = [
        _comparison_summary(role, report)
        for role, report in sorted(t055_comparisons.items())
    ]
    t050_summary = _reachability_summary(
        task_id="T050",
        report=t050_reachability_report,
        manifest=t050_retention_manifest,
    )
    t051_summary = _reachability_summary(
        task_id="T051",
        report=t051_reachability_report,
        manifest=t051_retention_manifest,
    )
    return {
        "positive_t048_fixed_cohort_root_prior_signal": {
            "evidence_family": (
                "positive T048 fixed-cohort restored-battle root-prior signal"
            ),
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "not_natural_a20_performance": True,
            "cohort_summaries": t048_summaries,
            "aggregate_outcomes": _aggregate_outcomes(
                t048_summaries,
                (
                    BASELINE_ORACLE_LABEL,
                    POST_SEARCH_MODEL_GUIDED_LABEL,
                    ROOT_PRIOR_GUIDED_LABEL,
                ),
            ),
            "interpretation": (
                "existing root-prior remains the positive restored-battle "
                "signal on the retained T048 cohorts"
            ),
        },
        "t052_t053_later_act_boss_diagnostic_signal": {
            "evidence_family": (
                "negative T052 Boss/later-act restored-battle diagnostic plus "
                "T053 disagreement taxonomy"
            ),
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "t052_outcomes": {
                "overall": _t052_outcomes(t052_result_summary.get("overall")),
                "boss_only": _t052_outcomes(t052_result_summary.get("boss_only")),
                "act2_plus": _t052_outcomes(t052_result_summary.get("act2_plus")),
            },
            "t052_comparison_config": _json_safe_mapping(
                _mapping(t052_result_summary.get("comparison_config"))
            ),
            "t053_disagreement_summary": _json_safe_mapping(
                t053_report.disagreement_summary
            ),
            "t053_failure_taxonomy": _json_safe_mapping(t053_report.failure_taxonomy),
            "t053_action_comparison_diagnostics": _json_safe_mapping(
                t053_report.action_comparison_diagnostics
            ),
            "t053_recommendation": _json_safe_mapping(t053_report.recommendation),
            "interpretation": (
                "T052/T053 leave the existing root-prior signal unresolved on "
                "Boss/later-act records and mark exact selected-action "
                "comparison unavailable"
            ),
        },
        "t054_guardrail_repair_result": {
            "evidence_family": "bounded T054 guardrail repair result",
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "aggregate_outcome_comparison": _json_safe_mapping(
                t054_report.aggregate_outcome_comparison
            ),
            "subset_summaries": _json_safe_mapping(t054_report.subset_summaries),
            "recommendation": _json_safe_mapping(t054_report.recommendation),
            "interpretation": (
                "the guardrail repaired T052 overall/Boss-only regression "
                "against existing root-prior but did not close the Act-2+ gap"
            ),
        },
        "t055_guardrail_scale_validation_regression": {
            "evidence_family": (
                "T055 retained T048 guardrail scale-validation regression"
            ),
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "aggregate_summary": _json_safe_mapping(t055_report.aggregate_summary),
            "cohort_summaries": _json_safe_value(t055_report.cohort_summaries),
            "comparison_summaries": t055_comparison_summaries,
            "exact_t055_recommendation": (
                t055_report.recommendation.get("recommended_next_task")
            ),
            "recommendation": _json_safe_mapping(t055_report.recommendation),
            "retention_manifest": {
                "schema_id": t055_retention_manifest.get("schema_id"),
                "format_version": t055_retention_manifest.get("format_version"),
                "task_id": t055_retention_manifest.get("task_id"),
                "artifact_count": len(
                    _sequence(t055_retention_manifest.get("artifacts"))
                ),
                "command_count": len(
                    _sequence(t055_retention_manifest.get("commands"))
                ),
                "runtime_stage_count": len(
                    _sequence(t055_retention_manifest.get("runtime_stages"))
                ),
                "retention_reason": t055_retention_manifest.get("retention_reason"),
            },
            "interpretation": (
                "T055's exactly one recommendation is to abandon the guardrail "
                "path after a one-win aggregate regression versus existing "
                "root-prior"
            ),
        },
        "t050_t051_complete_run_reachability": {
            "evidence_family": (
                "T050/T051 complete-run source reachability and broad-training "
                "gate status"
            ),
            "t050": t050_summary,
            "t051": t051_summary,
            "t051_best_later_act_arm": _mapping(
                t051_reachability_report.get("comparison")
            ).get("best_later_act_arm"),
            "broad_training_allowed_any_arm": bool(
                _mapping(t050_reachability_report.get("comparison")).get(
                    "broad_training_allowed_any_arm"
                )
                or _mapping(t051_reachability_report.get("comparison")).get(
                    "broad_training_allowed_any_arm"
                )
            ),
            "interpretation": (
                "complete-run reachability recovered scarce later-act starts in "
                "T051 but kept broad training closed"
            ),
        },
    }


def _guardrail_branch_closure(
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> dict[str, Any]:
    return {
        "closed_for_now": True,
        "closed_branch": "T054/T055 guardrailed root-prior allocation",
        "exact_t055_recommendation": t055_report.recommendation.get(
            "recommended_next_task"
        ),
        "guardrailed_root_prior_complete_run_reachability_next": False,
        "another_guardrail_tuning_pass_next": False,
        "controller_promotion_next": False,
        "reason": (
            "T055 regressed by one win versus existing root-prior on the "
            "assist_0 retained cohort and aggregate, so the guardrail branch "
            "is closed for now"
        ),
    }


def _recommendation(
    evidence_ledger: Mapping[str, Any],
    closure: Mapping[str, Any],
) -> dict[str, Any]:
    t052_t053 = _mapping(
        evidence_ledger.get("t052_t053_later_act_boss_diagnostic_signal")
    )
    t053_action = _mapping(t052_t053.get("t053_action_comparison_diagnostics"))
    return {
        "recommendation_count": 1,
        "selected_next_path": T056_SELECTED_NEXT_PATH,
        "recommended_next_task": T056_SELECTED_NEXT_PATH,
        "allowed_recommendation_set": [
            "existing-root-prior allocation or telemetry diagnostic",
            "assisted/de-assisted checkpoint, teacher, or distribution-repair diagnostic",
            "source-generation, reachability, or non-combat-driver branch",
            "publish a blocked path requiring maintainer decision",
        ],
        "reason": (
            "the existing root-prior arm still has the positive retained T048 "
            "signal, the guardrail branch is closed, later-act/Boss evidence "
            "is conflicting, and exact selected-action/allocation diagnostics "
            "remain unavailable"
        ),
        "evidence_support": {
            "positive_t048_signal_preserved_for_existing_root_prior": True,
            "guardrail_branch_closed": bool(closure.get("closed_for_now")),
            "t052_t053_later_act_boss_conflict_requires_diagnosis": True,
            "exact_selected_action_comparison_available": (
                t053_action.get("exact_step_level_matching_record_count")
                not in {0, None}
            ),
            "broad_training_still_closed": True,
        },
        "not_recommended_next_branches": [
            "guardrailed root-prior complete-run reachability",
            "another guardrail tuning pass",
            "controller promotion or default-controller replacement",
            "broad teacher/checkpoint refresh",
            "live-game validation",
            "normal-information belief search",
        ],
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
            "path": (
                "assisted/de-assisted checkpoint, teacher, or "
                "distribution-repair diagnostic"
            ),
            "reason": (
                "T055 closes a root-prior guardrail branch, while the immediate "
                "missing evidence is exact existing-root-prior allocation and "
                "selected-action diagnostics"
            ),
        },
        {
            "path": "source-generation, reachability, or non-combat-driver branch",
            "reason": (
                "T050/T051 reachability remains useful context, but broad "
                "training is still closed and T056 must first select a "
                "non-guardrail diagnostic path"
            ),
        },
        {
            "path": "publish a blocked path requiring maintainer decision",
            "reason": (
                "the retained artifacts are sufficient to choose one "
                "implementation path without blocking on a new maintainer "
                "decision"
            ),
        },
        {
            "path": "guardrailed root-prior complete-run reachability",
            "reason": (
                "explicitly rejected because T055's exact recommendation is to "
                "abandon the guardrail path"
            ),
        },
    ]


def _unavailable_diagnostics(
    *,
    t053_report: T053RootPriorFailureAnalysisReport,
    t054_report: T054GuardrailedRootPriorRepairReport,
    t055_report: T055GuardrailedRootPriorScaleValidationReport,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        _json_safe_mapping(item) for item in t053_report.unavailable_diagnostics
    )
    rows.extend(
        _json_safe_mapping(item) for item in t054_report.unavailable_diagnostics
    )
    rows.extend(
        _json_safe_mapping(item) for item in t055_report.unavailable_diagnostics
    )
    rows.append(
        {
            "diagnostic": "normal_information_strength",
            "reason": (
                "T048/T052/T054/T055 search evidence remains "
                f"{NATIVE_SEARCH_INFORMATION_REGIME}"
            ),
        }
    )
    return _dedupe_unavailable(rows)


def _comparison_summary(
    role: str,
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    outcomes = _arm_outcomes(report)
    return {
        "role": role,
        "task_id": report.comparison_config.get("task_id"),
        "cohort_key": T056_COMPARISON_CONTRACTS[role]["cohort_key"],
        "cohort_identity": report.cohort_identity,
        "run_scale": report.run_scale,
        "record_range": report.comparison_config.get("record_range"),
        "evaluated_record_count": _evaluated_record_count(report),
        "worker_count": report.comparison_config.get("worker_count"),
        "shard_count": report.comparison_config.get("shard_count"),
        "source_match_status": (
            "matched" if not report.source_match_problems else "mismatch"
        ),
        "evaluation_successful": report.evaluation_successful,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "arm_outcomes": outcomes,
        "root_prior_vs_baseline": _outcome_delta(
            _mapping(outcomes.get(ROOT_PRIOR_GUIDED_LABEL)),
            _mapping(outcomes.get(BASELINE_ORACLE_LABEL)),
        ),
        "root_prior_vs_post_search": _outcome_delta(
            _mapping(outcomes.get(ROOT_PRIOR_GUIDED_LABEL)),
            _mapping(outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL)),
        ),
        "guardrail_vs_existing_root_prior": (
            _outcome_delta(
                _mapping(outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)),
                _mapping(outcomes.get(ROOT_PRIOR_GUIDED_LABEL)),
            )
            if GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL in outcomes
            else {"status": "not_applicable"}
        ),
        "budget_summary": _json_safe_mapping(root_prior_guided_budget_summary(report)),
        "source_distribution_summary": _json_safe_mapping(
            root_prior_guided_source_distribution_summary(report)
        ),
        "controller_summaries": _json_safe_mapping(
            root_prior_guided_controller_summaries(report)
        ),
        "root_prior_allocation_summary": _root_prior_allocation_summary(report),
        "problems": list(report.problems),
    }


def _reachability_summary(
    *,
    task_id: str,
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    comparison = _mapping(report.get("comparison"))
    arms = [_reachability_arm_summary(item) for item in _sequence(report.get("arms"))]
    return {
        "task_id": task_id,
        "schema_id": report.get("schema_id"),
        "format_version": report.get("format_version"),
        "command_passed": report.get("command_passed"),
        "followup_hint": report.get("followup_hint"),
        "comparison": _json_safe_mapping(comparison),
        "arm_summaries": arms,
        "retention_manifest": {
            "schema_id": manifest.get("schema_id"),
            "retention_path": manifest.get("retention_path"),
            "retention_reason": manifest.get("retention_reason"),
        },
    }


def _reachability_arm_summary(value: Any) -> dict[str, Any]:
    arm = _mapping(value)
    gate = _mapping(arm.get("training_gate_report"))
    return {
        "label": arm.get("label"),
        "source_run_count": arm.get("source_run_count"),
        "terminal_run_count": arm.get("terminal_run_count"),
        "natural_battle_start_count": arm.get("natural_battle_start_count"),
        "boss_battle_start_count": arm.get("boss_battle_start_count"),
        "act1_boss_battle_start_count": arm.get("act1_boss_battle_start_count"),
        "later_act_battle_start_count": arm.get("later_act_battle_start_count"),
        "boss_source_run_count": arm.get("boss_source_run_count"),
        "later_act_source_run_count": arm.get("later_act_source_run_count"),
        "broad_training_allowed": bool(
            gate.get("broad_training_allowed") or gate.get("training_allowed")
        ),
        "observed_act_counts": _json_safe_mapping(
            _mapping(gate.get("observed_act_counts"))
        ),
        "training_gate_problem_count": len(_sequence(gate.get("problems"))),
        "problems": _json_safe_value(_sequence(arm.get("problems"))),
    }


def _t052_outcomes(value: Any) -> dict[str, Any]:
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
        for label in (
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
        )
        if isinstance(section.get(label), Mapping)
    }


def _arm_outcomes(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, dict[str, Any]]:
    return {
        arm.label: _outcome_counts(arm.report.battle_results) for arm in report.arms
    }


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


def _aggregate_outcomes(
    summaries: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
) -> dict[str, Any]:
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
    for summary in summaries:
        outcomes = _mapping(summary.get("arm_outcomes"))
        for label in labels:
            values = _mapping(outcomes.get(label))
            for key in totals[label]:
                totals[label][key] += _as_int(values.get(key))
    root = _mapping(totals.get(ROOT_PRIOR_GUIDED_LABEL))
    baseline = _mapping(totals.get(BASELINE_ORACLE_LABEL))
    post = _mapping(totals.get(POST_SEARCH_MODEL_GUIDED_LABEL))
    return {
        "arm_outcomes": totals,
        "root_prior_vs_baseline": _outcome_delta(root, baseline),
        "root_prior_vs_post_search": _outcome_delta(root, post),
        "metric": "authoritative_win_count",
    }


def _outcome_delta(
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


def _delta_status(delta: int) -> str:
    if delta > 0:
        return "improved"
    if delta < 0:
        return "regressed"
    return "tied"


def _root_prior_allocation_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    for arm in report.arms:
        if arm.label == ROOT_PRIOR_GUIDED_LABEL:
            return _json_safe_mapping(root_prior_allocation_summary(arm.report))
    return {}


def _evaluated_record_count(report: RootPriorGuidedSearchComparisonReport) -> int:
    value = report.comparison_config.get("evaluated_record_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return max((arm.report.total_battles for arm in report.arms), default=0)


def _dedupe_unavailable(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        mapping = _json_safe_mapping(row)
        key = json.dumps(mapping, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduped.append(mapping)
    return deduped


def _format_arm_wins(value: Mapping[str, Any]) -> str:
    arms = _mapping(value.get("arm_outcomes"))
    parts = []
    for label in (
        BASELINE_ORACLE_LABEL,
        POST_SEARCH_MODEL_GUIDED_LABEL,
        ROOT_PRIOR_GUIDED_LABEL,
    ):
        outcome = _mapping(arms.get(label))
        if outcome:
            parts.append(
                f"{label}={_as_int(outcome.get('authoritative_wins'))}W/"
                f"{_as_int(outcome.get('losses'))}L"
            )
    return ", ".join(parts) if parts else "missing"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0


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
