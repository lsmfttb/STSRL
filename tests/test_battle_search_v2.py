from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import pytest

from sts_combat_rl.sim.battle_search_v2 import (
    BATTLE_SEARCH_V2_NATIVE_API,
    BATTLE_SEARCH_V2_PATCH_IDENTITY,
    T079_IDENTITY_COMPONENTS,
    T079_IDENTITY_SEMANTICS,
    BattleSearchV2Controller,
    _validate_t079_state_utilization,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
)
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND,
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceValuePrediction,
)
from sts_combat_rl.sim.t079_state_utilization import (
    T079_ACTIVE_QUEUE_NORMALIZATION_PROOF,
)


def _checkpoint() -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id="unit-test-checkpoint",
        checkpoint_path="/tmp/unit-test.pt",
        model_class="TinyPolicyValueNet",
        model_config={"hidden_size": 8},
        trainer_input_artifact_id="trainer-input-sha256:abc",
        trainer_input_sha256="abc",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="oracle_teacher_row.teacher_action",
    )


def test_value_prediction_preserves_legacy_positional_field_order() -> None:
    prediction = SearchGuidanceValuePrediction(
        0.5,
        42.0,
        {"gold": 3.0},
        7.0,
    )
    assert prediction.battle_survival_probability == 0.5
    assert prediction.terminal_absolute_current_hp == 42.0
    assert prediction.structured_resource_values == {"gold": 3.0}
    assert prediction.native_leaf_utility == 7.0


@dataclass
class _Scorer:
    checkpoint_provenance: SearchGuidanceCheckpointProvenance
    with_value: bool = True
    native_value: float | None = None
    name: str = "unit-test-scorer"
    calls: int = 0

    def score_decision_context(
        self, context: DecisionContext
    ) -> SearchGuidanceInferenceResult:
        self.calls += 1
        count = len(context.legal_action_features)
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.checkpoint_provenance,
            legal_action_count=count,
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=[
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=context.legal_action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=float(index),
                    policy_probability=(0.3 if index == 0 else 0.7),
                    action_identity=_action_identity(context, index),
                )
                for index in range(count)
            ],
            value_prediction=(
                SearchGuidanceValuePrediction(
                    battle_survival_probability=(
                        None if self.native_value is not None else 0.7
                    ),
                    native_leaf_utility=self.native_value,
                )
                if self.with_value
                else None
            ),
        )


@dataclass(frozen=True)
class _Projection:
    public_context: dict[str, Any]

    def telemetry(self) -> dict[str, Any]:
        return {
            "schema_id": "t069-public-context-feature-projection-v1",
            "schema_version": 1,
            "implementation_id": (
                "search-scope-complete-public-context-feature-projection-v1"
            ),
            "construction_ms": 1.0,
            "canonicalization_ms": 0.25,
            "validation_encoding_ms": 0.75,
            "canonical_public_context_sha256": "abc",
            "canonical_public_context_byte_count": 2,
            "public_context_features_sha256": "def",
            "feature_schema_id": "public-context-model-input-v1",
            "feature_schema_version": 1,
            "feature_names": [],
            "feature_size": 0,
            "dtype": "float32",
            "device": "cpu",
            "checkpoint_artifact_id": "unit-test-checkpoint",
            "construction_count": 1,
        }


@dataclass
class _ProjectionScorer(_Scorer):
    projection_builds: int = 0
    projected_calls: int = 0

    def prepare_public_context_projection(
        self, public_run_context: dict[str, Any]
    ) -> _Projection:
        self.projection_builds += 1
        return _Projection(dict(public_run_context))

    def score_decision_context_with_projection(
        self, context: DecisionContext, projection: _Projection
    ) -> SearchGuidanceInferenceResult:
        if dict(context.public_run_context) != projection.public_context:
            raise ValueError("stale projection")
        self.projected_calls += 1
        result = self.score_decision_context(context)
        return SearchGuidanceInferenceResult(
            scorer_name=result.scorer_name,
            checkpoint_provenance=result.checkpoint_provenance,
            legal_action_count=result.legal_action_count,
            eligible_action_count=result.eligible_action_count,
            action_scores=result.action_scores,
            value_prediction=result.value_prediction,
            timing_ms={
                "feature_encoding_ms": 0.1,
                "tensor_construction_ms": 0.2,
                "model_forward_ms": 0.3,
                "result_postprocess_ms": 0.4,
                "public_context_projection_validation_ms": 0.05,
                "state_vector_assembly_ms": 0.05,
            },
        )


