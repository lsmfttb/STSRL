"""Bounded, deterministic audit of the retained T064 target lineage."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from types import SimpleNamespace
from sts_combat_rl.sim.source_identity import complete_source_identity, canonical_sha256

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
            if item.get("type") == "metadata":
                continue
            yield dict(item.get("record", item))

def _source_rows(path: Path) -> Iterable[dict[str, Any]]:
    """Stream only fields needed for T082, excluding raw snapshots/features."""
    keep = {"record_index", "source_checkpoint_id", "source_run_id", "source_seed", "source_battle_index", "action_trace", "battle_outcome", "checkpoint_information_regime", "distribution_kind", "structural_metadata", "source_battle_controller_provenance", "source_controller_provenance"}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if item.get("type") == "metadata":
                continue
            row = item.get("record", item)
            if not isinstance(row, Mapping):
                raise ValueError(f"invalid source row {number}")
            yield {key: row[key] for key in keep if key in row}

def _record_identity(row: Mapping[str, Any], component: str) -> tuple[dict[str, Any], str]:
    metadata = dict(row.get("structural_metadata", {}))
    metadata.setdefault("assistance_level", component)
    obj = SimpleNamespace(
        structural_metadata=metadata,
        action_trace=tuple(row.get("action_trace", ())),
        source_checkpoint_id=row.get("source_checkpoint_id"),
        source_seed=row.get("source_seed"), source_run_id=row.get("source_run_id"),
        source_battle_index=row.get("source_battle_index"),
        checkpoint_information_regime=row.get("checkpoint_information_regime"),
        distribution_kind=row.get("distribution_kind"),
    )
    identity = complete_source_identity(obj, source_arm="")
    return identity, identity["complete_identity_sha256"]

def _load_envelope(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if item.get("type") == "metadata":
                metadata = dict(item.get("metadata", {}))
            elif item.get("type") == "record":
                rows.append(dict(item["record"]))
            else:
                raise ValueError(f"invalid envelope row {number}")
    if metadata is None:
        raise ValueError(f"missing metadata envelope: {path}")
    return metadata, rows

def _load_selected_envelope(path: Path, expected: int, index_field: str) -> list[dict[str, Any]]:
    metadata: dict[str, Any] | None = None
    rows: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if item.get("type") == "metadata":
                metadata = dict(item.get("metadata", {}))
            elif item.get("type") == "record":
                raw = item["record"]
                keep = {"row_index", "example_index", "teacher_action", "policy_target_action_identity", "policy_target_kind", "policy_target_source", "source_metadata", "controller_provenance", "raw_reward_components", "structured_battle_outcome", "behavior_action", "behavior_action_status"}
                row = {key: raw[key] for key in keep if key in raw}
                index = row.get(index_field, number - 2)
                if isinstance(index, int) and 0 <= index < expected:
                    if index in rows: raise ValueError(f"duplicate {index_field}: {index}")
                    rows[index] = row
            else:
                raise ValueError(f"invalid envelope row {number}")
    if metadata is None or len(rows) != expected:
        raise ValueError(f"{path} does not contain exactly {expected} indexed rows")
    return [rows[index] for index in range(expected)]

def audit_t064(manifest_path: Path, output: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = manifest["selected_sources"]
    if len(selected) != 460:
        raise ValueError("T064 selected inventory must contain exactly 460 rows")
    root = manifest_path.parent
    teacher_path, trainer_path = root / "teacher/merged.jsonl", root / "trainer/trainer-input.jsonl"
    teachers = _load_selected_envelope(teacher_path, 460, "row_index")
    trainers = _load_selected_envelope(trainer_path, 460, "example_index")
    if len(teachers) != 460 or len(trainers) != 460:
        raise ValueError("T064 teacher/trainer inventories must each contain 460 rows")
    by_component: defaultdict[str, set[int]] = defaultdict(set)
    for index, item in enumerate(selected): by_component[item["component"]].add(item["source_record_index"])
    found: dict[tuple[str, int], tuple[dict[str, Any], dict[str, Any] | None]] = {}
    for component, indexes in by_component.items():
        previous = None
        pool = Path(manifest["input_artifacts"][component]["path"].replace("D:\\", "/mnt/d/").replace("\\", "/"))
        for record in _source_rows(pool):
            record_index = record.get("record_index")
            if record_index in indexes:
                found[(component, record_index)] = (record, None)
            if previous is not None and previous.get("record_index") in indexes and record.get("source_run_id") == previous.get("source_run_id") and record.get("source_seed") == previous.get("source_seed") and record.get("source_battle_index") == previous.get("source_battle_index", -1) + 1:
                key = (component, previous["record_index"])
                if key in found: found[key] = (previous, record)
            previous = record
    rows = []
    for index, item in enumerate(selected):
        component, record_index = item["component"], item["source_record_index"]
        source, successor = found.get((component, record_index), ({}, None))
        try: derived, derived_sha = _record_identity(source, component)
        except (ValueError, KeyError) as exc: derived, derived_sha = {}, None; source_error = str(exc)
        else: source_error = None
        identity_ok = derived_sha == item.get("complete_identity_sha256")
        behavior = recover_behavior(source, successor) if source else {"status": "unavailable", "reason": "source record missing"}
        teacher_action = _identity(teachers[index].get("teacher_action", {}).get("action_identity"))
        trainer_meta = trainers[index].get("source_metadata", {})
        same = teacher_action == _identity(trainers[index].get("policy_target_action_identity"))
        comparison = "unavailable" if behavior.get("status") != "available" or teacher_action is None else "same" if tuple(behavior["identity"]) == teacher_action else "different"
        outcome = source.get("battle_outcome")
        rows.append({"index": index, "selected_identity": item["complete_identity"], "selected_identity_sha256": item.get("complete_identity_sha256"), "derived_identity_sha256": derived_sha, "identity_valid": identity_ok, "identity_error": source_error, "component": component, "source_record_index": record_index, "source_checkpoint_id": source.get("source_checkpoint_id"), "source_run_id": source.get("source_run_id"), "source_seed": source.get("source_seed"), "source_battle_index": source.get("source_battle_index"), "act": item.get("act"), "room_type": item.get("room_type"), "trace_length": len(source.get("action_trace", ())), "successor": {"record_index": successor.get("record_index"), "trace_length": len(successor.get("action_trace", ())), "battle_index": successor.get("source_battle_index")} if successor else None, "behavior": behavior, "teacher_action": teacher_action, "trainer_policy_action": _identity(trainers[index].get("policy_target_action_identity")), "comparison": comparison, "source_battle_outcome": outcome if isinstance(outcome, str) else None, "trainer_value_lineage": trainers[index].get("raw_reward_components", {}).get("battle_outcome"), "source_controller": source.get("source_battle_controller_provenance"), "teacher_controller": teachers[index].get("controller_provenance"), "policy_target_source": trainers[index].get("policy_target_source"), "value_target_source": "trainer_input_record.raw_reward_components.battle_outcome"})
    report = {"schema_version": SCHEMA, "inputs": {"manifest": str(manifest_path), "manifest_sha256": sha256(manifest_path), "teacher": {"path": str(teacher_path), "sha256": sha256(teacher_path)}, "trainer": {"path": str(trainer_path), "sha256": sha256(trainer_path)}, "source_components": {component: {"path": str(manifest["input_artifacts"][component]["path"]), "expected_sha256": manifest["input_artifacts"][component]["sha256"]} for component in sorted(by_component)}}, "integrity": {"selected_teacher_trainer_counts": len(rows) == 460, "source_identity_valid": all(row["identity_valid"] for row in rows), "problems": [] if all(row["identity_valid"] for row in rows) else ["one or more source identities failed validation"]}, "counts": {"total_rows": len(rows), "behavior_recoverable": sum(row["behavior"]["status"] == "available" for row in rows), "behavior_unavailable": sum(row["behavior"]["status"] != "available" for row in rows), "comparisons": dict(Counter(row["comparison"] for row in rows)), "outcomes": dict(Counter("survived" if row["source_battle_outcome"] == "PLAYER_VICTORY" else "lost" if row["source_battle_outcome"] else "unavailable" for row in rows))}, "classification": classify(integrity_valid=all(row["identity_valid"] for row in rows), rows=rows), "rows": rows, "semantic_call_chain": {"policy_target": "oracle teacher action", "value_target": "realized source battle outcome", "search_v2_leaf": "battle_survival_probability at hypothetical leaf"}}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

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
