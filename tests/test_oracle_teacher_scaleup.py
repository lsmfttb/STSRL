from __future__ import annotations

from dataclasses import replace
from io import StringIO
import hashlib
import json
import random
from pathlib import Path

import pytest

from sts_combat_rl.commands.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME,
    run_assisted_oracle_teacher_scaleup_from_paths,
    run_oracle_teacher_scaleup_from_paths,
)
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    ASSIST_LEVEL_0,
    AssistedSourcePoolArtifact,
    assistance_schedule_by_level,
    dump_assisted_source_pool_jsonl,
)
from sts_combat_rl.sim.a20_battle_start_coverage import (
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
)
from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    dump_natural_battle_start_pool_jsonl,
    record_to_manifest,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import OracleTeacherDataset, OracleTeacherRow
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_T032_T039_NARROW,
    T032_T039_ACT1_BOSS_SOURCE_COUNT,
    T032_T039_ACT2_SOURCE_COUNT,
    T032_T039_NARROW_SELECTION_CONTRACT_ID,
    build_t032_t039_narrow_source_selection_plan,
    build_assisted_oracle_teacher_source_selection_plan,
    build_oracle_teacher_scaleup_manifest,
    build_oracle_teacher_source_selection_plan,
    dump_oracle_teacher_scaleup_manifest_json,
    validate_oracle_teacher_scaleup_budgets,
)


class _ScaleupAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "scaleup-adapter"

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        index = 0 if seed is None else seed - 100
        return _snapshot(index)

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return _actions()

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(
                observation=(9, 9),
                raw={
                    "screen_state": "REWARDS",
                    "battle_active": False,
                    "outcome": "PLAYER_VICTORY",
                    "completed_battle_outcome": "PLAYER_VICTORY",
                    "cur_hp": 68,
                    "max_hp": 80,
                    "floor_num": 5,
                },
            ),
            terminal=False,
            info={},
        )

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        return _raw_search(simulations)


def test_source_selection_limit_is_seeded_and_deterministic() -> None:
    pool = _pool(record_count=5)

    first = build_oracle_teacher_source_selection_plan(
        pool,
        selection_seed=11,
        source_limit=3,
    )
    second = build_oracle_teacher_source_selection_plan(
        pool,
        selection_seed=11,
        source_limit=3,
    )

    assert first.to_dict() == second.to_dict()
    assert first.passed
    assert first.selected_source_count == 3
    assert first.selection_method == "seeded_uniform_source_sample"
    assert first.structural_coverage["ascensions"] == {"20": 3}
    assert set(first.selected_sources[0]) >= {
        "ascension",
        "act",
        "room_type",
        "encounter_id",
        "source_run_id",
        "source_checkpoint_id",
    }


def test_source_selection_fails_closed_for_bad_source_identity() -> None:
    bad = replace(
        _record(0),
        source_checkpoint_id="",
        structural_metadata={**_metadata(0), "ascension": 0},
    )
    legacy = replace(
        _record(1),
        checkpoint_information_regime="unknown",
    )
    pool = replace(_pool(record_count=1), records=[bad, legacy])

    plan = build_oracle_teacher_source_selection_plan(
        pool,
        selection_seed=1,
    )

    assert not plan.passed
    assert any(
        "source_checkpoint_id is missing" in problem for problem in plan.problems
    )
    assert any("source is not A20" in problem for problem in plan.problems)
    assert any("information regime" in problem for problem in plan.problems)


def test_assisted_source_selection_preserves_assistance_groups() -> None:
    artifact = _assisted_artifact(record_count=3)

    plan = build_assisted_oracle_teacher_source_selection_plan(
        artifact.pool,
        selection_seed=11,
        source_limit=2,
    )

    assert plan.passed
    assert plan.selection_method == "seeded_uniform_assisted_run_source_sample"
    assert plan.structural_coverage["distribution_kinds"] == {"assisted_run": 2}
    assert plan.structural_coverage["assistance_levels"] == {ASSIST_LEVEL_0: 2}
    assert all(
        source["distribution_kind"] == ASSISTED_RUN_DISTRIBUTION_KIND
        for source in plan.selected_sources
    )


