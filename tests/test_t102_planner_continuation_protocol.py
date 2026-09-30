from pathlib import Path


CURRENT = {
    "notification_id": "github-pr-comment:100",
    "planner_decision_comment_id": "200",
    "decision_exact_head": "abc123",
    "continuation_action_kind": "MERGE_PR",
    "continuation_action_key": "lsmfttb/STSRL#125@abc123",
}


def terminal_record(kind: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        **CURRENT,
        "kind": kind,
        "status": "COMPLETED" if kind == "completion" else "BLOCKED",
    }
    if kind == "completion":
        record["completion_evidence"] = "merged-pr=125;main=merge123"
    else:
        record["blocker"] = "mergeability failure"
        record["next_owner"] = "MAINTAINER"
    record.update(overrides)
    return record


def _is_relevant(record: dict[str, object]) -> bool:
    return (
        record.get("notification_id") == CURRENT["notification_id"]
        or record.get("planner_decision_comment_id")
        == CURRENT["planner_decision_comment_id"]
    )


def _is_valid(record: dict[str, object]) -> bool:
    for field in (
        "notification_id",
        "planner_decision_comment_id",
        "decision_exact_head",
        "continuation_action_kind",
        "continuation_action_key",
    ):
        if record.get(field) != CURRENT[field]:
            return False

    if record.get("kind") == "completion":
        return bool(record.get("completion_evidence")) and record.get("status") == "COMPLETED"
    if record.get("kind") == "blocker":
        return (
            record.get("status") == "BLOCKED"
            and bool(record.get("blocker"))
            and record.get("next_owner") in {"MAINTAINER", "USER"}
        )
    return False


def preflight(records: list[dict[str, object]]) -> str:
    relevant = [record for record in records if _is_relevant(record)]
    if not relevant:
        return "NO_RELEVANT_TERMINAL_EVIDENCE"
    if len(relevant) != 1:
        return "TERMINAL_EVIDENCE_INVALID"

    record = relevant[0]
    if not _is_valid(record):
        return "TERMINAL_EVIDENCE_INVALID"
    if record["kind"] == "completion":
        return "ONE_VALID_COMPLETION"
    return "ONE_VALID_BLOCKER"


def poll_state(
    *,
    decision_present: bool,
    continuation_owner: str | None = None,
    terminal_records: list[dict[str, object]] | None = None,
) -> tuple[str, bool]:
    if not decision_present:
        return "WAITING_FOR_PLANNER_DECISION", True
    if continuation_owner == "MAINTAINER" or continuation_owner == "NONE":
        return "HANDOFF_READY", False
    if continuation_owner != "PLANNER":
        return "DECISION_INVALID", False

    result = preflight(terminal_records or [])
    if result == "TERMINAL_EVIDENCE_INVALID":
        return result, False
    if result == "ONE_VALID_COMPLETION":
        return "PLANNER_CONTINUATION_COMPLETED", False
    if result == "ONE_VALID_BLOCKER":
        return "PLANNER_CONTINUATION_BLOCKED", False
    return "WAITING_FOR_PLANNER_CONTINUATION", True


def test_zero_relevant_terminal_evidence_is_only_planner_wait_case() -> None:
    unrelated = terminal_record(
        "completion",
        notification_id="github-pr-comment:other",
        planner_decision_comment_id="other",
    )
    assert preflight([unrelated]) == "NO_RELEVANT_TERMINAL_EVIDENCE"
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[unrelated],
    ) == ("WAITING_FOR_PLANNER_CONTINUATION", True)


def test_malformed_relevant_terminal_evidence_fails_closed_without_reminder() -> None:
    malformed = terminal_record("completion", decision_exact_head="wrong")
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[malformed],
    ) == ("TERMINAL_EVIDENCE_INVALID", False)


def test_completion_plus_blocker_fails_closed_before_either_terminal_branch() -> None:
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[terminal_record("completion"), terminal_record("blocker")],
    ) == ("TERMINAL_EVIDENCE_INVALID", False)


def test_duplicate_same_type_terminal_evidence_fails_closed() -> None:
    completion = terminal_record("completion")
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[completion, dict(completion)],
    ) == ("TERMINAL_EVIDENCE_INVALID", False)

    blocker = terminal_record("blocker")
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[blocker, dict(blocker)],
    ) == ("TERMINAL_EVIDENCE_INVALID", False)


def test_exactly_one_valid_completion_resolves_before_waiting() -> None:
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[terminal_record("completion")],
    ) == ("PLANNER_CONTINUATION_COMPLETED", False)


def test_exactly_one_valid_blocker_resolves_before_waiting() -> None:
    assert poll_state(
        decision_present=True,
        continuation_owner="PLANNER",
        terminal_records=[terminal_record("blocker")],
    ) == ("PLANNER_CONTINUATION_BLOCKED", False)


def test_partial_identity_match_is_relevant_then_malformed_not_unrelated() -> None:
    partial = terminal_record(
        "completion",
        planner_decision_comment_id="wrong",
        decision_exact_head="wrong",
    )
    assert partial["notification_id"] == CURRENT["notification_id"]
    assert preflight([partial]) == "TERMINAL_EVIDENCE_INVALID"


def test_governance_documents_link_and_name_the_new_t102_states() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = (root / "docs/tasks/ARCHIVE.md").read_text(encoding="utf-8")
    workflow = (root / "docs/collaboration_workflow.md").read_text(encoding="utf-8")
    coordination = (root / "docs/implementer_coordination.md").read_text(
        encoding="utf-8"
    )
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")

    amendment = "T102-planner-response-reminder-amendment.md"
    assert amendment in archive
    assert amendment in workflow
    assert amendment in coordination
    assert amendment in agents

    for text in (workflow, coordination, agents):
        assert "WAITING_FOR_PLANNER_DECISION" in text
        assert "WAITING_FOR_PLANNER_CONTINUATION" in text
        assert "MERGE_PR" in text

    assert "TERMINAL_EVIDENCE_INVALID" in workflow
    assert "NO_RELEVANT_TERMINAL_EVIDENCE" in coordination
