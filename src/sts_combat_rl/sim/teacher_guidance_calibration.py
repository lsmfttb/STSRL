"""Offline checkpoint-vs-teacher calibration diagnostics.

This module compares search-guidance checkpoint scores against explicit T024
teacher policy targets. It does not train a model, run a simulator, choose game
actions, or claim controller strength.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import math
from typing import Any, TextIO

from sts_combat_rl.sim.model_input import (
    build_model_input_batch,
    decision_context_from_model_input_batch,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
)
from sts_combat_rl.sim.trainer_input import (
    BEHAVIOR_ACTION_AVAILABLE,
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    TRAINER_POLICY_TARGET_SCHEMA_ID,
    TRAINER_POLICY_TARGET_SCHEMA_VERSION,
    TrainerInputDataset,
    TrainerInputRecord,
)


TEACHER_GUIDANCE_CALIBRATION_REPORT_SCHEMA_ID = "teacher-guidance-calibration-report-v1"
TEACHER_GUIDANCE_CALIBRATION_REPORT_FORMAT_VERSION = 1
SUPPORTED_TEACHER_TARGET_KINDS = (
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
)
DEFAULT_CALIBRATION_TOP_K = 3
CALIBRATION_BIN_COUNT = 10
EPSILON = 1e-12
EVIDENCE_BOUNDARY = {
    "information_regime": "full_simulator_state_oracle_like",
    "not_normal_information": True,
    "not_live_game_evidence": True,
    "not_broad_training_evidence": True,
    "not_controller_strength_evidence": True,
    "not_search_controller_integration": True,
}


@dataclass(frozen=True)
class CheckpointCalibrationReport:
    """Calibration metrics for one compatible checkpoint."""

    scorer_name: str
    checkpoint_provenance: SearchGuidanceCheckpointProvenance
    policy_target_kind: str
    policy_target_source: str
    top_k: int
    record_count: int
    evaluated_record_count: int
    skipped_row_counts: dict[str, int] = field(default_factory=dict)
    teacher_target_metrics: dict[str, Any] = field(default_factory=dict)
    behavior_action_metrics: dict[str, Any] = field(default_factory=dict)
    calibration: dict[str, Any] = field(default_factory=dict)
    source_coverage: dict[str, Any] = field(default_factory=dict)
    decision_metrics: list[dict[str, Any]] = field(default_factory=list)
    warnings: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    @property
    def calibration_ok(self) -> bool:
        return self.evaluated_record_count > 0 and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_ok": self.calibration_ok,
            "scorer_name": self.scorer_name,
            "checkpoint_provenance": self.checkpoint_provenance.to_dict(),
            "policy_target_kind": self.policy_target_kind,
            "policy_target_source": self.policy_target_source,
            "top_k": self.top_k,
            "record_count": self.record_count,
            "evaluated_record_count": self.evaluated_record_count,
            "skipped_record_count": sum(self.skipped_row_counts.values()),
            "skipped_row_counts": _counter_dict(self.skipped_row_counts),
            "teacher_target_metrics": _json_safe_value(self.teacher_target_metrics),
            "behavior_action_metrics": _json_safe_value(self.behavior_action_metrics),
            "calibration": _json_safe_value(self.calibration),
            "source_coverage": _json_safe_value(self.source_coverage),
            "decision_metrics": _json_safe_value(self.decision_metrics),
            "warnings": list(self.warnings),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class TeacherGuidanceCalibrationReport:
    """Versioned artifact-level T027 report."""

    trainer_input_artifact_identity: dict[str, Any]
    dataset_summary: dict[str, Any]
    checkpoint_reports: list[CheckpointCalibrationReport]
    evidence_boundary: dict[str, Any] = field(
        default_factory=lambda: dict(EVIDENCE_BOUNDARY)
    )
    schema_id: str = TEACHER_GUIDANCE_CALIBRATION_REPORT_SCHEMA_ID
    format_version: int = TEACHER_GUIDANCE_CALIBRATION_REPORT_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return bool(self.checkpoint_reports) and all(
            checkpoint.calibration_ok for checkpoint in self.checkpoint_reports
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "command_passed": self.command_passed,
            "trainer_input_artifact_identity": _json_safe_value(
                self.trainer_input_artifact_identity
            ),
            "dataset_summary": _json_safe_value(self.dataset_summary),
            "checkpoint_reports": [
                checkpoint.to_dict() for checkpoint in self.checkpoint_reports
            ],
            "evidence_boundary": dict(self.evidence_boundary),
        }


@dataclass(frozen=True)
class _TargetDistribution:
    target_probabilities: list[float]
    target_top_index: int
    target_top_probability: float


def build_teacher_guidance_calibration_report(
    dataset: TrainerInputDataset,
    scorers: Sequence[SearchGuidanceScorer],
    *,
    trainer_input_artifact_identity: Mapping[str, Any],
    top_k: int = DEFAULT_CALIBRATION_TOP_K,
) -> TeacherGuidanceCalibrationReport:
    """Build a deterministic offline checkpoint-vs-teacher report."""

    if top_k <= 0:
        raise ValueError("teacher guidance calibration top_k must be positive")
    if not scorers:
        raise ValueError(
            "teacher guidance calibration requires at least one checkpoint"
        )
    if not dataset.records:
        raise ValueError("teacher guidance calibration requires trainer records")
    if dataset.format_version != TRAINER_INPUT_DATASET_FORMAT_VERSION:
        raise ValueError("trainer input artifact is not current format version")
    if dataset.policy_target_schema_id != TRAINER_POLICY_TARGET_SCHEMA_ID:
        raise ValueError("trainer input policy target schema is not current")
    if dataset.policy_target_schema_version != TRAINER_POLICY_TARGET_SCHEMA_VERSION:
        raise ValueError("trainer input policy target schema version is not current")

    target_kind = _single_target_kind(dataset.records)
    if target_kind not in SUPPORTED_TEACHER_TARGET_KINDS:
        raise ValueError(
            "teacher guidance calibration requires Oracle teacher targets, got "
            f"{target_kind!r}"
        )
    target_source_counts = _counter_dict(
        Counter(record.policy_target_source for record in dataset.records)
    )
    target_source = _single_count_key(target_source_counts)
    batch = build_model_input_batch(dataset)
    if batch.problems:
        raise ValueError(
            "trainer input cannot be rebuilt as model input: "
            + "; ".join(dict.fromkeys(batch.problems))
        )

    identity = _json_safe_mapping(trainer_input_artifact_identity)
    checkpoint_reports = [
        _build_checkpoint_report(
            dataset,
            batch,
            scorer,
            trainer_input_artifact_identity=identity,
            policy_target_kind=target_kind,
            policy_target_source=target_source,
            top_k=top_k,
        )
        for scorer in scorers
    ]
    return TeacherGuidanceCalibrationReport(
        trainer_input_artifact_identity=identity,
        dataset_summary=_dataset_summary(
            dataset,
            policy_target_kind=target_kind,
            policy_target_source_counts=target_source_counts,
        ),
        checkpoint_reports=checkpoint_reports,
    )


def dump_teacher_guidance_calibration_report_json(
    report: TeacherGuidanceCalibrationReport,
    stream: TextIO,
) -> None:
    """Write a deterministic calibration report JSON document."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def format_teacher_guidance_calibration_report(
    report: TeacherGuidanceCalibrationReport,
    *,
    detail_limit: int = 5,
) -> str:
    """Format T027 calibration evidence for stderr and PR summaries."""

    dataset = report.dataset_summary
    lines = [
        "Teacher guidance calibration report",
        (
            "scope: offline checkpoint-vs-teacher diagnostics only; no simulator, "
            "controller, live-game, broad-training, or strength claim"
        ),
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "evidence boundary: full_simulator_state_oracle_like teacher "
            "supervision; not normal-information, live-game, broad-training, "
            "or controller-strength evidence"
        ),
        (
            "trainer input sha256: "
            f"{report.trainer_input_artifact_identity.get('sha256', '(missing)')}"
        ),
        f"trainer records: {dataset.get('record_count', 0)}",
        f"policy target kind: {dataset.get('policy_target_kind', 'missing')}",
        f"policy target source: {dataset.get('policy_target_source', 'missing')}",
    ]
    _append_mapping(lines, "target sources", dataset.get("policy_target_source_counts"))
    _append_mapping(lines, "information regimes", dataset.get("information_regimes"))
    _append_mapping(
        lines,
        "source information regimes",
        dataset.get("source_information_regimes"),
    )
    _append_mapping(
        lines,
        "teacher information regimes",
        dataset.get("teacher_information_regimes"),
    )
    source_coverage = _mapping(dataset.get("source_coverage"))
    lines.extend(
        [
            "source coverage:",
            f"  unique sources: {source_coverage.get('unique_source_count', 0)}",
            f"  repeated rows: {source_coverage.get('repeated_row_count', 0)}",
            (
                "  missing source identities: "
                f"{source_coverage.get('missing_source_identity_count', 0)}"
            ),
        ]
    )
    for checkpoint in report.checkpoint_reports:
        provenance = checkpoint.checkpoint_provenance
        metrics = checkpoint.teacher_target_metrics
        behavior = checkpoint.behavior_action_metrics
        calibration = checkpoint.calibration
        lines.extend(
            [
                "",
                f"checkpoint: {provenance.checkpoint_artifact_id}",
                f"scorer: {checkpoint.scorer_name}",
                f"calibration ok: {_yes_no(checkpoint.calibration_ok)}",
                f"checkpoint schema: {provenance.checkpoint_schema_id} v{provenance.checkpoint_format_version}",
                f"checkpoint trainer input: {provenance.trainer_input_artifact_id}",
                f"checkpoint target kind: {provenance.policy_target_kind}",
                f"checkpoint target source: {provenance.policy_target_source}",
                f"oracle-like supervision: {_yes_no(provenance.oracle_like_supervision)}",
                f"evaluated records: {checkpoint.evaluated_record_count}",
                f"skipped records: {sum(checkpoint.skipped_row_counts.values())}",
                (
                    "teacher top-1 agreement: "
                    f"{metrics.get('top1_agreement_count', 0)}/"
                    f"{metrics.get('evaluated_records', 0)} "
                    f"({_optional_rate(metrics.get('top1_agreement_rate'))})"
                ),
                (
                    f"teacher top-{checkpoint.top_k} agreement: "
                    f"{metrics.get('top_k_agreement_count', 0)}/"
                    f"{metrics.get('evaluated_records', 0)} "
                    f"({_optional_rate(metrics.get('top_k_agreement_rate'))})"
                ),
                (
                    "mean cross entropy: "
                    f"{_optional_float(metrics.get('mean_cross_entropy'))}"
                ),
                f"mean KL divergence: {_optional_float(metrics.get('mean_kl_divergence'))}",
                f"mean target rank: {_optional_float(metrics.get('mean_target_rank'))}",
                (
                    "behavior top-1 agreement: "
                    f"{behavior.get('top1_agreement_count', 0)}/"
                    f"{behavior.get('available_records', 0)} "
                    f"({_optional_rate(behavior.get('top1_agreement_rate'))})"
                ),
                (
                    "teacher-behavior agreement: "
                    f"{behavior.get('teacher_target_agreement_count', 0)}/"
                    f"{behavior.get('available_records', 0)} "
                    f"({_optional_rate(behavior.get('teacher_target_agreement_rate'))})"
                ),
                f"action-row ECE: {_optional_float(calibration.get('expected_calibration_error'))}",
            ]
        )
        _append_mapping(lines, "skipped rows", checkpoint.skipped_row_counts)
        if detail_limit > 0:
            lines.append(f"decision details (limit {detail_limit}):")
            for decision in checkpoint.decision_metrics[:detail_limit]:
                lines.append(
                    "  "
                    f"example={decision['example_index']} "
                    f"teacher={decision['teacher_target_action_index']} "
                    f"behavior={decision.get('behavior_action_index', 'unavailable')} "
                    f"model_top={decision['model_top_action_index']} "
                    f"target_prob={decision['model_target_probability']:.6f} "
                    f"rank={decision['target_rank']}"
                )
            remaining = len(checkpoint.decision_metrics) - detail_limit
            if remaining > 0:
                lines.append(f"  ... {remaining} more")
        lines.append("warnings:")
        if checkpoint.warnings:
            lines.extend(f"  - {warning}" for warning in checkpoint.warnings)
        else:
            lines.append("  (none)")
        lines.append("problems:")
        if checkpoint.problems:
            lines.extend(f"  - {problem}" for problem in checkpoint.problems)
        else:
            lines.append("  (none)")
    return "\n".join(lines)


