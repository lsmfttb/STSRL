"""Small deterministic guard for learning-artifact task specifications."""

import re
from pathlib import Path

LEARNING_ARTIFACT = re.compile(r"\b(checkpoint|teacher|trainer|dataset|source artifact)\b", re.I)
CONTRACT = "## Artifact Eligibility Contract"
REQUIRED_MARKER = "Artifact Eligibility Required: true"


def artifact_contract_errors(text: str) -> list[str]:
    if not LEARNING_ARTIFACT.search(text):
        return []
    if CONTRACT not in text:
        return ["missing Artifact Eligibility Contract section"]
    section = text.split(CONTRACT, 1)[1].split("\n## ", 1)[0].lower()
    required = ("inputs", "reuse mode", "claim boundary", "required predicates", "unavailable")
    return [f"contract missing {item}" for item in required if item not in section]


def check_task_doc(path: str | Path) -> list[str]:
    return artifact_contract_errors(Path(path).read_text(encoding="utf-8"))


def check_published_task_doc(path: str | Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return artifact_contract_errors(text) if REQUIRED_MARKER in text else []
