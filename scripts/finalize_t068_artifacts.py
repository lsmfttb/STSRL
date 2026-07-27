#!/usr/bin/env python3
"""Write the stable ignored retention manifest for a closed T068 audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--decision-report", type=Path, required=True)
    parser.add_argument("--feasibility-report", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--stage-execution-report", type=Path, required=True)
    parser.add_argument("--native-source-audit", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--regeneration-output-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    _verify_source_checkout(args.source_checkout, args.code_commit)
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
    feasibility = _load(
        args.feasibility_report, "t068-native-boundary-batch-feasibility-v1"
    )
    semantic = _load(
        args.semantic_report, "t068-native-boundary-semantic-equivalence-v1"
    )
    stage_execution = _load(
        args.stage_execution_report, "t068-native-boundary-stage-execution-v1"
    )
    source = _load(args.native_source_audit, "t068-native-callback-source-audit-v1")
    input_manifest_sha = hashlib.sha256(args.input_manifest.read_bytes()).hexdigest()
    if (
        input_manifest_sha
        != "2119e36bccff86fd65f00474177d11bb222a05303651dc18423de7f1174d35da"
    ):
        raise SystemExit("T068 finalizer requires the exact accepted T067 manifest")
    reports = (audit, feasibility, decision, semantic, stage_execution)
    if any(value.get("code_commit") != args.code_commit for value in reports):
        raise SystemExit("T068 finalizer report code commit mismatch")
    if any(
        value.get("native_commit") != "3cb9ebecb87c38044b34aa0e013d42b222a04087"
        for value in reports
    ):
        raise SystemExit("T068 finalizer report native commit mismatch")
    if any(
        value.get("input_identities") != audit.get("input_identities")
        for value in (feasibility, decision)
    ):
        raise SystemExit("T068 finalizer report input identity mismatch")
    if audit.get("command_passed") is not True or not audit.get("input_identities"):
        raise SystemExit("T068 finalizer audit is incomplete")
    audit_stage = stage_execution.get("stages", {}).get(
        "callback_dependency_audit_0_16", {}
    )
    if audit_stage.get("worker_count") != 16 or audit_stage.get("shard_count") != 16:
        raise SystemExit("T068 finalizer stage execution layout mismatch")
    if source.get("native_commit") != "3cb9ebecb87c38044b34aa0e013d42b222a04087":
        raise SystemExit("T068 finalizer native commit mismatch")
    if (
        audit["feasibility_gate"]["passed"] is not False
        or decision["calibration_authorized"]
        or feasibility.get("calibration_authorized")
        or semantic.get("command_passed") is not True
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
                    "schema_id": _artifact_schema(path),
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
        "feasibility": feasibility,
        "semantic_equivalence": semantic,
        "stage_execution": stage_execution,
        "decision": decision,
        "retention_reason": "retain complete fail-closed callback evidence and measured feature-encoding costs before public-node feature projection is considered",
        "downstream_consumers": [
            "T069-public-node-feature-encoding-projection-feasibility"
        ],
        "raw_artifacts_may_be_deleted_when": "after the named feature-encoding projection follow-up is accepted or superseded and the maintainer confirms no retained trace is needed",
        "large_artifacts_committed_to_git": False,
        "regeneration_commands": [
            "set -euo pipefail; source_repo=/mnt/d/DeadlycatCoding/STSRL; source_checkout="
            + source_checkout
            + "; output_root="
            + output
            + "; code_commit="
            + args.code_commit
            + '; test ! -e "$output_root"; if [ -e "$source_checkout" ]; then test "$(git -c safe.directory="$source_checkout" -C "$source_checkout" rev-parse HEAD)" = "$code_commit"; test -z "$(git -c safe.directory="$source_checkout" -C "$source_checkout" status --porcelain)"; else git -c safe.directory="$source_repo" -C "$source_repo" worktree add --detach "$source_checkout" "$code_commit"; fi; mkdir -p "$output_root"',
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
            + "/t068-native-source-audit.json > "
            + output
            + "/source-audit.stdout.log 2> "
            + output
            + "/source-audit.stderr.log",
            "cd "
            + source_checkout
            + " && audit_started=$(date +%s.%N); pids=(); for i in $(seq 0 15); do (PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313:"
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/run_t068_callback_dependency_audit.py --cohort /mnt/d/DeadlycatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl --checkpoint /mnt/d/DeadlycatCoding/STSRL/artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt --t061-retention-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t061-a20-reachability-bottleneck-decomposition/t061-retention-manifest.json --preflight-output "
            + output
            + "/preflight-$i.json --output "
            + output
            + "/shard-$i.json --code-commit "
            + args.code_commit
            + ' --record-range "$i:$((i+1))" --shard-index "$i" > "'
            + output
            + '/shard-$i.stdout.log" 2> "'
            + output
            + '/shard-$i.stderr.log; status=$?; printf "%s\\n" "$status" > "'
            + output
            + '/shard-$i.exit-code"; exit "$status") & pids+=("$!"); done; failed=0; for pid in "${pids[@]}"; do wait "$pid" || failed=1; done; audit_finished=$(date +%s.%N); python3 -c "import sys; print(float(sys.argv[2])-float(sys.argv[1]))" "$audit_started" "$audit_finished" > "'
            + output
            + '/audit-stage-wall-clock-seconds.txt"; exit "$failed"',
            "cd "
            + source_checkout
            + " && args=(); for i in $(seq 0 15); do args+=(--shard "
            + output
            + "/shard-$i.json); done; PYTHONPATH="
            + source_checkout
            + '/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/merge_t068_callback_dependency_audit.py "${args[@]}" --input-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t067-battle-search-v2-inference-cost-repair/reproduction-ea47ee9/t067-retention-manifest.json --native-source-audit '
            + output
            + "/t068-native-source-audit.json --code-commit "
            + args.code_commit
            + " --audit-output "
            + output
            + "/t068-callback-dependency-audit.json --feasibility-output "
            + output
            + "/t068-feasibility-report.json --decision-output "
            + output
            + "/t068-decision-report.json > "
            + output
            + "/merge.stdout.log 2> "
            + output
            + "/merge.stderr.log",
            "cd "
            + source_checkout
            + " && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313:"
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/verify_t068_semantic_equivalence.py --cohort /mnt/d/DeadlycatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl --checkpoint /mnt/d/DeadlycatCoding/STSRL/artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt --t061-retention-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t061-a20-reachability-bottleneck-decomposition/t061-retention-manifest.json --preflight-output "
            + output
            + "/semantic-preflight.json --output "
            + output
            + "/t068-semantic-equivalence.json --code-commit "
            + args.code_commit
            + " > "
            + output
            + "/semantic.stdout.log 2> "
            + output
            + "/semantic.stderr.log",
            "cd "
            + source_checkout
            + " && args=(); for i in $(seq 0 15); do args+=(--shard "
            + output
            + "/shard-$i.json --shard-stdout "
            + output
            + "/shard-$i.stdout.log --shard-stderr "
            + output
            + "/shard-$i.stderr.log --shard-exit-code "
            + output
            + "/shard-$i.exit-code); done; PYTHONPATH="
            + source_checkout
            + '/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/build_t068_stage_execution.py "${args[@]}" --audit-stage-wall-clock-seconds "$(cat '
            + output
            + '/audit-stage-wall-clock-seconds.txt)" --semantic-report '
            + output
            + "/t068-semantic-equivalence.json --semantic-stdout "
            + output
            + "/semantic.stdout.log --semantic-stderr "
            + output
            + "/semantic.stderr.log --output "
            + output
            + "/t068-stage-execution.json",
            "cd "
            + source_checkout
            + " && PYTHONPATH="
            + source_checkout
            + "/src /home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 scripts/finalize_t068_artifacts.py --artifact-root "
            + str(root)
            + " --input-manifest /mnt/d/DeadlycatCoding/STSRL/artifacts/t067-battle-search-v2-inference-cost-repair/reproduction-ea47ee9/t067-retention-manifest.json --audit-report "
            + output
            + "/t068-callback-dependency-audit.json --feasibility-report "
            + output
            + "/t068-feasibility-report.json --semantic-report "
            + output
            + "/t068-semantic-equivalence.json --stage-execution-report "
            + output
            + "/t068-stage-execution.json --decision-report "
            + output
            + "/t068-decision-report.json --native-source-audit "
            + output
            + "/t068-native-source-audit.json --code-commit "
            + args.code_commit
            + " --source-checkout "
            + source_checkout
            + " --regeneration-output-root "
            + output
            + " > "
            + output
            + "/finalizer.stdout.log 2> "
            + output
            + "/finalizer.stderr.log",
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


def _artifact_schema(path: Path) -> str:
    if path.suffix != ".json":
        return "text-log-v1"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unparsed-json-v1"
    if isinstance(value, dict) and isinstance(value.get("schema_id"), str):
        return value["schema_id"]
    return "json-without-schema-v1"


def _verify_source_checkout(path: Path, code_commit: str) -> None:
    try:
        verify_exact_git_checkout(path, code_commit)
    except ValueError as exc:
        raise SystemExit(f"T068 finalizer {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
