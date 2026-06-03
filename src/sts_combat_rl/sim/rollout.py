"""Minimal simulator rollout collection for pre-RL data checks.

Rollouts keep all legal actions in the recorded step data while marking which
actions are eligible under the current action-space config. That keeps the first
no-potion pass compatible with a later potion-enabled action space.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    choose_deterministic_action,
    filter_eligible_actions,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.features import (
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)


ActionChooser = Callable[[list[SimulatorAction], ActionSpaceConfig], SimulatorAction]


@dataclass(frozen=True)
class RolloutStep:
    """One collected simulator decision point."""

    step_index: int
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    chosen_action_index: int
    chosen_action_id: int | str
    chosen_action_kind: str
    terminal_after_step: bool


@dataclass(frozen=True)
class RolloutBatch:
    """A bounded rollout collected from a simulator adapter."""

    seed: int | None
    requested_steps: int
    steps: list[RolloutStep] = field(default_factory=list)
    terminal: bool = False
    outcome: str = "UNKNOWN"
    problems: list[str] = field(default_factory=list)
    initial_raw: Mapping[str, Any] = field(default_factory=dict)
    final_raw: Mapping[str, Any] = field(default_factory=dict)


def collect_simulator_rollout(
    adapter: SimulatorAdapter,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    chooser: ActionChooser | None = None,
) -> RolloutBatch:
    """Collect a bounded rollout without training or mutating game mechanics."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    active_chooser = chooser or choose_deterministic_action
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

        eligible_indices = _eligible_indices(actions, active_action_space)
        try:
            chosen_action = active_chooser(actions, active_action_space)
        except ValueError as exc:
            problems.append(str(exc))
            break

        chosen_action_index = _action_index(actions, chosen_action)
        transition = adapter.step(chosen_action)
        terminal = transition.terminal
        steps.append(
            RolloutStep(
                step_index=step_index,
                screen_state=str(snapshot.raw.get("screen_state", "(none)")),
                snapshot_features=encode_lightspeed_battle_snapshot(snapshot.raw),
                legal_action_features=encode_simulator_actions(actions),
                legal_action_kinds=[action.kind for action in actions],
                eligible_action_indices=eligible_indices,
                chosen_action_index=chosen_action_index,
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


def format_rollout_batch(batch: RolloutBatch) -> str:
    """Format a compact rollout-data summary for stderr."""

    snapshot_feature_sizes = Counter(
        str(len(step.snapshot_features)) for step in batch.steps
    )
    action_feature_sizes = Counter(
        str(len(features))
        for step in batch.steps
        for features in step.legal_action_features
    )
    legal_action_counts = Counter(
        str(len(step.legal_action_features)) for step in batch.steps
    )
    eligible_action_counts = Counter(
        str(len(step.eligible_action_indices)) for step in batch.steps
    )
    chosen_action_kinds = Counter(step.chosen_action_kind for step in batch.steps)

    lines = [
        "Simulator rollout summary",
        f"seed: {batch.seed if batch.seed is not None else '(default)'}",
        f"requested steps: {batch.requested_steps}",
        f"collected steps: {len(batch.steps)}",
        f"terminal: {_bool_label(batch.terminal)}",
        f"outcome: {batch.outcome}",
    ]
    _append_counter(lines, "snapshot feature sizes", snapshot_feature_sizes)
    _append_counter(lines, "action feature sizes", action_feature_sizes)
    _append_counter(lines, "legal action counts", legal_action_counts)
    _append_counter(lines, "eligible action counts", eligible_action_counts)
    _append_counter(lines, "chosen action kinds", chosen_action_kinds)

    lines.append("problems:")
    if batch.problems:
        lines.extend(f"  {problem}" for problem in batch.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


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


def _action_index(actions: list[SimulatorAction], selected: SimulatorAction) -> int:
    for index, action in enumerate(actions):
        if action is selected:
            return index
    raise ValueError("chosen action is not in the legal action list")


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _bool_label(value: bool) -> str:
    return "true" if value else "false"
