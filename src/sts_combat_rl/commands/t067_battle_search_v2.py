"""T067 cost-attribution report builders.

The simulator execution remains the T062 fixed-cohort workflow.  This module
wraps its current-schema reports with a versioned T067 attribution surface and
fails closed when any of the four arms or required timing fields are missing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t062_battle_search_v2 import T062_ARM_LABELS


T067_COMPARISON_SCHEMA_ID = "t067-battle-search-v2-cost-comparison-v1"
T067_ATTRIBUTION_SCHEMA_ID = "t067-battle-search-v2-cost-attribution-v1"
T067_ATTRIBUTION_SCHEMA_VERSION = 1
T067_REQUIRED_COST_FIELDS = (
    "native_tree_search_excluding_python_callbacks_ms",
    "node_context_projection_ms",
    "checkpoint_feature_encoding_ms",
    "tensor_construction_ms",
    "policy_value_forward_pass_ms",
    "inference_result_postprocess_ms",
    "python_native_callback_overhead_ms",
    "cache_lookup_ms",
    "cache_lookup_count",
    "cache_hit_count",
    "cache_miss_count",
    "cache_eviction_count",
    "cache_eviction_ms",
    "policy_callback_count",
    "value_callback_count",
    "model_call_count",
)


def build_t067_cost_attribution_report(
    t062_report: Mapping[str, Any],
    *,
    input_identities: Mapping[str, Mapping[str, Any]],
    candidate_budget: Mapping[str, int],
    normalization_family: str,
    worker_count: int,
    shard_count: int,
    record_range: str,
) -> dict[str, Any]:
    """Validate one merged T062-shaped report and add T067 attribution."""

    if t062_report.get("schema_id") != "t062-battle-search-v2-comparison-v1":
        raise ValueError("T067 attribution requires current T062 comparison schema")
    if t062_report.get("report_kind") != "merged_comparison":
        raise ValueError("T067 attribution requires a merged comparison report")
    if worker_count != 16 or shard_count != 16:
        raise ValueError("T067 substantial calibration requires 16 workers and shards")
    if record_range != "0:16":
        raise ValueError("T067 calibration requires record range 0:16")
    arms = t062_report.get("arms")
    if not isinstance(arms, Mapping) or set(arms) != set(T062_ARM_LABELS):
        raise ValueError("T067 report must retain exactly the four T062 arms")
    provenance = t062_report.get("controller_provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != set(T062_ARM_LABELS):
        raise ValueError("T067 report has incomplete arm provenance")

    attribution: dict[str, Any] = {}
    problems: list[str] = []
    for label in T062_ARM_LABELS:
        arm = arms[label]
        if not isinstance(arm, Mapping):
            raise ValueError(f"T067 arm {label} is malformed")
        records = arm.get("records")
        if not isinstance(records, list) or len(records) != 16:
            raise ValueError(f"T067 arm {label} must contain 16 records")
        rows = []
        for row in records:
            if not isinstance(row, Mapping):
                raise ValueError(f"T067 arm {label} has malformed record")
            telemetry = row.get("controller_compute_telemetry")
            if not isinstance(telemetry, Mapping):
                if label != "baseline":
                    raise ValueError(f"T067 guided arm {label} lacks telemetry")
                continue
            cost = telemetry.get("t067_cost_attribution")
            if not isinstance(cost, Mapping):
                if label != "baseline":
                    raise ValueError(f"T067 guided arm {label} lacks cost telemetry")
                continue
            missing = [
                field for field in T067_REQUIRED_COST_FIELDS if field not in cost
            ]
            if missing:
                raise ValueError(f"T067 {label} telemetry missing {missing}")
            rows.append({str(key): _number(value) for key, value in cost.items()})
        attribution[label] = _aggregate_rows(rows, label)
        if any(row.get("problems") for row in records if isinstance(row, Mapping)):
            problems.append(f"{label}: record problems present")

    report = {
        "schema_id": T067_COMPARISON_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "report_kind": "merged_cost_comparison",
        "normalization_family": normalization_family,
        "record_range": record_range,
        "evaluated_record_count": t062_report.get("evaluated_record_count"),
        "cohort_identity": t062_report.get("cohort_identity"),
        "cohort_total_record_count": t062_report.get("cohort_total_record_count"),
        "worker_count": worker_count,
        "shard_count": shard_count,
        "candidate_budget": {
            str(key): int(value) for key, value in candidate_budget.items()
        },
        "input_identities": {
            str(key): dict(value) for key, value in input_identities.items()
        },
        "native_integration": _native_identity(provenance),
        "controller_provenance": {
            str(key): dict(value) for key, value in provenance.items()
        },
        "arm_attribution": attribution,
        "t062_comparison": dict(t062_report),
        "problems": problems,
        "command_passed": not problems and bool(t062_report.get("command_passed")),
    }
    return report


def write_t067_report(path: Path, report: Mapping[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _aggregate_rows(rows: Sequence[Mapping[str, float]], label: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "record_count": len(rows),
        "timings": {},
    }
    for field in T067_REQUIRED_COST_FIELDS:
        values = [float(row.get(field, 0.0)) for row in rows]
        result["timings"][field] = _distribution(values)
    return result


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    finite = [value for value in values if math.isfinite(value) and value >= 0.0]
    if len(finite) != len(values):
        raise ValueError("T067 telemetry contains non-finite or negative values")
    ordered = sorted(finite)
    if not ordered:
        return {
            "count": 0,
            "total": 0.0,
            "minimum": None,
            "maximum": None,
            "mean": None,
            "p50": None,
            "p95": None,
        }
    return {
        "count": len(ordered),
        "total": sum(ordered),
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "mean": sum(ordered) / len(ordered),
        "p50": _quantile(ordered, 0.50),
        "p95": _quantile(ordered, 0.95),
    }


def _quantile(values: Sequence[float], quantile: float) -> float:
    index = min(len(values) - 1, max(0, int(math.ceil(quantile * len(values)) - 1)))
    return float(values[index])


def _native_identity(provenance: Mapping[str, Any]) -> dict[str, Any]:
    values = []
    for label in T062_ARM_LABELS:
        config = provenance[label].get("config", {})
        identity = config.get("native_source_identity")
        if isinstance(identity, Mapping):
            values.append(dict(identity))
    if not values or any(identity != values[0] for identity in values[1:]):
        raise ValueError("T067 arm native source identities differ or are missing")
    return values[0]


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("T067 cost telemetry values must be numeric")
    return float(value)
