from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_t110_configuration_aware_mapping import _v2_report

from sts_combat_rl.commands import t111_configured_search_execution as execution
from sts_combat_rl.commands import t111_configured_search_execution_cli as execution_cli
from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t105_native_stage_observability import (
    STAGES_IN_EXECUTION_ORDER,
    TRACE_SCHEMA,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111SupportExclusion,
)

_NATIVE = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": T111_NATIVE_REF,
    "commit": T111_NATIVE_COMMIT,
}


def _two_particle_report(seed: int) -> dict[str, object]:
    report = _v2_report()
    first = report["particles"][0]
    first["sampler_seed"] = 0xA5100000
    first["root_evaluation"]["simulations_requested"] = 400
    first["root_evaluation"]["root_visits"] = 800
    second = deepcopy(first)
    second["particle_index"] = 1
    second["sampler_seed"] = 0xA5100001
    second["hidden_future_fingerprint"] = "second-fingerprint"
    report["search_simulations"] = 400
    report["sampler_seed_input"] = seed
    report["particle_count"] = 2
    report["particles"] = [first, second]
    return report


def _adapter_actions(report):
    return [
        SimpleNamespace(
            kind=action["kind"],
            label=action["label"],
            raw={
                **{key: action[key] for key in ("scope", "idx1", "idx2", "idx3")},
                "native_private": object(),
            },
        )
        for action in report["anchor_ordered_public_legal_actions"]
    ]


class _FakeAdapter:
    def __init__(
        self,
        report,
        *,
        actions=None,
        bridge_exception=None,
        stage_trace=None,
    ):
        self.report = report
        self.actions = _adapter_actions(report) if actions is None else actions
        self.bridge_exception = bridge_exception
        self.stage_trace = stage_trace
        self.bridge_calls = []

    def legal_actions(self, _restored):
        return self.actions

    def sample_hidden_future_particles_search(self, snapshot, **kwargs):
        self.bridge_calls.append((snapshot, kwargs))
        if self.bridge_exception is not None:
            raise self.bridge_exception
        return self.report

    def last_particle_search_stage_diagnostics(self):
        return self.stage_trace


def _runner(
    monkeypatch,
    *,
    identity="A:fixture",
    report=None,
    adapter_actions=None,
    context_candidate_actions=None,
    bridge_exception=None,
    stage_trace=None,
    on_bridge_call=None,
):
    seed = derive_t101_sampler_seed(identity, 0)
    expected_actions = _two_particle_report(seed)["anchor_ordered_public_legal_actions"]
    expected_context = {
        "history": [],
        "candidate_actions": expected_actions,
        "input_state": "PLAYER_NORMAL",
    }
    restored = SimpleNamespace(raw=object())
    projection = SimpleNamespace(
        canonical_payload=json.dumps(
            _two_particle_report(seed)["anchor_public_information_projection"]
        )
    )
    selected = SimpleNamespace(selection_identity=identity)
    canonical = SimpleNamespace(public_run_context=expected_context)
    report = report or _two_particle_report(seed)
    adapter = _FakeAdapter(
        report,
        actions=adapter_actions,
        bridge_exception=bridge_exception,
        stage_trace=stage_trace,
    )
    actual_context = dict(expected_context)
    if context_candidate_actions is not None:
        actual_context["candidate_actions"] = context_candidate_actions
    restore_calls = []

    monkeypatch.setattr(
        execution,
        "restore_t085_canonical_record",
        lambda actual_adapter, actual_selected, canonical_map: (
            restore_calls.append((actual_adapter, actual_selected, canonical_map))
            or (restored, "exact_t085_canonical")
        ),
    )
    monkeypatch.setattr(
        execution,
        "read_native_public_projection",
        lambda _adapter, _restored: projection,
    )
    monkeypatch.setattr(
        execution,
        "_validate_projection_candidate_parity",
        lambda _projection, _actions: None,
    )
    monkeypatch.setattr(
        execution,
        "build_public_run_context",
        lambda *_args, **_kwargs: actual_context,
    )
    runner = execution.T111NativeRecordRunner(
        adapter_factory=lambda: adapter,
        selected_records={identity: selected},
        canonical_records_by_stratum={"A": {identity: canonical}},
        native_identity=_NATIVE,
        on_bridge_call=on_bridge_call,
    )
    record = {"selection_identity": identity, "cohort": "A"}
    return runner, record, adapter, restore_calls, restored


