from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.t106_failure_stages import (
    _readiness_qualified,
    _write_outputs,
)
from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t105_native_stage_observability import (
    STAGES_IN_EXECUTION_ORDER,
    TRACE_SCHEMA,
)
from sts_combat_rl.sim.t106_failure_stages import (
    HISTORICAL_T104_CLASSES,
    STAGE_CLASSES,
    T106IncompleteError,
    T106NativeRecordRunner,
    aggregate,
    classify_trace,
    select_t104_part_b,
)


def _trace(stage: str | None) -> dict:
    stages = dict.fromkeys(STAGES_IN_EXECUTION_ORDER, "not_reached")
    code = "request_or_preflight_failure" if stage is None else "native_stage_exception"
    particles = []
    if stage is not None:
        for earlier in STAGES_IN_EXECUTION_ORDER[
            : STAGES_IN_EXECUTION_ORDER.index(stage)
        ]:
            stages[earlier] = "completed"
        stages[stage] = "failed"
        particles = [
            {
                "particle_index": 0,
                "stages": stages,
                "first_failed_stage": stage,
                "failure_code": code,
            }
        ]
    return {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "failed_closed",
        "first_failed_stage": stage,
        "failure_code": code,
        "accepted_root_report_returned": False,
        "particles": particles,
    }


def _accepted_trace() -> dict:
    trace = _trace("root_occurrence_mapping")
    trace.update(
        attempt_status="accepted",
        first_failed_stage=None,
        failure_code=None,
        accepted_root_report_returned=True,
    )
    particle = trace["particles"][0]
    particle["stages"] = dict.fromkeys(STAGES_IN_EXECUTION_ORDER, "completed")
    particle["first_failed_stage"] = None
    particle["failure_code"] = None
    return trace


def _candidate() -> dict:
    return {
        "selection_identity": "test",
        "stratum": "A",
        "source_ordinal": 0,
        "selection_digest": "digest",
        "part_b_class": HISTORICAL_T104_CLASSES[0],
        "sampler_seed": 7,
        "t104_row_ordinal": 0,
        "current_native_identity": {
            "commit": "97f59b620efe5ee1571f8da298c99d1e21c1149b"
        },
    }


@pytest.mark.parametrize(
    "stage,cls",
    list(zip((None, *STAGES_IN_EXECUTION_ORDER), STAGE_CLASSES, strict=True)),
)
def test_all_seven_classes_are_native_telemetry_only(
    stage: str | None, cls: str
) -> None:
    assert classify_trace(_trace(stage))[0] == cls
    trace = _trace(stage)
    trace["exception_text"] = "search setup failure"
    with pytest.raises(ValueError, match="exactly"):
        classify_trace(trace)


def test_failed_trace_rejects_private_and_contradictory_metadata() -> None:
    trace = _trace("search_execution")
    trace["particles"][0]["stages"]["root_occurrence_mapping"] = "completed"
    with pytest.raises(ValueError, match="later stage"):
        classify_trace(trace)
    trace = _trace("search_execution")
    trace["first_failed_stage"] = "search_setup"
    with pytest.raises(ValueError, match="disagrees"):
        classify_trace(trace)
    trace = _trace("search_execution")
    trace["particles"][0]["stages"]["hidden_intent"] = "private"
    with pytest.raises(ValueError, match="exactly"):
        classify_trace(trace)


@pytest.mark.parametrize("indices", ([99], [2], [0, 0], [1, 0]))
def test_failed_trace_binds_available_particle_indices(indices: list[int]) -> None:
    trace = _trace("search_execution")
    trace["particles"][0]["particle_index"] = indices[0]
    if len(indices) == 2:
        trace["particles"].append(
            {
                "particle_index": indices[1],
                "stages": dict.fromkeys(STAGES_IN_EXECUTION_ORDER, "not_reached"),
                "first_failed_stage": None,
                "failure_code": None,
            }
        )
    with pytest.raises(ValueError, match="particle index"):
        classify_trace(trace)
    if len(indices) == 1:
        trace["particles"][0]["particle_index"] = None
        assert classify_trace(trace)[0] == "SEARCH_EXECUTION_FAILURE"


