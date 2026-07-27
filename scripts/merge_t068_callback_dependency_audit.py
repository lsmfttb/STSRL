#!/usr/bin/env python3
"""Merge exact T068 shards; reject any provenance or stage-layout drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t068_native_boundary_batching import (
    T068_GUIDED_ARMS,
    build_t068_batch_feasibility_report,
    build_t068_callback_dependency_audit,
    build_t068_decision_report,
)


T067_MANIFEST_SHA256 = (
    "2119e36bccff86fd65f00474177d11bb222a05303651dc18423de7f1174d35da"
)
NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", action="append", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--native-source-audit", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--feasibility-output", type=Path, required=True)
    parser.add_argument("--decision-output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T068 merge requires an exact 40-character code commit")
    if len(args.shard) != 16:
        raise SystemExit("T068 merge requires exactly 16 shards")
    manifest = _load_json(args.input_manifest)
    if _sha256(args.input_manifest) != T067_MANIFEST_SHA256:
        raise SystemExit("T068 input manifest is not the exact accepted T067 contract")
    if manifest.get("schema_id") != "t067-battle-search-v2-retention-manifest-v2":
        raise SystemExit("T068 input manifest has the wrong schema")
    source_audit = _load_json(args.native_source_audit)
    if source_audit.get("native_commit") != NATIVE_COMMIT:
        raise SystemExit("T068 source audit native commit does not match T067")
    shards = [
        _load_shard(path, expected_index=index, code_commit=args.code_commit)
        for index, path in enumerate(args.shard)
    ]
    preflight_identities = [
        _canonical_preflight(shard["input_preflight"]) for shard in shards
    ]
    if any(value != preflight_identities[0] for value in preflight_identities[1:]):
        raise SystemExit("T068 shard preflight identities differ")
    input_identities = {
        "t067_retention_manifest": {
            "path": str(args.input_manifest),
            "sha256": T067_MANIFEST_SHA256,
            "schema_id": manifest["schema_id"],
            "artifact_count": manifest.get("artifact_count"),
            "artifact_total_bytes": manifest.get("artifact_total_bytes"),
        },
        "t052_t043_t061_preflight": preflight_identities[0],
    }
    audit = build_t068_callback_dependency_audit(
        shard_traces=shards,
        input_identities=input_identities,
        native_source_audit=source_audit,
        code_commit=args.code_commit,
    )
    costs = _aggregate_costs(shards)
    feasibility = build_t068_batch_feasibility_report(audit, prototype_costs=costs)
    decision = build_t068_decision_report(audit, feasibility)
    _write_fresh(args.audit_output, audit)
    _write_fresh(args.feasibility_output, feasibility)
    _write_fresh(args.decision_output, decision)
    print(
        "T068 audit: "
        + ", ".join(
            f"{arm}={audit['arms'][arm]['request_count']} singleton requests"
            for arm in T068_GUIDED_ARMS
        )
    )
    return 0


def _load_shard(path: Path, *, expected_index: int, code_commit: str) -> dict[str, Any]:
    raw = _load_json(path)
    if raw.get("schema_id") != "t068-native-callback-dependency-shard-v1":
        raise SystemExit(f"T068 wrong shard schema: {path}")
    if (
        raw.get("code_commit") != code_commit
        or raw.get("native_commit") != NATIVE_COMMIT
    ):
        raise SystemExit(f"T068 shard commit identity mismatch: {path}")
    if (
        raw.get("shard_index") != expected_index
        or raw.get("record_range") != f"{expected_index}:{expected_index + 1}"
    ):
        raise SystemExit(f"T068 shard range identity mismatch: {path}")
    if (
        raw.get("shard_count") != 16
        or raw.get("worker_count") != 1
        or raw.get("stage_worker_count") != 16
    ):
        raise SystemExit(f"T068 shard worker layout mismatch: {path}")
    if raw.get("stage_classification") != "one_record_component_of_16_worker_audit":
        raise SystemExit(f"T068 shard stage classification mismatch: {path}")
    if (
        raw.get("command_passed") is not True
        or raw.get("comparison_successful") is not True
    ):
        raise SystemExit(f"T068 shard failed: {path}")
    if raw.get("comparison_problems"):
        raise SystemExit(f"T068 shard reports comparison problems: {path}")
    if set(raw.get("arms", {})) != set(T068_GUIDED_ARMS):
        raise SystemExit(f"T068 shard arm set mismatch: {path}")
    if not isinstance(raw.get("input_preflight"), dict):
        raise SystemExit(f"T068 shard lacks preflight identity: {path}")
    if set(raw.get("arm_cost_summaries", {})) != set(T068_GUIDED_ARMS):
        raise SystemExit(f"T068 shard cost summaries are incomplete: {path}")
    return raw


def _canonical_preflight(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("command_passed") is not True or value.get("problems"):
        raise SystemExit("T068 shard input preflight failed")
    # Volatile paths/output names are deliberately omitted; all immutable input
    # identities supplied by the T062 preflight remain exact.
    return {
        key: value[key]
        for key in sorted(value)
        if key not in {"output_path", "elapsed_wall_clock_seconds"}
    }


def _aggregate_costs(shards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for arm in T068_GUIDED_ARMS:
        component_totals: dict[str, float] = {}
        totals = {
            "record_count": 0,
            "outer_simulator_steps": 0.0,
            "record_wall_clock_seconds": 0.0,
            "native_search_simulator_steps": 0.0,
            "search_wall_clock_seconds": 0.0,
        }
        failures: list[str] = []
        for shard in shards:
            value = shard["arm_cost_summaries"][arm]
            if not isinstance(value, dict) or value.get("failures"):
                raise SystemExit(
                    f"T068 {arm} has failed or malformed component telemetry"
                )
            components = value.get("component_cost_ms")
            if not isinstance(components, dict):
                raise SystemExit(f"T068 {arm} lacks component telemetry")
            for key, item in components.items():
                if not isinstance(item, (int, float)) or isinstance(item, bool):
                    raise SystemExit(f"T068 {arm} has nonnumeric component telemetry")
                component_totals[key] = component_totals.get(key, 0.0) + float(item)
            for key in totals:
                item = value.get(key)
                if not isinstance(item, (int, float)) or isinstance(item, bool):
                    raise SystemExit(f"T068 {arm} lacks numeric {key}")
                totals[key] += float(item)
            failures.extend(str(problem) for problem in value["failures"])
        output[arm] = {
            "component_cost_ms": component_totals,
            **totals,
            "failures": failures,
        }
    return output


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"T068 cannot load JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"T068 JSON must be an object: {path}")
    return raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fresh(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"T068 refuses to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
