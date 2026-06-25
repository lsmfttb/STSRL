"""Cross-command CLI validation helpers."""

from __future__ import annotations

import argparse


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
        args.lightspeed_oracle_search_teacher is not None
        and args.oracle_teacher_output is None
    ):
        return "--lightspeed-oracle-search-teacher requires --oracle-teacher-output"
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
    if (
        args.pytorch_search_guidance_train is not None
        and args.pytorch_checkpoint_output is None
    ):
        return "--pytorch-search-guidance-train requires --pytorch-checkpoint-output"
    return None
