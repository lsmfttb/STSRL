"""T055 guardrailed root-prior fixed-cohort scale validation report.

This module consumes the accepted T048/T054 retained evidence plus two new
T055 four-arm fixed-cohort comparisons. It validates the repaired T054
guardrail on the retained T048 cohorts without changing controller behavior or
making promotion claims.
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
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    T054GuardrailedRootPriorRepairReport,
)


T055_SCALE_VALIDATION_REPORT_SCHEMA_ID = (
    "t055-guardrailed-root-prior-scale-validation-report-v1"
)
T055_SCALE_VALIDATION_REPORT_FORMAT_VERSION = 1
T055_RETENTION_MANIFEST_SCHEMA_ID = "t055-retention-manifest-v1"
T055_RETENTION_MANIFEST_FORMAT_VERSION = 1
T055_REQUIRED_REFERENCE_LABELS = (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
)
T055_REQUIRED_COMPARISON_LABELS = (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
)
T055_REQUIRED_INPUT_ROLES = (
    "t054_guardrailed_repair_report",
    "t054_guardrailed_comparison",
    "t054_retention_manifest",
    "t048_current_reference_comparison",
    "t048_current_fixed_cohort",
    "t043_assist0_smoke_checkpoint",
    "t055_current_guardrailed_comparison",
    "t048_assist0_reference_comparison",
    "t048_assist0_fixed_cohort",
    "t043_main_runs1000_assist0_checkpoint",
    "t055_assist0_guardrailed_comparison",
)
T055_COHORT_CONTRACTS: tuple[dict[str, Any], ...] = (
    {
        "cohort_key": "current_t046_full8",
        "display_name": "current T046-compatible full8",
        "cohort_identity": "875ea52e3df4cb93",
        "record_range": "0:8",
        "record_count": 8,
        "workers": 8,
        "shards": 8,
        "t048_reference_role": "t048_current_reference_comparison",
        "t055_comparison_role": "t055_current_guardrailed_comparison",
        "fixed_cohort_role": "t048_current_fixed_cohort",
        "checkpoint_role": "t043_assist0_smoke_checkpoint",
        "accepted_t048_wins": {
            BASELINE_ORACLE_LABEL: 5,
            POST_SEARCH_MODEL_GUIDED_LABEL: 5,
            ROOT_PRIOR_GUIDED_LABEL: 6,
        },
    },
    {
        "cohort_key": "assist0_runs1000_full21",
        "display_name": "assist_0 runs1000 full21",
        "cohort_identity": "a336ffb1fda9ed7e",
        "record_range": "0:21",
        "record_count": 21,
        "workers": 16,
        "shards": 16,
        "t048_reference_role": "t048_assist0_reference_comparison",
        "t055_comparison_role": "t055_assist0_guardrailed_comparison",
        "fixed_cohort_role": "t048_assist0_fixed_cohort",
        "checkpoint_role": "t043_main_runs1000_assist0_checkpoint",
        "accepted_t048_wins": {
            BASELINE_ORACLE_LABEL: 11,
            POST_SEARCH_MODEL_GUIDED_LABEL: 11,
            ROOT_PRIOR_GUIDED_LABEL: 13,
        },
    },
)
T055_EVIDENCE_BOUNDARY = {
    "task_id": "T055",
    "scope": "guardrailed root-prior fixed-cohort scale validation",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}


@dataclass(frozen=True)
class T055GuardrailedRootPriorScaleValidationReport:
    """Versioned T055 report assembled from retained and generated artifacts."""

    input_artifacts: list[dict[str, Any]]
    t054_reference_summary: dict[str, Any]
    cohort_summaries: list[dict[str, Any]]
    aggregate_summary: dict[str, Any]
    allocation_telemetry_summary: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]]
    recommendation: dict[str, Any]
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T055_SCALE_VALIDATION_REPORT_SCHEMA_ID
    format_version: int = T055_SCALE_VALIDATION_REPORT_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T055_EVIDENCE_BOUNDARY)
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
            "t054_reference_summary": _json_safe_value(self.t054_reference_summary),
            "cohort_summaries": _json_safe_value(self.cohort_summaries),
            "aggregate_summary": _json_safe_value(self.aggregate_summary),
            "allocation_telemetry_summary": _json_safe_value(
                self.allocation_telemetry_summary
            ),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "recommendation": _json_safe_value(self.recommendation),
            "validation_problems": list(self.validation_problems),
        }


def build_t055_guardrailed_root_prior_scale_validation_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    t054_report: T054GuardrailedRootPriorRepairReport,
    t054_comparison: RootPriorGuidedSearchComparisonReport,
    t048_reference_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
) -> T055GuardrailedRootPriorScaleValidationReport:
    """Build and validate the T055 fixed-cohort scale report."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        t054_report=t054_report,
        t054_comparison=t054_comparison,
        t048_reference_comparisons=t048_reference_comparisons,
        t055_comparisons=t055_comparisons,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    cohort_summaries = [
        _cohort_summary(
            contract=contract,
            t048_reference=t048_reference_comparisons[str(contract["cohort_key"])],
            t055_comparison=t055_comparisons[str(contract["cohort_key"])],
        )
        for contract in T055_COHORT_CONTRACTS
    ]
    aggregate = _aggregate_summary(cohort_summaries)
    allocation = _allocation_telemetry_summary(t055_comparisons)
    unavailable = _unavailable_diagnostics(
        t055_comparisons=t055_comparisons,
        allocation=allocation,
    )
    recommendation = _recommendation(aggregate)
    return T055GuardrailedRootPriorScaleValidationReport(
        input_artifacts=artifacts,
        t054_reference_summary=_t054_reference_summary(t054_report, t054_comparison),
        cohort_summaries=cohort_summaries,
        aggregate_summary=aggregate,
        allocation_telemetry_summary=allocation,
        unavailable_diagnostics=unavailable,
        recommendation=recommendation,
    )


