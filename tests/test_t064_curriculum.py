from __future__ import annotations

import hashlib
from io import StringIO
import json
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import threading

import pytest

from sts_combat_rl.commands import t064_curriculum as curriculum_command
from sts_combat_rl.commands import t064_curriculum_transfer as transfer_command
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
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
    environment["PYTHONPATH"] = str(repository / "src")
    completed = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "t064_curriculum_transfer.py"),
            "--dry-run-manifest",
            str(tmp_path / "t064-curriculum-manifest.json"),
            "--code-commit",
            "d" * 40,
            "--stage",
            "stage2_teacher",
            "--mock-execute",
            "--attempt-root",
            str(tmp_path / "mock-attempt"),
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert len(payload["shards"]) == 16
    child = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "t064_curriculum_transfer.py"),
            "--dry-run-manifest",
            str(tmp_path / "t064-curriculum-manifest.json"),
            "--code-commit",
            "d" * 40,
            "--stage",
            "stage2_teacher",
            "--execute-command",
            f'"{sys.executable}" -c "import sys; raise SystemExit(0)"',
            "--attempt-root",
            str(tmp_path / "command-attempt"),
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    attempt = Path(json.loads(child.stdout)["attempt"])
    assert len(list(attempt.glob("shard-*"))) == 16
    assert len(list((attempt / "logs").glob("shard-*.log"))) == 16


def test_empty_selected_source_pool_is_valid_for_complete_source_inadequacy() -> None:
    pool, selected = curriculum_command.load_selected_source_pool(
        {"selected_sources": []}
    )
    assert selected == []
    assert pool.records == []


def test_stage2_to_7_contract_helpers_refuse_stale_resume_and_preserve_identity_order() -> (
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
    with pytest.raises(ValueError, match="stale"):
        transfer_command.validate_resume_manifest(manifest, code_commit="b" * 40)
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
        "action_space": {"include_potions": False},
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
        == "rerun_once_four_arm"
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
    assert transfer_command.validate_t070_baseline_reuse(
        baseline, cohort_identity="t052"
    )
    baseline["tree_geometry_enabled"] = True
    assert not transfer_command.validate_t070_baseline_reuse(
        baseline, cohort_identity="t052"
    )


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
        "schema_id": "t070-frozen-manifest-v1",
        "code_commit": "b" * 40,
        "primary_shard_ranges": list(transfer_command.T070_T052_RANGES),
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
        manifest, code_commit="a" * 40
    )
    assert plan[0]["workers"] == plan[0]["shards"] == 16
    assert plan[0]["ranges"] == list(contiguous_ranges(460))
    assert len([row for row in plan if row["stage"] == "stage5_t044"]) == 8
    assert len([row for row in plan if row["stage"] == "stage6_t070"]) == 4
    assert plan[-1]["stage"] == "stage7_aggregate"


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
