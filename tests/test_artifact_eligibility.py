import json

import pytest

from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
    evaluate_eligibility,
)

IDENTITY = (
    "/retained/checkpoint-runs1000.pt",
    "checkpoint",
    "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3",
)


def qualification(path="/retained/checkpoint-runs1000.pt", trainer_count=4):
    return ArtifactQualification(
        artifact={"id": path, "kind": "checkpoint"},
        integrity={
            "sha256": "ab68439df429f603816f30064484cc99f33611a196ba456103397fc7ef8ed5f3"
        },
        facts={
            "trainer_record_count": Fact(trainer_count),
            "override_kind": Fact("smoke"),
            "training_gate": Fact("passed"),
            "source.act": Fact([1]),
            "coverage.acts": Fact([1]),
        },
    )


def test_exact_facts_and_misleading_filename_do_not_upgrade_scale():
    q = qualification()
    req = EligibilityRequirements(
        "scientific_quality_claim",
        "checkpoint-conditional",
        (Predicate("trainer_record_count", "min", 1),),
        *IDENTITY,
    )
    report = evaluate_eligibility(q, req)
    assert report["eligible"] is False
    assert any(
        p["fact"] == "trainer_record_count" and p["observed"] == 4
        for p in report["predicates"]
    )
    json.dumps(report, sort_keys=True)


def test_unknown_required_fact_fails_closed():
    q = qualification()
    req = EligibilityRequirements(
        "diagnostic_mechanism",
        "bounded mechanism",
        (Predicate("teacher_record_count", "min", 1),),
    )
    result = evaluate_eligibility(q, req)
    assert result["eligible"] is False
    assert any(
        p["fact"] == "teacher_record_count"
        and p["observed"] == {"status": "unavailable"}
        for p in result["predicates"]
    )


def test_empty_quality_requirements_fail_closed():
    result = evaluate_eligibility(
        qualification(),
        EligibilityRequirements(
            "scientific_quality_claim", "model quality", (), *IDENTITY
        ),
    )
    assert result["eligible"] is False


def test_unavailable_override_fact_fails_quality_claim_closed():
    q = qualification()
    q.facts["override_kind"] = Fact.unavailable("legacy provenance omitted override")
    result = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "scientific_quality_claim",
            "model quality",
            (
                Predicate("trainer_record_count", "min", 1),
                Predicate("coverage.acts", "contains", 1),
            ),
            *IDENTITY,
        ),
    )
    assert result["eligible"] is False
    assert any(
        p["fact"] == "override_kind" and not p["result"] for p in result["predicates"]
    )


@pytest.mark.parametrize(
    "mode,boundary",
    [
        ("historical_reproduction", "original historical result only"),
        ("diagnostic_mechanism", "artifact-conditional mechanism only"),
        ("scientific_quality_claim", "new model-quality claim"),
    ],
)
def test_reuse_modes_and_claim_boundaries_are_preserved(mode, boundary):
    q = qualification()
    if mode == "scientific_quality_claim":
        q = qualification()
        q.facts["override_kind"] = Fact("none")
        if mode == "scientific_quality_claim":
            predicates = (
                Predicate("trainer_record_count", "min", 1),
                Predicate("coverage.acts", "contains", 1),
            )
        else:
            predicates = (Predicate("training_gate", required="passed"),)
    else:
        predicates = (Predicate("training_gate", required="passed"),)
    result = evaluate_eligibility(
        q,
        EligibilityRequirements(mode, boundary, predicates, *IDENTITY),
    )
    assert result["eligible"] is True
    assert result["reuse_mode"] == mode
    assert result["claim_boundary"] == boundary


def test_report_is_deterministic():
    req = EligibilityRequirements(
        "historical_reproduction",
        "original",
        (
            Predicate("override_kind", required="smoke"),
            Predicate("trainer_record_count", "min", 4),
        ),
        *IDENTITY,
    )
    assert evaluate_eligibility(qualification(), req) == evaluate_eligibility(
        qualification(), req
    )


def test_malformed_mode_fails_clearly():
    with pytest.raises(ValueError, match="unknown reuse mode"):
        evaluate_eligibility(
            qualification(), EligibilityRequirements("other", "none", (), *IDENTITY)
        )


def test_historical_identity_is_required_and_mismatch_fails_closed():
    q = qualification()
    missing = evaluate_eligibility(
        q, EligibilityRequirements("historical_reproduction", "original", ())
    )

    missing_diagnostic = evaluate_eligibility(
        q, EligibilityRequirements("diagnostic_mechanism", "original", ())
    )
    assert not missing["eligible"] and not missing_diagnostic["eligible"]
    wrong_sha = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "historical_reproduction",
            "original",
            (),
            "/retained/checkpoint-runs1000.pt",
            "checkpoint",
            "wrong",
        ),
    )
    wrong_kind = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "historical_reproduction",
            "original",
            (),
            "/retained/checkpoint-runs1000.pt",
            "dataset",
            q.integrity["sha256"],
        ),
    )
    wrong_diag_sha = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "diagnostic_mechanism",
            "original",
            (),
            "/retained/checkpoint-runs1000.pt",
            "checkpoint",
            "wrong",
        ),
    )
    wrong_diag_kind = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "diagnostic_mechanism",
            "original",
            (),
            "/retained/checkpoint-runs1000.pt",
            "dataset",
            q.integrity["sha256"],
        ),
    )
    assert not wrong_sha["eligible"] and not wrong_kind["eligible"]
    assert not wrong_diag_sha["eligible"] and not wrong_diag_kind["eligible"]


def test_mandatory_checks_cannot_be_spoofed_by_fact_names():
    q = qualification()
    q.facts["__artifact_identity_requirements"] = Fact(True)
    q.facts["__explicit_scale_predicate_required"] = Fact(True)
    q.facts["__explicit_coverage_predicate_required"] = Fact(True)
    result = evaluate_eligibility(
        q, EligibilityRequirements("scientific_quality_claim", "quality", (), *IDENTITY)
    )
    assert not result["eligible"]


def test_quality_override_safety_cannot_be_permissed_by_consumer_predicate():
    q = qualification()
    result = evaluate_eligibility(
        q,
        EligibilityRequirements(
            "scientific_quality_claim",
            "quality",
            (
                Predicate("trainer_record_count", "min", 1),
                Predicate("coverage.acts", "contains", 1),
                Predicate("override_kind", "equals", "smoke"),
            ),
            *IDENTITY,
        ),
    )
    assert not result["eligible"]
