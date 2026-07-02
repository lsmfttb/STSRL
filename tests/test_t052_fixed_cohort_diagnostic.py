from __future__ import annotations

import json

import pytest

from sts_combat_rl.cli import build_parser, main
from sts_combat_rl.commands.t052_fixed_cohort_diagnostic import (
    run_t052_fixed_cohort_extraction_from_paths,
    run_t052_retention_manifest_from_paths,
)
from sts_combat_rl.sim.battle_start_pool import (
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    dump_natural_battle_start_pool_jsonl,
    sha256_file,
)
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl


def test_t052_extraction_selects_boss_and_later_act_sources(tmp_path) -> None:
    baseline_pool = _write_pool(
        tmp_path / "baseline.jsonl",
        _pool(
            [
                _record(
                    0,
                    act=1,
                    room_type="BOSS",
                    encounter_id="Hexaghost",
                    checkpoint_id="baseline-boss",
                ),
                _record(
                    1,
                    act=1,
                    room_type="MONSTER",
                    encounter_id="Jaw Worm",
                    checkpoint_id="baseline-monster",
                ),
            ],
            name="baseline",
        ),
    )
    post_pool = _write_pool(
        tmp_path / "post.jsonl",
        _pool(
            [
                _record(
                    0,
                    act=1,
                    room_type="BOSS",
                    encounter_id="Slime Boss",
                    checkpoint_id="post-boss",
                ),
                _record(
                    1,
                    act=2,
                    room_type="MONSTER",
                    encounter_id="Chosen",
                    checkpoint_id="duplicate-later",
                ),
            ],
            name="post",
        ),
    )
    root_pool = _write_pool(
        tmp_path / "root.jsonl",
        _pool(
            [
                _record(
                    0,
                    act=1,
                    room_type="BOSS",
                    encounter_id="Guardian",
                    checkpoint_id="root-boss",
                ),
                _record(
                    1,
                    act=2,
                    room_type="ELITE",
                    encounter_id="Book of Stabbing",
                    checkpoint_id="duplicate-later",
                ),
            ],
            name="root",
        ),
    )
    t051_manifest = _write_text(tmp_path / "t051-manifest.json", "{}\n")
    reachability = _write_text(tmp_path / "reachability.json", "{}\n")
    checkpoint = _write_text(tmp_path / "checkpoint.pt", "checkpoint\n")

    cohort_path = tmp_path / "t052-cohort.jsonl"
    summary_path = tmp_path / "t052-summary.json"
    summary = run_t052_fixed_cohort_extraction_from_paths(
        output_path=cohort_path,
        source_arm_specs=[
            [
                "baseline",
                "baseline_oracle_search_v1",
                str(baseline_pool),
                sha256_file(baseline_pool),
            ],
            [
                "post_search",
                "post_search_model_guided_v2",
                str(post_pool),
                sha256_file(post_pool),
            ],
            [
                "root_prior",
                "root_prior_guided_v1",
                str(root_pool),
                sha256_file(root_pool),
            ],
        ],
        verify_artifact_specs=[
            ["t051_retention_manifest", str(t051_manifest), sha256_file(t051_manifest)],
            ["t051_reachability_report", str(reachability), sha256_file(reachability)],
            ["checkpoint", str(checkpoint), sha256_file(checkpoint)],
        ],
        summary_path=summary_path,
    )

    assert summary["command_passed"] is True
    assert summary["cohort"]["record_count"] == 4
    assert summary["counts"]["by_source_arm_label"] == {
        "baseline_oracle_search_v1": 1,
        "post_search_model_guided_v2": 2,
        "root_prior_guided_v1": 1,
    }
    assert summary["counts"]["by_selection_reason"] == {
        "act1_boss": 3,
        "act2_plus": 1,
    }
    assert len(summary["duplicate_omissions"]) == 1
    assert summary["duplicate_omissions"][0]["source_checkpoint_id"] == (
        "duplicate-later"
    )

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    assert cohort.unique_source_count == 4
    assert cohort.selection_config.stratum_fields == (
        "ascension",
        "act",
        "room_type",
        "encounter_id",
        "t051_source_arm_label",
    )
    root_record = [
        record
        for record in cohort.records
        if record.structural_metadata["t051_source_arm_label"] == "root_prior_guided_v1"
    ][0]
    assert root_record.structural_metadata[
        "t051_completed_battle_resource_outcome_status"
    ] == ("legacy_unavailable")
    assert root_record.checkpoint_information_regime == CHECKPOINT_INFORMATION_REGIME

    written = json.loads(summary_path.read_text(encoding="utf-8"))
    assert written["cohort"]["identity"] == cohort.identity


def test_t052_extraction_fails_on_source_pool_hash_mismatch(tmp_path) -> None:
    pool_path = _write_pool(
        tmp_path / "baseline.jsonl",
        _pool([_record(0, act=1, room_type="BOSS")], name="baseline"),
    )
    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t052_fixed_cohort_extraction_from_paths(
            output_path=tmp_path / "cohort.jsonl",
            source_arm_specs=[
                ["baseline", "baseline", str(pool_path), "0" * 64],
                ["post_search", "post", str(pool_path), sha256_file(pool_path)],
                ["root_prior", "root", str(pool_path), sha256_file(pool_path)],
            ],
            verify_artifact_specs=[],
            summary_path=tmp_path / "summary.json",
        )


