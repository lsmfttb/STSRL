"""Validate the safe, structured native STSRL-007 stage surface.

The native simulator owns every stage transition and its deterministic audit.
This module checks only the returned control-flow metadata; it never inspects
exception text or reconstructs hidden simulator state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    validate_t107_mapping_diagnostic,
)

TRACE_SCHEMA = "native-particle-search-stage-observability-v1"
AUDIT_SCHEMA = "native-stsr007-particle-search-stage-audit-v1"
STAGES_IN_EXECUTION_ORDER = (
    "hidden_future_sample_construction",
    "public_fidelity_validation",
    "search_setup",
    "search_execution",
    "root_occurrence_mapping",
    "sanitized_root_report",
)
STAGE_STATUSES = frozenset({"not_reached", "entered", "completed", "failed"})
FAILURE_CODES = frozenset(
    {
        "anchor_unsupported_fidelity",
        "native_exception",
        "native_stage_exception",
        "public_fidelity_failed",
        "request_or_preflight_failure",
        "root_occurrence_mapping_failed",
    }
)
AUDIT_PREDICATES = (
    "success_all_stages_completed",
    "success_output_sanitized",
    "early_public_failure_stops_later_stages",
    "mapping_failure_attributed",
    "search_setup_failure_attributed",
    "search_execution_failure_attributed",
    "sanitized_report_failure_attributed",
)


def _object(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly {sorted(keys)}")
    return value


def validate_t105_stage_trace(
    value: object,
    *,
    expected_status: str | None = None,
    particle_start: int | None = None,
    particle_count: int | None = None,
) -> Mapping[str, Any]:
    """Reject malformed, unsafe, or internally inconsistent native telemetry."""

    trace = _object(
        value,
        {
            "schema_id",
            "attempt_status",
            "first_failed_stage",
            "failure_code",
            "accepted_root_report_returned",
            "particles",
        },
        "STSRL-007 trace",
    )
    if trace["schema_id"] != TRACE_SCHEMA:
        raise ValueError("STSRL-007 trace schema mismatch")
    status = trace["attempt_status"]
    if status not in {"not_attempted", "accepted", "failed_closed"}:
        raise ValueError("STSRL-007 attempt status is invalid")
    if expected_status is not None and status != expected_status:
        raise ValueError("STSRL-007 attempt status disagrees with bridge outcome")
    returned = trace["accepted_root_report_returned"]
    if not isinstance(returned, bool) or returned != (status == "accepted"):
        raise ValueError("STSRL-007 accepted-root-report flag is inconsistent")
    rows = trace["particles"]
    if not isinstance(rows, list):
        raise TypeError("STSRL-007 particle rows must be a list")
    if status == "not_attempted" and rows:
        raise ValueError("STSRL-007 not-attempted trace has particle rows")
    if particle_count is not None and len(rows) != particle_count:
        raise ValueError("STSRL-007 particle row count disagrees with bridge")

    failed_rows = []
    for ordinal, value_row in enumerate(rows):
        row_fields = {"particle_index", "stages", "first_failed_stage", "failure_code"}
        additive_mapping_field = "root_occurrence_mapping_diagnostic"
        if not isinstance(value_row, Mapping) or frozenset(value_row) not in {
            frozenset(row_fields),
            frozenset(row_fields | {additive_mapping_field}),
        }:
            raise ValueError(
                "STSRL-007 particle row must contain exactly the legacy fields "
                "and the optional STSRL-008 mapping diagnostic"
            )
        row = value_row
        index = row["particle_index"]
        if index is not None and (
            isinstance(index, bool) or not isinstance(index, int) or index < 0
        ):
            raise ValueError("STSRL-007 particle index is invalid")
        if particle_start is not None and index != particle_start + ordinal:
            raise ValueError("STSRL-007 particle index disagrees with bridge")
        stages = _object(
            row["stages"], set(STAGES_IN_EXECUTION_ORDER), "STSRL-007 stages"
        )
        if any(stage_status not in STAGE_STATUSES for stage_status in stages.values()):
            raise ValueError("STSRL-007 stage status is invalid")
        if additive_mapping_field in row:
            validate_t107_mapping_diagnostic(
                row[additive_mapping_field],
                mapping_stage_status=stages["root_occurrence_mapping"],
            )
        failed_stage = row["first_failed_stage"]
        code = row["failure_code"]
        failed = [
            name for name in STAGES_IN_EXECUTION_ORDER if stages[name] == "failed"
        ]
        if failed_stage is None:
            if failed or code is not None:
                raise ValueError("STSRL-007 row has unclassified failure")
        else:
            if failed != [failed_stage] or code not in FAILURE_CODES:
                raise ValueError("STSRL-007 row failure metadata is inconsistent")
            failed_rows.append(row)
            failed_ordinal = STAGES_IN_EXECUTION_ORDER.index(failed_stage)
            if any(
                stages[name] != "not_reached"
                for name in STAGES_IN_EXECUTION_ORDER[failed_ordinal + 1 :]
            ):
                raise ValueError("STSRL-007 later stage was reached after failure")
        if status == "accepted" and any(
            stages[name] != "completed" for name in STAGES_IN_EXECUTION_ORDER
        ):
            raise ValueError("STSRL-007 accepted particle did not complete all stages")

    first_failed = trace["first_failed_stage"]
    failure_code = trace["failure_code"]
    if status in {"accepted", "not_attempted"}:
        if first_failed is not None or failure_code is not None or failed_rows:
            raise ValueError("STSRL-007 nonfailed attempt has failure metadata")
    elif failed_rows:
        if (
            first_failed != failed_rows[0]["first_failed_stage"]
            or failure_code != failed_rows[0]["failure_code"]
        ):
            raise ValueError("STSRL-007 top-level failure disagrees with particle")
    elif first_failed is not None or failure_code != "request_or_preflight_failure":
        raise ValueError("STSRL-007 preflight failure metadata is invalid")
    return trace


def validate_t105_stage_audit(value: object) -> Mapping[str, Any]:
    """Require every native-owned deterministic stage-boundary witness."""

    audit = _object(value, {"schema_id", *AUDIT_PREDICATES}, "STSRL-007 audit")
    if audit["schema_id"] != AUDIT_SCHEMA:
        raise ValueError("STSRL-007 audit schema mismatch")
    if any(audit[name] is not True for name in AUDIT_PREDICATES):
        raise ValueError("STSRL-007 native audit predicate failed")
    return audit
