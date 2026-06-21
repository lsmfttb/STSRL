from __future__ import annotations

from sts_combat_rl.sim.calibration import (
    choose_calibration_action,
    format_communicationmod_feature_calibration_report,
    format_simulator_calibration_report,
    format_tactical_feature_coverage_report,
    run_communicationmod_feature_calibration,
    run_communicationmod_tactical_feature_audit,
    run_simulator_calibration,
    run_tactical_feature_coverage_audit,
)
from sts_combat_rl.sim.features import communicationmod_battle_feature_size
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)


class FakeCalibrationAdapter:
    def __init__(self) -> None:
        self.last_action: SimulatorAction | None = None

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[80, 80, seed or 0],
            raw={
                "screen_state": "BATTLE",
                "outcome": "UNDECIDED",
                "battle_active": True,
                "battle_player": {"current_hp": 80, "energy": 3},
                "battle_hand": [{"type": "ATTACK", "playable": True}],
                "battle_monsters": [
                    {"current_hp": 51, "targetable": True, "intent": "ATTACK"}
                ],
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="battle:1",
                label="potion",
                kind="potion",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            ),
            SimulatorAction(
                action_id="battle:2",
                label="card",
                kind="card",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            ),
            SimulatorAction(
                action_id="battle:3",
                label="end",
                kind="end_turn",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            ),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.last_action = action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[70, 80, 7],
                raw={
                    "screen_state": "BATTLE",
                    "outcome": "PLAYER_VICTORY",
                    "battle_active": False,
                },
            ),
            terminal=True,
            info={},
        )


class FakeNonCombatCalibrationAdapter:
    def __init__(self) -> None:
        self.last_action: SimulatorAction | None = None

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        return SimulatorSnapshot(
            observation=[80],
            raw={
                "screen_state": "REWARDS",
                "outcome": "UNDECIDED",
                "battle_active": False,
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="game:1",
                label="potion reward",
                kind="reward_potion",
                raw={"scope": "game"},
            ),
            SimulatorAction(
                action_id="game:2",
                label="gold reward",
                kind="reward_gold",
                raw={"scope": "game"},
            ),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self.last_action = action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[80],
                raw={
                    "screen_state": "MAP_SCREEN",
                    "outcome": "PLAYER_VICTORY",
                    "battle_active": False,
                },
            ),
            terminal=True,
            info={},
        )


class FakeMissingIntentAdapter(FakeCalibrationAdapter):
    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        snapshot = super().reset(seed)
        snapshot.raw["battle_monsters"][0].pop("intent")
        return snapshot


def test_choose_calibration_action_prefers_non_potion_card() -> None:
    actions = FakeCalibrationAdapter().legal_actions(
        SimulatorSnapshot(observation=[], raw={})
    )

    action = choose_calibration_action(actions)

    assert action.kind == "card"


def test_choose_calibration_action_avoids_potion_rewards_when_possible() -> None:
    action = choose_calibration_action(
        [
            SimulatorAction(
                action_id="game:1",
                label="potion",
                kind="reward_potion",
                raw={"scope": "game"},
            ),
            SimulatorAction(
                action_id="game:2",
                label="gold",
                kind="reward_gold",
                raw={"scope": "game"},
            ),
        ]
    )

    assert action.kind == "reward_gold"


def test_run_simulator_calibration_summarizes_adapter_shapes() -> None:
    adapter = FakeCalibrationAdapter()

    report = run_simulator_calibration(adapter, seed=7, max_steps=1)
    text = format_simulator_calibration_report(report)

    assert adapter.last_action is not None
    assert adapter.last_action.kind == "card"
    assert report.executed_steps == 1
    assert report.terminal is True
    assert report.outcome == "PLAYER_VICTORY"
    assert report.chosen_action_kind_counts["card"] == 1
    assert report.legal_action_kind_counts["potion"] == 1
    assert report.eligible_action_kind_counts["card"] == 1
    assert report.eligible_action_kind_counts["end_turn"] == 1
    assert report.excluded_legal_action_kind_counts["potion"] == 1
    assert report.problems == []
    assert "Simulator calibration summary" in text
    assert "configured battle excluded action kinds:" in text
    assert "eligible action kinds:" in text
    assert "problems:\n  (none)" in text


