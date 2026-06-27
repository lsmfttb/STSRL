from __future__ import annotations

from collections import Counter
import io
import os
from pathlib import Path
import subprocess
import sys

from sts_combat_rl.cli import build_parser, main
from sts_combat_rl.sim.constructed_battle_start import (
    ConstructedBattleStartAuditReport,
)
from sts_combat_rl.sim.battle_start_pool import load_natural_battle_start_pool_jsonl
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.native_public_projection import (
    NativePublicProjectionCapabilityReport,
)
from sts_combat_rl.sim.public_context_audit import (
    PublicContextArtifactAuditReport,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)


def test_cli_parser_keeps_lightspeed_training_flags() -> None:
    args = build_parser().parse_args(
        [
            "--lightspeed-battle-model-score-smoke",
            "--sim-seed",
            "7",
            "--sim-ascension",
            "20",
            "--sim-episodes",
            "2",
            "--reward-detail-limit",
            "0",
            "--log-file",
            "-",
        ]
    )

    assert args.lightspeed_battle_model_score_smoke is True
    assert args.sim_seed == 7
    assert args.sim_ascension == 20
    assert args.sim_episodes == 2
    assert args.reward_detail_limit == 0
    assert str(args.log_file) == "-"


def test_cli_parser_accepts_a20_coverage_flags(tmp_path) -> None:
    pool_path = tmp_path / "pool.jsonl"
    constructed_path = tmp_path / "constructed.jsonl"
    output_path = tmp_path / "coverage.json"

    args = build_parser().parse_args(
        [
            "--lightspeed-a20-battle-start-coverage",
            str(pool_path),
            "--a20-coverage-constructed-artifact",
            str(constructed_path),
            "--a20-coverage-output",
            str(output_path),
            "--battle-start-restore-limit",
            "2",
            "--battle-start-sample-count",
            "3",
            "--pytorch-gate-min-records",
            "4",
        ]
    )

    assert args.lightspeed_a20_battle_start_coverage == pool_path
    assert args.a20_coverage_constructed_artifact == constructed_path
    assert args.a20_coverage_output == output_path
    assert args.battle_start_restore_limit == 2
    assert args.battle_start_sample_count == 3
    assert args.pytorch_gate_min_records == 4


def test_cli_parser_accepts_t036_reachability_flags(tmp_path) -> None:
    default_pool = tmp_path / "default-pool.jsonl"
    default_coverage = tmp_path / "default-coverage.json"
    search_pool = tmp_path / "search-pool.jsonl"
    search_coverage = tmp_path / "search-coverage.json"
    report_path = tmp_path / "reachability.json"

    args = build_parser().parse_args(
        [
            "--a20-reachability-report",
            str(report_path),
            "--reachability-arm",
            "default",
            str(default_pool),
            str(default_coverage),
            "--reachability-arm",
            "oracle-no-potion",
            str(search_pool),
            str(search_coverage),
        ]
    )

    assert args.a20_reachability_report == report_path
    assert args.reachability_arm == [
        ["default", str(default_pool), str(default_coverage)],
        ["oracle-no-potion", str(search_pool), str(search_coverage)],
    ]


def test_cli_parser_accepts_oracle_teacher_scaleup_flags(tmp_path) -> None:
    pool_path = tmp_path / "pool.jsonl"
    output_dir = tmp_path / "scaleup"
    coverage_path = tmp_path / "coverage.json"

    args = build_parser().parse_args(
        [
            "--lightspeed-a20-oracle-teacher-scaleup",
            str(pool_path),
            "--oracle-teacher-scaleup-output-dir",
            str(output_dir),
            "--oracle-teacher-scaleup-budgets",
            "20",
            "50",
            "--oracle-teacher-scaleup-source-limit",
            "8",
            "--oracle-teacher-scaleup-seed",
            "3",
            "--oracle-teacher-scaleup-coverage-report",
            str(coverage_path),
            "--oracle-teacher-scaleup-root-selection",
            "most_visits",
        ]
    )

    assert args.lightspeed_a20_oracle_teacher_scaleup == pool_path
    assert args.oracle_teacher_scaleup_output_dir == output_dir
    assert args.oracle_teacher_scaleup_budgets == [20, 50]
    assert args.oracle_teacher_scaleup_source_limit == 8
    assert args.oracle_teacher_scaleup_source_selection == "seeded_uniform"
    assert args.oracle_teacher_scaleup_background_count == 64
    assert args.oracle_teacher_scaleup_seed == 3
    assert args.oracle_teacher_scaleup_coverage_report == coverage_path
    assert args.oracle_teacher_scaleup_root_selection == "most_visits"


