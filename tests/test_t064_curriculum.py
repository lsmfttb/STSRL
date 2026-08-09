from __future__ import annotations

import hashlib
from io import StringIO
import json
from dataclasses import replace

import pytest

from sts_combat_rl.commands import t064_curriculum as curriculum_command
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.t064_curriculum import (
    ARM_CURRICULUM,
    ARM_STATIC,
    BUCKET_ANCHOR,
    BUCKET_MEDIUM,
    BUCKET_STRONG,
    TRAINING_RUN_ORDER,
    TRANSFER_GATE_NAMES,
    action_trace_identity_sha256,
    build_ordered_batch_plan,
    build_transfer_decision,
    canonical_json_bytes,
    complete_source_identity,
    contiguous_ranges,
    dump_compact_json,
    select_curriculum_buckets,
    source_adequacy,
    source_descriptor,
    validate_compact_document,
    validate_exposure_parity,
    validate_training_run_report,
)


def _record(*, trace: tuple[dict[str, object], ...] | None = None):
    return BattleStartCheckpointRecord(
        record_index=0,
        source_checkpoint_id="checkpoint",
        source_run_id="seed-1-run-0",
        source_seed=1,
        source_battle_index=0,
        structural_metadata={
            "ascension": 20,
            "act": 2,
            "room_type": "MONSTER",
            "encounter_id": "SNECKO",
            "assistance_level": "assist_hp75_potion",
        },
        source_controller_provenance={"kind": "routed"},
        source_battle_controller_provenance={"kind": "oracle"},
        source_non_combat_controller_provenance={"kind": "driver"},
        action_trace=trace
        or (
            {
                "action_id": "play:Strike",
                "kind": "play",
                "label": "Strike",
                "occurrence": 0,
                "stable_id": '{"action_id":"play:Strike","occurrence":0}',
            },
        ),
        snapshot_observation=(1.0,),
        snapshot_raw={"screen_state": "BATTLE"},
        battle_outcome="PLAYER_VICTORY",
        battle_completed=True,
        completed_battle_resource_outcome_status="available",
        completed_battle_resource_outcome={"schema_id": "structured-battle-outcome-v1"},
        distribution_kind="assisted_run",
        public_context_status="available",
        public_run_context={"schema_id": "public-run-context-v1"},
    )


def _descriptor(component: str, identity: str, *, act: int = 1, stratum: int = 1):
    return {
        "component": component,
        "complete_identity_sha256": identity,
        "act": act,
        "room_type": "MONSTER",
        "encounter_id": f"encounter-{stratum}",
        "floor_bucket": stratum,
        "exclusion_reasons": [],
    }


def test_complete_source_identity_reuses_occurrence_safe_trace_exactly() -> None:
    record = _record()
    identity = complete_source_identity(record)
    expected_rows = [
        {"decision_index": 0, "selected_action": dict(record.action_trace[0])}
    ]
    assert (
        identity["action_trace_identity"]
        == hashlib.sha256(canonical_json_bytes(expected_rows)).hexdigest()
    )
    assert identity["assistance_level"] == "assist_hp75_potion"
    assert identity["source_arm"] == ""


@pytest.mark.parametrize(
    "trace",
    [
        ({"stable_id": "x", "occurrence": None},),
        ({"stable_id": "", "occurrence": 0},),
        ({"stable_id": "x", "occurrence": -1},),
    ],
)
def test_trace_fallback_fails_closed(trace) -> None:
    with pytest.raises(ValueError):
        action_trace_identity_sha256(_record(trace=trace))


