"""Model-guided Oracle-like battle search controller.

This module keeps the current hidden-state native search boundary intact.  The
native search still runs exactly once for the requested root playout budget; the
public checkpoint scorer is used only for a versioned root-selection score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import time
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig, POTION_ACTION_KINDS
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
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchReport,
    OracleSearchTarget,
    build_oracle_search_report,
    oracle_search_decision_telemetry,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION,
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
)
from sts_combat_rl.sim.search_telemetry import (
    SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
    SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
    SearchDecisionTelemetry,
)


MODEL_GUIDED_ORACLE_SEARCH_CONTROLLER_VERSION = (
    "model-guided-oracle-search-controller-v1"
)
MODEL_GUIDED_ORACLE_CONTROLLER_NAME = "model_guided_oracle_search_v1"
MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE = "native_mean_plus_policy_probability"
MODEL_GUIDED_ORACLE_DEFAULT_POLICY_PROBABILITY_WEIGHT = 0.05
MODEL_GUIDED_ORACLE_SEARCH_V2_CONTROLLER_VERSION = (
    "model-guided-oracle-search-controller-v2"
)
MODEL_GUIDED_ORACLE_V2_CONTROLLER_NAME = "model_guided_oracle_search_v2"
MODEL_GUIDED_ORACLE_V2_ROOT_SELECTION_RULE = (
    "native_mean_plus_visit_adjusted_policy_probability"
)


@dataclass(frozen=True)
class ModelGuidedOracleRootScore:
    """One root action's native search row plus public checkpoint guidance."""

    legal_action_index: int
    action_identity: dict[str, Any]
    eligible: bool
    native_visits: int
    native_mean_value: float | None
    model_policy_logit: float
    model_policy_probability: float
    combined_score: float | None
    model_guidance_multiplier: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_action_index": self.legal_action_index,
            "action_identity": dict(self.action_identity),
            "eligible": self.eligible,
            "native_visits": self.native_visits,
            "native_mean_value": self.native_mean_value,
            "model_policy_logit": self.model_policy_logit,
            "model_policy_probability": self.model_policy_probability,
            "combined_score": self.combined_score,
            "model_guidance_multiplier": self.model_guidance_multiplier,
        }


@dataclass(frozen=True)
class ModelGuidedOracleSearchTarget:
    """Selected action under the model-guided root-selection rule."""

    selection_rule: str
    legal_action_index: int
    action_identity: dict[str, Any]
    native_visits: int
    native_mean_value: float
    model_policy_logit: float
    model_policy_probability: float
    combined_score: float

    def to_oracle_target(self) -> OracleSearchTarget:
        return OracleSearchTarget(
            selection_rule=self.selection_rule,
            legal_action_index=self.legal_action_index,
            action_identity=dict(self.action_identity),
            visits=self.native_visits,
            mean_value=self.native_mean_value,
            score=self.combined_score,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_rule": self.selection_rule,
            "legal_action_index": self.legal_action_index,
            "action_identity": dict(self.action_identity),
            "native_visits": self.native_visits,
            "native_mean_value": self.native_mean_value,
            "model_policy_logit": self.model_policy_logit,
            "model_policy_probability": self.model_policy_probability,
            "combined_score": self.combined_score,
        }


@dataclass(frozen=True)
class ModelGuidedOracleSearchDecisionReport:
    """Per-decision report for model-guided Oracle-like root selection."""

    oracle_report: OracleSearchReport
    guidance_result: SearchGuidanceInferenceResult
    policy_probability_weight: float
    root_scores: tuple[ModelGuidedOracleRootScore, ...]
    target: ModelGuidedOracleSearchTarget
    total_wall_clock_time_s: float | None
    native_search_wall_clock_time_s: float | None
    controller_version: str = MODEL_GUIDED_ORACLE_SEARCH_CONTROLLER_VERSION
    root_selection_rule: str = MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE
    guidance_formula: str | None = None
    telemetry_controller_kind: str = "model_guided_oracle_battle_search"
    search_kind: str = "native_random_terminal_playout_with_public_root_guidance"

    def to_dict(self) -> dict[str, Any]:
        return {
            "controller_version": self.controller_version,
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "root_selection_rule": self.root_selection_rule,
            "guidance_formula": self.guidance_formula
            or _guidance_formula(self.policy_probability_weight),
            "policy_probability_weight": self.policy_probability_weight,
            "total_wall_clock_time_s": self.total_wall_clock_time_s,
            "native_search_wall_clock_time_s": self.native_search_wall_clock_time_s,
            "model_calls": 1,
            "oracle_search_report": self.oracle_report.to_dict(),
            "guidance_result": self.guidance_result.to_dict(),
            "root_scores": [score.to_dict() for score in self.root_scores],
            "target": self.target.to_dict(),
            "telemetry_controller_kind": self.telemetry_controller_kind,
            "search_kind": self.search_kind,
        }


