"""Fake-only admission tests for the T088 path-bound canary command."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands import t088_canary as command
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_T087_FINAL_REPORT_SHA256,
    T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256,
    T088_T087_RETENTION_MANIFEST_SHA256,
)

SOURCE = {
    "path": "/retained/t085-selection.json",
    "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
    "schema_id": "t085-native-selection-artifact-v1",
    "byte_count": 1,
}


def _rows() -> list[dict[str, object]]:
    rows = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append(
                {
                    "selection_identity": f"{cohort}:{index}",
                    "cohort": cohort,
                    "outcome": "PLAYER_LOSS" if index == 2 else "PLAYER_VICTORY",
                    "entry": {
                        "raw_snapshot": {
                            "act": 2 if cohort == "B" and index == 0 else 1,
                            "room_type": "BOSS" if index == 0 else "MONSTER",
                        }
                    },
                    "terminal": {
                        "raw_snapshot": {
                            "completed_battle_monsters": [
                                {
                                    "id_label": "mUgGeR" if index == 0 else "Cultist",
                                    "current_hp": 10 if index == 0 else 0,
                                    "targetable": False,
                                }
                            ]
                        }
                    },
                }
            )
    rows[1]["outcome"] = "PLAYER_VICTORY"
    return rows


def _maps(rows):
    return {
        cohort: {
            row["selection_identity"]: SimpleNamespace(
                structural_metadata={
                    "act": 2
                    if row["cohort"] == "B" and row["selection_identity"] == "B:0"
                    else 1,
                    "room_type": "BOSS"
                    if row["selection_identity"].endswith(":0")
                    else "MONSTER",
                },
                public_run_context={
                    "candidate_actions": {
                        "availability": "available",
                        "items": [{}, {}],
                    }
                },
            )
            for row in rows
            if row["cohort"] == cohort
        }
        for cohort in ("A", "B", "C")
    }


def _reference(path, sha, schema):
    return {"path": str(path), "sha256": sha, "schema_id": schema, "byte_count": 1}


def test_projection_mechanically_derives_roles_from_bound_raw_and_canonical_facts():
    rows = _rows()
    projected = command._project_t087_cohort({"rows": rows}, SOURCE, _maps(rows))
    assert len(projected) == 413
    assert projected[0]["is_escaping_mugger_case"] is True
    assert projected[1]["is_ordinary_victory"] is True
    assert projected[2]["is_ordinary_loss"] is True
    assert projected[93]["is_later_act_or_boss"] is True
    assert projected[0]["legal_root_action_count"] == 2


def test_bad_path_authorization_cannot_reach_adapter_creation(tmp_path, monkeypatch):
    rows = _rows()
    maps = _maps(rows)
    formal_ref = _reference(
        "formal", T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256, "t087-natural-evidence-v1"
    )
    report_ref = _reference(
        "report",
        T088_T087_FINAL_REPORT_SHA256,
        "t087-dense-combat-diagnostics-report-v1",
    )
    retention_ref = _reference(
        "retention",
        T088_T087_RETENTION_MANIFEST_SHA256,
        "t087-retention-manifest-v1",
    )
    selection_ref = _reference(
        "selection",
        "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
        "t085-native-selection-artifact-v1",
    )
    restore_ref = _reference(
        "restore",
        "0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef",
        "t085-native-selection-restore-evidence-v1",
    )
    documents = {
        "formal": ({"schema_id": "t087-natural-evidence-v1", "rows": rows}, formal_ref),
        "report": (
            {"schema_id": "t087-dense-combat-diagnostics-report-v1"},
            report_ref,
        ),
        "retention": ({"schema_id": "t087-retention-manifest-v1"}, retention_ref),
        "selection": (
            {"schema_id": selection_ref["schema_id"], "cohorts": {"B": []}},
            selection_ref,
        ),
        "restore": ({"schema_id": restore_ref["schema_id"]}, restore_ref),
        "authorization": (
            {"schema_id": command.T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID},
            _reference(
                "authorization",
                "a" * 64,
                command.T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID,
            ),
        ),
    }
    monkeypatch.setattr(
        command, "_read_exact_json", lambda path, **_: documents[path.name]
    )
    monkeypatch.setattr(
        command, "_load_canonical_maps", lambda **_: (maps, {"A": {}, "B": {}, "C": {}})
    )
    monkeypatch.setattr(
        command,
        "load_t087_t085_input_gate",
        lambda **_: SimpleNamespace(
            source_selection_manifest_identity=SOURCE, cohorts={}
        ),
    )
    created = False

    def adapter_factory():
        nonlocal created
        created = True
        return object()

    with pytest.raises(command.T088CanaryPathError, match="exact input binding"):
        command.run_t088_authorized_canary_from_paths(
            authorization_path=tmp_path / "authorization",
            implementation_head="a" * 40,
            t087_formal_path=tmp_path / "formal",
            t087_report_path=tmp_path / "report",
            t087_retention_path=tmp_path / "retention",
            t085_selection_path=tmp_path / "selection",
            t085_restore_path=tmp_path / "restore",
            a_pool_path=tmp_path / "a",
            b_pool_path=tmp_path / "b",
            c_pool_path=tmp_path / "c",
            b_source_manifest_path=tmp_path / "b-manifest",
            c_source_manifest_path=tmp_path / "c-manifest",
            output_path=tmp_path / "retained" / "canary.json",
            artifact_root=tmp_path / "retained",
            adapter_factory=adapter_factory,
        )
    assert created is False


def test_restore_source_bindings_are_the_only_accepted_canonical_source_shape():
    assert command._source_references(
        {"source_bindings": {"A": {}, "B": {}, "C": {}}}
    ) == {"A": {}, "B": {}, "C": {}}
    with pytest.raises(command.T088CanaryPathError, match="source bindings"):
        command._source_references(
            {"input_artifact": {"source_artifacts": {"A": {}, "B": {}, "C": {}}}}
        )


def test_path_authorization_rejects_non_exact_head_before_runner_or_adapter():
    with pytest.raises(command.T088CanaryPathError, match="full SHA-1"):
        command._validate_path_authorization(
            {
                "schema_id": command.T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID,
                "task_id": "T088",
                "authorization_kind": "bounded_canary",
                "authorized": True,
                "authorization_id": "fake",
                "implementation_head": "not-a-sha",
                "input_identities_sha256": "unused",
                "maintainer_attestation": {},
            },
            implementation_head="not-a-sha",
            inputs={},
        )


def test_cli_routes_only_explicit_paths_and_emits_concise_success_json(
    tmp_path, monkeypatch, capsys
):
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return {
            "artifact": {
                "path": "/retained/t088-canary.json",
                "sha256": "a" * 64,
                "size_bytes": 9,
                "schema_id": "t088-canary-evidence-v1",
            },
            "worker_count": 1,
            "single_worker_reason": "bounded canary has at most 20 executions",
        }

    monkeypatch.setattr(command, "run_t088_authorized_canary_from_paths", fake_run)
    paths = {
        "authorization": tmp_path / "authorization.json",
        "t087-formal": tmp_path / "formal.json",
        "t087-report": tmp_path / "report.json",
        "t087-retention": tmp_path / "retention.json",
        "t085-selection": tmp_path / "selection.json",
        "t085-restore": tmp_path / "restore.json",
        "a-pool": tmp_path / "a.jsonl",
        "b-pool": tmp_path / "b.jsonl",
        "c-pool": tmp_path / "c.jsonl",
        "b-source-manifest": tmp_path / "b-manifest.json",
        "c-source-manifest": tmp_path / "c-manifest.json",
        "output": tmp_path / "out" / "canary.json",
        "artifact-root": tmp_path / "out",
    }
    argv = ["--implementation-head", "a" * 40]
    for flag, path in paths.items():
        argv.extend((f"--{flag}", str(path)))

    assert command.main(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "schema_id": "t088-canary-command-result-v1",
        "task_id": "T088",
        "artifact": {
            "path": "/retained/t088-canary.json",
            "sha256": "a" * 64,
            "size_bytes": 9,
            "schema_id": "t088-canary-evidence-v1",
        },
        "worker_count": 1,
        "single_worker_reason": "bounded canary has at most 20 executions",
    }
    assert observed["implementation_head"] == "a" * 40
    assert observed["authorization_path"] == paths["authorization"]
    assert observed["output_path"] == paths["output"]
    assert observed["artifact_root"] == paths["artifact-root"]


def test_hash_drift_fails_before_any_schema_is_trusted(tmp_path):
    artifact = tmp_path / "formal.json"
    artifact.write_text(json.dumps({"schema_id": "t087-natural-evidence-v1"}))
    with pytest.raises(command.T088CanaryPathError, match="SHA-256"):
        command._read_exact_json(
            artifact,
            expected_sha256="0" * 64,
            schema_id="t087-natural-evidence-v1",
            label="fake formal evidence",
        )
