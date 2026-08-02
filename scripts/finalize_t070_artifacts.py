#!/usr/bin/env python3
"""Aggregate completed T070 stages, decide, and write compact retention evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sts_combat_rl.commands.t070_search_v2_audit import (
    HIGH_BUDGET_STAGE_CONFIGS,
    NATIVE_COMMIT,
    PRIMARY_STAGE_CONFIGS,
    STAGE_SCHEMA_ID,
    build_budget_curve_and_geometry,
    build_decision_report,
    build_primary_report,
    build_retention_manifest,
    validate_t070_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--native-checkout", type=Path, required=True)
    parser.add_argument("--native-build-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    reports = root / "reports"
    if reports.exists() or (root / "t070-retention-manifest.json").exists():
        raise SystemExit("T070 finalizer refuses to overwrite visible outcomes")
    preflight_path = root / "native-preflight" / "t070-native-capability-preflight.json"
    native_build_root = args.native_build_root.resolve()
    sys.path.insert(0, str(native_build_root))
    try:
        preflight = validate_t070_preflight(
            preflight_path,
            code_commit=args.code_commit,
            source_manifest_path=Path("docs/sts_lightspeed_source_manifest.json"),
            source_verifier_path=Path("scripts/verify_lightspeed_source.sh"),
            native_checkout=args.native_checkout,
            native_build_root=native_build_root,
        )
    finally:
        sys.path.remove(str(native_build_root))
    native_runtime_identity = preflight["native_runtime_identity"]
    stage_executions = [
        _validated_stage_execution(
            root / "primary" / name / "stage-execution.json",
            stage_name=name,
            stage_kind="primary",
            arm=arm,
            family=family,
            budget=budget,
            ranges=[
                "0:6",
                "6:12",
                "12:18",
                "18:24",
                "24:30",
                "30:36",
                "36:42",
                "42:48",
                "48:54",
                "54:60",
                "60:66",
                "66:72",
                "72:78",
                "78:83",
                "83:88",
                "88:93",
            ],
            code_commit=args.code_commit,
            native_runtime_identity=native_runtime_identity,
        )
        for name, arm, family, budget in PRIMARY_STAGE_CONFIGS
    ] + [
        _validated_stage_execution(
            root / "high-budget" / name / "stage-execution.json",
            stage_name=name,
            stage_kind="high_budget",
            arm=arm,
            family=family,
            budget=budget,
            ranges=[f"{index}:{index + 1}" for index in range(16)],
            code_commit=args.code_commit,
            native_runtime_identity=native_runtime_identity,
        )
        for name, arm, family, budget in HIGH_BUDGET_STAGE_CONFIGS
    ]
    primary_stages = {
        name: _load(root / "primary" / name / "merged.json")
        for name, *_ in PRIMARY_STAGE_CONFIGS
    }
    high_stages = {
        name: _load(root / "high-budget" / name / "merged.json")
        for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
    }
    if any(
        report.get("native_runtime_identity") != native_runtime_identity
        for report in (*primary_stages.values(), *high_stages.values())
    ):
        raise ValueError("T070 merged stage runtime identities differ from preflight")
    primary = build_primary_report(primary_stages)
    curve, geometry = build_budget_curve_and_geometry(high_stages)
    decision = build_decision_report(primary, curve, geometry)
    reports.mkdir(parents=True, exist_ok=True)
    paths = {
        "primary": reports / "t070-primary-comparison.json",
        "curve": reports / "t070-budget-curve.json",
        "geometry": reports / "t070-tree-geometry.json",
        "decision": reports / "t070-decision.json",
    }
    for key, value in (
        ("primary", primary),
        ("curve", curve),
        ("geometry", geometry),
        ("decision", decision),
    ):
        _write(paths[key], value)
    stage_inventory = {
        "schema_id": "t070-stage-execution-v1",
        "schema_version": 1,
        "task_id": "T070",
        "stages": stage_executions,
        "primary_stage_count": 10,
        "high_budget_stage_count": 6,
        "command_passed": True,
    }
    stage_path = reports / "t070-stage-execution.json"
    _write(stage_path, stage_inventory)
    retained = [
        root / "native-preflight" / "t070-native-capability-preflight.json",
        root / "native-preflight" / "source-verifier.stdout.log",
        root / "native-preflight" / "source-verifier.stderr.log",
        root / "native-preflight" / "runtime-build.stdout.log",
        root / "native-preflight" / "runtime-build.stderr.log",
        root / "frozen-manifest" / "t070-frozen-manifest.json",
        root / "budget-subset" / "t070-budget-subset-manifest.json",
        root / "budget-subset" / "t070-budget-subset-cohort.jsonl",
        *paths.values(),
        stage_path,
        *[
            root / "primary" / name / "merged.json"
            for name, *_ in PRIMARY_STAGE_CONFIGS
        ],
        *[
            root / "primary" / name / "stage-execution.json"
            for name, *_ in PRIMARY_STAGE_CONFIGS
        ],
        *[
            shard
            for name, *_ in PRIMARY_STAGE_CONFIGS
            for shard in (root / "primary" / name).glob("shard-*.json")
        ],
        *[
            log
            for name, *_ in PRIMARY_STAGE_CONFIGS
            for log in (root / "primary" / name / "logs").glob("*.log")
        ],
        *[
            root / "high-budget" / name / "merged.json"
            for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
        ],
        *[
            root / "high-budget" / name / "stage-execution.json"
            for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
        ],
        *[
            shard
            for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
            for shard in (root / "high-budget" / name).glob("shard-*.json")
        ],
        *[
            log
            for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
            for log in (root / "high-budget" / name / "logs").glob("*.log")
        ],
    ]
    commands = [
        "freeze_t070_experiment.py --input-root <stable-artifacts> --artifact-root <t070-root> --code-commit <exact>",
        "orchestrate_t070_search_stage.py (each frozen stage; exact args in stage execution reports)",
        "finalize_t070_artifacts.py --artifact-root <t070-root> --code-commit <exact>",
    ]
    retention = build_retention_manifest(
        artifact_root=root,
        retained_paths=retained,
        regeneration_commands=commands,
        code_commit=args.code_commit,
        decision=decision,
    )
    _write(root / "t070-retention-manifest.json", retention)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validated_stage_execution(
    path: Path,
    *,
    stage_name: str,
    stage_kind: str,
    arm: str,
    family: str,
    budget: int,
    ranges: list[str],
    code_commit: str,
    native_runtime_identity,
):
    report = _load(path)
    workers = report.get("workers")
    if (
        report.get("schema_id") != STAGE_SCHEMA_ID
        or report.get("stage_name") != stage_name
        or report.get("stage_kind") != stage_kind
        or report.get("arm") != arm
        or report.get("family") != family
        or report.get("native_budget") != budget
        or report.get("tree_geometry_enabled")
        != (stage_kind == "high_budget" and arm == "prior_value")
        or report.get("code_commit") != code_commit
        or report.get("native_commit") != NATIVE_COMMIT
        or report.get("native_runtime_identity") != native_runtime_identity
        or report.get("record_ranges") != ranges
        or report.get("worker_count") != 16
        or report.get("shard_count") != 16
        or report.get("effective_parallel_workers") != 16
        or not isinstance(workers, list)
        or len(workers) != 16
        or any(
            worker.get("worker_index") != index
            or worker.get("record_range") != ranges[index]
            or worker.get("returncode") != 0
            or worker.get("native_runtime_identity") != native_runtime_identity
            for index, worker in enumerate(workers)
            if isinstance(worker, dict)
        )
        or not all(isinstance(worker, dict) for worker in workers)
        or report.get("command_passed") is not True
    ):
        raise ValueError(f"T070 stage execution is invalid: {stage_name}")
    return report


def _write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