@dataclass(frozen=True)
class ModelGuidedOracleSearchController:
    """OnlineController using native Oracle search with public root guidance.

    The current native API does not accept policy priors, leaf values, or model
    allocation hooks.  This controller therefore guides only root action
    selection after one native hidden-state search has completed.
    """

    simulations: int
    scorer: SearchGuidanceScorer
    policy_probability_weight: float = (
        MODEL_GUIDED_ORACLE_DEFAULT_POLICY_PROBABILITY_WEIGHT
    )
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)

    def __post_init__(self) -> None:
        if self.simulations <= 0:
            raise ValueError("model-guided oracle simulations must be positive")
        if (
            not isinstance(self.policy_probability_weight, (int, float))
            or isinstance(self.policy_probability_weight, bool)
            or not math.isfinite(float(self.policy_probability_weight))
            or self.policy_probability_weight < 0.0
        ):
            raise ValueError(
                "model-guided oracle policy probability weight must be finite "
                "and non-negative"
            )
        checkpoint_provenance = _scorer_checkpoint_provenance(self.scorer)
        object.__setattr__(self, "checkpoint_provenance", checkpoint_provenance)
        source_identity = (
            dict(self.native_source_identity)
            if self.native_source_identity is not None
            else lightspeed_source_identity_dict()
        )
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="model_guided_oracle_battle_search",
                name=(
                    f"{MODEL_GUIDED_ORACLE_CONTROLLER_NAME}_"
                    f"s{self.simulations}_"
                    f"pw{float(self.policy_probability_weight):g}"
                ),
                config={
                    "controller_version": (
                        MODEL_GUIDED_ORACLE_SEARCH_CONTROLLER_VERSION
                    ),
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": ORACLE_SEARCH_NATIVE_API,
                    "native_search_patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "root_selection_rule": (MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE),
                    "guidance_formula": _guidance_formula(
                        float(self.policy_probability_weight)
                    ),
                    "guidance_scope": (
                        "root selection only; current native battle_search API "
                        "does not accept model priors, allocation hints, or leaf "
                        "values"
                    ),
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "inference_schema_id": SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
                        "inference_schema_version": (
                            SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
                        ),
                        "policy_probability_weight": float(
                            self.policy_probability_weight
                        ),
                        "checkpoint_provenance": checkpoint_provenance.to_dict(),
                    },
                    "search_telemetry": {
                        "schema_id": SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
                        "schema_version": SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
                        "model_calls_per_decision": 1,
                        "unavailable_native_fields": {
                            "tree_depth": "native battle_search does not expose tree depth",
                            "value_uncertainty": (
                                "native battle_search does not expose uncertainty"
                            ),
                            "model_guided_allocation": (
                                "current native battle_search API does not accept "
                                "model allocation hints"
                            ),
                        },
                    },
                    "action_space": self.action_space.to_dict(),
                    "root_mapping": "occurrence_safe_action_identity_v1",
                    "reproducibility": {
                        "deterministic_given_restored_checkpoint": True,
                        "native_rng_seed_source": "BattleContext.seed+floorNum",
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
        del step_index
        if not hasattr(adapter, "battle_search"):
            raise ValueError(
                "model-guided oracle search controller requires battle_search adapter"
            )

        total_start = time.perf_counter()
        search_fn = getattr(adapter, "battle_search")
        search_start = time.perf_counter()
        raw_search = search_fn(
            snapshot,
            simulations=self.simulations,
            include_potions=_include_potions_for_battle_search(self.action_space),
        )
        search_elapsed = time.perf_counter() - search_start
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "model-guided oracle root mapping failed: " + "; ".join(report.problems)
            )

        try:
            guidance = self.scorer.score_decision_context(context)
        except ValueError as exc:
            raise ValueError(f"model guidance inference failed: {exc}") from exc
        _validate_guidance_result(
            guidance,
            context=context,
            expected_checkpoint=self.checkpoint_provenance,
        )

        root_scores = build_model_guided_oracle_root_scores(
            report,
            guidance,
            policy_probability_weight=float(self.policy_probability_weight),
        )
        target = select_model_guided_oracle_root_action(root_scores)
        total_elapsed = time.perf_counter() - total_start
        decision_report = ModelGuidedOracleSearchDecisionReport(
            oracle_report=report,
            guidance_result=guidance,
            policy_probability_weight=float(self.policy_probability_weight),
            root_scores=root_scores,
            target=target,
            total_wall_clock_time_s=total_elapsed,
            native_search_wall_clock_time_s=search_elapsed,
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"model_guided_oracle:{MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE}",
            score=target.combined_score,
            metadata=model_guided_oracle_search_controller_metadata(decision_report),
        )


