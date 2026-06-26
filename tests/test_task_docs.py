from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_task_files_do_not_duplicate_lifecycle_status() -> None:
    task_docs = sorted((ROOT / "docs" / "tasks").glob("T*.md"))
    offenders: list[str] = []
    for path in task_docs:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.startswith("Status:"):
                offenders.append(f"{path.relative_to(ROOT)}:{line_number}")

    assert offenders == []


def test_status_field_is_reserved_for_task_index() -> None:
    current_docs = [
        path
        for path in (ROOT / "docs").rglob("*.md")
        if "history" not in path.relative_to(ROOT / "docs").parts
    ]
    offenders: list[str] = []
    for path in current_docs:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.startswith("Status:"):
                offenders.append(f"{path.relative_to(ROOT)}:{line_number}")

    assert offenders == []
