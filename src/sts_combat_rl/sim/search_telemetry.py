"""Versioned search-decision telemetry helpers.

The current native Oracle-like search exposes root statistics but not a full
tree telemetry surface. This module gives controllers and reports one stable
JSON-safe shape while keeping unavailable native fields explicit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SEARCH_DECISION_TELEMETRY_SCHEMA_ID = "search-decision-telemetry-v1"
SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION = 1
SEARCH_TELEMETRY_SUMMARY_SCHEMA_ID = "search-telemetry-summary-v1"
SEARCH_TELEMETRY_SUMMARY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SearchTelemetryMetricSummary:
    """Distribution summary for one numeric telemetry field."""

    count: int
    missing_count: int
    total: float | None
    minimum: float | None
    maximum: float | None
    mean: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "missing_count": self.missing_count,
            "total": self.total,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
        }


@dataclass(frozen=True)
class SearchDecisionTelemetry:
    """Current-schema telemetry for one search-backed decision."""

    information_regime: str
    controller_kind: str
    search_kind: str
    search_backend: dict[str, Any]
    requested_budget: dict[str, Any]
    simulations_requested: int
    root_visits: int
    root_action_count: int
    legal_action_count: int
    eligible_action_count: int
    visited_action_count: int
    visited_eligible_action_count: int
    native_simulator_steps: int | None
    model_calls: int
    wall_clock_time_s: float | None
    root_value_min: float | None
    root_value_max: float | None
    root_value_spread: float | None
    root_decision_gap: float | None
    unsearched_legal_action_count: int | None
    unmapped_search_edge_count: int | None
    unmapped_root_row_count: int
    root_mapping_failure_count: int
    selection_rule: str | None = None
    selected_legal_action_index: int | None = None
    selected_visits: int | None = None
    selected_mean_value: float | None = None
    unavailable_fields: dict[str, str] = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    schema_id: str = SEARCH_DECISION_TELEMETRY_SCHEMA_ID
    schema_version: int = SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "information_regime": self.information_regime,
            "controller_kind": self.controller_kind,
            "search_kind": self.search_kind,
            "search_backend": _json_safe_mapping(self.search_backend),
            "requested_budget": _json_safe_mapping(self.requested_budget),
            "simulations_requested": self.simulations_requested,
            "root_visits": self.root_visits,
            "root_action_count": self.root_action_count,
            "legal_action_count": self.legal_action_count,
            "eligible_action_count": self.eligible_action_count,
            "visited_action_count": self.visited_action_count,
            "visited_eligible_action_count": self.visited_eligible_action_count,
            "native_simulator_steps": self.native_simulator_steps,
            "model_calls": self.model_calls,
            "wall_clock_time_s": self.wall_clock_time_s,
            "root_value_min": self.root_value_min,
            "root_value_max": self.root_value_max,
            "root_value_spread": self.root_value_spread,
            "root_decision_gap": self.root_decision_gap,
            "unsearched_legal_action_count": self.unsearched_legal_action_count,
            "unmapped_search_edge_count": self.unmapped_search_edge_count,
            "unmapped_root_row_count": self.unmapped_root_row_count,
            "root_mapping_failure_count": self.root_mapping_failure_count,
            "selection_rule": self.selection_rule,
            "selected_legal_action_index": self.selected_legal_action_index,
            "selected_visits": self.selected_visits,
            "selected_mean_value": self.selected_mean_value,
            "unavailable_fields": dict(sorted(self.unavailable_fields.items())),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class SearchTelemetrySummary:
    """Deterministic aggregate over current-schema search-decision telemetry."""

    decision_count: int
    information_regime_counts: dict[str, int]
    controller_kind_counts: dict[str, int]
    search_kind_counts: dict[str, int]
    backend_counts: dict[str, int]
    budget_unit_counts: dict[str, int]
    simulations_requested: SearchTelemetryMetricSummary
    root_visits: SearchTelemetryMetricSummary
    root_action_count: SearchTelemetryMetricSummary
    legal_action_count: SearchTelemetryMetricSummary
    native_simulator_steps: SearchTelemetryMetricSummary
    model_calls: SearchTelemetryMetricSummary
    wall_clock_time_s: SearchTelemetryMetricSummary
    root_value_spread: SearchTelemetryMetricSummary
    root_decision_gap: SearchTelemetryMetricSummary
    unsearched_legal_action_count: SearchTelemetryMetricSummary
    unmapped_search_edge_count: SearchTelemetryMetricSummary
    unmapped_root_row_count: SearchTelemetryMetricSummary
    root_mapping_failure_count: SearchTelemetryMetricSummary
    unavailable_field_counts: dict[str, int]
    unavailable_reasons: dict[str, list[str]]
    decision_problem_count: int
    problem_count: int
    schema_id: str = SEARCH_TELEMETRY_SUMMARY_SCHEMA_ID
    schema_version: int = SEARCH_TELEMETRY_SUMMARY_SCHEMA_VERSION
    decision_telemetry_schema_id: str = SEARCH_DECISION_TELEMETRY_SCHEMA_ID
    decision_telemetry_schema_version: int = SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "decision_telemetry_schema_id": self.decision_telemetry_schema_id,
            "decision_telemetry_schema_version": (
                self.decision_telemetry_schema_version
            ),
            "decision_count": self.decision_count,
            "information_regime_counts": dict(self.information_regime_counts),
            "controller_kind_counts": dict(self.controller_kind_counts),
            "search_kind_counts": dict(self.search_kind_counts),
            "backend_counts": dict(self.backend_counts),
            "budget_unit_counts": dict(self.budget_unit_counts),
            "simulations_requested": self.simulations_requested.to_dict(),
            "root_visits": self.root_visits.to_dict(),
            "root_action_count": self.root_action_count.to_dict(),
            "legal_action_count": self.legal_action_count.to_dict(),
            "native_simulator_steps": self.native_simulator_steps.to_dict(),
            "model_calls": self.model_calls.to_dict(),
            "wall_clock_time_s": self.wall_clock_time_s.to_dict(),
            "root_value_spread": self.root_value_spread.to_dict(),
            "root_decision_gap": self.root_decision_gap.to_dict(),
            "unsearched_legal_action_count": (
                self.unsearched_legal_action_count.to_dict()
            ),
            "unmapped_search_edge_count": (self.unmapped_search_edge_count.to_dict()),
            "unmapped_root_row_count": self.unmapped_root_row_count.to_dict(),
            "root_mapping_failure_count": (self.root_mapping_failure_count.to_dict()),
            "unavailable_field_counts": dict(self.unavailable_field_counts),
            "unavailable_reasons": {
                key: list(values)
                for key, values in sorted(self.unavailable_reasons.items())
            },
            "decision_problem_count": self.decision_problem_count,
            "problem_count": self.problem_count,
        }


def search_decision_telemetry_from_dict(
    raw: Mapping[str, Any],
    *,
    label: str = "search decision telemetry",
) -> SearchDecisionTelemetry:
    """Load one current-schema search-decision telemetry record."""

    schema_id = raw.get("schema_id")
    if schema_id != SEARCH_DECISION_TELEMETRY_SCHEMA_ID:
        raise ValueError(
            f"{label} has unsupported schema_id {schema_id!r}; expected "
            f"{SEARCH_DECISION_TELEMETRY_SCHEMA_ID!r}"
        )
    schema_version = raw.get("schema_version")
    if schema_version != SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION:
        raise ValueError(
            f"{label} has unsupported schema_version {schema_version!r}; expected "
            f"{SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION}"
        )
    return SearchDecisionTelemetry(
        information_regime=_required_string(
            raw.get("information_regime"), f"{label} information_regime"
        ),
        controller_kind=_required_string(
            raw.get("controller_kind"), f"{label} controller_kind"
        ),
        search_kind=_required_string(raw.get("search_kind"), f"{label} search_kind"),
        search_backend=_require_mapping(
            raw.get("search_backend"), f"{label} search_backend"
        ),
        requested_budget=_require_mapping(
            raw.get("requested_budget"), f"{label} requested_budget"
        ),
        simulations_requested=_non_negative_int(
            raw.get("simulations_requested"), f"{label} simulations_requested"
        ),
        root_visits=_non_negative_int(raw.get("root_visits"), f"{label} root_visits"),
        root_action_count=_non_negative_int(
            raw.get("root_action_count"), f"{label} root_action_count"
        ),
        legal_action_count=_non_negative_int(
            raw.get("legal_action_count"), f"{label} legal_action_count"
        ),
        eligible_action_count=_non_negative_int(
            raw.get("eligible_action_count"), f"{label} eligible_action_count"
        ),
        visited_action_count=_non_negative_int(
            raw.get("visited_action_count"), f"{label} visited_action_count"
        ),
        visited_eligible_action_count=_non_negative_int(
            raw.get("visited_eligible_action_count"),
            f"{label} visited_eligible_action_count",
        ),
        native_simulator_steps=_optional_non_negative_int(
            raw.get("native_simulator_steps"), f"{label} native_simulator_steps"
        ),
        model_calls=_non_negative_int(raw.get("model_calls"), f"{label} model_calls"),
        wall_clock_time_s=_optional_non_negative_float(
            raw.get("wall_clock_time_s"), f"{label} wall_clock_time_s"
        ),
        root_value_min=_optional_float(
            raw.get("root_value_min"), f"{label} root_value_min"
        ),
        root_value_max=_optional_float(
            raw.get("root_value_max"), f"{label} root_value_max"
        ),
        root_value_spread=_optional_non_negative_float(
            raw.get("root_value_spread"), f"{label} root_value_spread"
        ),
        root_decision_gap=_optional_non_negative_float(
            raw.get("root_decision_gap"), f"{label} root_decision_gap"
        ),
        unsearched_legal_action_count=_optional_non_negative_int(
            raw.get("unsearched_legal_action_count"),
            f"{label} unsearched_legal_action_count",
        ),
        unmapped_search_edge_count=_optional_non_negative_int(
            raw.get("unmapped_search_edge_count"),
            f"{label} unmapped_search_edge_count",
        ),
        unmapped_root_row_count=_non_negative_int(
            raw.get("unmapped_root_row_count"), f"{label} unmapped_root_row_count"
        ),
        root_mapping_failure_count=_non_negative_int(
            raw.get("root_mapping_failure_count"),
            f"{label} root_mapping_failure_count",
        ),
        selection_rule=_optional_string(raw.get("selection_rule")),
        selected_legal_action_index=_optional_non_negative_int(
            raw.get("selected_legal_action_index"),
            f"{label} selected_legal_action_index",
        ),
        selected_visits=_optional_non_negative_int(
            raw.get("selected_visits"), f"{label} selected_visits"
        ),
        selected_mean_value=_optional_float(
            raw.get("selected_mean_value"), f"{label} selected_mean_value"
        ),
        unavailable_fields=_require_string_mapping(
            raw.get("unavailable_fields", {}), f"{label} unavailable_fields"
        ),
        problems=tuple(_require_string_list(raw.get("problems", []), label)),
    )


def iter_search_decision_telemetry_dicts(value: Any) -> list[dict[str, Any]]:
    """Return current-schema telemetry dicts found in a nested metadata payload."""

    found: list[dict[str, Any]] = []
    _collect_search_decision_telemetry_dicts(value, found)
    return found


def summarize_search_decision_telemetry_dicts(
    records: Sequence[Mapping[str, Any]],
) -> SearchTelemetrySummary:
    """Load and summarize current-schema search-decision telemetry dicts."""

    telemetry = [
        search_decision_telemetry_from_dict(record, label=f"telemetry {index}")
        for index, record in enumerate(records)
    ]
    return summarize_search_decision_telemetry(telemetry)


def summarize_search_decision_telemetry(
    records: Sequence[SearchDecisionTelemetry],
) -> SearchTelemetrySummary:
    """Aggregate current-schema search-decision telemetry records."""

    regimes = Counter(record.information_regime for record in records)
    controller_kinds = Counter(record.controller_kind for record in records)
    search_kinds = Counter(record.search_kind for record in records)
    backends = Counter(_backend_label(record.search_backend) for record in records)
    budget_units = Counter(
        str(record.requested_budget.get("unit", "(missing)")) for record in records
    )
    unavailable_fields: Counter[str] = Counter()
    unavailable_reasons: dict[str, set[str]] = {}
    decision_problem_count = 0
    problem_count = 0
    for record in records:
        if record.problems:
            decision_problem_count += 1
            problem_count += len(record.problems)
        for field_name, reason in record.unavailable_fields.items():
            unavailable_fields[field_name] += 1
            unavailable_reasons.setdefault(field_name, set()).add(reason)

    return SearchTelemetrySummary(
        decision_count=len(records),
        information_regime_counts=_counter_dict(regimes),
        controller_kind_counts=_counter_dict(controller_kinds),
        search_kind_counts=_counter_dict(search_kinds),
        backend_counts=_counter_dict(backends),
        budget_unit_counts=_counter_dict(budget_units),
        simulations_requested=_metric(
            [record.simulations_requested for record in records]
        ),
        root_visits=_metric([record.root_visits for record in records]),
        root_action_count=_metric([record.root_action_count for record in records]),
        legal_action_count=_metric([record.legal_action_count for record in records]),
        native_simulator_steps=_metric(
            [record.native_simulator_steps for record in records]
        ),
        model_calls=_metric([record.model_calls for record in records]),
        wall_clock_time_s=_metric([record.wall_clock_time_s for record in records]),
        root_value_spread=_metric([record.root_value_spread for record in records]),
        root_decision_gap=_metric([record.root_decision_gap for record in records]),
        unsearched_legal_action_count=_metric(
            [record.unsearched_legal_action_count for record in records]
        ),
        unmapped_search_edge_count=_metric(
            [record.unmapped_search_edge_count for record in records]
        ),
        unmapped_root_row_count=_metric(
            [record.unmapped_root_row_count for record in records]
        ),
        root_mapping_failure_count=_metric(
            [record.root_mapping_failure_count for record in records]
        ),
        unavailable_field_counts=_counter_dict(unavailable_fields),
        unavailable_reasons={
            key: sorted(values) for key, values in sorted(unavailable_reasons.items())
        },
        decision_problem_count=decision_problem_count,
        problem_count=problem_count,
    )


def format_search_telemetry_summary(
    summary: SearchTelemetrySummary,
    *,
    title: str = "Search decision telemetry",
) -> str:
    """Format an aggregate search telemetry summary deterministically."""

    lines = [
        title,
        (
            "schema: "
            f"{summary.decision_telemetry_schema_id} "
            f"v{summary.decision_telemetry_schema_version}"
        ),
        f"decisions: {summary.decision_count}",
    ]
    _append_counter(lines, "information regimes", summary.information_regime_counts)
    _append_counter(lines, "controller kinds", summary.controller_kind_counts)
    _append_counter(lines, "search kinds", summary.search_kind_counts)
    _append_counter(lines, "search backends", summary.backend_counts)
    _append_counter(lines, "budget units", summary.budget_unit_counts)
    lines.extend(
        [
            _format_metric("simulations requested", summary.simulations_requested),
            _format_metric("root visits", summary.root_visits),
            _format_metric("root actions", summary.root_action_count),
            _format_metric("legal actions", summary.legal_action_count),
            _format_metric("native simulator steps", summary.native_simulator_steps),
            _format_metric("model calls", summary.model_calls),
            _format_metric(
                "wall-clock seconds", summary.wall_clock_time_s, precision=6
            ),
            _format_metric("root value spread", summary.root_value_spread, precision=6),
            _format_metric("root decision gap", summary.root_decision_gap, precision=6),
            _format_metric(
                "unsearched legal actions",
                summary.unsearched_legal_action_count,
            ),
            _format_metric("unmapped search edges", summary.unmapped_search_edge_count),
            _format_metric("unmapped root rows", summary.unmapped_root_row_count),
            _format_metric("root mapping failures", summary.root_mapping_failure_count),
            f"problem decisions: {summary.decision_problem_count}",
            f"problems: {summary.problem_count}",
        ]
    )
    _append_counter(lines, "unavailable fields", summary.unavailable_field_counts)
    if summary.unavailable_reasons:
        lines.append("unavailable reasons:")
        for field_name, reasons in sorted(summary.unavailable_reasons.items()):
            lines.append(f"  {field_name}: {'; '.join(reasons)}")
    return "\n".join(lines)


def _collect_search_decision_telemetry_dicts(
    value: Any,
    found: list[dict[str, Any]],
) -> None:
    if isinstance(value, Mapping):
        if value.get("schema_id") == SEARCH_DECISION_TELEMETRY_SCHEMA_ID:
            found.append({str(key): item for key, item in value.items()})
            return
        for key in (
            "search_decision_telemetry",
            "search_decision_telemetry_records",
            "decision_telemetry",
        ):
            if key in value:
                _collect_search_decision_telemetry_dicts(value[key], found)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _collect_search_decision_telemetry_dicts(item, found)


def _metric(values: Sequence[int | float | None]) -> SearchTelemetryMetricSummary:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    missing_count = len(values) - len(numeric)
    if not numeric:
        return SearchTelemetryMetricSummary(
            count=0,
            missing_count=missing_count,
            total=None,
            minimum=None,
            maximum=None,
            mean=None,
        )
    total = sum(numeric)
    return SearchTelemetryMetricSummary(
        count=len(numeric),
        missing_count=missing_count,
        total=total,
        minimum=min(numeric),
        maximum=max(numeric),
        mean=total / len(numeric),
    )


def _backend_label(value: Mapping[str, Any]) -> str:
    native_api = value.get("native_api")
    if isinstance(native_api, str) and native_api:
        return native_api
    backend = value.get("backend")
    if isinstance(backend, str) and backend:
        return backend
    return "(missing)"


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter)}


def _append_counter(lines: list[str], label: str, values: Mapping[str, int]) -> None:
    lines.append(f"{label}:")
    if not values:
        lines.append("  (none)")
        return
    for key, value in sorted(values.items()):
        lines.append(f"  {key}: {value}")


def _format_metric(
    label: str,
    metric: SearchTelemetryMetricSummary,
    *,
    precision: int = 0,
) -> str:
    if metric.count == 0:
        suffix = f"; missing={metric.missing_count}" if metric.missing_count else ""
        return f"{label}: (unavailable{suffix})"
    parts = [
        f"total={_format_number(metric.total, precision=precision)}",
        f"min={_format_number(metric.minimum, precision=precision)}",
        f"max={_format_number(metric.maximum, precision=precision)}",
        f"mean={_format_number(metric.mean, precision=precision)}",
    ]
    if metric.missing_count:
        parts.append(f"missing={metric.missing_count}")
    return f"{label}: " + ", ".join(parts)


def _format_number(value: float | None, *, precision: int) -> str:
    if value is None:
        return "(missing)"
    if precision:
        return f"{value:.{precision}f}"
    if value.is_integer():
        return str(int(value))
    return f"{value:.3f}"


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"search telemetry value is not JSON-safe: {type(value).__name__}")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
    raw = _require_mapping(value, label)
    result: dict[str, str] = {}
    for key, item in raw.items():
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label} values must be non-empty strings")
        result[str(key)] = item
    return result


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional string telemetry field must be a string or null")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} problems must be a string list")
    return list(value)


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, label)


def _optional_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric or null")
    return float(value)


def _optional_non_negative_float(value: Any, label: str) -> float | None:
    converted = _optional_float(value, label)
    if converted is not None and converted < 0.0:
        raise ValueError(f"{label} must be non-negative or null")
    return converted
