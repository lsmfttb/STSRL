from __future__ import annotations

from dataclasses import replace
from io import StringIO
import json
from typing import Any

from sts_combat_rl.commands import a20_coverage as a20_command
from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20CoverageCommandConfig,
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
    format_a20_battle_start_coverage_report,
)
from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    STRUCTURAL_SAMPLING_COMPONENT,
    BattleStartCheckpointRecord,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    SampledBattleStart,
    dump_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.constructed_battle_start import (
    CONSTRUCTED_DISTRIBUTION_KIND,
    ConstructedBattleStartArtifact,
    ConstructedBattleStartPolicy,
    ConstructedBattleStartRecord,
    build_training_mixture_manifest,
    dump_constructed_battle_start_artifact_jsonl,
)
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.resource_outcome import (
    available_battle_resource_outcome,
    build_battle_resource_outcome,
)
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


def test_a20_coverage_separates_natural_sampled_constructed_and_gate_gaps() -> None:
    pool = _pool(record_count=2)
    sampled = [
        SampledBattleStart(
            sample_index=0,
            source_checkpoint_id=pool.records[0].source_checkpoint_id,
            sampling_component=STRUCTURAL_SAMPLING_COMPONENT,
            record=pool.records[0],
        ),
        SampledBattleStart(
            sample_index=1,
            source_checkpoint_id=pool.records[0].source_checkpoint_id,
            sampling_component=STRUCTURAL_SAMPLING_COMPONENT,
            record=pool.records[0],
        ),
    ]
    constructed = _constructed_artifact(pool, source_index=0)

    report = build_a20_battle_start_coverage_report(
        pool,
        sampled=sampled,
        constructed_artifact=constructed,
        restore_report=_restore_ok(pool),
        command_config=A20CoverageCommandConfig(
            sample_count=2,
            gate_config=TrainingScaleGateConfig(
                required_ascensions=(20,),
                required_acts=(1,),
                min_records_per_ascension_act=5,
                min_unique_sources_per_ascension_act=3,
            ),
        ),
        source_identity={"integration_commit": "fixture"},
    )
    text = format_a20_battle_start_coverage_report(report)

    assert report.command_passed is True
    assert report.natural_coverage.unique_source_start_count == 2
    assert report.sampled_draw_count == 2
    assert report.sampled_unique_source_count == 1
    assert report.constructed_coverage.constructed_record_count == 1
    assert report.training_row_coverage.row_count == 5
    assert report.training_row_coverage.unique_natural_source_count == 2
    assert report.training_gate_report.cells[0].record_count == 5
    assert report.training_gate_report.cells[0].unique_source_count == 2
    assert report.training_gate_report.broad_training_allowed is False
    assert "accepted constructed rows: 1" in text
    assert "broad training allowed: no" in text


def test_missing_metadata_is_visible_and_contributes_to_gate_problems() -> None:
    pool = _pool(record_count=1)
    missing_act = replace(
        pool.records[0],
        structural_metadata={**pool.records[0].structural_metadata, "act": None},
    )
    pool = replace(pool, records=[missing_act])

    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=_restore_ok(pool),
        command_config=A20CoverageCommandConfig(
            gate_config=TrainingScaleGateConfig(
                required_ascensions=(20,),
                required_acts=(1,),
                min_records_per_ascension_act=1,
                min_unique_sources_per_ascension_act=1,
            ),
        ),
        source_identity={"integration_commit": "fixture"},
    )

    assert report.natural_coverage.missing_metadata_counts["act"] == 1
    assert report.training_row_coverage.missing_metadata_counts["act"] == 1
    assert any(
        "missing required gate metadata: act" in problem
        for problem in report.training_gate_report.problems
    )
    assert any(
        "A20/act1: record count 0" in problem
        for problem in report.training_gate_report.problems
    )


def test_constructed_source_mismatch_is_a_command_problem() -> None:
    source_pool = _pool(record_count=1)
    constructed = _constructed_artifact(source_pool, source_index=0)
    mismatched_pool = replace(
        source_pool,
        records=[
            replace(
                source_pool.records[0],
                snapshot_raw={**source_pool.records[0].snapshot_raw, "cur_hp": 49},
            )
        ],
    )

    report = build_a20_battle_start_coverage_report(
        mismatched_pool,
        constructed_artifact=constructed,
        restore_report=_restore_ok(mismatched_pool),
        source_identity={"integration_commit": "fixture"},
    )

    assert report.command_passed is False
    assert any(
        "embedded source record" in problem for problem in report.command_problems
    )


