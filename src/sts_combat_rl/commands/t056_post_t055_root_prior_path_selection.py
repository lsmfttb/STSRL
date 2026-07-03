"""Command helpers for the T056 post-T055 path-selection report."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    load_root_prior_guided_search_comparison_jsonl,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    load_t053_root_prior_failure_analysis_report_json,
)
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    load_t054_guardrailed_root_prior_repair_report_json,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    load_t055_guardrailed_root_prior_scale_validation_report_json,
)
from sts_combat_rl.sim.t056_post_t055_root_prior_path_selection import (
    T056PostT055RootPriorPathSelectionReport,
    T056_REQUIRED_INPUT_ROLES,
    build_t056_post_t055_root_prior_path_selection_report,
    dump_t056_post_t055_root_prior_path_selection_report_json,
    format_t056_post_t055_root_prior_path_selection_report,
)


def run_t056_post_t055_root_prior_path_selection_from_paths(
    *,
    artifact_specs: Sequence[Sequence[str]],
    output_path: Path,
) -> T056PostT055RootPriorPathSelectionReport:
    """Load retained artifacts, build the T056 report, and write it."""

    artifacts = _verified_artifacts(artifact_specs)
    by_role = {artifact["role"]: artifact for artifact in artifacts}

    with Path(by_role["t055_scale_validation_report"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t055_report = load_t055_guardrailed_root_prior_scale_validation_report_json(
            stream
        )
    with Path(by_role["t053_failure_analysis_report"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t053_report = load_t053_root_prior_failure_analysis_report_json(stream)
    with Path(by_role["t054_guardrailed_repair_report"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t054_report = load_t054_guardrailed_root_prior_repair_report_json(stream)

    t048_comparisons = {}
    for role in (
        "t048_current_reference_comparison",
        "t048_assist0_reference_comparison",
    ):
        with Path(by_role[role]["path"]).open("r", encoding="utf-8") as stream:
            t048_comparisons[role] = load_root_prior_guided_search_comparison_jsonl(
                stream
            )
    t055_comparisons = {}
    for role in (
        "t055_current_guardrailed_comparison",
        "t055_assist0_guardrailed_comparison",
    ):
        with Path(by_role[role]["path"]).open("r", encoding="utf-8") as stream:
            t055_comparisons[role] = load_root_prior_guided_search_comparison_jsonl(
                stream
            )

    t052_result_summary = _load_json_object(
        Path(by_role["t052_result_summary"]["path"]),
        "T052 result summary",
    )
    t050_reachability_report = _load_json_object(
        Path(by_role["t050_reachability_report"]["path"]),
        "T050 reachability report",
    )
    t050_retention_manifest = _load_json_object(
        Path(by_role["t050_retention_manifest"]["path"]),
        "T050 retention manifest",
    )
    t051_reachability_report = _load_json_object(
        Path(by_role["t051_reachability_report"]["path"]),
        "T051 reachability report",
    )
    t051_retention_manifest = _load_json_object(
        Path(by_role["t051_retention_manifest"]["path"]),
        "T051 retention manifest",
    )

    report = build_t056_post_t055_root_prior_path_selection_report(
        input_artifacts=artifacts,
        t048_comparisons=t048_comparisons,
        t055_comparisons=t055_comparisons,
        t052_result_summary=t052_result_summary,
        t053_report=t053_report,
        t054_report=t054_report,
        t055_report=t055_report,
        t050_reachability_report=t050_reachability_report,
        t050_retention_manifest=t050_retention_manifest,
        t051_reachability_report=t051_reachability_report,
        t051_retention_manifest=t051_retention_manifest,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t056_post_t055_root_prior_path_selection_report_json(report, stream)
    return report


def format_t056_post_t055_root_prior_path_selection_command(
    report: T056PostT055RootPriorPathSelectionReport,
) -> str:
    """Format the T056 path-level report command output."""

    return format_t056_post_t055_root_prior_path_selection_report(report)


def _verified_artifacts(
    artifact_specs: Sequence[Sequence[str]],
) -> list[dict[str, Any]]:
    if len(artifact_specs) != len(T056_REQUIRED_INPUT_ROLES):
        raise ValueError(
            "T056 requires exactly thirteen --t056-input-artifact values: "
            + ", ".join(T056_REQUIRED_INPUT_ROLES)
        )
    artifacts = []
    for spec in artifact_specs:
        if len(spec) != 3:
            raise ValueError("--t056-input-artifact requires ROLE PATH SHA256")
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
                "sha256": actual,
                "sha256_verified": True,
                "byte_count": path.stat().st_size,
                **_schema_hint(path),
            }
        )
    roles = [artifact["role"] for artifact in artifacts]
    for role in T056_REQUIRED_INPUT_ROLES:
        if role not in roles:
            raise ValueError(f"missing required T056 input artifact role {role}")
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate T056 input artifact roles")
    return artifacts


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


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
