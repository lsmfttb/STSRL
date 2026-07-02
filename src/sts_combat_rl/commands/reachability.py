"""Offline T036 reachability comparison command."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import (
    load_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_metadata_jsonl,
)
from sts_combat_rl.sim.reachability import (
    A20ReachabilityComparisonReport,
    build_a20_reachability_comparison_report,
    build_a20_reachability_comparison_report_from_arm_reports,
    build_streamed_reachability_arm_report,
    dump_a20_reachability_comparison_report_json,
)


def run_a20_reachability_report_from_paths(
    *,
    output_path: Path,
    arm_specs: Sequence[Sequence[str]],
    stream_pools: bool = False,
) -> A20ReachabilityComparisonReport:
    """Load arm artifacts, build the comparison, and write JSON output."""

    arm_inputs = []
    streamed_arms = []
    for spec_index, spec in enumerate(arm_specs):
        if len(spec) != 3:
            raise ValueError(f"reachability arm {spec_index} must have 3 values")
        label, pool_raw, coverage_raw = spec
        pool_path = Path(pool_raw)
        coverage_path = Path(coverage_raw)
        coverage_report = _load_json_object(coverage_path)
        artifact_identity = {
            "pool_path": str(pool_path),
            "pool_sha256": _sha256_file(pool_path),
            "coverage_report_path": str(coverage_path),
            "coverage_report_sha256": _sha256_file(coverage_path),
            "coverage_record_count": _coverage_record_count(coverage_report),
        }
        if stream_pools:
            metadata, actual_record_count = (
                load_natural_battle_start_pool_metadata_jsonl(pool_path)
            )
            expected_record_count = metadata.get("record_count")
            if expected_record_count != actual_record_count:
                raise ValueError(
                    f"{pool_path}: metadata record_count mismatch "
                    f"({expected_record_count} != {actual_record_count})"
                )
            streamed_arms.append(
                build_streamed_reachability_arm_report(
                    label=label,
                    pool_metadata=metadata,
                    pool_records=_iter_current_pool_records_jsonl(pool_path),
                    coverage_report=coverage_report,
                    artifact_identity=artifact_identity,
                )
            )
        else:
            with pool_path.open("r", encoding="utf-8") as stream:
                pool = load_natural_battle_start_pool_jsonl(stream)
            arm_inputs.append((label, pool, coverage_report, artifact_identity))

    report = (
        build_a20_reachability_comparison_report_from_arm_reports(streamed_arms)
        if stream_pools
        else build_a20_reachability_comparison_report(arm_inputs)
    )
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


def _iter_current_pool_records_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    metadata_seen = False
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number}: row must be an object")
            row_type = row.get("type")
            if row_type == "metadata":
                if metadata_seen:
                    raise ValueError(f"{path} line {line_number}: duplicate metadata")
                metadata_seen = True
                continue
            if row_type == "record":
                if not metadata_seen:
                    raise ValueError(
                        f"{path} line {line_number}: record before metadata"
                    )
                record = row.get("record")
                if not isinstance(record, dict):
                    raise ValueError(
                        f"{path} line {line_number}: record must be an object"
                    )
                yield {str(key): value for key, value in record.items()}
                continue
            raise ValueError(f"{path} line {line_number}: unknown row type")
    if not metadata_seen:
        raise ValueError(f"{path}: missing battle-start pool metadata")


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
