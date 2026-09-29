"""Telemetry-only census of T104 Part-B bridge failures."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t103_particle_diagnostic import T103NativeRecordRunner
from sts_combat_rl.sim.t105_native_stage_observability import (
    STAGES_IN_EXECUTION_ORDER,
    validate_t105_stage_trace,
)

ROW_SCHEMA = "t106-structured-failure-stage-rows-v1"
REPORT_SCHEMA = "t106-structured-failure-stage-report-v1"
MANIFEST_SCHEMA = "t106-failure-stage-retention-manifest-v1"
NATIVE_COMMIT = "5afae22def0c69657b0139bfa21306aebac831af"
NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": NATIVE_COMMIT,
}
HISTORICAL_T104_CLASSES = (
    "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS",
    "STANDALONE_SAMPLER_FAILURE",
)
STAGE_CLASSES = (
    "REQUEST_OR_PREFLIGHT_FAILURE",
    *(f"{stage.upper()}_FAILURE" for stage in STAGES_IN_EXECUTION_ORDER),
)


class T106IncompleteError(ValueError):
    """An accepted input, replay binding, or census is unavailable."""


def select_t104_part_b(rows: object) -> list[dict[str, Any]]:
    """Qualify the exact ordered historical subset before any native replay."""

    if not isinstance(rows, list) or len(rows) != 413:
        raise T106IncompleteError("T104 candidate population must contain 413 rows")
    selected = []
    identities = set()
    for row in rows:
        if not isinstance(row, dict):
            raise T106IncompleteError("T104 row is malformed")
        cls = row.get("part_b_class")
        if cls not in HISTORICAL_T104_CLASSES:
            if row.get("diagnostic_class") != "PUBLIC_PROJECTION_PARITY_FAILURE":
                raise T106IncompleteError("unexpected T104 Part-A row")
            continue
        identity = row.get("selection_identity")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in identities
            or row.get("diagnostic_class") != "OPAQUE_BRIDGE_FAILURE"
            or row.get("baseline_reproduced") is not True
            or row.get("full_bridge_failed") is not True
            or row.get("bridge_invocation_status") != "failed"
            or row.get("native_observability_required") is not True
            or row.get("pre_bridge_passed") is not True
            or row.get("replicate_index") != 0
            or row.get("sampler_seed") != derive_t101_sampler_seed(identity, 0)
            or row.get("particle_count") != 2
            or row.get("search_simulations") != 400
            or row.get("include_potions") is not False
            or row.get("current_native_identity", {}).get("commit")
            != "97f59b620efe5ee1571f8da298c99d1e21c1149b"
        ):
            raise T106IncompleteError(
                "T104 Part-B identity or frozen parameters differ"
            )
        identities.add(identity)
        selected.append(row)
    by_class = Counter(r["part_b_class"] for r in selected)
    by_stratum = Counter(r.get("stratum") for r in selected)
    crossed = Counter((r["part_b_class"], r["stratum"]) for r in selected)
    if (
        len(selected) != 343
        or by_class != dict(zip(HISTORICAL_T104_CLASSES, (323, 20), strict=True))
        or by_stratum != {"A": 89, "B": 189, "C": 65}
        or crossed
        != {
            (HISTORICAL_T104_CLASSES[0], "A"): 84,
            (HISTORICAL_T104_CLASSES[0], "B"): 174,
            (HISTORICAL_T104_CLASSES[0], "C"): 65,
            (HISTORICAL_T104_CLASSES[1], "A"): 5,
            (HISTORICAL_T104_CLASSES[1], "B"): 15,
        }
    ):
        raise T106IncompleteError("T104 Part-B counts disagree with accepted census")
    return selected


def classify_trace(value: object) -> tuple[str, Mapping[str, Any]]:
    trace = validate_t105_stage_trace(value, expected_status="failed_closed")
    stage = trace["first_failed_stage"]
    cls = (
        "REQUEST_OR_PREFLIGHT_FAILURE" if stage is None else f"{stage.upper()}_FAILURE"
    )
    if cls not in STAGE_CLASSES:
        raise ValueError("T105 first failed stage is not in the closed vocabulary")
    return cls, trace


class _TraceAdapter:
    """Capture the native snapshot on the same simulator immediately after call."""

    def __init__(self, adapter: object, capture: dict[str, Any]) -> None:
        self._adapter = adapter
        self._capture = capture

    def __getattr__(self, name: str) -> object:
        return getattr(self._adapter, name)

    def sample_hidden_future_particles_search(
        self, *args: object, **kwargs: object
    ) -> object:
        self._capture["call_parameters"] = dict(kwargs)
        bridge = self._adapter.sample_hidden_future_particles_search
        started = time.perf_counter()
        try:
            result = bridge(*args, **kwargs)
        except Exception:
            self._capture["bridge_outcome"] = "exception"
            raise
        else:
            self._capture["bridge_outcome"] = "returned"
            return result
        finally:
            self._capture["bridge_wall_clock_time_s"] = time.perf_counter() - started
            try:
                self._capture["trace"] = (
                    self._adapter.last_particle_search_stage_diagnostics()
                )
            except Exception as exc:  # noqa: BLE001 - trace failure must not mask bridge outcome
                self._capture["trace_error_type"] = type(exc).__name__[:120]


class T106NativeRecordRunner:
    def __init__(self, **runner_inputs: object) -> None:
        self.inputs = runner_inputs

    def diagnose(
        self, record: Mapping[str, object], accepted: Mapping[str, object]
    ) -> dict[str, Any]:
        capture: dict[str, Any] = {}
        factory = self.inputs["adapter_factory"]
        runner = T103NativeRecordRunner(
            **{
                **self.inputs,
                "adapter_factory": lambda: _TraceAdapter(factory(), capture),
            }
        )
        baseline = runner.diagnose(
            record,
            source_ordinal=accepted["source_ordinal"],
            selection_digest=accepted["selection_digest"],
        )
        expected_call = {
            "sampler_seed": accepted["sampler_seed"],
            "particle_start": 0,
            "particle_count": 2,
            "search_simulations": 400,
            "include_potions": False,
        }
        if capture.get("call_parameters") != expected_call:
            raise T106IncompleteError(
                "frozen bridge invocation was not reached exactly"
            )
        outcome = capture.get("bridge_outcome")
        contradiction = (
            outcome != "exception"
            or baseline.get("bridge_invocation_status") != "failed"
        )
        trace = capture.get("trace")
        violation = False
        stage_class = None
        if trace is not None:
            try:
                validated = validate_t105_stage_trace(trace)
                if validated["attempt_status"] == "accepted":
                    contradiction = True
                if contradiction:
                    if (
                        outcome == "returned"
                        and validated["attempt_status"] != "accepted"
                    ):
                        violation = True
                else:
                    stage_class, validated = classify_trace(trace)
            except (ValueError, TypeError, KeyError):
                violation = True
                validated = None
        else:
            violation = True
            validated = None
        return {
            "selection_identity": accepted["selection_identity"],
            "stratum": accepted["stratum"],
            "source_ordinal": accepted["source_ordinal"],
            "selection_digest": accepted["selection_digest"],
            "historical_t104_part_b_class": accepted["part_b_class"],
            "accepted_t104_producer": "90cbe6c5020f2fb360503e7731c9a892afc6447a",
            "accepted_t104_row_ordinal": accepted["t104_row_ordinal"],
            "accepted_t104_rows_sha256": "3232719325d790dcc84f7e91f907d12b56da37c7557edc8848a5f38fe530dd41",
            "historical_t104_native_identity": accepted["current_native_identity"],
            "current_native_identity": NATIVE_IDENTITY,
            "replicate_index": 0,
            "sampler_seed": accepted["sampler_seed"],
            "bridge_call_parameters": expected_call,
            "bridge_outcome": outcome,
            "bridge_invocation_status": baseline.get("bridge_invocation_status"),
            "baseline_contradiction": contradiction,
            "telemetry_contract_violation": violation,
            "telemetry_error_type": capture.get("trace_error_type"),
            "native_stage_trace": validated,
            "stage_class": stage_class,
            "classification_source": "native_structured_telemetry"
            if stage_class
            else None,
            "exception_type": baseline.get("exception_type"),
            "exception_signature_audit_only": baseline.get("exception_signature"),
            "wall_clock_time_s": baseline["wall_clock_time_s"],
            "bridge_wall_clock_time_s": capture.get("bridge_wall_clock_time_s"),
        }


def aggregate(rows: Sequence[Mapping[str, Any]], *, full: bool) -> dict[str, Any]:
    contradictions = [
        r["selection_identity"] for r in rows if r["baseline_contradiction"]
    ]
    violations = [
        r["selection_identity"] for r in rows if r["telemetry_contract_violation"]
    ]
    good = [
        r
        for r in rows
        if not r["baseline_contradiction"] and not r["telemetry_contract_violation"]
    ]
    terminal = (
        "T104_PART_B_BASELINE_NOT_REPRODUCED"
        if contradictions
        else "NATIVE_OBSERVABILITY_CONTRACT_NOT_REPRODUCED"
        if violations
        else "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED"
        if full and len(rows) == 343 and len(good) == 343
        else "INCOMPLETE"
    )

    def counts(
        key: str, domain: Sequence[str], subset: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        n = len(subset)
        count = Counter(r[key] for r in subset)
        return {
            name: {"count": count[name], "fraction": count[name] / n if n else 0.0}
            for name in domain
        }

    by_stratum = {
        s: counts("stage_class", STAGE_CLASSES, [r for r in good if r["stratum"] == s])
        for s in ("A", "B", "C")
    }
    by_history = {
        s: counts(
            "stage_class",
            STAGE_CLASSES,
            [r for r in good if r["historical_t104_part_b_class"] == s],
        )
        for s in HISTORICAL_T104_CLASSES
    }
    codes = sorted({r["native_stage_trace"]["failure_code"] for r in good})
    stage_code = {}
    for cls in STAGE_CLASSES:
        class_total = sum(r["stage_class"] == cls for r in good)
        stage_code[cls] = {}
        for code in codes:
            count = sum(
                r["stage_class"] == cls
                and r["native_stage_trace"]["failure_code"] == code
                for r in good
            )
            stage_code[cls][code] = {
                "count": count,
                "fraction_of_valid_replays": count / len(good) if good else 0.0,
                "fraction_within_stage_class": count / class_total
                if class_total
                else 0.0,
            }
    first_indices: Counter[int] = Counter()
    signatures: Counter[tuple[str, ...]] = Counter()
    for row in good:
        trace = row["native_stage_trace"]
        for particle in trace["particles"]:
            signatures[
                tuple(particle["stages"][stage] for stage in STAGES_IN_EXECUTION_ORDER)
            ] += 1
        for particle in trace["particles"]:
            if (
                particle["first_failed_stage"] is not None
                and particle["particle_index"] is not None
            ):
                first_indices[particle["particle_index"]] += 1
                break
    if (
        terminal == "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED"
        and sum(x["count"] for x in counts("stage_class", STAGE_CLASSES, good).values())
        != 343
    ):
        raise T106IncompleteError("stage census does not sum to 343")
    return {
        "schema_id": REPORT_SCHEMA,
        "task_id": "T106",
        "terminal_classification": terminal,
        "selected_count": 343,
        "replayed_count": len(rows),
        "replayed_failures_with_valid_telemetry": len(good),
        "baseline_contradiction_count": len(contradictions),
        "baseline_contradiction_identities": contradictions,
        "telemetry_contract_violation_count": len(violations),
        "telemetry_contract_violation_identities": violations,
        "stage_classes": counts("stage_class", STAGE_CLASSES, good),
        "by_stratum": by_stratum,
        "by_historical_t104_class": by_history,
        "stage_class_by_failure_code": stage_code,
        "first_failing_particle_index": {
            str(index): {
                "count": count,
                "fraction_of_valid_replays": count / len(good) if good else 0.0,
            }
            for index, count in sorted(first_indices.items())
        },
        "first_failing_particle_index_unavailable_count": len(good)
        - sum(first_indices.values()),
        "stage_status_transition_signatures": [
            {
                "statuses": dict(
                    zip(STAGES_IN_EXECUTION_ORDER, signature, strict=True)
                ),
                "count": count,
                "fraction_of_particle_rows": count / sum(signatures.values()),
            }
            for signature, count in sorted(signatures.items())
        ],
    }
