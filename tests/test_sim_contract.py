from __future__ import annotations

from collections.abc import Sequence

from sts_combat_rl.sim import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)


class TinyAdapter:
    def __init__(self) -> None:
        self.steps = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[seed or 0, self.steps],
            raw={"seed": seed},
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> Sequence[SimulatorAction]:
        return [
            SimulatorAction(
                action_id=0,
                label="end turn",
                kind="end",
                raw={"observation_length": len(snapshot.observation)},
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.steps += 1
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[self.steps], raw={"action": action.label}
            ),
            terminal=True,
            info={"action_kind": action.kind},
        )


def test_simulator_contract_supports_reset_legal_actions_and_step() -> None:
    adapter = TinyAdapter()

    snapshot = adapter.reset(seed=123)
    action = adapter.legal_actions(snapshot)[0]
    transition = adapter.step(action)

    assert snapshot.observation == [123, 0]
    assert action.kind == "end"
    assert transition.snapshot.observation == [1]
    assert transition.terminal is True
    assert transition.info["action_kind"] == "end"
