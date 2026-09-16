"""Authorization-gated T092 413-start formal telemetry command surface.

Preparation and finalization are native-free.  ``run-shard`` deliberately
requires an exact formal authorization and an explicitly injected runner; the
repository ships no command that can silently start a formal collection.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t092_formal_execution import (
    T092_FORMAL_EVIDENCE_SCHEMA_ID,
    T092_FORMAL_SHARD_SCHEMA_ID,
    build_t092_formal_authorization_template,
    execute_t092_authorized_formal_shard,
    finalize_t092_formal_shards,
    write_t092_formal_json,
)
from sts_combat_rl.commands.t092_formal_runtime import build_t092_formal_restore_payloads
from sts_combat_rl.commands.t092_canary_runtime import T092_CANARY_ARM_PROCESS_SPECS


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(path: Path, label: str) -> dict[str, Any]:
    value = _read(path)
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return value


def _within(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("T092 formal output must remain below the retention root") from exc


def _runner(spec: str, inputs: dict[str, Any], head: str, root: Path):
    if spec != "sts_combat_rl.commands.t092_formal_runtime:t092_formal_runtime":
        raise ValueError("T092 formal runner factory is not the approved runtime recipe")
    module_name, function = spec.split(":", 1)
    factory = getattr(importlib.import_module(module_name), function)
    return factory(input_identities=inputs, implementation_head=head, output_root=root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sts_combat_rl.commands.t092_formal")
    commands = parser.add_subparsers(dest="operation", required=True)
    compact = commands.add_parser("prepare-restore-inputs")
    compact.add_argument("--implementation-head", required=True)
    compact.add_argument("--upstream-identities", type=Path, required=True)
    compact.add_argument("--artifact-root", type=Path, required=True)
    compact.add_argument("--manifest-output", type=Path, required=True)
    compact.add_argument("--runtime-input-identities-output", type=Path, required=True)
    for name in ("prepare-authorization", "run-shard", "finalize"):
        item = commands.add_parser(name)
        item.add_argument("--implementation-head", required=True)
        item.add_argument("--split-manifest", type=Path, required=True)
        item.add_argument("--root-reference", type=Path, required=True)
        item.add_argument("--canary-evidence-reference", type=Path, required=True)
        item.add_argument("--input-identities", type=Path, required=True)
        item.add_argument("--artifact-root", type=Path, required=True)
        item.add_argument("--output", type=Path, required=True)
    commands.choices["prepare-authorization"].add_argument("--shard-count", type=int, default=8)
    commands.choices["prepare-authorization"].add_argument("--worker-count", type=int, default=8)
    run = commands.choices["run-shard"]
    run.add_argument("--authorization", type=Path, required=True)
    run.add_argument("--shard-index", type=int, required=True)
    run.add_argument("--shard-count", type=int, default=8)
    run.add_argument("--worker-count", type=int, default=8)
    run.add_argument("--runtime-factory", required=True)
    finalize = commands.choices["finalize"]
    finalize.add_argument("--authorization", type=Path, required=True)
    finalize.add_argument("--shard", type=Path, action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.operation == "prepare-restore-inputs":
        _within(args.manifest_output, args.artifact_root)
        _within(args.runtime_input_identities_output, args.artifact_root)
        upstream = _mapping(args.upstream_identities, "formal upstream identities")
        manifest, payloads = build_t092_formal_restore_payloads(
            implementation_head=args.implementation_head,
            upstream_identities=upstream,
        )
        for ordinal, (source_identity, payload) in enumerate(sorted(payloads.items())):
            path = args.artifact_root / "restore-inputs" / f"{ordinal:03d}.json"
            manifest["sources"][source_identity] = write_t092_formal_json(
                path, payload, schema_id=payload["schema_id"]
            )
        manifest_reference = write_t092_formal_json(
            args.manifest_output, manifest, schema_id=manifest["schema_id"]
        )
        runtime_inputs = {
            "formal_restore_manifest": manifest_reference,
            "arm_process_specs": {"ON": T092_CANARY_ARM_PROCESS_SPECS["ON"]},
            **upstream,
        }
        write_t092_formal_json(
            args.runtime_input_identities_output,
            runtime_inputs,
            schema_id="t092-formal-runtime-input-identities-v1",
        )
        return 0
    _within(args.output, args.artifact_root)
    split = _mapping(args.split_manifest, "split manifest")
    reference = _mapping(args.root_reference, "root reference")
    canary = _mapping(args.canary_evidence_reference, "canary evidence reference")
    inputs = _mapping(args.input_identities, "formal input identities")
    if args.operation == "prepare-authorization":
        prepared = build_t092_formal_authorization_template(implementation_head=args.implementation_head,
            split_manifest=split, root_reference=reference, canary_evidence=canary, input_identities=inputs,
            output_root=args.artifact_root, shard_count=args.shard_count, worker_count=args.worker_count)
        write_t092_formal_json(args.output, prepared, schema_id=prepared["schema_id"])
        return 0
    authorization = _mapping(args.authorization, "formal authorization")
    if args.operation == "run-shard":
        runner = _runner(args.runtime_factory, inputs, args.implementation_head, args.artifact_root)
        shard = execute_t092_authorized_formal_shard(authorization=authorization, implementation_head=args.implementation_head,
            split_manifest=split, root_reference=reference, canary_evidence=canary, input_identities=inputs,
            output_root=args.artifact_root, shard_index=args.shard_index, shard_count=args.shard_count,
            worker_count=args.worker_count, runner=runner)
        write_t092_formal_json(args.output, shard, schema_id=T092_FORMAL_SHARD_SCHEMA_ID)
        return 0
    shards = [_mapping(path, "formal shard") for path in args.shard]
    evidence = finalize_t092_formal_shards(authorization=authorization, implementation_head=args.implementation_head,
        split_manifest=split, root_reference=reference, canary_evidence=canary, input_identities=inputs,
        output_root=args.artifact_root, shards=shards)
    write_t092_formal_json(args.output, evidence, schema_id=T092_FORMAL_EVIDENCE_SCHEMA_ID)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
