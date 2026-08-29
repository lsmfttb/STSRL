"""Neutral command surface for T065 learning and T075 acceptance stages.

The bounded T075 operations live below a nested command group so the legacy
T065 command meanings remain unchanged.  Long-running collection and
evaluation are explicit subcommands so their artifact paths, seed ranges, and
stage boundaries remain visible in the command itself.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.non_combat_acceptance import (
    T075OperationalError,
    T075StageClassificationError,
    canonical_json_document,
    finalize_t075,
    reconstruct_t075_state,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_eval as commit_t075_eval,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_gate as commit_t075_gate,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_preflight as commit_t075_preflight,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_selection as commit_t075_selection,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_target as commit_t075_target,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_train as commit_t075_train,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    run_t075_validate_reuse as commit_t075_validate_reuse,
)
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065_EXPERIMENT_SCHEMA_VERSION,
    T065_LIGHTSPEED_BUILD_PYTHONPATH,
    T065_SOURCE_SEED_RANGE,
    T065_TRAINING_INTERPRETER,
    T065CaseD,
    T065ExperimentConfig,
    T065SourceState,
    build_stage5_report,
    build_t065_preflight_report,
    canonical_source_selection_key,
    collect_source_arm,
    collect_source_arm_sharded_to_path,
    file_sha256,
    frozen_action_space,
    frozen_battle_provenance,
    generate_counterfactual_targets,
    generate_counterfactual_targets_sharded,
    load_non_combat_checkpoint,
    read_source_states,
    read_target_table,
    run_stage6_experiment,
    select_source_candidates,
    terminal_decision_report,
    train_frozen_model_seeds,
    validate_t065_preflight,
    write_source_selection_manifest,
    write_source_states,
    write_t065_manifest,
    write_t065_terminal_decision_report,
    write_target_table,
)

T075_COMMAND_OPERATIONS = (
    "preflight",
    "validate-reuse",
    "select",
    "target",
    "train",
    "gate",
    "eval",
    "finalize",
)
run_t075_preflight = commit_t075_preflight
run_t075_validate_reuse = commit_t075_validate_reuse
run_t075_selection = commit_t075_selection
run_t075_target = commit_t075_target
run_t075_train = commit_t075_train
run_t075_gate = commit_t075_gate
run_t075_eval = commit_t075_eval


def _add_t075_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--run-head", required=True)


def _add_t075_validity_arguments(
    parser: argparse.ArgumentParser, *, failure_codes: tuple[str, ...]
) -> None:
    validity = parser.add_mutually_exclusive_group(required=True)
    validity.add_argument("--valid", action="store_true")
    validity.add_argument("--invalid", action="store_true")
    parser.add_argument("--failure-code", choices=failure_codes)


def _add_t075_result_arguments(
    parser: argparse.ArgumentParser, *, failure_code: str
) -> None:
    _add_t075_validity_arguments(parser, failure_codes=(failure_code,))
    result = parser.add_mutually_exclusive_group()
    result.add_argument("--passed", action="store_true")
    result.add_argument("--failed", action="store_true")


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
    collect.add_argument("--preceding-manifest", type=Path, action="append")
    collect.add_argument("--retention-manifest", type=Path)

    select = subparsers.add_parser(
        "select", help="deduplicate and select the frozen cohort"
    )
    select.add_argument("--input", type=Path, action="append", required=True)
    select.add_argument("--output", type=Path, required=True)
    select.add_argument("--manifest", type=Path)
    select.add_argument("--decision-report", type=Path)
    select.add_argument("--preflight", type=Path, required=True)
    select.add_argument("--preceding-manifest", type=Path, action="append")
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
    target.add_argument("--preceding-manifest", type=Path, action="append")
    target.add_argument("--retention-manifest", type=Path)

    train = subparsers.add_parser("train", help="train the two frozen model seeds")
    train.add_argument("--target-table", type=Path, required=True)
    train.add_argument("--checkpoint-directory", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--preflight", type=Path, required=True)
    train.add_argument("--preceding-manifest", type=Path, action="append")
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
    evaluate.add_argument("--preceding-manifest", type=Path, action="append")
    evaluate.add_argument("--decision-report", type=Path)
    evaluate.add_argument("--retention-manifest", type=Path)

    t075 = subparsers.add_parser(
        "t075",
        help="run explicit T075 acceptance stages on the durable neutral surface",
    )
    t075_operations = t075.add_subparsers(dest="t075_operation", required=True)

    t075_preflight = t075_operations.add_parser(
        "preflight", help="commit the T075 preflight audit"
    )
    _add_t075_common_arguments(t075_preflight)
    t075_preflight.add_argument("--audit", type=Path)
    _add_t075_validity_arguments(t075_preflight, failure_codes=("PREFLIGHT_INVALID",))

    t075_reuse = t075_operations.add_parser(
        "validate-reuse", help="commit validation of the two frozen T065 sources"
    )
    _add_t075_common_arguments(t075_reuse)
    t075_reuse.add_argument("--audit", type=Path)
    _add_t075_validity_arguments(t075_reuse, failure_codes=("SOURCE_REUSE_INVALID",))

    t075_select = t075_operations.add_parser(
        "select", help="commit global replay ownership and selected states"
    )
    _add_t075_common_arguments(t075_select)
    t075_select.add_argument("--ownership-audit", type=Path)
    t075_select.add_argument("--selected-states", type=Path)
    _add_t075_validity_arguments(
        t075_select,
        failure_codes=(
            "SELECTION_MEMBER_ORDER_TIE",
            "SELECTION_OWNER_QUOTA_SHORTAGE",
            "SELECTION_REPLAY_INVALID",
        ),
    )

    t075_target = t075_operations.add_parser(
        "target", help="commit the inherited T065 target table"
    )
    _add_t075_common_arguments(t075_target)
    t075_target.add_argument("--target-table", type=Path)
    _add_t075_validity_arguments(t075_target, failure_codes=("TARGET_INVALID",))

    t075_train = t075_operations.add_parser(
        "train", help="commit the two inherited T065 checkpoints and selection"
    )
    _add_t075_common_arguments(t075_train)
    t075_train.add_argument("--checkpoint-653001", type=Path)
    t075_train.add_argument("--checkpoint-653002", type=Path)
    t075_train.add_argument("--training-selection", type=Path)
    _add_t075_validity_arguments(t075_train, failure_codes=("TRAIN_INVALID",))

    t075_gate = t075_operations.add_parser(
        "gate", help="commit valid Stage-5 evidence or a Stage-5 evidence failure"
    )
    _add_t075_common_arguments(t075_gate)
    t075_gate.add_argument("--stage5-report", type=Path)
    _add_t075_result_arguments(t075_gate, failure_code="GATE_EVIDENCE_INVALID")

    t075_eval = t075_operations.add_parser(
        "eval", help="commit valid Stage-6 evidence or a Stage-6 evidence failure"
    )
    _add_t075_common_arguments(t075_eval)
    t075_eval.add_argument("--stage6-report", type=Path)
    _add_t075_result_arguments(t075_eval, failure_code="EVAL_EVIDENCE_INVALID")

    t075_finalize = t075_operations.add_parser(
        "finalize", help="materialize the terminal report and final retention record"
    )
    _add_t075_common_arguments(t075_finalize)
    t075_finalize.add_argument("--entry-metadata", type=Path, required=True)
    t075_finalize.add_argument("--retention-reason", required=True)
    t075_finalize.add_argument("--downstream-consumer", action="append", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args._command_argv = tuple(argv if argv is not None else sys.argv[1:])
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
        if args.command == "t075":
            return _run_t075(args)
    except (T075OperationalError, T075StageClassificationError) as exc:
        print(f"T075 command failed: {exc}", file=sys.stderr)
        return 1
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


def _read_t075_mapping(path: Path, label: str) -> Mapping[str, Any]:
    try:
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T075OperationalError(f"{label} is not readable canonical JSON") from exc
    if not isinstance(value, Mapping) or canonical_json_document(value) != payload:
        raise T075OperationalError(f"{label} is not a canonical JSON object")
    return value


def _read_t075_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise T075OperationalError(f"{label} is not readable") from exc


def _required_t075_path(path: Path | None, label: str) -> Path:
    if path is None:
        raise T075OperationalError(f"T075 {label} path is required")
    return path


def _t075_git_output(repository_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise T075OperationalError(
            f"repository_root is not a usable git checkout: {repository_root}"
        ) from exc
    return result.stdout.strip()


def _validate_t075_checkout(repository_root: Path, run_head: str) -> None:
    repository_root = repository_root.resolve()
    if not repository_root.is_dir():
        raise T075OperationalError(
            f"repository_root is not a directory: {repository_root}"
        )
    checkout_root = Path(
        _t075_git_output(repository_root, "rev-parse", "--show-toplevel")
    ).resolve()
    if checkout_root != repository_root:
        raise T075OperationalError(
            "repository_root must be the top-level directory of the git checkout"
        )
    status = _t075_git_output(repository_root, "status", "--porcelain")
    if status:
        raise T075OperationalError("T075 commands require a clean git checkout")
    actual_head = _t075_git_output(repository_root, "rev-parse", "HEAD")
    if actual_head != run_head:
        raise T075OperationalError(
            f"T075 run_head does not match checkout HEAD: {run_head} != {actual_head}"
        )


def _validate_t075_input_paths(
    repository_root: Path,
    paths: tuple[tuple[str, Path | None], ...],
) -> None:
    for label, path in paths:
        if path is None:
            continue
        resolved_path = path.resolve()
        if repository_root not in resolved_path.parents:
            raise T075OperationalError(
                f"T075 {label} path must be within repository_root: {path}"
            )


def run_t075_operation(
    operation: str,
    *,
    repository_root: Path,
    run_head: str,
    audit: Path | None = None,
    ownership_audit: Path | None = None,
    selected_states: Path | None = None,
    target_table: Path | None = None,
    checkpoint_653001: Path | None = None,
    checkpoint_653002: Path | None = None,
    training_selection: Path | None = None,
    stage5_report: Path | None = None,
    stage6_report: Path | None = None,
    entry_metadata: Path | None = None,
    retention_reason: str | None = None,
    downstream_consumers: tuple[str, ...] = (),
    valid: bool = True,
    passed: bool | None = None,
    failure_code: str | None = None,
) -> Any:
    """Route one explicit T075 operation to the public acceptance adapters."""

    if operation not in T075_COMMAND_OPERATIONS:
        raise T075OperationalError(f"unsupported T075 operation: {operation!r}")
    root = Path(repository_root).resolve()
    _validate_t075_checkout(root, run_head)
    _validate_t075_input_paths(
        root,
        (
            ("audit", audit),
            ("ownership-audit", ownership_audit),
            ("selected-states", selected_states),
            ("target-table", target_table),
            ("checkpoint-653001", checkpoint_653001),
            ("checkpoint-653002", checkpoint_653002),
            ("training-selection", training_selection),
            ("stage5-report", stage5_report),
            ("stage6-report", stage6_report),
            ("entry-metadata", entry_metadata),
        ),
    )
    state = reconstruct_t075_state(root, run_head)
    if operation == "preflight":
        return run_t075_preflight(
            state,
            _read_t075_mapping(_required_t075_path(audit, "audit"), "preflight audit")
            if valid
            else None,
            root,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "validate-reuse":
        return run_t075_validate_reuse(
            state,
            _read_t075_mapping(
                _required_t075_path(audit, "audit"), "source-reuse audit"
            )
            if valid
            else None,
            root,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "select":
        return run_t075_selection(
            state,
            _read_t075_mapping(
                _required_t075_path(ownership_audit, "ownership-audit"),
                "ownership audit",
            )
            if valid
            else None,
            _read_t075_bytes(
                _required_t075_path(selected_states, "selected-states"),
                "selected states",
            )
            if valid
            else None,
            root,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "target":
        if not valid and failure_code != "TARGET_INVALID":
            raise T075OperationalError(
                "invalid T075 target requires TARGET_INVALID failure code"
            )
        return run_t075_target(
            state,
            _read_t075_bytes(
                _required_t075_path(target_table, "target-table"), "target table"
            )
            if valid
            else None,
            root,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "train":
        return run_t075_train(
            state,
            (
                _read_t075_bytes(
                    _required_t075_path(checkpoint_653001, "checkpoint-653001"),
                    "checkpoint 653001",
                ),
                _read_t075_bytes(
                    _required_t075_path(checkpoint_653002, "checkpoint-653002"),
                    "checkpoint 653002",
                ),
            )
            if valid
            else None,
            _read_t075_mapping(
                _required_t075_path(training_selection, "training-selection"),
                "training-selection summary",
            )
            if valid
            else None,
            root,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "gate":
        if valid and passed is None:
            raise T075OperationalError("T075 gate result is required")
        if not valid and failure_code != "GATE_EVIDENCE_INVALID":
            raise T075OperationalError(
                "invalid T075 gate requires GATE_EVIDENCE_INVALID failure code"
            )
        return run_t075_gate(
            state,
            _read_t075_bytes(
                _required_t075_path(stage5_report, "stage5-report"),
                "Stage-5 report",
            )
            if valid
            else None,
            root,
            passed=bool(passed) if valid else False,
            valid=valid,
            failure_code=failure_code,
        )
    if operation == "eval":
        if valid and passed is None:
            raise T075OperationalError("T075 eval result is required")
        if not valid and failure_code != "EVAL_EVIDENCE_INVALID":
            raise T075OperationalError(
                "invalid T075 eval requires EVAL_EVIDENCE_INVALID failure code"
            )
        return run_t075_eval(
            state,
            _read_t075_bytes(
                _required_t075_path(stage6_report, "stage6-report"),
                "Stage-6 report",
            )
            if valid
            else None,
            root,
            passed=bool(passed) if valid else False,
            valid=valid,
            failure_code=failure_code,
        )
    metadata_path = _required_t075_path(entry_metadata, "entry-metadata")
    if retention_reason is None or not retention_reason:
        raise T075OperationalError("T075 retention reason is required")
    if not downstream_consumers:
        raise T075OperationalError("T075 downstream consumer is required")
    return finalize_t075(
        state,
        root,
        entry_metadata=_read_t075_mapping(metadata_path, "retention entry metadata"),
        retention_reason=retention_reason,
        possible_downstream_consumers=downstream_consumers,
    )


def _run_t075(args: argparse.Namespace) -> int:
    operation = args.t075_operation
    result = run_t075_operation(
        operation,
        repository_root=args.repository_root,
        run_head=args.run_head,
        audit=getattr(args, "audit", None),
        ownership_audit=getattr(args, "ownership_audit", None),
        selected_states=getattr(args, "selected_states", None),
        target_table=getattr(args, "target_table", None),
        checkpoint_653001=getattr(args, "checkpoint_653001", None),
        checkpoint_653002=getattr(args, "checkpoint_653002", None),
        training_selection=getattr(args, "training_selection", None),
        stage5_report=getattr(args, "stage5_report", None),
        stage6_report=getattr(args, "stage6_report", None),
        entry_metadata=getattr(args, "entry_metadata", None),
        retention_reason=getattr(args, "retention_reason", None),
        downstream_consumers=tuple(getattr(args, "downstream_consumer", ()) or ()),
        valid=getattr(args, "valid", True),
        passed=(
            True
            if getattr(args, "passed", False)
            else False
            if getattr(args, "failed", False)
            else None
        ),
        failure_code=getattr(args, "failure_code", None),
    )
    if isinstance(result, tuple):
        print(f"T075 {operation} finalized", file=sys.stderr)
    else:
        print(
            f"T075 {operation} committed current_stage={result.current_stage} "
            f"terminal_case={result.terminal_case}",
            file=sys.stderr,
        )
    return 0


def _run_preflight(args: argparse.Namespace) -> int:
    _require_frozen_simulator_args(args)
    factory = None
    if args.simulator_runtime:
        factory = lambda: LightSpeedAdapter(
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
    _require_preceding_manifests(args)
    _require_frozen_simulator_args(args)
    seeds = tuple(range(args.seed_start, args.seed_end + 1))
    factory = lambda: LightSpeedAdapter(
        seed=args.sim_seed,
        ascension=args.ascension,
        player_class="IRONCLAD",
    )
    if (args.seed_start, args.seed_end) == T065_SOURCE_SEED_RANGE:
        report = collect_source_arm_sharded_to_path(
            factory,
            args.output,
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
    _require_preceding_manifests(args)
    if len(args.input) != 2:
        raise ValueError("T065 selection requires exactly two source-arm artifacts")
    source_artifacts = []
    observed_arms = set()
    simulator_identity: Mapping[str, Any] | None = None

    def candidate_stream() -> Iterator[_SourceSelectionLocator]:
        nonlocal simulator_identity
        for source_index, path in enumerate(args.input):
            reader = _SourceArmArtifactReader(path)
            for record_index, state in enumerate(reader.iter_states()):
                yield _SourceSelectionLocator.from_state(
                    state, source_index=source_index, record_index=record_index
                )
            arm = _validate_source_arm_metadata(
                reader.metadata, path, record_count=reader.record_count
            )
            if arm in observed_arms:
                raise ValueError(f"duplicate T065 source arm artifact: {arm}")
            observed_arms.add(arm)
            artifact_simulator_identity = reader.metadata.get("simulator_identity")
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
            source_artifacts.append(
                {
                    "arm": arm,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "size_bytes": path.stat().st_size,
                    "record_count": reader.record_count,
                }
            )

    selected_locators = select_source_candidates(candidate_stream())
    if observed_arms != {
        "stochastic_non_combat_v1",
        "expert_non_combat_v1",
    }:
        raise ValueError("T065 selection requires stochastic and expert source arms")
    desired = {
        (candidate.source_index, candidate.record_index): (digest, payload)
        for candidate, digest, payload in selected_locators
    }
    selected_states_by_locator: dict[tuple[int, int], T065SourceState] = {}
    for source_index, path in enumerate(args.input):
        reader = _SourceArmArtifactReader(path)
        for record_index, state in enumerate(reader.iter_states()):
            key = (source_index, record_index)
            expected = desired.get(key)
            if expected is not None:
                actual = canonical_source_selection_key(state)
                if actual != expected:
                    raise T065CaseD(
                        "source-selection",
                        [f"{path}: selected source record changed during selection"],
                    )
                selected_states_by_locator[key] = state
    for source_index, path in enumerate(args.input):
        expected_artifact = source_artifacts[source_index]
        try:
            actual_size = path.stat().st_size
            actual_sha256 = file_sha256(path)
        except OSError as exc:
            raise T065CaseD(
                "source-selection",
                [f"{path}: source artifact disappeared during selection"],
            ) from exc
        if (
            actual_size != expected_artifact["size_bytes"]
            or actual_sha256 != expected_artifact["sha256"]
        ):
            raise T065CaseD(
                "source-selection",
                [f"{path}: source artifact changed between selection passes"],
            )
    if len(selected_states_by_locator) != len(selected_locators):
        raise T065CaseD(
            "source-selection", ["selected source record locator is missing"]
        )
    selected = tuple(
        replace(
            selected_states_by_locator[
                (candidate.source_index, candidate.record_index)
            ],
            selected_state_index=index,
            selection_digest=digest,
            selection_canonical_json=payload.decode("utf-8"),
        )
        for index, (candidate, digest, payload) in enumerate(selected_locators)
    )
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
    _require_preceding_manifests(args)
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
        "size_bytes": args.states.stat().st_size,
        "record_count": len(states),
    }
    simulator_identity = lightspeed_source_identity_dict()
    factory = lambda: LightSpeedAdapter(
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
    _require_preceding_manifests(args)
    table = read_target_table(args.target_table)
    args.checkpoint_directory.mkdir(parents=True, exist_ok=True)
    runs = train_frozen_model_seeds(
        states=table.states,
        targets=table.targets,
        source_artifact_identity=table.source_artifact_identity,
        target_artifact_identity={
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
            "size_bytes": args.target_table.stat().st_size,
            "record_count": len(table.targets),
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
                "size_bytes": args.target_table.stat().st_size,
                "record_count": len(table.targets),
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
    _require_preceding_manifests(args)
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
            preceding_stage_manifests=_preceding_manifest_identities(args),
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
                preceding_stage_manifests=_preceding_manifest_identities(args),
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


class _StreamingJsonReader:
    """Decode one JSON value at a time from a bounded text buffer."""

    _CHUNK_SIZE = 1024 * 1024

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._decoder = json.JSONDecoder()
        self._buffer = ""
        self._eof = False

    def _read_more(self) -> bool:
        if self._eof:
            return False
        chunk = self._stream.read(self._CHUNK_SIZE)
        if chunk == "":
            self._eof = True
            return False
        self._buffer += chunk
        return True

    def _skip_whitespace(self) -> None:
        while True:
            self._buffer = self._buffer.lstrip()
            if self._buffer or self._eof:
                return
            self._read_more()

    def _consume(self, expected: str) -> None:
        self._skip_whitespace()
        while len(self._buffer) < len(expected) and self._read_more():
            pass
        if not self._buffer.startswith(expected):
            raise ValueError(f"expected JSON token {expected!r}")
        self._buffer = self._buffer[len(expected) :]

    def _consume_if(self, token: str) -> bool:
        self._skip_whitespace()
        while len(self._buffer) < len(token) and self._read_more():
            pass
        if not self._buffer.startswith(token):
            return False
        self._buffer = self._buffer[len(token) :]
        return True

    def value(self) -> Any:
        self._skip_whitespace()
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer)
            except json.JSONDecodeError:
                if not self._read_more():
                    raise
                continue
            if end == len(self._buffer) and not self._eof:
                self._read_more()
                continue
            self._buffer = self._buffer[end:]
            return value

    def array_values(self) -> Iterator[Any]:
        self._consume("[")
        if self._consume_if("]"):
            return
        while True:
            yield self.value()
            if self._consume_if("]"):
                return
            self._consume(",")

    def ensure_end(self) -> None:
        self._skip_whitespace()
        if self._buffer:
            raise ValueError("unexpected trailing JSON data")


@dataclass(frozen=True)
class _SourceSelectionLocator:
    """Compact first-pass candidate retained until full-state reread."""

    source_index: int
    record_index: int
    family: str
    split: str
    simulator_seed: int
    source_arm: str
    source_run_id: str
    source_step_index: int
    public_state_identity: str
    legal_action_identities: tuple[Mapping[str, Any], ...]
    action_trace: tuple[Mapping[str, Any], ...]
    terminal: bool

    @classmethod
    def from_state(
        cls, state: T065SourceState, *, source_index: int, record_index: int
    ) -> _SourceSelectionLocator:
        return cls(
            source_index=source_index,
            record_index=record_index,
            family=state.family,
            split=state.split,
            simulator_seed=state.simulator_seed,
            source_arm=state.source_arm,
            source_run_id=state.source_run_id,
            source_step_index=state.source_step_index,
            public_state_identity=state.public_state_identity,
            legal_action_identities=tuple(
                dict(identity) for identity in state.legal_action_identities
            ),
            action_trace=tuple(dict(item) for item in state.action_trace),
            terminal=state.terminal,
        )


class _SourceArmArtifactReader:
    """Stream source records while retaining only small source metadata."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.metadata: dict[str, Any] = {}
        self.record_count = 0

    def iter_states(self) -> Iterator[T065SourceState]:
        first_record_arm: str | None = None
        for row in self:
            if not isinstance(row, dict):
                raise ValueError(f"{self.path}: source row is not an object")
            state = T065SourceState.from_dict(row)
            if first_record_arm is None:
                first_record_arm = state.source_arm
            elif state.source_arm != first_record_arm:
                raise ValueError(f"{self.path}: source record arms are inconsistent")
            yield state
        if first_record_arm != self.metadata.get("arm"):
            raise ValueError(
                f"{self.path}: source record arm does not match artifact arm"
            )

    def __iter__(self) -> Iterator[Any]:
        seen_keys: set[str] = set()
        saw_records = False
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                reader = _StreamingJsonReader(stream)
                reader._consume("{")
                if reader._consume_if("}"):
                    raise ValueError("source artifact object is empty")
                while True:
                    key = reader.value()
                    if not isinstance(key, str):
                        raise ValueError("source artifact key is not a string")
                    if key in seen_keys:
                        raise ValueError(f"duplicate source artifact key {key!r}")
                    seen_keys.add(key)
                    reader._consume(":")
                    if key == "records":
                        saw_records = True
                        for row in reader.array_values():
                            self.record_count += 1
                            yield row
                    else:
                        self.metadata[key] = reader.value()
                    if reader._consume_if("}"):
                        break
                    reader._consume(",")
                reader.ensure_end()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"{self.path}: invalid source artifact JSON: {exc}"
            ) from exc
        if not saw_records:
            raise ValueError(f"{self.path}: source records are missing")
        _validate_source_arm_metadata(
            self.metadata, self.path, record_count=self.record_count
        )