def _action_identity(context: DecisionContext, index: int) -> dict[str, Any]:
    if index >= len(context.tactical_legal_actions):
        return {}
    raw = context.tactical_legal_actions[index]
    identity = raw.get("identity") if isinstance(raw, dict) else None
    return dict(identity) if isinstance(identity, dict) else {}


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="Defend",
            kind="card",
            raw={"scope": "battle", "bits": 22, "idx1": 1, "idx2": 0, "idx3": 0},
        ),
    ]


def _context() -> DecisionContext:
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[], []],
        legal_action_kinds=["card", "card"],
        eligible_action_indices=[0, 1],
        public_run_context={},
    )


def _node_raw() -> dict[str, Any]:
    return {
        "screen_state": "BATTLE",
        "battle_active": True,
        "act": 1,
        "floor_num": 1,
        "ascension": 20,
        "battle_turn": 1,
        "battle_player_hp": 70,
        "battle_player_energy": 3,
        "battle_player_block": 0,
        "battle_hand": [],
        "battle_monsters": [],
    }


def _node_actions() -> list[dict[str, Any]]:
    return [
        {
            "scope": "battle",
            "bits": 11,
            "kind": "card",
            "label": "Strike",
            "idx1": 0,
            "idx2": 0,
            "idx3": 0,
        },
        {
            "scope": "battle",
            "bits": 22,
            "kind": "card",
            "label": "Defend",
            "idx1": 1,
            "idx2": 0,
            "idx3": 0,
        },
    ]


def _raw_search(*, policy_calls: int, value_calls: int) -> dict[str, Any]:
    return {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": BATTLE_SEARCH_V2_NATIVE_API,
        "patch_identity": BATTLE_SEARCH_V2_PATCH_IDENTITY,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": 10,
        "root_visits": 10,
        "include_potions": False,
        "native_simulator_steps": 123,
        "model_calls": policy_calls + value_calls,
        "best_action_value": 0.7,
        "min_action_value": 0.2,
        "outcome_player_hp": 42,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": [
            {
                "scope": "battle",
                "bits": 11,
                "kind": "card",
                "label": "Strike",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 0,
                "visits": 6,
                "evaluation_sum": 3.6,
                "mean_value": 0.6,
            },
            {
                "scope": "battle",
                "bits": 22,
                "kind": "card",
                "label": "Defend",
                "idx1": 1,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 1,
                "visits": 4,
                "evaluation_sum": 2.0,
                "mean_value": 0.5,
            },
        ],
        "tree_internal_telemetry": {
            "expanded_nodes": 5,
            "policy_prior_calls": policy_calls,
            "leaf_value_calls": value_calls,
            "policy_prior_scope": "every_expanded_player_decision_node"
            if policy_calls
            else "disabled",
            "leaf_value_boundary": "after_first_action_from_newly_expanded_node"
            if value_calls
            else "disabled",
        },
    }


