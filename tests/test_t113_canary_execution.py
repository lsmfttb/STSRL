from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import test_t113_configured_particle_convergence as fixtures

from sts_combat_rl.commands import t113_canary_execution as command
from sts_combat_rl.commands.t113_canary_execution import T113CanaryWorkflowError
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t113_canary_execution import (
    T113_CANARY_AUTHORIZATION_SCHEMA,
    T113_CANARY_RESOURCE_POLICY_SCHEMA,
    T113CanaryAuthorizationError,
    build_t113_canary_readiness,
    canonical_sha256,
    validate_t113_canary_authorization,
)
from sts_combat_rl.sim.t113_configured_particle_convergence import (
    T113_APPROVED_SPEC_COMMIT,
    T113_EXECUTION_ENVELOPE_SCHEMA,
    T113_NATIVE_IDENTITY,
    T113_SEARCH_CONFIGURATION,
    T113_STAGE_EXECUTION_ENVELOPE_SCHEMA,
    build_t113_cost_report,
)

_HEAD = "a" * 40
_MANIFEST_SHA = "b" * 64


def _qualification(cohort: dict[str, object], binary_path) -> dict[str, object]:
    binary_sha = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    return {
        "schema_id": "t113-input-qualification-v1",
        "task_id": "T113",
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "implementation_head": _HEAD,
        "eligible": True,
        "candidate_execution_started": False,
        "execution_authorized": False,
        "canary_authorized": False,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "native_source_manifest": {"sha256": _MANIFEST_SHA},
        "native_binary_sha256": binary_sha,
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "fixed_cohort": cohort,
        "t112_artifact_references": {
            "native_binary": {
                "path": str(binary_path.resolve()),
                "schema_id": None,
                "sha256": binary_sha,
                "size_bytes": binary_path.stat().st_size,
            }
        },
    }


def _authorization(readiness: dict[str, object]) -> dict[str, object]:
    binding_keys = (
        "implementation_head",
        "approved_spec_commit",
        "qualification_artifact_sha256",
        "fixed_cohort_artifact_sha256",
        "fixed_cohort_semantic_sha256",
        "native_identity",
        "native_manifest_sha256",
        "native_binary_sha256",
        "frozen_search_configuration",
        "canary_selection_sha256",
    )
    guard = {
        "schema_id": T113_CANARY_RESOURCE_POLICY_SCHEMA,
        "worker_count": 1,
        "max_effective_concurrency": 1,
        "memory_request_mib": 64,
        "runtime_rss_limit_mib": 32,
        "measured_available_memory_mib": 2048,
        "measured_peak_rss_mib": 10,
        "measurement_source": "maintainer measured host resource probe",
        "measured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    auth = {
        "schema_id": T113_CANARY_AUTHORIZATION_SCHEMA,
        "task_id": "T113",
        "authorization_kind": "bounded_canary",
        "authorized": True,
        "authorization_id": "maintainer-canary-approval-fixture",
        **{key: readiness[key] for key in binding_keys},
        "resource_guard_policy": guard,
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "BOUNDED_CANARY_AUTHORIZED",
            "exact_head": readiness["implementation_head"],
            "resource_guard_policy_sha256": canonical_sha256(guard),
        },
    }
    return auth


def _write_json(path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _resources():
    return {
        "available_memory_mib": 1024,
        "process_rss_mib": 4,
        "process_peak_rss_mib": 8,
    }


class _FakeAdapter:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = calls

    def sample_hidden_future_particles_search(
        self,
        restored: dict[str, object],
        *,
        sampler_seed: int,
        particle_start: int,
        particle_count: int,
        search_simulations: int,
        include_potions: bool,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "selection_identity": restored["selection_identity"],
                "sampler_seed": sampler_seed,
                "particle_start": particle_start,
                "particle_count": particle_count,
                "search_simulations": search_simulations,
                "include_potions": include_potions,
            }
        )
        full = fixtures._batch_report(seed=sampler_seed)
        direct = deepcopy(full)
        direct["particle_count"] = particle_count
        direct["particles"] = deepcopy(full["particles"][:particle_count])
        return direct


