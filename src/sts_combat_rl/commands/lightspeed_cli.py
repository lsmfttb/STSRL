"""CLI routing for sts_lightspeed-backed simulator commands."""

from __future__ import annotations

import argparse
import sys

from sts_combat_rl.commands.a20_coverage import (
    run_a20_battle_start_coverage_from_paths,
)
from sts_combat_rl.commands.checkpoint_pool import (
    collect_checkpoint_pool,
    collect_search_checkpoint_pool,
    run_checkpoint_verification,
    verify_checkpoint_pool_file,
    write_checkpoint_pool,
)
from sts_combat_rl.commands.cli_policies import (
    build_pytorch_gate_config,
    build_non_combat_driver_policy,
    build_online_sim_policy,
    build_sim_policy,
)
from sts_combat_rl.commands.constructed_battle_start import (
    run_constructed_battle_start_audit,
    write_constructed_battle_start_artifact,
)
from sts_combat_rl.commands.fixed_evaluation import (
    run_fixed_evaluation_from_pool_path,
    write_fixed_cohort,
    write_fixed_evaluation_report,
)
from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
    format_model_guided_oracle_fixed_evaluation_report,
    run_model_guided_oracle_fixed_evaluation_from_cohort_path,
)
from sts_combat_rl.commands.model_guided_search_comparison import (
    run_model_guided_search_fixed_comparison_from_cohort_path,
    run_model_guided_search_v2_fixed_comparison_from_cohort_path,
    write_model_guided_search_fixed_comparison_report,
    write_model_guided_search_v2_fixed_comparison_report,
)
from sts_combat_rl.commands.oracle_search import (
    collect_oracle_teacher_from_pool_path,
    format_oracle_fixed_evaluation_comparison,
    format_oracle_teacher_collection,
    run_oracle_fixed_evaluation_comparison_from_cohort_path,
    write_oracle_teacher_dataset,
)
from sts_combat_rl.commands.oracle_teacher_scaleup import (
    format_oracle_teacher_scaleup_command,
    run_oracle_teacher_scaleup_from_paths,
)
from sts_combat_rl.commands.public_context import run_public_context_audit
from sts_combat_rl.commands.public_projection import (
    run_public_projection_capability_audit,
)
from sts_combat_rl.commands.resource_outcome import (
    format_battle_resource_outcome_audit_report,
    run_battle_resource_outcome_audit,
)
from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    choose_deterministic_action,
)
from sts_combat_rl.sim.a20_battle_start_coverage import (
    format_a20_battle_start_coverage_report,
)
from sts_combat_rl.sim.batching import (
    build_decision_batch,
    format_decision_batch_report,
)
from sts_combat_rl.sim.battle_agent import (
    build_battle_decision_batch,
    build_battle_segment_report,
    collect_battle_agent_rollout,
    format_battle_agent_sweep_report,
    format_battle_decision_batch_report,
    format_battle_segment_report,
    run_battle_agent_sweep,
)
from sts_combat_rl.sim.battle_start_pool import (
    format_battle_start_pool_coverage_report,
    format_battle_start_pool_restore_report,
)
from sts_combat_rl.sim.calibration import (
    format_simulator_calibration_report,
    format_tactical_feature_coverage_report,
    run_simulator_calibration,
    run_tactical_feature_coverage_audit,
)
from sts_combat_rl.sim.checkpoint_verification import (
    format_battle_checkpoint_verification_report,
)
from sts_combat_rl.sim.constructed_battle_start import (
    ConstructedBattleStartPolicy,
    format_constructed_battle_start_audit_report,
)
from sts_combat_rl.sim.evaluation import (
    format_policy_episode_evaluation_report,
    run_policy_episode_evaluation,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    format_fixed_evaluation_report,
)
from sts_combat_rl.sim.fixed_evaluation_set import format_cohort_coverage_report
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.model_input import (
    build_model_input_batch,
    build_model_input_batch_smoke_report,
    format_model_input_batch_smoke_report,
)
from sts_combat_rl.sim.model_scoring import (
    format_model_score_smoke_report,
    score_model_input_batch,
)
from sts_combat_rl.sim.native_public_projection import (
    format_native_public_projection_capability_report,
)
from sts_combat_rl.sim.non_combat_calibration import (
    format_non_combat_driver_calibration_report,
    run_non_combat_driver_calibration,
)
from sts_combat_rl.sim.online_controller import PolicyController
from sts_combat_rl.sim.model_guided_oracle_search import (
    ModelGuidedOracleSearchController,
    ModelGuidedOracleSearchV2Controller,
)
from sts_combat_rl.sim.model_guided_search_comparison import (
    format_model_guided_search_fixed_comparison_report,
    format_model_guided_search_v2_fixed_comparison_report,
)
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.policy import (
    evaluate_decision_policy,
    format_policy_evaluation_report,
)
from sts_combat_rl.sim.policy_rollout import collect_policy_simulator_rollout
from sts_combat_rl.sim.public_context_audit import (
    format_public_context_artifact_audit_report,
)
from sts_combat_rl.sim.reward_components import (
    build_battle_reward_component_report,
    format_battle_reward_component_report,
)
from sts_combat_rl.sim.reward_design import (
    battle_reward_weights_from_preset,
    build_battle_reward_design_report,
    format_battle_reward_design_report,
)
from sts_combat_rl.sim.reward_labeling import (
    build_reward_labeled_battle_decision_batch,
    format_reward_labeled_battle_decision_batch_report,
)
from sts_combat_rl.sim.rollout import collect_simulator_rollout, format_rollout_batch
from sts_combat_rl.sim.trainer_input import (
    build_trainer_input_dataset,
    build_trainer_input_dataset_smoke_report,
    format_trainer_input_dataset_smoke_report,
)
from sts_combat_rl.sim.trainer_input_contract import (
    build_trainer_input_contract_report,
    format_trainer_input_contract_report,
)
from sts_combat_rl.sim.training_readiness import (
    build_training_readiness_report,
    format_training_readiness_report,
)

