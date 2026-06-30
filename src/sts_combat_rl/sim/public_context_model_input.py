"""Public run-context model-input feature contract.

This module owns the T033 normal-public context encoder. It consumes only the
sanitized public run context artifact and its explicit status, then emits a
versioned fixed-width feature vector plus a separate missingness summary.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Any

from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
    public_context_missing_paths,
    sanitize_public_context_artifact,
)


PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID = "public-context-model-input-v1"
PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION = 1

_SCREEN_CATEGORIES = (
    "battle",
    "rewards",
    "event",
    "shop",
    "rest",
    "treasure",
    "boss_reward",
    "map",
)
_ROOM_CATEGORIES = (
    "monster",
    "elite",
    "boss",
    "event",
    "shop",
    "rest",
    "treasure",
    "rewards",
)
_ACT_BOSS_CATEGORIES = (
    "act1",
    "act2",
    "act3",
)
_ROUTE_ROOM_CATEGORIES = (
    "monster",
    "elite",
    "boss",
    "event",
    "shop",
    "rest",
    "treasure",
    "unknown",
)
_RECENT_HISTORY_LIMIT = 5

PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES = (
    "status.available",
    "schema.current",
    "projection.available",
    "run_position.ascension.available",
    "run_position.ascension",
    "run_position.act.available",
    "run_position.act",
    "run_position.floor.available",
    "run_position.floor",
    *[f"run_position.screen.{name}" for name in _SCREEN_CATEGORIES],
    "run_position.screen.other",
    *[f"run_position.room_type.{name}" for name in _ROOM_CATEGORIES],
    "run_position.room_type.other",
    "run_position.is_battle",
    "run_position.is_boss",
    "run_position.is_elite",
    "run_position.is_monster",
    "run_position.visible_act_boss.available",
    *[f"run_position.visible_act_boss.{name}" for name in _ACT_BOSS_CATEGORIES],
    "run_position.visible_act_boss.other",
    "public_resources.current_hp.available",
    "public_resources.current_hp",
    "public_resources.max_hp.available",
    "public_resources.max_hp",
    "public_resources.hp_ratio.available",
    "public_resources.hp_ratio",
    "public_resources.gold.available",
    "public_resources.gold",
    "public_resources.potion_slot_count.available",
    "public_resources.potion_slot_count",
    "public_resources.occupied_potion_count.available",
    "public_resources.occupied_potion_count",
    "public_resources.deck_size.available",
    "public_resources.deck_size",
    "public_resources.relic_count.available",
    "public_resources.relic_count",
    "public_resources.curse_count.available",
    "public_resources.curse_count",
    "public_resources.blue_key.available",
    "public_resources.blue_key",
    "public_resources.green_key.available",
    "public_resources.green_key",
    "public_resources.red_key.available",
    "public_resources.red_key",
    "route_context.current_node.available",
    "route_context.legal_routes.available",
    "route_context.legal_route_count",
    *[f"route_context.next_room.{name}_count" for name in _ROUTE_ROOM_CATEGORIES],
    "history_counts.entry_count",
    "history_counts.monster",
    "history_counts.elite",
    "history_counts.boss",
    "history_counts.event",
    "history_counts.shop",
    "history_counts.rest",
    "history_counts.treasure",
    "history_counts.reward",
    "history_counts.card_choice",
    "history_counts.relic_choice",
    "history_counts.potion_choice",
    "history_counts.key_choice",
    "recent_public_outcomes.entry_count",
    "recent_public_outcomes.battle_victory_count",
    "recent_public_outcomes.battle_loss_count",
    "recent_public_outcomes.current_hp_delta_total",
    "recent_public_outcomes.max_hp_delta_total",
    "recent_public_outcomes.gold_delta_total",
    "recent_public_outcomes.potion_delta_total",
    "identity_summary_v1.deck_identity_count",
    "identity_summary_v1.attack_card_count",
    "identity_summary_v1.skill_card_count",
    "identity_summary_v1.power_card_count",
    "identity_summary_v1.curse_card_count",
    "identity_summary_v1.relic_identity_count",
    "identity_summary_v1.potion_identity_count",
    "identity_summary_v1.candidate_card_action_count",
    "identity_summary_v1.candidate_potion_action_count",
    "identity_summary_v1.candidate_end_turn_action_count",
    "missingness.explicit_missing_field_count",
    "missingness.problem_count",
)
PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE = len(PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES)

_ASSISTANCE_LEAKAGE_KEY_FRAGMENTS = (
    "assistance",
    "assisted",
    "assist_schedule",
    "assist_level",
    "before_assistance",
    "after_assistance",
    "requested_assistance",
    "actual_assistance",
)
_ASSISTANCE_LEAKAGE_VALUES = (
    "assisted_run",
    "assist_",
)


@dataclass(frozen=True)
class PublicContextModelInput:
    """One encoded public-context row and its audit summary."""

    public_context_feature_schema_id: str = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
    public_context_feature_schema_version: int = (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    )
    public_context_feature_names: tuple[str, ...] = (
        PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES
    )
    public_context_feature_size: int = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
    public_context_features: list[float] = field(default_factory=list)
    public_context_missingness_summary: dict[str, Any] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def public_context_feature_schema_id() -> str:
    return PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID


def public_context_feature_schema_version() -> int:
    return PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION


def public_context_feature_names() -> tuple[str, ...]:
    return PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES


def public_context_feature_size() -> int:
    return PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE


def public_context_features(
    public_run_context: Mapping[str, Any],
    public_context_status: str = PUBLIC_CONTEXT_AVAILABLE,
) -> list[float]:
    encoded = encode_public_context_model_input(
        public_context_status=public_context_status,
        public_run_context=public_run_context,
    )
    if encoded.problems:
        raise ValueError("; ".join(encoded.problems))
    return list(encoded.public_context_features)


def public_context_missingness_summary(
    public_run_context: Mapping[str, Any],
    public_context_status: str = PUBLIC_CONTEXT_AVAILABLE,
) -> dict[str, Any]:
    encoded = encode_public_context_model_input(
        public_context_status=public_context_status,
        public_run_context=public_run_context,
    )
    return dict(encoded.public_context_missingness_summary)


def encode_public_context_model_input(
    *,
    public_context_status: str,
    public_run_context: Mapping[str, Any],
) -> PublicContextModelInput:
    """Encode one public context or return an explicit unavailable summary."""

    if public_context_status != PUBLIC_CONTEXT_AVAILABLE:
        reason = f"public_context_status is {public_context_status!r}"
        problems = []
        if public_context_status != PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
            problems.append(reason)
        return _unavailable_encoded(
            public_context_status=public_context_status,
            reason=reason,
            problems=problems,
        )

    leakage_problems = assistance_leakage_problems(public_run_context)
    if leakage_problems:
        return _unavailable_encoded(
            public_context_status=public_context_status,
            reason="public context contains assistance-only provenance",
            problems=leakage_problems,
        )

    try:
        context = sanitize_public_context_artifact(
            public_run_context,
            label="public context model input",
        )
    except ValueError as exc:
        return _unavailable_encoded(
            public_context_status=public_context_status,
            reason="public context failed sanitizer",
            problems=[str(exc)],
        )

    missing_paths = public_context_missing_paths(context)
    features = _encode_available_context(context, missing_paths)
    summary = _missingness_summary(
        public_context_status=public_context_status,
        context_available=True,
        encoded=True,
        missing_paths=missing_paths,
        problems=[],
    )
    return PublicContextModelInput(
        public_context_features=features,
        public_context_missingness_summary=summary,
        problems=[],
    )


def assistance_leakage_problems(value: object) -> list[str]:
    """Return model-input problems for T042 assistance-only fields."""

    problems: list[str] = []
    _append_assistance_leakage(value, "$", problems)
    return problems


def public_context_model_input_problems(
    *,
    public_context_feature_schema_id: object,
    public_context_feature_schema_version: object,
    public_context_feature_size: object,
    public_context_feature_names: object,
    public_context_features: Sequence[Sequence[float]],
    public_context_missingness_summary: Sequence[Mapping[str, Any]],
    expected_rows: int,
) -> list[str]:
    """Validate model-input context feature fields."""

    problems: list[str] = []
    if public_context_feature_schema_id != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID:
        problems.append(
            "unsupported public context feature schema: "
            f"{public_context_feature_schema_id!r}"
        )
    if (
        public_context_feature_schema_version
        != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    ):
        problems.append(
            "unsupported public context feature schema version: "
            f"{public_context_feature_schema_version!r}"
        )
    if public_context_feature_size != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE:
        problems.append(
            "public context feature size "
            f"{public_context_feature_size!r} does not match "
            f"{PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE}"
        )
    if tuple(public_context_feature_names) != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES:
        problems.append("public context feature names do not match current schema")
    if len(public_context_features) != expected_rows:
        problems.append(
            "public context feature row count "
            f"{len(public_context_features)} does not match {expected_rows} examples"
        )
    if len(public_context_missingness_summary) != expected_rows:
        problems.append(
            "public context missingness summary count "
            f"{len(public_context_missingness_summary)} does not match "
            f"{expected_rows} examples"
        )
    for index, row in enumerate(public_context_features):
        if len(row) != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE:
            problems.append(
                f"example {index}: public context feature size {len(row)} "
                f"does not match {PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE}"
            )
            continue
        for feature_index, value in enumerate(row):
            if not math.isfinite(float(value)):
                problems.append(
                    "example "
                    f"{index}: public context feature {feature_index} is not finite"
                )
                break
    for index, summary in enumerate(public_context_missingness_summary):
        if not isinstance(summary, Mapping):
            problems.append(
                f"example {index}: public context missingness summary is not a mapping"
            )
            continue
        if summary.get("schema_id") != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID:
            problems.append(
                f"example {index}: public context missingness schema is unsupported"
            )
        if summary.get("schema_version") != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION:
            problems.append(
                f"example {index}: public context missingness schema version is unsupported"
            )
    return problems


def summarize_public_context_missingness(
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-example missingness summaries for smoke/preflight reports."""

    status_counts: Counter[str] = Counter()
    missing_paths: Counter[str] = Counter()
    problem_count = 0
    encoded_count = 0
    context_available_count = 0
    for summary in summaries:
        status_counts[str(summary.get("public_context_status", "missing"))] += 1
        if bool(summary.get("encoded")):
            encoded_count += 1
        if bool(summary.get("context_available")):
            context_available_count += 1
        problem_count += _int(summary.get("problem_count"))
        for path in _sequence(summary.get("missing_fields")):
            missing_paths[str(path)] += 1
    return {
        "schema_id": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
        "schema_version": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
        "example_count": len(summaries),
        "encoded_count": encoded_count,
        "context_available_count": context_available_count,
        "status_counts": dict(sorted(status_counts.items())),
        "total_problem_count": problem_count,
        "unique_missing_field_count": len(missing_paths),
        "top_missing_fields": [
            {"path": path, "count": count}
            for path, count in missing_paths.most_common(8)
        ],
    }


