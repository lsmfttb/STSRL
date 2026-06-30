from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.commands.oracle_teacher_search_guidance import (
    run_oracle_teacher_search_guidance_from_paths,
)
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    ASSIST_LEVEL_0,
    AssistedSourcePoolArtifact,
    assistance_schedule_by_level,
    dump_assisted_source_pool_jsonl,
)
from sts_combat_rl.sim.battle_start_pool import (
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    dump_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import (
    OracleTeacherDataset,
    OracleTeacherRow,
    dump_oracle_teacher_dataset_jsonl,
)
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION,
    ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID,
)
from sts_combat_rl.sim.oracle_teacher_search_guidance import (
    ORACLE_TEACHER_SEARCH_GUIDANCE_ASSISTED_TASK_ID,
    ORACLE_TEACHER_SEARCH_GUIDANCE_NATURAL_TASK_ID,
)
from sts_combat_rl.sim.public_run_context import build_public_run_context
from sts_combat_rl.sim.resource_outcome import (
    available_battle_resource_outcome,
    build_battle_resource_outcome,
)
from sts_combat_rl.sim.trainer_input import (
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    load_trainer_input_dataset_jsonl_text,
)


class _BridgeAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "bridge-adapter"

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        return _snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return _actions()


def test_bridge_converts_teacher_action_target_and_writes_report(
    tmp_path: Path,
) -> None:
    manifest_path, trainer_path, report_path = _write_artifact_chain(tmp_path)

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=manifest_path,
        selected_budget=100,
        output_path=trainer_path,
        target="teacher_action_one_hot",
        stability_filter="none",
        report_output_path=report_path,
    )

    dataset = load_trainer_input_dataset_jsonl_text(
        trainer_path.read_text(encoding="utf-8")
    )
    record = dataset.records[0]
    report_json = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.command_passed
    assert report_json["schema_id"] == "oracle-teacher-search-guidance-bridge-report-v1"
    assert report.policy_target_kind == POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    assert record.policy_target_kind == POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    assert record.policy_target_source == "oracle_teacher_row.teacher_action"
    assert record.policy_target == [0.0, 1.0]
    assert record.chosen_action_index == 1
    assert record.behavior_action_status == "unavailable"
    assert record.controller_provenance["config"]["information_regime"] == (
        "full_simulator_state_oracle_like"
    )
    assert dataset.generation_metadata["task_id"] == (
        ORACLE_TEACHER_SEARCH_GUIDANCE_NATURAL_TASK_ID
    )
    assert record.source_metadata["teacher_budget"] == 100
    assert report_json["trainer_artifact_identity"]["sha256"] == _sha256_file(
        trainer_path
    )
    assert report_json["evidence_boundary"]["not_normal_information"] is True


def test_bridge_resolves_scaleup_cli_cwd_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _trainer_path, _report_path = _write_artifact_chain(tmp_path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["input_artifacts"]["natural_pool"]["path"] = "pool.jsonl"
    raw["generated_artifacts"][0]["teacher_artifact"]["path"] = "teacher.jsonl"
    raw["generated_artifacts"][0]["t022_report_artifact"]["path"] = (
        "teacher-report.json"
    )
    manifest_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=Path("oracle-teacher-scaleup-manifest.json"),
        selected_budget=100,
        output_path=Path("trainer-relative.jsonl"),
        target="teacher_action_one_hot",
        stability_filter="none",
        report_output_path=Path("bridge-relative.json"),
    )

    assert report.command_passed
    assert Path("trainer-relative.jsonl").exists()
    assert report.source_pool_identity["path"] == "pool.jsonl"


def test_bridge_converts_soft_visit_target_by_action_identity(tmp_path: Path) -> None:
    manifest_path, trainer_path, report_path = _write_artifact_chain(tmp_path)

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=manifest_path,
        selected_budget=100,
        output_path=trainer_path,
        target="soft_visit_distribution",
        stability_filter="none",
        report_output_path=report_path,
    )

    dataset = load_trainer_input_dataset_jsonl_text(
        trainer_path.read_text(encoding="utf-8")
    )
    record = dataset.records[0]

    assert report.command_passed
    assert record.policy_target_kind == POLICY_TARGET_KIND_ORACLE_SOFT_VISIT
    assert record.policy_target_source == "oracle_teacher_row.soft_visit_target"
    assert record.policy_target == [0.25, 0.75]
    assert record.policy_target_action_index == 1


