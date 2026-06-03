from __future__ import annotations

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.evaluation import (
    format_policy_episode_evaluation_report,
    outcome_value,
    run_policy_episode_evaluation,
    summarize_rollout_episode,
)
from sts_combat_rl.sim.policy import PreferredKindPolicy
from sts_combat_rl.sim.policy_rollout import collect_policy_simulator_rollout


class FakeEpisodeAdapter:
    def __init__(self) -> None:
        self.seed = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        self.seed = 0 if seed is None else seed
        return SimulatorSnapshot(
            observation=[self.seed],
            raw={
                "screen_state": "BATTLE",
                "outcome": "UNDECIDED",
                "battle_active": True,
                "floor_num": 0,
                "cur_hp": 80,
                "gold": 99,
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
        del action
        won = self.seed == 1
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[self.seed],
                raw={
                    "screen_state": "BATTLE",
                    "outcome": "PLAYER_VICTORY" if won else "PLAYER_LOSS",
                    "battle_active": False,
                    "floor_num": 2 if won else 1,
                    "cur_hp": 70 if won else 0,
                    "gold": 110 if won else 99,
                },
            ),
            terminal=True,
            info={},
        )


def test_outcome_value_maps_terminal_labels_only() -> None:
    assert outcome_value("PLAYER_VICTORY") == 1.0
    assert outcome_value("PLAYER_LOSS") == -1.0
    assert outcome_value("UNDECIDED") == 0.0


def test_summarize_rollout_episode_reads_progress_fields() -> None:
    rollout = collect_policy_simulator_rollout(
        FakeEpisodeAdapter(),
        PreferredKindPolicy(),
        seed=1,
        max_steps=1,
    )

    summary = summarize_rollout_episode(rollout)

    assert summary.seed == 1
    assert summary.collected_steps == 1
    assert summary.terminal is True
    assert summary.outcome == "PLAYER_VICTORY"
    assert summary.outcome_value == 1.0
    assert summary.start_floor == 0.0
    assert summary.final_floor == 2.0
    assert summary.start_hp == 80.0
    assert summary.final_hp == 70.0
    assert summary.chosen_action_kind_counts["card"] == 1
    assert summary.problems == []


def test_run_policy_episode_evaluation_aggregates_episodes() -> None:
    report = run_policy_episode_evaluation(
        FakeEpisodeAdapter(),
        PreferredKindPolicy(),
        seeds=[1, 2],
        max_steps=1,
    )
    text = format_policy_episode_evaluation_report(report)

    assert len(report.episodes) == 2
    assert report.terminal_episodes == 2
    assert report.total_steps == 2
    assert report.outcome_value_total == 0.0
    assert report.outcome_counts["PLAYER_VICTORY"] == 1
    assert report.outcome_counts["PLAYER_LOSS"] == 1
    assert report.final_floor_counts["2"] == 1
    assert report.final_floor_counts["1"] == 1
    assert report.chosen_action_kind_counts["card"] == 2
    assert report.problems == []
    assert "Policy episode evaluation summary" in text
    assert "average outcome value: 0.00" in text
