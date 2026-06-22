"""Focused T014 workflow for native public-projection capability evidence."""

from __future__ import annotations

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.native_public_projection import (
    NativePublicProjectionAuditCollector,
    NativePublicProjectionCapabilityReport,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import PreferredKindPolicy, StochasticNonCombatDriver


def run_public_projection_capability_audit(
    adapter: LightSpeedAdapter,
    *,
    seed: int,
    episodes: int,
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
) -> NativePublicProjectionCapabilityReport:
    """Audit one current native projection per controlled-run decision.

    The executor remains responsible for selection and advancement.  The
    observer only reads the native raw projection, verifies parity/checkpoint
    preservation, and records capability coverage.
    """

    if episodes <= 0:
        raise ValueError("public projection audit episodes must be positive")
    if max_steps <= 0:
        raise ValueError("public projection audit max_steps must be positive")

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    collector = NativePublicProjectionAuditCollector(adapter)
    completed_episodes = 0
    for offset in range(episodes):
        run_seed = seed + offset
        controller = RoutedRunController(
            battle=PolicyController(PreferredKindPolicy()),
            non_combat=PolicyController(StochasticNonCombatDriver(seed=seed)),
        )

        def observe(snapshot, actions, context, step_index) -> None:  # type: ignore[no-untyped-def]
            del context
            collector.observe_decision(
                snapshot,
                actions,
                seed=run_seed,
                step_index=step_index,
            )

        run = execute_controlled_run(
            adapter,
            controller,
            seed=run_seed,
            max_steps=max_steps,
            action_space=active_action_space,
            before_decision=observe,
        )
        completed_episodes += 1
        collector.record_run_problems(seed=run_seed, problems=run.problems)

    return collector.finalize(
        requested_episodes=episodes,
        completed_episodes=completed_episodes,
        max_steps=max_steps,
    )
