from pathlib import Path
from sts_combat_rl.task_doc_guard import check_published_task_doc


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


def test_t109_diagnostic_method_docs_are_discoverable() -> None:
    template = ROOT / "docs" / "tasks" / "TEMPLATE.md"
    method = (template.parent / ".." / "diagnostic_method.md").resolve()
    t109 = (
        ROOT
        / "docs"
        / "tasks"
        / "T109-static-first-root-mapping-action-domain-audit.md"
    )

    template_text = template.read_text(encoding="utf-8")
    t109_text = t109.read_text(encoding="utf-8")
    assert method.is_file()
    assert "## Diagnostic Method Gate" in template_text
    assert "../diagnostic_method.md" in template_text
    assert "## Static Sufficiency Gate" in t109_text
    assert "ROOT_MAPPING_ACTION_DOMAIN_MISMATCH_ESTABLISHED" in t109_text


def test_published_learning_artifact_docs_have_eligibility_contract() -> None:
    offenders = {
        str(path.relative_to(ROOT)): check_published_task_doc(path)
        for path in sorted((ROOT / "docs" / "tasks").glob("T*.md"))
        if check_published_task_doc(path)
    }
    assert "docs/tasks/T081-scientific-artifact-eligibility-gate.md" not in offenders
    assert offenders == {}


def test_published_task_doc_scan_detects_learning_source_omission() -> None:
    from sts_combat_rl.task_doc_guard import check_published_task_doc

    synthetic = ROOT / "tests" / "T082-learning-source-omission.md"
    synthetic.write_text(
        "Artifact Eligibility Required: true\n\nConsumes a learning-source artifact.\n",
        encoding="utf-8",
    )
    try:
        assert check_published_task_doc(synthetic) == [
            "missing Artifact Eligibility Contract section"
        ]
    finally:
        synthetic.unlink()


def test_legacy_task_is_explicitly_exempt():
    synthetic = ROOT / "tests" / "T080-legacy.md"
    synthetic.write_text("# T080\nConsumes a checkpoint.\n", encoding="utf-8")
    try:
        assert check_published_task_doc(synthetic) == []
    finally:
        synthetic.unlink()


def test_new_unmarked_learning_artifact_doc_fails_closed():
    synthetic = ROOT / "tests" / "T082-unmarked-learning-source.md"
    synthetic.write_text(
        "# T082\nConsumes a learning-source artifact.\n", encoding="utf-8"
    )
    try:
        assert check_published_task_doc(synthetic) == [
            "missing Artifact Eligibility Required marker"
        ]
    finally:
        synthetic.unlink()