def test_t032_t039_narrow_selection_keeps_rare_sources_and_samples_background() -> None:
    pool = _custom_pool(
        [
            *[
                _custom_record(
                    index,
                    act=1,
                    room_type="BOSS",
                    encounter_id=f"BOSS_{index:02d}",
                )
                for index in range(T032_T039_ACT1_BOSS_SOURCE_COUNT)
            ],
            *[
                _custom_record(
                    100 + index,
                    act=2,
                    room_type="ELITE" if index == 1 else "MONSTER",
                    encounter_id=f"ACT2_{index}",
                )
                for index in range(T032_T039_ACT2_SOURCE_COUNT)
            ],
            *[
                _custom_record(
                    200 + index,
                    act=1,
                    room_type="MONSTER",
                    encounter_id=f"BACKGROUND_{index}",
                )
                for index in range(6)
            ],
        ]
    )

    plan = build_t032_t039_narrow_source_selection_plan(
        pool,
        selection_seed=32039,
        background_source_count=3,
    )
    repeated = build_t032_t039_narrow_source_selection_plan(
        pool,
        selection_seed=32039,
        background_source_count=3,
    )

    assert plan.to_dict() == repeated.to_dict()
    assert plan.passed
    assert (
        plan.selection_method
        == ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_T032_T039_NARROW
    )
    assert plan.selection_metadata["selection_contract_id"] == (
        T032_T039_NARROW_SELECTION_CONTRACT_ID
    )
    assert plan.selection_metadata["groups"] == {
        "act1_boss": {
            "available": T032_T039_ACT1_BOSS_SOURCE_COUNT,
            "selected": T032_T039_ACT1_BOSS_SOURCE_COUNT,
            "required": T032_T039_ACT1_BOSS_SOURCE_COUNT,
            "required_all_available": True,
        },
        "act2": {
            "available": T032_T039_ACT2_SOURCE_COUNT,
            "selected": T032_T039_ACT2_SOURCE_COUNT,
            "required": T032_T039_ACT2_SOURCE_COUNT,
            "required_all_available": True,
        },
        "act1_non_boss_background": {
            "available": 6,
            "selected": 3,
            "required": 3,
            "selection_seed": 32039,
        },
    }
    assert [
        source["selection_group"]
        for source in plan.selected_sources[
            : T032_T039_ACT1_BOSS_SOURCE_COUNT + T032_T039_ACT2_SOURCE_COUNT
        ]
    ] == [
        *(["act1_boss"] * T032_T039_ACT1_BOSS_SOURCE_COUNT),
        *(["act2"] * T032_T039_ACT2_SOURCE_COUNT),
    ]

    background_ids = [
        source["source_checkpoint_id"]
        for source in plan.selected_sources
        if source["selection_group"] == "act1_non_boss_background"
    ]
    expected_background_indices = sorted(random.Random(32039).sample(range(6), 3))
    assert background_ids == [
        f"checkpoint-{200 + index}" for index in expected_background_indices
    ]


def test_t032_t039_narrow_selection_fails_closed_for_missing_act1_boss() -> None:
    pool = _custom_pool(
        [
            *[
                _custom_record(
                    index,
                    act=1,
                    room_type="BOSS",
                    encounter_id=f"BOSS_{index:02d}",
                )
                for index in range(T032_T039_ACT1_BOSS_SOURCE_COUNT - 1)
            ],
            *[
                _custom_record(
                    100 + index,
                    act=2,
                    room_type="MONSTER",
                    encounter_id=f"ACT2_{index}",
                )
                for index in range(T032_T039_ACT2_SOURCE_COUNT)
            ],
            *[
                _custom_record(
                    200 + index,
                    act=1,
                    room_type="MONSTER",
                    encounter_id=f"BACKGROUND_{index}",
                )
                for index in range(2)
            ],
        ]
    )

    plan = build_t032_t039_narrow_source_selection_plan(
        pool,
        selection_seed=32039,
        background_source_count=2,
    )

    assert not plan.passed
    assert any("31 Act 1 Boss sources" in problem for problem in plan.problems)
    assert plan.selection_metadata["groups"]["act1_boss"] == {
        "available": T032_T039_ACT1_BOSS_SOURCE_COUNT - 1,
        "selected": T032_T039_ACT1_BOSS_SOURCE_COUNT - 1,
        "required": T032_T039_ACT1_BOSS_SOURCE_COUNT,
        "required_all_available": True,
    }


