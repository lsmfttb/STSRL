from __future__ import annotations

import hashlib
from io import StringIO
import json

import pytest

from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.t064_curriculum import (
    ARM_CURRICULUM,
    ARM_STATIC,
    BUCKET_ANCHOR,
    BUCKET_MEDIUM,
    BUCKET_STRONG,
    TRAINING_RUN_ORDER,
    action_trace_identity_sha256,
    build_ordered_batch_plan,
    build_transfer_decision,
    canonical_json_bytes,
    complete_source_identity,
    contiguous_ranges,
    dump_compact_json,
    select_curriculum_buckets,
    source_adequacy,
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


def _descriptor(component: str, identity: str, *, act: int = 1, stratum: int = 0):
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
    assert identity["action_trace_identity"] == hashlib.sha256(
        canonical_json_bytes(expected_rows)
    ).hexdigest()
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
    curriculum = build_ordered_batch_plan(
        selected, seed=64001, arm=ARM_CURRICULUM
    )
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
    assert static["per_source_exposure_counts"] == curriculum[
        "per_source_exposure_counts"
    ]


def test_frozen_range_and_terminal_decision_truth_table() -> None:
    assert contiguous_ranges(21) == (
        "0:2", "2:4", "4:6", "6:8", "8:10", "10:11", "11:12", "12:13",
        "13:14", "14:15", "15:16", "16:17", "17:18", "18:19", "19:20", "20:21",
    )
    transfer = build_transfer_decision(
        source_adequate=True,
        experiment_complete=True,
        transfer_gates={"g1": True, "g2": True},
        diagnostics={},
    )
    assert transfer["terminal_case"] == "Case A"
    negative = build_transfer_decision(
        source_adequate=True,
        experiment_complete=True,
        transfer_gates={"g1": False},
        diagnostics={},
    )
    assert negative["terminal_case"] == "Case B"
    incomplete = build_transfer_decision(
        source_adequate=True,
        experiment_complete=False,
        transfer_gates={"g1": None},
        diagnostics={},
        problems=("missing",),
    )
    assert incomplete["terminal_case"] == "INCOMPLETE"
    assert "recommendation" not in incomplete


def test_aggregate_training_report_cardinality_order_and_canonical_writer() -> None:
    report = {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": [{"arm": arm, "seed": seed} for arm, seed in TRAINING_RUN_ORDER],
    }
    assert validate_training_run_report(report) == report
    report["runs"] = list(reversed(report["runs"]))
    with pytest.raises(ValueError):
        validate_training_run_report(report)
    decision = build_transfer_decision(
        source_adequate=False,
        experiment_complete=False,
        transfer_gates={},
        diagnostics={},
    )
    stream = StringIO()
    dump_compact_json(decision, stream)
    assert stream.getvalue().endswith("\n")
    assert json.loads(stream.getvalue())["terminal_case"] == "Case B"
