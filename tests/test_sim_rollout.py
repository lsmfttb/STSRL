from __future__ import annotations

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.features import (
    lightspeed_battle_feature_size,
    simulator_action_feature_size,
)
from sts_combat_rl.sim.rollout import collect_simulator_rollout, format_rollout_batch


class FakeRolloutAdapter:
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
                action_id="potion",
                label="potion",
                kind="potion",
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
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[1],
                raw={"screen_state": "BATTLE", "outcome": "PLAYER_VICTORY"},
            ),
            terminal=True,
            info={"kind": action.kind},
        )


def test_collect_simulator_rollout_keeps_legal_potions_but_excludes_by_default() -> None:
    batch = collect_simulator_rollout(FakeRolloutAdapter(), seed=3, max_steps=1)

    assert batch.terminal is True
    assert batch.outcome == "PLAYER_VICTORY"
    assert batch.problems == []
    assert len(batch.steps) == 1

    step = batch.steps[0]
    assert step.legal_action_kinds == ["potion", "card"]
    assert step.eligible_action_indices == [1]
    assert step.chosen_action_index == 1
    assert step.chosen_action_kind == "card"
    assert len(step.snapshot_features) == lightspeed_battle_feature_size()
    assert len(step.legal_action_features[0]) == simulator_action_feature_size()
    assert "Simulator rollout summary" in format_rollout_batch(batch)


def test_collect_simulator_rollout_can_include_potions_without_shape_change() -> None:
    batch = collect_simulator_rollout(
        FakeRolloutAdapter(),
        seed=3,
        max_steps=1,
        action_space=ActionSpaceConfig.include_all(),
    )

    step = batch.steps[0]
    assert step.eligible_action_indices == [0, 1]
    assert step.chosen_action_kind == "card"
    assert len(step.snapshot_features) == lightspeed_battle_feature_size()
    assert len(step.legal_action_features[0]) == simulator_action_feature_size()