@dataclass(frozen=True)
class ModelGuidedOracleSearchV2Controller:
    """Second root-only model-guided Oracle-like search experiment.

    The v2 experiment still runs the same native hidden-state ``battle_search``
    once. Since that API cannot consume model priors or leaf values, v2 applies
    model guidance only at final root selection. It differs from T028/v1 by
    scaling the public policy probability with a deterministic post-search
    visit factor, giving model guidance more influence on visited root actions
    with fewer native playouts.
    """

    simulations: int
    scorer: SearchGuidanceScorer
    policy_probability_weight: float = (
        MODEL_GUIDED_ORACLE_DEFAULT_POLICY_PROBABILITY_WEIGHT
    )
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)

    def __post_init__(self) -> None:
        if self.simulations <= 0:
            raise ValueError("model-guided oracle v2 simulations must be positive")
        _validate_policy_probability_weight(self.policy_probability_weight)
        checkpoint_provenance = _scorer_checkpoint_provenance(self.scorer)
        object.__setattr__(self, "checkpoint_provenance", checkpoint_provenance)
        source_identity = (
            dict(self.native_source_identity)
            if self.native_source_identity is not None
            else lightspeed_source_identity_dict()
        )
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="model_guided_oracle_battle_search_v2",
                name=(
                    f"{MODEL_GUIDED_ORACLE_V2_CONTROLLER_NAME}_"
                    f"s{self.simulations}_"
                    f"pw{float(self.policy_probability_weight):g}"
                ),
                config={
                    "controller_version": (
                        MODEL_GUIDED_ORACLE_SEARCH_V2_CONTROLLER_VERSION
                    ),
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": ORACLE_SEARCH_NATIVE_API,
                    "native_search_patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "root_selection_rule": (MODEL_GUIDED_ORACLE_V2_ROOT_SELECTION_RULE),
                    "guidance_formula": _v2_guidance_formula(
                        float(self.policy_probability_weight)
                    ),
                    "guidance_scope": (
                        "root selection only; visit adjustment is computed after "
                        "native search and current battle_search does not accept "
                        "model priors, allocation hints, or leaf values"
                    ),
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "inference_schema_id": SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
                        "inference_schema_version": (
                            SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
                        ),
                        "policy_probability_weight": float(
                            self.policy_probability_weight
                        ),
                        "checkpoint_provenance": checkpoint_provenance.to_dict(),
                    },
                    "v2_root_guidance": {
                        "visit_adjustment": (
                            "sqrt(total_root_visits / native_visits) for visited "
                            "eligible root actions"
                        ),
                        "uses_native_allocation_api": False,
                        "uses_native_leaf_value_api": False,
                    },
                    "search_telemetry": {
                        "schema_id": SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
                        "schema_version": SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
                        "model_calls_per_decision": 1,
                        "unavailable_native_fields": {
                            "tree_depth": "native battle_search does not expose tree depth",
                            "value_uncertainty": (
                                "native battle_search does not expose uncertainty"
                            ),
                            "model_guided_allocation": (
                                "current native battle_search API does not accept "
                                "model allocation hints"
                            ),
                            "model_guided_leaf_values": (
                                "current native battle_search API does not accept "
                                "model leaf values"
                            ),
                        },
                    },
                    "action_space": self.action_space.to_dict(),
                    "root_mapping": "occurrence_safe_action_identity_v1",
                    "reproducibility": {
                        "deterministic_given_restored_checkpoint": True,
                        "native_rng_seed_source": "BattleContext.seed+floorNum",
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
        del step_index
        if not hasattr(adapter, "battle_search"):
            raise ValueError(
                "model-guided oracle v2 search controller requires battle_search adapter"
            )

        total_start = time.perf_counter()
        search_fn = getattr(adapter, "battle_search")
        search_start = time.perf_counter()
        raw_search = search_fn(
            snapshot,
            simulations=self.simulations,
            include_potions=_include_potions_for_battle_search(self.action_space),
        )
        search_elapsed = time.perf_counter() - search_start
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "model-guided oracle v2 root mapping failed: "
                + "; ".join(report.problems)
            )

        try:
            guidance = self.scorer.score_decision_context(context)
        except ValueError as exc:
            raise ValueError(f"model guidance inference failed: {exc}") from exc
        _validate_guidance_result(
            guidance,
            context=context,
            expected_checkpoint=self.checkpoint_provenance,
        )

        root_scores = build_model_guided_oracle_v2_root_scores(
            report,
            guidance,
            policy_probability_weight=float(self.policy_probability_weight),
        )
        target = select_model_guided_oracle_root_action(
            root_scores,
            selection_rule=MODEL_GUIDED_ORACLE_V2_ROOT_SELECTION_RULE,
        )
        total_elapsed = time.perf_counter() - total_start
        decision_report = ModelGuidedOracleSearchDecisionReport(
            oracle_report=report,
            guidance_result=guidance,
            policy_probability_weight=float(self.policy_probability_weight),
            root_scores=root_scores,
            target=target,
            total_wall_clock_time_s=total_elapsed,
            native_search_wall_clock_time_s=search_elapsed,
            controller_version=MODEL_GUIDED_ORACLE_SEARCH_V2_CONTROLLER_VERSION,
            root_selection_rule=MODEL_GUIDED_ORACLE_V2_ROOT_SELECTION_RULE,
            guidance_formula=_v2_guidance_formula(
                float(self.policy_probability_weight)
            ),
            telemetry_controller_kind="model_guided_oracle_battle_search_v2",
            search_kind=(
                "native_random_terminal_playout_with_visit_adjusted_public_root_guidance"
            ),
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"model_guided_oracle_v2:{MODEL_GUIDED_ORACLE_V2_ROOT_SELECTION_RULE}",
            score=target.combined_score,
            metadata=model_guided_oracle_search_controller_metadata(decision_report),
        )


