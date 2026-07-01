"""Framework-neutral search-guidance checkpoint inference contract.

This module defines the public result shape for using a trained policy/value
checkpoint as a scorer. It does not implement a controller, choose an action,
advance a simulator, or import PyTorch.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Any, Protocol

from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    tactical_action_problems,
    tactical_state_problems,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.public_context_artifacts import sanitize_public_context_artifact


SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID = "search-guidance-inference-v1"
SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION = 1


class SearchGuidanceScorer(Protocol):
    """Inference-only scorer over one public decision context."""

    name: str

    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> "SearchGuidanceInferenceResult":
        """Return checkpoint guidance for all current legal actions."""


def search_guidance_scorer_checkpoint_provenance(
    scorer: SearchGuidanceScorer,
    *,
    label: str = "search guidance scorer",
) -> "SearchGuidanceCheckpointProvenance":
    """Return the current checkpoint provenance exposed by a scorer."""

    value = getattr(scorer, "checkpoint_provenance", None)
    if not isinstance(value, SearchGuidanceCheckpointProvenance):
        raise ValueError(
            f"{label} must expose current SearchGuidanceCheckpointProvenance "
            "as checkpoint_provenance"
        )
    return value


@dataclass(frozen=True)
class SearchGuidanceCheckpointProvenance:
    """Auditable checkpoint identity and training target provenance."""

    checkpoint_schema_id: str
    checkpoint_format_version: int
    checkpoint_artifact_id: str
    checkpoint_path: str | None
    model_class: str
    model_config: dict[str, Any]
    trainer_input_artifact_id: str
    trainer_input_sha256: str
    policy_target_kind: str
    policy_target_source: str
    policy_target_kind_counts: dict[str, int] = field(default_factory=dict)
    policy_target_source_counts: dict[str, int] = field(default_factory=dict)
    information_regime_counts: dict[str, int] = field(default_factory=dict)
    source_information_regime_counts: dict[str, int] = field(default_factory=dict)
    oracle_like_supervision: bool = False
    training_data_provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_schema_id": self.checkpoint_schema_id,
            "checkpoint_format_version": self.checkpoint_format_version,
            "checkpoint_artifact_id": self.checkpoint_artifact_id,
            "checkpoint_path": self.checkpoint_path,
            "model_class": self.model_class,
            "model_config": dict(self.model_config),
            "trainer_input_artifact_id": self.trainer_input_artifact_id,
            "trainer_input_sha256": self.trainer_input_sha256,
            "policy_target_kind": self.policy_target_kind,
            "policy_target_source": self.policy_target_source,
            "policy_target_kind_counts": dict(self.policy_target_kind_counts),
            "policy_target_source_counts": dict(self.policy_target_source_counts),
            "information_regime_counts": dict(self.information_regime_counts),
            "source_information_regime_counts": dict(
                self.source_information_regime_counts
            ),
            "oracle_like_supervision": self.oracle_like_supervision,
            "training_data_provenance": dict(self.training_data_provenance),
        }


@dataclass(frozen=True)
class SearchGuidanceActionScore:
    """One legal action's checkpoint guidance row."""

    legal_action_index: int
    action_kind: str
    eligible: bool
    policy_logit: float
    policy_probability: float
    action_identity: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_action_index": self.legal_action_index,
            "action_kind": self.action_kind,
            "eligible": self.eligible,
            "policy_logit": self.policy_logit,
            "policy_probability": self.policy_probability,
            "action_identity": dict(self.action_identity),
        }


@dataclass(frozen=True)
class SearchGuidanceValuePrediction:
    """Optional value and terminal-outcome predictions from the checkpoint."""

    battle_survival_probability: float | None = None
    terminal_absolute_current_hp: float | None = None
    structured_resource_values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_survival_probability": self.battle_survival_probability,
            "terminal_absolute_current_hp": self.terminal_absolute_current_hp,
            "structured_resource_values": dict(self.structured_resource_values),
        }


@dataclass(frozen=True)
class SearchGuidanceInferenceResult:
    """Inference result for one public decision context."""

    scorer_name: str
    checkpoint_provenance: SearchGuidanceCheckpointProvenance
    legal_action_count: int
    eligible_action_count: int
    action_scores: list[SearchGuidanceActionScore]
    value_prediction: SearchGuidanceValuePrediction | None = None
    duration_ms: float = 0.0
    schema_id: str = SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID
    schema_version: int = SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
    problems: tuple[str, ...] = ()

    @property
    def inference_ok(self) -> bool:
        return (
            self.schema_id == SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID
            and self.schema_version == SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
            and not self.problems
            and self.legal_action_count == len(self.action_scores)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "scorer_name": self.scorer_name,
            "inference_ok": self.inference_ok,
            "legal_action_count": self.legal_action_count,
            "eligible_action_count": self.eligible_action_count,
            "duration_ms": self.duration_ms,
            "checkpoint_provenance": self.checkpoint_provenance.to_dict(),
            "action_scores": [score.to_dict() for score in self.action_scores],
            "value_prediction": (
                self.value_prediction.to_dict()
                if self.value_prediction is not None
                else None
            ),
            "problems": list(self.problems),
        }


