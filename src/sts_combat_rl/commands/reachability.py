"""Offline T036 reachability comparison command."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import load_natural_battle_start_pool_jsonl
from sts_combat_rl.sim.reachability import (
    A20ReachabilityComparisonReport,
    build_a20_reachability_comparison_report,
    dump_a20_reachability_comparison_report_json,
)


def run_a20_reachability_report_from_paths(
    *,
    output_path: Path,
    arm_specs: Sequence[Sequence[str]],
) -> A20ReachabilityComparisonReport:
    """Load arm artifacts, build the comparison, and write JSON output."""

    arm_inputs = []
    for spec_index, spec in enumerate(arm_specs):
        if len(spec) != 3:
            raise ValueError(f"reachability arm {spec_index} must have 3 values")
        label, pool_raw, coverage_raw = spec
        pool_path = Path(pool_raw)
        coverage_path = Path(coverage_raw)
        with pool_path.open("r", encoding="utf-8") as stream:
            pool = load_natural_battle_start_pool_jsonl(stream)
        coverage_report = _load_json_object(coverage_path)
        artifact_identity = {
            "pool_path": str(pool_path),
            "pool_sha256": _sha256_file(pool_path),
            "coverage_report_path": str(coverage_path),
            "coverage_report_sha256": _sha256_file(coverage_path),
            "coverage_record_count": _coverage_record_count(coverage_report),
        }
        arm_inputs.append((label, pool, coverage_report, artifact_identity))

    report = build_a20_reachability_comparison_report(arm_inputs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_reachability_comparison_report_json(report, stream)
    return report


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return {str(key): value for key, value in raw.items()}


def _coverage_record_count(report: dict[str, Any]) -> int | None:
    natural = report.get("natural_coverage")
    if not isinstance(natural, dict):
        return None
    value = natural.get("natural_battle_start_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