_LIGHTSPEED_BOOL_FLAGS = (
    "lightspeed_smoke",
    "lightspeed_tactical_feature_audit",
    "lightspeed_rollout_smoke",
    "lightspeed_batch_smoke",
    "lightspeed_policy_smoke",
    "lightspeed_policy_rollout_smoke",
    "lightspeed_episode_eval",
    "lightspeed_battle_sweep",
    "lightspeed_battle_batch_smoke",
    "lightspeed_battle_segments_smoke",
    "lightspeed_battle_reward_components",
    "lightspeed_battle_reward_design",
    "lightspeed_battle_reward_batch_smoke",
    "lightspeed_battle_trainer_input_contract",
    "lightspeed_battle_trainer_input_smoke",
    "lightspeed_battle_model_input_smoke",
    "lightspeed_battle_model_score_smoke",
    "lightspeed_battle_training_readiness",
    "lightspeed_battle_resource_outcome_audit",
    "lightspeed_constructed_battle_start_audit",
    "lightspeed_non_combat_calibration",
    "lightspeed_public_projection_capability_audit",
    "lightspeed_public_context_audit",
    "lightspeed_battle_checkpoint_verify",
)
_LIGHTSPEED_PATH_FLAGS = (
    "lightspeed_battle_start_pool",
    "lightspeed_search_battle_start_pool",
    "lightspeed_battle_start_pool_restore",
    "lightspeed_a20_battle_start_coverage",
    "lightspeed_a20_oracle_teacher_scaleup",
    "lightspeed_fixed_battle_evaluation",
    "lightspeed_oracle_search_teacher",
    "lightspeed_oracle_fixed_evaluation",
    "lightspeed_model_guided_oracle_fixed_evaluation",
    "lightspeed_model_guided_search_fixed_comparison",
    "lightspeed_model_guided_search_v2_fixed_comparison",
)


def is_lightspeed_command(args: argparse.Namespace) -> bool:
    """Return whether parsed args select a sts_lightspeed-backed command."""

    return any(getattr(args, name) for name in _LIGHTSPEED_BOOL_FLAGS) or any(
        getattr(args, name) is not None for name in _LIGHTSPEED_PATH_FLAGS
    )


