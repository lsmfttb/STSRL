"""Explicitly authorized, fail-closed T088 formal execution boundaries.

This module owns the formal raw-row retention boundary only.  It intentionally
does not produce statistical, promotion, or report artifacts.  A caller must
admit the retained T087/T085 inputs and the accepted canary separately, then
provide one exact Maintainer authorization before a shard can construct a
runner.  Each shard is all-or-nothing and the finalizer accepts only the full
deterministic shard topology.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace

from sts_combat_rl.commands.t088_classical_combat_tournament import (
    T088_ARM_ORDER,
    build_t088_controller,
    t088_controller_definitions,
)
from sts_combat_rl.sim.t088_canary_execution import (
    T088CanaryExecutionError,
    _safe_runner_exception_detail,
    _validate_execution_row,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_ARMS,
    T088_TASK_ID,
    T088IncompleteError,
    _binding_identity,
    build_t088_formal_plan,
    validate_t088_canary_evidence,
    validate_t088_execution_rows,
    validate_t088_t087_cohort_binding,
)

T088_FORMAL_AUTHORIZATION_SCHEMA_ID = "t088-maintainer-formal-authorization-v1"
T088_FORMAL_SHARD_SCHEMA_ID = "t088-formal-execution-shard-v1"
T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID = "t088-formal-raw-evidence-v1"
T088_FORMAL_DEFAULT_SHARD_COUNT = 16
T088_FORMAL_SHARD_ASSIGNMENT = "canonical-global-ordinal-modulo-v1"


class T088FormalExecutionError(T088IncompleteError):
    """A formal authorization, shard, or raw-evidence boundary failed closed."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _artifact_reference(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "path",
        "sha256",
        "size_bytes",
        "schema_id",
    }:
        raise T088FormalExecutionError(f"{label} identity is malformed")
    path, digest, size, schema = (
        value.get("path"),
        value.get("sha256"),
        value.get("size_bytes"),
        value.get("schema_id"),
    )
    if (
        not isinstance(path, str)
        or not path
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
        or not isinstance(schema, str)
        or not schema
    ):
        raise T088FormalExecutionError(f"{label} identity is malformed")
    return dict(value)


def _topology(
    *, shard_index: int, shard_count: int, worker_count: int
) -> dict[str, object]:
    if (
        isinstance(shard_index, bool)
        or not isinstance(shard_index, int)
        or isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or shard_count <= 0
        or worker_count <= 0
        or worker_count > shard_count
        or shard_index < 0
        or shard_index >= shard_count
    ):
        raise T088FormalExecutionError("formal shard topology is invalid")
    return {
        "shard_index": shard_index,
        "shard_count": shard_count,
        "worker_count": worker_count,
        "assignment": T088_FORMAL_SHARD_ASSIGNMENT,
    }


def _shard_plan_rows(
    plan: Mapping[str, object], *, shard_index: int, shard_count: int
) -> list[dict[str, object]]:
    rows = plan.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise T088FormalExecutionError("formal plan rows are unavailable")
    selected = [
        dict(row)
        for global_ordinal, row in enumerate(rows)
        if global_ordinal % shard_count == shard_index and isinstance(row, Mapping)
    ]
    if not selected or len(selected) != sum(
        1 for ordinal in range(len(rows)) if ordinal % shard_count == shard_index
    ):
        raise T088FormalExecutionError("formal shard plan is malformed")
    return selected


