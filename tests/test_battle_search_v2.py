from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from sts_combat_rl.sim.battle_search_v2 import (
    BATTLE_SEARCH_V2_NATIVE_API,
    BATTLE_SEARCH_V2_PATCH_IDENTITY,
    BattleSearchV2Controller,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
)
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceValuePrediction,
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


@dataclass
class _Scorer:
    checkpoint_provenance: SearchGuidanceCheckpointProvenance
    with_value: bool = True
    name: str = "unit-test-scorer"

    def score_decision_context(
        self, context: DecisionContext
    ) -> SearchGuidanceInferenceResult:
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
                SearchGuidanceValuePrediction(battle_survival_probability=0.7)
                if self.with_value
                else None
            ),
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


class _Adapter:
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
            assert value(_node_raw(), _node_actions()) == pytest.approx(0.7)
            value_calls = 1
        return _raw_search(policy_calls=policy_calls, value_calls=value_calls)

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
