"""Offline, fail-closed T091 audit of retained T090 teacher telemetry.

This module consumes materialized JSON only.  It never restores a checkpoint,
imports the native extension, or invokes Search.  In particular, unvisited
root actions remain unknown rather than becoming negative examples.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

T091_TASK_ID = "T091"
T091_SCHEMA_ID = "t091-battle-teacher-data-surface-report-v1"
T091_MANIFEST_SCHEMA_ID = "t091-retention-manifest-v1"
T091_APPROVED_SPEC_COMMIT = "88a0e6dfd71f57f7d8dd5bbe3ef7c6a37ec4c162"
T091_PUBLICATION_BASE = "ca95317ca0f21d5c07cfa0a9c845a26a66548bb4"
T091_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
}
T091_N_MINS = (1, 2, 4, 8, 16)
T091_INPUT_HASHES = {
    "raw-teacher-rows.json": "68de0626fe8cd50386e354641ecc65a3f3e8a0673fb5c7fe4b7e91b0c87b6a94",
    "raw-decision-provenance.json": "a72f15bbf02e46026ae5afa9bdf4d9693b32c74e8ce28a39212171f67c753939",
    "source-execution-ledger.json": "503f2a363aaf8a1d30dfe4d2b20b4d9e93a6f2c16c5cca7650447ce7c3c21635",
    "target-table.json": "16d1eb92038bdd6f52fb8d02f637c89a244316a0478c3086e6f09d3091fa791a",
    "status.json": "3933f6a55b2a8705dea72f8be83b3b47575542a8dff4d87b37826eae94933e6f",
    "shard-reuse-provenance.json": "52837d3c40269fe8ee18b401364326557258a3ad8db8d182cec83f5c8fd19caf",
}


class T091Incomplete(ValueError):
    """The immutable input evidence cannot support the registered audit."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _identity(value: object) -> str:
    if not isinstance(value, Mapping):
        raise T091Incomplete("action identity must be an object")
    stable = value.get("stable_id")
    return stable if isinstance(stable, str) and stable else _canonical(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _bucket(legal_count: int) -> str:
    if legal_count == 2:
        return "2"
    if legal_count <= 4:
        return "3-4"
    if legal_count <= 8:
        return "5-8"
    if legal_count <= 16:
        return "9-16"
    return "17+"


def _distribution(values: Sequence[float | int]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "max": None,
        }
    ordered = sorted(values)

    def percentile(p: float) -> float:
        index = (len(ordered) - 1) * p
        low, high = math.floor(index), math.ceil(index)
        return float(ordered[low] + (ordered[high] - ordered[low]) * (index - low))

    return {
        "count": len(ordered),
        "mean": float(statistics.fmean(ordered)),
        "median": percentile(0.5),
        "p75": percentile(0.75),
        "p90": percentile(0.9),
        "p95": percentile(0.95),
        "max": ordered[-1],
    }


def _iter_json_array(path: Path) -> Iterator[object]:
    """Incrementally decode the large T090 raw array without a giant heap peak."""

    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as stream:
        buffer = ""
        started = False
        eof = False
        while not eof:
            chunk = stream.read(1024 * 1024)
            if chunk:
                buffer += chunk
            else:
                eof = True
            position = 0
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if not started:
                    if position == len(buffer):
                        break
                    if buffer[position] != "[":
                        raise T091Incomplete(f"{path.name} must be a JSON array")
                    started = True
                    position += 1
                    continue
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position == len(buffer):
                    break
                if buffer[position] == "]":
                    return
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if eof:
                        raise T091Incomplete(f"{path.name} is truncated JSON") from None
                    break
                yield value
                position = end
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer):
                    if buffer[position] == ",":
                        position += 1
                    elif buffer[position] != "]":
                        raise T091Incomplete(
                            f"{path.name} has an invalid array separator"
                        )
            buffer = buffer[position:]
        raise T091Incomplete(f"{path.name} lacks a closing array bracket")


