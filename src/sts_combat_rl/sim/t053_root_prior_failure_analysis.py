"""Offline T053 analysis for T052 root-prior allocation failures.

This module consumes retained T052 artifacts only.  It does not run the
simulator, train a checkpoint, choose actions, or promote a controller.
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
    POST_SEARCH_MODEL_GUIDED_LABEL,
    REQUIRED_ROOT_PRIOR_COMPARISON_LABELS,
    ROOT_PRIOR_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION,
    ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID,
)


T053_FAILURE_ANALYSIS_SCHEMA_ID = "t053-root-prior-allocation-failure-analysis-v1"
T053_FAILURE_ANALYSIS_FORMAT_VERSION = 1
T053_EVIDENCE_BOUNDARY = {
    "task_id": "T053",
    "scope": "offline T052 root-prior allocation diagnostics",
    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
    "not_controller_promotion": True,
    "not_live_game_evidence": True,
    "not_natural_a20_performance": True,
    "not_broad_training_evidence": True,
    "not_normal_information_search": True,
    "not_final_agent_evidence": True,
}
T053_REQUIRED_INPUT_ROLES = (
    "retention_manifest",
    "fixed_cohort",
    "root_prior_guided_comparison",
    "result_summary",
)
T053_TAXONOMY_CATEGORIES = (
    "harmful_root_prior_allocation",
    "no_op_or_ineffective_root_prior_allocation",
    "weak_or_miscalibrated_checkpoint_prior",
    "native_root_outcome_tie_broken_differently",
    "telemetry_or_schema_insufficient",
)
T053_RECOMMENDED_NEXT_TASK = "guardrailed root-prior allocation repair experiment"
MISSING_VALUE = "missing"


@dataclass(frozen=True)
class T053RootPriorFailureAnalysisReport:
    """Versioned T053 diagnostic report assembled from T052 artifacts."""

    input_artifacts: list[dict[str, Any]]
    comparison_summary: dict[str, Any]
    t052_result_summary: dict[str, Any]
    disagreement_summary: dict[str, Any]
    disagreement_records: list[dict[str, Any]]
    subset_summaries: dict[str, dict[str, Any]]
    allocation_telemetry_summary: dict[str, Any]
    action_comparison_diagnostics: dict[str, Any]
    failure_taxonomy: dict[str, Any]
    recommendation: dict[str, Any]
    unavailable_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    validation_problems: list[str] = field(default_factory=list)
    schema_id: str = T053_FAILURE_ANALYSIS_SCHEMA_ID
    format_version: int = T053_FAILURE_ANALYSIS_FORMAT_VERSION
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(T053_EVIDENCE_BOUNDARY)
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
            "comparison_summary": _json_safe_value(self.comparison_summary),
            "t052_result_summary": _json_safe_value(self.t052_result_summary),
            "disagreement_summary": _json_safe_value(self.disagreement_summary),
            "disagreement_records": _json_safe_value(self.disagreement_records),
            "subset_summaries": _json_safe_value(self.subset_summaries),
            "allocation_telemetry_summary": _json_safe_value(
                self.allocation_telemetry_summary
            ),
            "action_comparison_diagnostics": _json_safe_value(
                self.action_comparison_diagnostics
            ),
            "failure_taxonomy": _json_safe_value(self.failure_taxonomy),
            "recommendation": _json_safe_value(self.recommendation),
            "unavailable_diagnostics": _json_safe_value(self.unavailable_diagnostics),
            "validation_problems": list(self.validation_problems),
        }


def build_t053_root_prior_failure_analysis_report(
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    comparison_metadata: Mapping[str, Any],
    battle_comparisons: Sequence[Mapping[str, Any]],
    controller_results: Mapping[str, Mapping[int, Mapping[str, Any]]],
    t052_result_summary: Mapping[str, Any],
) -> T053RootPriorFailureAnalysisReport:
    """Build a deterministic T053 diagnostic report from streamed T052 rows."""

    artifacts = [_json_safe_mapping(item) for item in input_artifacts]
    result_summary = _json_safe_mapping(t052_result_summary)
    unavailable: list[dict[str, Any]] = []
    validation_problems = _validation_problems(
        input_artifacts=artifacts,
        comparison_metadata=comparison_metadata,
        battle_comparisons=battle_comparisons,
        controller_results=controller_results,
        unavailable=unavailable,
    )
    if validation_problems:
        raise ValueError("; ".join(validation_problems))

    comparison_summary = _comparison_summary(comparison_metadata)
    disagreement_records = [
        _disagreement_record(comparison, controller_results, unavailable)
        for comparison in battle_comparisons
        if _is_disagreement(comparison)
    ]
    subset_summaries = _subset_summaries(disagreement_records, controller_results)
    allocation_summary = _allocation_telemetry_summary(disagreement_records)
    action_diagnostics = _action_comparison_diagnostics(
        disagreement_records,
        unavailable,
    )
    disagreement_summary = _disagreement_summary(
        disagreement_records,
        total_battle_count=len(battle_comparisons),
    )
    taxonomy = _failure_taxonomy(
        disagreement_records,
        action_diagnostics=action_diagnostics,
    )
    recommendation = _recommendation(taxonomy, disagreement_summary)
    return T053RootPriorFailureAnalysisReport(
        input_artifacts=artifacts,
        comparison_summary=comparison_summary,
        t052_result_summary=result_summary,
        disagreement_summary=disagreement_summary,
        disagreement_records=disagreement_records,
        subset_summaries=subset_summaries,
        allocation_telemetry_summary=allocation_summary,
        action_comparison_diagnostics=action_diagnostics,
        failure_taxonomy=taxonomy,
        recommendation=recommendation,
        unavailable_diagnostics=_dedupe_unavailable(unavailable),
    )


def load_t053_t052_comparison_analysis_inputs(
    stream: TextIO,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[int, dict[str, Any]]]]:
    """Stream the current T052/T047 comparison artifact into T053 inputs."""

    metadata: dict[str, Any] | None = None
    battle_comparisons: list[dict[str, Any]] = []
    disagreement_indices: set[int] = set()
    controller_results: dict[str, dict[int, dict[str, Any]]] = {
        label: {} for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
    }
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
            comparison = _require_mapping(row.get("comparison"), "comparison")
            battle_comparisons.append(comparison)
            if _is_disagreement(comparison):
                index = _optional_int(comparison.get("comparison_index"))
                if index is not None:
                    disagreement_indices.add(index)
        elif row_type == "controller_result":
            label = _require_non_empty_string(row.get("label"), "controller label")
            result = _require_mapping(row.get("result"), "result")
            cohort_index = _optional_int(result.get("cohort_index"))
            if label in controller_results and cohort_index in disagreement_indices:
                controller_results[label][cohort_index] = result
        else:
            raise ValueError(f"line {line_number}: unknown row type {row_type!r}")
    if metadata is None:
        raise ValueError("missing root-prior guided comparison metadata")
    return metadata, battle_comparisons, controller_results


def dump_t053_root_prior_failure_analysis_report_json(
    report: T053RootPriorFailureAnalysisReport,
    stream: TextIO,
) -> None:
    """Write a deterministic current-schema T053 JSON artifact."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_t053_root_prior_failure_analysis_report_json(
    stream: TextIO,
) -> T053RootPriorFailureAnalysisReport:
    """Load and validate a current-schema T053 report."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T053 root-prior failure analysis JSON") from exc
    return t053_root_prior_failure_analysis_report_from_dict(raw)


def t053_root_prior_failure_analysis_report_from_dict(
    raw: Mapping[str, Any],
) -> T053RootPriorFailureAnalysisReport:
    """Validate a current-schema T053 report dictionary."""

    if not isinstance(raw, Mapping):
        raise ValueError("T053 root-prior failure analysis report must be an object")
    schema_id = raw.get("schema_id")
    if schema_id != T053_FAILURE_ANALYSIS_SCHEMA_ID:
        raise ValueError(
            f"unsupported T053 failure analysis schema_id {schema_id!r}; "
            f"expected {T053_FAILURE_ANALYSIS_SCHEMA_ID!r}"
        )
    format_version = raw.get("format_version")
    if format_version != T053_FAILURE_ANALYSIS_FORMAT_VERSION:
        raise ValueError(
            "unsupported T053 failure analysis format_version "
            f"{format_version!r}; expected {T053_FAILURE_ANALYSIS_FORMAT_VERSION}"
        )
    return T053RootPriorFailureAnalysisReport(
        input_artifacts=_require_list_of_mappings(
            raw.get("input_artifacts"),
            "input_artifacts",
        ),
        comparison_summary=_require_mapping(
            raw.get("comparison_summary"),
            "comparison_summary",
        ),
        t052_result_summary=_require_mapping(
            raw.get("t052_result_summary"),
            "t052_result_summary",
        ),
        disagreement_summary=_require_mapping(
            raw.get("disagreement_summary"),
            "disagreement_summary",
        ),
        disagreement_records=_require_list_of_mappings(
            raw.get("disagreement_records"),
            "disagreement_records",
        ),
        subset_summaries=_require_mapping(
            raw.get("subset_summaries"), "subset_summaries"
        ),
        allocation_telemetry_summary=_require_mapping(
            raw.get("allocation_telemetry_summary"),
            "allocation_telemetry_summary",
        ),
        action_comparison_diagnostics=_require_mapping(
            raw.get("action_comparison_diagnostics"),
            "action_comparison_diagnostics",
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
            raw.get("evidence_boundary", T053_EVIDENCE_BOUNDARY),
            "evidence_boundary",
        ),
    )


def format_t053_root_prior_failure_analysis_report(
    report: T053RootPriorFailureAnalysisReport,
) -> str:
    """Format concise T053 diagnostics for stderr and PR summaries."""

    summary = report.disagreement_summary
    subsets = report.subset_summaries
    taxonomy = report.failure_taxonomy
    recommendation = report.recommendation
    lines = [
        "T053 root-prior allocation failure analysis",
        (
            "scope: offline T052 diagnostics only; no simulator, training, "
            "controller promotion, live-game, natural A20, broad-training, "
            "normal-information, or final-agent claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        f"cohort identity: {report.comparison_summary.get('cohort_identity', 'missing')}",
        (
            "disagreement records: "
            f"{summary.get('disagreement_count', 0)}/"
            f"{summary.get('evaluated_record_count', 0)} "
            f"(win/loss={summary.get('win_loss_disagreement_count', 0)}, "
            f"terminal-hp-only={summary.get('terminal_hp_only_disagreement_count', 0)})"
        ),
        "subset disagreements:",
    ]
    for name in ("boss_only", "act2_plus"):
        item = subsets.get(name, {})
        lines.append(
            "  "
            + name
            + ": records="
            + str(item.get("disagreement_count", 0))
            + ", root="
            + _win_loss_text(item.get("root_prior_guided_outcomes"))
            + ", baseline="
            + _win_loss_text(item.get("baseline_oracle_outcomes"))
            + ", post-search="
            + _win_loss_text(item.get("post_search_model_guided_outcomes"))
        )
    lines.append("failure taxonomy:")
    for key in T053_TAXONOMY_CATEGORIES:
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
    lines.append(
        "recommended next task: "
        + str(recommendation.get("recommended_next_task", "missing"))
    )
    lines.append("unavailable diagnostics:")
    if report.unavailable_diagnostics:
        for item in report.unavailable_diagnostics:
            lines.append(
                f"  - {item.get('diagnostic', 'missing')}: "
                f"{item.get('reason', item.get('missing_field', 'missing'))}"
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
    comparison_metadata: Mapping[str, Any],
    battle_comparisons: Sequence[Mapping[str, Any]],
    controller_results: Mapping[str, Mapping[int, Mapping[str, Any]]],
    unavailable: list[dict[str, Any]],
) -> list[str]:
    problems: list[str] = []
    roles = [str(item.get("role") or "") for item in input_artifacts]
    for role in T053_REQUIRED_INPUT_ROLES:
        if role not in roles:
            problems.append(f"missing required T052 input artifact role {role}")
    if len(set(roles)) != len(roles):
        problems.append("duplicate T052 input artifact roles")
    for artifact in input_artifacts:
        if artifact.get("sha256_verified") is not True:
            problems.append(f"{artifact.get('role', 'artifact')}: sha256 not verified")
    problems.extend(_comparison_metadata_problems(comparison_metadata))
    comparison_count = _optional_int(comparison_metadata.get("battle_comparison_count"))
    if comparison_count is not None and comparison_count != len(battle_comparisons):
        problems.append(
            "battle_comparison_count mismatch: metadata "
            f"{comparison_count}, streamed {len(battle_comparisons)}"
        )
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        missing = sorted(
            index
            for index in _disagreement_indices(battle_comparisons)
            if index not in controller_results.get(label, {})
        )
        if missing:
            problems.append(
                f"{label}: missing controller_result rows for disagreement indices "
                + ", ".join(str(index) for index in missing)
            )
    for result in controller_results.get(ROOT_PRIOR_GUIDED_LABEL, {}).values():
        malformed = _root_prior_allocation_summary_for_result(result)[
            "malformed_allocation_metadata_count"
        ]
        if malformed:
            _add_unavailable(
                unavailable,
                diagnostic="root_prior_allocation_metadata",
                reason="malformed allocation metadata in root-prior disagreement row",
                cohort_index=_optional_int(result.get("cohort_index")),
            )
    return list(dict.fromkeys(problems))


def _validate_comparison_metadata(metadata: Mapping[str, Any]) -> None:
    problems = _comparison_metadata_problems(metadata)
    if problems:
        raise ValueError("; ".join(problems))


def _comparison_metadata_problems(metadata: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if metadata.get("schema_id") != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID:
        problems.append(
            "unsupported root-prior guided comparison schema_id "
            f"{metadata.get('schema_id')!r}; expected "
            f"{ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_SCHEMA_ID!r}"
        )
    if (
        metadata.get("format_version")
        != ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION
    ):
        problems.append(
            "unsupported root-prior guided comparison format_version "
            f"{metadata.get('format_version')!r}; expected "
            f"{ROOT_PRIOR_GUIDED_SEARCH_COMPARISON_FORMAT_VERSION}"
        )
    arms = metadata.get("controller_arms")
    if not isinstance(arms, list):
        problems.append("controller_arms must be a list")
        labels: list[str] = []
    else:
        labels = [
            str(_mapping(arm).get("label") or "")
            for arm in arms
            if isinstance(arm, Mapping)
        ]
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        if label not in labels:
            problems.append(f"missing required arm {label}")
    if len(set(labels)) != len(labels):
        problems.append("duplicate controller arm labels")
    if metadata.get("source_match_status") != "matched":
        problems.append("T052 comparison source/cohort match status is not matched")
    for key in ("report_problems", "validation_problems", "problems"):
        values = metadata.get(key)
        if isinstance(values, list) and values:
            problems.append(f"T052 comparison metadata has {key}: {values}")
    summaries = _mapping(metadata.get("controller_summaries"))
    for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS:
        regime = _mapping(summaries.get(label)).get("information_regime")
        if regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(
                f"{label}: information regime {regime!r}; expected "
                f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
            )
    allocation = _mapping(metadata.get("root_prior_allocation_summary"))
    if _optional_int(allocation.get("malformed_metadata_count")) not in (None, 0):
        problems.append("T052 root-prior allocation summary has malformed metadata")
    return list(dict.fromkeys(problems))


def _comparison_summary(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": metadata.get("schema_id"),
        "format_version": metadata.get("format_version"),
        "cohort_identity": metadata.get("cohort_identity"),
        "run_scale": metadata.get("run_scale"),
        "evidence_boundary": metadata.get("evidence_boundary"),
        "controller_labels": [
            _mapping(arm).get("label")
            for arm in _sequence(metadata.get("controller_arms"))
        ],
        "required_arms": list(REQUIRED_ROOT_PRIOR_COMPARISON_LABELS),
        "source_match_status": metadata.get("source_match_status"),
        "evaluation_successful": metadata.get("evaluation_successful"),
        "battle_comparison_count": metadata.get("battle_comparison_count"),
        "comparison_config": _json_safe_mapping(
            _mapping(metadata.get("comparison_config"))
        ),
        "controller_summaries": _json_safe_mapping(
            _mapping(metadata.get("controller_summaries"))
        ),
        "aggregate_outcomes": _json_safe_mapping(
            _mapping(metadata.get("aggregate_outcomes"))
        ),
        "budget_comparison": _json_safe_mapping(
            _mapping(metadata.get("budget_comparison"))
        ),
        "root_prior_allocation_summary": _json_safe_mapping(
            _mapping(metadata.get("root_prior_allocation_summary"))
        ),
        "outcome_comparison": _json_safe_mapping(
            _mapping(metadata.get("outcome_comparison"))
        ),
    }


def _is_disagreement(comparison: Mapping[str, Any]) -> bool:
    arms = _mapping(comparison.get("arms"))
    root = _mapping(arms.get(ROOT_PRIOR_GUIDED_LABEL))
    baseline = _mapping(arms.get(BASELINE_ORACLE_LABEL))
    post = _mapping(arms.get(POST_SEARCH_MODEL_GUIDED_LABEL))
    if not root or not baseline or not post:
        return False
    root_signature = _outcome_signature(root)
    return root_signature != _outcome_signature(
        baseline
    ) or root_signature != _outcome_signature(post)


def _disagreement_record(
    comparison: Mapping[str, Any],
    controller_results: Mapping[str, Mapping[int, Mapping[str, Any]]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    cohort_index = _optional_int(comparison.get("comparison_index"))
    if cohort_index is None:
        cohort_index = -1
    result_by_label = {
        label: _mapping(controller_results.get(label, {}).get(cohort_index))
        for label in REQUIRED_ROOT_PRIOR_COMPARISON_LABELS
    }
    fallback_arms = _mapping(comparison.get("arms"))
    baseline = result_by_label[BASELINE_ORACLE_LABEL] or _mapping(
        fallback_arms.get(BASELINE_ORACLE_LABEL)
    )
    post = result_by_label[POST_SEARCH_MODEL_GUIDED_LABEL] or _mapping(
        fallback_arms.get(POST_SEARCH_MODEL_GUIDED_LABEL)
    )
    root = result_by_label[ROOT_PRIOR_GUIDED_LABEL] or _mapping(
        fallback_arms.get(ROOT_PRIOR_GUIDED_LABEL)
    )
    source = _source_identity(
        comparison=comparison,
        preferred_result=root or baseline or post,
    )
    allocation = _root_prior_allocation_summary_for_result(root)
    action_comparison = _selected_action_comparison(
        baseline=baseline,
        post=post,
        root=root,
        unavailable=unavailable,
        cohort_index=cohort_index,
    )
    outcome = {
        "root_prior_vs_baseline": _outcome_delta(root, baseline),
        "root_prior_vs_post_search": _outcome_delta(root, post),
        "root_prior_harmful_vs_any": _is_harmful(root, baseline)
        or _is_harmful(root, post),
        "root_prior_beneficial_vs_any": _is_harmful(baseline, root)
        or _is_harmful(post, root),
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
    }
    return {
        "cohort_index": cohort_index,
        "subset": _subset_label(source),
        "source_identity": source,
        "outcome_delta": outcome,
        "arms": {
            BASELINE_ORACLE_LABEL: _arm_record_summary(baseline),
            POST_SEARCH_MODEL_GUIDED_LABEL: _arm_record_summary(post),
            ROOT_PRIOR_GUIDED_LABEL: _arm_record_summary(root),
        },
        "root_prior_allocation": allocation,
        "selected_action_comparison": action_comparison,
        "taxonomy_labels": _record_taxonomy_labels(
            outcome=outcome,
            allocation=allocation,
            action_comparison=action_comparison,
        ),
        "problems": list(_sequence(comparison.get("problems"))),
    }


def _arm_record_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
    search_summary = _mapping(telemetry.get("search_telemetry_summary"))
    return {
        "present": bool(result),
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
    }


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
            selected_actions.append(
                {
                    "decision_index": index,
                    "selected_index": selected,
                    "target": _target_summary(target),
                }
            )
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
                    (_as_int(row.get("visits")) for row in rows), default=0
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


def _selected_action_comparison(
    *,
    baseline: Mapping[str, Any],
    post: Mapping[str, Any],
    root: Mapping[str, Any],
    unavailable: list[dict[str, Any]],
    cohort_index: int,
) -> dict[str, Any]:
    root_reports = _root_prior_decision_reports(root)
    baseline_actions, baseline_reason = _selected_actions_for_non_root_arm(baseline)
    post_actions, post_reason = _selected_actions_for_non_root_arm(post)
    root_actions = [
        _target_summary(_mapping(report.get("target"))) for report in root_reports
    ]
    diagnostics: dict[str, Any] = {
        "status": "available",
        "root_prior_decision_count": len(root_actions),
        "baseline_decision_count": len(baseline_actions),
        "post_search_decision_count": len(post_actions),
        "root_prior_first_actions": root_actions[:5],
        "baseline_first_actions": baseline_actions[:5],
        "post_search_first_actions": post_actions[:5],
    }
    missing_reasons = []
    if baseline_reason is not None:
        missing_reasons.append(f"baseline_oracle_search:{baseline_reason}")
    if post_reason is not None:
        missing_reasons.append(f"model_guided_oracle_search_v2:{post_reason}")
    if not root_actions:
        missing_reasons.append("root_prior_guided_oracle_search:missing target actions")
    if missing_reasons:
        diagnostics.update(
            {
                "status": "unavailable",
                "reason": "; ".join(missing_reasons),
                "exact_step_level_matching": False,
            }
        )
        _add_unavailable(
            unavailable,
            diagnostic="step_level_action_identity_comparison",
            reason=diagnostics["reason"],
            cohort_index=cohort_index,
        )
        return diagnostics
    comparable_count = min(len(root_actions), len(baseline_actions), len(post_actions))
    baseline_diff = _first_action_difference(root_actions, baseline_actions)
    post_diff = _first_action_difference(root_actions, post_actions)
    diagnostics.update(
        {
            "exact_step_level_matching": True,
            "comparable_decision_count": comparable_count,
            "first_difference_vs_baseline": baseline_diff,
            "first_difference_vs_post_search": post_diff,
            "root_prior_matches_baseline_action_count": _matching_action_count(
                root_actions,
                baseline_actions,
            ),
            "root_prior_matches_post_search_action_count": _matching_action_count(
                root_actions,
                post_actions,
            ),
        }
    )
    return diagnostics


def _selected_actions_for_non_root_arm(
    result: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    telemetry = _mapping(result.get("controller_compute_telemetry"))
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
        missing_identity = True
    if actions:
        reason = "some selected action identities missing" if missing_identity else None
        return actions, reason
    return [], "selected action identity unavailable in T052 telemetry"


def _target_summary(target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selected_index": target.get("legal_action_index"),
        "visits": target.get("visits"),
        "mean_value": target.get("mean_value"),
        "score": target.get("score"),
        "selection_rule": target.get("selection_rule"),
        "action_identity": _json_safe_mapping(_mapping(target.get("action_identity"))),
    }


def _source_identity(
    *,
    comparison: Mapping[str, Any],
    preferred_result: Mapping[str, Any],
) -> dict[str, Any]:
    source = _mapping(comparison.get("source"))
    metadata = _mapping(preferred_result.get("structural_metadata"))
    return {
        "cohort_index": preferred_result.get(
            "cohort_index",
            source.get("cohort_index", comparison.get("comparison_index")),
        ),
        "source_checkpoint_id": preferred_result.get(
            "source_checkpoint_id",
            source.get("source_checkpoint_id"),
        ),
        "source_seed": preferred_result.get("source_seed", source.get("source_seed")),
        "source_run_id": preferred_result.get(
            "source_run_id",
            source.get("source_run_id", metadata.get("source_run_id")),
        ),
        "source_battle_index": preferred_result.get(
            "source_battle_index",
            source.get("source_battle_index", metadata.get("source_battle_index")),
        ),
        "t051_source_arm_role": metadata.get("t051_source_arm_role"),
        "t051_source_arm_label": metadata.get("t051_source_arm_label"),
        "act": metadata.get("act"),
        "room_type": metadata.get("room_type"),
        "encounter_id": metadata.get("encounter_id"),
        "floor": metadata.get("floor"),
        "public_context_status": preferred_result.get("public_context_status"),
        "public_context_replay_status": preferred_result.get(
            "public_context_replay_status"
        ),
        "structured_outcome_status": preferred_result.get(
            "structured_battle_outcome_status"
        ),
        "information_regime": preferred_result.get("information_regime"),
        "selection_reasons": _sequence(metadata.get("t052_selection_reasons")),
        "structural_metadata": _json_safe_mapping(metadata),
    }


def _disagreement_summary(
    disagreement_records: Sequence[Mapping[str, Any]],
    *,
    total_battle_count: int,
) -> dict[str, Any]:
    win_loss = 0
    hp_only = 0
    harmful = 0
    beneficial = 0
    by_subset = Counter()
    for record in disagreement_records:
        delta = _mapping(record.get("outcome_delta"))
        if delta.get("terminal_hp_only_difference"):
            hp_only += 1
        else:
            win_loss += 1
        if delta.get("root_prior_harmful_vs_any"):
            harmful += 1
        if delta.get("root_prior_beneficial_vs_any"):
            beneficial += 1
        by_subset[str(record.get("subset") or MISSING_VALUE)] += 1
    return {
        "evaluated_record_count": total_battle_count,
        "disagreement_definition": (
            "root-prior termination_status or terminal_absolute_hp differs from "
            "baseline Oracle or post-search model-guided on the matched source"
        ),
        "disagreement_count": len(disagreement_records),
        "disagreement_rate": _rate(len(disagreement_records), total_battle_count),
        "win_loss_disagreement_count": win_loss,
        "terminal_hp_only_disagreement_count": hp_only,
        "root_prior_harmful_record_count": harmful,
        "root_prior_beneficial_record_count": beneficial,
        "by_subset": _counter_dict(by_subset),
        "cohort_indices": [
            record.get("cohort_index") for record in disagreement_records
        ],
    }


def _subset_summaries(
    disagreement_records: Sequence[Mapping[str, Any]],
    controller_results: Mapping[str, Mapping[int, Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    all_indices_by_subset: dict[str, set[int]] = {
        "boss_only": set(),
        "act2_plus": set(),
    }
    for result in controller_results.get(ROOT_PRIOR_GUIDED_LABEL, {}).values():
        source = _source_identity(comparison={}, preferred_result=result)
        subset = _subset_label(source)
        all_indices_by_subset.setdefault(subset, set()).add(
            _as_int(result.get("cohort_index"))
        )
    records_by_subset: dict[str, list[Mapping[str, Any]]] = {
        "boss_only": [],
        "act2_plus": [],
    }
    for record in disagreement_records:
        records_by_subset.setdefault(str(record.get("subset")), []).append(record)
    output: dict[str, dict[str, Any]] = {}
    for subset in ("boss_only", "act2_plus"):
        records = records_by_subset.get(subset, [])
        output[subset] = {
            "disagreement_count": len(records),
            "cohort_indices": [record.get("cohort_index") for record in records],
            "baseline_oracle_outcomes": _arm_outcome_counts(
                records, BASELINE_ORACLE_LABEL
            ),
            "post_search_model_guided_outcomes": _arm_outcome_counts(
                records,
                POST_SEARCH_MODEL_GUIDED_LABEL,
            ),
            "root_prior_guided_outcomes": _arm_outcome_counts(
                records,
                ROOT_PRIOR_GUIDED_LABEL,
            ),
            "terminal_hp": {
                BASELINE_ORACLE_LABEL: _arm_hp_values(records, BASELINE_ORACLE_LABEL),
                POST_SEARCH_MODEL_GUIDED_LABEL: _arm_hp_values(
                    records,
                    POST_SEARCH_MODEL_GUIDED_LABEL,
                ),
                ROOT_PRIOR_GUIDED_LABEL: _arm_hp_values(
                    records, ROOT_PRIOR_GUIDED_LABEL
                ),
            },
            "decision_counts": {
                BASELINE_ORACLE_LABEL: _arm_decision_counts(
                    records,
                    BASELINE_ORACLE_LABEL,
                ),
                POST_SEARCH_MODEL_GUIDED_LABEL: _arm_decision_counts(
                    records,
                    POST_SEARCH_MODEL_GUIDED_LABEL,
                ),
                ROOT_PRIOR_GUIDED_LABEL: _arm_decision_counts(
                    records,
                    ROOT_PRIOR_GUIDED_LABEL,
                ),
            },
            "root_prior_allocation": _subset_allocation_summary(records),
            "unavailable_telemetry_counts": _subset_unavailable_counts(records),
        }
    return output


def _allocation_telemetry_summary(
    disagreement_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    totals = Counter()
    for record in disagreement_records:
        allocation = _mapping(record.get("root_prior_allocation"))
        totals["decision_count"] += _as_int(allocation.get("decision_count"))
        totals["malformed_allocation_metadata_count"] += _as_int(
            allocation.get("malformed_allocation_metadata_count")
        )
        totals["positive_prior_count"] += _as_int(
            allocation.get("positive_prior_count")
        )
        totals["provided_prior_count"] += _as_int(
            allocation.get("provided_prior_count")
        )
        totals["missing_prior_decision_count"] += _as_int(
            allocation.get("missing_prior_decision_count")
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
    decision_count = totals["decision_count"]
    return {
        **_counter_dict(totals),
        "positive_prior_selected_rate": _rate(
            totals["positive_prior_selected_count"],
            decision_count,
        ),
        "malformed_allocation_metadata_rate": _rate(
            totals["malformed_allocation_metadata_count"],
            decision_count,
        ),
        "missing_prior_decision_rate": _rate(
            totals["missing_prior_decision_count"],
            decision_count,
        ),
    }


def _action_comparison_diagnostics(
    disagreement_records: Sequence[Mapping[str, Any]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter()
    exact = 0
    for record in disagreement_records:
        diagnostic = _mapping(record.get("selected_action_comparison"))
        status = str(diagnostic.get("status") or MISSING_VALUE)
        status_counts[status] += 1
        if diagnostic.get("exact_step_level_matching"):
            exact += 1
    if not exact and disagreement_records:
        _add_unavailable(
            unavailable,
            diagnostic="aggregate_step_level_action_identity_comparison",
            reason=(
                "T052 comparison does not expose compatible exact per-decision "
                "selected action identities for all required arms"
            ),
            cohort_index=None,
        )
    return {
        "status_counts": _counter_dict(status_counts),
        "exact_step_level_matching_record_count": exact,
        "unavailable_record_count": status_counts.get("unavailable", 0),
        "record_count": len(disagreement_records),
    }


def _failure_taxonomy(
    disagreement_records: Sequence[Mapping[str, Any]],
    *,
    action_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    counts = Counter()
    for record in disagreement_records:
        for label in _sequence(record.get("taxonomy_labels")):
            counts[str(label)] += 1
    total = len(disagreement_records)
    taxonomy: dict[str, Any] = {}
    for category in T053_TAXONOMY_CATEGORIES:
        count = int(counts.get(category, 0))
        taxonomy[category] = {
            "status": "supported" if count else "not_observed",
            "evidence_count": count,
            "evidence_proportion": _rate(count, total),
            "cohort_indices": [
                record.get("cohort_index")
                for record in disagreement_records
                if category in _sequence(record.get("taxonomy_labels"))
            ],
        }
    if action_diagnostics.get("unavailable_record_count"):
        item = taxonomy["telemetry_or_schema_insufficient"]
        item["status"] = "supported"
        item["evidence_count"] = max(
            _as_int(item.get("evidence_count")),
            _as_int(action_diagnostics.get("unavailable_record_count")),
        )
        item["evidence_proportion"] = _rate(_as_int(item["evidence_count"]), total)
        item["reason"] = (
            "exact step-level selected-action comparison was unavailable for "
            "one or more disagreement records"
        )
    return taxonomy


def _recommendation(
    taxonomy: Mapping[str, Any],
    disagreement_summary: Mapping[str, Any],
) -> dict[str, Any]:
    harmful = _as_int(
        _mapping(taxonomy.get("harmful_root_prior_allocation")).get("evidence_count")
    )
    no_op = _as_int(
        _mapping(taxonomy.get("no_op_or_ineffective_root_prior_allocation")).get(
            "evidence_count"
        )
    )
    weak_prior = _as_int(
        _mapping(taxonomy.get("weak_or_miscalibrated_checkpoint_prior")).get(
            "evidence_count"
        )
    )
    return {
        "recommended_next_task": T053_RECOMMENDED_NEXT_TASK,
        "recommendation_count": 1,
        "rationale": (
            "T052/T053 found "
            f"{harmful} harmful root-prior disagreement record(s), "
            f"{no_op} no-op/HP-only disagreement record(s), and "
            f"{weak_prior} record(s) with concentrated checkpoint priors. "
            "The next branch should test guardrails or calibration for native "
            "root-prior allocation before changing training, non-combat, or "
            "promotion paths."
        ),
        "based_on": {
            "disagreement_count": disagreement_summary.get("disagreement_count"),
            "win_loss_disagreement_count": disagreement_summary.get(
                "win_loss_disagreement_count"
            ),
            "root_prior_harmful_record_count": disagreement_summary.get(
                "root_prior_harmful_record_count"
            ),
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


def _record_taxonomy_labels(
    *,
    outcome: Mapping[str, Any],
    allocation: Mapping[str, Any],
    action_comparison: Mapping[str, Any],
) -> list[str]:
    labels: list[str] = []
    if outcome.get("root_prior_harmful_vs_any"):
        labels.append("harmful_root_prior_allocation")
    if outcome.get("terminal_hp_only_difference"):
        labels.append("no_op_or_ineffective_root_prior_allocation")
    if _as_int(allocation.get("positive_prior_count")) > 0:
        labels.append("weak_or_miscalibrated_checkpoint_prior")
    if _as_int(allocation.get("positive_prior_selected_count")) < _as_int(
        allocation.get("decision_count")
    ):
        labels.append("native_root_outcome_tie_broken_differently")
    if action_comparison.get("status") != "available" or _as_int(
        allocation.get("malformed_allocation_metadata_count")
    ):
        labels.append("telemetry_or_schema_insufficient")
    return list(dict.fromkeys(labels))


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


def _restore_status(result: Mapping[str, Any]) -> str:
    if not result:
        return "missing"
    if result.get("termination_status") == "error":
        return "error"
    if result.get("restoration_method"):
        return "restored"
    return "unavailable"


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
            "right": "missing"
            if count >= len(right)
            else _json_safe_mapping(right[count]),
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


def _arm_outcome_counts(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, int]:
    counts = Counter()
    for record in records:
        arm = _mapping(_mapping(record.get("arms")).get(label))
        counts[str(arm.get("termination_status") or MISSING_VALUE)] += 1
    return _counter_dict(counts)


def _arm_hp_values(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> list[int | None]:
    return [
        _optional_int(
            _mapping(_mapping(record.get("arms")).get(label)).get(
                "terminal_absolute_hp"
            )
        )
        for record in records
    ]


def _arm_decision_counts(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> list[int | None]:
    return [
        _optional_int(
            _mapping(_mapping(record.get("arms")).get(label)).get("decision_count")
        )
        for record in records
    ]


def _subset_allocation_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _allocation_telemetry_summary(records)


def _subset_unavailable_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for record in records:
        comparison = _mapping(record.get("selected_action_comparison"))
        if comparison.get("status") != "available":
            counts["selected_action_comparison"] += 1
        allocation = _mapping(record.get("root_prior_allocation"))
        if _as_int(allocation.get("malformed_allocation_metadata_count")):
            counts["malformed_allocation_metadata"] += 1
        if not _as_int(allocation.get("decision_count")):
            counts["root_prior_decision_reports"] += 1
    return _counter_dict(counts)


def _disagreement_indices(
    battle_comparisons: Sequence[Mapping[str, Any]],
) -> set[int]:
    indices: set[int] = set()
    for item in battle_comparisons:
        index = _optional_int(item.get("comparison_index"))
        if index is not None and _is_disagreement(item):
            indices.add(index)
    return indices


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
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        output.append(_require_mapping(item, f"{label}[{index}]"))
    return output


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _add_unavailable(
    unavailable: list[dict[str, Any]],
    *,
    diagnostic: str,
    reason: str,
    cohort_index: int | None,
) -> None:
    unavailable.append(
        {
            "diagnostic": diagnostic,
            "reason": reason,
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


def _optional_rate(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.3f}"


def _win_loss_text(value: Any) -> str:
    mapping = _mapping(value)
    wins = _as_int(mapping.get("win"))
    losses = _as_int(mapping.get("loss"))
    truncated = _as_int(mapping.get("truncated"))
    errors = _as_int(mapping.get("error"))
    extras = []
    if truncated:
        extras.append(f"T{truncated}")
    if errors:
        extras.append(f"E{errors}")
    suffix = "" if not extras else " " + "/".join(extras)
    return f"{wins}W/{losses}L{suffix}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
