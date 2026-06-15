"""Policy-driven simulator rollout smoke collection.

This exercises the future online selection boundary without training,
Gymnasium, Stable-Baselines3, or local game mechanics.
"""

from __future__ import annotations

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
)
from sts_combat_rl.sim.contract import (
    SimulatorAdapter,
)
from sts_combat_rl.sim.battle_agent import build_decision_context
from sts_combat_rl.sim.policy import DecisionPolicy
from sts_combat_rl.sim.rollout import RolloutBatch, RolloutStep


def collect_policy_simulator_rollout(
    adapter: SimulatorAdapter,
    policy: DecisionPolicy,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> RolloutBatch:
    """Collect a bounded rollout by selecting each action through ``policy``."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    snapshot = adapter.reset(seed=seed)
    initial_raw = dict(snapshot.raw)
    steps: list[RolloutStep] = []
    problems: list[str] = []
    terminal = False

    for step_index in range(max_steps):
        actions = list(adapter.legal_actions(snapshot))
        if not actions:
            problems.append("no legal actions before terminal state")
            break

        context = build_decision_context(snapshot.raw, actions, active_action_space)
        try:
            decision = policy.select_action(context)
        except ValueError as exc:
            problems.append(str(exc))
            break

        if decision.legal_action_index < 0 or decision.legal_action_index >= len(
            actions
        ):
            problems.append(
                f"policy selected action index {decision.legal_action_index} "
                f"outside {len(actions)} legal actions"
            )
            break
        if decision.legal_action_index not in context.eligible_action_indices:
            problems.append(
                f"policy selected action index {decision.legal_action_index} "
                "outside the active action space"
            )
            break

        chosen_action = actions[decision.legal_action_index]
        transition = adapter.step(chosen_action)
        terminal = transition.terminal
        steps.append(
            RolloutStep(
                step_index=step_index,
                screen_state=context.screen_state,
                snapshot_features=context.snapshot_features,
                legal_action_features=context.legal_action_features,
                legal_action_kinds=context.legal_action_kinds,
                eligible_action_indices=context.eligible_action_indices,
                chosen_action_index=decision.legal_action_index,
                chosen_action_id=chosen_action.action_id,
                chosen_action_kind=chosen_action.kind,
                terminal_after_step=terminal,
            )
        )

        snapshot = transition.snapshot
        if terminal:
            break

    return RolloutBatch(
        seed=seed,
        requested_steps=max_steps,
        steps=steps,
        terminal=terminal,
        outcome=str(snapshot.raw.get("outcome", "UNKNOWN")),
        problems=problems,
        initial_raw=initial_raw,
        final_raw=dict(snapshot.raw),
    )