def _encode_available_context(
    context: Mapping[str, Any],
    missing_paths: Sequence[str],
) -> list[float]:
    current = _mapping(context.get("current"))
    screen = _field_value(_mapping(current.get("screen")))
    location = _mapping(current.get("location"))
    room_type = _field_value(_mapping(location.get("room_type")))
    visible_boss = _field_value(_mapping(context.get("visible_act_boss")))
    resources = _mapping(_mapping(context.get("persistent_resources")).get("fields"))
    route_map = _mapping(context.get("map"))
    route_current_node = _mapping(route_map.get("current_node"))
    route_legal = _mapping(route_map.get("immediately_legal_routes"))
    history = _history_entries(context.get("history"))
    recent = history[-_RECENT_HISTORY_LIMIT:]
    candidate_items = _items_if_available(_mapping(context.get("candidate_actions")))

    current_hp_available, current_hp = _numeric_pair(resources.get("current_hp"))
    max_hp_available, max_hp = _numeric_pair(resources.get("max_hp"))
    hp_ratio_available = (
        1.0 if current_hp_available and max_hp_available and max_hp > 0 else 0.0
    )
    hp_ratio = current_hp / max_hp if hp_ratio_available else 0.0
    gold_available, gold = _numeric_pair(resources.get("gold"))
    potion_slot_available, potion_slots = _numeric_pair(
        resources.get("potion_capacity")
    )
    occupied_potion_available, occupied_potions = _numeric_pair(
        resources.get("potion_count")
    )
    deck_available, deck_size, curse_count = _deck_summary(resources.get("deck"))
    relic_available, relic_count = _identity_list_count(resources.get("relics"))
    potion_identity_available, potion_identity_count = _identity_list_count(
        resources.get("potion_identities")
    )
    keys = _mapping(_field_value(_mapping(resources.get("keys"))))
    route_items = _items_if_available(route_legal)
    history_counts = _history_counts(history)
    recent_outcomes = _recent_outcomes(recent)
    identity_counts = _identity_counts(
        resources=resources,
        candidate_items=candidate_items,
    )
    route_counts = _route_counts(route_items)

    features = [
        1.0,
        1.0,
        1.0 if context.get("projection_status") == "available" else 0.0,
        *_numeric_pair(location.get("ascension")),
        *_numeric_pair(location.get("act")),
        *_numeric_pair(location.get("floor")),
        *_category_flags(screen, _SCREEN_CATEGORIES),
        *_category_flags(room_type, _ROOM_CATEGORIES),
        1.0 if _is_battle(screen, room_type) else 0.0,
        1.0 if _matches_category(room_type, "boss") else 0.0,
        1.0 if _matches_category(room_type, "elite") else 0.0,
        1.0 if _matches_category(room_type, "monster") else 0.0,
        1.0 if visible_boss is not None else 0.0,
        *_act_boss_flags(visible_boss),
        current_hp_available,
        current_hp,
        max_hp_available,
        max_hp,
        hp_ratio_available,
        hp_ratio,
        gold_available,
        gold,
        potion_slot_available,
        potion_slots,
        occupied_potion_available,
        occupied_potions,
        deck_available,
        deck_size,
        relic_available,
        relic_count,
        deck_available,
        curse_count,
        *_key_pair(keys, "blue_key"),
        *_key_pair(keys, "green_key"),
        *_key_pair(keys, "red_key"),
        1.0 if _field_available(route_current_node) else 0.0,
        1.0 if _field_available(route_legal) else 0.0,
        float(len(route_items)),
        *(float(route_counts[name]) for name in _ROUTE_ROOM_CATEGORIES),
        float(len(history)),
        *(
            float(history_counts[name])
            for name in (
                "monster",
                "elite",
                "boss",
                "event",
                "shop",
                "rest",
                "treasure",
                "reward",
                "card_choice",
                "relic_choice",
                "potion_choice",
                "key_choice",
            )
        ),
        float(len(recent)),
        recent_outcomes["battle_victory_count"],
        recent_outcomes["battle_loss_count"],
        recent_outcomes["current_hp_delta_total"],
        recent_outcomes["max_hp_delta_total"],
        recent_outcomes["gold_delta_total"],
        recent_outcomes["potion_delta_total"],
        identity_counts["deck_identity_count"],
        identity_counts["attack_card_count"],
        identity_counts["skill_card_count"],
        identity_counts["power_card_count"],
        identity_counts["curse_card_count"],
        identity_counts["relic_identity_count"],
        float(potion_identity_count),
        identity_counts["candidate_card_action_count"],
        identity_counts["candidate_potion_action_count"],
        identity_counts["candidate_end_turn_action_count"],
        float(len(missing_paths)),
        0.0,
    ]
    if len(features) != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE:
        raise AssertionError(
            "public context feature implementation does not match feature names"
        )
    return [float(value) for value in features]


