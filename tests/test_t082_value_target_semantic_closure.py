import json
from pathlib import Path

import sts_combat_rl.t082_value_target_semantic_closure as audit_module
from sts_combat_rl.t082_value_target_semantic_closure import (
    _linkage_ok,
    _load_selected_envelope,
    _record_identity,
    _validate_pool,
    classify,
    recover_behavior,
    sha256,
)


def action(number, occurrence=0):
    return {
        "action_id": number,
        "occurrence": occurrence,
        "kind": "card",
        "label": f"Card {number}",
        "stable_id": f"card:{number}",
    }


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
    assert (
        recover_behavior(current, {"action_trace": [action(9), action(2)]})["status"]
        == "unavailable"
    )
    assert recover_behavior(current, None)["status"] == "unavailable"


def test_duplicate_actions_use_occurrence_identity():
    current = {"action_trace": [action(1, 0)]}
    successor = {"action_trace": [action(1, 0), action(1, 1)]}
    assert recover_behavior(current, successor)["identity"]["occurrence"] == 1


def test_compact_production_audit_fixture_valid_mutation_and_determinism(
    tmp_path: Path, monkeypatch, boundary=False
):
    root = tmp_path
    pool = root / "pool.jsonl"
    teacher = root / "teacher/merged.jsonl"
    trainer = root / "trainer/trainer-input.jsonl"
    teacher.parent.mkdir()
    trainer.parent.mkdir()
    meta = {
        "act": 1,
        "room_type": "monster",
        "encounter_id": "jaw_worm",
        "assistance_level": "assist_0",
    }
    current = {
        "record_index": 0,
        "source_checkpoint_id": "ckpt",
        "source_run_id": "run",
        "source_seed": 1,
        "source_battle_index": 0,
        "action_trace": [action(1)],
        "battle_outcome": "PLAYER_VICTORY",
        "checkpoint_information_regime": "full_simulator_state_oracle_like",
        "distribution_kind": "constructed",
        "structural_metadata": meta,
    }
    successor = current | {
        "record_index": 1,
        "source_battle_index": 1,
        "action_trace": [action(1), action(2)],
        "battle_outcome": "PLAYER_VICTORY",
    }
    if boundary:
        successor = successor | {"source_run_id": "next-run"}
    identity, identity_sha = _record_identity(current, "assist_0")
    pool_lines = [
        {
            "type": "metadata",
            "metadata": {
                "schema_id": "assisted-run-source-pool-v1",
                "format_version": 1,
                "record_count": 2,
                "assistance_level": "assist_0",
            },
        }
    ] + [{"type": "record", "record": row} for row in (current, successor)]
    pool.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in pool_lines) + "\n"
    )
    source = {
        "source_checkpoint_id": "ckpt",
        "source_run_id": "run",
        "source_seed": 1,
        "source_battle_index": 0,
        "source_pool_record_index": 0,
    }
    _envelope(
        teacher,
        [
            {
                "row_index": 0,
                **source,
                "teacher_action": {"action_identity": action(2)},
                "structural_metadata": meta,
            }
        ],
        artifact_schema_id="oracle-search-teacher-v1",
        format_version=1,
        controller_provenance={
            "name": "oracle",
            "config": {
                "information_regime": "full_simulator_state_oracle_like",
                "search_budget": {"simulations": 100},
                "root_selection_rule": "highest_mean",
                "include_potions": False,
                "target": "soft_visit_distribution",
            },
        },
    )
    _envelope(
        trainer,
        [
            {
                "example_index": 0,
                "policy_target_kind": "oracle_soft_visit_distribution",
                "policy_target_source": "oracle_teacher_row.soft_visit_target",
                "source_metadata": source
                | {"t064_complete_identity_sha256": identity_sha, **meta},
                "structured_battle_outcome": {
                    "battle_survived": {"status": "available", "value": True}
                },
            }
        ],
        format_version=6,
        policy_target_schema_id="trainer-policy-target-v1",
        policy_target_schema_version=1,
        structured_battle_outcome_schema_id="structured-battle-outcome-v1",
        structured_battle_outcome_schema_version=1,
    )
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "selected_sources": [
                    {
                        "component": "assist_0",
                        "source_record_index": 0,
                        "source_path": str(pool),
                        **meta,
                        "complete_identity": identity,
                        "complete_identity_sha256": identity_sha,
                    }
                ],
                "input_artifacts": {
                    "assist_0": {
                        "path": str(pool),
                        "record_count": 2,
                        "bytes": pool.stat().st_size,
                        "sha256": sha256(pool),
                        "schema_id": "assisted-run-source-pool-v1",
                        "format_version": 1,
                    }
                },
            },
            sort_keys=True,
        )
    )
    (root / "t064-transfer-decision.json").write_text(
        json.dumps(
            {
                "experiment_complete": True,
                "source_adequacy": True,
                "source_integrity_valid": True,
                "terminal_case": "Case B",
            }
        )
    )
    control = root / "control.json"
    control.write_text(
        json.dumps(
            {"schema_id": "synthetic-control-v1", "value": "frozen"}, sort_keys=True
        )
        + "\n"
    )
    expected_inputs = {"control.json": (sha256(control), "synthetic-control-v1")}
    out1 = root / "report1.json"
    monkeypatch.setattr(audit_module, "EXPECTED_INPUTS", expected_inputs)
    first = audit_module.audit_t064(manifest, out1, expected_rows=1)
    assert all(decision["valid"] for decision in first["inputs"]["control_artifacts"])
    assert first["integrity"]["valid"] and first["counts"]["total_rows"] == 1
    assert first["rows"][0]["linkage_valid"]
    if not boundary:
        assert first["rows"][0]["behavior"]["status"] == "available"
    first_bytes = out1.read_bytes()
    audit_module.audit_t064(manifest, out1, expected_rows=1)
    assert first_bytes == out1.read_bytes()
    mutated = json.loads(manifest.read_text())
    mutated["input_artifacts"]["assist_0"]["sha256"] = "wrong"
    manifest.write_text(json.dumps(mutated))
    assert (
        audit_module.audit_t064(manifest, root / "bad.json", expected_rows=1)[
            "classification"
        ]
        == "INCOMPLETE"
    )


