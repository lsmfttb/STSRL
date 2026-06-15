from __future__ import annotations

from sts_combat_rl.sim.battle_agent import (
    BATTLE_AGENT_CONTROLLER,
    BattleAgentRollout,
    BattleAgentRolloutStep,
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
from sts_combat_rl.sim.policy import (
    PolicyDecision,
    PreferredKindPolicy,
    choose_highest_scored_eligible_index,
)
from sts_combat_rl.sim.reward_components import (
    build_battle_reward_component_report,
    format_battle_reward_component_report,
)
from sts_combat_rl.sim.reward_design import (
    BattleRewardWeights,
    battle_reward_weights_from_preset,
    build_battle_reward_design_report,
    format_battle_reward_design_report,
)
from sts_combat_rl.sim.reward_labeling import (
    RewardLabeledBattleDecisionBatch,
    build_reward_labeled_battle_decision_batch,
    format_reward_labeled_battle_decision_batch_report,
)
from sts_combat_rl.sim.trainer_input_contract import (
    build_trainer_input_contract_report,
    format_trainer_input_contract_report,
)
from sts_combat_rl.sim.trainer_input import (
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    build_trainer_input_dataset,
    build_trainer_input_dataset_smoke_report,
    format_trainer_input_dataset_smoke_report,
    load_trainer_input_dataset_jsonl_text,
    trainer_input_dataset_to_jsonl_text,
)
from sts_combat_rl.sim.model_input import (
    MODEL_INPUT_BATCH_FORMAT_VERSION,
    ModelInputBatch,
    build_model_input_batch,
    build_model_input_batch_smoke_report,
    decision_context_from_model_input_batch,
    format_model_input_batch_smoke_report,
)
from sts_combat_rl.sim.model_scoring import (
    ActionKindPriorScorer,
    LinearActionScorer,
    format_model_score_smoke_report,
    score_model_input_batch,
)
from sts_combat_rl.sim.training_readiness import (
    build_training_readiness_report,
    format_training_readiness_report,
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

        return SimulatorTransition(
            snapshot=self._snapshot(), terminal=terminal, info={}
        )

    def _snapshot(self) -> SimulatorSnapshot:
        if self.phase.startswith("battle"):
            floor = 1 if self.phase == "battle-1" else 2
            max_hp = 80 if floor == 1 else 82
            gold = 101 if floor == 1 else 99
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
                    "gold": 99,
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
                "gold": 99,
                "potion_count": 1,
            },
        )


class BadBattlePolicy:
    name = "bad_battle"

    def select_action(self, context: object) -> PolicyDecision:
        del context
        return PolicyDecision(legal_action_index=8, reason="bad")


class FixedBatchScorer:
    name = "fixed_batch"

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def score_action_rows(self, batch: ModelInputBatch) -> list[float]:
        del batch
        return list(self._scores)


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
    assert (
        summary.battle_snapshot_feature_size_counts[
            str(lightspeed_battle_feature_size())
        ]
        == 2
    )
    assert (
        summary.battle_action_feature_size_counts[str(simulator_action_feature_size())]
        == 4
    )
    assert summary.problems == []


def test_collect_battle_agent_rollout_reports_battle_policy_errors() -> None:
    rollout = collect_battle_agent_rollout(
        FakeBattleAgentAdapter(),
        BadBattlePolicy(),
        seed=1,
        max_steps=3,
    )

    assert rollout.steps == []
    assert (
        "battle_agent selected action index 8 outside 2 legal actions"
        in rollout.problems[0]
    )


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
    assert first.start_gold == 101.0
    assert first.end_gold == 99.0
    assert first.gold_delta == -2.0
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
    assert report.components["gold_delta"].total == -2.0
    assert report.components["potion_count_delta"].samples == 2
    assert report.components["potion_count_delta"].total == 0.0
    assert report.highlight_counts["gold_delta"] == 1
    assert report.highlight_counts["max_hp_delta"] == 1
    assert report.highlight_counts["terminal_loss"] == 1
    assert len(report.highlights) == 2
    assert "Battle reward component calibration summary" in text
    assert "no reward weights" in text
    assert "highlighted segments (limit 8):" in text
    assert "gold_delta=-2.00" in text
    assert "future signal gaps:" in text


