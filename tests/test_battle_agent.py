from __future__ import annotations

from sts_combat_rl.sim.battle_agent import (
    BATTLE_AGENT_CONTROLLER,
    NON_COMBAT_DRIVER_CONTROLLER,
    build_battle_decision_batch,
    build_battle_segment_report,
    collect_battle_agent_rollout,
    format_battle_decision_batch_report,
    format_battle_segment_report,
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
from sts_combat_rl.sim.reward_components import (
    build_battle_reward_component_report,
    format_battle_reward_component_report,
)


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
            max_hp = 80 if floor == 1 else 82
            gold = 99 if floor == 1 else 101
            return SimulatorSnapshot(
                observation=[floor],
                raw={
                    "screen_state": "BATTLE",
                    "outcome": "UNDECIDED",
                    "battle_active": True,
                    "floor_num": floor,
                    "cur_hp": 80 if floor == 1 else 75,
                    "max_hp": max_hp,
                    "gold": gold,
                    "potion_count": 1,
                    "battle_potion_count": 1,
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
                    "cur_hp": 75,
                    "max_hp": 82,
                    "gold": 101,
                    "potion_count": 1,
                },
            )
        return SimulatorSnapshot(
            observation=[2],
            raw={
                "screen_state": "BATTLE",
                "outcome": "PLAYER_LOSS",
                "battle_active": False,
                "floor_num": 2,
                "cur_hp": 0,
                "max_hp": 82,
                "gold": 101,
                "potion_count": 1,
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
        NON_COMBAT_DRIVER_CONTROLLER,
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


def test_build_battle_decision_batch_excludes_autopilot_steps() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    battle_batch = build_battle_decision_batch(rollouts)
    decision_batch = battle_batch.decision_batch
    text = format_battle_decision_batch_report(battle_batch)

    assert battle_batch.source_rollout_count == 1
    assert battle_batch.excluded_autopilot_steps == 1
    assert decision_batch.rollout_count == 1
    assert decision_batch.terminal_rollouts == 1
    assert len(decision_batch.examples) == 2
    assert {example.screen_state for example in decision_batch.examples} == {"BATTLE"}
    assert [example.chosen_action_kind for example in decision_batch.examples] == [
        "card",
        "card",
    ]
    assert decision_batch.snapshot_feature_size == lightspeed_battle_feature_size()
    assert decision_batch.action_feature_size == simulator_action_feature_size()
    assert decision_batch.problems == []
    assert "Battle decision batch summary" in text
    assert "excluded non-combat driver steps: 1" in text


def test_build_battle_segment_report_summarizes_combat_boundaries() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    report = build_battle_segment_report(rollouts)
    text = format_battle_segment_report(report)

    assert report.source_rollout_count == 1
    assert len(report.segments) == 2
    assert report.excluded_autopilot_steps == 1
    assert report.total_battle_decisions == 2
    assert report.end_reason_counts["nonterminal_battle_exit"] == 1
    assert report.end_reason_counts["terminal_loss"] == 1
    assert report.action_kind_counts["card"] == 2
    assert report.hp_delta_count == 2
    assert report.hp_delta_total == -80.0

    first, second = report.segments
    assert first.start_step_index == 0
    assert first.end_step_index == 0
    assert first.end_reason == "nonterminal_battle_exit"
    assert first.start_hp == 80.0
    assert first.end_hp == 75.0
    assert first.hp_delta == -5.0
    assert first.start_max_hp == 80.0
    assert first.end_max_hp == 82.0
    assert first.max_hp_delta == 2.0
    assert first.start_gold == 99.0
    assert first.end_gold == 101.0
    assert first.gold_delta == 2.0
    assert second.start_step_index == 2
    assert second.end_reason == "terminal_loss"
    assert second.start_hp == 75.0
    assert second.end_hp == 0.0
    assert second.hp_delta == -75.0
    assert "Battle segment calibration summary" in text
    assert "segments: 2" in text


def test_build_battle_reward_component_report_keeps_raw_components_unweighted() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    report = build_battle_reward_component_report(rollouts)
    text = format_battle_reward_component_report(report)

    assert report.source_rollout_count == 1
    assert report.segment_count == 2
    assert report.components["battle_success_proxy"].samples == 2
    assert report.components["battle_success_proxy"].total == 1.0
    assert report.components["terminal_loss"].total == 1.0
    assert report.components["hp_loss"].total == 80.0
    assert report.components["max_hp_delta"].total == 2.0
    assert report.components["gold_delta"].total == 2.0
    assert report.components["potion_count_delta"].samples == 2
    assert report.components["potion_count_delta"].total == 0.0
    assert "Battle reward component calibration summary" in text
    assert "no reward weights" in text
    assert "future signal gaps:" in text


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
