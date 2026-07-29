#!/usr/bin/env python3
"""Aggregate completed T070 stages, decide, and write compact retention evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sts_combat_rl.commands.t070_search_v2_audit import (
    HIGH_BUDGET_STAGE_CONFIGS,
    PRIMARY_STAGE_CONFIGS,
    build_budget_curve_and_geometry,
    build_decision_report,
    build_primary_report,
    build_retention_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    reports = root / "reports"
    if reports.exists() or (root / "t070-retention-manifest.json").exists():
        raise SystemExit("T070 finalizer refuses to overwrite visible outcomes")
    reports.mkdir(parents=True, exist_ok=True)
    primary_stages = {
        name: _load(root / "primary" / name / "merged.json")
        for name, *_ in PRIMARY_STAGE_CONFIGS
    }
    high_stages = {
        name: _load(root / "high-budget" / name / "merged.json")
        for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
    }
    primary = build_primary_report(primary_stages)
    curve, geometry = build_budget_curve_and_geometry(high_stages)
    decision = build_decision_report(primary, curve, geometry)
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
        "stages": [
            _load(root / "primary" / name / "stage-execution.json")
            for name, *_ in PRIMARY_STAGE_CONFIGS
        ]
        + [
            _load(root / "high-budget" / name / "stage-execution.json")
            for name, *_ in HIGH_BUDGET_STAGE_CONFIGS
        ],
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


def _write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