def test_bucket_selection_is_deterministic_holdout_excluding_and_stratified() -> None:
    rows = []
    rows.extend(
        _descriptor("assist_hp75_potion", f"{index:064x}", act=2)
        for index in range(1, 170)
    )
    rows.extend(
        _descriptor("assist_hp50", f"{index:064x}", act=2)
        for index in range(1000, 1040)
    )
    rows.extend(
        _descriptor("assist_hp50_potion_elite_boss", f"{index:064x}", act=2)
        for index in range(2000, 2040)
    )
    rows.extend(
        _descriptor("assist_0", f"{index:064x}", stratum=index % 4)
        for index in range(3000, 3300)
    )
    holdout = f"{1:064x}"
    first = select_curriculum_buckets(rows, holdout_identity_sha256s={holdout})
    second = select_curriculum_buckets(rows, holdout_identity_sha256s={holdout})
    assert first == second
    assert len(first[BUCKET_STRONG]) == 160
    assert holdout not in {
        row["complete_identity_sha256"] for row in first[BUCKET_STRONG]
    }
    assert len(first[BUCKET_MEDIUM]) == 64
    assert len(first[BUCKET_ANCHOR]) == 256
    assert source_adequacy(first)


def test_batch_plans_have_exact_exposure_parity_and_different_order() -> None:
    selected = {
        BUCKET_STRONG: [_descriptor("s", f"{index:064x}") for index in range(2)],
        BUCKET_MEDIUM: [_descriptor("m", f"{index + 10:064x}") for index in range(3)],
        BUCKET_ANCHOR: [_descriptor("a", f"{index + 20:064x}") for index in range(4)],
    }
    static = build_ordered_batch_plan(selected, seed=64001, arm=ARM_STATIC)
    curriculum = build_ordered_batch_plan(selected, seed=64001, arm=ARM_CURRICULUM)
    validate_exposure_parity(
        [
            static,
            curriculum,
            build_ordered_batch_plan(selected, seed=64002, arm=ARM_STATIC),
            build_ordered_batch_plan(selected, seed=64002, arm=ARM_CURRICULUM),
        ]
    )
    assert len(static["ordered_batches"]) == 900
    assert all(len(batch) == 32 for batch in static["ordered_batches"])
    assert static["batch_plan_sha256"] != curriculum["batch_plan_sha256"]
    assert (
        static["per_source_exposure_counts"] == curriculum["per_source_exposure_counts"]
    )


