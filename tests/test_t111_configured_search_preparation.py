from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands import (
    t111_configured_search_execution_cli as t111_execution,
)
from sts_combat_rl.commands import t111_configured_search_support as t111
from sts_combat_rl.commands.t088_canary import T088CanaryPathError
from sts_combat_rl.commands.t103_particle_diagnostic import T103PathError
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_RESTORE_SCHEMA_ID,
    T085_SELECTION_SCHEMA_ID,
    T085_SOURCE_MANIFEST_SCHEMA_ID,
)


def _raise(error: Exception):
    raise error


def test_t111_repository_root_comes_from_git_at_manifest_parent(
    monkeypatch, tmp_path: Path
):
    repo_root = tmp_path / "repo"
    nested_manifest = (
        repo_root / "artifacts" / "old-task" / "admission" / "manifest.json"
    )
    nested_manifest.parent.mkdir(parents=True)
    nested_manifest.write_text("{}", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=f"{repo_root}\n")

    monkeypatch.setattr(t111.subprocess, "run", fake_run)

    assert t111._git_repository_root(nested_manifest) == repo_root.resolve()
    assert calls[0][0] == [
        "git",
        "-C",
        str(nested_manifest.parent.resolve()),
        "rev-parse",
        "--show-toplevel",
    ]


