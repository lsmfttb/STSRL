"""Determinism checks for simulator-owned battle-start checkpoints.

The native checkpoint is deliberately never serialized.  This module verifies
that the authoritative simulator can restore one in-process, while the pool
module verifies portable fresh-adapter replay from seed plus public action
identities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import (
    build_decision_context,
    execute_controlled_run,
)
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.online_controller import deterministic_chooser_controller


@dataclass(frozen=True)
class CheckpointReplayStep:
    """One deterministic battle action and its before/after fingerprints."""

    action_identity: dict[str, Any]
    before_fingerprint: object
    after_fingerprint: object
    terminal: bool


@dataclass(frozen=True)
class BattleCheckpointVerificationReport:
    """Result of the native in-process battle-start checkpoint gate."""

    seed: int | None
    checkpoint_supported: bool
    checkpoint_id: str | None = None
    advancement_steps: int = 0
    replay_steps_requested: int = 0
    replay_steps_executed: int = 0
    initial_restore_matches: bool = False
    repeated_restore_matches: bool = False
    transition_trace_matches: bool = False
    problems: list[str] = field(default_factory=list)

    @property
    def determinism_ok(self) -> bool:
        return (
            self.checkpoint_supported
            and self.initial_restore_matches
            and self.repeated_restore_matches
            and self.transition_trace_matches
            and self.replay_steps_executed > 0
            and not self.problems
        )


@dataclass(frozen=True)
class CapturedBattleStart:
    """The exact battle-start state captured before the controller acts."""

    checkpoint: SimulatorCheckpoint
    snapshot: SimulatorSnapshot
    initial_fingerprint: tuple[object, tuple[object, ...]]
    action_trace: tuple[dict[str, Any], ...]
    step_index: int


def verify_battle_start_checkpoint(
    adapter: CheckpointingSimulatorAdapter,
    controller: Any,
    *,
    seed: int | None,
    max_advancement_steps: int = 200,
    replay_steps: int = 10,
    action_space: ActionSpaceConfig | None = None,
) -> BattleCheckpointVerificationReport:
    """Capture the first naturally reached battle start and replay it twice.

    Reaching the battle uses ``execute_controlled_run`` and the supplied routed
    controller, so non-combat actions retain the same selection semantics and
    provenance boundary as normal collection.  The post-capture replays are a
    distinct checkpoint-validation boundary.
    """

    if max_advancement_steps <= 0:
        raise ValueError("checkpoint max advancement steps must be positive")
    if replay_steps <= 0:
        raise ValueError("checkpoint replay steps must be positive")
    if not adapter.supports_checkpoint_restore:
        return BattleCheckpointVerificationReport(
            seed=seed,
            checkpoint_supported=False,
            replay_steps_requested=replay_steps,
            problems=["simulator does not support native checkpoint capture/restore"],
        )

    captured: CapturedBattleStart | None = None
    action_trace: list[dict[str, Any]] = []

    def before_decision(
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: object,
        step_index: int,
    ) -> None:
        del context
        nonlocal captured
        if captured is None and is_battle_snapshot(snapshot):
            captured = CapturedBattleStart(
                checkpoint=adapter.capture_checkpoint(snapshot),
                snapshot=snapshot,
                initial_fingerprint=(
                    snapshot_fingerprint(snapshot),
                    tuple(action_fingerprint(action) for action in actions),
                ),
                action_trace=tuple(action_trace),
                step_index=step_index,
            )

    def after_transition(step: Any) -> None:
        action_trace.append(dict(step.chosen_action_identity))

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    controlled = execute_controlled_run(
        adapter,
        controller,
        seed=seed,
        max_steps=max_advancement_steps,
        action_space=active_action_space,
        before_decision=before_decision,
        after_transition=after_transition,
    )
    if captured is None:
        return BattleCheckpointVerificationReport(
            seed=seed,
            checkpoint_supported=True,
            replay_steps_requested=replay_steps,
            advancement_steps=len(controlled.steps),
            problems=["no battle start was reached before the advancement limit"],
        )

    expected_initial = captured.initial_fingerprint
    first_initial = adapter.restore_checkpoint(captured.checkpoint)
    first_initial_matches = (
        snapshot_and_actions_fingerprint(adapter, first_initial) == expected_initial
    )
    first_trace = replay_deterministic_battle_steps(
        adapter,
        first_initial,
        max_steps=replay_steps,
        action_space=active_action_space,
    )

    second_initial = adapter.restore_checkpoint(captured.checkpoint)
    second_initial_matches = (
        snapshot_and_actions_fingerprint(adapter, second_initial) == expected_initial
    )
    second_trace = replay_action_identities(
        adapter,
        second_initial,
        [step.action_identity for step in first_trace],
    )

    problems = list(controlled.problems)
    if not first_initial_matches:
        problems.append("first native restore did not reproduce the battle start")
    if not second_initial_matches:
        problems.append("repeated native restore did not reproduce the battle start")
    if first_trace != second_trace:
        problems.append("replayed transition trace differed after repeated restore")
    if not first_trace:
        problems.append("battle checkpoint produced no replayable battle actions")

    return BattleCheckpointVerificationReport(
        seed=seed,
        checkpoint_supported=True,
        checkpoint_id=captured.checkpoint.checkpoint_id,
        advancement_steps=captured.step_index,
        replay_steps_requested=replay_steps,
        replay_steps_executed=len(first_trace),
        initial_restore_matches=first_initial_matches,
        repeated_restore_matches=second_initial_matches,
        transition_trace_matches=first_trace == second_trace,
        problems=list(dict.fromkeys(problems)),
    )


def replay_deterministic_battle_steps(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
    *,
    max_steps: int,
    action_space: ActionSpaceConfig,
) -> tuple[CheckpointReplayStep, ...]:
    """Replay deterministic legal selections while the restored state is battle."""

    controller = deterministic_chooser_controller(action_space)
    replay: list[CheckpointReplayStep] = []
    current = snapshot
    for step_index in range(max_steps):
        if not is_battle_snapshot(current):
            break
        actions = list(adapter.legal_actions(current))
        if not actions:
            break
        context = build_decision_context(current.raw, actions, action_space)
        decision = controller.select_action(
            adapter,
            current,
            actions,
            context,
            step_index,
        )
        if decision.selected_index not in context.eligible_action_indices:
            raise ValueError("deterministic replay selected an ineligible action")
        identities = action_identity_dicts_for_actions(actions)
        transition = adapter.step(actions[decision.selected_index])
        replay.append(
            CheckpointReplayStep(
                action_identity=identities[decision.selected_index],
                before_fingerprint=snapshot_fingerprint(current),
                after_fingerprint=snapshot_fingerprint(transition.snapshot),
                terminal=transition.terminal,
            )
        )
        current = transition.snapshot
        if transition.terminal:
            break
    return tuple(replay)


def replay_action_identities(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
    action_identities: Sequence[Mapping[str, Any]],
) -> tuple[CheckpointReplayStep, ...]:
    """Replay exact occurrence-disambiguated actions from one restored state."""

    from sts_combat_rl.sim.decision_record import find_action_index_by_identity

    current = snapshot
    replay: list[CheckpointReplayStep] = []
    for identity in action_identities:
        actions = list(adapter.legal_actions(current))
        index = find_action_index_by_identity(actions, identity)
        transition = adapter.step(actions[index])
        replay.append(
            CheckpointReplayStep(
                action_identity=dict(identity),
                before_fingerprint=snapshot_fingerprint(current),
                after_fingerprint=snapshot_fingerprint(transition.snapshot),
                terminal=transition.terminal,
            )
        )
        current = transition.snapshot
        if transition.terminal:
            break
    return tuple(replay)


def snapshot_and_actions_fingerprint(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
) -> tuple[object, tuple[object, ...]]:
    """Return a native-payload-free fingerprint of a visible simulator state."""

    return (
        snapshot_fingerprint(snapshot),
        tuple(action_fingerprint(action) for action in adapter.legal_actions(snapshot)),
    )


def snapshot_fingerprint(snapshot: SimulatorSnapshot) -> object:
    """Freeze a snapshot for equality checks without requiring it be JSON-safe."""

    return freeze_value((tuple(snapshot.observation), dict(snapshot.raw)))


def action_fingerprint(action: SimulatorAction) -> object:
    """Freeze one legal action while excluding its opaque native object."""

    raw = {key: value for key, value in action.raw.items() if key != "native"}
    return freeze_value((action.action_id, action.label, action.kind, raw))


def is_battle_snapshot(snapshot: SimulatorSnapshot) -> bool:
    """Match the routed-controller battle predicate without local mechanics."""

    return bool(snapshot.raw.get("battle_active")) or (
        str(snapshot.raw.get("screen_state", "")) == "BATTLE"
    )


def freeze_value(value: Any) -> object:
    """Make nested simulator values comparable without serializing native state."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return tuple(
            sorted((str(key), freeze_value(item)) for key, item in value.items())
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(freeze_value(item) for item in value)
    return str(value)


