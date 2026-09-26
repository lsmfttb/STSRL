from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import sts_combat_rl.sim.t101_particle_convergence as t101
import sts_combat_rl.sim.t103_particle_diagnostic as t103
from sts_combat_rl.sim.t103_particle_diagnostic import (
    T103_CLASSES,
    T103DiagnosticError,
    T103NativeRecordRunner,
    aggregate_t103_diagnostics,
    classify_t103_observation,
    replay_t103_candidates,
    t103_record_shard_ranges,
    write_t103_retained_artifacts,
)


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ({"restore_binding_failed": True}, "RESTORE_OR_SOURCE_BINDING_FAILURE"),
        (
            {
                "public_projection_parity": False,
                "ordered_legal_action_parity": False,
                "mapping_complete": False,
            },
            "PUBLIC_PROJECTION_PARITY_FAILURE",
        ),
        (
            {
                "public_projection_parity": True,
                "ordered_legal_action_parity": False,
                "mapping_complete": False,
            },
            "ORDERED_LEGAL_ACTION_PARITY_FAILURE",
        ),
        (
            {
                "bridge_precondition_or_sampler_failed": True,
                "mapping_complete": False,
            },
            "BRIDGE_PRECONDITION_OR_SAMPLER_FAILURE",
        ),
        (
            {"mapping_complete": False, "mapping_ambiguous": False},
            "ROOT_OCCURRENCE_MAPPING_INCOMPLETE",
        ),
        (
            {"mapping_complete": False, "mapping_ambiguous": True},
            "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS",
        ),
        (
            {"mapping_error_code": "incomplete_or_ambiguous"},
            "ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS",
        ),
        (
            {
                "mapping_complete": True,
                "mapping_ambiguous": False,
                "search_execution_reached": True,
                "search_execution_failed": True,
            },
            "SEARCH_EXECUTION_FAILURE",
        ),
        (
            {
                "mapping_complete": True,
                "mapping_ambiguous": False,
                "search_execution_reached": True,
                "required_root_values_valid": False,
            },
            "NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES",
        ),
        ({"complete_admission": True}, "ADMITTED"),
        ({}, "OPAQUE_BRIDGE_FAILURE"),
    ],
)
def test_classifier_uses_structured_first_boundary(evidence, expected) -> None:
    observed_class, _subreason = classify_t103_observation(evidence)
    assert observed_class == expected


@pytest.mark.parametrize(
    "evidence",
    [
        {"exception_message": "root occurrence mapping is incomplete"},
        {"exception_message": "ambiguous action mapping"},
        {"mapping_error_code": "probably_incomplete"},
        {"mapping_complete": "false", "mapping_ambiguous": "true"},
        {"search_execution_failed": True, "search_execution_reached": True},
    ],
)
def test_classifier_keeps_unproven_causes_opaque(evidence) -> None:
    observed_class, _subreason = classify_t103_observation(evidence)
    assert observed_class == "OPAQUE_BRIDGE_FAILURE"


def test_classification_is_deterministic_for_repeated_evidence() -> None:
    evidence = {
        "mapping_complete": False,
        "mapping_ambiguous": True,
        "exception_message": "must not affect classification",
    }
    first = classify_t103_observation(evidence)
    second = classify_t103_observation(evidence)
    assert first == second == ("ROOT_OCCURRENCE_MAPPING_AMBIGUOUS", "mapping_ambiguous")


