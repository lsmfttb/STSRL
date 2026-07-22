"""T062 tree-internal policy/value Oracle-like battle search controller."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import time
from typing import Any, Literal

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    OracleSearchController,
    build_oracle_search_report,
    oracle_search_controller_metadata,
    select_oracle_root_action,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)


BATTLE_SEARCH_V2_CONTROLLER_NAME = "battle_search_v2_oracle_like_v1"
BATTLE_SEARCH_V2_CONTROLLER_VERSION = "battle-search-v2-oracle-like-v1"
BATTLE_SEARCH_V2_NATIVE_API = "StepSimulator.battle_search_v2.v1"
BATTLE_SEARCH_V2_PATCH_IDENTITY = "sts_lightspeed_battle_search_v2_tree_internal_v1"
BATTLE_SEARCH_V2_ABLATIONS = ("baseline", "prior_only", "value_only", "prior_value")
BattleSearchV2Ablation = Literal["baseline", "prior_only", "value_only", "prior_value"]


@dataclass(frozen=True)
class BattleSearchV2Controller:
    """One versioned T062 surface with fixed mechanism ablations.

    ``baseline`` delegates to :class:`OracleSearchController` so it retains the
    existing native API, root selection, action-space, and provenance exactly.
    The other three arms use the native T062 API and fail closed unless native
    telemetry proves the enabled mechanism was used below the root.
    """

    simulations: int
    scorer: SearchGuidanceScorer
    ablation: BattleSearchV2Ablation = "prior_value"
    root_selection_rule: str = "highest_mean"
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)
    _baseline: OracleSearchController = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.simulations <= 0:
            raise ValueError("battle search v2 simulations must be positive")
        if self.ablation not in BATTLE_SEARCH_V2_ABLATIONS:
            raise ValueError(f"unknown battle search v2 ablation {self.ablation!r}")
        if self.root_selection_rule != "highest_mean":
            raise ValueError("battle search v2 requires highest_mean root selection")
        checkpoint = search_guidance_scorer_checkpoint_provenance(self.scorer)
        object.__setattr__(self, "checkpoint_provenance", checkpoint)
        source_identity = (
            dict(self.native_source_identity)
            if self.native_source_identity is not None
            else lightspeed_source_identity_dict()
        )
        baseline = OracleSearchController(
            simulations=self.simulations,
            root_selection_rule=self.root_selection_rule,
            action_space=self.action_space,
            native_source_identity=source_identity,
        )
        object.__setattr__(self, "_baseline", baseline)
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="tree_internal_policy_value_oracle_battle_search",
                name=(
                    f"{BATTLE_SEARCH_V2_CONTROLLER_NAME}_{self.ablation}_"
                    f"highest_mean_s{self.simulations}"
                ),
                config={
                    "controller_version": BATTLE_SEARCH_V2_CONTROLLER_VERSION,
                    "task_id": "T062",
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": "native-battle-search-root-v1",
                    "native_search_api": BATTLE_SEARCH_V2_NATIVE_API,
                    "native_search_patch_identity": BATTLE_SEARCH_V2_PATCH_IDENTITY,
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_tree_search_playouts",
                    },
                    "root_selection_rule": self.root_selection_rule,
                    "action_space": self.action_space.to_dict(),
                    "ablation": self.ablation,
                    "tree_internal_guidance": {
                        "policy_prior": self.uses_policy_prior,
                        "policy_prior_scope": "every_expanded_player_decision_node",
                        "learned_leaf_value": self.uses_leaf_value,
                        "learned_leaf_value_boundary": (
                            "after_first_action_from_newly_expanded_node"
                        ),
                        "root_only_or_post_search_fallback": False,
                    },
                    "guidance_scorer": {
                        "name": self.scorer.name,
                        "checkpoint_provenance": checkpoint.to_dict(),
                    },
                },
            ),
        )

    @property
    def uses_policy_prior(self) -> bool:
        return self.ablation in {"prior_only", "prior_value"}

    @property
    def uses_leaf_value(self) -> bool:
        return self.ablation in {"value_only", "prior_value"}

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        if self.ablation == "baseline":
            return self._baseline.select_action(
                adapter, snapshot, actions, context, step_index
            )
        if not hasattr(adapter, "battle_search_v2"):
            raise ValueError(
                "battle search v2 controller requires battle_search_v2 adapter"
            )

        total_start = time.perf_counter()
        callback_counts = {"policy": 0, "value": 0}

        def policy_callback(
            raw: Mapping[str, Any], native_actions: Sequence[Mapping[str, Any]]
        ) -> list[float]:
            node_context = _node_context(
                raw, native_actions, self.action_space, context
            )
            result = self.scorer.score_decision_context(node_context)
            validate_search_guidance_result(
                result,
                context=node_context,
                expected_checkpoint=self.checkpoint_provenance,
            )
            callback_counts["policy"] += 1
            return [float(score.policy_probability) for score in result.action_scores]

        def value_callback(
            raw: Mapping[str, Any], native_actions: Sequence[Mapping[str, Any]]
        ) -> float:
            node_context = _node_context(
                raw, native_actions, self.action_space, context
            )
            result = self.scorer.score_decision_context(node_context)
            validate_search_guidance_result(
                result,
                context=node_context,
                expected_checkpoint=self.checkpoint_provenance,
            )
            prediction = result.value_prediction
            value = (
                None if prediction is None else prediction.battle_survival_probability
            )
            if value is None or not math.isfinite(float(value)):
                raise ValueError("checkpoint has no finite battle-survival value head")
            callback_counts["value"] += 1
            return float(value)

        search_start = time.perf_counter()
        raw_search = getattr(adapter, "battle_search_v2")(
            snapshot,
            simulations=self.simulations,
            include_potions=False,
            policy_prior_callback=policy_callback if self.uses_policy_prior else None,
            leaf_value_callback=value_callback if self.uses_leaf_value else None,
        )
        search_elapsed = time.perf_counter() - search_start
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            expected_native_api=BATTLE_SEARCH_V2_NATIVE_API,
            expected_patch_identity=BATTLE_SEARCH_V2_PATCH_IDENTITY,
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "battle search v2 root mapping failed: " + "; ".join(report.problems)
            )
        telemetry = _require_tree_internal_telemetry(raw_search)
        _validate_mechanism_telemetry(
            telemetry,
            use_policy_prior=self.uses_policy_prior,
            use_leaf_value=self.uses_leaf_value,
            callbacks=callback_counts,
        )
        target = select_oracle_root_action(
            report, selection_rule=self.root_selection_rule
        )
        metadata = oracle_search_controller_metadata(report, target)
        metadata.update(
            {
                "battle_search_v2": {
                    "ablation": self.ablation,
                    "tree_internal_telemetry": telemetry,
                    "python_callback_counts": callback_counts,
                    "total_wall_clock_time_s": time.perf_counter() - total_start,
                    "checkpoint_provenance": self.checkpoint_provenance.to_dict(),
                }
            }
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"battle_search_v2:{self.ablation}:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def _node_context(
    raw: Mapping[str, Any],
    native_actions: Sequence[Mapping[str, Any]],
    action_space: ActionSpaceConfig,
    root_context: DecisionContext,
) -> DecisionContext:
    actions: list[SimulatorAction] = []
    for index, native in enumerate(native_actions):
        scope = native.get("scope")
        bits = native.get("bits")
        kind = native.get("kind")
        if (
            not isinstance(scope, str)
            or not isinstance(bits, int)
            or not isinstance(kind, str)
        ):
            raise ValueError(f"native node action {index} is malformed")
        actions.append(
            SimulatorAction(
                action_id=f"{scope}:{bits}",
                label=str(native.get("label", "")),
                kind=kind,
                raw={
                    "scope": scope,
                    "bits": bits,
                    "idx1": native.get("idx1"),
                    "idx2": native.get("idx2"),
                    "idx3": native.get("idx3"),
                },
            )
        )
    if not actions:
        raise ValueError("native tree node exposed no legal actions")
    return build_decision_context(
        raw,
        actions,
        action_space,
        public_run_context=root_context.public_run_context,
    )


def _require_tree_internal_telemetry(raw_search: Mapping[str, Any]) -> dict[str, Any]:
    telemetry = raw_search.get("tree_internal_telemetry")
    if not isinstance(telemetry, Mapping):
        raise ValueError("native battle search v2 omitted tree-internal telemetry")
    return dict(telemetry)


def _validate_mechanism_telemetry(
    telemetry: Mapping[str, Any],
    *,
    use_policy_prior: bool,
    use_leaf_value: bool,
    callbacks: Mapping[str, int],
) -> None:
    expected_scope = (
        "every_expanded_player_decision_node" if use_policy_prior else "disabled"
    )
    expected_boundary = (
        "after_first_action_from_newly_expanded_node" if use_leaf_value else "disabled"
    )
    if telemetry.get("policy_prior_scope") != expected_scope:
        raise ValueError("native battle search v2 policy-prior scope mismatch")
    if telemetry.get("leaf_value_boundary") != expected_boundary:
        raise ValueError("native battle search v2 leaf-value boundary mismatch")
    for telemetry_field, enabled, callback_key in (
        ("policy_prior_calls", use_policy_prior, "policy"),
        ("leaf_value_calls", use_leaf_value, "value"),
    ):
        value = telemetry.get(telemetry_field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"native battle search v2 {telemetry_field} is invalid")
        if enabled and (value <= 0 or callbacks[callback_key] != value):
            raise ValueError(
                f"native battle search v2 did not exercise {telemetry_field}"
            )
        if not enabled and value != 0:
            raise ValueError(
                f"native battle search v2 unexpectedly used {telemetry_field}"
            )