def build_model_guided_oracle_root_scores(
    report: OracleSearchReport,
    guidance: SearchGuidanceInferenceResult,
    *,
    policy_probability_weight: float,
) -> tuple[ModelGuidedOracleRootScore, ...]:
    """Combine native root means with one public policy probability per action."""

    if not report.search_ok:
        raise ValueError("cannot score invalid oracle search report")
    _validate_policy_probability_weight(policy_probability_weight)
    by_index = _guidance_scores_by_index(guidance)
    rows: list[ModelGuidedOracleRootScore] = []
    for root_action in report.root_actions:
        model_score = by_index[root_action.legal_action_index]
        combined: float | None = None
        if (
            root_action.eligible
            and root_action.visits > 0
            and root_action.mean_value is not None
        ):
            combined = float(root_action.mean_value) + (
                policy_probability_weight * model_score.policy_probability
            )
        rows.append(
            ModelGuidedOracleRootScore(
                legal_action_index=root_action.legal_action_index,
                action_identity=dict(root_action.action_identity),
                eligible=root_action.eligible,
                native_visits=root_action.visits,
                native_mean_value=root_action.mean_value,
                model_policy_logit=model_score.policy_logit,
                model_policy_probability=model_score.policy_probability,
                combined_score=combined,
            )
        )
    return tuple(rows)