def _runner(monkeypatch, bridge):
    identity = "fixture-selection-identity"
    expected_context = {
        "candidate_actions": {"availability": "available", "items": []},
        "public_projection": "same",
        "missing_fields": [],
        "history": [],
    }
    calls = []
    report = {
        "schema_id": "fixture-t099-report-v1",
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
        "sampler_seed_input": t101.derive_t101_sampler_seed(identity, 0),
        "particles": [],
    }

    def sample(_snapshot, **kwargs):
        calls.append(kwargs)
        return bridge(report)

    adapter = SimpleNamespace(
        legal_actions=lambda _snapshot: [],
        sample_hidden_future_particles_search=sample,
    )
    monkeypatch.setattr(
        t103,
        "restore_t085_canonical_record",
        lambda *_args: (SimpleNamespace(raw={}), "fixture_restore"),
    )
    monkeypatch.setattr(t103, "read_native_public_projection", lambda *_args: None)
    monkeypatch.setattr(
        t103,
        "build_public_run_context",
        lambda *_args, include_candidates=True, **_kwargs: deepcopy(expected_context),
    )
    runner = T103NativeRecordRunner(
        adapter_factory=lambda: adapter,
        selected_records={identity: object()},
        canonical_records_by_stratum={
            "A": {identity: SimpleNamespace(public_run_context=expected_context)}
        },
        native_identity={
            "repository": "fixture/native",
            "ref": "fixture",
            "commit": "a" * 40,
        },
        historical_bindings={"input_sha256": "b" * 64},
    )
    return identity, report, calls, runner


def test_diagnostic_invokes_frozen_success_call_once_and_does_not_retain_report(
    monkeypatch,
) -> None:
    identity, raw_report, calls, runner = _runner(monkeypatch, lambda report: report)
    expected_seed = int.from_bytes(
        hashlib.sha256(b"T101-v1" + identity.encode("utf-8") + b"0").digest()[:8],
        "big",
    )
    assert raw_report["sampler_seed_input"] == expected_seed
    validator_inputs = []
    monkeypatch.setattr(
        t101,
        "validate_t101_bridge_report",
        lambda report, *, particle_count: (
            validator_inputs.append(report) or {**report, "accepted": True}
        ),
    )
    monkeypatch.setattr(
        t103,
        "validate_t101_bridge_report",
        lambda report, *, particle_count: (
            validator_inputs.append(report) or {**report, "accepted": True}
        ),
    )
    adapter = runner._adapter_factory()
    baseline = t101.call_t101_bridge(
        adapter,
        object(),
        sampler_seed=raw_report["sampler_seed_input"],
        particle_count=2,
    )
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )

    assert row["diagnostic_class"] == "ADMITTED"
    assert row["sampler_seed"] == expected_seed
    assert row["valid_finite_root_report_status"] == "reached"
    expected_call = {
        "sampler_seed": raw_report["sampler_seed_input"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    assert calls == [
        expected_call,
        expected_call,
    ]
    assert validator_inputs == [raw_report, raw_report]
    assert baseline["accepted"] is True
    assert validator_inputs[0] == validator_inputs[1]
    assert row["search_simulations"] == 400
    assert row["include_potions"] is False
    assert "bridge_report" not in row
    assert "particles" not in row
    assert "hidden_future_fingerprint" not in row


def test_untyped_native_exception_stays_opaque_without_retry(monkeypatch) -> None:
    def fail(_report):
        raise RuntimeError("root occurrence mapping incomplete")

    identity, _report, calls, runner = _runner(monkeypatch, fail)
    with pytest.raises(RuntimeError):
        t101.call_t101_bridge(
            runner._adapter_factory(),
            object(),
            sampler_seed=t101.derive_t101_sampler_seed(identity, 0),
            particle_count=2,
        )
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )
    assert row["diagnostic_class"] == "OPAQUE_BRIDGE_FAILURE"
    assert row["exception_type"] == "RuntimeError"
    assert len(row["exception_signature"]) == 64
    assert row["bridge_invocation_status"] == "failed"
    assert row["occurrence_mapping_status"] == "unknown"
    assert row["search_execution_status"] == "unknown"
    assert row["valid_finite_root_report_status"] == "unknown"
    assert len(calls) == 2


def test_anchor_projection_mismatch_updates_candidate_status(monkeypatch) -> None:
    identity, report, _calls, runner = _runner(monkeypatch, lambda value: value)
    report["anchor_public_information_projection"] = {"anchor": "accepted"}
    monkeypatch.setattr(
        t103,
        "read_native_public_projection",
        lambda *_args: SimpleNamespace(canonical_payload='{"anchor":"current"}'),
    )
    monkeypatch.setattr(
        t103,
        "validate_t101_bridge_report",
        lambda value, *, particle_count: {**value, "accepted": True},
    )

    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )

    assert row["diagnostic_class"] == "PUBLIC_PROJECTION_PARITY_FAILURE"
    assert row["public_projection_parity_status"] == "failed"
    assert row["bridge_invocation_status"] == "returned_report"