def test_bridge_loads_assisted_pool_and_preserves_assistance_metadata(
    tmp_path: Path,
) -> None:
    manifest_path, trainer_path, report_path = _write_artifact_chain(
        tmp_path,
        assisted=True,
    )

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=manifest_path,
        selected_budget=100,
        output_path=trainer_path,
        target="soft_visit_distribution",
        stability_filter="none",
        report_output_path=report_path,
    )

    dataset = load_trainer_input_dataset_jsonl_text(
        trainer_path.read_text(encoding="utf-8")
    )
    record = dataset.records[0]
    report_json = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.command_passed
    assert record.source_metadata["distribution_kind"] == ASSISTED_RUN_DISTRIBUTION_KIND
    assert record.source_metadata["assistance_level"] == ASSIST_LEVEL_0
    assert (
        record.source_metadata["sampling_component"] == ASSISTED_RUN_DISTRIBUTION_KIND
    )
    assert dataset.generation_metadata["task_id"] == (
        ORACLE_TEACHER_SEARCH_GUIDANCE_ASSISTED_TASK_ID
    )
    assert dataset.generation_metadata["source_pool_kind"] == "assisted_pool"
    assert dataset.generation_metadata["source_group_summary"][
        "assistance_level_counts"
    ] == {ASSIST_LEVEL_0: 1}
    assert report_json["source_pool_identity"]["source_pool_kind"] == "assisted_pool"
    assert report_json["source_group_summary"]["assistance_act_room_counts"] == {
        f"{ASSIST_LEVEL_0}/act1/MONSTER": 1
    }


def test_bridge_fails_closed_for_manifest_teacher_sha_mismatch(
    tmp_path: Path,
) -> None:
    manifest_path, trainer_path, report_path = _write_artifact_chain(tmp_path)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["generated_artifacts"][0]["teacher_artifact"]["sha256"] = "mismatch"
    manifest_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=manifest_path,
        selected_budget=100,
        output_path=trainer_path,
        target="teacher_action_one_hot",
        stability_filter="none",
        report_output_path=report_path,
    )

    assert not report.command_passed
    assert not trainer_path.exists()
    assert any("teacher artifact sha256" in problem for problem in report.problems)
    assert (
        json.loads(report_path.read_text(encoding="utf-8"))["command_passed"] is False
    )


@pytest.mark.parametrize(
    ("assisted", "expected_task_id", "expected_source_pool_kind"),
    [
        (False, ORACLE_TEACHER_SEARCH_GUIDANCE_NATURAL_TASK_ID, "natural_pool"),
        (True, ORACLE_TEACHER_SEARCH_GUIDANCE_ASSISTED_TASK_ID, "assisted_pool"),
    ],
)
def test_bridge_optional_checkpoint_records_teacher_target_provenance(
    tmp_path: Path,
    assisted: bool,
    expected_task_id: str,
    expected_source_pool_kind: str,
) -> None:
    pytest.importorskip("torch")
    from sts_combat_rl.sim.torch_policy_value import (
        TorchPolicyValueTrainingConfig,
        load_torch_policy_value_checkpoint,
    )

    manifest_path, trainer_path, report_path = _write_artifact_chain(
        tmp_path,
        assisted=assisted,
    )
    checkpoint_path = tmp_path / "teacher-guidance.pt"

    report = run_oracle_teacher_search_guidance_from_paths(
        adapter_factory=_BridgeAdapter,
        manifest_path=manifest_path,
        selected_budget=100,
        output_path=trainer_path,
        target="teacher_action_one_hot",
        stability_filter="none",
        report_output_path=report_path,
        checkpoint_output_path=checkpoint_path,
        training_config=TorchPolicyValueTrainingConfig(
            epochs=1,
            hidden_size=8,
            batch_size=1,
        ),
        gate_override="smoke",
    )
    loaded = load_torch_policy_value_checkpoint(str(checkpoint_path))

    assert report.command_passed
    assert checkpoint_path.exists()
    assert loaded.metadata["task_id"] == expected_task_id
    assert loaded.metadata["source_pool_kind"] == expected_source_pool_kind
    assert (
        loaded.training_data_provenance["target_source_summary"]["policy_target_kind"]
        == POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    )
    assert (
        loaded.training_data_provenance["target_source_summary"]["policy_target_source"]
        == "oracle_teacher_row.teacher_action"
    )
    assert loaded.training_data_provenance["information_regime_counts"] == {
        "full_simulator_state_oracle_like": 1
    }


