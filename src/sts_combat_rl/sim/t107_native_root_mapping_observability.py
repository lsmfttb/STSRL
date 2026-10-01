"""Validate the bounded STSRL-008 native root-mapping diagnostics.

The native implementation owns mapping control flow and writes these records
directly.  This module only checks the returned allowlisted structure and its
relationship to the existing STSRL-007 stage trace.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DIAGNOSTIC_SCHEMA = "native-root-occurrence-mapping-diagnostic-v1"
DIAGNOSTIC_V2_SCHEMA = "native-root-occurrence-mapping-diagnostic-v2"
AUDIT_SCHEMA = "native-stsr008-root-occurrence-mapping-audit-v1"

FAILURE_SUBREASONS = frozenset(
    {
        "no_public_legal_action_surface",
        "multiple_direct_search_root_matches",
        "missing_non_card_direct_search_root_match",
        "card_not_adjacent_mechanical_duplicate",
        "representative_search_root_match_zero",
        "representative_search_root_match_multiple",
        "uncovered_search_root_edge",
    }
)
MAPPING_SUBREASONS = FAILURE_SUBREASONS | {"mapping_completed"}

COUNT_FIELDS = frozenset(
    {
        "public_legal_occurrence_count",
        "search_root_edge_count",
        "public_occurrences_mapped",
        "search_root_edges_covered",
        "direct_mapping_count",
        "mechanical_duplicate_mapping_count",
    }
)
V2_COUNT_FIELDS = COUNT_FIELDS | {
    "public_occurrences_classified",
    "searched_public_occurrence_count",
    "configuration_excluded_public_occurrence_count",
}
OCCURRENCE_FIELDS = frozenset(
    {
        "public_occurrence_index",
        "public_action_kind",
        "direct_match_multiplicity",
    }
)
REPRESENTATIVE_FIELDS = frozenset({"representative_match_multiplicity"})
DIAGNOSTIC_FIELDS = frozenset(
    {
        "schema_id",
        "status",
        "mapping_subreason",
        *COUNT_FIELDS,
        *OCCURRENCE_FIELDS,
        *REPRESENTATIVE_FIELDS,
    }
)
AUDIT_PREDICATES = (
    "success_completion_reported",
    "success_root_report_semantics_preserved",
    "no_public_surface_classified",
    "multiple_direct_classified",
    "missing_non_card_classified",
    "representative_ineligible_classified",
    "representative_zero_classified",
    "representative_multiple_classified",
    "uncovered_edge_classified",
    "not_reached_absent",
    "later_particle_not_mapping_attempted",
    "snapshot_attempt_isolation",
    "diagnostic_field_whitelist",
)
ACTION_KINDS = frozenset(
    {
        "card",
        "potion",
        "potion_discard",
        "single_card_select",
        "multi_card_select",
        "end_turn",
        "battle_unknown",
    }
)
MATCH_MULTIPLICITIES = frozenset({"zero", "one", "multiple"})


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def validate_t107_mapping_diagnostic(
    value: object,
    *,
    mapping_stage_status: str,
) -> Mapping[str, Any] | None:
    """Validate a row's optional T107 diagnostic against its T105 stage.

    ``None`` is the native representation only before mapping was reached.
    Once reached, even an unexpected native exception must retain the bounded
    ``entered`` record rather than erase whether the mapping stage ran.
    """

    if not isinstance(mapping_stage_status, str) or mapping_stage_status not in {
        "not_reached",
        "entered",
        "completed",
        "failed",
    }:
        raise ValueError("STSRL-008 mapping stage status is invalid")
    if value is None:
        if mapping_stage_status != "not_reached":
            raise ValueError("STSRL-008 diagnostic is absent after mapping was reached")
        return None
    if mapping_stage_status == "not_reached":
        raise ValueError("STSRL-008 diagnostic exists before mapping was reached")

    diagnostic = _mapping(value, "STSRL-008 mapping diagnostic")
    schema = diagnostic.get("schema_id")
    if schema not in {DIAGNOSTIC_SCHEMA, DIAGNOSTIC_V2_SCHEMA}:
        raise ValueError("STSRL-008 diagnostic schema mismatch")
    v2 = schema == DIAGNOSTIC_V2_SCHEMA
    count_fields = V2_COUNT_FIELDS if v2 else COUNT_FIELDS
    keys = set(diagnostic)
    if keys - (DIAGNOSTIC_FIELDS | (V2_COUNT_FIELDS if v2 else set())):
        raise ValueError("STSRL-008 diagnostic contains a non-whitelisted field")
    base_fields = {"schema_id", "status", "mapping_subreason"}
    if not base_fields <= keys:
        raise ValueError("STSRL-008 diagnostic is missing required base fields")

    diagnostic_status = diagnostic["status"]
    subreason = diagnostic["mapping_subreason"]
    if not isinstance(diagnostic_status, str):
        raise TypeError("STSRL-008 diagnostic status must be a string")
    if subreason is not None and not isinstance(subreason, str):
        raise TypeError("STSRL-008 mapping subreason must be a string or None")
    if diagnostic_status == "entered":
        if mapping_stage_status not in {"entered", "failed"} or subreason is not None:
            raise ValueError("STSRL-008 entered diagnostic disagrees with stage status")
        if keys != base_fields:
            raise ValueError("STSRL-008 entered diagnostic has unexpected fields")
        return diagnostic

    if diagnostic_status == "completed":
        if mapping_stage_status != "completed" or subreason != "mapping_completed":
            raise ValueError("STSRL-008 completion disagrees with stage status")
        if keys != base_fields | count_fields:
            raise ValueError("STSRL-008 completed diagnostic has unexpected fields")
    elif diagnostic_status == "failed":
        if mapping_stage_status != "failed" or subreason not in FAILURE_SUBREASONS:
            raise ValueError("STSRL-008 failure disagrees with stage status")
        expected_fields = base_fields | count_fields
        if subreason in {
            "multiple_direct_search_root_matches",
            "missing_non_card_direct_search_root_match",
            "card_not_adjacent_mechanical_duplicate",
            "representative_search_root_match_zero",
            "representative_search_root_match_multiple",
        }:
            expected_fields |= OCCURRENCE_FIELDS
        if subreason in {
            "representative_search_root_match_zero",
            "representative_search_root_match_multiple",
        }:
            expected_fields |= REPRESENTATIVE_FIELDS
        if keys != expected_fields:
            raise ValueError("STSRL-008 failed diagnostic has unexpected fields")
    else:
        raise ValueError("STSRL-008 diagnostic status is invalid")

    counts = {name: _nonnegative_int(diagnostic[name], name) for name in count_fields}
    legal_count = counts["public_legal_occurrence_count"]
    edge_count = counts["search_root_edge_count"]
    mapped_count = counts["public_occurrences_mapped"]
    covered_count = counts["search_root_edges_covered"]
    direct_count = counts["direct_mapping_count"]
    duplicate_count = counts["mechanical_duplicate_mapping_count"]
    if mapped_count > legal_count or covered_count > edge_count:
        raise ValueError("STSRL-008 mapping progress exceeds aggregate counts")
    if direct_count + duplicate_count != mapped_count:
        raise ValueError("STSRL-008 mapping counters are inconsistent")
    classified_count = mapped_count
    if v2:
        classified_count = counts["public_occurrences_classified"]
        if (
            counts["searched_public_occurrence_count"] != mapped_count
            or mapped_count + counts["configuration_excluded_public_occurrence_count"]
            != classified_count
            or classified_count > legal_count
        ):
            raise ValueError("STSRL-009 classification counters are inconsistent")

    if diagnostic_status == "completed":
        if v2 and legal_count == 0:
            raise ValueError("STSRL-009 empty public action surface cannot complete")
        if legal_count != classified_count or edge_count != covered_count:
            raise ValueError("STSRL-008 completion did not map and cover all entries")
        return diagnostic

    if subreason == "no_public_legal_action_surface":
        if legal_count != 0 or classified_count != 0 or covered_count != 0:
            raise ValueError("STSRL-008 empty-surface counts are inconsistent")
        return diagnostic
    if subreason == "uncovered_search_root_edge":
        if (
            legal_count == 0
            or classified_count != legal_count
            or edge_count <= covered_count
        ):
            raise ValueError("STSRL-008 uncovered-edge counts are inconsistent")
        return diagnostic

    occurrence_index = _nonnegative_int(
        diagnostic["public_occurrence_index"], "public_occurrence_index"
    )
    action_kind = diagnostic["public_action_kind"]
    if not isinstance(action_kind, str) or action_kind not in ACTION_KINDS:
        raise ValueError(
            "STSRL-008 public action kind is outside the closed vocabulary"
        )
    if occurrence_index >= legal_count or occurrence_index != classified_count:
        raise ValueError("STSRL-008 occurrence index disagrees with mapping progress")
    direct_multiplicity = diagnostic["direct_match_multiplicity"]
    if not isinstance(direct_multiplicity, str):
        raise TypeError("STSRL-008 direct-match multiplicity must be a string")
    if direct_multiplicity not in MATCH_MULTIPLICITIES:
        raise ValueError("STSRL-008 direct-match multiplicity is invalid")

    if subreason == "multiple_direct_search_root_matches":
        if direct_multiplicity != "multiple":
            raise ValueError("STSRL-008 multiple-direct witness is inconsistent")
    elif subreason == "missing_non_card_direct_search_root_match":
        if action_kind == "card" or direct_multiplicity != "zero":
            raise ValueError("STSRL-008 missing non-card witness is inconsistent")
    elif subreason == "card_not_adjacent_mechanical_duplicate":
        if action_kind != "card" or direct_multiplicity != "zero":
            raise ValueError("STSRL-008 duplicate eligibility witness is inconsistent")
    else:
        representative_multiplicity = diagnostic["representative_match_multiplicity"]
        if not isinstance(representative_multiplicity, str):
            raise TypeError("STSRL-008 representative multiplicity must be a string")
        if (
            action_kind != "card"
            or direct_multiplicity != "zero"
            or representative_multiplicity not in MATCH_MULTIPLICITIES
        ):
            raise ValueError("STSRL-008 representative-match witness is inconsistent")
        expected = (
            "zero"
            if subreason == "representative_search_root_match_zero"
            else "multiple"
        )
        if representative_multiplicity != expected:
            raise ValueError("STSRL-008 representative subreason is inconsistent")
    return diagnostic


def validate_t107_mapping_audit(value: object) -> Mapping[str, Any]:
    """Require the native-owned fixed witnesses for all mapping outcomes."""

    audit = _mapping(value, "STSRL-008 audit")
    expected = {"schema_id", *AUDIT_PREDICATES}
    if set(audit) != expected:
        raise ValueError(f"STSRL-008 audit must contain exactly {sorted(expected)}")
    if audit["schema_id"] != AUDIT_SCHEMA:
        raise ValueError("STSRL-008 audit schema mismatch")
    if any(audit[name] is not True for name in AUDIT_PREDICATES):
        raise ValueError("STSRL-008 native audit predicate failed")
    return audit