def build_model_guided_oracle_v2_root_scores(
    report: OracleSearchReport,
    guidance: SearchGuidanceInferenceResult,
    *,
    policy_probability_weight: float,
) -> tuple[ModelGuidedOracleRootScore, ...]:
    """Combine native root means with visit-adjusted public policy probability."""

    if not report.search_ok:
        raise ValueError("cannot score invalid oracle search report")
    _validate_policy_probability_weight(policy_probability_weight)
    by_index = _guidance_scores_by_index(guidance)
    rows: list[ModelGuidedOracleRootScore] = []
    for root_action in report.root_actions:
        model_score = by_index[root_action.legal_action_index]
        combined: float | None = None
        multiplier = 1.0
        if (
            root_action.eligible
            and root_action.visits > 0
            and root_action.mean_value is not None
        ):
            multiplier = _v2_model_guidance_multiplier(
                root_visits=report.root_visits,
                native_visits=root_action.visits,
            )
            combined = float(root_action.mean_value) + (
                policy_probability_weight * model_score.policy_probability * multiplier
            )
        rows.append(
            ModelGuidedOracleRootScore(
                legal_action_index=root_action.legal_action_index,
                action_identity=dict(root_action.action_identity),
                eligible=root_action.eligible,
                native_visits=root_action.visits,
                native_mean_value=root_action.mean_value,
                model_policy_logit=model_score.policy_logit,
                model_policy_probability=model_score.policy_probability,
                combined_score=combined,
                model_guidance_multiplier=multiplier,
            )
        )
    return tuple(rows)


def select_model_guided_oracle_root_action(
    root_scores: Sequence[ModelGuidedOracleRootScore],
    *,
    selection_rule: str = MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE,
) -> ModelGuidedOracleSearchTarget:
    """Select the highest combined root score, with deterministic tie-breaks."""

    candidates = [
        score
        for score in root_scores
        if score.eligible
        and score.native_visits > 0
        and score.combined_score is not None
    ]
    if not candidates:
        raise ValueError(
            "model-guided oracle search has no eligible visited action with "
            "native mean and model score"
        )
    selected = max(
        candidates,
        key=lambda score: (
            float(score.combined_score),
            score.native_visits,
            score.model_policy_probability,
            -score.legal_action_index,
        ),
    )
    assert selected.native_mean_value is not None
    assert selected.combined_score is not None
    return ModelGuidedOracleSearchTarget(
        selection_rule=selection_rule,
        legal_action_index=selected.legal_action_index,
        action_identity=dict(selected.action_identity),
        native_visits=selected.native_visits,
        native_mean_value=float(selected.native_mean_value),
        model_policy_logit=selected.model_policy_logit,
        model_policy_probability=selected.model_policy_probability,
        combined_score=selected.combined_score,
    )