def test_t111_runner_restores_checks_parity_and_makes_one_frozen_bridge_call(
    monkeypatch,
):
    runner, record, adapter, restore_calls, restored = _runner(monkeypatch)
    seed = derive_t101_sampler_seed(record["selection_identity"], 0)

    result = runner(record)

    assert result["restore_exact_accepted_state"] is True
    assert result["public_projection_parity"] is True
    assert result["ordered_legal_action_parity"] is True
    assert result["search_configuration_unchanged"] is True
    assert result["restore_method"] == "exact_t085_canonical"
    assert len(restore_calls) == 1
    assert restore_calls[0][1].selection_identity == record["selection_identity"]
    assert len(adapter.bridge_calls) == 1
    snapshot, kwargs = adapter.bridge_calls[0]
    assert snapshot is restored
    assert kwargs == {
        "sampler_seed": seed,
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    assert (
        execution._adapter_actions_as_public_identities(adapter.actions)
        == result["bridge_report"]["anchor_ordered_public_legal_actions"]
    )


@pytest.mark.parametrize(
    "drift",
    ["ordinal", "kind", "idx", "label"],
)
def test_t111_runner_rejects_ordered_bridge_action_identity_drift(monkeypatch, drift):
    report = _two_particle_report(derive_t101_sampler_seed("A:fixture", 0))
    actions = _adapter_actions(report)
    if drift == "ordinal":
        actions[0], actions[1] = actions[1], actions[0]
    elif drift == "kind":
        actions[0] = SimpleNamespace(
            kind="drifted-kind", label=actions[0].label, raw=actions[0].raw
        )
    elif drift == "idx":
        raw = dict(actions[0].raw)
        raw["idx1"] += 1
        actions[0] = SimpleNamespace(
            kind=actions[0].kind, label=actions[0].label, raw=raw
        )
    else:
        actions[0] = SimpleNamespace(
            kind=actions[0].kind,
            label="drifted-label",
            raw=actions[0].raw,
        )
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch, report=report, adapter_actions=actions
    )

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)

    assert error.value.reason == "ordered_public_action_parity_failure"
    assert (
        error.value.evidence["boundary"] == "bridge_to_restored_ordered_action_parity"
    )
    assert (
        error.value.evidence["structural_admission_predicates"][
            "ordered_legal_action_parity"
        ]
        is False
    )
    assert len(adapter.bridge_calls) == 1


def test_t111_t015_restored_context_candidate_parity_remains_strict(monkeypatch):
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch,
        context_candidate_actions=[{"availability": "available", "items": []}],
    )

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)

    assert error.value.reason == "ordered_public_action_parity_failure"
    assert error.value.evidence["boundary"] == "restored_ordered_action_parity"
    assert adapter.bridge_calls == []


def test_t111_runner_bridge_observer_counts_only_actual_bridge_invocations(monkeypatch):
    observed = []
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch, on_bridge_call=observed.append
    )

    runner(record)

    assert observed == [record["selection_identity"]]
    assert len(adapter.bridge_calls) == 1


def test_t111_runner_rejects_wrong_bridge_input_seed_from_native_bridge(monkeypatch):
    identity = "A:fixture"
    seed = derive_t101_sampler_seed(identity, 0)
    report = _two_particle_report(seed)
    report["sampler_seed_input"] += 1
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch, identity=identity, report=report
    )

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)
    assert error.value.reason == "v2_bridge_schema_or_classification_failure"
    assert len(adapter.bridge_calls) == 1


def test_t111_runner_accepts_valid_native_derived_particle_seed_metadata(monkeypatch):
    identity = "A:fixture"
    seed = derive_t101_sampler_seed(identity, 0)
    report = _two_particle_report(seed)
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch, identity=identity, report=report
    )

    result = runner(record)

    assert result["bridge_report"]["sampler_seed_input"] == seed
    assert [row["sampler_seed"] for row in result["bridge_report"]["particles"]] == [
        0xA5100000,
        0xA5100001,
    ]
    assert len(adapter.bridge_calls) == 1