def _write_artifact_chain(
    tmp_path: Path,
    *,
    assisted: bool = False,
) -> tuple[Path, Path, Path]:
    pool = _pool(assisted=assisted)
    teacher_dataset = _teacher_dataset(assisted=assisted)
    pool_path = tmp_path / "pool.jsonl"
    teacher_path = tmp_path / "teacher.jsonl"
    t022_report_path = tmp_path / "teacher-report.json"
    manifest_path = tmp_path / "oracle-teacher-scaleup-manifest.json"
    trainer_path = tmp_path / "teacher-guidance-trainer.jsonl"
    bridge_report_path = tmp_path / "teacher-guidance-report.json"
    with pool_path.open("w", encoding="utf-8", newline="\n") as stream:
        if assisted:
            dump_assisted_source_pool_jsonl(_assisted_artifact(pool), stream)
        else:
            dump_natural_battle_start_pool_jsonl(pool, stream)
    with teacher_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_teacher_dataset_jsonl(teacher_dataset, stream)
    t022_report_path.write_text(
        json.dumps(
            {
                "schema_id": "oracle-teacher-dataset-report-v1",
                "format_version": 1,
                "command_passed": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_id": ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID,
        "format_version": ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION,
        "input_artifacts": {
            "assisted_pool" if assisted else "natural_pool": {
                "path": str(pool_path),
                "sha256": _sha256_file(pool_path),
                "record_count": 1,
                **(
                    {
                        "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
                        "assistance_level": ASSIST_LEVEL_0,
                    }
                    if assisted
                    else {}
                ),
            }
        },
        "requested_budgets": [100],
        "generated_artifacts": [
            {
                "budget": 100,
                "teacher_artifact": {
                    "path": str(teacher_path),
                    "sha256": _sha256_file(teacher_path),
                    "record_count": 1,
                },
                "t022_report_artifact": {
                    "path": str(t022_report_path),
                    "sha256": _sha256_file(t022_report_path),
                    "schema_id": "oracle-teacher-dataset-report-v1",
                    "format_version": 1,
                },
            }
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path, trainer_path, bridge_report_path


def _teacher_dataset(*, assisted: bool = False) -> OracleTeacherDataset:
    controller = OracleSearchController(simulations=100)
    return OracleTeacherDataset(
        native_source_identity={},
        controller_provenance=controller.provenance.to_dict(),
        action_space_config=controller.action_space.to_dict(),
        source_pool_format_version=4,
        source_pool_controller_provenance=_provenance("source"),
        records=[_teacher_row(assisted=assisted)],
    )


def _teacher_row(*, assisted: bool = False) -> OracleTeacherRow:
    identities = action_identity_dicts_for_actions(_actions())
    metadata = _metadata(assisted=assisted)
    return OracleTeacherRow(
        row_index=0,
        source_checkpoint_id="checkpoint-0",
        source_pool_record_index=0,
        source_run_id="run-0",
        source_seed=1,
        source_battle_index=0,
        source_distribution_kind=(
            ASSISTED_RUN_DISTRIBUTION_KIND if assisted else NATURAL_DISTRIBUTION_KIND
        ),
        sampling_component=ASSISTED_RUN_DISTRIBUTION_KIND if assisted else "natural",
        restoration_method="seed_action_trace",
        structural_metadata=metadata,
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
        legal_action_identities=identities,
        legal_action_kinds=["card", "end_turn"],
        eligible_action_indices=[0, 1],
        root_statistics=[
            {"legal_action_index": 0, "visits": 25, "mean_value": 0.2},
            {"legal_action_index": 1, "visits": 75, "mean_value": 0.6},
        ],
        teacher_action={
            "selection_rule": "highest_mean",
            "legal_action_index": 1,
            "action_identity": identities[1],
            "visits": 75,
            "mean_value": 0.6,
        },
        soft_visit_target={
            "target_kind": "root_visit_distribution",
            "probabilities": [0.25, 0.75],
            "denominator": 100,
        },
        behavior_action=None,
        controller_provenance=OracleSearchController(
            simulations=100
        ).provenance.to_dict(),
        information_regime="full_simulator_state_oracle_like",
        public_context_status="available",
        public_run_context=_public_context(),
        native_search_report={
            "schema_id": "native-battle-search-root-v1",
            "information_regime": "full_simulator_state_oracle_like",
            "simulations_requested": 100,
            "root_visits": 100,
            "native_simulator_steps": 123,
            "model_calls": None,
            "wall_clock_time_s": 0.0,
            "unsearched_legal_action_count": 0,
            "unmapped_search_edge_count": 0,
            "problems": [],
        },
    )


def _pool(*, assisted: bool = False) -> NaturalBattleStartPool:
    status, outcome = available_battle_resource_outcome(
        build_battle_resource_outcome(
            _raw(battle_active=True), _raw(battle_active=False)
        )
    )
    snapshot = _snapshot()
    metadata = _metadata(assisted=assisted)
    distribution_kind = (
        ASSISTED_RUN_DISTRIBUTION_KIND if assisted else NATURAL_DISTRIBUTION_KIND
    )
    assistance_history = (_assistance_decision(),) if assisted else ()
    return NaturalBattleStartPool(
        source_run_count=1,
        terminal_run_count=1,
        truncated_run_count=0,
        source_controller_provenance=_provenance("source"),
        records=[
            BattleStartCheckpointRecord(
                record_index=0,
                source_checkpoint_id="checkpoint-0",
                source_run_id="run-0",
                source_seed=1,
                source_battle_index=0,
                structural_metadata=metadata,
                source_controller_provenance=_provenance("source"),
                source_battle_controller_provenance=_provenance("battle"),
                source_non_combat_controller_provenance=_provenance("non-combat"),
                action_trace=(),
                snapshot_observation=tuple(snapshot.observation),
                snapshot_raw=dict(snapshot.raw),
                battle_outcome="PLAYER_VICTORY",
                battle_completed=True,
                completed_battle_resource_outcome_status=status,
                completed_battle_resource_outcome=outcome,
                distribution_kind=distribution_kind,
                checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
                public_context_status="available",
                public_run_context=_public_context(),
                assistance_history=assistance_history,
            )
        ],
    )


def _assisted_artifact(pool: NaturalBattleStartPool) -> AssistedSourcePoolArtifact:
    schedule = assistance_schedule_by_level(ASSIST_LEVEL_0)
    return AssistedSourcePoolArtifact(
        pool=pool,
        assistance_level=ASSIST_LEVEL_0,
        assistance_schedule=schedule,
        policy_seed=1,
        assistance_decisions=tuple(
            record.assistance_history[-1] for record in pool.records
        ),
    )


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="strike",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="end",
            label="End Turn",
            kind="end_turn",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
    ]


def _snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(observation=(1, 2, 3), raw=_raw(battle_active=True))


def _raw(*, battle_active: bool) -> dict[str, object]:
    return {
        "screen_state": "BATTLE" if battle_active else "BOSS_REWARD",
        "battle_active": battle_active,
        "outcome": "UNDECIDED" if battle_active else "PLAYER_VICTORY",
        "completed_battle_outcome": (
            "UNDECIDED" if battle_active else "PLAYER_VICTORY"
        ),
        "ascension": 20,
        "act": 1,
        "floor_num": 5,
        "room_type": "MONSTER",
        "encounter_id": "Cultist",
        "cur_hp": 70,
        "max_hp": 80,
        "gold": 99,
        "potion_capacity": 2,
        "potions": [{"id": "Potion Slot", "name": "Potion Slot", "slot_index": 0}],
        "deck": [{"id": "Strike_R", "name": "Strike", "type": "ATTACK"}],
        "relics": [{"id": "Burning Blood", "name": "Burning Blood", "counter": 0}],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
        "battle_player": {
            "current_hp": 70,
            "max_hp": 80,
            "energy": 3,
            "block": 0,
        },
        "battle_hand": [
            {
                "id": "Strike_R",
                "name": "Strike",
                "type": "ATTACK",
                "cost": 1,
                "playable": True,
                "requires_target": True,
            }
        ],
        "battle_hand_size": 1,
        "battle_draw_pile_size": 4,
        "battle_discard_pile_size": 1,
        "battle_exhaust_pile_size": 0,
        "battle_monsters": [
            {
                "id": "Cultist",
                "name": "Cultist",
                "current_hp": 48,
                "max_hp": 48,
                "intent": "ATTACK",
                "intent_category": "ATTACK",
            }
        ],
    }


def _public_context() -> dict[str, object]:
    return build_public_run_context(
        _raw(battle_active=True),
        _actions(),
        projection=None,
        history=[],
    )


def _metadata(*, assisted: bool = False) -> dict[str, object]:
    distribution_kind = (
        ASSISTED_RUN_DISTRIBUTION_KIND if assisted else NATURAL_DISTRIBUTION_KIND
    )
    metadata = {
        "ascension": 20,
        "act": 1,
        "floor": 5,
        "room_type": "MONSTER",
        "encounter_id": "Cultist",
        "seed": 1,
        "source_kind": distribution_kind,
        "distribution_kind": distribution_kind,
        "source_run_id": "run-0",
        "source_checkpoint_id": "checkpoint-0",
        "source_battle_index": 0,
    }
    if assisted:
        schedule = assistance_schedule_by_level(ASSIST_LEVEL_0)
        metadata.update(
            {
                "assistance_level": schedule.level,
                "assistance_version": schedule.version,
                "distribution_tag": schedule.distribution_tag,
            }
        )
    return metadata


def _assistance_decision() -> dict[str, object]:
    resources = {
        "current_hp": 70,
        "max_hp": 80,
        "potion_count": 0,
        "potion_capacity": 2,
    }
    return {
        "assistance_version": assistance_schedule_by_level(ASSIST_LEVEL_0).version,
        "assistance_level": ASSIST_LEVEL_0,
        "policy_seed": 1,
        "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
        "information_regime": CHECKPOINT_INFORMATION_REGIME,
        "source_run_id": "run-0",
        "source_seed": 1,
        "source_battle_index": 0,
        "source_checkpoint_id": "checkpoint-0",
        "source_record_index": 0,
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
