"""Script-process fixture for the thin T064 stage-runner adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run(*, stage: dict[str, Any], manifest: dict[str, Any], attempt: Path) -> None:
    del manifest
    (attempt / "executed.txt").write_text(stage["stage"], encoding="utf-8")
