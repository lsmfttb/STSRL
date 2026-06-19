"""Policy-driven simulator rollout smoke collection.

This exercises the online selection boundary without training, Gymnasium,
Stable-Baselines3, or local game mechanics. All rollout logic routes through
the authoritative ``execute_controlled_run`` executor.
"""

from __future__ import annotations

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    execute_controlled_run,
)
from sts_combat_rl.sim.contract import (
    SimulatorAdapter,
)
from sts_combat_rl.sim.online_controller import PolicyController
from sts_combat_rl.sim.policy import DecisionPolicy


def collect_policy_simulator_rollout(
    adapter: SimulatorAdapter,
    policy: DecisionPolicy,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> ControlledRun:
    """Collect a bounded rollout by selecting each action through ``policy``."""

    controller = PolicyController(policy)
    return execute_controlled_run(
        adapter,
        controller,
        seed=seed,
        max_steps=max_steps,
        action_space=action_space,
    )
