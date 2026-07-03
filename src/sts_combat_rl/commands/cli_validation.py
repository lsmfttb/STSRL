"""Cross-command CLI validation helpers."""

from __future__ import annotations

import argparse
import math

from sts_combat_rl.commands.search_battle_controller import (
    SEARCH_BATTLE_CONTROLLER_ORACLE,
    SEARCH_BATTLE_CONTROLLERS_REQUIRING_CHECKPOINT,
)
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
    if not 0.0 <= args.battle_start_structural_fraction <= 1.0:
        return "--battle-start-structural-fraction must be between zero and one"
    if args.oracle_search_simulations <= 0:
        return "--oracle-search-simulations must be positive"
    if args.search_budget is not None and args.search_budget <= 0:
        return "--search-budget must be positive"
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
    if (
        not math.isfinite(args.root_prior_guardrail_uniform_blend_weight)
        or args.root_prior_guardrail_uniform_blend_weight < 0.0
        or args.root_prior_guardrail_uniform_blend_weight > 1.0
    ):
        return (
            "--root-prior-guardrail-uniform-blend-weight must be between zero and one"
        )
    if (
        not math.isfinite(args.root_prior_guardrail_max_prior_probability)
        or args.root_prior_guardrail_max_prior_probability <= 0.0
        or args.root_prior_guardrail_max_prior_probability > 1.0
    ):
        return (
            "--root-prior-guardrail-max-prior-probability must be in the range (0, 1]"
        )
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
        or args.lightspeed_t054_guardrailed_root_prior_repair_comparison is not None
        or args.lightspeed_t055_guardrailed_root_prior_scale_comparison is not None
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
            "--lightspeed-t054-guardrailed-root-prior-repair-comparison or "
            "--lightspeed-t055-guardrailed-root-prior-scale-comparison or "
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
        args.t054_guardrailed_root_prior_comparison_report is not None
        and args.lightspeed_t054_guardrailed_root_prior_repair_comparison is None
    ):
        return (
            "--t054-guardrailed-root-prior-comparison-report requires "
            "--lightspeed-t054-guardrailed-root-prior-repair-comparison"
        )
    if (
        args.t055_guardrailed_root_prior_comparison_report is not None
        and args.lightspeed_t055_guardrailed_root_prior_scale_comparison is None
    ):
        return (
            "--t055-guardrailed-root-prior-comparison-report requires "
            "--lightspeed-t055-guardrailed-root-prior-scale-comparison"
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
    if args.t053_root_prior_allocation_failure_analysis_report is not None:
        if len(args.t053_t052_artifact) != 4:
            return (
                "--t053-root-prior-allocation-failure-analysis-report requires "
                "exactly four --t053-t052-artifact values"
            )
        roles = [values[0] for values in args.t053_t052_artifact]
        if sorted(roles) != [
            "fixed_cohort",
            "result_summary",
            "retention_manifest",
            "root_prior_guided_comparison",
        ]:
            return (
                "--t053-t052-artifact roles must be fixed_cohort, "
                "result_summary, retention_manifest, and "
                "root_prior_guided_comparison"
            )
    elif args.t053_t052_artifact:
        return (
            "--t053-t052-artifact requires "
            "--t053-root-prior-allocation-failure-analysis-report"
        )
    if args.t054_guardrailed_root_prior_repair_report is not None:
        if len(args.t054_input_artifact) != 6:
            return (
                "--t054-guardrailed-root-prior-repair-report requires exactly "
                "six --t054-input-artifact values"
            )
        roles = [values[0] for values in args.t054_input_artifact]
        if sorted(roles) != [
            "t052_fixed_cohort",
            "t052_result_summary",
            "t052_retention_manifest",
            "t052_root_prior_guided_comparison",
            "t053_failure_analysis",
            "t054_guardrailed_comparison",
        ]:
            return (
                "--t054-input-artifact roles must be t052_fixed_cohort, "
                "t052_result_summary, t052_retention_manifest, "
                "t052_root_prior_guided_comparison, t053_failure_analysis, "
                "and t054_guardrailed_comparison"
            )
    elif args.t054_input_artifact:
        return (
            "--t054-input-artifact requires --t054-guardrailed-root-prior-repair-report"
        )
    if args.t055_guardrailed_root_prior_scale_validation_report is not None:
        if len(args.t055_input_artifact) != 11:
            return (
                "--t055-guardrailed-root-prior-scale-validation-report requires "
                "exactly eleven --t055-input-artifact values"
            )
        roles = [values[0] for values in args.t055_input_artifact]
        if sorted(roles) != [
            "t043_assist0_smoke_checkpoint",
            "t043_main_runs1000_assist0_checkpoint",
            "t048_assist0_fixed_cohort",
            "t048_assist0_reference_comparison",
            "t048_current_fixed_cohort",
            "t048_current_reference_comparison",
            "t054_guardrailed_comparison",
            "t054_guardrailed_repair_report",
            "t054_retention_manifest",
            "t055_assist0_guardrailed_comparison",
            "t055_current_guardrailed_comparison",
        ]:
            return (
                "--t055-input-artifact roles must include T054 "
                "report/comparison/manifest, both T048 reference comparisons, "
                "both retained cohorts, both checkpoints, and both generated "
                "T055 guardrailed comparisons"
            )
    elif args.t055_input_artifact:
        return (
            "--t055-input-artifact requires "
            "--t055-guardrailed-root-prior-scale-validation-report"
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
    if args.t054_retention_manifest is not None:
        if not args.t054_retained_artifact:
            return "--t054-retention-manifest requires --t054-retained-artifact"
    elif (
        args.t054_retained_artifact
        or args.t054_retention_command
        or args.t054_retention_stage
        or args.t054_retention_note
    ):
        return (
            "--t054-retained-artifact, --t054-retention-command, "
            "--t054-retention-stage, and --t054-retention-note require "
            "--t054-retention-manifest"
        )
    if args.t055_retention_manifest is not None:
        if not args.t055_retained_artifact:
            return "--t055-retention-manifest requires --t055-retained-artifact"
    elif (
        args.t055_retained_artifact
        or args.t055_retention_command
        or args.t055_retention_stage
        or args.t055_retention_note
    ):
        return (
            "--t055-retained-artifact, --t055-retention-command, "
            "--t055-retention-stage, and --t055-retention-note require "
            "--t055-retention-manifest"
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
