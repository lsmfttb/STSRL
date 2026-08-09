"""Executable, restart-safe orchestration for the T064 reuse-first transfer.

The module intentionally owns only the small amount of glue T064 needs.  It
does not implement a simulator, a teacher format, a trainer format, or an
evaluation format: callers provide the existing T043/T044/T070 runners.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import argparse
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import subprocess
from pathlib import Path
import time
from typing import Any

from sts_combat_rl.commands.oracle_teacher_scaleup import (
    collect_oracle_teacher_range_from_selected_manifest,
)
from sts_combat_rl.commands.de_assisted_fixed_cohort_comparison import (
    merge_de_assisted_fixed_cohort_comparison_shards,
    run_de_assisted_fixed_cohort_comparison_from_cohort_path,
    write_de_assisted_fixed_cohort_comparison_report,
)
from sts_combat_rl.commands.t070_search_v2_audit import FROZEN_MANIFEST_SCHEMA_ID
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
    contiguous_ranges,
    independent_rehash,
    load_compact_json,
    validate_exposure_parity,
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
T044_ASSIST_0_RANGES = contiguous_ranges(21)
T044_ASSIST_HP50_RANGES = contiguous_ranges(38)
T070_T052_RANGES = contiguous_ranges(93)
T064_ARTIFACT_ROOT_NAME = "t064-later-act-curriculum-transfer"

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
    {"kind": "other_terminated_attempts", "status": "retained_non_evidence"},
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
    stage6_values = (
        args.stage6_shard_script,
        args.stage6_cohort,
        args.stage6_checkpoint,
        args.stage6_wrapper_manifest,
        args.stage6_native_preflight,
        args.stage6_native_checkout,
        args.stage6_native_build_root,
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
        print(json.dumps({"stage": "stage6_t070", "shards": records}, sort_keys=True))
        return 0
    for stage in stages:
        print(json.dumps(stage, sort_keys=True, separators=(",", ":")))
    return 0


def validate_resume_manifest(manifest: Mapping[str, Any], *, code_commit: str) -> None:
    """Refuse resumes after a code change or before a completed restore audit."""

    if manifest.get("code_commit") != code_commit:
        raise ValueError("T064 resume refuses stale code head")
    audit = manifest.get("complete_source_audit")
    if not isinstance(audit, Mapping) or audit.get("status") != "complete":
        raise ValueError("T064 resume requires a completed selected-source audit")
    if audit.get("selected_restore_failure_count") != 0:
        raise ValueError("T064 resume refuses failed selected-source audit")


def refuse_overwrite(path: Path) -> None:
    """Make stage outputs append-free: an old output must be explicitly audited."""

    if path.exists():
        raise ValueError(f"T064 stage refuses to overwrite existing output: {path}")


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
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Execute exactly sixteen shard jobs concurrently and retain every result log.

    Output serialization remains in the existing T043/T044/T070 writers used by
    each worker.  This function records only ordinary text logs and return
    codes; it deliberately creates no alternate artifact schema.
    """

    if len(ranges) != 16:
        raise ValueError("T064 substantial stages require exactly 16 shards")
    log_dir.mkdir(parents=True, exist_ok=True)
    results: list[Any] = [None] * 16
    records: list[dict[str, Any]] = [{} for _ in ranges]

    def invoke(index: int, record_range: str) -> tuple[int, Any, dict[str, Any]]:
        log_path = log_dir / f"shard-{index:02d}.log"
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
            },
        )

    with ThreadPoolExecutor(max_workers=16, thread_name_prefix="t064-shard") as pool:
        futures = [
            pool.submit(invoke, index, record_range)
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
            "workers": 1,
            "shards": 1,
            "ranges": [f"0:{source_count}"],
        },
        {
            "stage": "stage4_training",
            "workers": 1,
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
) -> tuple[OracleTeacherDataset, list[dict[str, Any]]]:
    """Merge the existing teacher rows in frozen complete-source order."""

    sources = _selected_sources(selected_manifest)
    ranges = tuple(expected_ranges or contiguous_ranges(len(sources)))
    if len(shards) != 16 or len(ranges) != 16:
        raise ValueError("T064 teacher merge requires exactly 16 shards")
    if not shards:
        raise ValueError("T064 teacher merge requires shards")
    first = shards[0]
    rows = []
    for index, (shard, record_range) in enumerate(zip(shards, ranges, strict=True)):
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
    shard_runner: Callable[
        ..., OracleTeacherDataset
    ] = collect_oracle_teacher_range_from_selected_manifest,
) -> OracleTeacherDataset:
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

    def one(index: int, record_range: str) -> OracleTeacherDataset:
        output = shard_output_dir / f"shard-{index:02d}.jsonl"
        refuse_overwrite(output)
        shard = shard_runner(
            adapter_factory=adapter_factory,
            pool=pool,
            controller=controller,
            selected_source_manifest=selected_manifest,
            record_range=record_range,
            action_space=action_space,
        )
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            dump_oracle_teacher_dataset_jsonl(shard, stream)
        return shard

    shards, shard_records = dispatch_t064_shards(
        ranges=ranges,
        log_dir=log_dir,
        worker=one,
    )
    merged = merge_t064_teacher_shards(
        shards=shards, selected_manifest=selected_manifest, expected_ranges=ranges
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
        "hidden_size": 128,
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


def run_t064_paired_training(
    *,
    selected_manifest: Mapping[str, Any],
    dataset: Any,
    initialization_checkpoint_path: Path,
    initialization_sha256: str,
    trainer_input_path: Path,
    identity_to_trainer_index: Mapping[str, int],
    checkpoint_paths: Mapping[tuple[str, int], Path],
) -> dict[str, Any]:
    """Run the four fixed CPU jobs using the existing trainer/checkpoint writer.

    The T009 broad gate stays closed; this passes only the named narrow
    curriculum override.  Every call reloads the same checkpoint then lets the
    existing trainer deep-copy it and allocate a new Adam optimizer.
    """

    from sts_combat_rl.commands.pytorch_search_guidance import (
        build_pytorch_search_guidance_training_data_provenance,
    )
    from sts_combat_rl.sim.torch_policy_value import (
        TorchPolicyValueTrainingConfig,
        load_torch_policy_value_checkpoint,
        save_torch_policy_value_checkpoint,
        train_torch_policy_value,
    )
    from sts_combat_rl.sim.training_gate import build_training_gate_report
    import torch

    if _sha256(initialization_checkpoint_path) != initialization_sha256:
        raise ValueError("T064 initialization checkpoint identity mismatch")
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
    plans_by_run = {(plan["arm"], plan["seed"]): plan for plan in regenerated}
    trainer_sha256 = _sha256(trainer_input_path)
    trainer_bytes = trainer_input_path.read_bytes()
    runs: list[dict[str, Any]] = []
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    for arm, seed in TRAINING_RUN_ORDER:
        plan = plans_by_run[(arm, seed)]
        output = checkpoint_paths.get((arm, seed))
        if output is None:
            raise ValueError("T064 training checkpoint path is missing")
        refuse_overwrite(output)
        config = TorchPolicyValueTrainingConfig(
            epochs=900,
            learning_rate=0.001,
            hidden_size=128,
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
        linkage: dict[str, Any] = {}
        if result.report.training_ok:
            save_torch_policy_value_checkpoint(
                result,
                str(output),
                training_data_provenance=build_pytorch_search_guidance_training_data_provenance(
                    dataset,
                    trainer_input_path,
                    trainer_input_bytes=trainer_bytes,
                    gate_report=gate,
                ),
                metadata={
                    "task_id": "T064",
                    "arm": arm,
                    "seed": seed,
                    "initialization_sha256": initialization_sha256,
                    "batch_plan_sha256": plan["batch_plan_sha256"],
                },
            )
            written = load_torch_policy_value_checkpoint(str(output))
            if (
                written.config != config
                or written.metadata.get("batch_plan_sha256")
                != plan["batch_plan_sha256"]
            ):
                raise ValueError(
                    "T064 written checkpoint metadata/config verification failed"
                )
            checkpoint = _file_identity(output)
            linkage = {
                "schema_id": "torch-policy-value-checkpoint-v1",
                "training_ok": True,
            }
        else:
            problems.append("T064 checkpoint was not written")
        runs.append(
            {
                "arm": arm,
                "seed": seed,
                "initialization_sha256": initialization_sha256,
                "configuration": frozen_training_configuration(seed=seed),
                "trainer_input_sha256": trainer_sha256,
                "batch_plan_sha256": plan["batch_plan_sha256"],
                "per_bucket_exposure_counts": _bucket_exposure_counts(plan),
                "per_source_exposure_counts": plan["per_source_exposure_counts"],
                "checkpoint": checkpoint,
                "checkpoint_metadata_linkage": linkage,
                "completion_status": "complete"
                if result.report.training_ok
                else "failed",
                "problems": problems,
            }
        )
    return {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": runs,
    }


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
    action_space = config.get("action_space")
    if (
        not isinstance(action_space, Mapping)
        or action_space.get("include_potions") is not False
    ):
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
    """Choose a historical four-arm reuse or one clean cohort rerun.

    The dependent two-arm output is never a substitute for the independent
    baseline/scripted evidence.  A failed historical validation therefore
    schedules precisely one all-four-arm fixed-cohort rerun for that cohort.
    """

    if historical_report is not None and validate_t044_historical_reuse(
        historical_report, frozen_cohort=frozen_cohort
    ):
        return "reuse_historical_four_arm"
    return "rerun_once_four_arm"


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
    )
    merged = merger(cohort_path=cohort_path, shards=shards, expected_ranges=ranges)
    report_writer(merged_output_path, merged)
    return merged, shard_records


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

    shards, records = dispatch_t064_shards(ranges=ranges, log_dir=log_dir, worker=one)
    merged = merger(cohort_path=cohort_path, shards=shards, expected_ranges=ranges)
    report_writer(merged_output_path, merged)
    return merged, records


def validate_t070_baseline_reuse(
    report: Mapping[str, Any],
    *,
    cohort_identity: str,
    frozen_contract: Mapping[str, Any] | None = None,
) -> bool:
    """Validate the T070 baseline without treating a display label as an arm role."""

    valid = (
        report.get("schema_id") == "t070-single-arm-merged-stage-v1"
        and report.get("cohort_identity") == cohort_identity
        and report.get("cohort_record_count") == 93
        and report.get("arm") == "baseline"
        and report.get("native_budget") == 100
        and report.get("tree_geometry_enabled") is False
        and tuple(report.get("shard_ranges", ())) == T070_T052_RANGES
        and report.get("command_passed") is True
        and not report.get("problems")
    )
    if not valid or frozen_contract is None:
        return valid
    return all(
        report.get(field) == frozen_contract.get(field)
        for field in (
            "code_commit",
            "native_commit",
            "native_runtime_identity",
            "controller_provenance",
            "family",
            "stage_name",
            "worker_count",
            "shard_count",
            "effective_parallel_workers",
        )
    )


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


def write_t064_t070_stage_manifest(
    *,
    base_manifest_path: Path,
    output_path: Path,
    code_commit: str,
    frozen_t070_manifest: Mapping[str, Any],
    frozen_identity: Mapping[str, Any],
    checkpoint_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one checkpoint's existing-schema T070 wrapper for its shard script.

    Each of the four checkpoint stages receives an attempt-scoped
    ``t064-curriculum-manifest-v1``.  The existing T070 reader already knows
    that schema and resolves ``t070_stage_manifest`` without any T064-only
    reader or invented wrapper file format.
    """

    refuse_overwrite(output_path)
    with base_manifest_path.open(encoding="utf-8") as stream:
        base = load_compact_json(stream)
    validate_resume_manifest(base, code_commit=code_commit)
    validate_external_frozen_identity(
        Path(str(frozen_identity.get("path", ""))),
        frozen_identity,
        label="T070 historical manifest",
    )
    wrapper = t064_t070_wrapper(
        current_code_commit=code_commit,
        frozen_t070_manifest=frozen_t070_manifest,
        frozen_identity=frozen_identity,
        checkpoint_identity=checkpoint_identity,
    )
    payload = dict(base)
    payload["t070_stage_manifest"] = wrapper
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_compact_json(output_path, payload)
    return payload


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
    return (
        getattr(report, "evaluation_successful", False)
        and tuple(arm.role for arm in arms) == T044_DEPENDENT_ROLES
        and config.get("cohort_identity") == cohort_identity
        and config.get("cohort_record_count") == cohort_count
        and config.get("max_battle_steps") == 200
        and config.get("run_scale") == "fixed"
        and config.get("shard_count") == 16
        and tuple(config.get("shard_ranges", ())) == expected_ranges
        and isinstance(config.get("action_space"), Mapping)
        and config["action_space"].get("include_potions") is False
        and exact_order
        and provenance_ok
        and all(
            len(arm.report.battle_results) == cohort_count and not arm.report.problems
            for arm in arms
        )
    )


def validate_t044_independent_report(
    report: Any,
    *,
    cohort_identity: str,
    cohort_count: int,
    expected_controller_provenance: Mapping[str, Any],
) -> bool:
    """Validate the retained four-arm reuse or the two-arm fallback separately."""

    config = getattr(report, "comparison_config", {})
    arms = getattr(report, "arms", ())
    roles = tuple(getattr(arm, "role", None) for arm in arms)
    valid_roles = roles in (T044_CONTROLLER_ROLES, T044_INDEPENDENT_ROLES)
    return (
        getattr(report, "evaluation_successful", False)
        and valid_roles
        and config.get("cohort_identity") == cohort_identity
        and config.get("cohort_record_count") == cohort_count
        and config.get("run_scale") == "fixed"
        and config.get("max_battle_steps") == 200
        and config.get("controller_provenance") == expected_controller_provenance
        and isinstance(config.get("action_space"), Mapping)
        and config["action_space"].get("include_potions") is False
        and all(
            [result.cohort_index for result in arm.report.battle_results]
            == list(range(cohort_count))
            and not arm.report.problems
            for arm in arms
        )
    )


def _validate_t044_frozen_cohort(
    contract: Mapping[str, Any], *, cohort_kind: str
) -> None:
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
    if (
        dataset.information_regime != "full_simulator_state_oracle_like"
        or dataset.action_space_config.get("include_potions") is not False
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
    recorded = getattr(dataset, "generation_metadata", {}).get(
        "t064_complete_identity_order"
    )
    if recorded != expected or len(dataset.records) == 0 or dataset.problems:
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


def _validate_t070_rows(rows: Any, *, cohort_identity: str) -> list[Mapping[str, Any]]:
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
    if not cohort_identity:
        raise ValueError("T070 frozen cohort identity is missing")
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
    adequate = bool(manifest.get("source_adequacy"))
    for stage in stages:
        if not isinstance(stage, Mapping):
            raise ValueError("T064 stage summary has a non-mapping stage")
        name = stage.get("name")
        prefix = name.split("_", 1)[0] if isinstance(name, str) else ""
        if prefix not in expected_counts:
            raise ValueError("T064 stage summary has an unknown stage inventory item")
        actual_counts[prefix] += 1
        if (
            stage.get("code_commit") != code_commit
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
        raise ValueError("T064 stage summary Stage0--7 inventory is incomplete")


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
                path = Path(str(evidence.get("path", "")))
                validate_external_frozen_identity(
                    path, evidence, label=f"T044 {cohort_name} independent report"
                )
                with path.open(encoding="utf-8") as stream:
                    independent = load_de_assisted_fixed_cohort_comparison_jsonl(stream)
                expected_provenance = cohort_contract.get(
                    "independent_controller_provenance"
                )
                if not isinstance(
                    expected_provenance, Mapping
                ) or not validate_t044_independent_report(
                    independent,
                    cohort_identity=str(cohort_contract.get("identity", "")),
                    cohort_count=int(cohort_contract.get("record_count", -1)),
                    expected_controller_provenance=expected_provenance,
                ):
                    raise ValueError("T044 independent roles/config/order mismatch")
                references.append(path)
            except (OSError, ValueError) as exc:
                problems.append(f"external T044 independent evidence invalid: {exc}")
    if not isinstance(frozen_t070, Mapping):
        problems.append("external frozen T070 contract missing")
    else:
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
        if isinstance(baseline_identity, Mapping) and isinstance(
            baseline_contract, Mapping
        ):
            baseline_path = Path(str(baseline_identity.get("path", "")))
            try:
                baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
                if not validate_t070_baseline_reuse(
                    baseline_report,
                    cohort_identity=str(frozen_t070.get("cohort_identity", "")),
                    frozen_contract=baseline_contract,
                ):
                    problems.append("external frozen T070 baseline contract mismatch")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                problems.append(f"external frozen T070 baseline unreadable: {exc}")
        else:
            problems.append("external frozen T070 baseline contract missing")
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
            except (OSError, ValueError) as exc:
                problems.append(f"external frozen T070 cohort unreadable: {exc}")
    for key in TRAINING_RUN_ORDER:
        cohort_paths = t044_paths.get(key)
        t070_path = t070_paths.get(key)
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
                _validate_t044_frozen_cohort(frozen_cohort, cohort_kind=cohort_name)
            except (OSError, ValueError) as exc:
                problems.append(f"T044 frozen cohort mismatch: {exc}")
                continue
            expected_provenance = frozen_cohort.get("dependent_controller_provenance")
            if not isinstance(
                expected_provenance, Mapping
            ) or not validate_t044_dependent_report(
                report,
                cohort_identity=str(frozen_cohort.get("identity", "")),
                cohort_count=int(frozen_cohort.get("record_count", -1)),
                expected_controller_provenance=expected_provenance,
            ):
                problems.append(f"T044 frozen contract mismatch: {path}")
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
        checkpoint = next(
            (
                row.get("checkpoint", {})
                for row in runs
                if (row.get("arm"), row.get("seed")) == key
            ),
            {},
        )
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
            wrapper_artifact = wrapper.get("artifact")
            if not isinstance(wrapper_artifact, Mapping):
                raise ValueError("external persisted T070 wrapper identity missing")
            wrapper_path = Path(str(wrapper_artifact.get("path", "")))
            validate_external_frozen_identity(
                wrapper_path, wrapper_artifact, label="T070 checkpoint wrapper"
            )
            with wrapper_path.open(encoding="utf-8") as stream:
                persisted_wrapper = load_compact_json(stream)
            persisted_stage = persisted_wrapper.get("t070_stage_manifest")
            if (
                persisted_wrapper.get("code_commit") != code_commit
                or not isinstance(persisted_stage, Mapping)
                or persisted_stage.get("checkpoint") != checkpoint
                or persisted_stage.get("frozen_t070_manifest")
                != frozen_t070.get("manifest")
            ):
                raise ValueError("persisted T070 wrapper selection mismatch")
            references.append(wrapper_path)
            contract = {**dict(frozen_t070), **dict(wrapper)}
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
            t052_rows[key] = _validate_t070_rows(
                rows, cohort_identity=str(frozen_t070.get("cohort_identity", ""))
            )
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
