"""Fail-closed runtime resolution for persisted artifact identities."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath


def resolve_runtime_artifact_path(
    persistent_path: object,
    *,
    wsl_mount_root: Path = Path("/mnt"),
    runtime_platform: str | None = None,
) -> dict[str, str]:
    """Resolve an absolute persisted path without mutating its stored identity.

    Windows paths are translated only for a POSIX runtime, while POSIX absolute
    paths are retained exactly.  The returned mapping records both spellings so
    callers can persist auditable runtime evidence.
    """

    if not isinstance(persistent_path, str) or not persistent_path:
        raise ValueError("artifact identity path must be a non-empty string")
    platform = os.name if runtime_platform is None else runtime_platform
    if platform not in {"nt", "posix"}:
        raise ValueError("artifact runtime platform is unsupported")
    if persistent_path.startswith(("\\\\", "//")):
        raise ValueError("UNC artifact paths are not permitted")

    windows = PureWindowsPath(persistent_path)
    if windows.drive:
        if not windows.root or len(windows.drive) != 2 or windows.drive[1] != ":":
            raise ValueError("artifact path must be an absolute Windows drive path")
        parts = windows.parts[1:]
        if any(part in {"..", "."} for part in parts):
            raise ValueError("artifact path must not contain traversal")
        resolved = (
            Path(str(windows))
            if platform == "nt"
            else wsl_mount_root / windows.drive[0].lower() / Path(*parts)
        )
    else:
        posix = PurePosixPath(persistent_path)
        if not posix.is_absolute():
            raise ValueError("artifact path must be absolute")
        if any(part in {"..", "."} for part in posix.parts):
            raise ValueError("artifact path must not contain traversal")
        resolved = Path(persistent_path)

    if not resolved.is_file():
        raise ValueError(f"artifact runtime path is missing: {resolved}")
    return {"persistent_path": persistent_path, "runtime_path": str(resolved)}
