"""Focused T004 workflows for checkpoint verification and natural pools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartPoolCoverageReport,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    build_battle_start_pool_coverage_report,
    dump_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_jsonl,
    collect_natural_battle_start_pool,
    sample_battle_start_pool,
    verify_battle_start_pool_restores,
)
from sts_combat_rl.sim.checkpoint_verification import (
    BattleCheckpointVerificationReport,
    verify_battle_start_checkpoint,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import DecisionPolicy


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
