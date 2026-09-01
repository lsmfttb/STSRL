from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scripts.run_t080_value_target_semantics_audit as t080


def _identity(number: int) -> dict[str, object]:
    return {
        "action_id": number,
        "occurrence": 0,
        "kind": "card",
        "label": f"Card {number}",
        "stable_id": f"card:{number}:0",
    }


def _trainer(
    path: Path, *, outcomes: list[bool | None], behavior: bool = False
) -> None:
    rows = []
    for index, outcome in enumerate(outcomes):
        row = {
            "example_index": index,
            "policy_target_kind": "oracle_teacher_action",
            "policy_target_source": "oracle_teacher_row.teacher_action",
            "policy_target_action_identity": _identity(index),
            "behavior_action_status": "available" if behavior else "unavailable",
            "source_metadata": {
                "assistance_level": "assist_0",
                "act": 1,
                "room_type": "MONSTER",
                "source_kind": "natural_run",
                "distribution_kind": "natural_run",
                "encounter_id": "jaw_worm",
                "source_checkpoint_id": f"source-{index}",
            },
            "structured_battle_outcome": {
                "battle_survived": {
                    "status": "available" if outcome is not None else "unavailable",
                    "value": outcome,
                }
            },
        }
        if behavior:
            row["behavior_action"] = {"action_identity": _identity(index + 10)}
        rows.append({"type": "record", "record": row})
    document = [
        {"type": "metadata", "metadata": {"format_version": 6, "record_count": 4}},
        *rows,
    ]
    path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in document)
    )


def _fake_audit(
    tmp_path: Path,
    monkeypatch,
    *,
    outcomes=None,
    behavior=False,
    recorded_path=None,
    target_source="oracle_teacher_row.teacher_action",
    provenance_target_source=None,
):
    checkpoint = tmp_path / "checkpoint.pt"
    trainer = tmp_path / "artifacts" / "trainer.jsonl"
    trainer.parent.mkdir(exist_ok=True)
    checkpoint.write_bytes(b"checkpoint")
    _trainer(trainer, outcomes=outcomes or [False] * 4, behavior=behavior)
    if target_source != "oracle_teacher_row.teacher_action":
        text = trainer.read_text().replace(
            "oracle_teacher_row.teacher_action", target_source
        )
        trainer.write_text(text)
    trainer_sha = hashlib.sha256(trainer.read_bytes()).hexdigest()
    provenance = {
        "trainer_input_path": recorded_path or "artifacts/trainer.jsonl",
        "trainer_input_sha256": trainer_sha,
        "trainer_input_byte_count": trainer.stat().st_size,
        "trainer_input_format_version": 6,
        "trainer_record_count": 4,
        "trainer_input_artifact_id": f"trainer-input-sha256:{trainer_sha}",
        "target_source_summary": {
            "policy_target_kind": "oracle_teacher_action",
            "policy_target_source": provenance_target_source or target_source,
            "outcome_target_kind": "terminal_battle_survival_probability",
            "outcome_target_source": "trainer_input_record.structured_battle_outcome.battle_survived",
        },
    }
    real_digest = t080.digest

    def digest(path):
        if Path(path) == checkpoint:
            return t080.CHECKPOINT_SHA, checkpoint.stat().st_size
        return real_digest(path)

    monkeypatch.setattr(t080, "digest", digest)
    raw = {
        "schema_id": "torch-policy-value-checkpoint-v1",
        "format_version": 1,
        "policy_target_kind": "oracle_teacher_action",
        "outcome_target_kind": "terminal_battle_survival_probability",
        "metadata": {"test": True},
    }
    return (
        t080.audit(checkpoint, trainer, lambda _: (provenance, raw)),
        checkpoint,
        trainer,
    )


def test_absolute_path_is_accepted(tmp_path, monkeypatch):
    report, _, trainer = _fake_audit(
        tmp_path,
        monkeypatch,
        recorded_path=str(tmp_path / "artifacts" / "trainer.jsonl"),
    )
    assert report["trainer_input"]["path"] == str(trainer.resolve())


