"""Neutral command surface for the T065 non-combat learning workflow.

This module is deliberately not wired into the legacy flat CLI.  Long-running
collection and evaluation are explicit subcommands so their artifact paths,
seed ranges, and stage boundaries remain visible in the command itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
from typing import Any, Mapping

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065_SOURCE_SEED_RANGE,
    T065CaseD,
    build_stage5_report,
    build_t065_preflight_report,
    collect_source_arm,
    collect_source_arm_sharded,
    file_sha256,
    frozen_battle_provenance,
    frozen_action_space,
    load_non_combat_checkpoint,
    read_source_states,
    read_target_table,
    run_stage6_experiment,
    select_source_states,
    train_frozen_model_seeds,
    terminal_decision_report,
    validate_t065_preflight,
    write_source_states,
    write_target_table,
    generate_counterfactual_targets,
    generate_counterfactual_targets_sharded,
    write_source_selection_manifest,
    write_t065_manifest,
    write_t065_terminal_decision_report,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.non_combat_learning",
        description="T065 learned public non-combat policy workflow",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser(
        "preflight", help="run cheap schema readiness checks"
    )
    preflight.add_argument("--output", type=Path, required=True)
    preflight.add_argument("--decision-report", type=Path)
    preflight.add_argument("--retention-manifest", type=Path)
    preflight.add_argument(
        "--simulator-runtime",
        action="store_true",
        help="explicitly probe the WSL-provided simulator runtime",
    )
    preflight.add_argument(
        "--torch-runtime",
        action="store_true",
        help="explicitly probe the optional PyTorch runtime",
    )
    preflight.add_argument("--sim-seed", type=int, default=1)
    preflight.add_argument("--ascension", type=int, default=20)

    collect = subparsers.add_parser(
        "collect", help="collect one fixed source behavior arm"
    )
    collect.add_argument(
        "--arm",
        choices=("stochastic_non_combat_v1", "expert_non_combat_v1"),
        required=True,
    )
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--seed-start", type=int, default=T065_SOURCE_SEED_RANGE[0])
    collect.add_argument("--seed-end", type=int, default=T065_SOURCE_SEED_RANGE[1])
    collect.add_argument("--sim-seed", type=int, default=1)
    collect.add_argument("--ascension", type=int, default=20)
    collect.add_argument("--decision-report", type=Path)
    collect.add_argument("--preflight", type=Path, required=True)
    collect.add_argument("--retention-manifest", type=Path)

    select = subparsers.add_parser(
        "select", help="deduplicate and select the frozen cohort"
    )
    select.add_argument("--input", type=Path, action="append", required=True)
    select.add_argument("--output", type=Path, required=True)
    select.add_argument("--manifest", type=Path)
    select.add_argument("--decision-report", type=Path)
    select.add_argument("--preflight", type=Path, required=True)
    select.add_argument("--retention-manifest", type=Path)

    target = subparsers.add_parser(
        "target", help="generate all-action counterfactual targets"
    )
    target.add_argument("--states", type=Path, required=True)
    target.add_argument("--output", type=Path, required=True)
    target.add_argument("--sim-seed", type=int, default=1)
    target.add_argument("--ascension", type=int, default=20)
    target.add_argument("--decision-report", type=Path)
    target.add_argument("--preflight", type=Path, required=True)
    target.add_argument("--retention-manifest", type=Path)

    train = subparsers.add_parser("train", help="train the two frozen model seeds")
    train.add_argument("--target-table", type=Path, required=True)
    train.add_argument("--checkpoint-directory", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--preflight", type=Path, required=True)
    train.add_argument("--decision-report", type=Path)
    train.add_argument("--retention-manifest", type=Path)

    evaluate = subparsers.add_parser(
        "evaluate", help="run held-out gate and conditional Stage 6"
    )
    evaluate.add_argument("--target-table", type=Path, required=True)
    evaluate.add_argument("--checkpoint-directory", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--run-stage6", action="store_true")
    evaluate.add_argument("--sim-seed", type=int, default=1)
    evaluate.add_argument("--ascension", type=int, default=20)
    evaluate.add_argument("--preflight", type=Path, required=True)
    evaluate.add_argument("--decision-report", type=Path)
    evaluate.add_argument("--retention-manifest", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            return _run_preflight(args)
        if args.command == "collect":
            return _run_collect(args)
        if args.command == "select":
            return _run_select(args)
        if args.command == "target":
            return _run_target(args)
        if args.command == "train":
            return _run_train(args)
        if args.command == "evaluate":
            return _run_evaluate(args)
    except T065CaseD as exc:
        _handle_case_d(args, exc)
        print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        failure = T065CaseD(
            _stage_name(args.command),
            [str(exc)],
            failure_ids=(f"command:{args.command}",),
            failure_counts={"failure_count": 1},
            simulator_identity=lightspeed_source_identity_dict(),
        )
        _handle_case_d(args, failure)
        print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    return 2


def _run_preflight(args: argparse.Namespace) -> int:
    factory = None
    if args.simulator_runtime:
        factory = lambda: LightSpeedAdapter(  # noqa: E731
            seed=args.sim_seed,
            ascension=args.ascension,
            player_class="IRONCLAD",
        )
    report = build_t065_preflight_report(
        adapter_factory=factory,
        check_simulator_runtime=args.simulator_runtime,
        check_torch_runtime=args.torch_runtime,
    ).to_dict()
    _write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    if not report["passed"]:
        failed_checks = tuple(
            name
            for section in ("capability_checks", "runtime_checks")
            for name, check in report.get(section, {}).items()
            if not isinstance(check, Mapping) or check.get("status") != "passed"
        )
        raise T065CaseD(
            "stage0-preflight",
            tuple(report.get("problems", ())) or ("preflight did not pass",),
            failure_ids=tuple(f"preflight-check:{name}" for name in failed_checks),
            failure_counts={"failed_checks": len(failed_checks)},
            simulator_identity=report.get("simulator_identity", {}),
        )
    _write_workflow_manifest(args, stage="stage0-preflight")
    return 0


def _run_collect(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_frozen_simulator_args(args)
    seeds = tuple(range(args.seed_start, args.seed_end + 1))
    factory = lambda: LightSpeedAdapter(  # noqa: E731 - explicit per-worker factory
        seed=args.sim_seed,
        ascension=args.ascension,
        player_class="IRONCLAD",
    )
    if (args.seed_start, args.seed_end) == T065_SOURCE_SEED_RANGE:
        report = collect_source_arm_sharded(
            factory,
            source_arm=args.arm,
            worker_count=16,
        )
    else:
        report = collect_source_arm(factory, source_arm=args.arm, seeds=seeds)
    _write_json(args.output, report.to_dict())
    print(
        f"T065 collected arm={args.arm} seeds={len(seeds)} "
        f"candidates={report.selected_candidate_count} "
        f"terminal={report.terminal_run_count} "
        f"truncated={report.truncated_run_count}",
        file=sys.stderr,
    )
    if not _source_report_is_complete(report):
        failed_ids = tuple(
            f"simulator_seed:{summary.get('simulator_seed')}"
            for summary in report.run_summaries
            if not summary.get("terminal") or summary.get("problems")
        )
        raise T065CaseD(
            "source-collection",
            report.problems
            or ("one or more frozen Stage 1 source runs did not complete",),
            failure_ids=failed_ids,
            failure_counts={
                "requested_runs": report.requested_seed_count,
                "terminal_runs": report.terminal_run_count,
                "truncated_runs": report.truncated_run_count,
                "failed_runs": report.failed_run_count,
            },
            simulator_identity=report.simulator_identity,
        )
    _write_workflow_manifest(args, stage="stage1-source-collection")
    return 0


def _run_select(args: argparse.Namespace) -> int:
    _require_preflight(args)
    if len(args.input) != 2:
        raise ValueError("T065 selection requires exactly two source-arm artifacts")
    candidates = []
    source_artifacts = []
    observed_arms = set()
    simulator_identity: Mapping[str, Any] | None = None
    for path in args.input:
        value = _load_json_object(path)
        arm = _validate_source_arm_artifact(value, path)
        if arm in observed_arms:
            raise ValueError(f"duplicate T065 source arm artifact: {arm}")
        observed_arms.add(arm)
        artifact_simulator_identity = value.get("simulator_identity")
        if not isinstance(artifact_simulator_identity, Mapping):
            raise T065CaseD(
                "source-selection", [f"{path}: simulator identity is missing"]
            )
        expected_simulator_identity = lightspeed_source_identity_dict()
        if dict(artifact_simulator_identity) != expected_simulator_identity:
            raise T065CaseD(
                "source-selection",
                [f"{path}: simulator identity does not match the pinned manifest"],
            )
        if simulator_identity is None:
            simulator_identity = dict(artifact_simulator_identity)
        elif dict(artifact_simulator_identity) != dict(simulator_identity):
            raise T065CaseD(
                "source-selection", [f"{path}: simulator identities do not match"]
            )
        rows = value["records"]
        candidates.extend(read_source_states_from_objects(rows, path))
        source_artifacts.append(
            {
                "arm": arm,
                "path": str(path),
                "sha256": file_sha256(path),
                "record_count": len(rows),
            }
        )
    if observed_arms != {
        "stochastic_non_combat_v1",
        "expert_non_combat_v1",
    }:
        raise ValueError("T065 selection requires stochastic and expert source arms")
    selected = select_source_states(candidates)
    digest = write_source_states(args.output, selected)
    manifest_path = args.manifest or Path(f"{args.output}.manifest.json")
    write_source_selection_manifest(
        manifest_path,
        selected_states=selected,
        selected_artifact_identity={
            "path": str(args.output),
            "sha256": digest,
            "record_count": len(selected),
        },
        source_artifacts=source_artifacts,
        simulator_identity=simulator_identity or {},
        approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
    )
    print(
        f"T065 selected states={len(selected)} sha256={digest} "
        f"manifest={manifest_path}",
        file=sys.stderr,
    )
    _write_workflow_manifest(args, stage="stage1-source-selection")
    return 0


def _run_target(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_frozen_simulator_args(args)
    states = read_source_states(args.states)
    if len(states) != 320:
        raise T065CaseD(
            "counterfactual-targets",
            [f"selected state count {len(states)} does not match frozen 320"],
            failure_ids=(f"selected_state_count:{len(states)}",),
            failure_counts={"selected_states": len(states), "required_states": 320},
            simulator_identity=lightspeed_source_identity_dict(),
        )
    source_artifact_identity = {
        "path": str(args.states),
        "sha256": file_sha256(args.states),
        "record_count": len(states),
    }
    simulator_identity = lightspeed_source_identity_dict()
    factory = lambda: LightSpeedAdapter(  # noqa: E731 - explicit per-worker factory
        seed=args.sim_seed,
        ascension=args.ascension,
        player_class="IRONCLAD",
    )
    table = (
        generate_counterfactual_targets_sharded(
            factory,
            states,
            worker_count=16,
            source_artifact_identity=source_artifact_identity,
            simulator_identity=simulator_identity,
        )
        if len(states) == 320
        else generate_counterfactual_targets(
            factory,
            states,
            source_artifact_identity=source_artifact_identity,
            simulator_identity=simulator_identity,
        )
    )
    digest = write_target_table(args.output, table)
    print(
        f"T065 target table rows={len(table.targets)} sha256={digest}", file=sys.stderr
    )
    _write_workflow_manifest(args, stage="stage2-counterfactual-targets")
    return 0


def _run_train(args: argparse.Namespace) -> int:
    _require_preflight(args)
    table = read_target_table(args.target_table)
    args.checkpoint_directory.mkdir(parents=True, exist_ok=True)
    runs = train_frozen_model_seeds(
        states=table.states,
        targets=table.targets,
        source_artifact_identity=table.source_artifact_identity,
        target_artifact_identity={
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
        },
        checkpoint_directory=args.checkpoint_directory,
    )
    _write_json(
        args.output,
        {
            "schema_id": "t065-training-report-v1",
            "schema_version": 1,
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": dict(table.simulator_identity),
            "source_artifact_identity": dict(table.source_artifact_identity),
            "target_artifact_identity": {
                "path": str(args.target_table),
                "sha256": file_sha256(args.target_table),
            },
            "model_input_schema": table.to_dict()["model_input_schema"],
            "models": [
                {
                    "model_seed": run.model_seed,
                    "validation_q_floor_mae": run.validation_mae,
                    "checkpoint_path": run.checkpoint_path,
                    "checkpoint_sha256": file_sha256(Path(run.checkpoint_path))
                    if run.checkpoint_path
                    else None,
                    "metadata": dict(run.metadata),
                }
                for run in runs
            ],
        },
    )
    print(f"T065 trained models={len(runs)}", file=sys.stderr)
    _write_workflow_manifest(args, stage="stage4-training")
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_frozen_simulator_args(args)
    table = read_target_table(args.target_table)
    model_runs = tuple(
        load_non_combat_checkpoint(args.checkpoint_directory / f"model-{seed}.pt")
        for seed in (653001, 653002)
    )
    stage5 = build_stage5_report(model_runs, table)
    payload: dict[str, Any] = {
        "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
        "simulator_identity": dict(table.simulator_identity),
        "target_artifact_identity": {
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
        },
        "model_input_schema": table.to_dict()["model_input_schema"],
        "stage5": stage5.to_dict(),
    }
    if stage5.passed and args.run_stage6:
        selected = next(
            run for run in model_runs if run.model_seed == stage5.selected_model_seed
        )
        stochastic, expert, learned, stage6 = run_stage6_experiment(
            lambda: LightSpeedAdapter(
                seed=args.sim_seed,
                ascension=args.ascension,
                player_class="IRONCLAD",
            ),
            stage5=stage5,
            selected_model=selected,
        )
        payload["stage6_arms"] = {
            "stochastic": stochastic.to_dict(),
            "expert": expert.to_dict(),
            "learned": learned.to_dict(),
        }
        payload["stage6"] = stage6.to_dict()
        if not stage6.valid:
            _write_json(args.output, payload)
            raise T065CaseD(
                "stage6",
                stage6.problems or ("Stage 6 reducer rejected the cohort",),
                failure_ids=tuple(
                    f"stage6-problem:{index}"
                    for index, _problem in enumerate(stage6.problems)
                ),
                failure_counts={
                    "paired_rows": len(stage6.paired_terminal_floor_deltas),
                    "controller_errors": stage6.controller_error_count,
                    "truncations": stage6.truncation_count,
                },
                simulator_identity=table.simulator_identity,
            )
        payload["decision"] = terminal_decision_report(
            stage5=stage5,
            stage6=stage6,
            simulator_identity=table.simulator_identity,
            preceding_stage_manifests=_artifact_identities(
                _preceding_artifact_paths(args)
            ),
        )
    else:
        if stage5.passed:
            payload["decision_status"] = "incomplete"
            payload["incomplete"] = True
            payload["decision_pending"] = (
                "Stage 6 was not requested; rerun with --run-stage6 before "
                "writing the terminal Case A/B decision"
            )
        else:
            payload["decision"] = terminal_decision_report(
                stage5=stage5,
                simulator_identity=table.simulator_identity,
                preceding_stage_manifests=_artifact_identities(
                    _preceding_artifact_paths(args)
                ),
            )
    _write_json(args.output, payload)
    decision_path: Path | None = None
    if "decision" in payload:
        decision_path = _decision_report_path(args)
        _write_json(decision_path, payload["decision"])
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    if "decision_pending" in payload:
        _write_workflow_manifest(args, stage="stage5-heldout-pending-stage6")
        return 1
    _write_workflow_manifest(
        args,
        stage="stage5-stage6-evaluation",
        decision_path=decision_path,
        terminal=True,
        terminal_case=payload["decision"]["case"],
    )
    return 0 if payload["decision"]["case"] in {"A", "B", "C", "D"} else 1


def read_source_states_from_objects(rows: list[Any], path: Path) -> list[Any]:
    result = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{path}: source row {index} is not an object")
        # Reuse the strict current-schema reader without inventing a second
        # deserialization path.
        from sts_combat_rl.sim.non_combat_learning import T065SourceState

        result.append(T065SourceState.from_dict(row))
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return {str(key): item for key, item in value.items()}


def _validate_source_arm_artifact(value: Mapping[str, Any], path: Path) -> str:
    expected_seeds = set(range(650001, 650257))
    if value.get("schema_id") != "t065-learned-non-combat-policy-v1":
        raise T065CaseD("source-collection", [f"{path}: source schema is unsupported"])
    arm = value.get("arm")
    if not isinstance(arm, str) or arm not in {
        "stochastic_non_combat_v1",
        "expert_non_combat_v1",
    }:
        raise T065CaseD("source-collection", [f"{path}: source arm is invalid"])
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        raise T065CaseD(
            "source-collection", [f"{path}: approved T065 spec commit is invalid"]
        )
    if value.get("driver_seed") != 654001:
        raise T065CaseD("source-collection", [f"{path}: source driver seed is invalid"])
    if value.get("requested_seed_count") != 256:
        raise T065CaseD("source-collection", [f"{path}: source seed count is not 256"])
    if value.get("terminal_run_count") != 256:
        raise T065CaseD(
            "source-collection", [f"{path}: not all source runs are terminal"]
        )
    if value.get("truncated_run_count") != 0 or value.get("failed_run_count") != 0:
        raise T065CaseD(
            "source-collection", [f"{path}: source run truncation/failure reported"]
        )
    if value.get("problems") != []:
        raise T065CaseD(
            "source-collection", [f"{path}: source artifact contains problems"]
        )
    if value.get("worker_count") != 16:
        raise T065CaseD("source-collection", [f"{path}: source worker count is not 16"])
    if value.get("action_space") != frozen_action_space().to_dict():
        raise T065CaseD("source-collection", [f"{path}: action space is not frozen"])
    battle_provenance = value.get("battle_controller_provenance")
    if battle_provenance != frozen_battle_provenance():
        raise T065CaseD(
            "source-collection", [f"{path}: battle provenance is not frozen"]
        )
    if value.get("simulator_identity") != lightspeed_source_identity_dict():
        raise T065CaseD(
            "source-collection", [f"{path}: simulator identity is not pinned"]
        )
    shard_specs = value.get("shard_specs")
    if value.get("shard_count") != 16 or not isinstance(shard_specs, list):
        raise T065CaseD(
            "source-collection", [f"{path}: source shard evidence is incomplete"]
        )
    if len(shard_specs) != 16 or any(
        not isinstance(spec, Mapping)
        or spec.get("shard_index") != index
        or spec.get("seed_start") != 650001 + 16 * index
        or spec.get("seed_end") != 650016 + 16 * index
        or spec.get("seed_count") != 16
        or spec.get("worker_count") != 16
        or spec.get("requested_seed_count") != 16
        or spec.get("terminal_run_count") != 16
        or spec.get("truncated_run_count") != 0
        or spec.get("failed_run_count") != 0
        or spec.get("problems")
        for index, spec in enumerate(shard_specs)
    ):
        raise T065CaseD(
            "source-collection", [f"{path}: source shard ranges/evidence are invalid"]
        )
    rows = value.get("records")
    summaries = value.get("run_summaries")
    if not isinstance(rows, list) or not isinstance(summaries, list):
        raise T065CaseD("source-collection", [f"{path}: source records are missing"])
    if len(summaries) != 256:
        raise T065CaseD(
            "source-collection", [f"{path}: source run summaries are incomplete"]
        )
    summary_seeds = set()
    for summary in summaries:
        if not isinstance(summary, Mapping):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary is malformed"]
            )
        seed = summary.get("simulator_seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary seed is invalid"]
            )
        summary_seeds.add(seed)
        if not summary.get("terminal") or summary.get("problems"):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary is not valid"]
            )
    for row in rows:
        if not isinstance(row, Mapping) or row.get("source_arm") != arm:
            raise T065CaseD(
                "source-collection", [f"{path}: source record arm is invalid"]
            )
    if summary_seeds != expected_seeds:
        raise T065CaseD(
            "source-collection", [f"{path}: source summary seed set is incomplete"]
        )
    return str(arm)


def _source_report_is_complete(report: Any) -> bool:
    return bool(
        not report.problems
        and report.requested_seed_count > 0
        and report.terminal_run_count == report.requested_seed_count
        and report.truncated_run_count == 0
        and report.failed_run_count == 0
    )


def _stage_name(command: str) -> str:
    return {
        "preflight": "stage0-preflight",
        "collect": "stage1-source-collection",
        "select": "stage1-source-selection",
        "target": "stage2-counterfactual-targets",
        "train": "stage4-training",
        "evaluate": "stage5",
    }.get(command, command)


def _decision_report_path(args: argparse.Namespace) -> Path:
    report_path = getattr(args, "decision_report", None)
    if isinstance(report_path, Path):
        return report_path
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path):
        return output_path.with_name(
            f"{output_path.stem}.t065-terminal-decision-report.json"
        )
    raise ValueError("T065 Case D requires an explicit output or decision-report path")


def _retention_manifest_path(args: argparse.Namespace) -> Path:
    manifest_path = getattr(args, "retention_manifest", None)
    if isinstance(manifest_path, Path):
        return manifest_path
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path):
        return output_path.with_name(f"{output_path.stem}.t065-retention-manifest.json")
    raise ValueError("T065 retention manifest requires an explicit output path")


def _file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _preceding_artifact_paths(args: argparse.Namespace) -> dict[str, Path]:
    paths: dict[str, Path] = {}

    def add(role: str, path: Any) -> None:
        if isinstance(path, Path) and path.is_file():
            paths.setdefault(role, path)

    if args.command == "preflight":
        add("stage0_preflight", getattr(args, "output", None))
    else:
        add("stage0_preflight", getattr(args, "preflight", None))
    if args.command == "select":
        for index, path in enumerate(args.input):
            add(f"source_arm_{index}", path)
    elif args.command == "target":
        add("selected_states", args.states)
    elif args.command in {"train", "evaluate"}:
        add("target_table", args.target_table)
    if args.command == "evaluate":
        for model_seed in (653001, 653002):
            add(
                f"checkpoint_{model_seed}",
                args.checkpoint_directory / f"model-{model_seed}.pt",
            )
    return paths


def _artifact_identities(paths: Mapping[str, Path]) -> dict[str, Any]:
    """Return identities only for artifacts that actually exist."""

    return {
        role: _file_identity(path) for role, path in paths.items() if path.is_file()
    }


def _manifest_artifact_paths(
    args: argparse.Namespace,
    *,
    decision_path: Path | None = None,
    case_d: bool = False,
) -> dict[str, Path]:
    if case_d:
        paths = _preceding_artifact_paths(args)
    else:
        paths = _preceding_artifact_paths(args)
        output_path = getattr(args, "output", None)
        if isinstance(output_path, Path) and output_path.is_file():
            paths["current_output"] = output_path
        if args.command == "select":
            selection_path = args.manifest or Path(f"{args.output}.manifest.json")
            if selection_path.is_file():
                paths["source_selection_manifest"] = selection_path
        if args.command == "train":
            for model_seed in (653001, 653002):
                checkpoint = args.checkpoint_directory / f"model-{model_seed}.pt"
                if checkpoint.is_file():
                    paths[f"checkpoint_{model_seed}"] = checkpoint
    if decision_path is not None and decision_path.is_file():
        paths["terminal_decision_report"] = decision_path
    return paths


def _regeneration_command(args: argparse.Namespace) -> str:
    command = [
        "python",
        "-m",
        "sts_combat_rl.commands.non_combat_learning",
        *(sys.argv[1:] if sys.argv[1:] else [args.command]),
    ]
    return shlex.join(command)


def _write_workflow_manifest(
    args: argparse.Namespace,
    *,
    stage: str,
    decision_path: Path | None = None,
    case_d: bool = False,
    failure: T065CaseD | None = None,
    terminal: bool = False,
    terminal_case: str | None = None,
) -> dict[str, Any]:
    artifacts = _manifest_artifact_paths(
        args, decision_path=decision_path, case_d=case_d
    )
    evidence: dict[str, Any] = {
        "status": "case_d" if case_d else "completed",
        "stage": stage,
        "command": _regeneration_command(args),
        "artifact_roles": sorted(artifacts),
        "terminal": terminal,
    }
    if terminal_case is not None:
        evidence["terminal_case"] = terminal_case
    if failure is not None:
        evidence.update(
            {
                "failure_ids": list(failure.failure_ids or failure.problems),
                "failure_counts": dict(failure.failure_counts),
                "downstream_skipped": failure.to_decision_report()[
                    "downstream_skipped"
                ],
                "no_replacement": True,
            }
        )
    manifest = write_t065_manifest(
        _retention_manifest_path(args),
        approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
        simulator_identity=(
            failure.simulator_identity
            if failure is not None and failure.simulator_identity
            else lightspeed_source_identity_dict()
        ),
        artifacts=artifacts,
        regeneration_commands=(_regeneration_command(args),),
        stage_evidence={stage: evidence},
    )
    print(f"T065 retention manifest: {_retention_manifest_path(args)}", file=sys.stderr)
    return manifest


def _handle_case_d(args: argparse.Namespace, failure: T065CaseD) -> None:
    failure.preceding_stage_manifests.update(
        _artifact_identities(_preceding_artifact_paths(args))
    )
    decision_path = _decision_report_path(args)
    write_t065_terminal_decision_report(
        decision_path,
        failure,
        simulator_identity=(
            failure.simulator_identity or lightspeed_source_identity_dict()
        ),
    )
    _write_workflow_manifest(
        args,
        stage=failure.stage,
        decision_path=decision_path,
        case_d=True,
        failure=failure,
        terminal=True,
        terminal_case="D",
    )
    print(f"T065 Case D decision report: {decision_path}", file=sys.stderr)


def _require_preflight(args: argparse.Namespace) -> dict[str, Any]:
    path = getattr(args, "preflight", None)
    if not isinstance(path, Path):
        raise T065CaseD(
            "stage0-preflight",
            ["workflow command did not receive an explicit --preflight artifact"],
            failure_ids=("preflight:missing-argument",),
            failure_counts={"missing_preflight": 1},
        )
    return validate_t065_preflight(path)


def _require_frozen_simulator_args(args: argparse.Namespace) -> None:
    if args.sim_seed != 1 or args.ascension != 20:
        raise ValueError("T065 simulator configuration is frozen at seed=1, A20")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":  # pragma: no cover - exercised by command smoke
    raise SystemExit(main())
