"""Authorization and execution-plan contracts for the T113 direct canary.

This module does not import the simulator bridge.  It validates a separate
Maintainer canary authorization and emits only non-authorizing readiness data.
The command/runtime boundary remains responsible for lazy native loading.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t113_configured_particle_convergence import (
    T113_APPROVED_SPEC_COMMIT,
    T113_NATIVE_IDENTITY,
    T113_SEARCH_CONFIGURATION,
    T113_TASK_ID,
    T113ConvergenceError,
    validate_t113_fixed_cohort,
)

T113_CANARY_READINESS_SCHEMA = "t113-canary-readiness-v1"
T113_CANARY_AUTHORIZATION_SCHEMA = "t113-maintainer-canary-authorization-v1"
T113_CANARY_RESOURCE_POLICY_SCHEMA = "t113-canary-resource-guard-policy-v1"
T113_CANARY_CALL_ATTEMPT_SCHEMA = "t113-canary-call-attempt-v1"
T113_CANARY_RAW_STAGE_SCHEMA = "t113-canary-raw-stage-manifest-v1"
T113_CANARY_FAILURE_SCHEMA = "t113-canary-stage-failure-v1"
T113_CANARY_FINALIZATION_SCHEMA = "t113-canary-finalization-v1"


class T113CanaryAuthorizationError(T113ConvergenceError):
    """The T113 canary authorization or its exact input binding is invalid."""


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T113CanaryAuthorizationError(f"{label} must be a lowercase SHA-256")
    return value


def _full_head(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T113CanaryAuthorizationError(f"{label} must be a full Git commit SHA")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise T113CanaryAuthorizationError(f"{label} must be a positive integer")
    return value


def _utc_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise T113CanaryAuthorizationError(f"{label} must be an ISO-8601 UTC time")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise T113CanaryAuthorizationError(
            f"{label} must be an ISO-8601 UTC time"
        ) from exc
    if parsed.utcoffset() != timedelta(0):
        raise T113CanaryAuthorizationError(f"{label} must use UTC")
    return parsed


def t113_canary_selection(
    cohort_manifest: Mapping[str, object],
) -> list[dict[str, object]]:
    """Return only the preregistered first A/B/C states at replicate zero."""

    cohort = validate_t113_fixed_cohort(cohort_manifest)
    selected = cohort["selected"]
    if not isinstance(selected, list):
        raise T113CanaryAuthorizationError("fixed cohort selected rows are malformed")
    selection: list[dict[str, object]] = []
    for stratum in T101_SOURCE_COUNTS:
        row = next((item for item in selected if item.get("stratum") == stratum), None)
        if not isinstance(row, Mapping):
            raise T113CanaryAuthorizationError(
                f"fixed cohort has no retained {stratum} state"
            )
        identity = row.get("selection_identity")
        if not isinstance(identity, str) or not identity:
            raise T113CanaryAuthorizationError("fixed cohort identity is malformed")
        selection.append(
            {
                "selection_identity": identity,
                "stratum": stratum,
                "replicate_index": 0,
                "sampler_seed_input": derive_t101_sampler_seed(identity, 0),
                "selection_digest": row.get("selection_digest"),
                "source_ordinal": row.get("source_ordinal"),
                "t112_admission_bridge_report_sha256": row.get(
                    "t112_admission_bridge_report_sha256"
                ),
            }
        )
    return selection


def _validate_qualification(
    qualification: Mapping[str, object],
    *,
    implementation_head: str,
    fixed_cohort: Mapping[str, object],
    native_manifest_sha256: str,
    native_binary_sha256: str,
) -> None:
    native_manifest = qualification.get("native_source_manifest")
    if (
        qualification.get("schema_id") != "t113-input-qualification-v1"
        or qualification.get("task_id") != T113_TASK_ID
        or qualification.get("eligible") is not True
        or qualification.get("candidate_execution_started") is not False
        or qualification.get("execution_authorized") is not False
        or qualification.get("canary_authorized") is not False
        or qualification.get("implementation_head") != implementation_head
        or qualification.get("approved_spec_commit") != T113_APPROVED_SPEC_COMMIT
        or qualification.get("native_identity") != T113_NATIVE_IDENTITY
        or not isinstance(native_manifest, Mapping)
        or native_manifest.get("sha256") != native_manifest_sha256
        or qualification.get("native_binary_sha256") != native_binary_sha256
        or qualification.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
    ):
        raise T113CanaryAuthorizationError(
            "T113 qualification does not bind the exact head/native/configuration"
        )
    qualified_cohort = qualification.get("fixed_cohort")
    if not isinstance(qualified_cohort, Mapping) or (
        validate_t113_fixed_cohort(qualified_cohort)
        != validate_t113_fixed_cohort(fixed_cohort)
    ):
        raise T113CanaryAuthorizationError(
            "T113 qualification and fixed-cohort artifact disagree"
        )


def build_t113_canary_readiness(
    *,
    qualification: Mapping[str, object],
    fixed_cohort: Mapping[str, object],
    implementation_head: str,
    qualification_artifact_sha256: str,
    fixed_cohort_artifact_sha256: str,
    native_manifest_sha256: str,
    native_binary_sha256: str,
) -> dict[str, object]:
    """Prepare a hash-bound canary authorization template without granting it."""

    head = _full_head(implementation_head, "implementation_head")
    qualification_sha = _sha256(
        qualification_artifact_sha256, "qualification_artifact_sha256"
    )
    cohort_sha = _sha256(fixed_cohort_artifact_sha256, "fixed_cohort_artifact_sha256")
    manifest_sha = _sha256(native_manifest_sha256, "native_manifest_sha256")
    binary_sha = _sha256(native_binary_sha256, "native_binary_sha256")
    cohort = validate_t113_fixed_cohort(fixed_cohort)
    _validate_qualification(
        qualification,
        implementation_head=head,
        fixed_cohort=cohort,
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    selection = t113_canary_selection(cohort)
    binding = {
        "implementation_head": head,
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "qualification_artifact_sha256": qualification_sha,
        "fixed_cohort_artifact_sha256": cohort_sha,
        "fixed_cohort_semantic_sha256": canonical_sha256(cohort),
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "native_manifest_sha256": manifest_sha,
        "native_binary_sha256": binary_sha,
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "canary_selection_sha256": canonical_sha256(selection),
    }
    return {
        "schema_id": T113_CANARY_READINESS_SCHEMA,
        "task_id": T113_TASK_ID,
        **binding,
        "canary_selection": selection,
        "preparation_only": True,
        "canary_authorized": False,
        "canary_started": False,
        "native_simulator_or_bridge_called": False,
        "authorization_template": {
            "schema_id": T113_CANARY_AUTHORIZATION_SCHEMA,
            "task_id": T113_TASK_ID,
            "authorization_kind": "bounded_canary",
            "authorized": None,
            "authorization_id": None,
            **binding,
            "resource_guard_policy": None,
            "maintainer_attestation": None,
        },
        "resource_guard_requirements": {
            "schema_id": T113_CANARY_RESOURCE_POLICY_SCHEMA,
            "worker_count": 1,
            "max_effective_concurrency": 1,
            "measured_available_memory_mib_required": True,
            "measured_peak_rss_mib_required": True,
            "runtime_rss_limit_mib_must_not_exceed_memory_request_mib": True,
        },
    }


def validate_t113_canary_authorization(
    value: object,
    *,
    readiness: Mapping[str, object],
    qualification: Mapping[str, object],
    fixed_cohort: Mapping[str, object],
    implementation_head: str,
    qualification_artifact_sha256: str,
    fixed_cohort_artifact_sha256: str,
    native_manifest_sha256: str,
    native_binary_sha256: str,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Require distinct exact-head authority and a fresh measured single-worker guard."""

    expected_readiness = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=fixed_cohort,
        implementation_head=implementation_head,
        qualification_artifact_sha256=qualification_artifact_sha256,
        fixed_cohort_artifact_sha256=fixed_cohort_artifact_sha256,
        native_manifest_sha256=native_manifest_sha256,
        native_binary_sha256=native_binary_sha256,
    )
    if dict(readiness) != expected_readiness:
        raise T113CanaryAuthorizationError(
            "T113 canary readiness is not the current exact input binding"
        )
    if not isinstance(value, Mapping):
        raise T113CanaryAuthorizationError(
            "distinct T113 canary authorization is required"
        )
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        "approved_spec_commit",
        "qualification_artifact_sha256",
        "fixed_cohort_artifact_sha256",
        "fixed_cohort_semantic_sha256",
        "native_identity",
        "native_manifest_sha256",
        "native_binary_sha256",
        "frozen_search_configuration",
        "canary_selection_sha256",
        "resource_guard_policy",
        "maintainer_attestation",
    }
    if set(value) != required:
        raise T113CanaryAuthorizationError(
            "T113 canary authorization has an unexpected shape"
        )
    binding_keys = (
        "implementation_head",
        "approved_spec_commit",
        "qualification_artifact_sha256",
        "fixed_cohort_artifact_sha256",
        "fixed_cohort_semantic_sha256",
        "native_identity",
        "native_manifest_sha256",
        "native_binary_sha256",
        "frozen_search_configuration",
        "canary_selection_sha256",
    )
    if (
        value.get("schema_id") != T113_CANARY_AUTHORIZATION_SCHEMA
        or value.get("task_id") != T113_TASK_ID
        or value.get("authorization_kind") != "bounded_canary"
        or value.get("authorized") is not True
        or not isinstance(value.get("authorization_id"), str)
        or not value["authorization_id"].strip()
        or any(value.get(key) != readiness.get(key) for key in binding_keys)
    ):
        raise T113CanaryAuthorizationError(
            "T113 canary authorization is not an exact-head binding"
        )
    guard = value.get("resource_guard_policy")
    if not isinstance(guard, Mapping):
        raise T113CanaryAuthorizationError("measured canary resource policy is missing")
    guard_fields = {
        "schema_id",
        "worker_count",
        "max_effective_concurrency",
        "memory_request_mib",
        "runtime_rss_limit_mib",
        "measured_available_memory_mib",
        "measured_peak_rss_mib",
        "measurement_source",
        "measured_at_utc",
    }
    if set(guard) != guard_fields:
        raise T113CanaryAuthorizationError(
            "T113 canary resource guard policy has an unexpected shape"
        )
    request_mib = _positive_int(guard.get("memory_request_mib"), "memory_request_mib")
    rss_limit = _positive_int(
        guard.get("runtime_rss_limit_mib"), "runtime_rss_limit_mib"
    )
    available_mib = _positive_int(
        guard.get("measured_available_memory_mib"),
        "measured_available_memory_mib",
    )
    peak_rss_mib = _positive_int(
        guard.get("measured_peak_rss_mib"), "measured_peak_rss_mib"
    )
    if (
        guard.get("schema_id") != T113_CANARY_RESOURCE_POLICY_SCHEMA
        or isinstance(guard.get("worker_count"), bool)
        or guard.get("worker_count") != 1
        or isinstance(guard.get("max_effective_concurrency"), bool)
        or guard.get("max_effective_concurrency") != 1
        or rss_limit > request_mib
        or available_mib < request_mib
        or peak_rss_mib > rss_limit
        or not isinstance(guard.get("measurement_source"), str)
        or not guard["measurement_source"].strip()
    ):
        raise T113CanaryAuthorizationError(
            "T113 measured single-worker resource guard policy is invalid"
        )
    measured_at = _utc_timestamp(guard.get("measured_at_utc"), "resource measurement")
    now = now_utc or datetime.now(UTC)
    if not isinstance(now, datetime) or now.utcoffset() != timedelta(0):
        raise T113CanaryAuthorizationError(
            "authorization validation clock must use UTC"
        )
    age = (now - measured_at).total_seconds()
    if not math.isfinite(age) or age < 0 or age > 30 * 60:
        raise T113CanaryAuthorizationError(
            "T113 canary resource measurement is older than 30 minutes"
        )
    expected_attestation = {
        "role": "maintainer",
        "decision": "BOUNDED_CANARY_AUTHORIZED",
        "exact_head": implementation_head,
        "resource_guard_policy_sha256": canonical_sha256(dict(guard)),
    }
    if value.get("maintainer_attestation") != expected_attestation:
        raise T113CanaryAuthorizationError(
            "T113 canary Maintainer attestation does not bind exact head/resources"
        )
    return dict(value)


__all__ = [
    "T113_CANARY_AUTHORIZATION_SCHEMA",
    "T113_CANARY_CALL_ATTEMPT_SCHEMA",
    "T113_CANARY_FAILURE_SCHEMA",
    "T113_CANARY_FINALIZATION_SCHEMA",
    "T113_CANARY_RAW_STAGE_SCHEMA",
    "T113_CANARY_READINESS_SCHEMA",
    "T113_CANARY_RESOURCE_POLICY_SCHEMA",
    "T113CanaryAuthorizationError",
    "build_t113_canary_readiness",
    "canonical_sha256",
    "t113_canary_selection",
    "validate_t113_canary_authorization",
]
