"""Fail-closed T092 parsing, pairing, and reporting for native tree telemetry.

The native companion is the sole reader of internal ``BattleContext`` values.
This module consumes its already-sanitized JSON-compatible output; it never
restores a checkpoint, invokes Search, or derives a feature from private state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

T092_SCHEMA_ID = "t092-internal-search-state-occurrence-v1"
T092_NATIVE_SCHEMA_ID = "native-battle-search-v2-internal-teacher-telemetry-v1"
T092_N_MINS = (1, 2, 4, 8, 16)
T092_CANARY_DOMAIN_SEPARATOR = 900492
T092_NATIVE_API = "StepSimulator.battle_search_v2_with_internal_teacher_telemetry.v1"
T092_NATIVE_PATCH_IDENTITY = "sts_lightspeed_battle_search_v2_internal_teacher_telemetry_v1"
T092_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/planner/t092-internal-search-state-telemetry",
    "commit": "07e1770cf0710d8c26719c153383d09e3bfd7686",
}
T092_FROZEN_TEACHER_CONFIG = {
    "schema_id": "t092-frozen-search-v2-teacher-config-v1",
    "implementation": "BattleScumSearcher2",
    "search_api": "StepSimulator.battle_search_v2",
    "information_regime": "full_simulator_state_oracle_like",
    "simulations": 400,
    "root_selection": "highest_mean",
    "include_potions": False,
    "policy_prior": None,
    "learned_leaf_value": None,
    "rollout": "playoutRandom",
    "terminal_utility": "evaluateEndState",
}
T092_PUBLIC_FORBIDDEN_TOKENS = (
    "checkpoint", "rng", "draw_order", "draworder", "actionqueue",
    "action_queue", "private", "native_node", "node_pointer", "uct",
    "evaluation_sum", "terminal_outcome", "path_fingerprint",
)


class T092Incomplete(ValueError):
    """The source does not meet T092's exact provenance/firewall contract."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise T092Incomplete(f"{label} must be an object")
    return value


def _action(value: object, label: str) -> dict[str, Any]:
    action = _mapping(value, label)
    required = ("scope", "bits", "kind", "idx1", "idx2", "idx3", "label")
    if set(action) != set(required):
        raise T092Incomplete(f"{label} lacks public action identity")
    _assert_public_only(action, label)
    if not isinstance(action["scope"], str) or action["scope"] != "battle":
        raise T092Incomplete(f"{label} is not a Battle public action")
    if not isinstance(action["kind"], str) or not action["kind"]:
        raise T092Incomplete(f"{label} has invalid kind")
    return {key: action[key] for key in required}