def test_t032_t039_narrow_selection_fails_closed_for_missing_act2() -> None:
    pool = _custom_pool(
        [
            *[
                _custom_record(
                    index,
                    act=1,
                    room_type="BOSS",
                    encounter_id=f"BOSS_{index:02d}",
                )
                for index in range(T032_T039_ACT1_BOSS_SOURCE_COUNT)
            ],
            *[
                _custom_record(
                    100 + index,
                    act=2,
                    room_type="MONSTER",
                    encounter_id=f"ACT2_{index}",
                )
                for index in range(T032_T039_ACT2_SOURCE_COUNT - 1)
            ],
            *[
                _custom_record(
                    200 + index,
                    act=1,
                    room_type="MONSTER",
                    encounter_id=f"BACKGROUND_{index}",
                )
                for index in range(2)
            ],
        ]
    )

    plan = build_t032_t039_narrow_source_selection_plan(
        pool,
        selection_seed=32039,
        background_source_count=2,
    )

    assert not plan.passed
    assert any("3 Act 2 sources" in problem for problem in plan.problems)
    assert plan.selection_metadata["groups"]["act2"] == {
        "available": T032_T039_ACT2_SOURCE_COUNT - 1,
        "selected": T032_T039_ACT2_SOURCE_COUNT - 1,
        "required": T032_T039_ACT2_SOURCE_COUNT,
        "required_all_available": True,
    }


def test_t032_t039_narrow_selection_fails_closed_without_background() -> None:
    pool = _custom_pool(
        [
            _custom_record(0, act=1, room_type="BOSS", encounter_id="BOSS_A"),
            _custom_record(1, act=2, room_type="MONSTER", encounter_id="ACT2_A"),
            _custom_record(2, act=1, room_type="MONSTER", encounter_id="ONLY_BG"),
        ]
    )

    plan = build_t032_t039_narrow_source_selection_plan(
        pool,
        selection_seed=32039,
        background_source_count=2,
    )

    assert not plan.passed
    assert any("Act 1 non-Boss background" in problem for problem in plan.problems)
    assert (
        plan.selection_metadata["groups"]["act1_non_boss_background"]["available"] == 1
    )


def test_scaleup_budget_validation_rejects_duplicates_and_nonpositive() -> None:
    assert validate_oracle_teacher_scaleup_budgets([20, 50]) == (20, 50)
    with pytest.raises(ValueError, match="positive"):
        validate_oracle_teacher_scaleup_budgets([20, 0])
    with pytest.raises(ValueError, match="unique"):
        validate_oracle_teacher_scaleup_budgets([20, 20])


def test_manifest_summarizes_cross_budget_action_and_soft_target_stability() -> None:
    pool = _pool(record_count=2)
    plan = build_oracle_teacher_source_selection_plan(pool, selection_seed=1)
    budget_20 = _dataset(
        budget=20,
        records=[
            _row(0, budget=20, selected_action=1, probabilities=[0.8, 0.2]),
            _row(1, budget=20, selected_action=0, probabilities=[0.5, 0.5]),
        ],
    )
    budget_50 = _dataset(
        budget=50,
        records=[
            _row(0, budget=50, selected_action=1, probabilities=[0.6, 0.4]),
            _row(1, budget=50, selected_action=1, probabilities=[0.25, 0.75]),
        ],
    )

    manifest = build_oracle_teacher_scaleup_manifest(
        input_artifacts={"natural_pool": {"sha256": "pool"}},
        source_selection=plan,
        requested_budgets=[20, 50],
        root_selection_rule="highest_mean",
        datasets_by_budget={20: budget_20, 50: budget_50},
        reports_by_budget={},
        generated_artifacts=[],
        native_source_identity=lightspeed_source_identity_dict(),
    )

    assert not manifest.command_passed
    assert manifest.teacher_action_stability["complete_source_count"] == 2
    assert manifest.teacher_action_stability["all_budget_agreement_count"] == 1
    assert manifest.teacher_action_stability["pairwise_agreement_count"] == 1
    assert manifest.soft_target_stability["available_source_count"] == 2
    assert manifest.soft_target_stability["mean_pairwise_total_variation"] == 0.225

    first = StringIO()
    second = StringIO()
    dump_oracle_teacher_scaleup_manifest_json(manifest, first)
    dump_oracle_teacher_scaleup_manifest_json(manifest, second)
    assert first.getvalue() == second.getvalue()
    assert '"schema_id": "oracle-teacher-scaleup-manifest-v1"' in first.getvalue()


