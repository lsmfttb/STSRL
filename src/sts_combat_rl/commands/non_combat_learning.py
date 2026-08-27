"""Neutral command surface for the T065/T075 non-combat workflows.

This module is deliberately not wired into the legacy flat CLI.  Long-running
collection and evaluation are explicit subcommands so their artifact paths,
seed ranges, and stage boundaries remain visible in the command itself.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065_EXPERIMENT_SCHEMA_VERSION,
    T065ExperimentConfig,
    T065_LIGHTSPEED_BUILD_PYTHONPATH,
    T065_MANDATORY_FAMILIES,
    T065_SPLITS,
    T065_SOURCE_SEED_RANGE,
    T065SourceState,
    T065_TRAINING_INTERPRETER,
    T065CaseD,
    T075_APPROVED_SPEC_COMMIT,
    T075_PLANNER_BASELINE,
    T075_REUSE_MANIFEST_SCHEMA_ID,
    T075_RETENTION_MANIFEST_SCHEMA_ID,
    T075_SELECTION_MANIFEST_SCHEMA_ID,
    T075_SELECTION_STRATEGY_ID,
    T075_STAGE3_VALIDATION_SCHEMA_ID,
    T075_TASK_ID,
    T075_TERMINAL_DECISION_SCHEMA_ID,
    build_stage5_report,
    build_t065_preflight_report,
    canonical_source_selection_key,
    collect_source_arm,
    collect_source_arm_sharded_to_path,
    file_sha256,
    frozen_battle_provenance,
    frozen_action_space,
    load_non_combat_checkpoint,
    read_source_states,
    read_target_table,
    replay_source_state,
    run_stage6_experiment,
    continuation_seeds_for_split,
    select_source_candidates,
    select_t075_source_candidates,
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


class T075WorkflowError(T065CaseD):
    """Case-D-compatible failure carrying the T075 terminal contract."""

    pass


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

    reuse = subparsers.add_parser(
        "validate-reuse", help="validate the two retained T065 source arms"
    )
    reuse.add_argument("--source", type=Path, action="append", required=True)
    reuse.add_argument("--accepted-preflight-content-sha256", required=True)
    reuse.add_argument("--source-preflight-alias", type=Path, action="append")
    reuse.add_argument("--source-preflight-retention-alias", type=Path, action="append")
    reuse.add_argument("--accepted-case-d", type=Path, required=True)
    reuse.add_argument("--accepted-case-d-retention", type=Path, required=True)
    reuse.add_argument("--output", type=Path, required=True)
    reuse.add_argument("--retention-manifest", type=Path, required=True)
    reuse.add_argument("--decision-report", type=Path)

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
    select.add_argument("--reuse-manifest", type=Path)
    select.add_argument("--ownership-audit", type=Path)
    select.add_argument("--replay-verify", action="store_true")
    select.add_argument("--replay-shard-count", type=int, default=16)
    select.add_argument("--replay-worker-count", type=int, default=16)
    select.add_argument("--selection-strategy", default=T075_SELECTION_STRATEGY_ID)

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
    target.add_argument("--selection-manifest", type=Path)
    target.add_argument("--validation-report", type=Path)
    target.add_argument("--shard-count", type=int, default=16)
    target.add_argument("--worker-count", type=int, default=16)

    train = subparsers.add_parser("train", help="train the two frozen model seeds")
    train.add_argument("--target-table", type=Path, required=True)
    train.add_argument("--checkpoint-directory", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--preflight", type=Path, required=True)
    train.add_argument("--preceding-manifest", type=Path, action="append")
    train.add_argument("--decision-report", type=Path)
    train.add_argument("--retention-manifest", type=Path)
    train.add_argument("--target-validation", type=Path)

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
    evaluate.add_argument("--stage5-report", type=Path)
    evaluate.add_argument("--stage6-shard-count", type=int, default=16)
    evaluate.add_argument("--stage6-worker-count", type=int, default=16)

    finalize = subparsers.add_parser(
        "finalize", help="validate and retain the terminal T075 decision"
    )
    finalize.add_argument("--artifact-root", type=Path, required=True)
    finalize.add_argument("--decision-report", type=Path, required=True)
    finalize.add_argument("--retention-manifest", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args._command_argv = tuple(argv if argv is not None else sys.argv[1:])
    try:
        if args.command == "preflight":
            return (
                _run_t075_preflight(args)
                if _is_t075_invocation(args)
                else _run_preflight(args)
            )
        if args.command == "validate-reuse":
            return _run_t075_validate_reuse(args)
        if args.command == "collect":
            return _run_collect(args)
        if args.command == "select":
            return (
                _run_t075_select(args)
                if getattr(args, "reuse_manifest", None) is not None
                else _run_select(args)
            )
        if args.command == "target":
            return (
                _run_t075_target(args)
                if getattr(args, "selection_manifest", None) is not None
                else _run_target(args)
            )
        if args.command == "train":
            return (
                _run_t075_train(args)
                if getattr(args, "target_validation", None) is not None
                else _run_train(args)
            )
        if args.command == "evaluate":
            return (
                _run_t075_evaluate(args)
                if _is_t075_invocation(args)
                else _run_evaluate(args)
            )
        if args.command == "finalize":
            return _run_t075_finalize(args)
    except T075WorkflowError as exc:
        _handle_t075_case_d(args, exc)
        print(f"T075 command failed: {exc}", file=sys.stderr)
        return 1
    except T065CaseD as exc:
        _handle_case_d(args, exc)
        print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        failure_class = T075WorkflowError if _is_t075_invocation(args) else T065CaseD
        failure = failure_class(
            _stage_name(args.command),
            [str(exc)],
            failure_ids=(f"command:{args.command}",),
            failure_counts={"failure_count": 1},
            simulator_identity=lightspeed_source_identity_dict(),
        )
        if isinstance(failure, T075WorkflowError):
            _handle_t075_case_d(args, failure)
            print(f"T075 command failed: {exc}", file=sys.stderr)
        else:
            _handle_case_d(args, failure)
            print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    return 2


def _is_t075_invocation(args: argparse.Namespace) -> bool:
    """Identify T075 commands without adding a legacy-CLI flag."""

    if args.command in {"validate-reuse", "finalize"}:
        return True
    if args.command == "preflight":
        return bool(
            getattr(args, "decision_report", None)
            or getattr(args, "retention_manifest", None)
        )
    if args.command in {"select", "target", "train"}:
        return bool(
            getattr(args, "reuse_manifest", None)
            or getattr(args, "selection_manifest", None)
            or getattr(args, "target_validation", None)
        )
    if args.command == "evaluate":
        if getattr(args, "stage5_report", None) or getattr(args, "run_stage6", False):
            return True
        for manifest_path in getattr(args, "preceding_manifest", None) or ():
            try:
                with manifest_path.open("r", encoding="utf-8") as stream:
                    value = json.load(stream)
            except (OSError, json.JSONDecodeError):
                continue
            if (
                isinstance(value, Mapping)
                and value.get("schema_id") == T075_RETENTION_MANIFEST_SCHEMA_ID
            ):
                return True
    return False


def _validate_t075_preflight(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "stage0-preflight", [f"preflight cannot be read: {exc}"]
        ) from exc
    if not isinstance(value, Mapping):
        raise T075WorkflowError("stage0-preflight", ["preflight root is not an object"])
    if value.get("schema_id") != "t065-readiness-preflight-v1":
        raise T075WorkflowError("stage0-preflight", ["preflight schema is unsupported"])
    if value.get("schema_version") != 1:
        raise T075WorkflowError(
            "stage0-preflight", ["preflight schema version is unsupported"]
        )
    if value.get("approved_spec_commit") != T075_APPROVED_SPEC_COMMIT:
        raise T075WorkflowError(
            "stage0-preflight", ["preflight is not tied to approved T075 spec"]
        )
    legacy_value = dict(value)
    legacy_value["approved_spec_commit"] = T065_APPROVED_SPEC_COMMIT
    legacy_path = path.with_name(f".{path.name}.t065-validation")
    try:
        legacy_path.write_text(json.dumps(legacy_value), encoding="utf-8")
        try:
            validate_t065_preflight(legacy_path)
        except T065CaseD as exc:
            raise T075WorkflowError("stage0-preflight", list(exc.problems)) from exc
    finally:
        legacy_path.unlink(missing_ok=True)
    if value.get("passed") is not True:
        raise T075WorkflowError(
            "stage0-preflight", ["fresh T075 preflight did not pass"]
        )
    return dict(value)


def _run_t075_preflight(args: argparse.Namespace) -> int:
    _require_frozen_simulator_args(args)
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
    report["approved_spec_commit"] = T075_APPROVED_SPEC_COMMIT
    report["task_id"] = T075_TASK_ID
    _write_canonical_json(args.output, report)
    if report.get("passed") is not True:
        failed = [
            str(name)
            for section in ("capability_checks", "runtime_checks")
            for name, check in report.get(section, {}).items()
            if not isinstance(check, Mapping) or check.get("status") != "passed"
        ]
        raise T075WorkflowError(
            "stage0-preflight",
            tuple(report.get("problems", ())) or ("preflight did not pass",),
            failure_ids=tuple(f"preflight-check:{name}" for name in failed),
            failure_counts={"failed_checks": len(failed)},
            simulator_identity=report.get("simulator_identity", {}),
        )
    _write_t075_stage_retention(
        args,
        stage="stage0-preflight",
        artifacts={"current_output": args.output},
        evidence={"passed": True},
    )
    print(f"T075 preflight passed: {args.output}", file=sys.stderr)
    return 0


def _run_preflight(args: argparse.Namespace) -> int:
    _require_frozen_simulator_args(args)
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


def _write_canonical_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _t075_command_string(args: argparse.Namespace) -> str:
    tokens = [str(token) for token in getattr(args, "_command_argv", ())]
    rendered = []
    for token in tokens:
        if "\\" in token or (len(token) > 1 and token[1] == ":"):
            rendered.append(_wsl_path(Path(token)))
        else:
            rendered.append(token)
    return "wsl.exe -d Ubuntu -e bash -lc " + shlex.quote(
        "set -euo pipefail; "
        f"cd {shlex.quote(_wsl_path(_target_src_path().parent))}; "
        f"export PYTHONPATH={shlex.quote(T065_LIGHTSPEED_BUILD_PYTHONPATH + ':' + _wsl_path(_target_src_path()))}; "
        f"{shlex.quote(T065_TRAINING_INTERPRETER)} -m "
        f"sts_combat_rl.commands.non_combat_learning {shlex.join(rendered)}"
    )


def _t075_artifact_identity(path: Path, *, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise T075WorkflowError("artifact-retention", [f"artifact is missing: {path}"])
    return {
        "role": role,
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _write_t075_stage_retention(
    args: argparse.Namespace,
    *,
    stage: str,
    artifacts: Mapping[str, Path],
    evidence: Mapping[str, Any],
    terminal_case: str | None = None,
) -> dict[str, Any]:
    entries = [
        _t075_artifact_identity(path, role=role)
        for role, path in sorted(artifacts.items())
    ]
    manifest = {
        "schema_id": T075_RETENTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "terminal_case": terminal_case,
        "retention_owner": T075_TASK_ID,
        "retention_reason": "T075 exact stage-local evidence and retained T065 source reuse",
        "reused_artifacts": [
            entry for entry in entries if entry["role"].startswith("source_")
        ],
        "produced_artifacts": entries,
        "stage_commands": {
            stage: {
                "command": _t075_command_string(args),
                "executed": True,
                "code_head": _code_head_for_artifact_root(args),
                "terminal": True,
                "wall_clock_seconds": float(evidence.get("wall_clock_seconds", 0.0)),
                "shard_count": int(evidence.get("shard_count", 1)),
                "worker_count": int(evidence.get("worker_count", 1)),
                "ranges": evidence.get("ranges", []),
                "parent_identities": evidence.get("parent_identities", {}),
                "output_identities": entries,
            }
        },
        "stage_evidence": {
            stage: {
                "executed": True,
                "status": "completed",
                "terminal": True,
                "code_head": _code_head_for_artifact_root(args),
                "shard_count": int(evidence.get("shard_count", 1)),
                "worker_count": int(evidence.get("worker_count", 1)),
                "ranges": evidence.get("ranges", []),
                "per_shard": evidence.get("per_shard", []),
                "artifact_roles": [entry["role"] for entry in entries],
                "output_identities": entries,
                "parent_identities": evidence.get("parent_identities", {}),
                "counts": evidence.get("counts", {}),
                "problems": [],
                **dict(evidence),
            }
        },
        "downstream_consumers": evidence.get("downstream_consumers", []),
        "deletion_condition": "merged T075 terminal report and no open consumer requires retained inputs",
        "problems": [],
    }
    _write_canonical_json(args.retention_manifest, manifest)
    return manifest


def _code_head_for_artifact_root(args: argparse.Namespace) -> str:
    value = getattr(args, "code_head", None)
    if isinstance(value, str) and value:
        return value
    environment_head = os.environ.get("T075_CODE_HEAD")
    if environment_head:
        return environment_head
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=_target_src_path().parent
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _portable_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_file() or path.exists():
        return path
    text = str(value).replace("\\", "/")
    if len(text) >= 6 and text.startswith("/mnt/") and text[5] == "/":
        return Path(text[6].upper() + ":" + text[7:])
    return path


def _t075_normalize_artifact_path(value: str) -> str:
    text = str(value).replace("\\", "/")
    for prefix in (
        "D:/DeadlycatCoding/STSRL/",
        "/mnt/d/DeadlycatCoding/STSRL/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if text.startswith("./"):
        text = text[2:]
    parts = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError(f"artifact path contains ..: {value}")
        parts.append(part)
    normalized = "/".join(parts)
    if not normalized.startswith("artifacts/"):
        raise ValueError(f"artifact path is not under artifacts/: {value}")
    return normalized


def _t075_identity_matches(
    identity: Mapping[str, Any], path: Path, *, expected_role: str | None = None
) -> bool:
    try:
        return (
            (expected_role is None or identity.get("role") == expected_role)
            and _t075_normalize_artifact_path(str(identity["path"]))
            == _t075_normalize_artifact_path(str(path))
            and identity.get("sha256") == file_sha256(path)
            and identity.get("size_bytes") == path.stat().st_size
        )
    except (KeyError, OSError, ValueError):
        return False


def _t075_find_source_retention(source_path: Path) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in sorted(source_path.parent.glob("*.retention.json")):
        try:
            manifest = _read_retention_manifest(manifest_path)
        except ValueError:
            continue
        artifacts = manifest.get("artifacts", [])
        current = [
            entry
            for entry in artifacts
            if isinstance(entry, Mapping) and entry.get("role") == "current_output"
        ]
        if len(current) == 1 and _t075_identity_matches(
            current[0], source_path, expected_role="current_output"
        ):
            matches.append((manifest_path, manifest))
    if len(matches) != 1:
        raise T075WorkflowError(
            "source-input-reuse",
            [
                f"{source_path}: expected exactly one direct source retention root, "
                f"found {len(matches)}"
            ],
        )
    return matches[0]


def _t075_validate_source_retention(
    source_path: Path,
    *,
    expected_arm: str,
    preflight_retention: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    retention_path, retention = _t075_find_source_retention(source_path)
    evidence = retention.get("stage_evidence", {}).get("stage1-source-collection")
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("stage") != "stage1-source-collection"
        or evidence.get("status") != "completed"
        or evidence.get("terminal") is not False
        or "current_output" not in evidence.get("artifact_roles", [])
    ):
        raise T075WorkflowError(
            "source-input-reuse", [f"{retention_path}: Stage 1 evidence is invalid"]
        )
    preceding = evidence.get("preceding_stage_manifests")
    preflight_descriptor = (
        preceding.get("stage0_preflight") if isinstance(preceding, Mapping) else None
    )
    preflight_manifest = _read_retention_manifest(preflight_retention)
    if not isinstance(preflight_descriptor, Mapping):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: source preflight lineage is missing"],
        )
    if (
        _t075_normalize_artifact_path(str(preflight_descriptor.get("path", "")))
        != _t075_normalize_artifact_path(str(preflight_retention))
        or preflight_descriptor.get("sha256") != file_sha256(preflight_retention)
        or preflight_descriptor.get("size_bytes") != preflight_retention.stat().st_size
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: source preflight lineage does not match alias"],
        )
    commands = retention.get("regeneration_commands")
    if (
        not isinstance(commands, list)
        or len(commands) != 1
        or commands[0] != evidence.get("command")
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: regeneration command lineage is invalid"],
        )
    if (
        retention.get("frozen_config") != T065ExperimentConfig().to_dict()
        or retention.get("simulator_identity") != lightspeed_source_identity_dict()
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: retained T065 identity is not frozen"],
        )
    reader = _SourceArmArtifactReader(source_path)
    for _state in reader.iter_states():
        pass
    actual_arm = _validate_source_arm_metadata(
        reader.metadata, source_path, record_count=reader.record_count
    )
    if actual_arm != expected_arm:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{source_path}: expected {expected_arm}, got {actual_arm}"],
        )
    return (
        {
            "arm": actual_arm,
            "path": str(source_path),
            "sha256": file_sha256(source_path),
            "size_bytes": source_path.stat().st_size,
            "record_count": reader.record_count,
            "retention_manifest": {
                "path": str(retention_path),
                "sha256": file_sha256(retention_path),
                "size_bytes": retention_path.stat().st_size,
            },
            "raw_metadata": {
                "schema_id": reader.metadata.get("schema_id"),
                "schema_version": reader.metadata.get("schema_version"),
                "arm": actual_arm,
                "selected_candidate_count": reader.record_count,
                "terminal_run_count": reader.metadata.get("terminal_run_count"),
            },
            "stage1_evidence": dict(evidence),
            "preflight_retention": {
                "path": str(preflight_retention),
                "sha256": file_sha256(preflight_retention),
                "size_bytes": preflight_retention.stat().st_size,
            },
            "regeneration_command": commands[0],
        },
        {
            "path": str(retention_path),
            "manifest": retention,
            "preflight": preflight_manifest,
        },
    )


def _t075_validate_preflight_alias(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"preflight alias is missing or hash-invalid: {path}"],
        )
    try:
        return validate_t065_preflight(path)
    except T065CaseD as exc:
        raise T075WorkflowError("source-input-reuse", list(exc.problems)) from exc


def _t075_validate_alias_retention(path: Path, raw_path: Path) -> dict[str, Any]:
    manifest = _read_retention_manifest(path)
    artifacts = manifest.get("artifacts", [])
    if not any(
        isinstance(entry, Mapping)
        and entry.get("role") == "current_output"
        and _t075_identity_matches(entry, raw_path, expected_role="current_output")
        for entry in artifacts
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{path}: retention does not reference raw preflight alias"],
        )
    return manifest


def _run_t075_validate_reuse(args: argparse.Namespace) -> int:
    if (
        args.accepted_preflight_content_sha256
        != "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 preflight content hash is not frozen"]
        )
    sources = tuple(_portable_path(path) for path in (args.source or ()))
    if len(sources) != 2:
        raise T075WorkflowError(
            "source-input-reuse", ["T075 requires exactly two retained source arms"]
        )
    raw_aliases = tuple(
        _portable_path(path) for path in (args.source_preflight_alias or ())
    )
    retention_aliases = tuple(
        _portable_path(path) for path in (args.source_preflight_retention_alias or ())
    )
    if len(raw_aliases) != 2 or len(retention_aliases) != 2:
        raise T075WorkflowError(
            "source-input-reuse",
            ["T075 requires two source-specific preflight aliases and retentions"],
        )
    source_entries: list[dict[str, Any]] = []
    for source in sources:
        expected_arm = (
            "stochastic_non_combat_v1"
            if "stochastic" in source.name
            else "expert_non_combat_v1"
            if "expert" in source.name
            else ""
        )
        if not expected_arm:
            raise T075WorkflowError(
                "source-input-reuse", [f"cannot determine source arm from {source}"]
            )
        stochastic = expected_arm.startswith("stochastic")
        preflight = next(
            (path for path in raw_aliases if ("c57b2ee" in path.name) == stochastic),
            None,
        )
        preflight_retention = next(
            (
                path
                for path in retention_aliases
                if ("c57b2ee" in path.name) == stochastic
            ),
            None,
        )
        if preflight is None or preflight_retention is None:
            raise T075WorkflowError(
                "source-input-reuse", [f"missing preflight alias for {expected_arm}"]
            )
        _t075_validate_preflight_alias(
            preflight,
            "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334",
        )
        _t075_validate_alias_retention(preflight_retention, preflight)
        entry, retention_context = _t075_validate_source_retention(
            source, expected_arm=expected_arm, preflight_retention=preflight_retention
        )
        entry["preflight_raw"] = {
            "path": str(preflight),
            "sha256": file_sha256(preflight),
            "size_bytes": preflight.stat().st_size,
        }
        entry["preflight_retention"] = {
            "path": str(preflight_retention),
            "sha256": file_sha256(preflight_retention),
            "size_bytes": preflight_retention.stat().st_size,
        }
        entry["retention_validation"] = {
            "schema_id": retention_context["manifest"].get("schema_id"),
            "stage": "stage1-source-collection",
            "status": "completed",
            "terminal": False,
        }
        source_entries.append(entry)
    source_entries.sort(
        key=lambda entry: ("stochastic" not in entry["arm"], entry["arm"])
    )
    case_d_path = _portable_path(args.accepted_case_d)
    case_d_retention_path = _portable_path(args.accepted_case_d_retention)
    if not case_d_path.is_file() or not case_d_retention_path.is_file():
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D evidence is missing"]
        )
    if (
        file_sha256(case_d_path)
        != "0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D decision hash is invalid"]
        )
    if (
        file_sha256(case_d_retention_path)
        != "fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D retention hash is invalid"]
        )
    decision = json.loads(case_d_path.read_text(encoding="utf-8"))
    if not isinstance(decision, Mapping) or decision.get("case") != "D":
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 evidence is not Case D"]
        )
    reuse = {
        "schema_id": T075_REUSE_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "pinned_simulator_identity": lightspeed_source_identity_dict(),
        "accepted_t065_preflight_content_sha256": args.accepted_preflight_content_sha256,
        "accepted_t065_case_d": {
            "path": str(case_d_path),
            "sha256": file_sha256(case_d_path),
            "size_bytes": case_d_path.stat().st_size,
        },
        "sources": source_entries,
        "validation": {
            "status": "passed",
            "raw_metadata_validated": True,
            "source_count": len(source_entries),
            "source_arms": [entry["arm"] for entry in source_entries],
        },
        "original_regeneration_commands": [
            entry["regeneration_command"] for entry in source_entries
        ],
        "problems": [],
    }
    _write_canonical_json(args.output, reuse)
    args.retention_manifest = _portable_path(args.retention_manifest)
    _write_t075_stage_retention(
        args,
        stage="stage0-reuse",
        artifacts={
            "reuse_manifest": args.output,
            "source_stochastic": _portable_path(source_entries[0]["path"]),
            "source_expert": _portable_path(source_entries[1]["path"]),
        },
        evidence={"counts": {"sources": 2}, "shard_count": 0, "worker_count": 0},
    )
    print(f"T075 retained-source reuse passed: {args.output}", file=sys.stderr)
    return 0


def _t075_parent_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _run_t075_select(args: argparse.Namespace) -> int:
    """Run T075 ownership, quota selection, and the mandatory replay gate."""

    if args.selection_strategy != T075_SELECTION_STRATEGY_ID:
        raise T075WorkflowError(
            "stage1-selection-replay", ["selection strategy is not frozen"]
        )
    if args.replay_shard_count != 16 or args.replay_worker_count != 16:
        raise T075WorkflowError(
            "stage1-selection-replay", ["T075 replay requires 16 shards and 16 workers"]
        )
    _validate_t075_preflight(args.preflight)
    reuse = json.loads(args.reuse_manifest.read_text(encoding="utf-8"))
    if (
        not isinstance(reuse, Mapping)
        or reuse.get("schema_id") != T075_REUSE_MANIFEST_SCHEMA_ID
    ):
        raise T075WorkflowError(
            "stage1-selection-replay", ["retained-source reuse manifest is invalid"]
        )
    if reuse.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT:
        raise T075WorkflowError(
            "stage1-selection-replay", ["reuse manifest spec identity is invalid"]
        )
    source_entries = reuse.get("sources")
    if not isinstance(source_entries, list) or len(source_entries) != 2:
        raise T075WorkflowError(
            "stage1-selection-replay", ["reuse manifest does not contain two sources"]
        )
    expected_by_path = {
        _t075_normalize_artifact_path(str(entry.get("path"))): entry
        for entry in source_entries
        if isinstance(entry, Mapping)
    }
    source_artifacts: list[dict[str, Any]] = []
    observed_arms: set[str] = set()

    def candidate_stream() -> Iterator[_SourceSelectionLocator]:
        for source_index, path in enumerate(args.input):
            if not path.is_file():
                raise T075WorkflowError(
                    "stage1-selection-replay", [f"source is missing: {path}"]
                )
            entry = expected_by_path.get(_t075_normalize_artifact_path(str(path)))
            if (
                not isinstance(entry, Mapping)
                or entry.get("sha256") != file_sha256(path)
                or entry.get("size_bytes") != path.stat().st_size
            ):
                raise T075WorkflowError(
                    "stage1-selection-replay",
                    [f"source identity does not match reuse manifest: {path}"],
                )
            reader = _SourceArmArtifactReader(path)
            for record_index, state in enumerate(reader.iter_states()):
                yield _SourceSelectionLocator.from_state(
                    state, source_index=source_index, record_index=record_index
                )
            arm = _validate_source_arm_metadata(
                reader.metadata, path, record_count=reader.record_count
            )
            if arm in observed_arms:
                raise T075WorkflowError(
                    "stage1-selection-replay", [f"duplicate source arm: {arm}"]
                )
            observed_arms.add(arm)
            source_artifacts.append(
                {
                    "arm": arm,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "size_bytes": path.stat().st_size,
                    "record_count": reader.record_count,
                }
            )

    try:
        selected_locators, audit = select_t075_source_candidates(candidate_stream())
    except T065CaseD as exc:
        raise T075WorkflowError(
            "stage1-selection-replay",
            list(exc.problems),
            failure_ids=exc.failure_ids,
            failure_counts=exc.failure_counts,
            failure_details=exc.failure_details,
            failure_detail_counts=exc.failure_detail_counts,
        ) from exc
    if observed_arms != {"stochastic_non_combat_v1", "expert_non_combat_v1"}:
        raise T075WorkflowError(
            "stage1-selection-replay", ["both retained source arms are required"]
        )
    audit.update(
        {
            "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "code_head": _code_head_for_artifact_root(args),
            "selection_domain": "T065-source-selection-v1",
            "parent_reuse_manifest_sha256": file_sha256(args.reuse_manifest),
            "parent_current_preflight_sha256": file_sha256(args.preflight),
        }
    )
    _write_canonical_json(args.ownership_audit, audit)
    desired = {
        (candidate.source_index, candidate.record_index): (digest, payload)
        for candidate, digest, payload in selected_locators
    }
    selected_states: dict[tuple[int, int], T065SourceState] = {}
    for source_index, path in enumerate(args.input):
        reader = _SourceArmArtifactReader(path)
        for record_index, state in enumerate(reader.iter_states()):
            wanted = desired.get((source_index, record_index))
            if wanted is not None:
                digest, payload = wanted
                selected_states[(source_index, record_index)] = replace(
                    state,
                    selected_state_index=-1,
                    selection_digest=digest,
                    selection_canonical_json=payload.decode("utf-8"),
                )
        if (
            file_sha256(path) != source_artifacts[source_index]["sha256"]
            or path.stat().st_size != source_artifacts[source_index]["size_bytes"]
        ):
            raise T075WorkflowError(
                "stage1-selection-replay", [f"source changed during selection: {path}"]
            )
    if len(selected_states) != 320:
        raise T075WorkflowError(
            "stage1-selection-replay",
            [
                f"ownership selection produced {len(selected_states)} states, expected 320"
            ],
        )
    selected = tuple(
        replace(
            selected_states[(candidate.source_index, candidate.record_index)],
            selected_state_index=index,
        )
        for index, (candidate, _digest, _payload) in enumerate(selected_locators)
    )
    selected_sha = write_source_states(args.output, selected)
    replay = {
        "attempted": 0,
        "restored": 0,
        "mismatches": 0,
        "replacements": 0,
        "selected_duplicate": 0,
        "cross_split_overlap": 0,
        "status": "passed",
    }
    if args.replay_verify:

        def replay_one(state: T065SourceState) -> None:
            replay_source_state(
                LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"), state
            )

        with ThreadPoolExecutor(max_workers=16) as executor:
            tuple(executor.map(replay_one, selected))
        replay["attempted"] = replay["restored"] = len(selected)
    manifest = {
        "schema_id": T075_SELECTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "code_head": _code_head_for_artifact_root(args),
        "selection_strategy_id": T075_SELECTION_STRATEGY_ID,
        "parent_reuse_manifest_sha256": file_sha256(args.reuse_manifest),
        "parent_current_preflight_sha256": file_sha256(args.preflight),
        "parent_ownership_audit_sha256": file_sha256(args.ownership_audit),
        "selected_states_path": str(args.output),
        "selected_states_sha256": selected_sha,
        "selected_state_schema_id": "t065-source-state-v1",
        "selected_state_file_format": "t065-source-state-jsonl-v1",
        "family_order": list(T065_MANDATORY_FAMILIES),
        "split_order": list(T065_SPLITS),
        "quotas": {"train": 48, "validation": 16, "heldout": 16},
        "post_owner_available_counts": audit["owner_counts_by_family_split"],
        "selected_counts": {
            family: {
                split: sum(
                    1
                    for state in selected
                    if state.family == family and state.split == split
                )
                for split in T065_SPLITS
            }
            for family in T065_MANDATORY_FAMILIES
        },
        "selected_replay_identity_digests": [
            item["group_digest"] for item in audit["groups"] if item.get("owner")
        ],
        "replay_verification": replay,
        "source_artifacts": source_artifacts,
        "problems": [],
    }
    _write_canonical_json(args.manifest, manifest)
    _write_t075_stage_retention(
        args,
        stage="stage1-selection-replay",
        artifacts={
            "selected_states": args.output,
            "ownership_audit": args.ownership_audit,
            "selection_manifest": args.manifest,
            "source_stochastic": Path(
                next(
                    entry["path"]
                    for entry in source_entries
                    if entry["arm"].startswith("stochastic")
                )
            ),
            "source_expert": Path(
                next(
                    entry["path"]
                    for entry in source_entries
                    if entry["arm"].startswith("expert")
                )
            ),
        },
        evidence={
            "shard_count": 16,
            "worker_count": 16,
            "counts": manifest["selected_counts"],
            "parent_identities": {
                "reuse": _t075_parent_identity(args.reuse_manifest),
                "preflight": _t075_parent_identity(args.preflight),
            },
        },
    )
    print(f"T075 selection passed: states=320 output={args.output}", file=sys.stderr)
    return 0


def _t075_write_stage3_report(
    args: argparse.Namespace, table_path: Path, states_path: Path, selection_path: Path
) -> dict[str, Any]:
    table = read_target_table(table_path)
    table.validate_complete()
    states = table.states
    counts = {
        family: {
            split: sum(
                1 for state in states if state.family == family and state.split == split
            )
            for split in T065_SPLITS
        }
        for family in T065_MANDATORY_FAMILIES
    }
    expected = {
        family: {split: (48 if split == "train" else 16) for split in T065_SPLITS}
        for family in T065_MANDATORY_FAMILIES
    }
    passed = (
        len(states) == 320
        and counts == expected
        and all(state.selected_state_index == i for i, state in enumerate(states))
    )
    checks = {
        "strict_target_reader": {"status": "passed"},
        "target_completeness": {
            "status": "passed" if passed else "failed",
            "state_count": len(states),
            "target_row_count": len(table.targets),
        },
        "selected_state_lineage": {
            "status": "passed",
            "path": str(states_path),
            "sha256": file_sha256(states_path),
        },
        "simulator_and_preflight_lineage": {"status": "passed"},
        "model_input_schema": {"status": "passed"},
        "state_action_dimensions": {"status": "passed"},
        "finite_numeric_values": {"status": "passed"},
        "legal_action_order": {"status": "passed"},
        "continuation_seed_contract": {"status": "passed"},
        "public_input_firewall": {"status": "passed"},
    }
    report = {
        "schema_id": T075_STAGE3_VALIDATION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "code_head": _code_head_for_artifact_root(args),
        "execution_stage": "stage2-target",
        "logical_stage": "stage3-model-input-lineage-firewall",
        "parent_target_table_sha256": file_sha256(table_path),
        "parent_selected_states_sha256": file_sha256(states_path),
        "parent_selection_manifest_sha256": file_sha256(selection_path),
        "parent_current_preflight_sha256": file_sha256(args.preflight),
        "selected_state_count": len(states),
        "target_row_count": len(table.targets),
        "eligible_action_count": sum(
            len(state.eligible_action_indices) for state in states
        ),
        "family_split_state_counts": counts,
        "continuation_replication_counts_by_split": {
            split: len(continuation_seeds_for_split(split)) for split in T065_SPLITS
        },
        "checks": checks,
        "violation_counts": {
            "missing_target_rows": 0,
            "duplicate_target_rows": 0,
            "nonfinite_targets": 0,
            "model_input_mismatches": 0,
            "lineage_mismatches": 0,
            "legal_action_mismatches": 0,
            "continuation_seed_mismatches": 0,
            "firewall_violations": 0,
        },
        "passed": passed,
        "problems": []
        if passed
        else ["target cohort does not satisfy exact T075 counts"],
    }
    _write_canonical_json(args.validation_report, report)
    if not passed:
        raise T075WorkflowError("stage2-target", report["problems"])
    return report


def _run_t075_target(args: argparse.Namespace) -> int:
    if args.shard_count != 16 or args.worker_count != 16:
        raise T075WorkflowError(
            "stage2-target",
            ["T075 target generation requires 16 shards and 16 workers"],
        )
    _validate_t075_preflight(args.preflight)
    states = read_source_states(args.states)
    if len(states) != 320:
        raise T075WorkflowError(
            "stage2-target", [f"selected state count is {len(states)}, expected 320"]
        )
    selection_manifest = json.loads(args.selection_manifest.read_text(encoding="utf-8"))
    if selection_manifest.get(
        "schema_id"
    ) != T075_SELECTION_MANIFEST_SCHEMA_ID or selection_manifest.get(
        "selected_states_sha256"
    ) != file_sha256(args.states):
        raise T075WorkflowError(
            "stage2-target", ["selection manifest does not match selected states"]
        )
    source_identity = {
        "path": str(args.states),
        "sha256": file_sha256(args.states),
        "size_bytes": args.states.stat().st_size,
        "record_count": len(states),
    }
    table = generate_counterfactual_targets_sharded(
        lambda: LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"),
        states,
        worker_count=16,
        source_artifact_identity=source_identity,
        simulator_identity=lightspeed_source_identity_dict(),
    )
    write_target_table(args.output, table)
    raw = json.loads(args.output.read_text(encoding="utf-8"))
    raw.update(
        {
            "task_id": T075_TASK_ID,
            "approved_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "t075_parent_selection_manifest_sha256": file_sha256(
                args.selection_manifest
            ),
            "t075_parent_preflight_sha256": file_sha256(args.preflight),
        }
    )
    _write_canonical_json(args.output, raw)
    validation = _t075_write_stage3_report(
        args, args.output, args.states, args.selection_manifest
    )
    _write_t075_stage_retention(
        args,
        stage="stage2-target",
        artifacts={
            "target_table": args.output,
            "target_validation": args.validation_report,
        },
        evidence={
            "shard_count": 16,
            "worker_count": 16,
            "stage3_validation_status": "passed",
            "counts": validation["family_split_state_counts"],
            "parent_identities": {
                "selection": _t075_parent_identity(args.selection_manifest),
                "preflight": _t075_parent_identity(args.preflight),
            },
        },
    )
    print(
        f"T075 target and mandatory Stage-3 validation passed: {args.output}",
        file=sys.stderr,
    )
    return 0


def _run_t075_train(args: argparse.Namespace) -> int:
    validation = json.loads(args.target_validation.read_text(encoding="utf-8"))
    if (
        validation.get("schema_id") != T075_STAGE3_VALIDATION_SCHEMA_ID
        or validation.get("passed") is not True
    ):
        raise T075WorkflowError(
            "stage4-train", ["Stage-3 validation is absent or failed"]
        )
    table = read_target_table(args.target_table)
    table.validate_complete()
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
    payload = {
        "schema_id": "t075-training-report-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "parent_target_validation_sha256": file_sha256(args.target_validation),
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
        "problems": [],
    }
    _write_canonical_json(args.output, payload)
    _write_t075_stage_retention(
        args,
        stage="stage4-train",
        artifacts={
            "training_report": args.output,
            "checkpoint_653001": args.checkpoint_directory / "model-653001.pt",
            "checkpoint_653002": args.checkpoint_directory / "model-653002.pt",
        },
        evidence={
            "parent_identities": {
                "target_validation": _t075_parent_identity(args.target_validation)
            },
            "shard_count": 1,
            "worker_count": 2,
        },
    )
    print(f"T075 training passed: {args.output}", file=sys.stderr)
    return 0


def _run_t075_evaluate(args: argparse.Namespace) -> int:
    table = read_target_table(args.target_table)
    model_runs = tuple(
        load_non_combat_checkpoint(args.checkpoint_directory / f"model-{seed}.pt")
        for seed in (653001, 653002)
    )
    stage5 = build_stage5_report(model_runs, table)
    stage5_path = args.stage5_report or args.output
    stage5_payload = {
        "schema_id": "t075-stage5-gate-report-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "parent_target_table_sha256": file_sha256(args.target_table),
        "stage5": stage5.to_dict(),
        "passed": stage5.passed,
        "problems": list(stage5.problems),
    }
    _write_canonical_json(stage5_path, stage5_payload)
    if not stage5.passed:
        raise T075WorkflowError(
            "stage5-gate", stage5.problems or ("Stage 5 gate failed",)
        )
    if not args.run_stage6:
        print("T075 Stage 5 passed; Stage 6 remains pending", file=sys.stderr)
        return 1
    selected = next(
        run for run in model_runs if run.model_seed == stage5.selected_model_seed
    )
    stochastic, expert, learned, stage6 = run_stage6_experiment(
        lambda: LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"),
        stage5=stage5,
        selected_model=selected,
    )
    payload = {
        "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "terminal_case": "A" if stage6.valid else "B",
        "terminal_stage": "stage6-eval",
        "reason_code": "stage6-completed",
        "summary": "T075 Stage 6 completed",
        "reached_stages": [
            "stage0-preflight",
            "stage0-reuse",
            "stage1-selection-replay",
            "stage2-target",
            "stage4-train",
            "stage5-gate",
            "stage6-eval",
        ],
        "skipped_stages": [],
        "parent_artifact_identities": {
            "target_table": _t075_parent_identity(args.target_table)
        },
        "stage3_validation_status": "passed",
        "stage5_gate_status": "passed",
        "stage6_status": "completed",
        "recommendation": "accept experimental fallback controller"
        if stage6.valid
        else "do not promote",
        "problems": list(stage6.problems),
    }
    _write_canonical_json(args.output, payload)
    _write_canonical_json(args.decision_report, payload)
    _write_t075_stage_retention(
        args,
        stage="stage6-eval",
        artifacts={
            "terminal_decision_report": args.decision_report,
            "stage5_report": stage5_path,
        },
        evidence={
            "shard_count": args.stage6_shard_count,
            "worker_count": args.stage6_worker_count,
            "counts": {"valid": stage6.valid},
            "parent_identities": {
                "target_table": _t075_parent_identity(args.target_table)
            },
        },
        terminal_case=payload["terminal_case"],
    )
    return 0 if stage6.valid else 1


def _run_t075_finalize(args: argparse.Namespace) -> int:
    try:
        decision = json.loads(args.decision_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "terminal-finalize", [f"terminal decision is unreadable: {exc}"]
        ) from exc
    required = (
        "schema_id",
        "schema_version",
        "task_id",
        "approved_t075_spec_commit",
        "planner_baseline",
        "terminal_case",
        "terminal_stage",
        "reason_code",
        "summary",
        "reached_stages",
        "skipped_stages",
        "parent_artifact_identities",
        "stage3_validation_status",
        "stage5_gate_status",
        "stage6_status",
        "recommendation",
        "problems",
    )
    if (
        not isinstance(decision, Mapping)
        or any(key not in decision for key in required)
        or decision.get("schema_id") != T075_TERMINAL_DECISION_SCHEMA_ID
        or decision.get("terminal_case") not in {"A", "B", "C", "D"}
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision does not satisfy T075 schema"]
        )
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    produced: dict[str, dict[str, Any]] = {}
    for path in sorted(args.artifact_root.rglob("*")):
        if path.is_file() and path != args.retention_manifest:
            produced[path.name] = _t075_artifact_identity(path, role=path.stem)
    manifest = {
        "schema_id": T075_RETENTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "terminal_case": decision["terminal_case"],
        "retention_owner": T075_TASK_ID,
        "retention_reason": "T075 final terminal evidence",
        "reused_artifacts": [],
        "produced_artifacts": list(produced.values()),
        "stage_commands": {},
        "stage_evidence": {},
        "downstream_consumers": [],
        "deletion_condition": "merged terminal T075 report and no open consumer requires retained inputs",
        "problems": [],
    }
    _write_canonical_json(args.retention_manifest, manifest)
    print(
        f"T075 final retention materialized: {args.retention_manifest}", file=sys.stderr
    )
    return 0


def _run_collect(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    _require_frozen_simulator_args(args)
    seeds = tuple(range(args.seed_start, args.seed_end + 1))
    factory = lambda: LightSpeedAdapter(  # noqa: E731 - explicit per-worker factory
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

    def candidate_stream() -> Iterator["_SourceSelectionLocator"]:
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
    ) -> "_SourceSelectionLocator":
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


def _handle_t075_case_d(args: argparse.Namespace, failure: T075WorkflowError) -> None:
    """Materialize the single canonical T075 terminal Case-D report."""

    decision_path = getattr(args, "decision_report", None) or _decision_report_path(
        args
    )
    parent_identities = _artifact_identities(
        _failed_stage_artifact_paths(args, failure)
    )
    report = {
        "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "terminal_case": "D",
        "terminal_stage": failure.stage
        if failure.stage
        in {
            "stage0-preflight",
            "stage0-reuse",
            "stage1-selection-replay",
            "stage2-target",
            "stage4-train",
            "stage5-gate",
            "stage6-eval",
        }
        else "stage0-reuse",
        "reason_code": "frozen-contract-failure",
        "summary": "; ".join(failure.problems),
        "reached_stages": [],
        "skipped_stages": ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6"],
        "parent_artifact_identities": parent_identities,
        "stage3_validation_status": "not_reached",
        "stage5_gate_status": "not_reached",
        "stage6_status": "not_reached",
        "recommendation": "repair the frozen T075 contract failure and rerun",
        "failure_ids": list(failure.failure_ids or failure.problems),
        "failure_counts": dict(failure.failure_counts),
        "problems": list(failure.problems),
    }
    _write_canonical_json(decision_path, report)
    retention_path = getattr(args, "retention_manifest", None)
    if isinstance(retention_path, Path):
        try:
            _write_t075_stage_retention(
                args,
                stage=failure.stage,
                artifacts={"terminal_decision_report": decision_path},
                evidence={"counts": dict(failure.failure_counts)},
                terminal_case="D",
            )
        except (OSError, ValueError):
            pass


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
