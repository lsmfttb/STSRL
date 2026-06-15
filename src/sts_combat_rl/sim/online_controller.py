"""Concrete online controllers for controlled runs.

These adapt the existing framework-neutral decision policies (and the legacy
action-chooser callback) to the :class:`OnlineController` contract. Each
controller publishes complete :class:`ControllerProvenance` so every selected
action is attributable.

The information-regime constants below tag what a controller is *allowed* to
see. ``normal_public_policy`` controllers act only on the sanitized
``DecisionContext``; ``full_simulator_state_oracle_like`` controllers (future
search) may use the raw adapter. Search itself is out of scope for the
controlled-run foundation and lands in a later task.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.sim.action_space import (
    ActionChooser,
    ActionSpaceConfig,
    SimulatorAction,
    choose_deterministic_action,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.contract import SimulatorAdapter, SimulatorSnapshot
from sts_combat_rl.sim.policy import DecisionContext, DecisionPolicy

PUBLIC_POLICY_INFORMATION_REGIME = "normal_public_policy"
"""A public policy/value acts from player-visible state and public history only."""

NATIVE_SEARCH_INFORMATION_REGIME = "full_simulator_state_oracle_like"
"""Search that copies the actual hidden simulator state.

Reserved for the future native search controller; no controller in this task
uses it. Declared here so the regime label is owned by the controller layer.
"""

BATTLE_AGENT_CONTROLLER_ROLE = "battle_agent"
NON_COMBAT_DRIVER_CONTROLLER_ROLE = "non_combat_driver"
"""Controller-role tags stamped on routed decisions.

