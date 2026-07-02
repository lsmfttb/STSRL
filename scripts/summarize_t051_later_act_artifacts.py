"""Write a lightweight manifest for the T051 retained source artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ARM_CONFIGS = (
    ("baseline_oracle_search_v1", "oracle_search_v1"),
    ("post_search_model_guided_v2", "model_guided_oracle_search_v2"),
    ("root_prior_guided_v1", "root_prior_guided_oracle_search_v1"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--runtime-python", required=True)
    parser.add_argument("--runtime-build", required=True)
    parser.add_argument("--task-id", default="T051")
    parser.add_argument("--total-runs", type=int, required=True)
    parser.add_argument("--source-seed-start", type=int, required=True)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--non-combat-seed", type=int, required=True)
    parser.add_argument("--step-cap", type=int, required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--root-selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.artifact_root
    reachability_path = root / "reachability-report.json"
    reachability = _load_json(reachability_path)
    reachability_arms = {
        str(arm.get("label")): arm
        for arm in _list(reachability.get("arms"))
        if isinstance(arm, dict) and isinstance(arm.get("label"), str)
    }
    manifest = {
        "schema_id": "t051-search-controlled-later-act-retention-manifest-v1",
        "schema_version": 1,
        "task_id": args.task_id,
        "repo": {
            "path_wsl": args.repo,
            "path_windows": _wsl_to_windows_path(args.repo),
        },
        "retention_path": _path_identity(root),
        "retention_reason": (
            "T051 review evidence and stable local input for the next selected "
            "source-generation or teacher/checkpoint task; contains source "
            "shards, merged pools, coverage shards, merged coverage reports, "
            "reachability report, logs, and stage timings."
        ),
        "deletion_condition": (
            "May be deleted after the T051 PR is reviewed and the next accepted "
            "task either records this manifest path/hash as input provenance or "
            "explicitly declines to consume these raw artifacts."
        ),
        "run_config": {
            "arms": [
                {"label": label, "controller": controller}
                for label, controller in ARM_CONFIGS
            ],
            "ascension": 20,
            "source_seed_range": (
                f"{args.source_seed_start}.."
                f"{args.source_seed_start + args.total_runs - 1}"
            ),
            "total_source_runs_per_arm": args.total_runs,
            "shards_per_arm": args.shards,
            "workers_per_parallel_stage": args.workers,
            "non_combat_seed": args.non_combat_seed,
            "step_cap": args.step_cap,
            "search_budget": args.budget,
            "root_selection": args.root_selection,
        },
        "provenance": {
            "checkpoint": _file_identity(args.checkpoint),
            "checkpoint_role": (
                "Accepted T048/T049/T050-compatible T043 checkpoint used by "
                "post-search and root-prior guided arms."
            ),
            "runtime_python": args.runtime_python,
            "runtime_pythonpath": f"{args.runtime_build}:{args.repo}/src",
            "runtime_build": args.runtime_build,
            "lightspeed_source_verifier": (
                "scripts/verify_lightspeed_source.sh "
                "/home/lsmft/stsrl-spikes/sts_lightspeed"
            ),
        },
        "stage_times": _load_stage_times(root / "stage-times.tsv"),
        "arms": [
            _arm_summary(root, label, reachability_arms.get(label, {}))
            for label, _ in ARM_CONFIGS
        ],
        "reachability": {
            "report": _file_identity(reachability_path),
            "command_passed": reachability.get("command_passed"),
            "comparison": reachability.get("comparison", {}),
            "followup_hint": reachability.get("followup_hint"),
        },
        "regeneration": {
            "script": _file_identity(Path(args.repo) / "scripts" / "run_t051_later_act_source_collection.sh"),
            "summary_script": _file_identity(Path(args.repo) / "scripts" / "summarize_t051_later_act_artifacts.py"),
            "command_note": (
                "Run from Windows PowerShell with wsl.exe -d Ubuntu -e env "
                f"REPO={args.repo} OUT={root} bash "
                f"{args.repo}/scripts/run_t051_later_act_source_collection.sh"
            ),
            "stdout_log": _optional_file_identity(root / "run_t051_scale.out"),
            "stderr_log": _optional_file_identity(root / "run_t051_scale.err"),
            "stage_times": _file_identity(root / "stage-times.tsv"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


def _arm_summary(
    root: Path,
    label: str,
    reachability_arm: dict[str, Any],
) -> dict[str, Any]:
    arm_dir = root / label
    merge_manifest = _load_json(arm_dir / "source-merge-manifest.json")
    coverage = _load_json(arm_dir / "merged-coverage.json")
    natural = _mapping(coverage.get("natural_coverage"))
    restore = _mapping(coverage.get("restore_verification"))
    coverage_shards = _coverage_shard_identities(coverage)
    source_shards = _list(merge_manifest.get("source_shards"))
    act_counts = _mapping(natural.get("act_counts"))
    room_type_counts = _mapping(natural.get("room_type_counts"))
    return {
        "label": label,
        "source_runs": _first_present(
            reachability_arm.get("source_run_count"),
            natural.get("source_run_count"),
        ),
        "terminal_runs": _first_present(
            reachability_arm.get("terminal_run_count"),
            natural.get("terminal_run_count"),
        ),
        "truncated_runs": _first_present(
            reachability_arm.get("truncated_run_count"),
            natural.get("truncated_run_count"),
        ),
        "natural_battle_starts": _first_present(
            reachability_arm.get("natural_battle_start_count"),
            natural.get("natural_battle_start_count"),
        ),
        "act_counts": act_counts,
        "room_type_counts": room_type_counts,
        "battle_outcome_counts": natural.get("reported_battle_outcome_counts", {}),
        "structured_resource_outcome_status_counts": natural.get(
            "structured_resource_outcome_status_counts", {}
        ),
        "act1_boss_battle_start_count": _first_present(
            reachability_arm.get("act1_boss_battle_start_count"),
            room_type_counts.get("BOSS", 0),
        ),
        "later_act_battle_start_count": _first_present(
            reachability_arm.get("later_act_battle_start_count"),
            _later_act_start_count(act_counts),
        ),
        "later_act_source_run_count": _first_present(
            reachability_arm.get("later_act_source_run_count"),
            natural.get("later_act_source_run_count"),
        ),
        "training_allowed": _training_allowed(coverage),
        "coverage_command_passed": coverage.get("command_passed"),
        "restore_verification": restore,
        "key_files": {
            "merged_pool": _file_identity(arm_dir / "merged-pool.jsonl"),
            "merged_coverage": _file_identity(arm_dir / "merged-coverage.json"),
            "source_merge_manifest": _file_identity(
                arm_dir / "source-merge-manifest.json"
            ),
        },
        "source_shards": {
            "directory": _path_identity(arm_dir / "source-shards"),
            "shards": source_shards,
        },
        "coverage_shards": {
            "directory": _path_identity(arm_dir / "coverage-shards"),
            "shards": coverage_shards,
        },
    }


def _later_act_start_count(act_counts: dict[str, Any]) -> int:
    count = 0
    for raw_act, raw_count in act_counts.items():
        try:
            act = int(raw_act)
        except (TypeError, ValueError):
            continue
        if act > 1 and isinstance(raw_count, int) and not isinstance(raw_count, bool):
            count += raw_count
    return count


def _training_allowed(coverage: dict[str, Any]) -> bool | None:
    report = coverage.get("training_gate_report")
    if isinstance(report, dict):
        value = report.get("training_allowed")
        if isinstance(value, bool):
            return value
    return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _coverage_shard_identities(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = _mapping(coverage.get("input_artifacts"))
    shards = _list(artifacts.get("coverage_shards"))
    return [dict(item) for item in shards if isinstance(item, dict)]


def _load_stage_times(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        arm, stage, workers, shards, record_range, elapsed = raw_line.split("\t")
        rows.append(
            {
                "arm": arm,
                "stage": stage,
                "workers": int(workers),
                "shards": int(shards),
                "record_range": record_range,
                "elapsed_seconds": int(elapsed),
            }
        )
    return rows


def _path_identity(path: Path) -> dict[str, Any]:
    files = [child for child in path.rglob("*") if child.is_file()] if path.exists() else []
    return {
        "path_wsl": str(path),
        "path_windows": _wsl_to_windows_path(str(path)),
        "file_count": len(files),
        "total_bytes": sum(child.stat().st_size for child in files),
    }


def _file_identity(path: Path) -> dict[str, Any]:
    return {
        "path_wsl": str(path),
        "path_windows": _wsl_to_windows_path(str(path)),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _optional_file_identity(path: Path) -> dict[str, Any] | None:
    return _file_identity(path) if path.exists() else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return data


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _wsl_to_windows_path(raw_path: str) -> str | None:
    prefix = "/mnt/"
    if not raw_path.startswith(prefix) or len(raw_path) < len(prefix) + 2:
        return None
    drive = raw_path[len(prefix)]
    remainder = raw_path[len(prefix) + 2 :]
    windows_remainder = remainder.replace("/", "\\")
    return f"{drive.upper()}:\\{windows_remainder}"


if __name__ == "__main__":
    raise SystemExit(main())
