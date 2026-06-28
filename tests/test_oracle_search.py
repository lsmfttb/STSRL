from __future__ import annotations

import pytest

from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
    build_oracle_search_report,
    oracle_search_decision_telemetry,
    select_oracle_root_action,
)
from sts_combat_rl.sim.policy import DecisionContext


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="Defend",
            kind="card",
            raw={"scope": "battle", "bits": 22},
        ),
    ]


def _context(
    action_count: int = 2,
    *,
    kinds: list[str] | None = None,
) -> DecisionContext:
    legal_kinds = kinds if kinds is not None else ["card" for _ in range(action_count)]
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[] for _ in range(action_count)],
        legal_action_kinds=legal_kinds,
        eligible_action_indices=list(range(action_count)),
    )


def _row(
    bits: int,
    *,
    visits: int,
    evaluation_sum: float | None,
    mean_value: float | None,
    label: str,
    kind: str = "card",
    idx1: int = 0,
    idx2: int = 0,
    idx3: int = 0,
) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": bits,
        "kind": kind,
        "label": label,
        "idx1": idx1,
        "idx2": idx2,
        "idx3": idx3,
        "search_tree_present": True,
        "search_edge_index": 0,
        "visits": visits,
        "evaluation_sum": evaluation_sum,
        "mean_value": mean_value,
    }


def _raw_search(
    rows: list[dict[str, object]],
    *,
    root_visits: int | None = None,
    include_potions: bool = False,
    unmapped_search_edge_count: int = 0,
) -> dict[str, object]:
    row_visit_sum = sum(int(row["visits"]) for row in rows)
    return {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": ORACLE_SEARCH_NATIVE_API,
        "patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": root_visits
        if root_visits is not None
        else row_visit_sum,
        "root_visits": root_visits if root_visits is not None else row_visit_sum,
        "include_potions": include_potions,
        "native_simulator_steps": 123,
        "model_calls": None,
        "best_action_value": 0.5,
        "min_action_value": 0.1,
        "outcome_player_hp": 42,
        "root_row_count": len(rows),
        "search_edge_count": len(rows),
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": unmapped_search_edge_count,
        "root_rows": rows,
    }


def test_oracle_root_mapping_selects_mean_and_visit_targets() -> None:
    report = build_oracle_search_report(
        _raw_search(
            [
                _row(11, visits=7, evaluation_sum=2.8, mean_value=0.4, label="Strike"),
                _row(22, visits=3, evaluation_sum=1.5, mean_value=0.5, label="Defend"),
            ]
        ),
        _actions(),
        _context(),
        wall_clock_time_s=0.25,
    )

    assert report.search_ok
    assert report.soft_visit_target == pytest.approx((0.7, 0.3))
    assert report.native_simulator_steps == 123
    assert report.model_calls is None
    telemetry = oracle_search_decision_telemetry(report)
    assert telemetry.schema_id == "search-decision-telemetry-v1"
    assert telemetry.model_calls == 0
    assert telemetry.root_value_spread == pytest.approx(0.1)
    assert telemetry.root_decision_gap == pytest.approx(0.1)
    assert telemetry.unavailable_fields["tree_depth"].startswith("native")
    assert report.to_dict()["decision_telemetry"]["model_calls"] == 0
    assert (
        select_oracle_root_action(
            report, selection_rule="highest_mean"
        ).legal_action_index
        == 1
    )
    assert (
        select_oracle_root_action(
            report, selection_rule="most_visits"
        ).legal_action_index
        == 0
    )


def test_oracle_root_mapping_uses_occurrence_safe_identities() -> None:
    actions = [
        SimulatorAction(action_id="battle:7", label="first", kind="card"),
        SimulatorAction(action_id="battle:7", label="second", kind="card"),
    ]
    report = build_oracle_search_report(
        _raw_search(
            [
                _row(7, visits=1, evaluation_sum=0.1, mean_value=0.1, label="first"),
                _row(7, visits=2, evaluation_sum=0.4, mean_value=0.2, label="second"),
            ]
        ),
        actions,
        _context(action_count=2),
    )

    assert report.search_ok
    assert [row.action_identity["occurrence"] for row in report.root_actions] == [0, 1]
    assert report.soft_visit_target == pytest.approx((1 / 3, 2 / 3))