def _run_fixture(tmp_path, monkeypatch):
    cohort = fixtures._fixed_cohort(fixtures._t112_cohort())
    binary_path = tmp_path / "authorized-extension.fixture"
    binary_path.write_bytes(b"not loaded by the mocked test runtime")
    qualification = _qualification(cohort, binary_path)
    qualification_path = tmp_path / "qualification.json"
    cohort_path = tmp_path / "cohort.json"
    qualification_ref_sha = hashlib.sha256(
        json.dumps(
            qualification,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    cohort_ref_sha = hashlib.sha256(
        json.dumps(
            cohort,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    _write_json(qualification_path, qualification)
    _write_json(cohort_path, cohort)
    readiness = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=_HEAD,
        qualification_artifact_sha256=qualification_ref_sha,
        fixed_cohort_artifact_sha256=cohort_ref_sha,
        native_manifest_sha256=_MANIFEST_SHA,
        native_binary_sha256=qualification["native_binary_sha256"],
    )
    readiness_path = tmp_path / "readiness.json"
    _write_json(readiness_path, readiness)
    auth_path = tmp_path / "authorization.json"
    _write_json(auth_path, _authorization(readiness))
    retention_path = tmp_path / "unused-t112-retention.json"
    native_manifest_path = tmp_path / "unused-native-manifest.json"
    retention_path.write_text("{}", encoding="utf-8")
    native_manifest_path.write_text("{}", encoding="utf-8")
    actual_sha256_file = command._sha256_file
    monkeypatch.setattr(
        command,
        "_sha256_file",
        lambda path: (
            _MANIFEST_SHA
            if Path(path).resolve() == native_manifest_path.resolve()
            else actual_sha256_file(path)
        ),
    )
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    monkeypatch.setattr(
        command,
        "_current_worktree",
        lambda _root: {"head": _HEAD, "branch": command.T113_BRANCH, "clean": True},
    )
    monkeypatch.setattr(command, "qualify_t113_inputs", lambda **_kwargs: qualification)
    monkeypatch.setattr(
        command, "_current_t113_native_identity", lambda: dict(T113_NATIVE_IDENTITY)
    )
    return {
        "cohort": cohort,
        "qualification": qualification,
        "qualification_path": qualification_path,
        "cohort_path": cohort_path,
        "readiness": readiness,
        "readiness_path": readiness_path,
        "authorization_path": auth_path,
        "retention_path": retention_path,
        "native_manifest_path": native_manifest_path,
        "repo_root": repo_root,
        "binary_path": binary_path,
    }


def test_t113_t085_source_manifest_reference_accepts_byte_count(tmp_path):
    manifest_path = tmp_path / "t085-source-generation-manifest.json"
    manifest_path.write_bytes(b"T085 source manifest reference fixture\n")
    reference = {
        "path": str(manifest_path.resolve()),
        "schema_id": command.T085_SOURCE_MANIFEST_SCHEMA_ID,
        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "byte_count": manifest_path.stat().st_size,
    }

    checked, resolved = command._verify_t085_source_manifest_reference(reference)

    assert resolved == manifest_path.resolve()
    assert checked == reference
    # Generic T113 artifact references remain size_bytes-based.
    with pytest.raises(command.T113WorkflowError):
        command._verify_reference(
            reference, expected_schema=command.T085_SOURCE_MANIFEST_SCHEMA_ID
        )


@pytest.mark.parametrize("field", ["byte_count", "sha256"])
def test_t113_t085_source_manifest_reference_rejects_changed_integrity(tmp_path, field):
    manifest_path = tmp_path / f"t085-source-generation-manifest-{field}.json"
    manifest_path.write_bytes(b"T085 source manifest reference fixture\n")
    reference = {
        "path": str(manifest_path.resolve()),
        "schema_id": command.T085_SOURCE_MANIFEST_SCHEMA_ID,
        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "byte_count": manifest_path.stat().st_size,
    }
    if field == "byte_count":
        reference[field] += 1
    else:
        reference[field] = "0" * 64

    with pytest.raises(T113CanaryWorkflowError):
        command._verify_t085_source_manifest_reference(reference)


def test_t113_readiness_is_non_authorizing_and_binds_exact_canary_rows(tmp_path):
    cohort = fixtures._fixed_cohort(fixtures._t112_cohort())
    binary_path = tmp_path / "native.bin"
    binary_path.write_bytes(b"binary")
    qualification = _qualification(cohort, binary_path)
    readiness = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=_HEAD,
        qualification_artifact_sha256="c" * 64,
        fixed_cohort_artifact_sha256="d" * 64,
        native_manifest_sha256=_MANIFEST_SHA,
        native_binary_sha256=qualification["native_binary_sha256"],
    )
    assert readiness["preparation_only"] is True
    assert readiness["canary_authorized"] is False
    assert readiness["canary_started"] is False
    assert readiness["authorization_template"]["authorized"] is None
    rows = readiness["canary_selection"]
    assert [(row["stratum"], row["replicate_index"]) for row in rows] == [
        (stratum, 0) for stratum in T101_SOURCE_COUNTS
    ]
    for row in rows:
        assert row["sampler_seed_input"] == derive_t101_sampler_seed(
            row["selection_identity"], 0
        )


def test_t113_authorization_rejects_head_drift_and_stale_resource_measurement(
    tmp_path,
):
    cohort = fixtures._fixed_cohort(fixtures._t112_cohort())
    binary_path = tmp_path / "native.bin"
    binary_path.write_bytes(b"binary")
    qualification = _qualification(cohort, binary_path)
    readiness = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=_HEAD,
        qualification_artifact_sha256="c" * 64,
        fixed_cohort_artifact_sha256="d" * 64,
        native_manifest_sha256=_MANIFEST_SHA,
        native_binary_sha256=qualification["native_binary_sha256"],
    )
    authorization = _authorization(readiness)
    authorization["implementation_head"] = "e" * 40
    with pytest.raises(T113CanaryAuthorizationError, match="exact-head"):
        validate_t113_canary_authorization(
            authorization,
            readiness=readiness,
            qualification=qualification,
            fixed_cohort=cohort,
            implementation_head=_HEAD,
            qualification_artifact_sha256="c" * 64,
            fixed_cohort_artifact_sha256="d" * 64,
            native_manifest_sha256=_MANIFEST_SHA,
            native_binary_sha256=qualification["native_binary_sha256"],
        )

    authorization = _authorization(readiness)
    authorization["resource_guard_policy"]["measured_available_memory_mib"] = 32
    authorization["maintainer_attestation"]["resource_guard_policy_sha256"] = (
        canonical_sha256(authorization["resource_guard_policy"])
    )
    with pytest.raises(T113CanaryAuthorizationError, match="resource guard"):
        validate_t113_canary_authorization(
            authorization,
            readiness=readiness,
            qualification=qualification,
            fixed_cohort=cohort,
            implementation_head=_HEAD,
            qualification_artifact_sha256="c" * 64,
            fixed_cohort_artifact_sha256="d" * 64,
            native_manifest_sha256=_MANIFEST_SHA,
            native_binary_sha256=qualification["native_binary_sha256"],
        )


def test_t113_exact_head_authorization_gate_rejects_before_adapter_factory(
    tmp_path, monkeypatch
):
    values = _run_fixture(tmp_path, monkeypatch)
    _write_json(values["authorization_path"], {"authorized": True})
    created: list[bool] = []
    output_root = tmp_path / "never-created"
    with pytest.raises(T113CanaryAuthorizationError, match="unexpected shape"):
        command.run_t113_canary_from_paths(
            qualification_path=values["qualification_path"],
            fixed_cohort_path=values["cohort_path"],
            readiness_path=values["readiness_path"],
            authorization_path=values["authorization_path"],
            t112_retention_manifest_path=values["retention_path"],
            native_manifest_path=values["native_manifest_path"],
            artifact_root=output_root,
            repo_root=values["repo_root"],
            worker_id="worker-test",
            adapter_factory=lambda: created.append(True),
        )
    assert created == []
    assert not output_root.exists()


def test_t113_mocked_canary_runs_exact_serial_plan_and_finalizes(tmp_path, monkeypatch):
    values = _run_fixture(tmp_path, monkeypatch)
    cohort = values["cohort"]
    selected = command.t113_canary_selection(cohort)
    calls: list[dict[str, object]] = []
    selected_records = {row["selection_identity"]: object() for row in selected}
    canonical_maps = {
        stratum: {row["selection_identity"]: object()}
        for row in selected
        for stratum in [row["stratum"]]
    }

    def load_restore_inputs(_qualification, *, implementation_head):
        assert implementation_head == _HEAD
        return None, selected_records, {"maps": canonical_maps}

    monkeypatch.setattr(command, "_load_t101_restore_inputs", load_restore_inputs)

    def adapter_factory():
        return _FakeAdapter(calls)

    def runner_factory(**kwargs):
        factory = kwargs["adapter_factory"]
        kwargs["restore_record"] = lambda identity, _stratum, _selected, _map: (
            factory(),
            {"selection_identity": identity},
            "mocked-exact-restore",
        )
        return command.T113DirectCanaryRunner(**kwargs)

    output_root = tmp_path / "canary-stage"
    result = command.run_t113_canary_from_paths(
        qualification_path=values["qualification_path"],
        fixed_cohort_path=values["cohort_path"],
        readiness_path=values["readiness_path"],
        authorization_path=values["authorization_path"],
        t112_retention_manifest_path=values["retention_path"],
        native_manifest_path=values["native_manifest_path"],
        artifact_root=output_root,
        repo_root=values["repo_root"],
        worker_id="worker-test",
        adapter_factory=adapter_factory,
        runner_factory=runner_factory,
        resource_probe=_resources,
    )
    assert result["bridge_call_count"] == 15
    assert result["formal_execution_authorized"] is False
    assert len(calls) == 15
    assert [row["particle_count"] for row in calls] == list(T101_COUNTS) * 3
    assert [row["selection_identity"] for row in calls] == [
        row["selection_identity"] for row in selected for _ in T101_COUNTS
    ]
    for state in selected:
        matching = [
            row
            for row in calls
            if row["selection_identity"] == state["selection_identity"]
        ]
        assert [row["sampler_seed"] for row in matching] == [
            derive_t101_sampler_seed(state["selection_identity"], 0)
        ] * 5
        assert all(
            row["particle_start"] == 0
            and row["search_simulations"] == 400
            and row["include_potions"] is False
            for row in matching
        )

    finalized = command.finalize_t113_canary_from_paths(
        raw_stage_manifest_path=Path(result["raw_stage_manifest"]["path"]),
        qualification_path=values["qualification_path"],
        fixed_cohort_path=values["cohort_path"],
        readiness_path=values["readiness_path"],
        authorization_path=values["authorization_path"],
        t112_retention_manifest_path=values["retention_path"],
        native_manifest_path=values["native_manifest_path"],
        repo_root=values["repo_root"],
    )
    assert finalized["terminal_classification"] == "CANARY_PREFIX_PARITY_VALID"
    final = json.loads(Path(finalized["finalization_artifact"]["path"]).read_text())
    assert final["formal_execution_authorized"] is False
    assert final["formal_execution_started"] is False
    envelope = json.loads(
        Path(finalized["stage_execution_envelope_artifact"]["path"]).read_text()
    )
    assert envelope["stage_name"] == "direct_canary_ladder"
    assert envelope["bridge_call_count"] == 15
    assert envelope["input_binding_sha256"] == canonical_sha256(cohort)

    canary_evidence = json.loads(
        Path(finalized["canary_evidence_artifact"]["path"]).read_text()
    )
    formal_cohort, formal_plan, formal_rows = fixtures._formal_fixture()
    assert formal_cohort == cohort
    formal_plan["implementation_head"] = _HEAD
    canary_finished = datetime.fromisoformat(envelope["finished_at_utc"])
    formal_started = canary_finished + timedelta(seconds=2)
    formal_finished = formal_started + timedelta(seconds=180)
    formal_envelope = {
        "schema_id": T113_STAGE_EXECUTION_ENVELOPE_SCHEMA,
        "task_id": "T113",
        "stage_name": "formal_n32_batch",
        "implementation_head": _HEAD,
        "input_binding_sha256": canonical_sha256(formal_plan),
        "bridge_call_count": 96,
        "terminal_status": "SUCCEEDED",
        "started_at_utc": formal_started.isoformat().replace("+00:00", "Z"),
        "finished_at_utc": formal_finished.isoformat().replace("+00:00", "Z"),
    }
    cost = build_t113_cost_report(
        formal_rows,
        formal_plan,
        canary_evidence=canary_evidence,
        cohort_manifest=cohort,
        execution_envelopes={
            "schema_id": T113_EXECUTION_ENVELOPE_SCHEMA,
            "task_id": "T113",
            "implementation_head": _HEAD,
            "complete": True,
            "canary_stage": envelope,
            "formal_stage": formal_envelope,
        },
    )
    assert cost["canary_stage_elapsed_time_s"] > 0
    assert cost["total_observed_wall_clock_time_scope"] == (
        "canary_stage_start_to_formal_stage_finish_including_inter_stage_gap"
    )


def test_t113_mocked_bridge_failure_is_retained_without_retry(tmp_path, monkeypatch):
    values = _run_fixture(tmp_path, monkeypatch)
    selected = command.t113_canary_selection(values["cohort"])
    selected_records = {row["selection_identity"]: object() for row in selected}
    canonical_maps = {
        stratum: {row["selection_identity"]: object()}
        for row in selected
        for stratum in [row["stratum"]]
    }

    def load_restore_inputs(_qualification, *, implementation_head):
        assert implementation_head == _HEAD
        return None, selected_records, {"maps": canonical_maps}

    monkeypatch.setattr(command, "_load_t101_restore_inputs", load_restore_inputs)
    bridge_attempts: list[int] = []

    class FailingAdapter:
        def sample_hidden_future_particles_search(self, _restored, **kwargs):
            bridge_attempts.append(kwargs["particle_count"])
            if kwargs["particle_count"] == 4:
                raise RuntimeError("fixture bridge failure")
            report = fixtures._batch_report(seed=kwargs["sampler_seed"])
            report["particle_count"] = kwargs["particle_count"]
            report["particles"] = report["particles"][: kwargs["particle_count"]]
            return report

    def runner_factory(**kwargs):
        factory = kwargs["adapter_factory"]
        kwargs["restore_record"] = lambda identity, _stratum, _selected, _map: (
            factory(),
            {"selection_identity": identity},
            "mocked-exact-restore",
        )
        return command.T113DirectCanaryRunner(**kwargs)

    output_root = tmp_path / "failed-canary"
    with pytest.raises(T113CanaryWorkflowError, match="without retry"):
        command.run_t113_canary_from_paths(
            qualification_path=values["qualification_path"],
            fixed_cohort_path=values["cohort_path"],
            readiness_path=values["readiness_path"],
            authorization_path=values["authorization_path"],
            t112_retention_manifest_path=values["retention_path"],
            native_manifest_path=values["native_manifest_path"],
            artifact_root=output_root,
            repo_root=values["repo_root"],
            worker_id="worker-test",
            adapter_factory=FailingAdapter,
            runner_factory=runner_factory,
            resource_probe=_resources,
        )
    assert bridge_attempts == [2, 4]
    failure = json.loads(
        (output_root / "t113-canary-stage-failure.json").read_text(encoding="utf-8")
    )
    assert failure["terminal_status"] == "FAILED_NO_RETRY"
    assert failure["terminal_classification"] == "INCOMPLETE"
    assert failure["retry_count"] == 0
    assert len(failure["attempt_references"]) == 2
    assert len(failure["completed_call_references"]) == 1