def _validate_canary_evidence(
    evidence: Mapping[str, object], *, cohort_binding: Mapping[str, object]
) -> None:
    if (
        evidence.get("schema_id") != "t088-canary-evidence-v1"
        or evidence.get("task_id") != T088_TASK_ID
        or evidence.get("formal_execution_authorized") is not False
        or evidence.get("t087_cohort_binding") != _binding_identity(cohort_binding)
        or evidence.get("controller_definitions") != t088_controller_definitions()
    ):
        raise T088FormalExecutionError("accepted T088 canary evidence is invalid")
    selection, rows = evidence.get("canary_selection"), evidence.get("rows")
    if not isinstance(selection, Mapping) or not isinstance(rows, Sequence):
        raise T088FormalExecutionError("accepted T088 canary evidence is incomplete")
    try:
        validate_t088_canary_evidence(
            selection,
            rows,  # type: ignore[arg-type]
            cohort_binding=cohort_binding,
        )
    except (T088IncompleteError, TypeError, ValueError) as exc:
        raise T088FormalExecutionError(
            "accepted T088 canary evidence is incomplete"
        ) from exc


def validate_t088_accepted_canary_evidence(
    evidence: Mapping[str, object], *, cohort_binding: Mapping[str, object]
) -> None:
    """Validate the accepted canary before formal authorization preparation."""

    _validate_canary_evidence(evidence, cohort_binding=cohort_binding)


def validate_t088_formal_authorization(
    authorization: Mapping[str, object] | None,
    *,
    implementation_head: str,
    input_identities: Mapping[str, object],
    canary_evidence_reference: Mapping[str, object],
    canary_evidence: Mapping[str, object],
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    shard_index: int,
    shard_count: int,
    worker_count: int,
    output_root: str,
) -> dict[str, object]:
    """Require one exact Maintainer authorization before a formal shard runs."""

    if not _is_sha(implementation_head):
        raise T088FormalExecutionError("T088 implementation head must be a full SHA-1")
    if not isinstance(authorization, Mapping):
        raise T088FormalExecutionError(
            "explicit T088 Maintainer formal authorization is required"
        )
    topology = _topology(
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
    )
    if not isinstance(output_root, str) or not output_root:
        raise T088FormalExecutionError("formal output root is invalid")
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    plan = build_t088_formal_plan(cohort, cohort_binding=cohort_binding)
    reference = _artifact_reference(canary_evidence_reference, label="canary evidence")
    _validate_canary_evidence(canary_evidence, cohort_binding=cohort_binding)
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        "input_identities_sha256",
        "canary_evidence",
        "t087_cohort_binding",
        "controller_definitions_sha256",
        "formal_plan_sha256",
        "shard_topology",
        "output_root",
        "maintainer_attestation",
    }
    if set(authorization) != required:
        raise T088FormalExecutionError("formal authorization has an unexpected shape")
    attestation = authorization.get("maintainer_attestation")
    expected_topology = {
        "shard_count": shard_count,
        "worker_count": worker_count,
        "assignment": T088_FORMAL_SHARD_ASSIGNMENT,
    }
    if (
        authorization.get("schema_id") != T088_FORMAL_AUTHORIZATION_SCHEMA_ID
        or authorization.get("task_id") != T088_TASK_ID
        or authorization.get("authorization_kind") != "formal_tournament"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != implementation_head
        or authorization.get("input_identities_sha256")
        != _canonical_sha256(input_identities)
        or authorization.get("canary_evidence") != reference
        or authorization.get("t087_cohort_binding") != _binding_identity(cohort_binding)
        or authorization.get("controller_definitions_sha256")
        != _canonical_sha256(t088_controller_definitions())
        or authorization.get("formal_plan_sha256") != _canonical_sha256(plan)
        or authorization.get("shard_topology") != expected_topology
        or authorization.get("output_root") != output_root
        or not isinstance(attestation, Mapping)
        or dict(attestation)
        != {
            "role": "maintainer",
            "decision": "FORMAL_AUTHORIZED",
            "exact_head": implementation_head,
        }
    ):
        raise T088FormalExecutionError(
            "formal authorization is not an exact approved binding"
        )
    return {"plan": plan, "topology": topology, "canary_evidence": reference}


