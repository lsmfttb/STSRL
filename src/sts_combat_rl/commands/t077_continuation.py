"""Callable TARGET-start workflow for the T077 continuation run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.non_combat_acceptance import ArtifactIdentity
from sts_combat_rl.sim.non_combat_learning import (
    T065_MAX_WORKERS,
    T065CaseD,
    build_stage5_report,
    generate_counterfactual_targets_sharded,
    load_non_combat_checkpoint,
    read_source_states,
    read_target_table,
    run_stage6_experiment,
    select_validation_checkpoint,
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

    def factory() -> LightSpeedAdapter:
        return LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")

    source_identity = {**T075_SELECTED_STATES.to_dict(), "record_count": 320}
    try:
        table = generate_counterfactual_targets_sharded(
            factory,
            states,
            worker_count=T065_MAX_WORKERS,
            source_artifact_identity=source_identity,
            simulator_identity=lightspeed_source_identity_dict(),
        )
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
            "worker_count": 16,
            "shard_count": 16,
            "selected_state_ranges": [f"{20 * i}..{20 * i + 19}" for i in range(16)],
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


def _load_selected_model(repository_root: Path):
    selection = _json(_run_root(repository_root) / "training-selection.json")
    checkpoint = ArtifactIdentity.from_mapping(selection["selected_checkpoint"])
    return load_non_combat_checkpoint(artifact_path(repository_root, checkpoint))


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
    selected_model = _load_selected_model(repository_root)

    def factory() -> LightSpeedAdapter:
        return LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")

    try:
        stochastic, expert, learned, report = run_stage6_experiment(
            factory,
            stage5=stage5,
            selected_model=selected_model,
            worker_count=T065_MAX_WORKERS,
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
