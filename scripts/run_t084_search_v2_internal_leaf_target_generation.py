#!/usr/bin/env python3
"""Run the bounded T084 internal-leaf target-generation audit.

The native collector input is intentionally explicit.  The accepted native
baseline has no restorable internal-leaf surface, so omitting ``--collector``
produces a report classified ``INCOMPLETE`` rather than fabricating leaves from
T079 public/digest telemetry.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    RETENTION_SCHEMA_ID,
    SCHEMA_ID,
    audit_t084,
    sha256_file,
)


def main() -> int:
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
        "--t083-report",
        type=Path,
        default=Path(
            "/mnt/d/DeadlyCatCoding/STSRL/artifacts/t083-battle-search-v2-leaf-value-target-contract/t083-battle-search-v2-leaf-value-target-contract-v1.json"
        ),
    )
    parser.add_argument(
        "--native-root",
        type=Path,
        default=Path("/home/lsmft/stsrl-spikes/sts_lightspeed-t079-native"),
    )
    parser.add_argument("--collector", type=Path)
    parser.add_argument("--native-runtime-ref")
    parser.add_argument("--native-runtime-commit")
    parser.add_argument("--native-build")
    parser.add_argument("--native-abi")
    parser.add_argument("--native-verifier-result")
    parser.add_argument("--native-probe-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retention-manifest", type=Path)
    args = parser.parse_args()

    started = time.monotonic()
    native_probe = None
    if args.native_probe_report:
        native_probe = json.loads(args.native_probe_report.read_text(encoding="utf-8"))
    result = audit_t084(
        args.t064_root,
        args.t082_report,
        args.t083_report,
        args.output,
        repo_root=Path(__file__).resolve().parents[1],
        native_root=args.native_root,
        collector=args.collector,
        native_runtime_ref=args.native_runtime_ref,
        native_runtime_commit=args.native_runtime_commit,
        native_build=args.native_build,
        native_abi=args.native_abi,
        native_verifier_result=args.native_verifier_result,
        native_probe=native_probe,
    )
    wall_clock_seconds = time.monotonic() - started
    manifest_path = args.retention_manifest or args.output.with_name(
        "t084-retention-manifest-v1.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])
    manifest = {
        "schema_id": RETENTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T084",
        "report_schema_id": SCHEMA_ID,
        "classification": result["classification"],
        "recommendation": result["recommendation"],
        "inputs": {
            "t064_root": str(args.t064_root),
            "t082_report": {
                "path": str(args.t082_report),
                "sha256": result["accepted_inputs"]["t082_report"].get("sha256"),
            },
            "t083_report": {
                "path": str(args.t083_report),
                "sha256": result["accepted_inputs"]["t083_report"].get("sha256"),
            },
            "collector": {
                "path": str(args.collector) if args.collector else None,
                "sha256": sha256_file(args.collector)
                if args.collector and args.collector.exists()
                else None,
                "schema_id": "t084-native-internal-leaf-collector-v1",
            },
            "accepted_artifact_evidence": {
                "t064_artifacts": result["accepted_inputs"]["t064"]["artifact_checks"],
                "t064_pools": result["accepted_inputs"]["t064"].get("pool_checks", []),
                "t064_static_checkpoints": result["accepted_inputs"]["t064"].get(
                    "static_checkpoints", {}
                ),
                "t082": result["accepted_inputs"]["t082_report"],
                "t083": result["accepted_inputs"]["t083_report"],
            },
        },
        "outputs": {
            "report": {
                "path": str(args.output),
                "schema_id": SCHEMA_ID,
                "bytes": args.output.stat().st_size,
                "sha256": sha256_file(args.output),
            },
        },
        "code_identity": result["identity"]["code"],
        "native_identity": result["identity"]["native"],
        "native_probe": result["identity"]["native_probe"],
        "execution": {
            "mode": "offline_collector_contract",
            "worker_count": result["execution"].get("worker_count", 16),
            "effective_worker_count": result["execution"].get(
                "effective_worker_count", 0
            ),
            "shards": result["execution"].get("shards", []),
            "wall_clock_seconds": wall_clock_seconds,
            "command": command,
            "failure_policy": "missing/conflicting collector evidence is INCOMPLETE",
        },
        "retention": {
            "root": str(manifest_path.parent),
            "raw_full_state_policy": "outside Git; retain until T084 acceptance and downstream review close",
            "deletion_condition": "delete raw collector/full-state payloads only after T084 is accepted and no downstream paired repair audit requires this provenance",
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "report": str(args.output),
                "retention_manifest": str(manifest_path),
                "wall_clock_seconds": wall_clock_seconds,
            },
            sort_keys=True,
        )
    )
    return 0 if result["classification"] != "INCOMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
