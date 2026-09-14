from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CURRENT_WORKFLOW_SUMMARIES = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "project_architecture.md",
)


STALE_WORKFLOW_PHRASES = (
    "read-only planner",
    "repository-read-only planner",
    "owns merge decisions",
    "maintainer publishes and manages tasks",
    (
        "main maintainer owns project documentation, task publication "
        "and lifecycle state"
    ),
)


def test_authoritative_workflow_keeps_dual_acceptance_before_planner_landing() -> None:
    workflow = (ROOT / "docs" / "collaboration_workflow.md").read_text(
        encoding="utf-8"
    )

    assert (
        "Both final acceptances must refer to the same exact final PR head."
        in workflow
    )
    assert "Planner may then merge the task PR directly" in workflow
    assert (
        "Before final acceptance, Maintainer normally places factual terminal results"
        in workflow
    )


def test_current_workflow_summaries_do_not_reintroduce_stale_role_ownership() -> None:
    offenders: list[str] = []
    for path in CURRENT_WORKFLOW_SUMMARIES:
        text = path.read_text(encoding="utf-8").casefold()
        for phrase in STALE_WORKFLOW_PHRASES:
            if phrase.casefold() in text:
                offenders.append(f"{path.relative_to(ROOT)}: {phrase}")

    assert offenders == []


def test_high_exposure_summaries_point_to_current_landing_rule() -> None:
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "project_architecture.md").read_text(
        encoding="utf-8"
    )

    assert "only then may the Planner land the task" in root_readme
    assert "task landing is not authorized by Maintainer acceptance alone" in agents
    assert "Planner may land the task directly" in agents
    assert "collaboration_workflow.md` overrides any shorter summary" in docs_readme
    assert "does not define a second workflow" in architecture
