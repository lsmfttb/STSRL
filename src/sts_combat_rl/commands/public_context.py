"""Focused T016 workflow for public-context artifact replay auditing."""

from __future__ import annotations

from collections.abc import Callable

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.public_context_audit import (
    PublicContextArtifactAuditReport,
    run_public_context_artifact_audit,
)


def run_public_context_audit(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    *,
    seed: int,
    episodes: int,
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
) -> PublicContextArtifactAuditReport:
    """Run the T016 public-context artifact/replay audit."""

    return run_public_context_artifact_audit(
        adapter_factory,
        seed=seed,
        episodes=episodes,
        max_steps=max_steps,
        action_space=action_space,
    )
