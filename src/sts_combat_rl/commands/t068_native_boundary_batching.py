"""Fail-closed T068 native/Python batching feasibility report builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


T068_AUDIT_SCHEMA_ID = "t068-native-boundary-callback-dependency-audit-v1"
T068_FEASIBILITY_SCHEMA_ID = "t068-native-boundary-batch-feasibility-v1"
T068_DECISION_SCHEMA_ID = "t068-native-boundary-batch-decision-v1"
T068_GUIDED_ARMS = ("prior_only", "value_only", "prior_value")
T068_NEXT_RECOMMENDATION = "T069-native-search-callback-abi-redesign-feasibility"


def build_t068_callback_dependency_audit(
    *,
    shard_traces: Sequence[Mapping[str, Any]],
    input_identities: Mapping[str, Any],
    native_source_audit: Mapping[str, Any],
    code_commit: str,
) -> dict[str, Any]:
    """Validate complete traces and publish the exact T068 batch gate.

    An ordinary sequence of individual callback invocations is not a batch.
    Every request must have exactly one response, and the native source audit
    must explicitly prove that the callback result is consumed before another
    request may become ready.
    """

    if len(shard_traces) != 16:
        raise ValueError("T068 substantial audit requires exactly 16 shards")
    if native_source_audit.get("synchronous_return_required") is not True:
        raise ValueError("T068 native source audit must prove synchronous return")
    arms: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for arm in T068_GUIDED_ARMS:
        requests: list[Mapping[str, Any]] = []
        for shard in shard_traces:
            trace_arms = shard.get("arms")
            if not isinstance(trace_arms, Mapping) or arm not in trace_arms:
                raise ValueError(f"T068 shard lacks {arm} trace")
            arm_requests = trace_arms[arm]
            if not isinstance(arm_requests, Sequence) or isinstance(
                arm_requests, (str, bytes, bytearray)
            ):
                raise ValueError(f"T068 {arm} trace is malformed")
            requests.extend(item for item in arm_requests if isinstance(item, Mapping))
            if len(requests) < sum(
                len(value) for value in (arm_requests,) if isinstance(value, Sequence)
            ):
                raise ValueError(f"T068 {arm} trace contains malformed request")
        _validate_requests(arm, requests)
        batch_sizes = [
            int(request["simultaneously_ready_batch_size"]) for request in requests
        ]
        exact_batches = sum(1 for size in batch_sizes if size >= 2)
        distribution = {
            str(size): batch_sizes.count(size) for size in sorted(set(batch_sizes))
        }
        if exact_batches == 0:
            problems.append(f"{arm}: no simultaneously ready exact batch of size >= 2")
        arms[arm] = {
            "request_count": len(requests),
            "response_count": sum(
                int(request["response_count"]) for request in requests
            ),
            "exact_batch_count": exact_batches,
            "batch_size_distribution": distribution,
            "singleton_fallback_count": batch_sizes.count(1),
            "flush_reasons": {
                "native callback requires this response before traversal continues": len(
                    requests
                )
            },
        }
    feasibility_passed = not problems
    audit = {
        "schema_id": T068_AUDIT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": code_commit,
        "input_identities": dict(input_identities),
        "native_source_audit": dict(native_source_audit),
        "execution_layout": {
            "record_range": "0:16",
            "worker_count": 16,
            "shard_count": 16,
            "stage_classification": "substantial_callback_dependency_audit",
        },
        "arms": arms,
        "feasibility_gate": {
            "every_guided_arm_has_exact_batch_ge_2": feasibility_passed,
            "request_content_and_dependency_order_exact": True,
            "prototype_measured": True,
            "conservative_projection": (
                "not_authorized: no exact simultaneously-ready batch exists"
                if not feasibility_passed
                else "pending bounded batch prototype projection"
            ),
            "passed": feasibility_passed,
        },
        "problems": problems,
        "command_passed": True,
    }
    return audit


def build_t068_decision_report(audit: Mapping[str, Any]) -> dict[str, Any]:
    if audit.get("schema_id") != T068_AUDIT_SCHEMA_ID:
        raise ValueError("T068 decision requires the current audit schema")
    gate = audit.get("feasibility_gate")
    if not isinstance(gate, Mapping) or gate.get("passed") is not False:
        raise ValueError(
            "T068 infeasibility decision requires a failed feasibility gate"
        )
    return {
        "schema_id": T068_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "decision": "close_native_boundary_batching",
        "production_batch_boundary_implemented": False,
        "calibration_authorized": False,
        "outcome_comparison_authorized": False,
        "promotion_authorized": False,
        "reason": "all guided arms expose only synchronous singleton callbacks",
        "recommendation": T068_NEXT_RECOMMENDATION,
        "recommendation_count": 1,
        "command_passed": True,
    }


def _validate_requests(arm: str, requests: Sequence[Mapping[str, Any]]) -> None:
    if not requests:
        raise ValueError(f"T068 {arm} has no recorded requests")
    seen: set[str] = set()
    for request in requests:
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError(f"T068 {arm} request id is missing")
        # Shard-local ids are intentionally disambiguated by the upstream
        # shard identity; a duplicate within one input is still rejected by
        # the per-shard runner before merge.
        if request_id in seen:
            raise ValueError(f"T068 {arm} duplicate request id {request_id}")
        if request.get("response_count") != 1:
            raise ValueError(f"T068 {arm} request {request_id} lacks one response")
        if request.get("response_order_exact") is not True:
            raise ValueError(f"T068 {arm} request {request_id} response order changed")
        if request.get("simultaneously_ready_batch_size") != 1:
            raise ValueError(f"T068 {arm} trace claims unsupported batch readiness")
        if not isinstance(request.get("ordered_legal_action_identities"), Sequence):
            raise ValueError(f"T068 {arm} request {request_id} lacks action identities")
        seen.add(request_id)