def _iter_source_arm_states(path: Path) -> Iterator[T065SourceState]:
    reader = _SourceArmArtifactReader(path)
    yield from reader.iter_states()


def _validate_source_arm_metadata(
    value: Mapping[str, Any], path: Path, *, record_count: int
) -> str:
    expected_seeds = set(range(650001, 650257))
    if value.get("schema_id") != "t065-learned-non-combat-policy-v1":
        raise T065CaseD("source-collection", [f"{path}: source schema is unsupported"])
    if value.get("schema_version") != T065_EXPERIMENT_SCHEMA_VERSION:
        raise T065CaseD(
            "source-collection", [f"{path}: source schema version is unsupported"]
        )
    if value.get("frozen_config") != T065ExperimentConfig().to_dict():
        raise T065CaseD(
            "source-collection", [f"{path}: source frozen config is not frozen"]
        )
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
    if value.get("selected_candidate_count") != record_count:
        raise T065CaseD(
            "source-collection",
            [f"{path}: source candidate count does not match records"],
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
    summaries = value.get("run_summaries")
    if not isinstance(summaries, list):
        raise T065CaseD("source-collection", [f"{path}: source summaries are missing"])
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
        if (
            summary.get("source_arm") != arm
            or summary.get("source_run_id") != f"{arm}:{seed}"
            or not isinstance(summary.get("terminal"), bool)
            or summary.get("terminal") is not True
            or summary.get("problems")
        ):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary is not valid"]
            )
    if summary_seeds != expected_seeds:
        raise T065CaseD(
            "source-collection", [f"{path}: source summary seed set is incomplete"]
        )
    return str(arm)


