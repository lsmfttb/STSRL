from __future__ import annotations

from dataclasses import replace
from io import StringIO

from sts_combat_rl.commands.oracle_search import (
    format_oracle_fixed_evaluation_report,
    run_oracle_fixed_evaluation_from_cohort_path,
)
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
    dump_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import (
    collect_oracle_teacher_dataset_from_pool,
    dump_oracle_teacher_dataset_jsonl,
    load_oracle_teacher_dataset_jsonl,
    oracle_teacher_dataset_problems,
)


class _TeacherAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "teacher-adapter"

    def __init__(self) -> None:
        self._terminal = False

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        self._terminal = False
        return _battle_snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return _actions()

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        self._terminal = True
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=(9, 9),
                raw={
                    "screen_state": "BOSS_REWARD",
                    "battle_active": False,
                    "outcome": "PLAYER_VICTORY",
                    "completed_battle_outcome": "PLAYER_VICTORY",
                    "cur_hp": 68,
                    "max_hp": 80,
                    "floor_num": 5,
                },
            ),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        return SimulatorCheckpoint(
            checkpoint_id="teacher-cp",
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
        del snapshot, include_potions
        return _raw_search(simulations)


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


def _battle_snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=(1, 2, 3),
        raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "outcome": "UNDECIDED",
            "ascension": 20,
            "act": 1,
            "floor_num": 5,
            "room_type": "MONSTER",
            "encounter_id": "Cultist",
            "cur_hp": 70,
            "max_hp": 80,
        },
    )


def _raw_search(simulations: int) -> dict[str, object]:
    return {
        "schema_id": "native-battle-search-root-v1",
        "native_api": "StepSimulator.battle_search.v1",
        "patch_identity": "sts_lightspeed_battle_search_root_v1",
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": simulations,
        "root_visits": simulations,
        "include_potions": False,
        "native_simulator_steps": 17,
        "model_calls": None,
        "best_action_value": 0.6,
        "min_action_value": 0.1,
        "outcome_player_hp": 68,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": [
            {
                "scope": "battle",
                "bits": 11,
                "kind": "card",
                "label": "Strike",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 0,
                "visits": simulations - 1,
                "evaluation_sum": 0.2,
                "mean_value": 0.2,
            },
            {
                "scope": "battle",
                "bits": 22,
                "kind": "card",
                "label": "Defend",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 1,
                "visits": 1,
                "evaluation_sum": 0.6,
                "mean_value": 0.6,
            },
        ],
    }


def _provenance(name: str) -> dict[str, object]:
    return ControllerProvenance(kind="test", name=name, config={}).to_dict()


def _pool() -> NaturalBattleStartPool:
    snapshot = _battle_snapshot()
    return NaturalBattleStartPool(
        source_run_count=1,
        terminal_run_count=0,
        truncated_run_count=1,
        source_controller_provenance=_provenance("source"),
        records=[
            BattleStartCheckpointRecord(
                record_index=0,
                source_checkpoint_id="cp-0",
                source_run_id="seed-1-run-0",
                source_seed=1,
                source_battle_index=0,
                structural_metadata={
                    "ascension": 20,
                    "act": 1,
                    "floor": 5,
                    "room_type": "MONSTER",
                    "encounter_id": "Cultist",
                    "seed": 1,
                    "source_kind": "natural_run",
                    "distribution_kind": "natural_run",
                    "source_run_id": "seed-1-run-0",
                    "source_battle_index": 0,
                },
                source_controller_provenance=_provenance("source"),
                source_battle_controller_provenance=_provenance("battle"),
                source_non_combat_controller_provenance=_provenance("non-combat"),
                action_trace=(),
                snapshot_observation=tuple(snapshot.observation),
                snapshot_raw=dict(snapshot.raw),
            )
        ],
    )


