from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from sts_combat_rl.sim.t061_bottleneck_decomposition import (
    build_t061_budget_curve_report,
    build_t061_bottleneck_report,
    build_t061_factorial_report,
)
from sts_combat_rl.commands.oracle_search import _select_record_range


def _provenance(distribution: str):
    return {
        "simulator": "sts_lightspeed",
        "source_manifest": "docs/sts_lightspeed_source_manifest.json",
        "integration_commit": "9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a",
        "action_space": "initial_no_potions",
        "root_selection_rule": "highest_mean",
        "information_regime": "full_simulator_state_oracle_like",
        "search_api": "StepSimulator.battle_search.v1",
        "distribution_kind": distribution,
        "controller_name": "oracle_search_v1",
    }


def _artifact(name: str):
    path = Path(__file__)
    data = path.read_bytes()
    digest = hashlib.sha256(path.name.encode() + data).hexdigest()
    return {
        "path": str(path),
        "sha256": digest,
        "bytes": len(data),
        "hash_basis": "file bytes with basename prefix",
    }


def _search_summary(budget=20):
    def metric(total=float(budget)):
        return {
            "count": 1,
            "missing_count": 0,
            "total": total,
            "minimum": total,
            "maximum": total,
            "mean": total,
        }

    return {
        "schema_id": "search-telemetry-summary-v1",
        "schema_version": 1,
        "decision_telemetry_schema_id": "search-decision-telemetry-v1",
        "decision_telemetry_schema_version": 1,
        "decision_count": 1,
        "information_regime_counts": {"full_simulator_state_oracle_like": 1},
        "controller_kind_counts": {"oracle_battle_search": 1},
        "search_kind_counts": {"native_random_terminal_playout": 1},
        "backend_counts": {"StepSimulator.battle_search.v1": 1},
        "budget_unit_counts": {"native_random_terminal_playouts": 1},
        "simulations_requested": metric(),
        "root_visits": metric(),
        "root_action_count": metric(),
        "legal_action_count": metric(),
        "native_simulator_steps": metric(),
        "model_calls": metric(0.0),
        "wall_clock_time_s": metric(),
        "root_value_spread": metric(),
        "root_decision_gap": metric(),
        "unsearched_legal_action_count": metric(),
        "unmapped_search_edge_count": metric(),
        "unmapped_root_row_count": metric(),
        "root_mapping_failure_count": metric(),
        "unavailable_field_counts": {},
        "unavailable_reasons": {},
        "decision_problem_count": 0,
        "problem_count": 0,
    }


def _budget_arm(budget: int):
    return {
        "provenance": _provenance("fixed_cohort"),
        "arm_provenance": {
            "budget": budget,
            "controller_name": "oracle_search_v1",
            "search_budget": budget,
            "root_selection_rule": "highest_mean",
            "action_space": "initial_no_potions",
            "information_regime": "full_simulator_state_oracle_like",
            "distribution_kind": "fixed_cohort",
            "workers": 16,
            "shards": 16,
            "cohort_record_ids_sha256": hashlib.sha256(
                "r0\nr1\nr2".encode()
            ).hexdigest(),
            "controller_implementation": f"oracle_search_v1_highest_mean_s{budget}",
            "action_space_config": {"preferred_kinds": ["card", "end_turn"]},
        },
        "artifact_identity": _artifact(f"budget-{budget}"),
        "records": [
            {
                "record_id": f"r{i}",
                "won": i == 0,
                "terminal_absolute_hp": 10 + budget,
                "status": "win" if i == 0 else "loss",
                "selected_root_action": {"action": "a"},
                "outer_simulator_steps": budget,
                "outer_wall_clock_seconds": 1.0,
                "search_telemetry_summary": _search_summary(budget),
                "search_simulations_completed": None,
                "search_simulations_completed_unavailable_reason": "native search does not expose completed simulations",
                "potion_outcome": {"status": "available", "value": []},
                "structured_terminal_resource_outcome": {
                    "schema_id": "structured-battle-outcome-v1"
                },
                "act": 1,
                "room_type": "BOSS",
                "encounter_id": "HEXAGHOST",
                "boss": "BOSS",
                "truncation": False,
                "controller_error": False,
                "unsupported_state": False,
                "problems": [],
            }
            for i in range(3)
        ],
    }