class _BaseAdapter:
    expected_value = 0.7

    def battle_search_v2(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> dict[str, Any]:
        del snapshot
        policy = kwargs["policy_prior_callback"]
        value = kwargs["leaf_value_callback"]
        policy_calls = 0
        value_calls = 0
        if policy is not None:
            assert policy(_node_raw(), _node_actions()) == pytest.approx([0.3, 0.7])
            policy_calls = 1
        if value is not None:
            assert value(_node_raw(), _node_actions()) == pytest.approx(
                self.expected_value
            )
            value_calls = 1
        return _raw_search(policy_calls=policy_calls, value_calls=value_calls)


class _Adapter(_BaseAdapter):
    def battle_search_v2_with_tree_geometry(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> dict[str, Any]:
        raw = self.battle_search_v2(snapshot, **kwargs)
        raw["tree_internal_telemetry"]["tree_geometry"] = {
            "schema_id": "native-battle-search-v2-tree-geometry-v1",
            "schema_version": 1,
            "root_depth": 0,
            "total_expanded_node_count": 5,
            "total_discovered_child_edge_count": 6,
            "total_visited_child_edge_count": 4,
            "max_expanded_depth": 1,
            "depth_rows": [
                {
                    "depth": 0,
                    "expanded_node_count": 1,
                    "discovered_child_edge_count": 2,
                    "visited_child_edge_count": 2,
                    "branching_histogram": [{"child_count": 2, "node_count": 1}],
                },
                {
                    "depth": 1,
                    "expanded_node_count": 4,
                    "discovered_child_edge_count": 4,
                    "visited_child_edge_count": 2,
                    "branching_histogram": [{"child_count": 1, "node_count": 4}],
                },
            ],
        }
        return raw

    def battle_search_v2_with_state_utilization(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> dict[str, Any]:
        raw = self.battle_search_v2(snapshot, **kwargs)
        raw["native_api"] = "StepSimulator.battle_search_v2_with_state_utilization.v1"
        raw["patch_identity"] = "sts_lightspeed_battle_search_v2_state_utilization_v1"
        raw["tree_internal_telemetry"]["state_utilization"] = {
            "schema_id": "native-battle-search-v2-state-utilization-v1",
            "schema_version": 1,
            "identity_schema_id": "native-battle-search-v2-exact-state-v1",
            "identity_semantics": T079_IDENTITY_SEMANTICS,
            "identity_components": list(T079_IDENTITY_COMPONENTS),
            "active_queue_normalization": dict(T079_ACTIVE_QUEUE_NORMALIZATION_PROOF),
            "identity_complete": True,
            "identity_unavailable_reason": None,
            "digest_algorithm": "fnv1a128-v1",
            "digest_collision_count": 0,
            "collision_check": "canonical_payload_equality_within_digest_bucket",
            "expanded_path_node_count": 5,
            "expanded_states": [
                {
                    "expansion_ordinal": ordinal,
                    "depth": 0 if ordinal == 1 else 1,
                    "exact_state_digest": f"{ordinal:032x}",
                    "first_seen": True,
                    "first_seen_expansion_ordinal": ordinal,
                    "first_seen_depth": 0 if ordinal == 1 else 1,
                    "path_fingerprint": f"p{ordinal}",
                }
                for ordinal in range(1, 6)
            ],
        }
        raw["tree_internal_telemetry"]["tree_geometry"] = {
            "schema_id": "native-battle-search-v2-tree-geometry-v1",
            "schema_version": 1,
            "root_depth": 0,
            "total_expanded_node_count": 5,
            "total_discovered_child_edge_count": 6,
            "total_visited_child_edge_count": 4,
            "max_expanded_depth": 1,
            "depth_rows": [
                {
                    "depth": 0,
                    "expanded_node_count": 1,
                    "discovered_child_edge_count": 2,
                    "visited_child_edge_count": 2,
                    "branching_histogram": [{"child_count": 2, "node_count": 1}],
                },
                {
                    "depth": 1,
                    "expanded_node_count": 4,
                    "discovered_child_edge_count": 4,
                    "visited_child_edge_count": 2,
                    "branching_histogram": [{"child_count": 1, "node_count": 4}],
                },
            ],
        }
        return raw

    def battle_search(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> dict[str, Any]:
        del snapshot, kwargs
        raw = _raw_search(policy_calls=0, value_calls=0)
        raw["native_api"] = ORACLE_SEARCH_NATIVE_API
        raw["patch_identity"] = ORACLE_SEARCH_PATCH_IDENTITY
        raw["model_calls"] = None
        raw.pop("tree_internal_telemetry")
        return raw


class _CorrectedValueAdapter(_Adapter):
    expected_value = 3.25


class _RepeatingAdapter(_Adapter):
    policy_results: list[list[float]]
    value_results: list[float]

    def __init__(self) -> None:
        self.policy_results = []
        self.value_results = []

    def battle_search_v2(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> dict[str, Any]:
        del snapshot
        policy = kwargs["policy_prior_callback"]
        value = kwargs["leaf_value_callback"]
        policy_calls = 0
        value_calls = 0
        if policy is not None:
            first = list(policy(_node_raw(), _node_actions()))
            second = list(policy(_node_raw(), _node_actions()))
            assert first == pytest.approx(second)
            self.policy_results.extend((first, second))
            policy_calls = 2
        if value is not None:
            first = float(value(_node_raw(), _node_actions()))
            second = float(value(_node_raw(), _node_actions()))
            assert first == pytest.approx(second)
            self.value_results.extend((first, second))
            value_calls = 2
        return _raw_search(policy_calls=policy_calls, value_calls=value_calls)


@pytest.mark.parametrize(
    ("ablation", "policy_calls", "value_calls"),
    [("prior_only", 1, 0), ("value_only", 0, 1), ("prior_value", 1, 1)],
)
def test_guided_ablations_exercise_declared_tree_internal_mechanisms(
    ablation: str, policy_calls: int, value_calls: int
) -> None:
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(_checkpoint()),
        ablation=ablation,  # type: ignore[arg-type]
        native_source_identity={"integration_commit": "t062"},
    )
    decision = controller.select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    telemetry = decision.metadata["battle_search_v2"]["tree_internal_telemetry"]
    assert telemetry["policy_prior_calls"] == policy_calls
    assert telemetry["leaf_value_calls"] == value_calls
    assert decision.selected_index == 0


def test_baseline_delegates_to_current_oracle_search_semantics() -> None:
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(_checkpoint()),
        ablation="baseline",
        native_source_identity={"integration_commit": "t062"},
    )
    decision = controller.select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    assert decision.provenance.name == "oracle_search_v1_highest_mean_s10"
    assert decision.selected_index == 0


def test_cache_disabled_preserves_accepted_t062_provenance_exactly() -> None:
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(_checkpoint()),
        ablation="prior_value",
        native_source_identity={"integration_commit": "t062"},
    )
    assert controller.provenance.to_dict() == {
        "schema_version": 1,
        "kind": "tree_internal_policy_value_oracle_battle_search",
        "name": "battle_search_v2_oracle_like_v1_prior_value_highest_mean_s10",
        "config": {
            "controller_version": "battle-search-v2-oracle-like-v1",
            "task_id": "T062",
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "native_search_schema_id": "native-battle-search-root-v1",
            "native_search_api": BATTLE_SEARCH_V2_NATIVE_API,
            "native_search_patch_identity": BATTLE_SEARCH_V2_PATCH_IDENTITY,
            "native_source_identity": {"integration_commit": "t062"},
            "search_budget": {
                "simulations": 10,
                "budget_unit": "native_tree_search_playouts",
            },
            "root_selection_rule": "highest_mean",
            "action_space": controller.action_space.to_dict(),
            "ablation": "prior_value",
            "tree_internal_guidance": {
                "policy_prior": True,
                "policy_prior_scope": "every_expanded_player_decision_node",
                "learned_leaf_value": True,
                "learned_leaf_value_boundary": (
                    "after_first_action_from_newly_expanded_node"
                ),
                "root_only_or_post_search_fallback": False,
            },
            "guidance_scorer": {
                "name": "unit-test-scorer",
                "checkpoint_provenance": _checkpoint().to_dict(),
            },
        },
    }


def test_value_ablation_rejects_checkpoint_without_survival_head() -> None:
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(_checkpoint(), with_value=False),
        ablation="value_only",
        native_source_identity={"integration_commit": "t062"},
    )
    with pytest.raises(ValueError, match="battle-survival value head"):
        controller.select_action(
            _Adapter(),
            SimulatorSnapshot(observation=[], raw=_node_raw()),
            _actions(),
            _context(),
            0,
        )


def test_corrected_native_utility_is_passed_to_existing_search_v2_callback() -> None:
    checkpoint = replace(
        _checkpoint(),
        outcome_target_kind=SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND,
    )
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(checkpoint, native_value=3.25),
        ablation="value_only",
        native_source_identity={"integration_commit": "t085"},
    )
    decision = controller.select_action(
        _CorrectedValueAdapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    assert decision.selected_index == 0


def test_t067_public_node_cache_reuses_exact_policy_value_result() -> None:
    scorer = _Scorer(_checkpoint())
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=scorer,
        ablation="prior_value",
        inference_cache_enabled=True,
        native_source_identity={"integration_commit": "t067"},
    )
    decision = controller.select_action(
        _RepeatingAdapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    assert decision.selected_index == 0
    assert scorer.calls == 1
    cost = decision.metadata["t067_cost_attribution"]
    assert cost["cache_lookup_count"] == 4.0
    assert cost["cache_hit_count"] == 3.0
    assert cost["cache_miss_count"] == 1.0
    assert cost["model_call_count"] == 1.0
    assert decision.provenance.config["cost_repair"]["task_id"] == "T067"


@pytest.mark.parametrize("ablation", ["prior_only", "value_only", "prior_value"])
def test_t067_cache_preserves_frozen_outputs_and_selected_action_identity(
    ablation: str,
) -> None:
    uncached_scorer = _Scorer(_checkpoint())
    cached_scorer = _Scorer(_checkpoint())
    uncached_adapter = _RepeatingAdapter()
    cached_adapter = _RepeatingAdapter()
    common = {
        "simulations": 10,
        "ablation": ablation,
        "native_source_identity": {"integration_commit": "t067"},
    }
    uncached = BattleSearchV2Controller(
        scorer=uncached_scorer,
        **common,  # type: ignore[arg-type]
    ).select_action(
        uncached_adapter,
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    cached = BattleSearchV2Controller(
        scorer=cached_scorer,
        inference_cache_enabled=True,
        **common,  # type: ignore[arg-type]
    ).select_action(
        cached_adapter,
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )

    assert len(cached_adapter.policy_results) == len(uncached_adapter.policy_results)
    for cached_policy, uncached_policy in zip(
        cached_adapter.policy_results, uncached_adapter.policy_results, strict=True
    ):
        assert cached_policy == pytest.approx(uncached_policy, rel=0.0, abs=1e-6)
    assert cached_adapter.value_results == pytest.approx(
        uncached_adapter.value_results, rel=0.0, abs=1e-6
    )
    assert cached.selected_index == uncached.selected_index
    assert (
        _actions()[cached.selected_index].action_id
        == _actions()[uncached.selected_index].action_id
    )
    assert cached.score == pytest.approx(uncached.score, rel=0.0, abs=1e-6)
    assert cached_scorer.calls < uncached_scorer.calls


def test_t067_cache_scope_is_one_select_action_invocation() -> None:
    scorer = _Scorer(_checkpoint())
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=scorer,
        ablation="prior_value",
        inference_cache_enabled=True,
        native_source_identity={"integration_commit": "t067"},
    )
    for step_index in range(2):
        controller.select_action(
            _RepeatingAdapter(),
            SimulatorSnapshot(observation=[], raw=_node_raw()),
            _actions(),
            _context(),
            step_index,
        )
    assert scorer.calls == 2


def test_t069_projection_is_search_local_versioned_and_telemetrized() -> None:
    scorer = _ProjectionScorer(_checkpoint())
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=scorer,
        ablation="prior_value",
        inference_cache_enabled=True,
        public_context_projection_enabled=True,
        native_source_identity={"integration_commit": "t069"},
    )
    decision = controller.select_action(
        _RepeatingAdapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )

    assert scorer.projection_builds == 1
    assert scorer.projected_calls == 1
    assert decision.provenance.config["task_id"] == "T069"
    assert decision.provenance.config["cost_repair"]["projection_scope"] == (
        "one_native_search_call"
    )
    assert decision.provenance.config["cost_repair"]["digest_only_reuse"] is False
    cost = decision.metadata["t069_cost_attribution"]
    assert cost["public_context_projection_construction_count"] == 1.0
    assert cost["public_context_projection_reuse_count"] == 1.0
    assert cost["public_context_projection_validation_ms"] == pytest.approx(0.05)
    assert cost["checkpoint_feature_encoding_ms"] == pytest.approx(0.1)
    assert (
        decision.metadata["battle_search_v2"]["public_context_projection"][
            "checkpoint_artifact_id"
        ]
        == "unit-test-checkpoint"
    )


