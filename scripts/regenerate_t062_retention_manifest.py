#!/usr/bin/env python3
"""Rebuild the stable T062 early-exit retention manifest after calibration."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from sts_combat_rl.commands.t062_battle_search_v2 import (
    T043_CHECKPOINT_SHA256,
    T052_COHORT_SHA256,
    write_t062_retention_manifest_from_paths,
)


def _wsl_command(body: str) -> str:
    return f"wsl.exe -d Ubuntu -e bash -lc {shlex.quote(body)}"


def _wait_for_background_jobs_shell() -> str:
    """Return the fail-closed wait loop used by both 16-shard stages."""

    return (
        'failed=0; for pid in "${pids[@]}"; do '
        'if ! wait "$pid"; then failed=1; fi; done; '
        'if [ "$failed" -ne 0 ]; then exit 1; fi; '
    )


def _stage_command(
    *,
    artifact_root: str,
    stage_directory: str,
    merged_report_name: str,
    merge_stdout_log_name: str,
    merge_stderr_log_name: str,
    family: str,
    arm_budgets: tuple[str, ...],
    source_root: str,
    native_build_root: str,
    python_executable: str,
    cohort_path: str,
    checkpoint_path: str,
) -> str:
    arm_budget_args = " ".join(
        f"--t062-arm-budget {shlex.quote(value)}" for value in arm_budgets
    )
    stable_root = f"{artifact_root}/{stage_directory}"
    command = (
        "set -euo pipefail; "
        f"stable_root={shlex.quote(stable_root)}; "
        'root="${stable_root}.staging"; rm -rf "$root"; mkdir -p "$root"; '
        "pids=(); "
        "for start in $(seq 0 15); do end=$((start + 1)); "
        "("
        f"PYTHONPATH={shlex.quote(native_build_root)}:{shlex.quote(source_root)} "
        f"{shlex.quote(python_executable)} -m sts_combat_rl.cli "
        f"--lightspeed-t062-battle-search-v2-comparison {shlex.quote(cohort_path)} "
        '--t062-battle-search-v2-comparison-report "$root/shard-$start.json" '
        f"--t062-battle-search-v2-family {shlex.quote(family)} "
        f"--model-guided-oracle-checkpoint {shlex.quote(checkpoint_path)} "
        "--sim-seed 1 --sim-ascension 20 --sim-steps 200 --search-budget 100 "
        f"{arm_budget_args} "
        '--oracle-root-selection highest_mean --record-range "$start:$end" '
        '--workers 1 --shards 1 > "$root/shard-$start.stdout.log" '
        '2> "$root/shard-$start.stderr.log") & pids+=("$!"); done; '
        f"{_wait_for_background_jobs_shell()}"
        "merge_args=(); for start in $(seq 0 15); do "
        'merge_args+=(--t062-comparison-shard "$root/shard-$start.json"); done; '
        f"PYTHONPATH={shlex.quote(native_build_root)}:{shlex.quote(source_root)} "
        f"{shlex.quote(python_executable)} -m sts_combat_rl.cli "
        f'--merge-t062-comparison "$root/{merged_report_name}" '
        '--t062-expected-record-count 16 "${merge_args[@]}" '
        f'> "$root/{merge_stdout_log_name}" '
        f'2> "$root/{merge_stderr_log_name}"; '
        'rm -rf "$stable_root"; mv "$root" "$stable_root"'
    )
    return _wsl_command(command)


def _derived_report_commands(
    *,
    artifact_root: str,
    source_root: str,
    python_executable: str,
    t061_retention_manifest: str,
    cohort_path: str,
    checkpoint_path: str,
) -> tuple[str, str, str]:
    python = f"PYTHONPATH={shlex.quote(source_root)} {shlex.quote(python_executable)}"
    preflight = _wsl_command(
        "set -euo pipefail; "
        f"root={shlex.quote(artifact_root)}; {python} -m sts_combat_rl.cli "
        '--t062-input-preflight-report "$root/t062-input-preflight.json" '
        f"--t062-t061-retention-manifest {shlex.quote(t061_retention_manifest)} "
        f"--t062-fixed-cohort {shlex.quote(cohort_path)} "
        f"--t062-checkpoint {shlex.quote(checkpoint_path)} "
        '> "$root/t062-input-preflight.stdout.log" '
        '2> "$root/t062-input-preflight.stderr.log"'
    )
    calibration = _wsl_command(
        "set -euo pipefail; "
        f"root={shlex.quote(artifact_root)}; {python} -m sts_combat_rl.cli "
        '--t062-calibration-manifest "$root/t062-calibration-manifest-v2.json" '
        "--t062-nominal-budget-calibration "
        '"$root/nominal-100-py313-with-native/'
        't062-calibration-nominal-100-merged.json" '
        "--t062-wall-clock-candidate-calibration "
        '"$root/wall-candidate-guided-1-py313/'
        't062-wall-candidate-guided-1-merged.json" '
        '> "$root/t062-calibration-manifest.stdout.log" '
        '2> "$root/t062-calibration-manifest.stderr.log"'
    )
    decision = _wsl_command(
        "set -euo pipefail; "
        f"root={shlex.quote(artifact_root)}; {python} -m sts_combat_rl.cli "
        "--t062-early-exit-decision-report "
        '"$root/t062-early-exit-decision-report-v2.json" '
        "--t062-early-exit-calibration-manifest "
        '"$root/t062-calibration-manifest-v2.json" '
        '> "$root/t062-early-exit-decision-report.stdout.log" '
        '2> "$root/t062-early-exit-decision-report.stderr.log"'
    )
    return preflight, calibration, decision


def _retention_command(args: argparse.Namespace) -> str:
    stable_script = (
        Path(args.windows_source_root)
        / "scripts"
        / "regenerate_t062_retention_manifest.py"
    )
    return (
        f"$env:PYTHONPATH='{Path(args.windows_source_root) / 'src'}'; "
        f"python '{stable_script}' "
        f"--artifact-root '{args.artifact_root}' "
        f"--windows-source-root '{args.windows_source_root}' "
        f"--wsl-artifact-root '{args.wsl_artifact_root}' "
        f"--source-root '{args.source_root}' "
        f"--native-build-root '{args.native_build_root}' "
        f"--python-executable '{args.python_executable}'"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--windows-source-root", default=r"D:\DeadlycatCoding\STSRL")
    parser.add_argument(
        "--wsl-artifact-root",
        default=(
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
            "t062-battle-search-v2-minimal-surface/calibration/native-prior-fix-3cb9ebe"
        ),
    )
    parser.add_argument("--source-root", default="/mnt/d/DeadlycatCoding/STSRL/src")
    parser.add_argument(
        "--native-build-root",
        default="/home/lsmft/stsrl-spikes/sts_lightspeed-t062/build-t062-py313",
    )
    parser.add_argument(
        "--python-executable",
        default="/home/lsmft/stsrl-spikes/py313-torch/bin/python3.13",
    )
    parser.add_argument(
        "--t061-retention-manifest",
        default=(
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
            "t061-a20-reachability-bottleneck-decomposition/t061-retention-manifest.json"
        ),
    )
    parser.add_argument(
        "--cohort-path",
        default=(
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
            "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl"
        ),
    )
    parser.add_argument(
        "--checkpoint-path",
        default=(
            "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
            "t044-de-assisted-comparison-pr/t043-assist_0-smoke/"
            "t043-assist_0-smoke-checkpoint.pt"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.artifact_root
    nominal_directory = root / "nominal-100-py313-with-native"
    wall_clock_directory = root / "wall-candidate-guided-1-py313"
    nominal_command = _stage_command(
        artifact_root=args.wsl_artifact_root,
        stage_directory="nominal-100-py313-with-native",
        merged_report_name="t062-calibration-nominal-100-merged.json",
        merge_stdout_log_name="t062-calibration-nominal-100-merge.stdout.log",
        merge_stderr_log_name="t062-calibration-nominal-100-merge.stderr.log",
        family="nominal",
        arm_budgets=(),
        source_root=args.source_root,
        native_build_root=args.native_build_root,
        python_executable=args.python_executable,
        cohort_path=args.cohort_path,
        checkpoint_path=args.checkpoint_path,
    )
    wall_clock_command = _stage_command(
        artifact_root=args.wsl_artifact_root,
        stage_directory="wall-candidate-guided-1-py313",
        merged_report_name="t062-wall-candidate-guided-1-merged.json",
        merge_stdout_log_name="t062-wall-candidate-guided-1-merge.stdout.log",
        merge_stderr_log_name="t062-wall-candidate-guided-1-merge.stderr.log",
        family="wall_clock_normalized",
        arm_budgets=("prior_only=1", "value_only=1", "prior_value=1"),
        source_root=args.source_root,
        native_build_root=args.native_build_root,
        python_executable=args.python_executable,
        cohort_path=args.cohort_path,
        checkpoint_path=args.checkpoint_path,
    )
    preflight_command, calibration_command, decision_command = _derived_report_commands(
        artifact_root=args.wsl_artifact_root,
        source_root=args.source_root,
        python_executable=args.python_executable,
        t061_retention_manifest=args.t061_retention_manifest,
        cohort_path=args.cohort_path,
        checkpoint_path=args.checkpoint_path,
    )
    manifest = write_t062_retention_manifest_from_paths(
        output_path=root / "t062-retention-manifest-v3.json",
        root_artifacts={
            "input_preflight_report": root / "t062-input-preflight.json",
            "input_preflight_stdout_log": root / "t062-input-preflight.stdout.log",
            "input_preflight_stderr_log": root / "t062-input-preflight.stderr.log",
            "calibration_manifest": root / "t062-calibration-manifest-v2.json",
            "calibration_manifest_stdout_log": root
            / "t062-calibration-manifest.stdout.log",
            "calibration_manifest_stderr_log": root
            / "t062-calibration-manifest.stderr.log",
            "early_exit_decision": root / "t062-early-exit-decision-report-v2.json",
            "early_exit_decision_stdout_log": root
            / "t062-early-exit-decision-report.stdout.log",
            "early_exit_decision_stderr_log": root
            / "t062-early-exit-decision-report.stderr.log",
        },
        nominal_merged_report_path=(
            nominal_directory / "t062-calibration-nominal-100-merged.json"
        ),
        nominal_merge_stdout_log_path=(
            nominal_directory / "t062-calibration-nominal-100-merge.stdout.log"
        ),
        nominal_merge_stderr_log_path=(
            nominal_directory / "t062-calibration-nominal-100-merge.stderr.log"
        ),
        nominal_shard_directory=nominal_directory,
        nominal_regeneration_command=nominal_command,
        wall_clock_merged_report_path=(
            wall_clock_directory / "t062-wall-candidate-guided-1-merged.json"
        ),
        wall_clock_merge_stdout_log_path=(
            wall_clock_directory / "t062-wall-candidate-guided-1-merge.stdout.log"
        ),
        wall_clock_merge_stderr_log_path=(
            wall_clock_directory / "t062-wall-candidate-guided-1-merge.stderr.log"
        ),
        wall_clock_shard_directory=wall_clock_directory,
        wall_clock_regeneration_command=wall_clock_command,
        execution_identity={
            "controller": "battle_search_v2_oracle_like_v1",
            "controller_arms": ["baseline", "prior_only", "value_only", "prior_value"],
            "root_selection": "highest_mean",
            "action_space": "initial_no_potions",
            "baseline_search_budget": 100,
            "wall_clock_candidate_arm_budgets": {
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            "checkpoint_sha256": T043_CHECKPOINT_SHA256,
            "cohort_sha256": T052_COHORT_SHA256,
            "native_integration_repository": "lsmfttb/sts_lightspeed",
            "native_integration_ref": "stsrl/main",
            "native_commit": "3cb9ebecb87c38044b34aa0e013d42b222a04087",
        },
        regeneration_commands=[
            preflight_command,
            nominal_command,
            wall_clock_command,
            calibration_command,
            decision_command,
            _retention_command(args),
        ],
    )
    print(
        f"wrote {root / 't062-retention-manifest-v3.json'} "
        f"with {len(manifest['retained_artifacts'])} retained artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
