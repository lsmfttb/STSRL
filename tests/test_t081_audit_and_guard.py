import json

from sts_combat_rl.t081_historical_audit import build_audit
from sts_combat_rl.task_doc_guard import artifact_contract_errors, check_published_task_doc
from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
    evaluate_eligibility,
)


def test_audit_is_deterministic_and_covers_required_tasks():
    audit = build_audit()
    assert audit == build_audit()
    assert {row["task"] for row in audit["claims"]} == {"T044", "T047", "T048", "T050", "T051", "T052", "T062", "T070"}
    assert audit["claims"][0]["qualification"]["trainer_record_count"] == 4
    assert {row["task"]: row["integrity"]["sha256"] for row in audit["claims"]} == {
        "T044": "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3",
        "T047": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T048": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T050": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T051": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T052": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T062": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        "T070": "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
    }
    assert all("consumer_decisions" in row for row in audit["claims"])
    json.dumps(audit, sort_keys=True)


def test_task_guard_exempts_non_artifact_and_checks_contract_fields():
    assert artifact_contract_errors("# TXXX\n\n## Dependencies\nnone") == []
    errors = artifact_contract_errors("## Dependencies\nConsumes a learned checkpoint")
    assert errors == ["missing Artifact Eligibility Contract section"]
    complete = """Consumes a learned checkpoint\n## Artifact Eligibility Contract\ninputs; reuse mode; claim boundary; required predicates; unavailable fact behavior\n## Scope\nsmall"""
    assert artifact_contract_errors(complete) == []
    assert check_published_task_doc(__file__) == []


def test_both_t043_fixtures_are_reproduction_diagnostic_only():
    for artifact_id, sha in (
        ("t043-assist_0-smoke", "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"),
        ("t043-main-runs1000-assist_0-s4", "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3"),
    ):
        qualification = ArtifactQualification(
            {"id": artifact_id, "path": "runs1000/checkpoint.pt"},
            {"trainer_record_count": Fact(4), "override_kind": Fact("smoke")},
            {"sha256": sha},
        )
        historical = evaluate_eligibility(
            qualification, EligibilityRequirements("historical_reproduction", "original", ())
        )
        diagnostic = evaluate_eligibility(
            qualification, EligibilityRequirements("diagnostic_mechanism", "conditional", (Predicate("trainer_record_count", "min", 1),))
        )
        quality = evaluate_eligibility(
            qualification, EligibilityRequirements("scientific_quality_claim", "general", (Predicate("trainer_record_count", "min", 1000),))
        )
        assert historical["eligible"] and diagnostic["eligible"]
        assert not quality["eligible"]
