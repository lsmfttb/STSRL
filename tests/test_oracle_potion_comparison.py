from __future__ import annotations

from io import StringIO

from sts_combat_rl.commands.oracle_potion_comparison import (
    run_oracle_potion_fixed_comparison_from_cohort_path,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
    dump_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_potion_comparison import (
    ORACLE_NO_POTION_LABEL,
    ORACLE_WITH_POTIONS_LABEL,
    dump_oracle_potion_fixed_comparison_jsonl,
    format_oracle_potion_fixed_comparison_report,
    load_oracle_potion_fixed_comparison_jsonl,
    oracle_potion_budget_summary,
    oracle_potion_controller_summaries,
    oracle_potion_delta_summary,
)
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
)


def _battle_snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=(1, 2, 3),
        raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "outcome": "UNDECIDED",
            "ascension": 20,
            "act": 1,
            "floor_num": 16,
            "room_type": "BOSS",
            "encounter_id": "The Guardian",
            "cur_hp": 70,
            "max_hp": 80,
            "gold": 99,
            "blue_key": False,
            "green_key": False,
            "red_key": False,
            "deck": [{"id": "Strike_R", "name": "Strike", "type": "ATTACK"}],
            "relics": [{"id": "Burning Blood", "name": "Burning Blood"}],
            "potions": [
                {"id": "Fire Potion", "name": "Fire Potion"},
                {"id": "Potion Slot", "name": "Potion Slot"},
            ],
        },
    )


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="battle:536870912",
            label="Fire Potion -> The Guardian",
            kind="potion",
            raw={
                "scope": "battle",
                "bits": 536870912,
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
            },
        ),
    ]


def _search_row(
    bits: int,
    *,
    kind: str,
    label: str,
    visits: int,
    mean_value: float | None,
) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": bits,
        "kind": kind,
        "label": label,
        "idx1": 0,
        "idx2": 0,
        "idx3": 0,
        "search_tree_present": visits > 0,
        "search_edge_index": 0 if visits > 0 else None,
        "visits": visits,
        "evaluation_sum": None if mean_value is None else mean_value * visits,
        "mean_value": mean_value,
    }


def _raw_search(*, include_potions: bool, simulations: int) -> dict[str, object]:
    if include_potions:
        rows = [
            _search_row(
                11,
                kind="card",
                label="Strike",
                visits=4,
                mean_value=0.2,
            ),
            _search_row(
                536870912,
                kind="potion",
                label="Fire Potion -> The Guardian",
                visits=12,
                mean_value=0.7,
            ),
        ]
        root_visits = simulations
        unmapped = 1
    else:
        rows = [
            _search_row(
                11,
                kind="card",
                label="Strike",
                visits=simulations,
                mean_value=0.2,
            ),
            _search_row(
                536870912,
                kind="potion",
                label="Fire Potion -> The Guardian",
                visits=0,
                mean_value=None,
            ),
        ]
        root_visits = simulations
        unmapped = 0
    return {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": ORACLE_SEARCH_NATIVE_API,
        "patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": simulations,
        "root_visits": root_visits,
        "include_potions": include_potions,
        "native_simulator_steps": 21,
        "model_calls": None,
        "best_action_value": 0.7 if include_potions else 0.2,
        "min_action_value": 0.2,
        "outcome_player_hp": 50 if include_potions else 0,
        "root_row_count": len(rows),
        "search_edge_count": len(rows) + unmapped,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": unmapped,
        "root_rows": rows,
    }