def test_t111_wsl_git_fallback_handles_windows_managed_worktree_pointer(
    monkeypatch, tmp_path: Path
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").write_text(
        "gitdir: D:/DeadlyCatCoding/STSRL/.git/worktrees/STSRL-T111\n",
        encoding="utf-8",
    )
    manifest = repo_root / "artifacts" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("{}", encoding="utf-8")
    windows_root = "D:\\DeadlyCatCoding\\STSRL-T111"
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "git":
            raise t111.subprocess.CalledProcessError(128, command)
        if command[:2] == ["wslpath", "-w"]:
            return SimpleNamespace(stdout=f"{windows_root}\n")
        if command[0] == "git.exe":
            arguments = command[3:]
            if arguments == ["rev-parse", "--show-toplevel"]:
                return SimpleNamespace(stdout=f"{windows_root}\n")
            if arguments == ["rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=f"{'a' * 40}\n")
            if arguments == ["branch", "--show-current"]:
                return SimpleNamespace(
                    stdout="planner/t111-configured-search-domain-support-reentry\n"
                )
            if arguments == ["status", "--porcelain"]:
                return SimpleNamespace(stdout="")
        raise AssertionError(f"unexpected subprocess command: {command!r}")

    monkeypatch.setattr(t111.sys, "platform", "linux")
    monkeypatch.setattr(t111.subprocess, "run", fake_run)
    monkeypatch.setattr(t111, "_wsl_posix_path", lambda _path: repo_root)

    assert t111._git_repository_root(manifest) == repo_root.resolve()
    assert t111_execution._git_state(repo_root) == (
        "a" * 40,
        "planner/t111-configured-search-domain-support-reentry",
        False,
    )
    assert all(call[0] != "git.exe" or call[2] == windows_root for call in calls)
    assert sum(call[0] == "git.exe" for call in calls) == 4


def test_t111_runtime_fingerprint_and_native_abi_suffix_are_fail_closed(
    tmp_path: Path,
):
    runtime = t111._python_runtime_fingerprint()
    suffix = runtime["extension_suffix"]
    assert runtime["implementation"] == "CPython"
    assert isinstance(suffix, str) and suffix

    matching = tmp_path / f"slaythespire{suffix}"
    matching.write_bytes(b"binary fixture")
    assert (
        t111._validate_native_binary_abi_path(matching, runtime) == matching.resolve()
    )

    mismatch = tmp_path / "slaythespire.cpython-0-unrelated.so"
    mismatch.write_bytes(b"binary fixture")
    try:
        t111._validate_native_binary_abi_path(mismatch, runtime)
    except t111.T111QualificationError as exc:
        assert "ABI suffix" in str(exc)
    else:
        raise AssertionError("incompatible native extension ABI was accepted")


def test_t111_restore_source_bindings_supply_b_and_c_manifest_paths():
    restore_document = {
        "schema_id": T085_RESTORE_SCHEMA_ID,
        "source_bindings": {
            "A": {
                "map": {
                    "path": "/retained/a-map.jsonl",
                    "schema_id": "fixed-cohort-v3-jsonl",
                    "sha256": "a" * 64,
                    "byte_count": 10,
                }
            },
            "B": {
                "map": {
                    "path": "/retained/b-map.jsonl",
                    "schema_id": "assisted-source-pool-v1-jsonl",
                    "sha256": "1" * 64,
                    "byte_count": 11,
                },
                "source_manifest": {
                    "path": "/retained/b-source-manifest.json",
                    "schema_id": T085_SOURCE_MANIFEST_SCHEMA_ID,
                    "sha256": "b" * 64,
                    "byte_count": 12,
                },
            },
            "C": {
                "map": {
                    "path": "/retained/c-map.jsonl",
                    "schema_id": "natural-source-pool-v1-jsonl",
                    "sha256": "2" * 64,
                    "byte_count": 13,
                },
                "source_manifest": {
                    "path": "/retained/c-source-manifest.json",
                    "schema_id": T085_SOURCE_MANIFEST_SCHEMA_ID,
                    "sha256": "c" * 64,
                    "byte_count": 14,
                },
            },
        },
    }

    assert t111._t085_source_manifest_paths(restore_document) == (
        Path("/retained/b-source-manifest.json"),
        Path("/retained/c-source-manifest.json"),
    )


@pytest.mark.parametrize(
    "restore_document",
    [
        {"source_artifacts": {"A": {}, "B": {}, "C": {}}},
        {"source_bindings": {"A": {}, "B": {}}},
        {
            "source_bindings": {
                "A": {},
                "B": {"source_manifest": {"schema_id": "schema", "sha256": "b" * 64}},
                "C": {"source_manifest": {"path": "/c.json", "schema_id": "schema"}},
            }
        },
    ],
)
def test_t111_malformed_or_missing_restore_source_bindings_fail_closed(
    restore_document,
):
    with pytest.raises(t111.T111QualificationError):
        t111._t085_source_manifest_paths(restore_document)


def test_t111_t101_terminal_gate_failure_writes_ineligible_artifact(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(
        t111.t103_particle_diagnostic,
        "_load_t101_terminal_inputs",
        lambda _path: _raise(T103PathError("missing retained terminal")),
    )

    result = t111.prepare_t111_input_qualification_from_paths(
        implementation_head="1" * 40,
        artifact_root=tmp_path,
        source_manifest_path=tmp_path / "unused-source-manifest.json",
    )

    assert result["qualification"]["eligible"] is False
    assert result["qualification"]["terminal_classification"] == (
        "CONFIGURED_SEARCH_DOMAIN_INPUT_INELIGIBLE"
    )
    assert result["qualification"]["python_runtime"] == (
        t111._python_runtime_fingerprint()
    )
    assert result["qualification"]["failure_type"] == "T103PathError"
    assert (tmp_path / "t111-input-qualification.json").is_file()
    assert "readiness_preparation" not in result


def test_t111_t088_path_failure_is_reported_not_name_error(monkeypatch, tmp_path: Path):
    paths: dict[str, Path] = {}
    for role in (
        "t087_formal",
        "t087_report",
        "t087_retention",
        "t085_selection",
        "t085_restore",
        "t085_canonical_a",
        "t085_canonical_b",
        "t085_canonical_c",
    ):
        path = tmp_path / f"{role}.json"
        path.write_text("fixture-retained-by-binding", encoding="utf-8")
        paths[role] = path
    restore_path = paths["t085_restore"]
    restore_path.write_text(
        json.dumps({"schema_id": T085_RESTORE_SCHEMA_ID}), encoding="utf-8"
    )

    def binding(role: str, schema_id: str) -> dict[str, object]:
        data = paths[role].read_bytes()
        return {
            "path": str(paths[role]),
            "schema_id": schema_id,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }

    old_manifest = {
        "path": "historical-T101-manifest",
        "schema_id": "sts-lightspeed-source-manifest-v1",
        "sha256": "a" * 64,
        "size_bytes": 1,
    }
    bindings = {
        "t087_formal": binding("t087_formal", "t087-formal"),
        "t087_report": binding("t087_report", "t087-report"),
        "t087_retention": binding("t087_retention", "t087-retention"),
        "t085_selection": binding("t085_selection", T085_SELECTION_SCHEMA_ID),
        "t085_restore": binding("t085_restore", T085_RESTORE_SCHEMA_ID),
        "t085_canonical_a": binding("t085_canonical_a", "t085-map-a"),
        "t085_canonical_b": binding("t085_canonical_b", "t085-map-b"),
        "t085_canonical_c": binding("t085_canonical_c", "t085-map-c"),
        "native_source_manifest": old_manifest,
    }
    historical = {
        "retained_t101_execution_identity": {
            "implementation_head": "361a77dbe88b2215a92cfe96e4f4c5c243f7ff1c"
        },
        "accepted_t101_source_artifacts": {},
        "t101_terminal_retention_manifest": old_manifest,
        "t101_input_admission": old_manifest,
        "t101_cohort_admission": old_manifest,
        "t101_final_report": old_manifest,
        "t101_cost_report": old_manifest,
    }
    monkeypatch.setattr(
        t111.t103_particle_diagnostic,
        "_load_t101_terminal_inputs",
        lambda _path: (
            {},
            {},
            {"attempted": []},
            historical,
            {"commit": "97f59b620efe5ee1571f8da298c99d1e21c1149b"},
        ),
    )
    monkeypatch.setattr(
        t111.t103_particle_diagnostic,
        "_t101_input_artifact_bindings",
        lambda _admission: bindings,
    )
    monkeypatch.setattr(
        t111,
        "_source_manifest_identity",
        lambda _path: (
            {
                "repository": "lsmfttb/sts_lightspeed",
                "ref": t111.T111_NATIVE_REF,
                "commit": t111.T111_NATIVE_COMMIT,
            },
            {
                "path": "current-T110-manifest",
                "schema_id": "sts-lightspeed-source-manifest-v1",
                "sha256": "b" * 64,
                "size_bytes": 1,
                "capabilities": ["native_stsr009_configuration_aware_root_mapping"],
            },
        ),
    )
    monkeypatch.setattr(
        t111, "_t085_source_manifest_paths", lambda _doc: (tmp_path, tmp_path)
    )
    monkeypatch.setattr(
        t111.t088_canary,
        "_admit_t088_canary_inputs_from_paths",
        lambda **_kwargs: _raise(T088CanaryPathError("T088 retained gate failed")),
    )
    monkeypatch.setattr(
        t111,
        "_verify_historical_manifest_blob",
        lambda _binding, **_kwargs: {
            **dict(_binding),
            "verification": "test-exact-blob",
        },
    )
    monkeypatch.setattr(
        t111,
        "_verify_file_binding",
        lambda binding, *, role: {
            **dict(binding),
            "resolved_path": binding["path"],
            "verification": f"test-file-binding:{role}",
        },
    )
    retained_manifest_path = tmp_path / "t101-terminal-retention-manifest.json"
    retained_manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(t111, "_git_repository_root", lambda _path: tmp_path)

    result = t111.prepare_t111_input_qualification_from_paths(
        implementation_head="2" * 40,
        t101_retention_manifest_path=retained_manifest_path,
        artifact_root=tmp_path / "artifacts",
        source_manifest_path=tmp_path / "unused-source-manifest.json",
    )

    qualification = result["qualification"]
    assert qualification["eligible"] is False
    assert qualification["failure_type"] == "T088CanaryPathError"
    assert (
        "T087_T085_SOURCE_POPULATION_OR_RESTORE_INELIGIBLE"
        in qualification["ineligible_reasons"]
    )
    assert qualification["candidate_execution_started"] is False
    assert result["readiness_preparation"]["candidate_execution_authorized"] is False
