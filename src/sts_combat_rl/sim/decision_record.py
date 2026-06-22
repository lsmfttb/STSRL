"""Current decision-record schema and action identity helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction


DECISION_RECORD_SCHEMA_VERSION = 3
DECISION_SOURCE_KINDS = (
    "natural_run",
    "stratified_training",
    "constructed_supplement",
    "paired_counterfactual",
    "live_communicationmod",
    "unknown",
)

DECISION_RECORD_FIELD_NAMES = (
    "record_schema_version",
    "seed",
    "step_index",
    "screen_state",
    "snapshot_features",
    "legal_action_features",
    "legal_action_kinds",
    "legal_action_identities",
    "eligible_action_indices",
    "chosen_action_index",
    "chosen_action_id",
    "chosen_action_identity",
    "chosen_action_kind",
    "terminal_after_step",
    "controller_provenance",
    "source_metadata",
    "feature_schema_id",
    "tactical_state",
    "tactical_legal_actions",
    "public_context_status",
    "public_run_context",
)


@dataclass(frozen=True)
class ActionIdentity:
    """Stable public identity for one occurrence in a legal-action list."""

    action_id: int | str | None
    occurrence: int
    kind: str
    label: str
    stable_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "occurrence": self.occurrence,
            "kind": self.kind,
            "label": self.label,
            "stable_id": self.stable_id,
        }


@dataclass(frozen=True, kw_only=True)
class DecisionRecord:
    """Current persisted schema for one policy decision."""

    seed: int | None
    step_index: int
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    chosen_action_index: int
    chosen_action_kind: str
    terminal_after_step: bool
    chosen_action_id: int | str | None = None
    record_schema_version: int = DECISION_RECORD_SCHEMA_VERSION
    legal_action_identities: list[dict[str, Any]] = field(default_factory=list)
    chosen_action_identity: dict[str, Any] = field(default_factory=dict)
    controller_provenance: dict[str, Any] = field(default_factory=dict)
    source_metadata: dict[str, Any] = field(default_factory=dict)
    feature_schema_id: str = "public-tactical-v2"
    tactical_state: dict[str, Any] = field(default_factory=dict)
    tactical_legal_actions: list[dict[str, Any]] = field(default_factory=list)
    public_context_status: str = "available"
    public_run_context: dict[str, Any] = field(default_factory=dict)


def action_identities_for_actions(
    actions: Sequence[SimulatorAction],
) -> list[ActionIdentity]:
    """Return occurrence-disambiguated identities for a legal-action list."""

    counts: dict[str, int] = {}
    identities: list[ActionIdentity] = []
    for action in actions:
        action_id = _json_safe_action_id(action.action_id)
        key = _action_id_key(action_id)
        occurrence = counts.get(key, 0)
        counts[key] = occurrence + 1
        stable_id = stable_action_identity_id(
            action_id=action_id,
            occurrence=occurrence,
            kind=action.kind,
        )
        identities.append(
            ActionIdentity(
                action_id=action_id,
                occurrence=occurrence,
                kind=str(action.kind),
                label=str(action.label),
                stable_id=stable_id,
            )
        )
    return identities


def action_identity_dicts_for_actions(
    actions: Sequence[SimulatorAction],
) -> list[dict[str, Any]]:
    """Return JSON-safe action identity dictionaries for artifact storage."""

    return [identity.to_dict() for identity in action_identities_for_actions(actions)]


def stable_action_identity_id(
    *,
    action_id: int | str | None,
    occurrence: int,
    kind: str,
) -> str:
    """Build the canonical stable id for one action occurrence."""

    return json.dumps(
        {
            "action_id": _json_safe_action_id(action_id),
            "kind": str(kind),
            "occurrence": int(occurrence),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def action_identity_from_dict(raw: Mapping[str, Any]) -> ActionIdentity:
    """Load an action identity from a JSON row."""

    action_id = _json_safe_action_id(raw.get("action_id"))
    occurrence = _int(raw.get("occurrence"))
    kind = str(raw.get("kind", ""))
    label = str(raw.get("label", ""))
    stable_id = str(
        raw.get(
            "stable_id",
            stable_action_identity_id(
                action_id=action_id,
                occurrence=occurrence,
                kind=kind,
            ),
        )
    )
    expected = stable_action_identity_id(
        action_id=action_id,
        occurrence=occurrence,
        kind=kind,
    )
    if stable_id != expected:
        raise ValueError("action identity stable_id does not match its fields")
    return ActionIdentity(
        action_id=action_id,
        occurrence=occurrence,
        kind=kind,
        label=label,
        stable_id=stable_id,
    )


def find_action_index_by_identity(
    actions: Sequence[SimulatorAction],
    identity: Mapping[str, Any],
) -> int:
    """Find the unique legal-action index matching a stored identity."""

    target = action_identity_from_dict(identity).stable_id
    matches = [
        index
        for index, candidate in enumerate(action_identities_for_actions(actions))
        if candidate.stable_id == target
    ]
    if len(matches) != 1:
        raise ValueError(
            f"action identity matched {len(matches)} legal actions, expected 1"
        )
    return matches[0]


def legacy_index_action_identities(
    legal_action_kinds: Sequence[str],
) -> list[dict[str, Any]]:
    """Build explicit index-only identities for legacy rows without action ids."""

    identities: list[dict[str, Any]] = []
    for index, kind in enumerate(legal_action_kinds):
        action_id = None
        stable_id = stable_action_identity_id(
            action_id=action_id,
            occurrence=index,
            kind=str(kind),
        )
        identities.append(
            {
                "action_id": action_id,
                "occurrence": index,
                "kind": str(kind),
                "label": "",
                "stable_id": stable_id,
            }
        )
    return identities


def source_metadata_from_snapshot(
    raw_snapshot: object,
    *,
    seed: int | None,
    source_kind: str = "natural_run",
) -> dict[str, Any]:
    """Extract rule-defined source metadata available on current main."""

    if source_kind not in DECISION_SOURCE_KINDS:
        raise ValueError(f"unknown decision source kind: {source_kind}")
    raw = raw_snapshot if isinstance(raw_snapshot, Mapping) else {}
    effective_seed = seed
    if effective_seed is None:
        effective_seed = _optional_int(_first_value(raw, "seed", "run_seed"))
    return {
        "source_kind": source_kind,
        "distribution_kind": source_kind,
        "seed": effective_seed,
        "ascension": _first_value(raw, "ascension", "ascension_level"),
        "act": _first_value(raw, "act"),
        "floor": _first_value(raw, "floor_num", "floor"),
        "room_type": _first_value(raw, "room_type", "screen_state"),
        "encounter_id": _encounter_id(raw),
    }


def decision_record_kwargs(record: Any) -> dict[str, Any]:
    """Return current decision-record fields from a compatible object."""

    return {name: getattr(record, name) for name in DECISION_RECORD_FIELD_NAMES}


def decision_record_problems(record: DecisionRecord, *, label: str) -> list[str]:
    """Return structural problems for a current decision record."""

    problems: list[str] = []
    legal_count = len(record.legal_action_features)
    if record.record_schema_version != DECISION_RECORD_SCHEMA_VERSION:
        problems.append(
            f"{label}: unsupported record schema version {record.record_schema_version}"
        )
    if len(record.legal_action_kinds) != legal_count:
        problems.append(
            f"{label}: {len(record.legal_action_features)} action rows but "
            f"{len(record.legal_action_kinds)} action kinds"
        )
    problems.extend(decision_record_identity_problems(record, label=label))
    _append_index_problems(
        record.eligible_action_indices,
        legal_count,
        f"{label}: eligible action index",
        problems,
    )
    if len(set(record.eligible_action_indices)) != len(record.eligible_action_indices):
        problems.append(f"{label}: eligible action indices contain duplicates")
    if record.chosen_action_index < 0 or record.chosen_action_index >= legal_count:
        problems.append(
            f"{label}: chosen action index {record.chosen_action_index} outside "
            f"{legal_count} legal actions"
        )
    elif record.chosen_action_index not in record.eligible_action_indices:
        problems.append(f"{label}: chosen action index is not eligible")
    elif (
        record.chosen_action_index < len(record.legal_action_kinds)
        and record.chosen_action_kind
        != record.legal_action_kinds[record.chosen_action_index]
    ):
        problems.append(f"{label}: chosen action kind does not match chosen action")
    if not record.controller_provenance:
        problems.append(f"{label}: controller provenance is missing")
    if not record.source_metadata:
        problems.append(f"{label}: source metadata is missing")
    problems.extend(_tactical_feature_problems(record, label=label))
    problems.extend(_public_context_problems(record, label=label))
    return problems


def _public_context_problems(record: DecisionRecord, *, label: str) -> list[str]:
    from sts_combat_rl.sim.public_context_artifacts import (
        public_context_artifact_problems,
    )

    return public_context_artifact_problems(
        status=record.public_context_status,
        context=record.public_run_context,
        label=label,
        require_available=True,
        require_candidate_actions=True,
    )


def _tactical_feature_problems(record: DecisionRecord, *, label: str) -> list[str]:
    """Validate v2 structured tactical inputs without creating an import cycle."""

    from sts_combat_rl.sim.features import (
        TACTICAL_FEATURE_SCHEMA_ID,
        tactical_action_problems,
        tactical_state_problems,
    )

    problems: list[str] = []
    if record.feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        problems.append(
            f"{label}: unsupported tactical feature schema {record.feature_schema_id!r}"
        )
        return problems
    if not record.tactical_state:
        problems.append(f"{label}: tactical state is missing")
    else:
        problems.extend(
            f"{label}: {problem}"
            for problem in tactical_state_problems(record.tactical_state)
        )
    if len(record.tactical_legal_actions) != len(record.legal_action_features):
        problems.append(
            f"{label}: {len(record.tactical_legal_actions)} tactical actions but "
            f"{len(record.legal_action_features)} action rows"
        )
    problems.extend(
        f"{label}: {problem}"
        for problem in tactical_action_problems(record.tactical_legal_actions)
    )
    return problems


def decision_record_identity_problems(
    record: DecisionRecord,
    *,
    label: str,
) -> list[str]:
    """Return replay-identity problems for one current decision record."""

    problems: list[str] = []
    legal_count = len(record.legal_action_features)
    if not record.legal_action_identities:
        problems.append(f"{label}: legal action identities are missing")
    elif len(record.legal_action_identities) != legal_count:
        problems.append(
            f"{label}: {len(record.legal_action_identities)} action identities "
            f"but {legal_count} action rows"
        )
    if not record.chosen_action_identity:
        problems.append(f"{label}: chosen action identity is missing")
    legal_identities, chosen_identity = _append_action_identity_problems(
        record.legal_action_identities,
        record.chosen_action_identity,
        label,
        problems,
    )
    _append_identity_action_consistency_problems(
        legal_identities,
        record.legal_action_kinds,
        label,
        problems,
    )
    if (
        record.chosen_action_id is not None
        and chosen_identity is not None
        and _json_safe_action_id(record.chosen_action_id) != chosen_identity.action_id
    ):
        problems.append(
            f"{label}: chosen action id does not match chosen action identity"
        )
    if (
        record.legal_action_identities
        and record.chosen_action_identity
        and 0 <= record.chosen_action_index < len(record.legal_action_identities)
    ):
        expected_identity = record.legal_action_identities[record.chosen_action_index]
        if record.chosen_action_identity != expected_identity:
            problems.append(f"{label}: chosen action identity does not match index")
    return problems


def _append_action_identity_problems(
    legal_action_identities: Sequence[Mapping[str, Any]],
    chosen_action_identity: Mapping[str, Any],
    label: str,
    problems: list[str],
) -> tuple[list[ActionIdentity | None], ActionIdentity | None]:
    parsed_legal_identities: list[ActionIdentity | None] = []
    for index, identity in enumerate(legal_action_identities):
        if not isinstance(identity, Mapping):
            problems.append(f"{label}: legal action identity {index} is not an object")
            parsed_legal_identities.append(None)
            continue
        if "stable_id" not in identity:
            problems.append(
                f"{label}: legal action identity {index} is missing stable_id"
            )
        try:
            parsed_legal_identities.append(action_identity_from_dict(identity))
        except ValueError as exc:
            problems.append(f"{label}: legal action identity {index} is invalid: {exc}")
            parsed_legal_identities.append(None)
    parsed_chosen_identity: ActionIdentity | None = None
    if chosen_action_identity:
        if not isinstance(chosen_action_identity, Mapping):
            problems.append(f"{label}: chosen action identity is not an object")
            return parsed_legal_identities, parsed_chosen_identity
        if "stable_id" not in chosen_action_identity:
            problems.append(f"{label}: chosen action identity is missing stable_id")
        try:
            parsed_chosen_identity = action_identity_from_dict(chosen_action_identity)
        except ValueError as exc:
            problems.append(f"{label}: chosen action identity is invalid: {exc}")
    return parsed_legal_identities, parsed_chosen_identity


def _append_identity_action_consistency_problems(
    legal_identities: Sequence[ActionIdentity | None],
    legal_action_kinds: Sequence[str],
    label: str,
    problems: list[str],
) -> None:
    expected_occurrences: dict[str, int] = {}
    for index, identity in enumerate(legal_identities):
        if identity is None:
            continue
        if (
            index < len(legal_action_kinds)
            and identity.kind != legal_action_kinds[index]
        ):
            problems.append(
                f"{label}: legal action identity {index} kind {identity.kind!r} "
                f"does not match action kind {legal_action_kinds[index]!r}"
            )
        action_id_key = _action_id_key(identity.action_id)
        expected_occurrence = expected_occurrences.get(action_id_key, 0)
        if identity.occurrence != expected_occurrence:
            problems.append(
                f"{label}: legal action identity {index} occurrence "
                f"{identity.occurrence} does not match expected "
                f"{expected_occurrence} for action id {identity.action_id!r}"
            )
        expected_occurrences[action_id_key] = expected_occurrence + 1


def _append_index_problems(
    indices: Sequence[int],
    legal_count: int,
    label: str,
    problems: list[str],
) -> None:
    if not indices:
        problems.append(f"{label} list is empty")
    for index in indices:
        if index < 0 or index >= legal_count:
            problems.append(f"{label} {index} outside {legal_count} legal actions")


def _encounter_id(raw_snapshot: Mapping[str, Any]) -> Any:
    direct = _first_value(
        raw_snapshot,
        "encounter_id",
        "encounter",
        "monster_group_id",
    )
    if direct is not None:
        return direct
    monsters = raw_snapshot.get("battle_monsters")
    if not isinstance(monsters, Sequence) or isinstance(monsters, (str, bytes)):
        return None
    labels: list[str] = []
    for monster in monsters:
        if not isinstance(monster, Mapping):
            continue
        label = _first_value(monster, "id", "monster_id", "name")
        if label is not None:
            labels.append(str(label))
    return "+".join(labels) if labels else None


def _first_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _action_id_key(action_id: int | str | None) -> str:
    return json.dumps(action_id, sort_keys=True, separators=(",", ":"))


def _json_safe_action_id(value: Any) -> int | str | None:
    if value is None or isinstance(value, (int, str)):
        return value
    return str(value)


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return _int(value)
