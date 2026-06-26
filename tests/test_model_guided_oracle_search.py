from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.model_guided_oracle_search import (
    MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE,
    MODEL_GUIDED_ORACLE_SEARCH_CONTROLLER_VERSION,
    ModelGuidedOracleSearchController,
)
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
        information_regime_counts={"normal_public_policy": 2},
        source_information_regime_counts={NATIVE_SEARCH_INFORMATION_REGIME: 2},
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


def _context(action_count: int = 2) -> DecisionContext:
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[] for _ in range(action_count)],
        legal_action_kinds=["card" for _ in range(action_count)],
        eligible_action_indices=list(range(action_count)),
    )


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


def _context_with_tactical_identities() -> DecisionContext:
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


def _row(
    bits: int,
    *,
    visits: int,
    mean_value: float,
    label: str,
) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": bits,
        "kind": "card",
        "label": label,
        "idx1": 0,
        "idx2": 0,
        "idx3": 0,
        "search_tree_present": True,
        "search_edge_index": 0,
        "visits": visits,
        "evaluation_sum": visits * mean_value,
        "mean_value": mean_value,
    }


def _raw_search(rows: list[dict[str, object]]) -> dict[str, object]:
    visits = sum(int(row["visits"]) for row in rows)
    return {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": ORACLE_SEARCH_NATIVE_API,
        "patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": visits,
        "root_visits": visits,
        "include_potions": False,
        "native_simulator_steps": 321,
        "model_calls": None,
        "best_action_value": 0.5,
        "min_action_value": 0.45,
        "outcome_player_hp": 42,
        "root_row_count": len(rows),
        "search_edge_count": len(rows),
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": rows,
    }


class _Adapter:
    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        assert simulations == 10
        return _raw_search(
            [
                _row(11, visits=6, mean_value=0.50, label="Strike"),
                _row(22, visits=4, mean_value=0.45, label="Defend"),
            ]
        )


@dataclass
class _FakeGuidanceScorer:
    probabilities: tuple[float, ...]
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(
        default_factory=_checkpoint
    )
    result_checkpoint_provenance: SearchGuidanceCheckpointProvenance | None = None
    action_kinds: tuple[str, ...] | None = None
    action_identities: tuple[dict[str, object], ...] | None = None
    name: str = "fake_guidance"

    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> SearchGuidanceInferenceResult:
        checkpoint = self.result_checkpoint_provenance or self.checkpoint_provenance
        action_kinds = self.action_kinds or tuple(context.legal_action_kinds)
        action_identities = self.action_identities or tuple(
            _score_identity(context, index) for index in range(len(self.probabilities))
        )
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=checkpoint,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=[
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=float(index),
                    policy_probability=probability,
                    action_identity=dict(action_identities[index]),
                )
                for index, probability in enumerate(self.probabilities)
            ],
            duration_ms=1.25,
        )


def _score_identity(context: DecisionContext, index: int) -> dict[str, object]:
    if index < len(context.tactical_legal_actions):
        identity = context.tactical_legal_actions[index].get("identity", {})
        if isinstance(identity, dict):
            return dict(identity)
    return {"stable_id": f"action-{index}"}


class _RaisingGuidanceScorer:
    name = "raising_guidance"
    checkpoint_provenance = _checkpoint()

    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> SearchGuidanceInferenceResult:
        del context
        raise ValueError("context mismatch")


def test_model_guided_controller_combines_native_mean_and_policy_probability() -> None:
    controller = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer((0.10, 0.90)),
        policy_probability_weight=0.1,
        native_source_identity={"integration_commit": "abc"},
    )

    decision = controller.select_action(
        _Adapter(),
        SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
        _actions(),
        _context(),
        step_index=0,
    )

    assert decision.selected_index == 1
    assert decision.score == pytest.approx(0.54)
    assert decision.provenance.kind == "model_guided_oracle_battle_search"
    assert decision.provenance.config["controller_version"] == (
        MODEL_GUIDED_ORACLE_SEARCH_CONTROLLER_VERSION
    )
    assert decision.provenance.config["information_regime"] == (
        NATIVE_SEARCH_INFORMATION_REGIME
    )
    assert (
        decision.provenance.config["guidance_scorer"]["checkpoint_provenance"][
            "checkpoint_artifact_id"
        ]
        == "checkpoint-a"
    )
    assert decision.metadata["model_guided_oracle_model_calls"] == 1
    assert decision.metadata["model_guided_oracle_selected_index"] == 1
    assert decision.metadata["model_guided_oracle_selected_combined_score"] == (
        pytest.approx(0.54)
    )
    assert decision.metadata["model_guided_oracle_selection_rule"] == (
        MODEL_GUIDED_ORACLE_ROOT_SELECTION_RULE
    )
    root_scores = decision.metadata["model_guided_oracle_root_scores"]
    assert root_scores[0]["combined_score"] == pytest.approx(0.51)
    assert root_scores[1]["combined_score"] == pytest.approx(0.54)
    assert decision.metadata["oracle_search_model_calls"] == 0

    telemetry = decision.metadata["search_decision_telemetry"][0]
    assert telemetry["schema_id"] == "search-decision-telemetry-v1"
    assert telemetry["controller_kind"] == "model_guided_oracle_battle_search"
    assert telemetry["information_regime"] == NATIVE_SEARCH_INFORMATION_REGIME
    assert telemetry["model_calls"] == 1
    assert telemetry["native_simulator_steps"] == 321
    assert telemetry["search_backend"]["checkpoint_artifact_id"] == "checkpoint-a"
    assert telemetry["selected_legal_action_index"] == 1
    assert "model_guided_allocation" in telemetry["unavailable_fields"]

    native_report = decision.metadata["oracle_search_decision_reports"][0]
    assert native_report["decision_telemetry"]["model_calls"] == 0


def test_model_guided_controller_fails_closed_on_checkpoint_change() -> None:
    scorer = _FakeGuidanceScorer(
        (0.5, 0.5),
        result_checkpoint_provenance=_checkpoint("checkpoint-b"),
    )
    controller = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=scorer,
        native_source_identity={"integration_commit": "abc"},
    )

    with pytest.raises(ValueError, match="changing checkpoint provenance"):
        controller.select_action(
            _Adapter(),
            SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
            _actions(),
            _context(),
            step_index=0,
        )


def test_model_guided_controller_fails_closed_on_action_kind_mismatch() -> None:
    controller = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer((0.5, 0.5), action_kinds=("end_turn", "card")),
        native_source_identity={"integration_commit": "abc"},
    )

    with pytest.raises(ValueError, match="action kind"):
        controller.select_action(
            _Adapter(),
            SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
            _actions(),
            _context(),
            step_index=0,
        )


def test_model_guided_controller_fails_closed_on_action_identity_mismatch() -> None:
    context = _context_with_tactical_identities()
    controller = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer(
            (0.5, 0.5),
            action_identities=(
                _public_action_identity("card", 1),
                _public_action_identity("card", 0),
            ),
        ),
        native_source_identity={"integration_commit": "abc"},
    )

    with pytest.raises(ValueError, match="action identity"):
        controller.select_action(
            _Adapter(),
            SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
            _actions(),
            context,
            step_index=0,
        )


def test_model_guided_controller_wraps_context_mismatch_failure() -> None:
    controller = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_RaisingGuidanceScorer(),
        native_source_identity={"integration_commit": "abc"},
    )

    with pytest.raises(ValueError, match="model guidance inference failed"):
        controller.select_action(
            _Adapter(),
            SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
            _actions(),
            _context(),
            step_index=0,
        )