def test_classification_requires_explicit_proof_and_outcome():
    divergent = [{"comparison": "different", "outcome": "available"}]
    assert (
        classify(
            integrity_valid=True,
            rows=divergent,
            proof=proof(missing=("value_target_from_source_outcome",)),
        )
        == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    )
    assert (
        classify(integrity_valid=True, rows=divergent, proof=proof())
        == "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
    )
    assert (
        classify(
            integrity_valid=True,
            rows=[{"comparison": "different", "outcome": "unavailable"}],
            proof=proof(),
        )
        == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    )
    assert (
        classify(integrity_valid=True, rows=[], proof=proof(alignment=True))
        == "VALUE_TARGET_SEMANTICS_ALIGNED"
    )
    assert (
        classify(integrity_valid=True, rows=[], proof=proof())
        == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    )


def test_pool_validator_rejects_mutated_metadata_hash_and_order(tmp_path: Path):
    pool = tmp_path / "pool.jsonl"
    pool.write_text(
        json.dumps(
            {
                "type": "metadata",
                "metadata": {"schema_id": "assisted-run-source-pool-v1"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "record",
                "record": {
                    "record_index": 0,
                    "structural_metadata": {"assistance_level": "assist_0"},
                },
            }
        )
        + "\n"
    )
    assert not _validate_pool(
        pool,
        {"record_count": 1, "bytes": pool.stat().st_size, "sha256": "wrong"},
        "assist_0",
    )["valid"]


def _envelope(path: Path, records, **metadata):
    lines = [
        {"type": "metadata", "metadata": metadata | {"record_count": len(records)}}
    ]
    lines.extend({"type": "record", "record": record} for record in records)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in lines) + "\n")


def test_actual_shaped_reader_preserves_teacher_and_trainer_provenance(tmp_path: Path):
    teacher = tmp_path / "teacher.jsonl"
    trainer = tmp_path / "trainer.jsonl"
    source = {
        "source_checkpoint_id": "ckpt",
        "source_run_id": "run",
        "source_seed": 3,
        "source_battle_index": 7,
        "source_pool_record_index": 11,
    }
    _envelope(
        teacher,
        [source | {"row_index": 0, "teacher_action": action(1)}],
        artifact_schema_id="oracle-search-teacher-v1",
    )
    _envelope(
        trainer,
        [
            {
                "example_index": 0,
                **source,
                "source_metadata": source
                | {"component": "assist_0", "assistance_level": "assist_0"},
                "policy_target_kind": "oracle_soft_visit_distribution",
                "policy_target_source": "oracle_teacher_row.soft_visit_target",
                "structured_battle_outcome": {
                    "battle_survived": {"status": "available", "value": True}
                },
            }
        ],
        format_version=6,
    )
    teacher_meta, teacher_rows = _load_selected_envelope(teacher, 1, "row_index")
    trainer_meta, trainer_rows = _load_selected_envelope(trainer, 1, "example_index")
    assert teacher_meta["artifact_schema_id"] == "oracle-search-teacher-v1"
    assert teacher_rows[0]["source_pool_record_index"] == 11
    assert trainer_meta["format_version"] == 6
    assert trainer_rows[0]["policy_target_kind"] == "oracle_soft_visit_distribution"
    assert (
        trainer_rows[0]["structured_battle_outcome"]["battle_survived"]["value"] is True
    )


