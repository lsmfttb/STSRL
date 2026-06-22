"""Public run-context artifact validation and comparison helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


PUBLIC_CONTEXT_AVAILABLE = "available"
PUBLIC_CONTEXT_LEGACY_UNAVAILABLE = "legacy_unavailable"
PUBLIC_CONTEXT_STATUS_VALUES = frozenset(
    {PUBLIC_CONTEXT_AVAILABLE, PUBLIC_CONTEXT_LEGACY_UNAVAILABLE}
)
PUBLIC_CONTEXT_LEGACY_LOSS = (
    "legacy artifact omitted sanitized public run context/history; missing "
    "history, map, Boss, resource provenance, and candidate-action context "
    "cannot be reconstructed"
)


def sanitize_public_context_artifact(value: object, *, label: str) -> dict[str, Any]:
    """Return a sanitized T015 public run context or raise a named failure."""

    from sts_combat_rl.sim.public_run_context import (
        PUBLIC_RUN_CONTEXT_SCHEMA_ID,
        PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
        public_history_problems,
        sanitize_public_run_context,
    )

    if not isinstance(value, Mapping):
        raise ValueError(f"{label} public_run_context must be an object")
    context = sanitize_public_run_context(value)
    if context.get("schema_id") != PUBLIC_RUN_CONTEXT_SCHEMA_ID:
        raise ValueError(f"{label} public_run_context schema_id is unsupported")
    if context.get("schema_version") != PUBLIC_RUN_CONTEXT_SCHEMA_VERSION:
        raise ValueError(f"{label} public_run_context schema_version is unsupported")
    missing_fields = context.get("missing_fields")
    if not isinstance(missing_fields, list) or not all(
        isinstance(path, str) for path in missing_fields
    ):
        raise ValueError(f"{label} public_run_context missing_fields must be strings")
    history = context.get("history")
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        raise ValueError(f"{label} public_run_context history must be a list")
    history_problems = public_history_problems(
        [entry for entry in history if isinstance(entry, Mapping)]
    )
    if any(not isinstance(entry, Mapping) for entry in history):
        raise ValueError(f"{label} public_run_context history entries must be objects")
    if history_problems:
        raise ValueError(
            f"{label} public_run_context history invalid: "
            + "; ".join(history_problems)
        )
    return context


def public_context_artifact_problems(
    *,
    status: object,
    context: object,
    label: str,
    require_available: bool = False,
    require_candidate_actions: bool = False,
) -> list[str]:
    """Validate an artifact's context object or explicit legacy loss marker."""

    problems: list[str] = []
    if status not in PUBLIC_CONTEXT_STATUS_VALUES:
        problems.append(
            f"{label}: public_context_status must be one of "
            f"{sorted(PUBLIC_CONTEXT_STATUS_VALUES)!r}"
        )
        return problems

    if status == PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
        if require_available:
            problems.append(f"{label}: public run context is a legacy loss")
        if context not in ({}, None):
            problems.append(f"{label}: legacy public context loss must not carry data")
        return problems

    try:
        sanitized = sanitize_public_context_artifact(context, label=label)
    except ValueError as exc:
        problems.append(str(exc))
        return problems

    if require_candidate_actions:
        candidates = _mapping(sanitized.get("candidate_actions"))
        if candidates.get("availability") != PUBLIC_CONTEXT_AVAILABLE:
            problems.append(f"{label}: public context candidate_actions unavailable")
        items = candidates.get("items")
        if not isinstance(items, list):
            problems.append(f"{label}: public context candidate_actions.items missing")
    return problems


def public_context_missing_paths(context: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the explicit missing paths retained by a sanitized context."""

    missing = context.get("missing_fields")
    if not isinstance(missing, list):
        return ()
    return tuple(str(path) for path in missing)


def public_context_mismatches(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    label: str,
    limit: int = 20,
) -> list[str]:
    """Return named exact mismatches between two sanitized public contexts."""

    mismatches: list[str] = []
    _append_mismatches(expected, actual, "$", mismatches, limit)
    return [f"{label}: {mismatch}" for mismatch in mismatches]


def public_context_digestable(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy suitable for artifact identity hashing."""

    return _json_safe_mapping(value)


def _append_mismatches(
    expected: object,
    actual: object,
    path: str,
    mismatches: list[str],
    limit: int,
) -> None:
    if len(mismatches) >= limit:
        return
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            mismatches.append(f"{path}.{key}: missing from replayed context")
            if len(mismatches) >= limit:
                return
        for key in sorted(actual_keys - expected_keys):
            mismatches.append(f"{path}.{key}: unexpected in replayed context")
            if len(mismatches) >= limit:
                return
        for key in sorted(expected_keys & actual_keys):
            _append_mismatches(
                expected[key],
                actual[key],
                f"{path}.{key}",
                mismatches,
                limit,
            )
            if len(mismatches) >= limit:
                return
        return
    if _is_sequence(expected) and _is_sequence(actual):
        expected_items = list(expected)
        actual_items = list(actual)
        if len(expected_items) != len(actual_items):
            mismatches.append(
                f"{path}: length {len(actual_items)} != expected {len(expected_items)}"
            )
            return
        for index, (left, right) in enumerate(zip(expected_items, actual_items)):
            _append_mismatches(left, right, f"{path}[{index}]", mismatches, limit)
            if len(mismatches) >= limit:
                return
        return
    if expected != actual:
        mismatches.append(f"{path}: {actual!r} != expected {expected!r}")


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if _is_sequence(value):
        return [_json_safe_value(item) for item in value]
    raise ValueError(
        f"public context artifact value is not JSON-safe: {type(value).__name__}"
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))
