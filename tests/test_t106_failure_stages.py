from __future__ import annotations

import json
from copy import deepcopy

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
    row = runner.diagnose(
        {},
        {
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
        },
    )
    assert [event[0] for event in events] == ["bridge", "snapshot"]
    assert row["stage_class"] == "ROOT_OCCURRENCE_MAPPING_FAILURE"
    assert row["classification_source"] == "native_structured_telemetry"
    assert row["exception_signature_audit_only"] == "audit"

    class AcceptedNativeAdapter(Adapter):
        def last_particle_search_stage_diagnostics(self) -> dict:
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
            events.append(("snapshot", None))
            return trace

    accepted = T106NativeRecordRunner(adapter_factory=AcceptedNativeAdapter).diagnose(
        {},
        {
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
        },
    )
    assert accepted["baseline_contradiction"] is True
    assert accepted["stage_class"] is None


def test_retention_hashes_and_full_readiness_gate(tmp_path) -> None:
    with pytest.raises(T106IncompleteError, match="separate Maintainer readiness"):
        _readiness_qualified(None, "a" * 40, 4)
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
