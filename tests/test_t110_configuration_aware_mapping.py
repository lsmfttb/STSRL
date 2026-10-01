from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_t099_particle_search_bridge import _action, _bridge_report

from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099ParticleSearchBridgeError,
    validate_particle_search_bridge_v1,
    validate_particle_search_bridge_v2,
    validate_t099_particle_search_bridge,
)
from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    validate_t107_mapping_diagnostic,
)
from sts_combat_rl.sim.t110_configuration_aware_mapping import (
    validate_t110_configuration_mapping_audit,
)


def _v2_report():
    # Expected schema/values are derived from the approved contract, never from
    # the production validator. Retain the historical direct/duplicate fixture.
    report = _bridge_report()
    report.update(
        schema_id="native-battle-public-particle-search-v2",
        native_api="StepSimulator.sample_hidden_future_particles_search.v2",
    )
    report["semantic_boundary"]["configuration_excluded_action_values"] = (
        "not_evaluated_not_numeric"
    )
    particle = report["particles"][0]
    root = particle["root_evaluation"]
    root.update(
        schema_id="native-battle-search-root-v2",
        native_api="StepSimulator.sample_hidden_future_particles_search.v2",
        patch_identity="sts_lightspeed_native_particle_search_bridge_v2",
        root_action_mapping_schema="native-search-root-occurrence-equivalence-v2",
        root_row_count=5,
        unsearched_legal_action_count=2,
        model_calls=None,
    )
    for holder in (particle, root):
        holder["root_action_mapping_completion_semantics"] = (
            "every_public_occurrence_classified_and_every_search_edge_covered"
        )
        holder["configuration_excluded_public_action_count"] = 2
    for index, (row, mapping) in enumerate(
        zip(particle["root_rows"], root["root_action_mapping"], strict=True)
    ):
        classification = (
            "searched_mechanical_duplicate_card_occurrence"
            if index == 2
            else "searched_direct"
        )
        row.update(
            mapping_classification=classification, configuration_exclusion_reason=None
        )
        mapping.update(
            mapping_classification=classification, configuration_exclusion_reason=None
        )
    for kind in ("potion", "potion_discard"):
        action = _action(kind, 0, kind)
        ordinal = len(report["anchor_ordered_public_legal_actions"])
        report["anchor_ordered_public_legal_actions"].append(action)
        particle["root_rows"].append(
            {
                **action,
                "public_action_ordinal": ordinal,
                "mapping_classification": "search_configuration_excluded",
                "configuration_exclusion_reason": "include_potions_false",
                "search_tree_present": False,
                "search_edge_index": None,
                "search_equivalence_source_edge_index": None,
                "search_equivalence_mapping_mode": None,
                "visits": 0,
                "evaluation_sum": None,
                "mean_value": None,
            }
        )
        root["root_action_mapping"].append(
            {
                "public_action_ordinal": ordinal,
                "public_action": action,
                "mapping_classification": "search_configuration_excluded",
                "configuration_exclusion_reason": "include_potions_false",
                "search_edge_index": None,
                "mapping_mode": None,
                "source_action": None,
                "edge_public_occurrence_count": None,
            }
        )
    return report


def test_v2_preserves_public_order_direct_duplicate_and_both_potion_identities():
    report = _v2_report()
    result = validate_particle_search_bridge_v2(report)
    assert result == report
    assert [row["kind"] for row in result["particles"][0]["root_rows"]] == [
        "end_turn",
        "card",
        "card",
        "potion",
        "potion_discard",
    ]
    assert result["particles"][0]["root_rows"][3]["evaluation_sum"] is None
    assert validate_t099_particle_search_bridge(report) == result


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("search_edge_index", 0),
        ("search_equivalence_source_edge_index", 0),
        ("search_equivalence_mapping_mode", "direct_action_bits"),
        ("search_tree_present", True),
        ("visits", 1),
        ("visits", False),
        ("evaluation_sum", 0.0),
        ("mean_value", 0.0),
        ("mapping_classification", "null_edge"),
        ("configuration_exclusion_reason", "anything_else"),
    ],
)
def test_excluded_row_is_not_generic_null_or_numeric_zero(field, value):
    report = _v2_report()
    report["particles"][0]["root_rows"][3][field] = value
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


