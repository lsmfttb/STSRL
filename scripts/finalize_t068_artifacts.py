#!/usr/bin/env python3
"""Write the stable ignored retention manifest for a closed T068 audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--decision-report", type=Path, required=True)
    parser.add_argument("--native-source-audit", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--regeneration-output-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    if ".claude" in root.parts or "worktrees" in root.parts:
        raise SystemExit("T068 retention root must not be a disposable worktree")
    if (
        not str(root)
        .replace("\\", "/")
        .endswith(
            "/artifacts/t068-native-boundary-batched-inference-feasibility/" + root.name
        )
    ):
        raise SystemExit("T068 retention root is outside its stable ignored namespace")
    manifest_path = root / "t068-retention-manifest.json"
    if manifest_path.exists():
        raise SystemExit("T068 refuses to overwrite retention manifest")
    audit = _load(
        args.audit_report, "t068-native-boundary-callback-dependency-audit-v1"
    )
    decision = _load(args.decision_report, "t068-native-boundary-batch-decision-v1")
    source = _load(args.native_source_audit, "t068-native-callback-source-audit-v1")
    if (
        audit["feasibility_gate"]["passed"] is not False
        or decision["calibration_authorized"]
    ):
        raise SystemExit("T068 finalizer only accepts the published infeasibility exit")
    indexed = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != manifest_path:
            indexed.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    output = args.regeneration_output_root.as_posix()
    source_checkout = args.source_checkout.as_posix()
    payload = {
        "schema_id": "t068-native-boundary-retention-manifest-v1",
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": args.code_commit,
        "native_commit": source["native_commit"],
        "stable_retention_root": str(root),
        "artifact_count": len(indexed),
        "artifact_total_bytes": sum(item["bytes"] for item in indexed),
        "artifacts": indexed,
        "input_identities": audit["input_identities"],
        "native_source_audit": {
            "path": args.native_source_audit.name,
            "sha256": hashlib.sha256(args.native_source_audit.read_bytes()).hexdigest(),
        },
        "decision": decision,
        "retention_reason": "retain complete fail-closed callback dependency evidence before any native callback ABI redesign is considered",
        "downstream_consumers": [
            "T069-native-search-callback-abi-redesign-feasibility"
        ],
        "raw_artifacts_may_be_deleted_when": "after the named follow-up is accepted or superseded and the maintainer confirms no retained trace is needed for ABI review",
        "large_artifacts_committed_to_git": False,
        "regeneration_commands": [
            "set -euo pipefail; source_repo=/mnt/d/DeadlycatCoding/STSRL; source_checkout="
            + source_checkout
            + "; output_root="
            + output
            + "; code_commit="
            + args.code_commit
            + '; test ! -e "$output_root"; if [ -e "$source_checkout" ]; then test "$(git -C "$source_checkout" rev-parse HEAD)" = "$code_commit"; test -z "$(git -C "$source_checkout" status --porcelain)"; else git -C "$source_repo" worktree add --detach "$source_checkout" "$code_commit"; fi; mkdir -p "$output_root"',
            "cd "
            + source_checkout
            + " && STSRL_LIGHTSPEED_BUILD_JOBS=16 bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed > "
            + output
            + "/pinned-source-verifier.log 2>&1",
            "cd "
            + source_checkout
            + " && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313:"
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/audit_t068_native_callback_source.py --native-repository /home/lsmft/stsrl-spikes/sts_lightspeed --output "
            + output
            + "/t068-native-source-audit.json",
            "cd "
            + source_checkout
            + " && (for i in $(seq 0 15); do PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313:"
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/run_t068_callback_dependency_audit.py --cohort /mnt/d/DeadlycatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl --checkpoint /mnt/d/DeadlycatCoding/STSRL/artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt --t061-retention-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t061-a20-reachability-bottleneck-decomposition/t061-retention-manifest.json --preflight-output "
            + output
            + "/preflight-$i.json --output "
            + output
            + "/shard-$i.json --code-commit "
            + args.code_commit
            + ' --record-range "$i:$((i+1))" --shard-index "$i" & done; wait)',
            "cd "
            + source_checkout
            + " && PYTHONPATH="
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/merge_t068_callback_dependency_audit.py $(for i in $(seq 0 15); do printf -- '--shard "
            + output
            + '/shard-%s.json \' "$i"; done) --input-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t067-battle-search-v2-inference-cost-repair/reproduction-ea47ee9/t067-retention-manifest.json --native-source-audit '
            + output
            + "/t068-native-source-audit.json --code-commit "
            + args.code_commit
            + " --audit-output "
            + output
            + "/t068-callback-dependency-audit.json --decision-output "
            + output
            + "/t068-decision-report.json",
        ],
        "command_passed": True,
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def _load(path: Path, schema_id: str) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_id") != schema_id:
        raise SystemExit(f"T068 wrong schema in {path}")
    return raw


if __name__ == "__main__":
    raise SystemExit(main())