def _cohort() -> FixedCohort:
    record = _pool().records[0]
    return FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance=_provenance("source"),
        selection_config=FixedCohortSelectionConfig(selection_seed=7),
        records=[
            FixedCohortRecord(
                cohort_index=0,
                source_pool_record_index=record.record_index,
                source_checkpoint_id=record.source_checkpoint_id,
                source_run_id=record.source_run_id,
                source_seed=record.source_seed,
                source_battle_index=record.source_battle_index,
                structural_stratum=(20, 1, "MONSTER", "Cultist"),
                structural_metadata=dict(record.structural_metadata),
                source_controller_provenance=record.source_controller_provenance,
                source_battle_controller_provenance=(
                    record.source_battle_controller_provenance
                ),
                source_non_combat_controller_provenance=(
                    record.source_non_combat_controller_provenance
                ),
                action_trace=record.action_trace,
                snapshot_observation=record.snapshot_observation,
                snapshot_raw=dict(record.snapshot_raw),
                source_distribution_kind=record.distribution_kind,
            )
        ],
    )


def test_oracle_teacher_dataset_preserves_teacher_targets_and_round_trips() -> None:
    controller = OracleSearchController(
        simulations=5,
        native_source_identity={"integration_commit": "abc"},
    )
    dataset = collect_oracle_teacher_dataset_from_pool(
        _TeacherAdapter,
        _pool(),
        controller,
    )

    assert not dataset.problems
    assert len(dataset.records) == 1
    row = dataset.records[0]
    assert row.information_regime == NATIVE_SEARCH_INFORMATION_REGIME
    assert row.sampling_component == "natural"
    assert row.behavior_action is None
    assert row.teacher_action["legal_action_index"] == 1
    assert row.soft_visit_target["target_kind"] == "root_visit_distribution"
    assert row.native_search_report["native_simulator_steps"] == 17

    stream = StringIO()
    dump_oracle_teacher_dataset_jsonl(dataset, stream)
    loaded = load_oracle_teacher_dataset_jsonl(StringIO(stream.getvalue()))

    assert loaded.records[0].teacher_action == row.teacher_action
    assert loaded.records[0].soft_visit_target == row.soft_visit_target


def test_oracle_teacher_dataset_rejects_behavior_teacher_alias() -> None:
    controller = OracleSearchController(
        simulations=5,
        native_source_identity={"integration_commit": "abc"},
    )
    dataset = collect_oracle_teacher_dataset_from_pool(
        _TeacherAdapter,
        _pool(),
        controller,
    )
    aliased_row = replace(
        dataset.records[0],
        behavior_action=dict(dataset.records[0].teacher_action),
    )
    bad_dataset = replace(dataset, records=[aliased_row])

    assert any(
        "behavior action must not alias teacher action" in problem
        for problem in oracle_teacher_dataset_problems(bad_dataset)
    )


def test_oracle_fixed_evaluation_uses_supplied_cohort_unchanged(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)
    controller = OracleSearchController(
        simulations=5,
        root_selection_rule="highest_mean",
        native_source_identity={"integration_commit": "abc"},
    )

    report = run_oracle_fixed_evaluation_from_cohort_path(
        adapter_factory=_TeacherAdapter,
        cohort_path=cohort_path,
        controller=controller,
        action_space=controller.action_space,
        max_battle_steps=3,
    )

    assert report.evaluation_successful
    assert report.total_battles == 1
    assert report.authoritative_wins == 1
    assert report.selection_config["selection_seed"] == 7
    assert report.per_stratum_source_counts == {"20/1/MONSTER/Cultist": 1}
    telemetry = report.battle_results[0].controller_compute_telemetry
    assert telemetry is not None
    assert telemetry["oracle_search_decision_count"] == 1.0
    assert telemetry["oracle_search_native_simulator_steps"] == 17.0

    text = format_oracle_fixed_evaluation_report(report)
    assert "sts_lightspeed source identity" in text
    assert "Fixed battle evaluation report" in text