@pytest.mark.parametrize(
    "field",
    [
        "search_edge_index",
        "mapping_mode",
        "source_action",
        "edge_public_occurrence_count",
    ],
)
def test_excluded_mapping_requires_all_null_fields(field):
    report = _v2_report()
    report["particles"][0]["root_evaluation"]["root_action_mapping"][3][field] = 0
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


@pytest.mark.parametrize(
    "kind",
    ["end_turn", "card", "single_card_select", "multi_card_select", "battle_unknown"],
)
def test_other_action_kinds_cannot_be_configuration_excluded(kind):
    report = _v2_report()
    action = report["anchor_ordered_public_legal_actions"][3]
    action["kind"] = kind
    report["particles"][0]["root_rows"][3]["kind"] = kind
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


@pytest.mark.parametrize("state", ["CARD_SELECT", "NONE", None])
def test_exclusion_requires_safe_player_normal_state(state):
    report = _v2_report()
    report["anchor_public_information_projection"]["input_state"] = state
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


def test_enabled_potion_missing_discard_fails_closed():
    report = _v2_report()
    report["include_potions"] = True
    report["particles"][0]["root_evaluation"]["include_potions"] = True
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("search_edge_count", 3),
        ("unmapped_search_edge_count", 1),
        ("unsearched_legal_action_count", 0),
        ("configuration_excluded_public_action_count", 1),
        ("root_row_count", 4),
        ("schema_id", "native-battle-search-root-v1"),
        ("root_action_mapping_schema", "native-search-root-occurrence-equivalence-v1"),
        ("root_action_mapping_completion_semantics", "every_null_is_excluded"),
    ],
)
def test_v2_root_count_coverage_and_schema_controls(field, value):
    report = _v2_report()
    report["particles"][0]["root_evaluation"][field] = value
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)


def test_public_order_and_unknown_private_fields_fail_closed():
    report = _v2_report()
    report["particles"][0]["root_rows"][0], report["particles"][0]["root_rows"][1] = (
        report["particles"][0]["root_rows"][1],
        report["particles"][0]["root_rows"][0],
    )
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(report)
    for field in (
        "bits",
        "specialData",
        "rng",
        "hidden_draw_order",
        "private_intent",
        "search_nodes",
        "exception_text",
    ):
        report = _v2_report()
        report["particles"][0]["root_evaluation"][field] = "private"
        with pytest.raises(T099ParticleSearchBridgeError):
            validate_particle_search_bridge_v2(report)


def test_v1_remains_strict_and_never_reinterprets_excluded_rows():
    historical = _bridge_report()
    assert validate_particle_search_bridge_v1(historical) == historical
    historical["particles"][0]["root_evaluation"]["unsearched_legal_action_count"] = 1
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v1(historical)
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v1(_v2_report())
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_particle_search_bridge_v2(_bridge_report())
    unknown = _v2_report()
    unknown["schema_id"] = "native-battle-public-particle-search-v3"
    with pytest.raises(T099ParticleSearchBridgeError):
        validate_t099_particle_search_bridge(unknown)


def _diagnostic():
    return {
        "schema_id": "native-root-occurrence-mapping-diagnostic-v2",
        "status": "completed",
        "mapping_subreason": "mapping_completed",
        "public_legal_occurrence_count": 5,
        "search_root_edge_count": 2,
        "public_occurrences_mapped": 3,
        "public_occurrences_classified": 5,
        "searched_public_occurrence_count": 3,
        "configuration_excluded_public_occurrence_count": 2,
        "search_root_edges_covered": 2,
        "direct_mapping_count": 2,
        "mechanical_duplicate_mapping_count": 1,
    }


def test_diagnostic_v2_completed_counts_and_v1_are_separate():
    diagnostic = _diagnostic()
    assert (
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="completed")
        == diagnostic
    )
    for field in (
        "public_occurrences_classified",
        "public_occurrences_mapped",
        "searched_public_occurrence_count",
        "configuration_excluded_public_occurrence_count",
        "search_root_edges_covered",
    ):
        invalid = deepcopy(diagnostic)
        invalid[field] += 1
        with pytest.raises(ValueError):
            validate_t107_mapping_diagnostic(invalid, mapping_stage_status="completed")
    diagnostic["schema_id"] = "native-root-occurrence-mapping-diagnostic-v1"
    with pytest.raises(ValueError):
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="completed")