def format_battle_checkpoint_verification_report(
    report: BattleCheckpointVerificationReport,
) -> str:
    """Format a diagnostic-only native checkpoint verification report."""

    lines = ["Battle-start checkpoint determinism summary"]
    lines.append(f"seed: {report.seed if report.seed is not None else '(none)'}")
    lines.append(
        f"checkpoint supported: {'yes' if report.checkpoint_supported else 'no'}"
    )
    lines.append(f"checkpoint id: {report.checkpoint_id or '(none)'}")
    lines.append(f"advancement steps: {report.advancement_steps}")
    lines.append(
        f"replay steps: {report.replay_steps_executed}/{report.replay_steps_requested}"
    )
    lines.append(
        f"initial restore matches: {'yes' if report.initial_restore_matches else 'no'}"
    )
    lines.append(
        f"repeated restore matches: {'yes' if report.repeated_restore_matches else 'no'}"
    )
    lines.append(
        f"transition trace matches: {'yes' if report.transition_trace_matches else 'no'}"
    )
    lines.append(f"determinism gate passed: {'yes' if report.determinism_ok else 'no'}")
    lines.append("problems:")
    lines.extend(f"  - {problem}" for problem in report.problems) or lines.append(
        "  (none)"
    )
    return "\n".join(lines)
