from __future__ import annotations

import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    stable_action_identity_id,
)
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
    NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
    build_root_action_prior_vector,
    native_root_prior_allocation_report_problems,
    run_native_root_prior_allocation_smoke,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.policy import DecisionContext


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(action_id="battle:7", label="Strike A", kind="card"),
        SimulatorAction(action_id="battle:7", label="Strike B", kind="card"),
        SimulatorAction(action_id="battle:9", label="Potion", kind="potion"),
    ]


def _context(eligible: list[int] | None = None) -> DecisionContext:
    actions = _actions()
    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=[],
        legal_action_features=[[] for _ in actions],
        legal_action_kinds=[action.kind for action in actions],
        eligible_action_indices=[0, 1] if eligible is None else eligible,
    )


def _raw_search(
    rows: list[dict[str, object]],
    *,
    native_api: str,
    patch_identity: str,
    simulations: int,
) -> dict[str, object]:
    return {
        "schema_id": "native-battle-search-root-v1",
        "native_api": native_api,
        "patch_identity": patch_identity,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": simulations,
        "root_visits": simulations,
        "include_potions": False,
        "native_simulator_steps": simulations + 1,
        "model_calls": None,
        "best_action_value": 1.0,
        "min_action_value": 0.0,
        "outcome_player_hp": 42,
        "root_row_count": len(rows),
        "search_edge_count": len(rows),
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": rows,
    }


def _row(
    bits: int,
    *,
    visits: int,
    allocated: int | None = None,
    prior: float | None = None,
    label: str = "action",
    kind: str = "card",
) -> dict[str, object]:
    row: dict[str, object] = {
        "scope": "battle",
        "bits": bits,
        "kind": kind,
        "label": label,
        "idx1": 0,
        "idx2": 0,
        "idx3": 0,
        "search_tree_present": True,
        "search_edge_index": 0,
        "visits": visits,
        "evaluation_sum": float(visits),
        "mean_value": 1.0,
    }
    if allocated is not None:
        row["allocated_root_visits"] = allocated
    if prior is not None:
        row["root_prior"] = prior
    return row


def test_root_prior_vector_uses_occurrence_safe_stable_ids() -> None:
    identities = action_identity_dicts_for_actions(_actions())
    second_strike = str(identities[1]["stable_id"])

    vector = build_root_action_prior_vector(
        _actions(),
        _context(),
        {second_strike: 0.75},
    )

    assert vector == [0.0, 0.75, 0.0]


def test_root_prior_vector_fails_closed_on_bad_keys() -> None:
    identities = action_identity_dicts_for_actions(_actions())
    first = str(identities[0]["stable_id"])
    potion = str(identities[2]["stable_id"])
    unknown = stable_action_identity_id(
        action_id="battle:404",
        occurrence=0,
        kind="card",
    )

    with pytest.raises(ValueError, match="duplicate root prior"):
        build_root_action_prior_vector(
            _actions(), _context(), [(first, 1.0), (first, 2.0)]
        )
    with pytest.raises(ValueError, match="unknown root prior"):
        build_root_action_prior_vector(_actions(), _context(), {unknown: 1.0})
    with pytest.raises(ValueError, match="malformed root prior"):
        build_root_action_prior_vector(_actions(), _context(), {"not-json": 1.0})
    with pytest.raises(ValueError, match="illegal root prior"):
        build_root_action_prior_vector(_actions(), _context(), {potion: 1.0})
    with pytest.raises(ValueError, match="finite and non-negative"):
        build_root_action_prior_vector(_actions(), _context(), {first: -1.0})


class _RootPriorSmokeAdapter:
    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        return SimulatorSnapshot(
            observation=[seed or 1],
            raw={
                "screen_state": "BATTLE",
                "battle_active": True,
                "outcome": "UNDECIDED",
                "ascension": 20,
                "act": 1,
                "floor_num": 1,
                "room_type": "MONSTER",
                "encounter_id": "Cultist",
            },
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(action_id="battle:1", label="A", kind="card"),
            SimulatorAction(action_id="battle:2", label="B", kind="card"),
            SimulatorAction(action_id="battle:3", label="C", kind="card"),
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        raise AssertionError(f"already starts in battle: {action}")

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        return _raw_search(
            [
                _row(1, visits=4, label="A"),
                _row(2, visits=3, label="B"),
                _row(3, visits=3, label="C"),
            ],
            native_api="StepSimulator.battle_search.v1",
            patch_identity="sts_lightspeed_battle_search_root_v1",
            simulations=simulations,
        )

    def battle_search_with_root_priors(
        self,
        snapshot: SimulatorSnapshot,
        *,
        actions: list[SimulatorAction],
        context: DecisionContext,
        simulations: int,
        include_potions: bool = False,
        root_action_priors: object = None,
        prior_temperature: float = 1.0,
        min_visits_per_legal_action: int = 1,
        prior_allocation_weight: float = 1.0,
    ) -> dict[str, object]:
        del snapshot, include_potions, prior_temperature, min_visits_per_legal_action
        del prior_allocation_weight
        vector = build_root_action_prior_vector(actions, context, root_action_priors)
        allocations = [4, 3, 3] if vector == [1.0, 1.0, 1.0] else [8, 1, 1]
        rows = [
            _row(
                1,
                visits=allocations[0],
                allocated=allocations[0],
                prior=vector[0],
                label="A",
            ),
            _row(
                2,
                visits=allocations[1],
                allocated=allocations[1],
                prior=vector[1],
                label="B",
            ),
            _row(
                3,
                visits=allocations[2],
                allocated=allocations[2],
                prior=vector[2],
                label="C",
            ),
        ]
        raw = _raw_search(
            rows,
            native_api=NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
            patch_identity=NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
            simulations=simulations,
        )
        raw["allocation_metadata"] = {
            "schema_id": "native-root-prior-allocation-metadata-v1",
            "allocation_strategy": "root_prior_mixture_v1",
            "prior_temperature": 1.0,
            "min_visits_per_legal_action": 1,
            "prior_allocation_weight": 1.0,
            "legal_action_prior_count": len(actions),
            "eligible_root_action_count": len(actions),
            "allocated_root_visits": simulations,
            "allocation_plan": [],
        }
        return raw


def test_native_root_prior_allocation_smoke_report_validates_schema_and_claims() -> (
    None
):
    report = run_native_root_prior_allocation_smoke(
        _RootPriorSmokeAdapter(),
        seed=1,
        max_steps=0,
        simulations=10,
        action_space=ActionSpaceConfig.include_all(),
        include_potions=False,
        prior_temperature=1.0,
        min_visits_per_legal_action=1,
        prior_allocation_weight=1.0,
        native_source_identity={"integration_commit": "abc"},
    )

    assert report.passed
    payload = report.to_dict()
    assert native_root_prior_allocation_report_problems(payload) == []
    assert payload["configuration"]["model_calls"] == 0
    assert payload["allocation_checks"]["one_hot_preferred_strictly_more"] is True
    assert payload["allocation_checks"]["uniform_allocations"] == [4, 3, 3]
    assert payload["allocation_checks"]["one_hot_allocations"] == [8, 1, 1]
    assert "controller-promotion" in payload["claim_boundary"]