def dump_t055_guardrailed_root_prior_scale_validation_report_json(
    report: T055GuardrailedRootPriorScaleValidationReport,
    stream: TextIO,
) -> None:
    """Write deterministic current-schema T055 report JSON."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t055_guardrailed_root_prior_scale_validation_report_json(
    stream: TextIO,
) -> T055GuardrailedRootPriorScaleValidationReport:
    """Load and validate a current-schema T055 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T055 scale-validation report JSON") from exc
    return t055_guardrailed_root_prior_scale_validation_report_from_dict(raw)


def t055_guardrailed_root_prior_scale_validation_report_from_dict(
    raw: Mapping[str, Any],
) -> T055GuardrailedRootPriorScaleValidationReport:
    """Validate a current-schema T055 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T055 scale-validation report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T055_SCALE_VALIDATION_REPORT_SCHEMA_ID:
        raise ValueError(
            f"unsupported T055 scale-validation schema_id {schema_id!r}; "
            f"expected {T055_SCALE_VALIDATION_REPORT_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T055_SCALE_VALIDATION_REPORT_FORMAT_VERSION:
        raise ValueError(
            "unsupported T055 scale-validation format_version "
            f"{format_version!r}; expected "
            f"{T055_SCALE_VALIDATION_REPORT_FORMAT_VERSION}"
        )
    return T055GuardrailedRootPriorScaleValidationReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        t054_reference_summary=_require_mapping(
            raw.get("t054_reference_summary"),
            "t054_reference_summary",
        ),
        cohort_summaries=_require_list_of_mappings(
            raw.get("cohort_summaries"),
            "cohort_summaries",
        ),
        aggregate_summary=_require_mapping(
            raw.get("aggregate_summary"),
            "aggregate_summary",
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
            raw.get("evidence_boundary", T055_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t055_guardrailed_root_prior_scale_validation_report(
    report: T055GuardrailedRootPriorScaleValidationReport,
) -> str:
    """Format concise T055 diagnostics for stderr and PR summaries."""

    recommendation = report.recommendation
    aggregate = report.aggregate_summary
    lines = [
        "T055 guardrailed root-prior scale validation report",
        (
            "scope: restored-battle scale validation only; no controller "
            "promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "aggregate guardrail status vs accepted T048 advantage: "
            + str(aggregate.get("t048_advantage_status"))
            + " (delta="
            + _format_optional_number(
                aggregate.get("guardrail_advantage_delta_vs_t048")
            )
            + ")"
        ),
        "cohort results:",
    ]
    for cohort in report.cohort_summaries:
        status = _mapping(cohort.get("t048_advantage_comparison"))
        outcome = _mapping(cohort.get("t055_outcome_comparison"))
        lines.append(
            "  "
            + str(cohort.get("cohort_key"))
            + ": records="
            + str(cohort.get("evaluated_record_count"))
            + ", guardrail="
            + _win_loss_text(
                _mapping(outcome.get("arm_outcomes")).get(
                    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL
                )
            )
            + ", accepted-status="
            + str(status.get("status"))
        )
    lines.append(
        "recommended next task: "
        + str(recommendation.get("recommended_next_task", "missing"))
    )
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


def build_t055_retention_manifest_payload(
    *,
    artifact_specs: Sequence[Mapping[str, Any]],
    command_specs: Sequence[Mapping[str, str]] = (),
    stage_specs: Sequence[Mapping[str, Any]] = (),
    note_items: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Build a lightweight T055 artifact retention manifest."""

    if not artifact_specs:
        raise ValueError("T055 retention manifest requires at least one artifact")
    return {
        "schema_id": T055_RETENTION_MANIFEST_SCHEMA_ID,
        "format_version": T055_RETENTION_MANIFEST_FORMAT_VERSION,
        "task_id": "T055",
        "evidence_boundary": dict(T055_EVIDENCE_BOUNDARY),
        "retention_reason": (
            "preserve T055 guardrailed root-prior scale comparison reports, "
            "report, logs, wrappers, and review evidence"
        ),
        "downstream_consumers": [
            "main maintainer review of T055",
            "the exactly one follow-up task recommended in the T055 report",
        ],
        "deletion_conditions": (
            "raw local artifacts may be deleted after T055 review is complete "
            "and the maintainer has recorded any retained identities needed by "
            "the next published task"
        ),
        "artifacts": [_json_safe_mapping(spec) for spec in artifact_specs],
        "commands": [_json_safe_mapping(spec) for spec in command_specs],
        "runtime_stages": [_json_safe_mapping(spec) for spec in stage_specs],
        "notes": {str(key): str(value) for key, value in note_items},
    }