def test_build_battle_reward_design_report_scores_v0_without_long_term_weights() -> (
    None
):
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    report = build_battle_reward_design_report(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    text = format_battle_reward_design_report(report)

    assert report.source_rollout_count == 1
    assert report.segment_count == 2
    assert report.score_stats.samples == 2
    assert round(report.score_stats.total, 3) == -0.802
    assert report.contribution_totals["battle_success_proxy"] == 1.0
    assert report.contribution_totals["terminal_loss"] == -1.0
    assert round(report.contribution_totals["hp_delta"], 3) == -0.8
    assert round(report.contribution_totals["decision_count"], 3) == -0.002
    assert report.contribution_totals["gold_delta"] == 0.0
    assert report.long_term_ledger_totals["gold_delta"] == -2.0
    assert report.long_term_ledger_totals["max_hp_delta"] == 2.0
    assert report.problems == []
    assert "Battle reward design draft summary" in text
    assert "reward preset: battle-v0" in text
    assert "long-term ledger totals:" in text
    assert (
        "Long-term resource deltas are ledgered but have zero default weight." in text
    )


def test_battle_reward_design_can_enable_long_term_weights_without_shape_change() -> (
    None
):
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    report = build_battle_reward_design_report(
        rollouts,
        BattleRewardWeights(max_hp_delta=0.05, gold_delta=0.01),
    )

    assert round(report.contribution_totals["max_hp_delta"], 3) == 0.1
    assert round(report.contribution_totals["gold_delta"], 3) == -0.02
    assert round(report.score_stats.total, 3) == -0.722


def test_reward_labeled_battle_decision_batch_aligns_labels_with_examples() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    text = format_reward_labeled_battle_decision_batch_report(batch)

    assert batch.source_rollout_count == 1
    assert batch.segment_count == 2
    assert batch.excluded_non_combat_driver_steps == 1
    assert len(batch.decision_batch.examples) == 2
    assert len(batch.reward_labels) == 2
    assert batch.problems == []
    assert [label.step_index for label in batch.reward_labels] == [
        example.step_index for example in batch.decision_batch.examples
    ]
    assert [label.segment_index for label in batch.reward_labels] == [0, 1]
    assert all(label.is_segment_final_step for label in batch.reward_labels)
    assert round(sum(label.step_reward for label in batch.reward_labels), 3) == -0.802
    assert (
        round(
            sum(
                {
                    label.segment_index: label.segment_reward
                    for label in batch.reward_labels
                }.values()
            ),
            3,
        )
        == -0.802
    )
    assert batch.reward_labels[0].raw_reward_components["gold_delta"] == -2.0
    assert "Reward-labeled battle decision batch summary" in text
    assert "labels aligned: yes" in text
    assert "reward allocation: terminal_step" in text


def test_reward_labeled_batch_uses_terminal_step_allocation() -> None:
    rollout = BattleAgentRollout(
        seed=7,
        requested_steps=3,
        steps=[
            _battle_rollout_step(0, player_hp=80, next_player_hp=78),
            _battle_rollout_step(1, player_hp=78, next_player_hp=75),
            _non_combat_rollout_step(2),
        ],
        terminal=False,
        outcome="UNDECIDED",
    )

    batch = build_reward_labeled_battle_decision_batch(
        [rollout],
        battle_reward_weights_from_preset("battle-v0"),
    )
    labels = batch.reward_labels

    assert len(batch.decision_batch.examples) == 2
    assert len(labels) == 2
    assert labels[0].segment_step_index == 0
    assert labels[1].segment_step_index == 1
    assert labels[0].is_segment_final_step is False
    assert labels[1].is_segment_final_step is True
    assert labels[0].step_reward == 0.0
    assert round(labels[0].return_to_go, 3) == 0.948
    assert round(labels[1].step_reward, 3) == 0.948
    assert round(labels[1].return_to_go, 3) == 0.948
    assert labels[0].segment_reward == labels[1].segment_reward
    assert batch.problems == []


def test_trainer_input_contract_accepts_reward_labeled_battle_batch() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )

    report = build_trainer_input_contract_report(batch)
    text = format_trainer_input_contract_report(report)

    assert report.contract_ok is True
    assert report.example_count == 2
    assert report.reward_label_count == 2
    assert report.labels_aligned is True
    assert report.snapshot_feature_size == lightspeed_battle_feature_size()
    assert report.action_feature_size == simulator_action_feature_size()
    assert report.final_step_labels == 2
    assert report.nonfinal_step_labels == 0
    assert round(report.segment_reward_total, 3) == -0.802
    assert round(report.step_reward_total, 3) == -0.802
    assert report.screen_state_counts["BATTLE"] == 2
    assert report.problems == []
    assert "Trainer input contract summary" in text
    assert "contract ok: yes" in text


