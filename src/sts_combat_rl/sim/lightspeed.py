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
        self._sim = self._module.StepSimulator(
            self._character_class(),
            int(seed),
            ascension,
        )

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        active_seed = 1 if seed is None else int(seed)
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

    def _snapshot(self, raw_snapshot: dict[str, Any] | None = None) -> SimulatorSnapshot:
        raw = dict(self._sim.snapshot()) if raw_snapshot is None else raw_snapshot
        observation = [_to_observation_value(value) for value in self._sim.observation()]
        return SimulatorSnapshot(observation=observation, raw=raw)

    def _character_class(self) -> Any:
        return getattr(self._module.CharacterClass, self._player_class)


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