def test_t111_runner_does_not_invoke_bridge_for_unbound_source_record(monkeypatch):
    runner, record, adapter, restore_calls, _restored = _runner(monkeypatch)
    record["selection_identity"] = "A:not-retained"

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)

    assert error.value.reason == "restore_or_provenance_incompatible"
    assert restore_calls == []
    assert adapter.bridge_calls == []


def _failed_stage_trace(*, stage: str, failure_code: str) -> dict[str, object]:
    stages: dict[str, str] = {}
    failed_seen = False
    for name in STAGES_IN_EXECUTION_ORDER:
        if name == stage:
            stages[name] = "failed"
            failed_seen = True
        elif failed_seen:
            stages[name] = "not_reached"
        else:
            stages[name] = "completed"
    particle = {
        "particle_index": 0,
        "stages": stages,
        "first_failed_stage": stage,
        "failure_code": failure_code,
    }
    return {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "failed_closed",
        "first_failed_stage": stage,
        "failure_code": failure_code,
        "accepted_root_report_returned": False,
        "particles": [particle, {**particle, "particle_index": 1}],
    }


@pytest.mark.parametrize(
    ("stage", "failure_code", "expected_reason"),
    [
        (
            "public_fidelity_validation",
            "public_fidelity_failed",
            "public_fidelity_failure",
        ),
        (
            "public_fidelity_validation",
            "anchor_unsupported_fidelity",
            "public_fidelity_failure",
        ),
        (
            "public_fidelity_validation",
            "native_exception",
            "accepted_structured_bridge_failure",
        ),
        (
            "root_occurrence_mapping",
            "root_occurrence_mapping_failed",
            "accepted_structured_bridge_failure",
        ),
    ],
)
def test_t111_bridge_failure_uses_only_validated_structured_failure_class(
    monkeypatch, stage, failure_code, expected_reason
):
    trace = _failed_stage_trace(stage=stage, failure_code=failure_code)
    runner, record, adapter, _restore_calls, _restored = _runner(
        monkeypatch,
        bridge_exception=RuntimeError("private payload must never be retained"),
        stage_trace=trace,
    )

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)

    assert error.value.reason == expected_reason
    diagnostics = error.value.evidence["bridge_diagnostics"]
    assert diagnostics["stage_diagnostics_status"] == "validated_failure"
    assert diagnostics["structured_stage_evidence"]["failure_code"] == failure_code
    assert diagnostics.get("structured_failure_class") == (
        "public_fidelity_failure"
        if expected_reason == "public_fidelity_failure"
        else None
    )
    assert "private payload" not in repr(error.value.evidence)
    assert len(adapter.bridge_calls) == 1


def test_t111_bridge_failure_with_invalid_trace_stays_generic_and_sanitized(
    monkeypatch,
):
    runner, record, _adapter, _restore_calls, _restored = _runner(
        monkeypatch,
        bridge_exception=RuntimeError("do not retain me"),
        stage_trace={"private": "payload"},
    )

    with pytest.raises(T111SupportExclusion) as error:
        runner(record)

    assert error.value.reason == "accepted_structured_bridge_failure"
    diagnostics = error.value.evidence["bridge_diagnostics"]
    assert diagnostics == {"stage_diagnostics_status": "invalid_or_unavailable"}
    assert "private payload" not in repr(error.value.evidence)
    assert "do not retain me" not in repr(error.value.evidence)


