"""Thin command surface for the staged T089 workflow.

The command only parses/routes and writes compact reports.  Simulator target
generation and fresh evaluation require explicit Python adapter factories and
are intentionally not started by this module's path-only operations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.non_combat_learning import (
    read_source_states,
    read_target_table,
)
from sts_combat_rl.sim.t089_non_combat_policy import (
    T089_APPROVED_SPEC_COMMIT,
    T089_NATIVE_COMMIT,
    T089_NATIVE_REF,
    T089_NATIVE_REPOSITORY,
    T089_TASK_ID,
    T089ExperimentConfig,
    T089Incomplete,
    build_t089_fresh_report,
    build_t089_heldout_gate,
    load_t089_checkpoint,
    select_t089_validation_checkpoint,
    t089_artifact_identity,
    t089_model_input_contract,
    t089_terminal_report,
    train_t089_model_seeds,
    validate_t089_revalidation_rows,
    validate_t089_selected_cohort,
    validate_t089_target_table,
)

T089_OPERATIONS = (
    "preflight",
    "revalidate",
    "target",
    "train",
    "heldout",
    "fresh",
    "finalize",
)


def _json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t089_non_combat_policy",
        description="T089 staged frozen-Search Non-Combat policy workflow",
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    preflight = subparsers.add_parser(
        "preflight", help="write cheap frozen-contract readiness"
    )
    preflight.add_argument("--output", type=Path, required=True)

    revalidate = subparsers.add_parser(
        "revalidate", help="validate current-native 320-state evidence"
    )
    revalidate.add_argument("--states", type=Path, required=True)
    revalidate.add_argument("--rows", type=Path, required=True)
    revalidate.add_argument("--output", type=Path, required=True)

    target = subparsers.add_parser(
        "target", help="declare the explicit target-generation boundary"
    )
    target.add_argument("--output", type=Path, required=True)
    target.add_argument("--revalidation", type=Path, required=True)
    target.add_argument("--allow-simulator", action="store_true")

    train = subparsers.add_parser("train", help="train the exact two T089 model seeds")
    train.add_argument("--states", type=Path, required=True)
    train.add_argument("--target-table", type=Path, required=True)
    train.add_argument("--checkpoint-directory", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)

    heldout = subparsers.add_parser(
        "heldout", help="evaluate the frozen held-out local gate"
    )
    heldout.add_argument("--target-table", type=Path, required=True)
    heldout.add_argument("--checkpoint", type=Path, action="append", required=True)
    heldout.add_argument("--output", type=Path, required=True)

    fresh = subparsers.add_parser(
        "fresh", help="reduce an already-authorized paired fresh-run artifact"
    )
    fresh.add_argument("--baseline", type=Path, required=True)
    fresh.add_argument("--candidate", type=Path, required=True)
    fresh.add_argument("--output", type=Path, required=True)

    finalize = subparsers.add_parser("finalize", help="write one terminal T089 report")
    finalize.add_argument("--classification", required=True)
    finalize.add_argument("--heldout", type=Path)
    finalize.add_argument("--fresh", type=Path)
    finalize.add_argument("--reason")
    finalize.add_argument("--output", type=Path, required=True)
    return parser


def _run_preflight(args: argparse.Namespace) -> int:
    report = {
        "schema_id": "t089-input-eligibility-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "approved_spec_commit": T089_APPROVED_SPEC_COMMIT,
        "publication_base": "6b739ee3f9b4bbd113aac141c755401d2a865252",
        "native_identity": {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
        "model_input": t089_model_input_contract(),
        "config": T089ExperimentConfig().to_dict(),
        "historical_targets_reused": False,
        "fresh_target_generation_authorized": False,
    }
    _write(args.output, report)
    return 0


def _run_revalidate(args: argparse.Namespace) -> int:
    states = read_source_states(args.states)
    validate_t089_selected_cohort(states)
    rows = _json(args.rows)
    if not isinstance(rows, list):
        raise TypeError("revalidation rows must be a JSON array")
    report = validate_t089_revalidation_rows(
        rows,
        states,
        native_identity={
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
    )
    _write(args.output, report)
    return 0


def _run_target(args: argparse.Namespace) -> int:
    if args.allow_simulator:
        raise T089Incomplete(
            "path-only command cannot construct an adapter factory; target execution "
            "requires an explicitly reviewed Python workflow"
        )
    raise T089Incomplete(
        "T089 target generation is separately authorized and is not started by this command"
    )


def _run_train(args: argparse.Namespace) -> int:
    states = read_source_states(args.states)
    table = read_target_table(
        args.target_table,
        expected_task_id=T089_TASK_ID,
        expected_approved_spec_commit=T089_APPROVED_SPEC_COMMIT,
        expected_frozen_config=T089ExperimentConfig().to_dict(),
        expected_continuation_seed_map=T089ExperimentConfig().to_dict()[
            "continuation_seeds"
        ],
    )
    validate_t089_target_table(table)
    source_identity = dict(table.source_artifact_identity)
    if not source_identity:
        raise T089Incomplete("T089 training source artifact identity is missing")
    target_identity = t089_artifact_identity(
        args.target_table,
        role="target_table",
        repository_root=args.target_table.parents[2],
    )
    target_identity["record_count"] = len(table.targets)
    runs = train_t089_model_seeds(
        states=states,
        targets=table.targets,
        source_artifact_identity=source_identity,
        target_artifact_identity=target_identity,
        checkpoint_directory=args.checkpoint_directory,
    )
    selected = select_t089_validation_checkpoint(runs)
    checkpoints = [
        t089_artifact_identity(
            args.checkpoint_directory / f"model-{run.model_seed}.pt",
            role=f"checkpoint_{run.model_seed}",
            repository_root=args.checkpoint_directory.parents[2],
        )
        for run in runs
    ]
    report = {
        "schema_id": "t089-validation-selection-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "model_seeds": [run.model_seed for run in runs],
        "validation_mae": [run.validation_mae for run in runs],
        "selected_model_seed": selected.model_seed,
        "selected_checkpoint": next(
            item
            for item in checkpoints
            if item["role"] == f"checkpoint_{selected.model_seed}"
        ),
        "checkpoints": checkpoints,
        "training_steps": 1500,
        "torch_threads": 1,
    }
    _write(args.output, report)
    return 0


def _run_heldout(args: argparse.Namespace) -> int:
    table = read_target_table(
        args.target_table,
        expected_task_id=T089_TASK_ID,
        expected_approved_spec_commit=T089_APPROVED_SPEC_COMMIT,
        expected_frozen_config=T089ExperimentConfig().to_dict(),
        expected_continuation_seed_map=T089ExperimentConfig().to_dict()[
            "continuation_seeds"
        ],
    )
    if len(args.checkpoint) != 2:
        raise ValueError("heldout gate requires exactly two checkpoints")
    runs = tuple(load_t089_checkpoint(path) for path in args.checkpoint)
    report = build_t089_heldout_gate(runs, table)
    _write(args.output, report)
    return 0 if report["passed"] else 1


def _run_fresh(args: argparse.Namespace) -> int:
    baseline = _json(args.baseline)
    candidate = _json(args.candidate)
    if not isinstance(baseline, list) or not isinstance(candidate, list):
        raise TypeError("fresh arm artifacts must be JSON arrays")
    report = build_t089_fresh_report(baseline, candidate)
    _write(args.output, report)
    return (
        0
        if report["classification"] == "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED"
        else 1
    )


def _run_finalize(args: argparse.Namespace) -> int:
    heldout = _json(args.heldout) if args.heldout else None
    fresh = _json(args.fresh) if args.fresh else None
    _write(
        args.output,
        t089_terminal_report(
            args.classification,
            heldout=heldout,
            fresh=fresh,
            reason=args.reason,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return {
            "preflight": _run_preflight,
            "revalidate": _run_revalidate,
            "target": _run_target,
            "train": _run_train,
            "heldout": _run_heldout,
            "fresh": _run_fresh,
            "finalize": _run_finalize,
        }[args.operation](args)
    except (OSError, TypeError, ValueError, T089Incomplete) as exc:
        print(f"T089 command failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