class _PotionComparisonAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "potion-comparison-adapter"

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        return _battle_snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return _actions()

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        if action.kind == "potion":
            raw = {
                **dict(_battle_snapshot().raw),
                "screen_state": "BOSS_REWARD",
                "battle_active": False,
                "outcome": "PLAYER_VICTORY",
                "completed_battle_outcome": "PLAYER_VICTORY",
                "cur_hp": 50,
                "potions": [
                    {"id": "Potion Slot", "name": "Potion Slot"},
                    {"id": "Potion Slot", "name": "Potion Slot"},
                ],
            }
        else:
            raw = {
                **dict(_battle_snapshot().raw),
                "screen_state": "GAME_OVER",
                "battle_active": False,
                "outcome": "PLAYER_LOSS",
                "completed_battle_outcome": "PLAYER_LOSS",
                "cur_hp": 0,
            }
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(observation=(9, 9), raw=raw),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        return SimulatorCheckpoint(
            checkpoint_id="potion-comparison-cp",
            adapter_id=self.checkpoint_adapter_id,
            payload=None,
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        del checkpoint
        return _battle_snapshot()

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot
        return _raw_search(include_potions=include_potions, simulations=simulations)


def _cohort() -> FixedCohort:
    snapshot = _battle_snapshot()
    return FixedCohort(
        source_pool_format_version=4,
        source_pool_controller_provenance={"kind": "source", "name": "source"},
        selection_config=FixedCohortSelectionConfig(selection_seed=41),
        records=[
            FixedCohortRecord(
                cohort_index=0,
                source_pool_record_index=0,
                source_checkpoint_id="cp-0",
                source_run_id="seed-1-run-0",
                source_seed=1,
                source_battle_index=0,
                structural_stratum=(20, 1, "BOSS", "The Guardian"),
                structural_metadata={
                    "ascension": 20,
                    "act": 1,
                    "floor": 16,
                    "room_type": "BOSS",
                    "encounter_id": "The Guardian",
                    "seed": 1,
                    "source_kind": "natural_run",
                    "distribution_kind": "natural_run",
                    "source_run_id": "seed-1-run-0",
                    "source_battle_index": 0,
                },
                source_controller_provenance={"kind": "source", "name": "source"},
                source_battle_controller_provenance={
                    "kind": "battle",
                    "name": "battle",
                },
                source_non_combat_controller_provenance={
                    "kind": "non_combat",
                    "name": "non_combat",
                },
                action_trace=(),
                snapshot_observation=tuple(snapshot.observation),
                snapshot_raw=dict(snapshot.raw),
                source_distribution_kind="natural_run",
            )
        ],
    )


def test_oracle_potion_comparison_runs_both_action_spaces(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)

    report = run_oracle_potion_fixed_comparison_from_cohort_path(
        adapter_factory=_PotionComparisonAdapter,
        cohort_path=cohort_path,
        simulations=20,
        root_selection_rule="highest_mean",
        max_battle_steps=3,
        run_scale="smoke",
    )

    assert report.evaluation_successful
    assert not report.source_match_problems
    assert report.no_potion_report.losses == 1
    assert report.potion_report.authoritative_wins == 1

    summaries = oracle_potion_controller_summaries(report)
    no_potion_summary = summaries[ORACLE_NO_POTION_LABEL]["search_telemetry_summary"]
    potion_summary = summaries[ORACLE_WITH_POTIONS_LABEL]["search_telemetry_summary"]
    assert no_potion_summary["root_mapping_failure_count"]["total"] == 0.0
    assert potion_summary["root_mapping_failure_count"]["total"] == 0.0
    assert potion_summary["unmapped_search_edge_count"]["total"] == 1.0

    budget = oracle_potion_budget_summary(report)
    assert budget["equal_native_playout_budget"] is True
    assert budget["include_potions"][ORACLE_NO_POTION_LABEL] is False
    assert budget["include_potions"][ORACLE_WITH_POTIONS_LABEL] is True
    assert budget["observed"][ORACLE_WITH_POTIONS_LABEL]["root_mapping_failures"] == 0.0
    assert budget["observed"][ORACLE_WITH_POTIONS_LABEL]["unmapped_search_edges"] == 1.0

    potion_delta = oracle_potion_delta_summary(report)
    assert potion_delta[ORACLE_WITH_POTIONS_LABEL]["removed_potion_slot_items"] == 1

    text = format_oracle_potion_fixed_comparison_report(report)
    assert "Oracle potion fixed-cohort comparison" in text
    assert "source starts matched: yes" in text
    assert "root_mapping_failures=0" in text
    assert "potion-enabled=1.0000" in text
    assert "full_simulator_state_oracle_like engineering comparison only" in text

    buffer = StringIO()
    dump_oracle_potion_fixed_comparison_jsonl(report, buffer)
    assert '"schema_id": "oracle-potion-fixed-comparison-v1"' in buffer.getvalue()
    loaded = load_oracle_potion_fixed_comparison_jsonl(StringIO(buffer.getvalue()))
    assert loaded.evaluation_successful
    assert loaded.no_potion_report.losses == 1
    assert loaded.potion_report.authoritative_wins == 1
