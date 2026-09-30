from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    AUDIT_PREDICATES,
    AUDIT_SCHEMA,
    DIAGNOSTIC_SCHEMA,
    FAILURE_SUBREASONS,
    validate_t107_mapping_audit,
    validate_t107_mapping_diagnostic,
)


def _counts(**overrides: int) -> dict[str, int]:
    counts = {
        "public_legal_occurrence_count": 1,
        "search_root_edge_count": 1,
        "public_occurrences_mapped": 0,
        "search_root_edges_covered": 0,
        "direct_mapping_count": 0,
        "mechanical_duplicate_mapping_count": 0,
    }
    counts.update(overrides)
    return counts


def _diagnostic(
    subreason: str,
    *,
    counts: dict[str, int] | None = None,
    occurrence: bool = False,
    representative: str | None = None,
) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "failed",
        "mapping_subreason": subreason,
        **(counts or _counts()),
    }
    if occurrence:
        diagnostic.update(
            public_occurrence_index=diagnostic["public_occurrences_mapped"],
            public_action_kind=(
                "end_turn"
                if subreason == "missing_non_card_direct_search_root_match"
                else "card"
            ),
            direct_match_multiplicity=(
                "multiple"
                if subreason == "multiple_direct_search_root_matches"
                else "zero"
            ),
        )
    if representative is not None:
        diagnostic["representative_match_multiplicity"] = representative
    return diagnostic


@pytest.mark.parametrize(
    ("diagnostic", "expected_stage"),
    [
        (
            _diagnostic(
                "no_public_legal_action_surface",
                counts=_counts(
                    public_legal_occurrence_count=0,
                    search_root_edge_count=1,
                ),
            ),
            "failed",
        ),
        (
            _diagnostic(
                "multiple_direct_search_root_matches",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "missing_non_card_direct_search_root_match",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "card_not_adjacent_mechanical_duplicate",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "representative_search_root_match_zero",
                occurrence=True,
                representative="zero",
            ),
            "failed",
        ),
        (
            _diagnostic(
                "representative_search_root_match_multiple",
                occurrence=True,
                representative="multiple",
            ),
            "failed",
        ),
        (
            _diagnostic(
                "uncovered_search_root_edge",
                counts=_counts(
                    search_root_edge_count=2,
                    public_occurrences_mapped=1,
                    search_root_edges_covered=1,
                    direct_mapping_count=1,
                ),
            ),
            "failed",
        ),
    ],
)
def test_all_seven_native_mapping_failure_subreasons_are_structured(
    diagnostic: dict[str, object], expected_stage: str
) -> None:
    assert diagnostic["mapping_subreason"] in FAILURE_SUBREASONS
    assert (
        validate_t107_mapping_diagnostic(
            diagnostic, mapping_stage_status=expected_stage
        )
        == diagnostic
    )


def test_entered_mapping_diagnostic_is_bounded_and_stage_consistent() -> None:
    entered = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "entered",
        "mapping_subreason": None,
    }
    assert (
        validate_t107_mapping_diagnostic(entered, mapping_stage_status="entered")
        == entered
    )
    with pytest.raises(ValueError, match="disagrees"):
        validate_t107_mapping_diagnostic(entered, mapping_stage_status="completed")


def test_none_is_only_valid_before_mapping_was_reached() -> None:
    assert (
        validate_t107_mapping_diagnostic(None, mapping_stage_status="not_reached")
        is None
    )
    with pytest.raises(ValueError, match="absent after mapping"):
        validate_t107_mapping_diagnostic(None, mapping_stage_status="entered")
    with pytest.raises(ValueError, match="exists before mapping"):
        validate_t107_mapping_diagnostic(
            {
                "schema_id": DIAGNOSTIC_SCHEMA,
                "status": "entered",
                "mapping_subreason": None,
            },
            mapping_stage_status="not_reached",
        )


def test_success_requires_complete_mapping_and_coverage_counts() -> None:
    completed = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "completed",
        "mapping_subreason": "mapping_completed",
        **_counts(
            public_occurrences_mapped=1,
            search_root_edges_covered=1,
            direct_mapping_count=1,
        ),
    }
    assert (
        validate_t107_mapping_diagnostic(completed, mapping_stage_status="completed")
        == completed
    )
    invalid = deepcopy(completed)
    invalid["root_state"] = "must never cross the native boundary"
    with pytest.raises(ValueError, match="non-whitelisted"):
        validate_t107_mapping_diagnostic(invalid, mapping_stage_status="completed")


def test_mapping_failure_vocabulary_is_closed_and_native_audit_is_exact() -> None:
    audit = {"schema_id": AUDIT_SCHEMA, **dict.fromkeys(AUDIT_PREDICATES, True)}
    assert validate_t107_mapping_audit(audit) == audit
    audit["unlisted_condition"] = True
    with pytest.raises(ValueError, match="exactly"):
        validate_t107_mapping_audit(audit)
