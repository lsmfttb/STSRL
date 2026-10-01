"""Strict acceptance of the reviewed native STSRL-009 deterministic audit."""

from collections.abc import Mapping
from typing import Any

AUDIT_SCHEMA = "native-stsr009-configuration-aware-root-mapping-audit-v1"
AUDIT_PREDICATES = (
    "potion_use_excluded",
    "potion_discard_excluded",
    "public_action_order_preserved",
    "searched_actions_preserved",
    "no_fake_values",
    "mapping_schema_versioned",
    "diagnostic_v2_counts_correct",
    "required_missing_non_card_fails_closed",
    "enabled_potion_missing_discard_fails_closed",
    "uncovered_edge_fails_closed",
    "search_surface_and_work_unchanged",
    "all_search_edges_covered",
)


def validate_t110_configuration_mapping_audit(value: object) -> Mapping[str, Any]:
    """Require the exact safe schema and all twelve native-owned predicates."""

    if not isinstance(value, Mapping):
        raise TypeError("STSRL-009 audit must be a mapping")
    if set(value) != {"schema_id", *AUDIT_PREDICATES}:
        raise ValueError("STSRL-009 audit has missing or unsafe fields")
    if value["schema_id"] != AUDIT_SCHEMA:
        raise ValueError("STSRL-009 audit schema mismatch")
    if any(value[name] is not True for name in AUDIT_PREDICATES):
        raise ValueError("STSRL-009 audit predicate failed")
    return value
