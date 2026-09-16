"""Authorized-only, detached T092 paired-canary execution boundary.

This module is deliberately separate from the file-only readiness commands.
It contains the one-start-per-shard runner entrypoint that a later Maintainer
authorization may call.  Nothing imports an adapter or invokes a runner until
the exact authorization, split ledger, frozen teacher envelope, arm identities,
worker topology, and retained-input identity mapping have all been checked.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.sim.t092_canary import (
    T092_CANARY_EVIDENCE_SCHEMA_ID,
    T092_CANARY_START_COUNT,
    T092_PUBLICATION_NATIVE_IDENTITY,
    T092CanaryError,
    _validate_pair_record,
    _validate_worker,
    build_t092_canary_plan,
    select_t092_canary_entries,
    validate_t092_canary_evidence,
)
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_IDENTITY,
)

T092_CANARY_AUTHORIZATION_SCHEMA_ID = "t092-maintainer-canary-authorization-v1"
T092_CANARY_SHARD_SCHEMA_ID = "t092-paired-canary-shard-v1"
T092_CANARY_RETENTION_SCHEMA_ID = "t092-paired-canary-retention-manifest-v1"
T092_CANARY_SHARD_ASSIGNMENT = "canonical-selected-ordinal-v1"


class T092CanaryExecutionError(T092CanaryError):
    """An authorization, detached shard, or retained output is incomplete."""


def _full_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _topology(*, shard_index: int, shard_count: int, worker_count: int) -> dict[str, Any]:
    if (
        isinstance(shard_index, bool)
        or not isinstance(shard_index, int)
        or isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or shard_count != T092_CANARY_START_COUNT
        or worker_count != T092_CANARY_START_COUNT
        or shard_index < 0
        or shard_index >= shard_count
    ):
        raise T092CanaryExecutionError("T092 canary requires exactly 12 shards/workers")
    return {
        "shard_index": shard_index,
        "shard_count": shard_count,
        "worker_count": worker_count,
        "assignment": T092_CANARY_SHARD_ASSIGNMENT,
    }


def build_t092_canary_authorization_template(
    *,
    implementation_head: str,
    split_manifest: Mapping[str, Any],
    runtime_input_identities: Mapping[str, Any],
    output_root: str | Path,
) -> dict[str, Any]:
    """Prepare an exact, non-authorizing record for Maintainer review."""

    if not _full_sha(implementation_head):
        raise T092CanaryExecutionError("T092 implementation head must be a full SHA-1")
    if not isinstance(runtime_input_identities, Mapping) or not runtime_input_identities:
        raise T092CanaryExecutionError("T092 runtime input identities are unavailable")
    plan = build_t092_canary_plan(split_manifest)
    identity = {
        "schema_id": T092_CANARY_AUTHORIZATION_SCHEMA_ID,
        "task_id": "T092",
        "authorization_kind": "bounded_canary",
        "implementation_head": implementation_head,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "canary_plan_sha256": canonical_sha256(plan),
        "runtime_input_identities_sha256": canonical_sha256(dict(runtime_input_identities)),
        "arm_native_identities": {
            "OFF": dict(T092_PUBLICATION_NATIVE_IDENTITY),
            "ON": dict(T092_NATIVE_IDENTITY),
        },
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "shard_topology": {
            "shard_count": T092_CANARY_START_COUNT,
            "worker_count": T092_CANARY_START_COUNT,
            "assignment": T092_CANARY_SHARD_ASSIGNMENT,
        },
        "output_root": str(Path(output_root).resolve()),
    }
    return {
        "schema_id": "t092-canary-authorization-preparation-v1",
        "task_id": "T092",
        "preparation_only": True,
        "canary_plan": plan,
        "runtime_input_identities": dict(runtime_input_identities),
        "authorization_identity": identity,
        "authorization_template": {
            **identity,
            "authorized": None,
            "authorization_id": None,
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "CANARY_AUTHORIZED",
                "exact_head": implementation_head,
            },
        },
    }


def validate_t092_canary_authorization(
    authorization: Mapping[str, Any] | None,
    *,
    implementation_head: str,
    split_manifest: Mapping[str, Any],
    runtime_input_identities: Mapping[str, Any],
    output_root: str | Path,
) -> None:
    """Require a single exact-head Maintainer authorization before a runner exists."""

    if not _full_sha(implementation_head):
        raise T092CanaryExecutionError("T092 implementation head must be a full SHA-1")
    if not isinstance(authorization, Mapping):
        raise T092CanaryExecutionError("explicit T092 Maintainer canary authorization is required")
    plan = build_t092_canary_plan(split_manifest)
    required = {
        "schema_id", "task_id", "authorization_kind", "authorized", "authorization_id",
        "implementation_head", "split_manifest_sha256", "canary_plan_sha256",
        "runtime_input_identities_sha256", "arm_native_identities", "teacher_config",
        "shard_topology", "output_root", "maintainer_attestation",
    }
    if set(authorization) != required:
        raise T092CanaryExecutionError("T092 canary authorization has an unexpected shape")
    expected_output = str(Path(output_root).resolve())
    expected_topology = {
        "shard_count": T092_CANARY_START_COUNT,
        "worker_count": T092_CANARY_START_COUNT,
        "assignment": T092_CANARY_SHARD_ASSIGNMENT,
    }
    expected_arms = {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY}
    attestation = authorization.get("maintainer_attestation")
    if (
        authorization.get("schema_id") != T092_CANARY_AUTHORIZATION_SCHEMA_ID
        or authorization.get("task_id") != "T092"
        or authorization.get("authorization_kind") != "bounded_canary"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != implementation_head
        or authorization.get("split_manifest_sha256") != canonical_sha256(split_manifest)
        or authorization.get("canary_plan_sha256") != canonical_sha256(plan)
        or authorization.get("runtime_input_identities_sha256")
        != canonical_sha256(dict(runtime_input_identities))
        or authorization.get("arm_native_identities") != expected_arms
        or authorization.get("teacher_config") != T092_FROZEN_TEACHER_CONFIG
        or authorization.get("shard_topology") != expected_topology
        or authorization.get("output_root") != expected_output
        or attestation != {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": implementation_head,
        }
    ):
        raise T092CanaryExecutionError("T092 canary authorization is not an exact approved binding")


def execute_t092_authorized_canary_shard(
    *,
    authorization: Mapping[str, Any] | None,
    implementation_head: str,
    split_manifest: Mapping[str, Any],
    runtime_input_identities: Mapping[str, Any],
    output_root: str | Path,
    shard_index: int,
    shard_count: int,
    worker_count: int,
    runner: Callable[[Any], Mapping[str, Any]],
) -> dict[str, Any]:
    """Run one exact selected start after all authorization checks pass."""

    topology = _topology(
        shard_index=shard_index, shard_count=shard_count, worker_count=worker_count
    )
    validate_t092_canary_authorization(
        authorization,
        implementation_head=implementation_head,
        split_manifest=split_manifest,
        runtime_input_identities=runtime_input_identities,
        output_root=output_root,
    )
    if not callable(runner):
        raise T092CanaryExecutionError("T092 canary runner must be callable")
    source = select_t092_canary_entries(split_manifest)[shard_index]
    try:
        pair = _validate_pair_record(runner(source), source)
    except T092CanaryError as exc:
        raise T092CanaryExecutionError("T092 canary shard pair is incomplete") from exc
    worker = {
        "stage_worker_count": worker_count,
        "worker_index": shard_index,
        "shard_count": shard_count,
        "shard_index": shard_index,
    }
    _validate_worker(worker)
    if pair.get("worker") != worker:
        raise T092CanaryExecutionError("T092 canary shard worker provenance mismatches topology")
    return {
        "schema_id": T092_CANARY_SHARD_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "authorization_id": authorization["authorization_id"],
        "implementation_head": implementation_head,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "canary_plan_sha256": canonical_sha256(build_t092_canary_plan(split_manifest)),
        "runtime_input_identities_sha256": canonical_sha256(dict(runtime_input_identities)),
        "topology": topology,
        "pair": pair,
        "pair_sha256": canonical_sha256(pair),
    }


def merge_t092_authorized_canary_shards(
    *,
    authorization: Mapping[str, Any] | None,
    implementation_head: str,
    split_manifest: Mapping[str, Any],
    runtime_input_identities: Mapping[str, Any],
    output_root: str | Path,
    shards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Fail closed unless all twelve exact detached shard records are present."""

    validate_t092_canary_authorization(
        authorization,
        implementation_head=implementation_head,
        split_manifest=split_manifest,
        runtime_input_identities=runtime_input_identities,
        output_root=output_root,
    )
    if len(shards) != T092_CANARY_START_COUNT:
        raise T092CanaryExecutionError("T092 canary merge requires all 12 shards")
    selected = select_t092_canary_entries(split_manifest)
    entries: list[dict[str, Any]] = []
    for index, (raw, source) in enumerate(zip(shards, selected, strict=True)):
        topology = _topology(shard_index=index, shard_count=12, worker_count=12)
        if not isinstance(raw, Mapping) or set(raw) != {
            "schema_id", "schema_version", "task_id", "authorization_id", "implementation_head",
            "split_manifest_sha256", "canary_plan_sha256", "runtime_input_identities_sha256",
            "topology", "pair", "pair_sha256",
        }:
            raise T092CanaryExecutionError("T092 canary shard has an unexpected shape")
        if (
            raw.get("schema_id") != T092_CANARY_SHARD_SCHEMA_ID
            or raw.get("schema_version") != 1
            or raw.get("task_id") != "T092"
            or raw.get("authorization_id") != authorization["authorization_id"]
            or raw.get("implementation_head") != implementation_head
            or raw.get("split_manifest_sha256") != canonical_sha256(split_manifest)
            or raw.get("canary_plan_sha256") != canonical_sha256(build_t092_canary_plan(split_manifest))
            or raw.get("runtime_input_identities_sha256") != canonical_sha256(dict(runtime_input_identities))
            or raw.get("topology") != topology
            or not isinstance(raw.get("pair"), Mapping)
            or raw.get("pair_sha256") != canonical_sha256(raw["pair"])
        ):
            raise T092CanaryExecutionError("T092 canary shard provenance is invalid")
        try:
            pair = _validate_pair_record(raw["pair"], source)
        except T092CanaryError as exc:
            raise T092CanaryExecutionError("T092 canary shard pair is incomplete") from exc
        expected_worker = {
            "stage_worker_count": 12, "worker_index": index,
            "shard_count": 12, "shard_index": index,
        }
        if pair.get("worker") != expected_worker:
            raise T092CanaryExecutionError("T092 canary shard worker binding is invalid")
        entries.append(pair)
    evidence = _build_evidence(split_manifest=split_manifest, entries=entries)
    validate_t092_canary_evidence(evidence, split_manifest=split_manifest)
    return evidence