@dataclass
class _Stats:
    decisions: int = 0
    single_action: int = 0
    multi_action: int = 0
    legal_counts: list[int] = field(default_factory=list)
    s0: int = 0
    s1_counts: list[int] = field(default_factory=list)
    s1_fractions: list[float] = field(default_factory=list)
    thresholds: dict[int, dict[str, Any]] = field(
        default_factory=lambda: {
            n: {
                "two_supported": 0,
                "supported_actions": 0,
                "ordered_pairs": 0,
                "pairs_per_multi": [],
                "fractions": [],
            }
            for n in T091_N_MINS
        }
    )

    def add(
        self,
        legal_count: int,
        s1: int,
        s0: bool,
        threshold_rows: Mapping[int, tuple[int, int]],
    ) -> None:
        self.decisions += 1
        if legal_count == 1:
            self.single_action += 1
            return
        self.multi_action += 1
        self.legal_counts.append(legal_count)
        self.s0 += int(s0)
        self.s1_counts.append(s1)
        self.s1_fractions.append(s1 / legal_count)
        for n, (supported, pairs) in threshold_rows.items():
            row = self.thresholds[n]
            row["two_supported"] += int(supported >= 2)
            row["supported_actions"] += supported
            row["ordered_pairs"] += pairs
            row["pairs_per_multi"].append(pairs)
            row["fractions"].append(supported / legal_count)

    def report(self) -> dict[str, Any]:
        threshold: dict[str, Any] = {}
        for n, row in self.thresholds.items():
            threshold[str(n)] = {
                "decisions_with_at_least_two_supported_actions": row["two_supported"],
                "fraction_of_multi_action_decisions_with_at_least_two_supported_actions": (
                    row["two_supported"] / self.multi_action
                    if self.multi_action
                    else None
                ),
                "total_supported_actions": row["supported_actions"],
                "total_ordered_non_tie_pairs": row["ordered_pairs"],
                "ordered_pairs_per_multi_action_decision": _distribution(
                    row["pairs_per_multi"]
                ),
                "supported_legal_fraction": _distribution(row["fractions"]),
            }
        return {
            "total_decisions": self.decisions,
            "single_action_decisions": self.single_action,
            "multi_action_decisions": self.multi_action,
            "legal_action_count": _distribution(self.legal_counts),
            "s0_complete_root_q": {
                "count": self.s0,
                "fraction_of_multi_action": self.s0 / self.multi_action
                if self.multi_action
                else None,
            },
            "s1_visited_action_support": {
                "supported_action_count": _distribution(self.s1_counts),
                "supported_legal_fraction": _distribution(self.s1_fractions),
            },
            "s2_partial_pairwise_support": threshold,
        }


