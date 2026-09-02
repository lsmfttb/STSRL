#!/usr/bin/env python3
"""Run the bounded T083 leaf-value target-contract audit."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts_combat_rl.t083_battle_search_v2_leaf_value_target_contract import (
    EXPECTED_MAIN_COMMIT,
    SCHEMA_ID,
    audit_t083,
    sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--t064-root",
        type=Path,
        default=Path(
            "/mnt/d/DeadlyCatCoding/STSRL/artifacts/t064-later-act-curriculum-transfer"
        ),
    )
    parser.add_argument(
        "--t082-report",
        type=Path,
        default=Path(
            "/mnt/d/DeadlyCatCoding/STSRL/artifacts/t082-value-target-semantic-closure/t082-value-target-semantic-closure-v1.json"
        ),
    )
    parser.add_argument(
        "--native-root",
        type=Path,
        default=Path("/home/lsmft/stsrl-spikes/sts_lightspeed"),
    )
    parser.add_argument("--code-commit", default=EXPECTED_MAIN_COMMIT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retention-manifest", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    started = time.monotonic()
    result = audit_t083(
        args.t064_root,
        args.t082_report,
        args.output,
        repo_root=Path(__file__).resolve().parents[1],
        native_root=args.native_root,
        code_commit=args.code_commit,
    )
    wall_seconds = time.monotonic() - started
    retention = args.retention_manifest or args.output.with_name(
        "t083-retention-manifest-v1.json"
    )
    retention.parent.mkdir(parents=True, exist_ok=True)
    command = " ".join(shlex.quote(item) for item in __import__("sys").argv)
    accepted_inputs = result.get("accepted_inputs", {})
    t064_details = accepted_inputs.get("t064", {})
    manifest = {
        "schema_id": "t083-retention-manifest-v1",
        "schema_version": 1,
        "task_id": "T083",
        "report_schema_id": SCHEMA_ID,
        "classification": result.get("classification"),
        "recommendation": result.get("recommendation"),
        "producer": {
            "code_commit": result.get("identity", {}).get("stsrl_main_resolved_commit"),
            "code_ref": result.get("identity", {}).get("stsrl_main_ref"),
            "native_commit": result.get("identity", {}).get("native_commit"),
            "native_ref": result.get("identity", {}).get("native_resolved_ref"),
            "native_resolved_commit": result.get("identity", {}).get(
                "native_resolved_commit"
            ),
            "native_root": str(args.native_root),
        },
        "inputs": {
            "t064_root": str(args.t064_root),
            "t082_report": str(args.t082_report),
            "t082_report_sha256": result.get("identity", {}).get("t082_report_sha256"),
            "artifacts": {
                "t082_report": accepted_inputs.get("t082"),
                "t064_compact_and_scale": t064_details.get("artifact_checks", []),
                "teacher": accepted_inputs.get("teacher"),
                "trainer": accepted_inputs.get("trainer"),
                "t042_pools": t064_details.get("pool_checks", []),
            },
        },
        "outputs": {
            "report": {
                "path": str(args.output),
                "schema_id": SCHEMA_ID,
                "bytes": args.output.stat().st_size,
                "sha256": sha256(args.output),
            }
        },
        "regeneration_command": command,
        "execution": {
            "mode": "offline_streaming",
            "worker_count": 1,
            "worker_reason": "non-simulator artifact audit; bounded single stream",
            "large_pool_hash_policy": "accepted_T064_manifest_identity_plus_size",
            "large_pool_scan_policy": "not_reopened; selected 460-row source contract is represented by accepted complete identities",
            "wall_clock_seconds": wall_seconds,
        },
        "deletion_condition": "retain while T083 evidence is a dependency; delete only after all successor audits no longer require the report and its provenance manifest",
    }
    retention.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "classification": result.get("classification"),
                "report": str(args.output),
                "retention_manifest": str(retention),
                "wall_clock_seconds": wall_seconds,
            },
            sort_keys=True,
        )
    )
    return 0 if result.get("classification") != "INCOMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