def validate_search_guidance_context(context: DecisionContext) -> None:
    """Fail closed unless the context matches the current public contract."""

    problems: list[str] = []
    if context.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        problems.append(
            "decision context tactical feature schema "
            f"{context.tactical_feature_schema_id!r} is not current "
            f"{TACTICAL_FEATURE_SCHEMA_ID!r}"
        )

    legal_count = len(context.legal_action_features)
    if legal_count <= 0:
        problems.append("decision context has no legal actions")
    if len(context.legal_action_kinds) != legal_count:
        problems.append(
            "decision context legal action kind count "
            f"{len(context.legal_action_kinds)} does not match legal action "
            f"feature count {legal_count}"
        )
    if not context.eligible_action_indices:
        problems.append("decision context has no eligible actions")
    invalid_eligible = [
        index
        for index in context.eligible_action_indices
        if index < 0 or index >= legal_count
    ]
    if invalid_eligible:
        problems.append(
            f"eligible action index {invalid_eligible[0]} outside {legal_count} "
            "legal actions"
        )

    _append_finite_sequence_problems(
        problems,
        context.snapshot_features,
        "snapshot_features",
    )
    for index, features in enumerate(context.legal_action_features):
        _append_finite_sequence_problems(
            problems,
            features,
            f"legal_action_features[{index}]",
        )

    try:
        sanitize_public_context_artifact(
            context.public_run_context,
            label="decision context",
        )
    except ValueError as exc:
        problems.append(str(exc))

    if context.tactical_state:
        problems.extend(
            f"decision context tactical_state: {problem}"
            for problem in tactical_state_problems(context.tactical_state)
        )
    if context.tactical_legal_actions:
        if len(context.tactical_legal_actions) != legal_count:
            problems.append(
                "decision context tactical action count "
                f"{len(context.tactical_legal_actions)} does not match legal "
                f"action count {legal_count}"
            )
        else:
            problems.extend(
                f"decision context tactical_legal_actions: {problem}"
                for problem in tactical_action_problems(context.tactical_legal_actions)
            )

    if problems:
        raise ValueError("; ".join(dict.fromkeys(problems)))


def validate_search_guidance_result(
    result: SearchGuidanceInferenceResult,
    *,
    context: DecisionContext,
    expected_checkpoint: SearchGuidanceCheckpointProvenance,
) -> None:
    """Fail closed unless a scorer result matches the current decision context."""

    problems: list[str] = []
    if result.schema_id != SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID:
        problems.append(f"unsupported guidance schema_id {result.schema_id!r}")
    if result.schema_version != SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION:
        problems.append(
            f"unsupported guidance schema_version {result.schema_version!r}"
        )
    if not result.inference_ok:
        problems.extend(result.problems or ("guidance inference was not ok",))
    legal_count = len(context.legal_action_features)
    if result.legal_action_count != legal_count:
        problems.append(
            "guidance legal action count "
            f"{result.legal_action_count} does not match context {legal_count}"
        )
    if len(result.action_scores) != legal_count:
        problems.append(
            "guidance action score count "
            f"{len(result.action_scores)} does not match context {legal_count}"
        )
    if result.eligible_action_count != len(context.eligible_action_indices):
        problems.append(
            "guidance eligible action count "
            f"{result.eligible_action_count} does not match context "
            f"{len(context.eligible_action_indices)}"
        )
    if result.checkpoint_provenance.to_dict() != expected_checkpoint.to_dict():
        problems.append("guidance scorer returned changing checkpoint provenance")

    seen: set[int] = set()
    eligible = set(context.eligible_action_indices)
    for score in result.action_scores:
        index = score.legal_action_index
        if index in seen:
            problems.append(f"duplicate guidance action score for index {index}")
            continue
        seen.add(index)
        if index < 0 or index >= legal_count:
            problems.append(
                f"guidance action score index {index} outside {legal_count} actions"
            )
            _append_guidance_score_problems(score, problems)
            continue
        expected_kind = context.legal_action_kinds[index]
        if score.action_kind != expected_kind:
            problems.append(
                "guidance action kind for index "
                f"{index} does not match context: "
                f"{score.action_kind!r} != {expected_kind!r}"
            )
        expected_identity = search_guidance_context_action_identity(context, index)
        if expected_identity:
            if not score.action_identity:
                problems.append(
                    f"guidance action identity for index {index} is missing"
                )
            elif dict(score.action_identity) != expected_identity:
                problems.append(
                    f"guidance action identity for index {index} does not match context"
                )
        if score.eligible != (index in eligible):
            problems.append(
                f"guidance eligibility for index {index} does not match context"
            )
        _append_guidance_score_problems(score, problems)
    missing = sorted(set(range(legal_count)) - seen)
    if missing:
        problems.append(f"missing guidance action score for index {missing[0]}")
    if problems:
        raise ValueError("; ".join(dict.fromkeys(problems)))


