"""Command-line entrypoint for the communication probe."""

from __future__ import annotations

import json
import sys

from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_paths import timestamped_path
from sts_combat_rl.commands.cli_policies import build_pytorch_gate_config
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.a20_coverage import (
    merge_a20_battle_start_coverage_from_paths,
)
from sts_combat_rl.commands.assisted_source_generation import (
    format_assisted_coverage_report,
    format_assisted_source_pool_merge_report,
    merge_assisted_a20_coverage_from_paths,
    merge_assisted_source_pool_from_paths,
    run_assisted_source_coverage_report_from_paths,
)
from sts_combat_rl.commands.checkpoint_pool import (
    format_battle_start_pool_shard_merge_report,
    merge_checkpoint_pool_shards_from_paths,
)
from sts_combat_rl.commands.expert_source_coverage import (
    run_expert_source_coverage_report_from_paths,
)
from sts_combat_rl.commands.lightspeed_cli import (
    is_lightspeed_command,
    run_lightspeed_command,
)
from sts_combat_rl.commands.oracle_teacher_report import (
    format_oracle_teacher_dataset_report_command,
    run_oracle_teacher_dataset_report_from_paths,
)
from sts_combat_rl.commands.oracle_teacher_search_guidance import (
    format_oracle_teacher_search_guidance_command,
    run_oracle_teacher_search_guidance_from_paths,
)
from sts_combat_rl.commands.pytorch_search_guidance import (
    build_trainer_input_preflight_from_path,
    format_pytorch_search_guidance_inference_workflow_report,
    format_pytorch_search_guidance_training_workflow_report,
    format_trainer_input_preflight_from_path_report,
    run_pytorch_search_guidance_inference_from_paths,
    run_pytorch_search_guidance_training_from_path,
)
from sts_combat_rl.commands.post_t044_failure_analysis import (
    format_post_t044_failure_analysis_command,
    run_post_t044_failure_analysis_from_paths,
)
from sts_combat_rl.commands.reachability import run_a20_reachability_report_from_paths
from sts_combat_rl.commands.root_prior_guided_search_comparison import (
    merge_root_prior_guided_search_comparison_reports_from_paths,
)
from sts_combat_rl.commands.t052_fixed_cohort_diagnostic import (
    format_t052_fixed_cohort_extraction_command,
    format_t052_retention_manifest_command,
    run_t052_fixed_cohort_extraction_from_paths,
    run_t052_retention_manifest_from_paths,
)
from sts_combat_rl.commands.t053_root_prior_failure_analysis import (
    format_t053_root_prior_failure_analysis_command,
    run_t053_root_prior_failure_analysis_from_paths,
)
from sts_combat_rl.commands.t054_guardrailed_root_prior_repair import (
    format_t054_guardrailed_root_prior_repair_command,
    format_t054_retention_manifest_command,
    run_t054_guardrailed_root_prior_repair_from_paths,
    run_t054_retention_manifest_from_paths,
)
from sts_combat_rl.commands.t055_guardrailed_root_prior_scale_validation import (
    format_t055_guardrailed_root_prior_scale_validation_command,
    format_t055_retention_manifest_command,
    run_t055_guardrailed_root_prior_scale_validation_from_paths,
    run_t055_retention_manifest_from_paths,
)
from sts_combat_rl.commands.teacher_guidance_calibration import (
    format_teacher_guidance_calibration_command,
    run_teacher_guidance_calibration_from_paths,
)
from sts_combat_rl.comm.protocol import format_command, format_ready_signal
from sts_combat_rl.comm.stdio_client import StdioClient
from sts_combat_rl.logging_utils import DEFAULT_LOG_FILE, configure_logging
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.samples import analyze_sample_paths, format_sample_analysis
from sts_combat_rl.sim.a20_battle_start_coverage import (
    format_a20_battle_start_coverage_report,
)
from sts_combat_rl.sim.calibration import (
    format_communicationmod_feature_calibration_report,
    format_tactical_feature_coverage_report,
    run_communicationmod_feature_calibration,
    run_communicationmod_tactical_feature_audit,
)
from sts_combat_rl.sim.reachability import (
    format_a20_reachability_comparison_report,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    format_root_prior_guided_search_comparison_report,
)
from sts_combat_rl.sim.expert_source_coverage import (
    format_expert_source_coverage_comparison_report,
)
from sts_combat_rl.sim.assisted_source_generation import (
    format_assisted_source_coverage_comparison_report,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.log_file is not None and args.log_dir is not None:
        print("use either --log-file or --log-dir, not both", file=sys.stderr)
        return 2

    capture_file = args.capture_file
    if args.capture_dir is not None:
        capture_file = timestamped_path(args.capture_dir, "capture", ".jsonl")

    log_file_arg = args.log_file
    if args.log_dir is not None:
        log_file_arg = timestamped_path(args.log_dir, "communicationmod", ".log")
    elif log_file_arg is None:
        log_file_arg = DEFAULT_LOG_FILE

    log_file = None if str(log_file_arg) == "-" else log_file_arg
    logger = configure_logging(log_file)
    if capture_file is not None:
        logger.info("capturing raw samples to %s", capture_file)
    if log_file is not None:
        logger.info("writing debug log to %s", log_file)
    if args.manual:
        logger.info(
            "manual capture mode enabled; emitting only wait/state poll commands"
        )

    validation_problem = validate_cli_args(args)
    if validation_problem is not None:
        print(validation_problem, file=sys.stderr)
        return 2

    policy = ScriptedCombatPolicy()
    client = StdioClient(
        policy=policy,
        logger=logger,
        sample_capture_file=capture_file,
        manual_mode=args.manual,
    )

    if args.analyze_samples is not None:
        try:
            analysis = analyze_sample_paths(args.analyze_samples, policy=policy)
        except OSError as exc:
            print(f"failed to read sample files: {exc}", file=sys.stderr)
            return 2

        print(format_sample_analysis(analysis), file=sys.stderr)
        return 0

    if args.trainer_input_preflight is not None:
        try:
            report = build_trainer_input_preflight_from_path(
                args.trainer_input_preflight,
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
        except (OSError, ValueError) as exc:
            print(f"failed to run trainer input preflight: {exc}", file=sys.stderr)
            return 2
        print(
            format_trainer_input_preflight_from_path_report(
                report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
        return 0 if report.preflight_ok else 2

    if args.pytorch_search_guidance_infer is not None:
        try:
            report = run_pytorch_search_guidance_inference_from_paths(
                args.pytorch_search_guidance_infer,
                args.pytorch_search_guidance_infer_trainer_input,
                example_index=(
                    args.pytorch_search_guidance_infer_example_index
                    if args.pytorch_search_guidance_infer_example_index is not None
                    else 0
                ),
            )
        except (ImportError, IndexError, OSError, ValueError) as exc:
            print(
                f"failed to run PyTorch search-guidance inference: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_pytorch_search_guidance_inference_workflow_report(
                report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
        return 0 if report.command_ok else 2

    if args.teacher_guidance_calibration_report is not None:
        try:
            report = run_teacher_guidance_calibration_from_paths(
                trainer_input_path=args.teacher_guidance_calibration_report,
                checkpoint_paths=args.teacher_guidance_calibration_checkpoint,
                output_path=args.teacher_guidance_calibration_output,
                top_k=args.teacher_guidance_calibration_top_k,
            )
        except (ImportError, OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to run teacher guidance calibration: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_teacher_guidance_calibration_command(
                report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
        return 0 if report.command_passed else 1

    if args.post_t044_failure_analysis_report is not None:
        try:
            report = run_post_t044_failure_analysis_from_paths(
                comparison_paths=args.post_t044_comparison,
                output_path=args.post_t044_failure_analysis_report,
                linked_artifact_specs=args.post_t044_linked_artifact,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build post-T044 failure analysis report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_post_t044_failure_analysis_command(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.t053_root_prior_allocation_failure_analysis_report is not None:
        try:
            report = run_t053_root_prior_failure_analysis_from_paths(
                artifact_specs=args.t053_t052_artifact,
                output_path=args.t053_root_prior_allocation_failure_analysis_report,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                "failed to build T053 root-prior allocation failure analysis "
                f"report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_t053_root_prior_failure_analysis_command(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.t054_guardrailed_root_prior_repair_report is not None:
        try:
            report = run_t054_guardrailed_root_prior_repair_from_paths(
                artifact_specs=args.t054_input_artifact,
                output_path=args.t054_guardrailed_root_prior_repair_report,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build T054 guardrailed root-prior repair report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_t054_guardrailed_root_prior_repair_command(report),
            file=sys.stderr,
        )
        return 0 if report.command_passed else 1

    if args.t055_guardrailed_root_prior_scale_validation_report is not None:
        try:
            report = run_t055_guardrailed_root_prior_scale_validation_from_paths(
                artifact_specs=args.t055_input_artifact,
                output_path=(args.t055_guardrailed_root_prior_scale_validation_report),
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                "failed to build T055 guardrailed root-prior scale validation "
                f"report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_t055_guardrailed_root_prior_scale_validation_command(report),
            file=sys.stderr,
        )
        return 0 if report.command_passed else 1

    if args.t052_t051_boss_later_act_fixed_cohort is not None:
        try:
            report = run_t052_fixed_cohort_extraction_from_paths(
                output_path=args.t052_t051_boss_later_act_fixed_cohort,
                source_arm_specs=args.t052_source_arm,
                verify_artifact_specs=args.t052_verify_artifact,
                summary_path=args.t052_cohort_summary,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build T052 fixed diagnostic cohort: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_t052_fixed_cohort_extraction_command(report), file=sys.stderr)
        return 0 if report.get("command_passed") else 1

    if args.t052_retention_manifest is not None:
        try:
            manifest = run_t052_retention_manifest_from_paths(
                output_path=args.t052_retention_manifest,
                artifact_specs=args.t052_retained_artifact,
                command_specs=args.t052_retention_command,
                stage_specs=args.t052_retention_stage,
                note_specs=args.t052_retention_note,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build T052 retention manifest: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_t052_retention_manifest_command(manifest), file=sys.stderr)
        return 0

    if args.t054_retention_manifest is not None:
        try:
            manifest = run_t054_retention_manifest_from_paths(
                output_path=args.t054_retention_manifest,
                artifact_specs=args.t054_retained_artifact,
                command_specs=args.t054_retention_command,
                stage_specs=args.t054_retention_stage,
                note_specs=args.t054_retention_note,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build T054 retention manifest: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_t054_retention_manifest_command(manifest), file=sys.stderr)
        return 0

    if args.t055_retention_manifest is not None:
        try:
            manifest = run_t055_retention_manifest_from_paths(
                output_path=args.t055_retention_manifest,
                artifact_specs=args.t055_retained_artifact,
                command_specs=args.t055_retention_command,
                stage_specs=args.t055_retention_stage,
                note_specs=args.t055_retention_note,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to build T055 retention manifest: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_t055_retention_manifest_command(manifest), file=sys.stderr)
        return 0

    if args.merge_root_prior_guided_search_comparison is not None:
        try:
            report = merge_root_prior_guided_search_comparison_reports_from_paths(
                shard_paths=args.root_prior_guided_search_comparison_shard,
                output_path=args.merge_root_prior_guided_search_comparison,
                worker_count=args.workers,
                shard_count=args.shards,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(
                f"failed to merge root-prior guided comparison shards: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_root_prior_guided_search_comparison_report(report), file=sys.stderr
        )
        return 0 if report.evaluation_successful else 1

    if args.pytorch_search_guidance_train is not None:
        try:
            from sts_combat_rl.sim.torch_policy_value import (
                TorchPolicyValueTrainingConfig,
            )

            report = run_pytorch_search_guidance_training_from_path(
                args.pytorch_search_guidance_train,
                args.pytorch_checkpoint_output,
                training_config=TorchPolicyValueTrainingConfig(
                    epochs=args.pytorch_epochs,
                    learning_rate=args.pytorch_learning_rate,
                    hidden_size=args.pytorch_hidden_size,
                    batch_size=args.pytorch_batch_size,
                    seed=args.sim_seed,
                ),
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
        except (ImportError, OSError, ValueError) as exc:
            print(
                f"failed to run PyTorch search-guidance training: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_pytorch_search_guidance_training_workflow_report(report),
            file=sys.stderr,
        )
        return 0 if report.command_ok else 2

    if args.oracle_teacher_search_guidance_input is not None:
        try:
            from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

            training_config = None
            if args.oracle_teacher_search_guidance_checkpoint_output is not None:
                from sts_combat_rl.sim.torch_policy_value import (
                    TorchPolicyValueTrainingConfig,
                )

                training_config = TorchPolicyValueTrainingConfig(
                    epochs=(
                        args.oracle_teacher_search_guidance_epochs
                        if args.oracle_teacher_search_guidance_epochs is not None
                        else args.pytorch_epochs
                    ),
                    learning_rate=args.pytorch_learning_rate,
                    hidden_size=args.pytorch_hidden_size,
                    batch_size=args.pytorch_batch_size,
                    seed=args.sim_seed,
                )

            report = run_oracle_teacher_search_guidance_from_paths(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=20,
                ),
                manifest_path=args.oracle_teacher_search_guidance_input,
                selected_budget=args.oracle_teacher_search_guidance_budget,
                output_path=args.oracle_teacher_search_guidance_output,
                target=args.oracle_teacher_search_guidance_target,
                stability_filter=args.oracle_teacher_search_guidance_stability_filter,
                report_output_path=args.oracle_teacher_search_guidance_report_output,
                checkpoint_output_path=(
                    args.oracle_teacher_search_guidance_checkpoint_output
                ),
                training_config=training_config,
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
        except (ImportError, OSError, ValueError) as exc:
            print(
                f"failed to run Oracle teacher search-guidance bridge: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_oracle_teacher_search_guidance_command(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.oracle_teacher_dataset_report is not None:
        try:
            report = run_oracle_teacher_dataset_report_from_paths(
                teacher_path=args.oracle_teacher_dataset_report,
                source_pool_path=args.oracle_teacher_source_pool,
                coverage_report_path=args.oracle_teacher_coverage_report,
                output_path=args.oracle_teacher_report_output,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to build Oracle teacher dataset report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_oracle_teacher_dataset_report_command(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.a20_reachability_report is not None:
        try:
            report = run_a20_reachability_report_from_paths(
                output_path=args.a20_reachability_report,
                arm_specs=args.reachability_arm,
                stream_pools=args.stream_reachability_pools,
            )
        except (OSError, ValueError) as exc:
            print(f"failed to build A20 reachability report: {exc}", file=sys.stderr)
            return 2
        print(format_a20_reachability_comparison_report(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.merge_battle_start_pool_shards is not None:
        try:
            summary = merge_checkpoint_pool_shards_from_paths(
                output_path=args.merge_battle_start_pool_shards,
                shard_paths=args.battle_start_pool_shard,
                manifest_path=args.battle_start_pool_shard_merge_manifest,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to merge natural battle-start pool shards: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_battle_start_pool_shard_merge_report(summary), file=sys.stderr)
        return 0

    if args.merge_a20_battle_start_coverage is not None:
        try:
            report = merge_a20_battle_start_coverage_from_paths(
                output_path=args.merge_a20_battle_start_coverage,
                pool_path=args.merged_battle_start_pool,
                coverage_shard_paths=args.battle_start_coverage_shard,
                restore_limit=args.battle_start_restore_limit,
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to merge A20 battle-start coverage shards: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_a20_battle_start_coverage_report(report), file=sys.stderr)
        return 0 if report.command_passed else 1

    if args.expert_source_coverage_report is not None:
        try:
            report = run_expert_source_coverage_report_from_paths(
                output_path=args.expert_source_coverage_report,
                arm_specs=args.expert_source_arm,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to build expert source-coverage report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_expert_source_coverage_comparison_report(report),
            file=sys.stderr,
        )
        return 0 if report.command_passed else 1

    if args.assisted_source_coverage_report is not None:
        try:
            report = run_assisted_source_coverage_report_from_paths(
                output_path=args.assisted_source_coverage_report,
                arm_specs=args.assisted_source_arm,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to build assisted source-coverage report: {exc}",
                file=sys.stderr,
            )
            return 2
        print(
            format_assisted_source_coverage_comparison_report(report),
            file=sys.stderr,
        )
        return 0 if report.command_passed else 1

    if args.merge_assisted_source_pool is not None:
        try:
            artifact = merge_assisted_source_pool_from_paths(
                output_path=args.merge_assisted_source_pool,
                shard_paths=args.assisted_source_shard,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to merge assisted source-pool shards: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_assisted_source_pool_merge_report(artifact), file=sys.stderr)
        return 0

    if args.merge_assisted_a20_coverage is not None:
        try:
            report = merge_assisted_a20_coverage_from_paths(
                output_path=args.merge_assisted_a20_coverage,
                pool_path=args.merged_assisted_source_pool,
                coverage_shard_paths=args.assisted_coverage_shard,
                restore_limit=args.battle_start_restore_limit,
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
        except (OSError, ValueError) as exc:
            print(
                f"failed to merge assisted A20 coverage shards: {exc}",
                file=sys.stderr,
            )
            return 2
        print(format_assisted_coverage_report(report), file=sys.stderr)
        return 0

    if is_lightspeed_command(args):
        return run_lightspeed_command(args)

    if args.calibrate_combat_features is not None:
        try:
            report = run_communicationmod_feature_calibration(
                args.calibrate_combat_features
            )
        except OSError as exc:
            print(f"failed to calibrate combat features: {exc}", file=sys.stderr)
            return 2

        print(
            format_communicationmod_feature_calibration_report(report),
            file=sys.stderr,
        )
        return 0

    if args.audit_tactical_features is not None:
        try:
            report = run_communicationmod_tactical_feature_audit(
                args.audit_tactical_features
            )
        except OSError as exc:
            print(f"failed to audit tactical features: {exc}", file=sys.stderr)
            return 2
        print(format_tactical_feature_coverage_report(report), file=sys.stderr)
        return 1 if report.problems else 0

    if args.mock is not None:
        try:
            with args.mock.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except OSError as exc:
            print(f"failed to read mock file: {exc}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"failed to parse mock JSON: {exc}", file=sys.stderr)
            return 2

        if not isinstance(raw, dict):
            print("mock JSON must be an object", file=sys.stderr)
            return 2

        command = client.act_from_raw(raw)
        print(format_command(command))
        return 0

    print(format_ready_signal(), flush=True)
    client.run(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