def test_v2_empty_surface_cannot_complete_without_reinterpreting_v1():
    diagnostic = {
        "schema_id": "native-root-occurrence-mapping-diagnostic-v2",
        "status": "completed",
        "mapping_subreason": "mapping_completed",
        "public_legal_occurrence_count": 0,
        "search_root_edge_count": 0,
        "public_occurrences_mapped": 0,
        "public_occurrences_classified": 0,
        "searched_public_occurrence_count": 0,
        "configuration_excluded_public_occurrence_count": 0,
        "search_root_edges_covered": 0,
        "direct_mapping_count": 0,
        "mechanical_duplicate_mapping_count": 0,
    }
    with pytest.raises(ValueError, match="empty public action surface"):
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="completed")
    historical = {
        key: value
        for key, value in diagnostic.items()
        if key
        not in {
            "public_occurrences_classified",
            "searched_public_occurrence_count",
            "configuration_excluded_public_occurrence_count",
        }
    }
    historical["schema_id"] = "native-root-occurrence-mapping-diagnostic-v1"
    assert (
        validate_t107_mapping_diagnostic(historical, mapping_stage_status="completed")
        == historical
    )
    diagnostic.update(
        status="failed", mapping_subreason="no_public_legal_action_surface"
    )
    assert (
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="failed")
        == diagnostic
    )


def test_v2_failure_progress_counts_classified_exclusions_before_failed_occurrence():
    diagnostic = _diagnostic()
    diagnostic.update(
        status="failed",
        mapping_subreason="missing_non_card_direct_search_root_match",
        public_legal_occurrence_count=6,
        public_occurrence_index=5,
        public_action_kind="end_turn",
        direct_match_multiplicity="zero",
    )
    assert (
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="failed")
        == diagnostic
    )
    diagnostic["public_occurrence_index"] = 3
    with pytest.raises(ValueError):
        validate_t107_mapping_diagnostic(diagnostic, mapping_stage_status="failed")


def test_stsr009_all_twelve_predicates_are_required():
    names = [
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
    ]
    audit = {
        "schema_id": "native-stsr009-configuration-aware-root-mapping-audit-v1",
        **dict.fromkeys(names, True),
    }
    assert validate_t110_configuration_mapping_audit(audit) == audit
    for name in names:
        for bad in (False, 1, None):
            invalid = dict(audit, **{name: bad})
            with pytest.raises(ValueError):
                validate_t110_configuration_mapping_audit(invalid)


def test_runtime_identity_allowlist_accepts_only_named_pins(monkeypatch):
    from sts_combat_rl.commands import t085_native_execution as runtime

    pin = "6496fc1c7e629a374b72bd94f7fd29afe29c7f62"
    assert runtime.T110_CONFIGURATION_MAPPING_NATIVE_IDENTITY["commit"] == pin
    assert runtime.T085_NATIVE_IDENTITY["commit"] != pin
    assert runtime.T107_ROOT_MAPPING_NATIVE_IDENTITY["commit"] == (
        "1458522294d967e8985e1fd52cc15d7ebe7f2acd"
    )

    def manifest_for(commit):
        return SimpleNamespace(
            capability_ids={"native_battle_search_v2_tree_internal"},
            integration=SimpleNamespace(
                repository_url="https://github.com/lsmfttb/sts_lightspeed.git",
                ref="refs/heads/stsrl/main",
                commit=commit,
            ),
        )

    for identity in runtime._T085_ACCEPTED_RUNTIME_IDENTITIES:
        monkeypatch.setattr(
            runtime,
            "load_lightspeed_source_manifest",
            lambda identity=identity: manifest_for(identity["commit"]),
        )
        assert runtime._validate_t085_native_source_manifest("battle_search_v2") == (
            identity
        )
    monkeypatch.setattr(
        runtime, "load_lightspeed_source_manifest", lambda: manifest_for("a" * 40)
    )
    with pytest.raises(
        runtime.T085NativeExecutionError, match="accepted sts_lightspeed"
    ):
        runtime._validate_t085_native_source_manifest("battle_search_v2")
