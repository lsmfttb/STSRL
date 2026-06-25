from __future__ import annotations

import pytest

from sts_combat_rl.sim.search_telemetry import (
    SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
    SearchDecisionTelemetry,
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    search_decision_telemetry_from_dict,
    summarize_search_decision_telemetry,
    summarize_search_decision_telemetry_dicts,
)


def _telemetry(
    *,
    simulations: int = 10,
    native_steps: int | None = 42,
    model_calls: int = 0,
    spread: float | None = 0.4,
    gap: float | None = 0.1,
) -> SearchDecisionTelemetry:
    unavailable = {
        "tree_depth": "native battle_search does not expose tree depth",
        "value_uncertainty": "native battle_search does not expose uncertainty",
    }
    if native_steps is None:
        unavailable["native_simulator_steps"] = (
            "native search result did not expose native_simulator_steps"
        )
    if spread is None:
        unavailable["root_value_spread"] = (
            "no visited eligible root action mean values were available"
        )
    if gap is None:
        unavailable["root_decision_gap"] = (
            "fewer than two visited eligible root actions had mean values"
        )
    return SearchDecisionTelemetry(
        information_regime="full_simulator_state_oracle_like",
        controller_kind="oracle_battle_search",
        search_kind="native_random_terminal_playout",
        search_backend={
            "native_api": "StepSimulator.battle_search.v1",
            "patch_identity": "sts_lightspeed_battle_search_root_v1",
        },
        requested_budget={
            "unit": "native_random_terminal_playouts",
            "amount": simulations,
        },
        simulations_requested=simulations,
        root_visits=simulations,
        root_action_count=2,
        legal_action_count=2,
        eligible_action_count=2,
        visited_action_count=2,
        visited_eligible_action_count=2,
        native_simulator_steps=native_steps,
        model_calls=model_calls,
        wall_clock_time_s=0.25,
        root_value_min=0.2,
        root_value_max=0.6,
        root_value_spread=spread,
        root_decision_gap=gap,
        unsearched_legal_action_count=0,
        unmapped_search_edge_count=0,
        unmapped_root_row_count=0,
        root_mapping_failure_count=0,
        selection_rule="highest_mean",
        selected_legal_action_index=1,
        selected_visits=3,
        selected_mean_value=0.6,
        unavailable_fields=unavailable,
    )


def test_search_decision_telemetry_round_trips() -> None:
    record = _telemetry().to_dict()

    loaded = search_decision_telemetry_from_dict(record)

    assert loaded.schema_id == SEARCH_DECISION_TELEMETRY_SCHEMA_ID
    assert loaded.model_calls == 0
    assert loaded.root_value_spread == pytest.approx(0.4)
    assert loaded.unavailable_fields["tree_depth"].startswith("native")


def test_search_decision_telemetry_rejects_unknown_schema() -> None:
    record = _telemetry().to_dict()
    record["schema_id"] = "search-decision-telemetry-v999"

    with pytest.raises(ValueError, match="unsupported schema_id"):
        search_decision_telemetry_from_dict(record)


def test_nested_metadata_extraction_and_summary() -> None:
    records = [_telemetry(simulations=10), _telemetry(simulations=20)]
    metadata = {
        "search_decision_telemetry": [[record.to_dict()] for record in records],
    }

    extracted = iter_search_decision_telemetry_dicts(metadata)
    summary = summarize_search_decision_telemetry_dicts(extracted)

    assert len(extracted) == 2
    assert summary.decision_count == 2
    assert summary.model_calls.total == 0.0
    assert summary.simulations_requested.total == 30.0
    assert summary.unavailable_field_counts == {
        "tree_depth": 2,
        "value_uncertainty": 2,
    }


def test_summary_formats_missing_native_fields_deterministically() -> None:
    summary = summarize_search_decision_telemetry(
        [
            _telemetry(simulations=5, native_steps=None, spread=None, gap=None),
        ]
    )

    text = format_search_telemetry_summary(summary)

    assert "schema: search-decision-telemetry-v1 v1" in text
    assert "model calls: total=0" in text
    assert "native simulator steps: (unavailable; missing=1)" in text
    assert "root_decision_gap: fewer than two" in text
