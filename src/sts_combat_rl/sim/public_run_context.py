"""Sanitized public run-context and ordered history contract.

This module is the T015 boundary between the raw T014 native projection and
normal-public controller inputs.  It accepts only declared native projection
fields, carries unavailable/unsupported facts explicitly, and emits JSON-safe
public context dictionaries for in-memory use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.features import build_public_tactical_actions
from sts_combat_rl.sim.native_public_projection import (
    RESOURCE_FIELD_NAMES,
    NativeProjectionField,
    NativePublicProjection,
    parse_native_public_projection,
)


PUBLIC_RUN_CONTEXT_SCHEMA_ID = "public-run-context-v1"
PUBLIC_RUN_CONTEXT_SCHEMA_VERSION = 1
PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_ID = "public-run-history-entry-v1"
PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_VERSION = 1

PUBLIC_RUN_CONTEXT_GAPS = (
    "visible_act_boss",
    "visible_map_graph",
    "current_map_node",
    "immediately_legal_routes",
    "screen_payload",
    "persistent_resources.deck",
    "persistent_resources.relics",
    "persistent_resources.potion_identities",
    "persistent_resources.keys",
)

_FORBIDDEN_KEY_FRAGMENTS = (
    "hidden_rng",
    "rng_state",
    "random_state",
    "draw_order",
    "draw_pile_order",
    "unrevealed",
    "future_encounter",
    "future_encounters",
    "second_boss",
    "act3_second_boss",
    "checkpoint",
    "native_object",
    "native_payload",
    "simulator_state",
)


def read_native_public_projection(
    adapter: object,
    snapshot: SimulatorSnapshot,
) -> NativePublicProjection | None:
    """Read and validate an optional T014 native projection from an adapter.

    Adapters that do not expose the optional projection capability produce an
    explicit unavailable context instead of failing a controlled run.  Malformed
    or schema-nonconforming projections still fail closed.
    """

    public_projection = getattr(adapter, "public_projection", None)
    if not callable(public_projection):
        return None
    try:
        projection = public_projection(snapshot)
    except RuntimeError as exc:
        message = str(exc)
        if "public_projection" in message and "does not expose" in message:
            return None
        raise
    if isinstance(projection, NativePublicProjection):
        return projection
    if isinstance(projection, Mapping):
        return parse_native_public_projection(projection)
    raise ValueError(
        "adapter public_projection must return NativePublicProjection or raw mapping"
    )


def build_public_run_context(
    raw_snapshot: object,
    actions: Sequence[SimulatorAction],
    *,
    projection: NativePublicProjection | None,
    history: Sequence[Mapping[str, Any]] = (),
    include_candidates: bool = True,
) -> dict[str, Any]:
    """Build one sanitized public context for a controller decision."""

    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    if projection is not None and include_candidates:
        _validate_projection_candidate_parity(projection, actions)

    context: dict[str, Any] = {
        "schema_id": PUBLIC_RUN_CONTEXT_SCHEMA_ID,
        "schema_version": PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
        "source_projection_schema_id": (
            projection.schema_id if projection is not None else None
        ),
        "projection_status": "available" if projection is not None else "unavailable",
        "current": {
            "screen": _screen_field(raw, projection),
            "location": {
                "act": _raw_public_field(raw, "act"),
                "floor": _raw_public_field(raw, "floor_num", "floor"),
                "room_type": _raw_public_field(raw, "room_type", "screen_state"),
                "map_node": _projection_declared_field(
                    projection,
                    "current_map_node",
                    fallback_reason="native current map node unavailable",
                ),
            },
            "result": {
                "outcome": _raw_public_field(raw, "outcome"),
                "battle_outcome": _raw_public_field(
                    raw,
                    "completed_battle_outcome",
                    "battle_outcome",
                ),
            },
        },
        "visible_act_boss": _projection_declared_field(
            projection,
            "visible_act_boss",
            fallback_reason="native visible act boss unavailable",
        ),
        "map": {
            "visible_map_graph": _projection_declared_field(
                projection,
                "visible_map_graph",
                fallback_reason="native visible map graph unavailable",
            ),
            "current_node": _projection_declared_field(
                projection,
                "current_map_node",
                fallback_reason="native current map node unavailable",
            ),
            "immediately_legal_routes": _projection_declared_field(
                projection,
                "immediately_legal_routes",
                fallback_reason="native legal routes unavailable",
            ),
        },
        "persistent_resources": _persistent_resources(projection),
        "screen_payload": _projection_declared_field(
            projection,
            "screen_payload",
            fallback_reason="native screen payload unavailable",
        ),
        "candidate_actions": _candidate_actions_field(
            raw,
            actions,
            include_candidates=include_candidates,
        ),
        "history": [dict(entry) for entry in history],
    }
    context["missing_fields"] = explicit_missing_paths(context)
    return sanitize_public_run_context(context)


def build_public_history_entry(
    *,
    history_index: int,
    step_index: int,
    pre_context: Mapping[str, Any],
    post_context: Mapping[str, Any],
    selected_action_index: int,
) -> dict[str, Any]:
    """Build one append-only history entry after a successful transition."""

    candidates = _candidate_items(pre_context)
    if selected_action_index < 0 or selected_action_index >= len(candidates):
        raise ValueError(
            f"selected public action index {selected_action_index} outside "
            f"{len(candidates)} candidate actions"
        )
    selected = dict(candidates[selected_action_index])
    entry: dict[str, Any] = {
        "schema_id": PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_ID,
        "schema_version": PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_VERSION,
        "history_index": history_index,
        "step_index": step_index,
        "pre_decision": {
            "screen": _dict(_dict(pre_context.get("current")).get("screen")),
            "candidate_actions": candidates,
        },
        "selected_action": {
            "index": selected_action_index,
            "candidate": selected,
            "identity": dict(_dict(selected.get("identity"))),
        },
        "post_decision": {
            "screen": _dict(_dict(post_context.get("current")).get("screen")),
            "location": _dict(_dict(post_context.get("current")).get("location")),
            "result": _dict(_dict(post_context.get("current")).get("result")),
        },
        "resource_change": _resource_change(pre_context, post_context),
    }
    entry["missing_fields"] = explicit_missing_paths(entry)
    return sanitize_public_run_context(entry)


def append_public_history_entry(
    history: Sequence[Mapping[str, Any]],
    entry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return a new contiguous public history with ``entry`` appended."""

    expected_index = len(history)
    observed_index = entry.get("history_index")
    if observed_index != expected_index:
        raise ValueError(
            f"public history entry index {observed_index!r} does not match "
            f"expected {expected_index}"
        )
    updated = [sanitize_public_run_context(entry) for entry in history]
    updated.append(sanitize_public_run_context(entry))
    problems = public_history_problems(updated)
    if problems:
        raise ValueError("; ".join(problems))
    return updated


