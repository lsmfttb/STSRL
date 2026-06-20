"""Authoritative controlled-run executor.

``execute_controlled_run`` is the ONE complete-run advancement path. It owns:
decision-context construction, action-space filtering, controller invocation,
selected-index validation, simulator stepping, observer callbacks, and bounded
termination. Every complete-run workflow routes through this executor.

Specialized loops (calibration, replay, checkpoint restore, fixed evaluation)
are allowed only for a genuinely different boundary and must reuse the shared
controller selection and validation semantics. They do not silently choose a
policy or redefine root action selection.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    action_space_for_screen,
    eligible_indices,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    OnlineController,
    selected_index_problem,
)
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    source_metadata_from_snapshot,
)
from sts_combat_rl.sim.features import (
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)

# DecisionContext is imported lazily inside build_decision_context to avoid
# a circular import: controlled_run → policy → batching → controlled_run.
if TYPE_CHECKING:
    from sts_combat_rl.sim.policy import DecisionContext


# ---------------------------------------------------------------------------
# Observer type aliases
# ---------------------------------------------------------------------------

BeforeDecisionObserver = Callable[
    [SimulatorSnapshot, Sequence[SimulatorAction], "DecisionContext", int],
    None,
]
"""Called before the controller selects an action.

Receives the current snapshot, legal actions, decision context, and step index.
Exceptions are recorded as problems and terminate the run.
"""

AfterTransitionObserver = Callable[["ControlledRunStep"], None]
"""Called after each successful transition.