def dump_t055_retention_manifest_json(
    payload: Mapping[str, Any],
    stream: TextIO,
) -> None:
    """Write deterministic T055 retention manifest JSON."""

    json.dump(_json_safe_mapping(payload), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_t055_retention_manifest(payload: Mapping[str, Any]) -> str:
    """Format the T055 retention manifest for stderr."""

    artifacts = _sequence(payload.get("artifacts"))
    stages = _sequence(payload.get("runtime_stages"))
    lines = [
        "T055 retention manifest",
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
    t054_report: T054GuardrailedRootPriorRepairReport,
    t054_comparison: RootPriorGuidedSearchComparisonReport,
    t048_reference_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
) -> list[str]:
    problems: list[str] = []
    roles = [str(item.get("role") or "") for item in input_artifacts]
    for role in T055_REQUIRED_INPUT_ROLES:
        if role not in roles:
            problems.append(f"missing required T055 input artifact role {role}")
    if len(set(roles)) != len(roles):
        problems.append("duplicate T055 input artifact roles")
    for artifact in input_artifacts:
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{artifact.get('role', 'artifact')}: sha256 not verified")
    input_artifact_sha256_by_role = _input_artifact_sha256_by_role(
        input_artifacts,
        problems,
    )

    if not t054_report.command_passed:
        problems.append("T054 repair report did not pass")
    if t054_report.recommendation.get("recommended_next_task") != (
        "scale the repaired variant"
    ):
        problems.append("T054 report did not recommend scaling the repaired variant")
    _extend_comparison_problems(
        problems,
        prefix="T054 comparison",
        report=t054_comparison,
        expected_task_id="T054",
        expected_cohort_identity=str(
            t054_report.t054_comparison_summary.get("cohort_identity")
        ),
        expected_record_count=_as_int(
            t054_report.t054_comparison_summary.get("evaluated_record_count")
        ),
        expected_record_range=None,
        expected_workers=None,
        expected_shards=None,
        required_labels=T055_REQUIRED_COMPARISON_LABELS,
        require_guardrail=True,
    )

    for contract in T055_COHORT_CONTRACTS:
        key = str(contract["cohort_key"])
        reference = t048_reference_comparisons.get(key)
        generated = t055_comparisons.get(key)
        if reference is None:
            problems.append(f"{key}: missing T048 reference comparison")
            continue
        if generated is None:
            problems.append(f"{key}: missing T055 guardrailed comparison")
            continue
        _extend_comparison_problems(
            problems,
            prefix=f"{key} T048 reference",
            report=reference,
            expected_task_id="T048",
            expected_cohort_identity=str(contract["cohort_identity"]),
            expected_record_count=_as_int(contract["record_count"]),
            expected_record_range=str(contract["record_range"]),
            expected_workers=_as_int(contract["workers"]),
            expected_shards=_as_int(contract["shards"]),
            required_labels=T055_REQUIRED_REFERENCE_LABELS,
            require_guardrail=False,
        )
        _validate_accepted_t048_wins(problems, contract, reference)
        checkpoint_role = str(contract["checkpoint_role"])
        expected_checkpoint_sha256 = input_artifact_sha256_by_role.get(checkpoint_role)
        if expected_checkpoint_sha256 is None:
            problems.append(
                f"{key}: {checkpoint_role} missing verified checkpoint sha256"
            )
        _extend_comparison_problems(
            problems,
            prefix=f"{key} T055 comparison",
            report=generated,
            expected_task_id="T055",
            expected_cohort_identity=str(contract["cohort_identity"]),
            expected_record_count=_as_int(contract["record_count"]),
            expected_record_range=str(contract["record_range"]),
            expected_workers=_as_int(contract["workers"]),
            expected_shards=_as_int(contract["shards"]),
            required_labels=T055_REQUIRED_COMPARISON_LABELS,
            require_guardrail=True,
        )
        if expected_checkpoint_sha256 is not None:
            _validate_checkpoint_provenance(
                problems,
                prefix=f"{key} T048 reference",
                report=reference,
                expected_checkpoint_sha256=expected_checkpoint_sha256,
                labels=(
                    POST_SEARCH_MODEL_GUIDED_LABEL,
                    ROOT_PRIOR_GUIDED_LABEL,
                ),
            )
            _validate_checkpoint_provenance(
                problems,
                prefix=f"{key} T055 comparison",
                report=generated,
                expected_checkpoint_sha256=expected_checkpoint_sha256,
                labels=(
                    POST_SEARCH_MODEL_GUIDED_LABEL,
                    ROOT_PRIOR_GUIDED_LABEL,
                    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                ),
            )
    return list(dict.fromkeys(problems))


def _extend_comparison_problems(
    problems: list[str],
    *,
    prefix: str,
    report: RootPriorGuidedSearchComparisonReport,
    expected_task_id: str,
    expected_cohort_identity: str,
    expected_record_count: int,
    expected_record_range: str | None,
    expected_workers: int | None,
    expected_shards: int | None,
    required_labels: Sequence[str],
    require_guardrail: bool,
) -> None:
    if report.schema_id != "root-prior-guided-search-comparison-v1":
        problems.append(f"{prefix}: unexpected schema {report.schema_id!r}")
    if report.comparison_config.get("task_id") != expected_task_id:
        problems.append(f"{prefix}: task_id is not {expected_task_id}")
    if report.cohort_identity != expected_cohort_identity:
        problems.append(
            f"{prefix}: cohort identity mismatch: expected "
            f"{expected_cohort_identity}, got {report.cohort_identity}"
        )
    if _evaluated_record_count(report) != expected_record_count:
        problems.append(
            f"{prefix}: evaluated record count mismatch: expected "
            f"{expected_record_count}, got {_evaluated_record_count(report)}"
        )
    if expected_record_range is not None:
        actual_range = str(report.comparison_config.get("record_range"))
        if actual_range != expected_record_range:
            problems.append(
                f"{prefix}: record range mismatch: expected "
                f"{expected_record_range}, got {actual_range}"
            )
    if (
        expected_workers is not None
        and _optional_int(report.comparison_config.get("worker_count"))
        != expected_workers
    ):
        problems.append(f"{prefix}: worker count mismatch")
    if (
        expected_shards is not None
        and _optional_int(report.comparison_config.get("shard_count"))
        != expected_shards
    ):
        problems.append(f"{prefix}: shard count mismatch")
    if report.source_match_problems:
        problems.append(f"{prefix}: source/cohort match status is not clean")
    if not report.evaluation_successful:
        problems.extend(f"{prefix}: {problem}" for problem in report.problems)

    arms = _arms_by_label(report)
    for label in required_labels:
        if label not in arms:
            problems.append(f"{prefix}: missing required arm {label!r}")
    regimes = {
        label: arm.report.information_regime
        for label, arm in arms.items()
        if label in required_labels
    }
    for label, regime in regimes.items():
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{prefix}: {label} information regime {regime!r} is not "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
    if not _equal_configured_budget(report, required_labels):
        problems.append(f"{prefix}: required arms do not share equal native budget")
    if _configured_budget_for_labels(report, required_labels) != 20:
        problems.append(f"{prefix}: required native root budget is not 20")

    if require_guardrail and GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL in arms:
        guardrail_report = arms[GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL].report
        guardrail_config = _guardrail_configuration(report)
        controller_name = str(guardrail_config.get("controller_name") or "")
        if (
            guardrail_config.get("controller_version")
            != GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
        ):
            problems.append(f"{prefix}: guardrailed arm has unexpected version")
        if GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME not in controller_name:
            problems.append(f"{prefix}: guardrailed arm has unexpected controller name")
        allocation = root_prior_allocation_summary(guardrail_report)
        guardrail = _guardrail_telemetry_summary(guardrail_report)
        if allocation["decision_count"] == 0:
            problems.append(f"{prefix}: guardrailed arm has no allocation telemetry")
        if allocation["malformed_metadata_count"]:
            problems.append(f"{prefix}: guardrailed arm has malformed allocation")
        if guardrail["decision_count"] == 0:
            problems.append(f"{prefix}: guardrailed arm has no guardrail telemetry")
        if guardrail["missing_guardrail_config_count"]:
            problems.append(f"{prefix}: guardrailed arm has missing guardrail config")
        if guardrail["missing_guardrail_summary_count"]:
            problems.append(f"{prefix}: guardrailed arm has missing guardrail summary")
        if guardrail["unexpected_guardrail_strategy_count"]:
            problems.append(f"{prefix}: guardrailed arm has unexpected guardrail data")


def _validate_accepted_t048_wins(
    problems: list[str],
    contract: Mapping[str, Any],
    report: RootPriorGuidedSearchComparisonReport,
) -> None:
    outcomes = _arm_outcomes(report, T055_REQUIRED_REFERENCE_LABELS)
    expected = _mapping(contract.get("accepted_t048_wins"))
    for label, value in expected.items():
        actual = _as_int(_mapping(outcomes.get(str(label))).get("authoritative_wins"))
        if actual != _as_int(value):
            problems.append(
                f"{contract.get('cohort_key')} T048 reference: {label} wins "
                f"mismatch: expected {_as_int(value)}, got {actual}"
            )


def _input_artifact_sha256_by_role(
    input_artifacts: Sequence[Mapping[str, Any]],
    problems: list[str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for artifact in input_artifacts:
        role = str(artifact.get("role") or "")
        values = {
            value
            for value in (
                _normalized_sha256(artifact.get("sha256")),
                _normalized_sha256(artifact.get("actual_sha256")),
                _normalized_sha256(artifact.get("expected_sha256")),
            )
            if value is not None
        }
        if len(values) > 1:
            problems.append(f"{role or 'artifact'}: sha256 fields disagree")
        if len(values) == 1 and role:
            result[role] = next(iter(values))
    return result


def _validate_checkpoint_provenance(
    problems: list[str],
    *,
    prefix: str,
    report: RootPriorGuidedSearchComparisonReport,
    expected_checkpoint_sha256: str,
    labels: Sequence[str],
) -> None:
    arms = _arms_by_label(report)
    checkpoints = {
        label: _checkpoint_provenance(arms[label].report)
        for label in labels
        if label in arms
    }
    for label, checkpoint in checkpoints.items():
        if not checkpoint:
            problems.append(f"{prefix}: {label} missing checkpoint provenance")
            continue
        checkpoint_sha256 = _checkpoint_provenance_sha256(checkpoint)
        if checkpoint_sha256 is None:
            problems.append(f"{prefix}: {label} missing checkpoint artifact sha256")
        elif checkpoint_sha256 != expected_checkpoint_sha256:
            problems.append(
                f"{prefix}: {label} checkpoint sha256 mismatch: expected "
                f"{expected_checkpoint_sha256}, got {checkpoint_sha256}"
            )
    values = {json.dumps(value, sort_keys=True) for value in checkpoints.values()}
    if len(values) > 1:
        problems.append(f"{prefix}: checkpoint provenance mismatch across guided arms")


def _checkpoint_provenance_sha256(checkpoint: Mapping[str, Any]) -> str | None:
    for key in ("sha256", "checkpoint_sha256"):
        value = _normalized_sha256(checkpoint.get(key))
        if value is not None:
            return value
    artifact_id = checkpoint.get("checkpoint_artifact_id")
    if isinstance(artifact_id, str):
        marker = "sha256:"
        if marker in artifact_id:
            return _normalized_sha256(artifact_id.rsplit(marker, 1)[1])
    return None


def _normalized_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if len(candidate) != 64:
        return None
    if any(char not in "0123456789abcdef" for char in candidate):
        return None
    return candidate


def _t054_reference_summary(
    t054_report: T054GuardrailedRootPriorRepairReport,
    t054_comparison: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    return {
        "schema_id": t054_report.schema_id,
        "format_version": t054_report.format_version,
        "command_passed": t054_report.command_passed,
        "recommendation": _json_safe_mapping(t054_report.recommendation),
        "repair_report_comparison_summary": _json_safe_mapping(
            t054_report.t054_comparison_summary
        ),
        "comparison_summary": _comparison_summary(t054_comparison),
        "guardrail_configuration": _guardrail_configuration(t054_comparison),
        "evidence_boundary": _json_safe_mapping(t054_report.evidence_boundary),
    }


def _cohort_summary(
    *,
    contract: Mapping[str, Any],
    t048_reference: RootPriorGuidedSearchComparisonReport,
    t055_comparison: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    reference_outcomes = _arm_outcomes(t048_reference, T055_REQUIRED_REFERENCE_LABELS)
    t055_outcomes = _arm_outcomes(t055_comparison, T055_REQUIRED_COMPARISON_LABELS)
    record_changes = _record_outcome_changes(t048_reference, t055_comparison)
    changed_count = sum(
        1
        for row in record_changes
        if row["guardrail_vs_t048_root_prior"]["outcome_changed"]
    )
    advantage = _t048_advantage_comparison(
        reference_outcomes=reference_outcomes,
        t055_outcomes=t055_outcomes,
        changed_record_count=changed_count,
    )
    return {
        "cohort_key": str(contract["cohort_key"]),
        "display_name": str(contract["display_name"]),
        "cohort_identity": str(contract["cohort_identity"]),
        "record_range": str(contract["record_range"]),
        "evaluated_record_count": _evaluated_record_count(t055_comparison),
        "worker_count": t055_comparison.comparison_config.get("worker_count"),
        "shard_count": t055_comparison.comparison_config.get("shard_count"),
        "distribution_summary": _json_safe_mapping(
            t055_comparison.comparison_config.get(
                "cohort_source_distribution_summary",
                {},
            )
        ),
        "t048_reference_summary": _comparison_summary(t048_reference),
        "t055_comparison_summary": _comparison_summary(t055_comparison),
        "t048_reference_outcomes": reference_outcomes,
        "t055_outcome_comparison": {
            "metric": "authoritative_win_count",
            "arm_outcomes": t055_outcomes,
            "guardrail_vs_existing_root_prior": _aggregate_delta(
                _mapping(t055_outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)),
                _mapping(t055_outcomes.get(ROOT_PRIOR_GUIDED_LABEL)),
            ),
            "guardrail_vs_baseline": _aggregate_delta(
                _mapping(t055_outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)),
                _mapping(t055_outcomes.get(BASELINE_ORACLE_LABEL)),
            ),
            "guardrail_vs_post_search": _aggregate_delta(
                _mapping(t055_outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)),
                _mapping(t055_outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL)),
            ),
        },
        "t048_advantage_comparison": advantage,
        "record_outcome_changes": record_changes,
        "record_outcome_change_count": changed_count,
        "guardrail_configuration": _guardrail_configuration(t055_comparison),
        "allocation_telemetry_summary": _single_comparison_allocation_summary(
            t055_comparison
        ),
        "unavailable_diagnostics": _comparison_unavailable_diagnostics(t055_comparison),
    }


def _aggregate_summary(cohort_summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reference_outcomes = _sum_named_outcomes(
        cohort_summaries,
        "t048_reference_outcomes",
        T055_REQUIRED_REFERENCE_LABELS,
    )
    t055_outcomes = _sum_named_outcomes(
        cohort_summaries,
        "t055_outcome_comparison",
        T055_REQUIRED_COMPARISON_LABELS,
        nested_arm_key="arm_outcomes",
    )
    changed_count = sum(
        _as_int(item.get("record_outcome_change_count")) for item in cohort_summaries
    )
    comparison = _t048_advantage_comparison(
        reference_outcomes=reference_outcomes,
        t055_outcomes=t055_outcomes,
        changed_record_count=changed_count,
    )
    guardrail = _mapping(t055_outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL))
    root = _mapping(t055_outcomes.get(ROOT_PRIOR_GUIDED_LABEL))
    baseline = _mapping(t055_outcomes.get(BASELINE_ORACLE_LABEL))
    post = _mapping(t055_outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL))
    return {
        "label": "aggregate_across_retained_t048_cohorts",
        "cohort_count": len(cohort_summaries),
        "record_count": sum(
            _as_int(item.get("evaluated_record_count")) for item in cohort_summaries
        ),
        "t048_reference_outcomes": reference_outcomes,
        "t055_outcomes": t055_outcomes,
        "t055_guardrail_vs_existing_root_prior": _aggregate_delta(guardrail, root),
        "t055_guardrail_vs_baseline": _aggregate_delta(guardrail, baseline),
        "t055_guardrail_vs_post_search": _aggregate_delta(guardrail, post),
        "t048_advantage_comparison": comparison,
        "t048_advantage_status": comparison["status"],
        "guardrail_advantage_delta_vs_t048": comparison[
            "guardrail_advantage_delta_vs_t048"
        ],
        "record_outcome_change_count": changed_count,
        "evidence_boundary": (
            "labeled aggregate across two retained T048 fixed cohorts only; "
            "not natural A20 performance"
        ),
    }