def _validate_shard_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    plan_rows: Sequence[Mapping[str, object]],
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
) -> list[dict[str, object]]:
    by_identity = {str(row["selection_identity"]): dict(row) for row in cohort_rows}
    if len(rows) != len(plan_rows):
        raise T088FormalExecutionError("formal shard row count is incomplete")
    result: list[dict[str, object]] = []
    for raw, planned in zip(rows, plan_rows, strict=True):
        if not isinstance(raw, Mapping):
            raise T088FormalExecutionError("formal shard row is malformed")
        identity, arm = planned.get("selection_identity"), planned.get("arm")
        if not isinstance(identity, str) or not isinstance(arm, str):
            raise T088FormalExecutionError("formal shard plan row is malformed")
        record = by_identity.get(identity)
        provenance = raw.get("controller_provenance")
        if record is None or not isinstance(provenance, Mapping):
            raise T088FormalExecutionError("formal shard row lacks bound provenance")
        try:
            result.append(
                _validate_execution_row(
                    raw,
                    record=record,
                    arm=arm,
                    controller=SimpleNamespace(provenance=provenance),
                    cohort_binding=cohort_binding,
                )
            )
        except (T088CanaryExecutionError, TypeError, ValueError) as exc:
            raise T088FormalExecutionError("formal shard row is invalid") from exc
    return result


def execute_t088_authorized_formal_shard(
    *,
    authorization: Mapping[str, object] | None,
    implementation_head: str,
    input_identities: Mapping[str, object],
    canary_evidence_reference: Mapping[str, object],
    canary_evidence: Mapping[str, object],
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    shard_index: int,
    shard_count: int,
    worker_count: int,
    output_root: str,
    runner: Callable[[Mapping[str, object], str, object], Mapping[str, object]],
    controller_factory: Callable[[str], object] = build_t088_controller,
) -> dict[str, object]:
    """Execute one complete deterministic shard with no partial return value."""

    if not callable(runner) or not callable(controller_factory):
        raise T088FormalExecutionError("formal execution requires runner/controllers")
    admitted = validate_t088_formal_authorization(
        authorization,
        implementation_head=implementation_head,
        input_identities=input_identities,
        canary_evidence_reference=canary_evidence_reference,
        canary_evidence=canary_evidence,
        cohort_rows=cohort_rows,
        cohort_binding=cohort_binding,
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
        output_root=output_root,
    )
    plan = admitted["plan"]
    if not isinstance(plan, Mapping):
        raise T088FormalExecutionError("admitted formal plan is malformed")
    plan_rows = _shard_plan_rows(plan, shard_index=shard_index, shard_count=shard_count)
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    by_identity = {str(record["selection_identity"]): record for record in cohort}
    rows: list[dict[str, object]] = []
    for arm in T088_ARM_ORDER:
        if arm not in T088_ARMS:
            raise T088FormalExecutionError("formal controller order drifted")
        controller = controller_factory(arm)
        for planned in (row for row in plan_rows if row["arm"] == arm):
            identity = planned["selection_identity"]
            record = by_identity.get(str(identity))
            if record is None:
                raise T088FormalExecutionError("formal plan record is unavailable")
            try:
                raw = runner(record, arm, controller)
            except Exception as exc:
                raise T088FormalExecutionError(
                    f"formal runner failed for {identity} arm {arm}: "
                    f"{_safe_runner_exception_detail(exc)}"
                ) from exc
            rows.append(raw)
    validated_rows = _validate_shard_rows(
        rows,
        plan_rows=plan_rows,
        cohort_rows=cohort,
        cohort_binding=cohort_binding,
    )
    return {
        "schema_id": T088_FORMAL_SHARD_SCHEMA_ID,
        "task_id": T088_TASK_ID,
        "formal_execution_authorized": True,
        "implementation_head": implementation_head,
        "authorization": dict(authorization),
        "input_identities_sha256": _canonical_sha256(input_identities),
        "canary_evidence": admitted["canary_evidence"],
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "controller_definitions": t088_controller_definitions(),
        "formal_plan_sha256": _canonical_sha256(plan),
        "shard": admitted["topology"],
        "execution_count": len(validated_rows),
        "rows": validated_rows,
    }


