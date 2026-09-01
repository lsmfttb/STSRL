import json
from pathlib import Path

from sts_combat_rl.t082_value_target_semantic_closure import audit, classify, recover_behavior, _validate_pool

def action(number, occurrence=0):
    return {"action_id": number, "occurrence": occurrence, "kind": "card", "label": f"Card {number}", "stable_id": f"card:{number}"}


def proof(*, alignment=False, missing=()):
    result = {
        "policy_target_from_oracle": {"verified": True},
        "value_target_from_source_outcome": {"verified": True},
        "search_v2_leaf_survival_consumer": {"verified": True},
        "continuation_alignment": {"verified": alignment},
    }
    for key in missing:
        result[key] = {"verified": False}
    return result

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

def test_classification_requires_explicit_proof_and_outcome():
    divergent = [{"comparison": "different", "outcome": "available"}]
    assert classify(integrity_valid=True, rows=divergent, proof=proof(missing=("value_target_from_source_outcome",))) == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    assert classify(integrity_valid=True, rows=divergent, proof=proof()) == "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
    assert classify(integrity_valid=True, rows=[{"comparison": "different", "outcome": "unavailable"}], proof=proof()) == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    assert classify(integrity_valid=True, rows=[], proof=proof(alignment=True)) == "VALUE_TARGET_SEMANTICS_ALIGNED"
    assert classify(integrity_valid=True, rows=[], proof=proof()) == "VALUE_TARGET_SEMANTICS_UNRESOLVED"

def test_pool_validator_rejects_mutated_metadata_hash_and_order(tmp_path: Path):
    pool = tmp_path / "pool.jsonl"
    pool.write_text(json.dumps({"type": "metadata", "metadata": {"schema_id": "assisted-run-source-pool-v1"}}) + "\n" + json.dumps({"type": "record", "record": {"record_index": 0, "structural_metadata": {"assistance_level": "assist_0"}}}) + "\n")
    assert not _validate_pool(pool, {"record_count": 1, "bytes": pool.stat().st_size, "sha256": "wrong"}, "assist_0")["valid"]
