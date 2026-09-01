#!/usr/bin/env python3
"""Offline, fail-closed audit for the frozen T043 value-target lineage."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

CHECKPOINT_SHA = "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
REPORT_SCHEMA = "t080-value-target-semantics-audit-v1"
MANIFEST_SCHEMA = "t080-retention-manifest-v1"


def digest(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block); size += len(block)
    return h.hexdigest(), size


def identity(value: object) -> object:
    return value if isinstance(value, dict) and value.get("stable_id") else None


def audit(checkpoint: Path, trainer: Path) -> dict:
    checkpoint_sha, checkpoint_bytes = digest(checkpoint)
    trainer_sha, trainer_bytes = digest(trainer)
    if checkpoint_sha != CHECKPOINT_SHA:
        raise SystemExit("T080 fail closed: checkpoint SHA-256 mismatch")
    rows = []
    metadata = None
    with trainer.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            obj = json.loads(line)
            if obj.get("type") == "metadata":
                if metadata is not None: raise SystemExit("duplicate metadata wrapper")
                metadata = obj["metadata"]
            elif obj.get("type") == "record" and isinstance(obj.get("record"), dict):
                rows.append(obj["record"])
            else: raise SystemExit(f"T080 fail closed: invalid line {line_number}")
    if not metadata or len(rows) != 4 or metadata.get("record_count") != 4:
        raise SystemExit("T080 fail closed: expected metadata plus exactly 4 records")
    provenance = metadata.get("generation_metadata", {})
    target_kinds = Counter(r.get("policy_target_kind", "unavailable") for r in rows)
    target_sources = Counter(r.get("policy_target_source", "unavailable") for r in rows)
    behavior = Counter(r.get("behavior_action_status", "unavailable") for r in rows)
    outcomes = Counter()
    comparisons = []
    strata = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        outcome = r.get("structured_battle_outcome", {}).get("battle_survived", {})
        status = outcome.get("status", "unavailable")
        outcomes["survived" if status == "available" and outcome.get("value") is True else
                 "lost" if status == "available" and outcome.get("value") is False else "unavailable"] += 1
        bstatus = r.get("behavior_action_status", "unavailable")
        teacher = identity(r.get("policy_target_action_identity"))
        baction = identity(r.get("behavior_action")) if bstatus == "available" else None
        same = teacher == baction if teacher is not None and baction is not None else None
        comparisons.append({"example_index": r.get("example_index"), "teacher_target_action_identity": teacher,
                            "behavior_action_identity": baction, "comparison":
                            "same" if same is True else "different" if same is False else "unavailable"})
        sm = r.get("source_metadata", {})
        for key in ("assistance_level", "act", "room_type", "source_kind", "distribution_kind"):
            strata[key][str(sm.get(key, "unavailable"))]["rows"] += 1
            if same is None: strata[key][str(sm.get(key, "unavailable"))]["unavailable"] += 1
    return {"schema_id": REPORT_SCHEMA, "classification": "VALUE_TARGET_SEMANTICS_UNRESOLVED",
        "offline_only": True, "checkpoint": {"path": str(checkpoint), "sha256": checkpoint_sha, "bytes": checkpoint_bytes,
        "expected_sha256": CHECKPOINT_SHA}, "trainer_input": {"path": str(trainer), "sha256": trainer_sha,
        "bytes": trainer_bytes, "schema_id": metadata.get("policy_target_schema_id"), "record_schema_version": metadata.get("decision_record_schema_version"),
        "record_count": len(rows), "metadata_wrapper_count": 1, "generation_metadata": provenance},
        "target_lineage": {"policy_target_kind_counts": dict(target_kinds), "policy_target_source_counts": dict(target_sources),
        "source_behavior_action_status_counts": dict(behavior), "source_outcome_field": "record.structured_battle_outcome.battle_survived",
        "source_outcome_status_counts": dict(outcomes)}, "action_comparisons": comparisons, "strata": {k: dict(v) for k,v in strata.items()},
        "static_call_chain": [{"producer": "src/sts_combat_rl/sim/torch_policy_value.py:TrainerInputRecord structured_battle_outcome", "field": "battle_survived"},
        {"producer": "src/sts_combat_rl/sim/oracle_teacher.py:_battle_survived", "field": "source battle outcome"},
        {"consumer": "src/sts_combat_rl/sim/search.py:learned-leaf value callback", "field": "battle_survival_probability", "boundary": "after_first_action_from_newly_expanded_node"}],
        "unresolved": ["all four behavior actions are unavailable", "no artifact proves source continuation policy equals Search v2 leaf continuation policy"],
        "prohibited_actions": ["retraining", "Search/model/feature/simulator changes", "successor publication"]}


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--checkpoint", type=Path, required=True); p.add_argument("--trainer", type=Path, required=True); p.add_argument("--output-root", type=Path, required=True)
    a = p.parse_args(); report = audit(a.checkpoint, a.trainer); a.output_root.mkdir(parents=True, exist_ok=True)
    report_path = a.output_root / "t080-value-target-semantics-audit-v1.json"; report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    files = [{"path": str(report_path), "sha256": digest(report_path)[0], "bytes": digest(report_path)[1], "schema_id": REPORT_SCHEMA}]
    manifest = {"schema_id": MANIFEST_SCHEMA, "report": report_path.name, "regeneration": "python3 scripts/run_t080_value_target_semantics_audit.py --checkpoint <checkpoint> --trainer <trainer> --output-root <root>", "retention_reason": "immutable offline T080 evidence", "files": files}
    (a.output_root / "t080-retention-manifest-v1.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"classification": report["classification"], "report": str(report_path), "trainer_sha256": report["trainer_input"]["sha256"]}, sort_keys=True))

if __name__ == "__main__": main()