def test_t052_retention_manifest_records_artifact_identities(tmp_path) -> None:
    cohort = _write_text(tmp_path / "cohort.jsonl", '{"type": "metadata"}\n')
    summary = _write_text(
        tmp_path / "summary.json",
        '{"schema_id": "t052-t051-boss-later-act-fixed-cohort-summary-v1"}\n',
    )
    comparison = _write_text(
        tmp_path / "comparison.jsonl",
        '{"type": "metadata", "metadata": {"schema_id": "root-prior-guided-search-comparison-v1"}}\n',
    )
    log = _write_text(tmp_path / "comparison.err", "comparison log\n")

    manifest = run_t052_retention_manifest_from_paths(
        output_path=tmp_path / "retention.json",
        artifact_specs=[
            ["cohort", str(cohort), "fixed-cohort-v3-jsonl"],
            [
                "summary",
                str(summary),
                "t052-t051-boss-later-act-fixed-cohort-summary-v1",
            ],
            ["comparison", str(comparison), "root-prior-guided-search-comparison-v1"],
            ["comparison_log", str(log), "stderr-log"],
        ],
        command_specs=[["comparison", "python -m sts_combat_rl.cli ..."]],
        stage_specs=[["comparison", "16", "16", "0:4", "12.5"]],
        note_specs=[["recommended_next_task", "publish one follow-up diagnostic task"]],
    )

    assert manifest["schema_id"] == "t052-retention-manifest-v1"
    assert len(manifest["artifacts"]) == 4
    assert manifest["runtime_stages"][0]["workers"] == 16
    assert manifest["runtime_stages"][0]["wall_clock_seconds"] == 12.5
    assert manifest["notes"]["recommended_next_task"] == (
        "publish one follow-up diagnostic task"
    )


def test_t052_cli_parser_accepts_extraction_and_manifest_flags(tmp_path) -> None:
    cohort = tmp_path / "cohort.jsonl"
    summary = tmp_path / "summary.json"
    pool = tmp_path / "pool.jsonl"
    manifest = tmp_path / "retention.json"

    args = build_parser().parse_args(
        [
            "--t052-t051-boss-later-act-fixed-cohort",
            str(cohort),
            "--t052-source-arm",
            "baseline",
            "baseline_oracle_search_v1",
            str(pool),
            "1" * 64,
            "--t052-source-arm",
            "post_search",
            "post_search_model_guided_v2",
            str(pool),
            "2" * 64,
            "--t052-source-arm",
            "root_prior",
            "root_prior_guided_v1",
            str(pool),
            "3" * 64,
            "--t052-verify-artifact",
            "t051_retention_manifest",
            str(tmp_path / "t051.json"),
            "4" * 64,
            "--t052-cohort-summary",
            str(summary),
        ]
    )

    assert args.t052_t051_boss_later_act_fixed_cohort == cohort
    assert args.t052_cohort_summary == summary
    assert args.t052_source_arm[0][0] == "baseline"

    manifest_args = build_parser().parse_args(
        [
            "--t052-retention-manifest",
            str(manifest),
            "--t052-retained-artifact",
            "cohort",
            str(cohort),
            "fixed-cohort-v3-jsonl",
            "--t052-retention-stage",
            "comparison",
            "16",
            "16",
            "0:4",
            "12.5",
        ]
    )

    assert manifest_args.t052_retention_manifest == manifest
    assert manifest_args.t052_retained_artifact == [
        ["cohort", str(cohort), "fixed-cohort-v3-jsonl"]
    ]


def test_t052_cli_main_writes_manifest(tmp_path, capsys) -> None:
    cohort = _write_text(tmp_path / "cohort.jsonl", '{"type": "metadata"}\n')
    output = tmp_path / "retention.json"

    assert (
        main(
            [
                "--t052-retention-manifest",
                str(output),
                "--t052-retained-artifact",
                "cohort",
                str(cohort),
                "fixed-cohort-v3-jsonl",
                "--log-file",
                "-",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "T052 retention manifest" in captured.err
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifacts"][0]["sha256"] == sha256_file(cohort)


def _pool(
    records: list[BattleStartCheckpointRecord],
    *,
    name: str,
) -> NaturalBattleStartPool:
    return NaturalBattleStartPool(
        source_run_count=len(records),
        terminal_run_count=len(records),
        truncated_run_count=0,
        source_controller_provenance=_provenance("routed_run", name),
        records=records,
    )


def _record(
    record_index: int,
    *,
    act: int,
    room_type: str,
    encounter_id: str = "Encounter",
    checkpoint_id: str | None = None,
) -> BattleStartCheckpointRecord:
    run_id = f"seed-{record_index + 1}-run-0"
    return BattleStartCheckpointRecord(
        record_index=record_index,
        source_checkpoint_id=checkpoint_id or f"checkpoint-{record_index}",
        source_run_id=run_id,
        source_seed=record_index + 1,
        source_battle_index=record_index,
        structural_metadata={
            "ascension": 20,
            "act": act,
            "floor": record_index + 1,
            "room_type": room_type,
            "encounter_id": encounter_id,
            "seed": record_index + 1,
            "source_kind": NATURAL_DISTRIBUTION_KIND,
            "distribution_kind": NATURAL_DISTRIBUTION_KIND,
            "source_run_id": run_id,
            "source_battle_index": record_index,
        },
        source_controller_provenance=_provenance("routed_run", "source"),
        source_battle_controller_provenance=_provenance(
            "oracle_battle_search",
            "battle",
        ),
        source_non_combat_controller_provenance=_provenance(
            "decision_policy",
            "non_combat",
        ),
        action_trace=(),
        snapshot_observation=(float(record_index),),
        snapshot_raw={
            "battle_active": True,
            "screen_state": "BATTLE",
            "act": act,
            "room_type": room_type,
        },
        checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
    )


def _provenance(kind: str, name: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": kind,
        "name": name,
        "config": {"information_regime": CHECKPOINT_INFORMATION_REGIME},
    }


def _write_pool(path, pool: NaturalBattleStartPool):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)
    return path


def _write_text(path, text: str):
    path.write_text(text, encoding="utf-8")
    return path
