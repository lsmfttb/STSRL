import json
from pathlib import Path

from sts_combat_rl.t082_value_target_semantic_closure import audit, classify, recover_behavior, _validate_pool, _load_selected_envelope, sha256

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
    assert classify(integrity_valid=False, rows=[], proof=proof()) == "INCOMPLETE"

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


def _envelope(path: Path, records, **metadata):
    lines = [{"type": "metadata", "metadata": metadata | {"record_count": len(records)}}]
    lines.extend({"type": "record", "record": record} for record in records)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in lines) + "\n")


def test_actual_shaped_reader_preserves_teacher_and_trainer_provenance(tmp_path: Path):
    teacher = tmp_path / "teacher.jsonl"
    trainer = tmp_path / "trainer.jsonl"
    source = {"source_checkpoint_id": "ckpt", "source_run_id": "run", "source_seed": 3, "source_battle_index": 7, "source_pool_record_index": 11}
    _envelope(teacher, [source | {"row_index": 0, "teacher_action": action(1)}], artifact_schema_id="oracle-search-teacher-v1")
    _envelope(trainer, [{"example_index": 0, **source, "source_metadata": source | {"component": "assist_0", "assistance_level": "assist_0"}, "policy_target_kind": "oracle_soft_visit_distribution", "policy_target_source": "oracle_teacher_row.soft_visit_target", "structured_battle_outcome": {"battle_survived": {"status": "available", "value": True}}}], format_version=6)
    teacher_meta, teacher_rows = _load_selected_envelope(teacher, 1, "row_index")
    trainer_meta, trainer_rows = _load_selected_envelope(trainer, 1, "example_index")
    assert teacher_meta["artifact_schema_id"] == "oracle-search-teacher-v1"
    assert teacher_rows[0]["source_pool_record_index"] == 11
    assert trainer_meta["format_version"] == 6
    assert trainer_rows[0]["policy_target_kind"] == "oracle_soft_visit_distribution"
    assert trainer_rows[0]["structured_battle_outcome"]["battle_survived"]["value"] is True


def test_successor_reason_categories_and_deterministic_pool_fixture(tmp_path: Path):
    current = {"action_trace": [action(1)], "source_run_id": "r", "source_seed": 1, "source_battle_index": 0, "structural_metadata": {"assistance_level": "assist_0"}}
    successor = current | {"action_trace": [action(1), action(2)], "source_battle_index": 2}
    assert recover_behavior(current, successor)["reason"] == "non-adjacent battle"
    assert recover_behavior(current, None)["reason"] == "final/no immediate record"
    bad = successor | {"action_trace": [action(9), action(2)], "source_battle_index": 1}
    assert recover_behavior(current, bad)["reason"] == "non-prefix"
    pool = tmp_path / "pool.jsonl"
    _envelope(pool, [{"record_index": 0, "structural_metadata": {"assistance_level": "assist_0"}}], schema_id="assisted-run-source-pool-v1")
    expected = {"record_count": 1, "bytes": pool.stat().st_size, "sha256": sha256(pool)}
    assert _validate_pool(pool, expected, "assist_0")["valid"]
    assert _validate_pool(pool, expected, "assist_0")["metadata"]["schema_id"] == "assisted-run-source-pool-v1"