def test_command_workflow_writes_teacher_reports_and_manifest(tmp_path: Path) -> None:
    pool = _pool(record_count=1)
    pool_path = tmp_path / "pool.jsonl"
    coverage_path = tmp_path / "coverage.json"
    output_dir = tmp_path / "scaleup"
    _write_pool(pool_path, pool)
    _write_coverage(coverage_path, pool_path, pool)

    manifest = run_oracle_teacher_scaleup_from_paths(
        adapter_factory=_ScaleupAdapter,
        pool_path=pool_path,
        output_dir=output_dir,
        budgets=[20, 50],
        source_limit=1,
        selection_seed=1,
        coverage_report_path=coverage_path,
        root_selection_rule="highest_mean",
    )

    assert manifest.command_passed
    assert (output_dir / "oracle-teacher-budget-20.jsonl").exists()
    assert (output_dir / "oracle-teacher-report-budget-20.json").exists()
    assert (output_dir / ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME).exists()
    assert manifest.source_selection.selected_checkpoint_ids == ("checkpoint-0",)
    assert [artifact["budget"] for artifact in manifest.generated_artifacts] == [
        20,
        50,
    ]
    assert manifest.teacher_action_stability["all_budget_agreement_count"] == 1
    assert any(
        "broad-training gate remains closed" in warning for warning in manifest.warnings
    )


def test_command_workflow_uses_t032_t039_narrow_selection(tmp_path: Path) -> None:
    pool = _custom_pool(
        [
            *[
                _custom_record(
                    index,
                    act=1,
                    room_type="BOSS",
                    encounter_id=f"BOSS_{index:02d}",
                )
                for index in range(T032_T039_ACT1_BOSS_SOURCE_COUNT)
            ],
            *[
                _custom_record(
                    T032_T039_ACT1_BOSS_SOURCE_COUNT + index,
                    act=2,
                    room_type="MONSTER",
                    encounter_id=f"ACT2_{index}",
                )
                for index in range(T032_T039_ACT2_SOURCE_COUNT)
            ],
            _custom_record(34, act=1, room_type="MONSTER", encounter_id="BG_A"),
            _custom_record(35, act=1, room_type="ELITE", encounter_id="BG_B"),
            _custom_record(36, act=1, room_type="EVENT", encounter_id="BG_C"),
        ]
    )
    pool_path = tmp_path / "pool.jsonl"
    output_dir = tmp_path / "scaleup"
    _write_pool(pool_path, pool)

    manifest = run_oracle_teacher_scaleup_from_paths(
        adapter_factory=_ScaleupAdapter,
        pool_path=pool_path,
        output_dir=output_dir,
        budgets=[20],
        source_limit=None,
        selection_seed=32039,
        source_selection_mode=ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_T032_T039_NARROW,
        background_source_count=2,
    )

    assert manifest.command_passed
    assert manifest.source_selection.selected_source_count == 36
    assert manifest.source_selection.selection_metadata["groups"]["act1_boss"] == {
        "available": T032_T039_ACT1_BOSS_SOURCE_COUNT,
        "selected": T032_T039_ACT1_BOSS_SOURCE_COUNT,
        "required": T032_T039_ACT1_BOSS_SOURCE_COUNT,
        "required_all_available": True,
    }
    assert manifest.source_selection.selection_metadata["groups"]["act2"] == {
        "available": T032_T039_ACT2_SOURCE_COUNT,
        "selected": T032_T039_ACT2_SOURCE_COUNT,
        "required": T032_T039_ACT2_SOURCE_COUNT,
        "required_all_available": True,
    }
    assert (
        manifest.source_selection.selection_metadata["groups"][
            "act1_non_boss_background"
        ]["selected"]
        == 2
    )
    assert (
        json.loads(
            (output_dir / ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME).read_text(
                encoding="utf-8"
            )
        )["source_selection"]["selection_metadata"]["selection_contract_id"]
        == T032_T039_NARROW_SELECTION_CONTRACT_ID
    )