def test_cli_parser_accepts_oracle_teacher_report_flags(tmp_path) -> None:
    teacher_path = tmp_path / "teacher.jsonl"
    pool_path = tmp_path / "pool.jsonl"
    coverage_path = tmp_path / "coverage.json"
    output_path = tmp_path / "teacher-report.json"

    args = build_parser().parse_args(
        [
            "--oracle-teacher-dataset-report",
            str(teacher_path),
            "--oracle-teacher-source-pool",
            str(pool_path),
            "--oracle-teacher-coverage-report",
            str(coverage_path),
            "--oracle-teacher-report-output",
            str(output_path),
        ]
    )

    assert args.oracle_teacher_dataset_report == teacher_path
    assert args.oracle_teacher_source_pool == pool_path
    assert args.oracle_teacher_coverage_report == coverage_path
    assert args.oracle_teacher_report_output == output_path


def test_cli_parser_accepts_oracle_teacher_search_guidance_flags(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "trainer.jsonl"
    report_path = tmp_path / "bridge-report.json"
    checkpoint_path = tmp_path / "checkpoint.pt"

    args = build_parser().parse_args(
        [
            "--oracle-teacher-search-guidance-input",
            str(manifest_path),
            "--oracle-teacher-search-guidance-budget",
            "100",
            "--oracle-teacher-search-guidance-output",
            str(output_path),
            "--oracle-teacher-search-guidance-target",
            "teacher_action_one_hot",
            "--oracle-teacher-search-guidance-stability-filter",
            "none",
            "--oracle-teacher-search-guidance-report-output",
            str(report_path),
            "--oracle-teacher-search-guidance-checkpoint-output",
            str(checkpoint_path),
            "--oracle-teacher-search-guidance-epochs",
            "1",
        ]
    )

    assert args.oracle_teacher_search_guidance_input == manifest_path
    assert args.oracle_teacher_search_guidance_budget == 100
    assert args.oracle_teacher_search_guidance_output == output_path
    assert args.oracle_teacher_search_guidance_target == "teacher_action_one_hot"
    assert args.oracle_teacher_search_guidance_stability_filter == "none"
    assert args.oracle_teacher_search_guidance_report_output == report_path
    assert args.oracle_teacher_search_guidance_checkpoint_output == checkpoint_path
    assert args.oracle_teacher_search_guidance_epochs == 1


def test_cli_parser_accepts_pytorch_inference_flags(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoint.pt"
    trainer_path = tmp_path / "trainer.jsonl"

    args = build_parser().parse_args(
        [
            "--pytorch-search-guidance-infer",
            str(checkpoint_path),
            "--pytorch-search-guidance-infer-trainer-input",
            str(trainer_path),
            "--pytorch-search-guidance-infer-example-index",
            "2",
        ]
    )

    assert args.pytorch_search_guidance_infer == checkpoint_path
    assert args.pytorch_search_guidance_infer_trainer_input == trainer_path
    assert args.pytorch_search_guidance_infer_example_index == 2


def test_cli_parser_accepts_model_guided_oracle_flags(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    checkpoint_path = tmp_path / "checkpoint.pt"
    comparison_path = tmp_path / "comparison.jsonl"

    args = build_parser().parse_args(
        [
            "--lightspeed-model-guided-oracle-fixed-evaluation",
            str(cohort_path),
            "--model-guided-oracle-checkpoint",
            str(checkpoint_path),
            "--model-guided-oracle-policy-probability-weight",
            "0.25",
        ]
    )

    assert args.lightspeed_model_guided_oracle_fixed_evaluation == cohort_path
    assert args.model_guided_oracle_checkpoint == checkpoint_path
    assert args.model_guided_oracle_policy_probability_weight == 0.25

    comparison_args = build_parser().parse_args(
        [
            "--lightspeed-model-guided-search-fixed-comparison",
            str(cohort_path),
            "--model-guided-oracle-checkpoint",
            str(checkpoint_path),
            "--model-guided-search-comparison-report",
            str(comparison_path),
            "--model-guided-search-comparison-scale",
            "fixed",
        ]
    )

    assert (
        comparison_args.lightspeed_model_guided_search_fixed_comparison == cohort_path
    )
    assert comparison_args.model_guided_oracle_checkpoint == checkpoint_path
    assert comparison_args.model_guided_search_comparison_report == comparison_path
    assert comparison_args.model_guided_search_comparison_scale == "fixed"


def test_cli_default_import_does_not_import_torch() -> None:
    repo_src = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_src)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            ("import sys; import sts_combat_rl.cli; print('torch' in sys.modules)"),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout == "False\n"


def test_cli_rejects_pytorch_inference_without_trainer_input(capsys) -> None:
    assert (
        main(
            [
                "--pytorch-search-guidance-infer",
                "checkpoint.pt",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --pytorch-search-guidance-infer-trainer-input" in captured.err


def test_cli_rejects_model_guided_oracle_without_checkpoint(
    tmp_path,
    capsys,
) -> None:
    cohort_path = tmp_path / "cohort.jsonl"

    assert (
        main(
            [
                "--lightspeed-model-guided-oracle-fixed-evaluation",
                str(cohort_path),
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --model-guided-oracle-checkpoint" in captured.err


def test_cli_rejects_model_guided_comparison_without_checkpoint(
    tmp_path,
    capsys,
) -> None:
    cohort_path = tmp_path / "cohort.jsonl"

    assert (
        main(
            [
                "--lightspeed-model-guided-search-fixed-comparison",
                str(cohort_path),
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --model-guided-oracle-checkpoint" in captured.err


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
                "ascension": self.ascension,
                "act": 1,
                "floor_num": 1,
                "room_type": "MONSTER",
                "encounter_id": "FakeEncounter",
                "cur_hp": 10,
                "max_hp": 80,
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id="battle:1",
                label="end",
                kind="end_turn",
                raw={"scope": "battle", "bits": 1, "idx1": 0, "idx2": 0, "idx3": 0},
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
                    "ascension": self.ascension,
                    "act": 1,
                    "floor_num": 1,
                    "room_type": "MONSTER",
                    "encounter_id": "FakeEncounter",
                    "cur_hp": 0,
                    "max_hp": 80,
                    "completed_battle_outcome": "PLAYER_LOSS",
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

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        return {
            "schema_id": "native-battle-search-root-v1",
            "native_api": "StepSimulator.battle_search.v1",
            "patch_identity": "sts_lightspeed_battle_search_root_v1",
            "information_regime": "full_simulator_state_oracle_like",
            "simulations_requested": simulations,
            "root_visits": simulations,
            "include_potions": False,
            "native_simulator_steps": 3,
            "model_calls": None,
            "best_action_value": 0.1,
            "min_action_value": 0.1,
            "outcome_player_hp": 1,
            "root_row_count": 1,
            "search_edge_count": 1,
            "unsearched_legal_action_count": 0,
            "unmapped_search_edge_count": 0,
            "root_rows": [
                {
                    "scope": "battle",
                    "bits": 1,
                    "kind": "end_turn",
                    "label": "end",
                    "idx1": 0,
                    "idx2": 0,
                    "idx3": 0,
                    "search_tree_present": True,
                    "search_edge_index": 0,
                    "visits": simulations,
                    "evaluation_sum": float(simulations) * 0.1,
                    "mean_value": 0.1,
                }
            ],
        }


def _cli_checkpoint() -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id="cli-checkpoint",
        checkpoint_path="/tmp/cli-checkpoint.pt",
        model_class="TinyPolicyValueNet",
        model_config={"hidden_size": 8},
        trainer_input_artifact_id="trainer-input-sha256:cli",
        trainer_input_sha256="cli",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="oracle_teacher_row.teacher_action",
        policy_target_kind_counts={"oracle_teacher_action_one_hot": 1},
        policy_target_source_counts={"oracle_teacher_row.teacher_action": 1},
        information_regime_counts={"normal_public_policy": 1},
        source_information_regime_counts={"full_simulator_state_oracle_like": 1},
        oracle_like_supervision=True,
        training_data_provenance={"artifact": "cli-test"},
    )


class _FakeCliGuidanceScorer:
    name = "fake_cli_guidance"
    checkpoint_provenance = _cli_checkpoint()

    def score_decision_context(self, context):
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.checkpoint_provenance,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=[
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=context.legal_action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=0.0,
                    policy_probability=1.0,
                    action_identity=_context_action_identity(context, index),
                )
                for index in range(len(context.legal_action_features))
            ],
            duration_ms=0.5,
        )


def _context_action_identity(context, index: int) -> dict:
    if index < len(context.tactical_legal_actions):
        identity = context.tactical_legal_actions[index].get("identity", {})
        if isinstance(identity, dict):
            return dict(identity)
    return {}


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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )

    assert main(["--lightspeed-smoke", "--sim-steps", "1", "--log-file", "-"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Simulator calibration summary" in captured.err
    assert "excluded action kinds:" in captured.err
    assert "chosen action kinds:" in captured.err


def test_cli_public_projection_audit_routes_and_writes_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    report = NativePublicProjectionCapabilityReport(
        requested_episodes=2,
        completed_episodes=2,
        max_steps=10,
        decisions_observed=2,
        candidate_parity_passes=2,
        checkpoint_passes=2,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_public_projection_capability_audit",
        lambda *args, **kwargs: report,
    )

    assert (
        main(
            [
                "--lightspeed-public-projection-capability-audit",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "10",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Native public-projection capability audit" in captured.err
    assert "episodes: 2/2" in captured.err


def test_cli_public_context_audit_routes_and_writes_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    report = PublicContextArtifactAuditReport(
        requested_episodes=2,
        completed_episodes=2,
        max_steps=10,
        decisions_observed=2,
        candidate_parity_passes=2,
        context_available_count=2,
        replay_checked_count=1,
        replay_matched_count=1,
        battle_start_record_count=1,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_public_context_audit",
        lambda *args, **kwargs: report,
    )

    assert (
        main(
            [
                "--lightspeed-public-context-audit",
                "--sim-episodes",
                "2",
                "--sim-steps",
                "10",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Public-context artifact replay audit" in captured.err
    assert "episodes: 2/2" in captured.err


def test_cli_checkpoint_commands_write_only_diagnostics_and_restore_pool(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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


def test_cli_search_battle_start_pool_uses_oracle_battle_child(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    pool_path = tmp_path / "search-pool.jsonl"

    assert (
        main(
            [
                "--lightspeed-search-battle-start-pool",
                str(pool_path),
                "--sim-episodes",
                "1",
                "--sim-steps",
                "1",
                "--oracle-search-simulations",
                "7",
                "--oracle-root-selection",
                "most_visits",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Natural battle-start checkpoint pool coverage" in captured.err
    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    assert len(pool.records) == 1
    battle_provenance = pool.records[0].source_battle_controller_provenance
    non_combat_provenance = pool.records[0].source_non_combat_controller_provenance
    assert battle_provenance["kind"] == "oracle_battle_search"
    assert battle_provenance["config"]["information_regime"] == (
        "full_simulator_state_oracle_like"
    )
    assert battle_provenance["config"]["search_budget"]["simulations"] == 7
    assert battle_provenance["config"]["root_selection_rule"] == "most_visits"
    assert non_combat_provenance["kind"] == "decision_policy"
    assert non_combat_provenance["name"] == "stochastic_non_combat_v1"
    assert pool.source_run_summaries[0].final_floor == 1.0


def test_cli_constructed_battle_start_audit_writes_stderr_and_artifact(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    def fake_audit(**kwargs):
        calls["source_pool_path"] = kwargs["source_pool_path"]
        return (
            object(),
            ConstructedBattleStartAuditReport(
                source_record_count=1,
                audit_record_count=3,
                constructed_record_count=1,
                first_battle_source_count=0,
                later_battle_source_count=1,
                transform_policy={"version": "constructed_battle_start_v1", "seed": 1},
                distribution_counts=Counter(
                    {"natural_run": 1, "constructed_supplement": 1}
                ),
            ),
        )

    def fake_write(path, artifact):
        calls["written_artifact"] = artifact
        path.write_text("fake\n", encoding="utf-8")

    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_constructed_battle_start_audit",
        fake_audit,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.write_constructed_battle_start_artifact",
        fake_write,
    )
    output_path = tmp_path / "constructed.jsonl"
    pool_path = tmp_path / "pool.jsonl"

    assert (
        main(
            [
                "--lightspeed-constructed-battle-start-audit",
                "--constructed-start-output",
                str(output_path),
                "--constructed-start-pool",
                str(pool_path),
                "--sim-ascension",
                "20",
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
    assert output_path.exists()
    assert calls["source_pool_path"] == pool_path
    assert "written_artifact" in calls
    assert "Constructed battle-start supplement audit" in captured.err
    assert "source natural battle starts: 1" in captured.err


def test_cli_a20_coverage_writes_stderr_and_optional_json(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    class FakeCoverageReport:
        command_passed = True

    def fake_coverage(**kwargs):
        calls.update(kwargs)
        output_path = kwargs["output_path"]
        if output_path is not None:
            output_path.write_text('{"schema_id":"fixture"}\n', encoding="utf-8")
        return FakeCoverageReport()

    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_a20_battle_start_coverage_from_paths",
        fake_coverage,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.format_a20_battle_start_coverage_report",
        lambda report: "A20 battle-start coverage report\ncommand passed: yes",
    )
    pool_path = tmp_path / "pool.jsonl"
    constructed_path = tmp_path / "constructed.jsonl"
    output_path = tmp_path / "coverage.json"

    assert (
        main(
            [
                "--lightspeed-a20-battle-start-coverage",
                str(pool_path),
                "--a20-coverage-constructed-artifact",
                str(constructed_path),
                "--a20-coverage-output",
                str(output_path),
                "--battle-start-restore-limit",
                "2",
                "--battle-start-sample-count",
                "3",
                "--pytorch-gate-required-acts",
                "1",
                "2",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert output_path.exists()
    assert calls["pool_path"] == pool_path
    assert calls["constructed_artifact_path"] == constructed_path
    assert calls["output_path"] == output_path
    assert calls["restore_limit"] == 2
    assert calls["sample_count"] == 3
    assert calls["gate_config"].required_acts == (1, 2)
    assert calls["adapter_factory"]().ascension == 20
    assert "A20 battle-start coverage report" in captured.err


def test_cli_a20_coverage_returns_nonzero_for_command_problem(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    class FakeCoverageReport:
        command_passed = False

    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_a20_battle_start_coverage_from_paths",
        lambda **kwargs: FakeCoverageReport(),
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.format_a20_battle_start_coverage_report",
        lambda report: "A20 battle-start coverage report\ncommand passed: no",
    )

    assert (
        main(
            [
                "--lightspeed-a20-battle-start-coverage",
                str(tmp_path / "pool.jsonl"),
                "--log-file",
                "-",
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "command passed: no" in captured.err


def test_cli_oracle_teacher_scaleup_routes_to_lightspeed_command(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    class FakeScaleupManifest:
        command_passed = True

    def fake_scaleup(**kwargs):
        calls.update(kwargs)
        return FakeScaleupManifest()

    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_oracle_teacher_scaleup_from_paths",
        fake_scaleup,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.format_oracle_teacher_scaleup_command",
        lambda manifest: "A20 Oracle teacher scale-up\ncommand passed: yes",
    )
    pool_path = tmp_path / "pool.jsonl"
    output_dir = tmp_path / "scaleup"
    coverage_path = tmp_path / "coverage.json"

    assert (
        main(
            [
                "--lightspeed-a20-oracle-teacher-scaleup",
                str(pool_path),
                "--oracle-teacher-scaleup-output-dir",
                str(output_dir),
                "--oracle-teacher-scaleup-budgets",
                "20",
                "50",
                "--oracle-teacher-scaleup-source-limit",
                "4",
                "--oracle-teacher-scaleup-seed",
                "9",
                "--oracle-teacher-scaleup-coverage-report",
                str(coverage_path),
                "--oracle-teacher-scaleup-root-selection",
                "most_visits",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert calls["adapter_factory"]().ascension == 20
    assert calls["pool_path"] == pool_path
    assert calls["output_dir"] == output_dir
    assert calls["budgets"] == [20, 50]
    assert calls["source_limit"] == 4
    assert calls["selection_seed"] == 9
    assert calls["source_selection_mode"] == "seeded_uniform"
    assert calls["background_source_count"] == 64
    assert calls["coverage_report_path"] == coverage_path
    assert calls["root_selection_rule"] == "most_visits"
    assert "A20 Oracle teacher scale-up" in captured.err


def test_cli_oracle_teacher_scaleup_routes_t032_selection(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    class FakeScaleupManifest:
        command_passed = True

    def fake_scaleup(**kwargs):
        calls.update(kwargs)
        return FakeScaleupManifest()

    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.run_oracle_teacher_scaleup_from_paths",
        fake_scaleup,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.format_oracle_teacher_scaleup_command",
        lambda manifest: "A20 Oracle teacher scale-up\ncommand passed: yes",
    )

    assert (
        main(
            [
                "--lightspeed-a20-oracle-teacher-scaleup",
                str(tmp_path / "pool.jsonl"),
                "--oracle-teacher-scaleup-output-dir",
                str(tmp_path / "scaleup"),
                "--oracle-teacher-scaleup-source-selection",
                "t032_t039_narrow",
                "--oracle-teacher-scaleup-background-count",
                "64",
                "--oracle-teacher-scaleup-seed",
                "32039",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert calls["source_limit"] is None
    assert calls["selection_seed"] == 32039
    assert calls["source_selection_mode"] == "t032_t039_narrow"
    assert calls["background_source_count"] == 64


def test_cli_oracle_teacher_scaleup_rejects_t032_source_limit(capsys) -> None:
    assert (
        main(
            [
                "--lightspeed-a20-oracle-teacher-scaleup",
                "pool.jsonl",
                "--oracle-teacher-scaleup-output-dir",
                "scaleup",
                "--oracle-teacher-scaleup-source-selection",
                "t032_t039_narrow",
                "--oracle-teacher-scaleup-source-limit",
                "8",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not compatible" in captured.err


def test_cli_oracle_teacher_scaleup_rejects_nonpositive_background_count(
    capsys,
) -> None:
    assert (
        main(
            [
                "--lightspeed-a20-oracle-teacher-scaleup",
                "pool.jsonl",
                "--oracle-teacher-scaleup-output-dir",
                "scaleup",
                "--oracle-teacher-scaleup-background-count",
                "0",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--oracle-teacher-scaleup-background-count must be positive" in captured.err


def test_cli_oracle_teacher_scaleup_rejects_t032_selection_without_scaleup(
    capsys,
) -> None:
    assert (
        main(
            [
                "--oracle-teacher-scaleup-source-selection",
                "t032_t039_narrow",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--oracle-teacher-scaleup-source-selection" in captured.err
    assert "--lightspeed-a20-oracle-teacher-scaleup" in captured.err


def test_cli_oracle_teacher_scaleup_rejects_background_count_without_scaleup(
    capsys,
) -> None:
    assert (
        main(
            [
                "--oracle-teacher-scaleup-background-count",
                "32",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--oracle-teacher-scaleup-background-count" in captured.err
    assert "--lightspeed-a20-oracle-teacher-scaleup" in captured.err


def test_cli_oracle_teacher_scaleup_requires_output_dir(capsys) -> None:
    assert (
        main(
            [
                "--lightspeed-a20-oracle-teacher-scaleup",
                "pool.jsonl",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --oracle-teacher-scaleup-output-dir" in captured.err


def test_cli_oracle_teacher_search_guidance_routes_to_command(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    class FakeBridgeReport:
        command_passed = True

    def fake_bridge(**kwargs):
        calls.update(kwargs)
        return FakeBridgeReport()

    monkeypatch.setattr(
        "sts_combat_rl.sim.lightspeed.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.run_oracle_teacher_search_guidance_from_paths",
        fake_bridge,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_oracle_teacher_search_guidance_command",
        lambda report: "Oracle teacher search-guidance bridge\ncommand passed: yes",
    )
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "trainer.jsonl"
    report_path = tmp_path / "bridge-report.json"

    assert (
        main(
            [
                "--oracle-teacher-search-guidance-input",
                str(manifest_path),
                "--oracle-teacher-search-guidance-budget",
                "50",
                "--oracle-teacher-search-guidance-output",
                str(output_path),
                "--oracle-teacher-search-guidance-target",
                "teacher_action_one_hot",
                "--oracle-teacher-search-guidance-stability-filter",
                "none",
                "--oracle-teacher-search-guidance-report-output",
                str(report_path),
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert calls["adapter_factory"]().ascension == 20
    assert calls["manifest_path"] == manifest_path
    assert calls["selected_budget"] == 50
    assert calls["output_path"] == output_path
    assert calls["target"] == "teacher_action_one_hot"
    assert calls["stability_filter"] == "none"
    assert calls["report_output_path"] == report_path
    assert calls["checkpoint_output_path"] is None
    assert calls["training_config"] is None
    assert "Oracle teacher search-guidance bridge" in captured.err


def test_cli_oracle_teacher_search_guidance_requires_outputs(capsys) -> None:
    assert (
        main(
            [
                "--oracle-teacher-search-guidance-input",
                "manifest.json",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --oracle-teacher-search-guidance-output" in captured.err


def test_cli_teacher_guidance_calibration_routes_to_command(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: dict[str, object] = {}

    class FakeCalibrationReport:
        command_passed = True

    def fake_calibration(**kwargs):
        calls.update(kwargs)
        return FakeCalibrationReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_teacher_guidance_calibration_from_paths",
        fake_calibration,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_teacher_guidance_calibration_command",
        lambda report, *, detail_limit: (
            "Teacher guidance calibration report\ncommand passed: yes"
        ),
    )
    trainer_path = tmp_path / "teacher-guidance-trainer.jsonl"
    checkpoint_a = tmp_path / "checkpoint-a.pt"
    checkpoint_b = tmp_path / "checkpoint-b.pt"
    report_path = tmp_path / "calibration-report.json"

    assert (
        main(
            [
                "--teacher-guidance-calibration-report",
                str(trainer_path),
                "--teacher-guidance-calibration-checkpoint",
                str(checkpoint_a),
                "--teacher-guidance-calibration-checkpoint",
                str(checkpoint_b),
                "--teacher-guidance-calibration-output",
                str(report_path),
                "--teacher-guidance-calibration-top-k",
                "2",
                "--reward-detail-limit",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert calls["trainer_input_path"] == trainer_path
    assert calls["checkpoint_paths"] == [checkpoint_a, checkpoint_b]
    assert calls["output_path"] == report_path
    assert calls["top_k"] == 2
    assert "Teacher guidance calibration report" in captured.err


def test_cli_teacher_guidance_calibration_requires_checkpoint(capsys) -> None:
    assert (
        main(
            [
                "--teacher-guidance-calibration-report",
                "trainer.jsonl",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --teacher-guidance-calibration-checkpoint" in captured.err


def test_cli_oracle_search_teacher_and_fixed_eval_routes_write_stderr_only(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    pool_path = tmp_path / "pool.jsonl"
    teacher_path = tmp_path / "teacher.jsonl"
    cohort_path = tmp_path / "cohort.jsonl"
    checkpoint_path = tmp_path / "checkpoint.pt"

    assert (
        main(
            [
                "--lightspeed-battle-start-pool",
                str(pool_path),
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
    capsys.readouterr()

    assert (
        main(
            [
                "--lightspeed-oracle-search-teacher",
                str(pool_path),
                "--oracle-teacher-output",
                str(teacher_path),
                "--oracle-search-simulations",
                "3",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    teacher_output = capsys.readouterr()
    assert teacher_output.out == ""
    assert teacher_path.exists()
    assert "Oracle search teacher collection" in teacher_output.err
    assert "records: 1" in teacher_output.err
    assert "native simulator steps: 3" in teacher_output.err

    assert (
        main(
            [
                "--lightspeed-fixed-battle-evaluation",
                str(pool_path),
                "--fixed-evaluation-cohort",
                str(cohort_path),
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "--lightspeed-oracle-fixed-evaluation",
                str(cohort_path),
                "--oracle-root-selection",
                "most_visits",
                "--oracle-search-simulations",
                "3",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    fixed_output = capsys.readouterr()
    assert fixed_output.out == ""
    assert "sts_lightspeed source identity" in fixed_output.err
    assert "Fixed battle evaluation report" in fixed_output.err
    assert "controller: oracle_search_v1_most_visits_s3" in fixed_output.err

    monkeypatch.setattr(
        (
            "sts_combat_rl.commands.lightspeed_cli."
            "build_torch_guidance_scorer_from_checkpoint"
        ),
        lambda path: _FakeCliGuidanceScorer(),
    )
    assert (
        main(
            [
                "--lightspeed-model-guided-oracle-fixed-evaluation",
                str(cohort_path),
                "--model-guided-oracle-checkpoint",
                str(checkpoint_path),
                "--oracle-search-simulations",
                "3",
                "--sim-steps",
                "1",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    model_guided_output = capsys.readouterr()
    assert model_guided_output.out == ""
    assert "Model-guided Oracle fixed evaluation smoke" in model_guided_output.err
    assert "full_simulator_state_oracle_like diagnostics only" in (
        model_guided_output.err
    )
    assert "controller: model_guided_oracle_search_v1_s3_pw0.05" in (
        model_guided_output.err
    )
    assert "model calls: total=1" in model_guided_output.err

    comparison_path = tmp_path / "model-guided-comparison.jsonl"
    assert (
        main(
            [
                "--lightspeed-model-guided-search-fixed-comparison",
                str(cohort_path),
                "--model-guided-oracle-checkpoint",
                str(checkpoint_path),
                "--oracle-search-simulations",
                "3",
                "--sim-steps",
                "1",
                "--model-guided-search-comparison-report",
                str(comparison_path),
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    comparison_output = capsys.readouterr()
    assert comparison_output.out == ""
    assert comparison_path.exists()
    assert "Model-guided search fixed-cohort comparison" in comparison_output.err
    assert "run scale: smoke-scale" in comparison_output.err
    assert "source starts matched: yes" in comparison_output.err
    assert "model calls: total=1" in comparison_output.err
    assert '"schema_id": "model-guided-search-fixed-comparison-v1"' in (
        comparison_path.read_text(encoding="utf-8")
    )


def test_cli_oracle_teacher_dataset_report_writes_stderr_and_json(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
        FakeLightSpeedSmokeAdapter,
    )
    pool_path = tmp_path / "pool.jsonl"
    teacher_path = tmp_path / "teacher.jsonl"
    report_path = tmp_path / "teacher-report.json"

    assert (
        main(
            [
                "--lightspeed-battle-start-pool",
                str(pool_path),
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
    capsys.readouterr()

    assert (
        main(
            [
                "--lightspeed-oracle-search-teacher",
                str(pool_path),
                "--oracle-teacher-output",
                str(teacher_path),
                "--oracle-search-simulations",
                "3",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "--oracle-teacher-dataset-report",
                str(teacher_path),
                "--oracle-teacher-source-pool",
                str(pool_path),
                "--oracle-teacher-report-output",
                str(report_path),
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert report_path.exists()
    assert "Oracle teacher dataset report" in captured.err
    assert "command passed: yes" in captured.err
    assert "not normal-information" in captured.err
    assert '"schema_id": "oracle-teacher-dataset-report-v1"' in (
        report_path.read_text(encoding="utf-8")
    )


def test_cli_oracle_teacher_requires_output_path(capsys) -> None:
    assert (
        main(
            [
                "--lightspeed-oracle-search-teacher",
                "pool.jsonl",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --oracle-teacher-output" in captured.err


def test_cli_oracle_teacher_report_coverage_requires_source_pool(capsys) -> None:
    assert (
        main(
            [
                "--oracle-teacher-dataset-report",
                "teacher.jsonl",
                "--oracle-teacher-coverage-report",
                "coverage.json",
                "--log-file",
                "-",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "requires --oracle-teacher-source-pool" in captured.err


def test_cli_lightspeed_rollout_smoke_writes_report_to_stderr_only(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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
        "sts_combat_rl.commands.lightspeed_cli.LightSpeedAdapter",
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


def test_cli_audits_versioned_tactical_live_features_to_stderr_only(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    sample_file = tmp_path / "live.jsonl"
    sample_file.write_text(
        '{"game_state":{"act":1,"floor":1,"current_hp":80,"max_hp":80,'
        '"gold":99,"combat_state":{"draw_pile":[],"discard_pile":[],'
        '"exhaust_pile":[],"turn":1,"player":{"current_hp":80,'
        '"max_hp":80,"energy":3,"block":0},"hand":[],"monsters":[]}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    assert main(["--audit-tactical-features", str(sample_file), "--log-file", "-"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Tactical feature coverage audit" in captured.err
    assert "feature schema: public-tactical-v2 v2" in captured.err
