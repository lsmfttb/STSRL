from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.t105_native_stage_observability import (
    AUDIT_PREDICATES,
    AUDIT_SCHEMA,
    STAGES_IN_EXECUTION_ORDER,
    TRACE_SCHEMA,
    validate_t105_stage_audit,
    validate_t105_stage_trace,
)


def _accepted_trace() -> dict:
    return {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "accepted",
        "first_failed_stage": None,
        "failure_code": None,
        "accepted_root_report_returned": True,
        "particles": [
            {
                "particle_index": 0,
                "stages": {stage: "completed" for stage in STAGES_IN_EXECUTION_ORDER},
                "first_failed_stage": None,
                "failure_code": None,
            }
        ],
    }


def test_stage_trace_accepts_only_structured_success_and_real_order() -> None:
    trace = _accepted_trace()
    assert STAGES_IN_EXECUTION_ORDER.index("search_execution") < (
        STAGES_IN_EXECUTION_ORDER.index("root_occurrence_mapping")
    )
    assert (
        validate_t105_stage_trace(
            trace, expected_status="accepted", particle_start=0, particle_count=1
        )
        == trace
    )


def test_stage_trace_rejects_private_or_exception_payload_fields() -> None:
    for location, key in (
        ("top", "BattleContext"),
        ("row", "exception_text"),
        ("stages", "rng_state"),
    ):
        trace = _accepted_trace()
        target = (
            trace
            if location == "top"
            else trace["particles"][0]
            if location == "row"
            else trace["particles"][0]["stages"]
        )
        target[key] = "private"
        with pytest.raises(ValueError, match="exactly"):
            validate_t105_stage_trace(trace)


def test_stage_trace_requires_later_stages_not_reached_after_failure() -> None:
    trace = _accepted_trace()
    trace.update(
        attempt_status="failed_closed",
        first_failed_stage="root_occurrence_mapping",
        failure_code="root_occurrence_mapping_failed",
        accepted_root_report_returned=False,
    )
    row = trace["particles"][0]
    row.update(
        first_failed_stage="root_occurrence_mapping",
        failure_code="root_occurrence_mapping_failed",
    )
    row["stages"]["root_occurrence_mapping"] = "failed"
    row["stages"]["sanitized_root_report"] = "not_reached"
    validate_t105_stage_trace(trace, expected_status="failed_closed")
    invalid = deepcopy(trace)
    invalid["particles"][0]["stages"]["sanitized_root_report"] = "completed"
    with pytest.raises(ValueError, match="later stage"):
        validate_t105_stage_trace(invalid)


def test_stage_trace_rejects_free_form_failure_classification() -> None:
    trace = _accepted_trace()
    trace.update(
        attempt_status="failed_closed",
        first_failed_stage="search_setup",
        failure_code="exception: private state was X",
        accepted_root_report_returned=False,
    )
    row = trace["particles"][0]
    row.update(first_failed_stage="search_setup", failure_code=trace["failure_code"])
    row["stages"]["search_setup"] = "failed"
    for stage in STAGES_IN_EXECUTION_ORDER[2:]:
        if stage != "search_setup":
            row["stages"][stage] = "not_reached"
    with pytest.raises(ValueError, match="failure metadata"):
        validate_t105_stage_trace(trace)


def test_native_audit_requires_all_seven_fixed_witnesses() -> None:
    audit = {"schema_id": AUDIT_SCHEMA, **dict.fromkeys(AUDIT_PREDICATES, True)}
    assert validate_t105_stage_audit(audit) == audit
    audit["search_execution_failure_attributed"] = False
    with pytest.raises(ValueError, match="predicate failed"):
        validate_t105_stage_audit(audit)