def test_trainer_input_contract_reports_label_alignment_problems() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    bad_batch = RewardLabeledBattleDecisionBatch(
        decision_batch=batch.decision_batch,
        reward_labels=batch.reward_labels[:-1],
        reward_design_report=batch.reward_design_report,
        source_rollout_count=batch.source_rollout_count,
        segment_count=batch.segment_count,
        excluded_non_combat_driver_steps=batch.excluded_non_combat_driver_steps,
        reward_allocation=batch.reward_allocation,
        problems=[],
    )

    report = build_trainer_input_contract_report(bad_batch)

    assert report.contract_ok is False
    assert report.labels_aligned is False
    assert any(
        "example/label length mismatch" in problem for problem in report.problems
    )
    assert any("final-step label count" in problem for problem in report.problems)


def test_trainer_input_dataset_round_trips_reward_labeled_battle_batch() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )

    dataset = build_trainer_input_dataset(batch)
    encoded = trainer_input_dataset_to_jsonl_text(dataset)
    loaded = load_trainer_input_dataset_jsonl_text(encoded)

    assert dataset.format_version == TRAINER_INPUT_DATASET_FORMAT_VERSION
    assert dataset.reward_allocation == "terminal_step"
    assert dataset.source_rollout_count == 1
    assert dataset.segment_count == 2
    assert dataset.snapshot_feature_size == lightspeed_battle_feature_size()
    assert dataset.action_feature_size == simulator_action_feature_size()
    assert len(dataset.records) == 2
    assert dataset.records[0].example_index == 0
    assert dataset.records[0].legal_action_kinds == ["end_turn", "card"]
    assert dataset.records[0].eligible_action_indices == [0, 1]
    assert dataset.records[0].chosen_action_index == 1
    assert dataset.records[0].segment_index == 0
    assert dataset.records[0].raw_reward_components["gold_delta"] == -2.0
    assert '"type":"metadata"' in encoded
    assert '"type":"record"' in encoded
    assert loaded == dataset


def test_trainer_input_dataset_smoke_report_checks_jsonl_round_trip() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )

    report = build_trainer_input_dataset_smoke_report(batch)
    text = format_trainer_input_dataset_smoke_report(report)

    assert report.contract_ok is True
    assert report.round_trip_ok is True
    assert report.record_count == 2
    assert report.max_legal_actions == 2
    assert report.max_eligible_actions == 2
    assert round(report.step_reward_total, 3) == -0.802
    assert report.problems == []
    assert "Trainer input dataset smoke summary" in text
    assert "JSONL round trip ok: yes" in text
    assert (
        "scope: dataset packaging only; no trainer, environment, or RL algorithm"
        in text
    )