def test_command_workflow_loads_migrated_v3_pool(tmp_path: Path) -> None:
    pool_path = tmp_path / "pool-v3.jsonl"
    output_dir = tmp_path / "scaleup"
    _write_v3_pool(pool_path)

    manifest = run_oracle_teacher_scaleup_from_paths(
        adapter_factory=_ScaleupAdapter,
        pool_path=pool_path,
        output_dir=output_dir,
        budgets=[20],
        source_limit=None,
        selection_seed=1,
    )

    assert manifest.command_passed
    assert manifest.input_artifacts["natural_pool"]["format_version"] == (
        BATTLE_START_POOL_FORMAT_VERSION
    )
    assert manifest.source_selection.selected_checkpoint_ids == ("checkpoint-0",)


def test_assisted_command_workflow_writes_teacher_reports_and_manifest(
    tmp_path: Path,
) -> None:
    artifact = _assisted_artifact(record_count=1)
    pool_path = tmp_path / "assisted-pool.jsonl"
    coverage_path = tmp_path / "assisted-coverage.json"
    output_dir = tmp_path / "assisted-scaleup"
    _write_assisted_pool(pool_path, artifact)
    _write_coverage(coverage_path, pool_path, artifact.pool)

    manifest = run_assisted_oracle_teacher_scaleup_from_paths(
        adapter_factory=_ScaleupAdapter,
        pool_path=pool_path,
        output_dir=output_dir,
        budgets=[20],
        source_limit=1,
        selection_seed=1,
        coverage_report_path=coverage_path,
        root_selection_rule="highest_mean",
    )
    manifest_json = json.loads(
        (output_dir / ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )

    assert manifest.command_passed
    assert "assisted_pool" in manifest.input_artifacts
    assert manifest.input_artifacts["assisted_pool"]["assistance_level"] == (
        ASSIST_LEVEL_0
    )
    assert manifest.source_selection.selection_method == (
        "all_assisted_run_sources_sorted_limit_exceeds_count"
    )
    assert manifest_json["input_artifacts"]["assisted_pool"]["distribution_kind"] == (
        "assisted_run"
    )
    assert (output_dir / "oracle-teacher-budget-20.jsonl").exists()
    assert (output_dir / "oracle-teacher-report-budget-20.json").exists()


def test_command_workflow_rejects_t021_source_pool_mismatch(
    tmp_path: Path,
) -> None:
    pool = _pool(record_count=1)
    pool_path = tmp_path / "pool.jsonl"
    coverage_path = tmp_path / "coverage.json"
    _write_pool(pool_path, pool)
    _write_coverage(coverage_path, pool_path, pool)
    raw = json.loads(coverage_path.read_text(encoding="utf-8"))
    raw["input_artifacts"]["natural_pool"]["sha256"] = "mismatch"
    coverage_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256 does not match"):
        run_oracle_teacher_scaleup_from_paths(
            adapter_factory=_ScaleupAdapter,
            pool_path=pool_path,
            output_dir=tmp_path / "scaleup",
            budgets=[20],
            source_limit=None,
            selection_seed=1,
            coverage_report_path=coverage_path,
        )


def _dataset(
    *,
    budget: int,
    records: list[OracleTeacherRow],
) -> OracleTeacherDataset:
    controller = OracleSearchController(
        simulations=budget,
        native_source_identity=lightspeed_source_identity_dict(),
    )
    return OracleTeacherDataset(
        native_source_identity=lightspeed_source_identity_dict(),
        controller_provenance=controller.provenance.to_dict(),
        action_space_config=controller.action_space.to_dict(),
        source_pool_format_version=BATTLE_START_POOL_FORMAT_VERSION,
        source_pool_controller_provenance=_provenance("routed"),
        records=records,
    )


def _row(
    index: int,
    *,
    budget: int,
    selected_action: int,
    probabilities: list[float],
) -> OracleTeacherRow:
    action_identities = [
        {"action_id": "battle:11", "kind": "card", "label": "Strike", "occurrence": 0},
        {"action_id": "battle:22", "kind": "card", "label": "Defend", "occurrence": 0},
    ]
    return OracleTeacherRow(
        row_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_pool_record_index=index,
        source_run_id=f"run-{index}",
        source_seed=100 + index,
        source_battle_index=index,
        source_distribution_kind=NATURAL_DISTRIBUTION_KIND,
        sampling_component="natural",
        restoration_method="seed_action_trace",
        structural_metadata=_metadata(index),
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
        legal_action_identities=action_identities,
        legal_action_kinds=["card", "card"],
        eligible_action_indices=[0, 1],
        root_statistics=[
            {"legal_action_index": 0, "visits": budget - 1, "mean_value": 0.2},
            {"legal_action_index": 1, "visits": 1, "mean_value": 0.6},
        ],
        teacher_action={
            "selection_rule": "highest_mean",
            "legal_action_index": selected_action,
            "action_identity": action_identities[selected_action],
            "visits": budget,
            "mean_value": 0.6,
            "score": 0.6,
        },
        soft_visit_target={
            "target_kind": "root_visit_distribution",
            "probabilities": probabilities,
            "denominator": budget,
        },
        behavior_action=None,
        controller_provenance=OracleSearchController(
            simulations=budget,
            native_source_identity=lightspeed_source_identity_dict(),
        ).provenance.to_dict(),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        public_context_status="legacy_unavailable",
        public_run_context={},
        native_search_report={
            "schema_id": "native-battle-search-root-v1",
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "simulations_requested": budget,
            "root_visits": budget,
            "native_simulator_steps": budget + 3,
            "model_calls": None,
            "wall_clock_time_s": 0.0,
            "unsearched_legal_action_count": 0,
            "unmapped_search_edge_count": 0,
            "problems": [],
        },
    )


def _pool(*, record_count: int) -> NaturalBattleStartPool:
    return NaturalBattleStartPool(
        source_run_count=record_count,
        terminal_run_count=record_count,
        truncated_run_count=0,
        source_controller_provenance=_provenance("routed"),
        records=[_record(index) for index in range(record_count)],
    )


def _custom_pool(records: list[BattleStartCheckpointRecord]) -> NaturalBattleStartPool:
    return NaturalBattleStartPool(
        source_run_count=len(records),
        terminal_run_count=len(records),
        truncated_run_count=0,
        source_controller_provenance=_provenance("routed"),
        records=records,
    )


def _assisted_artifact(*, record_count: int) -> AssistedSourcePoolArtifact:
    schedule = assistance_schedule_by_level(ASSIST_LEVEL_0)
    records = [_assisted_record(index) for index in range(record_count)]
    decisions = tuple(record.assistance_history[-1] for record in records)
    return AssistedSourcePoolArtifact(
        pool=NaturalBattleStartPool(
            source_run_count=record_count,
            terminal_run_count=record_count,
            truncated_run_count=0,
            source_controller_provenance=_provenance("routed"),
            records=records,
        ),
        assistance_level=ASSIST_LEVEL_0,
        assistance_schedule=schedule,
        policy_seed=1,
        assistance_decisions=decisions,
    )


def _record(index: int) -> BattleStartCheckpointRecord:
    snapshot = _snapshot(index)
    return BattleStartCheckpointRecord(
        record_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_run_id=f"run-{index}",
        source_seed=100 + index,
        source_battle_index=index,
        structural_metadata=_metadata(index),
        source_controller_provenance=_provenance("routed"),
        source_battle_controller_provenance=_provenance("battle"),
        source_non_combat_controller_provenance=_provenance("non-combat"),
        action_trace=(),
        snapshot_observation=tuple(snapshot.observation),
        snapshot_raw=dict(snapshot.raw),
        distribution_kind=NATURAL_DISTRIBUTION_KIND,
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
        public_context_status="legacy_unavailable",
        public_run_context={},
    )


def _assisted_record(index: int) -> BattleStartCheckpointRecord:
    record = _record(index)
    schedule = assistance_schedule_by_level(ASSIST_LEVEL_0)
    decision = _assistance_decision(record, schedule=schedule)
    metadata = {
        **record.structural_metadata,
        "source_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
        "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
        "assistance_level": schedule.level,
        "assistance_version": schedule.version,
        "distribution_tag": schedule.distribution_tag,
        "source_checkpoint_id": record.source_checkpoint_id,
    }
    return replace(
        record,
        structural_metadata=metadata,
        distribution_kind=ASSISTED_RUN_DISTRIBUTION_KIND,
        assistance_history=(decision,),
    )


def _assistance_decision(
    record: BattleStartCheckpointRecord,
    *,
    schedule: object,
) -> dict[str, object]:
    resources = {
        "current_hp": record.snapshot_raw.get("cur_hp"),
        "max_hp": record.snapshot_raw.get("max_hp"),
        "potion_count": 0,
        "potion_capacity": 0,
    }
    return {
        "assistance_version": schedule.version,
        "assistance_level": schedule.level,
        "policy_seed": 1,
        "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
        "information_regime": CHECKPOINT_INFORMATION_REGIME,
        "source_run_id": record.source_run_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_record_index": record.record_index,
        "before_resources": resources,
        "requested_change": {
            "reason": "assist_0_no_assistance",
            "hp_bonus": 0,
            "add_random_potion": False,
            "native_rebuild_requested": False,
        },
        "actual_change": {
            "applied": False,
            "reason": "native_rebuild_no_visible_change",
            "current_hp_delta": 0,
            "potion_count_delta": 0,
            "native_rebuild_called": False,
        },
        "after_resources": resources,
        "native_support_status": "supported",
    }


def _custom_record(
    index: int,
    *,
    act: int,
    room_type: str,
    encounter_id: str,
) -> BattleStartCheckpointRecord:
    return replace(
        _record(index),
        structural_metadata={
            **_metadata(index),
            "act": act,
            "room_type": room_type,
            "encounter_id": encounter_id,
        },
    )


def _metadata(index: int) -> dict[str, object]:
    return {
        "ascension": 20,
        "act": 1 + index % 2,
        "floor": index + 1,
        "room_type": "MONSTER",
        "encounter_id": f"ENCOUNTER_{index}",
        "seed": 100 + index,
        "source_kind": NATURAL_DISTRIBUTION_KIND,
        "distribution_kind": NATURAL_DISTRIBUTION_KIND,
        "source_run_id": f"run-{index}",
        "source_battle_index": index,
    }


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


def _snapshot(index: int) -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=(100 + index, index),
        raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "outcome": "UNDECIDED",
            "ascension": 20,
            "act": 1 + index % 2,
            "floor_num": index + 1,
            "room_type": "MONSTER",
            "encounter_id": f"ENCOUNTER_{index}",
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
        "native_simulator_steps": simulations + 3,
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


def _write_pool(path: Path, pool: NaturalBattleStartPool) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)


