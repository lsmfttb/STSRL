"""Tests for the public-context artifact replay audit."""

from __future__ import annotations

from sts_combat_rl.sim.battle_start_pool import BattleStartPoolRestoreReport
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.public_context_audit import run_public_context_artifact_audit


class _OneDecisionAdapter:
    """Tiny battle adapter for exercising audit accounting."""

    checkpoint_adapter_id = "fake-public-context-audit"
    supports_checkpoint_restore = True

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[float(seed or 0)],
            raw={
                "screen_state": "BATTLE",
                "battle_active": True,
                "act": 1,
                "floor_num": 1,
                "room_type": "MONSTER",
                "cur_hp": 70,
                "max_hp": 80,
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="card:Strike_R",
                label="Strike",
                kind="card",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[1.0],
                raw={
                    "screen_state": "REWARDS",
                    "battle_active": False,
                    "completed_battle_outcome": "PLAYER_VICTORY",
                    "outcome": "PLAYER_VICTORY",
                    "act": 1,
                    "floor_num": 1,
                    "room_type": "MONSTER",
                    "cur_hp": 68,
                    "max_hp": 80,
                },
            ),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        return SimulatorCheckpoint(
            adapter_id=self.checkpoint_adapter_id,
            checkpoint_id="fake-audit-cp",
            payload=None,
            metadata={"snapshot": dict(snapshot.raw)},
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        del checkpoint
        return self.reset(seed=1)


def test_public_context_audit_counts_required_failure_classes(monkeypatch) -> None:
    def fake_context_problems(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        return ["schema failure"]

    def fake_forbidden_problems(value):  # type: ignore[no-untyped-def]
        del value
        return ["forbidden field"]

    def fake_restore_report(adapter_factory, pool):  # type: ignore[no-untyped-def]
        del adapter_factory, pool
        return BattleStartPoolRestoreReport(
            checkpoint_count=1,
            requested_limit=0,
            restored_count=0,
            native_restored_count=0,
            replay_restored_count=0,
            context_compared_count=1,
            context_matched_count=0,
            context_mismatch_count=1,
            problems=["record 0: replay context mismatch"],
        )

    monkeypatch.setattr(
        "sts_combat_rl.sim.public_context_audit.public_context_artifact_problems",
        fake_context_problems,
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.public_context_audit.forbidden_public_context_problems",
        fake_forbidden_problems,
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.public_context_audit._candidate_parity_ok",
        lambda context, actions: False,
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.public_context_audit.verify_battle_start_pool_restores",
        fake_restore_report,
    )

    report = run_public_context_artifact_audit(
        lambda: _OneDecisionAdapter(),
        seed=1,
        episodes=1,
        max_steps=1,
    )

    assert report.decisions_observed == 1
    assert report.context_schema_failures == 1
    assert report.forbidden_field_failures == 1
    assert report.candidate_parity_failures == 1
    assert report.replay_mismatch_count == 1
    assert not report.passed
    assert "schema failure" in report.problems
    assert "seed 1 step 0: forbidden field" in report.problems
    assert "seed 1 step 0: candidate action-set parity mismatch" in report.problems
    assert "record 0: replay context mismatch" in report.problems
