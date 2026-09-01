import json
from pathlib import Path

from sts_combat_rl.t082_value_target_semantic_closure import audit, classify, recover_behavior

def action(number, occurrence=0):
    return {"action_id": number, "occurrence": occurrence, "kind": "card", "label": f"Card {number}", "stable_id": f"card:{number}"}

def test_recovery_requires_immediate_strict_occurrence_safe_successor():
    current = {"action_trace": [action(1)]}
    successor = {"action_trace": [action(1), action(2)]}
    assert recover_behavior(current, successor)["identity"]["stable_id"] == "card:2"
    assert recover_behavior(current, {"action_trace": [action(9), action(2)]})["status"] == "unavailable"
    assert recover_behavior(current, None)["status"] == "unavailable"

def test_duplicate_actions_use_occurrence_identity():
    current = {"action_trace": [action(1, 0)]}
    successor = {"action_trace": [action(1, 0), action(1, 1)]}
    assert recover_behavior(current, successor)["identity"]["occurrence"] == 1

def test_bounded_audit_counts_and_incomplete_classification(tmp_path: Path):
    source = tmp_path / "sources.jsonl"
    source.write_text(json.dumps({"complete_identity": ["s"], "source_run_id": "r", "source_seed": 1, "source_battle_index": 0, "action_trace": [action(1)]}) + "\n" + json.dumps({"complete_identity": ["n"], "source_run_id": "r", "source_seed": 1, "source_battle_index": 1, "action_trace": [action(1), action(2)]}) + "\n")
    selected = [{"complete_identity": ["s"], "source_run_id": "r", "source_seed": 1, "source_battle_index": 0, "action_trace": [action(1)]}]
    teacher = [{"teacher_action": action(2)}]
    trainer = [{"battle_survived": True}]
    report = audit(selected, teacher, trainer, source, expected_rows=1)
    assert report["counts"]["behavior_recoverable"] == 1
    assert classify(integrity_valid=False, rows=[]) == "INCOMPLETE"