def _write_json_reference(path: Path, value: dict[str, object], schema: str):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(data)
    return {
        "path": str(path),
        "schema_id": schema,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _authorization_fixture(tmp_path: Path, monkeypatch):
    head = "a" * 40
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    qualification_path = artifact_root / "qualification.json"
    preparation_path = artifact_root / "preparation.json"
    resource_status_path = artifact_root / "status.json"
    python_runtime = execution_cli.preparation._python_runtime_fingerprint()
    qualification = {
        "schema_id": execution_cli.T111_PREP_QUALIFICATION_SCHEMA,
        "eligible": True,
        "candidate_execution_started": False,
        "implementation_head": head,
        "python_runtime": python_runtime,
        "native_identity": _NATIVE,
        "retained_artifacts": {
            name: {} for name in execution_cli._EXPECTED_INPUT_ROLES
        },
    }
    qualification_ref = _write_json_reference(
        qualification_path,
        qualification,
        execution_cli.T111_PREP_QUALIFICATION_SCHEMA,
    )
    readiness = {
        "schema_id": execution_cli.T111_PREPARATION_SCHEMA,
        "candidate_execution_authorized": False,
        "candidate_execution_started": False,
        "implementation_head": head,
        "python_runtime": python_runtime,
        "input_qualification_sha256": qualification_ref["sha256"],
    }
    preparation_ref = _write_json_reference(
        preparation_path, readiness, execution_cli.T111_PREPARATION_SCHEMA
    )
    extension_suffix = str(python_runtime["extension_suffix"])
    binary_path = artifact_root / f"native{extension_suffix}"
    binary_path.write_bytes(b"exact native binary fixture")
    resource_root = artifact_root / "leases"
    resource_root.mkdir()
    resource_plan = {
        "effective_worker_count": 1,
        "shard_count": 1,
        "shards": [
            {
                "worker_id": "worker-0",
                "shard_id": "shard-0",
                "candidate_range": [0, 413],
                "stratum_ranges": {"A": [0, 93], "B": [93, 285], "C": [285, 413]},
            }
        ],
        "resource_guard": {
            "resource_root": str(resource_root),
            "status_path": str(resource_status_path.resolve()),
            "batch_id": "t111-test-batch",
            "job_id": "t111-test-job",
            "memory_budget_mib": 4096,
            "memory_request_mib": 3072,
            "runtime_rss_limit_mib": 3072,
            "runtime_memavailable_floor_mib": 1024,
            "runtime_sample_seconds": 1,
        },
    }
    authorization = {
        "schema_id": execution_cli.T111_EXECUTION_AUTH_SCHEMA,
        "task_id": "T111",
        "authorization_id": "maintainer-authorization-test-unique",
        "authorized": True,
        "decision": "EXECUTION_AUTHORIZED",
        "implementation_worktree_path": str(repo_root.resolve()),
        "implementation_head": head,
        "approved_spec_commit": "f8ceef6f68bab587f7696d9230fbffd7416b19b2",
        "python_runtime": python_runtime,
        "qualification_artifact": qualification_ref,
        "preparation_artifact": preparation_ref,
        "native_identity": _NATIVE,
        "native_binary": {
            "path": str(binary_path),
            "sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
            "size_bytes": binary_path.stat().st_size,
        },
        "resource_plan": resource_plan,
    }
    authorization_path = artifact_root / "execution-authorization.json"
    monkeypatch.setattr(
        execution_cli,
        "_git_state",
        lambda _root: (
            head,
            "planner/t111-configured-search-domain-support-reentry",
            False,
        ),
    )
    kwargs = {
        "authorization_path": authorization_path,
        "qualification_path": qualification_path,
        "preparation_path": preparation_path,
        "resource_status_path": resource_status_path,
        "expected_head": head,
        "repo_root": repo_root,
    }
    return authorization, kwargs


def test_t111_execution_authorization_binds_full_serial_population_and_guard(
    tmp_path, monkeypatch
):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)

    verified = execution_cli.validate_t111_execution_authorization(
        authorization, **kwargs
    )

    assert verified["resource_plan"]["effective_worker_count"] == 1
    assert verified["resource_plan"]["shards"][0]["candidate_range"] == [0, 413]
    assert verified["resource_plan"]["shards"][0]["stratum_ranges"] == {
        "A": [0, 93],
        "B": [93, 285],
        "C": [285, 413],
    }
    assert verified["resource_plan"]["resource_guard"]["batch_id"] == "t111-test-batch"


def test_t111_authorization_binds_external_artifacts_to_exact_worktree(
    tmp_path, monkeypatch
):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    assert kwargs["authorization_path"].parent != kwargs["repo_root"]
    authorization["implementation_worktree_path"] = str(
        (tmp_path / "other-worktree").resolve()
    )

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli.validate_t111_execution_authorization(authorization, **kwargs)