def public_history_problems(history: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return structural problems for a typed ordered public history."""

    problems: list[str] = []
    for expected_index, entry in enumerate(history):
        if entry.get("schema_id") != PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_ID:
            problems.append(f"history {expected_index}: unsupported schema_id")
        if entry.get("schema_version") != PUBLIC_RUN_HISTORY_ENTRY_SCHEMA_VERSION:
            problems.append(f"history {expected_index}: unsupported schema_version")
        if entry.get("history_index") != expected_index:
            problems.append(
                f"history {expected_index}: noncontiguous history_index "
                f"{entry.get('history_index')!r}"
            )
    return problems


def sanitize_public_run_context(value: object) -> dict[str, Any]:
    """Return a JSON-safe public context/history object or fail closed."""

    problems = forbidden_public_context_problems(value)
    if problems:
        raise ValueError("; ".join(problems))
    sanitized = _sanitize_json_value(value, "$")
    if not isinstance(sanitized, dict):
        raise ValueError("public run context root must be an object")
    return sanitized


def forbidden_public_context_problems(value: object) -> list[str]:
    """Audit recursively for forbidden normal-information fields."""

    problems: list[str] = []
    _append_forbidden_problems(value, "$", problems)
    return problems


def explicit_missing_paths(value: object) -> list[str]:
    """Return paths whose field wrappers are unavailable or unsupported."""

    paths: list[str] = []
    _append_missing_paths(value, "$", paths)
    return sorted(dict.fromkeys(paths))


def _screen_field(
    raw: Mapping[str, Any],
    projection: NativePublicProjection | None,
) -> dict[str, Any]:
    if projection is not None:
        return _available_field(projection.screen_identity)
    return _raw_public_field(raw, "screen_state")


def _projection_declared_field(
    projection: NativePublicProjection | None,
    field_name: str,
    *,
    fallback_reason: str,
) -> dict[str, Any]:
    if projection is None:
        return _unavailable_field(fallback_reason)
    field = projection.fields[field_name]
    return _declared_missing_or_available_without_value(field, field_name)


def _declared_missing_or_available_without_value(
    field: NativeProjectionField,
    field_name: str,
) -> dict[str, Any]:
    if field.availability == "available":
        return _unavailable_field(
            f"{field_name} value is not retained by the T014 parsed projection"
        )
    if field.availability == "unsupported":
        return _unsupported_field(field.reason or f"{field_name} unsupported")
    return _unavailable_field(field.reason or f"{field_name} unavailable")


def _persistent_resources(
    projection: NativePublicProjection | None,
) -> dict[str, Any]:
    resources: dict[str, Any] = {
        "schema_id": "public-persistent-resources-v1",
        "fields": {},
    }
    fields = resources["fields"]
    if projection is None:
        for field_name in RESOURCE_FIELD_NAMES:
            fields[field_name] = _unavailable_field(
                "native persistent resources unavailable"
            )
        return resources
    for field_name in RESOURCE_FIELD_NAMES:
        field = projection.resource_fields[field_name]
        if field.availability == "available":
            if field_name in projection.resource_values:
                fields[field_name] = _available_field(
                    projection.resource_values[field_name]
                )
            else:
                fields[field_name] = _unavailable_field(
                    f"{field_name} value is not retained by the parsed projection"
                )
        elif field.availability == "unsupported":
            fields[field_name] = _unsupported_field(
                field.reason or f"{field_name} unsupported"
            )
        else:
            fields[field_name] = _unavailable_field(
                field.reason or f"{field_name} unavailable"
            )
    return resources


def _candidate_actions_field(
    raw: Mapping[str, Any],
    actions: Sequence[SimulatorAction],
    *,
    include_candidates: bool,
) -> dict[str, Any]:
    if not include_candidates:
        return _unavailable_field("candidate actions not requested")
    tactical_actions = build_public_tactical_actions(actions, raw)
    items: list[dict[str, Any]] = []
    for index, (action, tactical_action) in enumerate(
        zip(actions, tactical_actions, strict=True)
    ):
        items.append(
            {
                "index": index,
                "kind": str(action.kind),
                "label": str(action.label),
                "identity": dict(_dict(tactical_action.get("identity"))),
                "parameters": dict(_dict(tactical_action.get("parameters"))),
            }
        )
    return {"availability": "available", "items": items}


def _validate_projection_candidate_parity(
    projection: NativePublicProjection,
    actions: Sequence[SimulatorAction],
) -> None:
    candidate_field = projection.fields["candidate_actions"]
    if candidate_field.availability != "available":
        return
    expected = action_identity_dicts_for_actions(actions)
    observed = projection.candidate_action_identities()
    if expected != observed:
        raise ValueError(
            "public projection candidate actions do not match adapter legal actions"
        )


def _resource_change(
    pre_context: Mapping[str, Any],
    post_context: Mapping[str, Any],
) -> dict[str, Any]:
    pre_fields = _dict(_dict(pre_context.get("persistent_resources")).get("fields"))
    post_fields = _dict(_dict(post_context.get("persistent_resources")).get("fields"))
    changes: dict[str, Any] = {}
    for field_name in RESOURCE_FIELD_NAMES:
        before = _dict(pre_fields.get(field_name))
        after = _dict(post_fields.get(field_name))
        before_value = before.get("value")
        after_value = after.get("value")
        if (
            before.get("availability") == "available"
            and after.get("availability") == "available"
            and isinstance(before_value, int)
            and not isinstance(before_value, bool)
            and isinstance(after_value, int)
            and not isinstance(after_value, bool)
        ):
            changes[field_name] = {
                "availability": "available",
                "before": before_value,
                "after": after_value,
                "delta": after_value - before_value,
            }
        else:
            changes[field_name] = _unavailable_field(
                "resource change requires available numeric before and after values"
            )
    return changes


def _raw_public_field(raw: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = raw.get(key)
        if value is not None and not isinstance(value, (Mapping, Sequence)):
            return _available_field(value)
        if isinstance(value, str) and value:
            return _available_field(value)
    return _unavailable_field(f"snapshot field {'/'.join(keys)} unavailable")


def _available_field(value: object) -> dict[str, Any]:
    return {"availability": "available", "value": _sanitize_json_value(value, "$")}


def _unavailable_field(reason: str) -> dict[str, Any]:
    return {"availability": "unavailable", "reason": reason}


def _unsupported_field(reason: str) -> dict[str, Any]:
    return {"availability": "unsupported", "reason": reason}


def _candidate_items(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates = _dict(context.get("candidate_actions"))
    if candidates.get("availability") != "available":
        return []
    raw_items = candidates.get("items")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        return []
    return [dict(_dict(item)) for item in raw_items]


def _append_missing_paths(value: object, path: str, paths: list[str]) -> None:
    if isinstance(value, Mapping):
        availability = value.get("availability")
        if isinstance(availability, str) and availability != "available":
            paths.append(path)
        for key, item in value.items():
            if key == "missing_fields":
                continue
            _append_missing_paths(item, f"{path}.{key}", paths)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _append_missing_paths(item, f"{path}[{index}]", paths)


def _append_forbidden_problems(value: object, path: str, problems: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if any(fragment in normalized for fragment in _FORBIDDEN_KEY_FRAGMENTS):
                problems.append(f"{path}.{key_text}: forbidden public-context field")
            _append_forbidden_problems(item, f"{path}.{key_text}", problems)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _append_forbidden_problems(item, f"{path}[{index}]", problems)


def _sanitize_json_value(value: object, path: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: public context keys must be strings")
            sanitized[key] = _sanitize_json_value(item, f"{path}.{key}")
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            _sanitize_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise ValueError(
        f"{path}: public context values must be JSON-compatible, "
        f"got {type(value).__name__}"
    )


def _dict(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