def test_model_input_batch_packs_variable_action_rows_for_scorer_context() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    reward_batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    dataset = build_trainer_input_dataset(reward_batch)

    batch = build_model_input_batch(dataset)
    context = decision_context_from_model_input_batch(batch, 0)

    assert batch.format_version == MODEL_INPUT_BATCH_FORMAT_VERSION
    assert batch.reward_allocation == "terminal_step"
    assert len(batch.example_refs) == 2
    assert batch.snapshot_feature_size == lightspeed_battle_feature_size()
    assert batch.action_feature_size == simulator_action_feature_size()
    assert batch.action_offsets == [0, 2, 4]
    assert len(batch.action_features) == 4
    assert batch.action_kinds == [["end_turn", "card"], ["end_turn", "card"]]
    assert batch.eligible_action_indices == [[0, 1], [0, 1]]
    assert batch.eligible_action_rows == [[0, 1], [2, 3]]
    assert batch.chosen_action_indices == [1, 1]
    assert batch.chosen_action_rows == [1, 3]
    assert batch.chosen_action_kinds == ["card", "card"]
    assert round(sum(batch.step_rewards), 3) == -0.802
    assert batch.problems == []
    assert context.screen_state == "BATTLE"
    assert context.legal_action_kinds == ["end_turn", "card"]
    assert choose_highest_scored_eligible_index(context, [0.0, 1.0]) == 1


def test_model_input_batch_smoke_report_checks_rebuilt_contexts() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    reward_batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    dataset = build_trainer_input_dataset(reward_batch)

    report = build_model_input_batch_smoke_report(dataset)
    text = format_model_input_batch_smoke_report(report)

    assert report.model_input_ok is True
    assert report.context_rebuild_ok is True
    assert report.example_count == 2
    assert report.snapshot_rows == 2
    assert report.action_rows == 4
    assert report.action_offset_count == 3
    assert report.max_legal_actions == 2
    assert report.max_eligible_actions == 2
    assert round(report.step_reward_total, 3) == -0.802
    assert report.problems == []
    assert "Model input batch smoke summary" in text
    assert "model input ok: yes" in text
    assert "context rebuild ok: yes" in text
    assert (
        "scope: model input packaging only; no trainer, environment, or RL algorithm"
        in text
    )


def test_model_score_smoke_selects_eligible_argmax_action_rows() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]
    reward_batch = build_reward_labeled_battle_decision_batch(
        rollouts,
        battle_reward_weights_from_preset("battle-v0"),
    )
    model_batch = build_model_input_batch(build_trainer_input_dataset(reward_batch))

    report = score_model_input_batch(model_batch, ActionKindPriorScorer())
    text = format_model_score_smoke_report(report, detail_limit=1)

    assert report.scoring_ok is True
    assert report.example_count == 2
    assert report.action_rows == 4
    assert report.score_count == 4
    assert report.selection_count == 2
    assert report.chosen_action_agreement == 2
    assert report.min_score == 1.0
    assert report.max_score == 3.0
    assert report.selected_action_kind_counts["card"] == 2
    assert report.problems == []
    assert "Model score smoke summary" in text
    assert "scoring ok: yes" in text
    assert "agreement with collected actions: 2/2" in text
    assert "selection examples (limit 1):" in text


def test_model_score_smoke_ignores_high_scores_on_ineligible_rows() -> None:
    batch = ModelInputBatch(
        format_version=MODEL_INPUT_BATCH_FORMAT_VERSION,
        reward_allocation="terminal_step",
        snapshot_feature_size=2,
        action_feature_size=2,
        screen_states=["BATTLE"],
        snapshot_features=[[1.0, 2.0]],
        action_features=[[0.0, 0.0], [1.0, 1.0]],
        action_offsets=[0, 2],
        action_kinds=[["end_turn", "card"]],
        eligible_action_indices=[[1]],
        eligible_action_rows=[[1]],
        chosen_action_indices=[1],
        chosen_action_rows=[1],
        chosen_action_kinds=["card"],
        terminal_after_step=[False],
        step_rewards=[0.0],
        return_to_go=[1.0],
    )

    report = score_model_input_batch(batch, FixedBatchScorer([100.0, 2.0]))

    assert report.scoring_ok is True
    assert report.selection_count == 1
    assert report.selections[0].selected_action_index == 1
    assert report.selections[0].selected_action_row == 1
    assert report.selections[0].selected_action_kind == "card"
    assert report.selections[0].selected_score == 2.0
    assert report.chosen_action_agreement == 1
    assert report.problems == []


