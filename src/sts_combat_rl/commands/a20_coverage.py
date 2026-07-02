"""Focused T021 workflow for A20 battle-start coverage measurement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20BattleStartCoverageReport,
    A20CoverageCommandConfig,
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
)
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartPoolRestoreReport,
    load_natural_battle_start_pool_metadata_jsonl,
    load_natural_battle_start_pool_jsonl,
    sample_battle_start_pool,
    verify_battle_start_pool_restores,
)
from sts_combat_rl.sim.constructed_battle_start import (
    load_constructed_battle_start_artifact_jsonl,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


def run_a20_battle_start_coverage_from_paths(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool_path: Path,
    constructed_artifact_path: Path | None = None,
    output_path: Path | None = None,
    restore_limit: int = 0,
    sample_count: int = 0,
    sampling_seed: int = 1,
    structural_fraction: float = 0.5,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> A20BattleStartCoverageReport:
    """Load artifacts, verify restores, and optionally write the report JSON."""

    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)

    constructed_artifact = None
    if constructed_artifact_path is not None:
        with constructed_artifact_path.open("r", encoding="utf-8") as stream:
            constructed_artifact = load_constructed_battle_start_artifact_jsonl(stream)

    sampled = sample_battle_start_pool(
        pool,
        sample_count=sample_count,
        seed=sampling_seed,
        structural_fraction=structural_fraction,
    )
    restore_report = verify_battle_start_pool_restores(
        adapter_factory,
        pool,
        limit=restore_limit,
    )
    input_artifacts = _input_artifacts_identity(
        pool_path=pool_path,
        constructed_artifact_path=constructed_artifact_path,
        pool_record_count=len(pool.records),
        constructed_record_count=(
            len(constructed_artifact.records)
            if constructed_artifact is not None
            else None
        ),
    )
    report = build_a20_battle_start_coverage_report(
        pool,
        sampled=sampled,
        constructed_artifact=constructed_artifact,
        restore_report=restore_report,
        command_config=A20CoverageCommandConfig(
            restore_limit=restore_limit,
            sample_count=sample_count,
            sampling_seed=sampling_seed,
            structural_fraction=structural_fraction,
            gate_config=gate_config or TrainingScaleGateConfig(),
            gate_override=gate_override,
        ),
        input_artifacts=input_artifacts,
        source_identity=lightspeed_source_identity_dict(),
    )
    if output_path is not None:
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_a20_battle_start_coverage_report_json(report, stream)
    return report


def merge_a20_battle_start_coverage_from_paths(
    *,
    output_path: Path,
    pool_path: Path,
    coverage_shard_paths: list[Path],
    restore_limit: int = 0,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> A20BattleStartCoverageReport:
    """Build one merged A20 coverage report from shard-level restore reports."""

    if not coverage_shard_paths:
        raise ValueError("at least one A20 coverage shard is required")
    metadata, _ = load_natural_battle_start_pool_metadata_jsonl(pool_path)
    source_pool_merge = _mapping(
        metadata.get("source_pool_merge"),
        "merged natural pool source_pool_merge",
    )
    source_shards = _list(
        source_pool_merge.get("source_shards"),
        "merged natural pool source_shards",
    )
    if len(source_shards) != len(coverage_shard_paths):
        raise ValueError(
            "coverage shard count does not match merged source-pool shard count"
        )
    coverage_shards = [
        (shard_path, _load_json_object(shard_path))
        for shard_path in coverage_shard_paths
    ]
    command_problems = _coverage_shard_linkage_problems(
        source_shards,
        coverage_shards,
    )
    source_identity = _shared_source_identity(coverage_shards)
    restore_report = _aggregate_restore_reports(coverage_shards)
    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    if restore_report.checkpoint_count != len(pool.records):
        raise ValueError(
            "coverage shard restore counts do not match merged natural pool "
            f"records: {restore_report.checkpoint_count} != {len(pool.records)}"
        )
    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=restore_report,
        command_config=A20CoverageCommandConfig(
            restore_limit=restore_limit,
            gate_config=gate_config or TrainingScaleGateConfig(),
            gate_override=gate_override,
        ),
        input_artifacts=_merged_input_artifacts(
            pool_path=pool_path,
            pool_record_count=len(pool.records),
            coverage_shards=coverage_shards,
        ),
        source_identity=source_identity,
    )
    report = replace(
        report,
        command_problems=tuple(
            dict.fromkeys([*report.command_problems, *command_problems])
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_battle_start_coverage_report_json(report, stream)
    return report


def _input_artifacts_identity(
    *,
    pool_path: Path,
    constructed_artifact_path: Path | None,
    pool_record_count: int,
    constructed_record_count: int | None,
) -> dict[str, object]:
    identity: dict[str, object] = {
        "natural_pool": {
            "path": str(pool_path),
            "sha256": _sha256_file(pool_path),
            "record_count": pool_record_count,
        }
    }
    if constructed_artifact_path is not None:
        identity["constructed_artifact"] = {
            "path": str(constructed_artifact_path),
            "sha256": _sha256_file(constructed_artifact_path),
            "record_count": constructed_record_count,
        }
    return identity


def _merged_input_artifacts(
    *,
    pool_path: Path,
    pool_record_count: int,
    coverage_shards: list[tuple[Path, dict[str, Any]]],
) -> dict[str, object]:
    return {
        "natural_pool": {
            "path": str(pool_path),
            "sha256": _sha256_file(pool_path),
            "record_count": pool_record_count,
        },
        "coverage_shards": [
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "natural_pool_sha256": _natural_pool_identity(payload).get("sha256"),
                "natural_pool_record_count": _natural_pool_identity(payload).get(
                    "record_count"
                ),
                "coverage_record_count": _coverage_record_count(payload),
                "command_passed": payload.get("command_passed"),
            }
            for path, payload in coverage_shards
        ],
    }


def _coverage_shard_linkage_problems(
    source_shards: list[Any],
    coverage_shards: list[tuple[Path, dict[str, Any]]],
) -> list[str]:
    problems: list[str] = []
    for index, (source_shard_raw, (coverage_path, coverage)) in enumerate(
        zip(source_shards, coverage_shards, strict=True)
    ):
        source_shard = _mapping(source_shard_raw, f"source shard {index}")
        natural_pool = _natural_pool_identity(coverage)
        expected_sha = source_shard.get("sha256")
        expected_count = source_shard.get("record_count")
        if natural_pool.get("sha256") != expected_sha:
            problems.append(
                f"{coverage_path}: natural-pool sha256 does not match source shard"
            )
        if natural_pool.get("record_count") != expected_count:
            problems.append(
                f"{coverage_path}: natural-pool record_count does not match source shard"
            )
        if _coverage_record_count(coverage) != expected_count:
            problems.append(
                f"{coverage_path}: coverage natural count does not match source shard"
            )
        if coverage.get("schema_id") != "a20-battle-start-coverage-report-v1":
            problems.append(f"{coverage_path}: coverage schema_id is unsupported")
        if coverage.get("format_version") != 1:
            problems.append(f"{coverage_path}: coverage format_version is unsupported")
        if coverage.get("command_passed") is False:
            problems.append(f"{coverage_path}: coverage shard command did not pass")
    return problems


def _aggregate_restore_reports(
    coverage_shards: list[tuple[Path, dict[str, Any]]],
) -> BattleStartPoolRestoreReport:
    checkpoint_count = 0
    restored_count = 0
    native_restored_count = 0
    replay_restored_count = 0
    context_compared_count = 0
    context_matched_count = 0
    context_legacy_unavailable_count = 0
    context_mismatch_count = 0
    problems: list[str] = []
    requested_limits: set[int] = set()
    for path, coverage in coverage_shards:
        restore = _mapping(
            coverage.get("restore_verification"),
            f"{path} restore_verification",
        )
        checkpoint_count += _int(restore.get("checkpoint_count"), "checkpoint_count")
        restored_count += _int(restore.get("restored_count"), "restored_count")
        native_restored_count += _int(
            restore.get("native_restored_count"),
            "native_restored_count",
        )
        replay_restored_count += _int(
            restore.get("replay_restored_count"),
            "replay_restored_count",
        )
        context_compared_count += _int(
            restore.get("context_compared_count"),
            "context_compared_count",
        )
        context_matched_count += _int(
            restore.get("context_matched_count"),
            "context_matched_count",
        )
        context_legacy_unavailable_count += _int(
            restore.get("context_legacy_unavailable_count"),
            "context_legacy_unavailable_count",
        )
        context_mismatch_count += _int(
            restore.get("context_mismatch_count"),
            "context_mismatch_count",
        )
        requested_limits.add(_int(restore.get("requested_limit"), "requested_limit"))
        problems.extend(
            f"{path}: {problem}" for problem in _string_list(restore.get("problems"))
        )
    requested_limit = requested_limits.pop() if len(requested_limits) == 1 else 0
    return BattleStartPoolRestoreReport(
        checkpoint_count=checkpoint_count,
        requested_limit=requested_limit,
        restored_count=restored_count,
        native_restored_count=native_restored_count,
        replay_restored_count=replay_restored_count,
        context_compared_count=context_compared_count,
        context_matched_count=context_matched_count,
        context_legacy_unavailable_count=context_legacy_unavailable_count,
        context_mismatch_count=context_mismatch_count,
        problems=list(dict.fromkeys(problems)),
    )


def _shared_source_identity(
    coverage_shards: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    first_path, first_payload = coverage_shards[0]
    first_identity = _mapping(first_payload.get("source_identity"), "source_identity")
    for path, payload in coverage_shards[1:]:
        identity = _mapping(payload.get("source_identity"), f"{path} source_identity")
        if identity != first_identity:
            raise ValueError(f"{path}: coverage source_identity mismatch")
    return first_identity


def _natural_pool_identity(payload: dict[str, Any]) -> dict[str, Any]:
    input_artifacts = _mapping(payload.get("input_artifacts"), "input_artifacts")
    return _mapping(input_artifacts.get("natural_pool"), "natural_pool")


def _coverage_record_count(report: dict[str, Any]) -> int | None:
    natural = report.get("natural_coverage")
    if not isinstance(natural, dict):
        return None
    value = natural.get("natural_battle_start_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc
    return _mapping(raw, f"{path} JSON root")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return list(value)


def _int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("restore problems must be a string list")
    return list(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
