#!/usr/bin/env python3
"""Merge 16 paired T069 shards and emit feasibility plus initial calibration."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t062_battle_search_v2 import (
    merge_t062_comparison_reports_from_paths,
)
from sts_combat_rl.commands.t069_public_context_projection import (
    T069_ATTRIBUTION_SCHEMA_ID,
    build_t069_attribution_and_feasibility_report,
    build_t069_calibration_report,
    build_t069_decision_report,
)


COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
CHECKPOINT_SHA256 = "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
T068_MANIFEST_SHA256 = (
    "bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678"
)
NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unprojected-shard", action="append", required=True)
    parser.add_argument("--projected-shard", action="append", required=True)
    parser.add_argument("--identity-shard", action="append", required=True)
    parser.add_argument("--unprojected-merged", type=Path, required=True)
    parser.add_argument("--projected-merged", type=Path, required=True)
    parser.add_argument("--attribution-output", type=Path, required=True)
    parser.add_argument("--feasibility-output", type=Path, required=True)
    parser.add_argument("--calibration-output", type=Path, required=True)
    parser.add_argument("--decision-output", type=Path)
    parser.add_argument("--semantic-report", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--t068-retention-manifest", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-verifier", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if not (
        len(args.unprojected_shard)
        == len(args.projected_shard)
        == len(args.identity_shard)
        == 16
    ):
        raise SystemExit("T069 merge requires 16 paired shard sets")
    outputs = (
        args.unprojected_merged,
        args.projected_merged,
        args.attribution_output,
        args.feasibility_output,
        args.calibration_output,
    )
    if any(path.exists() for path in outputs):
        raise SystemExit("T069 merge refuses to overwrite output")

    unprojected = merge_t062_comparison_reports_from_paths(
        shard_paths=[Path(path) for path in args.unprojected_shard],
        output_path=args.unprojected_merged,
        expected_record_count=16,
        bootstrap_resamples=2000,
    )
    projected = merge_t062_comparison_reports_from_paths(
        shard_paths=[Path(path) for path in args.projected_shard],
        output_path=args.projected_merged,
        expected_record_count=16,
        bootstrap_resamples=2000,
    )
    before_records: list[dict[str, Any]] = []
    after_records: list[dict[str, Any]] = []
    for expected_index, path_text in enumerate(args.identity_shard):
        path = Path(path_text)
        raw = _load_json(path)
        if (
            raw.get("schema_id") != "t069-projection-paired-shard-v1"
            or raw.get("command_passed") is not True
            or raw.get("shard_index") != expected_index
            or raw.get("record_range") != f"{expected_index}:{expected_index + 1}"
        ):
            raise SystemExit(f"T069 identity shard is invalid: {path}")
        before_records.extend(raw["unprojected_identity_records"])
        after_records.extend(raw["projected_identity_records"])

    semantic = _load_json(args.semantic_report)
    input_identities = {
        "t052_fixed_cohort": _identity(args.cohort, COHORT_SHA256),
        "t043_checkpoint": _identity(args.checkpoint, CHECKPOINT_SHA256),
        "t061_retention_manifest": _identity(
            args.t061_retention_manifest,
            None,
        ),
        "t068_retention_manifest": _identity(
            args.t068_retention_manifest,
            T068_MANIFEST_SHA256,
        ),
        "sts_lightspeed_source_manifest": _identity(
            args.source_manifest,
            None,
        ),
        "sts_lightspeed_source_verifier": _identity(
            args.source_verifier,
            None,
        ),
        "t069_semantic_report": _identity(args.semantic_report, None),
    }
    feasibility = build_t069_attribution_and_feasibility_report(
        unprojected=unprojected,
        projected=projected,
        unprojected_identity_records=before_records,
        projected_identity_records=after_records,
        semantic_report=semantic,
        input_identities=input_identities,
        code_commit=args.code_commit,
        native_commit=NATIVE_COMMIT,
    )
    attribution = {
        "schema_id": T069_ATTRIBUTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "record_range": "0:16",
        "worker_count": 16,
        "shard_count": 16,
        "input_identities": input_identities,
        "feature_identity_pair_count": feasibility["feature_identity_pair_count"],
        "feature_identity_pairs": feasibility["feature_identity_pairs"],
        "component_attribution": feasibility["component_attribution"],
        "public_context_invariance_and_vector_exact": feasibility["gates"][
            "exact_complete_scorer_inputs"
        ],
        "command_passed": feasibility["gates"]["exact_complete_scorer_inputs"],
    }
    calibration = build_t069_calibration_report([projected])
    _write_json(args.attribution_output, attribution)
    _write_json(args.feasibility_output, feasibility)
    _write_json(args.calibration_output, calibration)

    decisive = not feasibility["conditional_calibration_authorized"] or bool(
        calibration["minimum_budget_infeasible_arms"]
    )
    if decisive:
        if args.decision_output is None:
            raise SystemExit("T069 decisive initial gate requires --decision-output")
        decision = build_t069_decision_report(
            feasibility,
            calibration if feasibility["conditional_calibration_authorized"] else None,
        )
        _write_json(args.decision_output, decision)
    return 0


def _identity(path: Path, expected_sha256: str | None) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"T069 missing identity input: {path}")
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and sha256 != expected_sha256:
        raise SystemExit(f"T069 input hash changed: {path}")
    schema_id = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            schema_id = raw.get("schema_id")
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256,
        "schema_id": schema_id,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"T069 missing JSON input: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"T069 expected JSON object: {path}")
    return raw


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"T069 refuses to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
