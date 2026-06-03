"""Policy-driven simulator rollout smoke collection.

This exercises the future online selection boundary without training,
Gymnasium, Stable-Baselines3, or local game mechanics.
"""

from __future__ import annotations

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    filter_eligible_actions,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
)
from sts_combat_rl.sim.features import (
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.policy import DecisionContext, DecisionPolicy
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

        context = _decision_context(snapshot.raw, actions, active_action_space)
        try:
            decision = policy.select_action(context)
        except ValueError as exc:
            problems.append(str(exc))
            break

        if decision.legal_action_index < 0 or decision.legal_action_index >= len(actions):
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


def _decision_context(
    raw_snapshot: object,
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig,
) -> DecisionContext:
    raw = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    return DecisionContext(
        screen_state=str(raw.get("screen_state", "(none)")),
        snapshot_features=encode_lightspeed_battle_snapshot(raw),
        legal_action_features=encode_simulator_actions(actions),
        legal_action_kinds=[action.kind for action in actions],
        eligible_action_indices=_eligible_indices(actions, action_space),
    )


def _eligible_indices(
    actions: list[SimulatorAction],
    action_space: ActionSpaceConfig,
) -> list[int]:
    eligible_action_ids = {
        id(action)
        for action in filter_eligible_actions(actions, action_space)
    }
    return [
        index
        for index, action in enumerate(actions)
        if id(action) in eligible_action_ids
    ]
