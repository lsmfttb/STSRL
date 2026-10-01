"""Validation for the native STSRL-006 particle-to-Search bridge.

The native simulator owns particle construction, Battle mechanics, and Search-v2
semantics.  This module only validates the sanitized capability report returned
across that boundary; it never reconstructs or stores native particle state.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from typing import Any

from sts_combat_rl.sim.t096_public_information_sampler import (
    T096SamplerError,
    validate_public_information_projection,
)

T099_BRIDGE_SCHEMA_ID = "native-battle-public-particle-search-v1"
T099_BRIDGE_NATIVE_API = "StepSimulator.sample_hidden_future_particles_search.v1"
T099_AUDIT_SCHEMA_ID = "native-stsr006-particle-search-audit-v1"
T099_MAPPING_SCHEMA_ID = "native-search-root-occurrence-equivalence-v1"
T099_VALUE_SEMANTICS = "full_state_continuation_strategy_fusion_proxy"
T110_BRIDGE_SCHEMA_ID = "native-battle-public-particle-search-v2"
T110_BRIDGE_NATIVE_API = "StepSimulator.sample_hidden_future_particles_search.v2"
T110_MAPPING_SCHEMA_ID = "native-search-root-occurrence-equivalence-v2"
T110_COMPLETION_SEMANTICS = (
    "every_public_occurrence_classified_and_every_search_edge_covered"
)

T099_REQUIRED_AUDIT_PREDICATES = (
    "direct_sampler_parity",
    "value_semantics_labeled",
    "root_work_counters_complete",
    "hidden_particle_diversity",
    "duplicate_occurrence_mapping",
    "frozen_eye_search_compatibility",
    "known_draw_constraint_preserved",
    "unsupported_anchor_fails_closed",
)

_ACTION_IDENTITY_KEYS = frozenset({"scope", "kind", "idx1", "idx2", "idx3", "label"})
_MAPPING_MODES = frozenset(
    {"direct_action_bits", "mechanical_duplicate_card_occurrence"}
)
_WORK_COUNTER_KEYS = frozenset(
    {
        "schema_id",
        "action_execution_count",
        "successor_transition_count",
        "tree_and_rollout_action_execution_count",
        "heuristic_successor_transition_count",
        "tree_node_expansion_count",
        "rollout_count",
        "terminal_utility_evaluation_count",
        "policy_prior_calls",
        "leaf_value_calls",
        "model_calls",
    }
)


class T099ParticleSearchBridgeError(ValueError):
    """Raised when the native bridge report violates the accepted contract."""


def validate_t099_particle_search_audit(value: object) -> dict[str, Any]:
    """Validate the complete native-owned deterministic STSRL-006 audit."""

    audit = _mapping(value, "T099 native particle-Search audit")
    required_keys = {"schema_id", *T099_REQUIRED_AUDIT_PREDICATES}
    _require_exact_keys(audit, required_keys, "T099 native particle-Search audit")
    if audit["schema_id"] != T099_AUDIT_SCHEMA_ID:
        raise T099ParticleSearchBridgeError("T099 native audit schema mismatch")
    failed: list[str] = []
    for predicate in T099_REQUIRED_AUDIT_PREDICATES:
        result = audit[predicate]
        if not isinstance(result, bool):
            raise T099ParticleSearchBridgeError(
                f"T099 native audit predicate {predicate!r} is not boolean"
            )
        if not result:
            failed.append(predicate)
    if failed:
        raise T099ParticleSearchBridgeError(
            "T099 native audit predicates failed: " + ", ".join(failed)
        )
    return audit


def validate_t099_particle_search_bridge(value: object) -> dict[str, Any]:
    """Dispatch explicitly between the historical v1 and configuration-aware v2."""

    report = _mapping(value, "particle-Search bridge report")
    if report.get("schema_id") == T099_BRIDGE_SCHEMA_ID:
        return validate_particle_search_bridge_v1(report)
    if report.get("schema_id") == T110_BRIDGE_SCHEMA_ID:
        return validate_particle_search_bridge_v2(report)
    raise T099ParticleSearchBridgeError("unknown particle-Search bridge schema")


def validate_particle_search_bridge_v1(value: object) -> dict[str, Any]:
    """Retain T099's strict every-public-occurrence-has-an-edge contract."""

    return _validate_bridge(value, version=1)