def test_t070_geometry_companion_is_explicit_validated_and_retained() -> None:
    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_ProjectionScorer(_checkpoint()),
        ablation="prior_value",
        inference_cache_enabled=True,
        public_context_projection_enabled=True,
        tree_geometry_enabled=True,
        native_source_identity={"integration_commit": "t070"},
    )
    decision = controller.select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        3,
    )

    assert decision.provenance.config["task_id"] == "T070"
    assert decision.provenance.config["tree_geometry"]["semantic_effect"] == (
        "read_only_post_search_aggregation"
    )
    record = decision.metadata["t070_tree_geometry_records"][0]
    assert record["decision_step_index"] == 3
    assert record["native_geometry"]["max_expanded_depth"] == 1
    assert record["selected_action_identity"]["action_id"] == "battle:11"
    assert record["model_calls"] == 1


def test_t070_geometry_rejects_non_prior_value_arm() -> None:
    with pytest.raises(ValueError, match="only for the prior_value"):
        BattleSearchV2Controller(
            simulations=10,
            scorer=_Scorer(_checkpoint()),
            ablation="prior_only",
            tree_geometry_enabled=True,
        )


def test_t079_state_utilization_is_read_only_and_preserves_search_outputs() -> None:
    common = {
        "simulations": 10,
        "scorer": _ProjectionScorer(_checkpoint()),
        "ablation": "prior_value",
        "inference_cache_enabled": True,
        "public_context_projection_enabled": True,
        "native_source_identity": {"integration_commit": "t079"},
    }
    normal = BattleSearchV2Controller(**common).select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    instrumented = BattleSearchV2Controller(
        **common, state_utilization_enabled=True
    ).select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    assert instrumented.selected_index == normal.selected_index
    assert instrumented.score == pytest.approx(normal.score, rel=0.0, abs=1e-12)
    for key in (
        "oracle_search_root_visits",
        "oracle_search_native_simulator_steps",
        "oracle_search_selected_index",
        "oracle_search_selected_mean_value",
    ):
        assert instrumented.metadata[key] == normal.metadata[key]
    telemetry = instrumented.metadata["t079_state_utilization_records"][0][
        "native_state_utilization"
    ]
    assert telemetry["unique_exact_state_count"] == 5
    assert telemetry["exact_duplicate_path_node_count"] == 0


