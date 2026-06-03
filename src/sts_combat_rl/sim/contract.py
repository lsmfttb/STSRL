"""Protocol-only simulator adapter boundary.

The live CommunicationMod path stays separate from this contract. A simulator
adapter can implement this interface later without importing Gymnasium,
Stable-Baselines3, or local game-mechanic code into this package.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


ObservationValue = int | float | bool


@dataclass(frozen=True)
class SimulatorSnapshot:
    """One simulator state snapshot exposed through a stable adapter boundary."""

    observation: Sequence[ObservationValue]
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulatorAction:
    """One legal simulator action with enough metadata for debugging/mapping."""

    action_id: int | str
    label: str
    kind: str = "unknown"
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulatorTransition:
    """Result of applying one simulator action."""

    snapshot: SimulatorSnapshot
    terminal: bool
    info: Mapping[str, Any] = field(default_factory=dict)


class SimulatorAdapter(Protocol):
    """Minimal reset/legal_actions/step contract for future fast simulators."""

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        """Reset the simulator and return the first snapshot."""

    def legal_actions(self, snapshot: SimulatorSnapshot) -> Sequence[SimulatorAction]:
        """Return legal actions for ``snapshot``."""

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        """Apply one previously legal action and return the next transition."""