def validate_particle_search_bridge_v2(value: object) -> dict[str, Any]:
    """Validate T110's explicit classified-occurrence contract, with no fallback."""

    return _validate_bridge(value, version=2)


def _validate_bridge(value: object, *, version: int) -> dict[str, Any]:

    report = _mapping(value, "T099 particle-Search bridge report")
    required_top_level = {
        "schema_id",
        "native_api",
        "sampler_seed_input",
        "particle_start",
        "particle_count",
        "search_simulations",
        "include_potions",
        "information_regime",
        "anchor_public_information_projection",
        "anchor_ordered_public_legal_actions",
        "semantic_boundary",
        "particles",
    }
    _require_exact_keys(report, required_top_level, "T099 bridge report")
    schema = T099_BRIDGE_SCHEMA_ID if version == 1 else T110_BRIDGE_SCHEMA_ID
    api = T099_BRIDGE_NATIVE_API if version == 1 else T110_BRIDGE_NATIVE_API
    if report["schema_id"] != schema:
        raise T099ParticleSearchBridgeError("T099 bridge schema mismatch")
    if report["native_api"] != api:
        raise T099ParticleSearchBridgeError("T099 bridge native API mismatch")
    if report["information_regime"] != (
        "normal_belief_search_outer_full_simulator_state_oracle_like_continuation"
    ):
        raise T099ParticleSearchBridgeError("T099 bridge information regime mismatch")
    _nonnegative_int(report["particle_start"], "particle_start")
    particle_count = _positive_int(report["particle_count"], "particle_count")
    _positive_int(report["search_simulations"], "search_simulations")
    if not isinstance(report["sampler_seed_input"], int) or isinstance(
        report["sampler_seed_input"], bool
    ):
        raise T099ParticleSearchBridgeError("T099 sampler_seed_input is not an integer")
    if not isinstance(report["include_potions"], bool):
        raise T099ParticleSearchBridgeError("T099 include_potions is not boolean")

    try:
        anchor_projection = validate_public_information_projection(
            report["anchor_public_information_projection"]
        )
    except T096SamplerError as exc:
        raise T099ParticleSearchBridgeError(
            f"T099 anchor public projection is invalid: {exc}"
        ) from exc
    if anchor_projection.get("information_fidelity") != "supported":
        raise T099ParticleSearchBridgeError(
            "T099 bridge accepted an unsupported-fidelity anchor"
        )
    anchor_actions = _action_list(
        report["anchor_ordered_public_legal_actions"], "T099 anchor actions"
    )
    if anchor_actions != anchor_projection["ordered_public_legal_actions"]:
        raise T099ParticleSearchBridgeError(
            "T099 anchor ordered public legal actions disagree with the projection"
        )

    _validate_semantic_boundary(report["semantic_boundary"], version=version)
    particles = report["particles"]
    if not isinstance(particles, list) or len(particles) != particle_count:
        raise T099ParticleSearchBridgeError(
            "T099 bridge particle count disagrees with returned rows"
        )
    expected_indices = list(
        range(report["particle_start"], report["particle_start"] + particle_count)
    )
    observed_indices: list[int] = []
    for particle in particles:
        row = _validate_particle_row(
            particle,
            anchor_projection,
            anchor_actions,
            version=version,
            include_potions=report["include_potions"],
            search_simulations=report["search_simulations"],
        )
        observed_indices.append(row["particle_index"])
    if observed_indices != expected_indices:
        raise T099ParticleSearchBridgeError(
            "T099 bridge particle indices are not the requested ordered range"
        )
    return report


