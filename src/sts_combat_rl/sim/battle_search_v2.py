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
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)
from sts_combat_rl.sim.battle_search_v2_cost import (
    PublicNodeInferenceCache,
    T067_COST_ATTRIBUTION_SCHEMA_ID,
    T067_COST_ATTRIBUTION_SCHEMA_VERSION,
    T067_REPAIR_IDENTITY,
    public_node_cache_key,
)


BATTLE_SEARCH_V2_CONTROLLER_NAME = "battle_search_v2_oracle_like_v1"
BATTLE_SEARCH_V2_CONTROLLER_VERSION = "battle-search-v2-oracle-like-v1"
BATTLE_SEARCH_V2_T067_CONTROLLER_NAME = "battle_search_v2_oracle_like_t067_cache_v1"
BATTLE_SEARCH_V2_T067_CONTROLLER_VERSION = "battle-search-v2-oracle-like-t067-cache-v1"
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
    # T068-only diagnostic instrumentation.  It records the existing
    # synchronous callback boundary; it never changes callback scheduling,
    # scoring, or native traversal.
    callback_dependency_trace_enabled: bool = False
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
            BATTLE_SEARCH_V2_T067_CONTROLLER_NAME
            if self.inference_cache_enabled
            else BATTLE_SEARCH_V2_CONTROLLER_NAME
        )
        provenance_config: dict[str, Any] = {
            "controller_version": (
                BATTLE_SEARCH_V2_T067_CONTROLLER_VERSION
                if self.inference_cache_enabled
                else BATTLE_SEARCH_V2_CONTROLLER_VERSION
            ),
            "task_id": "T067" if self.inference_cache_enabled else "T062",
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
        if self.inference_cache_enabled:
            provenance_config["cost_repair"] = {
                "task_id": "T067",
                "repair_identity": T067_REPAIR_IDENTITY,
                "inference_cache_enabled": True,
                "inference_cache_capacity": self.inference_cache_capacity,
                "cache_scope": "one_native_search_call",
                "cache_key_schema_id": "t067-public-node-cache-key-v1",
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
        }

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
                node_context, self.scorer, inference_cache
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
                node_context, self.scorer, inference_cache
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
        raw_search = getattr(adapter, "battle_search_v2")(
            snapshot,
            simulations=self.simulations,
            include_potions=False,
            policy_prior_callback=policy_callback if self.uses_policy_prior else None,
            leaf_value_callback=value_callback if self.uses_leaf_value else None,
        )
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
                    "cost_attribution": {
                        "schema_id": T067_COST_ATTRIBUTION_SCHEMA_ID,
                        "schema_version": T067_COST_ATTRIBUTION_SCHEMA_VERSION,
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
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"battle_search_v2:{self.ablation}:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def _score_node_context(
    node_context: DecisionContext,
    scorer: SearchGuidanceScorer,
    inference_cache: PublicNodeInferenceCache | None,
) -> tuple[SearchGuidanceInferenceResult, bool, float, float]:
    if inference_cache is None:
        started = time.perf_counter()
        result = scorer.score_decision_context(node_context)
        return result, False, 0.0, (time.perf_counter() - started) * 1000.0
    scored = inference_cache.score(node_context, scorer.score_decision_context)
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
        "public_input_canonical_bytes": len(cache_key[1]),
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