def _t048_advantage_comparison(
    *,
    reference_outcomes: Mapping[str, Any],
    t055_outcomes: Mapping[str, Any],
    changed_record_count: int,
) -> dict[str, Any]:
    ref_baseline = _as_int(
        _mapping(reference_outcomes.get(BASELINE_ORACLE_LABEL)).get(
            "authoritative_wins"
        )
    )
    ref_post = _as_int(
        _mapping(reference_outcomes.get(POST_SEARCH_MODEL_GUIDED_LABEL)).get(
            "authoritative_wins"
        )
    )
    ref_root = _as_int(
        _mapping(reference_outcomes.get(ROOT_PRIOR_GUIDED_LABEL)).get(
            "authoritative_wins"
        )
    )
    guardrail = _as_int(
        _mapping(t055_outcomes.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)).get(
            "authoritative_wins"
        )
    )
    reference_best_baseline = max(ref_baseline, ref_post)
    accepted_advantage = ref_root - reference_best_baseline
    guardrail_advantage = guardrail - reference_best_baseline
    delta = guardrail_advantage - accepted_advantage
    if delta > 0:
        status = "improved"
    elif delta < 0:
        status = "regressed"
    elif changed_record_count:
        status = "changed"
    else:
        status = "preserved"
    return {
        "metric": "authoritative_win_count",
        "reference_baseline_wins": ref_baseline,
        "reference_post_search_wins": ref_post,
        "accepted_t048_root_prior_wins": ref_root,
        "accepted_t048_root_prior_advantage_vs_best_reference": accepted_advantage,
        "t055_guardrailed_wins": guardrail,
        "t055_guardrailed_advantage_vs_best_reference": guardrail_advantage,
        "guardrail_advantage_delta_vs_t048": delta,
        "changed_record_count_vs_t048_root_prior": changed_record_count,
        "status": status,
    }