def _validate_source_arm_artifact(value: Mapping[str, Any], path: Path) -> str:
    rows = value.get("records")
    if not isinstance(rows, list):
        raise T065CaseD("source-collection", [f"{path}: source records are missing"])
    arm = _validate_source_arm_metadata(value, path, record_count=len(rows))
    for row in rows:
        if not isinstance(row, Mapping) or row.get("source_arm") != arm:
            raise T065CaseD(
                "source-collection", [f"{path}: source record arm is invalid"]
            )
    return arm


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
    """Return ordinary input/current artifact paths, never manifest lineage."""

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


def _expected_preceding_stages(args: argparse.Namespace) -> tuple[str, ...]:
    return {
        "collect": ("stage0-preflight",),
        "select": (
            "stage0-preflight",
            "stage1-source-collection",
            "stage1-source-collection",
        ),
        "target": ("stage0-preflight", "stage1-source-selection"),
        "train": ("stage0-preflight", "stage2-counterfactual-targets"),
        "evaluate": (
            "stage0-preflight",
            "stage2-counterfactual-targets",
            "stage4-training",
        ),
    }[args.command]


def _read_retention_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: retention manifest cannot be read: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: retention manifest root must be an object")
    if value.get("schema_id") != "t065-retention-manifest-v1":
        raise ValueError(f"{path}: retention manifest schema is unsupported")
    if value.get("schema_version") != 1:
        raise ValueError(f"{path}: retention manifest schema version is unsupported")
    if value.get("task_id") != "T065":
        raise ValueError(f"{path}: retention manifest task id is invalid")
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        raise ValueError(f"{path}: retention manifest approved spec is invalid")
    artifacts = value.get("artifacts")
    evidence = value.get("stage_evidence")
    if not isinstance(artifacts, list) or not isinstance(evidence, Mapping):
        raise ValueError(f"{path}: retention manifest lineage fields are missing")
    if not evidence or any(not isinstance(item, Mapping) for item in evidence.values()):
        raise ValueError(f"{path}: retention manifest stage evidence is invalid")

    def validate_identity(role: str, identity: Mapping[str, Any]) -> None:
        artifact_path = identity.get("path")
        digest = identity.get("sha256")
        size = identity.get("size_bytes")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise ValueError(f"{path}: artifact {role} has an invalid path")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"{path}: artifact {role} has an invalid sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"{path}: artifact {role} has an invalid size_bytes")
        actual_path = Path(artifact_path)
        if not actual_path.is_file():
            raise ValueError(f"{path}: artifact {role} is missing: {artifact_path}")
        if file_sha256(actual_path) != digest:
            raise ValueError(f"{path}: artifact {role} sha256 does not match")
        if actual_path.stat().st_size != size:
            raise ValueError(f"{path}: artifact {role} size_bytes does not match")

    roles: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            raise ValueError(f"{path}: artifact entry {index} is not an object")
        role = artifact.get("role")
        if not isinstance(role, str) or not role or role in roles:
            raise ValueError(f"{path}: artifact entry {index} has an invalid role")
        validate_identity(role, artifact)
        if role.startswith("checkpoint_"):
            expected_seed = role.removeprefix("checkpoint_")
            identity = artifact.get("identity")
            if (
                not expected_seed.isdigit()
                or not isinstance(identity, Mapping)
                or identity.get("model_seed") != int(expected_seed)
            ):
                raise ValueError(f"{path}: artifact {role} seed identity is invalid")
        roles.add(role)
    for section_name in ("preceding_stage_manifests", "failed_stage_artifacts"):
        identities = value.get(section_name, {})
        if not isinstance(identities, Mapping):
            raise ValueError(f"{path}: {section_name} must be an object")
        for role, identity in identities.items():
            if (
                not isinstance(role, str)
                or not role
                or not isinstance(identity, Mapping)
            ):
                raise ValueError(f"{path}: {section_name} contains an invalid entry")
            validate_identity(role, identity)
    for stage, stage_value in evidence.items():
        if not isinstance(stage, str) or not stage:
            raise ValueError(f"{path}: stage evidence has an invalid stage")
        referenced_roles = stage_value.get("artifact_roles")
        if not isinstance(referenced_roles, list) or any(
            not isinstance(role, str) or role not in roles for role in referenced_roles
        ):
            raise ValueError(
                f"{path}: stage evidence {stage} references unknown artifact roles"
            )
    return value


