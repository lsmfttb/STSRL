"""Sanitized public run context for continuation-aware battle policies.

The public run context carries every player-visible fact that can affect later
choices: visible act boss, complete visible map with connectivity, current and
next map nodes, and a typed append-only run history of every executed decision.

This module defines the canonical extraction from a simulator snapshot that
carries the native ``public_visible_screen``, ``visible_map``,
``visible_act_boss``, ``current_map_node``, ``next_map_nodes``, and
``public_encounter_history`` projections. It also owns the typed run history
entries and their allowlists.

No caller may pass a raw simulator object or unrestricted snapshot through this
boundary. Every accepted field is selected below.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import json
from typing import Any

# ---------------------------------------------------------------------------
# Schema identity
# ---------------------------------------------------------------------------

PUBLIC_RUN_CONTEXT_SCHEMA_ID = "public-run-context-v1"
PUBLIC_RUN_CONTEXT_SCHEMA_VERSION = 1
PUBLIC_RUN_HISTORY_SCHEMA_ID = "public-run-history-v1"

# ---------------------------------------------------------------------------
# Key allowlists --- every nested object is validated against its frozenset
# ---------------------------------------------------------------------------

_MAP_NODE_KEYS: frozenset[str] = frozenset(
    {
        "symbol",
        "room_type",
        "burning_elite",
        "x",
        "y",
        "parents",
        "children",
    }
)

_PUBLIC_RUN_CONTEXT_TOP_KEYS: frozenset[str] = frozenset(
    {
        "schema_id",
        "schema_version",
        "visible_act_boss",
        "encounter_history",
        "run_history",
        "visible_map",
        "current_map_node",
        "next_map_nodes",
        "missing_fields",
    }
)

_PUBLIC_RUN_HISTORY_TOP_KEYS: frozenset[str] = frozenset(
    {"schema_id", "entries", "missing_fields"}
)

_PUBLIC_RUN_HISTORY_ENTRY_KEYS: frozenset[str] = frozenset(
    {"sequence", "before", "action", "after", "missing_fields"}
)

_PUBLIC_RUN_HISTORY_BEFORE_KEYS: frozenset[str] = frozenset(
    {"visible_screen", "location"}
)

_PUBLIC_RUN_HISTORY_AFTER_KEYS: frozenset[str] = frozenset(
    {"location", "resource_delta"}
)

_PUBLIC_LOCATION_KEYS: frozenset[str] = frozenset(
    {
        "screen_state",
        "act",
        "floor",
        "room_type",
        "event_id",
        "encounter_id",
        "map_x",
        "map_y",
        "current_map_node",
        "missing_fields",
    }
)

_PUBLIC_ACTION_IDENTITY_KEYS: frozenset[str] = frozenset(
    {"scope", "kind", "parameters", "occurrence", "stable_id"}
)

_PUBLIC_RESOURCE_DELTA_KEYS: frozenset[str] = frozenset(
    {
        "schema_id",
        "current_hp_delta",
        "max_hp_delta",
        "gold_delta",
        "potions_added",
        "potions_removed",
        "cards_added",
        "cards_removed",
        "relics_added",
        "relics_removed",
        "keys_gained",
        "keys_lost",
        "missing_fields",
    }
)

_PUBLIC_POTION_KEYS: frozenset[str] = frozenset({"id", "name"})
_PUBLIC_CARD_KEYS: frozenset[str] = frozenset(
    {"id", "name", "type", "rarity", "upgraded", "upgrades"}
)
_PUBLIC_RELIC_KEYS: frozenset[str] = frozenset({"id", "name"})

_ENCOUNTER_HISTORY_KEYS: frozenset[str] = frozenset(
    {"act", "floor", "room_type", "encounter_id"}
)

# Visible screen allowlist --- flat frozenset covering all screen-category keys.
# Unknown keys at any nesting depth are rejected by the recursive validator.
_PUBLIC_VISIBLE_SCREEN_KEYS: frozenset[str] = frozenset(
    {
        "schema_id",
        "screen_state",
        "projection_available",
        "legal_actions",
        "event_id",
        "event_options",
        "options",
        "option_id",
        "option_index",
        "option_label",
        "rewards",
        "reward_index",
        "reward_type",
        "cards",
        "card_select",
        "selection_type",
        "selection_count",
        "selected_count",
        "selected",
        "potions",
        "relics",
        "boss_relics",
        "map",
        "visible_map",
        "nodes",
        "current_node",
        "current_map_node",
        "next_nodes",
        "next_map_nodes",
        "visible_act_boss",
        "treasure",
        "chest_size",
        "rest_options",
        "shop",
        "shop_items",
        "remove_card_cost",
        "remove_card_sold_out",
        "card_remove_price",
        "inventory",
        "category",
        "id",
        "name",
        "label",
        "type",
        "rarity",
        "amount",
        "index",
        "price",
        "cost",
        "upgraded",
        "upgrades",
        "upgrade_count",
        "enabled",
        "available",
        "skip_allowed",
        "requires_target",
        "target_index",
        "sold_out",
        "singing_bowl_available",
        "potion_slot_index",
        "relic_index",
        "card_index",
        "missing_fields",
    }
)

_RESOURCE_FIELDS = ("cur_hp", "max_hp", "gold", "potions", "deck", "relics")
_KEY_FIELDS = ("blue_key", "green_key", "red_key")

# Forbidden fields --- their presence anywhere in the context is a hard audit
# failure, even if they'd otherwise fall through an allowlist gap.
_FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "draw_pile",
        "draw_pile_order",
        "draw_order",
        "rng",
        "rng_state",
        "seed_internal",
        "hidden_rng",
        "raw_native_checkpoint",
        "native_payload",
        "native",
        "sim_internals",
        "unrevealed_encounters",
        "hidden_act3_boss",
        "hidden_future",
    }
)

# ---------------------------------------------------------------------------
# Public run context extraction
# ---------------------------------------------------------------------------


def build_public_run_context(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only explicitly player-visible run context from a snapshot.

    The snapshot is expected to carry the native projections from the
    ``sts_lightspeed_public_run_context`` patch: ``visible_act_boss``,
    ``visible_map``, ``current_map_node``, ``next_map_nodes``,
    ``public_encounter_history``, and ``public_visible_screen``.

    Every sub-object is projected through the module allowlists. Fields not
    supplied by the native projection are recorded in ``missing_fields``.
    """

    game = _mapping(raw.get("game_state")) or _mapping(raw.get("gameState")) or raw
    screen_state_src = _mapping(game.get("screen_state")) or _mapping(
        game.get("screenState")
    )

    boss_present, boss_value = _first_present(game, "visible_act_boss", "act_boss")
    encounter_present, encounter_value = _first_present(
        game, "public_encounter_history", "encounter_history"
    )
    map_present, map_value = _first_present(game, "visible_map", "map")
    current_present, current_value = _first_present(game, "current_map_node")
    next_present, next_value = _first_present(game, "next_map_nodes")

    if not current_present and "current_node" in screen_state_src:
        current_present, current_value = True, screen_state_src.get("current_node")
    if not next_present and "next_nodes" in screen_state_src:
        next_present, next_value = True, screen_state_src.get("next_nodes")

    history_present, history_value = _first_present(
        game, "public_run_history", "run_history"
    )

    missing_fields: list[str] = []
    for field_name, present in (
        ("visible_act_boss", boss_present),
        ("encounter_history", encounter_present),
        ("run_history", history_present),
        ("visible_map", map_present),
        ("current_map_node", current_present),
        ("next_map_nodes", next_present),
    ):
        if not present:
            missing_fields.append(field_name)

    context: dict[str, Any] = {
        "schema_id": PUBLIC_RUN_CONTEXT_SCHEMA_ID,
        "schema_version": PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
        "visible_act_boss": (
            str(boss_value)
            if boss_present and boss_value is not None and _is_public_scalar(boss_value)
            else None
        ),
        "encounter_history": _project_rows(encounter_value, _ENCOUNTER_HISTORY_KEYS),
        "run_history": (
            project_public_run_history(history_value)
            if history_present
            else empty_public_run_history(missing_fields=("public_run_history",))
        ),
        "visible_map": _project_rows(map_value, _MAP_NODE_KEYS),
        "current_map_node": (
            _project_mapping(current_value, _MAP_NODE_KEYS)
            if current_present and isinstance(current_value, Mapping)
            else None
        ),
        "next_map_nodes": _project_rows(next_value, _MAP_NODE_KEYS),
        "missing_fields": missing_fields,
    }
    context["missing_fields"] = public_run_context_missing_fields(context)
    return context


