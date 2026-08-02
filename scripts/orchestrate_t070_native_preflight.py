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
    probe_t070_native_runtime_identity,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--native-checkout", type=Path, required=True)
    parser.add_argument("--native-build-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    native_checkout = args.native_checkout.resolve()
    native_build_root = args.native_build_root.resolve()
    output = args.artifact_root.resolve() / "native-preflight"
    verify_exact_git_checkout(repo, args.code_commit)
    if _git(native_checkout, "rev-parse", "HEAD") != NATIVE_COMMIT:
        raise SystemExit("T070 native preflight checkout commit mismatch")
    if _git(native_checkout, "status", "--short", "--untracked-files=no"):
        raise SystemExit("T070 native preflight checkout has tracked modifications")
    try:
        native_build_root.relative_to(native_checkout)
    except ValueError as exc:
        raise SystemExit(
            "T070 runtime build root must be inside its exact source checkout"
        ) from exc
    if native_build_root.exists():
        raise SystemExit("T070 native preflight requires a new runtime build root")
    if output.exists():
        raise SystemExit("T070 native preflight refuses to overwrite output")
    output.mkdir(parents=True)
    manifest = repo / "docs" / "sts_lightspeed_source_manifest.json"
    verifier = repo / "scripts" / "verify_lightspeed_source.sh"
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_value.get("integration", {}).get("commit") != NATIVE_COMMIT:
        raise SystemExit("T070 native preflight manifest commit mismatch")
    build = manifest_value["build"]
    build_jobs = 16
    verifier_command = ["bash", str(verifier), str(native_checkout)]
    configure_command = [
        "cmake",
        "-S",
        str(native_checkout),
        "-B",
        str(native_build_root),
        f"-DCMAKE_POLICY_VERSION_MINIMUM={build['cmake_policy_version_minimum']}",
        f"-DPYTHON_EXECUTABLE={sys.executable}",
    ]
    build_command = [
        "cmake",
        "--build",
        str(native_build_root),
        "--target",
        build["cmake_target"],
        "-j",
        str(build_jobs),
    ]
    stdout_path = output / "source-verifier.stdout.log"
    stderr_path = output / "source-verifier.stderr.log"
    build_stdout_path = output / "runtime-build.stdout.log"
    build_stderr_path = output / "runtime-build.stderr.log"
    started_at = _now()
    started = perf_counter()
    env = dict(os.environ)
    env["STSRL_LIGHTSPEED_BUILD_JOBS"] = str(build_jobs)
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        verifier_result = subprocess.run(
            verifier_command,
            cwd=repo,
            env=env,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    configure_result = None
    build_result = None
    if verifier_result.returncode == 0:
        with (
            build_stdout_path.open("wb") as stdout,
            build_stderr_path.open("wb") as stderr,
        ):
            configure_result = subprocess.run(
                configure_command,
                cwd=repo,
                env=env,
                stdout=stdout,
                stderr=stderr,
                check=False,
            )
            if configure_result.returncode == 0:
                build_result = subprocess.run(
                    build_command,
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
    cmake = subprocess.run(
        ["cmake", "--version"], capture_output=True, text=True, check=False
    )
    runtime_identity = None
    if build_result is not None and build_result.returncode == 0:
        sys.path.insert(0, str(native_build_root))
        try:
            runtime_identity = probe_t070_native_runtime_identity(
                native_checkout=native_checkout,
                native_build_root=native_build_root,
            )
        finally:
            sys.path.remove(str(native_build_root))
    return_codes = [
        verifier_result.returncode,
        configure_result.returncode if configure_result is not None else None,
        build_result.returncode if build_result is not None else None,
    ]
    passed = return_codes == [0, 0, 0] and runtime_identity is not None
    aggregate_return_code = next(
        (code for code in return_codes if code not in (None, 0)), 0 if passed else 1
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
        "cmake_identity": (cmake.stdout or cmake.stderr).splitlines()[0],
        "manifest_build_directory": build["build_directory"],
        "manifest_cmake_target": build["cmake_target"],
        "build_jobs": build_jobs,
        "verifier_clean_worktree_mode": "temporary_detached_exact_commit_worktree",
        "verifier_clean_worktree_scope": "clean_source_verifier_only",
        "runtime_source_mode": "exact_head_tracked_clean_stable_checkout",
        "native_source_checkout": str(native_checkout),
        "native_runtime_build_root": str(native_build_root),
        "native_runtime_identity": runtime_identity,
        "required_apis": [
            "StepSimulator.battle_search_v2",
            "StepSimulator.battle_search_v2_with_tree_geometry",
        ],
        "geometry_schema": "native-battle-search-v2-tree-geometry-v1",
        "semantic_parity_result": verifier_result.returncode == 0,
        "commands": [
            {"name": "clean_source_verifier", "argv": verifier_command},
            {"name": "runtime_cmake_configure", "argv": configure_command},
            {"name": "runtime_cmake_build", "argv": build_command},
        ],
        "return_codes": return_codes,
        "return_code": aggregate_return_code,
        "started_at_utc": started_at,
        "finished_at_utc": _now(),
        "wall_clock_seconds": elapsed,
        "worker_count": build_jobs,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "runtime_build_stdout": str(build_stdout_path),
        "runtime_build_stderr": str(build_stderr_path),
        "command_passed": passed,
    }
    (output / "t070-native-capability-preflight.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return aggregate_return_code


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "T070 native git identity command failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
    return completed.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