def _manifest_contains_artifact(
    manifest: Mapping[str, Any],
    path: Path,
    *,
    expected_role: str | None = None,
    expected_seed: int | None = None,
) -> bool:
    if not path.is_file():
        return False
    expected_path = path.resolve()
    expected_hash = file_sha256(path)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        try:
            artifact_path = Path(str(artifact["path"])).resolve()
        except (KeyError, OSError, ValueError):
            continue
        if (
            artifact_path == expected_path
            and artifact.get("sha256") == expected_hash
            and artifact.get("schema_id") in {None, "t065-retention-manifest-v1"}
            and (expected_role is None or artifact.get("role") == expected_role)
        ):
            if expected_seed is not None:
                identity = artifact.get("identity")
                if (
                    artifact.get("role") != f"checkpoint_{expected_seed}"
                    or not isinstance(identity, Mapping)
                    or identity.get("model_seed") != expected_seed
                ):
                    continue
            return True
    return False


def _manifest_descriptor(path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "schema_id": manifest["schema_id"],
        "schema_version": manifest["schema_version"],
        "completed_stages": sorted(str(stage) for stage in manifest["stage_evidence"]),
    }


def _require_preceding_manifests(args: argparse.Namespace) -> None:
    expected_stages = _expected_preceding_stages(args)
    supplied = tuple(getattr(args, "preceding_manifest", None) or ())
    if len(supplied) != len(expected_stages):
        raise T065CaseD(
            _stage_name(args.command),
            [
                f"expected {len(expected_stages)} explicit preceding retention "
                f"manifests, received {len(supplied)}"
            ],
            failure_ids=(f"preceding-manifest-count:{len(supplied)}",),
            failure_counts={
                "required_manifests": len(expected_stages),
                "supplied_manifests": len(supplied),
            },
        )
    manifests: list[tuple[Path, Mapping[str, Any], str]] = []
    problems: list[str] = []
    for index, (path, expected_stage) in enumerate(zip(supplied, expected_stages)):
        try:
            manifest = _read_retention_manifest(path)
            evidence = manifest["stage_evidence"]
            stage_evidence = evidence.get(expected_stage)
            if (
                not isinstance(stage_evidence, Mapping)
                or stage_evidence.get("status") != "completed"
            ):
                raise ValueError(
                    f"{path}: completed evidence for {expected_stage} is missing"
                )
            manifests.append((path, manifest, expected_stage))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"preceding manifest {index}: {exc}")
    if problems:
        args._preceding_manifest_paths = tuple(
            path for path, _manifest, _stage in manifests
        )
        args._preceding_manifest_identities = {
            (
                "stage1_source_collection_" + str(index - 1)
                if stage == "stage1-source-collection"
                else stage.replace("-", "_")
            ): _manifest_descriptor(path, manifest)
            for index, (path, manifest, stage) in enumerate(manifests)
        }
        raise T065CaseD(
            _stage_name(args.command),
            problems,
            failure_ids=tuple(
                f"preceding-manifest:{index}" for index in range(len(problems))
            ),
            failure_counts={"invalid_preceding_manifests": len(problems)},
        )

    relation_paths: list[Path | tuple[Path, ...] | None] = [None] * len(manifests)
    if args.command == "collect":
        relation_paths[0] = args.preflight
    elif args.command == "select":
        relation_paths[0] = args.preflight
        relation_paths[1:] = list(args.input)
    elif args.command == "target":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.states
    elif args.command == "train":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.target_table
    elif args.command == "evaluate":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.target_table
        relation_paths[2] = tuple(
            args.checkpoint_directory / f"model-{seed}.pt" for seed in (653001, 653002)
        )
    relation_problems = []
    for index, ((path, manifest, _stage), relation_path) in enumerate(
        zip(manifests, relation_paths)
    ):
        paths = (
            relation_path
            if isinstance(relation_path, tuple)
            else (relation_path,)
            if relation_path is not None
            else ()
        )
        for required_path in paths:
            expected_seed = (
                int(required_path.stem.removeprefix("model-"))
                if args.command == "evaluate"
                and required_path.name.startswith("model-")
                else None
            )
            if not _manifest_contains_artifact(
                manifest,
                required_path,
                expected_role=(
                    f"checkpoint_{expected_seed}" if expected_seed is not None else None
                ),
                expected_seed=expected_seed,
            ):
                relation_problems.append(
                    f"preceding manifest {index} does not contain the exact "
                    f"path/hash/size/seed identity for {required_path}"
                )
    if relation_problems:
        raise T065CaseD(
            _stage_name(args.command),
            relation_problems,
            failure_ids=tuple(
                f"preceding-manifest-artifact:{index}"
                for index in range(len(relation_problems))
            ),
            failure_counts={"manifest_artifact_mismatches": len(relation_problems)},
        )

    args._preceding_manifest_paths = tuple(
        path for path, _manifest, _stage in manifests
    )
    args._preceding_manifest_identities = {
        (
            "stage1_source_collection_" + str(index - 1)
            if stage == "stage1-source-collection"
            else stage.replace("-", "_")
        ): _manifest_descriptor(path, manifest)
        for index, (path, manifest, stage) in enumerate(manifests)
    }