def _unavailable_encoded(
    *,
    public_context_status: str,
    reason: str,
    problems: Sequence[str],
) -> PublicContextModelInput:
    features = [0.0 for _ in PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES]
    features[-1] = float(len(problems))
    summary = _missingness_summary(
        public_context_status=public_context_status,
        context_available=False,
        encoded=False,
        missing_paths=(),
        problems=list(problems),
        reason=reason,
    )
    return PublicContextModelInput(
        public_context_features=features,
        public_context_missingness_summary=summary,
        problems=list(problems),
    )


def _missingness_summary(
    *,
    public_context_status: str,
    context_available: bool,
    encoded: bool,
    missing_paths: Sequence[str],
    problems: Sequence[str],
    reason: str | None = None,
) -> dict[str, Any]:
    summary = {
        "schema_id": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
        "schema_version": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
        "public_context_status": str(public_context_status),
        "context_available": bool(context_available),
        "encoded": bool(encoded),
        "missing_field_count": len(missing_paths),
        "missing_fields": list(missing_paths),
        "missing_group_counts": _missing_group_counts(missing_paths),
        "problem_count": len(problems),
        "problems": list(problems),
    }
    if reason is not None:
        summary["reason"] = reason
    return summary


def _missing_group_counts(paths: Sequence[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in paths:
        if path.startswith("$.persistent_resources"):
            counts["public_resources_numeric"] += 1
        elif path.startswith("$.map"):
            counts["route_context"] += 1
        elif path.startswith("$.visible_act_boss"):
            counts["run_position"] += 1
        elif path.startswith("$.history"):
            counts["history_counts"] += 1
        elif path.startswith("$.current"):
            counts["run_position"] += 1
        else:
            counts["other"] += 1
    return dict(sorted(counts.items()))


def _append_assistance_leakage(
    value: object,
    path: str,
    problems: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if any(
                fragment in normalized for fragment in _ASSISTANCE_LEAKAGE_KEY_FRAGMENTS
            ):
                problems.append(
                    f"{path}.{key_text}: assistance-only field is not a normal model input"
                )
            _append_assistance_leakage(item, f"{path}.{key_text}", problems)
        return
    if isinstance(value, str):
        normalized_value = value.lower()
        if any(
            normalized_value == marker or normalized_value.startswith(marker)
            for marker in _ASSISTANCE_LEAKAGE_VALUES
        ):
            problems.append(
                f"{path}: assistance-only value is not a normal model input"
            )
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _append_assistance_leakage(item, f"{path}[{index}]", problems)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _field_available(field: Mapping[str, Any]) -> bool:
    return field.get("availability") == "available"


def _field_value(field: Mapping[str, Any]) -> Any:
    if not _field_available(field):
        return None
    return field.get("value")


def _numeric_pair(field: object) -> tuple[float, float]:
    value = _field_value(_mapping(field))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0, 0.0
    return 1.0, float(value)


def _items_if_available(field: Mapping[str, Any]) -> list[Any]:
    if not _field_available(field):
        return []
    value = field.get("items", field.get("value"))
    return _sequence(value)


def _history_entries(value: object) -> list[Mapping[str, Any]]:
    return [entry for entry in _sequence(value) if isinstance(entry, Mapping)]


def _category_flags(value: object, categories: Sequence[str]) -> list[float]:
    normalized = _normalize_category(value)
    flags = [1.0 if normalized == category else 0.0 for category in categories]
    flags.append(0.0 if any(flags) else (1.0 if normalized else 0.0))
    return flags


def _act_boss_flags(value: object) -> list[float]:
    normalized = _normalize_category(value)
    category = ""
    if normalized in {"slime_boss", "guardian", "hexaghost"}:
        category = "act1"
    elif normalized in {"champ", "collector", "automaton", "bronze_automaton"}:
        category = "act2"
    elif normalized in {
        "awakened_one",
        "time_eater",
        "donu_deca",
        "donu_and_deca",
        "the_shapes",
    }:
        category = "act3"
    flags = [1.0 if category == name else 0.0 for name in _ACT_BOSS_CATEGORIES]
    flags.append(0.0 if any(flags) else (1.0 if normalized else 0.0))
    return flags


def _normalize_category(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _matches_category(value: object, category: str) -> bool:
    normalized = _normalize_category(value)
    return normalized == category or category in normalized.split("_")


def _is_battle(screen: object, room_type: object) -> bool:
    return (
        _normalize_category(screen) == "battle"
        or _matches_category(
            room_type,
            "monster",
        )
        or _matches_category(room_type, "elite")
        or _matches_category(room_type, "boss")
    )


def _deck_summary(field: object) -> tuple[float, float, float]:
    if not _field_available(_mapping(field)):
        return 0.0, 0.0, 0.0
    cards = _sequence(_field_value(_mapping(field)))
    curse_count = sum(1 for card in cards if _is_card_type(card, "curse"))
    return 1.0, float(len(cards)), float(curse_count)


def _identity_list_count(field: object) -> tuple[float, float]:
    if not _field_available(_mapping(field)):
        return 0.0, 0.0
    return 1.0, float(len(_sequence(_field_value(_mapping(field)))))


def _key_pair(keys: Mapping[str, Any], key: str) -> tuple[float, float]:
    if key not in keys:
        return 0.0, 0.0
    value = keys.get(key)
    if isinstance(value, bool):
        return 1.0, 1.0 if value else 0.0
    return 0.0, 0.0


def _route_counts(route_items: Sequence[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in route_items:
        room = _route_room_type(item)
        if room not in _ROUTE_ROOM_CATEGORIES:
            room = "unknown"
        counts[room] += 1
    return counts


def _route_room_type(value: object) -> str:
    if isinstance(value, Mapping):
        for key in ("room_type", "type", "screen", "screen_state"):
            normalized = _normalize_category(value.get(key))
            if normalized:
                return normalized
    return _normalize_category(value) or "unknown"


def _history_counts(history: Sequence[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in history:
        room = _entry_room_category(entry)
        if room in {"monster", "elite", "boss", "event", "shop", "rest", "treasure"}:
            counts[room] += 1
        if room == "rewards":
            counts["reward"] += 1
        choice = _selected_action_text(entry)
        if "card" in choice:
            counts["card_choice"] += 1
        if "relic" in choice:
            counts["relic_choice"] += 1
        if "potion" in choice:
            counts["potion_choice"] += 1
        if "key" in choice:
            counts["key_choice"] += 1
    return counts


def _entry_room_category(entry: Mapping[str, Any]) -> str:
    post = _mapping(entry.get("post_decision"))
    location = _mapping(post.get("location"))
    room = _field_value(_mapping(location.get("room_type")))
    if room is not None:
        return _normalize_category(room)
    screen = _field_value(_mapping(post.get("screen")))
    if screen is not None:
        return _normalize_category(screen)
    pre = _mapping(entry.get("pre_decision"))
    return _normalize_category(_field_value(_mapping(pre.get("screen"))))


def _selected_action_text(entry: Mapping[str, Any]) -> str:
    selected = _mapping(entry.get("selected_action"))
    candidate = _mapping(selected.get("candidate"))
    identity = _mapping(selected.get("identity"))
    parts = [
        candidate.get("kind"),
        candidate.get("label"),
        identity.get("kind"),
        identity.get("label"),
    ]
    return " ".join(_normalize_category(part) for part in parts if part)


def _recent_outcomes(history: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    values = {
        "battle_victory_count": 0.0,
        "battle_loss_count": 0.0,
        "current_hp_delta_total": 0.0,
        "max_hp_delta_total": 0.0,
        "gold_delta_total": 0.0,
        "potion_delta_total": 0.0,
    }
    for entry in history:
        result = _mapping(_mapping(entry.get("post_decision")).get("result"))
        outcome = _normalize_category(
            _field_value(_mapping(result.get("battle_outcome")))
            or _field_value(_mapping(result.get("outcome")))
        )
        if "victory" in outcome or "win" in outcome:
            values["battle_victory_count"] += 1.0
        if "loss" in outcome or "death" in outcome:
            values["battle_loss_count"] += 1.0
        changes = _mapping(entry.get("resource_change"))
        values["current_hp_delta_total"] += _resource_delta(changes, "current_hp")
        values["max_hp_delta_total"] += _resource_delta(changes, "max_hp")
        values["gold_delta_total"] += _resource_delta(changes, "gold")
        values["potion_delta_total"] += _resource_delta(changes, "potion_count")
    return values


def _resource_delta(changes: Mapping[str, Any], name: str) -> float:
    value = _mapping(changes.get(name)).get("delta")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _identity_counts(
    *,
    resources: Mapping[str, Any],
    candidate_items: Sequence[Any],
) -> dict[str, float]:
    deck_items = _sequence(_field_value(_mapping(resources.get("deck"))))
    relic_items = _sequence(_field_value(_mapping(resources.get("relics"))))
    action_kinds = [
        _normalize_category(_mapping(item).get("kind"))
        for item in candidate_items
        if isinstance(item, Mapping)
    ]
    return {
        "deck_identity_count": float(len(deck_items)),
        "attack_card_count": float(
            sum(1 for card in deck_items if _is_card_type(card, "attack"))
        ),
        "skill_card_count": float(
            sum(1 for card in deck_items if _is_card_type(card, "skill"))
        ),
        "power_card_count": float(
            sum(1 for card in deck_items if _is_card_type(card, "power"))
        ),
        "curse_card_count": float(
            sum(1 for card in deck_items if _is_card_type(card, "curse"))
        ),
        "relic_identity_count": float(len(relic_items)),
        "candidate_card_action_count": float(action_kinds.count("card")),
        "candidate_potion_action_count": float(
            sum(1 for kind in action_kinds if "potion" in kind)
        ),
        "candidate_end_turn_action_count": float(action_kinds.count("end_turn")),
    }


def _is_card_type(card: object, card_type: str) -> bool:
    if not isinstance(card, Mapping):
        return False
    return _normalize_category(card.get("type")) == card_type or card_type in {
        _normalize_category(card.get("id")),
        _normalize_category(card.get("name")),
    }


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0
