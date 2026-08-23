"""Executable, restart-safe orchestration for the T064 reuse-first transfer.

The module intentionally owns only the small amount of glue T064 needs.  It
does not implement a simulator, a teacher format, a trainer format, or an
evaluation format: callers provide the existing T043/T044/T070 runners.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
import argparse
from dataclasses import dataclass, replace
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import gc
import json
import multiprocessing
import os
import subprocess
from pathlib import Path
import time
from typing import Any

from sts_combat_rl.commands.oracle_teacher_scaleup import (
    collect_oracle_teacher_range_from_selected_manifest,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    restore_assisted_battle_start_record,
)
from sts_combat_rl.commands.t064_curriculum import load_selected_source_pool
from sts_combat_rl.commands.de_assisted_fixed_cohort_comparison import (
    merge_de_assisted_fixed_cohort_comparison_shards,
    run_de_assisted_fixed_cohort_comparison_from_cohort_path,
    write_de_assisted_fixed_cohort_comparison_report,
)
from sts_combat_rl.commands.t070_search_v2_audit import (
    FROZEN_MANIFEST_SCHEMA_ID,
    expected_checkpoint_identity_from_stage_manifest,
    load_t070_frozen_contract,
    merge_single_arm_stage,
)
from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    load_de_assisted_fixed_cohort_comparison_jsonl,
)
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl
from sts_combat_rl.sim.oracle_teacher import (
    OracleTeacherDataset,
    dump_oracle_teacher_dataset_jsonl,
    load_oracle_teacher_dataset_jsonl,
)
from sts_combat_rl.sim.trainer_input import (
    dump_trainer_input_dataset_jsonl,
    load_trainer_input_dataset_jsonl,
)
from sts_combat_rl.sim.t064_curriculum import (
    BUCKETS,
    COMPACT_FILENAMES,
    TRAINING_RUN_ORDER,
    TRAINING_RUN_REPORT_FILENAME,
    TRANSFER_GATE_NAMES,
    build_ordered_batch_plan,
    build_transfer_decision,
    complete_source_identity,
    contiguous_ranges,
    dump_compact_json,
    independent_rehash,
    load_compact_json,
    validate_exposure_parity,
    validate_training_run_report,
    write_compact_json,
)


T044_CONTROLLER_ROLES = (
    "baseline_oracle_search",
    "model_guided_search_t043_checkpoint",
    "raw_checkpoint_public_policy",
    "scripted_public_policy_baseline",
)
T044_DEPENDENT_ROLES = T044_CONTROLLER_ROLES[1:3]
T044_INDEPENDENT_ROLES = (
    T044_CONTROLLER_ROLES[0],
    T044_CONTROLLER_ROLES[3],
)
T044_SEARCH_BUDGET = 1
T044_ROOT_SELECTION = "highest_mean"
T044_GUIDANCE_WEIGHT = 0.1
T044_ASSIST_0_RANGES = contiguous_ranges(21)
T044_ASSIST_HP50_RANGES = contiguous_ranges(38)
T070_T052_RANGES = contiguous_ranges(93)
T064_ARTIFACT_ROOT_NAME = "t064-later-act-curriculum-transfer"
T064_INITIALIZATION_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)
# The retained T043 initialization was created with the existing 16-wide
# architecture.  Keep this override local to T064; the shared training
# configuration default remains 128 for legacy callers.
T064_TRAINING_HIDDEN_SIZE = 16
T064_STAGE4_MAX_WORKERS = 2
T064_TRAINING_RUN_LABELS = tuple(f"{arm}/{seed}" for arm, seed in TRAINING_RUN_ORDER)
T064_RETAINED_REUSABLE_CHECKPOINT_IDENTITIES = {
    ("static_mixture_v1", 64001): {
        "sha256": "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193",
        "bytes": 462895,
    }
}

# These are retained history, never inputs to an accepted rerun.  Keeping them
# in the sole stage summary avoids a fifth T064 log-index artifact.
KNOWN_PRIOR_ATTEMPTS = (
    {
        "kind": "successful_but_incomplete_stage1",
        "code_commit": "7b2b763c48a89a7542e7df5e03d0c63895664585",
        "shards": 16,
        "records": "460 of 460",
        "failures": 0,
        "wall_clock_seconds": 3007.420617,
        "manifest_sha256": "1cf759ee334abdce0702e2056416de9d5f80ed40a2dc6e0738b9830248541e22",
        "log_sha256": "a3cfea00ad0f41ea997b7c61cccb181c5daddd7a721d95d0f73643435e97fa51",
    },
    {
        "kind": "pre_overlap_fix_failed_stage0",
        "manifest_path": "logs/failed-attempts/t064-curriculum-manifest.pre-overlap-fix-431f098.json",
        "manifest_sha256": "7c631d0cd136508be5e04a6d8bfe27b49c064a198e78d114921ad2b2c610ea17",
    },
    {"kind": "windows_path_stage1", "return_code": 1, "shards": 0},
    {"kind": "hand_entered_commit_rerun", "wall_clock_seconds": 30.0, "artifacts": 0},
    {
        "kind": "serial_stage4_interrupted_after_one_complete_run",
        "status": "retained_for_strict_reuse_audit",
        "run": "static_mixture_v1/64001",
        "checkpoint_sha256": "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193",
        "checkpoint_bytes": 462895,
    },
    {"kind": "other_terminated_attempts", "status": "retained_non_evidence"},
)


def _is_t044_frozen_action_space(value: Any) -> bool:
    """Require the complete current ``initial_no_potions`` action-space contract."""

    return (
        isinstance(value, Mapping)
        and dict(value) == ActionSpaceConfig.initial_no_potions().to_dict()
    )


def current_code_identity(checkout: Path) -> str:
    """Read the exact source revision without permitting a stale continuation."""

    import subprocess

    value = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ValueError("T064 checkout does not have a full git revision")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    """Thin operational dispatcher; simulator construction stays in existing runners."""

    parser = argparse.ArgumentParser(description="T064 staged curriculum dispatcher")
    parser.add_argument("--dry-run-manifest", type=Path)
    parser.add_argument("--code-commit")
    parser.add_argument(
        "--stage",
        choices=(
            "stage2_teacher",
            "stage3_trainer",
            "stage4_training",
            "stage5_t044",
            "stage6_t070",
            "stage7_aggregate",
        ),
        help="Emit one frozen stage's dispatch inventory.",
    )
    parser.add_argument(
        "--mock-execute",
        action="store_true",
        help="Execute the selected stage's dispatcher with no simulator/artifact runner.",
    )
    parser.add_argument("--attempt-root", type=Path)
    parser.add_argument("--checkpoint-arm")
    parser.add_argument("--stage6-shard-script", type=Path)
    parser.add_argument("--stage6-python", default="python")
    parser.add_argument("--stage6-cohort", type=Path)
    parser.add_argument("--stage6-checkpoint", type=Path)
    parser.add_argument("--stage6-wrapper-manifest", type=Path)
    parser.add_argument("--stage6-native-preflight", type=Path)
    parser.add_argument("--stage6-native-checkout", type=Path)
    parser.add_argument("--stage6-native-build-root", type=Path)
    parser.add_argument("--stage6-baseline-report", type=Path)
    parser.add_argument("--stage6-baseline-contract", type=Path)
    parser.add_argument("--stage6-merged-output", type=Path)
    parser.add_argument("--stage2-teacher-output", type=Path)
    parser.add_argument("--stage2-shard-output-dir", type=Path)
    parser.add_argument("--stage2-log-dir", type=Path)
    parser.add_argument("--stage3-teacher", type=Path)
    parser.add_argument("--stage3-output", type=Path)
    parser.add_argument("--stage3-shard-output-dir", type=Path)
    parser.add_argument("--stage3-log-dir", type=Path)
    parser.add_argument("--stage4-trainer-input", type=Path)
    parser.add_argument("--stage4-initialization", type=Path)
    parser.add_argument("--stage4-initialization-sha256")
    parser.add_argument("--stage4-checkpoint-root", type=Path)
    parser.add_argument("--stage4-frozen-t070-manifest", type=Path)
    parser.add_argument("--stage4-training-report", type=Path)
    parser.add_argument(
        "--stage4-earliest-affected-run",
        choices=T064_TRAINING_RUN_LABELS,
        help=(
            "Allow strict reuse only for completed runs before this frozen run; "
            "omit to require four absent checkpoint targets."
        ),
    )
    parser.add_argument(
        "--stage4-failure-recovery",
        action="store_true",
        help=(
            "Retry the same approved-head Stage4 attempt by strictly auditing "
            "completed checkpoints not invalidated by the repair boundary."
        ),
    )
    parser.add_argument("--stage5-cohort", type=Path)
    parser.add_argument("--stage5-checkpoint", type=Path)
    parser.add_argument("--stage5-cohort-kind", choices=("assist_0", "assist_hp50"))
    parser.add_argument("--stage5-log-dir", type=Path)
    parser.add_argument("--stage5-shard-output-dir", type=Path)
    parser.add_argument("--stage5-merged-output", type=Path)
    parser.add_argument("--stage5-historical-report", type=Path)
    parser.add_argument("--stage7-root", type=Path)
    parser.add_argument("--stage7-teacher", type=Path)
    parser.add_argument("--stage7-trainer-input", type=Path)
    parser.add_argument("--stage7-artifact-contract", type=Path)
    args = parser.parse_args(argv)
    if args.dry_run_manifest is None or args.code_commit is None:
        parser.error("--dry-run-manifest and --code-commit are required")
    with args.dry_run_manifest.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    stages = build_t064_stage_execution_plan(manifest, code_commit=args.code_commit)
    if args.stage is not None:
        stages = [stage for stage in stages if stage["stage"] == args.stage]
    if args.checkpoint_arm is not None:
        stages = [
            stage
            for stage in stages
            if stage.get("checkpoint_arm") == args.checkpoint_arm
        ]
    if args.stage5_checkpoint is not None:
        stages = [
            stage for stage in stages if stage.get("cohort") == args.stage5_cohort_kind
        ]
    if args.mock_execute:
        if not stages or args.attempt_root is None:
            parser.error("--mock-execute requires one --stage and --attempt-root")
        executions: list[dict[str, Any]] = []
        for ordinal, stage in enumerate(stages):
            label = f"{stage['stage']}-{ordinal:02d}"
            if stage["workers"] == 16:
                _, records = dispatch_t064_shards(
                    ranges=stage["ranges"],
                    log_dir=args.attempt_root / label / "logs",
                    worker=lambda index, record_range: {
                        "shard_index": index,
                        "range": record_range,
                        "mock": True,
                    },
                )
                executions.append({"stage": stage["stage"], "shards": records})
            else:
                log = args.attempt_root / label / "stage.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text("return_code=0\\nmock=true\\n", encoding="utf-8")
                executions.append(
                    {"stage": stage["stage"], "return_code": 0, "log_path": str(log)}
                )
        print(json.dumps({"executions": executions}, sort_keys=True))
        return 0
    stage2_values = (
        args.stage2_teacher_output,
        args.stage2_shard_output_dir,
        args.stage2_log_dir,
    )
    if any(value is not None for value in stage2_values):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage2_teacher"
            or any(value is None for value in stage2_values)
        ):
            parser.error("Stage2 execution requires its three explicit output paths")
        merged, records = run_t064_stage2_production(
            manifest=manifest,
            merged_output_path=args.stage2_teacher_output,
            shard_output_dir=args.stage2_shard_output_dir,
            log_dir=args.stage2_log_dir,
        )
        print(
            json.dumps(
                {
                    "stage": "stage2_teacher",
                    "rows": len(merged.records),
                    "shards": records,
                },
                sort_keys=True,
            )
        )
        return 0
    stage3_values = (
        args.stage3_teacher,
        args.stage3_output,
        args.stage3_shard_output_dir,
        args.stage3_log_dir,
    )
    if any(value is not None for value in stage3_values):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage3_trainer"
            or any(value is None for value in stage3_values)
        ):
            parser.error(
                "Stage3 execution requires teacher, output, shard-output, and log paths"
            )
        result = run_t064_stage3_production(
            selected_manifest=manifest,
            teacher_path=args.stage3_teacher,
            output_path=args.stage3_output,
            shard_output_dir=args.stage3_shard_output_dir,
            log_dir=args.stage3_log_dir,
            code_commit=args.code_commit,
        )
        print(
            json.dumps(
                {"stage": "stage3_trainer", "rows": len(result[0].records)},
                sort_keys=True,
            )
        )
        return 0
    stage4_values = (
        args.stage4_trainer_input,
        args.stage4_initialization,
        args.stage4_initialization_sha256,
        args.stage4_checkpoint_root,
        args.stage4_frozen_t070_manifest,
        args.stage4_training_report,
    )
    if (
        any(value is not None for value in stage4_values)
        or args.stage4_failure_recovery
    ):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage4_training"
            or any(value is None for value in stage4_values)
        ):
            parser.error("Stage4 execution requires all fixed artifact paths")
        if args.stage4_training_report.name != TRAINING_RUN_REPORT_FILENAME:
            parser.error("Stage4 report path must be t064-training-run-report.json")
        if args.stage4_initialization_sha256 != T064_INITIALIZATION_SHA256:
            parser.error("Stage4 initialization SHA-256 is not the frozen T064 input")
        reusable_runs: dict[tuple[str, int], Mapping[str, Any]] = {}

        def validate_reusable_checkpoint(
            arm: str, seed: int, checkpoint_path: Path
        ) -> Mapping[str, Any]:
            return _validate_reusable_t064_stage4_isolated(
                _T064Stage4RunRequest(
                    manifest_path=args.dry_run_manifest,
                    trainer_input_path=args.stage4_trainer_input,
                    initialization_checkpoint_path=args.stage4_initialization,
                    initialization_sha256=args.stage4_initialization_sha256,
                    checkpoint_path=checkpoint_path,
                    arm=arm,
                    seed=seed,
                )
            )

        frozen_t070_manifest = _preflight_t064_stage4_paths(
            manifest_path=args.dry_run_manifest,
            training_report_path=args.stage4_training_report,
            checkpoint_root=args.stage4_checkpoint_root,
            frozen_t070_manifest_path=args.stage4_frozen_t070_manifest,
            code_commit=args.code_commit,
            earliest_affected_run=args.stage4_earliest_affected_run,
            failure_recovery=args.stage4_failure_recovery,
            reusable_checkpoint_validator=validate_reusable_checkpoint,
            reusable_runs=reusable_runs,
        )
        report = run_t064_stage4_production(
            manifest_path=args.dry_run_manifest,
            trainer_input_path=args.stage4_trainer_input,
            initialization_checkpoint_path=args.stage4_initialization,
            initialization_sha256=args.stage4_initialization_sha256,
            checkpoint_root=args.stage4_checkpoint_root,
            frozen_t070_manifest_path=args.stage4_frozen_t070_manifest,
            earliest_affected_run=args.stage4_earliest_affected_run,
            failure_recovery=args.stage4_failure_recovery,
            reusable_runs=reusable_runs,
        )
        _validate_completed_t064_training_report(report)
        _write_new_compact_json_atomically(args.stage4_training_report, report)
        # This is deliberately last.  A failed report write leaves the original
        # manifest untouched, so no Stage 6 checkpoint selection can point at
        # an unreported training result.
        persist_t064_t070_checkpoint_selections(
            manifest_path=args.dry_run_manifest,
            code_commit=args.code_commit,
            frozen_t070_manifest=frozen_t070_manifest,
            frozen_identity=_file_identity(args.stage4_frozen_t070_manifest),
            checkpoints={
                f"{run['arm']}:{run['seed']}": run["checkpoint"]
                for run in report["runs"]
            },
        )
        print(
            json.dumps(
                {"stage": "stage4_training", "runs": len(report["runs"])},
                sort_keys=True,
            )
        )
        return 0
    stage5_independent_values = (
        args.stage5_cohort,
        args.stage5_cohort_kind,
        args.stage5_log_dir,
        args.stage5_shard_output_dir,
        args.stage5_merged_output,
        args.stage5_historical_report,
    )
    if args.stage5_historical_report is not None:
        if (
            len(stages) != 8
            or any(stage.get("stage") != "stage5_t044" for stage in stages)
            or sum(stage.get("cohort") == args.stage5_cohort_kind for stage in stages)
            != 4
            or args.stage5_checkpoint is not None
            or any(value is None for value in stage5_independent_values)
        ):
            parser.error(
                "Stage5 historical disposition requires one cohort, no checkpoint, and all paths"
            )
        reused, report, records = run_t064_stage5_historical_disposition_production(
            cohort_path=args.stage5_cohort,
            cohort_kind=args.stage5_cohort_kind,
            historical_report_path=args.stage5_historical_report,
            log_dir=args.stage5_log_dir,
            shard_output_dir=args.stage5_shard_output_dir,
            merged_output_path=args.stage5_merged_output,
        )
        print(
            json.dumps(
                {
                    "stage": "stage5_t044_independent",
                    "disposition": "reused_historical"
                    if reused
                    else "reran_independent",
                    "arms": len(report.arms),
                    "shards": records,
                },
                sort_keys=True,
            )
        )
        return 0
    stage5_dependent_values = (
        args.stage5_cohort,
        args.stage5_checkpoint,
        args.stage5_cohort_kind,
        args.stage5_log_dir,
        args.stage5_shard_output_dir,
        args.stage5_merged_output,
    )
    if any(value is not None for value in stage5_dependent_values):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage5_t044"
            or any(value is None for value in stage5_dependent_values)
        ):
            parser.error(
                "Stage5 execution requires one planned checkpoint/cohort and all output paths"
            )
        runner = run_t064_stage5_dependent_production
        report, records = runner(
            cohort_path=args.stage5_cohort,
            checkpoint_path=args.stage5_checkpoint,
            cohort_kind=args.stage5_cohort_kind,
            log_dir=args.stage5_log_dir,
            shard_output_dir=args.stage5_shard_output_dir,
            merged_output_path=args.stage5_merged_output,
        )
        print(
            json.dumps(
                {"stage": "stage5_t044", "arms": len(report.arms), "shards": records},
                sort_keys=True,
            )
        )
        return 0
    stage7_values = (
        args.stage7_root,
        args.stage7_teacher,
        args.stage7_trainer_input,
        args.stage7_artifact_contract,
    )
    if any(value is not None for value in stage7_values):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage7_aggregate"
            or any(value is None for value in stage7_values)
        ):
            parser.error(
                "Stage7 execution requires root, teacher, trainer, and artifact-contract paths"
            )
        contract = json.loads(args.stage7_artifact_contract.read_text(encoding="utf-8"))
        t044 = {
            (arm, int(seed)): {name: Path(path) for name, path in paths.items()}
            for key, paths in contract["t044_paths"].items()
            for arm, seed in (key.split(":", 1),)
        }
        t070 = {
            (arm, int(seed)): Path(path)
            for key, path in contract["t070_paths"].items()
            for arm, seed in (key.split(":", 1),)
        }
        result = aggregate_t064_stage7_from_artifacts(
            root=args.stage7_root,
            code_commit=args.code_commit,
            teacher_path=args.stage7_teacher,
            trainer_input_path=args.stage7_trainer_input,
            t044_paths=t044,
            t070_paths=t070,
            stage_summary=contract["stage_summary"],
            frozen_inputs=contract["frozen_inputs"],
        )
        print(
            json.dumps(
                {
                    "stage": "stage7_aggregate",
                    "terminal_case": result["decision"]["terminal_case"],
                },
                sort_keys=True,
            )
        )
        return 0
    stage6_values = (
        args.stage6_shard_script,
        args.stage6_cohort,
        args.stage6_checkpoint,
        args.stage6_wrapper_manifest,
        args.stage6_native_preflight,
        args.stage6_native_checkout,
        args.stage6_native_build_root,
        args.stage6_baseline_report,
        args.stage6_baseline_contract,
        args.stage6_merged_output,
    )
    if any(value is not None for value in stage6_values):
        if (
            len(stages) != 1
            or stages[0].get("stage") != "stage6_t070"
            or args.attempt_root is None
            or any(value is None for value in stage6_values)
        ):
            parser.error(
                "Stage6 execution requires one checkpoint arm and all T070 paths"
            )
        if args.stage6_wrapper_manifest.resolve() != args.dry_run_manifest.resolve():
            parser.error("Stage6 must consume the sole curriculum manifest")
        if (
            args.stage6_merged_output.parent.resolve()
            != args.dry_run_manifest.parent.resolve()
        ):
            parser.error("Stage6 merged report must share the curriculum manifest root")
        planned_key = stages[0].get("checkpoint_arm")
        if args.checkpoint_arm != planned_key:
            parser.error(
                "Stage6 checkpoint arm does not match the frozen dispatch plan"
            )
        baseline = json.loads(args.stage6_baseline_report.read_text(encoding="utf-8"))
        contract = json.loads(args.stage6_baseline_contract.read_text(encoding="utf-8"))
        selection_key = args.checkpoint_arm.replace("/", ":")
        if not _validate_t064_stage6_preflight(
            baseline=baseline,
            baseline_path=args.stage6_baseline_report,
            contract=contract,
            cohort_path=args.stage6_cohort,
            wrapper_manifest_path=args.stage6_wrapper_manifest,
            checkpoint_path=args.stage6_checkpoint,
            selection_key=selection_key,
        ):
            parser.error("Stage6 baseline report does not match its frozen contract")
        refuse_overwrite(args.stage6_merged_output)
        attempt = prepare_t064_attempt(
            args.attempt_root, stage="stage6_t070", code_commit=args.code_commit
        )

        def invoke_stage6(index: int, record_range: str) -> int:
            completed = run_t064_t070_shard_script(
                script_path=args.stage6_shard_script,
                python_executable=args.stage6_python,
                cohort_path=args.stage6_cohort,
                checkpoint_path=args.stage6_checkpoint,
                wrapper_manifest_path=args.stage6_wrapper_manifest,
                native_preflight_path=args.stage6_native_preflight,
                native_checkout=args.stage6_native_checkout,
                native_build_root=args.stage6_native_build_root,
                code_commit=args.code_commit,
                selection_key=selection_key,
                output_path=attempt / f"shard-{index:02d}.json",
                record_range=record_range,
                shard_index=index,
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr or "T070 shard script failed")
            return completed.returncode

        _, records = dispatch_t064_shards(
            ranges=stages[0]["ranges"], log_dir=attempt / "logs", worker=invoke_stage6
        )
        merged = merge_single_arm_stage(
            shard_paths=[attempt / f"shard-{index:02d}.json" for index in range(16)],
            expected_ranges=T070_T052_RANGES,
            expected_record_count=93,
            output_path=attempt / "merged.json",
        )
        if merged.get("command_passed") is not True or merged.get("problems"):
            raise ValueError("Stage6 merged report is not accepted")
        os.replace(attempt / "merged.json", args.stage6_merged_output)
        print(json.dumps({"stage": "stage6_t070", "shards": records}, sort_keys=True))
        return 0
    for stage in stages:
        print(json.dumps(stage, sort_keys=True, separators=(",", ":")))
    return 0


def execute_t064_production_stage(stage: str, *, inputs: Mapping[str, Any]) -> Any:
    """Directly route a named T064 stage to its repository-owned primitive.

    This intentionally has an explicit branch per stage instead of a plug-in
    runner mechanism.  The command layer supplies standard LightSpeed and
    controller construction; tests may pass ordinary mock values through the
    same fixed arguments.
    """

    if stage == "stage2_teacher":
        return collect_t064_teacher_stage(**inputs)
    if stage == "stage3_trainer":
        return build_t064_trainer_input_stage(**inputs)
    if stage == "stage4_training":
        return run_t064_paired_training(**inputs)
    if stage == "stage5_t044_dependent":
        return run_t064_t044_dependent_stage(**inputs)
    if stage == "stage5_t044_independent":
        return run_t064_t044_independent_fallback_stage(**inputs)
    if stage == "stage6_t070":
        return run_t064_t070_prior_value_stage(**inputs)
    if stage == "stage7_aggregate":
        return aggregate_t064_stage7_from_artifacts(**inputs)
    raise ValueError(f"unsupported T064 production stage {stage!r}")


def run_t064_stage2_production(
    *,
    manifest: Mapping[str, Any],
    merged_output_path: Path,
    shard_output_dir: Path,
    log_dir: Path,
) -> tuple[OracleTeacherDataset, list[dict[str, Any]]]:
    """Construct the repository LightSpeed oracle path for the real Stage 2 route."""

    from sts_combat_rl.sim.action_space import ActionSpaceConfig
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
    from sts_combat_rl.sim.oracle_search import OracleSearchController

    pool, _ = load_selected_source_pool(manifest)
    action_space = ActionSpaceConfig.initial_no_potions()
    controller = OracleSearchController(
        simulations=100,
        root_selection_rule="highest_mean",
        action_space=action_space,
    )
    return collect_t064_teacher_stage(
        selected_manifest=manifest,
        pool=pool,
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        controller=controller,
        action_space=action_space,
        log_dir=log_dir,
        shard_output_dir=shard_output_dir,
        merged_output_path=merged_output_path,
        record_restorer=restore_assisted_battle_start_record,
        dispatch_backend="fork",
    )


def run_t064_stage3_production(
    *,
    selected_manifest: Mapping[str, Any],
    teacher_path: Path,
    output_path: Path,
    shard_output_dir: Path,
    log_dir: Path,
    code_commit: str,
) -> tuple[Any, Any, dict[str, int]]:
    """Run the T043 converter from the authoritative T064 Stage-1/2 inputs."""

    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
    from sts_combat_rl.sim.oracle_teacher_search_guidance import (
        build_oracle_teacher_search_guidance_dataset_from_direct_provenance,
    )

    validate_resume_manifest(selected_manifest, code_commit=code_commit)
    with teacher_path.open(encoding="utf-8") as stream:
        teacher = load_oracle_teacher_dataset_jsonl(stream)
    pool, selected = load_selected_source_pool(selected_manifest)
    _validate_teacher_against_selected_manifest(teacher, selected_manifest)
    ranges = tuple(selected_manifest.get("teacher_shard_ranges", ()))
    if ranges != contiguous_ranges(len(selected)) or len(ranges) != 16:
        raise ValueError("T064 Stage3 ranges must reuse the frozen 16 teacher ranges")
    refuse_overwrite(output_path)
    shard_output_dir.mkdir(parents=True, exist_ok=True)
    teacher_identity = _file_identity(teacher_path)
    pool_by_identity = {
        complete_source_identity(record)["complete_identity_sha256"]: record
        for record in pool.records
    }
    if len(pool_by_identity) != len(pool.records):
        raise ValueError("T064 Stage3 selected pool has duplicate complete identities")

    def one(index: int, record_range: str) -> dict[str, Any]:
        start, end = _range(record_range, len(selected))
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        selected_range = selected[start:end]
        try:
            range_pool = replace(
                pool,
                records=[
                    pool_by_identity[item["complete_identity_sha256"]]
                    for item in selected_range
                ],
            )
        except KeyError as exc:
            raise ValueError("T064 Stage3 selected range source is missing") from exc
        shard = build_oracle_teacher_search_guidance_dataset_from_direct_provenance(
            adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
            teacher_dataset=replace(teacher, records=teacher.records[start:end]),
            source_pool=range_pool,
            selected_sources=selected_range,
            teacher_artifact_identity=teacher_identity,
            record_restorer=restore_assisted_battle_start_record,
        )
        _write_trainer_input_shard_atomically(output, shard)
        return {"shard_index": index, "record_range": record_range, "path": str(output)}

    # ``teacher``, ``pool``, and ``pool_by_identity`` are deliberately loaded
    # once before the 16-way fork.  Freeze their tracked heap graph so child GC
    # can collect only objects allocated for its own range rather than dirtying
    # the multi-GB merged teacher/source pages through copy-on-write.
    descriptors, shard_records = _dispatch_t064_stage3_fork_shards(
        ranges=ranges, log_dir=log_dir, worker=one, backend="fork"
    )
    merged = _merge_t064_trainer_shard_stream(
        shards=_iter_t064_persisted_trainer_shards(
            descriptors=descriptors,
            expected_ranges=ranges,
            shard_output_dir=shard_output_dir,
        ),
        selected_manifest=selected_manifest,
        expected_ranges=ranges,
    )
    _write_trainer_input_shard_atomically(output_path, merged)
    expected = [item["complete_identity_sha256"] for item in selected]
    mapping = build_trainer_row_mapping(
        selected_manifest=selected_manifest,
        teacher_source_hashes=expected,
        trainer_source_hashes=_trainer_identity_hashes(merged),
    )
    return merged, None, mapping


def validate_resume_manifest(manifest: Mapping[str, Any], *, code_commit: str) -> None:
    """Validate recorded producer provenance and the completed restore audit."""

    for label, value in (
        ("manifest producer", manifest.get("code_commit")),
        ("current execution", code_commit),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 40
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"T064 {label} code commit is invalid")
    audit = manifest.get("complete_source_audit")
    if not isinstance(audit, Mapping) or audit.get("status") != "complete":
        raise ValueError("T064 resume requires a completed selected-source audit")
    if audit.get("selected_restore_failure_count") != 0:
        raise ValueError("T064 resume refuses failed selected-source audit")


def refuse_overwrite(path: Path) -> None:
    """Make stage outputs append-free: an old output must be explicitly audited."""

    if path.exists():
        raise ValueError(f"T064 stage refuses to overwrite existing output: {path}")


def _t064_reusable_run_keys(
    earliest_affected_run: str | None,
    *,
    failure_recovery: bool = False,
) -> tuple[tuple[str, int], ...]:
    """Return runs excluded by repair boundary or same-head failure recovery."""

    if earliest_affected_run is None:
        return TRAINING_RUN_ORDER if failure_recovery else ()
    try:
        boundary = T064_TRAINING_RUN_LABELS.index(earliest_affected_run)
    except ValueError as exc:
        raise ValueError("T064 earliest affected run is not frozen") from exc
    return TRAINING_RUN_ORDER[:boundary]


def _preflight_t064_stage4_paths(
    *,
    manifest_path: Path,
    training_report_path: Path,
    checkpoint_root: Path,
    frozen_t070_manifest_path: Path,
    code_commit: str,
    earliest_affected_run: str | None = None,
    failure_recovery: bool = False,
    reusable_checkpoint_validator: (
        Callable[[str, int, Path], Mapping[str, Any]] | None
    ) = None,
    reusable_runs: dict[tuple[str, int], Mapping[str, Any]] | None = None,
) -> Mapping[str, Any]:
    """Validate-or-refuse every Stage 4 output before training changes anything."""

    if training_report_path.parent.resolve() != manifest_path.parent.resolve():
        raise ValueError("T064 Stage4 report must share the curriculum manifest root")
    if training_report_path.name != TRAINING_RUN_REPORT_FILENAME:
        raise ValueError("T064 Stage4 report filename is not frozen")
    refuse_overwrite(training_report_path)
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    validate_resume_manifest(manifest, code_commit=code_commit)
    if manifest.get("t070_stage_manifest") is not None:
        raise ValueError("T064 Stage4 selections were already finalized")
    if not frozen_t070_manifest_path.is_file():
        raise ValueError("T064 Stage4 frozen T070 manifest is missing")
    frozen = json.loads(frozen_t070_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(frozen, Mapping):
        raise ValueError("T064 Stage4 frozen T070 manifest is invalid")
    reusable = set(
        _t064_reusable_run_keys(
            earliest_affected_run,
            failure_recovery=failure_recovery,
        )
    )
    for arm, seed in TRAINING_RUN_ORDER:
        checkpoint = checkpoint_root / f"{arm}-{seed}.pt"
        partial = checkpoint.with_suffix(checkpoint.suffix + ".tmp")
        if partial.exists():
            raise ValueError(f"T064 Stage4 partial checkpoint blocks reuse: {partial}")
        if not checkpoint.exists():
            continue
        if (arm, seed) not in reusable:
            raise ValueError(
                "T064 Stage4 existing checkpoint is not excluded by "
                f"earliest_affected_run: {checkpoint}"
            )
        if reusable_checkpoint_validator is None:
            raise ValueError(
                f"T064 Stage4 existing checkpoint requires strict validation: {checkpoint}"
            )
        validated = reusable_checkpoint_validator(arm, seed, checkpoint)
        if reusable_runs is not None:
            reusable_runs[(arm, seed)] = validated
    # Establish the stable root before expensive training.  This makes an
    # unwritable/missing artifact location fail before any checkpoint is made.
    training_report_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    return frozen


def _validate_completed_t064_training_report(report: Mapping[str, Any]) -> None:
    """Require the single aggregate report and all four successful outcomes."""

    validated = validate_training_run_report(report)
    runs = validated["runs"]
    if len(runs) != len(TRAINING_RUN_ORDER) or any(
        run.get("completion_status") != "complete" for run in runs
    ):
        raise ValueError("T064 Stage4 requires four complete training outcomes")


def _write_new_compact_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically create a compact T064 document without leaving a temp file."""

    if path.name not in COMPACT_FILENAMES:
        raise ValueError("T064 writer only permits the four frozen compact paths")
    refuse_overwrite(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    refuse_overwrite(temporary)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            dump_compact_json(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def _write_oracle_teacher_shard_atomically(
    path: Path, dataset: OracleTeacherDataset
) -> None:
    """Publish a completed teacher shard only after its JSONL stream is durable."""

    refuse_overwrite(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    refuse_overwrite(temporary)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            dump_oracle_teacher_dataset_jsonl(dataset, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def _iter_t064_persisted_teacher_shards(
    *,
    descriptors: Sequence[Any],
    expected_ranges: Sequence[str],
    shard_output_dir: Path,
) -> Iterator[OracleTeacherDataset]:
    """Yield validated forked Stage-2 shards without retaining all 16 datasets."""

    if len(descriptors) != 16 or len(expected_ranges) != 16:
        raise ValueError("T064 persisted teacher shard topology requires 16 shards")
    for index, (descriptor, record_range) in enumerate(
        zip(descriptors, expected_ranges, strict=True)
    ):
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        temporary = output.with_suffix(output.suffix + ".tmp")
        if (
            not isinstance(descriptor, Mapping)
            or descriptor.get("shard_index") != index
            or descriptor.get("record_range") != record_range
            or descriptor.get("path") != str(output)
        ):
            raise ValueError(f"T064 forked teacher shard {index} descriptor is invalid")
        if temporary.exists():
            raise ValueError(
                f"T064 forked teacher shard {index} has an incomplete temp"
            )
        if not output.is_file():
            raise ValueError(f"T064 forked teacher shard {index} was not persisted")
        with output.open(encoding="utf-8") as stream:
            yield load_oracle_teacher_dataset_jsonl(stream)


def _write_trainer_input_shard_atomically(path: Path, dataset: Any) -> None:
    """Publish an existing-schema trainer shard only after its stream is durable."""

    refuse_overwrite(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    refuse_overwrite(temporary)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            dump_trainer_input_dataset_jsonl(dataset, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def _iter_t064_persisted_trainer_shards(
    *,
    descriptors: Sequence[Any],
    expected_ranges: Sequence[str],
    shard_output_dir: Path,
) -> Iterator[Any]:
    """Stream the 16 existing-schema Stage-3 shards in their frozen order."""

    if len(descriptors) != 16 or len(expected_ranges) != 16:
        raise ValueError("T064 persisted trainer shard topology requires 16 shards")
    for index, (descriptor, record_range) in enumerate(
        zip(descriptors, expected_ranges, strict=True)
    ):
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        temporary = output.with_suffix(output.suffix + ".tmp")
        if (
            not isinstance(descriptor, Mapping)
            or descriptor.get("shard_index") != index
            or descriptor.get("record_range") != record_range
            or descriptor.get("path") != str(output)
        ):
            raise ValueError(f"T064 forked trainer shard {index} descriptor is invalid")
        if temporary.exists():
            raise ValueError(
                f"T064 forked trainer shard {index} has an incomplete temp"
            )
        if not output.is_file():
            raise ValueError(f"T064 forked trainer shard {index} was not persisted")
        with output.open(encoding="utf-8") as stream:
            yield load_trainer_input_dataset_jsonl(stream)


def _trainer_identity_hashes(dataset: Any) -> list[str]:
    """Read the direct selected identity link from existing trainer row metadata."""

    values: list[str] = []
    for index, record in enumerate(dataset.records):
        metadata = record.source_metadata
        identity = metadata.get("t064_complete_identity_sha256")
        if not isinstance(identity, str) or len(identity) != 64:
            raise ValueError(
                f"T064 trainer row {index} lacks complete identity linkage"
            )
        values.append(identity)
    return values


def _merge_t064_trainer_shard_stream(
    *,
    shards: Iterable[Any],
    selected_manifest: Mapping[str, Any],
    expected_ranges: Sequence[str],
) -> Any:
    """Strictly merge existing trainer datasets without retaining shard datasets."""

    selected = _selected_sources(selected_manifest)
    if len(expected_ranges) != 16:
        raise ValueError("T064 trainer merge requires exactly 16 shard ranges")
    first: Any | None = None
    rows: list[Any] = []
    expected_metadata: dict[str, Any] | None = None
    restore_counts: dict[str, int] = {}
    expected_identities = [item.get("complete_identity_sha256") for item in selected]
    if len(expected_identities) != len(set(expected_identities)) or not all(
        isinstance(value, str) and len(value) == 64 for value in expected_identities
    ):
        raise ValueError("T064 trainer merge selected identity inventory is invalid")
    shard_count = 0
    for index, (shard, record_range) in enumerate(
        zip(shards, expected_ranges, strict=True)
    ):
        start, end = _range(record_range, len(selected))
        if shard.problems or len(shard.records) != end - start:
            raise ValueError(f"T064 trainer shard {index} is incomplete")
        metadata = getattr(shard, "generation_metadata", {})
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("direct_provenance_mode")
            != "t064_manifest_and_merged_teacher"
        ):
            raise ValueError(f"T064 trainer shard {index} lacks direct provenance mode")
        metadata_fields = (
            "task_id",
            "workflow",
            "direct_provenance_mode",
            "teacher_artifact_identity",
        )
        if any(field not in metadata for field in metadata_fields):
            raise ValueError(
                f"T064 trainer shard {index} direct provenance is incomplete"
            )
        signature = {field: metadata[field] for field in metadata_fields}
        if expected_metadata is None:
            expected_metadata = signature
        elif signature != expected_metadata:
            raise ValueError(f"T064 trainer shard {index} direct provenance differs")
        raw_restore_counts = metadata.get("restore_counts")
        if not isinstance(raw_restore_counts, Mapping) or not raw_restore_counts:
            raise ValueError(f"T064 trainer shard {index} restore counts are invalid")
        for method, count in raw_restore_counts.items():
            if (
                not isinstance(method, str)
                or not method
                or isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError(
                    f"T064 trainer shard {index} restore counts are invalid"
                )
            restore_counts[method] = restore_counts.get(method, 0) + count
        actual_identities = _trainer_identity_hashes(shard)
        if actual_identities != expected_identities[start:end]:
            raise ValueError(f"T064 trainer shard {index} identity/order mismatch")
        if first is None:
            first = shard
        else:
            for attribute in (
                "format_version",
                "reward_allocation",
                "snapshot_feature_size",
                "action_feature_size",
                "decision_record_schema_version",
                "tactical_feature_schema_id",
                "tactical_feature_schema_version",
                "identity_vocabulary_version",
                "policy_target_schema_id",
                "policy_target_schema_version",
                "structured_battle_outcome_schema_id",
                "structured_battle_outcome_schema_version",
            ):
                if getattr(shard, attribute) != getattr(first, attribute):
                    raise ValueError(
                        f"T064 trainer shard {index} configuration differs"
                    )
        for record in shard.records:
            row_index = len(rows)
            rows.append(
                replace(
                    record,
                    example_index=row_index,
                    rollout_index=row_index,
                    segment_index=row_index,
                )
            )
        shard_count += 1
    if first is None or shard_count != 16 or len(rows) != len(selected):
        raise ValueError("T064 trainer merge dropped selected sources")
    source_run_ids = {record.source_metadata.get("source_run_id") for record in rows}
    if not source_run_ids or any(
        not isinstance(source_run_id, str) or not source_run_id
        for source_run_id in source_run_ids
    ):
        raise ValueError("T064 trainer merge source-run provenance is invalid")
    if sum(restore_counts.values()) != len(rows):
        raise ValueError("T064 trainer merge restore counts do not cover every row")
    merged = replace(
        first,
        source_rollout_count=len(source_run_ids),
        segment_count=len(rows),
        generation_metadata={
            **dict(first.generation_metadata),
            "restore_counts": dict(sorted(restore_counts.items())),
            "t064_complete_identity_order": list(expected_identities),
        },
        records=rows,
        problems=[],
    )
    if _trainer_identity_hashes(merged) != expected_identities:
        raise ValueError("T064 trainer merge output identity/order mismatch")
    return merged


def prepare_t064_attempt(root: Path, *, stage: str, code_commit: str) -> Path:
    """Create an isolated attempt directory; failed outputs are never reused."""

    if not stage or len(code_commit) != 40:
        raise ValueError("T064 attempt requires a named stage and exact code commit")
    attempts = root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    sequence = 0
    while True:
        candidate = attempts / f"{stage}-{code_commit[:12]}-{sequence:03d}"
        if not candidate.exists():
            candidate.mkdir()
            return candidate
        sequence += 1


def dispatch_t064_shards(
    *,
    ranges: Sequence[str],
    log_dir: Path,
    worker: Callable[[int, str], Any],
    backend: str = "thread",
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Execute exactly sixteen shard jobs concurrently and retain every result log.

    Output serialization remains in the existing T043/T044/T070 writers used by
    each worker.  This function records only ordinary text logs and return
    codes; it deliberately creates no alternate artifact schema.
    """

    if len(ranges) != 16:
        raise ValueError("T064 substantial stages require exactly 16 shards")
    if backend not in {"thread", "fork"}:
        raise ValueError("T064 shard backend must be thread or fork")
    if backend == "fork":
        return _dispatch_t064_fork_shards(ranges=ranges, log_dir=log_dir, worker=worker)
    log_dir.mkdir(parents=True, exist_ok=True)
    results: list[Any] = [None] * 16
    records: list[dict[str, Any]] = [{} for _ in ranges]

    with ThreadPoolExecutor(max_workers=16, thread_name_prefix="t064-shard") as pool:
        futures = [
            pool.submit(
                _invoke_t064_shard,
                worker,
                index,
                record_range,
                log_dir / f"shard-{index:02d}.log",
            )
            for index, record_range in enumerate(ranges)
        ]
        for future in as_completed(futures):
            index, value, record = future.result()
            results[index] = value
            records[index] = record
    if any(record["return_code"] for record in records):
        raise RuntimeError(
            "T064 shard stage failed; retained outputs cannot contribute"
        )
    return results, records


def _dispatch_t064_stage3_fork_shards(
    *,
    ranges: Sequence[str],
    log_dir: Path,
    worker: Callable[[int, str], Any],
    backend: str,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Fork Stage 3 after freezing its preloaded teacher/source heap graph.

    This is intentionally Stage-3-specific.  Other T064 stages retain their
    existing dispatcher semantics, while the retained merged teacher can be
    several GB and must not be GC-scanned in every child after ``fork``.
    """

    if backend != "fork":
        raise ValueError("T064 Stage3 requires the WSL fork backend")
    was_enabled = gc.isenabled()
    frozen = False
    try:
        gc.collect()
        gc.freeze()
        frozen = True
        return dispatch_t064_shards(
            ranges=ranges,
            log_dir=log_dir,
            worker=worker,
            backend="fork",
        )
    finally:
        if frozen:
            gc.unfreeze()
        if was_enabled:
            gc.enable()
        else:
            gc.disable()


def _invoke_t064_shard(
    worker: Callable[[int, str], Any],
    index: int,
    record_range: str,
    log_path: Path,
) -> tuple[int, Any, dict[str, Any]]:
    """Run one shard and return its ordinary log/return-code record."""

    started = time.perf_counter()
    try:
        value = worker(index, record_range)
    except BaseException as exc:
        log_path.write_text(f"return_code=1\nerror={exc!r}\n", encoding="utf-8")
        return (
            index,
            None,
            {
                "shard_index": index,
                "range": record_range,
                "return_code": 1,
                "log_path": str(log_path),
                "wall_clock_seconds": time.perf_counter() - started,
                "worker_pid": os.getpid(),
                "problem": str(exc),
            },
        )
    log_path.write_text("return_code=0\n", encoding="utf-8")
    return (
        index,
        value,
        {
            "shard_index": index,
            "range": record_range,
            "return_code": 0,
            "log_path": str(log_path),
            "wall_clock_seconds": time.perf_counter() - started,
            "worker_pid": os.getpid(),
        },
    )


def _fork_t064_shard_worker(
    worker: Callable[[int, str], Any],
    index: int,
    record_range: str,
    log_path: Path,
    sender: Any,
) -> None:
    """Execute one inherited worker closure and return its result to the parent."""

    try:
        sender.send(_invoke_t064_shard(worker, index, record_range, log_path))
    finally:
        sender.close()


def _receive_t064_fork_shard_result(receiver: Any) -> tuple[int, Any, dict[str, Any]]:
    """Receive one forked shard result; kept separate for interruption tests."""

    return receiver.recv()


def _cleanup_t064_fork_children(
    children: Sequence[tuple[Any, Any, Any, int, str, Path]],
) -> None:
    """Close parent pipes and stop only children created by this dispatcher."""

    for _child, receiver, sender, _index, _record_range, _log_path in children:
        for connection in (receiver, sender):
            try:
                connection.close()
            except BaseException:
                pass
    for child, _receiver, _sender, _index, _record_range, _log_path in children:
        try:
            if child.is_alive():
                child.terminate()
        except BaseException:
            pass
    for child, _receiver, _sender, _index, _record_range, _log_path in children:
        try:
            child.join(timeout=5)
            if child.is_alive():
                child.kill()
                child.join()
        except BaseException:
            pass


def _dispatch_t064_fork_shards(
    *,
    ranges: Sequence[str],
    log_dir: Path,
    worker: Callable[[int, str], Any],
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Fork sixteen inherited WSL workers after their parent has loaded inputs."""

    if os.name == "nt" or "fork" not in multiprocessing.get_all_start_methods():
        raise RuntimeError("T064 fork shard backend requires WSL/Linux")
    log_dir.mkdir(parents=True, exist_ok=True)
    context = multiprocessing.get_context("fork")
    children: list[tuple[Any, Any, Any, int, str, Path]] = []
    try:
        for index, record_range in enumerate(ranges):
            receiver, sender = context.Pipe(duplex=False)
            log_path = log_dir / f"shard-{index:02d}.log"
            child = context.Process(
                target=_fork_t064_shard_worker,
                args=(worker, index, record_range, log_path, sender),
                name=f"t064-shard-{index:02d}",
            )
            children.append((child, receiver, sender, index, record_range, log_path))
            child.start()
            sender.close()

        results: list[Any] = [None] * 16
        records: list[dict[str, Any]] = [{} for _ in ranges]
        for child, receiver, _sender, index, record_range, log_path in children:
            try:
                received_index, value, record = _receive_t064_fork_shard_result(
                    receiver
                )
            except EOFError:
                record = {
                    "shard_index": index,
                    "range": record_range,
                    "return_code": 1,
                    "log_path": str(log_path),
                    "wall_clock_seconds": 0.0,
                    "worker_pid": child.pid,
                    "problem": "forked T064 shard exited without a result",
                }
                log_path.write_text(
                    "return_code=1\nerror=forked T064 shard exited without a result\n",
                    encoding="utf-8",
                )
                received_index, value = index, None
            finally:
                receiver.close()
            child.join()
            if child.exitcode not in {0, None} and record["return_code"] == 0:
                record = {
                    **record,
                    "return_code": 1,
                    "problem": f"forked T064 shard exited with code {child.exitcode}",
                }
                log_path.write_text(
                    f"return_code=1\nerror={record['problem']}\n", encoding="utf-8"
                )
                value = None
            results[received_index] = value
            records[received_index] = record
        if any(record["return_code"] for record in records):
            raise RuntimeError(
                "T064 shard stage failed; retained outputs cannot contribute"
            )
        return results, records
    except BaseException:
        _cleanup_t064_fork_children(children)
        raise


def build_t064_stage_execution_plan(
    manifest: Mapping[str, Any], *, code_commit: str
) -> list[dict[str, Any]]:
    """Return the frozen Stage 2--7 topology for a dry-run or real dispatcher."""

    validate_resume_manifest(manifest, code_commit=code_commit)
    source_count = len(_selected_sources(manifest))
    teacher_ranges = tuple(manifest.get("teacher_shard_ranges", ()))
    if teacher_ranges != contiguous_ranges(source_count):
        raise ValueError("T064 teacher range inventory changed")
    stages = [
        {
            "stage": "stage2_teacher",
            "workers": 16,
            "shards": 16,
            "ranges": list(teacher_ranges),
        },
        {
            "stage": "stage3_trainer",
            "workers": 16,
            "shards": 16,
            "ranges": list(teacher_ranges),
        },
        {
            "stage": "stage4_training",
            "workers": T064_STAGE4_MAX_WORKERS,
            "shards": 4,
            "runs": [f"{arm}/{seed}" for arm, seed in TRAINING_RUN_ORDER],
        },
    ]
    stages.extend(
        {
            "stage": "stage5_t044",
            "workers": 16,
            "shards": 16,
            "checkpoint_arm": f"{arm}/{seed}",
            "cohort": cohort,
            "ranges": list(ranges),
            "roles": list(T044_DEPENDENT_ROLES),
        }
        for arm, seed in TRAINING_RUN_ORDER
        for cohort, ranges in (
            ("assist_0", T044_ASSIST_0_RANGES),
            ("assist_hp50", T044_ASSIST_HP50_RANGES),
        )
    )
    stages.extend(
        {
            "stage": "stage6_t070",
            "workers": 16,
            "shards": 16,
            "checkpoint_arm": f"{arm}/{seed}",
            "ranges": list(T070_T052_RANGES),
            "arm": "prior_value",
            "native_budget": 100,
        }
        for arm, seed in TRAINING_RUN_ORDER
    )
    stages.append(
        {"stage": "stage7_aggregate", "workers": 1, "shards": 1, "ranges": ["0:4"]}
    )
    return stages


def build_t064_stage_summary(
    *,
    reuse_inventory: Sequence[Mapping[str, Any]],
    stages: Sequence[Mapping[str, Any]],
    problems: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the single compact stage/retention record, including prior attempts."""

    normalized = [dict(stage) for stage in stages]
    if not normalized:
        raise ValueError("T064 stage summary requires all executed or skipped stages")
    for stage in normalized:
        attempts = stage.setdefault("failed_attempts", [])
        if not isinstance(attempts, list):
            raise ValueError("T064 stage failed attempts must be a list")
    normalized[0]["failed_attempts"] = [
        *KNOWN_PRIOR_ATTEMPTS,
        *normalized[0]["failed_attempts"],
    ]
    return {
        "schema_id": "t064-stage-summary-v1",
        "format_version": 1,
        "reuse_inventory": [dict(item) for item in reuse_inventory],
        "stages": normalized,
        "retention_reason": "T064 reproducible curriculum-transfer evidence and failed-attempt audit",
        "downstream_consumer": "T063 or T065 only after terminal Case A or Case B",
        "deletion_condition": "retain until accepted terminal result and successor retention review",
        "problems": list(problems),
    }


def merge_t064_teacher_shards(
    *,
    shards: Sequence[OracleTeacherDataset],
    selected_manifest: Mapping[str, Any],
    expected_ranges: Sequence[str] | None = None,
) -> OracleTeacherDataset:
    """Merge the existing teacher rows in frozen complete-source order."""

    sources = _selected_sources(selected_manifest)
    ranges = tuple(expected_ranges or contiguous_ranges(len(sources)))
    if len(shards) != 16 or len(ranges) != 16:
        raise ValueError("T064 teacher merge requires exactly 16 shards")
    return _merge_t064_teacher_shard_stream(
        shards=shards, selected_manifest=selected_manifest, expected_ranges=ranges
    )


def _merge_t064_teacher_shard_stream(
    *,
    shards: Iterable[OracleTeacherDataset],
    selected_manifest: Mapping[str, Any],
    expected_ranges: Sequence[str],
) -> OracleTeacherDataset:
    """Apply the frozen strict merge contract while retaining one input shard."""

    sources = _selected_sources(selected_manifest)
    if len(expected_ranges) != 16:
        raise ValueError("T064 teacher merge requires exactly 16 shard ranges")
    first: OracleTeacherDataset | None = None
    rows = []
    shard_count = 0
    for index, (shard, record_range) in enumerate(
        zip(shards, expected_ranges, strict=True)
    ):
        if first is None:
            first = shard
        start, end = _range(record_range, len(sources))
        for attribute in (
            "native_source_identity",
            "controller_provenance",
            "action_space_config",
            "source_pool_format_version",
            "source_pool_controller_provenance",
            "information_regime",
        ):
            if getattr(shard, attribute) != getattr(first, attribute):
                raise ValueError(f"T064 teacher shard {index} configuration differs")
        if shard.problems or len(shard.records) != end - start:
            raise ValueError(f"T064 teacher shard {index} is incomplete")
        for row, source in zip(shard.records, sources[start:end], strict=True):
            if _teacher_source_key(row) != _source_key(source):
                raise ValueError("T064 teacher rows do not match selected source order")
            if not row.soft_visit_target:
                raise ValueError("T064 teacher rows require soft visit targets")
            rows.append(replace(row, row_index=len(rows)))
        shard_count += 1
    if first is None or shard_count != 16:
        raise ValueError("T064 teacher merge requires exactly 16 shards")
    if len(rows) != len(sources):
        raise ValueError("T064 teacher merge dropped selected sources")
    return replace(first, records=rows, problems=[])


def collect_t064_teacher_stage(
    *,
    selected_manifest: Mapping[str, Any],
    pool: Any,
    adapter_factory: Callable[[], Any],
    controller: Any,
    action_space: Any,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
    record_restorer: Callable[[Any, Any], tuple[Any, str]] | None = None,
    dispatch_backend: str = "thread",
    shard_runner: Callable[
        ..., OracleTeacherDataset
    ] = collect_oracle_teacher_range_from_selected_manifest,
) -> tuple[OracleTeacherDataset, list[dict[str, Any]]]:
    """Route all 16 T064 teacher shards through the existing T043 primitive."""

    sources = _selected_sources(selected_manifest)
    ranges = tuple(selected_manifest.get("teacher_shard_ranges", ()))
    if (
        ranges != contiguous_ranges(len(sources))
        or selected_manifest.get("teacher_worker_count") != 16
    ):
        raise ValueError("T064 teacher topology is not frozen at 16 shards/workers")
    refuse_overwrite(merged_output_path)
    shard_output_dir.mkdir(parents=True, exist_ok=True)

    def one(index: int, record_range: str) -> OracleTeacherDataset | dict[str, Any]:
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        shard = shard_runner(
            adapter_factory=adapter_factory,
            pool=pool,
            controller=controller,
            selected_source_manifest=selected_manifest,
            record_range=record_range,
            action_space=action_space,
            **(
                {"record_restorer": record_restorer}
                if record_restorer is not None
                else {}
            ),
        )
        _write_oracle_teacher_shard_atomically(output, shard)
        if dispatch_backend == "fork":
            # Do not pickle a 20--90 MB OracleTeacherDataset back through the
            # parent pipe.  The parent reloads this exact, atomically-published
            # path before it performs the normal strict merge validation.
            return {
                "shard_index": index,
                "record_range": record_range,
                "path": str(output),
            }
        return shard

    dispatched, shard_records = dispatch_t064_shards(
        ranges=ranges,
        log_dir=log_dir,
        worker=one,
        backend=dispatch_backend,
    )
    if dispatch_backend == "fork":
        merged = _merge_t064_teacher_shard_stream(
            shards=_iter_t064_persisted_teacher_shards(
                descriptors=dispatched,
                expected_ranges=ranges,
                shard_output_dir=shard_output_dir,
            ),
            selected_manifest=selected_manifest,
            expected_ranges=ranges,
        )
    else:
        merged = merge_t064_teacher_shards(
            shards=dispatched,
            selected_manifest=selected_manifest,
            expected_ranges=ranges,
        )
    # The caller puts this list directly in the sole stage summary.
    with merged_output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_teacher_dataset_jsonl(merged, stream)
    return merged, shard_records


def build_trainer_row_mapping(
    *,
    selected_manifest: Mapping[str, Any],
    teacher_source_hashes: Sequence[str],
    trainer_source_hashes: Sequence[str],
) -> dict[str, int]:
    """Prove the selected identity -> teacher -> trainer cardinality/order map."""

    expected = [
        source["complete_identity_sha256"]
        for source in _selected_sources(selected_manifest)
    ]
    if list(teacher_source_hashes) != expected:
        raise ValueError("T064 teacher identity order/cardinality is not exact")
    if list(trainer_source_hashes) != expected:
        raise ValueError("T064 trainer identity order/cardinality is not exact")
    if len(expected) != len(set(expected)):
        raise ValueError("T064 selected identities are duplicated")
    return {identity: index for index, identity in enumerate(expected)}


def build_t064_trainer_input_stage(
    *,
    selected_manifest: Mapping[str, Any],
    teacher_dataset: OracleTeacherDataset,
    selected_pool: Any,
    trainer_builder: Callable[..., tuple[Any, Any]],
    trainer_identity_resolver: Callable[[Any], Sequence[str]],
    output_path: Path,
) -> tuple[Any, Any, dict[str, int]]:
    """Call the existing T043 bridge and write its existing trainer-input schema."""

    refuse_overwrite(output_path)
    dataset, bridge_report = trainer_builder(
        teacher_dataset=teacher_dataset,
        source_pool=selected_pool,
    )
    teacher_hashes = [
        source["complete_identity_sha256"]
        for source in _selected_sources(selected_manifest)
    ]
    mapping = build_trainer_row_mapping(
        selected_manifest=selected_manifest,
        teacher_source_hashes=teacher_hashes,
        trainer_source_hashes=trainer_identity_resolver(dataset),
    )
    # This linkage is deliberately in the existing trainer-input metadata, not
    # in a T064 sidecar.  Stage 7 can therefore reload and prove the exact
    # selected identity order without trusting a caller-supplied report.
    dataset = replace(
        dataset,
        generation_metadata={
            **dict(getattr(dataset, "generation_metadata", {})),
            "t064_complete_identity_order": teacher_hashes,
        },
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_trainer_input_dataset_jsonl(dataset, stream)
    return dataset, bridge_report, mapping


def frozen_training_configuration(*, seed: int) -> dict[str, Any]:
    """The paired CPU configuration, represented once for report and execution."""

    return {
        "device": "cpu",
        "deterministic_algorithms": True,
        "torch_threads": 1,
        "seed": seed,
        "hidden_size": T064_TRAINING_HIDDEN_SIZE,
        "optimizer": {
            "kind": "Adam",
            "learning_rate": 0.001,
            "betas": [0.9, 0.999],
            "epsilon": 1e-8,
            "weight_decay": 0.0,
            "amsgrad": False,
            "scheduler": None,
        },
        "batch_size": 32,
        "optimizer_steps": 900,
        "phases": [300, 300, 300],
        "loss_weights": {"policy": 1.0, "outcome": 1.0, "hp": 1.0, "resource": 1.0},
        "hp_loss_scale": 100.0,
        "gradient_clip_norm": 10.0,
    }


def t064_plan_indices(
    batch_plan: Mapping[str, Any], *, identity_to_trainer_index: Mapping[str, int]
) -> list[list[int]]:
    """Translate the manifest's complete identities to existing trainer row indices."""

    batches = batch_plan.get("ordered_batches")
    if not isinstance(batches, list) or len(batches) != 900:
        raise ValueError("T064 requires exactly 900 ordered batches")
    result: list[list[int]] = []
    for batch in batches:
        if not isinstance(batch, list) or len(batch) != 32:
            raise ValueError("T064 requires full ordered batches of 32")
        try:
            result.append(
                [identity_to_trainer_index[str(identity)] for identity in batch]
            )
        except KeyError as exc:
            raise ValueError(
                "T064 batch plan references an unmapped trainer row"
            ) from exc
    return result


def _t064_torch_training_config(seed: int) -> Any:
    from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueTrainingConfig

    return TorchPolicyValueTrainingConfig(
        epochs=900,
        learning_rate=0.001,
        hidden_size=T064_TRAINING_HIDDEN_SIZE,
        hp_loss_scale=100.0,
        policy_loss_weight=1.0,
        outcome_loss_weight=1.0,
        hp_loss_weight=1.0,
        resource_loss_weight=1.0,
        batch_size=32,
        seed=seed,
        adam_betas=(0.9, 0.999),
        adam_epsilon=1e-8,
        weight_decay=0.0,
        amsgrad=False,
        gradient_clip_norm=10.0,
    )


def _validated_t064_training_plans(
    selected_manifest: Mapping[str, Any],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    selected = selected_manifest.get("selected_buckets")
    manifest_plans = selected_manifest.get("batch_plans")
    if not isinstance(selected, Mapping) or not isinstance(manifest_plans, list):
        raise ValueError("T064 training requires validated manifest batch plans")
    regenerated = [
        build_ordered_batch_plan(selected, seed=seed, arm=arm)
        for arm, seed in TRAINING_RUN_ORDER
    ]
    expected_summaries = [
        {key: value for key, value in plan.items() if key != "ordered_batches"}
        for plan in regenerated
    ]
    if manifest_plans != expected_summaries:
        raise ValueError("T064 manifest batch plans do not rehash to frozen plans")
    validate_exposure_parity(regenerated)
    return {(plan["arm"], plan["seed"]): plan for plan in regenerated}


def _t064_training_data_provenance(
    dataset: Any,
    trainer_input_path: Path,
    *,
    trainer_sha256: str,
    trainer_byte_count: int,
    gate_report: Any,
) -> dict[str, Any]:
    from sts_combat_rl.commands.pytorch_search_guidance import (
        build_pytorch_search_guidance_training_data_provenance,
    )

    payload = build_pytorch_search_guidance_training_data_provenance(
        dataset,
        trainer_input_path,
        trainer_input_sha256=trainer_sha256,
        trainer_input_byte_count=trainer_byte_count,
        gate_report=gate_report,
    )
    # The checkpoint writer applies the same JSON-safe normalization before
    # persistence (notably stringifying integer mapping keys in gate evidence).
    return json.loads(json.dumps(payload, allow_nan=False, sort_keys=True))


def _validate_loaded_t064_run_checkpoint(
    loaded: Any,
    *,
    arm: str,
    seed: int,
    initialization_sha256: str,
    plan: Mapping[str, Any],
    expected_provenance: Mapping[str, Any],
) -> None:
    expected_config = _t064_torch_training_config(seed)
    expected_metadata = {
        "task_id": "T064",
        "arm": arm,
        "seed": seed,
        "initialization_sha256": initialization_sha256,
        "batch_plan_sha256": plan["batch_plan_sha256"],
    }
    if loaded.config != expected_config or any(
        loaded.metadata.get(key) != value for key, value in expected_metadata.items()
    ):
        raise ValueError("T064 checkpoint frozen run config/metadata mismatch")
    if loaded.training_data_provenance != dict(expected_provenance):
        raise ValueError("T064 checkpoint trainer provenance mismatch")
    model = loaded.model
    if (
        model.hidden_size != T064_TRAINING_HIDDEN_SIZE
        or any(parameter.device.type != "cpu" for parameter in model.parameters())
        or any(buffer.device.type != "cpu" for buffer in model.buffers())
    ):
        raise ValueError("T064 checkpoint model metadata/device mismatch")


def _t064_training_run_entry(
    *,
    arm: str,
    seed: int,
    initialization_sha256: str,
    trainer_sha256: str,
    trainer_byte_count: int,
    plan: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    completion_status: str,
    problems: Sequence[str],
    disposition: str,
) -> dict[str, Any]:
    return {
        "arm": arm,
        "seed": seed,
        "initialization_sha256": initialization_sha256,
        "configuration": frozen_training_configuration(seed=seed),
        "trainer_input_sha256": trainer_sha256,
        "trainer_input_bytes": trainer_byte_count,
        "batch_plan_sha256": plan["batch_plan_sha256"],
        "per_bucket_exposure_counts": _bucket_exposure_counts(plan),
        "per_source_exposure_counts": plan["per_source_exposure_counts"],
        "checkpoint": dict(checkpoint),
        "checkpoint_metadata_linkage": {
            "schema_id": "torch-policy-value-checkpoint-v1",
            "training_ok": completion_status == "complete",
            "task_id": "T064",
            "arm": arm,
            "seed": seed,
            "initialization_sha256": initialization_sha256,
            "batch_plan_sha256": plan["batch_plan_sha256"],
            "trainer_input_sha256": trainer_sha256,
            "trainer_input_bytes": trainer_byte_count,
        },
        "run_disposition": disposition,
        "completion_status": completion_status,
        "problems": list(problems),
    }


def run_t064_paired_training(
    *,
    selected_manifest: Mapping[str, Any],
    dataset: Any,
    initialization_checkpoint_path: Path,
    initialization_sha256: str,
    trainer_input_path: Path,
    identity_to_trainer_index: Mapping[str, int],
    checkpoint_paths: Mapping[tuple[str, int], Path],
    run_order: Sequence[tuple[str, int]] = TRAINING_RUN_ORDER,
) -> dict[str, Any]:
    """Run fixed CPU jobs sequentially; production isolates at most two calls."""

    from sts_combat_rl.sim.torch_policy_value import (
        load_torch_policy_value_checkpoint,
        save_torch_policy_value_checkpoint,
        train_torch_policy_value,
    )
    from sts_combat_rl.sim.training_gate import build_training_gate_report
    import torch

    if initialization_sha256 != T064_INITIALIZATION_SHA256:
        raise ValueError("T064 initialization SHA-256 is not the frozen input")
    if _sha256(initialization_checkpoint_path) != initialization_sha256:
        raise ValueError("T064 initialization checkpoint identity mismatch")
    plans_by_run = _validated_t064_training_plans(selected_manifest)
    if any(run not in TRAINING_RUN_ORDER for run in run_order) or len(
        set(run_order)
    ) != len(run_order):
        raise ValueError("T064 requested training run inventory is invalid")
    trainer_sha256 = _sha256(trainer_input_path)
    trainer_byte_count = trainer_input_path.stat().st_size
    runs: list[dict[str, Any]] = []
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    for arm, seed in run_order:
        plan = plans_by_run[(arm, seed)]
        output = checkpoint_paths.get((arm, seed))
        if output is None:
            raise ValueError("T064 training checkpoint path is missing")
        temporary = output.with_suffix(output.suffix + ".tmp")
        refuse_overwrite(output)
        refuse_overwrite(temporary)
        config = _t064_torch_training_config(seed)
        initial = load_torch_policy_value_checkpoint(
            str(initialization_checkpoint_path)
        )
        gate = build_training_gate_report(dataset, override="narrow_curriculum")
        result = train_torch_policy_value(
            dataset,
            config,
            gate_report=gate,
            initial_model=initial,
            ordered_batch_plan=t064_plan_indices(
                plan, identity_to_trainer_index=identity_to_trainer_index
            ),
        )
        problems = list(result.report.problems)
        checkpoint: dict[str, Any] = {
            "path": str(output),
            "sha256": "0" * 64,
            "bytes": 0,
        }
        if result.report.training_ok:
            provenance = _t064_training_data_provenance(
                dataset,
                trainer_input_path,
                trainer_sha256=trainer_sha256,
                trainer_byte_count=trainer_byte_count,
                gate_report=gate,
            )
            save_torch_policy_value_checkpoint(
                result,
                str(temporary),
                training_data_provenance=provenance,
                metadata={
                    "task_id": "T064",
                    "arm": arm,
                    "seed": seed,
                    "initialization_sha256": initialization_sha256,
                    "batch_plan_sha256": plan["batch_plan_sha256"],
                },
            )
            written = load_torch_policy_value_checkpoint(str(temporary))
            _validate_loaded_t064_run_checkpoint(
                written,
                arm=arm,
                seed=seed,
                initialization_sha256=initialization_sha256,
                plan=plan,
                expected_provenance=provenance,
            )
            os.replace(temporary, output)
            checkpoint = _file_identity(output)
        else:
            problems.append("T064 checkpoint was not written")
        runs.append(
            _t064_training_run_entry(
                arm=arm,
                seed=seed,
                initialization_sha256=initialization_sha256,
                trainer_sha256=trainer_sha256,
                trainer_byte_count=trainer_byte_count,
                plan=plan,
                checkpoint=checkpoint,
                completion_status="complete" if result.report.training_ok else "failed",
                problems=problems,
                disposition="trained_new",
            )
        )
    return {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": runs,
    }


@dataclass(frozen=True)
class _T064Stage4RunRequest:
    manifest_path: Path
    trainer_input_path: Path
    initialization_checkpoint_path: Path
    initialization_sha256: str
    checkpoint_path: Path
    arm: str
    seed: int


def _load_t064_stage4_worker_inputs(request: _T064Stage4RunRequest) -> tuple[Any, Any]:
    with request.manifest_path.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    with request.trainer_input_path.open(encoding="utf-8") as stream:
        dataset = load_trainer_input_dataset_jsonl(stream)
    order = dataset.generation_metadata.get("t064_complete_identity_order")
    if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
        raise ValueError("T064 Stage4 trainer input lacks identity-bound order")
    if len(set(order)) != len(order):
        raise ValueError("T064 Stage4 trainer input identity order is duplicated")
    return manifest, dataset


def _run_t064_stage4_worker(request: _T064Stage4RunRequest) -> Mapping[str, Any]:
    manifest, dataset = _load_t064_stage4_worker_inputs(request)
    order = dataset.generation_metadata["t064_complete_identity_order"]
    report = run_t064_paired_training(
        selected_manifest=manifest,
        dataset=dataset,
        initialization_checkpoint_path=request.initialization_checkpoint_path,
        initialization_sha256=request.initialization_sha256,
        trainer_input_path=request.trainer_input_path,
        identity_to_trainer_index={
            identity: index for index, identity in enumerate(order)
        },
        checkpoint_paths={(request.arm, request.seed): request.checkpoint_path},
        run_order=((request.arm, request.seed),),
    )
    run = report["runs"][0]
    del report, dataset, manifest
    gc.collect()
    return run


def _validate_reusable_t064_stage4_worker(
    request: _T064Stage4RunRequest,
) -> Mapping[str, Any]:
    from sts_combat_rl.sim.torch_policy_value import (
        load_torch_policy_value_checkpoint,
    )
    from sts_combat_rl.sim.training_gate import build_training_gate_report

    if _sha256(request.initialization_checkpoint_path) != request.initialization_sha256:
        raise ValueError("T064 initialization checkpoint identity mismatch")
    manifest, dataset = _load_t064_stage4_worker_inputs(request)
    plans = _validated_t064_training_plans(manifest)
    plan = plans[(request.arm, request.seed)]
    trainer_sha256 = _sha256(request.trainer_input_path)
    trainer_byte_count = request.trainer_input_path.stat().st_size
    gate = build_training_gate_report(dataset, override="narrow_curriculum")
    expected_provenance = _t064_training_data_provenance(
        dataset,
        request.trainer_input_path,
        trainer_sha256=trainer_sha256,
        trainer_byte_count=trainer_byte_count,
        gate_report=gate,
    )
    loaded = load_torch_policy_value_checkpoint(str(request.checkpoint_path))
    _validate_loaded_t064_run_checkpoint(
        loaded,
        arm=request.arm,
        seed=request.seed,
        initialization_sha256=request.initialization_sha256,
        plan=plan,
        expected_provenance=expected_provenance,
    )
    checkpoint_identity = _file_identity(request.checkpoint_path)
    retained_identity = T064_RETAINED_REUSABLE_CHECKPOINT_IDENTITIES.get(
        (request.arm, request.seed)
    )
    if retained_identity is not None and any(
        checkpoint_identity[field] != value
        for field, value in retained_identity.items()
    ):
        raise ValueError("T064 retained checkpoint file identity mismatch")
    return _t064_training_run_entry(
        arm=request.arm,
        seed=request.seed,
        initialization_sha256=request.initialization_sha256,
        trainer_sha256=trainer_sha256,
        trainer_byte_count=trainer_byte_count,
        plan=plan,
        checkpoint=checkpoint_identity,
        completion_status="complete",
        problems=(),
        disposition="reused_validated",
    )


def _t064_stage4_process_executor(max_workers: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=multiprocessing.get_context("spawn"),
    )


def _validate_reusable_t064_stage4_isolated(
    request: _T064Stage4RunRequest,
) -> Mapping[str, Any]:
    with _t064_stage4_process_executor(1) as executor:
        return executor.submit(_validate_reusable_t064_stage4_worker, request).result()


def _canonical_t064_training_report(
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    for run in runs:
        arm = run.get("arm")
        seed = run.get("seed")
        if (
            not isinstance(arm, str)
            or not isinstance(seed, int)
            or isinstance(seed, bool)
        ):
            raise ValueError("T064 completed/reused run inventory is invalid")
        key = (arm, seed)
        if key not in TRAINING_RUN_ORDER or key in by_key:
            raise ValueError("T064 completed/reused run inventory is invalid")
        by_key[key] = run
    if set(by_key) != set(TRAINING_RUN_ORDER):
        raise ValueError("T064 Stage4 did not produce all four frozen runs")
    return {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": [dict(by_key[key]) for key in TRAINING_RUN_ORDER],
    }


def _validate_cached_t064_reuse_summary(
    run: Mapping[str, Any],
    *,
    key: tuple[str, int],
    plan: Mapping[str, Any],
    initialization_sha256: str,
    trainer_sha256: str,
    trainer_byte_count: int,
) -> None:
    arm, seed = key
    expected = {
        "arm": arm,
        "seed": seed,
        "initialization_sha256": initialization_sha256,
        "configuration": frozen_training_configuration(seed=seed),
        "trainer_input_sha256": trainer_sha256,
        "trainer_input_bytes": trainer_byte_count,
        "batch_plan_sha256": plan["batch_plan_sha256"],
        "per_bucket_exposure_counts": _bucket_exposure_counts(plan),
        "per_source_exposure_counts": plan["per_source_exposure_counts"],
        "run_disposition": "reused_validated",
        "completion_status": "complete",
        "problems": [],
    }
    if any(run.get(field) != value for field, value in expected.items()):
        raise ValueError("T064 cached reusable run summary no longer matches inputs")
    linkage = run.get("checkpoint_metadata_linkage")
    if not isinstance(linkage, Mapping) or any(
        linkage.get(field) != value
        for field, value in {
            "schema_id": "torch-policy-value-checkpoint-v1",
            "training_ok": True,
            "task_id": "T064",
            "arm": arm,
            "seed": seed,
            "initialization_sha256": initialization_sha256,
            "batch_plan_sha256": plan["batch_plan_sha256"],
            "trainer_input_sha256": trainer_sha256,
            "trainer_input_bytes": trainer_byte_count,
        }.items()
    ):
        raise ValueError("T064 cached reusable checkpoint linkage is invalid")


def _run_t064_stage4_requests(
    requests: Sequence[_T064Stage4RunRequest],
) -> list[Mapping[str, Any]]:
    if not requests:
        return []
    completed: list[Mapping[str, Any]] = []
    failures: list[BaseException] = []
    worker_count = min(T064_STAGE4_MAX_WORKERS, len(requests))
    with _t064_stage4_process_executor(worker_count) as executor:
        futures = [
            executor.submit(_run_t064_stage4_worker, request) for request in requests
        ]
        for future in as_completed(futures):
            try:
                completed.append(future.result())
            except BaseException as exc:
                failures.append(exc)
    if failures:
        raise RuntimeError(
            "T064 Stage4 worker failed; other complete checkpoints are retained "
            "for a later strict reuse audit"
        ) from failures[0]
    return completed


def run_t064_stage4_production(
    *,
    manifest_path: Path,
    trainer_input_path: Path,
    initialization_checkpoint_path: Path,
    initialization_sha256: str,
    checkpoint_root: Path,
    frozen_t070_manifest_path: Path,
    earliest_affected_run: str | None = None,
    failure_recovery: bool = False,
    reusable_runs: Mapping[tuple[str, int], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run missing jobs in at most two isolated workers and canonically aggregate."""

    del frozen_t070_manifest_path  # Stage-4 preflight owns this frozen input.
    reusable_keys = set(
        _t064_reusable_run_keys(
            earliest_affected_run,
            failure_recovery=failure_recovery,
        )
    )
    validated_reuse = dict(reusable_runs or {})
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    plans = _validated_t064_training_plans(manifest)
    trainer_sha256 = _sha256(trainer_input_path)
    trainer_byte_count = trainer_input_path.stat().st_size
    paths = {
        (arm, seed): checkpoint_root / f"{arm}-{seed}.pt"
        for arm, seed in TRAINING_RUN_ORDER
    }
    for path in paths.values():
        partial = path.with_suffix(path.suffix + ".tmp")
        if partial.exists():
            raise ValueError(
                f"T064 Stage4 partial checkpoint blocks execution: {partial}"
            )
    for key, path in paths.items():
        if not path.exists():
            continue
        if key not in reusable_keys:
            raise ValueError("T064 Stage4 found an affected existing checkpoint")
        if key not in validated_reuse:
            validated_reuse[key] = _validate_reusable_t064_stage4_isolated(
                _T064Stage4RunRequest(
                    manifest_path=manifest_path,
                    trainer_input_path=trainer_input_path,
                    initialization_checkpoint_path=initialization_checkpoint_path,
                    initialization_sha256=initialization_sha256,
                    checkpoint_path=path,
                    arm=key[0],
                    seed=key[1],
                )
            )
        if validated_reuse[key].get("checkpoint") != _file_identity(path):
            raise ValueError("T064 reusable checkpoint changed after preflight")
        _validate_cached_t064_reuse_summary(
            validated_reuse[key],
            key=key,
            plan=plans[key],
            initialization_sha256=initialization_sha256,
            trainer_sha256=trainer_sha256,
            trainer_byte_count=trainer_byte_count,
        )
    if set(validated_reuse) != {key for key, path in paths.items() if path.exists()}:
        raise ValueError("T064 reusable checkpoint inventory does not match disk")
    requests = [
        _T064Stage4RunRequest(
            manifest_path=manifest_path,
            trainer_input_path=trainer_input_path,
            initialization_checkpoint_path=initialization_checkpoint_path,
            initialization_sha256=initialization_sha256,
            checkpoint_path=path,
            arm=key[0],
            seed=key[1],
        )
        for key, path in paths.items()
        if not path.exists()
    ]
    del manifest, plans
    gc.collect()
    trained = _run_t064_stage4_requests(requests)
    return _canonical_t064_training_report([*validated_reuse.values(), *trained])


def validate_t044_reuse(
    report: Any, *, cohort_identity: str, cohort_count: int
) -> bool:
    """Accept historical independent arms only under the frozen persisted contract."""

    config = getattr(report, "comparison_config", None)
    arms = getattr(report, "arms", None)
    if not isinstance(config, Mapping) or not isinstance(arms, tuple):
        return False
    roles = config.get("controller_roles")
    if not isinstance(roles, Mapping) or tuple(roles.values()) != T044_CONTROLLER_ROLES:
        return False
    if (
        config.get("cohort_identity") != cohort_identity
        or config.get("cohort_record_count") != cohort_count
    ):
        return False
    if config.get("max_battle_steps") != 200 or config.get("run_scale") != "fixed":
        return False
    if not _is_t044_frozen_action_space(config.get("action_space")):
        return False
    if not getattr(report, "evaluation_successful", False) or len(arms) != 4:
        return False
    return tuple(
        getattr(arm, "role", None) for arm in arms
    ) == T044_CONTROLLER_ROLES and all(
        not arm.report.problems and len(arm.report.battle_results) == cohort_count
        for arm in arms
    )


def t044_independent_arm_disposition(
    historical_report: Any | None,
    *,
    frozen_cohort: Mapping[str, Any],
) -> str:
    """Choose a historical four-arm reuse or one clean independent-arm rerun.

    The dependent two-arm output is never a substitute for the independent
    baseline/scripted evidence.  A failed historical validation therefore
    schedules precisely one baseline/scripted fixed-cohort rerun for that cohort.
    """

    if historical_report is not None and validate_t044_historical_reuse(
        historical_report, frozen_cohort=frozen_cohort
    ):
        return "reuse_historical_four_arm"
    return "rerun_once_two_independent_arms"


def run_t064_t044_dependent_stage(
    *,
    adapter_factory: Callable[[], Any],
    cohort_path: Path,
    controller_arms: Sequence[Any],
    cohort_kind: str,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
    shard_runner: Callable[
        ..., Any
    ] = run_de_assisted_fixed_cohort_comparison_from_cohort_path,
    merger: Callable[..., Any] = merge_de_assisted_fixed_cohort_comparison_shards,
    report_writer: Callable[
        [Path, Any], None
    ] = write_de_assisted_fixed_cohort_comparison_report,
    dispatch_backend: str = "thread",
) -> tuple[Any, list[dict[str, Any]]]:
    """Run/merge only the two checkpoint-dependent T044 arms in 16 shards."""

    if cohort_kind == "assist_0":
        ranges = T044_ASSIST_0_RANGES
    elif cohort_kind == "assist_hp50":
        ranges = T044_ASSIST_HP50_RANGES
    else:
        raise ValueError("T064 only evaluates the two frozen T044 cohorts")
    roles = tuple(item[1] for item in controller_arms)
    if roles != T044_DEPENDENT_ROLES:
        raise ValueError("T064 T044 stage must contain only persisted dependent roles")
    refuse_overwrite(merged_output_path)
    shard_output_dir.mkdir(parents=True, exist_ok=True)

    def one(index: int, record_range: str) -> Any:
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        refuse_overwrite(output)
        shard = shard_runner(
            adapter_factory,
            cohort_path,
            controller_arms=controller_arms,
            action_space=controller_arms[0][2].action_space,
            max_battle_steps=200,
            run_scale="fixed",
            record_range=record_range,
        )
        report_writer(output, shard)
        return shard

    shards, shard_records = dispatch_t064_shards(
        ranges=ranges,
        log_dir=log_dir,
        worker=one,
        backend=dispatch_backend,
    )
    merged = merger(cohort_path=cohort_path, shards=shards, expected_ranges=ranges)
    report_writer(merged_output_path, merged)
    return merged, shard_records


def run_t064_stage5_dependent_production(
    *,
    cohort_path: Path,
    checkpoint_path: Path,
    cohort_kind: str,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
) -> tuple[Any, list[dict[str, Any]]]:
    """Construct the existing LightSpeed T044 dependent arms for one checkpoint."""

    from sts_combat_rl.commands.lightspeed_cli import (
        MODEL_GUIDED_ORACLE_V2_LABEL,
        RAW_CHECKPOINT_POLICY_LABEL,
    )
    from sts_combat_rl.sim.action_space import ActionSpaceConfig
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
    from sts_combat_rl.commands.model_guided_oracle_search import (
        build_torch_guidance_scorer_from_checkpoint,
    )
    from sts_combat_rl.sim.model_guided_oracle_search import (
        ModelGuidedOracleSearchV2Controller,
    )
    from sts_combat_rl.sim.search_guidance_policy import SearchGuidancePolicyController

    action_space = ActionSpaceConfig.initial_no_potions()
    scorer = build_torch_guidance_scorer_from_checkpoint(checkpoint_path)
    guided = ModelGuidedOracleSearchV2Controller(
        simulations=T044_SEARCH_BUDGET,
        scorer=scorer,
        policy_probability_weight=T044_GUIDANCE_WEIGHT,
        action_space=action_space,
    )
    raw = SearchGuidancePolicyController(scorer)
    return run_t064_t044_dependent_stage(
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        cohort_path=cohort_path,
        controller_arms=(
            (
                MODEL_GUIDED_ORACLE_V2_LABEL,
                T044_DEPENDENT_ROLES[0],
                guided,
            ),
            (RAW_CHECKPOINT_POLICY_LABEL, T044_DEPENDENT_ROLES[1], raw),
        ),
        cohort_kind=cohort_kind,
        log_dir=log_dir,
        shard_output_dir=shard_output_dir,
        merged_output_path=merged_output_path,
        dispatch_backend="fork",
    )


def run_t064_stage5_independent_production(
    *,
    cohort_path: Path,
    cohort_kind: str,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
) -> tuple[Any, list[dict[str, Any]]]:
    """Run exactly the checkpoint-independent baseline/scripted fallback arms."""
    from sts_combat_rl.commands.lightspeed_cli import (
        BASELINE_ORACLE_LABEL,
        SCRIPTED_POLICY_LABEL,
    )
    from sts_combat_rl.sim.action_space import ActionSpaceConfig
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
    from sts_combat_rl.sim.oracle_search import OracleSearchController
    from sts_combat_rl.sim.model_scoring import ActionKindPriorScorer
    from sts_combat_rl.sim.online_controller import PolicyController
    from sts_combat_rl.sim.policy import ScoredActionPolicy

    action_space = ActionSpaceConfig.initial_no_potions()
    return run_t064_t044_independent_fallback_stage(
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        cohort_path=cohort_path,
        controller_arms=(
            (
                BASELINE_ORACLE_LABEL,
                T044_INDEPENDENT_ROLES[0],
                OracleSearchController(
                    simulations=1,
                    root_selection_rule="highest_mean",
                    action_space=action_space,
                ),
            ),
            (
                SCRIPTED_POLICY_LABEL,
                T044_INDEPENDENT_ROLES[1],
                PolicyController(
                    ScoredActionPolicy(
                        ActionKindPriorScorer(), name=SCRIPTED_POLICY_LABEL
                    )
                ),
            ),
        ),
        cohort_kind=cohort_kind,
        log_dir=log_dir,
        shard_output_dir=shard_output_dir,
        merged_output_path=merged_output_path,
        dispatch_backend="fork",
    )


def run_t064_stage5_historical_disposition_production(
    *,
    cohort_path: Path,
    cohort_kind: str,
    historical_report_path: Path,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
) -> tuple[bool, Any, list[dict[str, Any]]]:
    """Reuse a valid T044 historical report or rerun independent arms once.

    This is intentionally a cohort-level route.  It never accepts a checkpoint
    and is therefore not one of the eight checkpoint-dependent T044 stages.
    """

    if cohort_kind not in {"assist_0", "assist_hp50"}:
        raise ValueError("T064 historical disposition only accepts frozen T044 cohorts")
    with cohort_path.open(encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    expected_count = 21 if cohort_kind == "assist_0" else 38
    if (
        len(cohort.records) != expected_count
        or cohort.problems
        or [record.cohort_index for record in cohort.records]
        != list(range(expected_count))
    ):
        raise ValueError("T064 historical disposition cohort is not frozen/ordered")
    frozen_cohort = {
        "identity": cohort.identity,
        "record_count": expected_count,
        "artifact": _file_identity(cohort_path),
        "source_pool_format_version": cohort.source_pool_format_version,
        "source_pool_controller_provenance": cohort.source_pool_controller_provenance,
        "selection_config": cohort.selection_config.to_dict(),
    }
    cohort = _validate_t044_frozen_cohort(frozen_cohort, cohort_kind=cohort_kind)
    historical: Any | None = None
    try:
        with historical_report_path.open(encoding="utf-8") as stream:
            historical = load_de_assisted_fixed_cohort_comparison_jsonl(stream)
        if not validate_t044_historical_reuse(historical, frozen_cohort=frozen_cohort):
            historical = None
        elif not validate_t044_independent_report(
            historical,
            cohort_identity=cohort.identity,
            cohort_count=expected_count,
            cohort=cohort,
        ):
            historical = None
        else:
            _validate_t044_controller_semantics(historical, checkpoint=None)
    except (OSError, ValueError, json.JSONDecodeError):
        historical = None
    if historical is not None:
        return True, historical, []
    report, records = run_t064_stage5_independent_production(
        cohort_path=cohort_path,
        cohort_kind=cohort_kind,
        log_dir=log_dir,
        shard_output_dir=shard_output_dir,
        merged_output_path=merged_output_path,
    )
    if not validate_t044_independent_report(
        report,
        cohort_identity=cohort.identity,
        cohort_count=expected_count,
        cohort=cohort,
    ):
        raise ValueError("T064 independent T044 fallback is incomplete")
    _validate_t044_controller_semantics(report, checkpoint=None)
    return False, report, records


def run_t064_t044_independent_fallback_stage(
    *,
    adapter_factory: Callable[[], Any],
    cohort_path: Path,
    controller_arms: Sequence[Any],
    cohort_kind: str,
    log_dir: Path,
    shard_output_dir: Path,
    merged_output_path: Path,
    shard_runner: Callable[
        ..., Any
    ] = run_de_assisted_fixed_cohort_comparison_from_cohort_path,
    merger: Callable[..., Any] = merge_de_assisted_fixed_cohort_comparison_shards,
    report_writer: Callable[
        [Path, Any], None
    ] = write_de_assisted_fixed_cohort_comparison_report,
    dispatch_backend: str = "thread",
) -> tuple[Any, list[dict[str, Any]]]:
    """Rerun only baseline+scripted once for one invalid historical cohort."""

    ranges = {
        "assist_0": T044_ASSIST_0_RANGES,
        "assist_hp50": T044_ASSIST_HP50_RANGES,
    }.get(cohort_kind)
    if ranges is None:
        raise ValueError("T064 fallback only accepts frozen T044 cohorts")
    if tuple(item[1] for item in controller_arms) != T044_INDEPENDENT_ROLES:
        raise ValueError("T064 T044 fallback must contain baseline/scripted only")
    refuse_overwrite(merged_output_path)
    shard_output_dir.mkdir(parents=True, exist_ok=True)

    def one(index: int, record_range: str) -> Any:
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        refuse_overwrite(output)
        shard = shard_runner(
            adapter_factory,
            cohort_path,
            controller_arms=controller_arms,
            action_space=controller_arms[0][2].action_space,
            max_battle_steps=200,
            run_scale="fixed",
            record_range=record_range,
        )
        report_writer(output, shard)
        return shard

    shards, records = dispatch_t064_shards(
        ranges=ranges,
        log_dir=log_dir,
        worker=one,
        backend=dispatch_backend,
    )
    merged = merger(cohort_path=cohort_path, shards=shards, expected_ranges=ranges)
    report_writer(merged_output_path, merged)
    return merged, records


def validate_t070_baseline_reuse(
    report: Mapping[str, Any],
    *,
    cohort_identity: str,
    frozen_contract: Mapping[str, Any] | None = None,
    cohort: Any | None = None,
) -> bool:
    """Validate the T070 baseline without treating a display label as an arm role."""

    valid = (
        report.get("schema_id") == "t070-single-arm-merged-stage-v1"
        and report.get("cohort_identity") == cohort_identity
        and report.get("cohort_record_count") == 93
        and report.get("arm") == "baseline"
        and report.get("native_budget") == 100
        # Merged T070 reports preserve tree geometry under controller
        # provenance; older compact fixtures additionally carry this top-level
        # convenience field.  Missing means the accepted primary default only
        # until the strict provenance branch below verifies it.
        and report.get("tree_geometry_enabled", False) is False
        and tuple(report.get("shard_ranges", ())) == T070_T052_RANGES
        and report.get("command_passed") is True
        and not report.get("problems")
    )
    if not valid or frozen_contract is None:
        return False
    expected_stages = [
        item
        for item in frozen_contract.get("primary_stage_inventory", [])
        if isinstance(item, Mapping)
        and item.get("arm") == "baseline"
        and item.get("native_budget") == 100
        and item.get("tree_geometry_enabled") is False
    ]
    if len(expected_stages) != 1:
        return False
    expected_stage = expected_stages[0]
    if (
        report.get("code_commit") != frozen_contract.get("code_commit")
        or report.get("native_commit") != frozen_contract.get("native_commit")
        or report.get("family") != expected_stage.get("family")
        or report.get("stage_name") != expected_stage.get("stage_name")
        or report.get("worker_count") != 16
        or report.get("shard_count") != 16
        or report.get("effective_parallel_workers") != 16
    ):
        return False
    arm_report = report.get("arm_report")
    if not isinstance(arm_report, Mapping):
        return False
    if (
        arm_report.get("record_count") != 93
        or arm_report.get("wins", 0) + arm_report.get("losses", 0) != 93
        or arm_report.get("truncations") != 0
        or arm_report.get("errors") != 0
        or arm_report.get("evaluation_problems")
    ):
        return False
    controller = report.get("controller_provenance")
    config = controller.get("config") if isinstance(controller, Mapping) else None
    if not isinstance(config, Mapping):
        return False
    from sts_combat_rl.sim.action_space import ActionSpaceConfig

    required_controller = {
        "information_regime": "full_simulator_state_oracle_like",
        "root_selection_rule": "highest_mean",
        "ablation": "baseline",
    }
    for field, expected in required_controller.items():
        observed = config.get(field)
        if isinstance(expected, Mapping):
            if not isinstance(observed, Mapping) or any(
                observed.get(key) != value for key, value in expected.items()
            ):
                return False
        elif observed != expected:
            return False
    if config.get("action_space") != ActionSpaceConfig.initial_no_potions().to_dict():
        return False
    search_budget = config.get("search_budget")
    if (
        not isinstance(search_budget, Mapping)
        or search_budget.get("simulations") != 100
    ):
        return False
    geometry = config.get("tree_geometry", {})
    guidance = config.get("tree_internal_guidance")
    if (
        not isinstance(geometry, Mapping)
        or geometry.get("enabled", False) is not False
        or not isinstance(guidance, Mapping)
        or guidance.get("policy_prior") is not False
        or guidance.get("learned_leaf_value") is not False
        or guidance.get("root_only_or_post_search_fallback") is not False
    ):
        return False
    if cohort is None:
        return True
    rows = arm_report.get("records")
    if not isinstance(rows, list) or len(rows) != 93:
        return False
    if [
        row.get("cohort_index") if isinstance(row, Mapping) else None for row in rows
    ] != list(range(93)):
        return False
    for row, record in zip(rows, cohort.records, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("problems")
            or row.get("termination_status") not in {"win", "loss"}
        ):
            return False
        if row.get("structural_metadata") != record.structural_metadata:
            return False
        for field in (
            "source_checkpoint_id",
            "source_run_id",
            "source_seed",
            "source_battle_index",
            "source_distribution_kind",
            "checkpoint_information_regime",
        ):
            if field in row and row.get(field) != getattr(record, field):
                return False
    return True


def _validate_t064_stage6_preflight(
    *,
    baseline: Mapping[str, Any],
    baseline_path: Path,
    contract: Mapping[str, Any],
    cohort_path: Path,
    wrapper_manifest_path: Path,
    checkpoint_path: Path,
    selection_key: str,
) -> bool:
    """Complete Stage 6 validation before its attempt directory or shard calls."""

    try:
        frozen = load_t070_frozen_contract(
            wrapper_manifest_path, t064_selection=selection_key
        )
        inputs = frozen.get("input_identities")
        if not isinstance(inputs, Mapping):
            return False
        artifact = inputs.get("t052_fixed_cohort")
        source = inputs.get("sts_lightspeed_source_manifest")
        if not isinstance(artifact, Mapping) or not isinstance(source, Mapping):
            return False
        if (
            contract.get("cohort_artifact") != artifact
            or contract.get("source_manifest_artifact") != source
        ):
            return False
        baseline_identity = contract.get("baseline_artifact")
        if not isinstance(baseline_identity, Mapping):
            return False
        validate_external_frozen_identity(
            baseline_path, baseline_identity, label="T070 baseline report"
        )
        validate_external_frozen_identity(cohort_path, artifact, label="T052 cohort")
        with cohort_path.open(encoding="utf-8") as stream:
            cohort = load_fixed_cohort_jsonl(stream)
        if (
            cohort.identity != frozen.get("primary_cohort_identity")
            or contract.get("cohort_identity") != frozen.get("primary_cohort_identity")
            or len(cohort.records) != 93
            or cohort.problems
            or [record.cohort_index for record in cohort.records] != list(range(93))
        ):
            return False
        validate_external_frozen_identity(
            Path(str(source.get("path", ""))), source, label="source manifest"
        )
        baseline_stages = [
            item
            for item in frozen.get("primary_stage_inventory", [])
            if isinstance(item, Mapping)
            and item.get("arm") == "baseline"
            and item.get("native_budget") == 100
            and item.get("tree_geometry_enabled") is False
        ]
        if (
            frozen.get("primary_record_count") != 93
            or tuple(frozen.get("primary_shard_ranges", ())) != T070_T052_RANGES
            or frozen.get("primary_worker_count") != 16
            or frozen.get("projection_mode") != "accepted_t069_search_scope_projection"
            or frozen.get("primary_geometry_disabled") is not True
            or len(baseline_stages) != 1
        ):
            return False
        expected_checkpoint = expected_checkpoint_identity_from_stage_manifest(
            wrapper_manifest_path, t064_selection=selection_key
        )
        if (
            _sha256(checkpoint_path) != expected_checkpoint["sha256"]
            or checkpoint_path.stat().st_size != expected_checkpoint["bytes"]
        ):
            return False
        return validate_t070_baseline_reuse(
            baseline,
            cohort_identity=cohort.identity,
            frozen_contract=frozen,
            cohort=cohort,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def t064_t070_wrapper(
    *,
    current_code_commit: str,
    frozen_t070_manifest: Mapping[str, Any],
    frozen_identity: Mapping[str, Any],
    checkpoint_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the identity-bound wrapper consumed by the parameterized T070 runner."""

    if frozen_t070_manifest.get("schema_id") != FROZEN_MANIFEST_SCHEMA_ID:
        raise ValueError("T064 wrapper needs the historical T070 frozen manifest")
    if frozen_t070_manifest.get("code_commit") == current_code_commit:
        raise ValueError(
            "T064 must bind T070 to its historical, not current, code commit"
        )
    if tuple(frozen_t070_manifest.get("primary_shard_ranges", ())) != T070_T052_RANGES:
        raise ValueError("T064 wrapper refuses non-frozen T070 ranges")
    inventory = frozen_t070_manifest.get("primary_stage_inventory")
    required_stage = {
        "stage_name": "equal-prior-value-0100",
        "arm": "prior_value",
        "family": "equal_nominal",
        "native_budget": 100,
        "tree_geometry_enabled": False,
    }
    if not isinstance(inventory, list) or required_stage not in inventory:
        raise ValueError("T064 wrapper requires the accepted T070 prior_value stage")
    return {
        # This mapping is the persisted ``t070_stage_manifest`` member of an
        # existing t064-curriculum-manifest-v1, consumed directly by the T070
        # reader and shard script.  It is not an alternate wrapper schema.
        "checkpoint": dict(checkpoint_identity),
        "frozen_t070_manifest": dict(frozen_identity),
        "historical_code_commit": frozen_t070_manifest["code_commit"],
        "current_code_commit": current_code_commit,
        "arm": "prior_value",
        "native_budget": 100,
        "tree_geometry_enabled": False,
        "projection_mode": "accepted_t069_search_scope_projection",
        "shard_ranges": list(T070_T052_RANGES),
        "worker_count": 16,
    }


def build_t064_t070_checkpoint_selections(
    *,
    current_code_commit: str,
    frozen_t070_manifest: Mapping[str, Any],
    frozen_identity: Mapping[str, Any],
    checkpoints: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the one manifest member holding all four checkpoint selections.

    The caller writes this once into the sole final
    ``t064-curriculum-manifest-v1`` before Stage 6.  The existing T070 reader
    selects a checkpoint by key; no per-checkpoint compact-manifest copies are
    allowed.
    """

    if tuple(checkpoints) != tuple(f"{arm}:{seed}" for arm, seed in TRAINING_RUN_ORDER):
        raise ValueError("T064 T070 selections must use the four frozen run keys")
    first = t064_t070_wrapper(
        current_code_commit=current_code_commit,
        frozen_t070_manifest=frozen_t070_manifest,
        frozen_identity=frozen_identity,
        checkpoint_identity=next(iter(checkpoints.values())),
    )
    return {
        "frozen_t070_manifest": first["frozen_t070_manifest"],
        "historical_code_commit": first["historical_code_commit"],
        "current_code_commit": first["current_code_commit"],
        "arm": first["arm"],
        "native_budget": first["native_budget"],
        "tree_geometry_enabled": first["tree_geometry_enabled"],
        "projection_mode": first["projection_mode"],
        "shard_ranges": first["shard_ranges"],
        "worker_count": first["worker_count"],
        "checkpoint_selections": {
            key: {"checkpoint": dict(checkpoint)}
            for key, checkpoint in checkpoints.items()
        },
    }


def persist_t064_t070_checkpoint_selections(
    *,
    manifest_path: Path,
    code_commit: str,
    frozen_t070_manifest: Mapping[str, Any],
    frozen_identity: Mapping[str, Any],
    checkpoints: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Atomically add all four selections to the one authorized manifest file."""

    with manifest_path.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    validate_resume_manifest(manifest, code_commit=code_commit)
    if manifest.get("t070_stage_manifest") is not None:
        raise ValueError("T064 refuses to overwrite its persisted T070 selections")
    selections = build_t064_t070_checkpoint_selections(
        current_code_commit=code_commit,
        frozen_t070_manifest=frozen_t070_manifest,
        frozen_identity=frozen_identity,
        checkpoints=checkpoints,
    )
    updated = dict(manifest)
    updated["t070_stage_manifest"] = selections
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    refuse_overwrite(temporary)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            dump_compact_json(updated, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, manifest_path)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    return updated


def run_t064_t070_shard_script(
    *,
    script_path: Path,
    python_executable: str,
    cohort_path: Path,
    checkpoint_path: Path,
    wrapper_manifest_path: Path,
    native_preflight_path: Path,
    native_checkout: Path,
    native_build_root: Path,
    code_commit: str,
    selection_key: str,
    output_path: Path,
    record_range: str,
    shard_index: int,
) -> subprocess.CompletedProcess[str]:
    """Invoke the repository T070 shard script with its real argument surface."""

    if output_path.exists():
        raise ValueError("T064 T070 shard refuses to overwrite output")
    command = [
        python_executable,
        str(script_path),
        "--cohort",
        str(cohort_path),
        "--checkpoint",
        str(checkpoint_path),
        "--frozen-manifest",
        str(wrapper_manifest_path),
        "--native-preflight",
        str(native_preflight_path),
        "--native-checkout",
        str(native_checkout),
        "--native-build-root",
        str(native_build_root),
        "--output",
        str(output_path),
        "--code-commit",
        code_commit,
        "--stage-name",
        "equal-prior-value-0100",
        "--t064-selection",
        selection_key,
        "--arm",
        "prior_value",
        "--family",
        "equal_nominal",
        "--budget",
        "100",
        "--record-range",
        record_range,
        "--shard-index",
        str(shard_index),
        "--range-kind",
        "primary",
    ]
    return subprocess.run(command, check=False, text=True, capture_output=True)


def run_t064_t070_prior_value_stage(
    *,
    shard_runner: Callable[..., Mapping[str, Any]],
    merger: Callable[..., Mapping[str, Any]],
    runner_kwargs: Mapping[str, Any],
    shard_dir: Path,
    log_dir: Path,
    merged_output_path: Path,
) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    """Route one checkpoint through the existing T070 16-shard runner/merge."""

    wrapper = runner_kwargs.get("t064_wrapper")
    if not isinstance(wrapper, Mapping):
        raise ValueError("T064 T070 stage requires an identity-bound wrapper")
    if (
        wrapper.get("arm") != "prior_value"
        or wrapper.get("native_budget") != 100
        or wrapper.get("tree_geometry_enabled") is not False
        or tuple(wrapper.get("shard_ranges", ())) != T070_T052_RANGES
        or wrapper.get("worker_count") != 16
        or wrapper.get("historical_code_commit") == wrapper.get("current_code_commit")
        or runner_kwargs.get("code_commit") != wrapper.get("current_code_commit")
    ):
        raise ValueError("T064 T070 wrapper/runner contract mismatch")
    forwarded_kwargs = {
        key: value for key, value in runner_kwargs.items() if key != "t064_wrapper"
    }
    refuse_overwrite(merged_output_path)
    shard_dir.mkdir(parents=True, exist_ok=True)
    ranges = T070_T052_RANGES

    def one(index: int, record_range: str) -> Mapping[str, Any]:
        output = shard_dir / f"shard-{index:02d}.json"
        refuse_overwrite(output)
        return shard_runner(
            **forwarded_kwargs,
            stage_name="equal-prior-value-0100",
            arm="prior_value",
            family="equal_nominal",
            record_range=record_range,
            shard_index=index,
            expected_ranges=ranges,
            output_path=output,
            max_battle_steps=200,
        )

    shards, records = dispatch_t064_shards(ranges=ranges, log_dir=log_dir, worker=one)
    merged = merger(
        shard_paths=[shard_dir / f"shard-{index:02d}.json" for index in range(16)],
        expected_ranges=ranges,
        expected_record_count=93,
        output_path=merged_output_path,
    )
    if (
        merged.get("arm") != "prior_value"
        or merged.get("native_budget") != 100
        or merged.get("command_passed") is not True
        or merged.get("problems")
    ):
        raise ValueError(
            "T064 T070 merged stage violates the frozen prior_value contract"
        )
    return merged, records


def compute_transfer_gates(metrics: Mapping[str, Any]) -> dict[str, bool]:
    """Evaluate exactly the six frozen transfer gates from aggregated outcomes."""

    def total(key: str) -> float:
        value = metrics[key]
        if isinstance(value, Mapping):
            return float(sum(value.values()))
        return float(value)

    curriculum_t052 = total("curriculum_t052_prior_value_wins")
    static_t052 = total("static_t052_prior_value_wins")
    paired = metrics["paired_t052_win_deltas"]
    subsets = metrics["t052_subset_deltas"]
    if not isinstance(paired, Mapping) or not isinstance(subsets, Mapping):
        raise ValueError("T064 gates require paired and subset diagnostics")
    return {
        TRANSFER_GATE_NAMES[0]: curriculum_t052 >= static_t052 + 2,
        TRANSFER_GATE_NAMES[1]: all(float(value) >= -1 for value in paired.values()),
        TRANSFER_GATE_NAMES[2]: all(
            float(subsets[name]) >= 0 for name in ("boss", "act2_plus")
        ),
        TRANSFER_GATE_NAMES[3]: total("curriculum_t044_assist_hp50_model_guided_wins")
        >= total("static_t044_assist_hp50_model_guided_wins") + 2,
        TRANSFER_GATE_NAMES[4]: total("curriculum_t044_assist_hp50_raw_policy_wins")
        >= total("static_t044_assist_hp50_raw_policy_wins"),
        TRANSFER_GATE_NAMES[5]: total("curriculum_t044_assist_0_model_guided_wins")
        >= total("static_t044_assist_0_model_guided_wins") - 1,
    }


def write_t064_final_documents(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    training_report: Mapping[str, Any],
    stage_summary: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    referenced_paths: Sequence[Path],
) -> dict[str, Any]:
    """Retired unsafe API; Stage 7 must use the strict artifact aggregator."""

    del manifest, training_report, stage_summary, diagnostics, referenced_paths
    raise RuntimeError(
        "write_t064_final_documents is retired; use aggregate_t064_stage7_from_artifacts"
    )


def assert_exact_compact_inventory(root: Path) -> None:
    """Require all and only the four compact T064 JSON documents before rehash."""

    found = {path.name for path in root.glob("t064-*.json")}
    expected = set(COMPACT_FILENAMES)
    if found != expected:
        raise ValueError(
            "T064 compact artifact inventory must contain exactly four paths"
        )
    for name in COMPACT_FILENAMES:
        with (root / name).open("r", encoding="utf-8") as stream:
            load_compact_json(stream)


def validate_external_frozen_identity(
    path: Path, expected: Mapping[str, Any], *, label: str
) -> dict[str, Any]:
    """Validate a path against an identity frozen outside the report it contains."""

    if not path.is_file():
        raise ValueError(f"T064 frozen {label} artifact is missing")
    actual = _file_identity(path)
    for field in ("sha256", "bytes"):
        if actual[field] != expected.get(field):
            raise ValueError(f"T064 frozen {label} {field} mismatch")
    expected_path = expected.get("path")
    if expected_path is not None and str(path) != expected_path:
        raise ValueError(f"T064 frozen {label} path mismatch")
    return actual


def validate_t044_historical_reuse(
    report: Any,
    *,
    frozen_cohort: Mapping[str, Any],
    expected_roles: Sequence[str] = T044_CONTROLLER_ROLES,
) -> bool:
    """Validate only a historical full four-arm report, never a new 2-arm stage."""

    identity = frozen_cohort.get("identity")
    count = frozen_cohort.get("record_count")
    if not isinstance(identity, str) or not isinstance(count, int):
        return False
    return validate_t044_reuse(
        report, cohort_identity=identity, cohort_count=count
    ) and tuple(arm.role for arm in report.arms) == tuple(expected_roles)


def validate_t044_dependent_report(
    report: Any,
    *,
    cohort_identity: str,
    cohort_count: int,
    expected_controller_provenance: Mapping[str, Any] | None = None,
    cohort: Any | None = None,
) -> bool:
    """Validate a new T064 two-arm output separately from reusable historical arms."""

    config = getattr(report, "comparison_config", {})
    expected_ranges = (
        T044_ASSIST_0_RANGES if cohort_count == 21 else T044_ASSIST_HP50_RANGES
    )
    arms = getattr(report, "arms", ())
    exact_order = all(
        [result.cohort_index for result in arm.report.battle_results]
        == list(range(cohort_count))
        and not arm.report.problems
        for arm in arms
    )
    provenance_ok = (
        expected_controller_provenance is None
        or config.get("controller_provenance") == expected_controller_provenance
    )
    valid = (
        getattr(report, "evaluation_successful", False)
        and tuple(arm.role for arm in arms) == T044_DEPENDENT_ROLES
        and config.get("cohort_identity") == cohort_identity
        and config.get("cohort_record_count") == cohort_count
        and config.get("max_battle_steps") == 200
        and config.get("run_scale") == "fixed"
        and config.get("shard_count") == 16
        and tuple(config.get("shard_ranges", ())) == expected_ranges
        and _is_t044_frozen_action_space(config.get("action_space"))
        and exact_order
        and provenance_ok
        and all(
            len(arm.report.battle_results) == cohort_count and not arm.report.problems
            for arm in arms
        )
    )
    return valid and (cohort is None or _t044_results_match_cohort(arms, cohort))


def validate_t044_independent_report(
    report: Any,
    *,
    cohort_identity: str,
    cohort_count: int,
    cohort: Any | None = None,
) -> bool:
    """Validate the retained four-arm reuse or the two-arm fallback separately."""

    config = getattr(report, "comparison_config", {})
    arms = getattr(report, "arms", ())
    roles = tuple(getattr(arm, "role", None) for arm in arms)
    valid_roles = roles in (T044_CONTROLLER_ROLES, T044_INDEPENDENT_ROLES)
    valid = (
        getattr(report, "evaluation_successful", False)
        and valid_roles
        and config.get("cohort_identity") == cohort_identity
        and config.get("cohort_record_count") == cohort_count
        and config.get("run_scale") == "fixed"
        and config.get("max_battle_steps") == 200
        and _is_t044_frozen_action_space(config.get("action_space"))
        and all(
            [result.cohort_index for result in arm.report.battle_results]
            == list(range(cohort_count))
            and not arm.report.problems
            for arm in arms
        )
    )
    return valid and (cohort is None or _t044_results_match_cohort(arms, cohort))


def _t044_results_match_cohort(arms: Sequence[Any], cohort: Any) -> bool:
    """Require every arm's ordered rows to preserve the frozen source record."""

    for arm in arms:
        for result, record in zip(
            arm.report.battle_results, cohort.records, strict=True
        ):
            if (
                result.source_checkpoint_id != record.source_checkpoint_id
                or result.source_seed != record.source_seed
                or result.source_run_id != record.source_run_id
                or result.source_battle_index != record.source_battle_index
                or result.structural_metadata != record.structural_metadata
            ):
                return False
    return True


def _validate_t044_frozen_cohort(
    contract: Mapping[str, Any], *, cohort_kind: str
) -> Any:
    """Rehash and reload a holdout before accepting any T044 report on it."""

    artifact = contract.get("artifact")
    if not isinstance(artifact, Mapping):
        raise ValueError("T044 frozen cohort artifact identity missing")
    path = Path(str(artifact.get("path", "")))
    validate_external_frozen_identity(
        path, artifact, label=f"T044 {cohort_kind} cohort"
    )
    with path.open(encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    expected_count = 21 if cohort_kind == "assist_0" else 38
    if (
        cohort.identity != contract.get("identity")
        or len(cohort.records) != expected_count
        or contract.get("record_count") != expected_count
        or [record.cohort_index for record in cohort.records]
        != list(range(expected_count))
        or cohort.problems
        or cohort.source_pool_format_version
        != contract.get("source_pool_format_version")
        or cohort.source_pool_controller_provenance
        != contract.get("source_pool_controller_provenance")
        or cohort.selection_config.to_dict() != contract.get("selection_config")
    ):
        raise ValueError("T044 frozen cohort order/source-format contract mismatch")
    return cohort


def _validate_t044_controller_semantics(
    report: Any, *, checkpoint: Mapping[str, Any] | None
) -> None:
    """Derive T044 controller requirements from task constants and a checkpoint."""

    config = getattr(report, "comparison_config", {})
    roles = config.get("controller_roles") if isinstance(config, Mapping) else None
    provenance = (
        config.get("controller_provenance") if isinstance(config, Mapping) else None
    )
    if not isinstance(roles, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError("T044 roles/controller provenance are missing")
    actual_roles = tuple(getattr(arm, "role", None) for arm in report.arms)
    if (
        actual_roles
        not in (
            T044_CONTROLLER_ROLES,
            T044_DEPENDENT_ROLES,
            T044_INDEPENDENT_ROLES,
        )
        or tuple(roles.values()) != actual_roles
        or len(set(actual_roles)) != len(actual_roles)
    ):
        raise ValueError("T044 persisted role set is not an exact accepted type")
    by_role = {role: label for label, role in roles.items()}
    for role in actual_roles:
        label = by_role.get(role)
        if label is None:
            raise ValueError(f"T044 controller label missing for {role}")
        entry = provenance.get(label) if isinstance(label, str) else None
        if not isinstance(entry, Mapping):
            raise ValueError(f"T044 controller provenance missing for {role}")
        settings = entry.get("config")
        if not isinstance(settings, Mapping):
            raise ValueError(f"T044 controller config missing for {role}")
        if role in {"baseline_oracle_search", "model_guided_search_t043_checkpoint"}:
            budget = settings.get("search_budget")
            if (
                not isinstance(budget, Mapping)
                or budget.get("simulations") != T044_SEARCH_BUDGET
                or settings.get("root_selection_rule") != T044_ROOT_SELECTION
                or settings.get("information_regime")
                != "full_simulator_state_oracle_like"
            ):
                raise ValueError(f"T044 search semantics mismatch for {role}")
            action_space = settings.get("action_space")
            if not isinstance(
                action_space, Mapping
            ) or "potion" not in action_space.get("excluded_kinds", ()):
                raise ValueError(f"T044 action-space semantics mismatch for {role}")
        if role == "raw_checkpoint_public_policy":
            scorer = settings.get("guidance_scorer")
            if (
                settings.get("information_regime") != "normal_public_policy"
                or not isinstance(scorer, Mapping)
                or checkpoint is None
            ):
                raise ValueError("T044 raw checkpoint policy semantics mismatch")
            raw_checkpoint = scorer.get("checkpoint_provenance")
            if not isinstance(raw_checkpoint, Mapping):
                raise ValueError("T044 raw checkpoint provenance missing")
            expected_artifact = "torch-policy-value-checkpoint-v1-sha256:" + str(
                checkpoint.get("sha256")
            )
            if raw_checkpoint.get(
                "checkpoint_artifact_id"
            ) != expected_artifact or raw_checkpoint.get(
                "checkpoint_path"
            ) != checkpoint.get("path"):
                raise ValueError("T044 raw checkpoint identity mismatch")
        if role == "scripted_public_policy_baseline":
            if (
                entry.get("kind") != "decision_policy"
                or settings.get("information_regime") != "normal_public_policy"
                or settings.get("policy_class") != "ScoredActionPolicy"
            ):
                raise ValueError("T044 scripted public-policy semantics mismatch")
    guided_label = by_role.get("model_guided_search_t043_checkpoint")
    if guided_label is None:
        return
    guided = provenance.get(guided_label) if isinstance(guided_label, str) else None
    guided_config = guided.get("config") if isinstance(guided, Mapping) else None
    scorer = (
        guided_config.get("guidance_scorer")
        if isinstance(guided_config, Mapping)
        else None
    )
    if (
        not isinstance(scorer, Mapping)
        or scorer.get("policy_probability_weight") != T044_GUIDANCE_WEIGHT
    ):
        raise ValueError("T044 model-guided weight/checkpoint semantics mismatch")
    checkpoint_provenance = scorer.get("checkpoint_provenance")
    if checkpoint is None:
        # A retained historical four-arm report is allowed only with the
        # published accepted T043 checkpoint identity, never a caller map.
        expected_artifact = "torch-policy-value-checkpoint-v1-sha256:a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
    else:
        expected_artifact = "torch-policy-value-checkpoint-v1-sha256:" + str(
            checkpoint.get("sha256")
        )
    if (
        not isinstance(checkpoint_provenance, Mapping)
        or checkpoint_provenance.get("checkpoint_artifact_id") != expected_artifact
        or (
            checkpoint is not None
            and checkpoint_provenance.get("checkpoint_path") != checkpoint.get("path")
        )
    ):
        raise ValueError("T044 model-guided checkpoint identity mismatch")


def _validate_teacher_against_selected_manifest(
    dataset: OracleTeacherDataset, manifest: Mapping[str, Any]
) -> None:
    """Reloaded T043 rows must be the 460 selected identities in order."""

    selected = _selected_sources(manifest)
    if len(selected) != 460 or len(dataset.records) != len(selected):
        raise ValueError("T064 teacher does not contain exactly 460 selected rows")
    expected_hashes = [item.get("complete_identity_sha256") for item in selected]
    if len(set(expected_hashes)) != len(expected_hashes) or not all(
        isinstance(value, str) and value for value in expected_hashes
    ):
        raise ValueError("T064 selected manifest identities are invalid")
    expected_action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    if dataset.action_space_config != expected_action_space:
        raise ValueError("T064 teacher dataset action space is not initial_no_potions")
    for index, (row, descriptor) in enumerate(
        zip(dataset.records, selected, strict=True)
    ):
        expected = descriptor.get("complete_identity")
        if not isinstance(expected, Mapping):
            raise ValueError(
                f"T064 selected descriptor lacks complete identity at {index}"
            )
        if (
            row.row_index != index
            or row.source_checkpoint_id != expected.get("source_checkpoint_id")
            or row.source_seed != expected.get("source_seed")
            or row.source_run_id != expected.get("source_run_id")
            or row.source_battle_index != expected.get("source_battle_index")
            or row.source_distribution_kind != expected.get("distribution_kind")
            or row.checkpoint_information_regime
            != expected.get("checkpoint_information_regime")
            or not row.soft_visit_target
        ):
            raise ValueError(f"T064 teacher identity/target mismatch at row {index}")
        row_config = row.controller_provenance.get("config", {})
        row_budget = (
            row_config.get("search_budget", {})
            if isinstance(row_config, Mapping)
            else {}
        )
        if (
            not isinstance(row_config, Mapping)
            or row_config.get("information_regime")
            != "full_simulator_state_oracle_like"
            or not isinstance(row_budget, Mapping)
            or row_budget.get("simulations") != 100
            or row_config.get("root_selection_rule") != "highest_mean"
        ):
            raise ValueError(f"T064 teacher configuration mismatch at row {index}")
        if row_config.get("action_space") != expected_action_space:
            raise ValueError(f"T064 teacher action-space mismatch at row {index}")
    config = dataset.controller_provenance.get("config", {})
    budget = config.get("search_budget", {}) if isinstance(config, Mapping) else {}
    if (
        dataset.information_regime != "full_simulator_state_oracle_like"
        or not isinstance(config, Mapping)
        or config.get("information_regime") != "full_simulator_state_oracle_like"
        or not isinstance(budget, Mapping)
        or budget.get("simulations") != 100
        or config.get("root_selection_rule") != "highest_mean"
        or config.get("action_space") != expected_action_space
        or dataset.problems
    ):
        raise ValueError("T064 teacher configuration is not the frozen T043 contract")


def _validate_trainer_against_selected_manifest(
    dataset: Any, manifest: Mapping[str, Any]
) -> None:
    """Require bridge metadata rather than letting a report repopulate order."""

    expected = [
        item.get("complete_identity_sha256") for item in _selected_sources(manifest)
    ]
    metadata = getattr(dataset, "generation_metadata", {})
    recorded = metadata.get("t064_complete_identity_order")
    if (
        recorded != expected
        or _trainer_identity_hashes(dataset) != expected
        or len(dataset.records) != len(expected)
        or dataset.problems
    ):
        raise ValueError("T064 trainer-input identity linkage/config is invalid")


def _validate_frozen_manifest_plans(manifest: Mapping[str, Any]) -> None:
    """Rebuild all four plans so summary hashes cannot be forged or collapsed."""

    selected = manifest.get("selected_buckets")
    stored = manifest.get("batch_plans")
    if not isinstance(selected, Mapping) or not isinstance(stored, list):
        raise ValueError("T064 manifest batch plans are missing")
    generated = [
        build_ordered_batch_plan(selected, seed=seed, arm=arm)
        for arm, seed in TRAINING_RUN_ORDER
    ]
    summaries = [
        {key: value for key, value in plan.items() if key != "ordered_batches"}
        for plan in generated
    ]
    if stored != summaries:
        raise ValueError("T064 manifest plan/phase/exposure hash mismatch")
    keys = [(plan["arm"], plan["seed"]) for plan in generated]
    if keys != list(TRAINING_RUN_ORDER) or len(set(keys)) != 4:
        raise ValueError("T064 manifest plans have duplicate/collapsed run keys")
    validate_exposure_parity(generated)


def validate_t070_prior_value_report(
    report: Mapping[str, Any],
    *,
    checkpoint: Mapping[str, Any],
    frozen_t070: Mapping[str, Any],
) -> None:
    """Validate every persisted T070 invariant needed by a T064 wrapper.

    ``frozen_t070`` is a separately hashed external input, so none of these
    expected values can be copied out of the report being accepted.
    """

    expected_ranges = list(T070_T052_RANGES)
    required = {
        "schema_id": "t070-single-arm-merged-stage-v1",
        "task_id": "T070",
        "stage_name": "equal-prior-value-0100",
        "arm": "prior_value",
        "family": "equal_nominal",
        "native_budget": 100,
        "cohort_record_count": 93,
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
    }
    for field, value in required.items():
        if report.get(field) != value:
            raise ValueError(f"T070 prior_value {field} mismatch")
    if (
        report.get("shard_ranges") != expected_ranges
        or report.get("problems")
        or frozen_t070.get("tree_geometry_enabled") is not False
        or frozen_t070.get("projection_mode") != "accepted_t069_search_scope_projection"
    ):
        raise ValueError("T070 prior_value ranges/problems mismatch")
    if report.get("command_passed") is not True:
        raise ValueError("T070 prior_value command did not pass")
    for field in (
        "cohort_identity",
        "native_commit",
        "native_runtime_identity",
        "controller_provenance",
    ):
        if report.get(field) != frozen_t070.get(field):
            raise ValueError(f"T070 prior_value frozen {field} mismatch")
    if report.get("code_commit") != frozen_t070.get("current_code_commit"):
        raise ValueError("T070 prior_value current wrapper code mismatch")
    provenance = report.get("controller_provenance")
    if not isinstance(provenance, Mapping) or any(
        key not in provenance for key in ("schema_version", "kind", "name", "config")
    ):
        raise ValueError("T070 prior_value controller semantics are incomplete")
    if frozen_t070.get("checkpoint") != checkpoint:
        raise ValueError("T070 prior_value wrapper checkpoint mismatch")


def _validate_t070_rows(rows: Any, *, cohort: Any) -> list[Mapping[str, Any]]:
    """Fail closed on every T052 primary row and its frozen structural split."""

    if (
        not isinstance(rows, list)
        or len(rows) != 93
        or not all(isinstance(row, Mapping) for row in rows)
    ):
        raise ValueError("T070 rows must be 93 mapping records")
    typed = [row for row in rows if isinstance(row, Mapping)]
    if [row.get("cohort_index") for row in typed] != list(range(93)):
        raise ValueError("T070 rows do not preserve cohort order 0..92")
    if any(row.get("problems") not in ([], None) for row in typed):
        raise ValueError("T070 rows contain evaluation problems")
    if any(not isinstance(row.get("structural_metadata"), Mapping) for row in typed):
        raise ValueError("T070 rows lack structural metadata")
    boss_count = sum(
        row["structural_metadata"].get("room_type") == "BOSS" for row in typed
    )
    act2_plus_count = sum(
        row["structural_metadata"].get("act", 0) >= 2 for row in typed
    )
    if boss_count != 88 or act2_plus_count != 5:
        raise ValueError("T070 rows do not match the frozen 88-boss/5-act2+ split")
    if not getattr(cohort, "identity", "") or len(getattr(cohort, "records", ())) != 93:
        raise ValueError("T070 frozen cohort identity is missing")
    for row, expected in zip(typed, cohort.records, strict=True):
        if (
            row.get("source_checkpoint_id") != expected.source_checkpoint_id
            or row.get("structural_metadata") != expected.structural_metadata
        ):
            raise ValueError("T070 rows do not match the frozen cohort identity/order")
    return typed


def _validate_stage_summary_evidence(
    summary: Mapping[str, Any], *, manifest: Mapping[str, Any], code_commit: str
) -> None:
    """Make completion depend on Stage 0--7 evidence, not just merged outputs."""

    stages = summary.get("stages")
    if not isinstance(stages, list) or summary.get("problems") != []:
        raise ValueError("T064 stage summary is missing clean stage evidence")
    expected_counts = {
        "stage0": 1,
        "stage1": 1,
        "stage2": 1,
        "stage3": 1,
        "stage4": 1,
        "stage5": 8,
        "stage6": 4,
        "stage7": 1,
    }
    actual_counts = {prefix: 0 for prefix in expected_counts}
    independent_stage_count = 0
    dispositions = {
        item.get("cohort"): item.get("disposition")
        for item in summary.get("reuse_inventory", [])
        if isinstance(item, Mapping)
        and item.get("cohort") in {"assist_0", "assist_hp50"}
    }
    if set(dispositions) != {"assist_0", "assist_hp50"} or not all(
        value in {"reuse_historical_four_arm", "rerun_once_two_independent_arms"}
        for value in dispositions.values()
    ):
        raise ValueError("T064 stage summary T044 reuse dispositions are incomplete")
    expected_independent = sum(
        value == "rerun_once_two_independent_arms" for value in dispositions.values()
    )
    adequate = bool(manifest.get("source_adequacy"))
    for stage in stages:
        if not isinstance(stage, Mapping):
            raise ValueError("T064 stage summary has a non-mapping stage")
        name = stage.get("name")
        prefix = name.split("_", 1)[0] if isinstance(name, str) else ""
        if prefix not in expected_counts:
            raise ValueError("T064 stage summary has an unknown stage inventory item")
        actual_counts[prefix] += 1
        if prefix == "stage5" and "independent" in name:
            independent_stage_count += 1
        current_head_required = prefix in {"stage4", "stage5", "stage6", "stage7"}
        if (
            (current_head_required and stage.get("code_commit") != code_commit)
            or stage.get("native_commit") != manifest.get("native_commit")
            or stage.get("failure_count") != 0
            or any(code != 0 for code in stage.get("return_codes", ()))
        ):
            raise ValueError(f"T064 stage summary failure/stale identity: {name}")
        downstream = prefix in {"stage2", "stage3", "stage4", "stage5", "stage6"}
        required_status = (
            "complete" if adequate or not downstream else "skipped_source_inadequate"
        )
        if stage.get("status") != required_status:
            raise ValueError(f"T064 stage summary status mismatch: {name}")
        if prefix == "stage4" and (
            stage.get("workers") != T064_STAGE4_MAX_WORKERS
            or stage.get("shards") != len(TRAINING_RUN_ORDER)
        ):
            raise ValueError("T064 stage summary Stage4 worker inventory mismatch")
        if prefix in {"stage2", "stage5", "stage6"}:
            ranges = stage.get("ranges")
            if stage.get("workers") != 16 or stage.get("shards") != 16:
                raise ValueError(
                    f"T064 stage summary worker inventory mismatch: {name}"
                )
            if prefix == "stage2" and ranges != manifest.get("teacher_shard_ranges"):
                raise ValueError("T064 Stage2 ranges differ from the manifest")
            if prefix == "stage5" and ranges not in (
                list(T044_ASSIST_0_RANGES),
                list(T044_ASSIST_HP50_RANGES),
            ):
                raise ValueError("T064 Stage5 ranges are not frozen")
            if prefix == "stage6" and ranges != list(T070_T052_RANGES):
                raise ValueError("T064 Stage6 ranges are not frozen")
        for identity in (
            *stage.get("outputs", {}).values(),
            *stage.get("referenced_artifacts", []),
        ):
            if not isinstance(identity, Mapping):
                raise ValueError("T064 stage summary artifact identity is invalid")
            validate_external_frozen_identity(
                Path(str(identity.get("path", ""))), identity, label=f"{name} output"
            )
    if actual_counts != expected_counts:
        if actual_counts["stage5"] != 8 + expected_independent:
            raise ValueError("T064 stage summary Stage0--7 inventory is incomplete")
        actual_counts["stage5"] = 8
        if actual_counts != expected_counts:
            raise ValueError("T064 stage summary Stage0--7 inventory is incomplete")
    if independent_stage_count != expected_independent:
        raise ValueError("T064 Stage5 independent fallback disposition mismatch")


def _validate_stage_summary_crosslinks(
    summary: Mapping[str, Any], references: Sequence[Path]
) -> None:
    """Require summary output identities to name the artifacts accepted by Stage 7."""

    summarized: dict[str, Mapping[str, Any]] = {}
    for stage in summary.get("stages", []):
        if not isinstance(stage, Mapping):
            continue
        for identity in (
            *stage.get("outputs", {}).values(),
            *stage.get("referenced_artifacts", []),
        ):
            if isinstance(identity, Mapping) and isinstance(identity.get("path"), str):
                summarized[identity["path"]] = identity
    for path in references:
        if not path.is_file():
            continue
        identity = summarized.get(str(path))
        if identity is None:
            raise ValueError(f"stage summary omits accepted artifact {path}")
        validate_external_frozen_identity(
            path, identity, label="Stage7 accepted artifact"
        )


def aggregate_t064_stage7_from_artifacts(
    *,
    root: Path,
    code_commit: str,
    teacher_path: Path,
    trainer_input_path: Path,
    t044_paths: Mapping[tuple[str, int], Mapping[str, Path]],
    t070_paths: Mapping[tuple[str, int], Path],
    stage_summary: Mapping[str, Any],
    frozen_inputs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Independently load, validate, hash, and aggregate the real stage outputs.

    There is intentionally no ``experiment_complete`` or metrics argument: both
    are derived here, after every referenced artifact has been opened again.
    """

    manifest_path = root / "t064-curriculum-manifest.json"
    training_path = root / TRAINING_RUN_REPORT_FILENAME
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = load_compact_json(stream)
    validate_resume_manifest(manifest, code_commit=code_commit)
    with training_path.open(encoding="utf-8") as stream:
        training = load_compact_json(stream)
    stage_summary_problem: str | None = None
    try:
        _validate_stage_summary_evidence(
            stage_summary, manifest=manifest, code_commit=code_commit
        )
    except ValueError as exc:
        stage_summary_problem = str(exc)
    if not manifest["source_adequacy"]:
        if (
            training.get("runs") != []
            or training.get("not_run_reason") != "source_inadequate"
            or stage_summary_problem is not None
        ):
            raise ValueError(
                "source-inadequate Case B requires the explicit skipped training report"
            )
        decision = build_transfer_decision(
            source_adequate=False,
            source_integrity_valid=True,
            experiment_complete=False,
            complete_source_audit_status=manifest["complete_source_audit"]["status"],
            transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
            diagnostics={
                "derived_from_artifacts": True,
                "downstream_stages": "skipped_source_inadequate",
            },
        )
        refuse_overwrite(root / "t064-stage-summary.json")
        refuse_overwrite(root / "t064-transfer-decision.json")
        write_compact_json(root / "t064-stage-summary.json", stage_summary)
        write_compact_json(root / "t064-transfer-decision.json", decision)
        return {
            "decision": decision,
            "metrics": {},
            "rehash": independent_rehash(root, [manifest_path, training_path]),
        }
    problems: list[str] = []
    unmet: list[str] = []
    if stage_summary_problem is not None:
        problems.append(f"stage summary evidence invalid: {stage_summary_problem}")
    references = [manifest_path, training_path, teacher_path, trainer_input_path]
    for label, path in (
        ("teacher", teacher_path),
        ("trainer_input", trainer_input_path),
    ):
        expected = frozen_inputs.get(label)
        if not isinstance(expected, Mapping):
            problems.append(f"external frozen identity missing for {label}")
        else:
            try:
                validate_external_frozen_identity(path, expected, label=label)
            except ValueError as exc:
                problems.append(str(exc))
    if not teacher_path.is_file() or not trainer_input_path.is_file():
        problems.append("teacher or trainer-input artifact missing")
    else:
        try:
            with teacher_path.open(encoding="utf-8") as stream:
                _validate_teacher_against_selected_manifest(
                    load_oracle_teacher_dataset_jsonl(stream), manifest
                )
            with trainer_input_path.open(encoding="utf-8") as stream:
                _validate_trainer_against_selected_manifest(
                    load_trainer_input_dataset_jsonl(stream), manifest
                )
        except (OSError, ValueError) as exc:
            problems.append(f"teacher/trainer schema/linkage mismatch: {exc}")
    runs = training.get("runs", [])
    if [(row.get("arm"), row.get("seed")) for row in runs] != list(TRAINING_RUN_ORDER):
        problems.append("aggregate training report lacks four frozen runs")
    else:
        try:
            _validate_frozen_manifest_plans(manifest)
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"manifest frozen plan validation failed: {exc}")
        for run in runs:
            checkpoint = run.get("checkpoint", {})
            path = Path(str(checkpoint.get("path", "")))
            if (
                run.get("completion_status") != "complete"
                or not path.is_file()
                or _sha256(path) != checkpoint.get("sha256")
                or path.stat().st_size != checkpoint.get("bytes")
            ):
                problems.append(
                    f"checkpoint identity/completion failed for {run.get('arm')}/{run.get('seed')}"
                )
            else:
                references.append(path)
    metrics: dict[str, Any] = {
        "curriculum_t052_prior_value_wins": {},
        "static_t052_prior_value_wins": {},
        "paired_t052_win_deltas": {},
        "t052_subset_deltas": {"boss": 0, "act2_plus": 0},
        "curriculum_t044_assist_hp50_model_guided_wins": 0,
        "static_t044_assist_hp50_model_guided_wins": 0,
        "curriculum_t044_assist_hp50_raw_policy_wins": 0,
        "static_t044_assist_hp50_raw_policy_wins": 0,
        "curriculum_t044_assist_0_model_guided_wins": 0,
        "static_t044_assist_0_model_guided_wins": 0,
    }
    t052_rows: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    t044_cohorts = frozen_inputs.get("t044_cohorts")
    frozen_t070 = frozen_inputs.get("t070")
    t052_cohort: Any | None = None
    if not isinstance(t044_cohorts, Mapping):
        problems.append("external frozen T044 cohort contracts missing")
    independent_reports = frozen_inputs.get("t044_independent_reports")
    if not isinstance(independent_reports, Mapping):
        problems.append("external T044 independent baseline/scripted evidence missing")
    elif isinstance(t044_cohorts, Mapping):
        for cohort_name in ("assist_0", "assist_hp50"):
            cohort_contract = t044_cohorts.get(cohort_name)
            evidence = independent_reports.get(cohort_name)
            if not isinstance(cohort_contract, Mapping) or not isinstance(
                evidence, Mapping
            ):
                problems.append(
                    f"external T044 independent evidence missing: {cohort_name}"
                )
                continue
            try:
                cohort = _validate_t044_frozen_cohort(
                    cohort_contract, cohort_kind=cohort_name
                )
                path = Path(str(evidence.get("path", "")))
                validate_external_frozen_identity(
                    path, evidence, label=f"T044 {cohort_name} independent report"
                )
                with path.open(encoding="utf-8") as stream:
                    independent = load_de_assisted_fixed_cohort_comparison_jsonl(stream)
                if not validate_t044_independent_report(
                    independent,
                    cohort_identity=str(cohort_contract.get("identity", "")),
                    cohort_count=int(cohort_contract.get("record_count", -1)),
                    cohort=cohort,
                ):
                    raise ValueError("T044 independent roles/config/order mismatch")
                _validate_t044_controller_semantics(independent, checkpoint=None)
                references.append(path)
            except (OSError, ValueError) as exc:
                problems.append(f"external T044 independent evidence invalid: {exc}")
    if not isinstance(frozen_t070, Mapping):
        problems.append("external frozen T070 contract missing")
    else:
        historical_frozen: Mapping[str, Any] | None = None
        manifest_identity = frozen_t070.get("manifest")
        if isinstance(manifest_identity, Mapping):
            try:
                historical_frozen = load_t070_frozen_contract(
                    Path(str(manifest_identity.get("path", "")))
                )
                inputs = historical_frozen.get("input_identities")
                if not isinstance(inputs, Mapping) or inputs.get(
                    "t052_fixed_cohort"
                ) != frozen_t070.get("cohort"):
                    raise ValueError("T070 frozen cohort identity is not bound")
            except (OSError, ValueError) as exc:
                problems.append(f"external frozen T070 manifest unreadable: {exc}")
                historical_frozen = None
        for label in ("manifest", "baseline", "cohort"):
            expected = frozen_t070.get(label)
            if not isinstance(expected, Mapping):
                problems.append(f"external frozen T070 {label} identity missing")
                continue
            candidate = Path(str(expected.get("path", "")))
            try:
                validate_external_frozen_identity(
                    candidate, expected, label=f"t070_{label}"
                )
                references.append(candidate)
            except ValueError as exc:
                problems.append(str(exc))
        baseline_identity = frozen_t070.get("baseline")
        baseline_contract = frozen_t070.get("baseline_contract")
        cohort_identity = frozen_t070.get("cohort")
        if isinstance(cohort_identity, Mapping):
            t052_path = Path(str(cohort_identity.get("path", "")))
            try:
                with t052_path.open(encoding="utf-8") as stream:
                    t052_cohort = load_fixed_cohort_jsonl(stream)
                if (
                    t052_cohort.identity != frozen_t070.get("cohort_identity")
                    or len(t052_cohort.records) != 93
                    or [record.cohort_index for record in t052_cohort.records]
                    != list(range(93))
                    or t052_cohort.problems
                ):
                    problems.append(
                        "external frozen T070 cohort order/identity mismatch"
                    )
                    t052_cohort = None
            except (OSError, ValueError) as exc:
                problems.append(f"external frozen T070 cohort unreadable: {exc}")
        if (
            isinstance(baseline_identity, Mapping)
            and isinstance(baseline_contract, Mapping)
            and t052_cohort is not None
            and historical_frozen is not None
        ):
            baseline_path = Path(str(baseline_identity.get("path", "")))
            try:
                baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
                if not validate_t070_baseline_reuse(
                    baseline_report,
                    cohort_identity=str(frozen_t070.get("cohort_identity", "")),
                    frozen_contract=historical_frozen,
                    cohort=t052_cohort,
                ):
                    problems.append("external frozen T070 baseline contract mismatch")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                problems.append(f"external frozen T070 baseline unreadable: {exc}")
        else:
            problems.append("external frozen T070 baseline contract missing")
    for key in TRAINING_RUN_ORDER:
        cohort_paths = t044_paths.get(key)
        t070_path = t070_paths.get(key)
        checkpoint = next(
            (
                row.get("checkpoint", {})
                for row in runs
                if (row.get("arm"), row.get("seed")) == key
            ),
            {},
        )
        if not isinstance(cohort_paths, Mapping) or set(cohort_paths) != {
            "assist_0",
            "assist_hp50",
        }:
            problems.append(f"T044 stage inventory missing for {key[0]}/{key[1]}")
            continue
        for cohort_name, path in cohort_paths.items():
            if not path.is_file():
                problems.append(f"T044 artifact missing: {path}")
                continue
            references.append(path)
            with path.open(encoding="utf-8") as stream:
                report = load_de_assisted_fixed_cohort_comparison_jsonl(stream)
            frozen_cohort = (
                t044_cohorts.get(cohort_name)
                if isinstance(t044_cohorts, Mapping)
                else None
            )
            if not isinstance(frozen_cohort, Mapping):
                problems.append(f"T044 frozen contract mismatch: {path}")
                continue
            try:
                cohort = _validate_t044_frozen_cohort(
                    frozen_cohort, cohort_kind=cohort_name
                )
            except (OSError, ValueError) as exc:
                problems.append(f"T044 frozen cohort mismatch: {exc}")
                continue
            if not validate_t044_dependent_report(
                report,
                cohort_identity=str(frozen_cohort.get("identity", "")),
                cohort_count=int(frozen_cohort.get("record_count", -1)),
                cohort=cohort,
            ):
                problems.append(f"T044 frozen contract mismatch: {path}")
                continue
            try:
                _validate_t044_controller_semantics(report, checkpoint=checkpoint)
            except ValueError as exc:
                problems.append(f"T044 controller semantics mismatch: {exc}")
                continue
            wins = {arm.role: arm.report.authoritative_wins for arm in report.arms}
            prefix = (
                "curriculum"
                if key[0] == "assistance_annealed_curriculum_v1"
                else "static"
            )
            if cohort_name == "assist_hp50":
                metrics[f"{prefix}_t044_assist_hp50_model_guided_wins"] += wins[
                    T044_DEPENDENT_ROLES[0]
                ]
                metrics[f"{prefix}_t044_assist_hp50_raw_policy_wins"] += wins[
                    T044_DEPENDENT_ROLES[1]
                ]
            else:
                metrics[f"{prefix}_t044_assist_0_model_guided_wins"] += wins[
                    T044_DEPENDENT_ROLES[0]
                ]
        if t070_path is None or not t070_path.is_file():
            problems.append(f"T070 artifact missing for {key[0]}/{key[1]}")
            continue
        references.append(t070_path)
        report = json.loads(t070_path.read_text(encoding="utf-8"))
        try:
            if not isinstance(frozen_t070, Mapping):
                raise ValueError("external T070 contract missing")
            wrappers = frozen_t070.get("wrappers")
            wrapper_key = f"{key[0]}:{key[1]}"
            wrapper = (
                wrappers.get(wrapper_key) if isinstance(wrappers, Mapping) else None
            )
            if not isinstance(wrapper, Mapping):
                raise ValueError("external T070 checkpoint wrapper missing")
            persisted_stage = manifest.get("t070_stage_manifest")
            selections = (
                persisted_stage.get("checkpoint_selections")
                if isinstance(persisted_stage, Mapping)
                else None
            )
            selected = (
                selections.get(wrapper_key) if isinstance(selections, Mapping) else None
            )
            if (
                not isinstance(persisted_stage, Mapping)
                or not isinstance(selected, Mapping)
                or selected.get("checkpoint") != checkpoint
                or persisted_stage.get("frozen_t070_manifest")
                != frozen_t070.get("manifest")
            ):
                raise ValueError("persisted T070 wrapper selection mismatch")
            contract = {
                **dict(frozen_t070),
                **dict(persisted_stage),
                **dict(wrapper),
                "checkpoint": checkpoint,
            }
            validate_t070_prior_value_report(
                report,
                checkpoint=checkpoint,
                frozen_t070=contract,
            )
        except ValueError as exc:
            problems.append(f"T070 frozen contract mismatch: {t070_path}: {exc}")
            continue
        rows = report.get("arm_report", {}).get("records", [])
        try:
            if t052_cohort is None:
                raise ValueError("frozen T052 cohort was not loaded")
            t052_rows[key] = _validate_t070_rows(rows, cohort=t052_cohort)
        except ValueError as exc:
            problems.append(f"T070 rows incomplete: {t070_path}: {exc}")
            continue
        wins = sum(row.get("termination_status") == "win" for row in t052_rows[key])
        metrics[
            (
                "curriculum"
                if key[0] == "assistance_annealed_curriculum_v1"
                else "static"
            )
            + "_t052_prior_value_wins"
        ][key[1]] = wins
    if len(t052_rows) == 4:
        for seed in (64001, 64002):
            static_rows = t052_rows[("static_mixture_v1", seed)]
            curriculum_rows = t052_rows[("assistance_annealed_curriculum_v1", seed)]
            metrics["paired_t052_win_deltas"][seed] = sum(
                a.get("termination_status") == "win" for a in curriculum_rows
            ) - sum(a.get("termination_status") == "win" for a in static_rows)
            for subset, predicate in (
                (
                    "boss",
                    lambda row: (
                        row.get("structural_metadata", {}).get("room_type") == "BOSS"
                    ),
                ),
                (
                    "act2_plus",
                    lambda row: row.get("structural_metadata", {}).get("act") >= 2,
                ),
            ):
                metrics["t052_subset_deltas"][subset] += sum(
                    row.get("termination_status") == "win"
                    for row in curriculum_rows
                    if predicate(row)
                ) - sum(
                    row.get("termination_status") == "win"
                    for row in static_rows
                    if predicate(row)
                )
    try:
        _validate_stage_summary_crosslinks(stage_summary, references)
    except ValueError as exc:
        problems.append(f"stage summary accepted-artifact crosslink failed: {exc}")
    complete = not problems and len(t052_rows) == 4
    if not complete:
        unmet.append(
            "complete validated teacher, trainer, checkpoint, T044, and T070 artifact set"
        )
    gates = (
        compute_transfer_gates(metrics)
        if complete
        else {name: None for name in TRANSFER_GATE_NAMES}
    )
    source_audit = manifest["complete_source_audit"]
    decision = build_transfer_decision(
        source_adequate=bool(manifest["source_adequacy"]),
        source_integrity_valid=True,
        experiment_complete=complete,
        complete_source_audit_status=source_audit["status"],
        transfer_gates=gates,
        diagnostics={
            "derived_from_artifacts": True,
            "metrics": metrics,
            "referenced_artifacts": [
                _file_identity(path) for path in references if path.is_file()
            ],
        },
        problems=problems,
        unmet_acceptance_criteria=unmet,
    )
    refuse_overwrite(root / "t064-stage-summary.json")
    refuse_overwrite(root / "t064-transfer-decision.json")
    write_compact_json(root / "t064-stage-summary.json", stage_summary)
    write_compact_json(root / "t064-transfer-decision.json", decision)
    return {
        "decision": decision,
        "metrics": metrics,
        "rehash": independent_rehash(root, references),
    }


def training_report_for_source_inadequacy(root: Path) -> dict[str, Any]:
    """Write the sole aggregate training report when Case B correctly skips training."""

    payload = {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": [],
        "not_run_reason": "source_inadequate",
    }
    refuse_overwrite(root / TRAINING_RUN_REPORT_FILENAME)
    write_compact_json(root / TRAINING_RUN_REPORT_FILENAME, payload)
    return payload


def _assert_existing_or_new(root: Path, names: Sequence[str]) -> None:
    illegal = [path.name for path in root.glob("t064-*.json") if path.name not in names]
    if illegal:
        raise ValueError(f"T064 compact artifact inventory is not exact: {illegal}")


def _selected_sources(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = manifest.get("selected_sources")
    if not isinstance(values, list) or any(
        not isinstance(value, Mapping) for value in values
    ):
        raise ValueError("T064 selected source manifest is invalid")
    return list(values)


def _range(value: str, count: int) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("T064 frozen range must use start:end")
    start, end = (int(part) for part in parts)
    if start < 0 or end < start or end > count:
        raise ValueError("T064 frozen range is outside its cohort")
    return start, end


def _source_key(source: Mapping[str, Any]) -> tuple[Any, ...]:
    identity = source.get("complete_identity", source)
    if not isinstance(identity, Mapping):
        raise ValueError("T064 selected complete identity is invalid")
    return tuple(
        identity.get(field)
        for field in (
            "source_checkpoint_id",
            "source_seed",
            "source_run_id",
            "source_battle_index",
            "distribution_kind",
            "checkpoint_information_regime",
        )
    )


def _teacher_source_key(row: Any) -> tuple[Any, ...]:
    return (
        row.source_checkpoint_id,
        row.source_seed,
        row.source_run_id,
        row.source_battle_index,
        row.source_distribution_kind,
        row.checkpoint_information_regime,
    )


def _bucket_exposure_counts(plan: Mapping[str, Any]) -> dict[str, int]:
    values = plan.get("per_source_exposure_counts")
    if not isinstance(values, Mapping):
        raise ValueError("T064 batch plan lacks per-source exposure counts")
    # Each bucket exposure sequence has exactly 9,600 draws.  Keeping this
    # explicit avoids deriving a bucket label from a public trainer feature.
    return {bucket: 9600 for bucket in BUCKETS}


def _sha256(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI shell.
    raise SystemExit(main())