def test_linear_action_scorer_scores_model_input_batch_without_training() -> None:
    batch = ModelInputBatch(
        format_version=MODEL_INPUT_BATCH_FORMAT_VERSION,
        reward_allocation="terminal_step",
        snapshot_feature_size=2,
        action_feature_size=2,
        screen_states=["BATTLE"],
        snapshot_features=[[1.0, 2.0]],
        action_features=[[0.0, 1.0], [2.0, 0.0]],
        action_offsets=[0, 2],
        action_kinds=[["end_turn", "card"]],
        eligible_action_indices=[[0, 1]],
        eligible_action_rows=[[0, 1]],
        chosen_action_indices=[1],
        chosen_action_rows=[1],
        chosen_action_kinds=["card"],
        terminal_after_step=[False],
        step_rewards=[0.0],
        return_to_go=[1.0],
    )

    report = score_model_input_batch(
        batch,
        LinearActionScorer(
            snapshot_weights=[0.5, 0.0],
            action_weights=[1.0, -1.0],
            bias=0.25,
        ),
    )

    assert report.scoring_ok is True
    assert report.selection_count == 1
    assert report.selections[0].selected_action_index == 1
    assert report.selections[0].selected_score == 2.75
    assert report.problems == []


def test_model_score_smoke_reports_bad_score_shape_and_values() -> None:
    batch = ModelInputBatch(
        format_version=MODEL_INPUT_BATCH_FORMAT_VERSION,
        reward_allocation="terminal_step",
        snapshot_feature_size=2,
        action_feature_size=2,
        screen_states=["BATTLE"],
        snapshot_features=[[1.0, 2.0]],
        action_features=[[0.0, 0.0], [1.0, 1.0]],
        action_offsets=[0, 2],
        action_kinds=[["end_turn", "card"]],
        eligible_action_indices=[[0, 1]],
        eligible_action_rows=[[0, 1]],
        chosen_action_indices=[1],
        chosen_action_rows=[1],
        chosen_action_kinds=["card"],
        terminal_after_step=[False],
        step_rewards=[0.0],
        return_to_go=[1.0],
    )

    short_report = score_model_input_batch(batch, FixedBatchScorer([1.0]))
    nan_report = score_model_input_batch(batch, FixedBatchScorer([1.0, float("nan")]))

    assert short_report.scoring_ok is False
    assert short_report.selection_count == 0
    assert any("score count 1" in problem for problem in short_report.problems)
    assert nan_report.scoring_ok is False
    assert any("not finite" in problem for problem in nan_report.problems)


def test_model_score_smoke_reports_linear_scorer_dimension_errors() -> None:
    batch = ModelInputBatch(
        format_version=MODEL_INPUT_BATCH_FORMAT_VERSION,
        reward_allocation="terminal_step",
        snapshot_feature_size=2,
        action_feature_size=2,
        screen_states=["BATTLE"],
        snapshot_features=[[1.0, 2.0]],
        action_features=[[0.0, 0.0], [1.0, 1.0]],
        action_offsets=[0, 2],
        action_kinds=[["end_turn", "card"]],
        eligible_action_indices=[[0, 1]],
        eligible_action_rows=[[0, 1]],
        chosen_action_indices=[1],
        chosen_action_rows=[1],
        chosen_action_kinds=["card"],
        terminal_after_step=[False],
        step_rewards=[0.0],
        return_to_go=[1.0],
    )

    report = score_model_input_batch(
        batch,
        LinearActionScorer(snapshot_weights=[1.0]),
    )

    assert report.scoring_ok is False
    assert report.selection_count == 0
    assert any("snapshot weight size 1" in problem for problem in report.problems)