def _allocation_telemetry_summary(
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
) -> dict[str, Any]:
    by_cohort = {
        key: _single_comparison_allocation_summary(report)
        for key, report in t055_comparisons.items()
    }
    aggregate_root = _sum_allocation(
        _mapping(value.get("root_prior_arm")) for value in by_cohort.values()
    )
    aggregate_guardrail = _sum_allocation(
        _mapping(value.get("guardrailed_arm")) for value in by_cohort.values()
    )
    aggregate_guardrail_telemetry = _sum_guardrail_telemetry(
        _mapping(value.get("guardrail_telemetry")) for value in by_cohort.values()
    )
    return {
        "by_cohort": by_cohort,
        "aggregate": {
            "root_prior_arm": aggregate_root,
            "guardrailed_arm": aggregate_guardrail,
            "guardrail_telemetry": aggregate_guardrail_telemetry,
        },
    }


def _single_comparison_allocation_summary(
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


def _unavailable_diagnostics(
    *,
    t055_comparisons: Mapping[str, RootPriorGuidedSearchComparisonReport],
    allocation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    unavailable = [
        {
            "diagnostic": "guardrail_causal_effect",
            "reason": (
                "T055 compares separate restored-battle controller arms; native "
                "telemetry does not expose paired within-decision counterfactual "
                "trees"
            ),
        },
        {
            "diagnostic": "normal_information_strength",
            "reason": ("all T055 search arms remain full_simulator_state_oracle_like"),
        },
    ]
    for key, report in t055_comparisons.items():
        unavailable.extend(
            {
                "cohort_key": key,
                "diagnostic": item["diagnostic"],
                "reason": item["reason"],
            }
            for item in _comparison_unavailable_diagnostics(report)
        )
    guardrail = _mapping(
        _mapping(allocation.get("aggregate")).get("guardrail_telemetry")
    )
    if _as_int(guardrail.get("missing_guardrail_config_count")):
        unavailable.append(
            {
                "diagnostic": "guardrail_config",
                "reason": "one or more guardrail decisions lacked guardrail config",
            }
        )
    return unavailable


def _comparison_unavailable_diagnostics(
    report: RootPriorGuidedSearchComparisonReport,
) -> list[dict[str, Any]]:
    unavailable: list[dict[str, Any]] = []
    if report.problems:
        unavailable.append(
            {
                "diagnostic": "comparison_validation",
                "reason": "; ".join(report.problems),
            }
        )
    return unavailable


def _recommendation(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    status = str(aggregate.get("t048_advantage_status"))
    if status in {"preserved", "improved"}:
        next_task = "repaired-variant complete-run reachability"
    elif status == "regressed":
        next_task = "abandon the guardrail path"
    elif status == "changed":
        next_task = "another fixed-cohort diagnostic"
    else:
        next_task = "publish a different blocked path"
    return {
        "recommendation_count": 1,
        "recommended_next_task": next_task,
        "allowed_recommendation_set": [
            "repaired-variant complete-run reachability",
            "another fixed-cohort diagnostic",
            "abandon the guardrail path",
            "publish a different blocked path",
        ],
        "reason": (
            "selected from the labeled T048-cohort aggregate without changing "
            "guardrail behavior or making a promotion claim"
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


def _comparison_summary(
    report: RootPriorGuidedSearchComparisonReport,
) -> dict[str, Any]:
    return {
        "schema_id": report.schema_id,
        "format_version": report.format_version,
        "task_id": report.comparison_config.get("task_id"),
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
        "controller_summaries": _json_safe_mapping(
            root_prior_guided_controller_summaries(report)
        ),
        "budget_summary": _json_safe_mapping(root_prior_guided_budget_summary(report)),
        "problems": list(report.problems),
    }


def _arm_outcomes(
    report: RootPriorGuidedSearchComparisonReport,
    labels: Sequence[str],
) -> dict[str, dict[str, Any]]:
    arms = _arms_by_label(report)
    return {
        label: _outcome_counts(arms[label].report.battle_results)
        for label in labels
        if label in arms
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


def _record_outcome_changes(
    t048_reference: RootPriorGuidedSearchComparisonReport,
    t055_comparison: RootPriorGuidedSearchComparisonReport,
) -> list[dict[str, Any]]:
    reference_arms = _arms_by_label(t048_reference)
    t055_arms = _arms_by_label(t055_comparison)
    count = max((arm.report.total_battles for arm in t055_comparison.arms), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        reference_results = {
            label: _result_by_index(reference_arms[label].report, index)
            for label in T055_REQUIRED_REFERENCE_LABELS
            if label in reference_arms
        }
        t055_results = {
            label: _result_by_index(t055_arms[label].report, index)
            for label in T055_REQUIRED_COMPARISON_LABELS
            if label in t055_arms
        }
        reference_root = _result_summary(reference_results.get(ROOT_PRIOR_GUIDED_LABEL))
        guardrail = _result_summary(
            t055_results.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
        )
        t055_root = _result_summary(t055_results.get(ROOT_PRIOR_GUIDED_LABEL))
        rows.append(
            {
                "cohort_index": index,
                "source": _source_key(
                    t055_results.get(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL)
                    or t055_results.get(ROOT_PRIOR_GUIDED_LABEL)
                    or reference_results.get(ROOT_PRIOR_GUIDED_LABEL)
                ),
                "t048_reference_arms": {
                    label: _result_summary(result)
                    for label, result in reference_results.items()
                },
                "t055_arms": {
                    label: _result_summary(result)
                    for label, result in t055_results.items()
                },
                "guardrail_vs_t048_root_prior": _result_change(
                    guardrail,
                    reference_root,
                ),
                "guardrail_vs_t055_existing_root_prior": _result_change(
                    guardrail,
                    t055_root,
                ),
            }
        )
    return rows


def _result_change(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_status = left.get("termination_status")
    right_status = right.get("termination_status")
    left_hp = _optional_int(left.get("terminal_absolute_hp"))
    right_hp = _optional_int(right.get("terminal_absolute_hp"))
    return {
        "outcome_changed": _outcome_signature(left) != _outcome_signature(right),
        "terminal_status_delta": _result_status(left_status, right_status),
        "terminal_absolute_hp_delta": (
            None if left_hp is None or right_hp is None else left_hp - right_hp
        ),
    }


def _result_status(left_status: Any, right_status: Any) -> str:
    left_win = left_status == "win"
    right_win = right_status == "win"
    if left_win and not right_win:
        return "improved"
    if not left_win and right_win:
        return "regressed"
    return "tied"


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


def _delta_status(delta: int) -> str:
    if delta > 0:
        return "improved"
    if delta == 0:
        return "tied"
    return "regressed"


def _sum_named_outcomes(
    cohort_summaries: Sequence[Mapping[str, Any]],
    source_key: str,
    labels: Sequence[str],
    *,
    nested_arm_key: str | None = None,
) -> dict[str, dict[str, Any]]:
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
        source = _mapping(summary.get(source_key))
        if nested_arm_key is not None:
            source = _mapping(source.get(nested_arm_key))
        for label in labels:
            values = _mapping(source.get(label))
            for key in totals[label]:
                totals[label][key] += _as_int(values.get(key))
    return totals


def _sum_allocation(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strategies: Counter[str] = Counter()
    selected: Counter[str] = Counter()
    decision_count = 0
    malformed = 0
    positive_prior_count = 0
    provided_prior_count = 0
    for item in items:
        decision_count += _as_int(item.get("decision_count"))
        malformed += _as_int(item.get("malformed_metadata_count"))
        positive_prior_count += _as_int(item.get("positive_prior_count"))
        provided_prior_count += _as_int(item.get("provided_prior_count"))
        strategies.update(_counter_from_mapping(item.get("allocation_strategy_counts")))
        selected.update(_counter_from_mapping(item.get("selected_index_counts")))
    return {
        "decision_count": decision_count,
        "malformed_metadata_count": malformed,
        "allocation_strategy_counts": dict(sorted(strategies.items())),
        "positive_prior_count": positive_prior_count,
        "provided_prior_count": provided_prior_count,
        "selected_index_counts": dict(sorted(selected.items())),
    }


def _sum_guardrail_telemetry(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    strategies: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    max_pre: list[float] = []
    max_post: list[float] = []
    result = {
        "decision_count": 0,
        "missing_guardrail_config_count": 0,
        "missing_guardrail_summary_count": 0,
        "unexpected_guardrail_strategy_count": 0,
        "changed_prior_count": 0,
        "l1_prior_delta_total": 0.0,
    }
    for item in items:
        for key in result:
            if key == "l1_prior_delta_total":
                result[key] += _as_float(item.get(key)) or 0.0
            else:
                result[key] += _as_int(item.get(key))
        strategies.update(_counter_from_mapping(item.get("guardrail_strategy_counts")))
        versions.update(_counter_from_mapping(item.get("guardrail_version_counts")))
        pre = _as_float(item.get("max_pre_guardrail_prior_probability"))
        post = _as_float(item.get("max_post_guardrail_prior_probability"))
        if pre is not None:
            max_pre.append(pre)
        if post is not None:
            max_post.append(post)
    return {
        **result,
        "max_pre_guardrail_prior_probability": max(max_pre) if max_pre else None,
        "max_post_guardrail_prior_probability": max(max_post) if max_post else None,
        "guardrail_strategy_counts": dict(sorted(strategies.items())),
        "guardrail_version_counts": dict(sorted(versions.items())),
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


def _restore_status(result: SingleBattleEvaluationResult) -> str:
    if result.termination_status == "error":
        return "error"
    if result.restoration_method:
        return "restored"
    return "unavailable"


def _outcome_signature(result: Mapping[str, Any]) -> tuple[Any, Any]:
    return result.get("termination_status"), result.get("terminal_absolute_hp")


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


def _arms_by_label(report: RootPriorGuidedSearchComparisonReport) -> dict[str, Any]:
    return {arm.label: arm for arm in report.arms}


def _evaluated_record_count(report: RootPriorGuidedSearchComparisonReport) -> int:
    value = report.comparison_config.get("evaluated_record_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return max((arm.report.total_battles for arm in report.arms), default=0)


def _equal_configured_budget(
    report: RootPriorGuidedSearchComparisonReport,
    labels: Sequence[str],
) -> bool:
    budget = _configured_budget_for_labels(report, labels)
    return budget is not None


def _configured_budget_for_labels(
    report: RootPriorGuidedSearchComparisonReport,
    labels: Sequence[str],
) -> int | None:
    arms = _arms_by_label(report)
    budgets = []
    for label in labels:
        arm = arms.get(label)
        if arm is None:
            return None
        value = _configured_native_playouts(arm.report)
        if value is None:
            return None
        budgets.append(value)
    return budgets[0] if budgets and len(set(budgets)) == 1 else None


def _configured_native_playouts(report: FixedEvaluationReport) -> int | None:
    config = _mapping(report.controller_provenance.get("config"))
    budget = _mapping(config.get("search_budget"))
    value = budget.get("simulations")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _checkpoint_provenance(report: FixedEvaluationReport) -> dict[str, Any]:
    config = _mapping(report.controller_provenance.get("config"))
    guidance = _mapping(config.get("guidance_scorer"))
    return _mapping(guidance.get("checkpoint_provenance"))


def _counter_from_mapping(value: Any) -> Counter[str]:
    counter: Counter[str] = Counter()
    for key, item in _mapping(value).items():
        counter[str(key)] += _as_int(item)
    return counter


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
