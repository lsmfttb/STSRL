"""Focused T004 workflows for checkpoint verification and natural pools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartPoolShardMergeSummary,
    BattleStartPoolCoverageReport,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    build_battle_start_pool_coverage_report,
    dump_natural_battle_start_pool_jsonl,
    dump_merged_natural_battle_start_pool_shards_jsonl,
    load_natural_battle_start_pool_jsonl,
    collect_natural_battle_start_pool,
    sample_battle_start_pool,
    sha256_file,
    verify_battle_start_pool_restores,
)
from sts_combat_rl.sim.checkpoint_verification import (
    BattleCheckpointVerificationReport,
    verify_battle_start_checkpoint,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import DecisionPolicy
import json


def build_routed_controller(
    battle_policy: DecisionPolicy,
    non_combat_policy: DecisionPolicy,
) -> RoutedRunController:
    """Create the explicit controller whose provenance is written to every start."""

    return RoutedRunController(
        battle=PolicyController(battle_policy),
        non_combat=PolicyController(non_combat_policy),
    )


def run_checkpoint_verification(
    adapter: CheckpointingSimulatorAdapter,
    *,
    battle_policy: DecisionPolicy,
    non_combat_policy: DecisionPolicy,
    seed: int,
    max_steps: int,
    replay_steps: int,
    action_space: ActionSpaceConfig,
) -> BattleCheckpointVerificationReport:
    """Run the in-process native capture/restore determinism gate."""

    return verify_battle_start_checkpoint(
        adapter,
        build_routed_controller(battle_policy, non_combat_policy),
        seed=seed,
        max_advancement_steps=max_steps,
        replay_steps=replay_steps,
        action_space=action_space,
    )


def collect_checkpoint_pool(
    adapter: CheckpointingSimulatorAdapter,
    *,
    battle_policy: DecisionPolicy,
    non_combat_policy: DecisionPolicy,
    seeds: Sequence[int],
    max_steps: int,
    action_space: ActionSpaceConfig,
    sample_count: int = 0,
    sampling_seed: int = 1,
    structural_fraction: float = 0.5,
) -> tuple[NaturalBattleStartPool, BattleStartPoolCoverageReport]:
    """Collect a natural pool and optionally report sampling weight draws."""

    return collect_checkpoint_pool_with_controller(
        adapter,
        controller=build_routed_controller(battle_policy, non_combat_policy),
        seeds=seeds,
        max_steps=max_steps,
        action_space=action_space,
        sample_count=sample_count,
        sampling_seed=sampling_seed,
        structural_fraction=structural_fraction,
    )


def collect_search_checkpoint_pool(
    adapter: CheckpointingSimulatorAdapter,
    *,
    battle_controller: Any,
    non_combat_policy: DecisionPolicy,
    seeds: Sequence[int],
    max_steps: int,
    action_space: ActionSpaceConfig,
    sample_count: int = 0,
    sampling_seed: int = 1,
    structural_fraction: float = 0.5,
) -> tuple[NaturalBattleStartPool, BattleStartPoolCoverageReport]:
    """Collect a natural pool with a search controller controlling only battles."""

    return collect_checkpoint_pool_with_controller(
        adapter,
        controller=RoutedRunController(
            battle=battle_controller,
            non_combat=PolicyController(non_combat_policy),
        ),
        seeds=seeds,
        max_steps=max_steps,
        action_space=action_space,
        sample_count=sample_count,
        sampling_seed=sampling_seed,
        structural_fraction=structural_fraction,
    )


def collect_checkpoint_pool_with_controller(
    adapter: CheckpointingSimulatorAdapter,
    *,
    controller: RoutedRunController,
    seeds: Sequence[int],
    max_steps: int,
    action_space: ActionSpaceConfig,
    sample_count: int = 0,
    sampling_seed: int = 1,
    structural_fraction: float = 0.5,
) -> tuple[NaturalBattleStartPool, BattleStartPoolCoverageReport]:
    """Collect a natural pool from a fully specified routed controller."""

    pool = collect_natural_battle_start_pool(
        adapter,
        controller,
        seeds=seeds,
        max_steps=max_steps,
        action_space=action_space,
    )
    sampled = sample_battle_start_pool(
        pool,
        sample_count=sample_count,
        seed=sampling_seed,
        structural_fraction=structural_fraction,
    )
    return pool, build_battle_start_pool_coverage_report(pool, sampled=sampled)


def write_checkpoint_pool(path: Path, pool: NaturalBattleStartPool) -> None:
    """Write a current-schema portable pool manifest to the requested path."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)


def merge_checkpoint_pool_shards_from_paths(
    *,
    output_path: Path,
    shard_paths: Sequence[Path],
    manifest_path: Path | None = None,
) -> BattleStartPoolShardMergeSummary:
    """Merge current-schema natural source-pool shards and optionally write a manifest."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        summary = dump_merged_natural_battle_start_pool_shards_jsonl(
            shard_paths,
            stream,
        )
    summary = summary.with_output_identity(
        output_path=output_path,
        output_sha256=sha256_file(output_path),
    )
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(summary.to_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
    return summary


def format_battle_start_pool_shard_merge_report(
    summary: BattleStartPoolShardMergeSummary,
) -> str:
    """Format a compact natural source-pool shard merge summary for stderr."""

    return "\n".join(
        [
            "Natural battle-start source-pool shard merge",
            f"schema: {summary.schema_id} v{summary.merge_version}",
            f"shards: {len(summary.source_shards)}",
            f"source runs: {summary.source_run_count}",
            f"terminal source runs: {summary.terminal_run_count}",
            f"truncated source runs: {summary.truncated_run_count}",
            f"records: {summary.record_count}",
            f"output sha256: {summary.output_sha256 or '(not written)'}",
        ]
    )


def verify_checkpoint_pool_file(
    path: Path,
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    limit: int,
) -> BattleStartPoolRestoreReport:
    """Load a portable manifest and restore it through fresh adapter instances."""

    with path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    return verify_battle_start_pool_restores(adapter_factory, pool, limit=limit)
