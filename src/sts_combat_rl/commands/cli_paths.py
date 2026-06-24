"""Small path helpers shared by CLI routing modules."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path


def timestamped_path(directory: Path, prefix: str, suffix: str) -> Path:
    """Return a timestamped path that does not currently exist."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{prefix}_{timestamp}_{os.getpid()}"
    candidate = directory / f"{base_name}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{base_name}_{counter}{suffix}"
        counter += 1
    return candidate