def empty_public_run_context() -> dict[str, Any]:
    """Return a valid context with every public field explicitly missing."""

    return build_public_run_context({})


# ---------------------------------------------------------------------------
# Public run history
# ---------------------------------------------------------------------------


def empty_public_run_history(*, missing_fields: Sequence[str] = ()) -> dict[str, Any]:
    """Return an empty, valid run history."""

    return {
        "schema_id": PUBLIC_RUN_HISTORY_SCHEMA_ID,
        "entries": [],
        "missing_fields": [str(name) for name in missing_fields],
    }


def project_public_run_history(value: Any) -> dict[str, Any]:
    """Project untrusted history data through the public-history allowlist."""

    if not isinstance(value, Mapping):
        return empty_public_run_history(missing_fields=("public_run_history",))
    entries = value.get("entries")
    source_entries = list(entries) if _is_sequence(entries) else []
    projected_entries = [
        _project_history_entry(entry, index)
        for index, entry in enumerate(source_entries)
        if isinstance(entry, Mapping)
    ]
    missing = _string_list(value.get("missing_fields"))
    if value.get("schema_id") != PUBLIC_RUN_HISTORY_SCHEMA_ID:
        missing.append("source.schema_id")
    if not _is_sequence(entries):
        missing.append("source.entries")
    if len(projected_entries) != len(source_entries):
        missing.append("source.entries.invalid_items")
    return {
        "schema_id": PUBLIC_RUN_HISTORY_SCHEMA_ID,
        "entries": projected_entries,
        "missing_fields": list(dict.fromkeys(missing)),
    }