def _build_checkpoint_report(
    dataset: TrainerInputDataset,
    batch: Any,
    scorer: SearchGuidanceScorer,
    *,
    trainer_input_artifact_identity: Mapping[str, Any],
    policy_target_kind: str,
    policy_target_source: str,
    top_k: int,
) -> CheckpointCalibrationReport:
    provenance = _initial_checkpoint_provenance(scorer)
    if provenance is not None:
        _validate_checkpoint_compatibility(
            provenance,
            trainer_input_artifact_identity=trainer_input_artifact_identity,
            policy_target_kind=policy_target_kind,
            policy_target_source=policy_target_source,
        )

    skipped = Counter()
    warnings: list[str] = []
    problems: list[str] = []
    decision_metrics: list[dict[str, Any]] = []
    cross_entropies: list[float] = []
    kl_divergences: list[float] = []
    brier_scores: list[float] = []
    target_ranks: list[int] = []
    top1_agreement_count = 0
    topk_agreement_count = 0
    behavior_available_count = 0
    behavior_top1_count = 0
    teacher_behavior_count = 0
    calibration_rows: list[tuple[float, float]] = []

    for record_index, record in enumerate(dataset.records):
        try:
            target = _target_distribution(record)
        except ValueError as exc:
            skipped["invalid_policy_target"] += 1
            warnings.append(f"record {record.example_index}: {exc}")
            continue

        context = decision_context_from_model_input_batch(batch, record_index)
        try:
            result = scorer.score_decision_context(context)
        except ValueError as exc:
            checkpoint_label = (
                provenance.checkpoint_artifact_id
                if provenance is not None
                else getattr(scorer, "name", "checkpoint")
            )
            raise ValueError(
                f"checkpoint {checkpoint_label} failed to score record "
                f"{record.example_index}: {exc}"
            ) from exc
        if provenance is None:
            provenance = result.checkpoint_provenance
            _validate_checkpoint_compatibility(
                provenance,
                trainer_input_artifact_identity=trainer_input_artifact_identity,
                policy_target_kind=policy_target_kind,
                policy_target_source=policy_target_source,
            )
        elif result.checkpoint_provenance.checkpoint_artifact_id != (
            provenance.checkpoint_artifact_id
        ):
            raise ValueError("scorer returned changing checkpoint provenance")

        result_problems = _result_problems(result, record)
        if result_problems:
            skipped["invalid_model_scores"] += 1
            warnings.extend(
                f"record {record.example_index}: {problem}"
                for problem in result_problems
            )
            continue

        decision = _decision_metric(
            record,
            result,
            target,
            policy_target_kind=policy_target_kind,
            top_k=top_k,
        )
        decision_metrics.append(decision)
        cross_entropies.append(float(decision["cross_entropy"]))
        kl_divergences.append(float(decision["kl_divergence"]))
        brier_scores.append(float(decision["brier_score"]))
        target_ranks.append(int(decision["target_rank"]))
        calibration_rows.extend(
            (row["model_probability"], row["target_probability"])
            for row in decision["action_score_rows"]
            if row["eligible"]
        )
        if decision["top1_teacher_agreement"]:
            top1_agreement_count += 1
        if decision["top_k_teacher_agreement"]:
            topk_agreement_count += 1
        if decision["behavior_action_status"] == BEHAVIOR_ACTION_AVAILABLE:
            behavior_available_count += 1
            if decision["top1_behavior_agreement"]:
                behavior_top1_count += 1
            if decision["teacher_behavior_agreement"]:
                teacher_behavior_count += 1

    if provenance is None:
        raise ValueError("checkpoint did not produce inference provenance")
    evaluated_count = len(decision_metrics)
    if evaluated_count == 0:
        problems.append("checkpoint produced no evaluated calibration rows")

    return CheckpointCalibrationReport(
        scorer_name=str(getattr(scorer, "name", "unknown")),
        checkpoint_provenance=provenance,
        policy_target_kind=policy_target_kind,
        policy_target_source=policy_target_source,
        top_k=top_k,
        record_count=len(dataset.records),
        evaluated_record_count=evaluated_count,
        skipped_row_counts=_counter_dict(skipped),
        teacher_target_metrics={
            "evaluated_records": evaluated_count,
            "top1_agreement_count": top1_agreement_count,
            "top1_agreement_rate": _rate(top1_agreement_count, evaluated_count),
            "top_k": top_k,
            "top_k_agreement_count": topk_agreement_count,
            "top_k_agreement_rate": _rate(topk_agreement_count, evaluated_count),
            "mean_cross_entropy": _mean(cross_entropies),
            "mean_kl_divergence": _mean(kl_divergences),
            "mean_brier_score": _mean(brier_scores),
            "mean_target_rank": _mean(target_ranks),
            "median_target_rank": _median(target_ranks),
        },
        behavior_action_metrics={
            "available_records": behavior_available_count,
            "top1_agreement_count": behavior_top1_count,
            "top1_agreement_rate": _rate(
                behavior_top1_count,
                behavior_available_count,
            ),
            "teacher_target_agreement_count": teacher_behavior_count,
            "teacher_target_agreement_rate": _rate(
                teacher_behavior_count,
                behavior_available_count,
            ),
        },
        calibration=_calibration_summary(calibration_rows),
        source_coverage=_source_coverage(dataset.records),
        decision_metrics=decision_metrics,
        warnings=tuple(dict.fromkeys(warnings)),
        problems=tuple(problems),
    )


