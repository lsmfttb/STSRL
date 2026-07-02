"""Offline command helpers for T052 fixed diagnostic cohort artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sts_combat_rl.sim.fixed_evaluation_set import dump_fixed_cohort_jsonl
from sts_combat_rl.sim.t052_fixed_cohort_diagnostic import (
    T052RetentionArtifactSpec,
    T052RetentionCommandSpec,
    T052RetentionStageSpec,
    T052SourceArmSpec,
    T052VerifiedArtifact,
    build_t052_cohort_summary_payload,
    build_t052_retention_manifest_payload,
    build_t052_t051_boss_later_act_fixed_cohort,
    dump_t052_cohort_summary_json,
    dump_t052_retention_manifest_json,
    format_t052_cohort_summary,
    format_t052_retention_manifest,
    verify_t052_artifact,
)


def run_t052_fixed_cohort_extraction_from_paths(
    *,
    output_path: Path,
    source_arm_specs: list[list[str]],
    verify_artifact_specs: list[list[str]],
    summary_path: Path,
) -> dict[str, Any]:
    """Verify T051 inputs, build the T052 cohort, and write artifacts."""

    source_specs = [_source_arm_spec(values) for values in source_arm_specs]
    verified_artifacts = [
        _verified_artifact(values) for values in verify_artifact_specs
    ]
    result = build_t052_t051_boss_later_act_fixed_cohort(
        source_arm_specs=source_specs,
        verified_artifacts=verified_artifacts,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(result.cohort, stream)

    summary = build_t052_cohort_summary_payload(result, cohort_path=output_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t052_cohort_summary_json(summary, stream)
    return summary


def run_t052_retention_manifest_from_paths(
    *,
    output_path: Path,
    artifact_specs: list[list[str]],
    command_specs: list[list[str]],
    stage_specs: list[list[str]],
    note_specs: list[list[str]],
) -> dict[str, Any]:
    """Write the T052 retention manifest from already generated artifacts."""

    manifest = build_t052_retention_manifest_payload(
        artifact_specs=[_retention_artifact_spec(values) for values in artifact_specs],
        command_specs=[_retention_command_spec(values) for values in command_specs],
        stage_specs=[_retention_stage_spec(values) for values in stage_specs],
        note_items=[_note_item(values) for values in note_specs],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_t052_retention_manifest_json(manifest, stream)
    return manifest


def format_t052_fixed_cohort_extraction_command(payload: dict[str, Any]) -> str:
    """Format the T052 extraction command result."""

    return format_t052_cohort_summary(payload)


def format_t052_retention_manifest_command(payload: dict[str, Any]) -> str:
    """Format the T052 retention manifest command result."""

    return format_t052_retention_manifest(payload)


def _source_arm_spec(values: list[str]) -> T052SourceArmSpec:
    if len(values) != 4:
        raise ValueError("T052 source arm specs must have four values")
    role, label, path, expected_sha256 = values
    return T052SourceArmSpec(
        role=role,
        label=label,
        pool_path=Path(path),
        expected_sha256=expected_sha256,
    )


def _verified_artifact(values: list[str]) -> T052VerifiedArtifact:
    if len(values) != 3:
        raise ValueError("T052 verification artifact specs must have three values")
    role, path, expected_sha256 = values
    return verify_t052_artifact(
        role=role,
        path=Path(path),
        expected_sha256=expected_sha256,
    )


def _retention_artifact_spec(values: list[str]) -> T052RetentionArtifactSpec:
    if len(values) != 3:
        raise ValueError("T052 retained artifact specs must have three values")
    role, path, schema_id = values
    return T052RetentionArtifactSpec(role=role, path=Path(path), schema_id=schema_id)


def _retention_command_spec(values: list[str]) -> T052RetentionCommandSpec:
    if len(values) != 2:
        raise ValueError("T052 retention command specs must have two values")
    role, command = values
    return T052RetentionCommandSpec(role=role, command=command)


def _retention_stage_spec(values: list[str]) -> T052RetentionStageSpec:
    if len(values) != 5:
        raise ValueError("T052 retention stage specs must have five values")
    role, workers, shards, record_range, wall_clock_seconds = values
    return T052RetentionStageSpec(
        role=role,
        workers=_positive_int(workers, "workers"),
        shards=_positive_int(shards, "shards"),
        record_range=record_range,
        wall_clock_seconds=_non_negative_float(
            wall_clock_seconds,
            "wall_clock_seconds",
        ),
    )


def _note_item(values: list[str]) -> tuple[str, str]:
    if len(values) != 2:
        raise ValueError("T052 retention notes must have two values")
    return values[0], values[1]


def _positive_int(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"T052 retention stage {label} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"T052 retention stage {label} must be positive")
    return parsed


def _non_negative_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"T052 retention stage {label} must be a number") from exc
    if parsed < 0.0:
        raise ValueError(f"T052 retention stage {label} must be non-negative")
    return parsed
