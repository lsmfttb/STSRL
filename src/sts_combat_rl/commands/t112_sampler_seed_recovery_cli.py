"""CLI for the separately qualified and authorized T112 recovery stages."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sts_combat_rl.commands.t112_sampler_seed_recovery import (
    T112WorkflowError,
    execute_t112_authorized_cohort,
    execute_t112_witness,
    finalize_t112_execution,
    finalize_t112_witness,
    prepare_t112_inputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--t101-retention-manifest", type=Path, required=True)
    prepare.add_argument("--t111-retention-manifest", type=Path, required=True)
    prepare.add_argument("--native-source-manifest", type=Path, required=True)
    prepare.add_argument("--artifact-root", type=Path, required=True)
    prepare.add_argument("--repo-root", type=Path, required=True)

    witness = subparsers.add_parser("witness")
    witness.add_argument("--authorization", type=Path, required=True)
    witness.add_argument("--qualification", type=Path, required=True)
    witness.add_argument("--readiness", type=Path, required=True)
    witness.add_argument("--resource-status", type=Path, required=True)
    witness.add_argument("--t101-retention-manifest", type=Path, required=True)
    witness.add_argument("--output-root", type=Path, required=True)
    witness.add_argument("--repo-root", type=Path, required=True)

    witness_finalize = subparsers.add_parser("finalize-witness")
    witness_finalize.add_argument("--output-root", type=Path, required=True)
    witness_finalize.add_argument("--resource-status", type=Path, required=True)

    execute = subparsers.add_parser("execute")
    execute.add_argument("--authorization", type=Path, required=True)
    execute.add_argument("--qualification", type=Path, required=True)
    execute.add_argument("--readiness", type=Path, required=True)
    execute.add_argument("--witness-terminal", type=Path, required=True)
    execute.add_argument("--resource-status", type=Path, required=True)
    execute.add_argument("--t101-retention-manifest", type=Path, required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    execute.add_argument("--repo-root", type=Path, required=True)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--resource-status", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_t112_inputs(
                t101_retention_manifest_path=args.t101_retention_manifest,
                t111_retention_manifest_path=args.t111_retention_manifest,
                current_native_source_manifest_path=args.native_source_manifest,
                artifact_root=args.artifact_root,
                repo_root=args.repo_root,
            )
            state = "PREPARED"
        elif args.command == "witness":
            result = execute_t112_witness(
                authorization_path=args.authorization,
                qualification_path=args.qualification,
                readiness_path=args.readiness,
                resource_status_path=args.resource_status,
                t101_manifest_path=args.t101_retention_manifest,
                witness_output_root=args.output_root,
                repo_root=args.repo_root,
            )
            state = "WITNESS_RECORDED"
        elif args.command == "finalize-witness":
            result = finalize_t112_witness(
                witness_output_root=args.output_root,
                resource_status_path=args.resource_status,
            )
            state = "WITNESS_FINALIZED"
        elif args.command == "execute":
            result = execute_t112_authorized_cohort(
                authorization_path=args.authorization,
                qualification_path=args.qualification,
                readiness_path=args.readiness,
                witness_terminal_path=args.witness_terminal,
                resource_status_path=args.resource_status,
                t101_manifest_path=args.t101_retention_manifest,
                cohort_output_root=args.output_root,
                repo_root=args.repo_root,
            )
            state = "COHORT_EXECUTION_COMPLETE"
        else:
            result = finalize_t112_execution(
                cohort_output_root=args.output_root,
                resource_status_path=args.resource_status,
            )
            state = "FINALIZED"
    except (
        OSError,
        T112WorkflowError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        print(
            json.dumps({"state": "INCOMPLETE", "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"state": state, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
