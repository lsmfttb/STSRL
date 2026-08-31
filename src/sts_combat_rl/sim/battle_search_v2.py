"""T062 tree-internal policy/value Oracle-like battle search controller."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import time
from typing import Any, Callable, Literal

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
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)
from sts_combat_rl.sim.search_cost import (
    PublicNodeInferenceCache,
    T067_COST_ATTRIBUTION_SCHEMA_ID,
    T067_COST_ATTRIBUTION_SCHEMA_VERSION,
    T067_REPAIR_IDENTITY,
    public_node_cache_key,
)
from sts_combat_rl.sim.public_context_feature_projection import (
    T069_PROJECTION_IMPLEMENTATION_ID,
)
from sts_combat_rl.sim.t079_state_utilization import validate_occurrence_rows


BATTLE_SEARCH_V2_CONTROLLER_NAME = "battle_search_v2_oracle_like_v1"
BATTLE_SEARCH_V2_CONTROLLER_VERSION = "battle-search-v2-oracle-like-v1"
BATTLE_SEARCH_V2_T067_CONTROLLER_NAME = "battle_search_v2_oracle_like_t067_cache_v1"
BATTLE_SEARCH_V2_T067_CONTROLLER_VERSION = "battle-search-v2-oracle-like-t067-cache-v1"
BATTLE_SEARCH_V2_T069_CONTROLLER_NAME = (
    "battle_search_v2_oracle_like_t069_public_context_projection_v1"
)
BATTLE_SEARCH_V2_T069_CONTROLLER_VERSION = (
    "battle-search-v2-oracle-like-t069-public-context-projection-v1"
)
BATTLE_SEARCH_V2_T070_GEOMETRY_CONTROLLER_NAME = (
    "battle_search_v2_oracle_like_t070_tree_geometry_v1"
)
BATTLE_SEARCH_V2_T070_GEOMETRY_CONTROLLER_VERSION = (
    "battle-search-v2-oracle-like-t070-tree-geometry-v1"
)
BATTLE_SEARCH_V2_T079_STATE_UTILIZATION_CONTROLLER_NAME = (
    "battle_search_v2_oracle_like_t079_state_utilization_v1"
)
BATTLE_SEARCH_V2_T079_STATE_UTILIZATION_CONTROLLER_VERSION = (
    "battle-search-v2-oracle-like-t079-state-utilization-v1"
)
T070_TREE_GEOMETRY_SCHEMA_ID = "native-battle-search-v2-tree-geometry-v1"
T079_STATE_UTILIZATION_SCHEMA_ID = "native-battle-search-v2-state-utilization-v1"
T079_IDENTITY_SEMANTICS = (
    "all future-dynamics BattleContext values including curCardQueueItem, "
    "ordered card/pile state, all combat RNG state, and collision-checked canonical equality"
)
T079_IDENTITY_COMPONENTS = (
    "BattleContext.scalar_control_flags",
    "BattleContext.all_six_rng_states",
    "BattleContext.potions_and_card_select",
    "Player.all_fields_and_status_map",
    "MonsterGroup.all_fields_and_monster_state",
    "CardManager.all_counters_and_ordered_piles",
    "CardQueue.all_slots_and_indices",
    "BattleContext.curCardQueueItem.all_fields",
    "ActionQueue.indices_size_and_clear_bits",
)
T069_COST_ATTRIBUTION_SCHEMA_ID = "t069-public-context-projection-cost-attribution-v1"
T069_COST_ATTRIBUTION_SCHEMA_VERSION = 1
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
    # T062 remains explicitly constructible with the cache disabled.  T067
    # enables this exact public-node cache on its repaired v2 controller.
    inference_cache_enabled: bool = False
    inference_cache_capacity: int = 4096
    # T069 prepares the complete current-schema public-context vector once per
    # select_action call. The accepted unprojected path remains the default.
    public_context_projection_enabled: bool = False
    # T069 evidence-only input identity observation. The concrete scorer
    # remains unmodified when this default-off switch is false.
    feature_identity_trace_enabled: bool = False
    # T068-only diagnostic instrumentation.  It records the existing
    # synchronous callback boundary; it never changes callback scheduling,
    # scoring, or native traversal.
    callback_dependency_trace_enabled: bool = False
    # T070-only, explicitly requested read-only native telemetry. Primary T070
    # stages leave this disabled so the accepted T069 calibration applies.
    tree_geometry_enabled: bool = False
    # T079-only read-only native exact-state and path-utilization telemetry.
    state_utilization_enabled: bool = False
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
        if self.inference_cache_capacity <= 0:
            raise ValueError(
                "battle search v2 inference cache capacity must be positive"
            )
        if self.tree_geometry_enabled and self.ablation != "prior_value":
            raise ValueError(
                "T070 tree geometry is defined only for the prior_value arm"
            )
        if self.state_utilization_enabled and self.ablation != "prior_value":
            raise ValueError(
                "T079 state utilization is defined only for the prior_value arm"
            )
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
        controller_name = (
            BATTLE_SEARCH_V2_T079_STATE_UTILIZATION_CONTROLLER_NAME
            if self.state_utilization_enabled
            else (
                BATTLE_SEARCH_V2_T070_GEOMETRY_CONTROLLER_NAME
                if self.tree_geometry_enabled
                else (
                    BATTLE_SEARCH_V2_T069_CONTROLLER_NAME
                    if self.public_context_projection_enabled
                    else (
                        BATTLE_SEARCH_V2_T067_CONTROLLER_NAME
                        if self.inference_cache_enabled
                        else BATTLE_SEARCH_V2_CONTROLLER_NAME
                    )
                )
            )
        )
        controller_version = (
            BATTLE_SEARCH_V2_T079_STATE_UTILIZATION_CONTROLLER_VERSION
            if self.state_utilization_enabled
            else (
                BATTLE_SEARCH_V2_T070_GEOMETRY_CONTROLLER_VERSION
                if self.tree_geometry_enabled
                else (
                    BATTLE_SEARCH_V2_T069_CONTROLLER_VERSION
                    if self.public_context_projection_enabled
                    else (
                        BATTLE_SEARCH_V2_T067_CONTROLLER_VERSION
                        if self.inference_cache_enabled
                        else BATTLE_SEARCH_V2_CONTROLLER_VERSION
                    )
                )
            )
        )
        provenance_config: dict[str, Any] = {
            "controller_version": controller_version,
            "task_id": (
                "T079"
                if self.state_utilization_enabled
                else (
                    "T070"
                    if self.tree_geometry_enabled
                    else (
                        "T069"
                        if self.public_context_projection_enabled
                        else ("T067" if self.inference_cache_enabled else "T062")
                    )
                )
            ),
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
        }
        if self.public_context_projection_enabled:
            provenance_config["cost_repair"] = {
                "task_id": "T069",
                "repair_identity": T069_PROJECTION_IMPLEMENTATION_ID,
                "projection_scope": "one_native_search_call",
                "complete_canonical_public_context_validation": True,
                "digest_only_reuse": False,
                "accepted_t067_cache_enabled": self.inference_cache_enabled,
                "inference_cache_capacity": (
                    self.inference_cache_capacity if self.inference_cache_enabled else 0
                ),
            }
        elif self.inference_cache_enabled:
            provenance_config["cost_repair"] = {
                "task_id": "T067",
                "repair_identity": T067_REPAIR_IDENTITY,
                "inference_cache_enabled": True,
                "inference_cache_capacity": self.inference_cache_capacity,
                "cache_scope": "one_native_search_call",
                "cache_key_schema_id": "t067-public-node-cache-key-v1",
            }
        if self.tree_geometry_enabled:
            provenance_config["tree_geometry"] = {
                "task_id": "T070",
                "enabled": True,
                "native_api": "StepSimulator.battle_search_v2_with_tree_geometry",
                "schema_id": T070_TREE_GEOMETRY_SCHEMA_ID,
                "semantic_effect": "read_only_post_search_aggregation",
            }
        if self.state_utilization_enabled:
            provenance_config["state_utilization"] = {
                "task_id": "T079",
                "enabled": True,
                "native_api": ("StepSimulator.battle_search_v2_with_state_utilization"),
                "schema_id": T079_STATE_UTILIZATION_SCHEMA_ID,
                "identity_regime": "full_simulator_state_oracle_like",
                "semantic_effect": "read_only_observation_only",
                "transposition_or_merge": False,
            }
        if self.feature_identity_trace_enabled:
            provenance_config["diagnostic_instrumentation"] = {
                "task_id": "T069",
                "feature_identity_trace": True,
                "semantic_effect": "observation_only",
            }
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="tree_internal_policy_value_oracle_battle_search",
                name=(
                    f"{controller_name}_{self.ablation}_"
                    f"highest_mean_s{self.simulations}"
                ),
                config=provenance_config,
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
        callback_trace: list[dict[str, Any]] = []
        callback_sequence = 0
        inference_cache = (
            PublicNodeInferenceCache(self.inference_cache_capacity)
            if self.inference_cache_enabled
            else None
        )
        attribution = {
            "node_context_projection_ms": 0.0,
            "checkpoint_feature_encoding_ms": 0.0,
            "tensor_construction_ms": 0.0,
            "policy_value_forward_pass_ms": 0.0,
            "inference_result_postprocess_ms": 0.0,
            "scorer_invocation_ms": 0.0,
            "python_native_callback_overhead_ms": 0.0,
            "python_callback_total_ms": 0.0,
            "cache_lookup_ms": 0.0,
            "model_call_count": 0.0,
            "public_context_projection_construction_ms": 0.0,
            "public_context_projection_canonicalization_ms": 0.0,
            "public_context_projection_validation_encoding_ms": 0.0,
            "public_context_projection_validation_ms": 0.0,
            "projected_state_vector_assembly_ms": 0.0,
            "snapshot_action_schema_validation_ms": 0.0,
            "public_context_schema_validation_encoding_ms": 0.0,
            "public_context_feature_encoding_ms": 0.0,
            "state_tensor_construction_ms": 0.0,
            "legal_action_tensor_construction_ms": 0.0,
            "public_context_projection_construction_count": 0.0,
            "public_context_projection_reuse_count": 0.0,
        }
        public_context_projection: Any | None = None
        score_context: Callable[[DecisionContext], SearchGuidanceInferenceResult] = (
            self.scorer.score_decision_context
        )
        if self.feature_identity_trace_enabled:
            begin_scope = getattr(self.scorer, "begin_search_scope", None)
            end_scope = getattr(self.scorer, "end_search_scope", None)
            if not callable(begin_scope) or not callable(end_scope):
                raise ValueError(
                    "T069 feature identity trace requires an observer-aware scorer"
                )
            begin_scope(context.public_run_context)
        if self.public_context_projection_enabled:
            prepare = getattr(
                self.scorer,
                "prepare_public_context_projection",
                None,
            )
            score_projected = getattr(
                self.scorer,
                "score_decision_context_with_projection",
                None,
            )
            if not callable(prepare) or not callable(score_projected):
                raise ValueError(
                    "T069 projection requires an explicit projection-aware scorer"
                )
            public_context_projection = prepare(context.public_run_context)
            projection_telemetry = public_context_projection.telemetry()
            attribution["public_context_projection_construction_ms"] = float(
                projection_telemetry["construction_ms"]
            )
            attribution["public_context_projection_canonicalization_ms"] = float(
                projection_telemetry["canonicalization_ms"]
            )
            attribution["public_context_projection_validation_encoding_ms"] = float(
                projection_telemetry["validation_encoding_ms"]
            )
            attribution["public_context_projection_construction_count"] = 1.0

            def score_context(
                node_context: DecisionContext,
            ) -> SearchGuidanceInferenceResult:
                return score_projected(node_context, public_context_projection)

        def policy_callback(
            raw: Mapping[str, Any], native_actions: Sequence[Mapping[str, Any]]
        ) -> list[float]:
            nonlocal callback_sequence
            callback_started = time.perf_counter()
            projection_started = time.perf_counter()
            node_context = _node_context(
                raw, native_actions, self.action_space, context
            )
            trace_entry = _begin_callback_trace(
                enabled=self.callback_dependency_trace_enabled,
                trace=callback_trace,
                sequence=callback_sequence,
                callback_kind="policy",
                node_context=node_context,
                required_outputs=("policy_probabilities",),
            )
            callback_sequence += 1
            attribution["node_context_projection_ms"] += (
                time.perf_counter() - projection_started
            ) * 1000.0
            result, cache_hit, lookup_ms, scorer_time_ms = _score_node_context(
                node_context, score_context, inference_cache
            )
            attribution["cache_lookup_ms"] += lookup_ms
            attribution["scorer_invocation_ms"] += scorer_time_ms
            validate_search_guidance_result(
                result,
                context=node_context,
                expected_checkpoint=self.checkpoint_provenance,
            )
            if not cache_hit:
                # Policy and value callbacks may share one exact-node cache
                # entry; count scorer invocations rather than callbacks.
                attribution["model_call_count"] += 1.0
                if self.public_context_projection_enabled:
                    attribution["public_context_projection_reuse_count"] += 1.0
                _add_inference_timing(attribution, result)
            callback_counts["policy"] += 1
            native_result = [
                float(score.policy_probability) for score in result.action_scores
            ]
            _finish_callback_trace(trace_entry, callback_started)
            _finish_callback_timing(attribution, callback_started)
            return native_result

        def value_callback(
            raw: Mapping[str, Any], native_actions: Sequence[Mapping[str, Any]]
        ) -> float:
            nonlocal callback_sequence
            callback_started = time.perf_counter()
            projection_started = time.perf_counter()
            node_context = _node_context(
                raw, native_actions, self.action_space, context
            )
            trace_entry = _begin_callback_trace(
                enabled=self.callback_dependency_trace_enabled,
                trace=callback_trace,
                sequence=callback_sequence,
                callback_kind="value",
                node_context=node_context,
                required_outputs=("battle_survival_probability",),
            )
            callback_sequence += 1
            attribution["node_context_projection_ms"] += (
                time.perf_counter() - projection_started
            ) * 1000.0
            result, cache_hit, lookup_ms, scorer_time_ms = _score_node_context(
                node_context, score_context, inference_cache
            )
            attribution["cache_lookup_ms"] += lookup_ms
            attribution["scorer_invocation_ms"] += scorer_time_ms
            validate_search_guidance_result(
                result,
                context=node_context,
                expected_checkpoint=self.checkpoint_provenance,
            )
            if not cache_hit:
                attribution["model_call_count"] += 1.0
                if self.public_context_projection_enabled:
                    attribution["public_context_projection_reuse_count"] += 1.0
                _add_inference_timing(attribution, result)
            prediction = result.value_prediction
            value = (
                None if prediction is None else prediction.battle_survival_probability
            )
            if value is None or not math.isfinite(float(value)):
                raise ValueError("checkpoint has no finite battle-survival value head")
            callback_counts["value"] += 1
            native_result = float(value)
            _finish_callback_trace(trace_entry, callback_started)
            _finish_callback_timing(attribution, callback_started)
            return native_result

        search_start = time.perf_counter()
        method_name = (
            "battle_search_v2_with_state_utilization"
            if self.state_utilization_enabled
            else (
                "battle_search_v2_with_tree_geometry"
                if self.tree_geometry_enabled
                else "battle_search_v2"
            )
        )
        if not hasattr(adapter, method_name):
            raise ValueError(
                f"battle search v2 controller requires {method_name} adapter"
            )
        raw_search = getattr(adapter, method_name)(
            snapshot,
            simulations=self.simulations,
            include_potions=False,
            policy_prior_callback=policy_callback if self.uses_policy_prior else None,
            leaf_value_callback=value_callback if self.uses_leaf_value else None,
        )
        if self.feature_identity_trace_enabled:
            end_scope = getattr(self.scorer, "end_search_scope")
            end_scope()
        search_elapsed = time.perf_counter() - search_start
        attribution["python_native_callback_overhead_ms"] = max(
            0.0,
            attribution["python_callback_total_ms"]
            - attribution["node_context_projection_ms"]
            - attribution["scorer_invocation_ms"]
            - attribution["cache_lookup_ms"]
            - (
                inference_cache.eviction_time_ms if inference_cache is not None else 0.0
            ),
        )
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            expected_native_api=(
                "StepSimulator.battle_search_v2_with_state_utilization.v1"
                if self.state_utilization_enabled
                else BATTLE_SEARCH_V2_NATIVE_API
            ),
            expected_patch_identity=(
                "sts_lightspeed_battle_search_v2_state_utilization_v1"
                if self.state_utilization_enabled
                else BATTLE_SEARCH_V2_PATCH_IDENTITY
            ),
            wall_clock_time_s=search_elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "battle search v2 root mapping failed: " + "; ".join(report.problems)
            )
        telemetry = _require_tree_internal_telemetry(raw_search)
        geometry: dict[str, Any] | None = None
        state_utilization: dict[str, Any] | None = None
        if self.state_utilization_enabled:
            state_utilization = _validate_t079_state_utilization(raw_search, telemetry)
            geometry = _validate_t070_tree_geometry(raw_search, telemetry)
        elif self.tree_geometry_enabled:
            geometry = _validate_t070_tree_geometry(raw_search, telemetry)
        elif "tree_geometry" in telemetry:
            raise ValueError(
                "native battle_search_v2 unexpectedly returned tree geometry"
            )
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
                    "cost_attribution": {
                        "schema_id": (
                            T069_COST_ATTRIBUTION_SCHEMA_ID
                            if self.public_context_projection_enabled
                            else T067_COST_ATTRIBUTION_SCHEMA_ID
                        ),
                        "schema_version": (
                            T069_COST_ATTRIBUTION_SCHEMA_VERSION
                            if self.public_context_projection_enabled
                            else T067_COST_ATTRIBUTION_SCHEMA_VERSION
                        ),
                        "native_tree_search_excluding_python_callbacks_ms": max(
                            0.0,
                            search_elapsed * 1000.0
                            - attribution["python_callback_total_ms"],
                        ),
                        **attribution,
                        **(
                            inference_cache.telemetry()
                            if inference_cache is not None
                            else {
                                "cache_capacity": 0.0,
                                "cache_lookup_count": 0.0,
                                "cache_hit_count": 0.0,
                                "cache_miss_count": 0.0,
                                "cache_uncacheable_count": 0.0,
                                "cache_eviction_count": 0.0,
                                "cache_eviction_ms": 0.0,
                                "cache_entry_count": 0.0,
                            }
                        ),
                        "policy_callback_count": float(callback_counts["policy"]),
                        "value_callback_count": float(callback_counts["value"]),
                        "model_call_count": attribution["model_call_count"],
                    },
                    **(
                        {
                            "public_context_projection": (
                                public_context_projection.telemetry()
                            )
                        }
                        if public_context_projection is not None
                        else {}
                    ),
                }
            }
        )
        # Fixed-evaluation aggregation intentionally sums immediate numeric
        # mapping values.  Keep this flattened mirror for durable report
        # aggregation while the nested record above remains human-readable.
        flat_cost = metadata["battle_search_v2"]["cost_attribution"]
        metadata["t067_cost_attribution"] = {
            key: value
            for key, value in flat_cost.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if self.public_context_projection_enabled:
            metadata["t069_cost_attribution"] = dict(metadata["t067_cost_attribution"])
        if self.callback_dependency_trace_enabled:
            # Fixed-battle evaluation only recursively merges numeric mapping
            # telemetry.  Keep this diagnostic payload as a top-level sequence
            # so its exact request order survives that existing aggregation.
            metadata["t068_callback_dependency_trace_records"] = [
                {
                    "schema_id": "t068-native-callback-request-trace-v1",
                    "schema_version": 1,
                    "trace_mode": "observe_existing_synchronous_callback",
                    "requests": callback_trace,
                }
            ]
        if geometry is not None:
            metadata["t070_tree_geometry_records"] = [
                {
                    "schema_id": "t070-search-tree-geometry-decision-v1",
                    "schema_version": 1,
                    "search_call_identity": {
                        "schema_id": "t070-search-call-identity-v1",
                        "controller_identity": self.provenance.identity,
                        "decision_step_index": step_index,
                    },
                    "decision_step_index": step_index,
                    "native_geometry": geometry,
                    "root_actions": [
                        action.to_dict() for action in report.root_actions
                    ],
                    "root_visits": report.root_visits,
                    "root_legal_action_count": report.legal_action_count,
                    "selected_action_identity": dict(target.action_identity),
                    "selected_legal_action_index": target.legal_action_index,
                    "native_simulator_steps": report.native_simulator_steps,
                    "model_calls": int(attribution["model_call_count"]),
                    "wall_clock_seconds": search_elapsed,
                    "search_status": "completed",
                    "search_failure_count": len(report.problems),
                }
            ]
        if state_utilization is not None:
            metadata["t079_state_utilization_records"] = [
                {
                    "schema_id": "t079-search-state-utilization-decision-v1",
                    "schema_version": 1,
                    "search_call_identity": {
                        "schema_id": "t079-search-call-identity-v1",
                        "controller_identity": self.provenance.identity,
                        "decision_step_index": step_index,
                    },
                    "decision_step_index": step_index,
                    "native_state_utilization": state_utilization,
                    "native_geometry": geometry,
                    "root_actions": [
                        action.to_dict() for action in report.root_actions
                    ],
                    "root_visits": report.root_visits,
                    "root_legal_action_count": report.legal_action_count,
                    "native_simulator_steps": report.native_simulator_steps,
                    "model_calls": int(attribution["model_call_count"]),
                    "wall_clock_seconds": search_elapsed,
                    "selected_action_identity": dict(target.action_identity),
                    "selected_legal_action_index": target.legal_action_index,
                    "search_status": "completed",
                    "search_failure_count": len(report.problems),
                }
            ]
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"battle_search_v2:{self.ablation}:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def _score_node_context(
    node_context: DecisionContext,
    scorer: Callable[[DecisionContext], SearchGuidanceInferenceResult],
    inference_cache: PublicNodeInferenceCache | None,
) -> tuple[SearchGuidanceInferenceResult, bool, float, float]:
    if inference_cache is None:
        started = time.perf_counter()
        result = scorer(node_context)
        return result, False, 0.0, (time.perf_counter() - started) * 1000.0
    scored = inference_cache.score(node_context, scorer)
    return (
        scored.result,
        scored.cache_hit,
        scored.cache_lookup_ms,
        scored.scorer_time_ms,
    )


def _add_inference_timing(
    attribution: dict[str, float],
    result: SearchGuidanceInferenceResult,
) -> None:
    timing = result.timing_ms
    attribution["checkpoint_feature_encoding_ms"] += _timing_value(
        timing, "feature_encoding_ms"
    )
    attribution["tensor_construction_ms"] += _timing_value(
        timing, "tensor_construction_ms"
    )
    attribution["policy_value_forward_pass_ms"] += _timing_value(
        timing, "model_forward_ms"
    )
    attribution["inference_result_postprocess_ms"] += _timing_value(
        timing, "result_postprocess_ms"
    )
    attribution["public_context_projection_validation_ms"] += _timing_value(
        timing, "public_context_projection_validation_ms"
    )
    attribution["projected_state_vector_assembly_ms"] += _timing_value(
        timing, "state_vector_assembly_ms"
    )
    attribution["snapshot_action_schema_validation_ms"] += _timing_value(
        timing, "snapshot_action_schema_validation_ms"
    )
    attribution["public_context_schema_validation_encoding_ms"] += _timing_value(
        timing, "public_context_schema_validation_encoding_ms"
    )
    attribution["public_context_feature_encoding_ms"] += _timing_value(
        timing, "public_context_feature_encoding_ms"
    )
    attribution["state_tensor_construction_ms"] += _timing_value(
        timing, "state_tensor_construction_ms"
    )
    attribution["legal_action_tensor_construction_ms"] += _timing_value(
        timing, "legal_action_tensor_construction_ms"
    )
    attribution["t069_input_identity_observer_ms"] = attribution.get(
        "t069_input_identity_observer_ms", 0.0
    ) + _timing_value(timing, "t069_input_identity_observer_ms")


def _timing_value(timing: Mapping[str, float], key: str) -> float:
    value = timing.get(key, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def _finish_callback_timing(
    attribution: dict[str, float],
    callback_started: float,
) -> None:
    total_ms = (time.perf_counter() - callback_started) * 1000.0
    attribution["python_callback_total_ms"] += total_ms


def _begin_callback_trace(
    *,
    enabled: bool,
    trace: list[dict[str, Any]],
    sequence: int,
    callback_kind: str,
    node_context: DecisionContext,
    required_outputs: tuple[str, ...],
) -> dict[str, Any] | None:
    """Record one exact T068 request without exposing simulator-only state.

    Pybind invokes these callbacks synchronously: native code cannot issue the
    next callback until this function returns its response.  The trace records
    that runtime boundary explicitly; the T068 report combines it with the
    pinned native-source audit before deciding whether a batch is legal.
    """

    if not enabled:
        return None
    cache_key = public_node_cache_key(node_context)
    action_identities: list[dict[str, Any]] = []
    for action in node_context.tactical_legal_actions:
        identity = action.get("identity") if isinstance(action, Mapping) else None
        if not isinstance(identity, Mapping):
            raise ValueError("T068 callback trace requires legal action identities")
        action_identities.append(dict(identity))
    if cache_key is None:
        raise ValueError(
            "T068 callback trace requires the complete canonical public-node identity"
        )
    input_identity = cache_key[0]
    entry = {
        "request_id": f"request-{sequence:06d}",
        "request_sequence": sequence,
        "callback_kind": callback_kind,
        "required_outputs": list(required_outputs),
        "public_input_identity": input_identity,
        "public_input_identity_schema_id": "t067-public-node-cache-key-v1",
        "public_input_canonical_byte_count": len(cache_key[1]),
        "ordered_legal_action_identities": action_identities,
        "native_traversal_point": (
            "policy_prior_apply" if callback_kind == "policy" else "leaf_value_backup"
        ),
        "earliest_result_consumer": (
            "native callback return boundary before subsequent native traversal"
        ),
        "dependency_edges": [
            "request_ready -> python_callback_response",
            "python_callback_response -> immediate_native_consumer",
            "immediate_native_consumer -> next_native_traversal_or_request",
        ],
        "simultaneously_ready_batch_size": 1,
        "flush_reason": "native callback requires this response before traversal continues",
        "response_count": 0,
        "response_order_exact": True,
    }
    trace.append(entry)
    return entry


def _finish_callback_trace(entry: dict[str, Any] | None, started: float) -> None:
    if entry is None:
        return
    entry["response_count"] = 1
    entry["callback_elapsed_ms"] = (time.perf_counter() - started) * 1000.0


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


def _validate_t070_tree_geometry(
    raw_search: Mapping[str, Any],
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    geometry = telemetry.get("tree_geometry")
    if not isinstance(geometry, Mapping):
        raise ValueError("native battle search v2 omitted T070 tree geometry")
    value = dict(geometry)
    expected_keys = {
        "schema_id",
        "schema_version",
        "root_depth",
        "total_expanded_node_count",
        "total_discovered_child_edge_count",
        "total_visited_child_edge_count",
        "max_expanded_depth",
        "depth_rows",
    }
    if set(value) != expected_keys:
        raise ValueError("native battle search v2 tree geometry fields mismatch")
    if (
        value.get("schema_id") != T070_TREE_GEOMETRY_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("root_depth") != 0
    ):
        raise ValueError("native battle search v2 tree geometry identity mismatch")
    rows = value.get("depth_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("native battle search v2 tree geometry rows are invalid")
    expanded_total = 0
    discovered_total = 0
    visited_total = 0
    normalized_rows: list[dict[str, Any]] = []
    for expected_depth, raw_row in enumerate(rows):
        if not isinstance(raw_row, Mapping):
            raise ValueError("native tree geometry row must be an object")
        row = dict(raw_row)
        if row.get("depth") != expected_depth:
            raise ValueError("native tree geometry depths must be contiguous")
        counts: dict[str, int] = {}
        for key in (
            "expanded_node_count",
            "discovered_child_edge_count",
            "visited_child_edge_count",
        ):
            count = row.get(key)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"native tree geometry {key} is invalid")
            counts[key] = count
        if counts["visited_child_edge_count"] > counts["discovered_child_edge_count"]:
            raise ValueError("native tree geometry visited edges exceed discovered")
        histogram = row.get("branching_histogram")
        if not isinstance(histogram, Sequence) or isinstance(histogram, (str, bytes)):
            raise ValueError("native tree geometry branching histogram is invalid")
        previous = -1
        histogram_nodes = 0
        histogram_edges = 0
        for bucket in histogram:
            if not isinstance(bucket, Mapping):
                raise ValueError("native tree geometry histogram bucket is invalid")
            child_count = bucket.get("child_count")
            node_count = bucket.get("node_count")
            if (
                isinstance(child_count, bool)
                or not isinstance(child_count, int)
                or child_count < 0
                or isinstance(node_count, bool)
                or not isinstance(node_count, int)
                or node_count < 0
                or child_count <= previous
            ):
                raise ValueError("native tree geometry histogram is not canonical")
            previous = child_count
            histogram_nodes += node_count
            histogram_edges += child_count * node_count
        if (
            histogram_nodes != counts["expanded_node_count"]
            or histogram_edges != counts["discovered_child_edge_count"]
        ):
            raise ValueError("native tree geometry histogram totals mismatch")
        expanded_total += counts["expanded_node_count"]
        discovered_total += counts["discovered_child_edge_count"]
        visited_total += counts["visited_child_edge_count"]
        normalized_rows.append(row)
    totals = (
        ("total_expanded_node_count", expanded_total),
        ("total_discovered_child_edge_count", discovered_total),
        ("total_visited_child_edge_count", visited_total),
    )
    for key, expected in totals:
        if value.get(key) != expected:
            raise ValueError(f"native tree geometry {key} mismatch")
    if expanded_total != telemetry.get("expanded_nodes"):
        raise ValueError("native tree geometry expanded-node parity failed")
    expected_max = -1 if not normalized_rows else len(normalized_rows) - 1
    if value.get("max_expanded_depth") != expected_max:
        raise ValueError("native tree geometry maximum depth mismatch")
    if normalized_rows and normalized_rows[0][
        "discovered_child_edge_count"
    ] != raw_search.get("search_edge_count"):
        raise ValueError("native tree geometry root edge count mismatch")
    return value


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
        # A newly expanded node can terminate immediately after its first
        # action.  That terminal has no legal player-action mapping for the
        # public checkpoint, so native search correctly backs up the terminal
        # result without a learned-value call.  Require exact accounting, but
        # do not turn that valid terminal boundary into a controller failure.
        if enabled and callbacks[callback_key] != value:
            raise ValueError(
                f"native battle search v2 callback accounting failed for "
                f"{telemetry_field}"
            )
        if not enabled and value != 0:
            raise ValueError(
                f"native battle search v2 unexpectedly used {telemetry_field}"
            )


def _validate_t079_state_utilization(
    raw_search: Mapping[str, Any], telemetry: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate T079 native identity completeness and occurrence evidence."""

    value = telemetry.get("state_utilization")
    if not isinstance(value, Mapping):
        raise ValueError("native battle search v2 omitted T079 state utilization")
    expected = {
        "schema_id",
        "schema_version",
        "identity_schema_id",
        "identity_semantics",
        "identity_components",
        "identity_complete",
        "identity_unavailable_reason",
        "digest_algorithm",
        "digest_collision_count",
        "collision_check",
        "expanded_path_node_count",
        "expanded_states",
    }
    if set(value) != expected:
        if "identity_components" not in value:
            raise ValueError("native T079 identity component audit is missing")
        raise ValueError("native T079 state-utilization fields mismatch")
    if (
        value.get("schema_id") != T079_STATE_UTILIZATION_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("identity_schema_id") != "native-battle-search-v2-exact-state-v1"
        or value.get("identity_semantics") != T079_IDENTITY_SEMANTICS
        or value.get("identity_complete") is not True
        or value.get("collision_check")
        != "canonical_payload_equality_within_digest_bucket"
        or value.get("digest_collision_count") != 0
    ):
        raise ValueError("native T079 exact-state identity is incomplete or collided")
    components = value.get("identity_components")
    if (
        not isinstance(components, list)
        or tuple(components) != T079_IDENTITY_COMPONENTS
    ):
        raise ValueError("native T079 identity component audit is incomplete")
    rows = value.get("expanded_states")
    count = value.get("expanded_path_node_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("native T079 expanded path-node count is invalid")
    if (
        not isinstance(rows, Sequence)
        or isinstance(rows, (str, bytes))
        or len(rows) != count
    ):
        raise ValueError("native T079 expanded-state rows do not cover every node")
    normalized = validate_occurrence_rows(rows, count=count)
    seen = {row["exact_state_digest"] for row in normalized}
    result = dict(value)
    result["expanded_states"] = normalized
    result["unique_exact_state_count"] = len(seen)
    result["exact_duplicate_path_node_count"] = count - len(seen)
    return result
