"""Command helpers for the T045 post-T044 failure analysis report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    load_de_assisted_fixed_cohort_comparison_jsonl,
)
from sts_combat_rl.sim.post_t044_failure_analysis import (
    PostT044FailureAnalysisReport,
    build_post_t044_failure_analysis_report,
    dump_post_t044_failure_analysis_report_json,
    format_post_t044_failure_analysis_report,
)


def run_post_t044_failure_analysis_from_paths(
    *,
    comparison_paths: Sequence[Path],
    output_path: Path,
    linked_artifact_specs: Sequence[Sequence[str]] = (),
) -> PostT044FailureAnalysisReport:
    """Load T044 artifacts, build the T045 report, and write it to disk."""

    comparisons = []
    for path in comparison_paths:
        payload = path.read_bytes()
        identity = _artifact_identity(
            path=path,
            payload=payload,
            role="t044_de_assisted_fixed_cohort_comparison",
        )
        text = payload.decode("utf-8")
        from io import StringIO

        report = load_de_assisted_fixed_cohort_comparison_jsonl(StringIO(text))
        identity["schema_id"] = report.schema_id
        identity["format_version"] = report.format_version
        identity["cohort_identity"] = report.cohort_identity
        identity["controller_labels"] = [arm.label for arm in report.arms]
        comparisons.append((identity, report))

    linked = [
        _linked_artifact_identity(role=str(role), path=Path(path))
        for role, path in linked_artifact_specs
    ]
    report = build_post_t044_failure_analysis_report(
        comparisons,
        linked_artifacts=linked,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_post_t044_failure_analysis_report_json(report, stream)
    return report


def format_post_t044_failure_analysis_command(
    report: PostT044FailureAnalysisReport,
) -> str:
    """Format the T045 path-level command report."""

    return format_post_t044_failure_analysis_report(report)


def _linked_artifact_identity(*, role: str, path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    identity = _artifact_identity(path=path, payload=payload, role=role)
    if role in {"calibration", "teacher_calibration"}:
        identity.update(_teacher_calibration_summary(payload))
    else:
        identity.update(_json_schema_hint(payload))
    return identity


def _artifact_identity(*, path: Path, payload: bytes, role: str) -> dict[str, Any]:
    sha256 = hashlib.sha256(payload).hexdigest()
    return {
        "role": role,
        "path": str(path),
        "sha256": sha256,
        "artifact_id": f"{role}-sha256:{sha256}",
        "byte_count": len(payload),
    }


def _teacher_calibration_summary(payload: bytes) -> dict[str, Any]:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "schema_id": "unavailable",
            "calibration_summary": {
                "status": "unavailable",
                "reason": "linked calibration artifact is not JSON",
            },
        }
    if not isinstance(raw, dict):
        return {
            "schema_id": "unavailable",
            "calibration_summary": {
                "status": "unavailable",
                "reason": "linked calibration artifact is not an object",
            },
        }
    schema_id = str(raw.get("schema_id") or "missing")
    checkpoint_reports = raw.get("checkpoint_reports")
    if not isinstance(checkpoint_reports, list):
        return {
            "schema_id": schema_id,
            "format_version": raw.get("format_version"),
            "calibration_summary": {
                "status": "unavailable",
                "reason": "checkpoint_reports missing",
            },
        }
    evaluated = 0
    skipped = 0
    problems = 0
    top1 = 0
    topk = 0
    ece_values: list[float] = []
    for checkpoint in checkpoint_reports:
        if not isinstance(checkpoint, dict):
            continue
        evaluated += _int_value(checkpoint.get("evaluated_record_count"))
        skipped += _int_value(checkpoint.get("skipped_record_count"))
        problems += len(checkpoint.get("problems") or [])
        teacher_metrics = _mapping(checkpoint.get("teacher_target_metrics"))
        top1 += _int_value(teacher_metrics.get("top1_agreement_count"))
        topk += _int_value(teacher_metrics.get("top_k_agreement_count"))
        calibration = _mapping(checkpoint.get("calibration"))
        ece = calibration.get("expected_calibration_error")
        if isinstance(ece, (int, float)) and not isinstance(ece, bool):
            ece_values.append(float(ece))
    return {
        "schema_id": schema_id,
        "format_version": raw.get("format_version"),
        "calibration_summary": {
            "status": "available",
            "evaluated_record_count": evaluated,
            "skipped_record_count": skipped,
            "problem_count": problems,
            "top1_agreement_count": top1,
            "top_k_agreement_count": topk,
            "expected_calibration_error": (
                sum(ece_values) / len(ece_values) if ece_values else None
            ),
        },
    }


def _json_schema_hint(payload: bytes) -> dict[str, Any]:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"schema_id": "unavailable"}
    if not isinstance(raw, dict):
        return {"schema_id": "unavailable"}
    return {
        "schema_id": raw.get("schema_id", "missing"),
        "format_version": raw.get("format_version"),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0
