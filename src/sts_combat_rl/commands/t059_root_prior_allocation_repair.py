"""Command helpers for the T059 root-prior allocation repair experiment."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t058_root_prior_selected_action_telemetry import (
    T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION,
    T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID,
    load_t058_root_prior_selected_action_telemetry_report_json,
)
from sts_combat_rl.sim.fixed_evaluation_set import FIXED_COHORT_FORMAT_VERSION
from sts_combat_rl.sim.t059_root_prior_allocation_repair import (
    T059RootPriorAllocationRepairReport,
    T059_COMPARISON_ROLES,
    T059_REQUIRED_INPUT_ROLES,
    build_t059_retention_manifest_payload,
    build_t059_root_prior_allocation_repair_report,
    dump_t059_retention_manifest_json,
    dump_t059_root_prior_allocation_repair_report_json,
    format_t059_retention_manifest,
    format_t059_root_prior_allocation_repair_report,
    load_t059_root_prior_comparison_inputs,
)


T058_RETENTION_MANIFEST_SCHEMA_ID = "t058-retention-manifest-v1"
_T059_JSONL_COMPARISON_ROLES = frozenset(T059_COMPARISON_ROLES)
_T059_FIXED_COHORT_ROLES = frozenset(
    {
        "t048_current_fixed_cohort",
        "t048_assist0_fixed_cohort",
        "t052_boss_later_act_fixed_cohort",
    }
)


def run_t059_root_prior_allocation_repair_from_paths(
    *,
    artifact_specs: Sequence[Sequence[str]],
    output_path: Path,
) -> T059RootPriorAllocationRepairReport:
    """Load explicit artifacts, build the T059 report, and write it."""

    artifacts = _verified_artifacts(artifact_specs, expected_count=13, flag="t059")
    by_role = {artifact["role"]: artifact for artifact in artifacts}

    with Path(by_role["t058_selected_action_telemetry_report"]["path"]).open(
        "r",
        encoding="utf-8",
    ) as stream:
        t058_report = load_t058_root_prior_selected_action_telemetry_report_json(stream)

    comparisons = {}
    for role in T059_COMPARISON_ROLES:
        with Path(by_role[role]["path"]).open("r", encoding="utf-8") as stream:
            comparisons[role] = load_t059_root_prior_comparison_inputs(
                stream,
                role=role,
            )

    report = build_t059_root_prior_allocation_repair_report(
        input_artifacts=artifacts,
        t058_report=t058_report,
        comparisons=comparisons,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t059_root_prior_allocation_repair_report_json(report, stream)
    return report


def run_t059_retention_manifest_from_paths(
    *,
    output_path: Path,
    artifact_specs: Sequence[Sequence[str]],
    command_specs: Sequence[Sequence[str]] = (),
    stage_specs: Sequence[Sequence[str]] = (),
    note_specs: Sequence[Sequence[str]] = (),
) -> dict[str, Any]:
    """Hash retained T059 artifacts and write a lightweight manifest."""

    manifest = build_t059_retention_manifest_payload(
        artifact_specs=_retained_artifacts(artifact_specs),
        command_specs=_retention_commands(command_specs),
        stage_specs=_retention_stages(stage_specs),
        note_items=_retention_notes(note_specs),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t059_retention_manifest_json(manifest, stream)
    return manifest


def format_t059_root_prior_allocation_repair_command(
    report: T059RootPriorAllocationRepairReport,
) -> str:
    """Format T059 path-level command output."""

    return format_t059_root_prior_allocation_repair_report(report)


def format_t059_retention_manifest_command(payload: dict[str, Any]) -> str:
    """Format T059 retention-manifest command output."""

    return format_t059_retention_manifest(payload)


def _verified_artifacts(
    artifact_specs: Sequence[Sequence[str]],
    *,
    expected_count: int,
    flag: str,
) -> list[dict[str, Any]]:
    if len(artifact_specs) != expected_count:
        raise ValueError(
            f"T059 requires exactly {expected_count} --{flag}-input-artifact values: "
            + ", ".join(T059_REQUIRED_INPUT_ROLES)
        )
    artifacts = []
    for spec in artifact_specs:
        if len(spec) != 3:
            raise ValueError(f"--{flag}-input-artifact requires ROLE PATH SHA256")
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
    for role in T059_REQUIRED_INPUT_ROLES:
        if role not in roles:
            raise ValueError(f"missing required T059 input artifact role {role}")
    if len(set(roles)) != len(roles):
        raise ValueError("duplicate T059 input artifact roles")
    schema_problems = _schema_problems(artifacts)
    if schema_problems:
        raise ValueError("; ".join(schema_problems))
    return artifacts


def _retained_artifacts(specs: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    artifacts = []
    for spec in specs:
        if len(spec) != 3:
            raise ValueError("--t059-retained-artifact requires ROLE PATH SCHEMA_ID")
        role, raw_path, schema_id = spec
        path = Path(raw_path)
        artifacts.append(
            {
                "role": str(role),
                "path": str(path),
                "schema_id": str(schema_id),
                "sha256": _sha256_file(path),
                "byte_count": path.stat().st_size,
                **_schema_hint(path),
            }
        )
    return artifacts


def _retention_commands(specs: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    commands = []
    for spec in specs:
        if len(spec) != 2:
            raise ValueError("--t059-retention-command requires ROLE COMMAND")
        role, command = spec
        commands.append({"role": str(role), "command": str(command)})
    return commands


def _retention_stages(specs: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    stages = []
    for spec in specs:
        if len(spec) != 5:
            raise ValueError(
                "--t059-retention-stage requires ROLE WORKERS SHARDS RECORD_RANGE SECONDS"
            )
        role, workers, shards, record_range, seconds = spec
        stages.append(
            {
                "role": str(role),
                "workers": int(workers),
                "shards": int(shards),
                "record_range": str(record_range),
                "wall_clock_seconds": float(seconds),
            }
        )
    return stages


def _retention_notes(specs: Sequence[Sequence[str]]) -> list[tuple[str, str]]:
    notes = []
    for spec in specs:
        if len(spec) != 2:
            raise ValueError("--t059-retention-note requires KEY VALUE")
        key, value = spec
        notes.append((str(key), str(value)))
    return notes


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
            try:
                raw = json.loads(first)
            except json.JSONDecodeError:
                stream.seek(0)
                raw = json.load(stream)
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


def _schema_problems(artifacts: Sequence[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    by_role = {str(item.get("role")): item for item in artifacts}
    for role in _T059_JSONL_COMPARISON_ROLES:
        artifact = by_role.get(role, {})
        if artifact.get("detected_schema_id") != (
            "root-prior-guided-search-comparison-v1"
        ):
            problems.append(f"{role}: unsupported detected schema")
        if artifact.get("detected_format_version") != 1:
            problems.append(f"{role}: unsupported detected format version")
    report = by_role.get("t058_selected_action_telemetry_report", {})
    if report.get("detected_schema_id") != T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID:
        problems.append("t058 selected-action report: unsupported detected schema")
    if (
        report.get("detected_format_version")
        != T058_SELECTED_ACTION_TELEMETRY_FORMAT_VERSION
    ):
        problems.append(
            "t058 selected-action report: unsupported detected format version"
        )
    manifest = by_role.get("t058_retention_manifest", {})
    if manifest.get("detected_schema_id") != T058_RETENTION_MANIFEST_SCHEMA_ID:
        problems.append("t058 retention manifest: unsupported detected schema")
    for role in _T059_FIXED_COHORT_ROLES:
        artifact = by_role.get(role, {})
        if artifact.get("detected_schema_id") not in {"missing", None}:
            problems.append(f"{role}: unsupported detected schema")
        if artifact.get("detected_format_version") != FIXED_COHORT_FORMAT_VERSION:
            problems.append(f"{role}: unsupported fixed cohort format version")
    return problems