@pytest.mark.parametrize(
    "root_rows_state",
    [
        "missing",
        "non_list",
        "empty",
        "malformed",
        "missing_required_value",
        "nonfinite",
    ],
)
def test_search_without_valid_required_root_rows_is_nonfinite_class(
    root_rows_state, monkeypatch
) -> None:
    particle = {
        "root_action_mapping_complete": True,
        "root_action_mapping_ambiguous": False,
        "root_evaluation": {},
    }
    if root_rows_state == "non_list":
        particle["root_rows"] = {"row": "not a list"}
    elif root_rows_state == "empty":
        particle["root_rows"] = []
    elif root_rows_state == "malformed":
        particle["root_rows"] = ["not a row"]
    elif root_rows_state == "missing_required_value":
        particle["root_rows"] = [{"visits": 1, "mean_value": 1.0}]
    elif root_rows_state == "nonfinite":
        particle["root_rows"] = [
            {"visits": 1, "evaluation_sum": float("nan"), "mean_value": 1.0}
        ]
    report = {"particles": [particle]}

    evidence, _config = t103._bridge_observations(report)
    assert evidence["search_execution_reached"] is True
    assert evidence["required_root_values_valid"] is False
    assert classify_t103_observation(evidence)[0] == (
        "NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES"
    )

    identity, raw_report, _calls, runner = _runner(monkeypatch, lambda value: value)
    raw_report["particles"] = [particle]
    monkeypatch.setattr(
        t103,
        "validate_t101_bridge_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("required root rows are invalid")
        ),
    )
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )
    assert row["diagnostic_class"] == "NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES"
    assert row["valid_finite_root_report_status"] == "failed"


def test_invalid_root_validator_unrelated_to_required_values_stays_opaque(
    monkeypatch,
) -> None:
    identity, report, _calls, runner = _runner(monkeypatch, lambda value: value)
    report["particles"] = [
        {
            "root_action_mapping_complete": True,
            "root_action_mapping_ambiguous": False,
            "root_evaluation": {},
            "root_rows": [{"visits": 1, "evaluation_sum": 1.0, "mean_value": 1.0}],
        }
    ]

    def invalid_for_another_reason(*_args, **_kwargs):
        raise ValueError("unrelated frozen report validation failure")

    monkeypatch.setattr(t103, "validate_t101_bridge_report", invalid_for_another_reason)
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )

    assert row["diagnostic_class"] == "OPAQUE_BRIDGE_FAILURE"
    assert row["search_execution_status"] == "reached"
    assert row["occurrence_mapping_status"] == "complete"
    assert row["valid_finite_root_report_status"] == "unknown"


def test_precondition_mismatch_preserves_directly_reached_report_stages(
    monkeypatch,
) -> None:
    identity, report, _calls, runner = _runner(monkeypatch, lambda value: value)
    report["search_simulations"] = 399
    report["particles"] = [
        {
            "root_action_mapping_complete": True,
            "root_action_mapping_ambiguous": False,
            "root_evaluation": {},
            "root_rows": [{"visits": 1, "evaluation_sum": 1.0, "mean_value": 1.0}],
        }
    ]
    monkeypatch.setattr(
        t103,
        "validate_t101_bridge_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("frozen config validation failed")
        ),
    )

    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )

    assert row["diagnostic_class"] == "BRIDGE_PRECONDITION_OR_SAMPLER_FAILURE"
    assert row["occurrence_mapping_status"] == "complete"
    assert row["search_execution_status"] == "reached"
    assert row["valid_finite_root_report_status"] == "unknown"


