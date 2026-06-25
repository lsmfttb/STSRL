from __future__ import annotations

from dataclasses import replace
from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.commands.oracle_teacher_report import (
    run_oracle_teacher_dataset_report_from_paths,
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
)
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import (
    OracleTeacherDataset,
    OracleTeacherRow,
    dump_oracle_teacher_dataset_jsonl,
)
from sts_combat_rl.sim.oracle_teacher_report import (
    build_oracle_teacher_dataset_audit_report,
    dump_oracle_teacher_dataset_audit_report_json,
    format_oracle_teacher_dataset_audit_report,
    load_a20_coverage_report_json,
)


def test_oracle_teacher_report_teacher_only_is_deterministic() -> None:
    dataset = _dataset()

    report = build_oracle_teacher_dataset_audit_report(
        dataset,
        current_source_manifest_identity=lightspeed_source_identity_dict(),
    )

    assert report.command_passed
    assert report.teacher_coverage["teacher_row_count"] == 1
    assert report.teacher_coverage["unique_source_start_count"] == 1
    assert report.search_statistics["root_row_count"] == 2
    assert report.search_statistics["root_visit_count"] == 5
    assert report.search_statistics["teacher_action_available_count"] == 1
    assert report.search_statistics["soft_visit_target_available_count"] == 1

    first = StringIO()
    second = StringIO()
    dump_oracle_teacher_dataset_audit_report_json(report, first)
    dump_oracle_teacher_dataset_audit_report_json(report, second)
    assert first.getvalue() == second.getvalue()
    assert '"schema_id": "oracle-teacher-dataset-report-v1"' in first.getvalue()

    text = format_oracle_teacher_dataset_audit_report(report)
    assert "full_simulator_state_oracle_like teacher data" in text
    assert "root rows and visits are search statistics only" in text


def test_oracle_teacher_report_repeated_rows_do_not_add_source_coverage() -> None:
    first = _row()
    second = replace(first, row_index=1)
    dataset = _dataset(records=[first, second])

    report = build_oracle_teacher_dataset_audit_report(
        dataset,
        current_source_manifest_identity=lightspeed_source_identity_dict(),
    )

    assert report.command_passed
    assert report.teacher_coverage["teacher_row_count"] == 2
    assert report.teacher_coverage["unique_source_start_count"] == 1
    assert report.search_statistics["root_row_count"] == 4
    assert report.search_statistics["root_visit_count"] == 10


def test_oracle_teacher_report_flags_missing_metadata_and_mixed_regime() -> None:
    row = _row()
    bad_metadata = dict(row.structural_metadata)
    bad_metadata.pop("act")
    bad_row = replace(
        row,
        structural_metadata=bad_metadata,
        information_regime="normal_public_policy",
    )
    dataset = _dataset(records=[bad_row])

    report = build_oracle_teacher_dataset_audit_report(
        dataset,
        current_source_manifest_identity=lightspeed_source_identity_dict(),
    )

    assert not report.command_passed
    assert report.teacher_coverage["missing_metadata_counts"]["act"] == 1
    assert any("wrong information regime" in problem for problem in report.problems)
    assert any(
        "missing structural metadata act" in problem for problem in report.problems
    )


def test_oracle_teacher_report_links_source_pool_and_detects_mismatch() -> None:
    pool = _pool()
    dataset = _dataset()

    report = build_oracle_teacher_dataset_audit_report(
        dataset,
        source_pool=pool,
        source_pool_artifact_identity={"sha256": "pool-sha"},
        current_source_manifest_identity=lightspeed_source_identity_dict(),
    )

    assert report.command_passed
    assert report.source_pool_linkage["matched"] is True
    assert report.source_pool_linkage["teacher_rows_linked_count"] == 1
    assert report.source_pool_linkage["missing_teacher_source_count"] == 0

    bad_dataset = _dataset(records=[replace(_row(), source_checkpoint_id="missing")])
    bad_report = build_oracle_teacher_dataset_audit_report(
        bad_dataset,
        source_pool=pool,
        source_pool_artifact_identity={"sha256": "pool-sha"},
        current_source_manifest_identity=lightspeed_source_identity_dict(),
    )

    assert not bad_report.command_passed
    assert bad_report.source_pool_linkage["missing_teacher_source_count"] == 1
    assert any(
        "is not in the source pool" in problem for problem in bad_report.problems
    )