def test_oracle_root_mapping_preserves_potion_identities() -> None:
    actions = [
        SimulatorAction(
            action_id="battle:0",
            label="End Turn",
            kind="end_turn",
            raw={"scope": "battle", "bits": 0, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="battle:536870912",
            label="Fire Potion -> Cultist",
            kind="potion",
            raw={
                "scope": "battle",
                "bits": 536870912,
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
            },
        ),
        SimulatorAction(
            action_id="battle:537264128",
            label="Fire Potion -> Jaw Worm",
            kind="potion",
            raw={
                "scope": "battle",
                "bits": 537264128,
                "idx1": 0,
                "idx2": 1,
                "idx3": 0,
            },
        ),
        SimulatorAction(
            action_id="battle:537264128",
            label="duplicate native potion occurrence",
            kind="potion",
            raw={
                "scope": "battle",
                "bits": 537264128,
                "idx1": 0,
                "idx2": 1,
                "idx3": 0,
            },
        ),
    ]
    report = build_oracle_search_report(
        _raw_search(
            [
                _row(
                    0,
                    visits=1,
                    evaluation_sum=0.1,
                    mean_value=0.1,
                    label="End Turn",
                    kind="end_turn",
                ),
                _row(
                    536870912,
                    visits=3,
                    evaluation_sum=1.2,
                    mean_value=0.4,
                    label="Fire Potion -> Cultist",
                    kind="potion",
                    idx1=0,
                    idx2=0,
                ),
                _row(
                    537264128,
                    visits=4,
                    evaluation_sum=2.4,
                    mean_value=0.6,
                    label="Fire Potion -> Jaw Worm",
                    kind="potion",
                    idx1=0,
                    idx2=1,
                ),
                _row(
                    537264128,
                    visits=2,
                    evaluation_sum=1.0,
                    mean_value=0.5,
                    label="duplicate native potion occurrence",
                    kind="potion",
                    idx1=0,
                    idx2=1,
                ),
            ],
            include_potions=True,
        ),
        actions,
        _context(
            action_count=len(actions),
            kinds=["end_turn", "potion", "potion", "potion"],
        ),
    )

    assert report.search_ok
    assert [row.kind for row in report.root_actions] == [
        "end_turn",
        "potion",
        "potion",
        "potion",
    ]
    assert [row.action_identity["occurrence"] for row in report.root_actions] == [
        0,
        0,
        0,
        1,
    ]
    assert (
        select_oracle_root_action(
            report,
            selection_rule="highest_mean",
        ).legal_action_index
        == 2
    )


def test_oracle_root_mapping_allows_reported_unmapped_search_edge_visits() -> None:
    report = build_oracle_search_report(
        _raw_search(
            [
                _row(11, visits=12, evaluation_sum=6.0, mean_value=0.5, label="Strike"),
                _row(22, visits=4, evaluation_sum=1.2, mean_value=0.3, label="Defend"),
            ],
            root_visits=20,
            include_potions=True,
            unmapped_search_edge_count=1,
        ),
        _actions(),
        _context(),
    )

    assert report.search_ok
    assert report.root_visits == 20
    assert report.soft_visit_denominator == 16
    assert report.unmapped_search_edge_count == 1
    telemetry = oracle_search_decision_telemetry(report)
    assert telemetry.root_mapping_failure_count == 0
    assert telemetry.unmapped_search_edge_count == 1


def test_oracle_root_mapping_still_fails_on_unexplained_visit_mismatch() -> None:
    report = build_oracle_search_report(
        _raw_search(
            [
                _row(11, visits=12, evaluation_sum=6.0, mean_value=0.5, label="Strike"),
                _row(22, visits=4, evaluation_sum=1.2, mean_value=0.3, label="Defend"),
            ],
            root_visits=20,
        ),
        _actions(),
        _context(),
    )

    assert not report.search_ok
    assert any(
        "native root visits do not equal summed root-row visits" in problem
        for problem in report.problems
    )


def test_oracle_root_mapping_fails_closed_on_missing_or_unexpected_rows() -> None:
    missing = build_oracle_search_report(
        _raw_search(
            [
                _row(11, visits=5, evaluation_sum=1.0, mean_value=0.2, label="Strike"),
            ]
        ),
        _actions(),
        _context(),
    )
    assert not missing.search_ok
    assert any(
        "omitted current legal actions" in problem for problem in missing.problems
    )

    unexpected = build_oracle_search_report(
        _raw_search(
            [
                _row(11, visits=2, evaluation_sum=0.2, mean_value=0.1, label="Strike"),
                _row(11, visits=3, evaluation_sum=0.6, mean_value=0.2, label="Strike"),
                _row(22, visits=1, evaluation_sum=0.3, mean_value=0.3, label="Defend"),
            ]
        ),
        _actions(),
        _context(),
    )
    assert not unexpected.search_ok
    assert any("unknown legal actions" in problem for problem in unexpected.problems)


class _OracleSearchAdapter:
    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        assert simulations == 10
        return _raw_search(
            [
                _row(11, visits=7, evaluation_sum=2.8, mean_value=0.4, label="Strike"),
                _row(22, visits=3, evaluation_sum=1.5, mean_value=0.5, label="Defend"),
            ]
        )


def test_oracle_controller_publishes_contract_and_telemetry() -> None:
    controller = OracleSearchController(
        simulations=10,
        native_source_identity={"integration_commit": "abc"},
    )

    decision = controller.select_action(
        _OracleSearchAdapter(),
        SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
        _actions(),
        _context(),
        step_index=0,
    )

    assert decision.selected_index == 1
    assert decision.provenance.kind == "oracle_battle_search"
    assert decision.provenance.config["information_regime"] == (
        NATIVE_SEARCH_INFORMATION_REGIME
    )
    assert decision.provenance.config["native_search_patch_identity"] == (
        ORACLE_SEARCH_PATCH_IDENTITY
    )
    assert decision.metadata["oracle_search_decision_count"] == 1
    assert decision.metadata["oracle_search_root_visits"] == 10
    assert decision.metadata["oracle_search_native_simulator_steps"] == 123
    assert decision.metadata["oracle_search_model_calls"] == 0
    telemetry_records = decision.metadata["search_decision_telemetry"]
    assert telemetry_records[0]["schema_id"] == "search-decision-telemetry-v1"
    assert telemetry_records[0]["selection_rule"] == "highest_mean"
    assert telemetry_records[0]["selected_legal_action_index"] == 1


def test_oracle_controller_raises_on_invalid_root_mapping() -> None:
    class MissingRowAdapter:
        def battle_search(self, *args, **kwargs):
            del args, kwargs
            return _raw_search(
                [
                    _row(
                        11,
                        visits=5,
                        evaluation_sum=1.0,
                        mean_value=0.2,
                        label="Strike",
                    ),
                ]
            )

    controller = OracleSearchController(
        simulations=5,
        native_source_identity={"integration_commit": "abc"},
    )
    with pytest.raises(ValueError, match="oracle root mapping failed"):
        controller.select_action(
            MissingRowAdapter(),
            SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
            _actions(),
            _context(),
            step_index=0,
        )