def _assert_public_only(value: object, path: str = "public_battle_projection") -> None:
    """Reject explicitly private field names everywhere in student-visible data."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise T092Incomplete(f"{path} has a non-string key")
            normalized = key.lower().replace("-", "_")
            if any(token in normalized for token in T092_PUBLIC_FORBIDDEN_TOKENS):
                raise T092Incomplete(f"{path} contains forbidden private field {key!r}")
            _assert_public_only(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_public_only(child, f"{path}[{index}]")


def public_fingerprint(public_projection: Mapping[str, Any], actions: Sequence[Mapping[str, Any]]) -> str:
    """Versioned fingerprint of exactly public state and ordered searchable actions."""

    _assert_public_only(public_projection)
    return hashlib.sha256(_canonical({
        "schema_id": "t092-public-decision-fingerprint-v1",
        "public_tactical_v2": public_projection,
        "teacher_searchable_actions": list(actions),
    }).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class T092Occurrence:
    native_identity: Mapping[str, Any]
    frozen_teacher_config: Mapping[str, Any]
    source_identity: str
    source_group: str
    split: str
    parent_root_decision_identity: str
    occurrence_identity: str
    tree_depth: int
    expansion_ordinal: int
    public_battle_projection: Mapping[str, Any]
    searchable_actions: tuple[Mapping[str, Any], ...]
    excluded_actions: tuple[Mapping[str, Any], ...]
    search_work: Mapping[str, Any]
    telemetry_cost: Mapping[str, Any]

    @property
    def fingerprint(self) -> str:
        return public_fingerprint(
            self.public_battle_projection,
            [row["action"] for row in self.searchable_actions],
        )


def validate_retained_occurrence(
    value: Mapping[str, Any], *, source_identity: str | None = None,
    source_group: str | None = None, split: str | None = None,
    parent_root_decision_identities: set[str] | None = None,
) -> T092Occurrence:
    """Revalidate one serialized occurrence without native execution.

    This is the retained-artifact boundary used by the canary validator as well
    as the native-report parser. It admits exactly the dataclass surface, not a
    superset with private or inferred fields.
    """

    required = {
        "native_identity", "frozen_teacher_config", "source_identity",
        "source_group", "split", "parent_root_decision_identity",
        "occurrence_identity", "tree_depth", "expansion_ordinal",
        "public_battle_projection", "searchable_actions", "excluded_actions",
        "search_work", "telemetry_cost",
    }
    if set(value) != required:
        raise T092Incomplete("retained internal occurrence fields are incomplete")
    if dict(_mapping(value["native_identity"], "occurrence native identity")) != T092_NATIVE_IDENTITY:
        raise T092Incomplete("retained occurrence native identity is conflicting")
    if dict(_mapping(value["frozen_teacher_config"], "occurrence teacher configuration")) != T092_FROZEN_TEACHER_CONFIG:
        raise T092Incomplete("retained occurrence teacher configuration is conflicting")
    identity = value["source_identity"]
    group = value["source_group"]
    retained_split = value["split"]
    parent = value["parent_root_decision_identity"]
    occurrence = value["occurrence_identity"]
    if (
        not all(isinstance(item, str) and item for item in (identity, group, retained_split, parent, occurrence))
        or group not in {"A", "B", "C"}
        or (source_identity is not None and identity != source_identity)
        or (source_group is not None and group != source_group)
        or (split is not None and retained_split != split)
        or (parent_root_decision_identities is not None and parent not in parent_root_decision_identities)
    ):
        raise T092Incomplete("retained occurrence source provenance is incomplete")
    depth, ordinal = value["tree_depth"], value["expansion_ordinal"]
    if (
        isinstance(depth, bool) or not isinstance(depth, int) or depth < 1
        or isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal <= 0
    ):
        raise T092Incomplete("retained occurrence tree metadata is invalid")
    projection = _mapping(value["public_battle_projection"], "retained public projection")
    _assert_public_only(projection)
    raw_actions = value["searchable_actions"]
    if not isinstance(raw_actions, Sequence) or isinstance(raw_actions, (str, bytes, bytearray)):
        raise T092Incomplete("retained teacher-searchable actions are unavailable")
    actions: list[Mapping[str, Any]] = []
    action_keys: set[str] = set()
    for child in raw_actions:
        child_mapping = _mapping(child, "retained teacher-searchable child")
        if set(child_mapping) != {"action", "visits", "mean_value"}:
            raise T092Incomplete("retained teacher-searchable child fields are incomplete")
        action = _action(child_mapping["action"], "retained teacher-searchable action")
        key = _canonical(action)
        if key in action_keys:
            raise T092Incomplete("retained teacher-searchable action identity is duplicate")
        action_keys.add(key)
        visits, mean = child_mapping["visits"], child_mapping["mean_value"]
        if (
            isinstance(visits, bool) or not isinstance(visits, int) or visits < 0
            or (visits == 0 and mean is not None)
            or (visits > 0 and not _finite(mean))
        ):
            raise T092Incomplete("retained child visit/mean contract is invalid")
        actions.append({"action": action, "visits": visits, "mean_value": None if visits == 0 else float(mean)})
    raw_excluded = value["excluded_actions"]
    if not isinstance(raw_excluded, Sequence) or isinstance(raw_excluded, (str, bytes, bytearray)):
        raise T092Incomplete("retained teacher-excluded actions are unavailable")
    excluded: list[Mapping[str, Any]] = []
    for entry in raw_excluded:
        item = _mapping(entry, "retained teacher-excluded action")
        if set(item) != {"action", "exclusion_reason"}:
            raise T092Incomplete("retained teacher-excluded action fields are incomplete")
        reason = item["exclusion_reason"]
        if not isinstance(reason, str) or not reason:
            raise T092Incomplete("retained teacher-excluded action lacks a reason")
        excluded.append({"action": _action(item["action"], "retained teacher-excluded action"), "exclusion_reason": reason})
    search_work = _mapping(value["search_work"], "retained Search work")
    if set(search_work) != {"root_visits", "native_simulator_steps", "simulations_requested"}:
        raise T092Incomplete("retained Search work fields are incomplete")
    if (
        search_work["simulations_requested"] != 400
        or any(
            isinstance(search_work[key], bool)
            or not isinstance(search_work[key], int)
            or search_work[key] < 0
            for key in ("root_visits", "native_simulator_steps")
        )
    ):
        raise T092Incomplete("retained Search work metadata is invalid")
    telemetry_cost = _mapping(value["telemetry_cost"], "retained telemetry cost")
    if set(telemetry_cost) != {"telemetry_extraction_transition_count", "collection_phase"}:
        raise T092Incomplete("retained telemetry cost fields are incomplete")
    transitions = telemetry_cost["telemetry_extraction_transition_count"]
    if (
        isinstance(transitions, bool) or not isinstance(transitions, int) or transitions < 0
        or telemetry_cost["collection_phase"] != "post_search_private_state_replay"
    ):
        raise T092Incomplete("retained telemetry cost metadata is invalid")
    return T092Occurrence(
        dict(value["native_identity"]), dict(value["frozen_teacher_config"]), identity,
        group, retained_split, parent, occurrence, depth, ordinal, dict(projection),
        tuple(actions), tuple(excluded), dict(search_work), dict(telemetry_cost),
    )


def parse_native_occurrences(
    native_report: Mapping[str, Any], *, source_identity: str, source_group: str,
    split: str, parent_root_decision_identity: str,
    native_identity: Mapping[str, Any] | None = None,
) -> list[T092Occurrence]:
    """Bind one native result to immutable source provenance and sanitize rows."""

    if native_report.get("schema_id") != "native-battle-search-root-v1":
        raise T092Incomplete("native report schema is not the accepted root schema")
    if native_report.get("native_api") != T092_NATIVE_API or native_report.get("patch_identity") != T092_NATIVE_PATCH_IDENTITY:
        raise T092Incomplete("native telemetry identity is not the T092 companion")
    if native_report.get("information_regime") != "full_simulator_state_oracle_like":
        raise T092Incomplete("native report information regime is not frozen Search-v2")
    if native_report.get("simulations_requested") != 400 or native_report.get("include_potions") is not False:
        raise T092Incomplete("native report is not frozen Search-v2@400 no-potion evidence")
    if native_identity is None or dict(native_identity) != T092_NATIVE_IDENTITY:
        raise T092Incomplete("exact task-scoped native identity is missing or conflicting")
    teacher_config = _mapping(native_report.get("teacher_config"), "frozen teacher configuration")
    if dict(teacher_config) != T092_FROZEN_TEACHER_CONFIG:
        raise T092Incomplete("frozen teacher configuration is missing or conflicting")
    telemetry_root = _mapping(native_report.get("tree_internal_telemetry"), "tree telemetry")
    native = _mapping(telemetry_root.get("internal_teacher_telemetry"), "internal telemetry")
    if native.get("schema_id") != T092_NATIVE_SCHEMA_ID or native.get("schema_version") != 1:
        raise T092Incomplete("unsupported internal telemetry schema")
    if native.get("collection_phase") != "post_search_private_state_replay":
        raise T092Incomplete("telemetry extraction is not separated private replay")
    if native.get("search_rng_or_counter_mutated") is not False or native.get("raw_private_state_exported") is not False:
        raise T092Incomplete("native telemetry does not prove private-boundary safety")
    rows = native.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise T092Incomplete("internal telemetry rows must be a list")
    if source_group not in {"A", "B", "C"} or not all(isinstance(x, str) and x for x in (source_identity, split, parent_root_decision_identity)):
        raise T092Incomplete("source provenance is incomplete")
    search_work = {
        key: native_report.get(key)
        for key in ("root_visits", "native_simulator_steps", "simulations_requested")
    }
    telemetry_cost = {
        "telemetry_extraction_transition_count": native.get("telemetry_extraction_transition_count"),
        "collection_phase": native["collection_phase"],
    }
    if not isinstance(telemetry_cost["telemetry_extraction_transition_count"], int):
        raise T092Incomplete("telemetry extraction cost is unavailable")
    result: list[T092Occurrence] = []
    seen: set[str] = set()
    for raw in rows:
        row = _mapping(raw, "internal occurrence")
        occurrence = row.get("occurrence_identity")
        if not isinstance(occurrence, str) or not occurrence or occurrence in seen:
            raise T092Incomplete("occurrence identity is missing or duplicate")
        seen.add(occurrence)
        if row.get("input_state") not in {"PLAYER_NORMAL", "CARD_SELECT"}:
            raise T092Incomplete("candidate is not a stable player-decision state")
        depth, ordinal = row.get("tree_depth"), row.get("expansion_ordinal")
        if not isinstance(depth, int) or depth < 1 or not isinstance(ordinal, int) or ordinal <= 0:
            raise T092Incomplete("candidate tree metadata is invalid")
        projection = _mapping(row.get("public_battle_projection"), "public projection")
        _assert_public_only(projection)
        raw_actions = row.get("teacher_searchable_actions")
        if not isinstance(raw_actions, Sequence) or isinstance(raw_actions, (str, bytes, bytearray)):
            raise T092Incomplete("teacher-searchable actions are unavailable")
        actions: list[Mapping[str, Any]] = []
        action_keys: set[str] = set()
        for child in raw_actions:
            child_mapping = _mapping(child, "teacher-searchable child")
            action = _action(child_mapping.get("action"), "teacher-searchable action")
            key = _canonical(action)
            if key in action_keys:
                raise T092Incomplete("teacher-searchable action identity is duplicate")
            action_keys.add(key)
            visits, mean = child_mapping.get("visits"), child_mapping.get("mean_value")
            if not isinstance(visits, int) or visits < 0 or (visits == 0 and mean is not None) or (visits > 0 and not _finite(mean)):
                raise T092Incomplete("child visit/mean contract is invalid")
            actions.append({"action": action, "visits": visits, "mean_value": None if visits == 0 else float(mean)})
        raw_excluded = row.get("public_teacher_excluded_actions")
        if not isinstance(raw_excluded, Sequence) or isinstance(raw_excluded, (str, bytes, bytearray)):
            raise T092Incomplete("public teacher-excluded actions are unavailable")
        excluded: list[Mapping[str, Any]] = []
        for entry in raw_excluded:
            item = _mapping(entry, "public teacher-excluded action")
            reason = item.get("exclusion_reason")
            if not isinstance(reason, str) or not reason:
                raise T092Incomplete("teacher-excluded action lacks a reason")
            excluded.append({"action": _action(item.get("action"), "teacher-excluded action"), "exclusion_reason": reason})
        normalized = T092Occurrence(
            dict(native_identity),
            dict(teacher_config),
            source_identity,
            source_group,
            split,
            parent_root_decision_identity,
            occurrence,
            depth,
            ordinal,
            dict(projection),
            tuple(actions),
            tuple(excluded),
            search_work,
            telemetry_cost,
        )
        result.append(
            validate_retained_occurrence(
                asdict(normalized),
                source_identity=source_identity,
                source_group=source_group,
                split=split,
                parent_root_decision_identities={parent_root_decision_identity},
            )
        )
    if native.get("candidate_count") != len(result):
        raise T092Incomplete("native candidate count disagrees with rows")
    return result


def support_pairs(occurrence: T092Occurrence, n_min: int) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Return ordered non-tie comparisons; zero-visit children stay unknown."""

    if n_min not in T092_N_MINS:
        raise ValueError("T092 support threshold is not registered")
    supported = [row for row in occurrence.searchable_actions if row["visits"] >= n_min and _finite(row["mean_value"])]
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for left_index, left in enumerate(supported):
        for right in supported[left_index + 1:]:
            delta = float(left["mean_value"]) - float(right["mean_value"])
            if abs(delta) <= 1e-9:
                continue
            pairs.append((left, right) if delta > 0 else (right, left))
    return pairs