def _population() -> list[dict]:
    rows = []
    layout = [
        ("A", HISTORICAL_T104_CLASSES[0], 84),
        ("A", HISTORICAL_T104_CLASSES[1], 5),
        ("B", HISTORICAL_T104_CLASSES[0], 174),
        ("B", HISTORICAL_T104_CLASSES[1], 15),
        ("C", HISTORICAL_T104_CLASSES[0], 65),
    ]
    for stratum, cls, n in layout:
        for _ in range(n):
            identity = f"test:{len(rows)}"
            rows.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "part_b_class": cls,
                    "diagnostic_class": "OPAQUE_BRIDGE_FAILURE",
                    "baseline_reproduced": True,
                    "full_bridge_failed": True,
                    "bridge_invocation_status": "failed",
                    "native_observability_required": True,
                    "pre_bridge_passed": True,
                    "replicate_index": 0,
                    "sampler_seed": derive_t101_sampler_seed(identity, 0),
                    "particle_count": 2,
                    "search_simulations": 400,
                    "include_potions": False,
                    "current_native_identity": {
                        "commit": "97f59b620efe5ee1571f8da298c99d1e21c1149b"
                    },
                }
            )
    rows.extend(
        {"diagnostic_class": "PUBLIC_PROJECTION_PARITY_FAILURE"} for _ in range(70)
    )
    return rows


def test_exact_t104_part_b_selection_and_frozen_seed() -> None:
    rows = _population()
    selected = select_t104_part_b(rows)
    assert len(selected) == 343
    assert [r["selection_identity"] for r in selected] == [
        f"test:{i}" for i in range(343)
    ]
    changed = deepcopy(rows)
    changed[0]["sampler_seed"] += 1
    with pytest.raises(T106IncompleteError, match="frozen"):
        select_t104_part_b(changed)


def test_aggregate_terminal_priority_and_complete_counts() -> None:
    rows = []
    for i in range(343):
        rows.append(
            {
                "selection_identity": f"test:{i}",
                "stratum": "A" if i < 89 else "B" if i < 278 else "C",
                "historical_t104_part_b_class": HISTORICAL_T104_CLASSES[0]
                if i < 323
                else HISTORICAL_T104_CLASSES[1],
                "baseline_contradiction": False,
                "telemetry_contract_violation": False,
                "stage_class": STAGE_CLASSES[4],
                "native_stage_trace": _trace("search_execution"),
            }
        )
    report = aggregate(rows, full=True)
    assert (
        report["terminal_classification"]
        == "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED"
    )
    assert report["stage_classes"][STAGE_CLASSES[4]]["count"] == 343
    assert report["first_failing_particle_index"]["0"]["count"] == 343
    assert sum(x["count"] for x in report["stage_classes"].values()) == 343
    assert report["stage_classes"][STAGE_CLASSES[4]]["fraction"] == {
        "numerator": 343,
        "denominator": 343,
    }
    assert report["by_stratum"]["A"][STAGE_CLASSES[4]]["fraction"] == {
        "numerator": 89,
        "denominator": 89,
    }
    assert report["by_stratum"]["B"][STAGE_CLASSES[4]]["fraction"]["denominator"] == 189
    assert report["by_stratum"]["C"][STAGE_CLASSES[4]]["fraction"]["denominator"] == 65
    assert (
        report["by_historical_t104_class"][HISTORICAL_T104_CLASSES[0]][
            STAGE_CLASSES[4]
        ]["fraction"]["denominator"]
        == 323
    )
    assert (
        report["by_historical_t104_class"][HISTORICAL_T104_CLASSES[1]][
            STAGE_CLASSES[4]
        ]["fraction"]["denominator"]
        == 20
    )
    code = report["stage_class_by_failure_code"][STAGE_CLASSES[4]][
        "native_stage_exception"
    ]
    assert code["fraction_of_valid_replays"] == {"numerator": 343, "denominator": 343}
    assert code["fraction_within_stage_class"] == {"numerator": 343, "denominator": 343}
    assert (
        report["first_failing_particle_index"]["0"]["fraction_of_valid_replays"][
            "denominator"
        ]
        == 343
    )
    assert (
        report["stage_status_transition_signatures"][0]["fraction_of_particle_rows"][
            "denominator"
        ]
        == 343
    )
    rows[0]["telemetry_contract_violation"] = True
    assert (
        aggregate(rows, full=True)["terminal_classification"]
        == "NATIVE_OBSERVABILITY_CONTRACT_NOT_REPRODUCED"
    )
    rows[1]["baseline_contradiction"] = True
    assert (
        aggregate(rows, full=True)["terminal_classification"]
        == "T104_PART_B_BASELINE_NOT_REPRODUCED"
    )


