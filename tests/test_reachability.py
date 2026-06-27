from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sts_combat_rl.cli import main
from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20CoverageCommandConfig,
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
)
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    SourceRunSummary,
    dump_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.policy import FirstEligiblePolicy, StochasticNonCombatDriver
from sts_combat_rl.sim.reachability import (
    build_a20_reachability_comparison_report,
)
from sts_combat_rl.sim.resource_outcome import unavailable_battle_resource_outcome
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


def test_reachability_cli_compares_default_and_oracle_arms(
    tmp_path: Path,
    capsys,
) -> None:
    default_pool = _pool(
        label="default",
        controller=_default_controller(),
        records=[
            _record(index=0, run_id="default-run-0", seed=1, act=1, floor=1),
        ],
        summaries=[
            _summary(
                run_id="default-run-0",
                seed=1,
                final_floor=3.0,
                final_act=1,
                battle_count=1,
                max_battle_start_floor=1.0,
            )
        ],
    )
    oracle_pool = _pool(
        label="oracle",
        controller=_oracle_controller(),
        records=[
            _record(
                index=0,
                run_id="oracle-run-0",
                seed=10,
                act=1,
                floor=16,
                room_type="BOSS",
                encounter_id="Hexaghost",
            ),
            _record(
                index=1,
                run_id="oracle-run-0",
                seed=10,
                act=2,
                floor=18,
                room_type="MONSTER",
                encounter_id="Chosen",
            ),
        ],
        summaries=[
            _summary(
                run_id="oracle-run-0",
                seed=10,
                final_floor=18.0,
                final_act=2,
                battle_count=2,
            )
        ],
    )
    default_paths = _write_pool_and_coverage(tmp_path, "default", default_pool)
    oracle_paths = _write_pool_and_coverage(tmp_path, "oracle", oracle_pool)
    report_path = tmp_path / "reachability.json"

    assert (
        main(
            [
                "--a20-reachability-report",
                str(report_path),
                "--reachability-arm",
                "default",
                str(default_paths[0]),
                str(default_paths[1]),
                "--reachability-arm",
                "oracle-no-potion",
                str(oracle_paths[0]),
                str(oracle_paths[1]),
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert captured.out == ""
    assert "A20 search-controlled reachability report" in captured.err
    assert payload["schema_id"] == "a20-search-controlled-reachability-report-v1"
    assert payload["command_passed"] is True
    assert payload["comparison"]["best_later_act_arm"] == "oracle-no-potion"
    oracle_arm = payload["arms"][1]
    assert oracle_arm["act1_boss_battle_start_count"] == 1
    assert oracle_arm["later_act_battle_start_count"] == 1
    assert oracle_arm["terminal_floor_counts"] == {"18": 1}
    assert oracle_arm["controller"]["information_regime"] == (
        "full_simulator_state_oracle_like"
    )


def test_reachability_report_fails_closed_on_coverage_pool_sha_mismatch(
    tmp_path: Path,
) -> None:
    pool = _pool(
        label="default",
        controller=_default_controller(),
        records=[_record(index=0, run_id="default-run-0", seed=1, act=1, floor=1)],
        summaries=[
            _summary(
                run_id="default-run-0",
                seed=1,
                final_floor=1.0,
                final_act=1,
                battle_count=1,
            )
        ],
    )
    pool_path, coverage_path = _write_pool_and_coverage(tmp_path, "default", pool)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["input_artifacts"]["natural_pool"]["sha256"] = "wrong"
    report = build_a20_reachability_comparison_report(
        [
            (
                "a",
                pool,
                coverage,
                {
                    "pool_path": str(pool_path),
                    "pool_sha256": _sha256(pool_path),
                    "coverage_report_path": str(coverage_path),
                    "coverage_report_sha256": _sha256(coverage_path),
                    "coverage_record_count": 1,
                },
            ),
            (
                "b",
                pool,
                coverage,
                {
                    "pool_path": str(pool_path),
                    "pool_sha256": _sha256(pool_path),
                    "coverage_report_path": str(coverage_path),
                    "coverage_report_sha256": _sha256(coverage_path),
                    "coverage_record_count": 1,
                },
            ),
        ]
    )

    assert report.command_passed is False
    assert any(
        "sha256 does not match" in problem for problem in report.command_problems
    )


def test_reachability_report_requires_artifact_linkage_and_source_identity(
    tmp_path: Path,
) -> None:
    pool = _pool(
        label="default",
        controller=_default_controller(),
        records=[_record(index=0, run_id="default-run-0", seed=1, act=1, floor=1)],
        summaries=[
            _summary(
                run_id="default-run-0",
                seed=1,
                final_floor=1.0,
                final_act=1,
                battle_count=1,
            )
        ],
    )
    pool_path, coverage_path = _write_pool_and_coverage(tmp_path, "default", pool)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["input_artifacts"]["natural_pool"].pop("sha256")
    coverage.pop("source_identity")
    artifact_identity = {
        "pool_path": str(pool_path),
        "pool_sha256": _sha256(pool_path),
        "coverage_report_path": str(coverage_path),
        "coverage_report_sha256": _sha256(coverage_path),
        "coverage_record_count": 1,
    }

    report = build_a20_reachability_comparison_report(
        [
            ("a", pool, coverage, artifact_identity),
            ("b", pool, coverage, artifact_identity),
        ]
    )

    assert report.command_passed is False
    assert any(
        "natural-pool sha256 is missing" in problem
        for problem in report.command_problems
    )
    assert any(
        "missing source_identity" in problem for problem in report.command_problems
    )


def _default_controller() -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(StochasticNonCombatDriver(seed=1)),
    )


def _oracle_controller() -> RoutedRunController:
    return RoutedRunController(
        battle=OracleSearchController(simulations=5),
        non_combat=PolicyController(StochasticNonCombatDriver(seed=1)),
    )


def _pool(
    *,
    label: str,
    controller: RoutedRunController,
    records: list[BattleStartCheckpointRecord],
    summaries: list[SourceRunSummary],
) -> NaturalBattleStartPool:
    return NaturalBattleStartPool(
        source_run_count=len(summaries),
        terminal_run_count=sum(1 for summary in summaries if summary.terminal),
        truncated_run_count=sum(1 for summary in summaries if not summary.terminal),
        source_controller_provenance=controller.provenance.to_dict(),
        records=[
            _with_provenance(record, controller=controller, index=index)
            for index, record in enumerate(records)
        ],
        source_run_summaries=summaries,
        problems=[],
    )


def _with_provenance(
    record: BattleStartCheckpointRecord,
    *,
    controller: RoutedRunController,
    index: int,
) -> BattleStartCheckpointRecord:
    from dataclasses import replace

    return replace(
        record,
        record_index=index,
        source_controller_provenance=controller.provenance.to_dict(),
        source_battle_controller_provenance=controller.battle.provenance.to_dict(),
        source_non_combat_controller_provenance=(
            controller.non_combat.provenance.to_dict()
        ),
    )


def _record(
    *,
    index: int,
    run_id: str,
    seed: int,
    act: int,
    floor: int,
    room_type: str = "MONSTER",
    encounter_id: str = "Cultist",
) -> BattleStartCheckpointRecord:
    status, payload = unavailable_battle_resource_outcome("test_fixture")
    return BattleStartCheckpointRecord(
        record_index=index,
        source_checkpoint_id=f"{run_id}-checkpoint-{index}",
        source_run_id=run_id,
        source_seed=seed,
        source_battle_index=index,
        structural_metadata={
            "ascension": 20,
            "act": act,
            "floor": floor,
            "room_type": room_type,
            "encounter_id": encounter_id,
            "seed": seed,
            "source_kind": "natural_run",
            "distribution_kind": "natural_run",
            "source_run_id": run_id,
            "source_battle_index": index,
        },
        source_controller_provenance=_default_controller().provenance.to_dict(),
        source_battle_controller_provenance=(
            _default_controller().battle.provenance.to_dict()
        ),
        source_non_combat_controller_provenance=(
            _default_controller().non_combat.provenance.to_dict()
        ),
        action_trace=(),
        snapshot_observation=(float(floor),),
        snapshot_raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "outcome": "UNDECIDED",
            "ascension": 20,
            "act": act,
            "floor_num": floor,
            "room_type": room_type,
            "encounter_id": encounter_id,
        },
        battle_completed=False,
        completed_battle_resource_outcome_status=status,
        completed_battle_resource_outcome=payload,
        public_context_status="legacy_unavailable",
        public_run_context={},
    )


def _summary(
    *,
    run_id: str,
    seed: int,
    final_floor: float,
    final_act: int,
    battle_count: int,
    max_battle_start_floor: float | None = None,
    max_battle_start_act: int | None = None,
) -> SourceRunSummary:
    return SourceRunSummary(
        source_run_id=run_id,
        source_seed=seed,
        terminal=True,
        outcome="PLAYER_LOSS",
        final_floor=final_floor,
        final_act=final_act,
        final_screen_state="BATTLE",
        final_battle_active=False,
        captured_battle_start_count=battle_count,
        completed_battle_count=0,
        max_battle_start_floor=(
            final_floor if max_battle_start_floor is None else max_battle_start_floor
        ),
        max_battle_start_act=(
            final_act if max_battle_start_act is None else max_battle_start_act
        ),
        problem_count=0,
    )


def _write_pool_and_coverage(
    tmp_path: Path,
    label: str,
    pool: NaturalBattleStartPool,
) -> tuple[Path, Path]:
    pool_path = tmp_path / f"{label}-pool.jsonl"
    coverage_path = tmp_path / f"{label}-coverage.json"
    with pool_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)
    restore_report = BattleStartPoolRestoreReport(
        checkpoint_count=len(pool.records),
        requested_limit=0,
        restored_count=len(pool.records),
        native_restored_count=0,
        replay_restored_count=len(pool.records),
        context_compared_count=0,
        context_matched_count=0,
        context_legacy_unavailable_count=len(pool.records),
        context_mismatch_count=0,
    )
    report = build_a20_battle_start_coverage_report(
        pool,
        restore_report=restore_report,
        command_config=A20CoverageCommandConfig(
            gate_config=TrainingScaleGateConfig(
                min_records_per_ascension_act=1,
                min_unique_sources_per_ascension_act=1,
            )
        ),
        input_artifacts={
            "natural_pool": {
                "path": str(pool_path),
                "sha256": _sha256(pool_path),
                "record_count": len(pool.records),
            }
        },
    )
    with coverage_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_battle_start_coverage_report_json(report, stream)
    return pool_path, coverage_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