def test_t111_authorization_rejects_python_runtime_mismatch(tmp_path, monkeypatch):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    authorization["python_runtime"] = {
        **authorization["python_runtime"],
        "minor": authorization["python_runtime"]["minor"] + 1,
    }

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli.validate_t111_execution_authorization(authorization, **kwargs)


def test_t111_authorization_rejects_native_extension_with_wrong_abi(
    tmp_path, monkeypatch
):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    binary_path = Path(str(authorization["native_binary"]["path"]))
    wrong_path = binary_path.with_name("native.cpython-0-unrelated.so")
    wrong_path.write_bytes(binary_path.read_bytes())
    authorization["native_binary"] = {
        "path": str(wrong_path),
        "sha256": hashlib.sha256(wrong_path.read_bytes()).hexdigest(),
        "size_bytes": wrong_path.stat().st_size,
    }

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli.validate_t111_execution_authorization(authorization, **kwargs)

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli._load_native_module(
            wrong_path, str(authorization["native_binary"]["sha256"])
        )


@pytest.mark.parametrize(
    ("platform_name", "ru_maxrss", "raw_unit"),
    [
        ("linux", 204800, "KiB"),
        ("darwin", 209715200, "bytes"),
    ],
)
def test_t111_peak_rss_report_uses_post_selector_ru_maxrss_and_units(
    monkeypatch, platform_name, ru_maxrss, raw_unit
):
    selector_state = {"complete": False}

    def getrusage(_who):
        assert selector_state["complete"] is True
        return SimpleNamespace(ru_maxrss=ru_maxrss)

    monkeypatch.setattr(
        execution_cli,
        "resource",
        SimpleNamespace(RUSAGE_SELF=0, getrusage=getrusage),
    )
    selector_state["complete"] = True

    metrics = execution_cli._capture_process_peak_rss(platform_name=platform_name)

    assert metrics["process_peak_rss_mib"] == 200.0
    assert metrics["process_peak_rss_raw"] == ru_maxrss
    assert metrics["process_peak_rss_raw_unit"] == raw_unit
    assert metrics["process_peak_rss_sample_phase"] == "after_selector_completion"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorized", False),
        ("decision", "PREPARATION_ONLY"),
    ],
)
def test_t111_unapproved_or_preparation_only_document_cannot_authorize_execution(
    tmp_path, monkeypatch, field, value
):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    authorization[field] = value

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli.validate_t111_execution_authorization(authorization, **kwargs)


def test_t111_authorization_rejects_noncanonical_population_shards(
    tmp_path, monkeypatch
):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    authorization["resource_plan"]["shards"][0]["stratum_ranges"]["B"] = [92, 285]

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli.validate_t111_execution_authorization(authorization, **kwargs)


def test_t111_active_guard_must_match_authorized_batch_and_job(tmp_path, monkeypatch):
    authorization, kwargs = _authorization_fixture(tmp_path, monkeypatch)
    verified = execution_cli.validate_t111_execution_authorization(
        authorization, **kwargs
    )
    guard_plan = verified["resource_plan"]["resource_guard"]
    status = {
        "state": "RUNNING",
        "target_pid": 44,
        "resource_admission": {
            "worker_count": 1,
            "shard_count": 1,
            "batch_id": "wrong-batch",
            "job_id": guard_plan["job_id"],
            "memory_budget_mib": guard_plan["memory_budget_mib"],
            "memory_request_mib": guard_plan["memory_request_mib"],
            "runtime_guard": {
                "enabled": True,
                "state": "MONITORING",
                "rss_limit_mib": guard_plan["runtime_rss_limit_mib"],
                "memavailable_floor_mib": guard_plan["runtime_memavailable_floor_mib"],
                "sample_interval_seconds": guard_plan["runtime_sample_seconds"],
            },
        },
    }
    kwargs["resource_status_path"].write_text(json.dumps(status), encoding="utf-8")

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli._verify_active_resource_guard(
            kwargs["resource_status_path"], authorization=verified, target_pid=44
        )