def test_malformed_opaque_bridge_report_keeps_unobserved_stages_unknown(
    monkeypatch,
) -> None:
    identity, _report, _calls, runner = _runner(monkeypatch, lambda _value: None)
    monkeypatch.setattr(
        t103,
        "validate_t101_bridge_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("malformed bridge report")
        ),
    )
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        source_ordinal=0,
        selection_digest=hashlib.sha256(identity.encode()).hexdigest(),
    )

    assert row["diagnostic_class"] == "OPAQUE_BRIDGE_FAILURE"
    assert row["bridge_invocation_status"] == "returned_report"
    assert row["occurrence_mapping_status"] == "unknown"
    assert row["search_execution_status"] == "unknown"
    assert row["valid_finite_root_report_status"] == "unknown"


def test_bridge_report_flags_localize_only_structured_failures() -> None:
    mapping_report = {
        "anchor_public_information_projection": {"information_fidelity": "supported"},
        "anchor_ordered_public_legal_actions": [],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
        "sampler_seed_input": 1,
        "particles": [
            {
                "public_projection_equal": True,
                "ordered_public_legal_actions_equal": True,
                "public_information_projection": {"information_fidelity": "supported"},
                "ordered_public_legal_actions": [],
                "root_action_mapping_complete": False,
                "root_action_mapping_ambiguous": True,
            }
        ],
    }
    evidence, config = t103._bridge_observations(mapping_report)
    observed_class, _ = classify_t103_observation(evidence)
    assert observed_class == "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS"
    assert config == {
        "particle_start": "0",
        "particle_count": "2",
        "search_simulations": "400",
        "include_potions": "False",
        "sampler_seed_input": "1",
    }


def _aggregate_rows(admitted_at: int | None = None):
    rows = []
    strata = ("A",) * 93 + ("B",) * 192 + ("C",) * 128
    for ordinal, stratum in enumerate(strata):
        diagnostic_class = (
            "ADMITTED"
            if ordinal == admitted_at
            else T103_CLASSES[ordinal % (len(T103_CLASSES) - 1)]
        )
        rows.append(
            {
                "selection_identity": f"selection-{ordinal}",
                "stratum": stratum,
                "source_ordinal": ordinal,
                "selection_digest": hashlib.sha256(
                    f"selection-{ordinal}".encode()
                ).hexdigest(),
                "diagnostic_class": diagnostic_class,
                "subreason_code": "fixture_reason",
                "search_execution_status": (
                    "reached" if diagnostic_class == "ADMITTED" else "not_reached"
                ),
                "valid_finite_root_report_status": (
                    "reached" if diagnostic_class == "ADMITTED" else "not_reached"
                ),
                "admitted": diagnostic_class == "ADMITTED",
            }
        )
    return rows