def model_guided_oracle_search_controller_metadata(
    decision_report: ModelGuidedOracleSearchDecisionReport,
) -> dict[str, Any]:
    """Return JSON-safe per-decision telemetry for fixed evaluation."""

    oracle_report = decision_report.oracle_report
    guidance = decision_report.guidance_result
    target = decision_report.target
    telemetry = model_guided_oracle_search_decision_telemetry(decision_report)
    native_telemetry = oracle_search_decision_telemetry(
        oracle_report,
        target=target.to_oracle_target(),
    )
    combined_gap = _combined_decision_gap(decision_report.root_scores)
    return json_safe_mapping(
        {
            "oracle_search_decision_count": 1,
            "oracle_search_simulations": oracle_report.simulations_requested,
            "oracle_search_root_visits": oracle_report.root_visits,
            "oracle_search_native_simulator_steps": (
                oracle_report.native_simulator_steps
            ),
            "oracle_search_model_calls": native_telemetry.model_calls,
            "oracle_search_wall_clock_time_s": (
                decision_report.total_wall_clock_time_s
            ),
            "oracle_search_root_row_count": oracle_report.root_row_count,
            "oracle_search_unmapped_root_rows": (oracle_report.unmapped_root_row_count),
            "oracle_search_unsearched_legal_actions": (
                oracle_report.unsearched_legal_action_count
            ),
            "oracle_search_unmapped_search_edges": (
                oracle_report.unmapped_search_edge_count
            ),
            "oracle_search_root_mapping_failures": len(oracle_report.problems),
            "oracle_search_selected_rule": target.selection_rule,
            "oracle_search_selected_index": target.legal_action_index,
            "oracle_search_selected_visits": target.native_visits,
            "oracle_search_selected_mean_value": target.native_mean_value,
            "model_guided_oracle_decision_count": 1,
            "model_guided_oracle_controller_version": (
                decision_report.controller_version
            ),
            "model_guided_oracle_selection_rule": target.selection_rule,
            "model_guided_oracle_guidance_formula": (
                decision_report.guidance_formula
                or _guidance_formula(decision_report.policy_probability_weight)
            ),
            "model_guided_oracle_policy_probability_weight": (
                decision_report.policy_probability_weight
            ),
            "model_guided_oracle_model_calls": 1,
            "model_guided_oracle_scorer_name": guidance.scorer_name,
            "model_guided_oracle_inference_schema_id": guidance.schema_id,
            "model_guided_oracle_checkpoint_artifact_id": (
                guidance.checkpoint_provenance.checkpoint_artifact_id
            ),
            "model_guided_oracle_selected_index": target.legal_action_index,
            "model_guided_oracle_selected_combined_score": target.combined_score,
            "model_guided_oracle_selected_model_policy_probability": (
                target.model_policy_probability
            ),
            "model_guided_oracle_selected_model_policy_logit": (
                target.model_policy_logit
            ),
            "model_guided_oracle_selected_native_mean_value": (
                target.native_mean_value
            ),
            "model_guided_oracle_combined_decision_gap": combined_gap,
            "model_guided_oracle_native_search_wall_clock_time_s": (
                decision_report.native_search_wall_clock_time_s
            ),
            "model_guided_oracle_total_wall_clock_time_s": (
                decision_report.total_wall_clock_time_s
            ),
            "model_guided_oracle_root_scores": [
                score.to_dict() for score in decision_report.root_scores
            ],
            "model_guided_oracle_checkpoint_provenance": (
                guidance.checkpoint_provenance.to_dict()
            ),
            "model_guidance_inference": [guidance.to_dict()],
            "model_guided_oracle_decision_reports": [decision_report.to_dict()],
            "oracle_search_decision_reports": [oracle_report.to_dict()],
            "search_decision_telemetry_schema_id": (
                SEARCH_DECISION_TELEMETRY_SCHEMA_ID
            ),
            "search_decision_telemetry": [telemetry.to_dict()],
        }
    )


def model_guided_oracle_search_decision_telemetry(
    decision_report: ModelGuidedOracleSearchDecisionReport,
) -> SearchDecisionTelemetry:
    """Build current-schema telemetry for one model-guided Oracle-like search."""

    oracle_report = decision_report.oracle_report
    target = decision_report.target
    baseline = oracle_search_decision_telemetry(
        oracle_report,
        target=target.to_oracle_target(),
    )
    unavailable = dict(baseline.unavailable_fields)
    unavailable["model_guided_allocation"] = (
        "current native battle_search API does not accept model priors or "
        "allocation hints; guidance is root selection only"
    )
    if (
        decision_report.controller_version
        == MODEL_GUIDED_ORACLE_SEARCH_V2_CONTROLLER_VERSION
    ):
        unavailable["model_guided_leaf_values"] = (
            "current native battle_search API does not accept model leaf values; "
            "v2 visit adjustment is applied only after root search completes"
        )
    checkpoint = decision_report.guidance_result.checkpoint_provenance
    return SearchDecisionTelemetry(
        information_regime=oracle_report.information_regime,
        controller_kind=decision_report.telemetry_controller_kind,
        search_kind=decision_report.search_kind,
        search_backend={
            "native_api": oracle_report.native_api,
            "patch_identity": oracle_report.patch_identity,
            "schema_id": oracle_report.schema_id,
            "controller_version": decision_report.controller_version,
            "root_selection_rule": decision_report.root_selection_rule,
            "guidance_schema_id": decision_report.guidance_result.schema_id,
            "guidance_schema_version": decision_report.guidance_result.schema_version,
            "guidance_scorer": decision_report.guidance_result.scorer_name,
            "checkpoint_schema_id": checkpoint.checkpoint_schema_id,
            "checkpoint_artifact_id": checkpoint.checkpoint_artifact_id,
        },
        requested_budget={
            "unit": "native_random_terminal_playouts",
            "amount": oracle_report.simulations_requested,
        },
        simulations_requested=oracle_report.simulations_requested,
        root_visits=oracle_report.root_visits,
        root_action_count=len(oracle_report.root_actions),
        legal_action_count=oracle_report.legal_action_count,
        eligible_action_count=oracle_report.eligible_action_count,
        visited_action_count=sum(
            1 for action in oracle_report.root_actions if action.visits > 0
        ),
        visited_eligible_action_count=sum(
            1
            for action in oracle_report.root_actions
            if action.eligible and action.visits > 0
        ),
        native_simulator_steps=oracle_report.native_simulator_steps,
        model_calls=1,
        wall_clock_time_s=decision_report.total_wall_clock_time_s,
        root_value_min=baseline.root_value_min,
        root_value_max=baseline.root_value_max,
        root_value_spread=baseline.root_value_spread,
        root_decision_gap=baseline.root_decision_gap,
        unsearched_legal_action_count=oracle_report.unsearched_legal_action_count,
        unmapped_search_edge_count=oracle_report.unmapped_search_edge_count,
        unmapped_root_row_count=oracle_report.unmapped_root_row_count,
        root_mapping_failure_count=len(oracle_report.problems),
        selection_rule=target.selection_rule,
        selected_legal_action_index=target.legal_action_index,
        selected_visits=target.native_visits,
        selected_mean_value=target.native_mean_value,
        unavailable_fields=unavailable,
        problems=oracle_report.problems,
    )