def _build_evidence(*, split_manifest: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [dict(entry) for entry in entries]
    return {
        "schema_id": T092_CANARY_EVIDENCE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "classification": "MECHANICS_INFORMATION_BOUNDARY_ONLY",
        "formal_execution_authorized": False,
        "training_eligible": False,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "arm_native_identities": {
            "OFF": dict(T092_PUBLICATION_NATIVE_IDENTITY), "ON": dict(T092_NATIVE_IDENTITY),
        },
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_execution_entries": normalized,
        "source_execution_entries_sha256": canonical_sha256(normalized),
        "semantic_parity": {"passed": True, "mismatch_count": 0},
        "internal_occurrences": [
            row for entry in normalized for row in entry["on"]["internal_occurrences"]
        ],
    }


def write_t092_canary_json(path: str | Path, payload: Mapping[str, Any], *, schema_id: str) -> dict[str, Any]:
    """Create one immutable JSON artifact and return its retention identity."""

    destination = Path(path).resolve()
    if destination.exists():
        raise T092CanaryExecutionError("refusing to overwrite retained T092 canary output")
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T092CanaryExecutionError("cannot create retained T092 canary output") from exc
    return {
        "path": str(destination), "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded), "schema_id": schema_id,
    }


__all__ = [
    "T092_CANARY_AUTHORIZATION_SCHEMA_ID", "T092_CANARY_RETENTION_SCHEMA_ID",
    "T092_CANARY_SHARD_SCHEMA_ID", "T092CanaryExecutionError",
    "build_t092_canary_authorization_template", "execute_t092_authorized_canary_shard",
    "merge_t092_authorized_canary_shards", "validate_t092_canary_authorization",
    "write_t092_canary_json",
]
