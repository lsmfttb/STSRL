from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest
from test_t099_particle_search_bridge import _bridge_report
from test_t110_configuration_aware_mapping import _v2_report

from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111ConfiguredSearchError,
    T111SupportExclusion,
    select_t111_configured_search_cohort,
    validate_t111_configured_search_cohort,
    validate_t111_configured_search_report,
)

_NATIVE = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": T111_NATIVE_REF,
    "commit": T111_NATIVE_COMMIT,
}


def _two_particle_v2_report(seed: int = 17) -> dict[str, object]:
    report = _v2_report()
    first = report["particles"][0]
    first["sampler_seed"] = seed
    first["root_evaluation"]["simulations_requested"] = 400
    first["root_evaluation"]["root_visits"] = 800
    report["search_simulations"] = 400
    second = deepcopy(first)
    second["particle_index"] = 1
    second["sampler_seed"] = seed
    second["hidden_future_fingerprint"] = "second-private-fingerprint"
    report["particle_count"] = 2
    report["sampler_seed_input"] = seed
    report["particles"] = [first, second]
    return report


def _source_population() -> list[dict[str, object]]:
    return [
        {"selection_identity": f"{stratum}:{index:03d}", "cohort": stratum}
        for stratum, count in T101_SOURCE_COUNTS.items()
        for index in range(count)
    ]


def test_t111_search_view_keeps_exclusions_public_but_out_of_numeric_classes():
    result = validate_t111_configured_search_report(
        _two_particle_v2_report(), expected_sampler_seed=17
    )

    assert result["public_action_count"] == 5
    assert result["searched_occurrence_count_per_particle"] == 3
    assert result["configuration_excluded_occurrence_count_per_particle"] == 2
    assert result["configuration_excluded_public_action_ordinals"] == [3, 4]
    excluded = result["configuration_excluded_public_occurrences"]
    assert [row["public_action_ordinal"] for row in excluded] == [3, 4]
    assert [row["public_action"]["kind"] for row in excluded] == [
        "potion",
        "potion_discard",
    ]
    for occurrence in excluded:
        for particle in occurrence["particle_evidence"]:
            assert particle["mapping_classification"] == "search_configuration_excluded"
            assert particle["configuration_exclusion_reason"] == "include_potions_false"
            assert particle["visits"] == 0
            assert particle["evaluation_sum"] is None
            assert particle["mean_value"] is None
    assert result["public_occurrence_classification_by_ordinal"] == [
        {"public_action_ordinal": 0, "classification": "searched_direct"},
        {
            "public_action_ordinal": 1,
            "classification": "searched_direct",
        },
        {
            "public_action_ordinal": 2,
            "classification": "searched_mechanical_duplicate_card_occurrence",
        },
        {
            "public_action_ordinal": 3,
            "classification": "search_configuration_excluded",
        },
        {
            "public_action_ordinal": 4,
            "classification": "search_configuration_excluded",
        },
    ]
    assert result["configured_search_decision_class_count"] == 2
    assert result["configured_search_decision_classes"] == [
        {"class_index": 0, "public_action_ordinals": [0]},
        {"class_index": 1, "public_action_ordinals": [1, 2]},
    ]
    assert len(result["searched_classification_by_public_ordinal"]) == 3
    assert result["all_searched_occurrences_finite_and_visited"] is True
    assert "mean_value" not in result
    assert "evaluation_sum" not in result
    assert all(
        "mean_value" not in row and "evaluation_sum" not in row
        for row in result["configured_search_decision_classes"]
    )


def test_t111_refuses_historical_v1_and_keeps_t099_semantics_out_of_scope():
    legacy = _bridge_report()
    legacy["particle_count"] = 2
    legacy["particles"].append(deepcopy(legacy["particles"][0]))
    legacy["particles"][1]["particle_index"] = 1
    with pytest.raises(T111SupportExclusion) as error:
        validate_t111_configured_search_report(legacy, expected_sampler_seed=17)
    assert error.value.reason == "v2_bridge_schema_or_classification_failure"


@pytest.mark.parametrize(
    ("field", "value"),
    [("mean_value", float("nan")), ("evaluation_sum", float("inf")), ("visits", 0)],
)
def test_t111_requires_finite_visited_value_for_every_searched_occurrence(field, value):
    report = _two_particle_v2_report()
    report["particles"][0]["root_rows"][1][field] = value
    with pytest.raises(T111SupportExclusion) as error:
        validate_t111_configured_search_report(report, expected_sampler_seed=17)
    assert error.value.reason == "searched_value_unavailable_nonfinite_or_unvisited"