def search_guidance_context_action_identity(
    context: DecisionContext,
    index: int,
) -> dict[str, Any]:
    """Return the public action identity for one current legal action if present."""

    if index < 0 or index >= len(context.tactical_legal_actions):
        return {}
    action = context.tactical_legal_actions[index]
    if not isinstance(action, Mapping):
        return {}
    identity = action.get("identity")
    if not isinstance(identity, Mapping):
        return {}
    return dict(identity)


def format_search_guidance_inference_result(
    result: SearchGuidanceInferenceResult,
    *,
    detail_limit: int = 8,
) -> str:
    """Format deterministic checkpoint inference output for stderr."""

    provenance = result.checkpoint_provenance
    values = result.value_prediction
    lines = [
        "Search-guidance checkpoint inference summary",
        "scope: checkpoint scoring only; no controller, simulator, or action selection",
        f"schema: {result.schema_id} v{result.schema_version}",
        f"inference ok: {_yes_no(result.inference_ok)}",
        f"scorer: {result.scorer_name}",
        f"checkpoint: {provenance.checkpoint_artifact_id}",
        f"checkpoint schema: {provenance.checkpoint_schema_id} v{provenance.checkpoint_format_version}",
        f"trainer input: {provenance.trainer_input_artifact_id}",
        f"policy target kind: {provenance.policy_target_kind}",
        f"policy target source: {provenance.policy_target_source}",
        f"oracle-like supervision: {_yes_no(provenance.oracle_like_supervision)}",
        f"legal actions: {result.legal_action_count}",
        f"eligible actions: {result.eligible_action_count}",
        f"duration ms: {result.duration_ms:.3f}",
    ]
    _append_mapping(lines, "information regimes", provenance.information_regime_counts)
    _append_mapping(
        lines,
        "source information regimes",
        provenance.source_information_regime_counts,
    )
    if values is not None:
        lines.extend(
            [
                "value predictions:",
                (
                    "  battle survival probability: "
                    f"{_optional_float(values.battle_survival_probability)}"
                ),
                (
                    "  terminal absolute current HP: "
                    f"{_optional_float(values.terminal_absolute_current_hp)}"
                ),
            ]
        )
        _append_mapping(
            lines,
            "  structured resource values",
            values.structured_resource_values,
        )

    lines.append(f"action scores (limit {detail_limit}):")
    for score in result.action_scores[: max(detail_limit, 0)]:
        lines.append(
            "  "
            f"index={score.legal_action_index} kind={score.action_kind} "
            f"eligible={_yes_no(score.eligible)} "
            f"logit={score.policy_logit:.6f} "
            f"probability={score.policy_probability:.6f}"
        )
    if len(result.action_scores) > max(detail_limit, 0):
        lines.append(f"  ... {len(result.action_scores) - max(detail_limit, 0)} more")

    lines.append("problems:")
    if result.problems:
        lines.extend(f"  {problem}" for problem in result.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _append_finite_sequence_problems(
    problems: list[str],
    values: Sequence[object],
    label: str,
) -> None:
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"{label}[{index}] must be numeric")
            return
        if not math.isfinite(float(value)):
            problems.append(f"{label}[{index}] must be finite")
            return


def _append_guidance_score_problems(
    score: SearchGuidanceActionScore,
    problems: list[str],
) -> None:
    if not math.isfinite(score.policy_logit):
        problems.append(
            f"guidance policy logit for index {score.legal_action_index} is not finite"
        )
    if (
        not math.isfinite(score.policy_probability)
        or score.policy_probability < 0.0
        or score.policy_probability > 1.0
    ):
        problems.append(
            "guidance policy probability for index "
            f"{score.legal_action_index} must be finite and in [0, 1]"
        )


def _append_mapping(lines: list[str], title: str, values: Mapping[str, Any]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        lines.append(f"  {key}: {values[key]}")


def _optional_float(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
