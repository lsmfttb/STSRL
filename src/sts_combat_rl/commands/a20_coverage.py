"""Focused T021 workflow for A20 battle-start coverage measurement."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path

from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20BattleStartCoverageReport,
    A20CoverageCommandConfig,
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
)
from sts_combat_rl.sim.battle_start_pool import (
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
