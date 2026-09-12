"""Explicitly-authorized, bounded execution seam for the T088 canary.

This module is deliberately *not* a general tournament runner.  It accepts a
single Maintainer authorization record that binds an exact implementation head,
the deterministic five-role canary selection, the accepted T087 cohort, and
the four frozen controller definitions.  Without that record it performs no
restore, controller construction, simulator call, or artifact write.

The actual simulator-facing record runner is injected.  That keeps source
restore and mechanics at the existing authoritative boundaries while this
module owns T088's authorization, all-arm coverage, evidence normalization,
and fail-closed artifact commit.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from sts_combat_rl.commands.t088_classical_combat_tournament import (
    T088_ARM_ORDER,
    T088_NATIVE_IDENTITY,
    build_t088_controller,
    t088_controller_definitions,
)
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T087IncompleteError,
    build_dense_diagnostic_row,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_ARMS,
    T088_TASK_ID,
    T088IncompleteError,
    _binding_identity,
    _finite,
    select_t088_canary_records,
    validate_t088_canary_evidence,
    validate_t088_t087_cohort_binding,
)

T088_CANARY_AUTHORIZATION_SCHEMA_ID = "t088-maintainer-canary-authorization-v1"
T088_CANARY_EVIDENCE_SCHEMA_ID = "t088-canary-evidence-v1"


class T088CanaryExecutionError(T088IncompleteError):
    """The canary is unapproved, incomplete, or unsuitable for retention."""


class T088CanaryRecordRunner(Protocol):
    """Restore, parity-check, and execute exactly one already-bound record."""

    def __call__(
        self, record: Mapping[str, object], arm: str, controller: object
    ) -> Mapping[str, object]: ...


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _controller_provenance(controller: object) -> Mapping[str, object]:
    provenance = getattr(controller, "provenance", None)
    to_dict = getattr(provenance, "to_dict", None)
    value = to_dict() if callable(to_dict) else provenance
    if not isinstance(value, Mapping):
        raise T088CanaryExecutionError("T088 controller provenance is unavailable")
    return dict(value)


def _selected_records(
    selection: Mapping[str, object], cohort: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    selected = selection.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T088CanaryExecutionError("T088 canary selection is malformed")
    by_identity = {str(record["selection_identity"]): dict(record) for record in cohort}
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, Mapping):
            raise T088CanaryExecutionError(
                "T088 canary selection contains a malformed role"
            )
        identity = item.get("selection_identity")
        if not isinstance(identity, str) or identity not in by_identity:
            raise T088CanaryExecutionError(
                "T088 canary selection is outside the bound cohort"
            )
        if identity not in seen:
            seen.add(identity)
            result.append(by_identity[identity])
    if not result or len(result) * len(T088_ARMS) > 20:
        raise T088CanaryExecutionError("T088 canary execution is not bounded")
    return result


def validate_t088_canary_authorization(
    authorization: Mapping[str, object] | None,
    *,
    implementation_head: str,
    selection: Mapping[str, object],
    cohort_binding: Mapping[str, object],
    controller_definitions: Mapping[str, object],
) -> None:
    """Verify the explicit, exact-head Maintainer permission before execution.

    A specification approval, a true-ish flag, or an authorization copied from
    another selection/head is intentionally insufficient.
    """

    if not _is_sha(implementation_head):
        raise T088CanaryExecutionError("T088 implementation head must be a full SHA-1")
    if not isinstance(authorization, Mapping):
        raise T088CanaryExecutionError(
            "explicit T088 Maintainer canary authorization is required"
        )
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        "canary_selection_sha256",
        "t087_cohort_binding",
        "controller_definitions_sha256",
        "maintainer_attestation",
    }
    if set(authorization) != required:
        raise T088CanaryExecutionError(
            "T088 canary authorization has an unexpected shape"
        )
    attestation = authorization.get("maintainer_attestation")
    if (
        authorization.get("schema_id") != T088_CANARY_AUTHORIZATION_SCHEMA_ID
        or authorization.get("task_id") != T088_TASK_ID
        or authorization.get("authorization_kind") != "bounded_canary"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != implementation_head
        or authorization.get("canary_selection_sha256") != _canonical_sha256(selection)
        or authorization.get("t087_cohort_binding") != _binding_identity(cohort_binding)
        or authorization.get("controller_definitions_sha256")
        != _canonical_sha256(controller_definitions)
        or not isinstance(attestation, Mapping)
        or dict(attestation)
        != {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": implementation_head,
        }
    ):
        raise T088CanaryExecutionError(
            "T088 canary authorization is not an exact approved binding"
        )


def _validate_amended_dense_diagnostic(
    row: Mapping[str, object],
    *,
    identity: str,
    cohort: str,
    source_identity: Mapping[str, object],
) -> None:
    """Recompute T087's amended vector without its arm-A-only provenance."""

    diagnostic = row.get("dense_diagnostic")
    if not isinstance(diagnostic, Mapping):
        raise T088CanaryExecutionError(
            "canary row lacks an amended dense diagnostic row"
        )
    if (
        diagnostic.get("selection_identity") != identity
        or diagnostic.get("cohort") != cohort
        or diagnostic.get("outcome") != row.get("outcome")
        or diagnostic.get("source_selection_manifest_identity") != source_identity
        or not isinstance(diagnostic.get("entry"), Mapping)
        or not isinstance(diagnostic.get("terminal"), Mapping)
        or not isinstance(diagnostic.get("action_trace"), Sequence)
        or isinstance(diagnostic.get("action_trace"), (str, bytes))
    ):
        raise T088CanaryExecutionError("canary dense diagnostic binding is malformed")
    try:
        rebuilt = build_dense_diagnostic_row(
            selection_identity=identity,
            cohort=cohort,
            entry=diagnostic["entry"],  # type: ignore[arg-type]
            terminal=diagnostic["terminal"],  # type: ignore[arg-type]
            outcome=str(row["outcome"]),
            action_trace=diagnostic["action_trace"],  # type: ignore[arg-type]
            provenance=(
                diagnostic["provenance"]
                if isinstance(diagnostic.get("provenance"), Mapping)
                else None
            ),
            source_selection_manifest_identity=source_identity,
        )
    except (KeyError, T087IncompleteError, TypeError, ValueError) as exc:
        raise T088CanaryExecutionError(
            "canary dense diagnostic does not recompute"
        ) from exc
    if dict(diagnostic) != rebuilt:
        raise T088CanaryExecutionError(
            "canary dense diagnostic has scalar or raw-evidence drift"
        )