def _write_assisted_pool(path: Path, artifact: AssistedSourcePoolArtifact) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_pool_jsonl(artifact, stream)


def _write_v3_pool(path: Path) -> None:
    record = record_to_manifest(_record(0))
    record.pop("completed_battle_resource_outcome_status")
    record.pop("completed_battle_resource_outcome")
    rows = [
        {
            "type": "metadata",
            "metadata": {
                "format_version": 3,
                "source_run_count": 1,
                "terminal_run_count": 1,
                "truncated_run_count": 0,
                "source_controller_provenance": _provenance("routed"),
                "record_count": 1,
                "problems": [],
            },
        },
        {"type": "record", "record": record},
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_coverage(
    path: Path,
    pool_path: Path,
    pool: NaturalBattleStartPool,
) -> None:
    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=BattleStartPoolRestoreReport(
            checkpoint_count=len(pool.records),
            requested_limit=0,
            restored_count=len(pool.records),
            native_restored_count=0,
            replay_restored_count=len(pool.records),
        ),
        input_artifacts={
            "natural_pool": {
                "path": str(pool_path),
                "sha256": _sha256_file(pool_path),
                "record_count": len(pool.records),
            }
        },
        source_identity=lightspeed_source_identity_dict(),
    )
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_battle_start_coverage_report_json(report, stream)


def _provenance(name: str) -> dict[str, object]:
    return ControllerProvenance(
        kind="decision_policy",
        name=name,
        config={"information_regime": "normal_public_policy"},
    ).to_dict()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