def test_restore_failures_are_command_problems() -> None:
    pool = _pool(record_count=1)
    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=BattleStartPoolRestoreReport(
            checkpoint_count=1,
            requested_limit=1,
            restored_count=0,
            native_restored_count=0,
            replay_restored_count=0,
            problems=["record 0: restore exploded"],
        ),
        source_identity={"integration_commit": "fixture"},
    )

    assert report.command_passed is False
    assert "record 0: restore exploded" in report.command_problems
    assert any("restore verified 0 of 1" in item for item in report.command_problems)


def test_command_workflow_loads_artifacts_and_writes_json(
    monkeypatch,
    tmp_path,
) -> None:
    pool = _pool(record_count=1)
    constructed = _constructed_artifact(pool, source_index=0)
    pool_path = tmp_path / "pool.jsonl"
    constructed_path = tmp_path / "constructed.jsonl"
    output_path = tmp_path / "coverage.json"
    with pool_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)
    with constructed_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_constructed_battle_start_artifact_jsonl(constructed, stream)

    monkeypatch.setattr(
        a20_command,
        "verify_battle_start_pool_restores",
        lambda adapter_factory, loaded_pool, limit: _restore_ok(loaded_pool),
    )

    report = a20_command.run_a20_battle_start_coverage_from_paths(
        adapter_factory=lambda: object(),  # type: ignore[return-value]
        pool_path=pool_path,
        constructed_artifact_path=constructed_path,
        output_path=output_path,
        sample_count=1,
        gate_config=TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert report.command_passed is True
    assert payload["schema_id"] == "a20-battle-start-coverage-report-v1"
    assert payload["input_artifacts"]["natural_pool"]["sha256"]
    assert payload["constructed_coverage"]["constructed_record_count"] == 1


def test_command_workflow_loads_migrated_natural_pool(
    monkeypatch,
    tmp_path,
) -> None:
    pool_path = tmp_path / "legacy-pool.jsonl"
    output_path = tmp_path / "coverage.json"
    _write_v1_pool(pool_path)

    monkeypatch.setattr(
        a20_command,
        "verify_battle_start_pool_restores",
        lambda adapter_factory, loaded_pool, limit: _restore_ok(loaded_pool),
    )

    report = a20_command.run_a20_battle_start_coverage_from_paths(
        adapter_factory=lambda: object(),  # type: ignore[return-value]
        pool_path=pool_path,
        output_path=output_path,
        gate_config=TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
    )

    assert report.command_passed is True
    assert report.natural_coverage.natural_battle_start_count == 1
    assert (
        report.natural_coverage.resource_outcome_status_counts["legacy_unavailable"]
        == 1
    )
    assert output_path.exists()


def test_report_json_is_deterministic_current_schema() -> None:
    pool = _pool(record_count=1)
    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=_restore_ok(pool),
        source_identity={"integration_commit": "fixture"},
    )
    first = StringIO()
    second = StringIO()

    dump_a20_battle_start_coverage_report_json(report, first)
    dump_a20_battle_start_coverage_report_json(report, second)

    assert first.getvalue() == second.getvalue()
    assert '"schema_id": "a20-battle-start-coverage-report-v1"' in first.getvalue()


def _pool(*, record_count: int) -> NaturalBattleStartPool:
    records = [_record(index) for index in range(record_count)]
    return NaturalBattleStartPool(
        source_run_count=record_count,
        terminal_run_count=record_count,
        truncated_run_count=0,
        source_controller_provenance=_provenance("routed"),
        records=records,
    )


def _record(index: int) -> BattleStartCheckpointRecord:
    start = _raw(index, battle_active=True)
    terminal = {
        **_raw(index, battle_active=False),
        "outcome": "PLAYER_VICTORY",
        "completed_battle_outcome": "PLAYER_VICTORY",
        "cur_hp": 50,
    }
    outcome_status, outcome_payload = available_battle_resource_outcome(
        build_battle_resource_outcome(start, terminal)
    )
    return BattleStartCheckpointRecord(
        record_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_run_id=f"run-{index}",
        source_seed=100 + index,
        source_battle_index=index,
        structural_metadata={
            "ascension": 20,
            "act": 1,
            "floor": index + 1,
            "room_type": "MONSTER",
            "encounter_id": f"ENCOUNTER_{index}",
            "seed": 100 + index,
            "source_kind": NATURAL_DISTRIBUTION_KIND,
            "distribution_kind": NATURAL_DISTRIBUTION_KIND,
            "source_run_id": f"run-{index}",
            "source_battle_index": index,
        },
        source_controller_provenance=_provenance("routed"),
        source_battle_controller_provenance=_provenance("battle"),
        source_non_combat_controller_provenance=_provenance("non-combat"),
        action_trace=(),
        snapshot_observation=(100 + index, index),
        snapshot_raw=start,
        battle_outcome="PLAYER_VICTORY",
        battle_completed=True,
        completed_battle_resource_outcome_status=outcome_status,
        completed_battle_resource_outcome=outcome_payload,
        distribution_kind=NATURAL_DISTRIBUTION_KIND,
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
        public_context_status="legacy_unavailable",
        public_run_context={},
    )