def test_t079_identity_component_audit_is_required() -> None:
    raw = _Adapter().battle_search_v2_with_state_utilization(
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        policy_prior_callback=None,
        leaf_value_callback=None,
    )
    telemetry = raw["tree_internal_telemetry"]
    del telemetry["state_utilization"]["identity_components"]
    with pytest.raises(ValueError, match="component audit"):
        _validate_t079_state_utilization(raw, telemetry)


def test_t079_incomplete_native_identity_is_explicitly_opaque() -> None:
    raw = _Adapter().battle_search_v2_with_state_utilization(
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        policy_prior_callback=None,
        leaf_value_callback=None,
    )
    telemetry = raw["tree_internal_telemetry"]
    state = telemetry["state_utilization"]
    state["identity_complete"] = False
    state["identity_unavailable_reason"] = (
        "native ActionQueue contains opaque std::function entries"
    )
    validated = _validate_t079_state_utilization(raw, telemetry)
    assert validated["identity_evidence_class_counts"] == {
        "exact_comparable": 0,
        "opaque": 5,
    }
    assert all(
        row["identity_evidence_class"] == "opaque" and row["exact_state_digest"] is None
        for row in validated["expanded_states"]
    )


def test_t079_complete_claim_without_active_queue_proof_is_opaque() -> None:
    raw = _Adapter().battle_search_v2_with_state_utilization(
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        policy_prior_callback=None,
        leaf_value_callback=None,
    )
    telemetry = raw["tree_internal_telemetry"]
    del telemetry["state_utilization"]["active_queue_normalization"]

    validated = _validate_t079_state_utilization(raw, telemetry)

    assert validated["identity_complete"] is False
    assert validated["identity_unavailable_reason"] == (
        "native identity does not prove active-slot/stale-slot queue normalization"
    )
    assert validated["identity_evidence_class_counts"] == {
        "exact_comparable": 0,
        "opaque": 5,
    }


def test_t068_trace_survives_fixed_evaluation_telemetry_aggregation() -> None:
    from sts_combat_rl.sim.fixed_battle_evaluation import (
        _append_controller_telemetry_value,
        _merge_mapping_controller_telemetry,
    )

    controller = BattleSearchV2Controller(
        simulations=10,
        scorer=_Scorer(_checkpoint()),
        ablation="prior_value",
        callback_dependency_trace_enabled=True,
        native_source_identity={"integration_commit": "t068"},
    )
    decision = controller.select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw=_node_raw()),
        _actions(),
        _context(),
        0,
    )
    telemetry: dict[str, Any] = {}
    for key, value in decision.metadata.items():
        if isinstance(value, dict):
            _merge_mapping_controller_telemetry(telemetry, key, value)
        else:
            _append_controller_telemetry_value(telemetry, key, value)
    traces = telemetry["t068_callback_dependency_trace_records"]
    assert isinstance(traces, list)
    assert traces[0][0]["schema_id"] == "t068-native-callback-request-trace-v1"
    assert len(traces[0][0]["requests"]) == 2