def _validate_execution_row(
    row: Mapping[str, object],
    *,
    record: Mapping[str, object],
    arm: str,
    controller: object,
    cohort_binding: Mapping[str, object],
) -> dict[str, object]:
    """Reject a runner result unless all T088 runtime facts remain bound."""

    identity = record["selection_identity"]
    cohort = record["cohort"]
    if not isinstance(identity, str) or not isinstance(cohort, str):
        raise T088CanaryExecutionError("bound canary record lacks identity/cohort")
    result = dict(row)
    if (
        result.get("arm") != arm
        or result.get("selection_identity") != identity
        or result.get("cohort") != cohort
        or result.get("native_identity") != T088_NATIVE_IDENTITY
        or result.get("controller_provenance") != _controller_provenance(controller)
    ):
        raise T088CanaryExecutionError(
            "canary runner result is substituted or lacks provenance"
        )
    if result.get("formal_execution_authorized") not in (None, False):
        raise T088CanaryExecutionError("canary row must not authorize formal execution")
    source_identity = cohort_binding.get("source_selection_manifest_identity")
    if not isinstance(source_identity, Mapping):
        raise T088CanaryExecutionError("T088 bound source identity is unavailable")
    _validate_amended_dense_diagnostic(
        result,
        identity=identity,
        cohort=cohort,
        source_identity=source_identity,
    )
    counters = result.get("work_counters")
    if not isinstance(counters, Mapping):
        raise T088CanaryExecutionError("canary row work counters are missing")
    for name in (
        "successor_transition_count",
        "action_execution_count",
        "model_calls",
        "root_decision_count",
        "native_simulator_step_count",
        "tree_node_expansion_count",
        "rollout_count",
        "terminal_utility_evaluation_count",
    ):
        value = counters.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise T088CanaryExecutionError(f"canary work counter {name} is invalid")
    if counters["model_calls"] != 0:
        raise T088CanaryExecutionError("T088 canary consumed learned model calls")
    _finite(result.get("wall_clock_time_s"), "wall_clock_time_s")
    return result


