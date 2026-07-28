#!/usr/bin/env python3
"""Publish the execution layout and retained logs for T068 evidence stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_ID = "t068-native-boundary-stage-execution-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", action="append", type=Path, required=True)
    parser.add_argument("--shard-stdout", action="append", type=Path, required=True)
    parser.add_argument("--shard-stderr", action="append", type=Path, required=True)
    parser.add_argument("--shard-exit-code", action="append", type=Path, required=True)
    parser.add_argument("--audit-stage-wall-clock-seconds", type=float, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--semantic-stdout", type=Path, required=True)
    parser.add_argument("--semantic-stderr", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("T068 stage execution refuses to overwrite output")
    values = (args.shard, args.shard_stdout, args.shard_stderr, args.shard_exit_code)
    if any(len(value) != 16 for value in values):
        raise SystemExit(
            "T068 stage execution requires 16 shard reports/logs/exit codes"
        )
    if (
        not math.isfinite(args.audit_stage_wall_clock_seconds)
        or args.audit_stage_wall_clock_seconds <= 0
    ):
        raise SystemExit("T068 audit stage wall clock must be finite and positive")
    shards: list[dict[str, Any]] = []
    for index, (report, stdout, stderr, exit_code) in enumerate(
        zip(*values, strict=True)
    ):
        raw = _load(report)
        if raw.get("shard_index") != index or raw.get("command_passed") is not True:
            raise SystemExit(f"T068 stage shard {index} failed its report contract")
        code = exit_code.read_text(encoding="utf-8").strip()
        if code != "0":
            raise SystemExit(f"T068 stage shard {index} exited {code!r}")
        shards.append(
            {
                "shard_index": index,
                "record_range": raw.get("record_range"),
                "exit_code": 0,
                "report": _artifact(report),
                "stdout": _artifact(stdout),
                "stderr": _artifact(stderr),
            }
        )
    semantic = _load(args.semantic_report)
    if (
        semantic.get("schema_id") != "t068-native-boundary-semantic-equivalence-v1"
        or semantic.get("command_passed") is not True
    ):
        raise SystemExit("T068 semantic report failed its stage contract")
    semantic_elapsed = semantic.get("elapsed_wall_clock_seconds")
    if (
        not isinstance(semantic_elapsed, (int, float))
        or not math.isfinite(semantic_elapsed)
        or semantic_elapsed <= 0
    ):
        raise SystemExit("T068 semantic stage wall clock must be finite and positive")
    payload = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": semantic["code_commit"],
        "native_commit": semantic["native_commit"],
        "stages": {
            "semantic_0_1": {
                "record_range": "0:1",
                "worker_count": 1,
                "shard_count": 1,
                "elapsed_wall_clock_seconds": semantic_elapsed,
                "report": _artifact(args.semantic_report),
                "stdout": _artifact(args.semantic_stdout),
                "stderr": _artifact(args.semantic_stderr),
            },
            "callback_dependency_audit_0_16": {
                "record_range": "0:16",
                "worker_count": 16,
                "shard_count": 16,
                "elapsed_wall_clock_seconds": args.audit_stage_wall_clock_seconds,
                "shards": shards,
            },
        },
        "command_passed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"T068 cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"T068 expected a JSON object: {path}")
    return value


def _artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"T068 missing retained stage file: {path}")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