def _preceding_manifest_identities(args: argparse.Namespace) -> dict[str, Any]:
    return dict(getattr(args, "_preceding_manifest_identities", {}))


def _failed_stage_artifact_paths(
    args: argparse.Namespace, failure: T065CaseD
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if failure.stage == "stage0-preflight":
        candidate = (
            args.output
            if args.command == "preflight"
            else getattr(args, "preflight", None)
        )
        if isinstance(candidate, Path) and candidate.is_file():
            paths["failed_preflight_artifact"] = candidate
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path) and output_path.is_file():
        paths["failed_current_artifact"] = output_path
    return paths


def _target_src_path() -> Path:
    return Path(__file__).resolve().parents[2]


def _wsl_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        return f"/mnt/{value[0].lower()}{value[2:]}"
    return value


def _manifest_artifact_paths(
    args: argparse.Namespace,
    *,
    decision_path: Path | None = None,
    case_d: bool = False,
    failure: T065CaseD | None = None,
) -> dict[str, Path]:
    if case_d:
        paths = _failed_stage_artifact_paths(args, failure or T065CaseD("unknown", ()))
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
    command_args = _canonical_command_args(args)
    rendered: list[str] = []
    for token in command_args:
        if isinstance(token, str) and ("\\" in token or ":" in token):
            rendered.append(_wsl_path(Path(token)))
        else:
            rendered.append(str(token))
    shard_count = {
        "collect": 16,
        "select": 0,
        "target": 16,
        "train": 0,
        "evaluate": 16,
        "preflight": 1,
    }[args.command]
    worker_count = 16 if shard_count else 1
    seed_range = {
        "collect": f"{getattr(args, 'seed_start', T065_SOURCE_SEED_RANGE[0])}.."
        f"{getattr(args, 'seed_end', T065_SOURCE_SEED_RANGE[1])}",
        "select": "source-artifacts-from-collect",
        "target": "selected-state-index=0..319",
        "train": "model-seeds=653001,653002",
        "evaluate": "stage6-seeds=651001..651256",
        "preflight": "simulator-seed=1;model-seed=653001",
    }[args.command]
    metadata = (
        f"# frozen_shards={shard_count} frozen_worker_count={worker_count} "
        f"frozen_seed_range={seed_range} pinned_simulator=sts_lightspeed"
    )
    pythonpath = f"{T065_LIGHTSPEED_BUILD_PYTHONPATH}:{_wsl_path(_target_src_path())}"
    return "wsl.exe -d Ubuntu -e bash -lc " + shlex.quote(
        "set -euo pipefail; "
        f"export PYTHONPATH={shlex.quote(pythonpath)}; "
        f"{T065_TRAINING_INTERPRETER} -m "
        f"sts_combat_rl.commands.non_combat_learning {shlex.join(rendered)}; "
        + metadata
    )


