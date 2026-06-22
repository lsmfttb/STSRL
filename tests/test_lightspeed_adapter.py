from __future__ import annotations

from dataclasses import dataclass

import pytest

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.contract import SimulatorSnapshot


class FakeCharacterClass:
    IRONCLAD = "IRONCLAD"


@dataclass
class FakeNativeAction:
    scope: str
    bits: int
    kind: str
    label: str
    idx1: int = 0
    idx2: int = 0
    idx3: int = 0


class FakeStepSimulator:
    def __init__(self, character_class: str, seed: int, ascension: int) -> None:
        self.character_class = character_class
        self.seed = seed
        self.ascension = ascension
        self.steps = 0
        self.outcome = "UNDECIDED"

    def reset(self, character_class: str, seed: int, ascension: int) -> None:
        self.character_class = character_class
        self.seed = seed
        self.ascension = ascension
        self.steps = 0
        self.outcome = "UNDECIDED"

    def snapshot(self) -> dict[str, object]:
        return {
            "screen_state": "BATTLE",
            "outcome": self.outcome,
            "seed": self.seed,
            "steps": self.steps,
            "battle_player": {
                "current_hp": 80,
                "energy": 3,
                "block": self.steps,
            },
            "battle_hand": [
                {
                    "hand_index": 0,
                    "name": "Strike",
                    "type": "ATTACK",
                    "playable": True,
                    "requires_target": True,
                }
            ],
            "battle_monsters": [
                {
                    "monster_index": 0,
                    "name": "CULTIST",
                    "current_hp": 51,
                    "targetable": True,
                }
            ],
        }

    def observation(self) -> list[int]:
        return [self.seed, self.steps]

    def legal_actions(self) -> list[FakeNativeAction]:
        return [
            FakeNativeAction(
                scope="battle",
                bits=123,
                kind="end_turn",
                label="{ end turn }",
            )
        ]

    def step(self, action: FakeNativeAction) -> dict[str, object]:
        assert action.bits == 123
        self.steps += 1
        self.outcome = "PLAYER_LOSS"
        snapshot = self.snapshot()
        snapshot["completed_battle_outcome"] = "PLAYER_LOSS"
        return snapshot

    def capture_checkpoint(self) -> tuple[int, str, int]:
        return self.seed, self.outcome, self.steps

    def restore_checkpoint(self, checkpoint: tuple[int, str, int]) -> dict[str, object]:
        self.seed, self.outcome, self.steps = checkpoint
        return self.snapshot()


class FakeModule:
    CharacterClass = FakeCharacterClass
    StepSimulator = FakeStepSimulator


def test_lightspeed_adapter_wraps_step_simulator_contract() -> None:
    adapter = LightSpeedAdapter(seed=7, ascension=20, module=FakeModule)

    snapshot = adapter.reset(seed=11)
    actions = adapter.legal_actions(snapshot)
    transition = adapter.step(actions[0])

    assert snapshot.observation == [11, 0]
    assert snapshot.raw["screen_state"] == "BATTLE"
    assert snapshot.raw["battle_hand"][0]["name"] == "Strike"
    assert snapshot.raw["battle_monsters"][0]["targetable"] is True
    assert actions[0].action_id == "battle:123"
    assert actions[0].kind == "end_turn"
    assert actions[0].raw["native"].bits == 123
    assert transition.terminal is True
    assert transition.snapshot.observation == [11, 1]
    assert transition.snapshot.raw["battle_player"]["block"] == 1
    assert transition.info == {
        "action_id": "battle:123",
        "action_kind": "end_turn",
        "completed_battle_outcome": "PLAYER_LOSS",
    }


def test_lightspeed_adapter_rejects_non_ironclad() -> None:
    with pytest.raises(ValueError, match="IRONCLAD"):
        LightSpeedAdapter(player_class="SILENT", module=FakeModule)


def test_lightspeed_adapter_wraps_native_checkpoint_restore() -> None:
    adapter = LightSpeedAdapter(seed=7, ascension=20, module=FakeModule)
    initial = adapter.reset(seed=11)
    checkpoint = adapter.capture_checkpoint(initial)
    adapter.step(adapter.legal_actions(initial)[0])

    restored = adapter.restore_checkpoint(checkpoint)

    assert adapter.supports_checkpoint_restore is True
    assert checkpoint.adapter_id == adapter.checkpoint_adapter_id
    assert checkpoint.metadata["seed"] == 11
    assert restored.observation == initial.observation
    assert restored.raw == initial.raw


def test_lightspeed_snapshot_fingerprint_ignores_transition_only_battle_outcome() -> (
    None
):
    stateful = LightSpeedAdapter._snapshot_fingerprint(
        SimulatorSnapshot(
            observation=[11, 3],
            raw={"screen_state": "REWARDS", "outcome": "UNDECIDED"},
        )
    )
    transition_labeled = LightSpeedAdapter._snapshot_fingerprint(
        SimulatorSnapshot(
            observation=[11, 3],
            raw={
                "screen_state": "REWARDS",
                "outcome": "UNDECIDED",
                "completed_battle_outcome": "PLAYER_VICTORY",
            },
        )
    )

    assert stateful == transition_labeled