Receives the fully populated step record. Exceptions are recorded as problems
and terminate the run.
"""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlledRunStep:
    """One simulator step with full controller provenance and resource metadata.

    This is the unified step type that replaces ``RolloutStep`` and
    ``BattleAgentRolloutStep``. Every step records which controller selected the
    action (``controller_role``) and that controller's provenance, so every
    action in a controlled run is fully attributable.
    """

    step_index: int
    controller_role: str
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    chosen_action_index: int
    chosen_action_id: int | str
    chosen_action_kind: str
    terminal_after_step: bool
    provenance: ControllerProvenance
    selection_reason: str = ""
    decision_metadata: Mapping[str, Any] = field(default_factory=dict)
    floor: float | None = None
    player_hp: float | None = None
    player_max_hp: float | None = None
    gold: float | None = None
    potion_count: float | None = None
    next_screen_state: str = "(none)"
    next_floor: float | None = None
    next_player_hp: float | None = None
    next_player_max_hp: float | None = None
    next_gold: float | None = None
    next_potion_count: float | None = None
    battle_active: bool = False
    next_battle_active: bool = False
    battle_outcome: str | None = None
    next_battle_outcome: str | None = None
    legal_action_identities: list[dict[str, Any]] = field(default_factory=list)
    chosen_action_identity: dict[str, Any] = field(default_factory=dict)
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlledRun:
    """The complete result of one controlled run through the executor.

    Contains every step with full provenance, the run-level controller
    provenance, raw state bookends, and any problems that interrupted or
    malformed the run.
    """

    seed: int | None
    requested_steps: int
    steps: list[ControlledRunStep] = field(default_factory=list)
    terminal: bool = False
    outcome: str = "UNKNOWN"
    problems: list[str] = field(default_factory=list)
    initial_raw: Mapping[str, Any] = field(default_factory=dict)
    final_raw: Mapping[str, Any] = field(default_factory=dict)
    controller_provenance: Mapping[str, Any] = field(default_factory=dict)
    action_space_config: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Authoritative executor
# ---------------------------------------------------------------------------


def execute_controlled_run(
    adapter: SimulatorAdapter,
    controller: OnlineController,
    *,
    seed: int | None,
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
    before_decision: BeforeDecisionObserver | None = None,
    after_transition: AfterTransitionObserver | None = None,
) -> ControlledRun:
    """Advance one simulator cursor through the single authoritative control path.

    This is the foundation for trustworthy datasets, search, and evaluation. It
    replaces all parallel select/validate/step loops with one shared
    implementation.

    Parameters:
        adapter: the simulator adapter providing ``reset``, ``legal_actions``,
            and ``step``.
        controller: the online controller that selects actions. For a routed
            run, pass a ``RoutedRunController``; for a single-policy run, pass a
            ``PolicyController``; for a legacy chooser, pass a
            ``ChooserController``.
        seed: optional simulator seed for deterministic runs.
        max_steps: upper bound on steps before forced termination. Must be
            non-negative.
        action_space: the action-space filter config. Defaults to the initial
            no-potions config.
        before_decision: optional observer called before each controller
            invocation. Exceptions terminate the run.
        after_transition: optional observer called after each successful
            transition. Exceptions terminate the run.

    Returns:
        A ``ControlledRun`` with every step, full provenance, and any problems.
    """

    if max_steps < 0:
        raise ValueError("controlled run max_steps cannot be negative")

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    _reset_controller_for_run(controller, seed)
    snapshot = adapter.reset(seed=seed)
    initial_raw = dict(snapshot.raw)
    steps: list[ControlledRunStep] = []
    problems: list[str] = []
    terminal = False

    for step_index in range(max_steps):
        actions = list(adapter.legal_actions(snapshot))
        if not actions:
            problems.append("no legal actions before terminal state")
            break

        context = build_decision_context(snapshot.raw, actions, active_action_space)

        if before_decision is not None:
            try:
                before_decision(snapshot, actions, context, step_index)
            except (RuntimeError, ValueError) as exc:
                problems.extend(_exception_problems(exc))
                break

        try:
            decision = controller.select_action(
                adapter, snapshot, actions, context, step_index
            )
        except (RuntimeError, ValueError) as exc:
            problems.extend(_exception_problems(exc))
            break

        controller_label = _controller_label(decision)
        validation_problem = selected_index_problem(
            decision.selected_index,
            len(actions),
            context.eligible_action_indices,
            controller_label,
        )
        if validation_problem is not None:
            problems.append(validation_problem)
            break

        chosen_action = actions[decision.selected_index]
        legal_action_identities = action_identity_dicts_for_actions(actions)
        transition = adapter.step(chosen_action)
        terminal = transition.terminal
        next_raw = transition.snapshot.raw

        step = ControlledRunStep(
            step_index=step_index,
            controller_role=controller_label,
            screen_state=context.screen_state,
            snapshot_features=context.snapshot_features,
            legal_action_features=context.legal_action_features,
            legal_action_kinds=context.legal_action_kinds,
            eligible_action_indices=context.eligible_action_indices,
            chosen_action_index=decision.selected_index,
            chosen_action_id=chosen_action.action_id,
            legal_action_identities=legal_action_identities,
            chosen_action_identity=legal_action_identities[decision.selected_index],
            chosen_action_kind=chosen_action.kind,
            terminal_after_step=terminal,
            provenance=decision.provenance,
            selection_reason=decision.reason,
            decision_metadata=dict(decision.metadata),
            source_metadata=source_metadata_from_snapshot(
                snapshot.raw,
                seed=seed,
                source_kind="natural_run",
            ),
            floor=_first_number(snapshot.raw, "floor_num", "floor"),
            player_hp=_player_hp(snapshot.raw),
            player_max_hp=_player_max_hp(snapshot.raw),
            gold=_first_number(snapshot.raw, "gold"),
            potion_count=_potion_count(snapshot.raw),
            next_screen_state=str(next_raw.get("screen_state", "(none)")),
            next_floor=_first_number(next_raw, "floor_num", "floor"),
            next_player_hp=_player_hp(next_raw),
            next_player_max_hp=_player_max_hp(next_raw),
            next_gold=_first_number(next_raw, "gold"),
            next_potion_count=_potion_count(next_raw),
            battle_active=bool(snapshot.raw.get("battle_active")),
            next_battle_active=bool(next_raw.get("battle_active")),
            battle_outcome=_battle_outcome(snapshot.raw),
            next_battle_outcome=_battle_outcome(next_raw),
        )
        steps.append(step)

        if after_transition is not None:
            try:
                after_transition(step)
            except (RuntimeError, ValueError) as exc:
                problems.append(str(exc))
                snapshot = transition.snapshot
                break

        snapshot = transition.snapshot
        if terminal:
            break

    return ControlledRun(
        seed=seed,
        requested_steps=max_steps,
        steps=steps,
        terminal=terminal,
        outcome=str(snapshot.raw.get("outcome", "UNKNOWN")),
        problems=problems,
        initial_raw=initial_raw,
        final_raw=dict(snapshot.raw),
        controller_provenance=controller.provenance.to_dict(),
        action_space_config=active_action_space.to_dict(),
    )


# ---------------------------------------------------------------------------
# Decision-context builder (canonical)
# ---------------------------------------------------------------------------


def build_decision_context(
    raw_snapshot: object,
    actions: Sequence[SimulatorAction],
    action_space: ActionSpaceConfig,
):
    """Build the policy input for the current simulator candidate list.

    This is the single canonical implementation, previously defined in
    ``battle_agent.py``. It encodes snapshot features, per-action features, and
    computes the eligible-action mask from the action-space config.
    """

    from sts_combat_rl.sim.policy import DecisionContext

    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    screen_state = str(raw.get("screen_state", "(none)"))
    effective_action_space = action_space_for_screen(
        action_space,
        screen_state=screen_state,
        battle_active=bool(raw.get("battle_active")),
    )
    return DecisionContext(
        screen_state=screen_state,
        snapshot_features=encode_lightspeed_battle_snapshot(raw),
        legal_action_features=encode_simulator_actions(list(actions)),
        legal_action_kinds=[action.kind for action in actions],
        eligible_action_indices=eligible_indices(list(actions), effective_action_space),
        snapshot_metadata=_public_non_combat_snapshot_metadata(raw),
        legal_action_metadata=[_public_action_metadata(action) for action in actions],
    )


def _reset_controller_for_run(controller: OnlineController, seed: int | None) -> None:
    """Invoke the optional seeded run lifecycle without widening the protocol."""

    reset_for_run = getattr(controller, "reset_for_run", None)
    if callable(reset_for_run):
        reset_for_run(seed)


def _public_non_combat_snapshot_metadata(
    raw: Mapping[str, Any],
) -> dict[str, int | float]:
    """Expose only visible resource counters needed by the non-combat driver."""

    metadata: dict[str, int | float] = {}
    for key in ("potion_count", "potion_capacity"):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metadata[key] = value
    return metadata


def _public_action_metadata(action: SimulatorAction) -> dict[str, int]:
    """Expose visible legal-action parameters used for category selection."""

    metadata: dict[str, int] = {}
    idx1 = action.raw.get("idx1")
    if isinstance(idx1, int) and not isinstance(idx1, bool):
        metadata["idx1"] = idx1
    return metadata


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_controlled_run(run: ControlledRun) -> str:
    """Format a compact controlled-run summary for stderr."""

    lines = [
        "Controlled run summary",
        f"seed: {run.seed if run.seed is not None else '(default)'}",
        f"requested steps: {run.requested_steps}",
        f"collected steps: {len(run.steps)}",
        f"terminal: {_bool_label(run.terminal)}",
        f"outcome: {run.outcome}",
    ]

    role_counts = Counter(step.controller_role for step in run.steps)
    _append_counter(lines, "controller roles", role_counts)

    kind_counts = Counter(step.chosen_action_kind for step in run.steps)
    _append_counter(lines, "chosen action kinds", kind_counts)

    snapshot_sizes = Counter(str(len(step.snapshot_features)) for step in run.steps)
    _append_counter(lines, "snapshot feature sizes", snapshot_sizes)

    action_sizes = Counter(
        str(len(f)) for step in run.steps for f in step.legal_action_features
    )
    _append_counter(lines, "action feature sizes", action_sizes)

    if run.controller_provenance:
        lines.append(
            f"controller provenance: {run.controller_provenance.get('name', '(none)')}"
        )

    lines.append("problems:")
    if run.problems:
        lines.extend(f"  {problem}" for problem in run.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _controller_label(decision: ControllerDecision) -> str:
    """Extract a human-readable controller label from a decision's metadata."""

    return str(decision.metadata.get("controller_role", decision.provenance.identity))


