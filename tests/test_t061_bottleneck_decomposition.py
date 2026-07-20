from __future__ import annotations

import pytest

from sts_combat_rl.sim.t061_bottleneck_decomposition import (
    build_t061_budget_curve_report,
    build_t061_bottleneck_report,
    build_t061_factorial_report,
)


def _budget_arm(budget: int, *, provenance=None):
    return {
        "provenance": provenance
        or {
            "simulator": "pinned",
            "information_regime": "full_simulator_state_oracle_like",
        },
        "records": [
            {
                "record_id": f"r{i}",
                "won": i == 0,
                "terminal_absolute_hp": 10 + budget,
                "selected_root_action": "a",
            }
            for i in range(3)
        ],
    }


def _factorial_arm(driver: str, budget: int, *, later_act: bool = False):
    return {
        "provenance": {
            "simulator": "pinned",
            "information_regime": "full_simulator_state_oracle_like",
        },
        "runs": [
            {
                "seed": str(i),
                "won": budget == 300 and driver == "expert_non_combat_v1",
                "act2_entry": later_act,
                "act3_entry": False,
                "heart_victory": False,
                "status": "completed",
                "natural_battle_starts": 2,
                "unique_source_starts": 2,
            }
            for i in range(4)
        ],
    }


def test_budget_curve_requires_identical_cohort_and_reports_pairwise():
    report = build_t061_budget_curve_report(
        [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    )
    assert report["command_passed"] is True
    assert report["cohort"]["record_count"] == 3
    assert report["pairwise"]["300_vs_20"]["first_action_disagreement_count"] == 0

    bad = _budget_arm(300)
    bad["records"][0]["record_id"] = "different"
    with pytest.raises(ValueError, match="same cohort identities"):
        build_t061_budget_curve_report(
            [("20", _budget_arm(20)), ("100", _budget_arm(100)), ("300", bad)]
        )


def test_factorial_requires_same_seed_set_and_keeps_zero_cells():
    drivers = ("stochastic_non_combat_v1", "expert_non_combat_v1")
    arms = [
        (driver, str(budget), _factorial_arm(driver, budget))
        for driver in drivers
        for budget in (20, 100, 300)
    ]
    report = build_t061_factorial_report(
        arms, expected_run_count=4, bootstrap_resamples=100
    )
    assert report["total_run_count"] == 24
    assert (
        report["arms"]["stochastic_non_combat_v1@20"]["reachability"]["act3_entry"] == 0
    )
    assert report["effects"]["driver_effects"]["300"]["won"]["mean"] == 1.0

    changed = _factorial_arm(drivers[0], 20)
    changed["runs"][0]["seed"] = "other"
    changed_arms = [
        (
            driver,
            str(budget),
            changed
            if (driver, budget) == (drivers[0], 20)
            else _factorial_arm(driver, budget),
        )
        for driver in drivers
        for budget in (20, 100, 300)
    ]
    with pytest.raises(ValueError, match="same seeds"):
        build_t061_factorial_report(
            changed_arms, expected_run_count=4, bootstrap_resamples=100
        )


def test_decision_recommends_one_next_task_using_published_order():
    budget = build_t061_budget_curve_report(
        [(str(budget), _budget_arm(budget)) for budget in (20, 100, 300)]
    )
    drivers = ("stochastic_non_combat_v1", "expert_non_combat_v1")
    factorial = build_t061_factorial_report(
        [
            (driver, str(budget), _factorial_arm(driver, budget))
            for driver in drivers
            for budget in (20, 100, 300)
        ],
        expected_run_count=4,
        bootstrap_resamples=100,
    )
    decision = build_t061_bottleneck_report(budget, factorial)
    assert decision["decision"]["recommended_next_task"] == "T065"
    assert isinstance(decision["decision"]["recommended_next_task"], str)