def test_native_snapshot_is_taken_immediately_after_exact_bridge_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    class Adapter:
        def sample_hidden_future_particles_search(
            self, _snapshot: object, **kwargs: object
        ) -> None:
            events.append(("bridge", kwargs))
            raise RuntimeError("words must not classify a stage")

        def last_particle_search_stage_diagnostics(self) -> dict:
            events.append(("snapshot", None))
            return _trace("root_occurrence_mapping")

    class FakeT103:
        def __init__(self, **kwargs: object) -> None:
            self.factory = kwargs["adapter_factory"]

        def diagnose(self, record: object, **kwargs: object) -> dict:
            adapter = self.factory()
            with pytest.raises(RuntimeError):
                adapter.sample_hidden_future_particles_search(
                    object(),
                    sampler_seed=7,
                    particle_start=0,
                    particle_count=2,
                    search_simulations=400,
                    include_potions=False,
                )
            return {
                "bridge_invocation_status": "failed",
                "wall_clock_time_s": 1.0,
                "exception_type": "RuntimeError",
                "exception_signature": "audit",
            }

    monkeypatch.setattr(
        "sts_combat_rl.sim.t106_failure_stages.T103NativeRecordRunner", FakeT103
    )
    runner = T106NativeRecordRunner(adapter_factory=Adapter)
    row = runner.diagnose({}, _candidate())
    assert [event[0] for event in events] == ["bridge", "snapshot"]
    assert row["stage_class"] == "ROOT_OCCURRENCE_MAPPING_FAILURE"
    assert row["classification_source"] == "native_structured_telemetry"
    assert row["exception_signature_audit_only"] == "audit"

    class AcceptedNativeAdapter(Adapter):
        def last_particle_search_stage_diagnostics(self) -> dict:
            events.append(("snapshot", None))
            return _accepted_trace()

    accepted = T106NativeRecordRunner(adapter_factory=AcceptedNativeAdapter).diagnose(
        {}, _candidate()
    )
    assert accepted["baseline_contradiction"] is False
    assert accepted["telemetry_contract_violation"] is True
    assert accepted["stage_class"] is None
    assert accepted["native_stage_trace"]["attempt_status"] == "accepted"
    assert (
        aggregate([accepted], full=False)["terminal_classification"]
        == "NATIVE_OBSERVABILITY_CONTRACT_NOT_REPRODUCED"
    )

    class WrongIndexAdapter(Adapter):
        def last_particle_search_stage_diagnostics(self) -> dict:
            trace = _trace("root_occurrence_mapping")
            trace["particles"][0]["particle_index"] = 99
            return trace

    wrong_index = T106NativeRecordRunner(adapter_factory=WrongIndexAdapter).diagnose(
        {}, _candidate()
    )
    assert wrong_index["baseline_contradiction"] is False
    assert wrong_index["telemetry_contract_violation"] is True


def test_returned_bridge_is_baseline_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Adapter:
        def sample_hidden_future_particles_search(
            self, _snapshot: object, **kwargs: object
        ) -> dict:
            return {"accepted": True}

        def last_particle_search_stage_diagnostics(self) -> dict:
            return _accepted_trace()

    class FakeT103:
        def __init__(self, **kwargs: object) -> None:
            self.factory = kwargs["adapter_factory"]

        def diagnose(self, record: object, **kwargs: object) -> dict:
            self.factory().sample_hidden_future_particles_search(
                object(),
                sampler_seed=7,
                particle_start=0,
                particle_count=2,
                search_simulations=400,
                include_potions=False,
            )
            return {
                "bridge_invocation_status": "returned_report",
                "restore_status": "succeeded",
                "wall_clock_time_s": 1.0,
            }

    monkeypatch.setattr(
        "sts_combat_rl.sim.t106_failure_stages.T103NativeRecordRunner", FakeT103
    )
    row = T106NativeRecordRunner(adapter_factory=Adapter).diagnose({}, _candidate())
    assert row["baseline_contradiction"] is True
    assert row["telemetry_contract_violation"] is False
    assert row["native_stage_trace"]["attempt_status"] == "accepted"
    assert (
        aggregate([row], full=False)["terminal_classification"]
        == "T104_PART_B_BASELINE_NOT_REPRODUCED"
    )


