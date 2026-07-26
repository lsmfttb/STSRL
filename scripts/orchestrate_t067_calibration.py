#!/usr/bin/env python3
"""Run the T067 minimum-budget calibration as 16 explicit WSL workers."""

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


NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
STAGE_SCHEMA_ID = "t067-battle-search-v2-stage-execution-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--cache-capacity", type=int, default=4096)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate exact source/input/output roles without starting workers.",
    )
    parser.add_argument(
        "--native-build-root",
        type=Path,
        default=Path("/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313"),
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    artifact_root = args.artifact_root.resolve()
    input_root = args.input_root.resolve()
    _validate_paths(repo_root, artifact_root)
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T067 stage requires an exact 40-character code commit")
    _validate_code_commit(repo_root, args.code_commit)
    stage = artifact_root / "initial-budget-1"
    if stage.exists():
        raise SystemExit(f"T067 stage already exists; refusing to overwrite: {stage}")

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
    t061_manifest = (
        input_root
        / "t061-a20-reachability-bottleneck-decomposition"
        / "t061-retention-manifest.json"
    )
    for path in (cohort, checkpoint, t061_manifest):
        if not path.is_file():
            raise SystemExit(f"missing T067 stage input: {path}")
    if args.preflight_only:
        print(
            "T067 calibration preflight passed: "
            f"source={repo_root} commit={args.code_commit} "
            f"fresh_stage={stage}",
            file=sys.stderr,
        )
        return 0

    logs = stage / "logs"
    logs.mkdir(parents=True)

    started_at = _now()
    started = perf_counter()
    workers: list[dict[str, object]] = []
    processes: list[tuple[subprocess.Popen[bytes], object, object]] = []
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{args.native_build_root.resolve()}:{repo_root / 'src'}"
    for index in range(16):
        output = stage / f"shard-{index}.json"
        preflight = stage / f"preflight-{index}.json"
        stdout_path = logs / f"shard-{index}.stdout.log"
        stderr_path = logs / f"shard-{index}.stderr.log"
        command = [
            sys.executable,
            str(repo_root / "scripts" / "run_t067_battle_search_v2.py"),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--t061-retention-manifest",
            str(t061_manifest),
            "--input-preflight-report",
            str(preflight),
            "--output",
            str(output),
            "--record-range",
            f"{index}:{index + 1}",
            "--workers",
            "16",
            "--shards",
            "16",
            "--baseline-budget",
            "100",
            "--arm-budget",
            "prior_only=1",
            "--arm-budget",
            "value_only=1",
            "--arm-budget",
            "prior_value=1",
            "--family",
            "wall_clock_normalized",
            "--cache-capacity",
            str(args.cache_capacity),
        ]
        stdout_stream = stdout_path.open("wb")
        stderr_stream = stderr_path.open("wb")
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=env,
            stdout=stdout_stream,
            stderr=stderr_stream,
        )
        processes.append((process, stdout_stream, stderr_stream))
        workers.append(
            {
                "worker_index": index,
                "record_range": f"{index}:{index + 1}",
                "command": command,
                "output_path": str(output),
                "preflight_path": str(preflight),
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
            }
        )

    failed = False
    for worker, (process, stdout_stream, stderr_stream) in zip(
        workers, processes, strict=True
    ):
        returncode = process.wait()
        stdout_stream.close()
        stderr_stream.close()
        worker["returncode"] = returncode
        output_path = Path(str(worker["output_path"]))
        worker["output_exists"] = output_path.is_file()
        if returncode != 0 or not output_path.is_file():
            failed = True

    report = {
        "schema_id": STAGE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "stage": "initial_budget_1_cost_calibration",
        "stage_classification": "substantial_restored_battle_calibration",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "python_executable": sys.executable,
        "native_build_root": str(args.native_build_root.resolve()),
        "repair_identity": "exact-public-node-inference-cache-v1",
        "cache_capacity": args.cache_capacity,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "host_logical_cpu_count": os.cpu_count(),
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "stage_wall_clock_seconds": perf_counter() - started,
        "workers": workers,
        "command_passed": not failed,
    }
    report_path = artifact_root / "t067-stage-execution.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"T067 calibration: workers=16 shards=16 passed={not failed} "
        f"wall={report['stage_wall_clock_seconds']:.3f}s",
        file=sys.stderr,
    )
    return 1 if failed else 0


def _validate_paths(repo_root: Path, artifact_root: Path) -> None:
    if not (repo_root / "scripts" / "run_t067_battle_search_v2.py").is_file():
        raise SystemExit(f"invalid T067 repo root: {repo_root}")
    if repo_root == artifact_root or repo_root in artifact_root.parents:
        raise SystemExit(
            "T067 stable artifacts must be outside the disposable worktree"
        )
    normalized = artifact_root.as_posix()
    if "/artifacts/t067-battle-search-v2-inference-cost-repair/" not in normalized:
        raise SystemExit("T067 artifact root is outside the published stable namespace")


def _validate_code_commit(repo_root: Path, code_commit: str) -> None:
    actual = _git_output(repo_root, "rev-parse", "HEAD")
    if actual is None:
        raise SystemExit(f"T067 cannot resolve source checkout HEAD: {repo_root}")
    if actual != code_commit:
        raise SystemExit(
            "T067 source checkout HEAD differs from --code-commit: "
            f"{actual} != {code_commit}"
        )
    status = _git_output(repo_root, "status", "--porcelain", "--untracked-files=no")
    if status is None or status:
        raise SystemExit("T067 source checkout has tracked or staged changes")


def _git_output(repo_root: Path, *arguments: str) -> str | None:
    commands = [["git", "-C", str(repo_root), *arguments]]
    dot_git = repo_root / ".git"
    if dot_git.is_file():
        marker = dot_git.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            git_dir = marker.removeprefix("gitdir:").strip()
            match = re.fullmatch(r"([A-Za-z]):[/\\](.*)", git_dir)
            if match is not None:
                git_dir = (
                    f"/mnt/{match.group(1).lower()}/"
                    f"{match.group(2).replace(chr(92), '/')}"
                )
            commands.append(
                [
                    "git",
                    "--git-dir",
                    git_dir,
                    "--work-tree",
                    str(repo_root),
                    "-c",
                    "core.autocrlf=true",
                    *arguments,
                ]
            )
    for command in commands:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