def validate_t088_formal_shard(
    shard: Mapping[str, object],
    *,
    authorization: Mapping[str, object],
    implementation_head: str,
    input_identities: Mapping[str, object],
    canary_evidence_reference: Mapping[str, object],
    canary_evidence: Mapping[str, object],
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    output_root: str,
) -> list[dict[str, object]]:
    """Validate one retained shard before it can enter the deterministic merge."""

    topology = shard.get("shard")
    if not isinstance(topology, Mapping):
        raise T088FormalExecutionError("formal shard topology is unavailable")
    shard_index = topology.get("shard_index")
    shard_count = topology.get("shard_count")
    worker_count = topology.get("worker_count")
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (
            shard_index,
            shard_count,
            worker_count,
        )
    ):
        raise T088FormalExecutionError("formal shard topology is invalid")
    admitted = validate_t088_formal_authorization(
        authorization,
        implementation_head=implementation_head,
        input_identities=input_identities,
        canary_evidence_reference=canary_evidence_reference,
        canary_evidence=canary_evidence,
        cohort_rows=cohort_rows,
        cohort_binding=cohort_binding,
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
        output_root=output_root,
    )
    plan = admitted["plan"]
    if not isinstance(plan, Mapping):
        raise T088FormalExecutionError("admitted formal plan is malformed")
    required = {
        "schema_id",
        "task_id",
        "formal_execution_authorized",
        "implementation_head",
        "authorization",
        "input_identities_sha256",
        "canary_evidence",
        "t087_cohort_binding",
        "controller_definitions",
        "formal_plan_sha256",
        "shard",
        "execution_count",
        "rows",
    }
    if (
        set(shard) != required
        or shard.get("schema_id") != T088_FORMAL_SHARD_SCHEMA_ID
        or shard.get("task_id") != T088_TASK_ID
        or shard.get("formal_execution_authorized") is not True
        or shard.get("implementation_head") != implementation_head
        or shard.get("authorization") != authorization
        or shard.get("input_identities_sha256") != _canonical_sha256(input_identities)
        or shard.get("canary_evidence") != canary_evidence_reference
        or shard.get("t087_cohort_binding") != _binding_identity(cohort_binding)
        or shard.get("controller_definitions") != t088_controller_definitions()
        or shard.get("formal_plan_sha256") != _canonical_sha256(plan)
        or shard.get("shard") != admitted["topology"]
        or not isinstance(shard.get("rows"), Sequence)
        or isinstance(shard.get("rows"), (str, bytes))
        or shard.get("execution_count") != len(shard["rows"])
    ):
        raise T088FormalExecutionError("formal shard identity is invalid")
    return _validate_shard_rows(
        shard["rows"],  # type: ignore[arg-type]
        plan_rows=_shard_plan_rows(
            plan, shard_index=shard_index, shard_count=shard_count
        ),
        cohort_rows=cohort_rows,
        cohort_binding=cohort_binding,
    )