def test_changed_pre_bridge_behavior_is_contradiction_but_missing_restore_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeT103:
        restore_status = "succeeded"

        def __init__(self, **kwargs: object) -> None:
            pass

        def diagnose(self, record: object, **kwargs: object) -> dict:
            return {
                "restore_status": self.restore_status,
                "bridge_invocation_status": "not_reached",
                "diagnostic_class": "PUBLIC_PROJECTION_PARITY_FAILURE",
                "subreason_code": "public_projection_mismatch",
                "wall_clock_time_s": 1.0,
            }

    monkeypatch.setattr(
        "sts_combat_rl.sim.t106_failure_stages.T103NativeRecordRunner", FakeT103
    )
    row = T106NativeRecordRunner(adapter_factory=object).diagnose({}, _candidate())
    assert row["pre_bridge_change"] is True
    assert row["bridge_outcome"] == "not_invoked"
    assert row["native_stage_trace"] is None
    assert row["baseline_contradiction"] is True
    assert row["telemetry_contract_violation"] is False
    assert (
        aggregate([row], full=False)["terminal_classification"]
        == "T104_PART_B_BASELINE_NOT_REPRODUCED"
    )
    FakeT103.restore_status = "not_reached"
    with pytest.raises(T106IncompleteError, match="restore or source"):
        T106NativeRecordRunner(adapter_factory=object).diagnose({}, _candidate())
    FakeT103.restore_status = "succeeded"
    original = FakeT103.diagnose

    def unavailable(self, record: object, **kwargs: object) -> dict:
        result = original(self, record, **kwargs)
        result["diagnostic_class"] = "OPAQUE_BRIDGE_FAILURE"
        return result

    monkeypatch.setattr(FakeT103, "diagnose", unavailable)
    with pytest.raises(T106IncompleteError, match="observation is unavailable"):
        T106NativeRecordRunner(adapter_factory=object).diagnose({}, _candidate())


def test_retention_hashes_and_full_readiness_gate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "verified-native.so"
    sha = "1" * 64
    with pytest.raises(T106IncompleteError, match="separate Maintainer readiness"):
        _readiness_qualified(None, "a" * 40, 4, binary, sha)
    monkeypatch.setattr(
        "sts_combat_rl.commands.t106_failure_stages.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="a" * 40),
    )
    approval = {
        "task_id": "T106",
        "implementation_head": "a" * 40,
        "full_execution_authorized": True,
        "approval_comment_url": "https://github.com/lsmfttb/STSRL/pull/122#issuecomment-1",
        "worker_count": 4,
        "native_binary": {
            "path": str(binary.resolve()),
            "sha256": sha,
            "source_commit": "5afae22def0c69657b0139bfa21306aebac831af",
        },
        "resource_plan": {
            "supervision": "detached_resource_guard",
            "summed_rss_limit_mib": 16384,
            "mem_available_floor_mib": 8192,
            "sample_interval_s": 1,
            "status_path": str(tmp_path / "job.status.json"),
        },
    }
    approval_path = tmp_path / "readiness.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    _readiness_qualified(approval_path, "a" * 40, 4, binary, sha)
    with pytest.raises(T106IncompleteError, match="native build"):
        _readiness_qualified(approval_path, "a" * 40, 4, binary, "2" * 64)
    approval["native_binary"]["source_commit"] = "0" * 40
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(T106IncompleteError, match="native build"):
        _readiness_qualified(approval_path, "a" * 40, 4, binary, sha)
    report = aggregate([], full=False)
    report["execution"] = {"schema_id": "t106-execution-record-v1", "task_id": "T106"}
    refs = _write_outputs(
        tmp_path, [], report, {"implementation_head": "a" * 40}, "command"
    )
    assert set(refs) == {
        "candidate_stages",
        "aggregate_report",
        "execution_record",
        "retention_manifest",
    }
    manifest = json.loads((tmp_path / "t106-retention-manifest.json").read_text())
    assert manifest["artifact_references"] == {
        k: refs[k] for k in refs if k != "retention_manifest"
    }
    with pytest.raises(T106IncompleteError, match="overwrite"):
        _write_outputs(tmp_path, [], {**report, "execution": {}}, {}, "command")
