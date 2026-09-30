from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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


def _mock_git_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    head: str,
    worktree_status: dict[str, str],
) -> None:
    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[-2:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=f"{head}\n")
        if command[-3:] == ["status", "--porcelain=v1", "--untracked-files=all"]:
            return SimpleNamespace(stdout=worktree_status["value"])
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(command.subprocess, "run", run)


def _write_fixture(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _path_reference(path: Path) -> dict[str, str]:
    return {"path": str(path)}


def _source_provenance_fixture(tmp_path: Path) -> tuple[dict[str, object], Path]:
    root = tmp_path / "accepted-inputs"
    t101_path = _write_fixture(
        root / "t101-terminal-retention-manifest.json",
        b'{"schema_id":"t101-terminal-retention-manifest-v1"}\n',
    )
    t101_reference = {
        "path": str(t101_path),
        "schema_id": "t101-terminal-retention-manifest-v1",
        "sha256": command._sha256(t101_path),
        "size_bytes": t101_path.stat().st_size,
    }

    t103_root = root / "t103"
    t103_candidate_path = _write_fixture(
        t103_root / "candidate-diagnostics.json", b"[]\n"
    )
    t103_manifest_path = _write_fixture(
        t103_root / "t103-retention-manifest.json", b'{"schema_id":"fixture"}\n'
    )
    t103_execution_path = _write_fixture(
        t103_root / "t103-execution-record.json", b'{"task_id":"T103"}\n'
    )

    t085_root = root / "t085"
    source_artifacts = {}
    for name in (
        "t085_canonical_a",
        "t085_canonical_b",
        "t085_canonical_c",
        "t085_selection",
        "t085_restore",
        "t087_formal",
        "t087_report",
        "t087_retention",
    ):
        filename = f"{name}.json"
        path = _write_fixture(t085_root / filename, b"{}\n")
        source_artifacts[name] = _path_reference(path)
    _write_fixture(t085_root / "cohort-b-source-manifest.json", b"{}\n")
    _write_fixture(t085_root / "cohort-c-source-manifest.json", b"{}\n")

    provenance: dict[str, object] = {
        "historical_t101_bindings": {
            "t101_terminal_retention_manifest": t101_reference,
            "accepted_t101_source_artifacts": source_artifacts,
        },
        "accepted_t103": {
            "manifest": {
                "artifact_references": {
                    "candidate_diagnostics": {"path": str(t103_candidate_path)}
                }
            },
            "manifest_sha256": command._sha256(t103_manifest_path),
            "execution_reference": {
                "path": str(t103_execution_path),
                "sha256": command._sha256(t103_execution_path),
            },
        },
    }
    return provenance, t101_path


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


def test_replay_requires_an_explicit_resource_status_path() -> None:
    args = SimpleNamespace(
        implementation_head="a" * 40,
        output_root=Path("/tmp/t108-output"),
        native_binary=Path("/tmp/slaythespire.so"),
        native_binary_sha256="b" * 64,
        resource_status_path=None,
    )

    with pytest.raises(T108IncompleteError, match="resource_status_path"):
        command._require_replay_arguments(args)


def test_t101_terminal_manifest_resolves_from_historical_sibling_fail_closed(
    tmp_path: Path,
) -> None:
    provenance, expected_path = _source_provenance_fixture(tmp_path)
    historical = provenance["historical_t101_bindings"]
    assert isinstance(historical, dict)
    source_artifacts = historical["accepted_t101_source_artifacts"]
    assert isinstance(source_artifacts, dict)
    assert "t101_terminal_retention_manifest" not in source_artifacts

    resolved = command._source_inputs_from_t106_provenance(provenance)
    assert resolved["t101_retention_manifest"] == expected_path

    missing_sibling = deepcopy(provenance)
    missing_historical = missing_sibling["historical_t101_bindings"]
    missing_artifacts = missing_historical["accepted_t101_source_artifacts"]
    missing_artifacts["t101_terminal_retention_manifest"] = missing_historical.pop(
        "t101_terminal_retention_manifest"
    )
    with pytest.raises(T108IncompleteError, match="T101 terminal retention manifest"):
        command._source_inputs_from_t106_provenance(missing_sibling)

    wrong_reference = deepcopy(provenance)
    wrong_historical = wrong_reference["historical_t101_bindings"]
    wrong_historical["t101_terminal_retention_manifest"]["sha256"] = "0" * 64
    with pytest.raises(T108IncompleteError, match="hash or schema reference mismatch"):
        command._source_inputs_from_t106_provenance(wrong_reference)


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
    resource_status_path = tmp_path / "stable" / "t108.status.json"
    git_state = {"value": ""}
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
            "status_path": str(resource_status_path),
        },
    }
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    _mock_git_state(monkeypatch, head=implementation_head, worktree_status=git_state)

    qualified = command._readiness_qualified(
        path=readiness_path,
        implementation_head=implementation_head,
        positions=positions,
        full=False,
        worker_count=1,
        native_binary=native_binary,
        native_binary_sha256="c" * 64,
        resource_status_path=resource_status_path,
    )
    assert qualified["approval_comment_url"] == readiness["approval_comment_url"]
    assert qualified["resource_status_path"] == str(resource_status_path.resolve())
    with pytest.raises(T108IncompleteError, match="clean exact head"):
        command._readiness_qualified(
            path=readiness_path,
            implementation_head=implementation_head,
            positions=positions,
            full=False,
            worker_count=1,
            native_binary=native_binary,
            native_binary_sha256="c" * 64,
            resource_status_path=tmp_path / "stable" / "other.status.json",
        )
    git_state["value"] = "?? local_untracked_code.py\n"
    with pytest.raises(T108IncompleteError, match="clean exact head"):
        command._readiness_qualified(
            path=readiness_path,
            implementation_head=implementation_head,
            positions=positions,
            full=False,
            worker_count=1,
            native_binary=native_binary,
            native_binary_sha256="c" * 64,
            resource_status_path=resource_status_path,
        )
    git_state["value"] = ""
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
            resource_status_path=resource_status_path,
        )


def test_population_readiness_requires_separate_full_population_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    implementation_head = "d" * 40
    native_binary = tmp_path / "slaythespire.cpython-313.so"
    native_binary.write_bytes(b"native fixture")
    readiness_path = tmp_path / "readiness.json"
    positions = list(range(323))
    resource_status_path = tmp_path / "stable" / "t108-full.status.json"
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
            "status_path": str(resource_status_path),
        },
    }
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    _mock_git_state(
        monkeypatch,
        head=implementation_head,
        worktree_status={"value": ""},
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
            resource_status_path=resource_status_path,
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
        resource_status_path=resource_status_path,
    )
    assert qualified["resource_plan"]["summed_rss_limit_mib"] == 16384