def _exception_problems(exc: BaseException) -> list[str]:
    """Extract problems from an exception, handling the .problems attribute."""

    problems = getattr(exc, "problems", None)
    if isinstance(problems, list) and problems:
        return list(problems)
    return [str(exc)]


def _first_number(
    data: Mapping[str, Any],
    *keys: str,
) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _player_hp(data: Mapping[str, Any]) -> float | None:
    direct = _first_number(data, "cur_hp", "current_hp")
    if direct is not None:
        return direct

    battle_player = _mapping(data.get("battle_player"))
    battle_hp = _first_number(battle_player, "current_hp", "cur_hp")
    if battle_hp is not None:
        return battle_hp

    player = _mapping(data.get("player"))
    return _first_number(player, "current_hp", "cur_hp")


def _player_max_hp(data: Mapping[str, Any]) -> float | None:
    direct = _first_number(data, "max_hp", "maxHp")
    if direct is not None:
        return direct

    battle_player = _mapping(data.get("battle_player"))
    battle_max_hp = _first_number(battle_player, "max_hp", "maxHp")
    if battle_max_hp is not None:
        return battle_max_hp

    player = _mapping(data.get("player"))
    return _first_number(player, "max_hp", "maxHp")


def _potion_count(data: Mapping[str, Any]) -> float | None:
    direct = _first_number(data, "battle_potion_count", "potion_count")
    if direct is not None:
        return direct

    potions = data.get("battle_potions", data.get("potions"))
    if isinstance(potions, list):
        return float(len(potions))
    return None


def _battle_outcome(data: Mapping[str, Any]) -> str | None:
    """Return a simulator-reported battle outcome without inferring mechanics."""

    for field_name in ("completed_battle_outcome", "battle_outcome"):
        value = data.get(field_name)
        if isinstance(value, str) and value and value != "UNDECIDED":
            return value
    value = data.get("outcome")
    if isinstance(value, str) and value and value != "UNDECIDED":
        return value
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_label(value: bool) -> str:
    return "true" if value else "false"


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return
    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