def _factorial_arm(driver: str, budget: int, *, later_act: bool = False):
    return {
        "provenance": _provenance("natural_run"),
        "arm_provenance": {
            "driver": driver,
            "budget": budget,
            "controller_name": "oracle_search_v1",
            "search_budget": budget,
            "root_selection_rule": "highest_mean",
            "action_space": "initial_no_potions",
            "information_regime": "full_simulator_state_oracle_like",
            "distribution_kind": "natural_run",
            "workers": 16,
            "shards": 16,
            "seed_start": 0,
            "seed_end": 3,
            "sim_steps": 500,
            "controller_implementation": f"oracle_search_v1_highest_mean_s{budget}",
            "non_combat_controller_implementation": driver,
        },
        "artifact_identity": _artifact(f"{driver}-{budget}"),
        "runs": [
            {
                "seed": str(i),
                "source_run_id": f"run-{i}",
                "won": budget == 300 and driver == "expert_non_combat_v1",
                "status": "completed",
                "terminal_floor": 10,
                "terminal_status": "PLAYER_LOSS",
                "act1_boss_start": False,
                "act1_boss_victory": False,
                "act2_boss_start": False,
                "act2_boss_victory": False,
                "act3_boss_start": False,
                "act3_boss_victory": False,
                "act2_entry": later_act,
                "act3_entry": False,
                "act4_entry": False,
                "heart_start": False,
                "heart_victory": False,
                "shield_spear_start": False,
                "shield_spear_outcome": False,
                "death_encounter": "JAW_WORM",
                "pre_death_public_resource_snapshot": None,
                "natural_battle_starts": 2,
                "unique_source_starts": 2,
                "act_counts": {"1": 2},
                "room_type_counts": {"MONSTER": 2},
                "encounter_id_counts": {"JAW_WORM": 2},
                "unique_act_counts": {"1": 2},
                "unique_room_type_counts": {"MONSTER": 2},
                "unique_encounter_id_counts": {"JAW_WORM": 2},
                "outer_simulator_steps": budget * 2,
                "outer_wall_clock_seconds": 1.0,
                "search_telemetry_summary": _search_summary(budget),
                "search_simulations_completed": None,
                "search_simulations_completed_unavailable_reason": "native search does not expose completed simulations",
                "truncation": False,
                "controller_error": False,
                "unsupported_state": False,
                "problems": [],
            }
            for i in range(4)
        ],
    }


def _factorial_arms():
    drivers = ("stochastic_non_combat_v1", "expert_non_combat_v1")
    return [
        (driver, str(budget), _factorial_arm(driver, budget))
        for driver in drivers
        for budget in (20, 100, 300)
    ]


