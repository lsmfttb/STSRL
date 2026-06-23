"""Focused T008 workflow for constructed battle-start supplement audits."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from sts_combat_rl.commands.checkpoint_pool import build_routed_controller
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import collect_natural_battle_start_pool
from sts_combat_rl.sim.constructed_battle_start import (
    ConstructedBattleStartArtifact,
    ConstructedBattleStartAuditReport,
    ConstructedBattleStartPolicy,
    build_constructed_battle_start_artifact,
    build_constructed_battle_start_audit_report,
    dump_constructed_battle_start_artifact_jsonl,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.policy import DecisionPolicy


def run_constructed_battle_start_audit(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    *,
    battle_policy: DecisionPolicy,
    non_combat_policy: DecisionPolicy,
    seeds: Sequence[int],
    max_steps: int,
    transform_policy: ConstructedBattleStartPolicy,
    action_space: ActionSpaceConfig | None = None,
) -> tuple[ConstructedBattleStartArtifact, ConstructedBattleStartAuditReport]:
    """Collect a natural pool and audit constructed supplement proposals."""

    controller = build_routed_controller(battle_policy, non_combat_policy)
    pool = collect_natural_battle_start_pool(
        adapter_factory(),
        controller,
        seeds=seeds,
        max_steps=max_steps,
        action_space=action_space,
    )
    artifact = build_constructed_battle_start_artifact(
        adapter_factory,
        pool,
        policy=transform_policy,
    )
    report = build_constructed_battle_start_audit_report(artifact)
    return artifact, report


def write_constructed_battle_start_artifact(
    path: Path,
    artifact: ConstructedBattleStartArtifact,
) -> None:
    """Write a constructed battle-start JSONL artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        dump_constructed_battle_start_artifact_jsonl(artifact, stream)