def _decision_metric(
    record: TrainerInputRecord,
    result: SearchGuidanceInferenceResult,
    target: _TargetDistribution,
    *,
    policy_target_kind: str,
    top_k: int,
) -> dict[str, Any]:
    probabilities = [score.policy_probability for score in result.action_scores]
    eligible = [
        index
        for index in record.eligible_action_indices
        if 0 <= index < len(probabilities)
    ]
    ranked = sorted(eligible, key=lambda index: (-probabilities[index], index))
    model_top = ranked[0]
    target_top = target.target_top_index
    target_rank = ranked.index(target_top) + 1
    top_k_indices = set(ranked[: min(top_k, len(ranked))])
    cross_entropy = -sum(
        target.target_probabilities[index]
        * math.log(max(probabilities[index], EPSILON))
        for index in eligible
    )
    kl_divergence = sum(
        (
            target.target_probabilities[index]
            * math.log(
                max(target.target_probabilities[index], EPSILON)
                / max(probabilities[index], EPSILON)
            )
        )
        for index in eligible
        if target.target_probabilities[index] > 0.0
    )
    brier_score = sum(
        (probabilities[index] - target.target_probabilities[index]) ** 2
        for index in eligible
    ) / len(eligible)
    behavior_index = _behavior_action_index(record)
    action_score_rows = [
        {
            "legal_action_index": score.legal_action_index,
            "action_kind": score.action_kind,
            "eligible": score.eligible,
            "model_logit": score.policy_logit,
            "model_probability": score.policy_probability,
            "target_probability": target.target_probabilities[score.legal_action_index],
            "action_identity": dict(score.action_identity),
        }
        for score in result.action_scores
    ]
    return {
        "example_index": record.example_index,
        "record_source_identity": _stable_source_identity_label(record),
        "sampling_component": _metadata_string(record, "sampling_component"),
        "policy_target_kind": policy_target_kind,
        "policy_target_source": record.policy_target_source,
        "teacher_target_action_index": target_top,
        "teacher_target_action_identity": dict(record.policy_target_action_identity),
        "teacher_target_probability": target.target_top_probability,
        "behavior_action_status": record.behavior_action_status,
        "behavior_action_index": behavior_index,
        "behavior_action_identity": _behavior_action_identity(record),
        "model_top_action_index": model_top,
        "model_top_action_identity": dict(
            result.action_scores[model_top].action_identity
        ),
        "model_top_probability": probabilities[model_top],
        "model_target_probability": probabilities[target_top],
        "target_rank": target_rank,
        "top1_teacher_agreement": model_top == target_top,
        "top_k_teacher_agreement": target_top in top_k_indices,
        "top1_behavior_agreement": (
            None if behavior_index is None else model_top == behavior_index
        ),
        "teacher_behavior_agreement": (
            None if behavior_index is None else target_top == behavior_index
        ),
        "cross_entropy": cross_entropy,
        "kl_divergence": kl_divergence,
        "brier_score": brier_score,
        "action_score_rows": action_score_rows,
    }


