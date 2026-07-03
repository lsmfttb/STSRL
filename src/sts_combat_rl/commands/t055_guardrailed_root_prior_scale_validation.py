"""Command helpers for the T055 guardrailed root-prior scale report."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    load_root_prior_guided_search_comparison_jsonl,
)
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    load_t054_guardrailed_root_prior_repair_report_json,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055GuardrailedRootPriorScaleValidationReport,
    T055_COHORT_CONTRACTS,
    T055_REQUIRED_INPUT_ROLES,
    build_t055_guardrailed_root_prior_scale_validation_report,
    build_t055_retention_manifest_payload,
    dump_t055_guardrailed_root_prior_scale_validation_report_json,
    dump_t055_retention_manifest_json,
    format_t055_guardrailed_root_prior_scale_validation_report,
    format_t055_retention_manifest,
)


def run_t055_guardrailed_root_prior_scale_validation_from_paths(
    *,
    artifact_specs: Sequence[Sequence[str]],
    output_path: Path,
) -> T055GuardrailedRootPriorScaleValidationReport:
    """Load retained/generated artifacts, build the T055 report, and write it."""

    artifacts = _verified_artifacts(artifact_specs)
    by_role = {artifact["role"]: artifact for artifact in artifacts}

    with Path(by_role["t054_guardrailed_repair_report"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t054_report = load_t054_guardrailed_root_prior_repair_report_json(stream)
    with Path(by_role["t054_guardrailed_comparison"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t054_comparison = load_root_prior_guided_search_comparison_jsonl(stream)

    t048_reference_comparisons = {}
    t055_comparisons = {}
    for contract in T055_COHORT_CONTRACTS:
        cohort_key = str(contract["cohort_key"])
        with Path(by_role[str(contract["t048_reference_role"])]["path"]).open(
            "r",
            encoding="utf-8",
        ) as stream:
            t048_reference_comparisons[cohort_key] = (
                load_root_prior_guided_search_comparison_jsonl(stream)
            )
        with Path(by_role[str(contract["t055_comparison_role"])]["path"]).open(
            "r",
            encoding="utf-8",
        ) as stream:
            t055_comparisons[cohort_key] = (
                load_root_prior_guided_search_comparison_jsonl(stream)
            )

    report = build_t055_guardrailed_root_prior_scale_validation_report(
        input_artifacts=artifacts,
        t054_report=t054_report,
        t054_comparison=t054_comparison,
        t048_reference_comparisons=t048_reference_comparisons,
        t055_comparisons=t055_comparisons,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t055_guardrailed_root_prior_scale_validation_report_json(report, stream)
    return report


def run_t055_retention_manifest_from_paths(
    *,
    output_path: Path,
    artifact_specs: Sequence[Sequence[str]],
    command_specs: Sequence[Sequence[str]] = (),
    stage_specs: Sequence[Sequence[str]] = (),
    note_specs: Sequence[Sequence[str]] = (),
) -> dict[str, Any]:
    """Build and write a T055 retention manifest for generated artifacts."""

    artifacts = [_retained_artifact_payload(spec) for spec in artifact_specs]
    commands = [_command_payload(spec) for spec in command_specs]
    stages = [_stage_payload(spec) for spec in stage_specs]
    notes = [_note_payload(spec) for spec in note_specs]
    manifest = build_t055_retention_manifest_payload(
        artifact_specs=artifacts,
        command_specs=commands,
        stage_specs=stages,
        note_items=notes,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t055_retention_manifest_json(manifest, stream)
    return manifest


def format_t055_guardrailed_root_prior_scale_validation_command(
    report: T055GuardrailedRootPriorScaleValidationReport,
) -> str:
    """Format the T055 path-level report command output."""

    return format_t055_guardrailed_root_prior_scale_validation_report(report)


def format_t055_retention_manifest_command(payload: dict[str, Any]) -> str:
    """Format the T055 retention manifest command output."""

    return format_t055_retention_manifest(payload)


def _verified_artifacts(
    artifact_specs: Sequence[Sequence[str]],
) -> list[dict[str, Any]]:
    if len(artifact_specs) != len(T055_REQUIRED_INPUT_ROLES):
        raise ValueError(
            "T055 requires exactly eleven --t055-input-artifact values: "
            + ", ".join(T055_REQUIRED_INPUT_ROLES)
        )
    artifacts = []
    for spec in artifact_specs:
        if len(spec) != 3:
            raise ValueError("--t055-input-artifact requires ROLE PATH SHA256")
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
    for role in T055_REQUIRED_INPUT_ROLES:
        if role not in roles:
            raise ValueError(f"missing required T055 input artifact role {role}")
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate T055 input artifact roles")
    return artifacts


def _retained_artifact_payload(spec: Sequence[str]) -> dict[str, Any]:
    if len(spec) != 3:
        raise ValueError("--t055-retained-artifact requires ROLE PATH SCHEMA_ID")
    role, raw_path, schema_id = spec
    path = Path(raw_path)
    return {
        "role": str(role),
        "path": str(path),
        "schema_id": str(schema_id),
        "sha256": _sha256_file(path),
        "byte_count": path.stat().st_size,
        **_schema_hint(path),
    }


def _command_payload(spec: Sequence[str]) -> dict[str, str]:
    if len(spec) != 2:
        raise ValueError("--t055-retention-command requires ROLE COMMAND")
    return {"role": str(spec[0]), "command": str(spec[1])}


def _stage_payload(spec: Sequence[str]) -> dict[str, Any]:
    if len(spec) != 5:
        raise ValueError(
            "--t055-retention-stage requires ROLE WORKERS SHARDS RECORD_RANGE SECONDS"
        )
    role, workers, shards, record_range, seconds = spec
    return {
        "role": str(role),
        "workers": _parse_int(workers, "workers"),
        "shards": _parse_int(shards, "shards"),
        "record_range": str(record_range),
        "wall_clock_seconds": _parse_float(seconds, "seconds"),
    }


def _note_payload(spec: Sequence[str]) -> tuple[str, str]:
    if len(spec) != 2:
        raise ValueError("--t055-retention-note requires KEY VALUE")
    return str(spec[0]), str(spec[1])


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


def _parse_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{label} must be non-negative")
    return parsed


def _parse_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number") from exc
    if parsed < 0.0:
        raise ValueError(f"{label} must be non-negative")
    return parsed