def test_training_readiness_report_accepts_full_pretrainer_path() -> None:
    rollouts = [
        collect_battle_agent_rollout(
            FakeBattleAgentAdapter(),
            PreferredKindPolicy(),
            seed=1,
            max_steps=3,
        )
    ]

    report = build_training_readiness_report(
        rollouts,
        weights=battle_reward_weights_from_preset("battle-v0"),
    )
    text = format_training_readiness_report(report)

    assert report.ready_for_first_training is True
    assert report.source_rollout_count == 1
    assert report.segment_count == 2
    assert report.battle_example_count == 2
    assert report.reward_label_count == 2
    assert report.trainer_record_count == 2
    assert report.model_example_count == 2
    assert report.action_row_count == 4
    assert report.score_count == 4
    assert report.snapshot_feature_size == lightspeed_battle_feature_size()
    assert report.action_feature_size == simulator_action_feature_size()
    assert report.trainer_contract_ok is True
    assert report.trainer_dataset_round_trip_ok is True
    assert report.model_input_ok is True
    assert report.model_context_rebuild_ok is True
    assert report.model_scoring_ok is True
    assert report.problems == []
    assert "Training readiness summary" in text
    assert "ready for first training: yes" in text
    assert "limitations:" in text


def test_training_readiness_report_blocks_empty_rollouts() -> None:
    report = build_training_readiness_report(
        [],
        weights=battle_reward_weights_from_preset("battle-v0"),
    )

    assert report.ready_for_first_training is False
    assert report.has_battle_examples is False
    assert any("battle examples present" in problem for problem in report.problems)


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


def _battle_rollout_step(
    step_index: int,
    *,
    player_hp: float,
    next_player_hp: float,
) -> BattleAgentRolloutStep:
    return BattleAgentRolloutStep(
        step_index=step_index,
        controller=BATTLE_AGENT_CONTROLLER,
        screen_state="BATTLE",
        snapshot_features=[1.0, float(step_index)],
        legal_action_features=[[1.0, 0.0], [0.0, 1.0]],
        legal_action_kinds=["end_turn", "card"],
        eligible_action_indices=[0, 1],
        chosen_action_index=1,
        chosen_action_id=f"card-{step_index}",
        chosen_action_kind="card",
        terminal_after_step=False,
        floor=1.0,
        player_hp=player_hp,
        player_max_hp=80.0,
        gold=99.0,
        potion_count=1.0,
        next_screen_state="BATTLE",
        next_floor=1.0,
        next_player_hp=next_player_hp,
        next_player_max_hp=80.0,
        next_gold=99.0,
        next_potion_count=1.0,
    )


def _non_combat_rollout_step(step_index: int) -> BattleAgentRolloutStep:
    return BattleAgentRolloutStep(
        step_index=step_index,
        controller=NON_COMBAT_DRIVER_CONTROLLER,
        screen_state="REWARDS",
        snapshot_features=[0.0, float(step_index)],
        legal_action_features=[[1.0, 0.0]],
        legal_action_kinds=["reward_gold"],
        eligible_action_indices=[0],
        chosen_action_index=0,
        chosen_action_id="gold",
        chosen_action_kind="reward_gold",
        terminal_after_step=False,
        floor=1.0,
        player_hp=75.0,
        player_max_hp=80.0,
        gold=99.0,
        potion_count=1.0,
        next_screen_state="BATTLE",
        next_floor=2.0,
        next_player_hp=75.0,
        next_player_max_hp=80.0,
        next_gold=99.0,
        next_potion_count=1.0,
    )