def summarize_occurrences(occurrences: Sequence[T092Occurrence]) -> dict[str, Any]:
    """Compute registered thresholds and deterministic leakage-safe deduplication."""

    by_fingerprint: dict[str, list[T092Occurrence]] = defaultdict(list)
    for occurrence in occurrences:
        by_fingerprint[occurrence.fingerprint].append(occurrence)
    collisions = {fingerprint for fingerprint, rows in by_fingerprint.items() if len({row.split for row in rows}) > 1}
    thresholds: dict[str, Any] = {}
    for minimum in T092_N_MINS:
        eligible = [row for fingerprint, rows in by_fingerprint.items() if fingerprint not in collisions for row in rows if support_pairs(row, minimum)]
        canonical: dict[tuple[str, str], T092Occurrence] = {}
        for row in sorted(eligible, key=lambda value: (value.split, value.source_identity, value.parent_root_decision_identity, value.occurrence_identity)):
            canonical.setdefault((row.split, row.fingerprint), row)
        retained = list(canonical.values())
        thresholds[str(minimum)] = {
            "raw_occurrences_with_pairs": len(eligible),
            "leakage_safe_unique_examples": len(retained),
            "retained_ordered_non_tie_pairs": sum(len(support_pairs(row, minimum)) for row in retained),
            "by_source_group": dict(Counter(row.source_group for row in retained)),
        }
    excluded_kinds = Counter(entry["action"]["kind"] for row in occurrences for entry in row.excluded_actions)
    return {
        "schema_id": "t092-internal-search-state-density-report-v1",
        "occurrence_count": len(occurrences),
        "public_fingerprint_count": len(by_fingerprint),
        "cross_split_fingerprint_count": len(collisions),
        "teacher_excluded_action_kinds": dict(sorted(excluded_kinds.items())),
        "thresholds": thresholds,
    }


def select_t092_canary_sources(source_rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Select exactly four occurrence-safe identities from each T087 group."""

    grouped: dict[str, list[Mapping[str, Any]]] = {"A": [], "B": [], "C": []}
    for row in source_rows:
        source = _mapping(row, "canary source")
        group, identity = source.get("source_group"), source.get("source_identity")
        if group not in grouped or not isinstance(identity, str) or not identity:
            raise T092Incomplete("canary source identity/group is invalid")
        grouped[group].append(source)
    selected: list[Mapping[str, Any]] = []
    for group, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: hashlib.sha256(f"{T092_CANARY_DOMAIN_SEPARATOR}:{row['source_identity']}".encode()).hexdigest())
        if len(ordered) < 4:
            raise T092Incomplete(f"canary group {group} has fewer than four sources")
        selected.extend(ordered[:4])
    return selected


def compare_semantic_parity(off: Mapping[str, Any], on: Mapping[str, Any]) -> list[str]:
    """Compare registered root semantics while deliberately excluding telemetry cost."""

    fields = ("root_rows", "root_visits", "native_simulator_steps", "best_action_value", "min_action_value", "outcome_player_hp")
    return [field for field in fields if off.get(field) != on.get(field)]
