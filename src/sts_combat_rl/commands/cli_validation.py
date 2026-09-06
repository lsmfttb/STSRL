"""Cross-command CLI validation helpers."""

from __future__ import annotations

import argparse
import math

from sts_combat_rl.commands.search_battle_controller import (
    SEARCH_BATTLE_CONTROLLER_ORACLE,
    SEARCH_BATTLE_CONTROLLERS_REQUIRING_CHECKPOINT,
)
from sts_combat_rl.commands.t062_battle_search_v2 import parse_t062_arm_budgets
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_ASSISTED_SEEDED_UNIFORM,
    ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_SEEDED_UNIFORM,
    T032_T039_BACKGROUND_SOURCE_COUNT,
)


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
    if args.lightspeed_t085_native_selection_restore is not None:
        restore_required = (
            args.t085_selection_input,
            args.t085_selection_input_sha256,
            args.t085_a_map,
            args.t085_b_map,
            args.t085_c_map,
            args.t085_a_map_sha256,
            args.t085_b_map_sha256,
            args.t085_c_map_sha256,
            args.t085_b_source_manifest,
            args.t085_b_source_manifest_sha256,
            args.t085_c_source_manifest,
            args.t085_c_source_manifest_sha256,
            args.t085_shard_index,
            args.t085_shard_count,
            args.t085_worker_count,
        )
        if any(value is None for value in restore_required):
            return (
                "T085 selection restore requires the outcome-blind input, A/B/C "
                "maps, final B/C manifests, all exact SHA-256 values, and "
                "explicit 16-shard/16-worker values"
            )
        if args.t085_b_artifact_kind != "assisted_pool":
            return "T085 selection restore requires an assisted Cohort-B source map"
        if args.t085_c_artifact_kind != "natural_pool":
            return "T085 selection restore requires a natural Cohort-C source map"
        if args.t085_shard_count != 16:
            return "--t085-shard-count must be 16"
        if not 0 <= args.t085_shard_index < 16:
            return "--t085-shard-index must be between 0 and 15"
        if args.t085_worker_count != 16:
            return "--t085-worker-count must be 16"
    if args.lightspeed_t085_native_selection_restore_finalize is not None and (
        args.t085_selection_output is None
        or len(args.t085_selection_restore_shard) != 16
    ):
        return (
            "T085 selection restore finalization requires --t085-selection-output "
            "and exactly 16 --t085-selection-restore-shard paths"
        )
    if args.lightspeed_t085_native_paired_evaluation is not None:
        paired_required = (
            args.t085_selection_sha256,
            args.t085_a_map,
            args.t085_b_map,
            args.t085_c_map,
            args.t085_a_map_sha256,
            args.t085_b_map_sha256,
            args.t085_c_map_sha256,
            args.t085_old_checkpoint_64001,
            args.t085_corrected_checkpoint_85001,
            args.t085_old_checkpoint_64002,
            args.t085_corrected_checkpoint_85002,
            args.t085_old_checkpoint_64001_sha256,
            args.t085_corrected_checkpoint_85001_sha256,
            args.t085_old_checkpoint_64002_sha256,
            args.t085_corrected_checkpoint_85002_sha256,
            args.t085_training_manifest,
            args.t085_training_manifest_sha256,
            args.t085_shard_index,
            args.t085_shard_count,
            args.t085_worker_count,
            args.t085_selection_output,
            args.t085_report_output,
            args.t085_outcomes_output,
        )
        if any(value is None for value in paired_required):
            return (
                "T085 paired evaluation requires selection, A/B/C full maps, "
                "all exact SHA-256 values, four checkpoints, training manifest, "
                "explicit 16-shard/16-worker values, and three outputs"
            )
        if args.t085_b_artifact_kind != "assisted_pool":
            return (
                "T085 paired evaluation requires --t085-b-artifact-kind assisted_pool"
            )
        if args.t085_c_artifact_kind != "natural_pool":
            return "T085 paired evaluation requires --t085-c-artifact-kind natural_pool"
        if args.t085_shard_count != 16:
            return "--t085-shard-count must be 16"
        if not 0 <= args.t085_shard_index < 16:
            return "--t085-shard-index must be between 0 and 15"
        if args.t085_worker_count != 16:
            return "--t085-worker-count must be 16"
    if args.lightspeed_t085_cohort_b_source_generation is not None:
        source_required = (
            args.t085_b_source_manifest_output,
            args.t085_b_source_shard_index,
            args.t085_b_source_shard_count,
            args.t085_b_source_worker_count,
        )
        if any(value is None for value in source_required):
            return (
                "T085 Cohort B source generation requires a shard manifest "
                "output and explicit shard/worker values"
            )
        if args.t085_b_source_shard_count != 16:
            return "--t085-b-source-shard-count must be 16"
        if not 0 <= args.t085_b_source_shard_index < 16:
            return "--t085-b-source-shard-index must be between 0 and 15"
        if args.t085_b_source_worker_count != 16:
            return "--t085-b-source-worker-count must be 16"
    if args.lightspeed_t085_cohort_b_source_merge is not None:
        if len(args.t085_b_source_shard) != 16:
            return "T085 Cohort B source merge requires exactly 16 source shard pools"
        if len(args.t085_b_source_shard_manifest) != 16:
            return "T085 Cohort B source merge requires exactly 16 shard manifests"
    if args.lightspeed_t085_cohort_b_source_manifest is not None and (
        args.t085_b_source_pool_sha256 is None
        or args.t085_b_source_manifest_output is None
    ):
        return (
            "T085 Cohort B source manifest finalization requires the "
            "merged pool SHA-256 and manifest output"
        )
    if args.lightspeed_t085_cohort_c_source_generation is not None:
        source_required = (
            args.t085_c_source_manifest_output,
            args.t085_c_source_shard_index,
            args.t085_c_source_shard_count,
            args.t085_c_source_worker_count,
        )
        if any(value is None for value in source_required):
            return (
                "T085 Cohort C source generation requires a shard manifest "
                "output and explicit shard/worker values"
            )
        if args.t085_c_source_shard_count != 16:
            return "--t085-c-source-shard-count must be 16"
        if not 0 <= args.t085_c_source_shard_index < 16:
            return "--t085-c-source-shard-index must be between 0 and 15"
        if args.t085_c_source_worker_count != 16:
            return "--t085-c-source-worker-count must be 16"
    if args.lightspeed_t085_cohort_c_source_merge is not None:
        if len(args.t085_c_source_shard) != 16:
            return "T085 Cohort C source merge requires exactly 16 source shard pools"
        if len(args.t085_c_source_shard_manifest) != 16:
            return "T085 Cohort C source merge requires exactly 16 shard manifests"
    if args.lightspeed_t085_cohort_c_source_manifest is not None and (
        args.t085_c_source_pool_sha256 is None
        or args.t085_c_source_manifest_output is None
    ):
        return (
            "T085 Cohort C source manifest finalization requires the "
            "merged pool SHA-256 and manifest output"
        )
    if not 0.0 <= args.battle_start_structural_fraction <= 1.0:
        return "--battle-start-structural-fraction must be between zero and one"
    if args.oracle_search_simulations <= 0:
        return "--oracle-search-simulations must be positive"
    if args.search_budget is not None and args.search_budget <= 0:
        return "--search-budget must be positive"
    try:
        parse_t062_arm_budgets(
            args.t062_arm_budget,
            args.oracle_search_simulations
            if args.search_budget is None
            else args.search_budget,
        )
    except ValueError as exc:
        return str(exc)
    if args.workers <= 0:
        return "--workers must be positive"
    if args.shards <= 0:
        return "--shards must be positive"
    if args.record_range is not None:
        range_problem = _validate_record_range(args.record_range)
        if range_problem is not None:
            return range_problem
    if (
        not math.isfinite(args.root_prior_temperature)
        or args.root_prior_temperature <= 0.0
    ):
        return "--root-prior-temperature must be finite and positive"
    if args.root_prior_min_visits < 0:
        return "--root-prior-min-visits must be non-negative"
    if (
        not math.isfinite(args.root_prior_allocation_weight)
        or args.root_prior_allocation_weight < 0.0
        or args.root_prior_allocation_weight > 1.0
    ):
        return "--root-prior-allocation-weight must be between zero and one"
    if args.assistance_policy_seed is not None and args.assistance_policy_seed < 0:
        return "--assistance-policy-seed must be non-negative"
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
    if args.oracle_teacher_scaleup_background_count <= 0:
        return "--oracle-teacher-scaleup-background-count must be positive"
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
    if (
        args.search_battle_controller != SEARCH_BATTLE_CONTROLLER_ORACLE
        and args.lightspeed_search_battle_start_pool is None
    ):
        return (
            "--search-battle-controller requires --lightspeed-search-battle-start-pool"
        )
    search_pool_uses_checkpoint = (
        args.lightspeed_search_battle_start_pool is not None
        and args.search_battle_controller
        in SEARCH_BATTLE_CONTROLLERS_REQUIRING_CHECKPOINT
    )
    uses_model_guided_oracle_checkpoint = (
        args.lightspeed_model_guided_oracle_fixed_evaluation is not None
        or args.lightspeed_model_guided_search_fixed_comparison is not None
        or args.lightspeed_model_guided_search_v2_fixed_comparison is not None
        or args.lightspeed_de_assisted_fixed_cohort_comparison is not None
        or args.lightspeed_root_prior_guided_search_comparison is not None
        or args.lightspeed_t062_battle_search_v2_comparison is not None
        or search_pool_uses_checkpoint
    )
    if (
        uses_model_guided_oracle_checkpoint
        and args.model_guided_oracle_checkpoint is None
    ):
        return (
            "--lightspeed model-guided Oracle evaluation/comparison or "
            "checkpoint-guided source collection requires "
            "--model-guided-oracle-checkpoint"
        )
    if (
        not uses_model_guided_oracle_checkpoint
        and args.model_guided_oracle_checkpoint is not None
    ):
        return (
            "--model-guided-oracle-checkpoint requires "
            "--lightspeed-model-guided-oracle-fixed-evaluation or "
            "--lightspeed-model-guided-search-fixed-comparison or "
            "--lightspeed-model-guided-search-v2-fixed-comparison or "
            "--lightspeed-de-assisted-fixed-cohort-comparison or "
            "--lightspeed-root-prior-guided-search-comparison or "
            "--lightspeed-t062-battle-search-v2-comparison or "
            "--lightspeed-search-battle-start-pool with a checkpoint-guided "
            "--search-battle-controller"
        )
    if (
        args.model_guided_search_comparison_report is not None
        and args.lightspeed_model_guided_search_fixed_comparison is None
        and args.lightspeed_model_guided_search_v2_fixed_comparison is None
    ):
        return (
            "--model-guided-search-comparison-report requires "
            "--lightspeed-model-guided-search-fixed-comparison or "
            "--lightspeed-model-guided-search-v2-fixed-comparison"
        )
    if (
        args.de_assisted_fixed_cohort_comparison_report is not None
        and args.lightspeed_de_assisted_fixed_cohort_comparison is None
    ):
        return (
            "--de-assisted-fixed-cohort-comparison-report requires "
            "--lightspeed-de-assisted-fixed-cohort-comparison"
        )
    if (
        args.root_prior_guided_search_comparison_report is not None
        and args.lightspeed_root_prior_guided_search_comparison is None
    ):
        return (
            "--root-prior-guided-search-comparison-report requires "
            "--lightspeed-root-prior-guided-search-comparison"
        )
    if (
        args.t062_battle_search_v2_comparison_report is not None
        and args.lightspeed_t062_battle_search_v2_comparison is None
    ):
        return (
            "--t062-battle-search-v2-comparison-report requires "
            "--lightspeed-t062-battle-search-v2-comparison"
        )
    if (
        args.merge_root_prior_guided_search_comparison is not None
        and not args.root_prior_guided_search_comparison_shard
    ):
        return (
            "--merge-root-prior-guided-search-comparison requires "
            "--root-prior-guided-search-comparison-shard"
        )
    if (
        args.merge_root_prior_guided_search_comparison is None
        and args.root_prior_guided_search_comparison_shard
    ):
        return (
            "--root-prior-guided-search-comparison-shard requires "
            "--merge-root-prior-guided-search-comparison"
        )
    teacher_scaleup_requested = (
        args.lightspeed_a20_oracle_teacher_scaleup is not None
        or args.lightspeed_a20_assisted_oracle_teacher_scaleup is not None
    )
    if teacher_scaleup_requested and args.oracle_teacher_scaleup_output_dir is None:
        return "Oracle teacher scale-up requires --oracle-teacher-scaleup-output-dir"
    if not teacher_scaleup_requested and (
        args.oracle_teacher_scaleup_output_dir is not None
        or args.oracle_teacher_scaleup_source_limit is not None
        or args.oracle_teacher_scaleup_coverage_report is not None
        or args.oracle_teacher_scaleup_source_selection
        != ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_SEEDED_UNIFORM
        or args.oracle_teacher_scaleup_background_count
        != T032_T039_BACKGROUND_SOURCE_COUNT
    ):
        return (
            "--oracle-teacher-scaleup-output-dir, "
            "--oracle-teacher-scaleup-source-limit, and "
            "--oracle-teacher-scaleup-coverage-report, "
            "--oracle-teacher-scaleup-source-selection, and "
            "--oracle-teacher-scaleup-background-count require "
            "--lightspeed-a20-oracle-teacher-scaleup or "
            "--lightspeed-a20-assisted-oracle-teacher-scaleup"
        )
    if (
        args.lightspeed_a20_oracle_teacher_scaleup is not None
        and args.oracle_teacher_scaleup_source_selection
        == ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_ASSISTED_SEEDED_UNIFORM
    ):
        return (
            "--oracle-teacher-scaleup-source-selection assisted_seeded_uniform "
            "requires --lightspeed-a20-assisted-oracle-teacher-scaleup"
        )
    if (
        args.lightspeed_a20_assisted_oracle_teacher_scaleup is not None
        and args.oracle_teacher_scaleup_source_selection
        not in {
            ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_SEEDED_UNIFORM,
            ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_ASSISTED_SEEDED_UNIFORM,
        }
    ):
        return (
            "--lightspeed-a20-assisted-oracle-teacher-scaleup supports only "
            "seeded_uniform or assisted_seeded_uniform source selection"
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
    if args.a20_reachability_report is None and args.stream_reachability_pools:
        return "--stream-reachability-pools requires --a20-reachability-report"
    t061_outputs = (
        args.t061_bottleneck_report,
        args.t061_budget_curve_report,
        args.t061_factorial_report,
    )
    if args.t061_bottleneck_report is not None and (
        args.t061_budget_curve_report is None or args.t061_factorial_report is None
    ):
        return (
            "--t061-bottleneck-report requires --t061-budget-curve-report and "
            "--t061-factorial-report"
        )
    if args.t061_bottleneck_report is None and any(
        path is not None for path in t061_outputs[1:]
    ):
        return "--t061-budget-curve-report and --t061-factorial-report require --t061-bottleneck-report"
    if args.t061_bottleneck_report is None and (
        args.t061_budget_arm or args.t061_factorial_arm
    ):
        return "--t061 arm inputs require --t061-bottleneck-report"
    if args.t061_bottleneck_report is not None and len(args.t061_budget_arm) != 3:
        return (
            "--t061-bottleneck-report requires exactly three --t061-budget-arm values"
        )
    if args.t061_bottleneck_report is not None and len(args.t061_factorial_arm) != 6:
        return (
            "--t061-bottleneck-report requires exactly six --t061-factorial-arm values"
        )
    if args.t061_expected_run_count < 1:
        return "--t061-expected-run-count must be positive"
    if args.t061_bootstrap_resamples < 100:
        return "--t061-bootstrap-resamples must be at least 100"
    t062_inputs = (
        args.t062_t061_retention_manifest,
        args.t062_fixed_cohort,
        args.t062_checkpoint,
    )
    if args.t062_input_preflight_report is not None and any(
        path is None for path in t062_inputs
    ):
        return (
            "--t062-input-preflight-report requires --t062-t061-retention-manifest, "
            "--t062-fixed-cohort, and --t062-checkpoint"
        )
    if args.t062_input_preflight_report is None and any(
        path is not None for path in t062_inputs
    ):
        return "--t062 input paths require --t062-input-preflight-report"
    if args.t062_expected_record_count <= 0:
        return "--t062-expected-record-count must be positive"
    if args.merge_t062_comparison is not None and not args.t062_comparison_shard:
        return "--merge-t062-comparison requires --t062-comparison-shard"
    if args.merge_t062_comparison is None and args.t062_comparison_shard:
        return "--t062-comparison-shard requires --merge-t062-comparison"
    t062_decision_inputs = (
        args.t062_nominal_comparison,
        args.t062_simulator_step_comparison,
        args.t062_wall_clock_comparison,
    )
    if args.t062_decision_report is not None and any(
        path is None for path in t062_decision_inputs
    ):
        return (
            "--t062-decision-report requires --t062-nominal-comparison, "
            "--t062-simulator-step-comparison, and --t062-wall-clock-comparison"
        )
    if args.t062_decision_report is None and any(
        path is not None for path in t062_decision_inputs
    ):
        return "T062 merged comparison inputs require --t062-decision-report"
    t062_calibration_inputs = (
        args.t062_nominal_budget_calibration,
        args.t062_wall_clock_candidate_calibration,
    )
    if args.t062_calibration_manifest is not None and any(
        path is None for path in t062_calibration_inputs
    ):
        return (
            "--t062-calibration-manifest requires "
            "--t062-nominal-budget-calibration and "
            "--t062-wall-clock-candidate-calibration"
        )
    if args.t062_calibration_manifest is None and any(
        path is not None for path in t062_calibration_inputs
    ):
        return "T062 calibration inputs require --t062-calibration-manifest"
    if (
        args.t062_early_exit_decision_report is not None
        and args.t062_early_exit_calibration_manifest is None
    ):
        return (
            "--t062-early-exit-decision-report requires "
            "--t062-early-exit-calibration-manifest"
        )
    if (
        args.t062_early_exit_decision_report is None
        and args.t062_early_exit_calibration_manifest is not None
    ):
        return (
            "--t062-early-exit-calibration-manifest requires "
            "--t062-early-exit-decision-report"
        )
    if (
        args.merge_battle_start_pool_shards is not None
        and not args.battle_start_pool_shard
    ):
        return "--merge-battle-start-pool-shards requires --battle-start-pool-shard"
    if args.merge_battle_start_pool_shards is None and (
        args.battle_start_pool_shard
        or args.battle_start_pool_shard_merge_manifest is not None
    ):
        return (
            "--battle-start-pool-shard and "
            "--battle-start-pool-shard-merge-manifest require "
            "--merge-battle-start-pool-shards"
        )
    if args.merge_a20_battle_start_coverage is not None and (
        args.merged_battle_start_pool is None or not args.battle_start_coverage_shard
    ):
        return (
            "--merge-a20-battle-start-coverage requires "
            "--merged-battle-start-pool and --battle-start-coverage-shard"
        )
    if args.merge_a20_battle_start_coverage is None and (
        args.merged_battle_start_pool is not None or args.battle_start_coverage_shard
    ):
        return (
            "--merged-battle-start-pool and --battle-start-coverage-shard require "
            "--merge-a20-battle-start-coverage"
        )
    if (
        args.expert_source_coverage_report is not None
        and len(args.expert_source_arm) != 3
    ):
        return (
            "--expert-source-coverage-report requires exactly three "
            "--expert-source-arm values"
        )
    if args.expert_source_coverage_report is None and args.expert_source_arm:
        return "--expert-source-arm requires --expert-source-coverage-report"
    if (
        args.assisted_source_coverage_report is not None
        and len(args.assisted_source_arm) != 5
    ):
        return (
            "--assisted-source-coverage-report requires exactly five "
            "--assisted-source-arm values"
        )
    if args.assisted_source_coverage_report is None and args.assisted_source_arm:
        return "--assisted-source-arm requires --assisted-source-coverage-report"
    if args.merge_assisted_source_pool is not None and not args.assisted_source_shard:
        return "--merge-assisted-source-pool requires --assisted-source-shard"
    if args.merge_assisted_source_pool is None and args.assisted_source_shard:
        return "--assisted-source-shard requires --merge-assisted-source-pool"
    if args.merge_assisted_a20_coverage is not None and (
        args.merged_assisted_source_pool is None or not args.assisted_coverage_shard
    ):
        return (
            "--merge-assisted-a20-coverage requires --merged-assisted-source-pool "
            "and --assisted-coverage-shard"
        )
    if args.merge_assisted_a20_coverage is None and (
        args.merged_assisted_source_pool is not None or args.assisted_coverage_shard
    ):
        return (
            "--merged-assisted-source-pool and --assisted-coverage-shard require "
            "--merge-assisted-a20-coverage"
        )
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
    if (
        args.post_t044_failure_analysis_report is not None
        and not args.post_t044_comparison
    ):
        return (
            "--post-t044-failure-analysis-report requires at least one "
            "--post-t044-comparison"
        )
    if args.post_t044_failure_analysis_report is None and (
        args.post_t044_comparison or args.post_t044_linked_artifact
    ):
        return (
            "--post-t044-comparison and --post-t044-linked-artifact require "
            "--post-t044-failure-analysis-report"
        )
    if args.t052_t051_boss_later_act_fixed_cohort is not None:
        if len(args.t052_source_arm) != 3:
            return (
                "--t052-t051-boss-later-act-fixed-cohort requires exactly "
                "three --t052-source-arm values"
            )
        roles = [values[0] for values in args.t052_source_arm]
        if sorted(roles) != ["baseline", "post_search", "root_prior"]:
            return (
                "--t052-source-arm roles must be baseline, post_search, and root_prior"
            )
        if args.t052_cohort_summary is None:
            return (
                "--t052-t051-boss-later-act-fixed-cohort requires --t052-cohort-summary"
            )
    elif (
        args.t052_source_arm
        or args.t052_verify_artifact
        or args.t052_cohort_summary is not None
    ):
        return (
            "--t052-source-arm, --t052-verify-artifact, and "
            "--t052-cohort-summary require "
            "--t052-t051-boss-later-act-fixed-cohort"
        )
    if args.t052_retention_manifest is not None:
        if not args.t052_retained_artifact:
            return "--t052-retention-manifest requires --t052-retained-artifact"
    elif (
        args.t052_retained_artifact
        or args.t052_retention_command
        or args.t052_retention_stage
        or args.t052_retention_note
    ):
        return (
            "--t052-retained-artifact, --t052-retention-command, "
            "--t052-retention-stage, and --t052-retention-note require "
            "--t052-retention-manifest"
        )
    if (
        args.root_prior_allocation_report is not None
        and not args.lightspeed_native_root_prior_allocation_smoke
    ):
        return (
            "--root-prior-allocation-report requires "
            "--lightspeed-native-root-prior-allocation-smoke"
        )
    return None


def _validate_record_range(value: str) -> str | None:
    parts = value.split(":", 1)
    if len(parts) != 2:
        return "--record-range must use START:END"
    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError:
        return "--record-range endpoints must be integers"
    if start < 0 or end < start:
        return "--record-range must be a non-negative end-exclusive range"
    return None
