from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import json
from dataclasses import dataclass, replace
import gc
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import threading
import time

import pytest

from sts_combat_rl.commands import t064_curriculum as curriculum_command
from sts_combat_rl.commands import t064_curriculum_transfer as transfer_command
from sts_combat_rl.commands.t070_search_v2_audit import (
    expected_checkpoint_identity_from_stage_manifest,
)
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.controller_contract import ControllerProvenance
from sts_combat_rl.sim.oracle_teacher import OracleTeacherDataset
from sts_combat_rl.sim.t064_curriculum import (
    ARM_CURRICULUM,
    ARM_STATIC,
    BUCKET_ANCHOR,
    BUCKET_MEDIUM,
    BUCKET_STRONG,
    TRAINING_RUN_ORDER,
    TRANSFER_GATE_NAMES,
    _validate_source_descriptor,
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


def _empty_oracle_teacher_dataset() -> OracleTeacherDataset:
    """A current-schema shard with no rows, suitable for persistence tests."""

    return OracleTeacherDataset(
        native_source_identity={"integration_commit": "test"},
        controller_provenance=ControllerProvenance(
            kind="oracle_battle_search",
            name="test-oracle",
            config={"information_regime": "full_simulator_state_oracle_like"},
        ).to_dict(),
        action_space_config={"include_potions": False},
        source_pool_format_version=1,
        source_pool_controller_provenance={"kind": "test"},
    )


def _complete_source_inadequate_manifest(*, code_commit: str) -> dict[str, object]:
    """Return a compact-reader-valid completed manifest with the real shape."""

    artifact = {"path": "fixture", "sha256": "a" * 64, "bytes": 1}
    return {
        "schema_id": "t064-curriculum-manifest-v1",
        "format_version": 1,
        "task_id": "T064",
        "code_commit": code_commit,
        "native_commit": "b" * 40,
        "input_artifacts": {
            name: dict(artifact)
            for name in (
                "t042_scale_manifest",
                "initialization_checkpoint",
                "assist_0",
                "assist_hp50",
                "assist_hp50_potion_elite_boss",
                "assist_hp75_potion",
            )
        },
        "frozen_holdouts": [],
        "complete_source_audit": {
            "status": "complete",
            "source_count": 0,
            "sources": [],
            "candidate_duplicate_complete_identity_count": 0,
            "candidate_holdout_exclusion_count": 0,
            "selected_duplicate_complete_identity_count": 0,
            "selected_holdout_overlap_count": 0,
            "selected_restore_count": 0,
            "selected_restore_failure_count": 0,
            "selected_restore_failures": [],
        },
        "selected_buckets": {
            bucket: [] for bucket in (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR)
        },
        "selected_sources": [],
        "selected_bucket_counts": {
            bucket: 0 for bucket in (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR)
        },
        "source_adequacy": False,
        "teacher_shard_ranges": list(contiguous_ranges(0)),
        "teacher_worker_count": 16,
        "batch_plans": [],
        "batch_plan_status": "not_run_source_inadequate",
        "exposure_parity": None,
        "t070_stage_manifest": None,
        "problems": [],
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
    assert sum(row["complete_identity_sha256"] == holdout for row in rows) == 1
    assert len(first[BUCKET_MEDIUM]) == 64
    assert len(first[BUCKET_ANCHOR]) == 256
    # The frozen T044 holdout is expected to be present in the candidate T042
    # pool.  It is an exclusion, not a selected-training-set leak.
    assert source_adequacy(
        first,
        selected_duplicate_complete_identity_count=0,
        selected_holdout_overlap_count=0,
    )
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
        source_integrity_valid=True,
        experiment_complete=True,
        complete_source_audit_status="complete",
        transfer_gates={name: True for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    assert transfer["terminal_case"] == "Case A"
    negative = build_transfer_decision(
        source_adequate=True,
        source_integrity_valid=True,
        experiment_complete=True,
        complete_source_audit_status="complete",
        transfer_gates={
            name: False if name == TRANSFER_GATE_NAMES[0] else True
            for name in TRANSFER_GATE_NAMES
        },
        diagnostics={},
    )
    assert negative["terminal_case"] == "Case B"
    incomplete = build_transfer_decision(
        source_adequate=True,
        source_integrity_valid=True,
        experiment_complete=False,
        complete_source_audit_status="pending",
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
        problems=("missing",),
    )
    assert incomplete["terminal_case"] == "INCOMPLETE"
    assert "recommendation" not in incomplete
    with pytest.raises(ValueError, match="exactly the six"):
        build_transfer_decision(
            source_adequate=True,
            source_integrity_valid=True,
            experiment_complete=True,
            complete_source_audit_status="complete",
            transfer_gates={},
            diagnostics={},
        )


@pytest.mark.parametrize(
    ("source_adequate", "experiment_complete", "problems", "unmet"),
    [
        (False, True, (), ()),
        (True, True, ("integrity failure",), ()),
        (True, True, (), ("missing acceptance criterion",)),
    ],
)
def test_transfer_truth_table_rejects_inconsistent_or_failed_case_a_inputs(
    source_adequate: bool,
    experiment_complete: bool,
    problems: tuple[str, ...],
    unmet: tuple[str, ...],
) -> None:
    decision = build_transfer_decision(
        source_adequate=source_adequate,
        source_integrity_valid=True,
        experiment_complete=experiment_complete,
        complete_source_audit_status="complete",
        transfer_gates={name: True for name in TRANSFER_GATE_NAMES},
        diagnostics={},
        problems=problems,
        unmet_acceptance_criteria=unmet,
    )
    assert decision["terminal_case"] == "INCOMPLETE"
    assert "recommendation" not in decision


def test_transfer_reader_rejects_tampered_terminal_case_and_recommendation() -> None:
    decision = build_transfer_decision(
        source_adequate=True,
        source_integrity_valid=True,
        experiment_complete=True,
        complete_source_audit_status="complete",
        transfer_gates={name: True for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    decision["recommendation"] = "T065-learned-non-combat-policy-v1"
    with pytest.raises(ValueError, match="recommendation fails"):
        validate_compact_document(decision)


def test_source_integrity_failure_is_incomplete_and_reader_rejects_forged_case_b() -> (
    None
):
    gates = {name: None for name in TRANSFER_GATE_NAMES}
    coverage_shortfall = build_transfer_decision(
        source_adequate=False,
        source_integrity_valid=True,
        experiment_complete=False,
        complete_source_audit_status="complete",
        transfer_gates=gates,
        diagnostics={},
    )
    assert coverage_shortfall["terminal_case"] == "Case B"

    integrity_failure = build_transfer_decision(
        source_adequate=False,
        source_integrity_valid=False,
        experiment_complete=False,
        complete_source_audit_status="complete",
        transfer_gates=gates,
        diagnostics={},
    )
    assert integrity_failure["terminal_case"] == "INCOMPLETE"
    assert "recommendation" not in integrity_failure
    assert validate_compact_document(integrity_failure) == integrity_failure

    integrity_failure["terminal_case"] = "Case B"
    integrity_failure["recommendation"] = "T065-learned-non-combat-policy-v1"
    with pytest.raises(ValueError, match="terminal case fails"):
        validate_compact_document(integrity_failure)


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
                "trainer_input_bytes": 1,
                "batch_plan_sha256": "c" * 64,
                "per_bucket_exposure_counts": {},
                "per_source_exposure_counts": {},
                "checkpoint": {"path": "checkpoint.pt", "sha256": "d" * 64, "bytes": 1},
                "checkpoint_metadata_linkage": {},
                "run_disposition": "trained_new",
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
        source_integrity_valid=True,
        experiment_complete=False,
        complete_source_audit_status="complete",
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


def test_source_descriptor_validator_rehashes_identity_and_rejects_structural_types() -> (
    None
):
    record = _record()
    record.structural_metadata["floor"] = 12
    descriptor = source_descriptor(
        record, component="assist_hp75_potion", source_path="pool.jsonl"
    )
    _validate_source_descriptor(descriptor, "fixture")
    descriptor["complete_identity_sha256"] = "a" * 64
    descriptor["complete_identity"]["complete_identity_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        _validate_source_descriptor(descriptor, "fixture")
    descriptor = source_descriptor(
        record, component="assist_hp75_potion", source_path="pool.jsonl"
    )
    descriptor["act"] = True
    with pytest.raises(ValueError, match="act"):
        _validate_source_descriptor(descriptor, "fixture")


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
    assert not source_adequacy(selected, selected_duplicate_complete_identity_count=1)
    assert not source_adequacy(selected, selected_holdout_overlap_count=1)


def test_compact_documents_fail_closed_on_required_fields() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        validate_compact_document(
            {"schema_id": "t064-transfer-decision-v1", "format_version": 1}
        )


def test_stage_summary_rejects_required_field_type_mutations() -> None:
    stage = {
        "name": "source_audit",
        "status": "complete",
        "command": "python audit.py",
        "code_commit": "a" * 40,
        "native_commit": "b" * 40,
        "inputs": {},
        "outputs": {},
        "workers": 16,
        "shards": 16,
        "ranges": ["0:0"],
        "return_codes": [0],
        "wall_clock_seconds": 1.0,
        "failure_count": 0,
        "referenced_artifacts": [],
        "failed_attempts": [],
        "retained_log_paths": [],
    }
    payload = {
        "schema_id": "t064-stage-summary-v1",
        "format_version": 1,
        "reuse_inventory": [],
        "stages": [stage],
        "retention_reason": "T064 review evidence",
        "downstream_consumer": "T065",
        "deletion_condition": "after acceptance",
        "problems": [],
    }
    assert validate_compact_document(payload) == payload
    payload["stages"][0]["workers"] = "16"
    with pytest.raises(ValueError, match="workers"):
        validate_compact_document(payload)
    payload["stages"][0]["workers"] = 16
    payload["stages"][0]["wall_clock_seconds"] = float("inf")
    with pytest.raises(ValueError, match="wall clock"):
        validate_compact_document(payload)


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
        rows = []
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
    assert manifest["teacher_shard_ranges"] == ["0:0"] * 16
    pending = build_transfer_decision(
        source_adequate=False,
        source_integrity_valid=True,
        experiment_complete=False,
        complete_source_audit_status="pending",
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    assert pending["terminal_case"] == "INCOMPLETE"
    finalized = curriculum_command.finalize_source_audit(
        manifest_path=tmp_path / "t064-curriculum-manifest.json",
        restore_results=(),
    )
    finalized["source_adequacy"] = True
    with pytest.raises(ValueError, match="source adequacy"):
        validate_compact_document(finalized)
    finalized["source_adequacy"] = False
    finalized["complete_source_audit"]["selected_restore_failure_count"] = 1
    with pytest.raises(ValueError, match="failure count"):
        validate_compact_document(finalized)
    finalized["complete_source_audit"]["selected_restore_failure_count"] = 0
    for field in (
        "candidate_duplicate_complete_identity_count",
        "selected_duplicate_complete_identity_count",
        "selected_holdout_overlap_count",
    ):
        finalized["complete_source_audit"][field] = 1
        with pytest.raises(ValueError, match="duplicate|overlaps"):
            validate_compact_document(finalized)
        finalized["complete_source_audit"][field] = 0
    decision = build_transfer_decision(
        source_adequate=False,
        source_integrity_valid=True,
        experiment_complete=False,
        complete_source_audit_status=finalized["complete_source_audit"]["status"],
        transfer_gates={name: None for name in TRANSFER_GATE_NAMES},
        diagnostics={},
    )
    assert decision["terminal_case"] == "Case B"
    repository = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(repository / "tests"))
    )
    expected_executions = {
        "stage2_teacher": 1,
        "stage3_trainer": 1,
        "stage4_training": 1,
        "stage5_t044": 8,
        "stage6_t070": 4,
        "stage7_aggregate": 1,
    }
    for stage, expected_count in expected_executions.items():
        completed = subprocess.run(
            [
                sys.executable,
                str(repository / "scripts" / "t064_curriculum_transfer.py"),
                "--dry-run-manifest",
                str(tmp_path / "t064-curriculum-manifest.json"),
                "--code-commit",
                "d" * 40,
                "--stage",
                stage,
                "--mock-execute",
                "--attempt-root",
                str(tmp_path / "mock-attempt" / stage),
            ],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        payload = json.loads(completed.stdout)
        assert len(payload["executions"]) == expected_count


def test_empty_selected_source_pool_is_valid_for_complete_source_inadequacy() -> None:
    pool, selected = curriculum_command.load_selected_source_pool(
        {"selected_sources": []}
    )
    assert selected == []
    assert pool.records == []


def test_stage2_to_7_contract_helpers_allow_producer_head_mismatch_and_preserve_identity_order() -> (
    None
):
    manifest = {
        "code_commit": "a" * 40,
        "complete_source_audit": {
            "status": "complete",
            "selected_restore_failure_count": 0,
        },
        "selected_sources": [
            {
                "complete_identity_sha256": f"{index:064x}",
                "complete_identity": {
                    "source_checkpoint_id": "checkpoint",
                    "source_seed": 1,
                    "source_run_id": f"run-{index}",
                    "source_battle_index": index,
                    "distribution_kind": "assisted_run",
                    "checkpoint_information_regime": "full_simulator_state_oracle_like",
                },
            }
            for index in range(2)
        ],
    }
    transfer_command.validate_resume_manifest(manifest, code_commit="a" * 40)
    transfer_command.validate_resume_manifest(manifest, code_commit="b" * 40)
    pending = {
        **manifest,
        "complete_source_audit": {
            **manifest["complete_source_audit"],
            "status": "static_complete_selected_restore_pending",
        },
    }
    with pytest.raises(ValueError, match="completed selected-source audit"):
        transfer_command.validate_resume_manifest(pending, code_commit="b" * 40)
    failed = {
        **manifest,
        "complete_source_audit": {
            **manifest["complete_source_audit"],
            "selected_restore_failure_count": 1,
        },
    }
    with pytest.raises(ValueError, match="failed selected-source audit"):
        transfer_command.validate_resume_manifest(failed, code_commit="b" * 40)
    identities = [
        row["complete_identity_sha256"] for row in manifest["selected_sources"]
    ]
    assert transfer_command.build_trainer_row_mapping(
        selected_manifest=manifest,
        teacher_source_hashes=identities,
        trainer_source_hashes=identities,
    ) == {identities[0]: 0, identities[1]: 1}
    with pytest.raises(ValueError, match="trainer identity"):
        transfer_command.build_trainer_row_mapping(
            selected_manifest=manifest,
            teacher_source_hashes=identities,
            trainer_source_hashes=list(reversed(identities)),
        )


def test_t044_t070_reuse_contracts_use_persisted_roles_and_frozen_ranges() -> None:
    config = {
        "controller_roles": dict(
            zip(("a", "b", "c", "d"), transfer_command.T044_CONTROLLER_ROLES)
        ),
        "cohort_identity": "cohort",
        "cohort_record_count": 21,
        "max_battle_steps": 200,
        "run_scale": "fixed",
        "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
    }

    def arm(role):
        return SimpleNamespace(
            role=role, report=SimpleNamespace(problems=[], battle_results=[1] * 21)
        )

    report = SimpleNamespace(
        comparison_config=config,
        arms=tuple(arm(role) for role in transfer_command.T044_CONTROLLER_ROLES),
        evaluation_successful=True,
    )

    assert transfer_command.validate_t044_reuse(
        report, cohort_identity="cohort", cohort_count=21
    )
    config["action_space"]["allow_excluded_fallback"] = False
    assert not transfer_command.validate_t044_reuse(
        report, cohort_identity="cohort", cohort_count=21
    )
    config["action_space"] = ActionSpaceConfig.initial_no_potions().to_dict()
    config["controller_roles"]["a"] = "display label only"
    assert not transfer_command.validate_t044_reuse(
        report, cohort_identity="cohort", cohort_count=21
    )
    config["controller_roles"]["a"] = transfer_command.T044_CONTROLLER_ROLES[0]
    assert (
        transfer_command.t044_independent_arm_disposition(
            report,
            frozen_cohort={"identity": "cohort", "record_count": 21},
        )
        == "reuse_historical_four_arm"
    )
    config["max_battle_steps"] = 199
    assert (
        transfer_command.t044_independent_arm_disposition(
            report,
            frozen_cohort={"identity": "cohort", "record_count": 21},
        )
        == "rerun_once_two_independent_arms"
    )
    baseline = {
        "schema_id": "t070-single-arm-merged-stage-v1",
        "cohort_identity": "t052",
        "cohort_record_count": 93,
        "arm": "baseline",
        "native_budget": 100,
        "tree_geometry_enabled": False,
        "shard_ranges": list(transfer_command.T070_T052_RANGES),
        "command_passed": True,
        "problems": [],
    }
    assert not transfer_command.validate_t070_baseline_reuse(
        baseline, cohort_identity="t052"
    )
    baseline["tree_geometry_enabled"] = True
    assert not transfer_command.validate_t070_baseline_reuse(
        baseline, cohort_identity="t052"
    )


def test_t044_current_action_space_is_exact_for_new_reports() -> None:
    def arm(role: str, count: int) -> SimpleNamespace:
        return SimpleNamespace(
            role=role,
            report=SimpleNamespace(
                problems=[],
                battle_results=[
                    SimpleNamespace(cohort_index=index) for index in range(count)
                ],
            ),
        )

    action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    independent = SimpleNamespace(
        comparison_config={
            "cohort_identity": "assist-0",
            "cohort_record_count": 21,
            "max_battle_steps": 200,
            "run_scale": "fixed",
            "action_space": action_space,
        },
        arms=tuple(arm(role, 21) for role in transfer_command.T044_INDEPENDENT_ROLES),
        evaluation_successful=True,
    )
    dependent = SimpleNamespace(
        comparison_config={
            "cohort_identity": "assist-0",
            "cohort_record_count": 21,
            "max_battle_steps": 200,
            "run_scale": "fixed",
            "shard_count": 16,
            "shard_ranges": list(transfer_command.T044_ASSIST_0_RANGES),
            "action_space": action_space,
        },
        arms=tuple(arm(role, 21) for role in transfer_command.T044_DEPENDENT_ROLES),
        evaluation_successful=True,
    )

    assert transfer_command.validate_t044_independent_report(
        independent, cohort_identity="assist-0", cohort_count=21
    )
    assert transfer_command.validate_t044_dependent_report(
        dependent, cohort_identity="assist-0", cohort_count=21
    )

    mutated = ActionSpaceConfig.initial_no_potions().to_dict()
    mutated["allow_excluded_fallback"] = False
    independent.comparison_config["action_space"] = mutated
    dependent.comparison_config["action_space"] = mutated
    assert not transfer_command.validate_t044_independent_report(
        independent, cohort_identity="assist-0", cohort_count=21
    )
    assert not transfer_command.validate_t044_dependent_report(
        dependent, cohort_identity="assist-0", cohort_count=21
    )


def test_t070_baseline_reuse_strictly_checks_controller_and_failures() -> None:
    controller = {
        "config": {
            "information_regime": "full_simulator_state_oracle_like",
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "root_selection_rule": "highest_mean",
            "ablation": "baseline",
            "search_budget": {"simulations": 100},
            "tree_internal_guidance": {
                "policy_prior": False,
                "learned_leaf_value": False,
                "root_only_or_post_search_fallback": False,
            },
        }
    }
    report = {
        "schema_id": "t070-single-arm-merged-stage-v1",
        "cohort_identity": "t052",
        "cohort_record_count": 93,
        "arm": "baseline",
        "native_budget": 100,
        "shard_ranges": list(transfer_command.T070_T052_RANGES),
        "command_passed": True,
        "problems": [],
        "code_commit": "a" * 40,
        "native_commit": "b" * 40,
        "native_runtime_identity": {"runtime": "frozen"},
        "controller_provenance": controller,
        "family": "shared",
        "stage_name": "baseline-0100",
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "arm_report": {
            "record_count": 93,
            "wins": 50,
            "losses": 43,
            "truncations": 0,
            "errors": 0,
            "evaluation_problems": [],
        },
    }
    contract = {
        key: report[key]
        for key in (
            "code_commit",
            "native_commit",
            "native_runtime_identity",
            "controller_provenance",
            "family",
            "stage_name",
            "worker_count",
            "shard_count",
            "effective_parallel_workers",
        )
    }
    contract["primary_stage_inventory"] = [
        {
            "stage_name": "baseline-0100",
            "arm": "baseline",
            "family": "shared",
            "native_budget": 100,
            "tree_geometry_enabled": False,
        }
    ]
    assert transfer_command.validate_t070_baseline_reuse(
        report, cohort_identity="t052", frozen_contract=contract
    )
    report["controller_provenance"]["config"]["tree_internal_guidance"][
        "policy_prior"
    ] = True
    assert not transfer_command.validate_t070_baseline_reuse(
        report, cohort_identity="t052", frozen_contract=contract
    )


@pytest.mark.parametrize(
    ("stage", "target"),
    (
        ("stage2_teacher", "collect_t064_teacher_stage"),
        ("stage3_trainer", "build_t064_trainer_input_stage"),
        ("stage4_training", "run_t064_paired_training"),
        ("stage5_t044_dependent", "run_t064_t044_dependent_stage"),
        ("stage5_t044_independent", "run_t064_t044_independent_fallback_stage"),
        ("stage6_t070", "run_t064_t070_prior_value_stage"),
        ("stage7_aggregate", "aggregate_t064_stage7_from_artifacts"),
    ),
)
def test_production_stage_dispatcher_routes_only_existing_primitives(
    monkeypatch: pytest.MonkeyPatch, stage: str, target: str
) -> None:
    calls = []

    def primitive(**kwargs):
        calls.append(kwargs)
        return target

    monkeypatch.setattr(transfer_command, target, primitive)
    assert (
        transfer_command.execute_t064_production_stage(
            stage, inputs={"frozen": "exact"}
        )
        == target
    )
    assert calls == [{"frozen": "exact"}]


def test_stage2_cli_routes_to_fixed_production_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [
            {"stage": "stage2_teacher", "workers": 16, "ranges": ["0:1"] * 16}
        ],
    )
    calls = []
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage2_production",
        lambda **kwargs: (
            SimpleNamespace(records=[object()]),
            calls.append(kwargs) or [],
        ),
    )
    assert (
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage2_teacher",
                "--stage2-teacher-output",
                str(tmp_path / "teacher.jsonl"),
                "--stage2-shard-output-dir",
                str(tmp_path / "shards"),
                "--stage2-log-dir",
                str(tmp_path / "logs"),
            ]
        )
        == 0
    )
    assert calls and calls[0]["merged_output_path"] == tmp_path / "teacher.jsonl"
    assert json.loads(capsys.readouterr().out)["stage"] == "stage2_teacher"


def test_stage2_production_uses_validated_assisted_restorer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}
    monkeypatch.setattr(
        transfer_command,
        "load_selected_source_pool",
        lambda _manifest: (SimpleNamespace(), []),
    )
    monkeypatch.setattr(
        transfer_command,
        "collect_t064_teacher_stage",
        lambda **kwargs: (captured.update(kwargs) or SimpleNamespace(records=[]), []),
    )

    transfer_command.run_t064_stage2_production(
        manifest={},
        merged_output_path=tmp_path / "teacher.jsonl",
        shard_output_dir=tmp_path / "shards",
        log_dir=tmp_path / "logs",
    )

    assert (
        captured["record_restorer"]
        is transfer_command.restore_assisted_battle_start_record
    )
    assert captured["dispatch_backend"] == "fork"


def test_stage3_production_rejects_caller_authored_synthetic_bridge_contract(
    tmp_path: Path,
) -> None:
    """The direct mode has no public synthetic T022/T023 contract argument."""

    with pytest.raises(TypeError, match="bridge_contract"):
        transfer_command.run_t064_stage3_production(
            selected_manifest={},
            teacher_path=tmp_path / "teacher.jsonl",
            output_path=tmp_path / "trainer.jsonl",
            shard_output_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            code_commit="a" * 40,
            bridge_contract={},  # type: ignore[call-arg]
        )


def test_stage3_cli_exposes_direct_inputs_without_bridge_contract() -> None:
    repository = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(repository / "tests"))
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "t064_curriculum_transfer.py"),
            "--help",
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "--stage3-bridge-contract" not in completed.stdout
    assert "--stage3-teacher" in completed.stdout
    assert "--stage3-output" in completed.stdout


