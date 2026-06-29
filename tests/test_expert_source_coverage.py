from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from dataclasses import replace
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
from sts_combat_rl.sim.expert_source_coverage import (
    build_expert_source_coverage_comparison_report,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.policy import ExpertNonCombatDriver, StochasticNonCombatDriver
from sts_combat_rl.sim.resource_outcome import unavailable_battle_resource_outcome
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


def test_expert_source_coverage_cli_reports_required_three_arm_gate(
    tmp_path: Path,
    capsys,
) -> None:
    stochastic = _pool(
        controller=_controller("stochastic", 20),
        run_prefix="stochastic",
        records=[
            _record(
                index=0,
                run_id="stochastic-run-0",
                seed=1,
                act=1,
                floor=16,
                room_type="BOSS",
                encounter_id="Slime Boss",
            ),
        ],
    )
    expert_s20 = _pool(
        controller=_controller("expert", 20),
        run_prefix="expert-s20",
        records=[
            _record(
                index=0,
                run_id="expert-s20-run-0",
                seed=1001,
                act=1,
                floor=16,
                room_type="BOSS",
                encounter_id="Slime Boss",
            ),
            _record(
                index=1,
                run_id="expert-s20-run-0",
                seed=1001,
                act=1,
                floor=16,
                room_type="BOSS",
                encounter_id="Hexaghost",
            ),
            _record(
                index=2,
                run_id="expert-s20-run-1",
                seed=1002,
                act=2,
                floor=18,
                encounter_id="Chosen",
            ),
        ],
    )
    expert_s100 = _pool(
        controller=_controller("expert", 100),
        run_prefix="expert-s100",
        records=[
            _record(
                index=0,
                run_id="expert-s100-run-0",
                seed=2001,
                act=1,
                floor=16,
                room_type="BOSS",
                encounter_id="Hexaghost",
            ),
            _record(
                index=1,
                run_id="expert-s100-run-1",
                seed=2002,
                act=2,
                floor=18,
                encounter_id="Chosen",
            ),
            _record(
                index=2,
                run_id="expert-s100-run-2",
                seed=2003,
                act=3,
                floor=35,
                encounter_id="Darklings",
            ),
        ],
    )
    stochastic_paths = _write_pool_and_coverage(tmp_path, "stochastic", stochastic)
    expert_s20_paths = _write_pool_and_coverage(tmp_path, "expert-s20", expert_s20)
    expert_s100_paths = _write_pool_and_coverage(tmp_path, "expert-s100", expert_s100)
    report_path = tmp_path / "expert-source-coverage.json"

    assert (
        main(
            [
                "--expert-source-coverage-report",
                str(report_path),
                "--expert-source-arm",
                "stochastic_s20",
                str(stochastic_paths[0]),
                str(stochastic_paths[1]),
                "--expert-source-arm",
                "expert_s20",
                str(expert_s20_paths[0]),
                str(expert_s20_paths[1]),
                "--expert-source-arm",
                "expert_s100",
                str(expert_s100_paths[0]),
                str(expert_s100_paths[1]),
                "--log-file",
                "-",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert captured.out == ""
    assert "Expert non-combat source-coverage comparison" in captured.err
    assert payload["schema_id"] == "expert-non-combat-source-coverage-comparison-v1"
    assert payload["command_passed"] is True
    assert payload["comparison"]["scale_target_met"] is True
    assert payload["comparison"]["expert_s20_reachability_gate_met"] is True
    assert payload["comparison"]["expert_s20_later_act_delta_vs_stochastic_s20"] == 1
    expert_arm = next(arm for arm in payload["arms"] if arm["role"] == "expert_s20")
    assert expert_arm["controller"]["non_combat_controller_name"] == (
        "expert_non_combat_v1"
    )


def test_expert_source_coverage_report_fails_closed_on_wrong_arm_contract(
    tmp_path: Path,
) -> None:
    pool = _pool(
        controller=_controller("stochastic", 20),
        run_prefix="wrong",
        records=[
            _record(index=0, run_id="wrong-run-0", seed=1, act=1, floor=1),
        ],
    )
    pool_path, coverage_path = _write_pool_and_coverage(tmp_path, "wrong", pool)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    artifact_identity = {
        "pool_path": str(pool_path),
        "pool_sha256": _sha256(pool_path),
        "coverage_report_path": str(coverage_path),
        "coverage_report_sha256": _sha256(coverage_path),
        "coverage_record_count": 1,
    }

    report = build_expert_source_coverage_comparison_report(
        [
            ("stochastic_s20", pool, coverage, artifact_identity),
            ("expert_s20", pool, coverage, artifact_identity),
            ("expert_s100", pool, coverage, artifact_identity),
        ]
    )

    assert report.command_passed is False
    assert any(
        "non-combat controller name" in problem for problem in report.command_problems
    )
    assert any(
        "oracle search simulations" in problem for problem in report.command_problems
    )


def _controller(driver: str, simulations: int) -> RoutedRunController:
    non_combat = (
        ExpertNonCombatDriver(seed=1)
        if driver == "expert"
        else StochasticNonCombatDriver(seed=1)
    )
    return RoutedRunController(
        battle=OracleSearchController(simulations=simulations),
        non_combat=PolicyController(non_combat),
    )


def _pool(
    *,
    controller: RoutedRunController,
    run_prefix: str,
    records: list[BattleStartCheckpointRecord],
) -> NaturalBattleStartPool:
    by_run: dict[str, list[BattleStartCheckpointRecord]] = defaultdict(list)
    for record in records:
        by_run[record.source_run_id].append(record)
    summaries = [
        _summary(
            run_id=run_id,
            seed=run_records[0].source_seed,
            battle_count=len(run_records),
            max_floor=max(
                float(record.structural_metadata["floor"]) for record in run_records
            ),
            max_act=max(
                int(record.structural_metadata["act"]) for record in run_records
            ),
        )
        for run_id, run_records in sorted(by_run.items())
    ]
    filler_index = 0
    while len(summaries) < 1000:
        run_id = f"{run_prefix}-source-run-{filler_index}"
        filler_index += 1
        if run_id in by_run:
            continue
        summaries.append(
            _summary(
                run_id=run_id,
                seed=10_000 + filler_index,
                battle_count=0,
                max_floor=None,
                max_act=None,
            )
        )
    return NaturalBattleStartPool(
        source_run_count=len(summaries),
        terminal_run_count=len(summaries),
        truncated_run_count=0,
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
        source_controller_provenance=_controller("stochastic", 20).provenance.to_dict(),
        source_battle_controller_provenance=(
            _controller("stochastic", 20).battle.provenance.to_dict()
        ),
        source_non_combat_controller_provenance=(
            _controller("stochastic", 20).non_combat.provenance.to_dict()
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
    battle_count: int,
    max_floor: float | None,
    max_act: int | None,
) -> SourceRunSummary:
    return SourceRunSummary(
        source_run_id=run_id,
        source_seed=seed,
        terminal=True,
        outcome="PLAYER_LOSS",
        final_floor=18.0 if battle_count else 1.0,
        final_act=2 if battle_count else 1,
        final_screen_state="BATTLE",
        final_battle_active=False,
        captured_battle_start_count=battle_count,
        completed_battle_count=0,
        max_battle_start_floor=max_floor,
        max_battle_start_act=max_act,
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
