"""T069 exact search-scope projection for invariant public-run context features."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import math
import struct
from time import perf_counter
from typing import Any

from sts_combat_rl.sim.search_cost import canonical_public_json
from sts_combat_rl.sim.public_context_artifacts import PUBLIC_CONTEXT_AVAILABLE
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
    public_context_features,
)


T069_PROJECTION_SCHEMA_ID = "t069-public-context-feature-projection-v1"
T069_PROJECTION_SCHEMA_VERSION = 1
T069_PROJECTION_IMPLEMENTATION_ID = (
    "search-scope-complete-public-context-feature-projection-v1"
)


@dataclass(frozen=True)
class PublicContextFeatureProjection:
    """Complete collision-checked public-context identity plus its exact vector."""

    canonical_public_context: bytes
    canonical_public_context_sha256: str
    public_context_features: tuple[float, ...]
    public_context_features_sha256: str
    checkpoint_artifact_id: str
    dtype: str
    device: str
    canonicalization_ms: float
    validation_encoding_ms: float
    construction_ms: float
    schema_id: str = T069_PROJECTION_SCHEMA_ID
    schema_version: int = T069_PROJECTION_SCHEMA_VERSION
    implementation_id: str = T069_PROJECTION_IMPLEMENTATION_ID
    feature_schema_id: str = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
    feature_schema_version: int = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    feature_names: tuple[str, ...] = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES
    feature_size: int = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE

    def telemetry(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "implementation_id": self.implementation_id,
            "feature_schema_id": self.feature_schema_id,
            "feature_schema_version": self.feature_schema_version,
            "feature_names": list(self.feature_names),
            "feature_size": self.feature_size,
            "dtype": self.dtype,
            "device": self.device,
            "checkpoint_artifact_id": self.checkpoint_artifact_id,
            "canonical_public_context_sha256": (self.canonical_public_context_sha256),
            "canonical_public_context_byte_count": len(self.canonical_public_context),
            "public_context_features_sha256": self.public_context_features_sha256,
            "construction_count": 1,
            "canonicalization_ms": self.canonicalization_ms,
            "validation_encoding_ms": self.validation_encoding_ms,
            "construction_ms": self.construction_ms,
        }


def build_public_context_feature_projection(
    public_run_context: Mapping[str, Any],
    *,
    checkpoint_artifact_id: str,
    dtype: str,
    device: str,
) -> PublicContextFeatureProjection:
    """Validate and encode one complete public context for one search scope."""

    started = perf_counter()
    canonical_started = perf_counter()
    canonical = canonical_public_json(public_run_context)
    canonicalization_ms = (perf_counter() - canonical_started) * 1000.0

    encoding_started = perf_counter()
    features = tuple(
        float(value)
        for value in public_context_features(
            public_run_context,
            PUBLIC_CONTEXT_AVAILABLE,
        )
    )
    validation_encoding_ms = (perf_counter() - encoding_started) * 1000.0
    _validate_finite_features(features)
    if len(features) != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE:
        raise ValueError(
            "T069 public-context projection feature size does not match current schema"
        )
    return PublicContextFeatureProjection(
        canonical_public_context=canonical,
        canonical_public_context_sha256=hashlib.sha256(canonical).hexdigest(),
        public_context_features=features,
        public_context_features_sha256=_feature_sha256(features),
        checkpoint_artifact_id=_required_text(
            checkpoint_artifact_id, "checkpoint artifact id"
        ),
        dtype=_required_text(dtype, "dtype"),
        device=_required_text(device, "device"),
        canonicalization_ms=canonicalization_ms,
        validation_encoding_ms=validation_encoding_ms,
        construction_ms=(perf_counter() - started) * 1000.0,
    )


def validate_public_context_feature_projection(
    projection: PublicContextFeatureProjection,
    public_run_context: Mapping[str, Any],
    *,
    checkpoint_artifact_id: str,
    dtype: str,
    device: str,
    feature_schema_id: str,
    feature_schema_version: int,
    feature_names: Sequence[str],
    feature_size: int,
) -> float:
    """Validate complete context bytes and every projection provenance field.

    A digest is reported for provenance, but reuse is authorized only after the
    complete canonical bytes compare equal.
    """

    started = perf_counter()
    if projection.schema_id != T069_PROJECTION_SCHEMA_ID:
        raise ValueError("T069 projection schema id does not match")
    if projection.schema_version != T069_PROJECTION_SCHEMA_VERSION:
        raise ValueError("T069 projection schema version does not match")
    if projection.implementation_id != T069_PROJECTION_IMPLEMENTATION_ID:
        raise ValueError("T069 projection implementation id does not match")
    if projection.checkpoint_artifact_id != checkpoint_artifact_id:
        raise ValueError("T069 projection checkpoint identity does not match")
    if projection.dtype != dtype or projection.device != device:
        raise ValueError("T069 projection dtype/device does not match scorer")
    if projection.feature_schema_id != feature_schema_id:
        raise ValueError("T069 projection feature schema id does not match model")
    if projection.feature_schema_version != feature_schema_version:
        raise ValueError("T069 projection feature schema version does not match model")
    if projection.feature_names != tuple(feature_names):
        raise ValueError("T069 projection feature names/order do not match model")
    if projection.feature_size != feature_size:
        raise ValueError("T069 projection feature size does not match model")
    if len(projection.public_context_features) != feature_size:
        raise ValueError("T069 projection vector is partial or has duplicate features")
    _validate_finite_features(projection.public_context_features)
    if (
        _feature_sha256(projection.public_context_features)
        != projection.public_context_features_sha256
    ):
        raise ValueError("T069 projection feature vector changed after construction")

    canonical = canonical_public_json(public_run_context)
    if canonical != projection.canonical_public_context:
        raise ValueError(
            "T069 projection public context is stale or belongs to another search"
        )
    if hashlib.sha256(canonical).hexdigest() != (
        projection.canonical_public_context_sha256
    ):
        raise ValueError("T069 projection canonical identity is inconsistent")
    return (perf_counter() - started) * 1000.0


def feature_vector_sha256(values: Sequence[float]) -> str:
    """Public helper for exact T069 diagnostic input identities."""

    finite = tuple(float(value) for value in values)
    _validate_finite_features(finite)
    return _feature_sha256(finite)


def _feature_sha256(values: Sequence[float]) -> str:
    payload = b"".join(struct.pack(">d", float(value)) for value in values)
    return hashlib.sha256(payload).hexdigest()


def _validate_finite_features(values: Sequence[float]) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("T069 projection contains non-finite public-context features")


def _required_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"T069 projection {label} must be non-empty")
    return value