def _validate_semantic_boundary(value: object, *, version: int = 1) -> None:
    semantics = _mapping(value, "T099 semantic boundary")
    _require_exact_keys(
        semantics,
        {
            "outer_particle_distribution",
            "continuation",
            "aggregation",
            "q_public_claim",
            "executable_no_sl_continuation_claim",
            "information_set_optimal_claim",
        }
        | ({"configuration_excluded_action_values"} if version == 2 else set()),
        "T099 semantic boundary",
    )
    expected = {
        "outer_particle_distribution": (
            "native_public_consistent_hidden_future_sampler"
        ),
        "continuation": "full_state_search_v2_per_particle",
        "aggregation": "not_performed",
        "q_public_claim": False,
        "executable_no_sl_continuation_claim": False,
        "information_set_optimal_claim": False,
    }
    if version == 2:
        expected["configuration_excluded_action_values"] = "not_evaluated_not_numeric"
    if semantics != expected:
        raise T099ParticleSearchBridgeError(
            "T099 bridge mixed information-regime semantics changed"
        )


def _validate_particle_row(
    value: object,
    anchor_projection: Mapping[str, Any],
    anchor_actions: list[dict[str, Any]],
    *,
    version: int = 1,
    include_potions: bool = False,
    search_simulations: int = 1,
) -> dict[str, Any]:
    row = _mapping(value, "T099 bridge particle")
    _require_exact_keys(
        row,
        {
            "particle_index",
            "sampler_seed",
            "hidden_future_fingerprint",
            "public_information_projection",
            "public_projection_equal",
            "ordered_public_legal_actions_equal",
            "ordered_public_legal_actions",
            "root_action_mapping_complete",
            "root_action_mapping_ambiguous",
            "search_value_semantics",
            "root_evaluation",
            "root_rows",
        }
        | (
            {
                "root_action_mapping_completion_semantics",
                "configuration_excluded_public_action_count",
            }
            if version == 2
            else set()
        ),
        "T099 bridge particle",
    )
    _nonnegative_int(row["particle_index"], "particle_index")
    if not isinstance(row["sampler_seed"], int) or isinstance(
        row["sampler_seed"], bool
    ):
        raise T099ParticleSearchBridgeError("T099 particle sampler_seed is invalid")
    if (
        not isinstance(row["hidden_future_fingerprint"], str)
        or not row["hidden_future_fingerprint"]
    ):
        raise T099ParticleSearchBridgeError(
            "T099 hidden-future fingerprint must be non-empty audit text"
        )
    if row["public_information_projection"] != anchor_projection:
        raise T099ParticleSearchBridgeError("T099 particle public projection drifted")
    if row["public_projection_equal"] is not True:
        raise T099ParticleSearchBridgeError("T099 public projection parity flag failed")
    actions = _action_list(
        row["ordered_public_legal_actions"], "T099 particle ordered actions"
    )
    if (
        actions != anchor_actions
        or row["ordered_public_legal_actions_equal"] is not True
    ):
        raise T099ParticleSearchBridgeError(
            "T099 ordered public legal-action parity failed"
        )
    if row["root_action_mapping_complete"] is not True:
        raise T099ParticleSearchBridgeError("T099 root mapping is incomplete")
    if row["root_action_mapping_ambiguous"] is not False:
        raise T099ParticleSearchBridgeError("T099 root mapping is ambiguous")
    if row["search_value_semantics"] != T099_VALUE_SEMANTICS:
        raise T099ParticleSearchBridgeError("T099 returned value semantics changed")
    root_rows = _validate_root_rows(
        row["root_rows"],
        actions,
        version=version,
        include_potions=include_potions,
        input_state=anchor_projection.get("input_state"),
    )
    _validate_root_evaluation(
        row["root_evaluation"],
        actions,
        root_rows,
        version=version,
        include_potions=include_potions,
        search_simulations=search_simulations,
    )
    if version == 2:
        excluded = sum(
            r["mapping_classification"] == "search_configuration_excluded"
            for r in root_rows
        )
        if (
            row["root_action_mapping_completion_semantics"] != T110_COMPLETION_SEMANTICS
            or _nonnegative_int(
                row["configuration_excluded_public_action_count"],
                "particle excluded count",
            )
            != excluded
        ):
            raise T099ParticleSearchBridgeError(
                "v2 particle classification counts/semantics disagree"
            )
    return row


