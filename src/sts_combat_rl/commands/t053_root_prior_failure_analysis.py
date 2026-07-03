"""Command helpers for the T053 root-prior allocation failure analysis."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053RootPriorFailureAnalysisReport,
    T053_REQUIRED_INPUT_ROLES,
    build_t053_root_prior_failure_analysis_report,
    dump_t053_root_prior_failure_analysis_report_json,
    format_t053_root_prior_failure_analysis_report,
    load_t053_t052_comparison_analysis_inputs,
)


def run_t053_root_prior_failure_analysis_from_paths(
    *,
    artifact_specs: Sequence[Sequence[str]],
    output_path: Path,
) -> T053RootPriorFailureAnalysisReport:
    """Load retained T052 artifacts, build the T053 report, and write it."""

    artifacts = _verified_artifacts(artifact_specs)
    by_role = {artifact["role"]: artifact for artifact in artifacts}
    comparison_path = Path(by_role["root_prior_guided_comparison"]["path"])
    result_summary_path = Path(by_role["result_summary"]["path"])

    with comparison_path.open("r", encoding="utf-8") as stream:
        metadata, battle_comparisons, controller_results = (
            load_t053_t052_comparison_analysis_inputs(stream)
        )

    with result_summary_path.open("r", encoding="utf-8") as stream:
        result_summary = json.load(stream)
    if not isinstance(result_summary, dict):
        raise ValueError("T052 result summary must be a JSON object")

    report = build_t053_root_prior_failure_analysis_report(
        input_artifacts=artifacts,
        comparison_metadata=metadata,
        battle_comparisons=battle_comparisons,
        controller_results=controller_results,
        t052_result_summary=result_summary,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t053_root_prior_failure_analysis_report_json(report, stream)
    return report


def format_t053_root_prior_failure_analysis_command(
    report: T053RootPriorFailureAnalysisReport,
) -> str:
    """Format the T053 path-level command report."""

    return format_t053_root_prior_failure_analysis_report(report)


def _verified_artifacts(
    artifact_specs: Sequence[Sequence[str]],
) -> list[dict[str, Any]]:
    if len(artifact_specs) != len(T053_REQUIRED_INPUT_ROLES):
        raise ValueError(
            "T053 requires exactly four --t053-t052-artifact values: "
            + ", ".join(T053_REQUIRED_INPUT_ROLES)
        )
    artifacts = []
    for spec in artifact_specs:
        if len(spec) != 3:
            raise ValueError("--t053-t052-artifact requires ROLE PATH SHA256")
        role, raw_path, expected_sha256 = spec
        role = str(role)
        path = Path(raw_path)
        expected = _normalize_sha256(expected_sha256, f"{role} expected sha256")
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(
                f"{role} sha256 mismatch: expected {expected}, got {actual}"
            )
        artifacts.append(
            {
                "role": role,
                "path": str(path),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "sha256_verified": True,
                "byte_count": path.stat().st_size,
                **_schema_hint(path),
            }
        )
    roles = [artifact["role"] for artifact in artifacts]
    for role in T053_REQUIRED_INPUT_ROLES:
        if role not in roles:
            raise ValueError(f"missing required T052 input artifact role {role}")
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate T052 input artifact roles")
    return artifacts


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_sha256(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{label} must be a 64-character lowercase hex digest")
    return normalized


def _schema_hint(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            first = stream.readline()
            if not first:
                return {"detected_schema_id": "unavailable"}
            raw = json.loads(first)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"detected_schema_id": "unavailable"}
    if not isinstance(raw, dict):
        return {"detected_schema_id": "unavailable"}
    if raw.get("type") == "metadata" and isinstance(raw.get("metadata"), dict):
        metadata = raw["metadata"]
        return {
            "detected_schema_id": metadata.get("schema_id", "missing"),
            "detected_format_version": metadata.get("format_version"),
        }
    return {
        "detected_schema_id": raw.get("schema_id", "missing"),
        "detected_format_version": raw.get("format_version"),
    }
