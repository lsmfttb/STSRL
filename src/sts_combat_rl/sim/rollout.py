"""Minimal simulator rollout collection for pre-RL data checks.

Rollouts keep all legal actions in the recorded step data while marking which
actions are eligible under the current action-space config. That keeps the first
no-potion pass compatible with a later potion-enabled action space.

All rollout logic routes through the authoritative ``execute_controlled_run``
executor. The legacy ``ActionChooser`` callback is adapted via
:class:`ChooserController`.
"""

from __future__ import annotations

from collections import Counter

from sts_combat_rl.sim.action_space import (
    ActionChooser,
    ActionSpaceConfig,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    execute_controlled_run,
)
from sts_combat_rl.sim.contract import (
    SimulatorAdapter,
)


def collect_simulator_rollout(
    adapter: SimulatorAdapter,
    *,
    seed: int | None = None,
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    chooser: ActionChooser | None = None,
) -> ControlledRun:
    """Collect a bounded rollout without training or mutating game mechanics.

    ``chooser`` must be supplied explicitly. A dataset helper may not silently
    construct a default controller. Pass ``choose_deterministic_action`` for the
    standard deterministic chooser.
    """

    if chooser is None:
        raise ValueError(
            "chooser is required; pass an explicit action chooser "
            "(e.g. choose_deterministic_action)"
        )

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()

    # Lazy import to keep the default import path lean.
    from sts_combat_rl.sim.action_space import choose_deterministic_action
    from sts_combat_rl.sim.online_controller import (
        ChooserController,
        deterministic_chooser_controller,
    )

    if chooser is choose_deterministic_action:
        # Use the canonical deterministic controller — reproducible identity.
        controller = deterministic_chooser_controller(
            action_space=active_action_space,
        )
    else:
        # Custom chooser: wrap in ChooserController (non-reproducible).
        controller = ChooserController(
            chooser=chooser,
            action_space=active_action_space,
            name="custom_chooser",
        )

    return execute_controlled_run(
        adapter,
        controller,
        seed=seed,
        max_steps=max_steps,
        action_space=active_action_space,
    )


def format_rollout_batch(run: ControlledRun) -> str:
    """Format a compact rollout-data summary for stderr."""

    snapshot_feature_sizes = Counter(
        str(len(step.snapshot_features)) for step in run.steps
    )
    action_feature_sizes = Counter(
        str(len(features))
        for step in run.steps
        for features in step.legal_action_features
    )
    legal_action_counts = Counter(
        str(len(step.legal_action_features)) for step in run.steps
    )
    eligible_action_counts = Counter(
        str(len(step.eligible_action_indices)) for step in run.steps
    )
    chosen_action_kinds = Counter(step.chosen_action_kind for step in run.steps)

    lines = [
        "Simulator rollout summary",
        f"seed: {run.seed if run.seed is not None else '(default)'}",
        f"requested steps: {run.requested_steps}",
        f"collected steps: {len(run.steps)}",
        f"terminal: {_bool_label(run.terminal)}",
        f"outcome: {run.outcome}",
    ]
    _append_counter(lines, "snapshot feature sizes", snapshot_feature_sizes)
    _append_counter(lines, "action feature sizes", action_feature_sizes)
    _append_counter(lines, "legal action counts", legal_action_counts)
    _append_counter(lines, "eligible action counts", eligible_action_counts)
    _append_counter(lines, "chosen action kinds", chosen_action_kinds)

    lines.append("problems:")
    if run.problems:
        lines.extend(f"  {problem}" for problem in run.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return
    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _bool_label(value: bool) -> str:
    return "true" if value else "false"