def _read_mapping(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise T091Incomplete(f"{path.name} must be a JSON object")
    return value


def _validate_inputs(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[Any], Mapping[str, Any], Mapping[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for filename, expected_hash in T091_INPUT_HASHES.items():
        path = root / filename
        if not path.is_file():
            raise T091Incomplete(f"missing accepted T090 artifact: {filename}")
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise T091Incomplete(
                f"{filename} SHA-256 differs from accepted T090 evidence"
            )
        identities[filename] = {
            "path": str(path),
            "sha256": actual_hash,
            "size_bytes": path.stat().st_size,
        }
    provenance_value = json.loads(
        (root / "raw-decision-provenance.json").read_text(encoding="utf-8")
    )
    if not isinstance(provenance_value, list):
        raise T091Incomplete("raw decision provenance must be a JSON array")
    ledger = _read_mapping(root / "source-execution-ledger.json")
    target = _read_mapping(root / "target-table.json")
    return identities, provenance_value, ledger, target


def _static_internal_audit() -> dict[str, Any]:
    """Bounded source audit of the pinned native implementation, not an export."""

    return {
        "schema_id": "t091-current-search-internal-surface-feasibility-v1",
        "conclusion": "CURRENT_SEARCH_INTERNAL_SURFACE_FEASIBLE",
        "scope": "static code/architecture audit only; no internal state was exported",
        "pinned_native_identity": T091_NATIVE_IDENTITY,
        "code_anchors": [
            {
                "path": "include/sim/search/BattleScumSearcher2.h",
                "anchor": "struct Node { simulationCount, evaluationSum, vector<Edge> edges; }",
                "finding": "nodes retain child-edge tree statistics but do not own a persistent BattleContext.",
            },
            {
                "path": "src/sim/search/BattleScumSearcher2.cpp",
                "anchor": "BattleScumSearcher2::step",
                "finding": "each traversal reconstructs curState from rootState and applies the search-stack action path before inspecting/expanding its current node.",
            },
            {
                "path": "src/sim/search/BattleScumSearcher2.cpp",
                "anchor": "BattleScumSearcher2::enumerateActionsForNode",
                "finding": "only PLAYER_NORMAL and CARD_SELECT are enumerated as legal player-input states; other input states are not decision-export candidates.",
            },
            {
                "path": "src/sim/search/BattleScumSearcher2.cpp",
                "anchor": "BattleScumSearcher2::playoutRandom",
                "finding": "rollout uses a temporary node and clears its edges; rollout-only transient states have no durable tree node/edge statistics.",
            },
            {
                "path": "src/sts_combat_rl/sim/lightspeed.py",
                "anchor": "LightSpeedAdapter.battle_search_v2",
                "finding": "the accepted Python boundary returns root telemetry only, so a new read-only companion telemetry payload is needed to transport any internal public projection.",
            },
        ],
        "stable_node_criterion": "A candidate is feasible only at an expanded tree node whose reconstructed BattleContext is nonterminal and inputState is PLAYER_NORMAL or CARD_SELECT, after the preceding Action::execute has completed; ActionQueue/transient non-input states are excluded.",
        "public_projection_and_legal_actions": "Feasible with bounded telemetry-only work: the reconstructed state is already passed to enumerateActionsForNode, but current accepted root-only Python extraction has no internal projection callback/payload.",
        "provenance": "Feasible: source/root identity plus the traversal action path and parent edge index can be attached at expansion time. This is path provenance, not an exact transposition identity claim.",
        "action_queue_boundary": "No ActionQueue semantic identity or exact transposition is required merely to emit a public decision example; candidates must fail closed when not at the enumerated stable input states. T079's opaque ActionQueue restriction remains in force for exact-state reuse claims.",
        "statistics_analogue": "For an expanded internal node, each child Edge::node has simulationCount and evaluationSum, so child mean evaluationSum/simulationCount and visits are a root-row analogue. Fresh local Search is not required for those existing subtree statistics, but a newly reached unexpanded node has no populated child support until Search expands it.",
        "implementation_boundary": "T091 does not add that companion telemetry/export. A successor would need to preserve Search traversal, selection, rollout, backup, and root selection exactly while copying already-observed public state/action/statistics.",
    }


def _selection_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Comparable descriptive columns for registered selection-bias subsets."""

    legal_counts = [int(row["legal_count"]) for row in rows]
    legal_kinds: Counter[str] = Counter()
    selected_kinds: Counter[str] = Counter()
    source_groups: Counter[str] = Counter()
    buckets: Counter[str] = Counter()
    terminal_outcomes: Counter[str] = Counter()
    for row in rows:
        legal_kinds.update(str(kind) for kind in row["legal_kinds"])
        selected_kinds[str(row["selected_kind"])] += 1
        source_groups[str(row["source_group"])] += 1
        buckets[_bucket(int(row["legal_count"]))] += 1
        terminal_outcomes[str(row["terminal_outcome"])] += 1
    return {
        "decision_count": len(rows),
        "legal_action_count": _distribution(legal_counts),
        "source_group": dict(sorted(source_groups.items())),
        "legal_action_count_bucket": dict(sorted(buckets.items())),
        "legal_action_kind_composition": dict(sorted(legal_kinds.items())),
        "selected_action_kind": dict(sorted(selected_kinds.items())),
        "battle_turn_or_decision_depth": "UNAVAILABLE (not retained as a separate public/formal field; decision_identity is not repurposed as depth)",
        "terminal_outcome_source_level_descriptive": dict(
            sorted(terminal_outcomes.items())
        ),
    }


def analyze_t090_teacher_surface(t090_root: Path) -> dict[str, Any]:
    """Validate immutable evidence and deterministically calculate every T091 surface."""

    t090_root = t090_root.resolve()
    identities, provenance, ledger, target = _validate_inputs(t090_root)
    entries = ledger.get("entries")
    if not isinstance(entries, list) or len(entries) != 413:
        raise T091Incomplete("T090 ledger must contain exactly 413 source entries")
    source_ledger: dict[str, Mapping[str, Any]] = {}
    source_group_counts: Counter[str] = Counter()
    total_simulations = 0
    total_wall_clock = 0.0
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise T091Incomplete("T090 ledger entry is invalid")
        source = entry.get("source_identity")
        if not isinstance(source, str) or source in source_ledger:
            raise T091Incomplete("T090 ledger source identity is missing or duplicated")
        if (
            entry.get("source_group") not in {"A", "B", "C"}
            or entry.get("completed") is not True
            or entry.get("terminal_reached") is not True
            or entry.get("restore_public_legal_parity") is not True
        ):
            raise T091Incomplete("T090 ledger completion/parity provenance is invalid")
        if entry.get("native_identity") != T091_NATIVE_IDENTITY:
            raise T091Incomplete(
                "T090 ledger native identity differs from pinned identity"
            )
        cost = entry.get("cost")
        if (
            not isinstance(cost, Mapping)
            or not isinstance(cost.get("search_simulation_count"), int)
            or not _finite(cost.get("wall_clock_time_s"))
        ):
            raise T091Incomplete("T090 retained cost provenance is invalid")
        total_simulations += int(cost["search_simulation_count"])
        total_wall_clock += float(cost["wall_clock_time_s"])
        source_ledger[source] = entry
        source_group_counts[str(entry["source_group"])] += 1
    if total_simulations <= 0 or total_wall_clock <= 0:
        raise T091Incomplete("T090 retained cost provenance is nonpositive")
    if source_group_counts != {"A": 93, "B": 192, "C": 128}:
        raise T091Incomplete("T090 ledger source-group counts differ from T087")

    observed = target.get("observed_decisions")
    if not isinstance(observed, list) or len(observed) != 6369:
        raise T091Incomplete("target table must retain all 6,369 observed decisions")
    if (
        target.get("task_id") != "T090"
        or target.get("schema_id") != "t090-search-v2-action-utility-targets-v1"
    ):
        raise T091Incomplete("target table schema identity differs from T090")
    target_provenance = target.get("target_provenance")
    if not isinstance(target_provenance, Mapping) or target_provenance.get(
        "public_input_contract"
    ) != {
        "action_features": "public-tactical-v2-derived",
        "legal_action_identity_contract": "ordered-public-legal-action-identity-v1",
        "schema_id": "public-tactical-v2",
        "schema_version": 2,
    }:
        raise T091Incomplete("target table public input provenance differs from T090")
    fingerprints: dict[str, tuple[str, str, str, str]] = {}
    for row in observed:
        if not isinstance(row, Mapping):
            raise T091Incomplete("target observed-decision row is invalid")
        decision, source, group, split, fingerprint = (
            row.get(key)
            for key in (
                "decision_identity",
                "source_identity",
                "source_group",
                "split",
                "public_fingerprint",
            )
        )
        if not all(
            isinstance(item, str) and item
            for item in (decision, source, group, split, fingerprint)
        ):
            raise T091Incomplete(
                "target table lacks retained public fingerprint provenance"
            )
        fingerprints[str(decision)] = (
            str(fingerprint),
            str(source),
            str(group),
            str(split),
        )
    if len(fingerprints) != 6369:
        raise T091Incomplete("target observed decision identities are duplicated")

    selected: dict[str, Mapping[str, Any]] = {}
    for row in provenance:
        if not isinstance(row, Mapping):
            raise T091Incomplete("raw decision provenance row is invalid")
        decision = row.get("decision_identity")
        native = row.get("native_search")
        action = row.get("selected_action_identity")
        if (
            not isinstance(decision, str)
            or not isinstance(native, Mapping)
            or not isinstance(action, Mapping)
        ):
            raise T091Incomplete("raw decision provenance is malformed")
        if (
            native.get("native_identity") != T091_NATIVE_IDENTITY
            or native.get("native_api") != "StepSimulator.battle_search_v2.v1"
            or native.get("simulations") != 400
            or native.get("include_potions") is not False
            or native.get("policy_prior_callback") is not None
            or native.get("leaf_value_callback") is not None
            or row.get("selection_rule") != "highest_mean"
        ):
            raise T091Incomplete(
                "raw decision provenance differs from frozen Search-v2@400"
            )
        if decision in selected:
            raise T091Incomplete("raw decision provenance duplicates a decision")
        selected[decision] = action
    if set(selected) != set(fingerprints):
        raise T091Incomplete("raw provenance and target-table decisions differ")

    all_stats, group_stats = _Stats(), {group: _Stats() for group in ("A", "B", "C")}
    bucket_stats = {bucket: _Stats() for bucket in ("2", "3-4", "5-8", "9-16", "17+")}
    kind_coverage: dict[str, Counter[str]] = defaultdict(Counter)
    fp_occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    n4_candidates: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    integrity: list[str] = []
    s3_unmapped_by_group: Counter[str] = Counter()
    raw_count = 0

    for raw in _iter_json_array(t090_root / "raw-teacher-rows.json"):
        raw_count += 1
        if not isinstance(raw, Mapping):
            raise T091Incomplete("raw teacher row is invalid")
        decision, source, group = (
            raw.get("decision_identity"),
            raw.get("source_identity"),
            raw.get("source_group"),
        )
        public, root_rows = raw.get("public_input"), raw.get("root_rows")
        if (
            not isinstance(decision, str)
            or not isinstance(source, str)
            or group not in group_stats
            or not isinstance(public, Mapping)
            or not isinstance(root_rows, list)
        ):
            raise T091Incomplete(
                "raw teacher row lacks required identity/public/root fields"
            )
        fingerprint_info = fingerprints.get(decision)
        if (
            fingerprint_info is None
            or fingerprint_info[1] != source
            or fingerprint_info[2] != group
            or source not in source_ledger
        ):
            raise T091Incomplete(
                "raw row conflicts with retained source/fingerprint provenance"
            )
        identities_raw, kinds_raw = (
            public.get("legal_action_identities"),
            public.get("legal_action_kinds"),
        )
        if (
            public.get("schema_id") != "public-tactical-v2"
            or public.get("schema_version") != 2
            or not isinstance(identities_raw, list)
            or not isinstance(kinds_raw, list)
            or len(identities_raw) != len(kinds_raw)
        ):
            raise T091Incomplete("raw row public input contract differs from T090")
        legal_ids = [_identity(item) for item in identities_raw]
        if len(set(legal_ids)) != len(legal_ids):
            raise T091Incomplete("raw row has duplicate legal action identities")
        legal_count = len(legal_ids)
        if legal_count < 1:
            raise T091Incomplete("raw row has no legal actions")
        roots: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for root in root_rows:
            if not isinstance(root, Mapping):
                integrity.append(f"{decision}: non-object root row")
                continue
            try:
                roots[_identity(root.get("legal_action_identity"))].append(root)
            except T091Incomplete:
                integrity.append(f"{decision}: malformed root identity")
        supported: list[tuple[str, str, int, float]] = []
        complete = True
        for index, (action_id, kind_raw) in enumerate(
            zip(legal_ids, kinds_raw, strict=True)
        ):
            kind = kind_raw if isinstance(kind_raw, str) and kind_raw else "UNAVAILABLE"
            kind_coverage[kind]["legal_instances"] += 1
            mapped = roots.get(action_id, [])
            if len(mapped) != 1:
                complete = False
                if len(mapped) > 1:
                    integrity.append(
                        f"{decision}: duplicate root mapping for action {index}"
                    )
                continue
            visits, mean = mapped[0].get("visits"), mapped[0].get("mean_value")
            valid = (
                isinstance(visits, int)
                and not isinstance(visits, bool)
                and visits > 0
                and _finite(mean)
            )
            if not valid:
                complete = False
                continue
            kind_coverage[kind]["positive_visit_instances"] += 1
            supported.append((action_id, kind, int(visits), float(mean)))
        extra = set(roots) - set(legal_ids)
        if extra:
            integrity.append(f"{decision}: root contains non-legal action")
            complete = False
        s1 = len(supported)
        threshold_rows: dict[int, tuple[int, int]] = {}
        pair_signs_n4: dict[str, int] = {}
        for minimum in T091_N_MINS:
            threshold_supported = [item for item in supported if item[2] >= minimum]
            pairs = 0
            for left_index, left in enumerate(threshold_supported):
                for right in threshold_supported[left_index + 1 :]:
                    delta = left[3] - right[3]
                    if abs(delta) <= 1e-9:
                        continue
                    pairs += 1
                    if minimum == 4:
                        kind_coverage[left[1]]["n4_pair_participations"] += 1
                        kind_coverage[right[1]]["n4_pair_participations"] += 1
                        ordered_ids = sorted((left[0], right[0]))
                        sign = 1 if (left[0] == ordered_ids[0]) == (delta > 0) else -1
                        pair_signs_n4[_canonical(ordered_ids)] = sign
            threshold_rows[minimum] = (len(threshold_supported), pairs)
        all_stats.add(legal_count, s1, complete and legal_count > 1, threshold_rows)
        group_stats[str(group)].add(
            legal_count, s1, complete and legal_count > 1, threshold_rows
        )
        if legal_count > 1:
            bucket_stats[_bucket(legal_count)].add(
                legal_count, s1, complete, threshold_rows
            )
        chosen = selected[decision]
        chosen_id = _identity(chosen)
        if chosen_id not in legal_ids:
            integrity.append(
                f"{decision}: selected action is not exactly mapped legal action"
            )
            s3_unmapped_by_group[str(group)] += 1
        else:
            kind_at_selection = str(kinds_raw[legal_ids.index(chosen_id)])
        fingerprint, _fingerprint_source, _fingerprint_group, _fingerprint_split = (
            fingerprint_info
        )
        split = next((entry.get("split") for entry in (source_ledger[source],)), None)
        if (
            not isinstance(split, str)
            or source_ledger[source].get("source_group") != group
            or fingerprint_info[3] != split
        ):
            raise T091Incomplete("ledger split is missing")
        fp_occurrences[fingerprint].append(
            {
                "decision_identity": decision,
                "source_identity": source,
                "source_group": group,
                "split": split,
                "selected_action": chosen_id,
                "pair_signs_n4": pair_signs_n4,
            }
        )
        supported_n4, pair_count_n4 = threshold_rows[4]
        if legal_count > 1 and pair_count_n4 > 0:
            n4_candidates.append(
                {
                    "fingerprint": fingerprint,
                    "decision_identity": decision,
                    "source_identity": source,
                    "source_group": group,
                    "split": split,
                    "pairs": pair_count_n4,
                }
            )
        if legal_count > 1:
            terminal = source_ledger[source].get("terminal_evidence")
            outcome = (
                terminal.get("outcome")
                if isinstance(terminal, Mapping)
                else "UNAVAILABLE"
            )
            selection_rows.append(
                {
                    "legal_count": legal_count,
                    "legal_kinds": [str(kind) for kind in kinds_raw],
                    "selected_kind": kind_at_selection
                    if chosen_id in legal_ids
                    else "UNMAPPED",
                    "source_group": group,
                    "terminal_outcome": outcome
                    if isinstance(outcome, str)
                    else "UNAVAILABLE",
                    "s0": complete,
                    "n4_pair_supported": supported_n4 >= 2,
                }
            )
    if raw_count != 6369:
        raise T091Incomplete(f"raw teacher-row count is {raw_count}, expected 6369")

    full = all_stats.report()
    if (
        full["multi_action_decisions"] != 6210
        or full["s0_complete_root_q"]["count"] != 309
    ):
        raise T091Incomplete("S0 failed to reproduce the accepted 309 / 6,210 result")
    for source, entry in source_ledger.items():
        _ = source, entry

    repeated = []
    for fingerprint, rows in sorted(fp_occurrences.items()):
        if len(rows) < 2:
            continue
        actions = {row["selected_action"] for row in rows}
        conflicts = 0
        pair_values: dict[str, set[int]] = defaultdict(set)
        for row in rows:
            for pair, sign in row["pair_signs_n4"].items():
                pair_values[pair].add(sign)
        conflicts = sum(len(signs) > 1 for signs in pair_values.values())
        repeated.append(
            {
                "public_fingerprint": fingerprint,
                "occurrence_count": len(rows),
                "distinct_teacher_selected_actions": len(actions),
                "selected_action_disagreement_rate": 1
                - max(Counter(row["selected_action"] for row in rows).values())
                / len(rows),
                "pairwise_preference_sign_conflicts": conflicts,
                "source_group_distribution": dict(
                    sorted(Counter(row["source_group"] for row in rows).items())
                ),
                "split_distribution": dict(
                    sorted(Counter(row["split"] for row in rows).items())
                ),
            }
        )
    cross_split_fingerprints = {
        fingerprint
        for fingerprint, rows in fp_occurrences.items()
        if len({row["split"] for row in rows}) > 1
    }
    by_split_fp: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in n4_candidates:
        if candidate["fingerprint"] not in cross_split_fingerprints:
            by_split_fp[
                (str(candidate["split"]), str(candidate["fingerprint"]))
            ].append(candidate)
    retained_n4 = [
        min(rows, key=lambda row: str(row["decision_identity"]))
        for _, rows in sorted(by_split_fp.items())
    ]
    gate_unique_examples = len(retained_n4)
    gate_pairs = sum(int(row["pairs"]) for row in retained_n4)
    n4 = full["s2_partial_pairwise_support"]["4"]
    bucket_reports = {
        key: value.report() for key, value in bucket_stats.items() if value.multi_action
    }
    kind_report = {
        kind: dict(sorted(counts.items()))
        for kind, counts in sorted(kind_coverage.items())
    }
    kind_gate = [
        kind
        for kind, counts in kind_coverage.items()
        if counts["legal_instances"] >= 50
    ]
    kind_gate_passed = [
        kind for kind in kind_gate if kind_coverage[kind]["n4_pair_participations"] > 0
    ]
    group_reports = {group: stats.report() for group, stats in group_stats.items()}
    source_cost: dict[str, Counter[str]] = defaultdict(Counter)
    for item in entries:
        assert isinstance(item, Mapping)
        group = str(item["source_group"])
        cost = item["cost"]
        assert isinstance(cost, Mapping)
        source_cost[group]["search_simulation_count"] += int(
            cost["search_simulation_count"]
        )
        source_cost[group]["wall_clock_time_s"] += float(cost["wall_clock_time_s"])
    cost_report: dict[str, Any] = {}
    for label, statistics_row in {
        "all": {
            "search_simulation_count": total_simulations,
            "wall_clock_time_s": total_wall_clock,
        },
        **source_cost,
    }.items():
        denominator = float(statistics_row["search_simulation_count"])

        def per_1000(value: float, *, _denominator: float = denominator) -> float:
            return value * 1000 / _denominator

        wall = float(statistics_row["wall_clock_time_s"])
        candidate_stats = full if label == "all" else group_reports[label]
        cost_report[label] = {
            "retained_search_simulations": int(denominator),
            "retained_wall_clock_seconds": wall,
            "usable_s0_roots_per_1000_search_simulations": per_1000(
                candidate_stats["s0_complete_root_q"]["count"]
            ),
            "n_min_4_pair_supported_roots_per_1000_search_simulations": per_1000(
                candidate_stats["s2_partial_pairwise_support"]["4"][
                    "decisions_with_at_least_two_supported_actions"
                ]
            ),
            "n_min_4_ordered_pairs_per_1000_search_simulations": per_1000(
                candidate_stats["s2_partial_pairwise_support"]["4"][
                    "total_ordered_non_tie_pairs"
                ]
            ),
            "chosen_action_labels_per_1000_search_simulations": per_1000(
                candidate_stats["multi_action_decisions"]
            ),
            "usable_s0_roots_per_wall_clock_second": candidate_stats[
                "s0_complete_root_q"
            ]["count"]
            / wall,
            "n_min_4_pair_supported_roots_per_wall_clock_second": candidate_stats[
                "s2_partial_pairwise_support"
            ]["4"]["decisions_with_at_least_two_supported_actions"]
            / wall,
            "n_min_4_ordered_pairs_per_wall_clock_second": candidate_stats[
                "s2_partial_pairwise_support"
            ]["4"]["total_ordered_non_tie_pairs"]
            / wall,
            "chosen_action_labels_per_wall_clock_second": candidate_stats[
                "multi_action_decisions"
            ]
            / wall,
        }
    gate_checks = {
        "raw_n4_two_supported_at_least_70_percent": n4[
            "fraction_of_multi_action_decisions_with_at_least_two_supported_actions"
        ]
        >= 0.70,
        "each_source_group_n4_two_supported_at_least_60_percent": {
            group: report["s2_partial_pairwise_support"]["4"][
                "fraction_of_multi_action_decisions_with_at_least_two_supported_actions"
            ]
            >= 0.60
            for group, report in group_reports.items()
        },
        "unique_examples_after_fingerprint_exclusion_and_within_split_dedup_at_least_3500": gate_unique_examples
        >= 3500,
        "ordered_non_tie_pairs_after_fingerprint_exclusion_and_within_split_dedup_at_least_10000": gate_pairs
        >= 10000,
        "median_n4_supported_legal_fraction_at_least_0_40": n4[
            "supported_legal_fraction"
        ]["median"]
        >= 0.40,
        "branching_buckets_at_least_100_have_n4_pair_supported_coverage_at_least_30_percent": {},
        "action_kinds_with_at_least_50_legal_instances_participate_at_least_90_percent": len(
            kind_gate_passed
        )
        / len(kind_gate)
        >= 0.90
        if kind_gate
        else False,
        "provenance_and_information_boundary_violations_zero": not integrity,
    }
    for bucket, report in bucket_reports.items():
        count = report["multi_action_decisions"]
        if count >= 100:
            gate_checks[
                "branching_buckets_at_least_100_have_n4_pair_supported_coverage_at_least_30_percent"
            ][bucket] = (
                report["s2_partial_pairwise_support"]["4"][
                    "fraction_of_multi_action_decisions_with_at_least_two_supported_actions"
                ]
                >= 0.30
            )
    flattened = [
        gate_checks["raw_n4_two_supported_at_least_70_percent"],
        *gate_checks["each_source_group_n4_two_supported_at_least_60_percent"].values(),
        gate_checks[
            "unique_examples_after_fingerprint_exclusion_and_within_split_dedup_at_least_3500"
        ],
        gate_checks[
            "ordered_non_tie_pairs_after_fingerprint_exclusion_and_within_split_dedup_at_least_10000"
        ],
        gate_checks["median_n4_supported_legal_fraction_at_least_0_40"],
        *gate_checks[
            "branching_buckets_at_least_100_have_n4_pair_supported_coverage_at_least_30_percent"
        ].values(),
        gate_checks[
            "action_kinds_with_at_least_50_legal_instances_participate_at_least_90_percent"
        ],
        gate_checks["provenance_and_information_boundary_violations_zero"],
    ]
    terminal = (
        "ROOT_PARTIAL_SUPERVISION_DENSE_ENOUGH"
        if all(flattened)
        else "ROOT_PARTIAL_SUPERVISION_TOO_SPARSE_OR_BIASED"
    )
    internal = _static_internal_audit()
    all_multi_selection = _selection_summary(selection_rows)
    s0_selection = _selection_summary([row for row in selection_rows if row["s0"]])
    n4_selection = _selection_summary(
        [row for row in selection_rows if row["n4_pair_supported"]]
    )
    return {
        "schema_id": T091_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T091_TASK_ID,
        "approved_spec_commit": T091_APPROVED_SPEC_COMMIT,
        "publication_base": T091_PUBLICATION_BASE,
        "input_artifacts": identities,
        "pinned_native_identity": T091_NATIVE_IDENTITY,
        "validation": {
            "valid": not integrity,
            "violations": integrity,
            "s0_reproduction": {
                "expected": {
                    "complete_roots": 309,
                    "multi_action_decisions": 6210,
                    "fraction": 309 / 6210,
                },
                "observed": full["s0_complete_root_q"],
                "passed": True,
            },
        },
        "density": {
            "all": full,
            "by_source_group": group_reports,
            "by_legal_action_count_bucket": bucket_reports,
            "action_kind_coverage": kind_report,
            "s3_chosen_action_mapping": {
                "valid_multi_action_decisions": full["multi_action_decisions"],
                "mapped_selected_actions": full["multi_action_decisions"]
                - sum("selected action" in item for item in integrity),
                "coverage": 1
                - sum("selected action" in item for item in integrity)
                / full["multi_action_decisions"],
                "by_source_group": {
                    group: {
                        "valid_multi_action_decisions": report[
                            "multi_action_decisions"
                        ],
                        "mapped_selected_actions": report["multi_action_decisions"]
                        - s3_unmapped_by_group[group],
                        "coverage": 1
                        - s3_unmapped_by_group[group]
                        / report["multi_action_decisions"],
                    }
                    for group, report in group_reports.items()
                },
            },
        },
        "cost_normalization": cost_report,
        "selection_bias": {
            "scope": "descriptive distribution analysis only; no causal/reward claim",
            "all_multi_action": all_multi_selection,
            "s0_eligible": s0_selection,
            "n4_pair_supported": n4_selection,
            "note": "Each subset is presented with identical columns for direct comparison. Terminal outcomes are repeated source-level retained diagnostics, not decision-level labels or causal outcomes.",
        },
        "public_fingerprint_ambiguity_lower_bound": {
            "status": "AVAILABLE",
            "fingerprint_schema_id": target.get("collision_deduplication", {}).get(
                "fingerprint_schema_id"
            )
            if isinstance(target.get("collision_deduplication"), Mapping)
            else "UNAVAILABLE",
            "distinct_fingerprints": len(fp_occurrences),
            "repeated_fingerprint_count": len(repeated),
            "repeated_fingerprints": repeated,
            "warning": "Observed conflicts are a lower bound only; absence of a conflict does not establish public-information-set uniqueness or remove the T034 warning.",
        },
        "leakage_safe_n4_deduplication": {
            "cross_split_fingerprint_count": len(cross_split_fingerprints),
            "raw_pair_examples": len(n4_candidates),
            "retained_unique_pair_examples": gate_unique_examples,
            "retained_ordered_non_tie_pairs": gate_pairs,
            "rule": "exclude any fingerprint observed across splits, then choose lexicographically smallest decision_identity within each remaining split/fingerprint.",
        },
        "viability_gate": {
            "n_min": 4,
            "checks": gate_checks,
            "all_passed": all(flattened),
        },
        "internal_search_state_feasibility_audit": internal,
        "terminal_classification": terminal,
        "successor_decision": "separate partial-ranking Battle-student gate"
        if terminal == "ROOT_PARTIAL_SUPERVISION_DENSE_ENOUGH"
        else "bounded internal Search-state telemetry/data-surface task",
        "interpretation_boundary": "This measures retained Search-exposed supervision density only; it does not establish student learnability, Search improvement, complete-run improvement, or normal-information optimality.",
    }


def write_t091_artifacts(t090_root: Path, output_dir: Path) -> dict[str, Path]:
    """Write deterministic scientific-quality reports and their local retention manifest."""

    report = analyze_t090_teacher_surface(t090_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "t091-data-surface-report-v1.json"
    audit_path = output_dir / "t091-internal-search-state-feasibility-audit-v1.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    audit_path.write_text(
        json.dumps(
            report["internal_search_state_feasibility_audit"], sort_keys=True, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = output_dir / "t091-retention-manifest-v1.json"
    outputs = []
    for role, path in (
        ("data_surface_report", report_path),
        ("internal_feasibility_audit", audit_path),
    ):
        outputs.append(
            {
                "role": role,
                "path": str(path),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest = {
        "schema_id": T091_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T091_TASK_ID,
        "provenance": {
            "publication_base": T091_PUBLICATION_BASE,
            "approved_spec_commit": T091_APPROVED_SPEC_COMMIT,
            "t090_inputs": report["input_artifacts"],
            "native_identity": T091_NATIVE_IDENTITY,
        },
        "outputs": outputs,
        "regeneration_command": f"python3 -m sts_combat_rl.commands.t091_battle_teacher_data_surface --t090-dir {t090_root} --output-dir {output_dir}",
        "compatibility": "accepted T090 formal order-repair artifacts with the exact six SHA-256 identities listed in this manifest's provenance",
        "retention_reason": "scientific-quality deterministic density, bias, ambiguity, and feasibility evidence for T091",
        "deletion_policy": "raw T090 inputs remain retained independently; these derived outputs may be deleted only after their hashes and terminal summary are preserved in accepted task records or regenerated from the immutable inputs.",
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return {"report": report_path, "audit": audit_path, "manifest": manifest_path}