def test_relative_path_and_provenance_mismatch_fail_closed(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="path mismatch"):
        _fake_audit(tmp_path, monkeypatch, recorded_path="artifacts/other.jsonl")
    report, checkpoint, trainer = _fake_audit(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="trainer SHA"):
        t080.audit(
            checkpoint,
            trainer,
            lambda _: ({"trainer_input_path": "artifacts/trainer.jsonl"}, {}),
        )
    assert report["classification"] == "VALUE_TARGET_SEMANTICS_UNRESOLVED"


def test_wrapper_requires_exact_metadata_plus_four_records(tmp_path, monkeypatch):
    _, _, trainer = _fake_audit(tmp_path, monkeypatch)
    lines = trainer.read_text().splitlines()
    trainer.write_text("\n".join(lines[1:]) + "\n")
    with pytest.raises(RuntimeError, match="metadata plus exactly 4"):
        t080._load_trainer(trainer)


def test_outcome_counts_preserve_one_lost_and_three_survived(tmp_path, monkeypatch):
    report, _, _ = _fake_audit(
        tmp_path, monkeypatch, outcomes=[False, True, True, True]
    )
    assert report["target_lineage"]["outcome_target"]["status_counts"] == {
        "lost": 1,
        "survived": 3,
    }


def test_unavailable_outcome_is_counted_without_a_value(tmp_path, monkeypatch):
    report, _, _ = _fake_audit(
        tmp_path, monkeypatch, outcomes=[None, False, False, False]
    )
    assert report["target_lineage"]["outcome_target"]["status_counts"] == {
        "lost": 3,
        "unavailable": 1,
    }


def test_target_source_mismatch_fails_closed(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="target source mismatch"):
        _fake_audit(tmp_path, monkeypatch, provenance_target_source="wrong.source")


def test_nested_behavior_identity_comparison_and_no_inference(tmp_path, monkeypatch):
    report, _, _ = _fake_audit(tmp_path, monkeypatch, behavior=True)
    assert (
        report["action_comparisons"][0]["behavior_action"]["comparison"] == "different"
    )
    report, _, _ = _fake_audit(tmp_path, monkeypatch)
    item = report["action_comparisons"][0]
    assert item["behavior_action"]["action_identity"] is None
    assert item["behavior_action"]["comparison"] == "unavailable"


def test_nested_behavior_same_and_malformed_identity(tmp_path, monkeypatch):
    same = t080._stable(_identity(1), "behavior")
    assert same["status"] == "available"
    with pytest.raises(RuntimeError, match="incomplete behavior identity"):
        t080._stable({"stable_id": "incomplete"}, "behavior")


def test_classification_requires_evidence_and_reports_criteria(tmp_path, monkeypatch):
    report, _, _ = _fake_audit(
        tmp_path, monkeypatch, behavior=True, outcomes=[True] * 4
    )
    assert report["classification"] == "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
    assert report["classification_criteria"]["evidence"]["divergent_rows"] == 4
    assert {
        "assistance_level",
        "act",
        "room_type",
        "source_kind",
        "distribution_kind",
        "encounter_id",
    } <= {key.split("=", 1)[0] for key in report["strata"]}


def test_report_and_manifest_are_deterministic_and_json_safe(tmp_path, monkeypatch):
    report, _, _ = _fake_audit(tmp_path, monkeypatch)
    first_report, first_manifest = t080.write_outputs(report, tmp_path / "out", "audit")
    first = first_report.read_bytes()
    t080.write_outputs(report, tmp_path / "out", "audit")
    assert first == first_report.read_bytes()
    manifest = json.loads(first_manifest.read_text())
    assert json.loads(first_report.read_text())["top_metadata"]
    assert "model_state_dict" not in json.dumps(report)
    clone = json.loads(json.dumps(manifest))
    self_entry = manifest["files"][-1]
    clone["files"][-1]["sha256"] = ""
    assert self_entry["sha256"] == hashlib.sha256(t080._canonical(clone)).hexdigest()
    assert self_entry["bytes"] == first_manifest.stat().st_size


def test_incomplete_action_identity_fails_closed():
    with pytest.raises(RuntimeError):
        t080._stable({"stable_id": "x"}, "teacher")