def execute_t088_canary(
    *,
    authorization: Mapping[str, object] | None,
    implementation_head: str,
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    runner: T088CanaryRecordRunner,
    selection: Mapping[str, object] | None = None,
    controller_factory: Callable[[str], object] = build_t088_controller,
) -> dict[str, object]:
    """Execute exactly the selected canary rows after exact authorization.

    No partial evidence is returned: a runner failure or any validation failure
    raises before callers receive a serializable evidence document.
    """

    if not callable(runner) or not callable(controller_factory):
        raise T088CanaryExecutionError(
            "T088 canary requires callable runner/controller factory"
        )
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    canonical_selection = select_t088_canary_records(
        cohort, cohort_binding=cohort_binding
    )
    if selection is None:
        raise T088CanaryExecutionError(
            "explicit deterministic canary selection is required"
        )
    if dict(selection) != canonical_selection:
        raise T088CanaryExecutionError(
            "T088 canary selection differs from its bound cohort"
        )
    definitions = t088_controller_definitions()
    validate_t088_canary_authorization(
        authorization,
        implementation_head=implementation_head,
        selection=selection,
        cohort_binding=cohort_binding,
        controller_definitions=definitions,
    )
    records = _selected_records(selection, cohort)
    rows: list[dict[str, object]] = []
    for arm in T088_ARM_ORDER:
        if arm not in T088_ARMS:
            raise T088CanaryExecutionError("T088 controller order drifted")
        controller = controller_factory(arm)
        for record in records:
            try:
                raw = runner(record, arm, controller)
            except Exception as exc:  # noqa: BLE001 - fail closed at execution boundary
                raise T088CanaryExecutionError(
                    "T088 canary runner failed for "
                    f"{record['selection_identity']} arm {arm}"
                ) from exc
            if not isinstance(raw, Mapping):
                raise T088CanaryExecutionError(
                    "T088 canary runner did not return a row object"
                )
            rows.append(
                _validate_execution_row(
                    raw,
                    record=record,
                    arm=arm,
                    controller=controller,
                    cohort_binding=cohort_binding,
                )
            )
    try:
        validate_t088_canary_evidence(selection, rows, cohort_binding=cohort_binding)
    except T088IncompleteError as exc:
        raise T088CanaryExecutionError("T088 canary evidence is incomplete") from exc
    return {
        "schema_id": T088_CANARY_EVIDENCE_SCHEMA_ID,
        "task_id": T088_TASK_ID,
        "formal_execution_authorized": False,
        "implementation_head": implementation_head,
        "authorization": dict(authorization),
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "canary_selection": dict(selection),
        "controller_definitions": definitions,
        "execution_count": len(rows),
        "rows": rows,
    }


def write_t088_canary_evidence(
    path: str | Path, evidence: Mapping[str, object]
) -> dict[str, object]:
    """Atomically create a validated canary artifact without overwriting evidence."""

    if (
        evidence.get("schema_id") != T088_CANARY_EVIDENCE_SCHEMA_ID
        or evidence.get("task_id") != T088_TASK_ID
    ):
        raise T088CanaryExecutionError("T088 canary evidence schema/task is invalid")
    destination = Path(path).resolve()
    if destination.exists():
        raise T088CanaryExecutionError("refusing to overwrite retained canary evidence")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(evidence),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T088CanaryExecutionError(
            "cannot create T088 canary evidence artifact"
        ) from exc
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "schema_id": T088_CANARY_EVIDENCE_SCHEMA_ID,
    }


__all__ = [
    "T088_CANARY_AUTHORIZATION_SCHEMA_ID",
    "T088_CANARY_EVIDENCE_SCHEMA_ID",
    "T088CanaryExecutionError",
    "execute_t088_canary",
    "validate_t088_canary_authorization",
    "write_t088_canary_evidence",
]