def _target_distribution(record: TrainerInputRecord) -> _TargetDistribution:
    legal_count = len(record.legal_action_features)
    if len(record.policy_target) != legal_count:
        raise ValueError(
            f"policy target length {len(record.policy_target)} does not match "
            f"legal action count {legal_count}"
        )
    eligible = [
        index for index in record.eligible_action_indices if 0 <= index < legal_count
    ]
    if not eligible:
        raise ValueError("record has no eligible actions")
    if any(not _finite_non_negative(record.policy_target[index]) for index in eligible):
        raise ValueError("policy target has non-finite or negative eligible weight")
    eligible_mass = sum(float(record.policy_target[index]) for index in eligible)
    if eligible_mass <= 0.0:
        raise ValueError("policy target has no eligible weight")
    target = [0.0 for _ in record.policy_target]
    for index in eligible:
        target[index] = float(record.policy_target[index]) / eligible_mass
    target_top = max(eligible, key=lambda index: (target[index], -index))
    if record.policy_target_kind == POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION:
        positive = [index for index in eligible if target[index] > 0.0]
        if len(positive) != 1 or not math.isclose(target[positive[0]], 1.0):
            raise ValueError(
                "teacher action target is not one-hot over eligible actions"
            )
        if record.policy_target_action_index != positive[0]:
            raise ValueError("teacher action target index does not match target vector")
    elif record.policy_target_kind != POLICY_TARGET_KIND_ORACLE_SOFT_VISIT:
        raise ValueError(
            f"unsupported teacher calibration target {record.policy_target_kind!r}"
        )
    return _TargetDistribution(
        target_probabilities=target,
        target_top_index=target_top,
        target_top_probability=target[target_top],
    )


