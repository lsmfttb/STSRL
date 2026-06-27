"""Cross-command CLI validation helpers."""

from __future__ import annotations

import argparse
import math


def validate_cli_args(args: argparse.Namespace) -> str | None:
    """Return the first user-facing CLI validation problem, if any."""

    if args.sim_steps < 0:
        return "--sim-steps must be non-negative"
    if args.sim_rollouts < 1:
        return "--sim-rollouts must be positive"
    if args.sim_episodes < 1:
        return "--sim-episodes must be positive"
    if args.reward_detail_limit < 0:
        return "--reward-detail-limit must be non-negative"
    if args.checkpoint_replay_steps <= 0:
        return "--checkpoint-replay-steps must be positive"
    if args.battle_start_restore_limit < 0:
        return "--battle-start-restore-limit must be non-negative"
    if args.battle_start_sample_count < 0:
        return "--battle-start-sample-count must be non-negative"
    if not 0.0 <= args.battle_start_structural_fraction <= 1.0:
        return "--battle-start-structural-fraction must be between zero and one"
    if args.oracle_search_simulations <= 0:
        return "--oracle-search-simulations must be positive"
    if (
        not math.isfinite(args.model_guided_oracle_policy_probability_weight)
        or args.model_guided_oracle_policy_probability_weight < 0.0
    ):
        return (
            "--model-guided-oracle-policy-probability-weight must be finite "
            "and non-negative"
        )
    if args.oracle_teacher_scaleup_seed < 0:
        return "--oracle-teacher-scaleup-seed must be non-negative"
    if (
        args.oracle_teacher_scaleup_source_limit is not None
        and args.oracle_teacher_scaleup_source_limit <= 0
    ):
        return "--oracle-teacher-scaleup-source-limit must be positive"
    if any(value <= 0 for value in args.oracle_teacher_scaleup_budgets):
        return "--oracle-teacher-scaleup-budgets must be positive"
    if len(set(args.oracle_teacher_scaleup_budgets)) != len(
        args.oracle_teacher_scaleup_budgets
    ):
        return "--oracle-teacher-scaleup-budgets must be unique"
    if args.oracle_teacher_search_guidance_budget <= 0:
        return "--oracle-teacher-search-guidance-budget must be positive"
    if (
        args.oracle_teacher_search_guidance_epochs is not None
        and args.oracle_teacher_search_guidance_epochs <= 0
    ):
        return "--oracle-teacher-search-guidance-epochs must be positive"
    if args.pytorch_gate_min_records <= 0:
        return "--pytorch-gate-min-records must be positive"
    if args.pytorch_gate_min_sources <= 0:
        return "--pytorch-gate-min-sources must be positive"
    if any(value < 0 for value in args.pytorch_gate_required_ascensions):
        return "--pytorch-gate-required-ascensions cannot contain negatives"
    if any(value <= 0 for value in args.pytorch_gate_required_acts):
        return "--pytorch-gate-required-acts must be positive"
    if args.pytorch_epochs <= 0:
        return "--pytorch-epochs must be positive"
    if args.pytorch_learning_rate <= 0.0:
        return "--pytorch-learning-rate must be positive"
    if args.pytorch_hidden_size <= 0:
        return "--pytorch-hidden-size must be positive"
    if args.pytorch_batch_size <= 0:
        return "--pytorch-batch-size must be positive"
    if (
        args.pytorch_search_guidance_infer_example_index is not None
        and args.pytorch_search_guidance_infer_example_index < 0
    ):
        return "--pytorch-search-guidance-infer-example-index must be non-negative"
    if args.teacher_guidance_calibration_top_k <= 0:
        return "--teacher-guidance-calibration-top-k must be positive"
    if (
        args.lightspeed_oracle_search_teacher is not None
        and args.oracle_teacher_output is None
    ):
        return "--lightspeed-oracle-search-teacher requires --oracle-teacher-output"
    uses_model_guided_oracle_checkpoint = (
        args.lightspeed_model_guided_oracle_fixed_evaluation is not None
        or args.lightspeed_model_guided_search_fixed_comparison is not None
    )
    if (
        uses_model_guided_oracle_checkpoint
        and args.model_guided_oracle_checkpoint is None
    ):
        return (
            "--lightspeed model-guided Oracle evaluation/comparison requires "
            "--model-guided-oracle-checkpoint"
        )
    if (
        not uses_model_guided_oracle_checkpoint
        and args.model_guided_oracle_checkpoint is not None
    ):
        return (
            "--model-guided-oracle-checkpoint requires "
            "--lightspeed-model-guided-oracle-fixed-evaluation or "
            "--lightspeed-model-guided-search-fixed-comparison"
        )
    if (
        args.model_guided_search_comparison_report is not None
        and args.lightspeed_model_guided_search_fixed_comparison is None
    ):
        return (
            "--model-guided-search-comparison-report requires "
            "--lightspeed-model-guided-search-fixed-comparison"
        )
    if (
        args.lightspeed_a20_oracle_teacher_scaleup is not None
        and args.oracle_teacher_scaleup_output_dir is None
    ):
        return (
            "--lightspeed-a20-oracle-teacher-scaleup requires "
            "--oracle-teacher-scaleup-output-dir"
        )
    if args.lightspeed_a20_oracle_teacher_scaleup is None and (
        args.oracle_teacher_scaleup_output_dir is not None
        or args.oracle_teacher_scaleup_source_limit is not None
        or args.oracle_teacher_scaleup_coverage_report is not None
    ):
        return (
            "--oracle-teacher-scaleup-output-dir, "
            "--oracle-teacher-scaleup-source-limit, and "
            "--oracle-teacher-scaleup-coverage-report require "
            "--lightspeed-a20-oracle-teacher-scaleup"
        )
    if (
        args.lightspeed_a20_oracle_teacher_scaleup is not None
        and args.oracle_teacher_scaleup_source_selection == "t032_t039_narrow"
        and args.oracle_teacher_scaleup_source_limit is not None
    ):
        return (
            "--oracle-teacher-scaleup-source-limit is not compatible with "
            "--oracle-teacher-scaleup-source-selection t032_t039_narrow"
        )
    if args.a20_reachability_report is not None and len(args.reachability_arm) < 2:
        return (
            "--a20-reachability-report requires at least two --reachability-arm values"
        )
    if args.a20_reachability_report is None and args.reachability_arm:
        return "--reachability-arm requires --a20-reachability-report"
    if (
        args.oracle_teacher_coverage_report is not None
        and args.oracle_teacher_source_pool is None
    ):
        return "--oracle-teacher-coverage-report requires --oracle-teacher-source-pool"
    if args.oracle_teacher_dataset_report is None and (
        args.oracle_teacher_source_pool is not None
        or args.oracle_teacher_coverage_report is not None
        or args.oracle_teacher_report_output is not None
    ):
        return (
            "--oracle-teacher-source-pool, --oracle-teacher-coverage-report, "
            "and --oracle-teacher-report-output require "
            "--oracle-teacher-dataset-report"
        )
    if args.oracle_teacher_search_guidance_input is not None and (
        args.oracle_teacher_search_guidance_output is None
        or args.oracle_teacher_search_guidance_report_output is None
    ):
        return (
            "--oracle-teacher-search-guidance-input requires "
            "--oracle-teacher-search-guidance-output and "
            "--oracle-teacher-search-guidance-report-output"
        )
    if args.oracle_teacher_search_guidance_input is None and (
        args.oracle_teacher_search_guidance_output is not None
        or args.oracle_teacher_search_guidance_report_output is not None
        or args.oracle_teacher_search_guidance_checkpoint_output is not None
        or args.oracle_teacher_search_guidance_epochs is not None
    ):
        return (
            "--oracle-teacher-search-guidance-output, "
            "--oracle-teacher-search-guidance-report-output, "
            "--oracle-teacher-search-guidance-checkpoint-output, and "
            "--oracle-teacher-search-guidance-epochs require "
            "--oracle-teacher-search-guidance-input"
        )
    if (
        args.pytorch_search_guidance_train is not None
        and args.pytorch_checkpoint_output is None
    ):
        return "--pytorch-search-guidance-train requires --pytorch-checkpoint-output"
    if (
        args.pytorch_search_guidance_infer is not None
        and args.pytorch_search_guidance_infer_trainer_input is None
    ):
        return (
            "--pytorch-search-guidance-infer requires "
            "--pytorch-search-guidance-infer-trainer-input"
        )
    if args.pytorch_search_guidance_infer is None and (
        args.pytorch_search_guidance_infer_trainer_input is not None
        or args.pytorch_search_guidance_infer_example_index is not None
    ):
        return (
            "--pytorch-search-guidance-infer-trainer-input and "
            "--pytorch-search-guidance-infer-example-index require "
            "--pytorch-search-guidance-infer"
        )
    if (
        args.teacher_guidance_calibration_report is not None
        and not args.teacher_guidance_calibration_checkpoint
    ):
        return (
            "--teacher-guidance-calibration-report requires "
            "--teacher-guidance-calibration-checkpoint"
        )
    if args.teacher_guidance_calibration_report is None and (
        args.teacher_guidance_calibration_checkpoint
        or args.teacher_guidance_calibration_output is not None
    ):
        return (
            "--teacher-guidance-calibration-checkpoint and "
            "--teacher-guidance-calibration-output require "
            "--teacher-guidance-calibration-report"
        )
    return None
