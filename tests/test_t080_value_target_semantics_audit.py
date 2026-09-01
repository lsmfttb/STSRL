from pathlib import Path

from scripts.run_t080_value_target_semantics_audit import audit


def test_frozen_t043_audit_is_fail_closed_and_unresolved() -> None:
    root = Path("artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke")
    report = audit(root / "t043-assist_0-smoke-checkpoint.pt", root / "search-guidance-trainer-budget-3.jsonl")
    assert report["classification"] == "VALUE_TARGET_SEMANTICS_UNRESOLVED"
    assert report["trainer_input"]["record_count"] == 4
    assert report["target_lineage"]["source_behavior_action_status_counts"] == {"unavailable": 4}
    assert all(x["comparison"] == "unavailable" for x in report["action_comparisons"])
    assert report["target_lineage"]["source_outcome_status_counts"] == {"lost": 4}
