from __future__ import annotations

from sts_combat_rl.sim.batching import (
    build_decision_batch,
    format_decision_batch_report,
)
from sts_combat_rl.sim.rollout import RolloutBatch, RolloutStep


def _step(step_index: int, legal_count: int, chosen_index: int) -> RolloutStep:
    return RolloutStep(
        step_index=step_index,
        screen_state="BATTLE",
        snapshot_features=[1.0, 2.0],
        legal_action_features=[[float(index)] for index in range(legal_count)],
        legal_action_kinds=["card"] * legal_count,
        eligible_action_indices=list(range(legal_count)),
        chosen_action_index=chosen_index,
        chosen_action_id=f"action-{chosen_index}",
        chosen_action_kind="card",
        terminal_after_step=False,
    )


def test_build_decision_batch_preserves_variable_action_lists() -> None:
    rollouts = [
        RolloutBatch(seed=1, requested_steps=2, steps=[_step(0, 2, 1)]),
        RolloutBatch(seed=2, requested_steps=2, steps=[_step(0, 4, 3)], terminal=True),
    ]

    batch = build_decision_batch(rollouts)
    text = format_decision_batch_report(batch)

    assert batch.rollout_count == 2
    assert batch.terminal_rollouts == 1
    assert batch.snapshot_feature_size == 2
    assert batch.action_feature_size == 1
    assert [len(example.legal_action_features) for example in batch.examples] == [2, 4]
    assert batch.examples[1].eligible_action_indices == [0, 1, 2, 3]
    assert batch.problems == []
    assert "Decision batch summary" in text
    assert "legal action counts:" in text


def test_build_decision_batch_reports_invalid_indices() -> None:
    rollout = RolloutBatch(
        seed=1,
        requested_steps=1,
        steps=[_step(0, 1, 3)],
    )

    batch = build_decision_batch([rollout])

    assert len(batch.problems) == 1
    assert "chosen action index 3 outside 1 actions" in batch.problems[0]