def append_run_history_entry(
    history: Mapping[str, Any],
    *,
    before_raw: Mapping[str, Any],
    action_identity: Mapping[str, Any],
    after_raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Append one successfully executed decision to the typed public history.

    Parameters:
        history: The current run history dict (may be empty or projected).
        before_raw: The simulator snapshot BEFORE the action was taken.
        action_identity: The occurrence-disambiguated public action identity
            (from ``_attach_public_action_identities`` in ``features.py``).
        after_raw: The simulator snapshot AFTER the action was taken.
    """

    projected = project_public_run_history(history)
    entries = list(projected["entries"])
    visible_screen = extract_public_visible_screen(before_raw)
    entry_missing: list[str] = []
    if "public_visible_screen" in visible_screen.get("missing_fields", ()):
        entry_missing.append("before.public_visible_screen")

    entries.append(
        {
            "sequence": len(entries),
            "before": {
                "visible_screen": visible_screen,
                "location": extract_public_location(before_raw),
            },
            "action": project_public_action_identity(action_identity),
            "after": {
                "location": extract_public_location(after_raw),
                "resource_delta": build_public_resource_delta(before_raw, after_raw),
            },
            "missing_fields": entry_missing,
        }
    )
    projected["entries"] = entries
    if projected["missing_fields"]:
        projected["missing_fields"] = [
            f for f in projected["missing_fields"] if f != "public_run_history"
        ]
    return projected


# ---------------------------------------------------------------------------
# Visible screen extraction
# ---------------------------------------------------------------------------


def extract_public_visible_screen(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Read only the native public-visible-screen projection.

    Returns a dict with ``schema_id``, recursive screen content projected
    through the visible-screen allowlist, and ``missing_fields``.
    """

    value = raw.get("public_visible_screen")
    if not isinstance(value, Mapping):
        return {
            "schema_id": "public-visible-screen-v1",
            "missing_fields": ["public_visible_screen"],
        }
    projected = _project_recursive_mapping(value, _PUBLIC_VISIBLE_SCREEN_KEYS)
    projected["schema_id"] = "public-visible-screen-v1"
    projected["missing_fields"] = _string_list(value.get("missing_fields"))
    return projected


# ---------------------------------------------------------------------------
# Action identity projection
# ---------------------------------------------------------------------------


def project_public_action_identity(action: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only the public action identity fields, discarding native payloads."""

    return {
        key: _json_scalar(action[key])
        for key in _PUBLIC_ACTION_IDENTITY_KEYS
        if key in action and _json_scalar(action[key]) is not None
    }


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------


def extract_public_location(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Extract explicitly public current-location fields."""

    location: dict[str, Any] = {}
    scalar_keys = (
        "screen_state",
        "act",
        "room_type",
        "event_id",
        "encounter_id",
        "map_x",
        "map_y",
    )
    for key in scalar_keys:
        if key in raw and _json_scalar(raw[key]) is not None:
            location[key] = raw[key]

    floor = raw.get("floor", raw.get("floor_num"))
    if _json_scalar(floor) is not None:
        location["floor"] = floor

    current_node = raw.get("current_map_node")
    if isinstance(current_node, Mapping):
        location["current_map_node"] = _project_mapping(current_node, _MAP_NODE_KEYS)

    location["missing_fields"] = [
        field_name
        for field_name, present in (
            ("screen_state", "screen_state" in raw),
            ("act", "act" in raw),
            ("floor", "floor" in raw or "floor_num" in raw),
            ("room_type", "room_type" in raw),
            ("current_map_node", "current_map_node" in raw),
        )
        if not present
    ]
    return location


# ---------------------------------------------------------------------------
# Resource delta
# ---------------------------------------------------------------------------


def build_public_resource_delta(
    before_raw: Mapping[str, Any],
    after_raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a strict public resource delta without exposing internal data."""

    missing: list[str] = []
    for side, raw in (("before", before_raw), ("after", after_raw)):
        for field_name in (*_RESOURCE_FIELDS, *_KEY_FIELDS):
            if field_name not in raw:
                missing.append(f"{side}.{field_name}")

    before_potions = _project_rows(before_raw.get("potions"), _PUBLIC_POTION_KEYS)
    after_potions = _project_rows(after_raw.get("potions"), _PUBLIC_POTION_KEYS)
    before_cards = _project_rows(before_raw.get("deck"), _PUBLIC_CARD_KEYS)
    after_cards = _project_rows(after_raw.get("deck"), _PUBLIC_CARD_KEYS)
    before_relics = _project_rows(before_raw.get("relics"), _PUBLIC_RELIC_KEYS)
    after_relics = _project_rows(after_raw.get("relics"), _PUBLIC_RELIC_KEYS)
    before_keys = {key for key in _KEY_FIELDS if before_raw.get(key) is True}
    after_keys = {key for key in _KEY_FIELDS if after_raw.get(key) is True}

    potions_added, potions_removed = _collection_delta(before_potions, after_potions)
    cards_added, cards_removed = _collection_delta(before_cards, after_cards)
    relics_added, relics_removed = _collection_delta(before_relics, after_relics)

    return {
        "schema_id": "public-resource-delta-v1",
        "current_hp_delta": _numeric_delta(
            before_raw.get("cur_hp"), after_raw.get("cur_hp")
        ),
        "max_hp_delta": _numeric_delta(
            before_raw.get("max_hp"), after_raw.get("max_hp")
        ),
        "gold_delta": _numeric_delta(before_raw.get("gold"), after_raw.get("gold")),
        "potions_added": potions_added,
        "potions_removed": potions_removed,
        "cards_added": cards_added,
        "cards_removed": cards_removed,
        "relics_added": relics_added,
        "relics_removed": relics_removed,
        "keys_gained": sorted(after_keys - before_keys),
        "keys_lost": sorted(before_keys - after_keys),
        "missing_fields": missing,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def public_run_context_missing_fields(context: Mapping[str, Any]) -> list[str]:
    """Return explicit missing-field paths for the run context."""

    missing: list[str] = []
    for field_name in (
        "visible_act_boss",
        "encounter_history",
        "run_history",
        "visible_map",
        "current_map_node",
        "next_map_nodes",
    ):
        value = context.get(field_name)
        if field_name == "visible_act_boss":
            if value is None:
                missing.append(field_name)
        elif field_name == "run_history":
            if not isinstance(value, Mapping) or not value.get("entries"):
                missing.append(field_name)
        elif not isinstance(value, list) or not value:
            missing.append(field_name)
    if (
        isinstance(context.get("visible_map"), list)
        and context["visible_map"]
        and context.get("current_map_node") is None
    ):
        missing.append("current_map_node")
    return sorted(set(context.get("missing_fields", [])) | set(missing))


def public_run_context_problems(context: Mapping[str, Any]) -> list[str]:
    """Validate the normal-information run-context boundary.

    Checks:
    - Top-level keys are within the allowlist.
    - Schema id is correct.
    - Every nested object contains only allowlisted keys (recursive).
    - Forbidden fields are absent at every level.
    - History entries are structurally valid and sequence-ordered.
    """

    problems: list[str] = []

    unexpected_top = sorted(set(context) - _PUBLIC_RUN_CONTEXT_TOP_KEYS)
    if unexpected_top:
        problems.append(
            "public run context contains non-allowlisted top-level fields: "
            + ", ".join(unexpected_top)
        )

    if context.get("schema_id") != PUBLIC_RUN_CONTEXT_SCHEMA_ID:
        problems.append("public run context schema id is missing or unsupported")

    missing = context.get("missing_fields")
    if not isinstance(missing, list) or not all(
        isinstance(name, str) for name in missing
    ):
        problems.append("public run context missing_fields must be a string list")

    _validate_projected_rows(
        context.get("encounter_history"),
        _ENCOUNTER_HISTORY_KEYS,
        "encounter_history",
        problems,
    )

    run_history = context.get("run_history")
    if not isinstance(run_history, Mapping):
        problems.append("public run context run_history must be an object")
    else:
        problems.extend(public_run_history_problems(run_history))

    _validate_projected_rows(
        context.get("visible_map"),
        _MAP_NODE_KEYS,
        "visible_map",
        problems,
    )

    current_node = context.get("current_map_node")
    if current_node is not None:
        _validate_projected_mapping(
            current_node, _MAP_NODE_KEYS, "current_map_node", problems
        )

    _validate_projected_rows(
        context.get("next_map_nodes"),
        _MAP_NODE_KEYS,
        "next_map_nodes",
        problems,
    )

    _check_forbidden_fields(context, "public run context", problems)

    return problems


def public_run_history_problems(history: Mapping[str, Any]) -> list[str]:
    """Validate that a run history contains only allowlisted public fields."""

    problems: list[str] = []
    _unexpected_keys(history, _PUBLIC_RUN_HISTORY_TOP_KEYS, "run history", problems)
    if history.get("schema_id") != PUBLIC_RUN_HISTORY_SCHEMA_ID:
        problems.append("run history schema id is missing or unsupported")
    _validate_string_list(history.get("missing_fields"), "run history", problems)
    entries = history.get("entries")
    if not isinstance(entries, list):
        problems.append("run history entries must be a list")
        return problems

    for index, entry in enumerate(entries):
        _validate_history_entry(entry, index, problems)

    sequences = [e.get("sequence") for e in entries if isinstance(e, Mapping)]
    expected = list(range(len(sequences)))
    if sequences != expected:
        problems.append(
            f"run history entries sequence numbers {sequences} "
            f"are not contiguous from 0; expected {expected}"
        )

    _check_forbidden_fields(history, "run history", problems)

    return problems


# ---------------------------------------------------------------------------
# Internal: history entry projection and validation
# ---------------------------------------------------------------------------


def _project_history_entry(
    entry: Mapping[str, Any], fallback_sequence: int
) -> dict[str, Any]:
    before = entry.get("before")
    after = entry.get("after")
    before_mapping = before if isinstance(before, Mapping) else {}
    after_mapping = after if isinstance(after, Mapping) else {}
    sequence = entry.get("sequence")
    result = {
        "sequence": (
            sequence
            if isinstance(sequence, int) and not isinstance(sequence, bool)
            else fallback_sequence
        ),
        "before": {
            "visible_screen": extract_public_visible_screen(
                {"public_visible_screen": before_mapping.get("visible_screen")}
            ),
            "location": _project_mapping(
                before_mapping.get("location"),
                _PUBLIC_LOCATION_KEYS,
                nested_keys={"current_map_node": _MAP_NODE_KEYS},
            ),
        },
        "action": project_public_action_identity(
            entry.get("action") if isinstance(entry.get("action"), Mapping) else {}
        ),
        "after": {
            "location": _project_mapping(
                after_mapping.get("location"),
                _PUBLIC_LOCATION_KEYS,
                nested_keys={"current_map_node": _MAP_NODE_KEYS},
            ),
            "resource_delta": _project_resource_delta(
                after_mapping.get("resource_delta")
            ),
        },
        "missing_fields": _string_list(entry.get("missing_fields")),
    }
    for key, item in entry.items():
        if key in _FORBIDDEN_FIELD_NAMES:
            result[key] = item
    return result


def _project_resource_delta(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "schema_id": "public-resource-delta-v1",
        "current_hp_delta": _optional_number(source.get("current_hp_delta")),
        "max_hp_delta": _optional_number(source.get("max_hp_delta")),
        "gold_delta": _optional_number(source.get("gold_delta")),
        "potions_added": _project_rows(
            source.get("potions_added"), _PUBLIC_POTION_KEYS
        ),
        "potions_removed": _project_rows(
            source.get("potions_removed"), _PUBLIC_POTION_KEYS
        ),
        "cards_added": _project_rows(source.get("cards_added"), _PUBLIC_CARD_KEYS),
        "cards_removed": _project_rows(source.get("cards_removed"), _PUBLIC_CARD_KEYS),
        "relics_added": _project_rows(source.get("relics_added"), _PUBLIC_RELIC_KEYS),
        "relics_removed": _project_rows(
            source.get("relics_removed"), _PUBLIC_RELIC_KEYS
        ),
        "keys_gained": _string_list(source.get("keys_gained")),
        "keys_lost": _string_list(source.get("keys_lost")),
        "missing_fields": _string_list(source.get("missing_fields")),
    }


def _validate_history_entry(value: Any, index: int, problems: list[str]) -> None:
    label = f"run history entries[{index}]"
    if not isinstance(value, Mapping):
        problems.append(f"{label} must be an object")
        return
    _unexpected_keys(value, _PUBLIC_RUN_HISTORY_ENTRY_KEYS, label, problems)
    if not isinstance(value.get("sequence"), int) or isinstance(
        value.get("sequence"), bool
    ):
        problems.append(f"{label} sequence must be an integer")
    _validate_string_list(value.get("missing_fields"), label, problems)

    before = value.get("before")
    if not isinstance(before, Mapping):
        problems.append(f"{label} before must be an object")
    else:
        _unexpected_keys(
            before,
            _PUBLIC_RUN_HISTORY_BEFORE_KEYS,
            f"{label} before",
            problems,
        )
        _validate_visible_screen(
            before.get("visible_screen"), f"{label} before", problems
        )
        _validate_location(before.get("location"), f"{label} before location", problems)

    action = value.get("action")
    if not isinstance(action, Mapping):
        problems.append(f"{label} action must be an object")
    else:
        _unexpected_keys(
            action,
            _PUBLIC_ACTION_IDENTITY_KEYS,
            f"{label} action",
            problems,
        )

    after = value.get("after")
    if not isinstance(after, Mapping):
        problems.append(f"{label} after must be an object")
    else:
        _unexpected_keys(
            after,
            _PUBLIC_RUN_HISTORY_AFTER_KEYS,
            f"{label} after",
            problems,
        )
        _validate_location(after.get("location"), f"{label} after location", problems)
        _validate_resource_delta(
            after.get("resource_delta"),
            f"{label} after resource_delta",
            problems,
        )

    _check_forbidden_fields(value, label, problems)


def _validate_visible_screen(value: Any, label: str, problems: list[str]) -> None:
    if not isinstance(value, Mapping):
        problems.append(f"{label} visible_screen must be an object")
        return
    _validate_recursive_mapping(
        value,
        _PUBLIC_VISIBLE_SCREEN_KEYS,
        f"{label} visible_screen",
        problems,
    )
    _validate_string_list(
        value.get("missing_fields"), f"{label} visible_screen", problems
    )


def _validate_location(value: Any, label: str, problems: list[str]) -> None:
    if not isinstance(value, Mapping):
        problems.append(f"{label} must be an object")
        return
    _unexpected_keys(value, _PUBLIC_LOCATION_KEYS, label, problems)
    current_node = value.get("current_map_node")
    if current_node is not None:
        if not isinstance(current_node, Mapping):
            problems.append(f"{label} current_map_node must be an object")
        else:
            _validate_recursive_mapping(
                current_node,
                _MAP_NODE_KEYS,
                f"{label} current_map_node",
                problems,
            )
    _validate_string_list(value.get("missing_fields"), label, problems)
    _check_forbidden_fields(value, label, problems)


def _validate_resource_delta(value: Any, label: str, problems: list[str]) -> None:
    if not isinstance(value, Mapping):
        problems.append(f"{label} must be an object")
        return
    _unexpected_keys(value, _PUBLIC_RESOURCE_DELTA_KEYS, label, problems)
    for field_name in ("current_hp_delta", "max_hp_delta", "gold_delta"):
        item = value.get(field_name)
        if item is not None and _optional_number(item) is None:
            problems.append(f"{label} {field_name} must be a number or null")
    for field_name, keys in (
        ("potions_added", _PUBLIC_POTION_KEYS),
        ("potions_removed", _PUBLIC_POTION_KEYS),
        ("cards_added", _PUBLIC_CARD_KEYS),
        ("cards_removed", _PUBLIC_CARD_KEYS),
        ("relics_added", _PUBLIC_RELIC_KEYS),
        ("relics_removed", _PUBLIC_RELIC_KEYS),
    ):
        _validate_rows(
            value.get(field_name),
            keys,
            f"{label} {field_name}",
            problems,
        )
    for field_name in ("keys_gained", "keys_lost", "missing_fields"):
        _validate_string_list(value.get(field_name), f"{label} {field_name}", problems)


# ---------------------------------------------------------------------------
# Recursive projection and validation helpers
# ---------------------------------------------------------------------------


def _project_recursive_mapping(
    value: Mapping[str, Any],
    allowed_keys: frozenset[str],
) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, item in value.items():
        if key not in allowed_keys and key not in _FORBIDDEN_FIELD_NAMES:
            continue
        if isinstance(item, Mapping):
            projected[key] = _project_recursive_mapping(item, allowed_keys)
        elif _is_sequence(item):
            projected[key] = [
                _project_recursive_mapping(child, allowed_keys)
                if isinstance(child, Mapping)
                else _json_scalar(child)
                for child in item
                if isinstance(child, Mapping) or _json_scalar(child) is not None
            ]
        else:
            scalar = _json_scalar(item)
            if scalar is not None:
                projected[key] = scalar
    return projected


def _validate_recursive_mapping(
    value: Mapping[str, Any],
    allowed_keys: frozenset[str],
    label: str,
    problems: list[str],
) -> None:
    _unexpected_keys(value, allowed_keys, label, problems)
    for key, item in value.items():
        if isinstance(item, Mapping):
            _validate_recursive_mapping(item, allowed_keys, f"{label}.{key}", problems)
        elif _is_sequence(item):
            for idx, child in enumerate(item):
                if isinstance(child, Mapping):
                    _validate_recursive_mapping(
                        child,
                        allowed_keys,
                        f"{label}.{key}[{idx}]",
                        problems,
                    )
                elif _json_scalar(child) is None and child is not None:
                    problems.append(f"{label}.{key}[{idx}] contains a non-public value")
        elif _json_scalar(item) is None and item is not None:
            problems.append(f"{label}.{key} contains a non-public value")


def _check_forbidden_fields(value: Any, label: str, problems: list[str]) -> None:
    """Recursively check that no forbidden field name appears anywhere."""

    if isinstance(value, Mapping):
        for key in value:
            if key in _FORBIDDEN_FIELD_NAMES:
                problems.append(f"{label} contains forbidden field {key!r}")
        for key, item in value.items():
            _check_forbidden_fields(item, f"{label}.{key}", problems)
    elif _is_sequence(value):
        for idx, item in enumerate(value):
            _check_forbidden_fields(item, f"{label}[{idx}]", problems)


def _validate_projected_rows(
    value: Any,
    keys: frozenset[str],
    label: str,
    problems: list[str],
) -> None:
    if not isinstance(value, list):
        problems.append(f"public run context {label} must be a list")
        return
    for index, row in enumerate(value):
        _validate_projected_mapping(row, keys, f"{label}[{index}]", problems)


def _validate_projected_mapping(
    value: Any,
    keys: frozenset[str],
    label: str,
    problems: list[str],
) -> None:
    if not isinstance(value, Mapping):
        problems.append(f"public run context {label} must be an object")
        return
    unexpected = sorted(set(value) - set(keys))
    if unexpected:
        problems.append(
            f"public run context {label} contains non-allowlisted fields: "
            + ", ".join(unexpected)
        )
    for key, item in value.items():
        if key in {"parents", "children"}:
            if not isinstance(item, list):
                problems.append(f"public run context {label}.{key} must be a list")
                continue
            for idx, child in enumerate(item):
                if isinstance(child, Mapping):
                    _validate_projected_mapping(
                        child, keys, f"{label}.{key}[{idx}]", problems
                    )
                elif not _is_public_scalar(child):
                    problems.append(
                        f"public run context {label}.{key}[{idx}] "
                        "contains a non-public value"
                    )
        elif not _is_public_scalar(item):
            problems.append(
                f"public run context {label}.{key} contains a non-public value"
            )


def _validate_rows(
    value: Any,
    keys: frozenset[str],
    label: str,
    problems: list[str],
) -> None:
    if not isinstance(value, list):
        problems.append(f"{label} must be a list")
        return
    for idx, row in enumerate(value):
        if not isinstance(row, Mapping):
            problems.append(f"{label}[{idx}] must be an object")
            continue
        _unexpected_keys(row, keys, f"{label}[{idx}]", problems)


def _unexpected_keys(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    label: str,
    problems: list[str],
) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        problems.append(
            f"{label} contains non-allowlisted fields: " + ", ".join(unexpected)
        )


def _validate_string_list(value: Any, label: str, problems: list[str]) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        problems.append(f"{label} missing_fields must be a string list")


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _project_rows(value: Any, keys: frozenset[str]) -> list[dict[str, Any]]:
    if not _is_sequence(value):
        return []
    return [_project_mapping(item, keys) for item in value if isinstance(item, Mapping)]


def _project_mapping(
    value: Any,
    keys: frozenset[str],
    *,
    nested_keys: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    nested_keys = nested_keys or {}
    projected: dict[str, Any] = {}
    for key in keys:
        if key not in value:
            continue
        item = value[key]
        if key in nested_keys and isinstance(item, Mapping):
            projected[key] = _project_mapping(item, nested_keys[key])
        elif key in {"parents", "children"} and _is_sequence(item):
            projected[key] = [
                _project_mapping(child, keys)
                if isinstance(child, Mapping)
                else _json_scalar(child)
                for child in item
                if isinstance(child, Mapping) or _json_scalar(child) is not None
            ]
        else:
            scalar = _json_scalar(item)
            if scalar is not None:
                projected[key] = scalar
    for key, item in value.items():
        if key in _FORBIDDEN_FIELD_NAMES:
            projected[key] = item
    return projected


# ---------------------------------------------------------------------------
# Delta helpers
# ---------------------------------------------------------------------------


def _collection_delta(
    before: Sequence[dict[str, Any]],
    after: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before_by_key = {_canonical(item): item for item in before}
    after_by_key = {_canonical(item): item for item in after}
    before_counts = Counter(_canonical(item) for item in before)
    after_counts = Counter(_canonical(item) for item in after)
    representatives = {**before_by_key, **after_by_key}
    added = [
        representatives[key]
        for key in sorted(after_counts)
        for _ in range(max(0, after_counts[key] - before_counts[key]))
    ]
    removed = [
        representatives[key]
        for key in sorted(before_counts)
        for _ in range(max(0, before_counts[key] - after_counts[key]))
    ]
    return added, removed


# ---------------------------------------------------------------------------
# Scalar and type helpers
# ---------------------------------------------------------------------------


def _first_present(data: Mapping[str, Any], *keys: str) -> tuple[bool, Any]:
    for key in keys:
        if key in data:
            return True, data.get(key)
    return False, None


def _string_list(value: Any) -> list[str]:
    if not _is_sequence(value):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _numeric_delta(before: Any, after: Any) -> float | None:
    before_number = _optional_number(before)
    after_number = _optional_number(after)
    if before_number is None or after_number is None:
        return None
    return after_number - before_number


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _json_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _is_public_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