def test_stage3_cli_requires_all_four_direct_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    stage = {"stage": "stage3_trainer", "workers": 16, "shards": 16}
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda *_args, **_kwargs: [stage],
    )
    common = [
        "--dry-run-manifest",
        str(manifest_path),
        "--code-commit",
        "a" * 40,
        "--stage",
        "stage3_trainer",
    ]
    with pytest.raises(SystemExit) as partial:
        transfer_command.main(
            [*common, "--stage3-shard-output-dir", str(tmp_path / "shards")]
        )
    assert partial.value.code == 2
    captured = {}
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage3_production",
        lambda **kwargs: (
            captured.update(kwargs) or (SimpleNamespace(records=[]), None, {})
        ),
    )
    assert (
        transfer_command.main(
            [
                *common,
                "--stage3-teacher",
                str(tmp_path / "teacher.jsonl"),
                "--stage3-output",
                str(tmp_path / "trainer.jsonl"),
                "--stage3-shard-output-dir",
                str(tmp_path / "shards"),
                "--stage3-log-dir",
                str(tmp_path / "logs"),
            ]
        )
        == 0
    )
    assert captured["shard_output_dir"] == tmp_path / "shards"
    assert captured["log_dir"] == tmp_path / "logs"


def test_t043_direct_conversion_reuses_assisted_restore_and_existing_row_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sts_combat_rl.sim import oracle_teacher_search_guidance as guidance

    source = _record()
    identity = complete_source_identity(source)
    descriptor = {
        "complete_identity": identity,
        "complete_identity_sha256": identity["complete_identity_sha256"],
    }

    @dataclass(frozen=True)
    class ConvertedRow:
        source_metadata: dict[str, object]
        snapshot_features: list[float]
        legal_action_features: list[list[float]]

    captured = {}

    def convert(**kwargs):
        captured.update(kwargs)
        return (
            ConvertedRow(
                source_metadata={},
                snapshot_features=[1.0],
                legal_action_features=[[1.0]],
            ),
            "assisted_replay",
        )

    monkeypatch.setattr(guidance, "_trainer_record_from_teacher_row", convert)
    teacher_row = SimpleNamespace(
        source_checkpoint_id=source.source_checkpoint_id,
        source_seed=source.source_seed,
        source_run_id=source.source_run_id,
        source_battle_index=source.source_battle_index,
        source_distribution_kind=source.distribution_kind,
        checkpoint_information_regime=source.checkpoint_information_regime,
        soft_visit_target={"probabilities": [1.0]},
    )
    teacher = SimpleNamespace(
        records=[teacher_row], action_space_config={"include_potions": False}
    )
    dataset = (
        guidance.build_oracle_teacher_search_guidance_dataset_from_direct_provenance(
            adapter_factory=lambda: object(),
            teacher_dataset=teacher,
            source_pool=SimpleNamespace(records=[source]),
            selected_sources=[descriptor],
            teacher_artifact_identity={"sha256": "a" * 64},
            record_restorer=transfer_command.restore_assisted_battle_start_record,
        )
    )

    assert (
        captured["record_restorer"]
        is transfer_command.restore_assisted_battle_start_record
    )
    assert captured["selected_budget"] == 100
    assert dataset.generation_metadata["direct_provenance_mode"] == (
        "t064_manifest_and_merged_teacher"
    )
    assert (
        dataset.records[0].source_metadata["t064_complete_identity_sha256"]
        == (identity["complete_identity_sha256"])
    )


