"""Callable TARGET-start workflow for the T077 continuation run."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.non_combat_acceptance import ArtifactIdentity
from sts_combat_rl.sim.non_combat_learning import (
    T065_MAX_STEPS,
    T065_MAX_WORKERS,
    T065_STAGE2_SHARD_COUNT,
    T065_STAGE6_SHARD_COUNT,
    T065CaseD,
    T065CompleteRunArmReport,
    T065TargetTable,
    build_stage5_report,
    build_stage6_paired_rows,
    build_stage6_report,
    compute_learned_coverage,
    generate_counterfactual_targets,
    load_non_combat_checkpoint,
    read_source_states,
    read_target_table,
    run_complete_run_arm,
    select_validation_checkpoint,
    stage6_shard_ranges,
    target_shard_ranges,
    train_frozen_model_seeds,
    write_target_table,
)
from sts_combat_rl.sim.t077_continuation import (
    T075_RETAINED_LINEAGE,
    T075_RETENTION_MANIFEST,
    T075_SELECTED_STATES,
    T077_ACCEPTED_T076_INTEGRATION,
    T077_APPROVED_SPEC,
    T077_EARLIEST_STAGE,
    T077_ROOT_RELATIVE,
    T077_STAGES,
    T077_TASK_ID,
    artifact_identity,
    artifact_path,
    build_t077_continuation_plan,
    verify_t075_reuse_boundary,
    verify_t076_source_manifest,
    write_canonical_json,
)


class T077OperationalError(RuntimeError):
    """Failure before or outside legitimate scientific stage classification."""


class T077ScientificFailure(RuntimeError):
    """Inherited Case-D failure at a legitimately reached stage."""

    def __init__(self, stage: str, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.stage = stage
        self.problems = tuple(str(problem) for problem in problems)


def _t077_adapter() -> LightSpeedAdapter:
    return LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")


def _t077_target_process_worker(payload: tuple[Any, ...]):
    """Spawn-safe TARGET worker; only simple config and source rows cross IPC."""
    states, source_identity, simulator_identity, start, end, max_steps = payload
    shard_states = tuple(
        state for state in states if start <= state.selected_state_index <= end
    )
    if len(shard_states) != 20:
        raise T065CaseD(
            "target-sharding", [f"TARGET shard {start}..{end} is not 20 states"]
        )
    started = time.process_time()
    table = generate_counterfactual_targets(
        _t077_adapter,
        shard_states,
        max_steps=max_steps,
        require_contiguous_indices=False,
        source_artifact_identity=source_identity,
        simulator_identity=simulator_identity,
    )
    table.validate_complete(require_contiguous_indices=False)
    return os.getpid(), table, time.process_time() - started


def _t077_eval_process_worker(
    payload: tuple[Any, ...],
) -> tuple[int, T065CompleteRunArmReport, float]:
    """Spawn-safe Stage-6 worker; load the checkpoint inside each child."""
    arm, seed_start, seed_end, checkpoint_path = payload
    model_run = (
        load_non_combat_checkpoint(Path(checkpoint_path))
        if checkpoint_path is not None
        else None
    )
    started = time.process_time()
    report = run_complete_run_arm(
        _t077_adapter,
        arm=arm,
        seeds=range(seed_start, seed_end + 1),
        model_run=model_run,
        worker_count=1,
    )
    return os.getpid(), report, time.process_time() - started


def _t077_process_pool(
    worker: Callable[[tuple[Any, ...]], Any], payloads: Sequence[tuple[Any, ...]]
) -> list[Any]:
    if not payloads:
        return []
    with ProcessPoolExecutor(
        max_workers=len(payloads), mp_context=mp.get_context("spawn")
    ) as executor:
        return list(executor.map(worker, payloads))


def _t077_target_process_tables(
    states: Sequence[Any],
    source_identity: Mapping[str, Any],
    simulator_identity: Mapping[str, Any],
    max_steps: int,
) -> tuple[tuple[int, Any, float], ...]:
    ordered_states = tuple(sorted(states, key=lambda state: state.selected_state_index))
    specs = target_shard_ranges(worker_count=T065_MAX_WORKERS)
    payloads = tuple(
        (
            tuple(
                state
                for state in ordered_states
                if int(spec["selected_state_start"])
                <= state.selected_state_index
                <= int(spec["selected_state_end"])
            ),
            dict(source_identity),
            dict(simulator_identity),
            int(spec["selected_state_start"]),
            int(spec["selected_state_end"]),
            max_steps,
        )
        for spec in specs
    )
    return tuple(_t077_process_pool(_t077_target_process_worker, payloads))


def _t077_eval_process_reports(
    arm: str, checkpoint_path: Path | None
) -> tuple[tuple[int, T065CompleteRunArmReport, float], ...]:
    specs = stage6_shard_ranges(arm=arm, worker_count=T065_MAX_WORKERS)
    payloads = tuple(
        (
            arm,
            int(spec["seed_start"]),
            int(spec["seed_end"]),
            str(checkpoint_path) if checkpoint_path else None,
        )
        for spec in specs
    )
    with ProcessPoolExecutor(
        max_workers=T065_MAX_WORKERS, mp_context=mp.get_context("spawn")
    ) as executor:
        return tuple(executor.map(_t077_eval_process_worker, payloads))


@dataclass(frozen=True)
class StageResult:
    outputs: tuple[ArtifactIdentity, ...]
    passed: bool = True
    details: Mapping[str, Any] | None = None
    next_parents: tuple[ArtifactIdentity, ...] | None = None


StageRunner = Callable[[Path, Path], StageResult]
ReuseVerifier = Callable[[Path], Mapping[str, Any]]
ManifestVerifier = Callable[[Path], Mapping[str, Any]]


def _git(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), *arguments),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise T077OperationalError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def validate_frozen_checkout(repository_root: Path, run_head: str) -> None:
    root = Path(repository_root).resolve()
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise T077OperationalError("repository root is not checkout top-level")
    if _git(root, "rev-parse", "HEAD") != run_head:
        raise T077OperationalError("T077 run_head does not match checkout HEAD")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise T077OperationalError("T077 scientific execution requires clean checkout")


def _json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise T077OperationalError(f"control record is not an object: {path}")
    return value


def _write_json_artifact(
    path: Path,
    payload: Mapping[str, Any],
    repository_root: Path,
    role: str,
) -> ArtifactIdentity:
    return write_canonical_json(
        path, payload, repository_root=repository_root, role=role
    )


def _run_root(repository_root: Path) -> Path:
    return Path(repository_root) / T077_ROOT_RELATIVE


def _reuse_report(
    repository_root: Path,
    run_head: str,
    reuse: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> ArtifactIdentity:
    payload = {
        "schema_id": "t077-reuse-boundary-v1",
        "schema_version": 1,
        "task_id": T077_TASK_ID,
        "approved_spec": T077_APPROVED_SPEC,
        "run_head": run_head,
        "earliest_stage": T077_EARLIEST_STAGE,
        "target_integration": T077_ACCEPTED_T076_INTEGRATION,
        "source_manifest": dict(manifest),
        "source_reuse_reused_not_rerun": True,
        "selection_replay_reused_not_rerun": True,
        "recollection_performed": False,
        "reselection_performed": False,
        "replacement_performed": False,
        "retained_t075": dict(reuse),
    }
    return _write_json_artifact(
        _run_root(repository_root) / "reuse-boundary.json",
        payload,
        repository_root,
        "reuse_boundary",
    )


def _stage_outcome_path(repository_root: Path, stage: str) -> Path:
    return (
        _run_root(repository_root)
        / "outcomes"
        / (f"{T077_STAGES.index(stage):02d}-{stage.lower()}.json")
    )


def _write_stage_outcome(
    repository_root: Path,
    run_head: str,
    stage: str,
    *,
    valid: bool,
    passed: bool,
    parents: Sequence[ArtifactIdentity],
    outputs: Sequence[ArtifactIdentity],
    wall_clock_seconds: float,
    details: Mapping[str, Any] | None = None,
    problems: Sequence[str] = (),
) -> ArtifactIdentity:
    payload = {
        "schema_id": "t077-stage-outcome-v1",
        "schema_version": 1,
        "task_id": T077_TASK_ID,
        "run_head": run_head,
        "stage": stage,
        "valid": valid,
        "passed": passed,
        "failure_code": None if valid else f"{stage}_INVALID",
        "parents": [item.to_dict() for item in parents],
        "outputs": [item.to_dict() for item in outputs] if valid else [],
        "target_integration": T077_ACCEPTED_T076_INTEGRATION,
        "wall_clock_seconds": wall_clock_seconds,
        "details": dict(details or {}),
        "problems": list(problems),
    }
    return _write_json_artifact(
        _stage_outcome_path(repository_root, stage),
        payload,
        repository_root,
        "stage_outcome",
    )


def _default_target(repository_root: Path, run_root: Path) -> StageResult:
    selected_path = artifact_path(repository_root, T075_SELECTED_STATES)
    states = read_source_states(selected_path)
    if len(states) != 320:
        raise T077ScientificFailure(
            "TARGET", (f"selected state count is {len(states)}, expected 320",)
        )

    source_identity = {**T075_SELECTED_STATES.to_dict(), "record_count": 320}
    try:
        shard_results = _t077_target_process_tables(
            states,
            source_identity,
            lightspeed_source_identity_dict(),
            T065_MAX_STEPS,
        )
        worker_process_ids = tuple(pid for pid, _table, _cpu in shard_results)
        if len(set(worker_process_ids)) != T065_STAGE2_SHARD_COUNT:
            raise T077OperationalError("TARGET did not observe one process per shard")
        shards = tuple(table for _pid, table, _cpu in shard_results)
        table = T065TargetTable(
            states=tuple(states),
            targets=tuple(row for shard in shards for row in shard.targets),
            source_artifact_identity=source_identity,
            simulator_identity=lightspeed_source_identity_dict(),
            expert_action_indices={
                index: action
                for shard in shards
                for index, action in shard.expert_action_indices.items()
            },
            expert_action_provenance=dict(shards[0].expert_action_provenance),
            execution_evidence={
                "worker_count": T065_MAX_WORKERS,
                "shard_count": T065_STAGE2_SHARD_COUNT,
                "executor_kind": "ProcessPoolExecutor",
                "worker_topology": "16 spawned OS processes, one contiguous 20-state shard each",
                "requested_process_count": T065_STAGE2_SHARD_COUNT,
                "observed_process_count": len(set(worker_process_ids)),
                "worker_process_ids": list(worker_process_ids),
                "host_logical_cpu_count": os.cpu_count(),
                "worker_process_cpu_seconds": [
                    cpu for _pid, _table, cpu in shard_results
                ],
                "shard_ranges": [
                    {
                        "start": int(spec["selected_state_start"]),
                        "end": int(spec["selected_state_end"]),
                    }
                    for spec in target_shard_ranges(worker_count=T065_MAX_WORKERS)
                ],
                "state_count": 320,
                "target_count": sum(len(shard.targets) for shard in shards),
            },
        )
        table.validate_complete()
        output = run_root / "target-table.json"
        write_target_table(output, table)
    except T065CaseD as exc:
        raise T077ScientificFailure("TARGET", exc.problems) from exc
    except ValueError as exc:
        raise T077ScientificFailure("TARGET", (str(exc),)) from exc
    target_identity = artifact_identity(output, repository_root, "target_table")
    return StageResult(
        outputs=(target_identity,),
        details={
            "worker_count": T065_MAX_WORKERS,
            "shard_count": T065_STAGE2_SHARD_COUNT,
            "executor_kind": "ProcessPoolExecutor",
            "worker_topology": "16 spawned OS processes, one contiguous 20-state shard each",
            "requested_process_count": T065_STAGE2_SHARD_COUNT,
            "observed_process_count": len(set(worker_process_ids)),
            "worker_process_ids": list(worker_process_ids),
            "host_logical_cpu_count": os.cpu_count(),
            "selected_state_ranges": [
                f"{spec['selected_state_start']}..{spec['selected_state_end']}"
                for spec in target_shard_ranges(worker_count=T065_MAX_WORKERS)
            ],
            "selected_state_count": 320,
        },
        next_parents=(target_identity,),
    )


def _target_identity(repository_root: Path) -> ArtifactIdentity:
    path = _run_root(repository_root) / "target-table.json"
    if not path.is_file():
        raise T077OperationalError("TARGET output is missing")
    return artifact_identity(path, repository_root, "target_table")


def _default_train(repository_root: Path, run_root: Path) -> StageResult:
    target_path = run_root / "target-table.json"
    table = read_target_table(target_path)
    checkpoint_root = run_root / "checkpoints"
    try:
        runs = train_frozen_model_seeds(
            states=table.states,
            targets=table.targets,
            source_artifact_identity=table.source_artifact_identity,
            target_artifact_identity={
                **_target_identity(repository_root).to_dict(),
                "record_count": len(table.targets),
            },
            checkpoint_directory=checkpoint_root,
        )
        selected = select_validation_checkpoint(runs)
    except (T065CaseD, ValueError) as exc:
        problems = exc.problems if isinstance(exc, T065CaseD) else (str(exc),)
        raise T077ScientificFailure("TRAIN", problems) from exc
    checkpoints = tuple(
        artifact_identity(
            checkpoint_root / f"model-{run.model_seed}.pt",
            repository_root,
            "checkpoint",
        )
        for run in runs
    )
    selected_index = [run.model_seed for run in runs].index(selected.model_seed)
    selection_payload = {
        "schema_id": "t077-training-selection-v1",
        "schema_version": 1,
        "task_id": T077_TASK_ID,
        "model_seeds": [run.model_seed for run in runs],
        "validation_mae": [run.validation_mae for run in runs],
        "checkpoints": [item.to_dict() for item in checkpoints],
        "selected_model_seed": selected.model_seed,
        "selected_checkpoint": checkpoints[selected_index].to_dict(),
    }
    selection = _write_json_artifact(
        run_root / "training-selection.json",
        selection_payload,
        repository_root,
        "training_selection",
    )
    target_identity = _target_identity(repository_root)
    selected_checkpoint = checkpoints[selected_index]
    return StageResult(
        outputs=(*checkpoints, selection),
        details={"model_processes": 1, "torch_threads_per_model": 1},
        next_parents=(target_identity, selection, selected_checkpoint),
    )


def _merge_t077_eval_reports(
    results: Sequence[tuple[int, T065CompleteRunArmReport, float]],
    arm: str,
    parent_elapsed_seconds: float,
) -> T065CompleteRunArmReport:
    ordered_results = tuple(
        sorted(results, key=lambda item: item[1].requested_seeds[0])
    )
    ordered = tuple(report for _pid, report, _cpu in ordered_results)
    first = ordered[0]
    return T065CompleteRunArmReport(
        arm=arm,
        driver_seed=first.driver_seed,
        requested_seeds=tuple(
            seed for report in ordered for seed in report.requested_seeds
        ),
        rows=tuple(row for report in ordered for row in report.rows),
        decision_events=tuple(
            event for report in ordered for event in report.decision_events
        ),
        wall_clock_seconds=parent_elapsed_seconds,
        worker_count=T065_MAX_WORKERS,
        shard_count=T065_STAGE6_SHARD_COUNT,
        shard_specs=tuple(
            {
                "shard_index": index,
                "seed_start": report.requested_seeds[0],
                "seed_end": report.requested_seeds[-1],
                "requested_seed_count": len(report.requested_seeds),
                "completed_row_count": len(report.rows),
                "executor_kind": "ProcessPoolExecutor",
                "worker_process_id": ordered_results[index][0],
                "worker_cpu_seconds": ordered_results[index][2],
            }
            for index, report in enumerate(ordered)
        ),
        problems=tuple(problem for report in ordered for problem in report.problems),
        simulator_identity=dict(first.simulator_identity),
        action_space=dict(first.action_space),
        controller_provenance=dict(first.controller_provenance),
        driver_provenance=dict(first.driver_provenance),
    )


def _run_t077_stage6_processes(
    selected_checkpoint: Path,
) -> tuple[
    T065CompleteRunArmReport, T065CompleteRunArmReport, T065CompleteRunArmReport, Any
]:
    started = time.perf_counter()
    stochastic_results = _t077_eval_process_reports("stochastic", None)
    expert_results = _t077_eval_process_reports("expert", None)
    learned_results = _t077_eval_process_reports("learned", selected_checkpoint)
    elapsed = time.perf_counter() - started
    stochastic = _merge_t077_eval_reports(stochastic_results, "stochastic", elapsed)
    expert = _merge_t077_eval_reports(expert_results, "expert", elapsed)
    learned = _merge_t077_eval_reports(learned_results, "learned", elapsed)
    coverage = compute_learned_coverage(learned.decision_events)
    paired = build_stage6_paired_rows(expert, learned, stochastic_report=stochastic)
    report = build_stage6_report(
        paired,
        coverage,
        execution_evidence={
            "worker_count": T065_MAX_WORKERS,
            "shard_count_per_arm": T065_STAGE6_SHARD_COUNT,
            "executor_kind": "ProcessPoolExecutor",
            "worker_topology": "16 spawned OS processes per arm, one contiguous 16-seed shard each",
            "requested_process_count": T065_MAX_WORKERS,
            "observed_process_count": len(
                {
                    pid
                    for results in (stochastic_results, expert_results, learned_results)
                    for pid, _report, _cpu in results
                }
            ),
            "host_logical_cpu_count": os.cpu_count(),
            "arms": {
                arm: {
                    "worker_process_ids": [pid for pid, _report, _cpu in results],
                    "observed_process_count": len(
                        {pid for pid, _report, _cpu in results}
                    ),
                    "shard_ranges": [
                        {
                            "start": report.requested_seeds[0],
                            "end": report.requested_seeds[-1],
                        }
                        for _pid, report, _cpu in results
                    ],
                }
                for arm, results in (
                    ("stochastic", stochastic_results),
                    ("expert", expert_results),
                    ("learned", learned_results),
                )
            },
        },
        arm_reports=(stochastic, expert, learned),
    )
    return stochastic, expert, learned, report


def _default_gate(repository_root: Path, run_root: Path) -> StageResult:
    table = read_target_table(run_root / "target-table.json")
    runs = tuple(
        load_non_combat_checkpoint(run_root / "checkpoints" / f"model-{seed}.pt")
        for seed in (653001, 653002)
    )
    try:
        report = build_stage5_report(runs, table)
    except (T065CaseD, ValueError) as exc:
        problems = exc.problems if isinstance(exc, T065CaseD) else (str(exc),)
        raise T077ScientificFailure("GATE", problems) from exc
    output = _write_json_artifact(
        run_root / "heldout-gate-report.json",
        report.to_dict(),
        repository_root,
        "stage5_report",
    )
    selection_identity = artifact_identity(
        run_root / "training-selection.json", repository_root, "training_selection"
    )
    selected_checkpoint = ArtifactIdentity.from_mapping(
        _json(run_root / "training-selection.json")["selected_checkpoint"]
    )
    return StageResult(
        outputs=(output,),
        passed=report.passed,
        details={
            "selected_model_seed": report.selected_model_seed,
            "aggregate_mean_delta": report.aggregate_mean_delta,
            "median_delta": report.median_delta,
            "p_positive": report.p_positive,
            "problems": list(report.problems),
        },
        next_parents=(output, selection_identity, selected_checkpoint),
    )


def _default_eval(repository_root: Path, run_root: Path) -> StageResult:
    stage5_payload = _json(run_root / "heldout-gate-report.json")
    from sts_combat_rl.sim.non_combat_learning import t065_stage5_report_from_dict

    stage5 = t065_stage5_report_from_dict(stage5_payload)
    if not stage5.passed:
        raise ValueError("T065 Stage 6 is conditionally skipped when Stage 5 fails")
    selected_checkpoint = ArtifactIdentity.from_mapping(
        _json(run_root / "training-selection.json")["selected_checkpoint"]
    )

    try:
        stochastic, expert, learned, report = _run_t077_stage6_processes(
            artifact_path(repository_root, selected_checkpoint)
        )
    except (T065CaseD, ValueError) as exc:
        problems = exc.problems if isinstance(exc, T065CaseD) else (str(exc),)
        raise T077ScientificFailure("EVAL", problems) from exc
    outputs = []
    for arm_report in (stochastic, expert, learned):
        outputs.append(
            _write_json_artifact(
                run_root / f"stage6-{arm_report.arm}-arm.json",
                arm_report.to_dict(),
                repository_root,
                "stage6_arm_report",
            )
        )
    outputs.append(
        _write_json_artifact(
            run_root / "complete-run-report.json",
            report.to_dict(),
            repository_root,
            "stage6_report",
        )
    )
    return StageResult(
        outputs=tuple(outputs),
        passed=report.passed,
        details=dict(report.execution_evidence),
    )


def _terminal_case(stage: str, valid: bool, passed: bool) -> str | None:
    if not valid:
        return "D"
    if stage == "GATE" and not passed:
        return "C"
    if stage == "EVAL":
        return "A" if passed else "B"
    return None


def _finalize(
    repository_root: Path,
    run_head: str,
    terminal_case: str,
    terminal_stage: str,
    reuse_identity: ArtifactIdentity,
    outcomes: Sequence[ArtifactIdentity],
    outputs: Sequence[ArtifactIdentity],
) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    terminal_payload = {
        "schema_id": "t077-terminal-decision-v1",
        "schema_version": 1,
        "task_id": T077_TASK_ID,
        "run_head": run_head,
        "terminal_case": terminal_case,
        "terminal_stage": terminal_stage,
        "promotion": "experimental_public_with_expert_fallback"
        if terminal_case == "A"
        else "no_promotion",
        "stage_outcomes": [item.to_dict() for item in outcomes],
        "source_reuse_reused_not_rerun": True,
        "selection_replay_reused_not_rerun": True,
        "replacement_performed": False,
    }
    terminal = _write_json_artifact(
        _run_root(repository_root) / "terminal-decision.json",
        terminal_payload,
        repository_root,
        "terminal_report",
    )
    retained = [reuse_identity, *outcomes, *outputs, terminal]
    retention_payload = {
        "schema_id": "t077-retention-v1",
        "schema_version": 1,
        "task_id": T077_TASK_ID,
        "run_head": run_head,
        "terminal_case": terminal_case,
        "retention_owner": T077_TASK_ID,
        "retention_reason": "T077 same-experiment continuation evidence",
        "deletion_condition_code": "after_merge_no_consumer_or_reproduction_hold",
        "inherited_inputs": [
            item.to_dict() for item in (*T075_RETAINED_LINEAGE, T075_RETENTION_MANIFEST)
        ],
        "entries": [item.to_dict() for item in retained],
    }
    retention = _write_json_artifact(
        _run_root(repository_root) / "retention.json",
        retention_payload,
        repository_root,
        "retention_manifest",
    )
    return terminal, retention


def run_t077_workflow(
    repository_root: Path,
    run_head: str,
    *,
    artifact_repository_root: Path | None = None,
    validate_checkout: bool = True,
    reuse_verifier: ReuseVerifier = verify_t075_reuse_boundary,
    manifest_verifier: ManifestVerifier = verify_t076_source_manifest,
    target_runner: StageRunner = _default_target,
    train_runner: StageRunner = _default_train,
    gate_runner: StageRunner = _default_gate,
    eval_runner: StageRunner = _default_eval,
) -> Mapping[str, Any]:
    """Execute the unchanged inherited experiment from TARGET to one terminal."""

    root = Path(repository_root).resolve()
    artifact_root = (
        Path(artifact_repository_root).resolve()
        if artifact_repository_root is not None
        else root
    )
    build_t077_continuation_plan(run_head)
    if validate_checkout:
        validate_frozen_checkout(root, run_head)
    reuse = reuse_verifier(artifact_root)
    manifest = manifest_verifier(root)
    if manifest.get("integration_commit") != T077_ACCEPTED_T076_INTEGRATION:
        raise T077OperationalError("runtime manifest integration is not accepted T076")
    reuse_identity = _reuse_report(artifact_root, run_head, reuse, manifest)
    run_root = _run_root(artifact_root)
    runners = {
        "TARGET": target_runner,
        "TRAIN": train_runner,
        "GATE": gate_runner,
        "EVAL": eval_runner,
    }
    parents: list[ArtifactIdentity] = [reuse_identity, T075_SELECTED_STATES]
    outcomes: list[ArtifactIdentity] = []
    outputs: list[ArtifactIdentity] = []
    for stage in T077_STAGES:
        started = time.perf_counter()
        try:
            result = runners[stage](artifact_root, run_root)
        except T077ScientificFailure as exc:
            if exc.stage != stage:
                raise T077OperationalError(
                    f"{stage} runner returned scientific failure for {exc.stage}"
                ) from exc
            outcome = _write_stage_outcome(
                artifact_root,
                run_head,
                stage,
                valid=False,
                passed=False,
                parents=parents,
                outputs=(),
                wall_clock_seconds=time.perf_counter() - started,
                problems=exc.problems,
                details={
                    "downstream_skipped": list(
                        T077_STAGES[T077_STAGES.index(stage) + 1 :]
                    ),
                    "no_replacement": True,
                },
            )
            outcomes.append(outcome)
            terminal, retention = _finalize(
                artifact_root,
                run_head,
                "D",
                stage,
                reuse_identity,
                outcomes,
                outputs,
            )
            return {
                "terminal_case": "D",
                "terminal_stage": stage,
                "terminal_report": terminal.to_dict(),
                "retention_manifest": retention.to_dict(),
            }
        outcome = _write_stage_outcome(
            artifact_root,
            run_head,
            stage,
            valid=True,
            passed=result.passed,
            parents=parents,
            outputs=result.outputs,
            wall_clock_seconds=time.perf_counter() - started,
            details=result.details,
        )
        outcomes.append(outcome)
        outputs.extend(result.outputs)
        terminal_case = _terminal_case(stage, True, result.passed)
        if terminal_case is not None:
            terminal, retention = _finalize(
                artifact_root,
                run_head,
                terminal_case,
                stage,
                reuse_identity,
                outcomes,
                outputs,
            )
            return {
                "terminal_case": terminal_case,
                "terminal_stage": stage,
                "terminal_report": terminal.to_dict(),
                "retention_manifest": retention.to_dict(),
            }
        parents = list(result.next_parents or result.outputs)
    raise T077OperationalError("T077 workflow reached no terminal")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify", "run"))
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument(
        "--artifact-repository-root",
        type=Path,
        help="repository root containing the authoritative stable artifacts tree",
    )
    parser.add_argument("--run-head", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        build_t077_continuation_plan(args.run_head)
        validate_frozen_checkout(args.repository_root.resolve(), args.run_head)
        artifact_root = (
            args.artifact_repository_root.resolve()
            if args.artifact_repository_root is not None
            else args.repository_root.resolve()
        )
        reuse = verify_t075_reuse_boundary(artifact_root)
        manifest = verify_t076_source_manifest(args.repository_root.resolve())
        if args.operation == "verify":
            print(
                json.dumps(
                    {"reuse": reuse, "source_manifest": manifest}, sort_keys=True
                )
            )
            return 0
        result = run_t077_workflow(
            args.repository_root,
            args.run_head,
            artifact_repository_root=artifact_root,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, T077OperationalError, ValueError) as exc:
        print(f"T077 error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