def test_frozen_range_and_terminal_decision_truth_table() -> None:
    assert contiguous_ranges(21) == (
        "0:2",
        "2:4",
        "4:6",
        "6:8",
        "8:10",
        "10:11",
        "11:12",
        "12:13",
        "13:14",
        "14:15",
        "15:16",
        "16:17",
        "17:18",
        "18:19",
        "19:20",
        "20:21",
    )
    transfer = build_transfer_decision(
        source_adequate=True,
        experiment_complete=True,
        transfer_gates={name: True for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    assert transfer["terminal_case"] == "Case A"
    negative = build_transfer_decision(
        source_adequate=True,
        experiment_complete=True,
        transfer_gates={
            name: False if name == TRANSFER_GATE_NAMES[0] else True
            for name in TRANSFER_GATE_NAMES
        },
        diagnostics={},
    )
    assert negative["terminal_case"] == "Case B"
    incomplete = build_transfer_decision(
        source_adequate=True,
        experiment_complete=False,
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
        problems=("missing",),
    )
    assert incomplete["terminal_case"] == "INCOMPLETE"
    assert "recommendation" not in incomplete
    with pytest.raises(ValueError, match="exactly the six"):
        build_transfer_decision(
            source_adequate=True,
            experiment_complete=True,
            transfer_gates={},
            diagnostics={},
        )


def test_aggregate_training_report_cardinality_order_and_canonical_writer() -> None:
    report = {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": [
            {
                "arm": arm,
                "seed": seed,
                "initialization_sha256": "a" * 64,
                "configuration": {},
                "trainer_input_sha256": "b" * 64,
                "batch_plan_sha256": "c" * 64,
                "per_bucket_exposure_counts": {},
                "per_source_exposure_counts": {},
                "checkpoint": {"path": "checkpoint.pt", "sha256": "d" * 64, "bytes": 1},
                "checkpoint_metadata_linkage": {},
                "completion_status": "complete",
                "problems": [],
            }
            for arm, seed in TRAINING_RUN_ORDER
        ],
    }
    assert validate_training_run_report(report) == report
    report["runs"] = list(reversed(report["runs"]))
    with pytest.raises(ValueError):
        validate_training_run_report(report)
    decision = build_transfer_decision(
        source_adequate=False,
        experiment_complete=False,
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    stream = StringIO()
    dump_compact_json(decision, stream)
    assert stream.getvalue().endswith("\n")
    assert json.loads(stream.getvalue())["terminal_case"] == "Case B"


@pytest.mark.parametrize("floor", [None, True, "12", 0, 57])
def test_source_descriptor_rejects_invalid_floor(floor: object) -> None:
    record = _record()
    record.structural_metadata["floor"] = floor
    with pytest.raises(ValueError, match="floor"):
        source_descriptor(
            record, component="assist_hp75_potion", source_path="pool.jsonl"
        )


def test_source_descriptor_uses_exact_floor_identity_mapping() -> None:
    record = _record()
    record.structural_metadata["floor"] = 56
    descriptor = source_descriptor(
        record, component="assist_hp75_potion", source_path="pool.jsonl"
    )
    assert descriptor["floor_bucket"] == 56


def test_complete_identity_rejects_wrong_typed_required_fields() -> None:
    record = replace(_record(), source_seed=True)
    with pytest.raises(ValueError, match="source_seed"):
        complete_source_identity(record)


def test_source_adequacy_requires_zero_duplicate_and_holdout_counts() -> None:
    selected = {
        BUCKET_STRONG: [
            _descriptor("strong", f"{index:064x}", act=2) for index in range(128)
        ],
        BUCKET_MEDIUM: [],
        BUCKET_ANCHOR: [
            _descriptor("anchor", f"{index + 1000:064x}") for index in range(256)
        ],
    }
    assert source_adequacy(selected)
    assert not source_adequacy(selected, duplicate_complete_identity_count=1)
    assert not source_adequacy(selected, holdout_overlap_count=1)


def test_compact_documents_fail_closed_on_required_fields() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        validate_compact_document(
            {"schema_id": "t064-transfer-decision-v1", "format_version": 1}
        )


def test_source_inadequacy_skips_batch_plans_and_forms_valid_case_b(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool_paths = {
        name: tmp_path / f"{name}.jsonl"
        for name in (
            "assist_0",
            "assist_hp50",
            "assist_hp50_potion_elite_boss",
            "assist_hp75_potion",
        )
    }
    for path in (
        *pool_paths.values(),
        tmp_path / "scale.json",
        tmp_path / "initial.pt",
    ):
        path.write_bytes(b"fixture")

    def fake_identity(path, expected_sha256):
        return {
            "path": str(path),
            "sha256": expected_sha256,
            "bytes": path.stat().st_size,
        }

    def fake_pool(path, *, component):
        rows = (
            [_descriptor(component, f"{len(component):064x}", act=1)]
            if component == "assist_0"
            else []
        )
        return {
            "schema_id": "assisted-complete-run-source-pool-v1",
            "format_version": 1,
            "record_count": len(rows),
        }, rows

    monkeypatch.setattr(curriculum_command, "_identity", fake_identity)
    monkeypatch.setattr(curriculum_command, "stream_assisted_pool_records", fake_pool)
    monkeypatch.setattr(
        curriculum_command,
        "load_fixed_cohort_jsonl",
        lambda _stream: type("Cohort", (), {"records": ()})(),
    )
    manifest = curriculum_command.build_curriculum_manifest(
        pool_paths=pool_paths,
        pool_sha256s={name: "a" * 64 for name in pool_paths},
        scale_manifest_path=tmp_path / "scale.json",
        scale_manifest_sha256="b" * 64,
        holdouts=(),
        initialization_checkpoint_path=tmp_path / "initial.pt",
        initialization_checkpoint_sha256="c" * 64,
        code_commit="d" * 40,
        output_path=tmp_path / "t064-curriculum-manifest.json",
    )
    assert manifest["source_adequacy"] is False
    assert manifest["batch_plans"] == []
    assert manifest["batch_plan_status"] == "not_run_source_inadequate"
    decision = build_transfer_decision(
        source_adequate=False,
        experiment_complete=False,
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    assert decision["terminal_case"] == "Case B"
