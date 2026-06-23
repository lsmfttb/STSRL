"""Structured battle-end resource outcomes.

The outcome schema keeps terminal battle result, absolute HP, and public
persistent resources inspectable as separate labels.  It intentionally does not
choose scalar reward weights or infer missing game mechanics from local rules.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any


BATTLE_RESOURCE_OUTCOME_SCHEMA_ID = "structured-battle-outcome-v1"
BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION = 1
BATTLE_RESOURCE_OUTCOME_AVAILABLE = "available"
BATTLE_RESOURCE_OUTCOME_UNAVAILABLE = "unavailable"
BATTLE_RESOURCE_OUTCOME_LEGACY_UNAVAILABLE = "legacy_unavailable"
BATTLE_RESOURCE_OUTCOME_STATUSES = frozenset(
    {
        BATTLE_RESOURCE_OUTCOME_AVAILABLE,
        BATTLE_RESOURCE_OUTCOME_UNAVAILABLE,
        BATTLE_RESOURCE_OUTCOME_LEGACY_UNAVAILABLE,
    }
)

BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS = (
    "legacy artifact did not preserve structured battle resource outcome"
)

FIELD_AVAILABLE = "available"
FIELD_MISSING = "missing"
FIELD_UNAVAILABLE = "unavailable"
FIELD_STATUSES = frozenset({FIELD_AVAILABLE, FIELD_MISSING, FIELD_UNAVAILABLE})

_OUTCOME_FIELDS = (
    "schema_id",
    "schema_version",
    "battle_result",
    "battle_survived",
    "terminal_absolute_current_hp",
    "terminal_max_hp",
    "start",
    "terminal",
    "deltas",
    "unsupported_native_fields",
    "problems",
)
_SNAPSHOT_COMPONENTS = (
    "current_hp",
    "max_hp",
    "gold",
    "potion_capacity",
    "potion_slots",
    "deck",
    "curses",
    "relics",
    "keys",
    "other_exposed_resources",
)
_KEY_NAMES = ("blue_key", "green_key", "red_key")
_OTHER_RESOURCE_KEYS = (
    "ascension",
    "ascension_level",
    "act",
    "floor",
    "floor_num",
    "room_type",
    "act_boss",
)
_EMPTY_POTION_NAMES = {"", "EMPTY_POTION_SLOT", "POTION SLOT", "Potion Slot"}


@dataclass(frozen=True)
class ResourceField:
    """One resource component with explicit availability and source."""

    status: str
    value: Any = None
    source: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status}
        if self.status == FIELD_AVAILABLE:
            result["value"] = _json_safe_value(self.value)
            result["source"] = self.source or "snapshot"
        else:
            result["reason"] = self.reason or self.status
        return result


@dataclass(frozen=True)
class PublicResourceSnapshot:
    """Sanitized public resources at one battle boundary."""

    current_hp: ResourceField
    max_hp: ResourceField
    gold: ResourceField
    potion_capacity: ResourceField
    potion_slots: ResourceField
    deck: ResourceField
    curses: ResourceField
    relics: ResourceField
    keys: ResourceField
    other_exposed_resources: ResourceField

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name).to_dict() for name in _SNAPSHOT_COMPONENTS}


@dataclass(frozen=True)
class BattleResourceOutcome:
    """Current structured outcome for one completed battle segment."""

    battle_result: ResourceField
    battle_survived: ResourceField
    terminal_absolute_current_hp: ResourceField
    terminal_max_hp: ResourceField
    start: PublicResourceSnapshot
    terminal: PublicResourceSnapshot
    deltas: dict[str, Any]
    unsupported_native_fields: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    schema_id: str = BATTLE_RESOURCE_OUTCOME_SCHEMA_ID
    schema_version: int = BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "battle_result": self.battle_result.to_dict(),
            "battle_survived": self.battle_survived.to_dict(),
            "terminal_absolute_current_hp": (
                self.terminal_absolute_current_hp.to_dict()
            ),
            "terminal_max_hp": self.terminal_max_hp.to_dict(),
            "start": self.start.to_dict(),
            "terminal": self.terminal.to_dict(),
            "deltas": _json_safe_mapping(self.deltas),
            "unsupported_native_fields": list(self.unsupported_native_fields),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class BattleResourceOutcomeComponentReport:
    """Component-level availability/change report for structured outcomes."""

    source_record_count: int
    outcome_status_counts: Counter[str] = field(default_factory=Counter)
    terminal_result_counts: Counter[str] = field(default_factory=Counter)
    component_presence_counts: dict[str, Counter[str]] = field(default_factory=dict)
    component_change_counts: Counter[str] = field(default_factory=Counter)
    unsupported_native_field_counts: Counter[str] = field(default_factory=Counter)
    problem_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def build_battle_resource_outcome(
    start_raw: Mapping[str, Any],
    terminal_raw: Mapping[str, Any],
    *,
    battle_result: str | None = None,
) -> BattleResourceOutcome:
    """Build an auditable outcome from authoritative boundary snapshots."""

    start = extract_public_resource_snapshot(start_raw)
    terminal = extract_public_resource_snapshot(terminal_raw)
    result = battle_result or _battle_result(terminal_raw)
    result_field = (
        _available_field(result, "terminal_snapshot")
        if result
        else _missing_field("authoritative battle result is missing")
    )
    survived = _battle_survived(result)
    survived_field = (
        _available_field(survived, "battle_result")
        if survived is not None
        else _missing_field("battle survival is unavailable without terminal result")
    )
    terminal_hp = terminal.current_hp
    terminal_max_hp = terminal.max_hp
    deltas = _resource_deltas(start, terminal)
    unsupported = tuple(
        sorted(
            set(
                [
                    *_unsupported_fields(start),
                    *_unsupported_fields(terminal),
                ]
            )
        )
    )
    problems = tuple(
        dict.fromkeys(
            [
                *(f"start {field}" for field in _problem_fields(start)),
                *(f"terminal {field}" for field in _problem_fields(terminal)),
                *(
                    ["terminal battle result is missing"]
                    if result_field.status != FIELD_AVAILABLE
                    else []
                ),
            ]
        )
    )
    return BattleResourceOutcome(
        battle_result=result_field,
        battle_survived=survived_field,
        terminal_absolute_current_hp=terminal_hp,
        terminal_max_hp=terminal_max_hp,
        start=start,
        terminal=terminal,
        deltas=deltas,
        unsupported_native_fields=unsupported,
        problems=problems,
    )


def extract_public_resource_snapshot(raw: Mapping[str, Any]) -> PublicResourceSnapshot:
    """Extract only player-visible persistent resources from one raw snapshot."""

    current_hp = _first_int_field(
        raw,
        ("cur_hp", "current_hp", "battle_player_hp"),
        nested=(
            ("battle_player", ("current_hp", "cur_hp")),
            ("player", ("current_hp", "cur_hp")),
        ),
    )
    max_hp = _first_int_field(
        raw,
        ("max_hp", "maxHp"),
        nested=(
            ("battle_player", ("max_hp", "maxHp")),
            ("player", ("max_hp", "maxHp")),
        ),
    )
    gold = _first_int_field(
        raw,
        ("gold",),
        nested=(("battle_player", ("gold",)), ("player", ("gold",))),
    )
    potion_capacity = _first_int_field(
        raw,
        ("battle_potion_capacity", "potion_capacity"),
    )
    potion_slots = _potion_slots_field(raw)
    deck = _sequence_field(raw, ("deck", "master_deck"), "deck")
    curses = _curses_field(deck)
    relics = _sequence_field(raw, ("relics",), "relics")
    keys = _keys_field(raw)
    other = _other_resources_field(raw)
    return PublicResourceSnapshot(
        current_hp=current_hp,
        max_hp=max_hp,
        gold=gold,
        potion_capacity=potion_capacity,
        potion_slots=potion_slots,
        deck=deck,
        curses=curses,
        relics=relics,
        keys=keys,
        other_exposed_resources=other,
    )


def battle_resource_outcome_to_dict(outcome: BattleResourceOutcome) -> dict[str, Any]:
    """Return a JSON-safe current-schema outcome dictionary."""

    return outcome.to_dict()


def battle_resource_outcome_from_dict(raw: Mapping[str, Any]) -> BattleResourceOutcome:
    """Load a current-schema outcome dictionary after validation."""

    validate_battle_resource_outcome_dict(raw)
    return BattleResourceOutcome(
        schema_id=str(raw["schema_id"]),
        schema_version=_required_int(raw["schema_version"], "schema_version"),
        battle_result=_field_from_dict(raw["battle_result"], "battle_result"),
        battle_survived=_field_from_dict(raw["battle_survived"], "battle_survived"),
        terminal_absolute_current_hp=_field_from_dict(
            raw["terminal_absolute_current_hp"], "terminal_absolute_current_hp"
        ),
        terminal_max_hp=_field_from_dict(raw["terminal_max_hp"], "terminal_max_hp"),
        start=_snapshot_from_dict(raw["start"], "start"),
        terminal=_snapshot_from_dict(raw["terminal"], "terminal"),
        deltas=_mapping(raw["deltas"], "deltas"),
        unsupported_native_fields=tuple(
            _string_list(raw["unsupported_native_fields"], "unsupported_native_fields")
        ),
        problems=tuple(_string_list(raw["problems"], "problems")),
    )


def validate_battle_resource_outcome_dict(raw: Mapping[str, Any]) -> None:
    """Strictly validate the current outcome schema shape."""

    _reject_unknown_keys(raw, frozenset(_OUTCOME_FIELDS), "battle resource outcome")
    schema_id = raw.get("schema_id")
    if schema_id != BATTLE_RESOURCE_OUTCOME_SCHEMA_ID:
        raise ValueError(f"unsupported battle resource outcome schema {schema_id!r}")
    schema_version = _required_int(raw.get("schema_version"), "schema_version")
    if schema_version != BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported battle resource outcome schema version {schema_version}"
        )
    for name in (
        "battle_result",
        "battle_survived",
        "terminal_absolute_current_hp",
        "terminal_max_hp",
    ):
        _validate_field(raw.get(name), name)
    _validate_snapshot(raw.get("start"), "start")
    _validate_snapshot(raw.get("terminal"), "terminal")
    _mapping(raw.get("deltas"), "deltas")
    _string_list(raw.get("unsupported_native_fields"), "unsupported_native_fields")
    _string_list(raw.get("problems"), "problems")


def battle_resource_outcome_problems(
    status: str,
    outcome: Mapping[str, Any],
    *,
    label: str,
    require_available: bool = False,
) -> list[str]:
    """Return structural and missingness problems for an outcome reference."""

    problems: list[str] = []
    if status not in BATTLE_RESOURCE_OUTCOME_STATUSES:
        return [f"{label}: invalid structured outcome status {status!r}"]
    if status == BATTLE_RESOURCE_OUTCOME_AVAILABLE:
        try:
            parsed = battle_resource_outcome_from_dict(outcome)
        except ValueError as exc:
            return [f"{label}: invalid structured outcome: {exc}"]
        if require_available:
            if parsed.battle_result.status != FIELD_AVAILABLE:
                problems.append(f"{label}: terminal battle result is unavailable")
            elif not is_authoritative_terminal_battle_result(
                parsed.battle_result.value
            ):
                problems.append(f"{label}: terminal battle result is not authoritative")
        return list(dict.fromkeys(problems))
    if status == BATTLE_RESOURCE_OUTCOME_UNAVAILABLE:
        if set(outcome) - {"reason"}:
            problems.append(
                f"{label}: unavailable structured outcome has unsupported fields"
            )
        reason = outcome.get("reason")
        if not isinstance(reason, str) or not reason:
            problems.append(
                f"{label}: unavailable structured outcome reason is missing"
            )
    elif outcome:
        problems.append(f"{label}: legacy unavailable structured outcome must be empty")
    if require_available:
        problems.append(f"{label}: structured outcome is {status}")
    return problems


def legacy_unavailable_battle_resource_outcome() -> tuple[str, dict[str, Any]]:
    """Return the explicit marker for migrated artifacts without outcome data."""

    return BATTLE_RESOURCE_OUTCOME_LEGACY_UNAVAILABLE, {}


def unavailable_battle_resource_outcome(reason: str) -> tuple[str, dict[str, Any]]:
    """Return the explicit marker for a current nonterminal/unavailable outcome."""

    return BATTLE_RESOURCE_OUTCOME_UNAVAILABLE, {"reason": str(reason)}


def available_battle_resource_outcome(
    outcome: BattleResourceOutcome,
) -> tuple[str, dict[str, Any]]:
    """Return the status/dict pair for a current available outcome."""

    return BATTLE_RESOURCE_OUTCOME_AVAILABLE, battle_resource_outcome_to_dict(outcome)


def is_authoritative_terminal_battle_result(value: Any) -> bool:
    """Whether a raw battle outcome is a recognized terminal win/loss label."""

    return _battle_survived(str(value)) is not None


def build_battle_resource_outcome_component_report(
    rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> BattleResourceOutcomeComponentReport:
    """Summarize component availability and changes without scalar weights."""

    status_counts: Counter[str] = Counter()
    result_counts: Counter[str] = Counter()
    component_presence = {name: Counter() for name in _SNAPSHOT_COMPONENTS}
    change_counts: Counter[str] = Counter()
    unsupported_counts: Counter[str] = Counter()
    problem_counts: Counter[str] = Counter()
    problems: list[str] = []

    for index, (status, raw_outcome) in enumerate(rows):
        status_counts[status] += 1
        row_problems = battle_resource_outcome_problems(
            status,
            raw_outcome,
            label=f"row {index}",
            require_available=status == BATTLE_RESOURCE_OUTCOME_AVAILABLE,
        )
        problems.extend(row_problems)
        problem_counts.update(row_problems)
        if status != BATTLE_RESOURCE_OUTCOME_AVAILABLE or row_problems:
            continue
        outcome = battle_resource_outcome_from_dict(raw_outcome)
        result_value = outcome.battle_result.value
        result_counts[str(result_value)] += 1
        for name in _SNAPSHOT_COMPONENTS:
            field_value = getattr(outcome.terminal, name)
            component_presence[name][field_value.status] += 1
        for name, delta in outcome.deltas.items():
            if _changed_delta(delta):
                change_counts[name] += 1
        unsupported_counts.update(outcome.unsupported_native_fields)
        problem_counts.update(outcome.problems)

    return BattleResourceOutcomeComponentReport(
        source_record_count=len(rows),
        outcome_status_counts=status_counts,
        terminal_result_counts=result_counts,
        component_presence_counts=component_presence,
        component_change_counts=change_counts,
        unsupported_native_field_counts=unsupported_counts,
        problem_counts=problem_counts,
        problems=list(dict.fromkeys(problems)),
    )


def format_battle_resource_outcome_component_report(
    report: BattleResourceOutcomeComponentReport,
) -> str:
    """Format the component-level outcome report for stderr/PR evidence."""

    lines = [
        "Structured battle resource outcome audit",
        f"schema: {BATTLE_RESOURCE_OUTCOME_SCHEMA_ID} v{BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION}",
        f"records: {report.source_record_count}",
        f"audit passed: {'yes' if report.passed else 'no'}",
    ]
    _append_counter(lines, "outcome statuses", report.outcome_status_counts)
    _append_counter(lines, "terminal battle results", report.terminal_result_counts)
    lines.append("component availability:")
    if report.component_presence_counts:
        for name in sorted(report.component_presence_counts):
            counts = ", ".join(
                f"{status}={count}"
                for status, count in sorted(
                    report.component_presence_counts[name].items()
                )
            )
            lines.append(f"  {name}: {counts or '(none)'}")
    else:
        lines.append("  (none)")
    _append_counter(lines, "component changes", report.component_change_counts)
    _append_counter(
        lines, "unsupported native fields", report.unsupported_native_field_counts
    )
    _append_counter(lines, "problem counts", report.problem_counts)
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _resource_deltas(
    start: PublicResourceSnapshot,
    terminal: PublicResourceSnapshot,
) -> dict[str, Any]:
    return {
        "current_hp_delta": _numeric_delta(start.current_hp, terminal.current_hp),
        "max_hp_delta": _numeric_delta(start.max_hp, terminal.max_hp),
        "gold_delta": _numeric_delta(start.gold, terminal.gold),
        "potion_slots_delta": _collection_delta(
            start.potion_slots,
            terminal.potion_slots,
            excluded_fields=("slot_index",),
        ),
        "deck_delta": _collection_delta(
            start.deck,
            terminal.deck,
            excluded_fields=("deck_index", "uuid"),
        ),
        "curse_delta": _collection_delta(
            start.curses,
            terminal.curses,
            excluded_fields=("deck_index", "uuid"),
        ),
        "relic_delta": _collection_delta(
            start.relics,
            terminal.relics,
            excluded_fields=("relic_index",),
        ),
        "relic_counter_delta": _relic_counter_delta(start.relics, terminal.relics),
        "keys_delta": _keys_delta(start.keys, terminal.keys),
    }


def _first_int_field(
    raw: Mapping[str, Any],
    keys: Sequence[str],
    *,
    nested: Sequence[tuple[str, Sequence[str]]] = (),
) -> ResourceField:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return _available_field(value, key)
        if isinstance(value, float):
            return _available_field(int(value), key)
    for parent_key, child_keys in nested:
        parent = raw.get(parent_key)
        if not isinstance(parent, Mapping):
            continue
        for key in child_keys:
            value = parent.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return _available_field(value, f"{parent_key}.{key}")
            if isinstance(value, float):
                return _available_field(int(value), f"{parent_key}.{key}")
    return _missing_field(f"missing any of {', '.join(keys)}")


def _potion_slots_field(raw: Mapping[str, Any]) -> ResourceField:
    for key in ("potions", "battle_potions"):
        value = raw.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            slots = tuple(
                _json_safe_mapping(
                    {
                        **dict(item),
                        "slot_index": index,
                        "is_empty": _is_empty_potion(item),
                    }
                )
                for index, item in enumerate(value)
                if isinstance(item, Mapping)
            )
            return _available_field([dict(slot) for slot in slots], key)
    count_value = raw.get("battle_potion_count", raw.get("potion_count"))
    if isinstance(count_value, int) and not isinstance(count_value, bool):
        return ResourceField(
            status=FIELD_UNAVAILABLE,
            source="potion_count",
            reason="potion identities unavailable; only count is exposed",
            value={"known_count": count_value},
        )
    return _missing_field("missing potion slot identities")


def _sequence_field(
    raw: Mapping[str, Any],
    keys: Sequence[str],
    label: str,
) -> ResourceField:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return _available_field(
                [
                    _json_safe_mapping(item)
                    for item in value
                    if isinstance(item, Mapping)
                ],
                key,
            )
    return _missing_field(f"missing {label}")


def _curses_field(deck: ResourceField) -> ResourceField:
    if deck.status != FIELD_AVAILABLE:
        return ResourceField(status=deck.status, reason=deck.reason, source=deck.source)
    cards = deck.value if isinstance(deck.value, list) else []
    curses = [
        dict(card)
        for card in cards
        if str(card.get("type", "")).upper() == "CURSE"
        or str(card.get("card_type", "")).upper() == "CURSE"
    ]
    return _available_field(curses, "deck")


def _keys_field(raw: Mapping[str, Any]) -> ResourceField:
    values: dict[str, bool | None] = {}
    missing: list[str] = []
    for key in _KEY_NAMES:
        value = raw.get(key)
        if isinstance(value, bool):
            values[key] = value
        else:
            values[key] = None
            missing.append(key)
    if len(missing) == len(_KEY_NAMES):
        return _missing_field("missing key flags")
    return _available_field(values, "key_flags")


def _other_resources_field(raw: Mapping[str, Any]) -> ResourceField:
    values = {
        key: _json_safe_value(raw[key])
        for key in _OTHER_RESOURCE_KEYS
        if key in raw and _is_json_safe(raw[key])
    }
    return _available_field(values, "snapshot")


def _available_field(value: Any, source: str) -> ResourceField:
    return ResourceField(status=FIELD_AVAILABLE, value=value, source=source)


def _missing_field(reason: str) -> ResourceField:
    return ResourceField(status=FIELD_MISSING, reason=reason)


def _unsupported_fields(snapshot: PublicResourceSnapshot) -> list[str]:
    fields: list[str] = []
    for name in _SNAPSHOT_COMPONENTS:
        field_value = getattr(snapshot, name)
        if field_value.status == FIELD_UNAVAILABLE:
            fields.append(name)
    return fields


def _problem_fields(snapshot: PublicResourceSnapshot) -> list[str]:
    fields: list[str] = []
    for name in _SNAPSHOT_COMPONENTS:
        field_value = getattr(snapshot, name)
        if field_value.status != FIELD_AVAILABLE:
            fields.append(f"{name}: {field_value.reason or field_value.status}")
    return fields


def _battle_result(raw: Mapping[str, Any]) -> str | None:
    for key in ("completed_battle_outcome", "battle_outcome", "outcome"):
        value = raw.get(key)
        if isinstance(value, str) and value and value != "UNDECIDED":
            return value
    return None


def _battle_survived(result: str | None) -> bool | None:
    normalized = str(result or "").upper()
    if normalized in {"PLAYER_VICTORY", "VICTORY", "WIN", "PLAYER_WIN"}:
        return True
    if normalized in {"PLAYER_LOSS", "LOSS", "DEFEAT", "PLAYER_DEFEAT"}:
        return False
    return None


def _numeric_delta(start: ResourceField, terminal: ResourceField) -> dict[str, Any]:
    if start.status != FIELD_AVAILABLE or terminal.status != FIELD_AVAILABLE:
        return {"status": FIELD_MISSING, "value": None}
    if not isinstance(start.value, int) or not isinstance(terminal.value, int):
        return {"status": FIELD_MISSING, "value": None}
    return {"status": FIELD_AVAILABLE, "value": terminal.value - start.value}


def _collection_delta(
    start: ResourceField,
    terminal: ResourceField,
    *,
    excluded_fields: tuple[str, ...],
) -> dict[str, Any]:
    if start.status != FIELD_AVAILABLE or terminal.status != FIELD_AVAILABLE:
        return {"status": FIELD_MISSING, "added": [], "removed": []}
    start_items = _item_keys(start.value, excluded_fields)
    terminal_items = _item_keys(terminal.value, excluded_fields)
    start_counts = Counter(key for key, _ in start_items)
    terminal_counts = Counter(key for key, _ in terminal_items)
    representatives = dict([*start_items, *terminal_items])
    added = [
        representatives[key]
        for key in sorted(terminal_counts)
        for _ in range(max(0, terminal_counts[key] - start_counts[key]))
    ]
    removed = [
        representatives[key]
        for key in sorted(start_counts)
        for _ in range(max(0, start_counts[key] - terminal_counts[key]))
    ]
    return {"status": FIELD_AVAILABLE, "added": added, "removed": removed}


def _item_keys(
    raw_items: Any,
    excluded_fields: tuple[str, ...],
) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        return []
    keyed: list[tuple[str, dict[str, Any]]] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        comparable = {
            str(key): _json_safe_value(value)
            for key, value in item.items()
            if key not in excluded_fields
        }
        keyed.append((_canonical(comparable), comparable))
    return keyed


def _relic_counter_delta(
    start: ResourceField, terminal: ResourceField
) -> dict[str, Any]:
    if start.status != FIELD_AVAILABLE or terminal.status != FIELD_AVAILABLE:
        return {"status": FIELD_MISSING, "changes": []}
    start_by_id = {_entity_identity(item): item for item in _mapping_items(start.value)}
    end_by_id = {
        _entity_identity(item): item for item in _mapping_items(terminal.value)
    }
    changes: list[dict[str, Any]] = []
    for identity in sorted(start_by_id.keys() & end_by_id.keys()):
        before = _counter_value(start_by_id[identity])
        after = _counter_value(end_by_id[identity])
        if before == after:
            continue
        item = end_by_id[identity]
        changes.append(
            {
                "identity": identity,
                "id": item.get("id"),
                "name": item.get("name"),
                "before": before,
                "after": after,
            }
        )
    return {"status": FIELD_AVAILABLE, "changes": changes}


def _keys_delta(start: ResourceField, terminal: ResourceField) -> dict[str, Any]:
    if start.status != FIELD_AVAILABLE or terminal.status != FIELD_AVAILABLE:
        return {"status": FIELD_MISSING, "gained": [], "lost": []}
    start_values = start.value if isinstance(start.value, Mapping) else {}
    end_values = terminal.value if isinstance(terminal.value, Mapping) else {}
    gained = [
        key
        for key in _KEY_NAMES
        if start_values.get(key) is False and end_values.get(key) is True
    ]
    lost = [
        key
        for key in _KEY_NAMES
        if start_values.get(key) is True and end_values.get(key) is False
    ]
    return {"status": FIELD_AVAILABLE, "gained": gained, "lost": lost}


def _changed_delta(delta: Any) -> bool:
    if not isinstance(delta, Mapping) or delta.get("status") != FIELD_AVAILABLE:
        return False
    if delta.get("value") not in (None, 0):
        return True
    for key in ("added", "removed", "changes", "gained", "lost"):
        value = delta.get(key)
        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and value
        ):
            return True
    return False


def _is_empty_potion(item: Mapping[str, Any]) -> bool:
    for key in ("id", "name", "potion_id"):
        value = item.get(key)
        if value is None:
            continue
        return str(value) in _EMPTY_POTION_NAMES
    return False


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _entity_identity(item: Mapping[str, Any]) -> str:
    return _canonical({"id": item.get("id"), "name": item.get("name")})


def _counter_value(item: Mapping[str, Any]) -> int | None:
    for key in ("counter", "data"):
        value = item.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _validate_snapshot(raw: Any, label: str) -> None:
    snapshot = _mapping(raw, label)
    _reject_unknown_keys(snapshot, frozenset(_SNAPSHOT_COMPONENTS), label)
    for name in _SNAPSHOT_COMPONENTS:
        _validate_field(snapshot.get(name), f"{label}.{name}")


def _snapshot_from_dict(raw: Any, label: str) -> PublicResourceSnapshot:
    _validate_snapshot(raw, label)
    snapshot = _mapping(raw, label)
    return PublicResourceSnapshot(
        **{
            name: _field_from_dict(snapshot[name], f"{label}.{name}")
            for name in _SNAPSHOT_COMPONENTS
        }
    )


def _validate_field(raw: Any, label: str) -> None:
    field = _mapping(raw, label)
    status = field.get("status")
    if status not in FIELD_STATUSES:
        raise ValueError(f"{label} has invalid status {status!r}")
    allowed = (
        {"status", "value", "source"}
        if status == FIELD_AVAILABLE
        else {"status", "reason"}
    )
    _reject_unknown_keys(field, allowed, label)
    if status == FIELD_AVAILABLE:
        if "value" not in field:
            raise ValueError(f"{label} is available but missing value")
        if not isinstance(field.get("source"), str) or not field.get("source"):
            raise ValueError(f"{label} is available but missing source")
        _validate_json_safe(field["value"], f"{label}.value")
    elif not isinstance(field.get("reason"), str) or not field.get("reason"):
        raise ValueError(f"{label} is unavailable but missing reason")


def _field_from_dict(raw: Any, label: str) -> ResourceField:
    _validate_field(raw, label)
    field = _mapping(raw, label)
    status = str(field["status"])
    if status == FIELD_AVAILABLE:
        return ResourceField(
            status=status,
            value=field.get("value"),
            source=str(field.get("source")),
        )
    return ResourceField(status=status, reason=str(field.get("reason")))


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _reject_unknown_keys(
    data: Mapping[str, Any],
    allowed: frozenset[str],
    label: str,
) -> None:
    for key in data:
        if not isinstance(key, str):
            raise ValueError(f"{label} key {key!r} must be a string")
        if key not in allowed:
            raise ValueError(f"{label} has unknown key {key!r}")


def _required_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _validate_json_safe(value: Any, label: str) -> None:
    try:
        json.dumps(value, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-safe") from exc


def _is_json_safe(value: Any) -> bool:
    try:
        _validate_json_safe(value, "value")
    except ValueError:
        return False
    return True


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _append_counter(lines: list[str], title: str, values: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        lines.append(f"  {key}: {values[key]}")
