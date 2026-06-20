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
        return SimulatorTransition(
            snapshot=snapshot,
            terminal=_is_terminal(raw_snapshot),
            info={"action_id": action.action_id, "action_kind": action.kind},
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
        return tuple(snapshot.observation), _freeze_snapshot_value(snapshot.raw)


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
