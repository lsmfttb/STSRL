"""Focused T022 workflow for saved Oracle teacher dataset reports."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
    load_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.oracle_teacher import load_oracle_teacher_dataset_jsonl
from sts_combat_rl.sim.oracle_teacher_report import (
    OracleTeacherDatasetAuditReport,
    build_oracle_teacher_dataset_audit_report,
    dump_oracle_teacher_dataset_audit_report_json,
    format_oracle_teacher_dataset_audit_report,
    load_a20_coverage_report_json,
)


def run_oracle_teacher_dataset_report_from_paths(
    *,
    teacher_path: Path,
    source_pool_path: Path | None = None,
    coverage_report_path: Path | None = None,
    output_path: Path | None = None,
) -> OracleTeacherDatasetAuditReport:
    """Load artifacts, build the T022 report, and optionally write JSON."""

    if coverage_report_path is not None and source_pool_path is None:
        raise ValueError(
            "--oracle-teacher-coverage-report requires --oracle-teacher-source-pool"
        )
    with teacher_path.open("r", encoding="utf-8") as stream:
        dataset = load_oracle_teacher_dataset_jsonl(stream, validate=False)

    source_pool: NaturalBattleStartPool | None = None
    source_pool_identity = None
    if source_pool_path is not None:
        with source_pool_path.open("r", encoding="utf-8") as stream:
            source_pool = load_natural_battle_start_pool_jsonl(stream)
        source_pool_identity = _source_pool_identity(source_pool_path, source_pool)

    coverage_report = None
    coverage_report_identity = None
    if coverage_report_path is not None:
        with coverage_report_path.open("r", encoding="utf-8") as stream:
            coverage_report = load_a20_coverage_report_json(stream)
        coverage_report_identity = {
            "path": str(coverage_report_path),
            "sha256": _sha256_file(coverage_report_path),
            "schema_id": coverage_report.get("schema_id"),
            "format_version": coverage_report.get("format_version"),
        }

    report = build_oracle_teacher_dataset_audit_report(
        dataset,
        teacher_artifact_identity=_teacher_artifact_identity(teacher_path, dataset),
        source_pool=source_pool,
        source_pool_artifact_identity=source_pool_identity,
        coverage_report=coverage_report,
        coverage_report_identity=coverage_report_identity,
        current_source_manifest_identity=lightspeed_source_identity_dict(),
        command_config={
            "source_pool_provided": source_pool_path is not None,
            "coverage_report_provided": coverage_report_path is not None,
            "report_output_requested": output_path is not None,
        },
    )
    if output_path is not None:
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_oracle_teacher_dataset_audit_report_json(report, stream)
    return report


def format_oracle_teacher_dataset_report_command(
    report: OracleTeacherDatasetAuditReport,
) -> str:
    """Format report command output for stderr."""

    return format_oracle_teacher_dataset_audit_report(report)


def _teacher_artifact_identity(
    path: Path,
    dataset: object,
) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "artifact_schema_id": getattr(dataset, "artifact_schema_id", None),
        "format_version": getattr(dataset, "format_version", None),
        "record_count": len(getattr(dataset, "records", [])),
    }


def _source_pool_identity(
    path: Path,
    pool: NaturalBattleStartPool,
) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "format_version": pool.format_version,
        "record_count": len(pool.records),
        "source_run_count": pool.source_run_count,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