def _validate_root_rows(
    value: object,
    actions: list[dict[str, Any]],
    *,
    version: int = 1,
    include_potions: bool = False,
    input_state: object = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(actions):
        raise T099ParticleSearchBridgeError(
            "T099 sanitized root-row count disagrees with public actions"
        )
    rows: list[dict[str, Any]] = []
    required = _ACTION_IDENTITY_KEYS | {
        "search_tree_present",
        "search_edge_index",
        "visits",
        "evaluation_sum",
        "mean_value",
        "public_action_ordinal",
        "search_equivalence_source_edge_index",
        "search_equivalence_mapping_mode",
    }
    if version == 2:
        required |= {"mapping_classification", "configuration_exclusion_reason"}
    for ordinal, value_row in enumerate(value):
        row = _mapping(value_row, "T099 sanitized root row")
        _require_exact_keys(row, required, "T099 sanitized root row")
        identity = {key: row[key] for key in _ACTION_IDENTITY_KEYS}
        _validate_action_identity(identity, "T099 sanitized root action")
        if identity != actions[ordinal] or row["public_action_ordinal"] != ordinal:
            raise T099ParticleSearchBridgeError(
                "T099 root row lost public action identity or ordinal"
            )
        if version == 2:
            _nonnegative_int(row["public_action_ordinal"], "public ordinal")
            classification = row["mapping_classification"]
            if classification == "search_configuration_excluded":
                if (
                    input_state != "PLAYER_NORMAL"
                    or row["scope"] != "battle"
                    or row["kind"] not in {"potion", "potion_discard"}
                    or include_potions is not False
                    or row["configuration_exclusion_reason"] != "include_potions_false"
                    or row["search_tree_present"] is not False
                    or _nonnegative_int(row["visits"], "excluded visits") != 0
                    or any(
                        row[k] is not None
                        for k in (
                            "search_edge_index",
                            "search_equivalence_source_edge_index",
                            "search_equivalence_mapping_mode",
                            "evaluation_sum",
                            "mean_value",
                        )
                    )
                ):
                    raise T099ParticleSearchBridgeError(
                        "invalid v2 configuration-excluded row"
                    )
                rows.append(row)
                continue
            expected_mode = {
                "searched_direct": "direct_action_bits",
                "searched_mechanical_duplicate_card_occurrence": "mechanical_duplicate_card_occurrence",
            }.get(classification)
            if (
                expected_mode is None
                or row["configuration_exclusion_reason"] is not None
                or row["search_equivalence_mapping_mode"] != expected_mode
                or row["search_tree_present"] is not True
                or (
                    expected_mode == "mechanical_duplicate_card_occurrence"
                    and row["kind"] != "card"
                )
                or (not include_potions and row["kind"] in {"potion", "potion_discard"})
            ):
                raise T099ParticleSearchBridgeError(
                    "invalid v2 searched classification"
                )
            _nonnegative_int(row["search_edge_index"], "Search edge index")
        source_edge = _nonnegative_int(
            row["search_equivalence_source_edge_index"], "source edge index"
        )
        if row["search_edge_index"] != source_edge:
            raise T099ParticleSearchBridgeError(
                "T099 root row source Search edge identity disagrees"
            )
        if row["search_equivalence_mapping_mode"] not in _MAPPING_MODES:
            raise T099ParticleSearchBridgeError("T099 root mapping mode is unknown")
        if not isinstance(row["search_tree_present"], bool):
            raise T099ParticleSearchBridgeError(
                "T099 root search_tree_present is not boolean"
            )
        visits = _nonnegative_int(row["visits"], "root visits")
        evaluation_sum = row["evaluation_sum"]
        if not isinstance(evaluation_sum, (int, float)) or isinstance(
            evaluation_sum, bool
        ):
            raise T099ParticleSearchBridgeError(
                "T099 root row evaluation_sum is not numeric"
            )
        mean_value = row["mean_value"]
        if visits == 0:
            if mean_value is not None:
                raise T099ParticleSearchBridgeError(
                    "T099 unvisited root row has inconsistent value state"
                )
        elif not isinstance(mean_value, (int, float)) or isinstance(mean_value, bool):
            raise T099ParticleSearchBridgeError(
                "T099 visited root row mean_value is not numeric"
            )
        if version == 2 and (
            not math.isfinite(evaluation_sum)
            or (mean_value is not None and not math.isfinite(mean_value))
        ):
            raise T099ParticleSearchBridgeError("v2 searched values must be finite")
        rows.append(row)
    return rows


def _validate_root_evaluation(
    value: object,
    actions: list[dict[str, Any]],
    root_rows: list[dict[str, Any]],
    *,
    version: int = 1,
    include_potions: bool = False,
    search_simulations: int = 1,
) -> None:
    root = _mapping(value, "T099 root evaluation")
    if root.get("information_regime") != "full_simulator_state_oracle_like":
        raise T099ParticleSearchBridgeError(
            "T099 per-particle continuation is not labeled oracle-like"
        )
    api = T099_BRIDGE_NATIVE_API if version == 1 else T110_BRIDGE_NATIVE_API
    mapping_schema = T099_MAPPING_SCHEMA_ID if version == 1 else T110_MAPPING_SCHEMA_ID
    if root.get("native_api") != api:
        raise T099ParticleSearchBridgeError("T099 root native API mismatch")
    if (
        root.get("patch_identity")
        != f"sts_lightspeed_native_particle_search_bridge_v{version}"
    ):
        raise T099ParticleSearchBridgeError("T099 root patch identity mismatch")
    if root.get("root_action_mapping_schema") != mapping_schema:
        raise T099ParticleSearchBridgeError("T099 root mapping schema mismatch")
    if root.get("root_rows") != root_rows:
        raise T099ParticleSearchBridgeError(
            "T099 root evaluation rows disagree with sanitized particle rows"
        )
    if root.get("root_row_count") != len(actions):
        raise T099ParticleSearchBridgeError("T099 root row count is incomplete")
    excluded = sum(
        r.get("mapping_classification") == "search_configuration_excluded"
        for r in root_rows
    )
    if root.get("unsearched_legal_action_count") != excluded:
        raise T099ParticleSearchBridgeError("T099 root has unsearched public actions")
    if root.get("unmapped_search_edge_count") != 0:
        raise T099ParticleSearchBridgeError("T099 root has unmapped Search edges")
    if version == 2:
        _require_exact_keys(
            root,
            {
                "schema_id",
                "native_api",
                "patch_identity",
                "information_regime",
                "simulations_requested",
                "root_visits",
                "include_potions",
                "native_simulator_steps",
                "model_calls",
                "best_action_value",
                "min_action_value",
                "outcome_player_hp",
                "root_row_count",
                "search_edge_count",
                "unsearched_legal_action_count",
                "unmapped_search_edge_count",
                "work_counters",
                "search_v2_configuration",
                "root_rows",
                "root_action_mapping_schema",
                "root_action_mapping",
                "root_action_mapping_completion_semantics",
                "configuration_excluded_public_action_count",
            },
            "v2 root evaluation",
        )
        if (
            root["schema_id"] != "native-battle-search-root-v2"
            or root["include_potions"] is not include_potions
            or root["simulations_requested"] != search_simulations
            or root["root_action_mapping_completion_semantics"]
            != T110_COMPLETION_SEMANTICS
            or _nonnegative_int(
                root["configuration_excluded_public_action_count"],
                "root excluded count",
            )
            != excluded
        ):
            raise T099ParticleSearchBridgeError(
                "v2 root schema/configuration/counts disagree"
            )
        for key in (
            "root_row_count",
            "search_edge_count",
            "unsearched_legal_action_count",
            "unmapped_search_edge_count",
        ):
            _nonnegative_int(root[key], key)
        for key in (
            "root_visits",
            "native_simulator_steps",
            "simulations_requested",
        ):
            _nonnegative_int(root[key], key)
        # The legacy aggregate report deliberately leaves this field absent in
        # value; the complete typed work counter below is authoritative.
        if root["model_calls"] is not None:
            raise T099ParticleSearchBridgeError(
                "v2 aggregate model_calls must remain null"
            )
        for key in ("best_action_value", "min_action_value", "outcome_player_hp"):
            if (
                isinstance(root[key], bool)
                or not isinstance(root[key], (int, float))
                or not math.isfinite(root[key])
            ):
                raise T099ParticleSearchBridgeError(
                    f"v2 {key} must be finite numeric data"
                )

    configuration = _mapping(
        root.get("search_v2_configuration"), "T099 Search-v2 configuration"
    )
    if configuration != {
        "policy_prior_enabled": False,
        "learned_leaf_value_enabled": False,
        "progressive_bias_enabled": False,
    }:
        raise T099ParticleSearchBridgeError(
            "T099 bridge did not preserve unchanged unguided Search-v2 configuration"
        )
    counters = _mapping(root.get("work_counters"), "T099 Search work counters")
    _require_exact_keys(counters, _WORK_COUNTER_KEYS, "T099 Search work counters")
    if counters["schema_id"] != "native-battle-search-work-v1":
        raise T099ParticleSearchBridgeError("T099 Search work-counter schema mismatch")
    for key in _WORK_COUNTER_KEYS - {"schema_id"}:
        _nonnegative_int(counters[key], f"work counter {key}")
    if counters["policy_prior_calls"] != 0 or counters["leaf_value_calls"] != 0:
        raise T099ParticleSearchBridgeError(
            "T099 bridge unexpectedly used learned Search callbacks"
        )
    if counters["model_calls"] != 0:
        raise T099ParticleSearchBridgeError(
            "T099 bridge unexpectedly reports model calls"
        )

    mappings = root.get("root_action_mapping")
    if not isinstance(mappings, list) or len(mappings) != len(actions):
        raise T099ParticleSearchBridgeError(
            "T099 occurrence mapping count disagrees with public actions"
        )
    edge_counts = Counter(
        row["search_equivalence_source_edge_index"]
        for row in root_rows
        if row["search_equivalence_source_edge_index"] is not None
    )
    source_actions_by_edge: dict[int, dict[str, Any]] = {}
    for ordinal, value_row in enumerate(mappings):
        mapping = _mapping(value_row, "T099 occurrence mapping row")
        _require_exact_keys(
            mapping,
            {
                "public_action_ordinal",
                "public_action",
                "search_edge_index",
                "mapping_mode",
                "source_action",
                "edge_public_occurrence_count",
            }
            | (
                {"mapping_classification", "configuration_exclusion_reason"}
                if version == 2
                else set()
            ),
            "T099 occurrence mapping row",
        )
        public_action = _action_identity(mapping["public_action"], "public action")
        root_row = root_rows[ordinal]
        if (
            mapping["public_action_ordinal"] != ordinal
            or public_action != actions[ordinal]
        ):
            raise T099ParticleSearchBridgeError(
                "T099 occurrence mapping lost public ordinal or identity"
            )
        if version == 2:
            _nonnegative_int(mapping["public_action_ordinal"], "mapping ordinal")
            if (
                mapping["mapping_classification"] != root_row["mapping_classification"]
                or mapping["configuration_exclusion_reason"]
                != root_row["configuration_exclusion_reason"]
            ):
                raise T099ParticleSearchBridgeError(
                    "v2 mapping classification disagrees with root row"
                )
            if root_row["mapping_classification"] == "search_configuration_excluded":
                if any(
                    mapping[k] is not None
                    for k in (
                        "search_edge_index",
                        "mapping_mode",
                        "source_action",
                        "edge_public_occurrence_count",
                    )
                ):
                    raise T099ParticleSearchBridgeError(
                        "v2 excluded mapping must have null edge/source/count"
                    )
                continue
        source_action = _action_identity(mapping["source_action"], "source action")
        edge_index = _nonnegative_int(mapping["search_edge_index"], "Search edge")
        if edge_index != root_row["search_equivalence_source_edge_index"]:
            raise T099ParticleSearchBridgeError(
                "T099 occurrence mapping source edge disagrees with root row"
            )
        if mapping["mapping_mode"] != root_row["search_equivalence_mapping_mode"]:
            raise T099ParticleSearchBridgeError(
                "T099 occurrence mapping mode disagrees with root row"
            )
        if mapping["mapping_mode"] not in _MAPPING_MODES:
            raise T099ParticleSearchBridgeError(
                "T099 occurrence mapping mode is unknown"
            )
        if mapping["edge_public_occurrence_count"] != edge_counts[edge_index]:
            raise T099ParticleSearchBridgeError(
                "T099 occurrence-equivalence count disagrees with source edge"
            )
        if (
            mapping["mapping_mode"] == "direct_action_bits"
            and source_action != public_action
        ):
            raise T099ParticleSearchBridgeError(
                "T099 direct occurrence mapping changed public action identity"
            )
        prior_source = source_actions_by_edge.setdefault(edge_index, source_action)
        if prior_source != source_action:
            raise T099ParticleSearchBridgeError(
                "T099 public occurrences disagree about the source action identity"
            )
    if version == 2:
        if set(edge_counts) != set(range(root["search_edge_count"])):
            raise T099ParticleSearchBridgeError("v2 root has an uncovered Search edge")
        if sum(edge_counts.values()) + excluded != len(actions):
            raise T099ParticleSearchBridgeError(
                "v2 public occurrence classification is incomplete"
            )
        for edge, source in source_actions_by_edge.items():
            if not any(
                m["search_edge_index"] == edge
                and m["mapping_mode"] == "direct_action_bits"
                and m["public_action"] == source
                for m in mappings
            ):
                raise T099ParticleSearchBridgeError(
                    "v2 duplicate mapping lacks direct representative"
                )


def _action_list(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise T099ParticleSearchBridgeError(f"{label} must be a non-empty list")
    return [_action_identity(item, label) for item in value]


def _action_identity(value: object, label: str) -> dict[str, Any]:
    action = _mapping(value, label)
    _require_exact_keys(action, _ACTION_IDENTITY_KEYS, label)
    _validate_action_identity(action, label)
    return action


def _validate_action_identity(action: Mapping[str, Any], label: str) -> None:
    for key in ("scope", "kind", "label"):
        if not isinstance(action[key], str):
            raise T099ParticleSearchBridgeError(f"{label} {key} must be text")
    for key in ("idx1", "idx2", "idx3"):
        if not isinstance(action[key], int) or isinstance(action[key], bool):
            raise T099ParticleSearchBridgeError(f"{label} {key} must be an integer")
    if "bits=" in action["label"]:
        raise T099ParticleSearchBridgeError(
            f"{label} exposes replay-only native action bits"
        )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise T099ParticleSearchBridgeError(f"{label} must be a mapping")
    return dict(value)


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str] | frozenset[str], label: str
) -> None:
    missing = set(expected) - set(value)
    unknown = set(value) - set(expected)
    if missing or unknown:
        raise T099ParticleSearchBridgeError(
            f"{label} keys mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise T099ParticleSearchBridgeError(f"T099 {label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise T099ParticleSearchBridgeError(
            f"T099 {label} must be a non-negative integer"
        )
    return value