def _constructed_artifact(
    pool: NaturalBattleStartPool,
    *,
    source_index: int,
) -> ConstructedBattleStartArtifact:
    source = pool.records[source_index]
    records = [
        ConstructedBattleStartRecord(
            record_index=0,
            source_record_index=source.record_index,
            source_checkpoint_id=source.source_checkpoint_id,
            source_distribution_kind=source.distribution_kind,
            source_checkpoint_information_regime=source.checkpoint_information_regime,
            source_public_context_status=source.public_context_status,
            source_record=_source_manifest(source),
            source_structural_metadata=dict(source.structural_metadata),
            transform_type="current_hp_addition",
            transform_policy_version="constructed-battle-start-policy-v1",
            transform_seed=1,
            proposal_seed=11,
            eligibility={"eligible": True, "reasons": []},
            proposal={"triggered": True, "reason": "seeded_probability_triggered"},
            requested_change={"current_hp_delta": 1},
            actual_change={"applied": True, "current_hp_delta": 1},
            resulting_distribution_kind=CONSTRUCTED_DISTRIBUTION_KIND,
            native_support_status="supported",
            constructed_snapshot_observation=source.snapshot_observation,
            constructed_snapshot_raw={**source.snapshot_raw, "cur_hp": 61},
        )
    ]
    return ConstructedBattleStartArtifact(
        source_pool_format_version=BATTLE_START_POOL_FORMAT_VERSION,
        transform_policy=ConstructedBattleStartPolicy(seed=1),
        records=records,
        source_record_count=len(pool.records),
        source_controller_provenance=pool.source_controller_provenance,
        mixture_manifest=build_training_mixture_manifest(pool, records),
    )


def _source_manifest(record: BattleStartCheckpointRecord) -> dict[str, Any]:
    from sts_combat_rl.sim.battle_start_pool import record_to_manifest

    return record_to_manifest(record)


def _restore_ok(pool: NaturalBattleStartPool) -> BattleStartPoolRestoreReport:
    return BattleStartPoolRestoreReport(
        checkpoint_count=len(pool.records),
        requested_limit=0,
        restored_count=len(pool.records),
        native_restored_count=0,
        replay_restored_count=len(pool.records),
    )


def _write_v1_pool(path) -> None:
    rows = [
        {
            "type": "metadata",
            "metadata": {
                "format_version": 1,
                "source_run_count": 1,
                "terminal_run_count": 1,
                "truncated_run_count": 0,
                "source_non_combat_policy": "first-eligible",
                "source_battle_policy": "first-eligible",
                "record_count": 1,
                "problems": [],
            },
        },
        {
            "type": "record",
            "record": {
                "record_index": 0,
                "checkpoint_id": "legacy-checkpoint-0",
                "source_run_id": "legacy-run-0",
                "seed": 100,
                "battle_index": 0,
                "ascension": 20,
                "act": 1,
                "floor": 1,
                "room_type": "MONSTER",
                "encounter_id": "LEGACY_ENCOUNTER",
                "source_non_combat_policy": "first-eligible",
                "source_battle_policy": "first-eligible",
                "action_trace": [],
                "observation": [100, 0],
                "raw_snapshot": _raw(0, battle_active=True),
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _provenance(name: str) -> dict[str, Any]:
    return ControllerProvenance(
        kind="decision_policy",
        name=name,
        config={"information_regime": "normal_public_policy"},
    ).to_dict()


def _raw(index: int, *, battle_active: bool) -> dict[str, Any]:
    return {
        "screen_state": "BATTLE" if battle_active else "REWARDS",
        "battle_active": battle_active,
        "outcome": "UNDECIDED" if battle_active else "PLAYER_VICTORY",
        "completed_battle_outcome": (
            "UNDECIDED" if battle_active else "PLAYER_VICTORY"
        ),
        "ascension": 20,
        "act": 1,
        "floor_num": index + 1,
        "room_type": "MONSTER",
        "encounter_id": f"ENCOUNTER_{index}",
        "cur_hp": 60,
        "max_hp": 80,
        "gold": 99,
        "potion_capacity": 2,
        "potions": [
            {"slot_index": 0, "id": "Potion Slot", "name": "Potion Slot"},
            {"slot_index": 1, "id": "Potion Slot", "name": "Potion Slot"},
        ],
        "deck": [{"id": "Strike_R", "name": "Strike", "type": "ATTACK"}],
        "relics": [{"id": "Burning Blood", "name": "Burning Blood"}],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
    }
