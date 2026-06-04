from __future__ import annotations

import pytest

from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample
from sts_combat_rl.sim.policy import (
    DecisionContext,
    FirstEligiblePolicy,
    PolicyDecision,
    PreferredKindPolicy,
    RandomEligiblePolicy,
    ReplayChosenPolicy,
    ScoredActionPolicy,
    choose_highest_scored_eligible_index,
    evaluate_decision_policy,
    format_policy_evaluation_report,
)
from sts_combat_rl.sim.model_scoring import ActionKindPriorScorer, LinearActionScorer


class FixedScorer:
    name = "fixed"

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def score_actions(self, example: DecisionExample) -> list[float]:
        del example
        return list(self._scores)


class BadIndexPolicy:
    name = "bad_index"

    def select_action(self, example: DecisionExample) -> PolicyDecision:
        del example
        return PolicyDecision(legal_action_index=99, reason="bad")


def _example(
    *,
    legal_kinds: list[str] | None = None,
    eligible: list[int] | None = None,
    chosen: int = 1,
) -> DecisionExample:
    kinds = legal_kinds or ["potion", "card", "end_turn"]
    return DecisionExample(
        rollout_index=0,
        seed=1,
        step_index=0,
        screen_state="BATTLE",
        snapshot_features=[1.0, 2.0],
        legal_action_features=[
            [float(index), float(index + 1)] for index in range(len(kinds))
        ],
        legal_action_kinds=kinds,
        eligible_action_indices=eligible if eligible is not None else [1, 2],
        chosen_action_index=chosen,
        chosen_action_kind=kinds[chosen],
        terminal_after_step=False,
    )


def test_first_eligible_policy_uses_eligible_indices() -> None:
    batch = DecisionBatch(examples=[_example()])

    evaluation = evaluate_decision_policy(batch, FirstEligiblePolicy())

    assert evaluation.problems == []
    assert evaluation.selections[0].selected_action_index == 1
    assert evaluation.selections[0].selected_action_kind == "card"
    assert evaluation.rollout_agreement == 1


def test_preferred_kind_policy_prefers_card_over_first_eligible_end_turn() -> None:
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[1.0],
        legal_action_features=[[0.0], [1.0]],
        legal_action_kinds=["end_turn", "card"],
        eligible_action_indices=[0, 1],
    )

    decision = PreferredKindPolicy().select_action(context)

    assert decision.legal_action_index == 1
    assert decision.reason == "preferred_kind:card"


def test_scored_policy_constrains_scores_to_eligible_indices() -> None:
    example = _example(eligible=[1, 2])
    policy = ScoredActionPolicy(FixedScorer([100.0, 2.0, 3.0]))

    decision = policy.select_action(example)

    assert decision.legal_action_index == 2
    assert decision.score == 3.0
    assert "fixed:max_eligible_score" == decision.reason


def test_action_kind_prior_scorer_can_drive_scored_policy() -> None:
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[1.0],
        legal_action_features=[[0.0], [1.0], [2.0]],
        legal_action_kinds=["end_turn", "card", "potion"],
        eligible_action_indices=[0, 1],
    )
    policy = ScoredActionPolicy(
        ActionKindPriorScorer(),
        name="action_kind_prior_scorer",
    )

    decision = policy.select_action(context)

    assert decision.legal_action_index == 1
    assert decision.score == 3.0
    assert decision.reason == "action_kind_prior:max_eligible_score"


def test_linear_action_scorer_scores_context_without_training() -> None:
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[1.0, 2.0],
        legal_action_features=[[0.0, 1.0], [2.0, 0.0]],
        legal_action_kinds=["end_turn", "card"],
        eligible_action_indices=[0, 1],
    )
    scorer = LinearActionScorer(
        snapshot_weights=[0.5, 0.0],
        action_weights=[1.0, -1.0],
        bias=0.25,
    )

    assert scorer.score_actions(context) == [-0.25, 2.75]
    assert ScoredActionPolicy(scorer).select_action(context).legal_action_index == 1


def test_choose_highest_scored_eligible_index_validates_score_shape() -> None:
    with pytest.raises(ValueError, match="score count 1"):
        choose_highest_scored_eligible_index(_example(), [1.0])


def test_choose_highest_scored_eligible_index_validates_score_values() -> None:
    with pytest.raises(ValueError, match="not finite"):
        choose_highest_scored_eligible_index(_example(eligible=[1]), [0.0, float("nan"), 0.0])


def test_replay_policy_reports_ineligible_rollout_choice() -> None:
    batch = DecisionBatch(examples=[_example(eligible=[1], chosen=0)])

    evaluation = evaluate_decision_policy(batch, ReplayChosenPolicy())
    text = format_policy_evaluation_report(evaluation)

    assert evaluation.rollout_agreement == 0
    assert "is not eligible" in evaluation.problems[0]
    assert "Policy selection smoke summary" in text
    assert "problems:" in text


def test_evaluate_decision_policy_reports_invalid_policy_indices() -> None:
    batch = DecisionBatch(examples=[_example()])

    evaluation = evaluate_decision_policy(batch, BadIndexPolicy())

    assert evaluation.selections[0].selected_action_kind == "(invalid)"
    assert "outside 3 legal actions" in evaluation.problems[0]


def test_random_eligible_policy_is_seeded() -> None:
    example = _example(eligible=[1, 2])

    first = RandomEligiblePolicy(seed=7).select_action(example)
    second = RandomEligiblePolicy(seed=7).select_action(example)

    assert first == second
    assert first.legal_action_index in {1, 2}
