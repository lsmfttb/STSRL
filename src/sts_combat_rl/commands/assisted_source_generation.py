"""T042 assisted complete-run source-generation commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.a20_battle_start_coverage import A20CoverageCommandConfig
from sts_combat_rl.sim.assisted_source_generation import (
    build_assisted_a20_coverage_report,
    build_assisted_source_coverage_comparison_report,
    dump_assisted_source_coverage_comparison_report_json,
    format_assisted_a20_coverage_report,
    load_assisted_source_pool_jsonl,
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
