#!/usr/bin/env python3
"""Run T069 semantic 0:1 and paired projection 0:16 with 16 workers."""

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


NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
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
        raise SystemExit("T069 stage requires exact code commit")
    _validate_checkout(repo_root, args.code_commit)
    if artifact_root.exists():
        raise SystemExit("T069 stage refuses to overwrite artifact root")
    if "/artifacts/t069-public-node-feature-encoding-projection-feasibility/" not in (
        artifact_root.as_posix()
    ):
        raise SystemExit("T069 artifact root is outside stable namespace")

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
    for path in (cohort, checkpoint, t061, t068):
        if not path.is_file():
            raise SystemExit(f"T069 stage missing input: {path}")

    artifact_root.mkdir(parents=True)
    logs = artifact_root / "logs"
    logs.mkdir()
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{args.native_build_root.resolve()}:{repo_root / 'src'}"
    started = perf_counter()
    started_at = _now()

    source_verifier_command = [
        "bash",
        str(repo_root / "scripts" / "verify_lightspeed_source.sh"),
        "/home/lsmft/stsrl-spikes/sts_lightspeed",
    ]
    verifier_env = dict(env)
    verifier_env["STSRL_LIGHTSPEED_BUILD_JOBS"] = "16"
    verifier_code = _run_logged(
        source_verifier_command,
        repo_root,
        verifier_env,
        logs / "source-verifier.stdout.log",
        logs / "source-verifier.stderr.log",
    )
    if verifier_code != 0:
        _write_stage(
            artifact_root,
            args,
            started,
            started_at,
            [],
            command_passed=False,
            source_verifier_command=source_verifier_command,
            source_verifier_code=verifier_code,
        )
        return verifier_code

    semantic_command = [
        sys.executable,
        str(repo_root / "scripts" / "verify_t069_semantic_equivalence.py"),
        "--cohort",
        str(cohort),
        "--checkpoint",
        str(checkpoint),
        "--t061-retention-manifest",
        str(t061),
        "--t068-retention-manifest",
        str(t068),
        "--preflight-output",
        str(artifact_root / "semantic-preflight.json"),
        "--output",
        str(artifact_root / "t069-semantic-equivalence.json"),
        "--code-commit",
        args.code_commit,
    ]
    semantic = _run_logged(
        semantic_command,
        repo_root,
        env,
        logs / "semantic.stdout.log",
        logs / "semantic.stderr.log",
    )
    if semantic != 0:
        return semantic

    workers: list[dict[str, Any]] = []
    processes: list[tuple[subprocess.Popen[bytes], Any, Any]] = []
    for index in range(16):
        command = [
            sys.executable,
            str(repo_root / "scripts" / "run_t069_projection_shard.py"),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--t061-retention-manifest",
            str(t061),
            "--t068-retention-manifest",
            str(t068),
            "--preflight-output",
            str(artifact_root / f"preflight-{index:02d}.json"),
            "--unprojected-output",
            str(artifact_root / f"unprojected-shard-{index:02d}.json"),
            "--projected-output",
            str(artifact_root / f"projected-shard-{index:02d}.json"),
            "--identity-output",
            str(artifact_root / f"identity-shard-{index:02d}.json"),
            "--code-commit",
            args.code_commit,
            "--record-range",
            f"{index}:{index + 1}",
            "--shard-index",
            str(index),
        ]
        stdout_path = logs / f"projection-{index:02d}.stdout.log"
        stderr_path = logs / f"projection-{index:02d}.stderr.log"
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
    if failed:
        _write_stage(
            artifact_root,
            args,
            started,
            started_at,
            workers,
            command_passed=False,
            source_verifier_command=source_verifier_command,
            source_verifier_code=verifier_code,
        )
        return 1

    merge_command = [
        sys.executable,
        str(repo_root / "scripts" / "merge_t069_projection_evidence.py"),
    ]
    for index in range(16):
        merge_command.extend(
            [
                "--unprojected-shard",
                str(artifact_root / f"unprojected-shard-{index:02d}.json"),
                "--projected-shard",
                str(artifact_root / f"projected-shard-{index:02d}.json"),
                "--identity-shard",
                str(artifact_root / f"identity-shard-{index:02d}.json"),
            ]
        )
    merge_command.extend(
        [
            "--unprojected-merged",
            str(artifact_root / "t069-unprojected-merged.json"),
            "--projected-merged",
            str(artifact_root / "t069-projected-merged.json"),
            "--attribution-output",
            str(artifact_root / "t069-attribution.json"),
            "--feasibility-output",
            str(artifact_root / "t069-feasibility.json"),
            "--calibration-output",
            str(artifact_root / "t069-initial-calibration.json"),
            "--decision-output",
            str(artifact_root / "t069-decision.json"),
            "--semantic-report",
            str(artifact_root / "t069-semantic-equivalence.json"),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--t061-retention-manifest",
            str(t061),
            "--t068-retention-manifest",
            str(t068),
            "--source-manifest",
            str(repo_root / "docs" / "sts_lightspeed_source_manifest.json"),
            "--source-verifier",
            str(repo_root / "scripts" / "verify_lightspeed_source.sh"),
            "--code-commit",
            args.code_commit,
        ]
    )
    merge_code = _run_logged(
        merge_command,
        repo_root,
        env,
        logs / "merge.stdout.log",
        logs / "merge.stderr.log",
    )
    _write_stage(
        artifact_root,
        args,
        started,
        started_at,
        workers,
        command_passed=merge_code == 0,
        merge_command=merge_command,
        source_verifier_command=source_verifier_command,
        source_verifier_code=verifier_code,
    )
    return merge_code


def _run_logged(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> int:
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        ).returncode


def _write_stage(
    root: Path,
    args: argparse.Namespace,
    started: float,
    started_at: str,
    workers: list[dict[str, Any]],
    *,
    command_passed: bool,
    merge_command: list[str] | None = None,
    source_verifier_command: list[str],
    source_verifier_code: int,
) -> None:
    report = {
        "schema_id": "t069-stage-execution-v1",
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "python_executable": sys.executable,
        "native_build_root": str(args.native_build_root.resolve()),
        "host_logical_cpu_count": os.cpu_count(),
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "stage_wall_clock_seconds": perf_counter() - started,
        "source_verifier": {
            "command": source_verifier_command,
            "returncode": source_verifier_code,
            "build_jobs": 16,
            "executed_before_simulator_evidence": True,
        },
        "semantic": {
            "record_range": "0:1",
            "worker_count": 1,
            "shard_count": 1,
            "single_worker_reason": "one-record semantic smoke",
        },
        "projection_attribution": {
            "record_range": "0:16",
            "worker_count": 16,
            "shard_count": 16,
            "effective_parallel_workers": 16,
            "workers": workers,
        },
        "merge_command": merge_command,
        "command_passed": command_passed,
    }
    (root / "t069-stage-execution.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_checkout(root: Path, commit: str) -> None:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != commit:
        raise SystemExit("T069 orchestrator source checkout differs")
    status = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root}",
            "-C",
            str(root),
            "status",
            "--porcelain",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0 or status.stdout.strip():
        raise SystemExit("T069 orchestrator source checkout is dirty")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
