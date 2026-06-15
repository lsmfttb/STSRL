"""Online controller contract and behavior provenance.

Every action selector used during a controlled run implements the
``OnlineController`` protocol and publishes a ``ControllerProvenance`` record
that captures every behavior-changing setting available at this stage. A short
policy name is not sufficient provenance; provenance is immutable, serializable,
and content-addressed so two controllers that differ in any behavior-changing
config receive different identities.

This module deliberately stays framework-neutral. It imports only standard
library types plus the simulator adapter contract. The ``DecisionContext``
annotation is a string/``TYPE_CHECKING`` import so the contract layer does not
pull in feature encoding or any policy implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sts_combat_rl.sim.contract import (
        SimulatorAction,
        SimulatorAdapter,
        SimulatorSnapshot,
    )
    from sts_combat_rl.sim.policy import DecisionContext


CONTROLLER_PROVENANCE_SCHEMA_VERSION = 1
"""Schema version of serialized controller provenance.

Migrations bump this value. Readers reject artifacts that do not match the
version they were written for instead of guessing missing provenance.
"""


def json_safe_value(value: Any) -> Any:
    """Coerce one value into a JSON-serializable form.

    Mappings, sequences, and scalars recurse; anything else falls back to its
    string form so provenance never fails to serialize on a stray enum or native
    object. The fallback is lossy by design: provenance records that a value was
    present rather than silently dropping it.
    """

    if isinstance(value, Mapping):
        return json_safe_mapping(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Sequence):
        return [json_safe_value(item) for item in value]
    return str(value)


def json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce one mapping into a JSON-serializable dict."""

    return {str(key): json_safe_value(item) for key, item in value.items()}


