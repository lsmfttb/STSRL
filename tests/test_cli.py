from __future__ import annotations

import io
import sys

from sts_combat_rl.cli import main
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)


class FakeLightSpeedSmokeAdapter:
    def __init__(self, seed: int, ascension: int) -> None:
        self.seed = seed
        self.ascension = ascension
        self._checkpoint_counter = 0

    @property
    def checkpoint_adapter_id(self) -> str:
        return "fake-cli"

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[seed or self.seed],
            raw={
                "screen_state": "BATTLE",
                "outcome": "UNDECIDED",
                "battle_active": True,
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="battle:1",
                label="end",
                kind="end_turn",
                raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=[0],
                raw={
                    "screen_state": "BATTLE",
                    "outcome": "PLAYER_LOSS",
                    "battle_active": False,
                },
            ),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        self._checkpoint_counter += 1
        return SimulatorCheckpoint(
            adapter_id=self.checkpoint_adapter_id,
            checkpoint_id=f"fake-cli:{self._checkpoint_counter}",
            payload=None,
            metadata={"seed": self.seed, "snapshot": dict(snapshot.raw)},
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        if checkpoint.adapter_id != self.checkpoint_adapter_id:
            raise ValueError("foreign checkpoint")
        return self.reset(seed=checkpoint.metadata["seed"])


def test_cli_stdin_mode_sends_ready_signal_then_commands(monkeypatch) -> None:
    input_stream = io.StringIO(
        '{"screen_type":"COMBAT","hand":[{"name":"Strike","type":"ATTACK",'
        '"playable":true}],"monsters":[{"name":"Cultist","hp":10}]}\n'
    )
    output_stream = io.StringIO()
    monkeypatch.setattr(sys, "stdin", input_stream)
    monkeypatch.setattr(sys, "stdout", output_stream)

    assert main(["--log-file", "-"]) == 0

    assert output_stream.getvalue() == "ready_for_command\nplay 1 0\n"


def test_cli_capture_and_log_dirs_create_fresh_session_files(
    monkeypatch,
    tmp_path,
) -> None:
    raw_line = (
        '{"screen_type":"COMBAT","hand":[{"name":"Strike","type":"ATTACK",'
        '"playable":true}],"monsters":[{"name":"Cultist","hp":10}]}\n'
    )
    input_stream = io.StringIO(raw_line)
    output_stream = io.StringIO()
    capture_dir = tmp_path / "captures"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(sys, "stdin", input_stream)
    monkeypatch.setattr(sys, "stdout", output_stream)

    assert main(["--capture-dir", str(capture_dir), "--log-dir", str(log_dir)]) == 0

    capture_files = list(capture_dir.glob("capture_*.jsonl"))
    log_files = list(log_dir.glob("communicationmod_*.log"))
    assert output_stream.getvalue() == "ready_for_command\nplay 1 0\n"
    assert len(capture_files) == 1
    assert capture_files[0].read_text(encoding="utf-8") == raw_line
    assert len(log_files) == 1
    assert "capturing raw samples to" in log_files[0].read_text(encoding="utf-8")


def test_cli_manual_mode_polls_without_gameplay_actions(monkeypatch) -> None:
    input_stream = io.StringIO(
        '{"available_commands":["play","end","key","click","wait","state"],'
        '"game_state":{"room_phase":"COMBAT","action_phase":"WAITING_ON_USER",'
        '"combat_state":{"hand":[{"name":"Strike","type":"ATTACK",'
        '"is_playable":true}],"monsters":[{"name":"Cultist",'
        '"current_hp":10}]}}}\n'
    )
    output_stream = io.StringIO()
    monkeypatch.setattr(sys, "stdin", input_stream)
    monkeypatch.setattr(sys, "stdout", output_stream)

    assert main(["--manual", "--log-file", "-"]) == 0

    assert output_stream.getvalue() == "ready_for_command\nwait 30\n"


def test_cli_analyze_samples_writes_report_to_stderr_only(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    sample_file = tmp_path / "captured.jsonl"
    sample_file.write_text(
        '{"available_commands":["play","end","wait","state"],'
        '"game_state":{"room_phase":"COMBAT","action_phase":"WAITING_ON_USER",'
        '"combat_state":{"hand":[{"name":"Strike","type":"ATTACK",'
        '"is_playable":true}],"monsters":[{"name":"Cultist",'
        '"current_hp":10}]}}}\n',
        encoding="utf-8",
    )
    second_sample_file = tmp_path / "captured_2.jsonl"
    second_sample_file.write_text(
        sample_file.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    assert (
        main(
            [
                "--analyze-samples",
                str(sample_file),
                str(second_sample_file),
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Sample replay summary" in captured.err
    assert "paths: 2" in captured.err
    assert "play 1 0: 2" in captured.err


def test_cli_lightspeed_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert main(["--lightspeed-smoke", "--sim-steps", "1", "--log-file", "-"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Simulator calibration summary" in captured.err
    assert "excluded action kinds:" in captured.err
    assert "chosen action kinds:" in captured.err


def test_cli_checkpoint_commands_write_only_diagnostics_and_restore_pool(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    pool_path = tmp_path / "pool.jsonl"

    assert (
        main(
            [
                "--lightspeed-battle-checkpoint-verify",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    checkpoint_output = capsys.readouterr()
    assert checkpoint_output.out == ""
    assert "determinism gate passed: yes" in checkpoint_output.err

    assert (
        main(
            [
                "--lightspeed-battle-start-pool",
                str(pool_path),
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--battle-start-sample-count",
                "3",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    collect_output = capsys.readouterr()
    assert collect_output.out == ""
    assert pool_path.exists()
    assert "natural battle starts: 2" in collect_output.err

    assert (
        main(
            [
                "--lightspeed-battle-start-pool-restore",
                str(pool_path),
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    restore_output = capsys.readouterr()
    assert restore_output.out == ""
    assert "restore ok: yes" in restore_output.err


def test_cli_lightspeed_rollout_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(["--lightspeed-rollout-smoke", "--sim-steps", "1", "--log-file", "-"]) == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Simulator rollout summary" in captured.err
    assert "snapshot feature sizes:" in captured.err


def test_cli_lightspeed_batch_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-batch-smoke",
                "--sim-rollouts",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Decision batch summary" in captured.err
    assert "rollouts: 2" in captured.err


def test_cli_lightspeed_policy_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-policy-smoke",
                "--sim-policy",
                "replay-chosen",
                "--sim-rollouts",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Decision batch summary" in captured.err
    assert "Policy selection smoke summary" in captured.err
    assert "policy: replay_chosen" in captured.err
    assert "agreement with rollout: 2/2" in captured.err


def test_cli_lightspeed_policy_rollout_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-policy-rollout-smoke",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Simulator rollout summary" in captured.err
    assert "chosen action kinds:" in captured.err


def test_cli_lightspeed_episode_eval_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-episode-eval",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Policy episode evaluation summary" in captured.err
    assert "episodes: 2" in captured.err
    assert "outcomes:" in captured.err


def test_cli_lightspeed_battle_sweep_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-sweep",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Battle agent seed sweep summary" in captured.err
    assert "total battle decisions: 2" in captured.err
    assert "non-combat driver policy: stochastic_non_combat_v1" in captured.err
    assert "total non-combat driver decisions: 0" in captured.err


def test_cli_non_combat_calibration_reports_unreached_branches_without_failure(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-non-combat-calibration",
                "--sim-episodes",
                "1",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Stochastic non-combat driver calibration summary" in captured.err
    assert "driver/provenance validation passed: yes" in captured.err
    assert "unavailable structural categories:" in captured.err


def test_cli_lightspeed_battle_batch_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-batch-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Battle decision batch summary" in captured.err
    assert "source rollouts: 2" in captured.err
    assert "battle examples: 2" in captured.err


def test_cli_lightspeed_battle_segments_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-segments-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Battle segment calibration summary" in captured.err
    assert "source rollouts: 2" in captured.err
    assert "segments: 2" in captured.err


def test_cli_lightspeed_battle_reward_components_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-reward-components",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--reward-detail-limit",
                "0",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Battle reward component calibration summary" in captured.err
    assert "source rollouts: 2" in captured.err
    assert "components:" in captured.err
    assert "highlighted segments (limit 0):" in captured.err
    assert "  (disabled)" in captured.err


def test_cli_lightspeed_battle_reward_design_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-reward-design",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--reward-detail-limit",
                "0",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Battle reward design draft summary" in captured.err
    assert "reward preset: battle-v0" in captured.err
    assert "long-term ledger totals:" in captured.err
    assert "lowest-reward segments (limit 0):" in captured.err


def test_cli_lightspeed_battle_reward_batch_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-reward-batch-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Reward-labeled battle decision batch summary" in captured.err
    assert "labels aligned: yes" in captured.err
    assert "reward allocation: terminal_step" in captured.err
    assert "battle examples: 2" in captured.err


def test_cli_lightspeed_battle_trainer_input_contract_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-trainer-input-contract",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Trainer input contract summary" in captured.err
    assert "contract ok: yes" in captured.err
    assert "labels aligned: yes" in captured.err
    assert "battle examples: 2" in captured.err


def test_cli_lightspeed_battle_trainer_input_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-trainer-input-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Trainer input dataset smoke summary" in captured.err
    assert "contract ok: yes" in captured.err
    assert "JSONL round trip ok: yes" in captured.err
    assert "records: 2" in captured.err


def test_cli_lightspeed_battle_model_input_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-model-input-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Model input batch smoke summary" in captured.err
    assert "model input ok: yes" in captured.err
    assert "context rebuild ok: yes" in captured.err
    assert "examples: 2" in captured.err


def test_cli_lightspeed_battle_model_score_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-model-score-smoke",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--reward-detail-limit",
                "0",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Model score smoke summary" in captured.err
    assert "scoring ok: yes" in captured.err
    assert "agreement with collected actions: 2/2" in captured.err
    assert "selection examples (limit 0):" in captured.err


def test_cli_lightspeed_battle_training_readiness_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-training-readiness",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Training readiness summary" in captured.err
    assert "ready for first training: yes" in captured.err
    assert "checks:" in captured.err
    assert "limitations:" in captured.err


def test_cli_rejects_negative_reward_detail_limit(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-reward-components",
                "--reward-detail-limit",
                "-1",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--reward-detail-limit must be non-negative" in captured.err


def test_cli_lightspeed_battle_sweep_accepts_non_combat_policy(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-sweep",
                "--sim-non-combat-policy",
                "preferred-kind",
                "--sim-episodes",
                "1",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "non-combat driver policy: preferred_kind" in captured.err


def test_cli_lightspeed_battle_sweep_accepts_scorer_policy(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-battle-sweep",
                "--sim-policy",
                "action-kind-prior-scorer",
                "--sim-episodes",
                "1",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "battle policy: action_kind_prior_scorer" in captured.err


def test_cli_rejects_replay_policy_for_online_policy_rollout(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert (
        main(
            [
                "--lightspeed-policy-rollout-smoke",
                "--sim-policy",
                "replay-chosen",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "replay-chosen is only valid" in captured.err


def test_cli_calibrate_combat_features_writes_report_to_stderr_only(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    sample_file = tmp_path / "live.jsonl"
    sample_file.write_text(
        '{"game_state":{"act":1,"floor":1,"current_hp":80,"max_hp":80,'
        '"gold":99,"combat_state":{"draw_pile":[],"discard_pile":[],'
        '"exhaust_pile":[],"turn":1,"cards_discarded_this_turn":0,'
        '"times_damaged":0,"player":{"current_hp":80,"max_hp":80,'
        '"energy":3,"block":0},"hand":[],"monsters":[]}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    assert (
        main(["--calibrate-combat-features", str(sample_file), "--log-file", "-"]) == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "CommunicationMod feature calibration summary" in captured.err
    assert "feature sizes:" in captured.err
