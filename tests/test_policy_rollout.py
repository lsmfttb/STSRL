from __future__ import annotations

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.features import (
    lightspeed_battle_feature_size,
    simulator_action_feature_size,
)
from sts_combat_rl.sim.policy import PolicyDecision, PreferredKindPolicy
from sts_combat_rl.sim.policy_rollout import collect_policy_simulator_rollout


class FakePolicyRolloutAdapter:
    def __init__(self) -> None:
        self.last_action: SimulatorAction | None = None

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[seed or 0],
            raw={
                "screen_state": "BATTLE",
                "outcome": "UNDECIDED",
                "battle_active": True,
                "battle_hand": [{"type": "ATTACK", "playable": True}],
                "battle_monsters": [{"current_hp": 10, "targetable": True}],
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="end",
                label="end",
                kind="end_turn",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            ),
            SimulatorAction(
                action_id="card",
                label="card",
                kind="card",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            ),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.last_action = action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[1],
                raw={"screen_state": "BATTLE", "outcome": "PLAYER_VICTORY"},
            ),
            terminal=True,
            info={"kind": action.kind},
        )


class OutOfRangePolicy:
    name = "out_of_range"

    def select_action(self, context: object) -> PolicyDecision:
        del context
        return PolicyDecision(legal_action_index=7, reason="bad")


def test_collect_policy_simulator_rollout_uses_policy_selection() -> None:
    adapter = FakePolicyRolloutAdapter()

    batch = collect_policy_simulator_rollout(
        adapter,
        PreferredKindPolicy(),
        seed=3,
        max_steps=1,
    )

    assert adapter.last_action is not None
    assert adapter.last_action.kind == "card"
    assert batch.terminal is True
    assert batch.outcome == "PLAYER_VICTORY"
    assert batch.problems == []
    assert len(batch.steps) == 1
    step = batch.steps[0]
    assert step.chosen_action_index == 1
    assert step.chosen_action_kind == "card"
    assert len(step.snapshot_features) == lightspeed_battle_feature_size()
    assert len(step.legal_action_features[0]) == simulator_action_feature_size()


def test_collect_policy_simulator_rollout_reports_invalid_policy_choice() -> None:
    batch = collect_policy_simulator_rollout(
        FakePolicyRolloutAdapter(),
        OutOfRangePolicy(),
        seed=3,
        max_steps=1,
    )

    assert batch.steps == []
    assert "outside 2 legal actions" in batch.problems[0]
