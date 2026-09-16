"""Path-bound command for a separately authorized T092 detached canary.

The readiness command remains file-only.  This command has a real shard mode,
but refuses to import its runtime factory until a signed exact-head
authorization has passed.  The factory is intentionally supplied by the
approved restore-input harness: this command does not guess or reconstruct
checkpoint maps from private bytes.
"""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t092_canary_runtime import (
    t092_canary_runtime_input_identities,
)
from sts_combat_rl.sim.t092_canary_process import T092IsolatedCanaryRunner
from sts_combat_rl.sim.t092_canary_execution import (
    T092_CANARY_EVIDENCE_SCHEMA_ID,
    T092_CANARY_SHARD_SCHEMA_ID,
    T092CanaryExecutionError,
    build_t092_canary_authorization_template,
    execute_t092_authorized_canary_shard,
    merge_t092_authorized_canary_shards,
    validate_t092_canary_authorization,
    write_t092_canary_json,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise T092CanaryExecutionError(f"{label} must be a JSON object")
    return value


def _within_root(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise T092CanaryExecutionError("T092 canary output must remain under output root") from exc


def _runtime_runner(
    factory_path: str, *, worker: Mapping[str, int], implementation_head: str,
    output_root: Path,
) -> T092IsolatedCanaryRunner:
    module_name, separator, attribute = factory_path.partition(":")
    if not separator or not module_name or not attribute:
        raise T092CanaryExecutionError("runtime factory must be module:callable")
    factory = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(factory):
        raise T092CanaryExecutionError("runtime factory is unavailable")
    runtime = factory()
    if not isinstance(runtime, Mapping) or set(runtime) != {
        "arm_process_specs",
        "source_records",
        "canonical_records",
    }:
        raise T092CanaryExecutionError("runtime factory did not supply isolated arm maps")
    return T092IsolatedCanaryRunner(
        arm_process_specs=runtime["arm_process_specs"],
        source_records=runtime["source_records"],
        canonical_records=runtime["canonical_records"],
        worker=worker,
        implementation_head=implementation_head,
        output_root=output_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sts_combat_rl.commands.t092_canary_execution")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare-authorization", "run-shard", "merge-shards"):
        command = commands.add_parser(name)
        command.add_argument("--implementation-head", required=True)
        command.add_argument("--split-manifest", type=Path, required=True)
        command.add_argument("--runtime-input-identities", type=Path, required=True)
        command.add_argument("--artifact-root", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    prepare = commands.choices["prepare-authorization"]
    prepare.set_defaults(mode="prepare")
    run = commands.choices["run-shard"]
    run.add_argument("--authorization", type=Path, required=True)
    run.add_argument("--runtime-factory", required=True)
    run.add_argument("--shard-index", type=int, required=True)
    run.set_defaults(mode="run")
    merge = commands.choices["merge-shards"]
    merge.add_argument("--authorization", type=Path, required=True)
    merge.add_argument("--shard", type=Path, action="append", required=True)
    merge.set_defaults(mode="merge")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    split = _object(_read_json(args.split_manifest), "split manifest")
    inputs = _object(_read_json(args.runtime_input_identities), "runtime input identities")
    if inputs != t092_canary_runtime_input_identities():
        raise T092CanaryExecutionError("T092 runtime input identity map is not the approved recipe")
    _within_root(args.output, args.artifact_root)
    if args.mode == "prepare":
        prepared = build_t092_canary_authorization_template(
            implementation_head=args.implementation_head,
            split_manifest=split,
            runtime_input_identities=inputs,
            output_root=args.artifact_root,
        )
        write_t092_canary_json(args.output, prepared, schema_id=prepared["schema_id"])
        return 0
    authorization = _object(_read_json(args.authorization), "authorization")
    # Validate before runtime import/adapter construction.  This is the command
    # boundary that prevents an accidental real simulator launch.
    validate_t092_canary_authorization(
        authorization,
        implementation_head=args.implementation_head,
        split_manifest=split,
        runtime_input_identities=inputs,
        output_root=args.artifact_root,
    )
    if args.mode == "run":
        if args.runtime_factory != "sts_combat_rl.commands.t092_canary_runtime:t092_canary_runtime":
            raise T092CanaryExecutionError("T092 canary runtime factory is not the approved recipe")
        worker = {
            "stage_worker_count": 12, "worker_index": args.shard_index,
            "shard_count": 12, "shard_index": args.shard_index,
        }
        runner = _runtime_runner(
            args.runtime_factory,
            worker=worker,
            implementation_head=args.implementation_head,
            output_root=args.artifact_root,
        )
        shard = execute_t092_authorized_canary_shard(
            authorization=authorization,
            implementation_head=args.implementation_head,
            split_manifest=split,
            runtime_input_identities=inputs,
            output_root=args.artifact_root,
            shard_index=args.shard_index,
            shard_count=12,
            worker_count=12,
            runner=runner,
        )
        write_t092_canary_json(args.output, shard, schema_id=T092_CANARY_SHARD_SCHEMA_ID)
        return 0
    evidence = merge_t092_authorized_canary_shards(
        authorization=authorization,
        implementation_head=args.implementation_head,
        split_manifest=split,
        runtime_input_identities=inputs,
        output_root=args.artifact_root,
        shards=[_object(_read_json(path), "T092 canary shard") for path in args.shard],
    )
    write_t092_canary_json(args.output, evidence, schema_id=T092_CANARY_EVIDENCE_SCHEMA_ID)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
