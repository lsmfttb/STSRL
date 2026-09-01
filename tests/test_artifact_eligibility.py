import json

import pytest

from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
    evaluate_eligibility,
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
        },
    )


def test_exact_facts_and_misleading_filename_do_not_upgrade_scale():
    q = qualification()
    req = EligibilityRequirements(
        "scientific_quality_claim",
        "checkpoint-conditional",
        (Predicate("trainer_record_count", "min", 1000),),
    )
    report = evaluate_eligibility(q, req)
    assert report["eligible"] is False
    assert report["predicates"][0]["observed"] == 4
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
    assert result["predicates"][0]["observed"] == {"status": "unavailable"}


def test_empty_quality_requirements_fail_closed():
    result = evaluate_eligibility(
        qualification(),
        EligibilityRequirements("scientific_quality_claim", "model quality", ()),
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
            (Predicate("trainer_record_count", "min", 1),),
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
    result = evaluate_eligibility(
        q,
        EligibilityRequirements(
            mode, boundary, (Predicate("training_gate", required="passed"),)
        ),
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
    )
    assert evaluate_eligibility(qualification(), req) == evaluate_eligibility(
        qualification(), req
    )


def test_malformed_mode_fails_clearly():
    with pytest.raises(ValueError, match="unknown reuse mode"):
        evaluate_eligibility(
            qualification(), EligibilityRequirements("other", "none", ())
        )
