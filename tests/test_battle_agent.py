from __future__ import annotations

from sts_combat_rl.sim.battle_agent import (
    BATTLE_AGENT_CONTROLLER,
    AUTOPILOT_CONTROLLER,
    collect_battle_agent_rollout,
    format_battle_agent_sweep_report,
    run_battle_agent_sweep,
    summarize_battle_agent_episode,
)
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


class FakeBattleAgentAdapter:
    def __init__(self) -> None:
        self.phase = "battle-1"
        self.actions: list[str] = []

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self.phase = "battle-1"
        self.actions = []
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        if self.phase.startswith("battle"):
            return [
                _action("end", "end_turn", "battle"),
                _action("card", "card", "battle"),
            ]
        return [
            _action("gold", "reward_gold", "game"),
            _action("skip", "skip", "game"),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.actions.append(action.kind)
        terminal = False
        if self.phase == "battle-1":
            self.phase = "reward"
        elif self.phase == "reward":
            self.phase = "battle-2"
        else:
            self.phase = "loss"
            terminal = True

        return SimulatorTransition(snapshot=self._snapshot(), terminal=terminal, info={})

    def _snapshot(self) -> SimulatorSnapshot:
        if self.phase.startswith("battle"):
            floor = 1 if self.phase == "battle-1" else 2
            return SimulatorSnapshot(
                observation=[floor],
                raw={
                    "screen_state": "BATTLE",
                    "outcome": "UNDECIDED",
                    "battle_active": True,
                    "floor_num": floor,
                    "battle_hand": [{"type": "ATTACK", "playable": True}],
                    "battle_monsters": [{"current_hp": 10, "targetable": True}],
                },
            )
        if self.phase == "reward":
            return SimulatorSnapshot(
                observation=[1],
                raw={
                    "screen_state": "REWARDS",
                    "outcome": "UNDECIDED",
                    "battle_active": False,
                    "floor_num": 1,
                },
            )
        return SimulatorSnapshot(
            observation=[2],
            raw={
                "screen_state": "BATTLE",
                "outcome": "PLAYER_LOSS",
                "battle_active": False,
                "floor_num": 2,
            },
        )


class BadBattlePolicy:
    name = "bad_battle"

    def select_action(self, context: object) -> PolicyDecision:
        del context
        return PolicyDecision(legal_action_index=8, reason="bad")


def test_collect_battle_agent_rollout_separates_battle_and_autopilot() -> None:
    adapter = FakeBattleAgentAdapter()

    rollout = collect_battle_agent_rollout(
        adapter,
        PreferredKindPolicy(),
        seed=1,
        max_steps=3,
    )
    summary = summarize_battle_agent_episode(rollout)

    assert [step.controller for step in rollout.steps] == [
        BATTLE_AGENT_CONTROLLER,
        AUTOPILOT_CONTROLLER,
        BATTLE_AGENT_CONTROLLER,
    ]
    assert adapter.actions == ["card", "reward_gold", "card"]
    assert rollout.terminal is True
    assert rollout.outcome == "PLAYER_LOSS"
    assert summary.battle_decisions == 2
    assert summary.autopilot_decisions == 1
    assert summary.battle_action_kind_counts["card"] == 2
    assert summary.autopilot_action_kind_counts["reward_gold"] == 1
    assert summary.final_floor == 2.0
    assert summary.battle_snapshot_feature_size_counts[
        str(lightspeed_battle_feature_size())
    ] == 2
    assert summary.battle_action_feature_size_counts[
        str(simulator_action_feature_size())
    ] == 4
    assert summary.problems == []


def test_collect_battle_agent_rollout_reports_battle_policy_errors() -> None:
    rollout = collect_battle_agent_rollout(
        FakeBattleAgentAdapter(),
        BadBattlePolicy(),
        seed=1,
        max_steps=3,
    )

    assert rollout.steps == []
    assert "battle_agent selected action index 8 outside 2 legal actions" in rollout.problems[0]


def test_run_battle_agent_sweep_aggregates_battle_only_counts() -> None:
    report = run_battle_agent_sweep(
        FakeBattleAgentAdapter(),
        PreferredKindPolicy(),
        seeds=[1, 2],
        max_steps=3,
    )
    text = format_battle_agent_sweep_report(report)

    assert len(report.episodes) == 2
    assert report.terminal_episodes == 2
    assert report.total_steps == 6
    assert report.total_battle_decisions == 4
    assert report.total_autopilot_decisions == 2
    assert report.battle_action_kind_counts["card"] == 4
    assert report.autopilot_action_kind_counts["reward_gold"] == 2
    assert report.problems == []
    assert "Battle agent seed sweep summary" in text
    assert "total battle decisions: 4" in text


def _action(
    action_id: str,
    kind: str,
    scope: str,
) -> SimulatorAction:
    return SimulatorAction(
        action_id=action_id,
        label=action_id,
        kind=kind,
        raw={"scope": scope, "idx1": 0, "idx2": 0, "idx3": 0},
    )
