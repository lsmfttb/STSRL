"""Raw public-policy controller backed by a search-guidance checkpoint."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import time
from typing import Any

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    json_safe_mapping,
)
from sts_combat_rl.sim.online_controller import PUBLIC_POLICY_INFORMATION_REGIME
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION,
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)


SEARCH_GUIDANCE_POLICY_CONTROLLER_VERSION = "search-guidance-policy-controller-v1"
SEARCH_GUIDANCE_POLICY_CONTROLLER_NAME = "search_guidance_policy_v1"
SEARCH_GUIDANCE_POLICY_SELECTION_RULE = "highest_eligible_policy_probability"


@dataclass(frozen=True)
class SearchGuidancePolicyDecisionReport:
    """Per-decision report for raw public checkpoint policy selection."""

    guidance_result: SearchGuidanceInferenceResult
    selected_score: SearchGuidanceActionScore
    total_wall_clock_time_s: float
    controller_version: str = SEARCH_GUIDANCE_POLICY_CONTROLLER_VERSION
    selection_rule: str = SEARCH_GUIDANCE_POLICY_SELECTION_RULE

    def to_dict(self) -> dict[str, Any]:
        return {
            "controller_version": self.controller_version,
            "information_regime": PUBLIC_POLICY_INFORMATION_REGIME,
            "selection_rule": self.selection_rule,
            "model_calls": 1,
            "total_wall_clock_time_s": self.total_wall_clock_time_s,
            "guidance_result": self.guidance_result.to_dict(),
            "selected_score": self.selected_score.to_dict(),
        }


@dataclass(frozen=True)
class SearchGuidancePolicyController:
    """OnlineController that directly acts from public checkpoint policy scores."""

    scorer: SearchGuidanceScorer
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)

    def __post_init__(self) -> None:
        checkpoint_provenance = search_guidance_scorer_checkpoint_provenance(
            self.scorer,
            label="search-guidance policy scorer",
        )
        object.__setattr__(self, "checkpoint_provenance", checkpoint_provenance)
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="search_guidance_public_policy",
                name=SEARCH_GUIDANCE_POLICY_CONTROLLER_NAME,
                config={
                    "controller_version": SEARCH_GUIDANCE_POLICY_CONTROLLER_VERSION,
                    "information_regime": PUBLIC_POLICY_INFORMATION_REGIME,
                    "selection_rule": SEARCH_GUIDANCE_POLICY_SELECTION_RULE,
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "inference_schema_id": SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
                        "inference_schema_version": (
                            SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
                        ),
                        "checkpoint_provenance": checkpoint_provenance.to_dict(),
                    },
                    "action_identity_validation": "occurrence_safe_action_identity_v1",
                    "assistance_provenance_usage": (
                        "not consumed; only sanitized public decision context is scored"
                    ),
                    "reproducibility": {
                        "deterministic_given_checkpoint_and_public_context": True,
                        "python_rng_seed": None,
                    },
                },
            ),
        )

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del adapter, snapshot, actions, step_index
        started = time.perf_counter()
        try:
            guidance = self.scorer.score_decision_context(context)
        except ValueError as exc:
            raise ValueError(f"search guidance policy inference failed: {exc}") from exc
        validate_search_guidance_result(
            guidance,
            context=context,
            expected_checkpoint=self.checkpoint_provenance,
        )
        selected = _select_highest_eligible_policy_score(guidance.action_scores)
        elapsed = time.perf_counter() - started
        decision_report = SearchGuidancePolicyDecisionReport(
            guidance_result=guidance,
            selected_score=selected,
            total_wall_clock_time_s=elapsed,
        )
        return ControllerDecision(
            selected_index=selected.legal_action_index,
            provenance=self.provenance,
            reason=f"search_guidance_policy:{SEARCH_GUIDANCE_POLICY_SELECTION_RULE}",
            score=selected.policy_probability,
            metadata=search_guidance_policy_controller_metadata(decision_report),
        )


def search_guidance_policy_controller_metadata(
    decision_report: SearchGuidancePolicyDecisionReport,
) -> dict[str, Any]:
    """Return JSON-safe per-decision metadata for fixed evaluation reports."""

    guidance = decision_report.guidance_result
    selected = decision_report.selected_score
    return json_safe_mapping(
        {
            "search_guidance_policy_decision_count": 1,
            "search_guidance_policy_controller_version": (
                decision_report.controller_version
            ),
            "search_guidance_policy_selection_rule": decision_report.selection_rule,
            "search_guidance_policy_model_calls": 1,
            "search_guidance_policy_scorer_name": guidance.scorer_name,
            "search_guidance_policy_inference_schema_id": guidance.schema_id,
            "search_guidance_policy_checkpoint_artifact_id": (
                guidance.checkpoint_provenance.checkpoint_artifact_id
            ),
            "search_guidance_policy_selected_index": selected.legal_action_index,
            "search_guidance_policy_selected_action_identity": (
                selected.action_identity
            ),
            "search_guidance_policy_selected_policy_probability": (
                selected.policy_probability
            ),
            "search_guidance_policy_selected_policy_logit": selected.policy_logit,
            "search_guidance_policy_decision_gap": _policy_probability_gap(
                guidance.action_scores
            ),
            "search_guidance_policy_total_wall_clock_time_s": (
                decision_report.total_wall_clock_time_s
            ),
            "search_guidance_policy_checkpoint_provenance": (
                guidance.checkpoint_provenance.to_dict()
            ),
            "model_guidance_inference": [guidance.to_dict()],
            "search_guidance_policy_decision_reports": [decision_report.to_dict()],
        }
    )


def _select_highest_eligible_policy_score(
    scores: Sequence[SearchGuidanceActionScore],
) -> SearchGuidanceActionScore:
    candidates = [score for score in scores if score.eligible]
    if not candidates:
        raise ValueError("search guidance policy has no eligible scored actions")
    return max(
        candidates,
        key=lambda score: (
            score.policy_probability,
            score.policy_logit,
            -score.legal_action_index,
        ),
    )


def _policy_probability_gap(
    scores: Sequence[SearchGuidanceActionScore],
) -> float | None:
    values = sorted(
        (score.policy_probability for score in scores if score.eligible),
        reverse=True,
    )
    if len(values) < 2:
        return None
    return values[0] - values[1]
