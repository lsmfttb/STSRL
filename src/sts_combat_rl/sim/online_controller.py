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
    action_space_for_screen,
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
        # Fail closed: a policy without an explicit provenance_config is an
        # implicitly name-only legacy policy. A short name is not sufficient
        # provenance — the policy must explicitly declare its behavior-changing
        # settings (even an empty mapping is a valid declaration of "no
        # behavior-changing config").
        if not hasattr(self.policy, "provenance_config"):
            raise ValueError(
                f"policy {type(self.policy).__name__!r} has no provenance_config; "
                "every policy used in a controlled run must publish its "
                "behavior-changing settings as a mapping"
            )
        policy_config = self.policy.provenance_config
        if not isinstance(policy_config, Mapping):
            raise ValueError("policy.provenance_config must be a mapping")
        merged_config: dict[str, Any] = {}
        merged_config.update(policy_config)
        # Caller-supplied extra config is namespaced under "extra" so it can
        # never overwrite canonical provenance fields or the policy's own config.
        if self.config:
            merged_config["extra"] = dict(self.config)
        # Canonical fields applied last so they are authoritative and never
        # overwritable by the policy's own provenance or by caller extra config.
        merged_config["policy_class"] = type(self.policy).__name__
        merged_config["information_regime"] = PUBLIC_POLICY_INFORMATION_REGIME
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

    def reset_for_run(self, seed: int | None) -> None:
        """Reset an optional stateful public policy for one controlled run."""

        reset_for_run = getattr(self.policy, "reset_for_run", None)
        if callable(reset_for_run):
            reset_for_run(seed)


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
        # A routed run is reproducible only when both children are reproducible.
        all_reproducible = battle_prov.reproducible and non_combat_prov.reproducible
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="routed_run",
                name=f"{battle_prov.name}+{non_combat_prov.name}",
                config={
                    "battle": battle_prov.to_dict(),
                    "non_combat": non_combat_prov.to_dict(),
                    "reproducible": all_reproducible,
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

    def reset_for_run(self, seed: int | None) -> None:
        """Reset child controllers that publish a per-run random lifecycle."""

        for controller in (self.battle, self.non_combat):
            reset_for_run = getattr(controller, "reset_for_run", None)
            if callable(reset_for_run):
                reset_for_run(seed)


@dataclass
class ChooserController:
    """Adapts the legacy action-chooser callback to the controller contract.

    The deterministic chooser (:func:`choose_deterministic_action`) is the only
    reproducible chooser because it is a known function whose behavior is fully
    determined by its :class:`ActionSpaceConfig`. Custom chooser callbacks are
    non-reproducible because two different closures with the same name would
    receive identical provenance, violating the behavior-complete identity
    requirement. The ``reproducible`` flag cannot be overridden to ``True`` for
    custom choosers — only the known deterministic chooser is reproducible.

    The effective ``action_space`` is stored at construction so the chooser
    acts under the same config the executor recorded in
    ``ControlledRun.action_space_config``.
    """

    chooser: ActionChooser
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    name: str = "deterministic_chooser"
    config: Mapping[str, Any] = field(default_factory=dict)
    provenance: ControllerProvenance = field(init=False, default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Only the known deterministic chooser is reproducible.
        is_deterministic = self.chooser is choose_deterministic_action
        effective_reproducible = is_deterministic

        # Name must match identity: the deterministic chooser keeps its
        # canonical name; custom choosers get a different name.
        effective_name = self.name
        if is_deterministic and self.name == "custom_chooser":
            effective_name = "deterministic_chooser"

        # Canonical fields are applied last so they are authoritative and never
        # overwritable by caller extra config.
        merged_config: dict[str, Any] = {}
        # Caller-supplied extra config is namespaced under "extra" so it can
        # never overwrite canonical provenance fields.
        if self.config:
            merged_config["extra"] = dict(self.config)
        merged_config["chooser"] = effective_name
        merged_config["reproducible"] = effective_reproducible
        merged_config["action_space"] = self.action_space.to_dict()
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="chooser",
                name=effective_name,
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
        del adapter, step_index
        action_list = list(actions)
        screen_state = getattr(context, "screen_state", "(none)")
        effective_action_space = action_space_for_screen(
            self.action_space,
            screen_state=screen_state,
            battle_active=is_battle_state(snapshot.raw, screen_state),
        )
        selected = self.chooser(action_list, effective_action_space)
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


def deterministic_chooser_controller(
    action_space: ActionSpaceConfig | None = None,
) -> ChooserController:
    """Build a :class:`ChooserController` over the default deterministic chooser."""

    return ChooserController(
        chooser=choose_deterministic_action,
        action_space=action_space or ActionSpaceConfig.initial_no_potions(),
        name="deterministic_chooser",
    )
