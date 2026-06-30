from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.online_controller import PUBLIC_POLICY_INFORMATION_REGIME
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)
from sts_combat_rl.sim.search_guidance_policy import (
    SEARCH_GUIDANCE_POLICY_CONTROLLER_NAME,
    SearchGuidancePolicyController,
)


def _checkpoint(identifier: str = "checkpoint-a") -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id=identifier,
        checkpoint_path=f"/tmp/{identifier}.pt",
        model_class="TinyPolicyValueNet",
        model_config={"hidden_size": 8},
        trainer_input_artifact_id="trainer-input-sha256:abc",
        trainer_input_sha256="abc",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="oracle_teacher_row.teacher_action",
        policy_target_kind_counts={"oracle_teacher_action_one_hot": 2},
        policy_target_source_counts={"oracle_teacher_row.teacher_action": 2},
        information_regime_counts={PUBLIC_POLICY_INFORMATION_REGIME: 2},
        source_information_regime_counts={
            "full_simulator_state_oracle_like": 2,
        },
        oracle_like_supervision=True,
        training_data_provenance={"artifact": "unit-test"},
    )


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="Defend",
            kind="card",
            raw={"scope": "battle", "bits": 22},
        ),
    ]


def _public_action_identity(kind: str, index: int) -> dict[str, object]:
    return {
        "scope": "battle",
        "kind": kind,
        "parameters": {},
        "selected_card_identity": {},
        "selected_target_identity": {},
        "occurrence": index,
        "stable_id": f"public-action-{index}",
        "vocabulary_version": "unit-test",
        "status": "known",
    }


def _context() -> DecisionContext:
    action_kinds = ["card", "card"]
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[] for _ in action_kinds],
        legal_action_kinds=list(action_kinds),
        eligible_action_indices=list(range(len(action_kinds))),
        tactical_legal_actions=[
            {
                "scope": "battle",
                "kind": kind,
                "identity": _public_action_identity(kind, index),
            }
            for index, kind in enumerate(action_kinds)
        ],
    )


def _context_action_identity(context: DecisionContext, index: int) -> dict[str, object]:
    if index < len(context.tactical_legal_actions):
        identity = context.tactical_legal_actions[index].get("identity", {})
        if isinstance(identity, dict):
            return dict(identity)
    return {}


@dataclass
class _FakeGuidanceScorer:
    probabilities: tuple[float, ...] = (0.10, 0.90)
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(
        default_factory=_checkpoint
    )
    result_checkpoint: SearchGuidanceCheckpointProvenance | None = None
    mutate_identity_index: int | None = None
    name: str = "fake_guidance_policy"

    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> SearchGuidanceInferenceResult:
        scores: list[SearchGuidanceActionScore] = []
        for index, probability in enumerate(self.probabilities):
            identity = _context_action_identity(context, index)
            if self.mutate_identity_index == index:
                identity = {**identity, "stable_id": "wrong-action"}
            scores.append(
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=context.legal_action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=float(index),
                    policy_probability=probability,
                    action_identity=identity,
                )
            )
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.result_checkpoint or self.checkpoint_provenance,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=scores,
            duration_ms=1.0,
        )


def test_search_guidance_policy_selects_highest_eligible_probability() -> None:
    controller = SearchGuidancePolicyController(_FakeGuidanceScorer())

    decision = controller.select_action(
        adapter=object(),
        snapshot=SimulatorSnapshot(observation=(), raw={"screen_state": "BATTLE"}),
        actions=_actions(),
        context=_context(),
        step_index=0,
    )

    assert decision.selected_index == 1
    assert decision.provenance.kind == "search_guidance_public_policy"
    assert decision.provenance.name == SEARCH_GUIDANCE_POLICY_CONTROLLER_NAME
    assert (
        decision.provenance.config["information_regime"]
        == PUBLIC_POLICY_INFORMATION_REGIME
    )
    assert decision.metadata["search_guidance_policy_model_calls"] == 1
    assert (
        decision.metadata["search_guidance_policy_checkpoint_artifact_id"]
        == "checkpoint-a"
    )
    assert decision.metadata["search_guidance_policy_selected_index"] == 1
    assert decision.metadata["model_guidance_inference"][0]["inference_ok"] is True


def test_search_guidance_policy_rejects_action_identity_mismatch() -> None:
    controller = SearchGuidancePolicyController(
        _FakeGuidanceScorer(mutate_identity_index=1)
    )

    with pytest.raises(ValueError, match="action identity"):
        controller.select_action(
            adapter=object(),
            snapshot=SimulatorSnapshot(observation=(), raw={"screen_state": "BATTLE"}),
            actions=_actions(),
            context=_context(),
            step_index=0,
        )


def test_search_guidance_policy_rejects_changing_checkpoint_provenance() -> None:
    controller = SearchGuidancePolicyController(
        _FakeGuidanceScorer(result_checkpoint=_checkpoint("checkpoint-b"))
    )

    with pytest.raises(ValueError, match="changing checkpoint provenance"):
        controller.select_action(
            adapter=object(),
            snapshot=SimulatorSnapshot(observation=(), raw={"screen_state": "BATTLE"}),
            actions=_actions(),
            context=_context(),
            step_index=0,
        )