def _result_problems(
    result: SearchGuidanceInferenceResult,
    record: TrainerInputRecord,
) -> list[str]:
    problems = list(result.problems)
    legal_count = len(record.legal_action_features)
    if result.legal_action_count != legal_count:
        problems.append(
            f"model score legal action count {result.legal_action_count} does not "
            f"match trainer record count {legal_count}"
        )
    if len(result.action_scores) != legal_count:
        problems.append(
            f"model score row count {len(result.action_scores)} does not match "
            f"trainer record count {legal_count}"
        )
        return problems
    observed_indices = [score.legal_action_index for score in result.action_scores]
    if observed_indices != list(range(legal_count)):
        problems.append("model score action indices are not contiguous")
    eligible = [
        index for index in record.eligible_action_indices if 0 <= index < legal_count
    ]
    probability_sum = 0.0
    for score in result.action_scores:
        if not math.isfinite(score.policy_logit):
            problems.append(f"action {score.legal_action_index} logit is not finite")
            break
        if (
            not math.isfinite(score.policy_probability)
            or score.policy_probability < 0.0
        ):
            problems.append(f"action {score.legal_action_index} probability is invalid")
            break
        if score.legal_action_index in eligible:
            probability_sum += score.policy_probability
        elif score.policy_probability != 0.0:
            problems.append(
                f"action {score.legal_action_index} is ineligible but has probability"
            )
            break
    if not math.isclose(probability_sum, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        problems.append("eligible action probabilities do not sum to one")
    return problems


def _single_target_kind(records: Sequence[TrainerInputRecord]) -> str:
    counts = Counter(record.policy_target_kind for record in records)
    if len(counts) > 1:
        kinds = ", ".join(sorted(counts))
        raise ValueError(f"trainer input has mixed policy target kinds: {kinds}")
    return next(iter(counts))


def _validate_checkpoint_compatibility(
    provenance: SearchGuidanceCheckpointProvenance,
    *,
    trainer_input_artifact_identity: Mapping[str, Any],
    policy_target_kind: str,
    policy_target_source: str,
) -> None:
    trainer_sha = _non_empty_string(trainer_input_artifact_identity.get("sha256"))
    if trainer_sha is not None and provenance.trainer_input_sha256 != trainer_sha:
        raise ValueError(
            "checkpoint trainer_input_sha256 does not match trainer input artifact"
        )
    if provenance.policy_target_kind != policy_target_kind:
        raise ValueError(
            "checkpoint policy target kind does not match trainer input target kind"
        )
    if (
        policy_target_source != "mixed"
        and provenance.policy_target_source != policy_target_source
    ):
        raise ValueError(
            "checkpoint policy target source does not match trainer input target source"
        )


def _initial_checkpoint_provenance(
    scorer: SearchGuidanceScorer,
) -> SearchGuidanceCheckpointProvenance | None:
    value = getattr(scorer, "checkpoint_provenance", None)
    if isinstance(value, SearchGuidanceCheckpointProvenance):
        return value
    return None


def _dataset_summary(
    dataset: TrainerInputDataset,
    *,
    policy_target_kind: str,
    policy_target_source_counts: Mapping[str, int],
) -> dict[str, Any]:
    records = dataset.records
    return {
        "format_version": dataset.format_version,
        "record_count": len(records),
        "segment_count": dataset.segment_count,
        "source_rollout_count": dataset.source_rollout_count,
        "snapshot_feature_size": dataset.snapshot_feature_size,
        "action_feature_size": dataset.action_feature_size,
        "tactical_feature_schema_id": dataset.tactical_feature_schema_id,
        "tactical_feature_schema_version": dataset.tactical_feature_schema_version,
        "policy_target_schema_id": dataset.policy_target_schema_id,
        "policy_target_schema_version": dataset.policy_target_schema_version,
        "policy_target_kind": policy_target_kind,
        "policy_target_source": _single_count_key(policy_target_source_counts),
        "policy_target_kind_counts": _counter_dict(
            Counter(record.policy_target_kind for record in records)
        ),
        "policy_target_source_counts": _counter_dict(policy_target_source_counts),
        "behavior_action_status_counts": _counter_dict(
            Counter(record.behavior_action_status for record in records)
        ),
        "public_context_status_counts": _counter_dict(
            Counter(record.public_context_status for record in records)
        ),
        "structured_outcome_status_counts": _counter_dict(
            Counter(record.structured_battle_outcome_status for record in records)
        ),
        "sampling_component_counts": _counter_dict(
            Counter(
                _metadata_string(record, "sampling_component") for record in records
            )
        ),
        "information_regimes": _counter_dict(
            Counter(_controller_information_regime(record) for record in records)
        ),
        "source_information_regimes": _counter_dict(
            Counter(_source_information_regime(record) for record in records)
        ),
        "teacher_information_regimes": _counter_dict(
            Counter(_teacher_information_regime(record) for record in records)
        ),
        "source_coverage": _source_coverage(records),
        "generation_metadata": _json_safe_value(dataset.generation_metadata),
        "migration_report": dataset.migration_report.to_dict(),
    }


def _source_coverage(records: Sequence[TrainerInputRecord]) -> dict[str, Any]:
    identities: set[str] = set()
    identity_kind_counts: Counter[str] = Counter()
    missing = 0
    for record in records:
        identity = _stable_source_identity(record)
        if identity is None:
            missing += 1
            continue
        identities.add(identity[1])
        identity_kind_counts[identity[0]] += 1
    return {
        "record_count": len(records),
        "unique_source_count": len(identities),
        "repeated_row_count": max(len(records) - len(identities) - missing, 0),
        "missing_source_identity_count": missing,
        "identity_kind_counts": _counter_dict(identity_kind_counts),
    }


def _calibration_summary(rows: Sequence[tuple[float, float]]) -> dict[str, Any]:
    bins = [
        {
            "bin_index": index,
            "lower_inclusive": index / CALIBRATION_BIN_COUNT,
            "upper_exclusive": (index + 1) / CALIBRATION_BIN_COUNT,
            "action_count": 0,
            "mean_model_probability": None,
            "mean_target_probability": None,
            "absolute_error": None,
        }
        for index in range(CALIBRATION_BIN_COUNT)
    ]
    probability_sums = [0.0 for _ in bins]
    target_sums = [0.0 for _ in bins]
    for probability, target in rows:
        index = min(int(probability * CALIBRATION_BIN_COUNT), CALIBRATION_BIN_COUNT - 1)
        bins[index]["action_count"] += 1
        probability_sums[index] += probability
        target_sums[index] += target
    total = len(rows)
    weighted_error = 0.0
    maximum_error = 0.0
    for index, bucket in enumerate(bins):
        count = int(bucket["action_count"])
        if count <= 0:
            continue
        mean_probability = probability_sums[index] / count
        mean_target = target_sums[index] / count
        absolute_error = abs(mean_probability - mean_target)
        bucket["mean_model_probability"] = mean_probability
        bucket["mean_target_probability"] = mean_target
        bucket["absolute_error"] = absolute_error
        weighted_error += (count / total) * absolute_error
        maximum_error = max(maximum_error, absolute_error)
    return {
        "bin_count": CALIBRATION_BIN_COUNT,
        "action_row_count": total,
        "expected_calibration_error": None if total == 0 else weighted_error,
        "maximum_bin_error": None if total == 0 else maximum_error,
        "bins": bins,
    }


def _behavior_action_index(record: TrainerInputRecord) -> int | None:
    if record.behavior_action_status != BEHAVIOR_ACTION_AVAILABLE:
        return None
    value = record.behavior_action.get("legal_action_index")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _behavior_action_identity(record: TrainerInputRecord) -> dict[str, Any]:
    if record.behavior_action_status != BEHAVIOR_ACTION_AVAILABLE:
        return {}
    return _mapping(record.behavior_action.get("action_identity"))


def _stable_source_identity(record: TrainerInputRecord) -> tuple[str, str] | None:
    metadata = _mapping(record.source_metadata)
    checkpoint_id = _non_empty_string(metadata.get("source_checkpoint_id"))
    if checkpoint_id is not None:
        return ("source_checkpoint_id", checkpoint_id)
    run_id = _non_empty_string(metadata.get("source_run_id"))
    battle_index = _optional_int(metadata.get("source_battle_index"))
    if run_id is not None and battle_index is not None:
        return ("source_run_battle", f"{run_id}:{battle_index}")
    return None


def _stable_source_identity_label(record: TrainerInputRecord) -> str:
    identity = _stable_source_identity(record)
    if identity is None:
        return "missing"
    return f"{identity[0]}:{identity[1]}"


def _controller_information_regime(record: TrainerInputRecord) -> str:
    provenance = _mapping(record.controller_provenance)
    config = _mapping(provenance.get("config"))
    return _non_empty_string(config.get("information_regime")) or "missing"


def _source_information_regime(record: TrainerInputRecord) -> str:
    return _metadata_string(record, "checkpoint_information_regime")


def _teacher_information_regime(record: TrainerInputRecord) -> str:
    return _metadata_string(record, "teacher_information_regime")


def _metadata_string(record: TrainerInputRecord, key: str) -> str:
    metadata = _mapping(record.source_metadata)
    return _non_empty_string(metadata.get(key)) or "missing"


def _finite_non_negative(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) >= 0.0


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): int(values[key]) for key in sorted(values, key=str)}


def _single_count_key(counts: Mapping[str, int]) -> str:
    if len(counts) == 1:
        return next(iter(counts))
    if not counts:
        return "missing"
    return "mixed"


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _mean(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def _median(values: Sequence[int]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[midpoint])
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2.0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _append_mapping(lines: list[str], title: str, values: Any) -> None:
    lines.append(f"{title}:")
    mapping = _mapping(values)
    if not mapping:
        lines.append("  (none)")
        return
    for key in sorted(mapping):
        lines.append(f"  {key}: {mapping[key]}")


def _optional_float(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.6f}"


def _optional_rate(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.3f}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
