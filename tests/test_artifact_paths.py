from __future__ import annotations

from pathlib import Path

import pytest

from sts_combat_rl import artifact_paths


def test_runtime_resolver_translates_windows_path_without_rewriting_identity(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "d" / "frozen" / "source.jsonl"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("source", encoding="utf-8")

    resolved = artifact_paths.resolve_runtime_artifact_path(
        r"D:\frozen\source.jsonl",
        wsl_mount_root=tmp_path,
        runtime_platform="posix",
    )

    assert resolved == {
        "persistent_path": r"D:\frozen\source.jsonl",
        "runtime_path": str(runtime),
    }


def test_runtime_resolver_preserves_posix_absolute_identity(monkeypatch) -> None:
    monkeypatch.setattr(artifact_paths.Path, "is_file", lambda _path: True)
    resolved = artifact_paths.resolve_runtime_artifact_path(
        "/stable/artifacts/source.jsonl", runtime_platform="posix"
    )
    assert resolved["persistent_path"] == "/stable/artifacts/source.jsonl"


def test_runtime_resolver_translates_wsl_mount_without_rewriting_identity(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "source.jsonl"
    runtime.write_text("source", encoding="utf-8")
    drive = runtime.drive.rstrip(":").lower()
    relative = runtime.relative_to(runtime.anchor).as_posix()
    persistent = f"/mnt/{drive}/{relative}"

    resolved = artifact_paths.resolve_runtime_artifact_path(
        persistent,
        runtime_platform="nt",
    )

    assert resolved == {
        "persistent_path": persistent,
        "runtime_path": str(runtime),
    }


@pytest.mark.parametrize(
    "path",
    [
        "relative/file.jsonl",
        r"\\server\share\file.jsonl",
        r"D:drive-relative.jsonl",
        r"D:\frozen\..\escape.jsonl",
    ],
)
def test_runtime_resolver_rejects_ambiguous_or_traversing_paths(path: str) -> None:
    with pytest.raises(ValueError):
        artifact_paths.resolve_runtime_artifact_path(path, runtime_platform="posix")
