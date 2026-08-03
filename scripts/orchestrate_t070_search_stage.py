#!/usr/bin/env python3
"""Run one T070 stage with exactly 16 explicit WSL worker processes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from typing import Any

from sts_combat_rl.commands.t070_search_v2_audit import (
    HIGH_BUDGET_RANGES,
    PRIMARY_RANGES,
    STAGE_DETAIL_SCHEMA_ID,
    merge_single_arm_stage,
    validate_t070_frozen_stage,
    validate_t070_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--stage-name", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument(
        "--range-kind", choices=("primary", "high_budget"), required=True
    )
    parser.add_argument("--tree-geometry", action="store_true")
    parser.add_argument("--native-checkout", type=Path, required=True)
    parser.add_argument("--native-build-root", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T070 stage requires exact code commit")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.stage_name):
        raise SystemExit("T070 stage name is unsafe")
    repo = args.repo_root.resolve()
    artifact = args.artifact_root.resolve()
    inputs = args.input_root.resolve()
    stage_parent = "primary" if args.range_kind == "primary" else "high-budget"
    stage = artifact / stage_parent / args.stage_name
    if stage.exists():
        raise SystemExit("T070 stage refuses to overwrite output")
    ranges = PRIMARY_RANGES if args.range_kind == "primary" else HIGH_BUDGET_RANGES
    cohort = (
        inputs
        / "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr"
        / "t052-fixed-cohort.jsonl"
        if args.range_kind == "primary"
        else artifact / "budget-subset" / "t070-budget-subset-cohort.jsonl"
    )
    checkpoint = (
        inputs
        / "t044-de-assisted-comparison-pr"
        / "t043-assist_0-smoke"
        / "t043-assist_0-smoke-checkpoint.pt"
    )
    frozen = artifact / "frozen-manifest" / "t070-frozen-manifest.json"
    preflight = artifact / "native-preflight" / "t070-native-capability-preflight.json"
    source_manifest = repo / "docs" / "sts_lightspeed_source_manifest.json"
    source_verifier = repo / "scripts" / "verify_lightspeed_source.sh"
    native_build_root = args.native_build_root.resolve()
    sys.path.insert(0, str(native_build_root))
    try:
        preflight_report = validate_t070_preflight(
            preflight,
            code_commit=args.code_commit,
            source_manifest_path=source_manifest,
            source_verifier_path=source_verifier,
            native_checkout=args.native_checkout,
            native_build_root=native_build_root,
        )
    finally:
        sys.path.remove(str(native_build_root))
    native_runtime_identity = preflight_report["native_runtime_identity"]
    _, frozen_ranges = validate_t070_frozen_stage(
        frozen,
        code_commit=args.code_commit,
        stage_name=args.stage_name,
        arm=args.arm,
        family=args.family,
        budget=args.budget,
        range_kind=args.range_kind,
        tree_geometry=args.tree_geometry,
        cohort_path=cohort,
        checkpoint_path=checkpoint,
        source_manifest_path=source_manifest,
        source_verifier_path=source_verifier,
    )
    if tuple(ranges) != tuple(frozen_ranges):
        raise SystemExit(
            "T070 orchestrator range topology differs from frozen manifest"
        )
    stage.mkdir(parents=True)
    logs = stage / "logs"
    logs.mkdir()
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{native_build_root}:{repo / 'src'}"
    workers: list[dict[str, Any]] = []
    processes = []
    started = perf_counter()
    started_at = _now()
    for index, record_range in enumerate(ranges):
        command = [
            sys.executable,
            str(repo / "scripts" / "run_t070_search_stage_shard.py"),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--frozen-manifest",
            str(frozen),
            "--native-preflight",
            str(preflight),
            "--native-checkout",
            str(args.native_checkout.resolve()),
            "--native-build-root",
            str(native_build_root),
            "--output",
            str(stage / f"shard-{index:02d}.json"),
            "--code-commit",
            args.code_commit,
            "--stage-name",
            args.stage_name,
            "--arm",
            args.arm,
            "--family",
            args.family,
            "--budget",
            str(args.budget),
            "--record-range",
            record_range,
            "--shard-index",
            str(index),
            "--range-kind",
            args.range_kind,
        ]
        if args.tree_geometry:
            command.append("--tree-geometry")
        stdout_path = logs / f"shard-{index:02d}.stdout.log"
        stderr_path = logs / f"shard-{index:02d}.stderr.log"
        stdout = stdout_path.open("wb")
        stderr = stderr_path.open("wb")
        process = subprocess.Popen(
            command, cwd=repo, env=env, stdout=stdout, stderr=stderr
        )
        processes.append((process, stdout, stderr))
        workers.append(
            {
                "worker_index": index,
                "record_range": record_range,
                "command": command,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            }
        )
    failed = False
    for worker, (process, stdout, stderr) in zip(workers, processes, strict=True):
        code = process.wait()
        stdout.close()
        stderr.close()
        worker["returncode"] = code
        if code == 0:
            shard_payload = json.loads(
                (stage / f"shard-{worker['worker_index']:02d}.json").read_text(
                    encoding="utf-8"
                )
            )
            worker["native_runtime_identity"] = shard_payload.get(
                "native_runtime_identity"
            )
            failed |= worker["native_runtime_identity"] != native_runtime_identity
        failed |= code != 0
    merged_path = stage / "merged.json"
    if not failed:
        merged = merge_single_arm_stage(
            shard_paths=[stage / f"shard-{index:02d}.json" for index in range(16)],
            expected_ranges=ranges,
            expected_record_count=93 if args.range_kind == "primary" else 16,
            output_path=merged_path,
        )
        failed |= merged.get("command_passed") is not True
    execution = {
        "schema_id": STAGE_DETAIL_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "stage_name": args.stage_name,
        "stage_kind": args.range_kind,
        "arm": args.arm,
        "family": args.family,
        "native_budget": args.budget,
        "tree_geometry_enabled": args.tree_geometry,
        "code_commit": args.code_commit,
        "native_commit": "fee272f1ae21c283ad2161f55293cfe6d714134a",
        "record_ranges": list(ranges),
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "host_logical_cpu_count": os.cpu_count(),
        "python_executable": sys.executable,
        "native_source_checkout": str(args.native_checkout.resolve()),
        "native_build_root": str(native_build_root),
        "native_runtime_identity": native_runtime_identity,
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "stage_wall_clock_seconds": perf_counter() - started,
        "workers": workers,
        "merged_report": str(merged_path),
        "command_passed": not failed,
    }
    (stage / "stage-execution.json").write_text(
        json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 1 if failed else 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
