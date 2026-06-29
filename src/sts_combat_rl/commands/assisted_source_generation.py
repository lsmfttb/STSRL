"""T042 assisted complete-run source-generation commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import BattleStartPoolRestoreReport
from sts_combat_rl.sim.a20_battle_start_coverage import A20CoverageCommandConfig
from sts_combat_rl.sim.assisted_source_generation import (
    build_assisted_a20_coverage_report,
    build_assisted_source_coverage_comparison_report,
    dump_assisted_source_coverage_comparison_report_json,
    dump_assisted_source_pool_jsonl,
    format_assisted_a20_coverage_report,
    load_assisted_source_pool_jsonl,
    merge_assisted_source_pool_shards,
    sha256_file,
    verify_assisted_source_pool_restores,
    write_assisted_a20_coverage_report,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict


def run_assisted_a20_coverage_from_paths(
    *,
    pool_path: Path,
    output_path: Path | None,
    adapter_factory,
    restore_limit: int,
    gate_config,
    gate_override: str,
) -> Any:
    """Load one assisted pool, verify restore, and build an A20 coverage report."""

    with pool_path.open("r", encoding="utf-8") as stream:
        artifact = load_assisted_source_pool_jsonl(stream)
    restore = verify_assisted_source_pool_restores(
        adapter_factory,
        artifact,
        limit=restore_limit,
    )
    report = build_assisted_a20_coverage_report(
        artifact,
        restore_report=restore,
        command_config=A20CoverageCommandConfig(
            restore_limit=restore_limit,
            gate_config=gate_config,
            gate_override=gate_override,
        ),
        input_artifacts={
            "natural_pool": {
                "path": str(pool_path),
                "sha256": sha256_file(pool_path),
                "record_count": len(artifact.records),
                "schema_id": artifact.schema_id,
                "format_version": artifact.format_version,
                "distribution_kind": "assisted_run",
                "assistance_level": artifact.assistance_level,
            }
        },
        source_identity=lightspeed_source_identity_dict(),
    )
    if output_path is not None:
        write_assisted_a20_coverage_report(output_path, report)
    return report


def run_assisted_source_coverage_report_from_paths(
    *,
    output_path: Path,
    arm_specs: list[list[str]],
) -> Any:
    """Build the offline T042 comparison report from repeated arm specs."""

    arm_inputs = []
    for spec_index, spec in enumerate(arm_specs):
        if len(spec) != 3:
            raise ValueError(f"assisted source arm {spec_index} must have 3 values")
        level, pool_raw, coverage_raw = spec
        pool_path = Path(pool_raw)
        coverage_path = Path(coverage_raw)
        with pool_path.open("r", encoding="utf-8") as stream:
            artifact = load_assisted_source_pool_jsonl(stream)
        with coverage_path.open("r", encoding="utf-8") as stream:
            coverage = json.load(stream)
        artifact_identity = {
            "pool_path": str(pool_path),
            "pool_sha256": sha256_file(pool_path),
            "coverage_report_path": str(coverage_path),
            "coverage_report_sha256": sha256_file(coverage_path),
            "pool_record_count": len(artifact.records),
            "coverage_record_count": _coverage_record_count(coverage),
        }
        arm_inputs.append((level, artifact, coverage, artifact_identity))
    report = build_assisted_source_coverage_comparison_report(arm_inputs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_coverage_comparison_report_json(report, stream)
    return report


def merge_assisted_source_pool_from_paths(
    *,
    output_path: Path,
    shard_paths: list[Path],
) -> Any:
    """Merge repeated T042 assisted source-pool shards into one arm artifact."""

    artifacts = []
    shard_identities = []
    for shard_index, shard_path in enumerate(shard_paths):
        with shard_path.open("r", encoding="utf-8") as stream:
            artifact = load_assisted_source_pool_jsonl(stream)
        artifacts.append(artifact)
        shard_identities.append(
            {
                "shard_index": shard_index,
                "path": str(shard_path),
                "sha256": sha256_file(shard_path),
                "record_count": len(artifact.records),
            }
        )
    merged = merge_assisted_source_pool_shards(
        artifacts,
        shard_identities=shard_identities,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_pool_jsonl(merged, stream)
    return merged


def merge_assisted_a20_coverage_from_paths(
    *,
    output_path: Path,
    pool_path: Path,
    coverage_shard_paths: list[Path],
    restore_limit: int,
    gate_config,
    gate_override: str,
) -> Any:
    """Build one merged assisted A20 coverage report from shard restore evidence."""

    with pool_path.open("r", encoding="utf-8") as stream:
        artifact = load_assisted_source_pool_jsonl(stream)
    coverage_shards = []
    for shard_path in coverage_shard_paths:
        with shard_path.open("r", encoding="utf-8") as stream:
            coverage_shards.append((shard_path, json.load(stream)))
    restore = _aggregate_restore_reports(coverage_shards)
    if restore.checkpoint_count != len(artifact.records):
        raise ValueError(
            "coverage shard restore counts do not match merged assisted pool "
            f"records: {restore.checkpoint_count} != {len(artifact.records)}"
        )
    report = build_assisted_a20_coverage_report(
        artifact,
        restore_report=restore,
        command_config=A20CoverageCommandConfig(
            restore_limit=restore_limit,
            gate_config=gate_config,
            gate_override=gate_override,
        ),
        input_artifacts={
            "natural_pool": {
                "path": str(pool_path),
                "sha256": sha256_file(pool_path),
                "record_count": len(artifact.records),
                "schema_id": artifact.schema_id,
                "format_version": artifact.format_version,
                "distribution_kind": "assisted_run",
                "assistance_level": artifact.assistance_level,
                "source_shard_count": len(artifact.source_shards),
            },
            "coverage_shards": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "record_count": _coverage_record_count(payload),
                    "restore_checkpoint_count": _restore_int(
                        payload,
                        "checkpoint_count",
                    ),
                    "command_passed": payload.get("command_passed")
                    if isinstance(payload, dict)
                    else None,
                }
                for path, payload in coverage_shards
            ],
        },
        source_identity=lightspeed_source_identity_dict(),
    )
    if output_path is not None:
        write_assisted_a20_coverage_report(output_path, report)
    return report


def format_assisted_source_pool_merge_report(artifact: Any) -> str:
    """Format a compact assisted shard-merge summary for stderr."""

    return "\n".join(
        [
            "Assisted source-pool merge summary",
            f"assistance level: {artifact.assistance_level}",
            f"shards: {len(artifact.source_shards)}",
            f"source runs: {artifact.pool.source_run_count}",
            f"terminal source runs: {artifact.pool.terminal_run_count}",
            f"truncated source runs: {artifact.pool.truncated_run_count}",
            f"records: {len(artifact.records)}",
            f"assistance decisions: {len(artifact.assistance_decisions)}",
        ]
    )


def format_assisted_coverage_report(report: Any) -> str:
    """Format an assisted A20 coverage report for stderr."""

    return format_assisted_a20_coverage_report(report)


def _coverage_record_count(coverage: Any) -> int | None:
    if not isinstance(coverage, dict):
        return None
    natural = coverage.get("natural_coverage")
    if not isinstance(natural, dict):
        return None
    value = natural.get("natural_battle_start_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _aggregate_restore_reports(
    coverage_shards: list[tuple[Path, Any]],
) -> BattleStartPoolRestoreReport:
    if not coverage_shards:
        raise ValueError("at least one assisted coverage shard is required")
    totals = {
        "checkpoint_count": 0,
        "restored_count": 0,
        "native_restored_count": 0,
        "replay_restored_count": 0,
        "context_compared_count": 0,
        "context_matched_count": 0,
        "context_legacy_unavailable_count": 0,
        "context_mismatch_count": 0,
    }
    problems: list[str] = []
    for path, payload in coverage_shards:
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: coverage shard must be a JSON object")
        restore = payload.get("restore_verification")
        if not isinstance(restore, dict):
            raise ValueError(f"{path}: missing restore_verification")
        for key in totals:
            totals[key] += _restore_int(payload, key)
        if restore.get("restore_ok") is not True:
            problems.append(f"{path}: restore_ok is not true")
        raw_problems = restore.get("problems", [])
        if not isinstance(raw_problems, list):
            raise ValueError(f"{path}: restore problems must be a list")
        problems.extend(f"{path}: {problem}" for problem in raw_problems)
    return BattleStartPoolRestoreReport(
        checkpoint_count=totals["checkpoint_count"],
        requested_limit=0,
        restored_count=totals["restored_count"],
        native_restored_count=totals["native_restored_count"],
        replay_restored_count=totals["replay_restored_count"],
        context_compared_count=totals["context_compared_count"],
        context_matched_count=totals["context_matched_count"],
        context_legacy_unavailable_count=totals["context_legacy_unavailable_count"],
        context_mismatch_count=totals["context_mismatch_count"],
        problems=problems,
    )


def _restore_int(coverage: Any, key: str) -> int:
    if not isinstance(coverage, dict):
        raise ValueError("coverage shard must be a JSON object")
    restore = coverage.get("restore_verification")
    if not isinstance(restore, dict):
        raise ValueError("coverage shard missing restore_verification")
    value = restore.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"restore_verification.{key} must be a non-negative integer")
    return value