def run_lightspeed_command(args: argparse.Namespace) -> int:
    """Run the selected sts_lightspeed-backed command."""

    try:
        adapter = LightSpeedAdapter(seed=args.sim_seed, ascension=args.sim_ascension)
        action_space = (
            ActionSpaceConfig.include_all()
            if args.include_potions
            else ActionSpaceConfig.initial_no_potions()
        )
        if args.lightspeed_smoke:
            report = run_simulator_calibration(
                adapter,
                seed=args.sim_seed,
                max_steps=args.sim_steps,
                action_space=action_space,
            )
            print(format_simulator_calibration_report(report), file=sys.stderr)
        elif args.lightspeed_tactical_feature_audit:
            report = run_tactical_feature_coverage_audit(
                adapter,
                seed=args.sim_seed,
                max_steps=args.sim_steps,
                action_space=action_space,
            )
            print(format_tactical_feature_coverage_report(report), file=sys.stderr)
            if report.problems:
                return 1
        elif args.lightspeed_public_projection_capability_audit:
            report = run_public_projection_capability_audit(
                adapter,
                seed=args.sim_seed,
                episodes=args.sim_episodes,
                max_steps=args.sim_steps,
                action_space=action_space,
            )
            print(
                format_native_public_projection_capability_report(report),
                file=sys.stderr,
            )
            if not report.passed:
                return 1
        elif args.lightspeed_public_context_audit:
            report = run_public_context_audit(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                seed=args.sim_seed,
                episodes=args.sim_episodes,
                max_steps=args.sim_steps,
                action_space=action_space,
            )
            print(format_public_context_artifact_audit_report(report), file=sys.stderr)
            if not report.passed:
                return 1
        elif args.lightspeed_battle_resource_outcome_audit:
            report = run_battle_resource_outcome_audit(
                adapter,
                battle_policy=build_online_sim_policy(
                    args.sim_policy,
                    args.sim_seed,
                ),
                non_combat_policy=build_non_combat_driver_policy(
                    args.sim_non_combat_policy,
                    args.sim_seed,
                ),
                seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
                max_steps=args.sim_steps,
                action_space=action_space,
            )
            print(format_battle_resource_outcome_audit_report(report), file=sys.stderr)
            if not report.passed:
                return 1
        elif args.lightspeed_constructed_battle_start_audit:
            artifact, report = run_constructed_battle_start_audit(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                battle_policy=build_online_sim_policy(
                    args.sim_policy,
                    args.sim_seed,
                ),
                non_combat_policy=build_non_combat_driver_policy(
                    args.sim_non_combat_policy,
                    args.sim_seed,
                ),
                seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
                max_steps=args.sim_steps,
                transform_policy=ConstructedBattleStartPolicy(seed=args.sim_seed),
                action_space=action_space,
                source_pool_path=args.constructed_start_pool,
            )
            if args.constructed_start_output is not None:
                write_constructed_battle_start_artifact(
                    args.constructed_start_output,
                    artifact,
                )
            print(format_constructed_battle_start_audit_report(report), file=sys.stderr)
            if not report.passed:
                return 1
        elif args.lightspeed_battle_checkpoint_verify:
            report = run_checkpoint_verification(
                adapter,
                battle_policy=build_online_sim_policy(
                    args.sim_policy,
                    args.sim_seed,
                ),
                non_combat_policy=build_non_combat_driver_policy(
                    args.sim_non_combat_policy,
                    args.sim_seed,
                ),
                seed=args.sim_seed,
                max_steps=args.sim_steps,
                replay_steps=args.checkpoint_replay_steps,
                action_space=action_space,
            )
            print(format_battle_checkpoint_verification_report(report), file=sys.stderr)
            if not report.determinism_ok:
                return 1
        elif args.lightspeed_battle_start_pool is not None:
            pool, coverage = collect_checkpoint_pool(
                adapter,
                battle_policy=build_online_sim_policy(
                    args.sim_policy,
                    args.sim_seed,
                ),
                non_combat_policy=build_non_combat_driver_policy(
                    args.sim_non_combat_policy,
                    args.sim_seed,
                ),
                seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
                max_steps=args.sim_steps,
                action_space=action_space,
                sample_count=args.battle_start_sample_count,
                sampling_seed=args.sim_seed,
                structural_fraction=args.battle_start_structural_fraction,
            )
            write_checkpoint_pool(args.lightspeed_battle_start_pool, pool)
            print(format_battle_start_pool_coverage_report(coverage), file=sys.stderr)
            if not coverage.completed_outcomes_complete:
                return 1
        elif args.lightspeed_search_battle_start_pool is not None:
            oracle_controller = OracleSearchController(
                simulations=args.oracle_search_simulations,
                root_selection_rule=args.oracle_root_selection,
                action_space=action_space,
            )
            pool, coverage = collect_search_checkpoint_pool(
                adapter,
                oracle_controller=oracle_controller,
                non_combat_policy=build_non_combat_driver_policy(
                    args.sim_non_combat_policy,
                    args.sim_seed,
                ),
                seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
                max_steps=args.sim_steps,
                action_space=action_space,
                sample_count=args.battle_start_sample_count,
                sampling_seed=args.sim_seed,
                structural_fraction=args.battle_start_structural_fraction,
            )
            write_checkpoint_pool(args.lightspeed_search_battle_start_pool, pool)
            print(format_battle_start_pool_coverage_report(coverage), file=sys.stderr)
            if not coverage.completed_outcomes_complete:
                return 1
        elif args.lightspeed_battle_start_pool_restore is not None:
            report = verify_checkpoint_pool_file(
                args.lightspeed_battle_start_pool_restore,
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                limit=args.battle_start_restore_limit,
            )
            print(format_battle_start_pool_restore_report(report), file=sys.stderr)
            if not report.restore_ok:
                return 1
        elif args.lightspeed_a20_battle_start_coverage is not None:
            report = run_a20_battle_start_coverage_from_paths(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=20,
                ),
                pool_path=args.lightspeed_a20_battle_start_coverage,
                constructed_artifact_path=args.a20_coverage_constructed_artifact,
                output_path=args.a20_coverage_output,
                restore_limit=args.battle_start_restore_limit,
                sample_count=args.battle_start_sample_count,
                sampling_seed=args.sim_seed,
                structural_fraction=args.battle_start_structural_fraction,
                gate_config=build_pytorch_gate_config(args),
                gate_override=args.pytorch_gate_override,
            )
            print(format_a20_battle_start_coverage_report(report), file=sys.stderr)
            if not report.command_passed:
                return 1
        elif args.lightspeed_a20_oracle_teacher_scaleup is not None:
            manifest = run_oracle_teacher_scaleup_from_paths(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=20,
                ),
                pool_path=args.lightspeed_a20_oracle_teacher_scaleup,
                output_dir=args.oracle_teacher_scaleup_output_dir,
                budgets=args.oracle_teacher_scaleup_budgets,
                source_limit=args.oracle_teacher_scaleup_source_limit,
                selection_seed=args.oracle_teacher_scaleup_seed,
                source_selection_mode=args.oracle_teacher_scaleup_source_selection,
                background_source_count=(args.oracle_teacher_scaleup_background_count),
                coverage_report_path=args.oracle_teacher_scaleup_coverage_report,
                root_selection_rule=args.oracle_teacher_scaleup_root_selection,
                action_space=action_space,
            )
            print(format_oracle_teacher_scaleup_command(manifest), file=sys.stderr)
            if not manifest.command_passed:
                return 1
        elif args.lightspeed_fixed_battle_evaluation is not None:
            battle_policy = build_online_sim_policy(
                args.sim_policy,
                args.sim_seed,
            )
            battle_controller = PolicyController(battle_policy)
            cohort, coverage, eval_report = run_fixed_evaluation_from_pool_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                pool_path=args.lightspeed_fixed_battle_evaluation,
                controller=battle_controller,
                selection_seed=args.fixed_evaluation_seed,
                action_space=action_space,
                max_battle_steps=args.sim_steps,
            )
            if args.fixed_evaluation_cohort is not None:
                write_fixed_cohort(args.fixed_evaluation_cohort, cohort)
            if args.fixed_evaluation_report is not None:
                write_fixed_evaluation_report(args.fixed_evaluation_report, eval_report)
            print(format_cohort_coverage_report(coverage), file=sys.stderr)
            print(file=sys.stderr)
            print(format_fixed_evaluation_report(eval_report), file=sys.stderr)
            if not eval_report.evaluation_successful:
                return 1
        elif args.lightspeed_oracle_search_teacher is not None:
            oracle_controller = OracleSearchController(
                simulations=args.oracle_search_simulations,
                root_selection_rule=args.oracle_root_selection,
                action_space=action_space,
            )
            teacher_dataset = collect_oracle_teacher_from_pool_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                pool_path=args.lightspeed_oracle_search_teacher,
                controller=oracle_controller,
                action_space=action_space,
            )
            print(format_oracle_teacher_collection(teacher_dataset), file=sys.stderr)
            if teacher_dataset.problems:
                return 1
            write_oracle_teacher_dataset(
                args.oracle_teacher_output,
                teacher_dataset,
            )
        elif args.lightspeed_oracle_fixed_evaluation is not None:
            comparison = run_oracle_fixed_evaluation_comparison_from_cohort_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                cohort_path=args.lightspeed_oracle_fixed_evaluation,
                simulations=args.oracle_search_simulations,
                primary_selection_rule=args.oracle_root_selection,
                action_space=action_space,
                max_battle_steps=args.sim_steps,
            )
            if args.fixed_evaluation_report is not None:
                write_fixed_evaluation_report(
                    args.fixed_evaluation_report,
                    comparison.primary_report,
                )
            print(
                format_oracle_fixed_evaluation_comparison(comparison), file=sys.stderr
            )
            if not comparison.evaluation_successful:
                return 1
        elif args.lightspeed_model_guided_oracle_fixed_evaluation is not None:
            scorer = build_torch_guidance_scorer_from_checkpoint(
                args.model_guided_oracle_checkpoint
            )
            controller = ModelGuidedOracleSearchController(
                simulations=args.oracle_search_simulations,
                scorer=scorer,
                policy_probability_weight=(
                    args.model_guided_oracle_policy_probability_weight
                ),
                action_space=action_space,
            )
            report = run_model_guided_oracle_fixed_evaluation_from_cohort_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                cohort_path=args.lightspeed_model_guided_oracle_fixed_evaluation,
                controller=controller,
                action_space=action_space,
                max_battle_steps=args.sim_steps,
            )
            if args.fixed_evaluation_report is not None:
                write_fixed_evaluation_report(args.fixed_evaluation_report, report)
            print(
                format_model_guided_oracle_fixed_evaluation_report(report),
                file=sys.stderr,
            )
            if not report.evaluation_successful:
                return 1
        elif args.lightspeed_model_guided_search_fixed_comparison is not None:
            scorer = build_torch_guidance_scorer_from_checkpoint(
                args.model_guided_oracle_checkpoint
            )
            baseline_controller = OracleSearchController(
                simulations=args.oracle_search_simulations,
                root_selection_rule=args.oracle_root_selection,
                action_space=action_space,
            )
            model_guided_controller = ModelGuidedOracleSearchController(
                simulations=args.oracle_search_simulations,
                scorer=scorer,
                policy_probability_weight=(
                    args.model_guided_oracle_policy_probability_weight
                ),
                action_space=action_space,
            )
            report = run_model_guided_search_fixed_comparison_from_cohort_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                cohort_path=args.lightspeed_model_guided_search_fixed_comparison,
                baseline_controller=baseline_controller,
                model_guided_controller=model_guided_controller,
                action_space=action_space,
                max_battle_steps=args.sim_steps,
                run_scale=args.model_guided_search_comparison_scale,
            )
            if args.model_guided_search_comparison_report is not None:
                write_model_guided_search_fixed_comparison_report(
                    args.model_guided_search_comparison_report,
                    report,
                )
            print(
                format_model_guided_search_fixed_comparison_report(report),
                file=sys.stderr,
            )
            if not report.evaluation_successful:
                return 1
        elif args.lightspeed_model_guided_search_v2_fixed_comparison is not None:
            scorer = build_torch_guidance_scorer_from_checkpoint(
                args.model_guided_oracle_checkpoint
            )
            baseline_controller = OracleSearchController(
                simulations=args.oracle_search_simulations,
                root_selection_rule=args.oracle_root_selection,
                action_space=action_space,
            )
            model_guided_v1_controller = ModelGuidedOracleSearchController(
                simulations=args.oracle_search_simulations,
                scorer=scorer,
                policy_probability_weight=(
                    args.model_guided_oracle_policy_probability_weight
                ),
                action_space=action_space,
            )
            model_guided_v2_controller = ModelGuidedOracleSearchV2Controller(
                simulations=args.oracle_search_simulations,
                scorer=scorer,
                policy_probability_weight=(
                    args.model_guided_oracle_policy_probability_weight
                ),
                action_space=action_space,
            )
            report = run_model_guided_search_v2_fixed_comparison_from_cohort_path(
                adapter_factory=lambda: LightSpeedAdapter(
                    seed=args.sim_seed,
                    ascension=args.sim_ascension,
                ),
                cohort_path=args.lightspeed_model_guided_search_v2_fixed_comparison,
                baseline_controller=baseline_controller,
                model_guided_v1_controller=model_guided_v1_controller,
                model_guided_v2_controller=model_guided_v2_controller,
                action_space=action_space,
                max_battle_steps=args.sim_steps,
                run_scale=args.model_guided_search_comparison_scale,
            )
            if args.model_guided_search_comparison_report is not None:
                write_model_guided_search_v2_fixed_comparison_report(
                    args.model_guided_search_comparison_report,
                    report,
                )
            print(
                format_model_guided_search_v2_fixed_comparison_report(report),
                file=sys.stderr,
            )
            if not report.evaluation_successful:
                return 1
        elif args.lightspeed_non_combat_calibration:
            battle_policy = build_online_sim_policy(
                args.sim_policy,
                args.sim_seed,
            )
            report = run_non_combat_driver_calibration(
                adapter,
                battle_policy,
                seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
                driver_seed=args.sim_seed,
                max_steps=args.sim_steps,
                action_space=action_space,
                simulator_config={
                    "ascension": args.sim_ascension,
                    "player_class": "IRONCLAD",
                },
            )
            print(format_non_combat_driver_calibration_report(report), file=sys.stderr)
            if not report.passed:
                return 1
        else:
            return _run_lightspeed_smoke_command(args, adapter, action_space)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"failed to run lightspeed simulator smoke: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_lightspeed_smoke_command(
    args: argparse.Namespace,
    adapter: LightSpeedAdapter,
    action_space: ActionSpaceConfig,
) -> int:
    if args.lightspeed_rollout_smoke:
        batch = collect_simulator_rollout(
            adapter,
            seed=args.sim_seed,
            max_steps=args.sim_steps,
            action_space=action_space,
            chooser=choose_deterministic_action,
        )
        print(format_rollout_batch(batch), file=sys.stderr)
    elif args.lightspeed_policy_rollout_smoke:
        batch = collect_policy_simulator_rollout(
            adapter,
            build_online_sim_policy(args.sim_policy, args.sim_seed),
            seed=args.sim_seed,
            max_steps=args.sim_steps,
            action_space=action_space,
        )
        print(format_rollout_batch(batch), file=sys.stderr)
    elif args.lightspeed_episode_eval:
        episode_report = run_policy_episode_evaluation(
            adapter,
            build_online_sim_policy(args.sim_policy, args.sim_seed),
            seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
            max_steps=args.sim_steps,
            action_space=action_space,
        )
        print(format_policy_episode_evaluation_report(episode_report), file=sys.stderr)
    elif args.lightspeed_battle_sweep:
        non_combat_policy = build_non_combat_driver_policy(
            args.sim_non_combat_policy,
            args.sim_seed,
        )
        battle_report = run_battle_agent_sweep(
            adapter,
            build_online_sim_policy(args.sim_policy, args.sim_seed),
            seeds=[args.sim_seed + offset for offset in range(args.sim_episodes)],
            max_steps=args.sim_steps,
            action_space=action_space,
            autopilot_policy=non_combat_policy,
        )
        print(format_battle_agent_sweep_report(battle_report), file=sys.stderr)
    elif args.lightspeed_battle_batch_smoke:
        battle_rollouts = _collect_battle_rollouts(args, adapter, action_space)
        battle_batch = build_battle_decision_batch(battle_rollouts)
        print(format_battle_decision_batch_report(battle_batch), file=sys.stderr)
    elif args.lightspeed_battle_segments_smoke:
        battle_rollouts = _collect_battle_rollouts(args, adapter, action_space)
        segment_report = build_battle_segment_report(battle_rollouts)
        print(format_battle_segment_report(segment_report), file=sys.stderr)
    elif args.lightspeed_battle_reward_components:
        battle_rollouts = _collect_battle_rollouts(args, adapter, action_space)
        reward_report = build_battle_reward_component_report(battle_rollouts)
        print(
            format_battle_reward_component_report(
                reward_report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
    elif args.lightspeed_battle_reward_design:
        battle_rollouts = _collect_battle_rollouts(args, adapter, action_space)
        reward_design_report = build_battle_reward_design_report(
            battle_rollouts,
            battle_reward_weights_from_preset(args.reward_preset),
        )
        print(
            format_battle_reward_design_report(
                reward_design_report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
    elif args.lightspeed_battle_reward_batch_smoke:
        labeled_batch = _build_reward_labeled_battle_batch(args, adapter, action_space)
        print(
            format_reward_labeled_battle_decision_batch_report(labeled_batch),
            file=sys.stderr,
        )
    elif args.lightspeed_battle_trainer_input_contract:
        labeled_batch = _build_reward_labeled_battle_batch(args, adapter, action_space)
        contract_report = build_trainer_input_contract_report(labeled_batch)
        print(format_trainer_input_contract_report(contract_report), file=sys.stderr)
    elif args.lightspeed_battle_trainer_input_smoke:
        labeled_batch = _build_reward_labeled_battle_batch(args, adapter, action_space)
        dataset_report = build_trainer_input_dataset_smoke_report(labeled_batch)
        print(
            format_trainer_input_dataset_smoke_report(dataset_report),
            file=sys.stderr,
        )
    elif args.lightspeed_battle_model_input_smoke:
        labeled_batch = _build_reward_labeled_battle_batch(args, adapter, action_space)
        dataset = build_trainer_input_dataset(labeled_batch)
        model_report = build_model_input_batch_smoke_report(dataset)
        print(format_model_input_batch_smoke_report(model_report), file=sys.stderr)
    elif args.lightspeed_battle_model_score_smoke:
        labeled_batch = _build_reward_labeled_battle_batch(args, adapter, action_space)
        dataset = build_trainer_input_dataset(labeled_batch)
        model_batch = build_model_input_batch(dataset)
        score_report = score_model_input_batch(model_batch)
        print(
            format_model_score_smoke_report(
                score_report,
                detail_limit=args.reward_detail_limit,
            ),
            file=sys.stderr,
        )
    elif args.lightspeed_battle_training_readiness:
        battle_rollouts = _collect_battle_rollouts(args, adapter, action_space)
        readiness_report = build_training_readiness_report(
            battle_rollouts,
            weights=battle_reward_weights_from_preset(args.reward_preset),
        )
        print(format_training_readiness_report(readiness_report), file=sys.stderr)
    else:
        rollouts = [
            collect_simulator_rollout(
                adapter,
                seed=args.sim_seed + offset,
                max_steps=args.sim_steps,
                action_space=action_space,
                chooser=choose_deterministic_action,
            )
            for offset in range(args.sim_rollouts)
        ]
        decision_batch = build_decision_batch(rollouts)
        if args.lightspeed_batch_smoke:
            print(format_decision_batch_report(decision_batch), file=sys.stderr)
        else:
            policy_evaluation = evaluate_decision_policy(
                decision_batch,
                build_sim_policy(args.sim_policy, args.sim_seed),
            )
            print(format_decision_batch_report(decision_batch), file=sys.stderr)
            print(file=sys.stderr)
            print(format_policy_evaluation_report(policy_evaluation), file=sys.stderr)
    return 0


def _collect_battle_rollouts(
    args: argparse.Namespace,
    adapter: LightSpeedAdapter,
    action_space: ActionSpaceConfig,
) -> list[object]:
    battle_policy = build_online_sim_policy(
        args.sim_policy,
        args.sim_seed,
    )
    non_combat_policy = build_non_combat_driver_policy(
        args.sim_non_combat_policy,
        args.sim_seed,
    )
    return [
        collect_battle_agent_rollout(
            adapter,
            battle_policy,
            seed=args.sim_seed + offset,
            max_steps=args.sim_steps,
            action_space=action_space,
            autopilot_policy=non_combat_policy,
        )
        for offset in range(args.sim_episodes)
    ]


def _build_reward_labeled_battle_batch(
    args: argparse.Namespace,
    adapter: LightSpeedAdapter,
    action_space: ActionSpaceConfig,
) -> object:
    return build_reward_labeled_battle_decision_batch(
        _collect_battle_rollouts(args, adapter, action_space),
        battle_reward_weights_from_preset(args.reward_preset),
    )
