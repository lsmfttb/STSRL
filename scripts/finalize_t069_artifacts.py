#!/usr/bin/env python3
"""Finalize T069 decision, stage inventory, and stable retention manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sts_combat_rl.commands.t069_public_context_projection import (
    T069_CALIBRATION_SCHEMA_ID,
    T069_FEASIBILITY_SCHEMA_ID,
    T069_RETENTION_SCHEMA_ID,
    build_t069_calibration_report,
    build_t069_decision_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--candidate-report", action="append", required=True)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    source_root = args.source_root.resolve()
    input_root = args.input_root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T069 finalizer requires exact code commit")
    if "/artifacts/t069-public-node-feature-encoding-projection-feasibility/" not in (
        root.as_posix()
    ):
        raise SystemExit("T069 finalizer root is outside stable namespace")
    if "/.claude/worktrees/" in source_root.as_posix():
        raise SystemExit("T069 retention source must not be disposable")
    feasibility = _load(root / "t069-feasibility.json")
    if feasibility.get("schema_id") != T069_FEASIBILITY_SCHEMA_ID:
        raise SystemExit("T069 feasibility schema changed")
    candidate_paths = [Path(path).resolve() for path in args.candidate_report]
    candidates = [_load(path) for path in candidate_paths]
    calibration = build_t069_calibration_report(candidates)
    calibration_path = root / "t069-calibration.json"
    if calibration_path.exists():
        raise SystemExit("T069 finalizer refuses to overwrite calibration")
    _write(calibration_path, calibration)
    decision = build_t069_decision_report(
        feasibility,
        calibration if feasibility["conditional_calibration_authorized"] else None,
    )
    decision_path = root / "t069-decision.json"
    if decision_path.exists():
        existing = _load(decision_path)
        if existing != decision:
            raise SystemExit("T069 existing decisive decision does not match finalizer")
    else:
        _write(decision_path, decision)

    stage_paths = sorted(root.rglob("*stage-execution.json"))
    initial_stage = root / "t069-stage-execution.json"
    if initial_stage.is_file() and initial_stage not in stage_paths:
        stage_paths.insert(0, initial_stage)
    stages = [_identity(path, root) for path in stage_paths]
    stage_summary = {
        "schema_id": "t069-complete-stage-execution-v1",
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "stages": stages,
        "substantial_stage_count": len(stages),
        "all_substantial_stages_use_16_workers": all(
            _load(path).get("worker_count", 16) == 16
            or _load(path).get("projection_attribution", {}).get("worker_count") == 16
            for path in stage_paths
        ),
        "semantic_single_worker_reason": "one-record semantic smoke",
        "command_passed": all(
            _load(path).get("command_passed") is True for path in stage_paths
        ),
    }
    complete_stage_path = root / "t069-complete-stage-execution.json"
    _write(complete_stage_path, stage_summary)

    source_short = args.code_commit[:7]
    output_root = root.as_posix()
    source_path = source_root.as_posix()
    input_path = input_root.as_posix()
    candidate_commands = []
    for path in candidate_paths:
        stage = path.parent
        stage_execution = stage / "stage-execution.json"
        if not stage_execution.is_file():
            continue
        stage_report = _load(stage_execution)
        arm_args = " ".join(
            f"--arm-budget {value}" for value in stage_report["arm_budgets"]
        )
        candidate_commands.append(
            f"cd {source_path} && PYTHONPATH=/home/lsmft/stsrl-spikes/"
            f"sts_lightspeed-t062/build-t062-py313:{source_path}/src "
            f"/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 "
            f"scripts/orchestrate_t069_calibration_candidate.py "
            f"--repo-root {source_path} --artifact-root {output_root} "
            f"--input-root {input_path} --code-commit {args.code_commit} "
            f"--candidate-name {stage_report['candidate_name']} "
            f"--family {stage_report['family']} --baseline-budget 100 {arm_args}"
        )
    regeneration_commands = [
        (
            "cd /mnt/d/DeadlycatCoding/STSRL && "
            f"git -c core.autocrlf=true worktree add --detach "
            f"{source_path} {args.code_commit}"
        ),
        (
            f"cd {source_path} && STSRL_LIGHTSPEED_BUILD_JOBS=16 "
            "bash scripts/verify_lightspeed_source.sh "
            "/home/lsmft/stsrl-spikes/sts_lightspeed"
        ),
        (
            f"cd {source_path} && PYTHONPATH=/home/lsmft/stsrl-spikes/"
            f"sts_lightspeed-t062/build-t062-py313:{source_path}/src "
            f"/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 "
            "scripts/orchestrate_t069_projection_stage.py "
            f"--repo-root {source_path} --artifact-root {output_root} "
            f"--input-root {input_path} --code-commit {args.code_commit}"
        ),
        *candidate_commands,
    ]
    candidate_args = " ".join(
        f"--candidate-report {path.as_posix()}" for path in candidate_paths
    )
    regeneration_commands.append(
        f"cd {source_path} && PYTHONPATH=/home/lsmft/stsrl-spikes/"
        f"sts_lightspeed-t062/build-t062-py313:{source_path}/src "
        f"/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13 "
        "scripts/finalize_t069_artifacts.py "
        f"--artifact-root {output_root} --source-root {source_path} "
        f"--input-root {input_path} --code-commit {args.code_commit} "
        f"{candidate_args}"
    )
    artifacts = [
        _identity(path, root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "t069-retention-manifest.json"
    ]
    manifest = {
        "schema_id": T069_RETENTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "source_root": source_path,
        "source_root_role": f"stable detached exact source {source_short}",
        "artifact_root": output_root,
        "input_root": input_path,
        "input_identities": feasibility["input_identities"],
        "decision": decision,
        "calibration": {
            "schema_id": T069_CALIBRATION_SCHEMA_ID,
            "path": calibration_path.relative_to(root).as_posix(),
            "sha256": _sha256(calibration_path),
        },
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "artifact_bytes": sum(item["bytes"] for item in artifacts),
        "regeneration_commands": regeneration_commands,
        "compatibility_requirements": {
            "python": "/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13",
            "native_build": (
                "/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313"
            ),
            "native_commit": ("3cb9ebecb87c38044b34aa0e013d42b222a04087"),
            "worker_count": 16,
            "shard_count": 16,
        },
        "retention_owner": "STSRL main maintainer",
        "retention_reason": (
            "compact T069 attribution, semantic, calibration, and terminal "
            "decision evidence for the next published task"
        ),
        "possible_downstream_consumers": [decision["recommendation"]],
        "deletion_conditions": (
            "raw shards may be deleted after the accepted compact reports and "
            "manifest are independently verified and no active review needs "
            "per-record reproduction"
        ),
        "no_93_record_outcome_aggregation_performed": True,
        "command_passed": stage_summary["command_passed"],
    }
    manifest_path = root / "t069-retention-manifest.json"
    if manifest_path.exists():
        raise SystemExit("T069 finalizer refuses to overwrite retention manifest")
    _write(manifest_path, manifest)
    return 0 if manifest["command_passed"] else 1


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"T069 missing JSON input: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"T069 expected JSON object: {path}")
    return raw


def _identity(path: Path, root: Path) -> dict[str, Any]:
    schema_id = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            schema_id = raw.get("schema_id")
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "schema_id": schema_id,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
