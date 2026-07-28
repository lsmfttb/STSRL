"""Fail-closed T068 native/Python batching feasibility report builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any


T068_AUDIT_SCHEMA_ID = "t068-native-boundary-callback-dependency-audit-v1"
T068_FEASIBILITY_SCHEMA_ID = "t068-native-boundary-batch-feasibility-v1"
T068_DECISION_SCHEMA_ID = "t068-native-boundary-batch-decision-v1"
T068_GUIDED_ARMS = ("prior_only", "value_only", "prior_value")
T068_NEXT_RECOMMENDATION = "T069-public-node-feature-encoding-projection-feasibility"
T068_NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"


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
    if native_source_audit.get("native_commit") != T068_NATIVE_COMMIT:
        raise ValueError("T068 native source audit must pin the accepted native commit")
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
        "native_commit": T068_NATIVE_COMMIT,
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
            "prototype_measured": False,
            "prototype_evidence": "published separately in the versioned feasibility report",
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


def build_t068_decision_report(
    audit: Mapping[str, Any], feasibility: Mapping[str, Any]
) -> dict[str, Any]:
    if audit.get("schema_id") != T068_AUDIT_SCHEMA_ID:
        raise ValueError("T068 decision requires the current audit schema")
    gate = audit.get("feasibility_gate")
    if not isinstance(gate, Mapping) or gate.get("passed") is not False:
        raise ValueError(
            "T068 infeasibility decision requires a failed feasibility gate"
        )
    if feasibility.get("schema_id") != T068_FEASIBILITY_SCHEMA_ID:
        raise ValueError("T068 decision requires the current feasibility schema")
    prototype = feasibility.get("prototype")
    if not isinstance(prototype, Mapping) or prototype.get("executable") is not True:
        raise ValueError("T068 decision requires executable prototype evidence")
    costs = prototype.get("costs")
    if not isinstance(costs, Mapping):
        raise ValueError("T068 decision requires prototype component costs")
    for arm in T068_GUIDED_ARMS:
        arm_costs = costs.get(arm)
        components = (
            arm_costs.get("component_cost_ms")
            if isinstance(arm_costs, Mapping)
            else None
        )
        if not isinstance(components, Mapping):
            raise ValueError(f"T068 decision lacks {arm} component costs")
        feature = components.get("checkpoint_feature_encoding_ms")
        forward = components.get("policy_value_forward_pass_ms")
        if not all(_finite_nonnegative(value) for value in (feature, forward)):
            raise ValueError(f"T068 decision has invalid {arm} component costs")
        if float(feature) <= float(forward):
            raise ValueError(
                f"T068 recommendation is unsupported by {arm} measured costs"
            )
    return {
        "schema_id": T068_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": audit["code_commit"],
        "native_commit": audit["native_source_audit"].get("native_commit"),
        "input_identities": dict(audit["input_identities"]),
        "decision": "close_native_boundary_batching",
        "production_batch_boundary_implemented": False,
        "calibration_authorized": False,
        "outcome_comparison_authorized": False,
        "promotion_authorized": False,
        "reason": "all guided arms expose only synchronous singleton callbacks; retained T067 attribution identifies public-node feature encoding as the dominant measured cost rather than model forward execution",
        "recommendation": T068_NEXT_RECOMMENDATION,
        "recommendation_count": 1,
        "command_passed": True,
    }


def build_t068_batch_feasibility_report(
    audit: Mapping[str, Any], *, prototype_costs: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Publish the executable unbatched-boundary probe result separately.

    The current native ABI can only measure singleton callback execution.  This
    is still a real prototype result, but it must not be mislabeled as a batch
    speedup or authorize calibration.
    """

    if audit.get("schema_id") != T068_AUDIT_SCHEMA_ID:
        raise ValueError("T068 feasibility requires the current dependency audit")
    gate = audit.get("feasibility_gate")
    if not isinstance(gate, Mapping) or gate.get("passed") is not False:
        raise ValueError("T068 feasibility report requires the failed exact-batch gate")
    costs: dict[str, Any] = {}
    for arm in T068_GUIDED_ARMS:
        cost = prototype_costs.get(arm)
        if not isinstance(cost, Mapping):
            raise ValueError(f"T068 feasibility lacks {arm} prototype cost")
        components = cost.get("component_cost_ms")
        if not isinstance(components, Mapping):
            raise ValueError(f"T068 feasibility lacks {arm} component costs")
        feature = components.get("checkpoint_feature_encoding_ms")
        forward = components.get("policy_value_forward_pass_ms")
        if not all(_finite_nonnegative(value) for value in (feature, forward)):
            raise ValueError(f"T068 feasibility has invalid {arm} component costs")
        _validate_prototype_cost(arm, cost)
        costs[arm] = dict(cost)
    return {
        "schema_id": T068_FEASIBILITY_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": audit["code_commit"],
        "native_commit": audit["native_source_audit"].get("native_commit"),
        "input_identities": dict(audit["input_identities"]),
        "prototype": {
            "kind": "unbatched_synchronous_native_python_callback_probe",
            "executable": True,
            "batch_boundary_implemented": False,
            "batch_size_distribution": {
                arm: audit["arms"][arm]["batch_size_distribution"]
                for arm in T068_GUIDED_ARMS
            },
            "costs": costs,
        },
        "conservative_projection": {
            "both_t067_infeasible_arms_can_reach_wall_ceiling": False,
            "reason": "no exact batch of size >= 2 exists, so no semantics-preserving batch speedup is available",
        },
        "calibration_authorized": False,
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
        if request.get("callback_kind") not in {"policy", "value"}:
            raise ValueError(f"T068 {arm} request {request_id} lacks callback kind")
        outputs = request.get("required_outputs")
        if (
            not isinstance(outputs, Sequence)
            or isinstance(outputs, (str, bytes, bytearray))
            or not outputs
        ):
            raise ValueError(f"T068 {arm} request {request_id} lacks required outputs")
        if not isinstance(request.get("public_input_identity"), str) or not request.get(
            "public_input_identity"
        ):
            raise ValueError(f"T068 {arm} request {request_id} lacks public identity")
        if (
            request.get("public_input_identity_schema_id")
            != "t067-public-node-cache-key-v1"
        ):
            raise ValueError(
                f"T068 {arm} request {request_id} has unknown public identity schema"
            )
        byte_count = request.get("public_input_canonical_byte_count")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count <= 0
        ):
            raise ValueError(
                f"T068 {arm} request {request_id} lacks canonical byte count"
            )
        actions = request.get("ordered_legal_action_identities")
        if (
            not isinstance(actions, Sequence)
            or isinstance(actions, (str, bytes, bytearray))
            or not actions
        ):
            raise ValueError(f"T068 {arm} request {request_id} lacks action identities")
        if not isinstance(request.get("dependency_edges"), Sequence) or not request.get(
            "dependency_edges"
        ):
            raise ValueError(f"T068 {arm} request {request_id} lacks dependency edges")
        if (
            request.get("flush_reason")
            != "native callback requires this response before traversal continues"
        ):
            raise ValueError(
                f"T068 {arm} request {request_id} has unknown flush reason"
            )
        elapsed = request.get("callback_elapsed_ms")
        if not _finite_nonnegative(elapsed):
            raise ValueError(f"T068 {arm} request {request_id} lacks callback timing")
        seen.add(request_id)


def _validate_prototype_cost(arm: str, cost: Mapping[str, Any]) -> None:
    components = cost["component_cost_ms"]
    if not isinstance(components, Mapping) or not components:
        raise ValueError(f"T068 feasibility lacks {arm} component costs")
    if not all(_finite_nonnegative(value) for value in components.values()):
        raise ValueError(f"T068 feasibility has invalid {arm} component costs")
    for name in ("record_wall_clock_seconds", "search_wall_clock_seconds"):
        if not _finite_nonnegative(cost.get(name)):
            raise ValueError(f"T068 feasibility has invalid {arm} {name}")
    for name in (
        "model_call_count",
        "record_count",
        "outer_simulator_steps",
        "native_search_simulator_steps",
    ):
        if not _nonnegative_integer(cost.get(name)):
            raise ValueError(f"T068 feasibility has invalid {arm} {name}")


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