def merge_t088_authorized_formal_shards(
    *,
    authorization: Mapping[str, object],
    implementation_head: str,
    input_identities: Mapping[str, object],
    canary_evidence_reference: Mapping[str, object],
    canary_evidence: Mapping[str, object],
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    output_root: str,
    shards: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Merge only every complete shard into canonical 1,652-row raw evidence."""

    topology = authorization.get("shard_topology")
    if not isinstance(topology, Mapping):
        raise T088FormalExecutionError("formal authorization topology is unavailable")
    shard_count, worker_count = (
        topology.get("shard_count"),
        topology.get("worker_count"),
    )
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (
            shard_count,
            worker_count,
        )
    ):
        raise T088FormalExecutionError("formal authorization topology is invalid")
    validated: dict[int, list[dict[str, object]]] = {}
    for shard in shards:
        shard_rows = validate_t088_formal_shard(
            shard,
            authorization=authorization,
            implementation_head=implementation_head,
            input_identities=input_identities,
            canary_evidence_reference=canary_evidence_reference,
            canary_evidence=canary_evidence,
            cohort_rows=cohort_rows,
            cohort_binding=cohort_binding,
            output_root=output_root,
        )
        index = shard["shard"]["shard_index"]  # type: ignore[index]
        if index in validated:
            raise T088FormalExecutionError("formal shards contain a duplicate index")
        validated[index] = shard_rows
    if set(validated) != set(range(shard_count)):
        raise T088FormalExecutionError("formal shard set is incomplete")
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    plan = build_t088_formal_plan(cohort, cohort_binding=cohort_binding)
    ordered_rows: list[dict[str, object]] = []
    pending = {index: iter(rows) for index, rows in validated.items()}
    for global_ordinal, _planned in enumerate(plan["rows"]):  # type: ignore[index]
        ordered_rows.append(next(pending[global_ordinal % shard_count]))
    if any(next(rows, None) is not None for rows in pending.values()):
        raise T088FormalExecutionError("formal shard rows exceed their plan")
    try:
        validate_t088_execution_rows(
            ordered_rows, cohort, cohort_binding=cohort_binding
        )
    except (T088IncompleteError, TypeError, ValueError) as exc:
        raise T088FormalExecutionError("formal raw evidence is incomplete") from exc
    return {
        "schema_id": T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID,
        "task_id": T088_TASK_ID,
        "formal_execution_authorized": True,
        "implementation_head": implementation_head,
        "authorization": dict(authorization),
        "input_identities_sha256": _canonical_sha256(input_identities),
        "canary_evidence": dict(canary_evidence_reference),
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "controller_definitions": t088_controller_definitions(),
        "formal_plan_sha256": _canonical_sha256(plan),
        "shard_topology": dict(topology),
        "execution_count": len(ordered_rows),
        "rows": ordered_rows,
    }


def _write_new_json(
    path: str | Path, document: Mapping[str, object], *, label: str
) -> dict[str, object]:
    destination = Path(path).resolve()
    if destination.exists():
        raise T088FormalExecutionError(f"refusing to overwrite retained {label}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(document),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T088FormalExecutionError(f"cannot create retained {label}") from exc
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "schema_id": str(document["schema_id"]),
    }


def write_t088_formal_shard(
    path: str | Path, shard: Mapping[str, object]
) -> dict[str, object]:
    """Atomically create one complete retained formal shard without overwrite."""

    if shard.get("schema_id") != T088_FORMAL_SHARD_SCHEMA_ID:
        raise T088FormalExecutionError("formal shard schema is invalid")
    return _write_new_json(path, shard, label="formal shard")


def write_t088_formal_raw_evidence(
    path: str | Path, evidence: Mapping[str, object]
) -> dict[str, object]:
    """Atomically create the one complete merged raw-evidence artifact."""

    if evidence.get("schema_id") != T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID:
        raise T088FormalExecutionError("formal raw evidence schema is invalid")
    return _write_new_json(path, evidence, label="formal raw evidence")


__all__ = [
    "T088_FORMAL_AUTHORIZATION_SCHEMA_ID",
    "T088_FORMAL_DEFAULT_SHARD_COUNT",
    "T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID",
    "T088_FORMAL_SHARD_ASSIGNMENT",
    "T088_FORMAL_SHARD_SCHEMA_ID",
    "T088FormalExecutionError",
    "execute_t088_authorized_formal_shard",
    "merge_t088_authorized_formal_shards",
    "validate_t088_accepted_canary_evidence",
    "validate_t088_formal_authorization",
    "validate_t088_formal_shard",
    "write_t088_formal_raw_evidence",
    "write_t088_formal_shard",
]
