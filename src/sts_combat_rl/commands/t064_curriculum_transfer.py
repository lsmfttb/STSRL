"""Executable, restart-safe orchestration for the T064 reuse-first transfer.

The module intentionally owns only the small amount of glue T064 needs.  It
does not implement a simulator, a teacher format, a trainer format, or an
evaluation format: callers provide the existing T043/T044/T070 runners.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
import time
from typing import Any

from sts_combat_rl.commands.oracle_teacher_scaleup import (
    collect_oracle_teacher_range_from_selected_manifest,
)
from sts_combat_rl.commands.de_assisted_fixed_cohort_comparison import (
    merge_de_assisted_fixed_cohort_comparison_shards,
    run_de_assisted_fixed_cohort_comparison_from_cohort_path,
)
from sts_combat_rl.sim.oracle_teacher import OracleTeacherDataset
from sts_combat_rl.sim.t064_curriculum import (
    BUCKETS,
    COMPACT_FILENAMES,
    TRAINING_RUN_ORDER,
    TRAINING_RUN_REPORT_FILENAME,
    TRANSFER_GATE_NAMES,
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
) -> OracleTeacherDataset:
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
    started = time.perf_counter()
    shards = [
        shard_runner(
            adapter_factory=adapter_factory,
            pool=pool,
            controller=controller,
            selected_source_manifest=selected_manifest,
            record_range=record_range,
            action_space=action_space,
        )
        for record_range in ranges
    ]
    del started  # the caller records wall-clock timing in the sole stage summary.
    return merge_t064_teacher_shards(
        shards=shards, selected_manifest=selected_manifest, expected_ranges=ranges
    )


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
    dataset: Any,
    initialization_checkpoint_path: Path,
    initialization_sha256: str,
    trainer_input_path: Path,
    batch_plans: Sequence[Mapping[str, Any]],
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
    plans_by_run = {
        (str(plan.get("arm")), int(plan.get("seed"))): plan for plan in batch_plans
    }
    if tuple(plans_by_run) != TRAINING_RUN_ORDER:
        raise ValueError("T064 training plans do not use the frozen run order")
    validate_exposure_parity([plans_by_run[key] for key in TRAINING_RUN_ORDER])
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
    if config.get("max_battle_steps") != 200:
        return False
    action_space = config.get("action_space")
    if (
        not isinstance(action_space, Mapping)
        or action_space.get("include_potions") is not False
    ):
        return False
    if not getattr(report, "evaluation_successful", False) or len(arms) != 4:
        return False
    return all(
        not arm.report.problems and len(arm.report.battle_results) == cohort_count
        for arm in arms
    )


def run_t064_t044_dependent_stage(
    *,
    adapter_factory: Callable[[], Any],
    cohort_path: Path,
    controller_arms: Sequence[Any],
    cohort_kind: str,
    shard_runner: Callable[
        ..., Any
    ] = run_de_assisted_fixed_cohort_comparison_from_cohort_path,
    merger: Callable[..., Any] = merge_de_assisted_fixed_cohort_comparison_shards,
) -> Any:
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
    shards = [
        shard_runner(
            adapter_factory,
            cohort_path,
            controller_arms=controller_arms,
            action_space=controller_arms[0][2].action_space,
            max_battle_steps=200,
            run_scale="fixed",
            record_range=record_range,
        )
        for record_range in ranges
    ]
    return merger(cohort_path=cohort_path, shards=shards, expected_ranges=ranges)


def validate_t070_baseline_reuse(
    report: Mapping[str, Any], *, cohort_identity: str
) -> bool:
    """Validate the T070 baseline without treating a display label as an arm role."""

    return (
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


def t064_t070_wrapper(
    *,
    current_code_commit: str,
    frozen_t070_manifest: Mapping[str, Any],
    frozen_identity: Mapping[str, Any],
    checkpoint_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the identity-bound wrapper consumed by the parameterized T070 runner."""

    if frozen_t070_manifest.get("schema_id") != "t070-frozen-manifest-v1":
        raise ValueError("T064 wrapper needs the historical T070 frozen manifest")
    if frozen_t070_manifest.get("code_commit") == current_code_commit:
        raise ValueError(
            "T064 must bind T070 to its historical, not current, code commit"
        )
    if tuple(frozen_t070_manifest.get("primary_shard_ranges", ())) != T070_T052_RANGES:
        raise ValueError("T064 wrapper refuses non-frozen T070 ranges")
    return {
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
    """Write the final two compact documents and independently rehash all evidence."""

    if root.name != T064_ARTIFACT_ROOT_NAME:
        raise ValueError("T064 artifacts must use the stable named root")
    _assert_existing_or_new(root, COMPACT_FILENAMES)
    source_audit = manifest.get("complete_source_audit", {})
    integrity = (
        isinstance(source_audit, Mapping)
        and source_audit.get("status") == "complete"
        and source_audit.get("candidate_duplicate_complete_identity_count") == 0
        and source_audit.get("selected_duplicate_complete_identity_count") == 0
        and source_audit.get("selected_holdout_overlap_count") == 0
        and source_audit.get("selected_restore_failure_count") == 0
    )
    complete = bool(diagnostics.get("experiment_complete"))
    gates = (
        compute_transfer_gates(diagnostics)
        if complete
        else {name: None for name in TRANSFER_GATE_NAMES}
    )
    decision = build_transfer_decision(
        source_adequate=bool(manifest.get("source_adequacy")),
        source_integrity_valid=integrity,
        experiment_complete=complete,
        complete_source_audit_status=(
            source_audit.get("status") if isinstance(source_audit, Mapping) else None
        ),
        transfer_gates=gates,
        diagnostics=diagnostics,
        problems=tuple(diagnostics.get("problems", ())),
        unmet_acceptance_criteria=tuple(
            diagnostics.get("unmet_acceptance_criteria", ())
        ),
    )
    refuse_overwrite(root / "t064-stage-summary.json")
    refuse_overwrite(root / "t064-transfer-decision.json")
    write_compact_json(root / "t064-stage-summary.json", stage_summary)
    write_compact_json(root / "t064-transfer-decision.json", decision)
    rehash = independent_rehash(root, referenced_paths)
    return {"decision": decision, "rehash": rehash}


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