def test_oracle_teacher_report_links_t021_coverage_without_failing_undercoverage(
    tmp_path: Path,
) -> None:
    pool = _pool()
    dataset = _dataset()
    pool_path = tmp_path / "pool.jsonl"
    teacher_path = tmp_path / "teacher.jsonl"
    coverage_path = tmp_path / "coverage.json"
    output_path = tmp_path / "teacher-report.json"
    _write_pool(pool_path, pool)
    _write_teacher(teacher_path, dataset)
    coverage_report = build_a20_battle_start_coverage_report(
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
    with coverage_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_battle_start_coverage_report_json(coverage_report, stream)

    report = run_oracle_teacher_dataset_report_from_paths(
        teacher_path=teacher_path,
        source_pool_path=pool_path,
        coverage_report_path=coverage_path,
        output_path=output_path,
    )

    assert report.command_passed
    assert output_path.exists()
    assert report.coverage_report_linkage["natural_pool_identity_matched"] is True
    assert report.coverage_report_linkage["broad_training_allowed"] is False
    assert report.coverage_report_linkage["coverage_gaps"]

    raw = json.loads(coverage_path.read_text(encoding="utf-8"))
    raw["input_artifacts"]["natural_pool"]["sha256"] = "mismatch"
    mismatch_path = tmp_path / "coverage-mismatch.json"
    mismatch_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")
    mismatch = run_oracle_teacher_dataset_report_from_paths(
        teacher_path=teacher_path,
        source_pool_path=pool_path,
        coverage_report_path=mismatch_path,
    )

    assert not mismatch.command_passed
    assert any("sha256 does not match" in problem for problem in mismatch.problems)


def test_oracle_teacher_report_rejects_malformed_coverage_schema() -> None:
    with pytest.raises(ValueError, match="unsupported T021 coverage schema_id"):
        load_a20_coverage_report_json(
            StringIO(json.dumps({"schema_id": "wrong", "format_version": 1}))
        )


def _dataset(
    *,
    records: list[OracleTeacherRow] | None = None,
) -> OracleTeacherDataset:
    controller = OracleSearchController(
        simulations=5,
        native_source_identity=lightspeed_source_identity_dict(),
    )
    return OracleTeacherDataset(
        native_source_identity=lightspeed_source_identity_dict(),
        controller_provenance=controller.provenance.to_dict(),
        action_space_config=controller.action_space.to_dict(),
        source_pool_format_version=BATTLE_START_POOL_FORMAT_VERSION,
        source_pool_controller_provenance=_provenance("routed"),
        records=records if records is not None else [_row()],
    )


def _row() -> OracleTeacherRow:
    action_identities = [
        {"action_id": "battle:11", "kind": "card", "label": "Strike", "occurrence": 0},
        {"action_id": "battle:22", "kind": "card", "label": "Defend", "occurrence": 0},
    ]
    return OracleTeacherRow(
        row_index=0,
        source_checkpoint_id="checkpoint-0",
        source_pool_record_index=0,
        source_run_id="run-0",
        source_seed=100,
        source_battle_index=0,
        source_distribution_kind=NATURAL_DISTRIBUTION_KIND,
        sampling_component="natural",
        restoration_method="seed_action_trace",
        structural_metadata=_structural_metadata(),
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
        legal_action_identities=action_identities,
        legal_action_kinds=["card", "card"],
        eligible_action_indices=[0, 1],
        root_statistics=[
            {"legal_action_index": 0, "visits": 4, "mean_value": 0.2},
            {"legal_action_index": 1, "visits": 1, "mean_value": 0.6},
        ],
        teacher_action={
            "selection_rule": "highest_mean",
            "legal_action_index": 1,
            "action_identity": action_identities[1],
            "visits": 1,
            "mean_value": 0.6,
            "score": 0.6,
        },
        soft_visit_target={
            "target_kind": "root_visit_distribution",
            "probabilities": [0.8, 0.2],
            "denominator": 5,
        },
        behavior_action=None,
        controller_provenance=OracleSearchController(
            simulations=5,
            native_source_identity=lightspeed_source_identity_dict(),
        ).provenance.to_dict(),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        public_context_status="legacy_unavailable",
        public_run_context={},
        native_search_report={
            "schema_id": "native-battle-search-root-v1",
            "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
            "simulations_requested": 5,
            "root_visits": 5,
            "native_simulator_steps": 17,
            "model_calls": None,
            "wall_clock_time_s": 0.125,
            "unsearched_legal_action_count": 0,
            "unmapped_search_edge_count": 0,
            "problems": [],
        },
    )


def _pool() -> NaturalBattleStartPool:
    return NaturalBattleStartPool(
        source_run_count=1,
        terminal_run_count=0,
        truncated_run_count=1,
        source_controller_provenance=_provenance("routed"),
        records=[
            BattleStartCheckpointRecord(
                record_index=0,
                source_checkpoint_id="checkpoint-0",
                source_run_id="run-0",
                source_seed=100,
                source_battle_index=0,
                structural_metadata=_structural_metadata(),
                source_controller_provenance=_provenance("routed"),
                source_battle_controller_provenance=_provenance("battle"),
                source_non_combat_controller_provenance=_provenance("non-combat"),
                action_trace=(),
                snapshot_observation=(1, 2, 3),
                snapshot_raw={
                    "screen_state": "BATTLE",
                    "battle_active": True,
                    "outcome": "UNDECIDED",
                    "ascension": 20,
                    "act": 1,
                    "floor_num": 1,
                    "room_type": "MONSTER",
                    "encounter_id": "Cultist",
                },
                checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
            )
        ],
    )


def _structural_metadata() -> dict[str, object]:
    return {
        "ascension": 20,
        "act": 1,
        "floor": 1,
        "room_type": "MONSTER",
        "encounter_id": "Cultist",
        "seed": 100,
        "source_kind": NATURAL_DISTRIBUTION_KIND,
        "distribution_kind": NATURAL_DISTRIBUTION_KIND,
        "source_run_id": "run-0",
        "source_battle_index": 0,
    }


def _provenance(name: str) -> dict[str, object]:
    return ControllerProvenance(
        kind="decision_policy",
        name=name,
        config={"information_regime": "normal_public_policy"},
    ).to_dict()


def _write_pool(path: Path, pool: NaturalBattleStartPool) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)


def _write_teacher(path: Path, dataset: OracleTeacherDataset) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_teacher_dataset_jsonl(dataset, stream)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