These mirror the long-standing ``BATTLE_AGENT_CONTROLLER`` /
``NON_COMBAT_DRIVER_CONTROLLER`` string constants and are the values placed in
``ControllerDecision.metadata["controller_role"]`` by the routed controller.
"""


def is_battle_state(
    raw_snapshot: object,
    screen_state: str,
) -> bool:
    """Whether the current state should be handled by the battle controller.

    A state is a battle state when the simulator reports ``battle_active`` or
    the screen is explicitly ``BATTLE``. Non-combat states (events, rewards,
    shops, map, treasure) are routed to the non-combat driver instead.
    """

    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    return bool(raw.get("battle_active")) or screen_state == "BATTLE"


@dataclass(frozen=True)
class PolicyController:
    """Adapts a framework-neutral :class:`DecisionPolicy` to the controller contract.

    Acts only on the sanitized ``DecisionContext`` (``normal_public_policy``
    regime). The raw adapter/snapshot/actions/step arguments are ignored, in
    keeping with the public-information boundary.
    """

    policy: DecisionPolicy
    config: Mapping[str, Any] = field(default_factory=dict)
    provenance: ControllerProvenance = field(init=False, default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        policy_config = getattr(self.policy, "provenance_config", {})
        if not isinstance(policy_config, Mapping):
            raise ValueError("policy.provenance_config must be a mapping")
        merged_config: dict[str, Any] = {
            "policy_class": type(self.policy).__name__,
            "information_regime": PUBLIC_POLICY_INFORMATION_REGIME,
        }
        merged_config.update(policy_config)
        merged_config.update(self.config)
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="decision_policy",
                name=self.policy.name,
                config=merged_config,
            ),
        )

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del adapter, snapshot, actions, step_index
        decision = self.policy.select_action(context)
        return ControllerDecision(
            selected_index=decision.legal_action_index,
            provenance=self.provenance,
            reason=decision.reason,
            score=decision.score,
        )


@dataclass(frozen=True)
class RoutedRunController:
    """Routes each decision to a battle or non-combat child controller.

    Battle states go to ``battle``; everything else goes to ``non_combat``. The
    composite provenance nests both child provenances, but each emitted decision
    carries the *chosen* child's provenance plus a ``controller_role`` metadata
    tag so the routing decision is fully auditable per step.
    """

    battle: Any
    non_combat: Any
    provenance: ControllerProvenance = field(init=False, default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        battle_prov = self.battle.provenance
        non_combat_prov = self.non_combat.provenance
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="routed_run",
                name=f"{battle_prov.name}+{non_combat_prov.name}",
                config={
                    "battle": battle_prov.to_dict(),
                    "non_combat": non_combat_prov.to_dict(),
                },
            ),
        )

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        battle = is_battle_state(snapshot.raw, context.screen_state)
        controller = self.battle if battle else self.non_combat
        role = (
            BATTLE_AGENT_CONTROLLER_ROLE
            if battle
            else NON_COMBAT_DRIVER_CONTROLLER_ROLE
        )
        decision = controller.select_action(
            adapter, snapshot, actions, context, step_index
        )
        metadata = {"controller_role": role}
        metadata.update(decision.metadata)
        return ControllerDecision(
            selected_index=decision.selected_index,
            provenance=decision.provenance,
            reason=decision.reason,
            score=decision.score,
            metadata=metadata,
        )


@dataclass
class ChooserController:
    """Adapts the legacy action-chooser callback to the controller contract.

    The legacy :func:`collect_simulator_rollout` selected a whole
    :class:`SimulatorAction` via a chooser (default
    :func:`choose_deterministic_action`) instead of going through a
    :class:`DecisionPolicy`. This controller wraps such a callable so the legacy
    path shares the authoritative executor without changing its behavior.

    Not frozen: the chooser is a runtime callback that is not part of identity,
    so it is stored mutably. Provenance records the chooser label and is
    reproducible only when the deterministic chooser is supplied (the default
    ``deterministic_chooser`` is reproducible). Custom choosers are marked
    non-reproducible because two different closures with the same name would
    receive identical provenance, violating the behavior-complete identity
    requirement.
    """

    chooser: ActionChooser
    name: str = "deterministic_chooser"
    reproducible: bool | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    provenance: ControllerProvenance = field(init=False, default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Fail closed: custom (non-deterministic) choosers are non-reproducible
        # unless the caller explicitly opts in. The deterministic chooser is
        # reproducible by default because it is a known function.
        if self.reproducible is None:
            is_deterministic = self.chooser is choose_deterministic_action
            effective_reproducible = is_deterministic
        else:
            effective_reproducible = bool(self.reproducible)

        merged_config: dict[str, Any] = {
            "chooser": self.name,
            "reproducible": effective_reproducible,
        }
        merged_config.update(self.config)
        if not effective_reproducible:
            merged_config["reproducible"] = False
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="chooser",
                name=self.name,
                config=merged_config,
            ),
        )

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del adapter, snapshot, step_index
        action_list = list(actions)
        selected = self.chooser(action_list, _action_space_from_context(context))
        try:
            selected_index = action_list.index(selected)
        except ValueError as exc:
            raise ValueError(
                "chooser returned an action not in the legal list"
            ) from exc
        return ControllerDecision(
            selected_index=selected_index,
            provenance=self.provenance,
            reason=self.name,
        )


def deterministic_chooser_controller() -> ChooserController:
    """Build a :class:`ChooserController` over the default deterministic chooser."""

    return ChooserController(
        chooser=choose_deterministic_action,
        name="deterministic_chooser",
    )


def _action_space_from_context(context: DecisionContext) -> ActionSpaceConfig:
    """Recover the action-space config that produced a context's eligible mask.

    The chooser contract wants an :class:`ActionSpaceConfig`, but the controller
    only sees the precomputed ``context.eligible_action_indices``. We pass the
    default no-potions config: the chooser only uses ``preferred_kinds`` and the
    fallback flag for tie-breaking, both of which are identical on the default
    config, and the executor's own eligibility check already enforces the real
    filter. This keeps chooser behavior identical to the legacy path.
    """

    del context
    return ActionSpaceConfig.initial_no_potions()