def test_t064_paired_training_uses_frozen_hidden_size_without_changing_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T064 passes the retained architecture while shared defaults stay legacy."""

    from sts_combat_rl.sim import torch_policy_value

    assert transfer_command.T064_TRAINING_HIDDEN_SIZE == 16
    assert torch_policy_value.TorchPolicyValueTrainingConfig().hidden_size == 128

    identity = "a" * 64
    plan = {
        "ordered_batches": [[identity] * 32 for _ in range(900)],
        "batch_plan_sha256": "b" * 64,
        "per_source_exposure_counts": {identity: 9600},
    }
    monkeypatch.setattr(
        transfer_command,
        "build_ordered_batch_plan",
        lambda _selected, *, seed, arm: {
            **plan,
            "arm": arm,
            "seed": seed,
        },
    )
    monkeypatch.setattr(
        transfer_command, "validate_exposure_parity", lambda _plans: None
    )
    monkeypatch.setattr(
        transfer_command,
        "_sha256",
        lambda _path: transfer_command.T064_INITIALIZATION_SHA256,
    )
    monkeypatch.setattr(
        torch_policy_value,
        "load_torch_policy_value_checkpoint",
        lambda _path: object(),
    )
    captured_configs = []

    def fake_train(_dataset, config, **_kwargs):
        captured_configs.append(config)
        return SimpleNamespace(report=SimpleNamespace(training_ok=False, problems=[]))

    monkeypatch.setattr(torch_policy_value, "train_torch_policy_value", fake_train)
    from sts_combat_rl.sim import training_gate

    monkeypatch.setattr(
        training_gate,
        "build_training_gate_report",
        lambda _dataset, *, override: {"override": override},
    )
    initialization = tmp_path / "initialization.pt"
    initialization.write_bytes(b"retained-initialization")
    trainer_input = tmp_path / "trainer.jsonl"
    trainer_input.write_bytes(b"trainer-input")
    checkpoint_paths = {
        (arm, seed): tmp_path / f"{arm}-{seed}.pt" for arm, seed in TRAINING_RUN_ORDER
    }
    report = transfer_command.run_t064_paired_training(
        selected_manifest={
            "selected_buckets": {},
            "batch_plans": [
                {key: value for key, value in plan.items() if key != "ordered_batches"}
                | {"arm": arm, "seed": seed}
                for arm, seed in TRAINING_RUN_ORDER
            ],
        },
        dataset=SimpleNamespace(),
        initialization_checkpoint_path=initialization,
        initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
        trainer_input_path=trainer_input,
        identity_to_trainer_index={identity: 0},
        checkpoint_paths=checkpoint_paths,
    )

    assert len(captured_configs) == len(TRAINING_RUN_ORDER)
    assert {config.hidden_size for config in captured_configs} == {16}
    assert [run["configuration"]["hidden_size"] for run in report["runs"]] == [16] * 4


def test_t064_single_run_checkpoint_publication_validates_temp_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sts_combat_rl.sim import torch_policy_value, training_gate

    identity = "a" * 64
    plan = {
        "ordered_batches": [[identity] * 32 for _ in range(900)],
        "batch_plan_sha256": "b" * 64,
        "per_source_exposure_counts": {identity: 9600},
        "arm": "static_mixture_v1",
        "seed": 64001,
    }
    monkeypatch.setattr(
        transfer_command,
        "_validated_t064_training_plans",
        lambda _manifest: {("static_mixture_v1", 64001): plan},
    )
    monkeypatch.setattr(
        transfer_command,
        "_sha256",
        lambda path: (
            transfer_command.T064_INITIALIZATION_SHA256
            if path.name == "initial.pt"
            else "c" * 64
        ),
    )
    provenance = {"normalized": True}
    monkeypatch.setattr(
        transfer_command,
        "_t064_training_data_provenance",
        lambda *_a, **_k: provenance,
    )
    monkeypatch.setattr(
        training_gate,
        "build_training_gate_report",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr(
        torch_policy_value,
        "train_torch_policy_value",
        lambda *_a, **_k: SimpleNamespace(
            report=SimpleNamespace(training_ok=True, problems=[])
        ),
    )
    cpu_tensor = SimpleNamespace(device=SimpleNamespace(type="cpu"))
    loaded = SimpleNamespace(
        config=transfer_command._t064_torch_training_config(64001),
        metadata={
            "task_id": "T064",
            "arm": "static_mixture_v1",
            "seed": 64001,
            "initialization_sha256": transfer_command.T064_INITIALIZATION_SHA256,
            "batch_plan_sha256": "b" * 64,
        },
        training_data_provenance=provenance,
        model=SimpleNamespace(
            hidden_size=16,
            parameters=lambda: iter((cpu_tensor,)),
            buffers=lambda: iter((cpu_tensor,)),
        ),
    )
    monkeypatch.setattr(
        torch_policy_value,
        "load_torch_policy_value_checkpoint",
        lambda path: object() if path.endswith("initial.pt") else loaded,
    )
    monkeypatch.setattr(
        torch_policy_value,
        "save_torch_policy_value_checkpoint",
        lambda _result, path, **_kwargs: Path(path).write_bytes(b"checkpoint"),
    )
    initialization = tmp_path / "initial.pt"
    initialization.write_bytes(b"initial")
    trainer = tmp_path / "trainer.jsonl"
    trainer.write_bytes(b"trainer")
    output = tmp_path / "checkpoint.pt"
    kwargs = {
        "selected_manifest": {},
        "dataset": SimpleNamespace(),
        "initialization_checkpoint_path": initialization,
        "initialization_sha256": transfer_command.T064_INITIALIZATION_SHA256,
        "trainer_input_path": trainer,
        "identity_to_trainer_index": {identity: 0},
        "checkpoint_paths": {("static_mixture_v1", 64001): output},
        "run_order": (("static_mixture_v1", 64001),),
    }
    report = transfer_command.run_t064_paired_training(**kwargs)
    assert output.read_bytes() == b"checkpoint"
    assert not output.with_suffix(".pt.tmp").exists()
    assert report["runs"][0]["run_disposition"] == "trained_new"

    output.unlink()
    loaded.metadata["seed"] = 64002
    with pytest.raises(ValueError, match="config/metadata"):
        transfer_command.run_t064_paired_training(**kwargs)
    assert not output.exists()
    assert output.with_suffix(".pt.tmp").read_bytes() == b"checkpoint"


@pytest.mark.skipif(
    not os.environ.get("STSRL_T064_INITIALIZATION_CHECKPOINT"),
    reason="set STSRL_T064_INITIALIZATION_CHECKPOINT to audit the retained artifact",
)
def test_t064_retained_initialization_checkpoint_matches_frozen_architecture() -> None:
    """Audit the real retained input when the maintainer exposes its stable path."""

    torch = pytest.importorskip("torch")
    from sts_combat_rl.sim.torch_policy_value import load_torch_policy_value_checkpoint

    checkpoint_path = Path(os.environ["STSRL_T064_INITIALIZATION_CHECKPOINT"])
    if not checkpoint_path.is_file():
        pytest.skip(f"retained checkpoint is unavailable: {checkpoint_path}")
    checkpoint = load_torch_policy_value_checkpoint(str(checkpoint_path))
    assert checkpoint.config.hidden_size == transfer_command.T064_TRAINING_HIDDEN_SIZE
    model = checkpoint.model
    hidden_size = transfer_command.T064_TRAINING_HIDDEN_SIZE
    assert model.hidden_size == hidden_size
    assert (
        model.state_mean.shape == model.state_std.shape == (model.state_feature_size,)
    )
    assert (
        model.action_mean.shape
        == model.action_std.shape
        == (model.action_feature_size,)
    )
    assert torch.isfinite(model.state_mean).all()
    assert torch.isfinite(model.action_mean).all()
    assert torch.isfinite(model.state_std).all() and torch.all(model.state_std > 0)
    assert torch.isfinite(model.action_std).all() and torch.all(model.action_std > 0)
    assert model.state_encoder[0].in_features == model.state_feature_size
    assert model.state_encoder[0].out_features == hidden_size
    assert model.state_encoder[2].in_features == hidden_size
    assert model.state_encoder[2].out_features == hidden_size
    assert model.action_encoder[0].in_features == model.action_feature_size
    assert model.action_encoder[0].out_features == hidden_size
    assert model.action_encoder[2].in_features == hidden_size
    assert model.action_encoder[2].out_features == hidden_size
    assert model.policy_head[0].in_features == hidden_size * 3
    assert model.policy_head[0].out_features == hidden_size
    assert model.policy_head[2].in_features == hidden_size
    assert model.policy_head[2].out_features == 1
    for head in (model.outcome_head, model.hp_head):
        assert head[0].in_features == head[0].out_features == hidden_size
        assert head[2].in_features == hidden_size
        assert head[2].out_features == 1
    assert model.resource_head[0].in_features == hidden_size
    assert model.resource_head[0].out_features == hidden_size
    assert model.resource_head[2].in_features == hidden_size
    assert model.resource_head[2].out_features == len(model.resource_target_names)


def test_stage5_production_uses_fork_dispatch_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    monkeypatch.setattr(
        transfer_command,
        "_build_t064_stage5_dependent_arms",
        lambda _path: pytest.fail("Torch scorer initialized in the fork parent"),
    )
    monkeypatch.setattr(
        transfer_command,
        "run_t064_t044_dependent_stage",
        lambda **kwargs: (captured.update(kwargs) or SimpleNamespace(), []),
    )

    transfer_command.run_t064_stage5_dependent_production(
        cohort_path=tmp_path / "cohort.jsonl",
        checkpoint_path=tmp_path / "checkpoint.pt",
        cohort_kind="assist_0",
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
    )

    assert captured["dispatch_backend"] == "fork"
    assert captured["controller_arms"] is None
    assert callable(captured["controller_arms_factory"])
    assert (
        captured["adapter_factory"]
        is transfer_command._t064_stage5_lightspeed_adapter_factory
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_stage5_dependent_factory_runs_after_sixteen_processes_are_isolated(
    tmp_path: Path,
) -> None:
    parent_pid = os.getpid()

    def arms_factory():
        controller = SimpleNamespace(
            action_space=ActionSpaceConfig.initial_no_potions(),
            created_pid=os.getpid(),
        )
        return (
            ("guided", transfer_command.T044_DEPENDENT_ROLES[0], controller),
            ("raw", transfer_command.T044_DEPENDENT_ROLES[1], controller),
        )

    def shard_runner(*_args, **kwargs):
        arms = kwargs["controller_arms"]
        return {
            "worker_pid": os.getpid(),
            "controller_pids": [arm[2].created_pid for arm in arms],
            "roles": [arm[1] for arm in arms],
        }

    merged, records = transfer_command.run_t064_t044_dependent_stage(
        adapter_factory=lambda: object(),
        cohort_path=tmp_path / "cohort.jsonl",
        controller_arms=None,
        cohort_kind="assist_0",
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
        shard_runner=shard_runner,
        merger=lambda **kwargs: kwargs["shards"],
        report_writer=lambda _path, _report: None,
        dispatch_backend="fork",
        controller_arms_factory=arms_factory,
    )

    worker_pids = {item["worker_pid"] for item in merged}
    assert len(worker_pids) == 16
    assert parent_pid not in worker_pids
    assert {record["worker_pid"] for record in records} == worker_pids
    assert all(set(item["controller_pids"]) == {item["worker_pid"]} for item in merged)
    assert all(
        tuple(item["roles"]) == transfer_command.T044_DEPENDENT_ROLES for item in merged
    )


@pytest.mark.skipif(
    os.name == "nt"
    or not os.environ.get("STSRL_T064_STAGE5_SMOKE_COHORT")
    or not os.environ.get("STSRL_T064_STAGE5_SMOKE_CHECKPOINT"),
    reason="set the two T064 Stage5 smoke paths and run through WSL",
)
def test_stage5_real_dependent_one_record_smoke_after_fork() -> None:
    cohort_path = Path(os.environ["STSRL_T064_STAGE5_SMOKE_COHORT"])
    checkpoint_path = Path(os.environ["STSRL_T064_STAGE5_SMOKE_CHECKPOINT"])
    assert cohort_path.is_file()
    assert checkpoint_path.is_file()
    parent_pid = os.getpid()
    summary = transfer_command.run_t064_stage5_dependent_one_record_smoke(
        cohort_path=cohort_path,
        checkpoint_path=checkpoint_path,
    )

    assert summary["worker_pid"] != parent_pid


def test_atomic_t070_selection_persist_promotes_once_and_cleans_failed_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "t064-curriculum-manifest.json"
    path.write_text('{"old":true}', encoding="utf-8")
    manifest = {"code_commit": "a" * 40, "t070_stage_manifest": None}
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: manifest)
    monkeypatch.setattr(
        transfer_command, "validate_resume_manifest", lambda *_args, **_kw: None
    )
    monkeypatch.setattr(
        transfer_command,
        "build_t064_t070_checkpoint_selections",
        lambda **_kw: {"checkpoint_selections": {"fixed": True}},
    )
    monkeypatch.setattr(
        transfer_command,
        "dump_compact_json",
        lambda payload, stream: json.dump(payload, stream, sort_keys=True),
    )
    transfer_command.persist_t064_t070_checkpoint_selections(
        manifest_path=path,
        code_commit="a" * 40,
        frozen_t070_manifest={},
        frozen_identity={},
        checkpoints={},
    )
    assert json.loads(path.read_text(encoding="utf-8"))["t070_stage_manifest"]
    original = path.read_bytes()
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: manifest)
    monkeypatch.setattr(
        transfer_command,
        "dump_compact_json",
        lambda *_args: (_ for _ in ()).throw(OSError("write")),
    )
    with pytest.raises(OSError, match="write"):
        transfer_command.persist_t064_t070_checkpoint_selections(
            manifest_path=path,
            code_commit="a" * 40,
            frozen_t070_manifest={},
            frozen_identity={},
            checkpoints={},
        )
    assert path.read_bytes() == original
    assert not path.with_suffix(".json.tmp").exists()


def _persisted_t064_selector_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    producer_commit = "1" * 40
    previous_commit = "2" * 40
    historical_commit = "3" * 40
    frozen = tmp_path / "t070-frozen.json"
    frozen_payload = {
        "schema_id": "t070-frozen-experiment-manifest-v1",
        "code_commit": historical_commit,
        "primary_shard_ranges": list(transfer_command.T070_T052_RANGES),
        "primary_stage_inventory": [
            {
                "stage_name": "equal-prior-value-0100",
                "arm": "prior_value",
                "family": "equal_nominal",
                "native_budget": 100,
                "tree_geometry_enabled": False,
            }
        ],
    }
    frozen.write_text(json.dumps(frozen_payload), encoding="utf-8")
    checkpoints: dict[str, dict[str, object]] = {}
    for arm, seed in TRAINING_RUN_ORDER:
        checkpoint = tmp_path / f"{arm}-{seed}.pt"
        checkpoint.write_bytes(f"{arm}:{seed}".encode())
        checkpoints[f"{arm}:{seed}"] = transfer_command._file_identity(checkpoint)
    manifest = _complete_source_inadequate_manifest(code_commit=producer_commit)
    manifest["t070_stage_manifest"] = (
        transfer_command.build_t064_t070_checkpoint_selections(
            current_code_commit=previous_commit,
            frozen_t070_manifest=frozen_payload,
            frozen_identity=transfer_command._file_identity(frozen),
            checkpoints=checkpoints,
        )
    )
    path = tmp_path / "t064-curriculum-manifest.json"
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(manifest, stream)
    return path, producer_commit, previous_commit


def test_t064_stage6_rebind_changes_only_execution_commit_atomically(
    tmp_path: Path,
) -> None:
    path, producer_commit, previous_commit = _persisted_t064_selector_fixture(tmp_path)
    with path.open(encoding="utf-8") as stream:
        before = transfer_command.load_compact_json(stream)
    before_bytes = path.read_bytes()
    new_commit = "4" * 40

    rebound = transfer_command.rebind_t064_t070_execution_commit(
        manifest_path=path,
        expected_previous_code_commit=previous_commit,
        new_code_commit=new_commit,
    )

    expected = dict(before)
    expected_stage = dict(before["t070_stage_manifest"])
    expected_stage["current_code_commit"] = new_commit
    expected["t070_stage_manifest"] = expected_stage
    assert rebound == expected
    assert rebound["code_commit"] == producer_commit
    assert path.read_bytes() != before_bytes
    with path.open(encoding="utf-8") as stream:
        assert transfer_command.load_compact_json(stream) == expected
    assert (
        transfer_command._validate_t064_t070_execution_binding(
            rebound, code_commit=new_commit
        )
        == rebound["t070_stage_manifest"]
    )
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("mutation", ("missing", "mixed", "invalid_identity"))
def test_t064_stage6_rebind_refuses_invalid_selection_inventory(
    tmp_path: Path, mutation: str
) -> None:
    path, _producer_commit, previous_commit = _persisted_t064_selector_fixture(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    selections = payload["t070_stage_manifest"]["checkpoint_selections"]
    if mutation == "missing":
        selections.pop("static_mixture_v1:64001")
    elif mutation == "mixed":
        selections["unexpected_arm:99999"] = next(iter(selections.values()))
    else:
        selections["static_mixture_v1:64001"]["checkpoint"]["sha256"] = "invalid"
    path.write_text(json.dumps(payload), encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(ValueError):
        transfer_command.rebind_t064_t070_execution_commit(
            manifest_path=path,
            expected_previous_code_commit=previous_commit,
            new_code_commit="4" * 40,
        )

    assert path.read_bytes() == original
    assert not path.with_suffix(".json.tmp").exists()


def test_t064_stage6_rebind_refuses_noop_stale_old_and_failed_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _producer_commit, previous_commit = _persisted_t064_selector_fixture(tmp_path)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="no-op"):
        transfer_command.rebind_t064_t070_execution_commit(
            manifest_path=path,
            expected_previous_code_commit=previous_commit,
            new_code_commit=previous_commit,
        )
    with pytest.raises(ValueError, match="different execution head"):
        transfer_command.rebind_t064_t070_execution_commit(
            manifest_path=path,
            expected_previous_code_commit="5" * 40,
            new_code_commit="4" * 40,
        )
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text("retained failed evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="refuses to overwrite"):
        transfer_command.rebind_t064_t070_execution_commit(
            manifest_path=path,
            expected_previous_code_commit=previous_commit,
            new_code_commit="4" * 40,
        )
    assert temporary.read_text(encoding="utf-8") == "retained failed evidence"
    temporary.unlink()
    monkeypatch.setattr(
        transfer_command,
        "dump_compact_json",
        lambda *_args: (_ for _ in ()).throw(OSError("atomic write failed")),
    )
    with pytest.raises(OSError, match="atomic write failed"):
        transfer_command.rebind_t064_t070_execution_commit(
            manifest_path=path,
            expected_previous_code_commit=previous_commit,
            new_code_commit="4" * 40,
        )
    assert path.read_bytes() == original
    assert not path.with_suffix(".json.tmp").exists()


def _complete_training_report() -> dict[str, object]:
    return {
        "schema_id": "t064-training-run-report-v1",
        "format_version": 1,
        "runs": [
            {
                "arm": arm,
                "seed": seed,
                "initialization_sha256": "a" * 64,
                "configuration": {},
                "trainer_input_sha256": "b" * 64,
                "trainer_input_bytes": 1,
                "batch_plan_sha256": "c" * 64,
                "per_bucket_exposure_counts": {},
                "per_source_exposure_counts": {},
                "checkpoint": {
                    "path": f"{arm}-{seed}.pt",
                    "sha256": "d" * 64,
                    "bytes": 1,
                },
                "checkpoint_metadata_linkage": {},
                "run_disposition": "trained_new",
                "completion_status": "complete",
                "problems": [],
            }
            for arm, seed in TRAINING_RUN_ORDER
        ],
    }


def test_stage4_preflight_creates_missing_checkpoint_root(tmp_path: Path) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    checkpoint_root = tmp_path / "training" / "checkpoints"

    loaded = transfer_command._preflight_t064_stage4_paths(
        manifest_path=manifest_path,
        training_report_path=tmp_path / "t064-training-run-report.json",
        checkpoint_root=checkpoint_root,
        frozen_t070_manifest_path=frozen,
        code_commit="b" * 40,
    )

    assert loaded == {}
    assert checkpoint_root.is_dir()


@pytest.mark.parametrize("arm,seed", TRAINING_RUN_ORDER)
def test_stage4_preflight_refuses_existing_checkpoint_without_overwrite(
    tmp_path: Path, arm: str, seed: int
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    checkpoint_root = tmp_path / "training" / "checkpoints"
    checkpoint_root.mkdir(parents=True)
    existing = checkpoint_root / f"{arm}-{seed}.pt"
    existing.write_bytes(b"retained checkpoint")

    with pytest.raises(ValueError, match="not excluded by earliest_affected_run"):
        transfer_command._preflight_t064_stage4_paths(
            manifest_path=manifest_path,
            training_report_path=tmp_path / "t064-training-run-report.json",
            checkpoint_root=checkpoint_root,
            frozen_t070_manifest_path=frozen,
            code_commit=code_commit,
        )

    assert existing.read_bytes() == b"retained checkpoint"
    assert list(checkpoint_root.iterdir()) == [existing]


def test_stage4_preflight_validates_only_runs_before_exact_boundary(
    tmp_path: Path,
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    checkpoint_root = tmp_path / "training" / "checkpoints"
    checkpoint_root.mkdir(parents=True)
    checkpoint = checkpoint_root / "static_mixture_v1-64001.pt"
    checkpoint.write_bytes(b"retained checkpoint")
    calls: list[tuple[str, int, Path]] = []
    reusable_runs: dict[tuple[str, int], object] = {}

    def validate(arm: str, seed: int, path: Path) -> dict[str, object]:
        calls.append((arm, seed, path))
        return {"arm": arm, "seed": seed, "checkpoint": {"path": str(path)}}

    transfer_command._preflight_t064_stage4_paths(
        manifest_path=manifest_path,
        training_report_path=tmp_path / "t064-training-run-report.json",
        checkpoint_root=checkpoint_root,
        frozen_t070_manifest_path=frozen,
        code_commit=code_commit,
        earliest_affected_run="assistance_annealed_curriculum_v1/64001",
        reusable_checkpoint_validator=validate,
        reusable_runs=reusable_runs,
    )

    assert calls == [("static_mixture_v1", 64001, checkpoint)]
    assert list(reusable_runs) == [("static_mixture_v1", 64001)]


def test_stage4_preflight_fails_closed_on_partial_or_mismatched_reuse(
    tmp_path: Path,
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    checkpoint_root = tmp_path / "training" / "checkpoints"
    checkpoint_root.mkdir(parents=True)
    checkpoint = checkpoint_root / "static_mixture_v1-64001.pt"
    partial = checkpoint.with_suffix(".pt.tmp")
    partial.write_bytes(b"partial")
    kwargs = {
        "manifest_path": manifest_path,
        "training_report_path": tmp_path / "t064-training-run-report.json",
        "checkpoint_root": checkpoint_root,
        "frozen_t070_manifest_path": frozen,
        "code_commit": code_commit,
        "earliest_affected_run": "assistance_annealed_curriculum_v1/64001",
    }
    with pytest.raises(ValueError, match="partial checkpoint"):
        transfer_command._preflight_t064_stage4_paths(**kwargs)
    partial.unlink()
    checkpoint.write_bytes(b"mismatch")
    with pytest.raises(ValueError, match="frozen config mismatch"):
        transfer_command._preflight_t064_stage4_paths(
            **kwargs,
            reusable_checkpoint_validator=lambda *_args: (_ for _ in ()).throw(
                ValueError("frozen config mismatch")
            ),
        )


def test_stage4_loaded_checkpoint_validation_covers_full_frozen_contract() -> None:
    plan = {
        "batch_plan_sha256": "b" * 64,
        "per_source_exposure_counts": {"source": 9600},
    }
    provenance = {"trainer_input_sha256": "c" * 64, "exact": True}
    cpu_tensor = SimpleNamespace(device=SimpleNamespace(type="cpu"))
    model = SimpleNamespace(
        hidden_size=16,
        parameters=lambda: iter((cpu_tensor,)),
        buffers=lambda: iter((cpu_tensor,)),
    )
    loaded = SimpleNamespace(
        config=transfer_command._t064_torch_training_config(64001),
        metadata={
            "task_id": "T064",
            "arm": "static_mixture_v1",
            "seed": 64001,
            "initialization_sha256": transfer_command.T064_INITIALIZATION_SHA256,
            "batch_plan_sha256": "b" * 64,
        },
        training_data_provenance=provenance,
        model=model,
    )
    transfer_command._validate_loaded_t064_run_checkpoint(
        loaded,
        arm="static_mixture_v1",
        seed=64001,
        initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
        plan=plan,
        expected_provenance=provenance,
    )
    loaded.metadata["arm"] = "wrong"
    with pytest.raises(ValueError, match="config/metadata"):
        transfer_command._validate_loaded_t064_run_checkpoint(
            loaded,
            arm="static_mixture_v1",
            seed=64001,
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            plan=plan,
            expected_provenance=provenance,
        )
    loaded.metadata["arm"] = "static_mixture_v1"
    loaded.training_data_provenance = {"trainer_input_sha256": "d" * 64}
    with pytest.raises(ValueError, match="trainer provenance"):
        transfer_command._validate_loaded_t064_run_checkpoint(
            loaded,
            arm="static_mixture_v1",
            seed=64001,
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            plan=plan,
            expected_provenance=provenance,
        )
    loaded.training_data_provenance = provenance
    loaded.config = transfer_command._t064_torch_training_config(64002)
    with pytest.raises(ValueError, match="config/metadata"):
        transfer_command._validate_loaded_t064_run_checkpoint(
            loaded,
            arm="static_mixture_v1",
            seed=64001,
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            plan=plan,
            expected_provenance=provenance,
        )
    loaded.config = transfer_command._t064_torch_training_config(64001)
    loaded.model.hidden_size = 128
    with pytest.raises(ValueError, match="model metadata/device"):
        transfer_command._validate_loaded_t064_run_checkpoint(
            loaded,
            arm="static_mixture_v1",
            seed=64001,
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            plan=plan,
            expected_provenance=provenance,
        )


def test_stage4_default_executor_is_spawned_process_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeProcessPool:
        def __init__(self, *, max_workers, mp_context):
            captured["max_workers"] = max_workers
            captured["start_method"] = mp_context.get_start_method()

    monkeypatch.setattr(transfer_command, "ProcessPoolExecutor", FakeProcessPool)
    executor = transfer_command._t064_stage4_process_executor(2)

    assert isinstance(executor, FakeProcessPool)
    assert captured == {"max_workers": 2, "start_method": "spawn"}


def test_stage4_cached_reuse_summary_requires_exact_exposure_and_config() -> None:
    plan = {
        "batch_plan_sha256": "b" * 64,
        "per_source_exposure_counts": {"source": 9600},
    }
    run = transfer_command._t064_training_run_entry(
        arm="static_mixture_v1",
        seed=64001,
        initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
        trainer_sha256="c" * 64,
        trainer_byte_count=123,
        plan=plan,
        checkpoint={"path": "checkpoint.pt", "sha256": "d" * 64, "bytes": 1},
        completion_status="complete",
        problems=(),
        disposition="reused_validated",
    )
    kwargs = {
        "key": ("static_mixture_v1", 64001),
        "plan": plan,
        "initialization_sha256": transfer_command.T064_INITIALIZATION_SHA256,
        "trainer_sha256": "c" * 64,
        "trainer_byte_count": 123,
    }
    transfer_command._validate_cached_t064_reuse_summary(run, **kwargs)
    run["per_source_exposure_counts"] = {"source": 9599}
    with pytest.raises(ValueError, match="no longer matches"):
        transfer_command._validate_cached_t064_reuse_summary(run, **kwargs)


def test_stage4_worker_cap_and_failure_retains_other_completed_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_workers: list[int] = []
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def executor_factory(max_workers: int):
        observed_workers.append(max_workers)
        return ThreadPoolExecutor(max_workers=max_workers)

    def worker(request):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            time.sleep(0.02)
            if request.arm == "assistance_annealed_curriculum_v1":
                raise RuntimeError("simulated worker failure")
            request.checkpoint_path.write_bytes(b"complete")
            return {"arm": request.arm, "seed": request.seed}
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(
        transfer_command, "_t064_stage4_process_executor", executor_factory
    )
    monkeypatch.setattr(transfer_command, "_run_t064_stage4_worker", worker)
    requests = [
        transfer_command._T064Stage4RunRequest(
            manifest_path=tmp_path / "manifest.json",
            trainer_input_path=tmp_path / "trainer.jsonl",
            initialization_checkpoint_path=tmp_path / "initial.pt",
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            checkpoint_path=tmp_path / f"{arm}-{seed}.pt",
            arm=arm,
            seed=seed,
        )
        for arm, seed in TRAINING_RUN_ORDER[:2]
    ]
    with pytest.raises(RuntimeError, match="other complete checkpoints are retained"):
        transfer_command._run_t064_stage4_requests(requests)

    assert observed_workers == [2]
    assert maximum_active == 2
    assert requests[0].checkpoint_path.read_bytes() == b"complete"
    assert not requests[1].checkpoint_path.exists()
    assert all(
        isinstance(value, (Path, str, int)) for value in vars(requests[0]).values()
    )


def test_stage4_canonical_report_ignores_schedule_completion_order() -> None:
    runs = list(reversed(_complete_training_report()["runs"]))
    report = transfer_command._canonical_t064_training_report(runs)
    assert [(run["arm"], run["seed"]) for run in report["runs"]] == list(
        TRAINING_RUN_ORDER
    )


def test_stage4_production_rehashes_reuse_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    checkpoint_root.mkdir()
    checkpoint = checkpoint_root / "static_mixture_v1-64001.pt"
    checkpoint.write_bytes(b"validated")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    trainer_path = tmp_path / "trainer.jsonl"
    trainer_path.write_bytes(b"trainer")
    reused = {
        ("static_mixture_v1", 64001): {
            "arm": "static_mixture_v1",
            "seed": 64001,
            "checkpoint": transfer_command._file_identity(checkpoint),
        }
    }
    checkpoint.write_bytes(b"changed-after-preflight")
    monkeypatch.setattr(
        transfer_command,
        "_run_t064_stage4_requests",
        lambda _requests: pytest.fail("training must not start after checkpoint drift"),
    )
    monkeypatch.setattr(
        transfer_command,
        "_validated_t064_training_plans",
        lambda _manifest: {key: {} for key in TRAINING_RUN_ORDER},
    )
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})

    with pytest.raises(ValueError, match="changed after preflight"):
        transfer_command.run_t064_stage4_production(
            manifest_path=manifest_path,
            trainer_input_path=trainer_path,
            initialization_checkpoint_path=tmp_path / "initial.pt",
            initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
            checkpoint_root=checkpoint_root,
            frozen_t070_manifest_path=tmp_path / "t070.json",
            earliest_affected_run="assistance_annealed_curriculum_v1/64001",
            reusable_runs=reused,
        )


def test_stage4_production_combines_valid_reuse_and_out_of_order_completions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    checkpoint_root.mkdir()
    checkpoint = checkpoint_root / "static_mixture_v1-64001.pt"
    checkpoint.write_bytes(b"validated")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    trainer_path = tmp_path / "trainer.jsonl"
    trainer_path.write_bytes(b"trainer")
    reused_run = {
        "arm": "static_mixture_v1",
        "seed": 64001,
        "checkpoint": transfer_command._file_identity(checkpoint),
        "run_disposition": "reused_validated",
    }
    missing = list(TRAINING_RUN_ORDER[1:])

    def finish_out_of_order(requests):
        assert [(request.arm, request.seed) for request in requests] == missing
        return [
            {"arm": arm, "seed": seed, "run_disposition": "trained_new"}
            for arm, seed in reversed(missing)
        ]

    monkeypatch.setattr(
        transfer_command, "_run_t064_stage4_requests", finish_out_of_order
    )
    monkeypatch.setattr(
        transfer_command,
        "_validated_t064_training_plans",
        lambda _manifest: {key: {} for key in TRAINING_RUN_ORDER},
    )
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command, "_validate_cached_t064_reuse_summary", lambda *_a, **_k: None
    )
    report = transfer_command.run_t064_stage4_production(
        manifest_path=manifest_path,
        trainer_input_path=trainer_path,
        initialization_checkpoint_path=tmp_path / "initial.pt",
        initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
        checkpoint_root=checkpoint_root,
        frozen_t070_manifest_path=tmp_path / "t070.json",
        earliest_affected_run="assistance_annealed_curriculum_v1/64001",
        reusable_runs={("static_mixture_v1", 64001): reused_run},
    )

    assert [(run["arm"], run["seed"]) for run in report["runs"]] == list(
        TRAINING_RUN_ORDER
    )
    assert report["runs"][0]["run_disposition"] == "reused_validated"


def test_stage4_failure_recovery_reuses_later_completed_run_and_trains_only_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    trainer_path = tmp_path / "trainer.jsonl"
    trainer_path.write_bytes(b"trainer")
    checkpoint_root = tmp_path / "checkpoints"
    checkpoint_root.mkdir()
    completed_keys = (TRAINING_RUN_ORDER[0], *TRAINING_RUN_ORDER[2:])
    for arm, seed in completed_keys:
        (checkpoint_root / f"{arm}-{seed}.pt").write_bytes(
            f"complete:{arm}:{seed}".encode()
        )
    reusable_runs: dict[tuple[str, int], object] = {}

    def validate(arm: str, seed: int, path: Path) -> dict[str, object]:
        return {
            "arm": arm,
            "seed": seed,
            "checkpoint": transfer_command._file_identity(path),
            "run_disposition": "reused_validated",
        }

    transfer_command._preflight_t064_stage4_paths(
        manifest_path=manifest_path,
        training_report_path=tmp_path / "t064-training-run-report.json",
        checkpoint_root=checkpoint_root,
        frozen_t070_manifest_path=frozen,
        code_commit=code_commit,
        failure_recovery=True,
        reusable_checkpoint_validator=validate,
        reusable_runs=reusable_runs,
    )
    assert tuple(reusable_runs) == completed_keys
    assert (
        "assistance_annealed_curriculum_v1",
        64002,
    ) in reusable_runs  # Final canonical run completed after the earlier failure.

    failed_key = TRAINING_RUN_ORDER[1]

    def finish_missing(requests):
        assert [(request.arm, request.seed) for request in requests] == [failed_key]
        return [
            {
                "arm": failed_key[0],
                "seed": failed_key[1],
                "run_disposition": "trained_new",
            }
        ]

    monkeypatch.setattr(transfer_command, "_run_t064_stage4_requests", finish_missing)
    monkeypatch.setattr(
        transfer_command,
        "_validated_t064_training_plans",
        lambda _manifest: {key: {} for key in TRAINING_RUN_ORDER},
    )
    monkeypatch.setattr(
        transfer_command, "_validate_cached_t064_reuse_summary", lambda *_a, **_k: None
    )
    report = transfer_command.run_t064_stage4_production(
        manifest_path=manifest_path,
        trainer_input_path=trainer_path,
        initialization_checkpoint_path=tmp_path / "initial.pt",
        initialization_sha256=transfer_command.T064_INITIALIZATION_SHA256,
        checkpoint_root=checkpoint_root,
        frozen_t070_manifest_path=frozen,
        failure_recovery=True,
        reusable_runs=reusable_runs,
    )

    assert [(run["arm"], run["seed"]) for run in report["runs"]] == list(
        TRAINING_RUN_ORDER
    )
    assert report["runs"][1]["run_disposition"] == "trained_new"
    assert report["runs"][3]["run_disposition"] == "reused_validated"
    assert (
        transfer_command._t064_reusable_run_keys(
            "assistance_annealed_curriculum_v1/64001",
            failure_recovery=True,
        )
        == TRAINING_RUN_ORDER[:1]
    )


def test_stage4_invalid_preflight_does_not_create_checkpoint_root(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest = _complete_source_inadequate_manifest(code_commit="a" * 40)
    manifest["complete_source_audit"]["status"] = (
        "static_complete_selected_restore_pending"
    )
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(manifest, stream)
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    checkpoint_root = tmp_path / "training" / "checkpoints"
    report_path = tmp_path / "t064-training-run-report.json"

    with pytest.raises(ValueError, match="completed selected-source audit"):
        transfer_command._preflight_t064_stage4_paths(
            manifest_path=manifest_path,
            training_report_path=report_path,
            checkpoint_root=checkpoint_root,
            frozen_t070_manifest_path=frozen,
            code_commit="b" * 40,
        )

    assert not checkpoint_root.exists()
    assert not report_path.exists()


def test_stage4_cli_writes_report_before_finalizing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    report_path = tmp_path / "t064-training-run-report.json"
    calls: list[str] = []
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [{"stage": "stage4_training"}],
    )

    def preflight(**kwargs):
        assert kwargs["failure_recovery"] is True
        calls.append("preflight")
        return {}

    def train(**kwargs):
        assert kwargs["failure_recovery"] is True
        calls.append("train")
        return _complete_training_report()

    monkeypatch.setattr(transfer_command, "_preflight_t064_stage4_paths", preflight)
    monkeypatch.setattr(transfer_command, "run_t064_stage4_production", train)

    def finalize(**_kwargs):
        calls.append("finalize")
        assert report_path.is_file()

    monkeypatch.setattr(
        transfer_command, "persist_t064_t070_checkpoint_selections", finalize
    )
    assert (
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage4_training",
                "--stage4-trainer-input",
                str(tmp_path / "trainer.jsonl"),
                "--stage4-initialization",
                str(tmp_path / "initial.pt"),
                "--stage4-initialization-sha256",
                transfer_command.T064_INITIALIZATION_SHA256,
                "--stage4-checkpoint-root",
                str(tmp_path / "checkpoints"),
                "--stage4-frozen-t070-manifest",
                str(frozen),
                "--stage4-training-report",
                str(report_path),
                "--stage4-failure-recovery",
            ]
        )
        == 0
    )
    assert calls == ["preflight", "train", "finalize"]
    assert not report_path.with_suffix(".json.tmp").exists()


def test_stage4_cli_rejects_output_path_before_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [{"stage": "stage4_training"}],
    )
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage4_production",
        lambda **_kwargs: calls.append(_kwargs),
    )
    with pytest.raises(SystemExit):
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage4_training",
                "--stage4-trainer-input",
                str(tmp_path / "trainer.jsonl"),
                "--stage4-initialization",
                str(tmp_path / "initial.pt"),
                "--stage4-initialization-sha256",
                transfer_command.T064_INITIALIZATION_SHA256,
                "--stage4-checkpoint-root",
                str(tmp_path / "checkpoints"),
                "--stage4-frozen-t070-manifest",
                str(frozen),
                "--stage4-training-report",
                str(tmp_path / "wrong-name.json"),
            ]
        )
    assert calls == []


def test_stage4_cli_rejects_nonfrozen_initialization_before_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [{"stage": "stage4_training"}],
    )
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage4_production",
        lambda **kwargs: calls.append(kwargs),
    )
    with pytest.raises(SystemExit):
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage4_training",
                "--stage4-trainer-input",
                str(tmp_path / "trainer.jsonl"),
                "--stage4-initialization",
                str(tmp_path / "initial.pt"),
                "--stage4-initialization-sha256",
                "0" * 64,
                "--stage4-checkpoint-root",
                str(tmp_path / "checkpoints"),
                "--stage4-frozen-t070-manifest",
                str(frozen),
                "--stage4-training-report",
                str(tmp_path / "t064-training-run-report.json"),
            ]
        )
    assert calls == []


def test_atomic_training_report_write_preserves_target_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t064-training-run-report.json"
    monkeypatch.setattr(
        transfer_command,
        "dump_compact_json",
        lambda *_args: (_ for _ in ()).throw(OSError("report write failed")),
    )
    with pytest.raises(OSError, match="report write failed"):
        transfer_command._write_new_compact_json_atomically(
            target, _complete_training_report()
        )
    assert not target.exists()
    assert not target.with_suffix(".json.tmp").exists()


def test_stage4_selection_finalization_failure_follows_report_persist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    frozen = tmp_path / "t070-frozen.json"
    frozen.write_text("{}", encoding="utf-8")
    report_path = tmp_path / "t064-training-run-report.json"
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [{"stage": "stage4_training"}],
    )
    monkeypatch.setattr(
        transfer_command, "_preflight_t064_stage4_paths", lambda **_kwargs: {}
    )
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage4_production",
        lambda **_kwargs: _complete_training_report(),
    )
    monkeypatch.setattr(
        transfer_command,
        "persist_t064_t070_checkpoint_selections",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("finalize failed")),
    )
    with pytest.raises(OSError, match="finalize failed"):
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage4_training",
                "--stage4-trainer-input",
                str(tmp_path / "trainer.jsonl"),
                "--stage4-initialization",
                str(tmp_path / "initial.pt"),
                "--stage4-initialization-sha256",
                transfer_command.T064_INITIALIZATION_SHA256,
                "--stage4-checkpoint-root",
                str(tmp_path / "checkpoints"),
                "--stage4-frozen-t070-manifest",
                str(frozen),
                "--stage4-training-report",
                str(report_path),
            ]
        )
    assert report_path.is_file()
    assert manifest_path.read_text(encoding="utf-8") == "{}"
    assert not report_path.with_suffix(".json.tmp").exists()


def test_stage5_historical_cli_is_cohort_level_and_checkpoint_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage5_historical_disposition_production",
        lambda **kwargs: (
            True,
            SimpleNamespace(arms=(1, 2, 3, 4)),
            calls.append(kwargs) or [],
        ),
    )
    assert (
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                code_commit,
                "--stage",
                "stage5_t044",
                "--stage5-cohort",
                str(tmp_path / "assist0.jsonl"),
                "--stage5-cohort-kind",
                "assist_0",
                "--stage5-log-dir",
                str(tmp_path / "logs"),
                "--stage5-shard-output-dir",
                str(tmp_path / "shards"),
                "--stage5-merged-output",
                str(tmp_path / "merged.jsonl"),
                "--stage5-historical-report",
                str(tmp_path / "historical.jsonl"),
            ]
        )
        == 0
    )
    assert calls and "checkpoint_path" not in calls[0]
    assert json.loads(capsys.readouterr().out)["disposition"] == "reused_historical"


@pytest.mark.parametrize(
    "checkpoint_arm",
    [f"{arm}/{seed}" for arm, seed in TRAINING_RUN_ORDER],
)
@pytest.mark.parametrize("cohort_kind", ("assist_0", "assist_hp50"))
def test_stage5_dependent_cli_routes_real_plan_to_exact_checkpoint_and_cohort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    checkpoint_arm: str,
    cohort_kind: str,
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    checkpoint_path = tmp_path / f"{checkpoint_arm.replace('/', '-')}.pt"
    calls: list[dict[str, object]] = []

    def run_stage(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(arms=(1, 2)), []

    monkeypatch.setattr(
        transfer_command, "run_t064_stage5_dependent_production", run_stage
    )
    assert (
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                code_commit,
                "--stage",
                "stage5_t044",
                "--checkpoint-arm",
                checkpoint_arm,
                "--stage5-cohort",
                str(tmp_path / f"{cohort_kind}.jsonl"),
                "--stage5-checkpoint",
                str(checkpoint_path),
                "--stage5-cohort-kind",
                cohort_kind,
                "--stage5-log-dir",
                str(tmp_path / "logs"),
                "--stage5-shard-output-dir",
                str(tmp_path / "shards"),
                "--stage5-merged-output",
                str(tmp_path / "merged.jsonl"),
            ]
        )
        == 0
    )
    assert len(calls) == 1
    assert calls[0]["checkpoint_path"] == checkpoint_path
    assert calls[0]["cohort_kind"] == cohort_kind
    assert json.loads(capsys.readouterr().out)["stage"] == "stage5_t044"


@pytest.mark.parametrize(
    "cohort_args",
    ((), ("--stage5-cohort-kind", "unknown_cohort")),
    ids=("missing", "invalid"),
)
def test_stage5_dependent_cli_fails_closed_for_missing_or_invalid_cohort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cohort_args: tuple[str, ...],
) -> None:
    code_commit = "a" * 40
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(
            _complete_source_inadequate_manifest(code_commit=code_commit), stream
        )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        transfer_command,
        "run_t064_stage5_dependent_production",
        lambda **kwargs: calls.append(kwargs),
    )
    argv = [
        "--dry-run-manifest",
        str(manifest_path),
        "--code-commit",
        code_commit,
        "--stage",
        "stage5_t044",
        "--checkpoint-arm",
        "static_mixture_v1/64001",
        "--stage5-cohort",
        str(tmp_path / "cohort.jsonl"),
        "--stage5-checkpoint",
        str(tmp_path / "checkpoint.pt"),
        "--stage5-log-dir",
        str(tmp_path / "logs"),
        "--stage5-shard-output-dir",
        str(tmp_path / "shards"),
        "--stage5-merged-output",
        str(tmp_path / "merged.jsonl"),
        *cohort_args,
    ]
    with pytest.raises(SystemExit) as exc_info:
        transfer_command.main(argv)
    assert exc_info.value.code == 2
    assert calls == []


def test_stage7_teacher_validation_reads_nested_complete_identity_descriptors() -> None:
    """Stage-0 persisted descriptors keep identity fields below complete_identity."""

    selected = []
    rows = []
    initial_action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    for index in range(460):
        identity = {
            "source_checkpoint_id": f"checkpoint-{index}",
            "source_seed": index,
            "source_run_id": f"run-{index}",
            "source_battle_index": index,
            "distribution_kind": "assisted_run",
            "checkpoint_information_regime": "full_simulator_state_oracle_like",
        }
        selected.append(
            {
                "component": "assist_hp75_potion",
                "structural_metadata": {"act": 2},
                "complete_identity_sha256": f"{index + 1:064x}",
                "complete_identity": identity,
            }
        )
        rows.append(
            SimpleNamespace(
                row_index=index,
                source_checkpoint_id=identity["source_checkpoint_id"],
                source_seed=identity["source_seed"],
                source_run_id=identity["source_run_id"],
                source_battle_index=identity["source_battle_index"],
                source_distribution_kind=identity["distribution_kind"],
                checkpoint_information_regime=identity["checkpoint_information_regime"],
                soft_visit_target={"target": 1.0},
                controller_provenance={
                    "config": {
                        "information_regime": "full_simulator_state_oracle_like",
                        "search_budget": {"simulations": 100},
                        "root_selection_rule": "highest_mean",
                        "action_space": initial_action_space,
                    }
                },
            )
        )
    # JSON round-trip mirrors the compact manifest's retained descriptor shape.
    manifest = json.loads(json.dumps({"selected_sources": selected}))
    dataset = SimpleNamespace(
        records=rows,
        information_regime="full_simulator_state_oracle_like",
        action_space_config=initial_action_space,
        controller_provenance={
            "config": {
                "information_regime": "full_simulator_state_oracle_like",
                "search_budget": {"simulations": 100},
                "root_selection_rule": "highest_mean",
                "action_space": initial_action_space,
            }
        },
        problems=[],
    )
    transfer_command._validate_teacher_against_selected_manifest(dataset, manifest)
    manifest["selected_sources"][0]["source_checkpoint_id"] = "forged-top-level"
    transfer_command._validate_teacher_against_selected_manifest(dataset, manifest)
    dataset.action_space_config = ActionSpaceConfig.include_all().to_dict()
    with pytest.raises(ValueError, match="dataset action space"):
        transfer_command._validate_teacher_against_selected_manifest(dataset, manifest)
    dataset.action_space_config = initial_action_space
    dataset.controller_provenance["config"]["action_space"] = (
        ActionSpaceConfig.include_all().to_dict()
    )
    with pytest.raises(ValueError, match="frozen T043 contract"):
        transfer_command._validate_teacher_against_selected_manifest(dataset, manifest)
    dataset.controller_provenance["config"]["action_space"] = initial_action_space
    rows[0].controller_provenance["config"]["action_space"] = (
        ActionSpaceConfig.include_all().to_dict()
    )
    with pytest.raises(ValueError, match="action-space mismatch"):
        transfer_command._validate_teacher_against_selected_manifest(dataset, manifest)


def test_t044_dependent_stage_routes_only_frozen_roles_and_ranges(
    tmp_path: Path,
) -> None:
    calls = []

    def shard_runner(*args, **kwargs):
        calls.append((args, kwargs))
        return kwargs["record_range"]

    def merger(**kwargs):
        return kwargs

    controller = SimpleNamespace(action_space=object())
    output, shard_records = transfer_command.run_t064_t044_dependent_stage(
        adapter_factory=lambda: object(),
        cohort_path=Path("cohort.jsonl"),
        controller_arms=(
            ("guided", transfer_command.T044_DEPENDENT_ROLES[0], controller),
            ("raw", transfer_command.T044_DEPENDENT_ROLES[1], controller),
        ),
        cohort_kind="assist_hp50",
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
        shard_runner=shard_runner,
        merger=merger,
        report_writer=lambda _path, _report: None,
    )
    assert sorted(kwargs["record_range"] for _, kwargs in calls) == sorted(
        transfer_command.T044_ASSIST_HP50_RANGES
    )
    assert output["expected_ranges"] == transfer_command.T044_ASSIST_HP50_RANGES
    assert [record["return_code"] for record in shard_records] == [0] * 16
    with pytest.raises(ValueError, match="dependent roles"):
        transfer_command.run_t064_t044_dependent_stage(
            adapter_factory=lambda: object(),
            cohort_path=Path("cohort.jsonl"),
            controller_arms=(("wrong", "a display label", controller),),
            cohort_kind="assist_0",
            log_dir=tmp_path / "other-logs",
            shard_output_dir=tmp_path / "other-shards",
            merged_output_path=tmp_path / "other-merged.jsonl",
            shard_runner=shard_runner,
            merger=merger,
            report_writer=lambda _path, _report: None,
        )


def test_t044_fallback_routes_only_baseline_and_scripted_once_per_cohort(
    tmp_path: Path,
) -> None:
    calls = []

    def shard_runner(*args, **kwargs):
        calls.append(kwargs)
        return kwargs["record_range"]

    controller = SimpleNamespace(action_space=object())
    output, records = transfer_command.run_t064_t044_independent_fallback_stage(
        adapter_factory=lambda: object(),
        cohort_path=Path("cohort.jsonl"),
        controller_arms=(
            ("baseline", transfer_command.T044_INDEPENDENT_ROLES[0], controller),
            ("scripted", transfer_command.T044_INDEPENDENT_ROLES[1], controller),
        ),
        cohort_kind="assist_0",
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
        shard_runner=shard_runner,
        merger=lambda **kwargs: kwargs,
        report_writer=lambda _path, _report: None,
    )
    assert len(calls) == len(records) == 16
    assert output["expected_ranges"] == transfer_command.T044_ASSIST_0_RANGES
    assert all(
        tuple(item[1] for item in call["controller_arms"])
        == transfer_command.T044_INDEPENDENT_ROLES
        for call in calls
    )


def test_t044_semantics_bind_raw_checkpoint_and_scripted_public_contract() -> None:
    checkpoint = {"path": "checkpoint.pt", "sha256": "a" * 64}
    artifact = "torch-policy-value-checkpoint-v1-sha256:" + checkpoint["sha256"]
    guided = {
        "kind": "model_guided_oracle_battle_search",
        "config": {
            "information_regime": "full_simulator_state_oracle_like",
            "search_budget": {"simulations": 1},
            "root_selection_rule": "highest_mean",
            "action_space": {"excluded_kinds": ["potion"]},
            "guidance_scorer": {
                "policy_probability_weight": 0.1,
                "checkpoint_provenance": {
                    "checkpoint_artifact_id": artifact,
                    "checkpoint_path": "checkpoint.pt",
                },
            },
        },
    }
    raw = {
        "kind": "search_guidance_public_policy",
        "config": {
            "information_regime": "normal_public_policy",
            "guidance_scorer": {
                "checkpoint_provenance": {
                    "checkpoint_artifact_id": artifact,
                    "checkpoint_path": "checkpoint.pt",
                }
            },
        },
    }
    report = SimpleNamespace(
        arms=tuple(
            SimpleNamespace(role=role) for role in transfer_command.T044_DEPENDENT_ROLES
        ),
        comparison_config={
            "controller_roles": {
                "guided": transfer_command.T044_DEPENDENT_ROLES[0],
                "raw": transfer_command.T044_DEPENDENT_ROLES[1],
            },
            "controller_provenance": {"guided": guided, "raw": raw},
        },
    )
    transfer_command._validate_t044_controller_semantics(report, checkpoint=checkpoint)
    raw["config"]["guidance_scorer"]["checkpoint_provenance"]["checkpoint_path"] = (
        "forged.pt"
    )
    with pytest.raises(ValueError, match="raw checkpoint identity"):
        transfer_command._validate_t044_controller_semantics(
            report, checkpoint=checkpoint
        )

    scripted = SimpleNamespace(
        arms=tuple(
            SimpleNamespace(role=role)
            for role in transfer_command.T044_INDEPENDENT_ROLES
        ),
        comparison_config={
            "controller_roles": {
                "baseline": transfer_command.T044_INDEPENDENT_ROLES[0],
                "scripted": transfer_command.T044_INDEPENDENT_ROLES[1],
            },
            "controller_provenance": {
                "baseline": {
                    "kind": "oracle_battle_search",
                    "config": {
                        "information_regime": "full_simulator_state_oracle_like",
                        "search_budget": {"simulations": 1},
                        "root_selection_rule": "highest_mean",
                        "action_space": {"excluded_kinds": ["potion"]},
                    },
                },
                "scripted": {
                    "kind": "decision_policy",
                    "config": {
                        "information_regime": "normal_public_policy",
                        "policy_class": "ScoredActionPolicy",
                    },
                },
            },
        },
    )
    transfer_command._validate_t044_controller_semantics(scripted, checkpoint=None)
    scripted.comparison_config["controller_provenance"]["scripted"]["kind"] = "forged"
    with pytest.raises(ValueError, match="scripted public-policy"):
        transfer_command._validate_t044_controller_semantics(scripted, checkpoint=None)


def test_t064_transfer_gates_and_historical_t070_wrapper_are_frozen() -> None:
    metrics = {
        "curriculum_t052_prior_value_wins": {64001: 10, 64002: 11},
        "static_t052_prior_value_wins": {64001: 9, 64002: 10},
        "paired_t052_win_deltas": {64001: 1, 64002: 1},
        "t052_subset_deltas": {"boss": 1, "act2_plus": 0},
        "curriculum_t044_assist_hp50_model_guided_wins": 12,
        "static_t044_assist_hp50_model_guided_wins": 10,
        "curriculum_t044_assist_hp50_raw_policy_wins": 9,
        "static_t044_assist_hp50_raw_policy_wins": 9,
        "curriculum_t044_assist_0_model_guided_wins": 8,
        "static_t044_assist_0_model_guided_wins": 9,
    }
    assert all(transfer_command.compute_transfer_gates(metrics).values())
    historical = {
        "schema_id": "t070-frozen-experiment-manifest-v1",
        "code_commit": "b" * 40,
        "primary_shard_ranges": list(transfer_command.T070_T052_RANGES),
        "primary_stage_inventory": [
            {
                "stage_name": "equal-prior-value-0100",
                "arm": "prior_value",
                "family": "equal_nominal",
                "native_budget": 100,
                "tree_geometry_enabled": False,
            }
        ],
    }
    wrapper = transfer_command.t064_t070_wrapper(
        current_code_commit="a" * 40,
        frozen_t070_manifest=historical,
        frozen_identity={"path": "historical.json", "sha256": "c" * 64, "bytes": 1},
        checkpoint_identity={"path": "new.pt", "sha256": "d" * 64, "bytes": 2},
    )
    assert wrapper["arm"] == "prior_value"
    assert wrapper["tree_geometry_enabled"] is False
    assert wrapper["worker_count"] == 16


def test_t070_prior_value_stage_dispatches_all_real_runner_arguments(
    tmp_path: Path,
) -> None:
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        kwargs["output_path"].write_text("{}", encoding="utf-8")
        return {"command_passed": True}

    def merger(**kwargs):
        return {
            "arm": "prior_value",
            "native_budget": 100,
            "command_passed": True,
            "problems": [],
        }

    merged, records = transfer_command.run_t064_t070_prior_value_stage(
        shard_runner=runner,
        merger=merger,
        runner_kwargs={
            "cohort_path": Path("cohort.jsonl"),
            "adapter_factory": object(),
            "code_commit": "a" * 40,
            "t064_wrapper": {
                "arm": "prior_value",
                "native_budget": 100,
                "tree_geometry_enabled": False,
                "shard_ranges": list(transfer_command.T070_T052_RANGES),
                "worker_count": 16,
                "historical_code_commit": "b" * 40,
                "current_code_commit": "a" * 40,
            },
        },
        shard_dir=tmp_path / "shards",
        log_dir=tmp_path / "logs",
        merged_output_path=tmp_path / "merged.json",
    )
    assert merged["arm"] == "prior_value"
    assert len(calls) == len(records) == 16
    assert sorted(call["record_range"] for call in calls) == sorted(
        transfer_command.T070_T052_RANGES
    )
    assert all(call["arm"] == "prior_value" for call in calls)
    assert all("t064_wrapper" not in call for call in calls)


def test_t070_script_runner_uses_the_repository_argument_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = []

    def fake_run(command, **kwargs):
        captured.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(transfer_command.subprocess, "run", fake_run)
    completed = transfer_command.run_t064_t070_shard_script(
        script_path=Path("scripts/run_t070_search_stage_shard.py"),
        python_executable="python",
        cohort_path=tmp_path / "t052.jsonl",
        checkpoint_path=tmp_path / "checkpoint.pt",
        wrapper_manifest_path=tmp_path / "t064-wrapper.json",
        native_preflight_path=tmp_path / "preflight.json",
        native_checkout=tmp_path / "native",
        native_build_root=tmp_path / "native" / "build",
        code_commit="a" * 40,
        selection_key="static_mixture_v1:64001",
        output_path=tmp_path / "shard.json",
        record_range="88:93",
        shard_index=15,
    )
    assert completed.returncode == 0
    command, kwargs = captured[0]
    assert "--output-dir" not in command
    assert command[command.index("--output") + 1] == str(tmp_path / "shard.json")
    assert command[command.index("--frozen-manifest") + 1] == str(
        tmp_path / "t064-wrapper.json"
    )
    assert command[command.index("--stage-name") + 1] == "equal-prior-value-0100"
    assert command[command.index("--family") + 1] == "equal_nominal"
    assert command[command.index("--range-kind") + 1] == "primary"
    assert command[command.index("--t064-selection") + 1] == "static_mixture_v1:64001"
    assert kwargs == {"check": False, "text": True, "capture_output": True}


def test_stage6_cli_invalid_baseline_starts_zero_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    for name in ("baseline.json", "contract.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [
            {
                "stage": "stage6_t070",
                "checkpoint_arm": "static_mixture_v1/64001",
                "ranges": list(transfer_command.T070_T052_RANGES),
            }
        ],
    )
    monkeypatch.setattr(
        transfer_command, "_validate_t064_stage6_preflight", lambda **_kwargs: False
    )
    shard_calls: list[object] = []
    monkeypatch.setattr(
        transfer_command,
        "run_t064_t070_shard_script",
        lambda **kwargs: shard_calls.append(kwargs),
    )
    with pytest.raises(SystemExit):
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage6_t070",
                "--checkpoint-arm",
                "static_mixture_v1/64001",
                "--attempt-root",
                str(tmp_path / "attempts"),
                "--stage6-shard-script",
                "scripts/run_t070_search_stage_shard.py",
                "--stage6-cohort",
                str(tmp_path / "cohort.jsonl"),
                "--stage6-checkpoint",
                str(tmp_path / "checkpoint.pt"),
                "--stage6-wrapper-manifest",
                str(manifest_path),
                "--stage6-native-preflight",
                str(tmp_path / "preflight.json"),
                "--stage6-native-checkout",
                str(tmp_path / "native"),
                "--stage6-native-build-root",
                str(tmp_path / "native-build"),
                "--stage6-baseline-report",
                str(tmp_path / "baseline.json"),
                "--stage6-baseline-contract",
                str(tmp_path / "contract.json"),
                "--stage6-merged-output",
                str(tmp_path / "merged.json"),
            ]
        )
    assert shard_calls == []


def test_stage6_cli_valid_preflight_invokes_exactly_sixteen_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "t064-curriculum-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    for name in ("baseline.json", "contract.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(transfer_command, "load_compact_json", lambda _stream: {})
    monkeypatch.setattr(
        transfer_command,
        "build_t064_stage_execution_plan",
        lambda _manifest, *, code_commit: [
            {
                "stage": "stage6_t070",
                "checkpoint_arm": "static_mixture_v1/64001",
                "ranges": list(transfer_command.T070_T052_RANGES),
            }
        ],
    )
    monkeypatch.setattr(
        transfer_command, "_validate_t064_stage6_preflight", lambda **_kwargs: True
    )
    events: list[str] = []
    rebind_calls: list[dict[str, object]] = []

    def verify_checkout(checkout: Path, code_commit: str) -> str:
        events.append("verify")
        assert checkout == Path.cwd()
        assert code_commit == "a" * 40
        return code_commit

    monkeypatch.setattr(transfer_command, "verify_exact_git_checkout", verify_checkout)

    def rebind(**kwargs):
        events.append("rebind")
        rebind_calls.append(kwargs)
        return {}

    monkeypatch.setattr(transfer_command, "rebind_t064_t070_execution_commit", rebind)
    calls: list[dict[str, object]] = []

    def shard(**kwargs):
        events.append("shard")
        calls.append(kwargs)
        kwargs["output_path"].write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(transfer_command, "run_t064_t070_shard_script", shard)
    merged: list[dict[str, object]] = []
    monkeypatch.setattr(
        transfer_command,
        "merge_single_arm_stage",
        lambda **kwargs: (
            kwargs["output_path"].write_text("{}", encoding="utf-8"),
            merged.append(kwargs),
            {"command_passed": True, "problems": []},
        )[-1],
    )
    assert (
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage6_t070",
                "--checkpoint-arm",
                "static_mixture_v1/64001",
                "--attempt-root",
                str(tmp_path / "attempts"),
                "--stage6-shard-script",
                "scripts/run_t070_search_stage_shard.py",
                "--stage6-cohort",
                str(tmp_path / "cohort.jsonl"),
                "--stage6-checkpoint",
                str(tmp_path / "checkpoint.pt"),
                "--stage6-wrapper-manifest",
                str(manifest_path),
                "--stage6-native-preflight",
                str(tmp_path / "preflight.json"),
                "--stage6-native-checkout",
                str(tmp_path / "native"),
                "--stage6-native-build-root",
                str(tmp_path / "native-build"),
                "--stage6-baseline-report",
                str(tmp_path / "baseline.json"),
                "--stage6-baseline-contract",
                str(tmp_path / "contract.json"),
                "--stage6-merged-output",
                str(tmp_path / "merged.json"),
                "--stage6-rebind-from-code-commit",
                "b" * 40,
            ]
        )
        == 0
    )
    assert len(calls) == 16
    assert events[:2] == ["verify", "rebind"]
    assert rebind_calls == [
        {
            "manifest_path": manifest_path,
            "expected_previous_code_commit": "b" * 40,
            "new_code_commit": "a" * 40,
        }
    ]
    assert sorted(call["record_range"] for call in calls) == sorted(
        transfer_command.T070_T052_RANGES
    )
    assert len(merged) == 1 and len(merged[0]["shard_paths"]) == 16

    events.clear()
    calls.clear()
    with pytest.raises(ValueError, match="refuses to overwrite"):
        transfer_command.main(
            [
                "--dry-run-manifest",
                str(manifest_path),
                "--code-commit",
                "a" * 40,
                "--stage",
                "stage6_t070",
                "--checkpoint-arm",
                "static_mixture_v1/64001",
                "--attempt-root",
                str(tmp_path / "attempts-second"),
                "--stage6-shard-script",
                "scripts/run_t070_search_stage_shard.py",
                "--stage6-cohort",
                str(tmp_path / "cohort.jsonl"),
                "--stage6-checkpoint",
                str(tmp_path / "checkpoint.pt"),
                "--stage6-wrapper-manifest",
                str(manifest_path),
                "--stage6-native-preflight",
                str(tmp_path / "preflight.json"),
                "--stage6-native-checkout",
                str(tmp_path / "native"),
                "--stage6-native-build-root",
                str(tmp_path / "native-build"),
                "--stage6-baseline-report",
                str(tmp_path / "baseline.json"),
                "--stage6-baseline-contract",
                str(tmp_path / "contract.json"),
                "--stage6-merged-output",
                str(tmp_path / "merged.json"),
                "--stage6-rebind-from-code-commit",
                "b" * 40,
            ]
        )
    assert events == []
    assert calls == []


def test_t070_existing_reader_accepts_persisted_t064_checkpoint_selection(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_identity = {
        "path": str(checkpoint),
        "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "bytes": checkpoint.stat().st_size,
    }
    frozen = tmp_path / "t070-frozen-experiment.json"
    frozen.write_text(
        json.dumps(
            {
                "schema_id": "t070-frozen-experiment-manifest-v1",
                "code_commit": "b" * 40,
                "primary_shard_ranges": list(transfer_command.T070_T052_RANGES),
                "primary_stage_inventory": [
                    {
                        "stage_name": "equal-prior-value-0100",
                        "arm": "prior_value",
                        "family": "equal_nominal",
                        "native_budget": 100,
                        "tree_geometry_enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    frozen_identity = {
        "path": str(frozen),
        "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
        "bytes": frozen.stat().st_size,
    }
    outer = tmp_path / "t064-curriculum-wrapper.json"
    outer.write_text(
        json.dumps(
            {
                "schema_id": "t064-curriculum-manifest-v1",
                "code_commit": "a" * 40,
                "t070_stage_manifest": transfer_command.build_t064_t070_checkpoint_selections(
                    current_code_commit="a" * 40,
                    frozen_t070_manifest=json.loads(frozen.read_text(encoding="utf-8")),
                    frozen_identity=frozen_identity,
                    checkpoints={
                        f"{arm}:{seed}": checkpoint_identity
                        for arm, seed in TRAINING_RUN_ORDER
                    },
                ),
            }
        ),
        encoding="utf-8",
    )
    assert (
        expected_checkpoint_identity_from_stage_manifest(
            outer, t064_selection="static_mixture_v1:64001"
        )
        == checkpoint_identity
    )


def test_single_manifest_t070_selector_requires_all_four_frozen_keys() -> None:
    checkpoint = {"path": "checkpoint.pt", "sha256": "a" * 64, "bytes": 1}
    stage = {
        "frozen_t070_manifest": {
            "path": "frozen.json",
            "sha256": "b" * 64,
            "bytes": 1,
        },
        "historical_code_commit": "b" * 40,
        "current_code_commit": "a" * 40,
        "arm": "prior_value",
        "native_budget": 100,
        "tree_geometry_enabled": False,
        "projection_mode": "accepted_t069_search_scope_projection",
        "shard_ranges": list(contiguous_ranges(93)),
        "worker_count": 16,
        "checkpoint_selections": {
            f"{arm}:{seed}": {"checkpoint": checkpoint}
            for arm, seed in TRAINING_RUN_ORDER
        },
    }
    from sts_combat_rl.sim import t064_curriculum as curriculum_sim

    curriculum_sim._validate_t070_stage_manifest(stage, {"code_commit": "c" * 40})
    stage["historical_code_commit"] = stage["current_code_commit"]
    with pytest.raises(ValueError, match="selector contract"):
        curriculum_sim._validate_t070_stage_manifest(stage, {"code_commit": "c" * 40})
    stage["historical_code_commit"] = "b" * 40
    del stage["checkpoint_selections"]["static_mixture_v1:64001"]
    with pytest.raises(ValueError, match="exactly four"):
        curriculum_sim._validate_t070_stage_manifest(stage, {"code_commit": "c" * 40})


def test_stage7_t070_rows_require_exact_order_clean_rows_and_frozen_subsets() -> None:
    rows = [
        {
            "cohort_index": index,
            "problems": [],
            "structural_metadata": {
                "room_type": "BOSS" if index < 88 else "MONSTER",
                "act": 1 if index < 88 else 2,
            },
        }
        for index in range(93)
    ]
    cohort = SimpleNamespace(
        identity="t052",
        records=[
            SimpleNamespace(
                source_checkpoint_id=None,
                structural_metadata=row["structural_metadata"],
            )
            for row in rows
        ],
    )
    assert transfer_command._validate_t070_rows(rows, cohort=cohort) == rows
    rows[92] = "forged-non-mapping"
    with pytest.raises(ValueError, match="mapping"):
        transfer_command._validate_t070_rows(rows, cohort=cohort)


def test_stage7_aggregation_consumes_complete_representative_mock_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer_commit = "a" * 40
    current_commit = "c" * 40
    root = tmp_path / "artifact-root"
    root.mkdir()

    def write(name: str, payload: object | None = None) -> Path:
        path = tmp_path / name
        path.write_text(
            json.dumps({} if payload is None else payload), encoding="utf-8"
        )
        return path

    def identity(path: Path) -> dict[str, object]:
        data = path.read_bytes()
        return {
            "path": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }

    teacher_path = write("teacher.jsonl")
    trainer_path = write("trainer.jsonl")
    checkpoint_paths = {
        key: write(f"{key[0]}-{key[1]}.pt", {"checkpoint": list(key)})
        for key in TRAINING_RUN_ORDER
    }
    checkpoints = {key: identity(path) for key, path in checkpoint_paths.items()}
    frozen_manifest_path = write("t070-frozen.json")
    baseline_path = write("t070-baseline.json")
    t052_path = write("t052-cohort.jsonl")
    frozen_manifest_identity = identity(frozen_manifest_path)
    t052_identity = identity(t052_path)
    t044_cohort_paths = {
        "assist_0": write("assist-0-cohort.jsonl"),
        "assist_hp50": write("assist-hp50-cohort.jsonl"),
    }
    t044_independent_paths = {
        name: write(f"{name}-independent.jsonl") for name in t044_cohort_paths
    }
    t044_paths = {
        key: {
            name: write(f"{key[0]}-{key[1]}-{name}.jsonl") for name in t044_cohort_paths
        }
        for key in TRAINING_RUN_ORDER
    }
    t052_records = [
        SimpleNamespace(
            cohort_index=index,
            source_checkpoint_id=f"source-{index}",
            structural_metadata={
                "room_type": "BOSS" if index < 88 else "MONSTER",
                "act": 1 if index < 88 else 2,
            },
        )
        for index in range(93)
    ]
    t070_rows = [
        {
            "cohort_index": index,
            "source_checkpoint_id": record.source_checkpoint_id,
            "structural_metadata": record.structural_metadata,
            "termination_status": "win" if index % 2 == 0 else "loss",
            "problems": [],
        }
        for index, record in enumerate(t052_records)
    ]
    t070_paths = {
        key: write(
            f"{key[0]}-{key[1]}-t070.json",
            {"arm_report": {"records": t070_rows}},
        )
        for key in TRAINING_RUN_ORDER
    }
    checkpoint_selections = {
        f"{arm}:{seed}": {"checkpoint": checkpoints[(arm, seed)]}
        for arm, seed in TRAINING_RUN_ORDER
    }
    manifest = {
        "code_commit": producer_commit,
        "source_adequacy": True,
        "complete_source_audit": {
            "status": "complete",
            "selected_restore_failure_count": 0,
        },
        "t070_stage_manifest": {
            "frozen_t070_manifest": frozen_manifest_identity,
            "checkpoint_selections": checkpoint_selections,
        },
    }
    training = {
        "runs": [
            {
                "arm": arm,
                "seed": seed,
                "completion_status": "complete",
                "checkpoint": checkpoints[(arm, seed)],
            }
            for arm, seed in TRAINING_RUN_ORDER
        ]
    }
    (root / "t064-curriculum-manifest.json").write_text("{}", encoding="utf-8")
    (root / "t064-training-run-report.json").write_text("{}", encoding="utf-8")

    def load_compact(stream):
        return manifest if "curriculum-manifest" in stream.name else training

    dependent_report = SimpleNamespace(
        arms=tuple(
            SimpleNamespace(
                role=role,
                report=SimpleNamespace(authoritative_wins=1),
            )
            for role in transfer_command.T044_DEPENDENT_ROLES
        )
    )
    t052_cohort = SimpleNamespace(identity="t052", records=t052_records, problems=[])
    written: dict[str, object] = {}
    monkeypatch.setattr(transfer_command, "load_compact_json", load_compact)
    monkeypatch.setattr(
        transfer_command, "_validate_stage_summary_evidence", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command, "validate_external_frozen_identity", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command, "load_oracle_teacher_dataset_jsonl", lambda _stream: object()
    )
    monkeypatch.setattr(
        transfer_command, "load_trainer_input_dataset_jsonl", lambda _stream: object()
    )
    monkeypatch.setattr(
        transfer_command,
        "_validate_teacher_against_selected_manifest",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transfer_command,
        "_validate_trainer_against_selected_manifest",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transfer_command, "_validate_frozen_manifest_plans", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command,
        "_validate_t044_frozen_cohort",
        lambda contract, *, cohort_kind: SimpleNamespace(
            identity=contract["identity"], records=[]
        ),
    )
    monkeypatch.setattr(
        transfer_command,
        "load_de_assisted_fixed_cohort_comparison_jsonl",
        lambda _stream: dependent_report,
    )
    monkeypatch.setattr(
        transfer_command, "validate_t044_independent_report", lambda *_a, **_k: True
    )
    monkeypatch.setattr(
        transfer_command, "validate_t044_dependent_report", lambda *_a, **_k: True
    )
    monkeypatch.setattr(
        transfer_command, "_validate_t044_controller_semantics", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command,
        "load_t070_frozen_contract",
        lambda *_a, **_k: {"input_identities": {"t052_fixed_cohort": t052_identity}},
    )
    monkeypatch.setattr(
        transfer_command, "load_fixed_cohort_jsonl", lambda _stream: t052_cohort
    )
    monkeypatch.setattr(
        transfer_command, "validate_t070_baseline_reuse", lambda *_a, **_k: True
    )
    monkeypatch.setattr(
        transfer_command, "validate_t070_prior_value_report", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command, "_validate_stage_summary_crosslinks", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        transfer_command,
        "write_compact_json",
        lambda path, payload: written.__setitem__(path.name, payload),
    )
    monkeypatch.setattr(
        transfer_command, "independent_rehash", lambda *_a, **_k: {"ok": True}
    )
    frozen_inputs = {
        "teacher": identity(teacher_path),
        "trainer_input": identity(trainer_path),
        "t044_cohorts": {
            name: {
                "identity": name,
                "record_count": 21 if name == "assist_0" else 38,
                "artifact": identity(path),
            }
            for name, path in t044_cohort_paths.items()
        },
        "t044_independent_reports": {
            name: identity(path) for name, path in t044_independent_paths.items()
        },
        "t070": {
            "manifest": frozen_manifest_identity,
            "baseline": identity(baseline_path),
            "baseline_contract": {},
            "cohort": t052_identity,
            "cohort_identity": "t052",
            "wrappers": {
                f"{arm}:{seed}": {
                    "historical_code_commit": "b" * 40,
                    "current_code_commit": current_commit,
                }
                for arm, seed in TRAINING_RUN_ORDER
            },
        },
    }

    result = transfer_command.aggregate_t064_stage7_from_artifacts(
        root=root,
        code_commit=current_commit,
        teacher_path=teacher_path,
        trainer_input_path=trainer_path,
        t044_paths=t044_paths,
        t070_paths=t070_paths,
        stage_summary={},
        frozen_inputs=frozen_inputs,
    )

    assert result["decision"]["experiment_complete"] is True
    assert result["decision"]["terminal_case"] in {"Case A", "Case B"}
    assert set(written) == {"t064-stage-summary.json", "t064-transfer-decision.json"}


def test_stage2_to_7_dry_plan_has_exact_worker_range_and_stage_inventory() -> None:
    manifest = {
        "code_commit": "a" * 40,
        "complete_source_audit": {
            "status": "complete",
            "selected_restore_failure_count": 0,
        },
        "selected_sources": [{} for _ in range(460)],
        "teacher_shard_ranges": list(contiguous_ranges(460)),
    }
    plan = transfer_command.build_t064_stage_execution_plan(
        manifest, code_commit="b" * 40
    )
    assert plan[0]["workers"] == plan[0]["shards"] == 16
    assert plan[0]["ranges"] == list(contiguous_ranges(460))
    assert plan[1] == {
        "stage": "stage3_trainer",
        "workers": 16,
        "shards": 16,
        "ranges": list(contiguous_ranges(460)),
    }
    assert next(row for row in plan if row["stage"] == "stage4_training") == {
        "stage": "stage4_training",
        "workers": 2,
        "shards": 4,
        "runs": [f"{arm}/{seed}" for arm, seed in TRAINING_RUN_ORDER],
    }
    assert len([row for row in plan if row["stage"] == "stage5_t044"]) == 8
    assert len([row for row in plan if row["stage"] == "stage6_t070"]) == 4
    assert plan[-1]["stage"] == "stage7_aggregate"


def test_stage_summary_allows_reused_stage0_to_3_producer_commits_only() -> None:
    producer_commit = "a" * 40
    native_commit = "b" * 40
    current_commit = "c" * 40

    def stage(
        name: str,
        *,
        code_commit: str,
        workers: int = 1,
        shards: int = 1,
        ranges: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "name": name,
            "status": "complete",
            "code_commit": code_commit,
            "native_commit": native_commit,
            "failure_count": 0,
            "return_codes": [0],
            "outputs": {},
            "referenced_artifacts": [],
            "workers": workers,
            "shards": shards,
            "ranges": ranges or [],
        }

    teacher_ranges = list(contiguous_ranges(460))
    stages = [
        stage("stage0_inputs", code_commit=producer_commit),
        stage("stage1_source_audit", code_commit=producer_commit),
        stage(
            "stage2_teacher",
            code_commit=producer_commit,
            workers=16,
            shards=16,
            ranges=teacher_ranges,
        ),
        stage("stage3_trainer", code_commit=producer_commit),
        stage(
            "stage4_training",
            code_commit=current_commit,
            workers=2,
            shards=4,
        ),
        *[
            stage(
                f"stage5_checkpoint_{index}",
                code_commit=current_commit,
                workers=16,
                shards=16,
                ranges=list(transfer_command.T044_ASSIST_0_RANGES),
            )
            for index in range(8)
        ],
        *[
            stage(
                f"stage6_checkpoint_{index}",
                code_commit=current_commit,
                workers=16,
                shards=16,
                ranges=list(transfer_command.T070_T052_RANGES),
            )
            for index in range(4)
        ],
        stage("stage7_aggregate", code_commit=current_commit),
    ]
    summary = {
        "problems": [],
        "reuse_inventory": [
            {"cohort": cohort, "disposition": "reuse_historical_four_arm"}
            for cohort in ("assist_0", "assist_hp50")
        ],
        "stages": stages,
    }
    manifest = {
        "source_adequacy": True,
        "native_commit": native_commit,
        "teacher_shard_ranges": teacher_ranges,
    }

    transfer_command._validate_stage_summary_evidence(
        summary, manifest=manifest, code_commit=current_commit
    )
    stages[4]["code_commit"] = producer_commit
    with pytest.raises(ValueError, match="failure/stale identity: stage4_training"):
        transfer_command._validate_stage_summary_evidence(
            summary, manifest=manifest, code_commit=current_commit
        )


def test_stage3_production_routes_all_sixteen_frozen_ranges_through_fork(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The script path dispatches descriptors, never a synthetic bridge object."""

    from sts_combat_rl.sim import oracle_teacher_search_guidance as guidance

    identities = [f"{index:064x}" for index in range(460)]
    selected = [
        {
            "complete_identity_sha256": identity,
            "complete_identity": {
                "source_checkpoint_id": f"checkpoint-{index}",
                "source_seed": index,
                "source_run_id": f"run-{index}",
                "source_battle_index": index,
                "distribution_kind": "assisted_run",
                "checkpoint_information_regime": "full_simulator_state_oracle_like",
            },
        }
        for index, identity in enumerate(identities)
    ]
    manifest = {
        "code_commit": "a" * 40,
        "complete_source_audit": {
            "status": "complete",
            "selected_restore_failure_count": 0,
        },
        "selected_sources": selected,
        "teacher_shard_ranges": list(contiguous_ranges(460)),
        "teacher_worker_count": 16,
    }
    teacher = _empty_oracle_teacher_dataset()
    teacher_path = tmp_path / "teacher.jsonl"
    teacher_path.write_text("teacher", encoding="utf-8")
    calls: list[tuple[int, str]] = []

    @dataclass
    class Pool:
        records: list[dict[str, str]]

    pool = Pool(
        records=[{"complete_identity_sha256": identity} for identity in identities]
    )

    monkeypatch.setattr(
        transfer_command, "load_oracle_teacher_dataset_jsonl", lambda _: teacher
    )
    monkeypatch.setattr(
        transfer_command, "load_selected_source_pool", lambda _: (pool, selected)
    )
    monkeypatch.setattr(
        transfer_command, "complete_source_identity", lambda record: record
    )
    monkeypatch.setattr(
        transfer_command, "_validate_teacher_against_selected_manifest", lambda *_: None
    )
    monkeypatch.setattr(
        transfer_command, "_file_identity", lambda _: {"sha256": "b" * 64}
    )
    monkeypatch.setattr(
        transfer_command, "_write_trainer_input_shard_atomically", lambda *_: None
    )

    def direct_builder(*, selected_sources, **_kwargs):
        return SimpleNamespace(
            records=[
                SimpleNamespace(
                    source_metadata={
                        "t064_complete_identity_sha256": item[
                            "complete_identity_sha256"
                        ]
                    }
                )
                for item in selected_sources
            ]
        )

    monkeypatch.setattr(
        guidance,
        "build_oracle_teacher_search_guidance_dataset_from_direct_provenance",
        direct_builder,
    )

    def fork_dispatch(*, ranges, log_dir, worker, backend):
        assert backend == "fork"
        del log_dir
        descriptors = []
        for index, record_range in enumerate(ranges):
            calls.append((index, record_range))
            descriptors.append(worker(index, record_range))
        return descriptors, [{"return_code": 0} for _ in ranges]

    monkeypatch.setattr(transfer_command, "dispatch_t064_shards", fork_dispatch)
    monkeypatch.setattr(
        transfer_command, "_iter_t064_persisted_trainer_shards", lambda **_: iter(())
    )
    merged = SimpleNamespace(
        records=[
            SimpleNamespace(source_metadata={"t064_complete_identity_sha256": identity})
            for identity in identities
        ]
    )
    monkeypatch.setattr(
        transfer_command, "_merge_t064_trainer_shard_stream", lambda **_: merged
    )

    dataset, _report, mapping = transfer_command.run_t064_stage3_production(
        selected_manifest=manifest,
        teacher_path=teacher_path,
        output_path=tmp_path / "trainer.jsonl",
        shard_output_dir=tmp_path / "shards",
        log_dir=tmp_path / "logs",
        code_commit="a" * 40,
    )

    assert dataset is merged
    assert calls == list(enumerate(contiguous_ranges(460)))
    assert mapping[identities[-1]] == 459


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_stage3_production_actual_fork_invokes_direct_converter_and_merges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the production Stage-3 route with fork-safe, no-simulator stubs."""

    from sts_combat_rl.sim import oracle_teacher_search_guidance as guidance
    from sts_combat_rl.sim.trainer_input import load_trainer_input_dataset_jsonl
    from t009_helpers import make_trainer_dataset

    identities = [f"{index:064x}" for index in range(460)]
    selected = [
        {
            "complete_identity_sha256": identity,
            "complete_identity": {
                "source_checkpoint_id": f"checkpoint-{index}",
                "source_seed": index,
                "source_run_id": f"run-{index}",
                "source_battle_index": index,
                "distribution_kind": "assisted_run",
                "checkpoint_information_regime": "full_simulator_state_oracle_like",
            },
        }
        for index, identity in enumerate(identities)
    ]
    manifest = {
        "code_commit": "a" * 40,
        "complete_source_audit": {
            "status": "complete",
            "selected_restore_failure_count": 0,
        },
        "selected_sources": selected,
        "teacher_shard_ranges": list(contiguous_ranges(460)),
        "teacher_worker_count": 16,
    }

    @dataclass(frozen=True)
    class Pool:
        records: list[dict[str, str]]

    pool = Pool(
        records=[{"complete_identity_sha256": identity} for identity in identities]
    )
    marker_dir = tmp_path / "converter-pids"
    marker_dir.mkdir()
    teacher_path = tmp_path / "teacher.jsonl"
    teacher_path.write_text("teacher", encoding="utf-8")
    teacher = _empty_oracle_teacher_dataset()
    monkeypatch.setattr(
        transfer_command, "load_oracle_teacher_dataset_jsonl", lambda _: teacher
    )
    monkeypatch.setattr(
        transfer_command, "load_selected_source_pool", lambda _: (pool, selected)
    )
    monkeypatch.setattr(
        transfer_command, "complete_source_identity", lambda record: record
    )
    monkeypatch.setattr(
        transfer_command, "_validate_teacher_against_selected_manifest", lambda *_: None
    )
    monkeypatch.setattr(
        transfer_command, "_file_identity", lambda _: {"sha256": "b" * 64}
    )

    def direct_builder(*, selected_sources, **_kwargs):
        (marker_dir / selected_sources[0]["complete_identity_sha256"]).write_text(
            str(os.getpid()), encoding="utf-8"
        )
        dataset = make_trainer_dataset([(20, 1)] * len(selected_sources))
        records = [
            replace(
                record,
                source_metadata={
                    **record.source_metadata,
                    "t064_complete_identity_sha256": descriptor[
                        "complete_identity_sha256"
                    ],
                },
            )
            for record, descriptor in zip(
                dataset.records, selected_sources, strict=True
            )
        ]
        return replace(
            dataset,
            generation_metadata={
                "task_id": "T064",
                "workflow": "oracle_teacher_search_guidance_bridge",
                "direct_provenance_mode": "t064_manifest_and_merged_teacher",
                "teacher_artifact_identity": {"sha256": "b" * 64},
                "restore_counts": {"assisted_replay": len(records)},
            },
            records=records,
        )

    monkeypatch.setattr(
        guidance,
        "build_oracle_teacher_search_guidance_dataset_from_direct_provenance",
        direct_builder,
    )
    output_path = tmp_path / "trainer.jsonl"
    dataset, _report, mapping = transfer_command.run_t064_stage3_production(
        selected_manifest=manifest,
        teacher_path=teacher_path,
        output_path=output_path,
        shard_output_dir=tmp_path / "shards",
        log_dir=tmp_path / "logs",
        code_commit="a" * 40,
    )

    assert (
        len({int(path.read_text(encoding="utf-8")) for path in marker_dir.iterdir()})
        == 16
    )
    assert len(list((tmp_path / "shards").glob("shard-*.jsonl"))) == 16
    assert dataset.generation_metadata["restore_counts"] == {"assisted_replay": 460}
    assert mapping[identities[-1]] == 459
    with output_path.open(encoding="utf-8") as stream:
        persisted = load_trainer_input_dataset_jsonl(stream)
    assert transfer_command._trainer_identity_hashes(persisted) == identities


def test_actual_sixteen_worker_dispatch_writes_per_shard_logs(tmp_path: Path) -> None:
    barrier = threading.Barrier(16)
    thread_ids = set()
    lock = threading.Lock()

    def worker(index: int, record_range: str):
        del index, record_range
        barrier.wait(timeout=5)
        with lock:
            thread_ids.add(threading.get_ident())
        return "ok"

    results, records = transfer_command.dispatch_t064_shards(
        ranges=contiguous_ranges(460), log_dir=tmp_path / "logs", worker=worker
    )
    assert results == ["ok"] * 16
    assert len(thread_ids) == 16
    assert [record["return_code"] for record in records] == [0] * 16
    assert all(Path(record["log_path"]).is_file() for record in records)


def test_stage3_fork_dispatch_freezes_then_unfreezes_and_restores_gc_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = []
    monkeypatch.setattr(transfer_command.gc, "isenabled", lambda: True)
    monkeypatch.setattr(
        transfer_command.gc, "collect", lambda: events.append("collect")
    )
    monkeypatch.setattr(transfer_command.gc, "freeze", lambda: events.append("freeze"))
    monkeypatch.setattr(
        transfer_command.gc, "unfreeze", lambda: events.append("unfreeze")
    )
    monkeypatch.setattr(transfer_command.gc, "enable", lambda: events.append("enable"))
    monkeypatch.setattr(
        transfer_command.gc, "disable", lambda: events.append("disable")
    )
    monkeypatch.setattr(
        transfer_command,
        "dispatch_t064_shards",
        lambda **kwargs: events.append(("dispatch", kwargs["backend"])) or ([], []),
    )

    assert transfer_command._dispatch_t064_stage3_fork_shards(
        ranges=contiguous_ranges(16),
        log_dir=tmp_path / "logs",
        worker=lambda *_: None,
        backend="fork",
    ) == ([], [])
    assert events == ["collect", "freeze", ("dispatch", "fork"), "unfreeze", "enable"]


def test_stage3_fork_dispatch_unfreezes_after_base_exception_and_restores_disabled_gc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = []
    monkeypatch.setattr(transfer_command.gc, "isenabled", lambda: False)
    monkeypatch.setattr(
        transfer_command.gc, "collect", lambda: events.append("collect")
    )
    monkeypatch.setattr(transfer_command.gc, "freeze", lambda: events.append("freeze"))
    monkeypatch.setattr(
        transfer_command.gc, "unfreeze", lambda: events.append("unfreeze")
    )
    monkeypatch.setattr(transfer_command.gc, "enable", lambda: events.append("enable"))
    monkeypatch.setattr(
        transfer_command.gc, "disable", lambda: events.append("disable")
    )

    def interrupted(**_kwargs):
        events.append("dispatch")
        raise KeyboardInterrupt("intentional Stage3 fork interruption")

    monkeypatch.setattr(transfer_command, "dispatch_t064_shards", interrupted)
    with pytest.raises(KeyboardInterrupt, match="Stage3 fork interruption"):
        transfer_command._dispatch_t064_stage3_fork_shards(
            ranges=contiguous_ranges(16),
            log_dir=tmp_path / "logs",
            worker=lambda *_: None,
            backend="fork",
        )
    assert events == ["collect", "freeze", "dispatch", "unfreeze", "disable"]


@pytest.mark.skipif(
    os.name == "nt",
    reason="the Stage3 COW fork regression is intentionally WSL/Linux only",
)
def test_stage3_fork_freezes_preloaded_tracked_graph_before_child_gc(
    tmp_path: Path,
) -> None:
    """A child collection sees the parent graph frozen, not collectible/scannable."""

    preloaded_graph = [[index] for index in range(40_000)]

    def worker(index: int, _record_range: str) -> dict[str, int]:
        # This explicit collection models automatic child GC after allocation.
        # Frozen parent objects remain in the permanent generation.
        gc.collect()
        return {
            "index": index,
            "pid": os.getpid(),
            "frozen_count": gc.get_freeze_count(),
            "preloaded_length": len(preloaded_graph),
        }

    results, records = transfer_command._dispatch_t064_stage3_fork_shards(
        ranges=contiguous_ranges(16),
        log_dir=tmp_path / "logs",
        worker=worker,
        backend="fork",
    )

    assert len({result["pid"] for result in results}) == 16
    assert all(result["preloaded_length"] == len(preloaded_graph) for result in results)
    assert all(result["frozen_count"] >= len(preloaded_graph) for result in results)
    assert [record["return_code"] for record in records] == [0] * 16


def test_stage2_fork_returns_small_descriptors_and_reloads_persisted_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ranges = contiguous_ranges(16)
    manifest = {
        "selected_sources": [{} for _ in range(16)],
        "teacher_shard_ranges": list(ranges),
        "teacher_worker_count": 16,
    }
    descriptors: list[dict[str, object]] = []
    reloaded = []
    original_iterator = transfer_command._iter_t064_persisted_teacher_shards

    def fake_fork_dispatch(*, ranges, log_dir, worker, backend):
        assert backend == "fork"
        del log_dir
        results = [
            worker(index, record_range) for index, record_range in enumerate(ranges)
        ]
        assert all(isinstance(value, dict) for value in results)
        assert all(len(json.dumps(value)) < 512 for value in results)
        descriptors.extend(results)
        return results, [
            {"shard_index": index, "return_code": 0} for index in range(len(results))
        ]

    def capture_iterator(**kwargs):
        for value in original_iterator(**kwargs):
            reloaded.append(value)
            yield value

    def capture_merge(*, shards, **kwargs):
        del kwargs
        values = list(shards)
        assert values == reloaded
        assert all(isinstance(shard, OracleTeacherDataset) for shard in values)
        return values[0]

    monkeypatch.setattr(transfer_command, "dispatch_t064_shards", fake_fork_dispatch)
    monkeypatch.setattr(
        transfer_command, "_iter_t064_persisted_teacher_shards", capture_iterator
    )
    monkeypatch.setattr(
        transfer_command, "_merge_t064_teacher_shard_stream", capture_merge
    )

    merged, records = transfer_command.collect_t064_teacher_stage(
        selected_manifest=manifest,
        pool=object(),
        adapter_factory=lambda: object(),
        controller=object(),
        action_space=object(),
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
        dispatch_backend="fork",
        shard_runner=lambda **_kwargs: _empty_oracle_teacher_dataset(),
    )

    assert isinstance(merged, OracleTeacherDataset)
    assert len(descriptors) == len(reloaded) == 16
    assert records == [{"shard_index": index, "return_code": 0} for index in range(16)]
    assert all(
        (tmp_path / "shards" / f"shard-{index:02d}.jsonl").is_file()
        for index in range(16)
    )


def test_stage2_persisted_teacher_shards_reject_partial_or_corrupt_outputs(
    tmp_path: Path,
) -> None:
    ranges = contiguous_ranges(16)
    output_dir = tmp_path / "shards"
    output_dir.mkdir()
    descriptors = []
    for index, record_range in enumerate(ranges):
        output = output_dir / f"shard-{index:02d}.jsonl"
        transfer_command._write_oracle_teacher_shard_atomically(
            output, _empty_oracle_teacher_dataset()
        )
        descriptors.append(
            {
                "shard_index": index,
                "record_range": record_range,
                "path": str(output),
            }
        )

    loaded = list(
        transfer_command._iter_t064_persisted_teacher_shards(
            descriptors=descriptors, expected_ranges=ranges, shard_output_dir=output_dir
        )
    )
    assert len(loaded) == 16

    temporary = output_dir / "shard-03.jsonl.tmp"
    temporary.write_text("partial", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete temp"):
        list(
            transfer_command._iter_t064_persisted_teacher_shards(
                descriptors=descriptors,
                expected_ranges=ranges,
                shard_output_dir=output_dir,
            )
        )
    temporary.unlink()
    (output_dir / "shard-03.jsonl").write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        list(
            transfer_command._iter_t064_persisted_teacher_shards(
                descriptors=descriptors,
                expected_ranges=ranges,
                shard_output_dir=output_dir,
            )
        )


def test_stage2_teacher_shard_atomic_writer_never_publishes_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "shard-00.jsonl"

    def partial_then_fail(_dataset, stream) -> None:
        stream.write('{"type":"metadata"}\n')
        raise RuntimeError("intentional interrupted shard write")

    monkeypatch.setattr(
        transfer_command, "dump_oracle_teacher_dataset_jsonl", partial_then_fail
    )
    with pytest.raises(RuntimeError, match="interrupted shard write"):
        transfer_command._write_oracle_teacher_shard_atomically(
            output, _empty_oracle_teacher_dataset()
        )
    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_stage3_trainer_shard_atomic_writer_never_publishes_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "shard-00.jsonl"

    def partial_then_fail(_dataset, stream) -> None:
        stream.write('{"type":"metadata"}\n')
        raise RuntimeError("intentional interrupted trainer shard write")

    monkeypatch.setattr(
        transfer_command, "dump_trainer_input_dataset_jsonl", partial_then_fail
    )
    with pytest.raises(RuntimeError, match="interrupted trainer shard write"):
        transfer_command._write_trainer_input_shard_atomically(
            output, SimpleNamespace()
        )
    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_stage3_persisted_trainer_shards_reject_incomplete_or_corrupt_output(
    tmp_path: Path,
) -> None:
    ranges = contiguous_ranges(16)
    output_dir = tmp_path / "trainer-shards"
    output_dir.mkdir()
    descriptors = []
    for index, record_range in enumerate(ranges):
        output = output_dir / f"shard-{index:02d}.jsonl"
        output.write_text("not-json", encoding="utf-8")
        descriptors.append(
            {
                "shard_index": index,
                "record_range": record_range,
                "path": str(output),
            }
        )
    with pytest.raises(ValueError, match="invalid JSON"):
        list(
            transfer_command._iter_t064_persisted_trainer_shards(
                descriptors=descriptors,
                expected_ranges=ranges,
                shard_output_dir=output_dir,
            )
        )
    (output_dir / "shard-00.jsonl").unlink()
    temporary = output_dir / "shard-00.jsonl.tmp"
    temporary.write_text("partial", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete temp"):
        list(
            transfer_command._iter_t064_persisted_trainer_shards(
                descriptors=descriptors,
                expected_ranges=ranges,
                shard_output_dir=output_dir,
            )
        )


def test_stage3_trainer_merge_rejects_out_of_order_or_incomplete_rows() -> None:
    identities = [f"{index:064x}" for index in range(16)]
    manifest = {
        "selected_sources": [
            {"complete_identity_sha256": identity} for identity in identities
        ]
    }

    @dataclass(frozen=True)
    class Row:
        source_metadata: dict[str, str]
        example_index: int = 0
        rollout_index: int = 0
        segment_index: int = 0

    def shard(identity: str, *, problems=()):
        return SimpleNamespace(
            records=[
                Row(
                    source_metadata={
                        "t064_complete_identity_sha256": identity,
                        "source_run_id": f"run-{identity}",
                    }
                )
            ],
            problems=list(problems),
            generation_metadata={
                "task_id": "T064",
                "workflow": "oracle_teacher_search_guidance_bridge",
                "direct_provenance_mode": "t064_manifest_and_merged_teacher",
                "teacher_artifact_identity": {"sha256": "a" * 64},
                "restore_counts": {"assisted_replay": 1},
            },
            format_version=6,
            reward_allocation="terminal_step",
            snapshot_feature_size=1,
            action_feature_size=1,
            decision_record_schema_version=1,
            tactical_feature_schema_id="tactical",
            tactical_feature_schema_version=1,
            identity_vocabulary_version="identity",
            policy_target_schema_id="target",
            policy_target_schema_version=1,
            structured_battle_outcome_schema_id="resource",
            structured_battle_outcome_schema_version=1,
        )

    out_of_order = [shard(identity) for identity in identities]
    out_of_order[3] = shard(identities[4])
    with pytest.raises(ValueError, match="identity/order mismatch"):
        transfer_command._merge_t064_trainer_shard_stream(
            shards=out_of_order,
            selected_manifest=manifest,
            expected_ranges=contiguous_ranges(16),
        )
    incomplete = [shard(identity) for identity in identities]
    incomplete[5] = shard(identities[5], problems=("corrupt",))
    with pytest.raises(ValueError, match="incomplete"):
        transfer_command._merge_t064_trainer_shard_stream(
            shards=incomplete,
            selected_manifest=manifest,
            expected_ranges=contiguous_ranges(16),
        )


def test_stage3_trainer_merge_aggregates_metadata_and_restore_counts() -> None:
    identities = [f"{index:064x}" for index in range(16)]

    @dataclass(frozen=True)
    class Row:
        source_metadata: dict[str, str]
        example_index: int = 0
        rollout_index: int = 0
        segment_index: int = 0

    @dataclass(frozen=True)
    class Dataset:
        format_version: int
        reward_allocation: str
        source_rollout_count: int
        segment_count: int
        snapshot_feature_size: int
        action_feature_size: int
        decision_record_schema_version: int
        tactical_feature_schema_id: str
        tactical_feature_schema_version: int
        identity_vocabulary_version: str
        policy_target_schema_id: str
        policy_target_schema_version: int
        structured_battle_outcome_schema_id: str
        structured_battle_outcome_schema_version: int
        generation_metadata: dict[str, object]
        records: list[Row]
        problems: list[str]

    def shard(index: int, *, teacher_sha: str = "a" * 64) -> Dataset:
        identity = identities[index]
        return Dataset(
            format_version=6,
            reward_allocation="terminal_step",
            source_rollout_count=1,
            segment_count=1,
            snapshot_feature_size=1,
            action_feature_size=1,
            decision_record_schema_version=1,
            tactical_feature_schema_id="tactical",
            tactical_feature_schema_version=1,
            identity_vocabulary_version="identity",
            policy_target_schema_id="target",
            policy_target_schema_version=1,
            structured_battle_outcome_schema_id="resource",
            structured_battle_outcome_schema_version=1,
            generation_metadata={
                "task_id": "T064",
                "workflow": "oracle_teacher_search_guidance_bridge",
                "direct_provenance_mode": "t064_manifest_and_merged_teacher",
                "teacher_artifact_identity": {"sha256": teacher_sha},
                "restore_counts": {"assisted_replay": 1},
            },
            records=[
                Row(
                    source_metadata={
                        "t064_complete_identity_sha256": identity,
                        "source_run_id": f"run-{index // 2}",
                    }
                )
            ],
            problems=[],
        )

    manifest = {
        "selected_sources": [
            {"complete_identity_sha256": identity} for identity in identities
        ]
    }
    merged = transfer_command._merge_t064_trainer_shard_stream(
        shards=[shard(index) for index in range(16)],
        selected_manifest=manifest,
        expected_ranges=contiguous_ranges(16),
    )
    assert merged.source_rollout_count == 8
    assert merged.generation_metadata["restore_counts"] == {"assisted_replay": 16}
    assert merged.generation_metadata["t064_complete_identity_order"] == identities
    with pytest.raises(ValueError, match="direct provenance differs"):
        transfer_command._merge_t064_trainer_shard_stream(
            shards=[
                shard(index, teacher_sha="b" * 64 if index == 4 else "a" * 64)
                for index in range(16)
            ],
            selected_manifest=manifest,
            expected_ranges=contiguous_ranges(16),
        )


def test_stage2_reloaded_invalid_shard_blocks_merged_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ranges = contiguous_ranges(16)
    manifest = {
        "selected_sources": [{} for _ in range(16)],
        "teacher_shard_ranges": list(ranges),
        "teacher_worker_count": 16,
    }

    def fake_fork_dispatch(*, ranges, log_dir, worker, backend):
        assert backend == "fork"
        del log_dir
        return (
            [worker(index, record_range) for index, record_range in enumerate(ranges)],
            [{"shard_index": index, "return_code": 0} for index in range(16)],
        )

    monkeypatch.setattr(transfer_command, "dispatch_t064_shards", fake_fork_dispatch)
    merged_output = tmp_path / "merged.jsonl"
    with pytest.raises(ValueError, match="teacher shard 0 is incomplete"):
        transfer_command.collect_t064_teacher_stage(
            selected_manifest=manifest,
            pool=object(),
            adapter_factory=lambda: object(),
            controller=object(),
            action_space=object(),
            log_dir=tmp_path / "logs",
            shard_output_dir=tmp_path / "shards",
            merged_output_path=merged_output,
            dispatch_backend="fork",
            shard_runner=lambda **_kwargs: _empty_oracle_teacher_dataset(),
        )
    assert not merged_output.exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_stage2_production_fork_returns_descriptors_then_reloads_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ranges = contiguous_ranges(16)
    manifest = {
        "selected_sources": [{} for _ in range(16)],
        "teacher_shard_ranges": list(ranges),
        "teacher_worker_count": 16,
    }
    descriptors: list[object] = []
    original_iterator = transfer_command._iter_t064_persisted_teacher_shards

    def capture_iterator(**kwargs):
        descriptors.extend(kwargs["descriptors"])
        yield from original_iterator(**kwargs)

    def capture_merge(*, shards, **kwargs):
        del kwargs
        values = list(shards)
        assert len(values) == 16
        assert all(isinstance(shard, OracleTeacherDataset) for shard in values)
        return values[0]

    monkeypatch.setattr(
        transfer_command, "_iter_t064_persisted_teacher_shards", capture_iterator
    )
    monkeypatch.setattr(
        transfer_command, "_merge_t064_teacher_shard_stream", capture_merge
    )
    _, records = transfer_command.collect_t064_teacher_stage(
        selected_manifest=manifest,
        pool=object(),
        adapter_factory=lambda: object(),
        controller=object(),
        action_space=object(),
        log_dir=tmp_path / "logs",
        shard_output_dir=tmp_path / "shards",
        merged_output_path=tmp_path / "merged.jsonl",
        dispatch_backend="fork",
        shard_runner=lambda **_kwargs: _empty_oracle_teacher_dataset(),
    )

    assert len(descriptors) == 16
    assert all(
        isinstance(value, dict) and len(json.dumps(value)) < 512
        for value in descriptors
    )
    assert len({record["worker_pid"] for record in records}) == 16
    assert all(
        (tmp_path / "shards" / f"shard-{index:02d}.jsonl").is_file()
        for index in range(16)
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_stage2_fork_fast_workers_exit_while_parent_waits_for_shard_zero(
    tmp_path: Path,
) -> None:
    ranges = contiguous_ranges(16)
    marker_dir = tmp_path / "pids"
    marker_dir.mkdir()
    output_dir = tmp_path / "shards"
    observed = tmp_path / "fast-workers-exited"

    def worker(index: int, record_range: str) -> dict[str, object]:
        marker = marker_dir / f"{index:02d}"
        marker.write_text(str(os.getpid()), encoding="utf-8")
        if index == 0:
            deadline = time.monotonic() + 5
            while len(list(marker_dir.iterdir())) != 16 and time.monotonic() < deadline:
                time.sleep(0.01)
            assert len(list(marker_dir.iterdir())) == 16
            fast_pids = [
                int((marker_dir / f"{ordinal:02d}").read_text(encoding="utf-8"))
                for ordinal in range(1, 16)
            ]

            def exited_or_reaped(pid: int) -> bool:
                status = Path(f"/proc/{pid}/status")
                return not status.is_file() or "State:\tZ" in status.read_text(
                    encoding="utf-8"
                )

            while (
                not all(exited_or_reaped(pid) for pid in fast_pids)
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            # Before shard 00 can return, fast children are either reaped by a
            # later Process.start() cleanup or remain as zombies pending the
            # ordered join.  Both states have released their address spaces.
            assert all(exited_or_reaped(pid) for pid in fast_pids)
            observed.write_text("before-shard-00-return", encoding="utf-8")
        output = output_dir / f"shard-{index:02d}.jsonl"
        output.parent.mkdir(parents=True, exist_ok=True)
        transfer_command._write_oracle_teacher_shard_atomically(
            output, _empty_oracle_teacher_dataset()
        )
        return {
            "shard_index": index,
            "record_range": record_range,
            "path": str(output),
        }

    results, records = transfer_command.dispatch_t064_shards(
        ranges=ranges,
        log_dir=tmp_path / "logs",
        worker=worker,
        backend="fork",
    )

    assert observed.read_text(encoding="utf-8") == "before-shard-00-return"
    assert all(len(json.dumps(result)) < 512 for result in results)
    assert len({record["worker_pid"] for record in records}) == 16


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_fork_dispatch_uses_sixteen_distinct_processes_and_ordered_results(
    tmp_path: Path,
) -> None:
    parent_pid = os.getpid()

    def worker(index: int, record_range: str) -> dict[str, object]:
        return {"index": index, "range": record_range, "pid": os.getpid()}

    results, records = transfer_command.dispatch_t064_shards(
        ranges=contiguous_ranges(16),
        log_dir=tmp_path / "logs",
        worker=worker,
        backend="fork",
    )

    assert [result["index"] for result in results] == list(range(16))
    assert [record["range"] for record in records] == list(contiguous_ranges(16))
    assert len({record["worker_pid"] for record in records}) == 16
    assert parent_pid not in {record["worker_pid"] for record in records}
    assert all(Path(record["log_path"]).is_file() for record in records)


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_fork_dispatch_failure_keeps_all_logs_and_blocks_merge(tmp_path: Path) -> None:
    def worker(index: int, _record_range: str) -> str:
        if index == 7:
            raise RuntimeError("intentional fork shard failure")
        return "ok"

    with pytest.raises(RuntimeError, match="cannot contribute"):
        transfer_command.dispatch_t064_shards(
            ranges=contiguous_ranges(16),
            log_dir=tmp_path / "logs",
            worker=worker,
            backend="fork",
        )

    logs = sorted((tmp_path / "logs").glob("shard-*.log"))
    assert len(logs) == 16
    assert "return_code=1" in (tmp_path / "logs" / "shard-07.log").read_text(
        encoding="utf-8"
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_fork_dispatch_interrupt_cleans_children_and_preserves_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    retained_log = log_dir / "shard-00.log"
    retained_log.write_text("preexisting diagnostic log\n", encoding="utf-8")
    marker_dir = tmp_path / "pids"
    marker_dir.mkdir()

    def worker(index: int, _record_range: str) -> str:
        (marker_dir / f"{index:02d}").write_text(str(os.getpid()), encoding="utf-8")
        time.sleep(30)
        return "unreachable"

    def interrupt_parent_receive(
        _receiver: object,
    ) -> tuple[int, object, dict[str, object]]:
        deadline = time.monotonic() + 5
        while len(list(marker_dir.iterdir())) != 16 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(list(marker_dir.iterdir())) == 16
        raise KeyboardInterrupt("intentional parent receive interruption")

    monkeypatch.setattr(
        transfer_command,
        "_receive_t064_fork_shard_result",
        interrupt_parent_receive,
    )
    with pytest.raises(KeyboardInterrupt, match="parent receive interruption"):
        transfer_command.dispatch_t064_shards(
            ranges=contiguous_ranges(16),
            log_dir=log_dir,
            worker=worker,
            backend="fork",
        )

    child_pids = [
        int(path.read_text(encoding="utf-8")) for path in marker_dir.iterdir()
    ]
    assert all(not Path(f"/proc/{pid}").exists() for pid in child_pids)
    assert retained_log.read_text(encoding="utf-8") == "preexisting diagnostic log\n"


@pytest.mark.skipif(
    os.name == "nt",
    reason="the production fork backend is intentionally WSL/Linux only",
)
def test_fork_dispatch_start_failure_cleans_already_started_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_context = multiprocessing.get_context("fork")
    marker_dir = tmp_path / "pids"
    marker_dir.mkdir()
    created = []

    def worker(index: int, _record_range: str) -> str:
        (marker_dir / f"{index:02d}").write_text(str(os.getpid()), encoding="utf-8")
        time.sleep(30)
        return "unreachable"

    class StartFailureProcess:
        def __init__(self, process: object, ordinal: int) -> None:
            self.process = process
            self.ordinal = ordinal

        def start(self) -> None:
            if self.ordinal == 2:
                deadline = time.monotonic() + 5
                while (
                    len(list(marker_dir.iterdir())) != 2 and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
                assert len(list(marker_dir.iterdir())) == 2
                raise RuntimeError("intentional fork start failure")
            self.process.start()

        def __getattr__(self, name: str) -> object:
            return getattr(self.process, name)

    class StartFailureContext:
        def Pipe(self, *, duplex: bool) -> object:
            return real_context.Pipe(duplex=duplex)

        def Process(self, **kwargs: object) -> StartFailureProcess:
            wrapped = StartFailureProcess(real_context.Process(**kwargs), len(created))
            created.append(wrapped)
            return wrapped

    monkeypatch.setattr(
        transfer_command.multiprocessing,
        "get_context",
        lambda _method: StartFailureContext(),
    )
    with pytest.raises(RuntimeError, match="fork start failure"):
        transfer_command.dispatch_t064_shards(
            ranges=contiguous_ranges(16),
            log_dir=tmp_path / "logs",
            worker=worker,
            backend="fork",
        )

    child_pids = [
        int(path.read_text(encoding="utf-8")) for path in marker_dir.iterdir()
    ]
    assert len(child_pids) == 2
    assert all(not Path(f"/proc/{pid}").exists() for pid in child_pids)


def test_attempt_directories_are_isolated_and_never_promote_failed_shards(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifact-root"
    first = transfer_command.prepare_t064_attempt(
        root, stage="stage5_t044", code_commit="a" * 40
    )
    second = transfer_command.prepare_t064_attempt(
        root, stage="stage5_t044", code_commit="a" * 40
    )
    assert first != second
    assert first.name.endswith("-000") and second.name.endswith("-001")

    def fails(_index: int, _record_range: str):
        raise RuntimeError("intentional mock shard failure")

    with pytest.raises(RuntimeError, match="cannot contribute"):
        transfer_command.dispatch_t064_shards(
            ranges=contiguous_ranges(460), log_dir=first / "logs", worker=fails
        )
    assert not (root / "promoted-output").exists()
    assert len(list((first / "logs").glob("shard-*.log"))) == 16


def test_stage_summary_carries_retained_prior_attempts_without_log_index() -> None:
    stage = {
        "name": "stage1_source_audit",
        "status": "complete",
        "command": "python -m sts_combat_rl.commands.t064_curriculum",
        "code_commit": "a" * 40,
        "native_commit": "b" * 40,
        "inputs": {},
        "outputs": {},
        "workers": 16,
        "shards": 16,
        "ranges": list(contiguous_ranges(0)),
        "return_codes": [0],
        "wall_clock_seconds": 1.0,
        "failure_count": 0,
        "referenced_artifacts": [],
        "failed_attempts": [],
        "retained_log_paths": [],
    }
    summary = transfer_command.build_t064_stage_summary(
        reuse_inventory=[], stages=[stage]
    )
    assert summary["stages"][0]["failed_attempts"] == list(
        transfer_command.KNOWN_PRIOR_ATTEMPTS
    )
    assert validate_compact_document(summary) == summary
