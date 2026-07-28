#!/usr/bin/env python3
"""Run one explicit T069 calibration candidate with 16 WSL workers."""

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

from sts_combat_rl.commands.t062_battle_search_v2 import (
    merge_t062_comparison_reports_from_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--candidate-name", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--baseline-budget", type=int, default=100)
    parser.add_argument("--arm-budget", action="append", required=True)
    parser.add_argument(
        "--native-build-root",
        type=Path,
        default=Path("/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313"),
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    artifact_root = args.artifact_root.resolve()
    input_root = args.input_root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T069 candidate requires exact code commit")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.candidate_name):
        raise SystemExit("T069 candidate name is unsafe")
    stage = artifact_root / "calibration" / args.candidate_name
    if stage.exists():
        raise SystemExit("T069 candidate refuses to overwrite stage")
    stage.mkdir(parents=True)
    logs = stage / "logs"
    logs.mkdir()
    cohort = (
        input_root
        / "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr"
        / "t052-fixed-cohort.jsonl"
    )
    checkpoint = (
        input_root
        / "t044-de-assisted-comparison-pr"
        / "t043-assist_0-smoke"
        / "t043-assist_0-smoke-checkpoint.pt"
    )
    t061 = (
        input_root
        / "t061-a20-reachability-bottleneck-decomposition"
        / "t061-retention-manifest.json"
    )
    t068 = (
        input_root
        / "t068-native-boundary-batched-inference-feasibility"
        / "reproduction-3dd14e3"
        / "t068-retention-manifest.json"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{args.native_build_root.resolve()}:{repo_root / 'src'}"
    workers: list[dict[str, Any]] = []
    processes: list[tuple[subprocess.Popen[bytes], Any, Any]] = []
    started = perf_counter()
    started_at = _now()
    for index in range(16):
        command = [
            sys.executable,
            str(repo_root / "scripts" / "run_t069_calibration_shard.py"),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--t061-retention-manifest",
            str(t061),
            "--t068-retention-manifest",
            str(t068),
            "--preflight-output",
            str(stage / f"preflight-{index:02d}.json"),
            "--output",
            str(stage / f"shard-{index:02d}.json"),
            "--code-commit",
            args.code_commit,
            "--record-range",
            f"{index}:{index + 1}",
            "--shard-index",
            str(index),
            "--baseline-budget",
            str(args.baseline_budget),
            "--family",
            args.family,
        ]
        for arm_budget in args.arm_budget:
            command.extend(["--arm-budget", arm_budget])
        stdout_path = logs / f"shard-{index:02d}.stdout.log"
        stderr_path = logs / f"shard-{index:02d}.stderr.log"
        stdout = stdout_path.open("wb")
        stderr = stderr_path.open("wb")
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
        processes.append((process, stdout, stderr))
        workers.append(
            {
                "worker_index": index,
                "record_range": f"{index}:{index + 1}",
                "command": command,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            }
        )
    failed = False
    for worker, (process, stdout, stderr) in zip(
        workers,
        processes,
        strict=True,
    ):
        code = process.wait()
        stdout.close()
        stderr.close()
        worker["returncode"] = code
        if code != 0:
            failed = True
    if not failed:
        merge_t062_comparison_reports_from_paths(
            shard_paths=[stage / f"shard-{index:02d}.json" for index in range(16)],
            output_path=stage / "merged.json",
            expected_record_count=16,
            bootstrap_resamples=2000,
        )
    report = {
        "schema_id": "t069-calibration-candidate-stage-v1",
        "schema_version": 1,
        "task_id": "T069",
        "candidate_name": args.candidate_name,
        "family": args.family,
        "arm_budgets": list(args.arm_budget),
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "host_logical_cpu_count": os.cpu_count(),
        "python_executable": sys.executable,
        "native_build_root": str(args.native_build_root.resolve()),
        "code_commit": args.code_commit,
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "stage_wall_clock_seconds": perf_counter() - started,
        "workers": workers,
        "command_passed": not failed,
    }
    (stage / "stage-execution.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 1 if failed else 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
