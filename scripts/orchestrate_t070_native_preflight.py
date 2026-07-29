#!/usr/bin/env python3
"""Run and retain the exact T070 clean native source verifier preflight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.commands.t070_search_v2_audit import (
    NATIVE_COMMIT,
    NATIVE_PREFLIGHT_SCHEMA_ID,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--native-checkout", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = args.artifact_root.resolve() / "native-preflight"
    verify_exact_git_checkout(repo, args.code_commit)
    if output.exists():
        raise SystemExit("T070 native preflight refuses to overwrite output")
    output.mkdir(parents=True)
    manifest = repo / "docs" / "sts_lightspeed_source_manifest.json"
    verifier = repo / "scripts" / "verify_lightspeed_source.sh"
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_value.get("integration", {}).get("commit") != NATIVE_COMMIT:
        raise SystemExit("T070 native preflight manifest commit mismatch")
    command = ["bash", str(verifier), str(args.native_checkout.resolve())]
    stdout_path = output / "source-verifier.stdout.log"
    stderr_path = output / "source-verifier.stderr.log"
    started_at = _now()
    started = perf_counter()
    env = dict(os.environ)
    env["STSRL_LIGHTSPEED_BUILD_JOBS"] = "16"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(
            command,
            cwd=repo,
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    elapsed = perf_counter() - started
    compiler = subprocess.run(
        ["c++", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = {
        "schema_id": NATIVE_PREFLIGHT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T070",
        "stsrl_code_commit": args.code_commit,
        "native_repository": "https://github.com/lsmfttb/sts_lightspeed.git",
        "native_ref": "refs/heads/stsrl/main",
        "native_commit": NATIVE_COMMIT,
        "source_manifest_sha256": _sha256(manifest),
        "source_verifier_sha256": _sha256(verifier),
        "python_identity": sys.version,
        "platform_identity": platform.platform(),
        "compiler_identity": (compiler.stdout or compiler.stderr).splitlines()[0],
        "required_apis": [
            "StepSimulator.battle_search_v2",
            "StepSimulator.battle_search_v2_with_tree_geometry",
        ],
        "geometry_schema": "native-battle-search-v2-tree-geometry-v1",
        "semantic_parity_result": completed.returncode == 0,
        "command": command,
        "return_code": completed.returncode,
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "wall_clock_seconds": elapsed,
        "worker_count": 16,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "command_passed": completed.returncode == 0,
    }
    (output / "t070-native-capability-preflight.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return completed.returncode


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