def _deep_freeze(value: Any) -> Any:
    """Recursively convert mutable containers to immutable equivalents.

    dict → MappingProxyType, list → tuple. Scalars pass through unchanged.
    This ensures that ``ControllerProvenance.config`` cannot be mutated after
    construction, protecting the content-addressed identity.
    """

    if isinstance(value, MappingProxyType):
        # Already frozen; recurse into values.
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Sequence):
        return tuple(_deep_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ControllerProvenance:
    """Immutable, serializable record of one controller's behavior-changing config.

    Fields:
        kind: taxonomy of the controller implementation
            (``decision_policy``, ``routed_run``, ``chooser``,
            ``oracle_battle_search`` once search lands). ``kind`` is informal and
            may grow; a stable identity comes from the content hash below.
        name: short human-readable label, typically the underlying policy or
            algorithm name. The name alone is not sufficient provenance.
        config: every behavior-changing setting (seed, information regime,
            nested child provenance, ...). Values are defensively deep-copied
            and JSON-coerced on construction so the provenance is immune to
            later mutation of the caller's original dict, and a native object
            never breaks identity hashing.
        schema_version: serialized-schema version this provenance was written
            for.
    """

    kind: str
    name: str
    config: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = CONTROLLER_PROVENANCE_SCHEMA_VERSION

    def __init__(
        self,
        kind: str,
        name: str,
        config: Mapping[str, Any] | None = None,
        schema_version: int = CONTROLLER_PROVENANCE_SCHEMA_VERSION,
    ) -> None:
        # Defensive deep-copy via json_safe_mapping, then deep-freeze via
        # _deep_freeze. The stored config is a MappingProxyType of tuples,
        # so mutating either the caller's original dict or the provenance's
        # own config never changes the identity after creation.
        safe_config = json_safe_mapping(config) if config is not None else {}
        frozen_config = _deep_freeze(safe_config)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "config", frozen_config)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def identity(self) -> str:
        """Content-addressed identity of this provenance.

        ``kind`` and ``name`` prefix a sha256 digest of the JSON serialization
        so any config change (seed, action space, nested child provenance) yields
        a new identity. This is the stable identifier used in reports and
        artifacts.
        """

        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{self.kind}:{self.name}:{digest}"

    @property
    def reproducible(self) -> bool:
        """Whether this provenance describes a reproducible controller.

        Legacy ``legacy_policy_name_only`` provenance (a name with no config)
        is not reproducible and is tagged explicitly when constructed. Any
        controller may also opt out by setting ``config["reproducible"]`` to
        ``False`` (for example, a legacy callback wrapper).
        """

        if self.kind == "legacy_policy_name_only":
            return False
        return self.config.get("reproducible", True) is not False

    def to_dict(self) -> dict[str, Any]:
        """Serialize provenance to a JSON-safe dict."""

        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "name": self.name,
            "config": json_safe_mapping(self.config),
        }

    def to_json(self) -> str:
        """Serialize provenance to a canonical JSON string."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def controller_provenance_from_dict(data: Mapping[str, Any]) -> ControllerProvenance:
    """Strict loader for serialized controller provenance.

    Rejects the wrong schema version, missing or empty ``kind``/``name``, or a
    non-mapping ``config``. Missing provenance is reported, not guessed.
    """

    if not isinstance(data, Mapping):
        raise ValueError("controller provenance must be a mapping")

    schema_version = data.get("schema_version")
    if schema_version != CONTROLLER_PROVENANCE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported controller provenance schema_version: {schema_version!r}"
        )

    kind = data.get("kind")
    name = data.get("name")
    if not isinstance(kind, str) or not kind:
        raise ValueError("controller provenance kind must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise ValueError("controller provenance name must be a non-empty string")

    config = data.get("config", {})
    if not isinstance(config, Mapping):
        raise ValueError("controller provenance config must be a mapping")

    return ControllerProvenance(
        kind=kind,
        name=name,
        config=config,
        schema_version=schema_version,
    )


def legacy_policy_provenance(policy_name: str) -> ControllerProvenance:
    """Provenance for a legacy reference that only recorded a policy name.

    Tagged ``legacy_policy_name_only`` so it is distinguishable from real
    provenance and never silently reported as reproducible.
    """

    if not isinstance(policy_name, str) or not policy_name:
        raise ValueError("legacy policy name must be a non-empty string")
    return ControllerProvenance(
        kind="legacy_policy_name_only",
        name=policy_name,
        config={"reproducible": False},
    )


@dataclass(frozen=True)
class ControllerDecision:
    """One controller selection expressed as a legal-action index.

    ``reason`` and ``score`` are optional audit metadata. ``metadata`` carries
    serializable per-decision audit info (e.g. the routed controller role).
    """

    selected_index: int
    provenance: ControllerProvenance
    reason: str = ""
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class OnlineController(Protocol):
    """Online action selector allowed to inspect the authoritative simulator adapter.

    Implementations receive both the raw simulator trio
    (``adapter``/``snapshot``/``actions``) and the sanitized ``context``. Public
    controllers must ignore the raw trio and act only on the public context;
    future oracle/search controllers may use the raw adapter to copy hidden
    state. The boundary is enforced by the public controllers validating their
    context, not by the type signature, so the contract stays forward-compatible.
    """

    provenance: ControllerProvenance

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        """Select one currently legal-action index for this decision point."""


def selected_index_problem(
    selected_index: int,
    legal_count: int,
    eligible_indices: Sequence[int],
    controller_label: str,
) -> str | None:
    """Validate a controller's selected index against legal and eligible bounds.

    Returns a problem string if the index is out of bounds or outside the
    active action space; returns ``None`` if the index is valid. The
    ``controller_label`` is included in the problem message for auditability.
    """

    if selected_index < 0 or selected_index >= legal_count:
        return (
            f"{controller_label} selected action index {selected_index} "
            f"outside {legal_count} legal actions"
        )
    if selected_index not in eligible_indices:
        return (
            f"{controller_label} selected action index {selected_index} "
            "outside the active action space"
        )
    return None
