"""Optional adapter for a patched ``sts_lightspeed`` pybind module.

This module does not vendor or require ``sts_lightspeed``. It only wraps a
runtime-provided module exposing the spike ``StepSimulator`` interface.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from sts_combat_rl.sim.contract import (
    ObservationValue,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.native_public_projection import (
    NativePublicProjection,
    parse_native_public_projection,
)


_CHECKPOINT_FINGERPRINT_TRANSITION_ONLY_RAW_KEYS = frozenset(
    {"completed_battle_outcome"}
)


class LightSpeedAdapter:
    """Thin adapter around the external ``slaythespire.StepSimulator`` shim."""

    def __init__(
        self,
        seed: int = 1,
        ascension: int = 0,
        player_class: str = "IRONCLAD",
        module: Any | None = None,
    ) -> None:
        if player_class != "IRONCLAD":
            raise ValueError("this project currently supports only IRONCLAD")

        self._module = module if module is not None else _import_lightspeed_module()
        self._player_class = player_class
        self._ascension = ascension
        self._default_seed = int(seed)
        self._active_seed = self._default_seed
        self._checkpoint_adapter_id = f"lightspeed:{id(self)}"
        self._checkpoint_counter = 0
        self._sim = self._module.StepSimulator(
            self._character_class(),
            self._default_seed,
            ascension,
        )

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        active_seed = self._default_seed if seed is None else int(seed)
        self._active_seed = active_seed
        self._sim.reset(self._character_class(), active_seed, self._ascension)
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        actions: list[SimulatorAction] = []
        for native in self._sim.legal_actions():
            scope = str(native.scope)
            bits = int(native.bits)
            actions.append(
                SimulatorAction(
                    action_id=f"{scope}:{bits}",
                    label=str(native.label),
                    kind=str(native.kind),
                    raw={
                        "native": native,
                        "scope": scope,
                        "bits": bits,
                        "idx1": int(native.idx1),
                        "idx2": int(native.idx2),
                        "idx3": int(native.idx3),
                    },
                )
            )
        return actions

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        native = action.raw.get("native")
        if native is None:
            raise ValueError("LightSpeedAdapter.step requires a native action")

        raw_snapshot = dict(self._sim.step(native))
        snapshot = self._snapshot(raw_snapshot)
        info = {"action_id": action.action_id, "action_kind": action.kind}
        completed_battle_outcome = raw_snapshot.get("completed_battle_outcome")
        if isinstance(completed_battle_outcome, str):
            info["completed_battle_outcome"] = completed_battle_outcome
        return SimulatorTransition(
            snapshot=snapshot,
            terminal=_is_terminal(raw_snapshot),
            info=info,
        )

    @property
    def checkpoint_adapter_id(self) -> str:
        """Process-local owner identity for opaque native checkpoints."""

        return self._checkpoint_adapter_id

    @property
    def supports_checkpoint_restore(self) -> bool:
        """Whether the external patched module exposes native checkpoints."""

        return hasattr(self._sim, "capture_checkpoint") and hasattr(
            self._sim, "restore_checkpoint"
        )

    @property
    def checkpoint_fingerprint_transition_only_raw_keys(self) -> frozenset[str]:
        """Declare the native transition annotation boundary explicitly."""

        return _CHECKPOINT_FINGERPRINT_TRANSITION_ONLY_RAW_KEYS

    def checkpoint_fingerprint(
        self, snapshot: SimulatorSnapshot
    ) -> tuple[tuple[ObservationValue, ...], dict[str, Any]]:
        """Return observation and raw state without transition-only labels."""

        stateful_raw = {
            key: value
            for key, value in snapshot.raw.items()
            if key not in self.checkpoint_fingerprint_transition_only_raw_keys
        }
        return tuple(snapshot.observation), stateful_raw

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        """Capture native simulator state without reconstructing game mechanics."""

        if not self.supports_checkpoint_restore:
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose native checkpoint "
                "capture/restore; apply the T004 checkpoint patch and rebuild"
            )
        self._assert_snapshot_is_current(snapshot)
        self._checkpoint_counter += 1
        return SimulatorCheckpoint(
            adapter_id=self._checkpoint_adapter_id,
            checkpoint_id=(f"{self._checkpoint_adapter_id}:{self._checkpoint_counter}"),
            payload=self._sim.capture_checkpoint(),
            metadata={
                "seed": self._active_seed,
                "ascension": snapshot.raw.get("ascension", self._ascension),
                "screen_state": snapshot.raw.get("screen_state"),
            },
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        """Restore a checkpoint only in its owning adapter process."""

        if checkpoint.adapter_id != self._checkpoint_adapter_id:
            raise ValueError("checkpoint belongs to a different simulator adapter")
        if not self.supports_checkpoint_restore:
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose native checkpoint "
                "capture/restore; apply the T004 checkpoint patch and rebuild"
            )
        raw_snapshot = self._sim.restore_checkpoint(checkpoint.payload)
        seed = checkpoint.metadata.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            self._active_seed = seed
        raw = dict(raw_snapshot) if raw_snapshot is not None else None
        return self._snapshot(raw)

    def public_projection(self, snapshot: SimulatorSnapshot) -> NativePublicProjection:
        """Read the current raw native public projection for a T014 audit only."""

        if not hasattr(self._sim, "public_projection"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose public_projection; "
                "apply the T014 native public-projection patch and rebuild"
            )
        self._assert_snapshot_is_current(snapshot)
        return parse_native_public_projection(dict(self._sim.public_projection()))

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, Any]:
        """Run native hidden-state battle search on the current battle state."""

        if not hasattr(self._sim, "battle_search"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose battle_search; "
                "build the T006 oracle-search native source integration"
            )
        self._assert_snapshot_is_current(snapshot)
        return dict(
            self._sim.battle_search(
                int(simulations),
                bool(include_potions),
            )
        )

    def battle_search_with_root_priors(
        self,
        snapshot: SimulatorSnapshot,
        *,
        actions: list[SimulatorAction],
        context: Any,
        simulations: int,
        include_potions: bool = False,
        root_action_priors: Any = None,
        prior_temperature: float = 1.0,
        min_visits_per_legal_action: int = 1,
        prior_allocation_weight: float = 1.0,
    ) -> dict[str, Any]:
        """Run native battle search with validated root allocation priors."""

        if not hasattr(self._sim, "battle_search_with_root_priors"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose "
                "battle_search_with_root_priors; build the T046 root-prior "
                "native source integration"
            )
        from sts_combat_rl.sim.native_root_prior_allocation import (
            build_root_action_prior_vector,
        )

        prior_vector = build_root_action_prior_vector(
            actions,
            context,
            root_action_priors,
        )
        self._assert_snapshot_is_current(snapshot)
        return dict(
            self._sim.battle_search_with_root_priors(
                int(simulations),
                bool(include_potions),
                prior_vector,
                float(prior_temperature),
                int(min_visits_per_legal_action),
                float(prior_allocation_weight),
            )
        )

    def battle_search_v2(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
        policy_prior_callback: Any | None = None,
        leaf_value_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Run the T062 tree-internal Oracle-like native search surface."""

        if not hasattr(self._sim, "battle_search_v2"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose battle_search_v2; "
                "build the T062 tree-internal native source integration"
            )
        if policy_prior_callback is not None and not callable(policy_prior_callback):
            raise ValueError("battle_search_v2 policy_prior_callback must be callable")
        if leaf_value_callback is not None and not callable(leaf_value_callback):
            raise ValueError("battle_search_v2 leaf_value_callback must be callable")
        self._assert_snapshot_is_current(snapshot)
        return dict(
            self._sim.battle_search_v2(
                int(simulations),
                bool(include_potions),
                policy_prior_callback,
                leaf_value_callback,
            )
        )

    def battle_search_v2_with_tree_geometry(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
        policy_prior_callback: Any | None = None,
        leaf_value_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Run Search v2 with the accepted read-only T070 geometry companion."""

        if not hasattr(self._sim, "battle_search_v2_with_tree_geometry"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose "
                "battle_search_v2_with_tree_geometry; build the T070 native "
                "tree-geometry source integration"
            )
        if policy_prior_callback is not None and not callable(policy_prior_callback):
            raise ValueError(
                "battle_search_v2_with_tree_geometry policy_prior_callback "
                "must be callable"
            )
        if leaf_value_callback is not None and not callable(leaf_value_callback):
            raise ValueError(
                "battle_search_v2_with_tree_geometry leaf_value_callback "
                "must be callable"
            )
        self._assert_snapshot_is_current(snapshot)
        return dict(
            self._sim.battle_search_v2_with_tree_geometry(
                int(simulations),
                bool(include_potions),
                policy_prior_callback,
                leaf_value_callback,
            )
        )

    def legal_battle_start_encounters(
        self,
        snapshot: SimulatorSnapshot,
    ) -> list[dict[str, Any]]:
        """Return native same-structure battle-start encounter candidates."""

        if not hasattr(self._sim, "legal_battle_start_encounters"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose "
                "legal_battle_start_encounters; build the T008 battle-start "
                "transform native source integration"
            )
        self._assert_snapshot_is_current(snapshot)
        return [dict(row) for row in self._sim.legal_battle_start_encounters()]

    def rebuild_battle_start(
        self,
        snapshot: SimulatorSnapshot,
        *,
        hp_bonus: int = 0,
        add_random_potion: bool = False,
        encounter_id: int | None = None,
    ) -> SimulatorSnapshot:
        """Apply an authoritative native battle-start rebuild transform."""

        if not hasattr(self._sim, "rebuild_battle_start"):
            raise RuntimeError(
                "slaythespire.StepSimulator does not expose rebuild_battle_start; "
                "build the T008 battle-start transform native source integration"
            )
        self._assert_snapshot_is_current(snapshot)
        native_encounter = -1 if encounter_id is None else int(encounter_id)
        raw_snapshot = dict(
            self._sim.rebuild_battle_start(
                int(hp_bonus),
                bool(add_random_potion),
                native_encounter,
            )
        )
        return self._snapshot(raw_snapshot)

    def _snapshot(
        self, raw_snapshot: dict[str, Any] | None = None
    ) -> SimulatorSnapshot:
        raw = dict(self._sim.snapshot()) if raw_snapshot is None else raw_snapshot
        observation = [
            _to_observation_value(value) for value in self._sim.observation()
        ]
        return SimulatorSnapshot(observation=observation, raw=raw)

    def _character_class(self) -> Any:
        return getattr(self._module.CharacterClass, self._player_class)

    def _assert_snapshot_is_current(self, snapshot: SimulatorSnapshot) -> None:
        """Reject accidental capture of a stale snapshot from another state."""

        current = self._snapshot_fingerprint(self._snapshot())
        candidate = self._snapshot_fingerprint(snapshot)
        if candidate != current:
            raise ValueError(
                "cannot capture a checkpoint for a stale simulator snapshot"
            )

    @staticmethod
    def _snapshot_fingerprint(snapshot: SimulatorSnapshot) -> tuple[object, object]:
        # ``completed_battle_outcome`` is a one-transition annotation returned
        # by StepSimulator.step().  It is intentionally retained on the
        # transition snapshot for battle-outcome labeling, but it is not part
        # of the simulator state and disappears from the next native snapshot.
        # Do not reject a legitimate reward-screen checkpoint solely because
        # that transient label is still attached to the Python snapshot.
        observation, stateful_raw = _checkpoint_fingerprint_parts(snapshot)
        return observation, _freeze_snapshot_value(stateful_raw)


def _checkpoint_fingerprint_parts(
    snapshot: SimulatorSnapshot,
) -> tuple[tuple[ObservationValue, ...], dict[str, Any]]:
    """Build the pinned LightSpeed state fingerprint before freezing raw data."""

    stateful_raw = {
        key: value
        for key, value in snapshot.raw.items()
        if key not in _CHECKPOINT_FINGERPRINT_TRANSITION_ONLY_RAW_KEYS
    }
    return tuple(snapshot.observation), stateful_raw


def _import_lightspeed_module() -> Any:
    try:
        return import_module("slaythespire")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "slaythespire is not importable; build the external sts_lightspeed "
            "StepSimulator shim and put its build directory on PYTHONPATH"
        ) from exc


def _is_terminal(snapshot: dict[str, Any]) -> bool:
    return str(snapshot.get("outcome")) != "UNDECIDED"


def _to_observation_value(value: Any) -> ObservationValue:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    raise TypeError(f"unsupported observation value: {value!r}")


def _freeze_snapshot_value(value: Any) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(key), _freeze_snapshot_value(item)) for key, item in value.items()
            )
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_snapshot_value(item) for item in value)
    return str(value)