def test_simulator_calibration_keeps_non_combat_potion_rewards_eligible() -> None:
    adapter = FakeNonCombatCalibrationAdapter()

    report = run_simulator_calibration(adapter, seed=7, max_steps=1)

    assert adapter.last_action is not None
    assert adapter.last_action.kind == "reward_potion"
    assert report.eligible_action_kind_counts["reward_potion"] == 1
    assert report.excluded_legal_action_kind_counts["reward_potion"] == 0


def test_tactical_feature_coverage_audit_reports_schema_missing_and_parity() -> None:
    report = run_tactical_feature_coverage_audit(
        FakeCalibrationAdapter(), seed=7, max_steps=1
    )
    text = format_tactical_feature_coverage_report(report)

    assert report.snapshot_count == 1
    assert report.legal_action_count == 3
    assert report.feature_schema_id == "public-tactical-v2"
    assert report.missing_field_counts["scalars.ascension"] == 1
    assert any(row["classification"] == "simulator_only" for row in report.field_parity)
    assert any(
        row["classification"] == "explicitly_unsupported" for row in report.field_parity
    )
    assert report.problems == []
    assert "Tactical feature coverage audit" in text
    assert "simulator/live field parity:" in text


def test_tactical_feature_coverage_audit_fails_without_simulator_intent() -> None:
    report = run_tactical_feature_coverage_audit(
        FakeMissingIntentAdapter(), seed=7, max_steps=1
    )

    assert report.missing_field_counts["monsters.intent"] == 1
    assert any(
        "required monster intent is absent" in problem for problem in report.problems
    )


def test_run_communicationmod_feature_calibration_counts_live_fields(
    tmp_path,
) -> None:
    sample_file = tmp_path / "live.jsonl"
    sample_file.write_text(
        '{"game_state":{"act":1,"floor":1,"current_hp":80,"max_hp":80,'
        '"gold":99,"combat_state":{"draw_pile":[],"discard_pile":[],'
        '"exhaust_pile":[],"turn":1,"cards_discarded_this_turn":0,'
        '"times_damaged":0,"player":{"current_hp":80,"max_hp":80,'
        '"energy":3,"block":0},"hand":[{"id":"Strike_R","name":"Strike",'
        '"type":"ATTACK","cost":1,"is_playable":true,"has_target":true,'
        '"exhausts":false,"ethereal":false}],"monsters":[{"id":"Cultist",'
        '"name":"Cultist","current_hp":48,"max_hp":48,"block":0,'
        '"intent":"ATTACK","move_base_damage":6,"move_hits":1,'
        '"powers":[]}]}}}\n',
        encoding="utf-8",
    )

    report = run_communicationmod_feature_calibration([sample_file])
    text = format_communicationmod_feature_calibration_report(report)

    assert report.combat_states == 1
    assert report.non_combat_states == 0
    assert report.feature_size_counts[str(communicationmod_battle_feature_size())] == 1
    assert report.present_field_counts["player.energy"] == 1
    assert report.present_field_counts["card.type"] == 1
    assert report.present_field_counts["monster.intent"] == 1
    assert report.missing_field_counts == {}
    assert report.problems == []
    assert "CommunicationMod feature calibration summary" in text
    assert "feature sizes:" in text

    tactical = run_communicationmod_tactical_feature_audit([sample_file])
    tactical_text = format_tactical_feature_coverage_report(tactical)

    assert tactical.snapshot_count == 1
    assert tactical.legal_action_count == 0
    assert tactical.problems == []
    assert "identity vocabulary: public-identity-v1" in tactical_text
