"""Occurrence-safe feature identities for diagnostic scorer observation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import math
import struct
from time import perf_counter
from typing import Any

from sts_combat_rl.sim.search_cost import canonical_public_json
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.public_context_feature_projection import (
    feature_vector_sha256,
)
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
)


FEATURE_IDENTITY_SCHEMA_ID = "t069-scorer-input-identity-v1"
FEATURE_IDENTITY_SCHEMA_VERSION = 1


class FeatureIdentityRecorder:
    """Observe complete scorer inputs without changing their values or ordering."""

    def __init__(self, *, arm: str, projected: bool) -> None:
        self.arm = _required_text(arm, "arm")
        self.projected = bool(projected)
        self.records: list[dict[str, Any]] = []
        self.problems: list[str] = []
        self._scope_index = -1
        self._request_index = 0
        self._scope_canonical: bytes | None = None

    def __call__(self, event: Mapping[str, Any]) -> None:
        event_kind = event.get("event")
        if event_kind == "begin_search_scope":
            self._begin_scope(event)
            return
        if event_kind == "end_search_scope":
            if self._scope_canonical is None:
                self.problems.append("search scope ended without a matching begin")
            self._scope_canonical = None
            return
        if event_kind == "score_input":
            self._record_input(event)
            return
        self.problems.append(f"unsupported observer event {event_kind!r}")

    def _begin_scope(self, event: Mapping[str, Any]) -> None:
        if self._scope_canonical is not None:
            self.problems.append("search scope began before the previous scope ended")
        public_context = event.get("public_run_context")
        if not isinstance(public_context, Mapping):
            self.problems.append("search scope lacks complete public run context")
            self._scope_canonical = None
            return
        try:
            canonical = canonical_public_json(public_context)
        except (TypeError, ValueError, OverflowError) as exc:
            self.problems.append(f"public context canonicalization failed: {exc}")
            self._scope_canonical = None
            return
        self._scope_index += 1
        self._request_index = 0
        self._scope_canonical = canonical

    def _record_input(self, event: Mapping[str, Any]) -> None:
        started = perf_counter()
        context = event.get("context")
        public_features = event.get("public_context_features")
        state_features = event.get("state_features")
        action_features = event.get("legal_action_features")
        if not isinstance(context, DecisionContext):
            self.problems.append("score observer lacks DecisionContext")
            return
        if self._scope_canonical is None:
            self.problems.append("score input occurred outside a search scope")
            return
        if bool(event.get("projected")) is not self.projected:
            self.problems.append(
                "score input projected/unprojected classification changed"
            )
            return
        try:
            canonical = canonical_public_json(context.public_run_context)
            public_values = _finite_tuple(public_features, "public context")
            state_values = _finite_tuple(state_features, "state")
            action_rows = _finite_rows(action_features)
            snapshot_values = _finite_tuple(
                context.snapshot_features,
                "snapshot",
            )
        except (TypeError, ValueError, OverflowError) as exc:
            self.problems.append(str(exc))
            return
        if canonical != self._scope_canonical:
            self.problems.append(
                "complete public context changed within one search scope"
            )
        if state_values != (*snapshot_values, *public_values):
            self.problems.append(
                "state vector is not exact snapshot plus public projection"
            )
        canonical_sha256 = hashlib.sha256(canonical).hexdigest()
        request_id = (
            f"{self.arm}-scope-{self._scope_index:06d}-"
            f"request-{self._request_index:06d}"
        )
        self._request_index += 1
        self.records.append(
            {
                "schema_id": FEATURE_IDENTITY_SCHEMA_ID,
                "schema_version": FEATURE_IDENTITY_SCHEMA_VERSION,
                "arm": self.arm,
                "projected": self.projected,
                "search_scope_index": self._scope_index,
                "request_index": self._request_index - 1,
                "request_id": request_id,
                "complete_public_context_sha256": canonical_sha256,
                "complete_public_context_byte_count": len(canonical),
                "public_context_feature_schema_id": (
                    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
                ),
                "public_context_feature_schema_version": (
                    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
                ),
                "public_context_feature_names": list(
                    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES
                ),
                "public_context_feature_size": len(public_values),
                "public_context_feature_sha256": feature_vector_sha256(public_values),
                "tactical_feature_schema_id": context.tactical_feature_schema_id,
                "snapshot_feature_size": len(snapshot_values),
                "snapshot_feature_sha256": feature_vector_sha256(snapshot_values),
                "state_feature_size": len(state_values),
                "state_feature_sha256": feature_vector_sha256(state_values),
                "ordered_legal_action_count": len(action_rows),
                "ordered_legal_action_row_sizes": [len(row) for row in action_rows],
                "ordered_legal_action_feature_sha256": _rows_sha256(action_rows),
                "ordered_legal_action_identities": _action_identities(context),
                "eligible_action_indices": list(context.eligible_action_indices),
                "identity_recording_ms": (perf_counter() - started) * 1000.0,
            }
        )


def _finite_tuple(value: Any, label: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"T069 {label} feature vector is malformed")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"T069 {label} feature vector contains non-finite values")
    return result


def _finite_rows(value: Any) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("T069 legal action feature rows are malformed")
    return tuple(_finite_tuple(row, "legal action") for row in value)


def _rows_sha256(rows: Sequence[Sequence[float]]) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack(">Q", len(rows)))
    for row in rows:
        digest.update(struct.pack(">Q", len(row)))
        for value in row:
            digest.update(struct.pack(">d", float(value)))
    return digest.hexdigest()


def _action_identities(context: DecisionContext) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    for action in context.tactical_legal_actions:
        identity = action.get("identity") if isinstance(action, Mapping) else None
        if not isinstance(identity, Mapping):
            raise ValueError("T069 legal action lacks occurrence-safe identity")
        stable_id = identity.get("stable_id")
        occurrence = identity.get("occurrence")
        if (
            not isinstance(stable_id, str)
            or not stable_id
            or not isinstance(occurrence, int)
            or isinstance(occurrence, bool)
        ):
            raise ValueError("T069 legal action identity is incomplete")
        identities.append(dict(identity))
    return identities


def _required_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"T069 {label} must be non-empty")
    return value