def test_aggregate_counts_and_baseline_gate() -> None:
    rows = _aggregate_rows()
    report = aggregate_t103_diagnostics(
        rows,
        source_counts={"A": 93, "B": 192, "C": 128},
        t101_input_bindings={"input_sha256": "a" * 64},
        native_identity={"commit": "b" * 40},
    )
    assert report["terminal_classification"] == (
        "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED"
    )
    distribution = report["diagnostic_distribution"]
    assert distribution["all_candidates"] == {
        "count": 413,
        "total": 413,
        "fraction": "413/413",
    }
    assert distribution["by_stratum"]["A"]["total"] == 93
    assert distribution["by_stratum"]["B"]["total"] == 192
    assert distribution["by_stratum"]["C"]["total"] == 128
    assert sum(item["count"] for item in distribution["classes"].values()) == 413

    changed = aggregate_t103_diagnostics(
        _aggregate_rows(admitted_at=0),
        source_counts={"A": 93, "B": 192, "C": 128},
        t101_input_bindings={
            "input_sha256": "a" * 64,
            "retained_t101_execution_identity": {
                "implementation_head": "d" * 40,
                "native_identity": {
                    "repository": "fixture/native",
                    "ref": "fixture/ref",
                    "commit": "f" * 40,
                },
                "readiness_authorization_sha256": "e" * 64,
                "input_admission_artifact_sha256": "1" * 64,
                "cohort_admission_artifact_sha256": "2" * 64,
            },
        },
        native_identity={
            "repository": "fixture/native",
            "ref": "fixture/ref",
            "commit": "b" * 40,
        },
    )
    assert changed["terminal_classification"] == "T101_SUPPORT_RESULT_NOT_REPRODUCED"
    assert changed["diagnostic_distribution"] is None
    baseline = changed["baseline_reproduction"]
    assert baseline["newly_admitted_candidates"] == [
        {
            "selection_identity": "selection-0",
            "stratum": "A",
            "source_ordinal": 0,
            "selection_digest": hashlib.sha256(b"selection-0").hexdigest(),
        }
    ]
    assert baseline["current_native_identity"] == {
        "repository": "fixture/native",
        "ref": "fixture/ref",
        "commit": "b" * 40,
    }
    assert baseline["retained_t101_execution_identity"] == {
        "implementation_head": "d" * 40,
        "native_identity": {
            "repository": "fixture/native",
            "ref": "fixture/ref",
            "commit": "f" * 40,
        },
        "readiness_authorization_sha256": "e" * 64,
        "input_admission_artifact_sha256": "1" * 64,
        "cohort_admission_artifact_sha256": "2" * 64,
    }


def test_replay_preserves_attempt_order_and_balanced_worker_ranges() -> None:
    attempts = []
    records = {}
    for index in range(413):
        stratum = "A" if index < 93 else "B" if index < 285 else "C"
        identity = f"source-{index}"
        digest = hashlib.sha256(identity.encode()).hexdigest()
        ordinal = sum(row["stratum"] == stratum for row in attempts)
        attempts.append(
            {
                "selection_identity": identity,
                "stratum": stratum,
                "source_ordinal": ordinal,
                "selection_digest": digest,
            }
        )
        records[identity] = {"selection_identity": identity, "cohort": stratum}

    class RecordingRunner:
        def diagnose(self, record, *, source_ordinal, selection_digest):
            return {
                "selection_identity": record["selection_identity"],
                "source_ordinal": source_ordinal,
                "selection_digest": selection_digest,
            }

    replayed = replay_t103_candidates(
        runner=RecordingRunner(),
        source_records_by_identity=records,
        attempts=attempts,
        worker_count=4,
    )
    assert [row["selection_identity"] for row in replayed] == [
        row["selection_identity"] for row in attempts
    ]
    ranges = t103_record_shard_ranges(413, 16)
    assert len(ranges) == 16
    assert sum(item["record_count"] for item in ranges) == 413
    assert ranges[0]["start_ordinal_inclusive"] == 0
    assert ranges[-1]["end_ordinal_exclusive"] == 413


def test_retention_manifest_hash_binds_candidate_rows_and_report(
    tmp_path: Path,
) -> None:
    rows = _aggregate_rows()
    report = {
        "schema_id": "t103-particle-support-report-v1",
        "terminal_classification": "fixture",
    }
    artifacts = write_t103_retained_artifacts(
        artifact_root=tmp_path,
        rows=rows,
        report=report,
        producer_provenance={"implementation_head": "a" * 40},
        regeneration_command="python -m test",
        retention_reason="fixture retention",
        deletion_condition="after test",
    )
    for key in ("candidate_diagnostics", "aggregate_report", "retention_manifest"):
        artifact = artifacts[key]
        path = Path(artifact["path"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        assert path.stat().st_size == artifact["size_bytes"]

    with pytest.raises(T103DiagnosticError, match="overwrite"):
        write_t103_retained_artifacts(
            artifact_root=tmp_path,
            rows=rows,
            report=report,
            producer_provenance={"implementation_head": "a" * 40},
            regeneration_command="python -m test",
            retention_reason="fixture retention",
            deletion_condition="after test",
        )