def test_actual_trainer_linkage_uses_complete_identity_hash_not_pool_index():
    identity = {
        "source_checkpoint_id": "ckpt",
        "source_run_id": "run",
        "source_seed": 3,
        "source_battle_index": 7,
        "complete_identity_sha256": "identity",
    }
    selected = {
        "complete_identity": identity,
        "act": 1,
        "room_type": "monster",
        "encounter_id": "jaw_worm",
        "assistance_level": "assist_0",
    }
    teacher = {
        "row_index": 0,
        "source_checkpoint_id": "ckpt",
        "source_run_id": "run",
        "source_seed": 3,
        "source_battle_index": 7,
        "source_pool_record_index": 11,
        "structural_metadata": {
            "act": 1,
            "room_type": "monster",
            "encounter_id": "jaw_worm",
            "assistance_level": "assist_0",
        },
    }
    trainer = {
        "example_index": 0,
        "policy_target_kind": "oracle_soft_visit_distribution",
        "policy_target_source": "oracle_teacher_row.soft_visit_target",
        "source_metadata": identity
        | {
            "t064_complete_identity_sha256": "identity",
            "act": 1,
            "room_type": "monster",
            "encounter_id": "jaw_worm",
            "assistance_level": "assist_0",
        },
    }
    assert _linkage_ok(selected, teacher, trainer, 0, 11)[0]
    trainer["source_metadata"] = trainer["source_metadata"] | {
        "t064_complete_identity_sha256": "wrong"
    }
    assert not _linkage_ok(selected, teacher, trainer, 0, 11)[0]


def test_successor_reason_categories_and_deterministic_pool_fixture(tmp_path: Path):
    current = {
        "action_trace": [action(1)],
        "source_run_id": "r",
        "source_seed": 1,
        "source_battle_index": 0,
        "structural_metadata": {"assistance_level": "assist_0"},
    }
    successor = current | {
        "action_trace": [action(1), action(2)],
        "source_battle_index": 2,
    }
    assert recover_behavior(current, successor)["reason"] == "non-adjacent battle"
    assert recover_behavior(current, None)["reason"] == "final/no immediate record"
    bad = successor | {"action_trace": [action(9), action(2)], "source_battle_index": 1}
    assert recover_behavior(current, bad)["reason"] == "non-prefix"
    pool = tmp_path / "pool.jsonl"
    _envelope(
        pool,
        [{"record_index": 0, "structural_metadata": {"assistance_level": "assist_0"}}],
        schema_id="assisted-run-source-pool-v1",
        format_version=1,
        assistance_level="assist_0",
    )
    expected = {
        "record_count": 1,
        "bytes": pool.stat().st_size,
        "sha256": sha256(pool),
        "schema_id": "assisted-run-source-pool-v1",
        "format_version": 1,
    }
    assert _validate_pool(pool, expected, "assist_0")["valid"]
    assert (
        _validate_pool(pool, expected, "assist_0")["metadata"]["schema_id"]
        == "assisted-run-source-pool-v1"
    )


def test_malformed_source_reader_is_explicit_not_silent(tmp_path: Path):
    source = tmp_path / "bad.jsonl"
    source.write_text('{"type":"record","record":[]\n')
    errors = list(audit_module._safe_source_rows(source))
    assert errors and "malformed" in errors[0]["_audit_source_error"]


def test_audit_t064_malformed_manifest_writes_complete_incomplete_report(
    tmp_path: Path,
):
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "report.json"
    manifest.write_text(json.dumps({"selected_sources": [{"component": []}]}))
    report = audit_module.audit_t064(manifest, output, expected_rows=1)
    assert report["classification"] == "INCOMPLETE"
    assert report["inputs"]["teacher"]["observed"] is None
    assert len(report["inputs"]["pool_checks"]) == 4
    assert output.read_bytes() == output.read_bytes()


def test_audit_t064_run_boundary_is_not_an_integrity_failure(tmp_path: Path):
    class Monkeypatch:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    test_compact_production_audit_fixture_valid_mutation_and_determinism(
        tmp_path, Monkeypatch(), boundary=True
    )
    report = json.loads((tmp_path / "report1.json").read_text())
    row = report["rows"][0]
    assert row["successor_exists"] is False
    assert row["physical_successor_candidate"] is True
    assert row["successor_reason"] == "run boundary/no exact successor"
    assert report["integrity"]["valid"] is True
