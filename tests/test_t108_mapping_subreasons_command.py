from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands import t108_mapping_subreasons as command
from sts_combat_rl.sim.t108_mapping_subreasons import (
    MANIFEST_SCHEMA,
    REPORT_SCHEMA,
    ROW_SCHEMA,
    T106_REPORT_SCHEMA,
    T106_ROOT_CLASS,
    T108IncompleteError,
    aggregate_t108,
)


def test_t106_report_gate_requires_accepted_full_terminal() -> None:
    report = {
        "schema_id": T106_REPORT_SCHEMA,
        "task_id": "T106",
        "terminal_classification": "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED",
        "selected_count": 343,
        "replayed_count": 343,
        "replayed_failures_with_valid_telemetry": 343,
        "baseline_contradiction_count": 0,
        "telemetry_contract_violation_count": 0,
        "stage_classes": {
            T106_ROOT_CLASS: {"count": 323},
            "PUBLIC_FIDELITY_VALIDATION_FAILURE": {"count": 20},
        },
        "by_stratum": {
            "A": {
                T106_ROOT_CLASS: {"count": 84},
                "PUBLIC_FIDELITY_VALIDATION_FAILURE": {"count": 5},
            },
            "B": {
                T106_ROOT_CLASS: {"count": 174},
                "PUBLIC_FIDELITY_VALIDATION_FAILURE": {"count": 15},
            },
            "C": {
                T106_ROOT_CLASS: {"count": 65},
                "PUBLIC_FIDELITY_VALIDATION_FAILURE": {"count": 0},
            },
        },
    }
    command._validate_t106_report(report)
    report["stage_classes"][T106_ROOT_CLASS]["count"] = 322
    with pytest.raises(T108IncompleteError, match="stage-class counts"):
        command._validate_t106_report(report)


def test_retention_manifest_binds_t108_rows_report_execution_and_provenance(
    tmp_path: Path,
) -> None:
    report = aggregate_t108([], full=False)
    execution = {"schema_id": "t108-execution-record-v1", "task_id": "T108"}
    provenance = {
        "implementation_head": "a" * 40,
        "current_native_identity": {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": "1458522294d967e8985e1fd52cc15d7ebe7f2acd",
        },
    }
    references = command._write_outputs(
        root=tmp_path / "t108-attempt",
        rows=[],
        report=report,
        execution=execution,
        provenance=provenance,
        command="python -m sts_combat_rl.commands.t108_mapping_subreasons",
    )

    manifest_path = tmp_path / "t108-attempt" / "t108-retention-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_id"] == MANIFEST_SCHEMA
    assert manifest["task_id"] == "T108"
    assert manifest["producer_provenance"] == provenance
    assert set(manifest["artifact_references"]) == {
        "candidate_rows",
        "aggregate_report",
        "execution_record",
    }
    expected_schemas = {
        "candidate_rows": ROW_SCHEMA,
        "aggregate_report": REPORT_SCHEMA,
        "execution_record": "t108-execution-record-v1",
    }
    for role, reference in manifest["artifact_references"].items():
        path = Path(reference["path"])
        assert path.is_file()
        assert reference["schema_id"] == expected_schemas[role]
        assert reference["size_bytes"] == path.stat().st_size
        assert reference["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert reference == references[role]
    with pytest.raises(T108IncompleteError, match="refusing to overwrite"):
        command._write_outputs(
            root=tmp_path / "t108-attempt",
            rows=[],
            report=report,
            execution=execution,
            provenance=provenance,
            command="python -m sts_combat_rl.commands.t108_mapping_subreasons",
        )


def test_readiness_binds_exact_head_selection_native_binary_and_resource_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementation_head = "b" * 40
    native_binary = tmp_path / "slaythespire.cpython-313.so"
    native_binary.write_bytes(b"native fixture")
    positions = [0, 1]
    readiness_path = tmp_path / "readiness.json"
    readiness = {
        "task_id": "T108",
        "implementation_head": implementation_head,
        "execution_authorized": True,
        "execution_scope": "bounded_canary",
        "candidate_positions": positions,
        "worker_count": 1,
        "approval_comment_url": "https://github.com/lsmfttb/STSRL/pull/126#issuecomment-1",
        "native_binary": {
            "path": str(native_binary.resolve()),
            "sha256": "c" * 64,
            "source_commit": "1458522294d967e8985e1fd52cc15d7ebe7f2acd",
        },
        "resource_plan": {
            "supervision": "detached_resource_guard",
            "summed_rss_limit_mib": 16384,
            "mem_available_floor_mib": 8192,
            "sample_interval_s": 1,
            "status_path": "/stable/t108.status.json",
        },
    }
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    monkeypatch.setattr(
        command.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=f"{implementation_head}\n"),
    )

    qualified = command._readiness_qualified(
        path=readiness_path,
        implementation_head=implementation_head,
        positions=positions,
        full=False,
        worker_count=1,
        native_binary=native_binary,
        native_binary_sha256="c" * 64,
    )
    assert qualified["approval_comment_url"] == readiness["approval_comment_url"]
    readiness["candidate_positions"] = [1, 0]
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    with pytest.raises(T108IncompleteError, match="does not bind"):
        command._readiness_qualified(
            path=readiness_path,
            implementation_head=implementation_head,
            positions=positions,
            full=False,
            worker_count=1,
            native_binary=native_binary,
            native_binary_sha256="c" * 64,
        )


def test_population_readiness_requires_separate_full_population_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementation_head = "d" * 40
    native_binary = tmp_path / "slaythespire.cpython-313.so"
    native_binary.write_bytes(b"native fixture")
    readiness_path = tmp_path / "readiness.json"
    positions = list(range(323))
    readiness = {
        "task_id": "T108",
        "implementation_head": implementation_head,
        "execution_authorized": True,
        "execution_scope": "full_population",
        "candidate_positions": positions,
        "worker_count": 4,
        "approval_comment_url": "https://github.com/lsmfttb/STSRL/pull/126#issuecomment-2",
        "native_binary": {
            "path": str(native_binary.resolve()),
            "sha256": "e" * 64,
            "source_commit": "1458522294d967e8985e1fd52cc15d7ebe7f2acd",
        },
        "resource_plan": {
            "supervision": "detached_resource_guard",
            "summed_rss_limit_mib": 16384,
            "mem_available_floor_mib": 8192,
            "sample_interval_s": 1,
            "status_path": "/stable/t108-full.status.json",
        },
    }
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    monkeypatch.setattr(
        command.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=f"{implementation_head}\n"),
    )
    with pytest.raises(T108IncompleteError, match="does not bind"):
        command._readiness_qualified(
            path=readiness_path,
            implementation_head=implementation_head,
            positions=positions,
            full=True,
            worker_count=4,
            native_binary=native_binary,
            native_binary_sha256="e" * 64,
        )
    readiness["full_population_authorized"] = True
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    qualified = command._readiness_qualified(
        path=readiness_path,
        implementation_head=implementation_head,
        positions=positions,
        full=True,
        worker_count=4,
        native_binary=native_binary,
        native_binary_sha256="e" * 64,
    )
    assert qualified["resource_plan"]["summed_rss_limit_mib"] == 16384