@pytest.mark.parametrize("particle_index", [None, 0, 1])
def test_t111_checks_actual_bridge_and_each_particle_sampler_seed(particle_index):
    report = _two_particle_v2_report(seed=derive_t101_sampler_seed("A:000", 0))
    if particle_index is None:
        report["sampler_seed_input"] += 1
    else:
        report["particles"][particle_index]["sampler_seed"] += 1

    with pytest.raises(T111SupportExclusion) as error:
        validate_t111_configured_search_report(
            report,
            expected_sampler_seed=derive_t101_sampler_seed("A:000", 0),
        )
    assert error.value.reason == "v2_bridge_schema_or_classification_failure"


def test_t111_requires_identical_searched_partition_across_n2_particles():
    report = _two_particle_v2_report()
    particle = report["particles"][1]
    root = particle["root_evaluation"]
    row = particle["root_rows"][2]
    mapping = root["root_action_mapping"][2]
    action = report["anchor_ordered_public_legal_actions"][2]
    row.update(
        mapping_classification="searched_direct",
        search_edge_index=2,
        search_equivalence_source_edge_index=2,
        search_equivalence_mapping_mode="direct_action_bits",
    )
    mapping.update(
        mapping_classification="searched_direct",
        search_edge_index=2,
        mapping_mode="direct_action_bits",
        source_action=action,
        edge_public_occurrence_count=1,
    )
    root["search_edge_count"] = 3
    root["root_action_mapping"][1]["edge_public_occurrence_count"] = 1
    with pytest.raises(T111SupportExclusion) as error:
        validate_t111_configured_search_report(report, expected_sampler_seed=17)
    assert error.value.reason == "searched_excluded_partition_drift"


def test_t111_selector_reuses_t101_hash_order_and_stops_after_eight_per_stratum():
    population = _source_population()
    expected: dict[str, list[str]] = {}
    for stratum in T101_SOURCE_COUNTS:
        expected[stratum] = sorted(
            row["selection_identity"] for row in population if row["cohort"] == stratum
        )
        expected[stratum].sort(
            key=lambda identity: (
                hashlib.sha256(identity.encode()).hexdigest(),
                identity,
            )
        )

    report = select_t111_configured_search_cohort(
        population,
        native_identity=_NATIVE,
        admit=lambda _row: {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": _two_particle_v2_report(
                derive_t101_sampler_seed(_row["selection_identity"], 0)
            ),
        },
    )
    checked = validate_t111_configured_search_cohort(report)

    assert checked["terminal_classification"] == (
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_SUFFICIENT"
    )
    assert checked["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert len(checked["attempted"]) == 24
    for stratum in T101_SOURCE_COUNTS:
        rows = [row for row in checked["attempted"] if row["stratum"] == stratum]
        assert [row["selection_identity"] for row in rows] == expected[stratum][:8]
        assert rows[-1]["admitted"] is True


def test_t111_exhausts_each_stratum_without_backfill_or_failure_preselection():
    population = _source_population()

    def admit(row):
        if row["cohort"] == "A":
            raise T111SupportExclusion(
                "searched_value_unavailable_nonfinite_or_unvisited"
            )
        return {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": _two_particle_v2_report(
                derive_t101_sampler_seed(row["selection_identity"], 0)
            ),
        }

    result = validate_t111_configured_search_cohort(
        select_t111_configured_search_cohort(
            population, native_identity=_NATIVE, admit=admit
        )
    )
    assert result["terminal_classification"] == (
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
    )
    assert result["selected_counts"] == {"A": 0, "B": 8, "C": 8}
    assert result["exhausted_strata"] == ["A"]
    assert len(result["attempted"]) == 93 + 8 + 8
    assert all(row["admitted"] is False for row in result["attempted"][:93])


def test_t111_validator_rejects_attempts_after_stratum_reaches_eight():
    population = _source_population()
    result = select_t111_configured_search_cohort(
        population,
        native_identity=_NATIVE,
        admit=lambda _row: {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": _two_particle_v2_report(
                derive_t101_sampler_seed(_row["selection_identity"], 0)
            ),
        },
    )
    result["attempted"].insert(8, deepcopy(result["attempted"][7]))
    with pytest.raises(T111ConfiguredSearchError):
        validate_t111_configured_search_cohort(result)


def test_t111_cohort_validator_checks_selected_seed_and_order_binding():
    result = select_t111_configured_search_cohort(
        _source_population(),
        native_identity=_NATIVE,
        admit=lambda row: {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": _two_particle_v2_report(
                derive_t101_sampler_seed(row["selection_identity"], 0)
            ),
        },
    )
    result["selected"][0]["sampler_seed"] += 1

    with pytest.raises(T111ConfiguredSearchError):
        validate_t111_configured_search_cohort(result)
