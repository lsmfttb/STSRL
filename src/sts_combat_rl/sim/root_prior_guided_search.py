"""Root-prior guided Oracle-like battle search controller for T047.

The controller scores the public decision context with the current search
guidance scorer, passes those policy probabilities into the T046 native
root-prior allocation surface, then selects from native root statistics only.
It remains full-simulator-state Oracle-like because the native search copies
the hidden simulator state.
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
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
    NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
    NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
    build_root_action_prior_vector,
    root_prior_allocation_metadata,
    root_prior_allocation_rows,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchReport,
    OracleSearchTarget,
    build_oracle_search_report,
    oracle_search_decision_telemetry,
    select_oracle_root_action,
    validate_oracle_root_selection_rule,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)
from sts_combat_rl.sim.search_telemetry import (
    SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
    SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
    SearchDecisionTelemetry,
)


ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION = "root-prior-guided-search-controller-v1"
ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME = "root_prior_guided_oracle_search_v1"
GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION = (
    "guardrailed-root-prior-guided-search-controller-v1"
)
GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME = (
    "guardrailed_root_prior_guided_oracle_search_v1"
)
ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION = "root-prior-allocation-guardrail-v1"
ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY = "uniform-blend-capped-prior-v1"
ROOT_PRIOR_GUIDED_SELECTION_SCOPE = (
    "public checkpoint policy probabilities influence native root playout "
    "allocation only; final root selection uses native root statistics"
)
GUARDRAILED_ROOT_PRIOR_SELECTION_SCOPE = (
    "public checkpoint policy probabilities are guardrailed before native root "
    "playout allocation; final root selection uses native root statistics"
)


@dataclass(frozen=True)
class RootPriorAllocationGuardrailConfig:
    """Versioned public-prior guardrail applied before native allocation."""

    uniform_blend_weight: float = 0.35
    max_prior_probability: float = 0.65
    strategy: str = ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY
    version: str = ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION

    def __post_init__(self) -> None:
        _validate_root_prior_guardrail_config(
            uniform_blend_weight=self.uniform_blend_weight,
            max_prior_probability=self.max_prior_probability,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "strategy": self.strategy,
            "uniform_blend_weight": float(self.uniform_blend_weight),
            "max_prior_probability": float(self.max_prior_probability),
            "online_inputs": [
                "public checkpoint legal-action policy probabilities",
                "current public legal-action identities",
            ],
            "forbidden_online_inputs": [
                "hidden future outcomes",
                "unrevealed encounter information",
                "T053 disagreement labels",
                "cohort indices",
            ],
        }


@dataclass(frozen=True)
class RootPriorGuidancePriorRow:
    """One public model prior mapped to an occurrence-safe root action."""

    legal_action_index: int
    action_identity: dict[str, Any]
    stable_action_identity: str
    action_kind: str
    eligible: bool
    policy_logit: float
    policy_probability: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_action_index": self.legal_action_index,
            "action_identity": dict(self.action_identity),
            "stable_action_identity": self.stable_action_identity,
            "action_kind": self.action_kind,
            "eligible": self.eligible,
            "policy_logit": self.policy_logit,
            "policy_probability": self.policy_probability,
        }


@dataclass(frozen=True)
class RootPriorGuidedSearchDecisionReport:
    """Per-decision T047 search report."""

    oracle_report: OracleSearchReport
    guidance_result: SearchGuidanceInferenceResult
    root_action_priors: dict[str, float]
    prior_rows: tuple[RootPriorGuidancePriorRow, ...]
    prior_summary: dict[str, Any]
    allocation_metadata: dict[str, Any]
    allocation_rows: tuple[dict[str, Any], ...]
    target: OracleSearchTarget
    total_wall_clock_time_s: float | None
    native_search_wall_clock_time_s: float | None
    controller_version: str = ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
    root_selection_rule: str = "highest_mean"
    guidance_scope: str = ROOT_PRIOR_GUIDED_SELECTION_SCOPE
    guardrail_config: dict[str, Any] | None = None
    pre_guardrail_prior_rows: tuple[RootPriorGuidancePriorRow, ...] = ()
    pre_guardrail_prior_summary: dict[str, Any] | None = None
    guardrail_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "controller_version": self.controller_version,
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "guidance_scope": self.guidance_scope,
            "root_selection_rule": self.root_selection_rule,
            "total_wall_clock_time_s": self.total_wall_clock_time_s,
            "native_search_wall_clock_time_s": self.native_search_wall_clock_time_s,
            "model_calls": 1,
            "oracle_search_report": self.oracle_report.to_dict(),
            "guidance_result": self.guidance_result.to_dict(),
            "root_action_priors": dict(self.root_action_priors),
            "prior_rows": [row.to_dict() for row in self.prior_rows],
            "prior_summary": dict(self.prior_summary),
            "allocation_metadata": dict(self.allocation_metadata),
            "allocation_rows": [dict(row) for row in self.allocation_rows],
            "target": self.target.to_dict(),
        }
        if self.guardrail_config is not None:
            payload["guardrail_config"] = dict(self.guardrail_config)
            payload["pre_guardrail_prior_rows"] = [
                row.to_dict() for row in self.pre_guardrail_prior_rows
            ]
            payload["pre_guardrail_prior_summary"] = dict(
                self.pre_guardrail_prior_summary or {}
            )
            payload["guardrail_summary"] = dict(self.guardrail_summary or {})
        return payload


@dataclass(frozen=True)
class RootPriorGuidedSearchController:
    """OnlineController using checkpoint priors for native root allocation."""

    simulations: int
    scorer: SearchGuidanceScorer
    root_selection_rule: str = "highest_mean"
    prior_temperature: float = 1.0
    min_visits_per_legal_action: int = 1
    prior_allocation_weight: float = 1.0
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)

    def __post_init__(self) -> None:
        _validate_root_prior_guided_config(
            simulations=self.simulations,
            root_selection_rule=self.root_selection_rule,
            prior_temperature=self.prior_temperature,
            min_visits_per_legal_action=self.min_visits_per_legal_action,
            prior_allocation_weight=self.prior_allocation_weight,
        )
        checkpoint_provenance = search_guidance_scorer_checkpoint_provenance(
            self.scorer,
            label="root-prior guided scorer",
        )
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
                kind="root_prior_guided_oracle_battle_search",
                name=(
                    f"{ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME}_"
                    f"{self.root_selection_rule}_s{self.simulations}"
                ),
                config={
                    "controller_version": ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
                    "task_id": "T047",
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
                    "native_search_patch_identity": (
                        NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY
                    ),
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "root_selection_rule": self.root_selection_rule,
                    "guidance_scope": ROOT_PRIOR_GUIDED_SELECTION_SCOPE,
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "inference_schema_id": SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
                        "inference_schema_version": (
                            SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
                        ),
                        "checkpoint_provenance": checkpoint_provenance.to_dict(),
                    },
                    "root_prior_allocation": {
                        "metadata_schema_id": (
                            NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
                        ),
                        "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
                        "prior_source": "search_guidance_policy_probability",
                        "prior_temperature": float(self.prior_temperature),
                        "min_visits_per_legal_action": int(
                            self.min_visits_per_legal_action
                        ),
                        "prior_allocation_weight": float(self.prior_allocation_weight),
                        "final_root_selection_uses_model_probability": False,
                    },
                    "search_telemetry": {
                        "schema_id": SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
                        "schema_version": SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
                        "model_calls_per_decision": 1,
                        "unavailable_native_fields": {
                            "tree_depth": "native search does not expose tree depth",
                            "value_uncertainty": (
                                "native search does not expose uncertainty"
                            ),
                            "learned_leaf_values": (
                                "T046 native surface consumes root priors only"
                            ),
                        },
                    },
                    "action_space": self.action_space.to_dict(),
                    "include_potions": _include_potions_for_battle_search(
                        self.action_space
                    ),
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
        if not hasattr(adapter, "battle_search_with_root_priors"):
            raise ValueError(
                "root-prior guided search controller requires "
                "battle_search_with_root_priors adapter"
            )

        total_start = time.perf_counter()
        try:
            guidance = self.scorer.score_decision_context(context)
        except ValueError as exc:
            raise ValueError(f"root-prior guidance inference failed: {exc}") from exc
        validate_search_guidance_result(
            guidance,
            context=context,
            expected_checkpoint=self.checkpoint_provenance,
        )
        priors, prior_rows, prior_summary = build_guidance_root_action_priors(
            actions,
            context,
            guidance,
        )

        search_fn = getattr(adapter, "battle_search_with_root_priors")
        search_start = time.perf_counter()
        raw_search = search_fn(
            snapshot,
            actions=actions,
            context=context,
            simulations=self.simulations,
            include_potions=_include_potions_for_battle_search(self.action_space),
            root_action_priors=priors,
            prior_temperature=self.prior_temperature,
            min_visits_per_legal_action=self.min_visits_per_legal_action,
            prior_allocation_weight=self.prior_allocation_weight,
        )
        search_elapsed = time.perf_counter() - search_start
        allocation_metadata = root_prior_allocation_metadata(raw_search)
        allocation_rows = root_prior_allocation_rows(raw_search)
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            expected_native_api=NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
            expected_patch_identity=NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "root-prior guided root mapping failed: " + "; ".join(report.problems)
            )
        target = select_oracle_root_action(
            report,
            selection_rule=self.root_selection_rule,
        )
        total_elapsed = time.perf_counter() - total_start
        decision_report = RootPriorGuidedSearchDecisionReport(
            oracle_report=report,
            guidance_result=guidance,
            root_action_priors=priors,
            prior_rows=prior_rows,
            prior_summary=prior_summary,
            allocation_metadata=allocation_metadata,
            allocation_rows=allocation_rows,
            target=target,
            total_wall_clock_time_s=total_elapsed,
            native_search_wall_clock_time_s=search_elapsed,
            root_selection_rule=self.root_selection_rule,
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"root_prior_guided_oracle_search:{self.root_selection_rule}",
            score=target.score,
            metadata=root_prior_guided_search_controller_metadata(decision_report),
        )


@dataclass(frozen=True)
class GuardrailedRootPriorGuidedSearchController:
    """T054 guardrailed variant of root-prior guided Oracle-like search."""

    simulations: int
    scorer: SearchGuidanceScorer
    root_selection_rule: str = "highest_mean"
    prior_temperature: float = 1.0
    min_visits_per_legal_action: int = 1
    prior_allocation_weight: float = 1.0
    guardrail_config: RootPriorAllocationGuardrailConfig = field(
        default_factory=RootPriorAllocationGuardrailConfig
    )
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)

    def __post_init__(self) -> None:
        _validate_root_prior_guided_config(
            simulations=self.simulations,
            root_selection_rule=self.root_selection_rule,
            prior_temperature=self.prior_temperature,
            min_visits_per_legal_action=self.min_visits_per_legal_action,
            prior_allocation_weight=self.prior_allocation_weight,
        )
        checkpoint_provenance = search_guidance_scorer_checkpoint_provenance(
            self.scorer,
            label="guardrailed root-prior guided scorer",
        )
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
                kind="guardrailed_root_prior_guided_oracle_battle_search",
                name=(
                    f"{GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME}_"
                    f"{self.root_selection_rule}_s{self.simulations}"
                ),
                config={
                    "controller_version": (
                        GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
                    ),
                    "task_id": "T054",
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
                    "native_search_patch_identity": (
                        NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY
                    ),
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "root_selection_rule": self.root_selection_rule,
                    "guidance_scope": GUARDRAILED_ROOT_PRIOR_SELECTION_SCOPE,
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "inference_schema_id": SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
                        "inference_schema_version": (
                            SEARCH_GUIDANCE_INFERENCE_SCHEMA_VERSION
                        ),
                        "checkpoint_provenance": checkpoint_provenance.to_dict(),
                    },
                    "root_prior_allocation": {
                        "metadata_schema_id": (
                            NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
                        ),
                        "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
                        "prior_source": (
                            "guardrailed_search_guidance_policy_probability"
                        ),
                        "prior_temperature": float(self.prior_temperature),
                        "min_visits_per_legal_action": int(
                            self.min_visits_per_legal_action
                        ),
                        "prior_allocation_weight": float(self.prior_allocation_weight),
                        "guardrail": self.guardrail_config.to_dict(),
                        "final_root_selection_uses_model_probability": False,
                    },
                    "search_telemetry": {
                        "schema_id": SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
                        "schema_version": SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
                        "model_calls_per_decision": 1,
                        "unavailable_native_fields": {
                            "tree_depth": "native search does not expose tree depth",
                            "value_uncertainty": (
                                "native search does not expose uncertainty"
                            ),
                            "learned_leaf_values": (
                                "T046 native surface consumes root priors only"
                            ),
                            "guardrail_causal_effect": (
                                "native search exposes allocation rows but not a "
                                "paired within-decision counterfactual search"
                            ),
                        },
                    },
                    "action_space": self.action_space.to_dict(),
                    "include_potions": _include_potions_for_battle_search(
                        self.action_space
                    ),
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
        if not hasattr(adapter, "battle_search_with_root_priors"):
            raise ValueError(
                "guardrailed root-prior guided search controller requires "
                "battle_search_with_root_priors adapter"
            )

        total_start = time.perf_counter()
        try:
            guidance = self.scorer.score_decision_context(context)
        except ValueError as exc:
            raise ValueError(f"root-prior guidance inference failed: {exc}") from exc
        validate_search_guidance_result(
            guidance,
            context=context,
            expected_checkpoint=self.checkpoint_provenance,
        )
        raw_priors, raw_prior_rows, raw_prior_summary = (
            build_guidance_root_action_priors(
                actions,
                context,
                guidance,
            )
        )
        priors, prior_rows, prior_summary, guardrail_summary = (
            apply_root_prior_allocation_guardrail(
                actions,
                context,
                raw_priors,
                raw_prior_rows,
                raw_prior_summary,
                config=self.guardrail_config,
            )
        )

        search_fn = getattr(adapter, "battle_search_with_root_priors")
        search_start = time.perf_counter()
        raw_search = search_fn(
            snapshot,
            actions=actions,
            context=context,
            simulations=self.simulations,
            include_potions=_include_potions_for_battle_search(self.action_space),
            root_action_priors=priors,
            prior_temperature=self.prior_temperature,
            min_visits_per_legal_action=self.min_visits_per_legal_action,
            prior_allocation_weight=self.prior_allocation_weight,
        )
        search_elapsed = time.perf_counter() - search_start
        allocation_metadata = root_prior_allocation_metadata(raw_search)
        allocation_rows = root_prior_allocation_rows(raw_search)
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            expected_native_api=NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
            expected_patch_identity=NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "guardrailed root-prior guided root mapping failed: "
                + "; ".join(report.problems)
            )
        target = select_oracle_root_action(
            report,
            selection_rule=self.root_selection_rule,
        )
        total_elapsed = time.perf_counter() - total_start
        decision_report = RootPriorGuidedSearchDecisionReport(
            oracle_report=report,
            guidance_result=guidance,
            root_action_priors=priors,
            prior_rows=prior_rows,
            prior_summary=prior_summary,
            allocation_metadata=allocation_metadata,
            allocation_rows=allocation_rows,
            target=target,
            total_wall_clock_time_s=total_elapsed,
            native_search_wall_clock_time_s=search_elapsed,
            controller_version=GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
            root_selection_rule=self.root_selection_rule,
            guidance_scope=GUARDRAILED_ROOT_PRIOR_SELECTION_SCOPE,
            guardrail_config=self.guardrail_config.to_dict(),
            pre_guardrail_prior_rows=raw_prior_rows,
            pre_guardrail_prior_summary=raw_prior_summary,
            guardrail_summary=guardrail_summary,
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=(
                "guardrailed_root_prior_guided_oracle_search:"
                f"{self.root_selection_rule}"
            ),
            score=target.score,
            metadata=root_prior_guided_search_controller_metadata(decision_report),
        )


def build_guidance_root_action_priors(
    actions: Sequence[SimulatorAction],
    context: DecisionContext,
    guidance: SearchGuidanceInferenceResult,
) -> tuple[dict[str, float], tuple[RootPriorGuidancePriorRow, ...], dict[str, Any]]:
    """Map checkpoint policy probabilities to occurrence-safe root prior keys."""

    identities = action_identity_dicts_for_actions(actions)
    by_index = {score.legal_action_index: score for score in guidance.action_scores}
    eligible_indices = list(context.eligible_action_indices)
    priors: dict[str, float] = {}
    rows: list[RootPriorGuidancePriorRow] = []
    probability_sum = 0.0
    positive_count = 0
    max_probability: float | None = None
    max_probability_index: int | None = None
    for index in eligible_indices:
        if index < 0 or index >= len(identities):
            raise ValueError(f"eligible action index {index} outside legal actions")
        score = by_index.get(index)
        if score is None:
            raise ValueError(f"missing guidance action score for index {index}")
        stable_id = str(identities[index]["stable_id"])
        probability = float(score.policy_probability)
        priors[stable_id] = probability
        rows.append(
            RootPriorGuidancePriorRow(
                legal_action_index=index,
                action_identity=dict(identities[index]),
                stable_action_identity=stable_id,
                action_kind=score.action_kind,
                eligible=True,
                policy_logit=float(score.policy_logit),
                policy_probability=probability,
            )
        )
        probability_sum += probability
        if probability > 0.0:
            positive_count += 1
        if max_probability is None or probability > max_probability:
            max_probability = probability
            max_probability_index = index

    if not priors:
        raise ValueError("root-prior guidance produced no eligible priors")
    if probability_sum <= 0.0:
        raise ValueError("root-prior guidance produced no positive eligible priors")
    vector = build_root_action_prior_vector(actions, context, priors)
    summary = {
        "prior_source": "search_guidance_policy_probability",
        "legal_action_count": len(actions),
        "eligible_action_count": len(eligible_indices),
        "provided_prior_count": len(priors),
        "positive_prior_count": positive_count,
        "prior_probability_sum": probability_sum,
        "max_prior_probability": max_probability,
        "max_prior_legal_action_index": max_probability_index,
        "native_prior_vector": list(vector),
    }
    return priors, tuple(rows), summary


def apply_root_prior_allocation_guardrail(
    actions: Sequence[SimulatorAction],
    context: DecisionContext,
    raw_priors: Mapping[str, float],
    raw_prior_rows: Sequence[RootPriorGuidancePriorRow],
    raw_prior_summary: Mapping[str, Any],
    *,
    config: RootPriorAllocationGuardrailConfig,
) -> tuple[
    dict[str, float],
    tuple[RootPriorGuidancePriorRow, ...],
    dict[str, Any],
    dict[str, Any],
]:
    """Blend public policy priors with uniform mass and cap concentration."""

    if not raw_prior_rows:
        raise ValueError("root-prior guardrail received no prior rows")
    raw_probabilities = [float(row.policy_probability) for row in raw_prior_rows]
    normalized = _normalize_probability_distribution(raw_probabilities)
    if len(normalized) == 1:
        adjusted = [1.0]
    else:
        uniform = 1.0 / len(normalized)
        blended = [
            (1.0 - config.uniform_blend_weight) * value
            + config.uniform_blend_weight * uniform
            for value in normalized
        ]
        adjusted = _cap_probability_distribution(
            blended,
            cap=config.max_prior_probability,
        )

    priors: dict[str, float] = {}
    adjusted_rows: list[RootPriorGuidancePriorRow] = []
    changed_count = 0
    l1_delta = 0.0
    max_pre = max(normalized)
    max_post = max(adjusted)
    for row, pre, post in zip(raw_prior_rows, normalized, adjusted, strict=True):
        stable_id = row.stable_action_identity
        priors[stable_id] = post
        l1_delta += abs(post - pre)
        if not math.isclose(post, pre, rel_tol=0.0, abs_tol=1e-12):
            changed_count += 1
        adjusted_rows.append(
            RootPriorGuidancePriorRow(
                legal_action_index=row.legal_action_index,
                action_identity=dict(row.action_identity),
                stable_action_identity=stable_id,
                action_kind=row.action_kind,
                eligible=row.eligible,
                policy_logit=row.policy_logit,
                policy_probability=post,
            )
        )

    vector = build_root_action_prior_vector(actions, context, priors)
    max_probability = max(adjusted)
    max_probability_index = adjusted_rows[
        adjusted.index(max_probability)
    ].legal_action_index
    positive_count = sum(1 for value in adjusted if value > 0.0)
    summary = {
        "prior_source": "guardrailed_search_guidance_policy_probability",
        "legal_action_count": raw_prior_summary.get("legal_action_count"),
        "eligible_action_count": len(adjusted_rows),
        "provided_prior_count": len(priors),
        "positive_prior_count": positive_count,
        "prior_probability_sum": sum(adjusted),
        "max_prior_probability": max_probability,
        "max_prior_legal_action_index": max_probability_index,
        "native_prior_vector": list(vector),
        "guardrail_version": config.version,
        "guardrail_strategy": config.strategy,
    }
    guardrail_summary = {
        "guardrail_applied": True,
        "guardrail_config": config.to_dict(),
        "pre_guardrail_prior_source": raw_prior_summary.get("prior_source"),
        "pre_guardrail_prior_probability_sum": sum(normalized),
        "post_guardrail_prior_probability_sum": sum(adjusted),
        "pre_guardrail_max_prior_probability": max_pre,
        "post_guardrail_max_prior_probability": max_post,
        "changed_prior_count": changed_count,
        "l1_prior_delta": l1_delta,
        "eligible_action_count": len(adjusted_rows),
        "single_action_noop": len(adjusted_rows) == 1,
        "native_prior_vector": list(vector),
    }
    return priors, tuple(adjusted_rows), summary, guardrail_summary


def root_prior_guided_search_controller_metadata(
    decision_report: RootPriorGuidedSearchDecisionReport,
) -> dict[str, Any]:
    """Return JSON-safe per-decision T047 telemetry."""

    report = decision_report.oracle_report
    target = decision_report.target
    telemetry = root_prior_guided_search_decision_telemetry(decision_report)
    native_telemetry = oracle_search_decision_telemetry(report, target=target)
    payload = {
        "oracle_search_decision_count": 1,
        "oracle_search_simulations": report.simulations_requested,
        "oracle_search_root_visits": report.root_visits,
        "oracle_search_native_simulator_steps": report.native_simulator_steps,
        "oracle_search_model_calls": native_telemetry.model_calls,
        "oracle_search_wall_clock_time_s": report.wall_clock_time_s,
        "oracle_search_root_row_count": report.root_row_count,
        "oracle_search_unmapped_root_rows": report.unmapped_root_row_count,
        "oracle_search_unsearched_legal_actions": (
            report.unsearched_legal_action_count
        ),
        "oracle_search_unmapped_search_edges": report.unmapped_search_edge_count,
        "oracle_search_root_mapping_failures": len(report.problems),
        "oracle_search_selected_rule": target.selection_rule,
        "oracle_search_selected_index": target.legal_action_index,
        "oracle_search_selected_visits": target.visits,
        "oracle_search_selected_mean_value": target.mean_value,
        "root_prior_guided_decision_count": 1,
        "root_prior_guided_controller_version": (decision_report.controller_version),
        "root_prior_guided_guidance_scope": decision_report.guidance_scope,
        "root_prior_guided_root_selection_rule": target.selection_rule,
        "root_prior_guided_model_calls": 1,
        "root_prior_guided_scorer_name": (decision_report.guidance_result.scorer_name),
        "root_prior_guided_checkpoint_artifact_id": (
            decision_report.guidance_result.checkpoint_provenance.checkpoint_artifact_id
        ),
        "root_prior_guided_prior_summary": dict(decision_report.prior_summary),
        "root_prior_guided_allocation_metadata": dict(
            decision_report.allocation_metadata
        ),
        "root_prior_guided_allocation_rows": [
            dict(row) for row in decision_report.allocation_rows
        ],
        "root_prior_guided_selected_index": target.legal_action_index,
        "root_prior_guided_selected_visits": target.visits,
        "root_prior_guided_selected_mean_value": target.mean_value,
        "root_prior_guided_native_search_wall_clock_time_s": (
            decision_report.native_search_wall_clock_time_s
        ),
        "root_prior_guided_total_wall_clock_time_s": (
            decision_report.total_wall_clock_time_s
        ),
        "root_prior_guided_checkpoint_provenance": (
            decision_report.guidance_result.checkpoint_provenance.to_dict()
        ),
        "model_guidance_inference": [decision_report.guidance_result.to_dict()],
        "root_prior_guided_decision_reports": [decision_report.to_dict()],
        "oracle_search_decision_reports": [report.to_dict()],
        "search_decision_telemetry_schema_id": (SEARCH_DECISION_TELEMETRY_SCHEMA_ID),
        "search_decision_telemetry": [telemetry.to_dict()],
    }
    if decision_report.guardrail_config is not None:
        payload.update(
            {
                "root_prior_guided_guardrail_config": dict(
                    decision_report.guardrail_config
                ),
                "root_prior_guided_pre_guardrail_prior_summary": dict(
                    decision_report.pre_guardrail_prior_summary or {}
                ),
                "root_prior_guided_guardrail_summary": dict(
                    decision_report.guardrail_summary or {}
                ),
            }
        )
    return json_safe_mapping(payload)


def root_prior_guided_search_decision_telemetry(
    decision_report: RootPriorGuidedSearchDecisionReport,
) -> SearchDecisionTelemetry:
    """Build current-schema telemetry for one root-prior guided decision."""

    report = decision_report.oracle_report
    target = decision_report.target
    baseline = oracle_search_decision_telemetry(report, target=target)
    unavailable = dict(baseline.unavailable_fields)
    unavailable["learned_leaf_values"] = (
        "T046 native root-prior surface does not accept learned leaf values"
    )
    checkpoint = decision_report.guidance_result.checkpoint_provenance
    guarded = decision_report.guardrail_config is not None
    if guarded:
        unavailable["guardrail_causal_effect"] = (
            "native search exposes allocation rows but not a paired "
            "within-decision counterfactual search"
        )
    return SearchDecisionTelemetry(
        information_regime=report.information_regime,
        controller_kind=(
            "guardrailed_root_prior_guided_oracle_battle_search"
            if guarded
            else "root_prior_guided_oracle_battle_search"
        ),
        search_kind=(
            "native_random_terminal_playout_with_guardrailed_public_root_priors"
            if guarded
            else "native_random_terminal_playout_with_public_root_priors"
        ),
        search_backend={
            "native_api": report.native_api,
            "patch_identity": report.patch_identity,
            "schema_id": report.schema_id,
            "controller_version": decision_report.controller_version,
            "root_selection_rule": decision_report.root_selection_rule,
            "allocation_metadata_schema_id": (
                decision_report.allocation_metadata.get("schema_id")
            ),
            "allocation_strategy": (
                decision_report.allocation_metadata.get("allocation_strategy")
            ),
            "guidance_schema_id": decision_report.guidance_result.schema_id,
            "guidance_schema_version": decision_report.guidance_result.schema_version,
            "guidance_scorer": decision_report.guidance_result.scorer_name,
            "checkpoint_schema_id": checkpoint.checkpoint_schema_id,
            "checkpoint_artifact_id": checkpoint.checkpoint_artifact_id,
            **(
                {
                    "root_prior_guardrail": dict(
                        decision_report.guardrail_config or {}
                    ),
                }
                if guarded
                else {}
            ),
        },
        requested_budget={
            "unit": "native_random_terminal_playouts",
            "amount": report.simulations_requested,
        },
        simulations_requested=report.simulations_requested,
        root_visits=report.root_visits,
        root_action_count=len(report.root_actions),
        legal_action_count=report.legal_action_count,
        eligible_action_count=report.eligible_action_count,
        visited_action_count=sum(
            1 for action in report.root_actions if action.visits > 0
        ),
        visited_eligible_action_count=sum(
            1 for action in report.root_actions if action.eligible and action.visits > 0
        ),
        native_simulator_steps=report.native_simulator_steps,
        model_calls=1,
        wall_clock_time_s=decision_report.total_wall_clock_time_s,
        root_value_min=baseline.root_value_min,
        root_value_max=baseline.root_value_max,
        root_value_spread=baseline.root_value_spread,
        root_decision_gap=baseline.root_decision_gap,
        unsearched_legal_action_count=report.unsearched_legal_action_count,
        unmapped_search_edge_count=report.unmapped_search_edge_count,
        unmapped_root_row_count=report.unmapped_root_row_count,
        root_mapping_failure_count=len(report.problems),
        selection_rule=target.selection_rule,
        selected_legal_action_index=target.legal_action_index,
        selected_visits=target.visits,
        selected_mean_value=target.mean_value,
        unavailable_fields=unavailable,
        problems=report.problems,
    )


def _validate_root_prior_guided_config(
    *,
    simulations: int,
    root_selection_rule: str,
    prior_temperature: float,
    min_visits_per_legal_action: int,
    prior_allocation_weight: float,
) -> None:
    if simulations <= 0:
        raise ValueError("root-prior guided simulations must be positive")
    validate_oracle_root_selection_rule(root_selection_rule)
    if not math.isfinite(prior_temperature) or prior_temperature <= 0.0:
        raise ValueError("root-prior temperature must be finite and positive")
    if min_visits_per_legal_action < 0:
        raise ValueError("root-prior min visits must be non-negative")
    if (
        not math.isfinite(prior_allocation_weight)
        or prior_allocation_weight < 0.0
        or prior_allocation_weight > 1.0
    ):
        raise ValueError("root-prior allocation weight must be between zero and one")


def _validate_root_prior_guardrail_config(
    *,
    uniform_blend_weight: float,
    max_prior_probability: float,
) -> None:
    if (
        not math.isfinite(uniform_blend_weight)
        or uniform_blend_weight < 0.0
        or uniform_blend_weight > 1.0
    ):
        raise ValueError(
            "root-prior guardrail uniform blend must be between zero and one"
        )
    if (
        not math.isfinite(max_prior_probability)
        or max_prior_probability <= 0.0
        or max_prior_probability > 1.0
    ):
        raise ValueError("root-prior guardrail max prior probability must be in (0, 1]")


def _normalize_probability_distribution(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("probability distribution must not be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError(
            "probability distribution must contain finite non-negative values"
        )
    total = sum(values)
    if total <= 0.0:
        raise ValueError("probability distribution must have positive mass")
    return [value / total for value in values]


def _cap_probability_distribution(
    values: Sequence[float], *, cap: float
) -> list[float]:
    normalized = _normalize_probability_distribution(values)
    if len(normalized) == 1:
        return [1.0]
    effective_cap = max(cap, 1.0 / len(normalized))
    adjusted = list(normalized)
    for _ in range(len(adjusted) + 1):
        over = [index for index, value in enumerate(adjusted) if value > effective_cap]
        if not over:
            break
        excess = 0.0
        for index in over:
            excess += adjusted[index] - effective_cap
            adjusted[index] = effective_cap
        under = [index for index, value in enumerate(adjusted) if value < effective_cap]
        if not under or excess <= 0.0:
            break
        room = sum(effective_cap - adjusted[index] for index in under)
        if room <= 0.0:
            break
        for index in under:
            share = (effective_cap - adjusted[index]) / room
            adjusted[index] += excess * share
    total = sum(adjusted)
    if total <= 0.0:
        raise ValueError("capped probability distribution lost all mass")
    return [value / total for value in adjusted]


def _include_potions_for_battle_search(action_space: ActionSpaceConfig) -> bool:
    return not bool(action_space.excluded_kinds.intersection(POTION_ACTION_KINDS))
