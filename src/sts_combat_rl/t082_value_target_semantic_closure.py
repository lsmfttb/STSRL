"""Bounded, deterministic audit of the retained T064 target lineage."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

SCHEMA = "t082-value-target-semantic-closure-v1"
CLASSIFICATIONS = {"VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED", "VALUE_TARGET_SEMANTICS_ALIGNED", "VALUE_TARGET_SEMANTICS_UNRESOLVED", "INCOMPLETE"}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _identity(action: Any) -> tuple[Any, ...] | None:
    if not isinstance(action, Mapping):
        return None
    fields = ("action_id", "occurrence", "kind", "label", "stable_id")
    if any(action.get(field) is None for field in fields):
        return None
    return tuple(action[field] for field in fields)

def recover_behavior(current: Mapping[str, Any], successor: Mapping[str, Any] | None) -> dict[str, Any]:
    if successor is None:
        return {"status": "unavailable", "reason": "no immediate successor"}
    before = current.get("action_trace", ())
    after = successor.get("action_trace", ())
    if not isinstance(before, list | tuple) or not isinstance(after, list | tuple):
        return {"status": "unavailable", "reason": "action trace unavailable"}
    before_ids = [_identity(item) for item in before]
    after_ids = [_identity(item) for item in after]
    if None in before_ids or None in after_ids:
        return {"status": "unavailable", "reason": "unstable action identity"}
    if len(after_ids) <= len(before_ids) or after_ids[: len(before_ids)] != before_ids:
        return {"status": "unavailable", "reason": "successor is not a strict trace prefix"}
    return {"status": "available", "identity": after_ids[len(before_ids)]}

def _rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if not isinstance(item, Mapping):
                raise ValueError(f"invalid JSONL row {number}")
            yield dict(item.get("record", item))

def _join_successors(path: Path, selected: set[tuple[Any, ...]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    previous: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in _rows(path):
        key = (row.get("source_pool_sha256"), row.get("source_run_id"), row.get("source_seed"))
        prior = previous.get(key)
        if prior is not None and (prior.get("source_battle_index", -1) + 1 == row.get("source_battle_index")):
            identity = tuple(prior.get("complete_identity", ()))
            if identity in selected:
                found[identity] = row
        previous[key] = row
    return found

def classify(*, integrity_valid: bool, rows: list[dict[str, Any]], source_outcome_proven: bool = True, search_leaf_proven: bool = True) -> str:
    if not integrity_valid:
        return "INCOMPLETE"
    divergent = [row for row in rows if row.get("comparison") == "different"]
    if source_outcome_proven and search_leaf_proven and divergent:
        return "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
    if not divergent and source_outcome_proven and search_leaf_proven:
        return "VALUE_TARGET_SEMANTICS_ALIGNED"
    return "VALUE_TARGET_SEMANTICS_UNRESOLVED"

def audit(selected: list[Mapping[str, Any]], teacher: list[Mapping[str, Any]], trainer: list[Mapping[str, Any]], source_path: Path, *, expected_rows: int = 460) -> dict[str, Any]:
    problems: list[str] = []
    integrity = len(selected) == len(teacher) == len(trainer) == expected_rows
    if not integrity:
        problems.append("selected/teacher/trainer row counts are not all 460")
    selected_keys = [tuple(row.get("complete_identity", ())) for row in selected]
    if len(set(selected_keys)) != len(selected_keys):
        integrity = False; problems.append("selected source identities are duplicated")
    source_successors = _join_successors(source_path, set(selected_keys))
    rows: list[dict[str, Any]] = []
    strata: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for index, (source, teach, train) in enumerate(zip(selected, teacher, trainer, strict=True)):
        successor = source_successors.get(selected_keys[index])
        behavior = recover_behavior(source, successor)
        teacher_id = _identity(teach.get("teacher_action") or teach.get("policy_target_action_identity"))
        comparison = "unavailable" if behavior.get("status") != "available" or teacher_id is None else "same" if tuple(behavior["identity"]) == teacher_id else "different"
        outcome = train.get("battle_survived", train.get("structured_battle_outcome", {}).get("battle_survived"))
        outcome_status = "available" if isinstance(outcome, bool) else "unavailable"
        row = {"index": index, "source_identity": source.get("complete_identity"), "behavior": behavior, "teacher_action": teacher_id, "comparison": comparison, "outcome": outcome_status, "assistance_level": source.get("assistance_level"), "act": source.get("act"), "room_type": source.get("room_type"), "source_battle_controller": source.get("battle_controller_provenance")}
        rows.append(row)
        for key in ("act", "room_type", "assistance_level", "source_battle_controller"):
            strata[f"{key}={row.get(key, 'unavailable')}"][comparison] += 1
    classification = classify(integrity_valid=integrity, rows=rows)
    return {"schema_version": SCHEMA, "classification": classification, "integrity": {"valid": integrity, "problems": problems}, "counts": {"total_rows": len(rows), "behavior_recoverable": sum(row["behavior"]["status"] == "available" for row in rows), "behavior_unavailable": sum(row["behavior"]["status"] != "available" for row in rows), "comparisons": dict(Counter(row["comparison"] for row in rows)), "outcomes": dict(Counter(row["outcome"] for row in rows))}, "strata": {key: dict(sorted(value.items())) for key, value in sorted(strata.items())}, "rows": rows}

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, required=True); parser.add_argument("--teacher", type=Path, required=True); parser.add_argument("--trainer", type=Path, required=True); parser.add_argument("--sources", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    def load(path: Path) -> list[dict[str, Any]]: return list(_rows(path))
    report = audit(load(parser.parse_args().selected), load(parser.parse_args().teacher), load(parser.parse_args().trainer), parser.parse_args().sources)
    parser.parse_args().output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