def _canonical_command_args(args: argparse.Namespace) -> list[str]:
    """Render every relevant frozen/default argument into the replay command."""

    tokens = [args.command]

    def add(flag: str, value: Any) -> None:
        if value is None:
            return
        tokens.extend((flag, str(value)))

    add("--output", getattr(args, "output", None))
    if args.command == "preflight":
        if args.simulator_runtime:
            tokens.append("--simulator-runtime")
        if args.torch_runtime:
            tokens.append("--torch-runtime")
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
    elif args.command == "collect":
        add("--arm", args.arm)
        add("--seed-start", args.seed_start)
        add("--seed-end", args.seed_end)
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    elif args.command == "select":
        for path in args.input:
            add("--input", path)
        add("--manifest", args.manifest or Path(f"{args.output}.manifest.json"))
        add("--preflight", args.preflight)
    elif args.command == "target":
        add("--states", args.states)
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    elif args.command == "train":
        add("--target-table", args.target_table)
        add("--checkpoint-directory", args.checkpoint_directory)
        add("--preflight", args.preflight)
    elif args.command == "evaluate":
        add("--target-table", args.target_table)
        add("--checkpoint-directory", args.checkpoint_directory)
        if args.run_stage6:
            tokens.append("--run-stage6")
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    else:  # pragma: no cover - parser restricts the command set
        raise ValueError(f"unsupported T065 command {args.command!r}")

    for path in getattr(args, "preceding_manifest", None) or ():
        add("--preceding-manifest", path)
    add("--decision-report", _decision_report_path(args))
    add("--retention-manifest", _retention_manifest_path(args))
    return tokens


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
        args, decision_path=decision_path, case_d=case_d, failure=failure
    )
    evidence: dict[str, Any] = {
        "status": "case_d" if case_d else "completed",
        "stage": stage,
        "command": _regeneration_command(args),
        "artifact_roles": sorted(artifacts),
        "preceding_stage_manifests": _preceding_manifest_identities(args),
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
                "failed_stage_artifacts": dict(failure.failed_stage_artifacts),
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
        preceding_stage_manifests=_preceding_manifest_identities(args),
        failed_stage_artifacts=(
            dict(failure.failed_stage_artifacts) if failure is not None else {}
        ),
    )
    print(f"T065 retention manifest: {_retention_manifest_path(args)}", file=sys.stderr)
    return manifest


def _handle_case_d(args: argparse.Namespace, failure: T065CaseD) -> None:
    failure.preceding_stage_manifests.update(_preceding_manifest_identities(args))
    failure.failed_stage_artifacts.update(
        _artifact_identities(_failed_stage_artifact_paths(args, failure))
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
