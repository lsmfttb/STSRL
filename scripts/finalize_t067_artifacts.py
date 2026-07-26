#!/usr/bin/env python3
"""Write T067 calibration, decision, and stable retention artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any

from sts_combat_rl.commands.t067_battle_search_v2 import (
    T067_COMPARISON_SCHEMA_ID,
    T067_RETENTION_SCHEMA_ID,
    build_t067_calibration_manifest,
    build_t067_decision_report,
    write_t067_report,
)


EXPECTED_INPUTS = {
    "t062_input_preflight": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/t062-input-preflight.json",
        1815,
        "19a948fe9a6978d67e7b45522d03868bffd410ccf958b5cf820291c46fe3f024",
        "t062-battle-search-v2-input-preflight-v1",
    ),
    "t062_nominal_merged": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/nominal-100-py313-with-native/"
        "t062-calibration-nominal-100-merged.json",
        20534396,
        "16deedf7fbd9035d1f050929e50f780a9f85dcd6185ea9e74813c3cc9004988e",
        "t062-battle-search-v2-comparison-v1",
    ),
    "t062_wall_candidate_merged": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/wall-candidate-guided-1-py313/"
        "t062-wall-candidate-guided-1-merged.json",
        23979082,
        "b9e1e17ea37cbe4dd2d51ef3c6d2248387ec0fd06b64d1977e825abb05da6b2b",
        "t062-battle-search-v2-comparison-v1",
    ),
    "t062_calibration_manifest": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/t062-calibration-manifest-v2.json",
        4856,
        "aa6dc013c6828d9c363dfefd0e201e303925f4ae40eb006e18ae4d00635104b4",
        "t062-battle-search-v2-calibration-manifest-v2",
    ),
    "t062_decision_report": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/t062-early-exit-decision-report-v2.json",
        639,
        "cfa015d94611dbf117b40539ba74256e53a618dd5acc72292f0674428315fec5",
        "t062-battle-search-v2-early-exit-decision-report-v1",
    ),
    "t062_retention_manifest": (
        "t062-battle-search-v2-minimal-surface/calibration/"
        "native-prior-fix-3cb9ebe/t062-retention-manifest-v3.json",
        99618,
        "dfac7d7660517cee65e311a8d1d2b6fa2d82ac7e26001b8da6ce28150e04ba12",
        "t062-battle-search-v2-retention-manifest-v3",
    ),
    "t052_fixed_cohort": (
        "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl",
        161435825,
        "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608",
        None,
    ),
    "t043_checkpoint": (
        "t044-de-assisted-comparison-pr/t043-assist_0-smoke/"
        "t043-assist_0-smoke-checkpoint.pt",
        386717,
        "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        None,
    ),
    "t061_retention_manifest": (
        "t061-a20-reachability-bottleneck-decomposition/t061-retention-manifest.json",
        6321,
        "ca08103322ef93d29468dbb50a5babdd21aa47e62de500649d184a9286322029",
        "t061-retention-manifest-v2",
    ),
}
EXPECTED_SOURCE_FILES = {
    "sts_lightspeed_source_manifest": (
        "docs/sts_lightspeed_source_manifest.json",
        7789,
        "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631",
        "sts-lightspeed-source-manifest-v1",
    ),
    "sts_lightspeed_source_verifier": (
        "scripts/verify_lightspeed_source.sh",
        19872,
        "16fc6ff8049c9c5083260e513e1472d6736e1aac946d27c8ec7b80b64d4dd0a3",
        None,
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-repository-root", type=Path, required=True)
    parser.add_argument("--regeneration-source-root", type=Path, required=True)
    parser.add_argument("--regeneration-output-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--attribution-report", type=Path, required=True)
    parser.add_argument("--stage-execution-report", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--verifier-log", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T067 finalization requires an exact code commit")
    root = args.artifact_root.resolve()
    repo_root = args.repo_root.resolve()
    source_repository_root = args.source_repository_root.resolve()
    regeneration_source_root = args.regeneration_source_root.resolve()
    regeneration_output_root = args.regeneration_output_root.resolve()
    input_root = args.input_root.resolve()
    if repo_root == root or repo_root in root.parents:
        raise SystemExit("T067 stable root must be outside the disposable worktree")
    _validate_checkout_commit(repo_root, args.code_commit)
    _validate_regeneration_roles(
        accepted_root=root,
        source_repository_root=source_repository_root,
        source_checkout_root=regeneration_source_root,
        output_root=regeneration_output_root,
    )
    if not (source_repository_root / ".git").exists():
        raise SystemExit(
            f"T067 source repository root is not a Git checkout: "
            f"{source_repository_root}"
        )

    attribution = _load_json(args.attribution_report, T067_COMPARISON_SCHEMA_ID)
    stage = _load_json(
        args.stage_execution_report, "t067-battle-search-v2-stage-execution-v1"
    )
    semantic = _load_json(
        args.semantic_report, "t067-battle-search-v2-semantic-equivalence-v1"
    )
    for label, report in (("stage", stage), ("semantic", semantic)):
        if report.get("code_commit") != args.code_commit:
            raise SystemExit(f"T067 {label} code commit differs")
        if report.get("command_passed") is not True:
            raise SystemExit(f"T067 {label} did not pass")
    if (
        stage.get("worker_count") != 16
        or stage.get("shard_count") != 16
        or stage.get("effective_parallel_workers") != 16
    ):
        raise SystemExit("T067 substantial calibration was not 16-worker")
    if stage.get(
        "python_executable"
    ) != "/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13" or stage.get(
        "native_build_root"
    ) != ("/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313"):
        raise SystemExit("T067 stage did not use the accepted Python/native pairing")
    ranges = [
        worker.get("record_range")
        for worker in stage.get("workers", [])
        if isinstance(worker, dict)
    ]
    if ranges != [f"{index}:{index + 1}" for index in range(16)]:
        raise SystemExit("T067 stage record ranges are incomplete or unordered")
    verifier_text = args.verifier_log.read_text(encoding="utf-8", errors="replace")
    for marker in (
        "integration: https://github.com/lsmfttb/sts_lightspeed.git "
        "refs/heads/stsrl/main @ 3cb9ebecb87c38044b34aa0e013d42b222a04087",
        "native API capability assertions passed",
        "clean sts_lightspeed pinned-source build passed",
    ):
        if marker not in verifier_text:
            raise SystemExit(f"T067 verifier log lacks marker: {marker}")

    calibration = build_t067_calibration_manifest(attribution)
    decision = build_t067_decision_report(calibration)
    calibration_path = root / "t067-calibration-manifest.json"
    decision_path = root / "t067-decision-report.json"
    write_t067_report(calibration_path, calibration)
    write_t067_report(decision_path, decision)

    inputs = {
        name: _identity(input_root / relative, size, digest, schema)
        for name, (relative, size, digest, schema) in EXPECTED_INPUTS.items()
    }
    inputs.update(
        {
            name: _identity(repo_root / relative, size, digest, schema)
            for name, (relative, size, digest, schema) in EXPECTED_SOURCE_FILES.items()
        }
    )
    artifacts = [
        _artifact_identity(path, root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "t067-retention-manifest.json"
    ]
    commands = _regeneration_commands(
        source_repository_root=source_repository_root,
        source_checkout_root=regeneration_source_root,
        accepted_root=root,
        output_root=regeneration_output_root,
        input_root=input_root,
        code_commit=args.code_commit,
    )
    _validate_regeneration_commands(
        commands=commands,
        code_commit=args.code_commit,
        source_checkout_root=regeneration_source_root,
        accepted_root=root,
        output_root=regeneration_output_root,
    )
    retention = {
        "schema_id": T067_RETENTION_SCHEMA_ID,
        "schema_version": 2,
        "task_id": "T067",
        "stable_retention_root": str(root),
        "code_commit": args.code_commit,
        "accepted_t062_merge_commit": ("b01a83e1ec436410945e8037add301d6f952a712"),
        "native_commit": "3cb9ebecb87c38044b34aa0e013d42b222a04087",
        "controller": "battle_search_v2_oracle_like_t067_cache_v1",
        "controller_arms": [
            "baseline",
            "prior_only",
            "value_only",
            "prior_value",
        ],
        "repair_identity": "exact-public-node-inference-cache-v1",
        "input_identities": inputs,
        "execution_layout": {
            "calibration_record_range": "0:16",
            "shard_count": 16,
            "worker_count": 16,
            "effective_parallel_workers": 16,
            "record_ranges": ranges,
            "python_executable": stage["python_executable"],
            "native_build_root": stage["native_build_root"],
            "semantic_smoke_record_range": "0:1",
            "semantic_smoke_single_worker_reason": semantic.get("single_worker_reason"),
        },
        "calibration": {
            "manifest_path": str(calibration_path),
            "all_required_locks_succeeded": calibration["all_required_locks_succeeded"],
            "primary_comparison_authorized": calibration[
                "primary_comparison_authorized"
            ],
            "proven_infeasible_arms": calibration["proven_infeasible_arms"],
        },
        "primary_comparison": {
            "status": "not_run_not_authorized",
            "record_count": 0,
            "outcome_claims": "none",
        },
        "decision": {
            "report_path": str(decision_path),
            "recommendation": decision["recommendation"],
            "recommendation_count": decision["recommendation_count"],
        },
        "artifact_count": len(artifacts),
        "artifact_total_bytes": sum(int(item["bytes"]) for item in artifacts),
        "artifacts": artifacts,
        "regeneration_contract": {
            "source_repository_root": str(source_repository_root),
            "source_checkout_root": str(regeneration_source_root),
            "source_commit": args.code_commit,
            "source_preparation": "detached_git_worktree_or_exact_clean_reuse",
            "output_root": str(regeneration_output_root),
            "output_root_was_absent_at_manifest_write": True,
            "accepted_root_is_never_overwritten": True,
        },
        "regeneration_commands": commands,
        "retention_reason": (
            "preserve exact T067 cost attribution and fail-closed calibration "
            "for maintainer review and the recommended boundary-batching task"
        ),
        "raw_artifacts_may_be_deleted_when": (
            "after T067 is merged and the maintainer confirms the recommended "
            "follow-up has copied every required compact report and identity"
        ),
        "large_artifacts_committed_to_git": False,
        "command_passed": True,
    }
    retention_path = root / "t067-retention-manifest.json"
    write_t067_report(retention_path, retention)
    print(json.dumps(_artifact_identity(retention_path, root), sort_keys=True))
    return 0


def _identity(
    path: Path,
    expected_bytes: int,
    expected_sha256: str,
    expected_schema: str | None,
) -> dict[str, Any]:
    identity = _file_identity(path)
    if identity["bytes"] != expected_bytes or identity["sha256"] != expected_sha256:
        raise SystemExit(f"T067 input identity mismatch: {path}")
    if expected_schema is not None and identity["schema_id"] != expected_schema:
        raise SystemExit(f"T067 input schema mismatch: {path}")
    return identity


def _artifact_identity(path: Path, root: Path) -> dict[str, Any]:
    identity = _file_identity(path)
    identity["relative_path"] = path.relative_to(root).as_posix()
    return identity


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"missing T067 artifact: {path}")
    schema = None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            schema = value.get("schema_id")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "schema_id": schema,
    }


def _load_json(path: Path, schema: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_id") != schema:
        raise SystemExit(f"unsupported T067 artifact schema: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _regeneration_commands(
    *,
    source_repository_root: Path,
    source_checkout_root: Path,
    accepted_root: Path,
    output_root: Path,
    input_root: Path,
    code_commit: str,
) -> list[str]:
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
    python_path = (
        "PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed-t062/"
        "build-t062-py313:"
        f"{source_checkout_root / 'src'}"
    )
    python_executable = "/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13"
    shard_args = " ".join(
        f"--shard {shlex.quote(str(output_root / 'initial-budget-1' / f'shard-{i}.json'))}"
        for i in range(16)
    )
    next_output_root = output_root.with_name(f"{output_root.name}-next")
    source_repo = shlex.quote(str(source_repository_root))
    source_checkout = shlex.quote(str(source_checkout_root))
    fresh_output = shlex.quote(str(output_root))
    commit = shlex.quote(code_commit)
    return [
        (
            "set -euo pipefail; "
            f"source_repo={source_repo}; source_checkout={source_checkout}; "
            f"output_root={fresh_output}; code_commit={commit}; "
            'test ! -e "$output_root"; '
            'if [ -e "$source_checkout" ]; then '
            'test "$(git -C "$source_checkout" rev-parse HEAD)" = "$code_commit"; '
            'test -z "$(git -C "$source_checkout" status --porcelain)"; '
            "else "
            'git -C "$source_repo" cat-file -e "$code_commit^{commit}"; '
            'git -C "$source_repo" worktree add --detach '
            '"$source_checkout" "$code_commit"; '
            "fi; "
            'test "$(git -C "$source_checkout" rev-parse HEAD)" = "$code_commit"; '
            'test -z "$(git -C "$source_checkout" status --porcelain)"; '
            'mkdir -p "$output_root"'
        ),
        (
            f"cd {shlex.quote(str(source_checkout_root))} && "
            "STSRL_LIGHTSPEED_BUILD_JOBS=16 "
            "bash scripts/verify_lightspeed_source.sh "
            "/home/lsmft/stsrl-spikes/sts_lightspeed > "
            f"{shlex.quote(str(output_root / 'pinned-source-verifier.log'))} 2>&1"
        ),
        (
            f"cd {shlex.quote(str(source_checkout_root))} && {python_path} "
            f"{python_executable} "
            "scripts/verify_t067_semantic_equivalence.py "
            f"--cohort {shlex.quote(str(cohort))} "
            f"--checkpoint {shlex.quote(str(checkpoint))} "
            f"--t061-retention-manifest {shlex.quote(str(t061))} "
            f"--preflight-output {shlex.quote(str(output_root / 'semantic-preflight.json'))} "
            f"--output {shlex.quote(str(output_root / 't067-semantic-equivalence.json'))} "
            f"--code-commit {code_commit}"
        ),
        (
            f"cd {shlex.quote(str(source_checkout_root))} && {python_path} "
            f"{python_executable} "
            "scripts/orchestrate_t067_calibration.py "
            f"--repo-root {shlex.quote(str(source_checkout_root))} "
            f"--artifact-root {shlex.quote(str(output_root))} "
            f"--input-root {shlex.quote(str(input_root))} "
            f"--code-commit {code_commit}"
        ),
        (
            f"cd {shlex.quote(str(source_checkout_root))} && {python_path} "
            f"{python_executable} "
            f"scripts/merge_t067_battle_search_v2.py {shard_args} "
            f"--raw-merged {shlex.quote(str(output_root / 't067-budget-1-raw-merged.json'))} "
            f"--output {shlex.quote(str(output_root / 't067-cost-attribution.json'))} "
            f"--cohort {shlex.quote(str(cohort))} "
            f"--checkpoint {shlex.quote(str(checkpoint))} "
            f"--t061-retention-manifest {shlex.quote(str(t061))} "
            f"--input-preflight-report "
            f"{shlex.quote(str(input_root / EXPECTED_INPUTS['t062_input_preflight'][0]))} "
            "--normalization-family initial_budget_1_both_cost_metrics "
            "--record-range 0:16"
        ),
        (
            f"cd {shlex.quote(str(source_checkout_root))} && {python_path} "
            f"{python_executable} "
            "scripts/finalize_t067_artifacts.py "
            f"--repo-root {shlex.quote(str(source_checkout_root))} "
            f"--source-repository-root {shlex.quote(str(source_repository_root))} "
            f"--regeneration-source-root {shlex.quote(str(source_checkout_root))} "
            f"--regeneration-output-root {shlex.quote(str(next_output_root))} "
            f"--artifact-root {shlex.quote(str(output_root))} "
            f"--input-root {shlex.quote(str(input_root))} "
            f"--attribution-report {shlex.quote(str(output_root / 't067-cost-attribution.json'))} "
            f"--stage-execution-report {shlex.quote(str(output_root / 't067-stage-execution.json'))} "
            f"--semantic-report {shlex.quote(str(output_root / 't067-semantic-equivalence.json'))} "
            f"--verifier-log {shlex.quote(str(output_root / 'pinned-source-verifier.log'))} "
            f"--code-commit {code_commit}"
        ),
    ]


def _validate_checkout_commit(repo_root: Path, code_commit: str) -> None:
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


def _validate_regeneration_roles(
    *,
    accepted_root: Path,
    source_repository_root: Path,
    source_checkout_root: Path,
    output_root: Path,
) -> None:
    normalized_roles = {
        "source repository": source_repository_root.as_posix(),
        "source checkout": source_checkout_root.as_posix(),
        "regeneration output": output_root.as_posix(),
    }
    for label, value in normalized_roles.items():
        if "/.claude/worktrees/" in value:
            raise SystemExit(
                f"T067 {label} must not depend on disposable .claude/worktrees"
            )
    if output_root == accepted_root:
        raise SystemExit("T067 regeneration output must differ from the accepted root")
    if output_root.exists():
        raise SystemExit(
            f"T067 regeneration output must be a fresh absent root: {output_root}"
        )
    if (
        source_checkout_root == output_root
        or source_checkout_root in output_root.parents
        or output_root in source_checkout_root.parents
    ):
        raise SystemExit("T067 regeneration source and output roles must be disjoint")
    if (
        accepted_root == source_checkout_root
        or accepted_root in source_checkout_root.parents
        or source_checkout_root in accepted_root.parents
    ):
        raise SystemExit("T067 accepted evidence and source roles must be disjoint")
    if accepted_root in output_root.parents or output_root in accepted_root.parents:
        raise SystemExit("T067 accepted and regeneration output roots must be siblings")
    if (
        "/artifacts/t067-battle-search-v2-inference-cost-repair/"
        not in output_root.as_posix()
    ):
        raise SystemExit(
            "T067 regeneration output is outside the stable ignored namespace"
        )


def _validate_regeneration_commands(
    *,
    commands: list[str],
    code_commit: str,
    source_checkout_root: Path,
    accepted_root: Path,
    output_root: Path,
) -> None:
    if len(commands) != 6:
        raise SystemExit("T067 retention requires six durable regeneration commands")
    if any(".claude/worktrees" in command for command in commands):
        raise SystemExit("T067 regeneration commands use a disposable worktree")
    preparation = commands[0]
    for marker in (
        code_commit,
        "worktree add --detach",
        'test ! -e "$output_root"',
        str(source_checkout_root),
        str(output_root),
    ):
        if marker not in preparation:
            raise SystemExit(f"T067 source preparation lacks marker: {marker}")
    if any(str(source_checkout_root) not in command for command in commands[1:]):
        raise SystemExit(
            "T067 regeneration stages do not use the exact source checkout"
        )
    if any(str(output_root) not in command for command in commands):
        raise SystemExit("T067 regeneration stages do not use the fresh output root")
    if any(str(accepted_root) in command for command in commands):
        raise SystemExit("T067 regeneration commands target accepted evidence")


if __name__ == "__main__":
    raise SystemExit(main())
