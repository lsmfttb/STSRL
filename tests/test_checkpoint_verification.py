from __future__ import annotations

from dataclasses import dataclass

from sts_combat_rl.sim.checkpoint_verification import (
    format_battle_checkpoint_verification_report,
    verify_battle_start_checkpoint,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import FirstEligiblePolicy


@dataclass
class _CheckpointPayload:
    phase: str
    battle_step: int


class FakeCheckpointAdapter:
    """Small authoritative-state fake with an event before a battle."""

    @property
    def checkpoint_adapter_id(self) -> str:
        return "fake-checkpoint-adapter"

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    def __init__(self) -> None:
        self.phase = "EVENT"
        self.battle_step = 0
        self._counter = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self.phase = "EVENT"
        self.battle_step = 0
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        if self.phase == "EVENT":
            return [SimulatorAction(action_id="game:1", label="event", kind="event")]
        return [
            SimulatorAction(
                action_id=f"battle:{self.battle_step}",
                label="card",
                kind="card",
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        if self.phase == "EVENT":
            self.phase = "BATTLE"
        else:
            self.battle_step += 1
            if self.battle_step == 2:
                self.phase = "REWARDS"
        return SimulatorTransition(
            snapshot=self._snapshot(),
            terminal=False,
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        self._counter += 1
        return SimulatorCheckpoint(
            adapter_id=self.checkpoint_adapter_id,
            checkpoint_id=f"checkpoint-{self._counter}",
            payload=_CheckpointPayload(self.phase, self.battle_step),
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        assert checkpoint.adapter_id == self.checkpoint_adapter_id
        self.phase = checkpoint.payload.phase
        self.battle_step = checkpoint.payload.battle_step
        return self._snapshot()

    def _snapshot(self) -> SimulatorSnapshot:
        is_battle = self.phase == "BATTLE"
        return SimulatorSnapshot(
            observation=[self.battle_step],
            raw={
                "screen_state": "BATTLE" if is_battle else self.phase,
                "battle_active": is_battle,
                "outcome": "UNDECIDED",
                "battle_outcome": "UNDECIDED",
            },
        )


class UnsupportedCheckpointAdapter(FakeCheckpointAdapter):
    @property
    def supports_checkpoint_restore(self) -> bool:
        return False


def _controller() -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(FirstEligiblePolicy()),
    )


def test_battle_start_checkpoint_determinism_gate_replays_native_checkpoint() -> None:
    report = verify_battle_start_checkpoint(
        FakeCheckpointAdapter(),
        _controller(),
        seed=7,
        replay_steps=5,
    )

    assert report.determinism_ok is True
    assert report.advancement_steps == 1
    assert report.replay_steps_executed == 2
    assert report.problems == []
    assert (
        "determinism gate passed: yes"
        in format_battle_checkpoint_verification_report(report)
    )


def test_battle_start_checkpoint_gate_reports_missing_native_support() -> None:
    report = verify_battle_start_checkpoint(
        UnsupportedCheckpointAdapter(),
        _controller(),
        seed=7,
    )

    assert report.determinism_ok is False
    assert report.checkpoint_supported is False
    assert "does not support native checkpoint" in report.problems[0]