def test_t111_finalizer_compares_ordered_jsonl_rows_to_cohort(tmp_path):
    attempts_path = tmp_path / "attempts.jsonl"
    attempt = {"selection_identity": "A:one", "admitted": True, "source_ordinal": 0}
    shard = {
        "worker_id": "worker-0",
        "shard_id": "shard-0",
        "candidate_range": [0, 413],
    }
    jsonl_row = {
        **attempt,
        "worker_id": "worker-0",
        "shard_id": "shard-0",
        "shard_candidate_range": [0, 413],
        "executor_attempt_status": "ADMITTED",
    }
    attempts_path.write_text(json.dumps(jsonl_row) + "\n", encoding="utf-8")
    reference = {
        "path": str(attempts_path),
        "schema_id": "t111-candidate-attempts-jsonl-v1",
        "size_bytes": attempts_path.stat().st_size,
        "sha256": hashlib.sha256(attempts_path.read_bytes()).hexdigest(),
    }
    record = {"executor": {"shards": [shard]}}

    execution_cli._validate_attempt_jsonl_matches_cohort(
        attempts_path=attempts_path,
        attempt_reference=reference,
        attempt_rows=[attempt],
        execution_record=record,
    )
    tampered = {**jsonl_row, "worker_id": "worker-other"}
    attempts_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    reference["size_bytes"] = attempts_path.stat().st_size
    reference["sha256"] = hashlib.sha256(attempts_path.read_bytes()).hexdigest()

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli._validate_attempt_jsonl_matches_cohort(
            attempts_path=attempts_path,
            attempt_reference=reference,
            attempt_rows=[attempt],
            execution_record=record,
        )


def _terminal_guard_fixture(tmp_path: Path):
    resource_root = tmp_path / "leases"
    resource_root.mkdir()
    plan = {
        "resource_root": str(resource_root),
        "batch_id": "t111-batch",
        "job_id": "t111-job",
        "memory_budget_mib": 4096,
        "memory_request_mib": 3072,
        "runtime_rss_limit_mib": 3072,
        "runtime_memavailable_floor_mib": 1024,
        "runtime_sample_seconds": 1,
    }
    record = {
        "target_pid": 44,
        "resource_guard_plan": plan,
        "executor": {"effective_worker_count": 1, "shard_count": 1},
    }
    status = {
        "state": "SUCCEEDED",
        "exit_code": 0,
        "target_pid": 44,
        "resource_admission": {
            "root": str(resource_root),
            "batch_id": "t111-batch",
            "job_id": "t111-job",
            "target_pid": 44,
            "worker_count": 1,
            "shard_count": 1,
            "memory_budget_mib": 4096,
            "memory_request_mib": 3072,
            "runtime_guard": {
                "state": "COMPLETED",
                "sample_count": 5,
                "rss_limit_mib": 3072,
                "memavailable_floor_mib": 1024,
                "sample_interval_seconds": 1,
                "peak_rss_mib": 2048,
                "lowest_memavailable_mib": 4096,
                "sample_error": None,
                "trigger_reason": None,
            },
        },
    }
    return status, record


def test_t111_terminal_guard_binds_pid_identity_and_measured_bounds(tmp_path):
    status, record = _terminal_guard_fixture(tmp_path)

    admission, guard = execution_cli._validate_completed_resource_guard(status, record)

    assert admission["target_pid"] == record["target_pid"]
    assert (
        guard["peak_rss_mib"] <= record["resource_guard_plan"]["runtime_rss_limit_mib"]
    )


@pytest.mark.parametrize(
    ("status_path", "status_value"),
    [
        (("resource_admission", "batch_id"), "wrong-batch"),
        (("resource_admission", "target_pid"), 45),
        (("resource_admission", "runtime_guard", "peak_rss_mib"), 4000),
        (("resource_admission", "runtime_guard", "lowest_memavailable_mib"), 100),
    ],
)
def test_t111_terminal_guard_rejects_changed_identity_or_tripwire(
    tmp_path, status_path, status_value
):
    status, record = _terminal_guard_fixture(tmp_path)
    cursor = status
    for key in status_path[:-1]:
        cursor = cursor[key]
    cursor[status_path[-1]] = status_value

    with pytest.raises(execution_cli.T111ExecutionAuthorizationError):
        execution_cli._validate_completed_resource_guard(status, record)