def test_budget_curve_requires_identical_cohort_and_reports_pairwise():
    report = build_t061_budget_curve_report(
        [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    )
    assert report["command_passed"] is True
    assert report["cohort"]["record_count"] == 3
    assert len(report["arms"]["20"]["records"]) == 3
    assert report["pairwise"]["300_vs_20"]["first_action_disagreement_count"] == 0

    bad = _budget_arm(300)
    bad["records"][0]["record_id"] = "different"
    with pytest.raises(ValueError, match="same cohort identities"):
        build_t061_budget_curve_report(
            [("20", _budget_arm(20)), ("100", _budget_arm(100)), ("300", bad)]
        )


def test_factorial_requires_same_seed_set_and_keeps_zero_cells():
    report = build_t061_factorial_report(
        _factorial_arms(), expected_run_count=4, bootstrap_resamples=100
    )
    assert report["total_run_count"] == 24
    assert (
        report["arms"]["stochastic_non_combat_v1@20"]["reachability"]["act3_entry"] == 0
    )
    assert report["effects"]["driver_effects"]["300"]["won"]["mean"] == 1.0
    assert "interaction_effects" in report["effects"]

    changed = _factorial_arm("stochastic_non_combat_v1", 20)
    changed["runs"][0]["seed"] = "other"
    changed_arms = [
        (
            driver,
            str(budget),
            changed
            if (driver, budget) == ("stochastic_non_combat_v1", 20)
            else _factorial_arm(driver, budget),
        )
        for driver in ("stochastic_non_combat_v1", "expert_non_combat_v1")
        for budget in (20, 100, 300)
    ]
    with pytest.raises(
        ValueError, match="seed range|same seeds|seeds must be integers"
    ):
        build_t061_factorial_report(
            changed_arms, expected_run_count=4, bootstrap_resamples=100
        )


def test_swapped_arm_provenance_fails_closed():
    arms = _factorial_arms()
    arms[0][2]["arm_provenance"]["driver"] = "expert_non_combat_v1"
    with pytest.raises(ValueError, match="driver does not match"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)

    arms = _factorial_arms()
    arms[0][2]["arm_provenance"]["budget"] = 300
    with pytest.raises(ValueError, match="budget does not match"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)


def test_missing_evidence_fails_closed_instead_of_becoming_zero():
    arms = _factorial_arms()
    del arms[0][2]["runs"][0]["act3_entry"]
    with pytest.raises(ValueError, match="missing fields"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)


def test_decision_includes_complete_run_budget_effect_and_recommends_t062():
    budget = build_t061_budget_curve_report(
        [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    )
    factorial = build_t061_factorial_report(
        _factorial_arms(), expected_run_count=4, bootstrap_resamples=100
    )
    decision = build_t061_bottleneck_report(budget, factorial)
    assert decision["decision"]["recommended_next_task"] == "T062"
    assert (
        "complete_run_factorial_budget_effect"
        in decision["decision"]["battle_budget_signal_sources"]
    )


def test_truncation_remains_visible_and_fails_command():
    arms = _factorial_arms()
    arms[0][2]["runs"][0]["status"] = "truncated"
    arms[0][2]["runs"][0]["truncation"] = True
    report = build_t061_factorial_report(
        arms, expected_run_count=4, bootstrap_resamples=100
    )
    assert report["command_passed"] is False
    assert report["arms"]["stochastic_non_combat_v1@20"]["truncation_count"] == 1


def test_controller_failure_and_problem_cannot_pass_as_success():
    arms = _factorial_arms()
    row = arms[0][2]["runs"][0]
    row["status"] = "error"
    row["controller_error"] = True
    row["problems"] = ["injected controller failure"]
    report = build_t061_factorial_report(
        arms, expected_run_count=4, bootstrap_resamples=100
    )
    assert report["command_passed"] is False
    assert report["arms"]["stochastic_non_combat_v1@20"]["error_count"] == 1

    arms = _factorial_arms()
    arms[0][2]["runs"][0]["controller_error"] = True
    with pytest.raises(ValueError, match="inconsistent with failure"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)


def test_oracle_record_range_selects_explicit_half_open_slice():
    records = list(range(6))
    assert list(_select_record_range(records, "1:4")) == [1, 2, 3]
    with pytest.raises(ValueError, match="outside the cohort"):
        _select_record_range(records, "4:7")


def test_missing_retained_artifact_path_fails_closed():
    arms = _factorial_arms()
    arms[0][2]["artifact_identity"] = {
        "path": "Z:/definitely-missing/t061-artifact",
        "sha256": "0" * 64,
        "bytes": 0,
    }
    with pytest.raises(ValueError, match="input artifact identity"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)

    budget_arms = [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    budget_arms[0][1]["artifact_identity"] = {
        "path": "Z:/definitely-missing/t061-budget-artifact",
        "sha256": "0" * 64,
        "bytes": 0,
    }
    with pytest.raises(ValueError, match="input artifact identity"):
        build_t061_budget_curve_report(budget_arms)


def test_malformed_search_telemetry_fails_closed_for_both_report_families():
    arms = _factorial_arms()
    summary = arms[0][2]["runs"][0]["search_telemetry_summary"]
    summary["native_simulator_steps"] = {
        "count": 0,
        "missing_count": 999,
        "total": -123.0,
        "minimum": -123.0,
        "maximum": -123.0,
        "mean": -123.0,
    }
    with pytest.raises(ValueError, match="count fields|invalid negative"):
        build_t061_factorial_report(arms, expected_run_count=4, bootstrap_resamples=100)

    budget_arms = [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    budget_arms[0][1]["records"][0]["search_telemetry_summary"][
        "information_regime_counts"
    ] = {"normal_public_policy": 1}
    with pytest.raises(ValueError, match="pinned arm provenance"):
        build_t061_budget_curve_report(budget_arms)