def _guidance_formula(policy_probability_weight: float) -> str:
    return (
        "combined_score = native_mean_value + "
        f"{policy_probability_weight:g} * model_policy_probability"
    )


def _v2_guidance_formula(policy_probability_weight: float) -> str:
    return (
        "combined_score = native_mean_value + "
        f"{policy_probability_weight:g} * model_policy_probability * "
        "sqrt(total_root_visits / native_visits)"
    )


def _v2_model_guidance_multiplier(*, root_visits: int, native_visits: int) -> float:
    if root_visits <= 0 or native_visits <= 0:
        return 1.0
    return math.sqrt(root_visits / native_visits)


def _scorer_checkpoint_provenance(
    scorer: SearchGuidanceScorer,
) -> SearchGuidanceCheckpointProvenance:
    value = getattr(scorer, "checkpoint_provenance", None)
    if not isinstance(value, SearchGuidanceCheckpointProvenance):
        raise ValueError(
            "model-guided oracle scorer must expose current "
            "SearchGuidanceCheckpointProvenance as checkpoint_provenance"
        )
    return value


def _validate_guidance_result(
    result: SearchGuidanceInferenceResult,
    *,
    context: DecisionContext,
    expected_checkpoint: SearchGuidanceCheckpointProvenance,
) -> None:
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
            _append_finite_score_problems(score, problems)
            continue
        expected_kind = context.legal_action_kinds[index]
        if score.action_kind != expected_kind:
            problems.append(
                "guidance action kind for index "
                f"{index} does not match context: "
                f"{score.action_kind!r} != {expected_kind!r}"
            )
        expected_identity = _context_action_identity(context, index)
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
        _append_finite_score_problems(score, problems)
    missing = sorted(set(range(legal_count)) - seen)
    if missing:
        problems.append(f"missing guidance action score for index {missing[0]}")
    if problems:
        raise ValueError("; ".join(dict.fromkeys(problems)))


def _context_action_identity(
    context: DecisionContext,
    index: int,
) -> dict[str, Any]:
    if index < 0 or index >= len(context.tactical_legal_actions):
        return {}
    action = context.tactical_legal_actions[index]
    if not isinstance(action, Mapping):
        return {}
    identity = action.get("identity")
    if not isinstance(identity, Mapping):
        return {}
    return dict(identity)


def _append_finite_score_problems(
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


def _guidance_scores_by_index(
    guidance: SearchGuidanceInferenceResult,
) -> dict[int, SearchGuidanceActionScore]:
    return {score.legal_action_index: score for score in guidance.action_scores}


def _combined_decision_gap(
    root_scores: Sequence[ModelGuidedOracleRootScore],
) -> float | None:
    values = sorted(
        (
            float(score.combined_score)
            for score in root_scores
            if score.eligible and score.combined_score is not None
        ),
        reverse=True,
    )
    if len(values) < 2:
        return None
    return values[0] - values[1]


def _validate_policy_probability_weight(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0.0
    ):
        raise ValueError("policy_probability_weight must be finite and non-negative")


def _include_potions_for_battle_search(action_space: ActionSpaceConfig) -> bool:
    return not bool(action_space.excluded_kinds.intersection(POTION_ACTION_KINDS))
