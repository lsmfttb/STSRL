"""Protocol-only simulator adapter boundary.

The live CommunicationMod path stays separate from this contract. A simulator
adapter can implement this interface later without importing Gymnasium,
Stable-Baselines3, or local game-mechanic code into this package.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


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
class SimulatorCheckpoint:
    """Opaque adapter-owned state saved for an exact in-process restore.

    ``payload`` deliberately has no repository-defined shape: the authoritative
    simulator owns both capture and restoration.  It must never be written to a
    portable pool artifact or offered to a normal-information controller.
    """

    adapter_id: str
    checkpoint_id: str
    payload: Any = field(repr=False, compare=False)
    metadata: Mapping[str, Any] = field(default_factory=dict)


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


@runtime_checkable
class CheckpointingSimulatorAdapter(SimulatorAdapter, Protocol):
    """Optional native checkpoint capability owned by a simulator adapter.

    Native checkpoints are process-local opaque restore handles.  Portable
    artifacts instead store the seed, occurrence-disambiguated public action
    trace, and expected battle-start snapshot needed for a fresh-process replay.
    """

    @property
    def checkpoint_adapter_id(self) -> str:
        """Return the process-local identity that owns native checkpoints."""

    @property
    def supports_checkpoint_restore(self) -> bool:
        """Whether this adapter exposes authoritative capture and restore."""

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        """Capture exactly the current native simulator state."""

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        """Restore an opaque checkpoint created by this adapter instance."""
