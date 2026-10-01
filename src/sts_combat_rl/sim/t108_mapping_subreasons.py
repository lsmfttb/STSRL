"""Strict T108 exact-323 mapping-subreason replay and aggregation helpers."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t103_particle_diagnostic import T103NativeRecordRunner
from sts_combat_rl.sim.t105_native_stage_observability import TRACE_SCHEMA
from sts_combat_rl.sim.t106_failure_stages import validate_t106_trace
from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    FAILURE_SUBREASONS,
    validate_t107_mapping_diagnostic,
)

ROW_SCHEMA = "t108-root-mapping-subreason-rows-v1"
REPORT_SCHEMA = "t108-root-mapping-subreason-report-v1"
MANIFEST_SCHEMA = "t108-root-mapping-subreason-retention-manifest-v1"
T106_ROW_SCHEMA = "t106-structured-failure-stage-rows-v1"
T106_REPORT_SCHEMA = "t106-structured-failure-stage-report-v1"
T106_MANIFEST_SCHEMA = "t106-failure-stage-retention-manifest-v1"
T106_EXECUTION_SCHEMA = "t106-execution-record-v1"
T106_IMPLEMENTATION_HEAD = "1514f8ffd16f12c7d554a484be233d7e9c15e1bf"
T106_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "5afae22def0c69657b0139bfa21306aebac831af",
}
NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "1458522294d967e8985e1fd52cc15d7ebe7f2acd",
}
T106_SHA256 = {
    "rows": "54475603f5072b316a4afc2b4e6ddb88b8ad2db0950c8ef3792347a07bbaae78",
    "report": "871771bcd94b558f7e85034ac95dd1f2b38da7550962bce71560ec9e8b9d015e",
    "execution": "2093eee53ed28de8d6d5941c72fc4a90af4f961add1a1c78903b1d6b107ed4e4",
    "manifest": "27141e5d6167da7c0fe5c62b8c6c673c5a02f5187bd9c8ae866dfd1443998647",
}
T106_ROOT_CLASS = "ROOT_OCCURRENCE_MAPPING_FAILURE"
T106_PUBLIC_CLASS = "PUBLIC_FIDELITY_VALIDATION_FAILURE"
HISTORICAL_T104_ROOT_CLASS = "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS"
SUBREASONS = tuple(sorted(FAILURE_SUBREASONS))
STRATA = ("A", "B", "C")
EXPECTED_SELECTED_BY_STRATUM = {"A": 84, "B": 174, "C": 65}
EXPECTED_CALL_PARAMETERS = {
    "particle_start": 0,
    "particle_count": 2,
    "search_simulations": 400,
    "include_potions": False,
}


class T108IncompleteError(ValueError):
    """An accepted input or frozen replay binding is unavailable."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise T108IncompleteError(f"{label} must be an object")
    return value


def ordered_identity_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """Hash the accepted ordered identity/source binding without exposing it."""

    payload = [
        {
            "selection_identity": row["selection_identity"],
            "source_ordinal": row["source_ordinal"],
            "selection_digest": row["selection_digest"],
        }
        for row in rows
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _diagnostic_safe_metadata(validated: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in validated.items()
        if key not in {"schema_id", "status", "mapping_subreason"}
    }


def _validate_parent_mapping_baseline(row: Mapping[str, Any]) -> None:
    identity = row.get("selection_identity")
    if not isinstance(identity, str) or not identity:
        raise T108IncompleteError("accepted T106 selection identity is missing")
    if (
        row.get("stage_class") != T106_ROOT_CLASS
        or row.get("historical_t104_part_b_class") != HISTORICAL_T104_ROOT_CLASS
        or row.get("replicate_index") != 0
        or row.get("sampler_seed") != derive_t101_sampler_seed(identity, 0)
        or row.get("current_native_identity") != T106_NATIVE_IDENTITY
        or row.get("bridge_outcome") != "exception"
        or row.get("bridge_invocation_status") != "failed"
        or row.get("baseline_contradiction") is not False
        or row.get("telemetry_contract_violation") is not False
        or row.get("classification_source") != "native_structured_telemetry"
    ):
        raise T108IncompleteError("accepted T106 root-mapping row is inconsistent")

    expected = {
        **EXPECTED_CALL_PARAMETERS,
        "sampler_seed": row["sampler_seed"],
    }
    execution = _mapping(row.get("execution"), "T106 row execution evidence")
    if (
        row.get("frozen_expected_bridge_call_parameters") != expected
        or row.get("bridge_call_parameters") != expected
        or execution.get("failure_retry_status") != "no_retry"
    ):
        raise T108IncompleteError("accepted T106 row has changed frozen parameters")

    trace = _mapping(row.get("native_stage_trace"), "T106 stage trace")
    try:
        trace = validate_t106_trace(trace)
    except (ValueError, TypeError, KeyError) as exc:
        raise T108IncompleteError(
            "accepted T106 parent stage trace is invalid"
        ) from exc
    if (
        trace.get("schema_id") != TRACE_SCHEMA
        or trace.get("attempt_status") != "failed_closed"
        or trace.get("first_failed_stage") != "root_occurrence_mapping"
        or trace.get("failure_code") != "root_occurrence_mapping_failed"
        or trace.get("accepted_root_report_returned") is not False
    ):
        raise T108IncompleteError("accepted T106 parent stage baseline is inconsistent")
    particles = trace.get("particles")
    if not isinstance(particles, list) or not particles:
        raise T108IncompleteError("accepted T106 trace has no failed particle")
    first_failed = next(
        (particle for particle in particles if particle.get("first_failed_stage")),
        None,
    )
    if (
        not isinstance(first_failed, Mapping)
        or first_failed.get("particle_index") != 0
        or first_failed.get("first_failed_stage") != "root_occurrence_mapping"
        or first_failed.get("failure_code") != "root_occurrence_mapping_failed"
        or first_failed.get("stages", {}).get("root_occurrence_mapping") != "failed"
    ):
        raise T108IncompleteError("accepted T106 first failing particle is not index 0")


def select_t106_root_mapping_failures(rows: object) -> list[dict[str, Any]]:
    """Filter the accepted T106 343 rows in place order to its exact 323 subset."""

    if not isinstance(rows, list) or len(rows) != 343:
        raise T108IncompleteError(
            "accepted T106 candidate population must contain 343 rows"
        )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_t104_ordinal = -1
    all_classes: Counter[str] = Counter()
    for row_ordinal, row in enumerate(rows):
        if not isinstance(row, dict):
            raise T108IncompleteError("accepted T106 candidate row is malformed")
        identity = row.get("selection_identity")
        source_ordinal = row.get("source_ordinal")
        selection_digest = row.get("selection_digest")
        t104_ordinal = row.get("accepted_t104_row_ordinal")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in seen
            or isinstance(source_ordinal, bool)
            or not isinstance(source_ordinal, int)
            or source_ordinal < 0
            or not isinstance(selection_digest, str)
            or not selection_digest
            or isinstance(t104_ordinal, bool)
            or not isinstance(t104_ordinal, int)
            or t104_ordinal <= previous_t104_ordinal
            or row.get("stratum") not in STRATA
        ):
            raise T108IncompleteError("accepted T106 identity/order binding is invalid")
        seen.add(identity)
        previous_t104_ordinal = t104_ordinal
        stage_class = row.get("stage_class")
        all_classes[stage_class] += 1
        if stage_class == T106_ROOT_CLASS:
            _validate_parent_mapping_baseline(row)
            selected.append(
                {
                    **row,
                    "accepted_t106_row_ordinal": row_ordinal,
                    "accepted_t106_producer": T106_IMPLEMENTATION_HEAD,
                    "accepted_t106_artifact_hashes": dict(T106_SHA256),
                }
            )
        elif stage_class != T106_PUBLIC_CLASS:
            raise T108IncompleteError(
                "accepted T106 rows contain an out-of-scope class"
            )

    by_stratum = Counter(row["stratum"] for row in selected)
    if (
        len(selected) != 323
        or all_classes != {T106_ROOT_CLASS: 323, T106_PUBLIC_CLASS: 20}
        or dict(by_stratum) != EXPECTED_SELECTED_BY_STRATUM
    ):
        raise T108IncompleteError("accepted T106 exact-323 selection/counts disagree")
    return selected


def _parent_trace_without_mapping_fields(value: object) -> Mapping[str, Any]:
    trace = _mapping(value, "native stage trace")
    particles = trace.get("particles")
    if not isinstance(particles, list):
        raise TypeError("native stage trace particle list is invalid")
    sanitized_particles = []
    for particle in particles:
        particle_map = _mapping(particle, "native stage particle")
        sanitized_particles.append(
            {
                key: child
                for key, child in particle_map.items()
                if key != "root_occurrence_mapping_diagnostic"
            }
        )
    return {**trace, "particles": sanitized_particles}


def classify_mapping_replay(
    *,
    accepted: Mapping[str, Any],
    bridge_outcome: str,
    bridge_call_parameters: Mapping[str, Any] | None,
    raw_trace: object,
    trace_error_type: str | None = None,
    exception_type: str | None = None,
    exception_signature_audit_only: str | None = None,
    wall_clock_time_s: float | None = None,
    bridge_wall_clock_time_s: float | None = None,
) -> dict[str, Any]:
    """Classify only the immediately captured, strict structured native field."""

    expected_call = {
        **EXPECTED_CALL_PARAMETERS,
        "sampler_seed": accepted["sampler_seed"],
    }
    if bridge_call_parameters != expected_call:
        raise T108IncompleteError(
            "production bridge call differs from frozen parameters"
        )

    row: dict[str, Any] = {
        "selection_identity": accepted["selection_identity"],
        "stratum": accepted["stratum"],
        "source_ordinal": accepted["source_ordinal"],
        "selection_digest": accepted["selection_digest"],
        "accepted_t106_row_ordinal": accepted["accepted_t106_row_ordinal"],
        "accepted_t106_producer": accepted["accepted_t106_producer"],
        "accepted_t106_artifact_hashes": dict(
            accepted["accepted_t106_artifact_hashes"]
        ),
        "accepted_t106_stage_class": accepted["stage_class"],
        "accepted_t106_failure_code": "root_occurrence_mapping_failed",
        "current_native_identity": dict(NATIVE_IDENTITY),
        "replicate_index": 0,
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "search_controller": "unguided_search_v2",
        "include_potions": False,
        "failure_injection": False,
        "stage_snapshot_binding": "immediately_after_same_production_bridge_call",
        "frozen_expected_bridge_call_parameters": expected_call,
        "bridge_call_parameters": dict(bridge_call_parameters),
        "bridge_outcome": bridge_outcome,
        "exception_type": exception_type if isinstance(exception_type, str) else None,
        "exception_signature_audit_only": (
            exception_signature_audit_only
            if isinstance(exception_signature_audit_only, str)
            else None
        ),
        "parent_stage_schema_id": None,
        "parent_attempt_status": None,
        "parent_first_failed_stage": None,
        "parent_failure_code": None,
        "accepted_root_report_returned": None,
        "first_failing_particle_index": None,
        "mapping_diagnostic_schema_id": None,
        "mapping_diagnostic_status": None,
        "mapping_subreason": None,
        "diagnostic_safe_metadata": None,
        "diagnostic_safe_metadata_role": None,
        "contradictory_mapping_diagnostics": None,
        "contradictory_mapping_diagnostics_role": None,
        "subreason_class": None,
        "classification_source": None,
        "baseline_contradiction": False,
        "parent_stage_contract_violation": False,
        "mapping_telemetry_contract_violation": False,
        "trace_error_type": trace_error_type,
        "wall_clock_time_s": wall_clock_time_s,
        "bridge_wall_clock_time_s": bridge_wall_clock_time_s,
    }

    if raw_trace is None:
        row["parent_stage_contract_violation"] = True
        row["baseline_contradiction"] = bridge_outcome != "exception"
        return row

    try:
        parent_trace = validate_t106_trace(
            _parent_trace_without_mapping_fields(raw_trace)
        )
    except (ValueError, TypeError, KeyError):
        row["parent_stage_contract_violation"] = True
        row["baseline_contradiction"] = bridge_outcome != "exception"
        return row

    row.update(
        parent_stage_schema_id=parent_trace["schema_id"],
        parent_attempt_status=parent_trace["attempt_status"],
        parent_first_failed_stage=parent_trace["first_failed_stage"],
        parent_failure_code=parent_trace["failure_code"],
        accepted_root_report_returned=parent_trace["accepted_root_report_returned"],
    )
    particles = parent_trace["particles"]
    first_failed = next(
        (
            particle
            for particle in particles
            if particle["first_failed_stage"] is not None
        ),
        None,
    )
    if first_failed is not None:
        row["first_failing_particle_index"] = first_failed["particle_index"]
    baseline_reproduced = not (
        bridge_outcome != "exception"
        or parent_trace["attempt_status"] != "failed_closed"
        or parent_trace["first_failed_stage"] != "root_occurrence_mapping"
        or parent_trace["failure_code"] != "root_occurrence_mapping_failed"
        or parent_trace["accepted_root_report_returned"] is not False
        or first_failed is None
        or first_failed["particle_index"] != 0
        or first_failed["first_failed_stage"] != "root_occurrence_mapping"
        or first_failed["failure_code"] != "root_occurrence_mapping_failed"
        or first_failed["stages"]["root_occurrence_mapping"] != "failed"
    )

    raw_particles = _mapping(raw_trace, "native stage trace")["particles"]
    validated_diagnostics: list[tuple[Mapping[str, Any], Mapping[str, Any] | None]] = []
    try:
        for raw_particle, parent_particle in zip(raw_particles, particles, strict=True):
            validated_diagnostic = validate_t107_mapping_diagnostic(
                raw_particle.get("root_occurrence_mapping_diagnostic"),
                mapping_stage_status=parent_particle["stages"][
                    "root_occurrence_mapping"
                ],
            )
            validated_diagnostics.append((parent_particle, validated_diagnostic))
    except (ValueError, TypeError, KeyError):
        row["mapping_telemetry_contract_violation"] = True

    if not baseline_reproduced:
        row["baseline_contradiction"] = True
        if not row["mapping_telemetry_contract_violation"]:
            row["contradictory_mapping_diagnostics"] = [
                {
                    "particle_index": parent_particle["particle_index"],
                    "schema_id": validated["schema_id"],
                    "status": validated["status"],
                    "mapping_subreason": validated["mapping_subreason"],
                    "diagnostic_safe_metadata": _diagnostic_safe_metadata(validated),
                }
                for parent_particle, validated in validated_diagnostics
                if validated is not None
            ]
            row["contradictory_mapping_diagnostics_role"] = (
                "validated_t107_trace_only_not_classification"
            )
        return row
    if row["mapping_telemetry_contract_violation"]:
        return row

    validated = next(
        (
            diagnostic
            for parent_particle, diagnostic in validated_diagnostics
            if parent_particle["particle_index"] == first_failed["particle_index"]
        ),
        None,
    )
    if validated is None or validated.get("status") != "failed":
        row["mapping_telemetry_contract_violation"] = True
        return row
    subreason = validated["mapping_subreason"]
    if subreason not in FAILURE_SUBREASONS:
        row["mapping_telemetry_contract_violation"] = True
        return row
    row.update(
        mapping_diagnostic_schema_id=validated["schema_id"],
        mapping_diagnostic_status=validated["status"],
        mapping_subreason=subreason,
        diagnostic_safe_metadata=_diagnostic_safe_metadata(validated),
        diagnostic_safe_metadata_role="diagnostic_only",
        subreason_class=subreason,
        classification_source="structured_native_mapping_diagnostic",
    )
    return row


class _ImmediateMappingTraceAdapter:
    """Read the combined T105/T107 snapshot before the adapter is reused."""

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
            except Exception as exc:  # noqa: BLE001 - telemetry failure must not mask the bridge
                self._capture["trace_error_type"] = type(exc).__name__[:120]


class T108NativeRecordRunner:
    """Replay one accepted source with a fresh adapter and same-call trace."""

    def __init__(self, **runner_inputs: object) -> None:
        self.inputs = runner_inputs

    def diagnose(
        self, record: Mapping[str, object], accepted: Mapping[str, Any]
    ) -> dict[str, Any]:
        capture: dict[str, Any] = {}
        factory = self.inputs["adapter_factory"]
        runner = T103NativeRecordRunner(
            **{
                **self.inputs,
                "adapter_factory": lambda: _ImmediateMappingTraceAdapter(
                    factory(), capture
                ),
            }
        )
        baseline = runner.diagnose(
            record,
            source_ordinal=accepted["source_ordinal"],
            selection_digest=accepted["selection_digest"],
        )
        if baseline.get("restore_status") != "succeeded":
            raise T108IncompleteError("accepted restore/source binding unavailable")
        if (
            baseline.get("bridge_invocation_status")
            not in {
                "invoked",
                "failed",
                "returned_report",
            }
            or "call_parameters" not in capture
        ):
            raise T108IncompleteError("production bridge invocation was not observed")
        expected_call = {
            **EXPECTED_CALL_PARAMETERS,
            "sampler_seed": accepted["sampler_seed"],
        }
        if capture.get("call_parameters") != expected_call:
            raise T108IncompleteError(
                "production bridge call differs from frozen parameters"
            )
        outcome = capture.get("bridge_outcome")
        if outcome not in {"exception", "returned"}:
            raise T108IncompleteError("production bridge outcome is unavailable")
        return classify_mapping_replay(
            accepted=accepted,
            bridge_outcome=outcome,
            bridge_call_parameters=capture["call_parameters"],
            raw_trace=capture.get("trace"),
            trace_error_type=capture.get("trace_error_type"),
            exception_type=baseline.get("exception_type"),
            exception_signature_audit_only=baseline.get("exception_signature"),
            wall_clock_time_s=baseline.get("wall_clock_time_s"),
            bridge_wall_clock_time_s=capture.get("bridge_wall_clock_time_s"),
        )


def _fraction(count: int, total: int) -> dict[str, int] | None:
    return {"numerator": count, "denominator": total} if total else None


def _subreason_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(
        row["subreason_class"]
        for row in rows
        if row.get("classification_source") == "structured_native_mapping_diagnostic"
    )
    denominator = sum(counts.values())
    return {
        name: {"count": counts[name], "fraction": _fraction(counts[name], denominator)}
        for name in SUBREASONS
    }


def _safe_metadata_cross_tab(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, Any]:
    pairs = [
        (row["subreason_class"], metadata[field])
        for row in rows
        if isinstance((metadata := row.get("diagnostic_safe_metadata")), Mapping)
        and field in metadata
    ]

    def category_counts(values: Sequence[Any]) -> dict[str, Any]:
        counts = Counter(values)
        return {
            str(name): {"count": count, "fraction": _fraction(count, len(values))}
            for name, count in sorted(counts.items(), key=lambda item: str(item[0]))
        }

    by_subreason = {}
    for subreason in SUBREASONS:
        values = [value for label, value in pairs if label == subreason]
        by_subreason[subreason] = {
            "available_count": len(values),
            "categories": category_counts(values),
        }
    return {
        "available_count": len(pairs),
        "by_category": category_counts([value for _, value in pairs]),
        "by_subreason": by_subreason,
    }


def aggregate_t108(
    rows: Sequence[Mapping[str, Any]],
    *,
    full: bool,
    selected_count: int = 323,
    expected_by_stratum: Mapping[str, int] | None = None,
    expected_identities: Sequence[str] | None = None,
    expected_identity_digest: str | None = None,
) -> dict[str, Any]:
    expected_strata = (
        dict(EXPECTED_SELECTED_BY_STRATUM)
        if expected_by_stratum is None
        else dict(expected_by_stratum)
    )
    if set(expected_strata) != set(STRATA) or any(
        isinstance(count, bool) or not isinstance(count, int) or count < 0
        for count in expected_strata.values()
    ):
        raise T108IncompleteError("T108 expected stratum counts are malformed")
    contradictions = [
        row["selection_identity"] for row in rows if row.get("baseline_contradiction")
    ]
    parent_violations = [
        row["selection_identity"]
        for row in rows
        if row.get("parent_stage_contract_violation")
    ]
    mapping_violations = [
        row["selection_identity"]
        for row in rows
        if row.get("mapping_telemetry_contract_violation")
    ]
    classified = [
        row
        for row in rows
        if row.get("classification_source") == "structured_native_mapping_diagnostic"
    ]
    replayed_identities = [row.get("selection_identity") for row in rows]
    identities_unique = all(
        isinstance(identity, str) and identity for identity in replayed_identities
    ) and len(set(replayed_identities)) == len(replayed_identities)
    if expected_identities is None:
        identity_order_matches = identities_unique and len(rows) == selected_count
    else:
        identity_order_matches = replayed_identities == list(expected_identities)
    replayed_identity_digest = None
    try:
        if all(
            isinstance(row.get("selection_identity"), str)
            and isinstance(row.get("source_ordinal"), int)
            and isinstance(row.get("selection_digest"), str)
            for row in rows
        ):
            replayed_identity_digest = ordered_identity_digest(rows)
    except (KeyError, TypeError, ValueError):
        replayed_identity_digest = None
    identity_digest_matches = (
        expected_identity_digest is None
        or replayed_identity_digest == expected_identity_digest
    )
    replayed_by_stratum = Counter(row.get("stratum") for row in rows)
    stratum_coverage_matches = all(
        replayed_by_stratum.get(stratum, 0) == expected_strata[stratum]
        for stratum in STRATA
    ) and all(stratum in STRATA for stratum in replayed_by_stratum)
    terminal = (
        "T106_ROOT_MAPPING_BASELINE_NOT_REPRODUCED"
        if contradictions
        else "NATIVE_MAPPING_OBSERVABILITY_CONTRACT_NOT_REPRODUCED"
        if mapping_violations
        else "ROOT_OCCURRENCE_MAPPING_SUBREASON_CENSUS_ESTABLISHED"
        if full
        and len(rows) == selected_count == 323
        and expected_strata == EXPECTED_SELECTED_BY_STRATUM
        and len(classified) == 323
        and not parent_violations
        and identity_order_matches
        and identity_digest_matches
        and stratum_coverage_matches
        else "INCOMPLETE"
    )

    strata = {
        stratum: [row for row in classified if row.get("stratum") == stratum]
        for stratum in STRATA
    }
    parent_stage_counts = Counter(row.get("parent_first_failed_stage") for row in rows)
    parent_code_counts = Counter(row.get("parent_failure_code") for row in rows)
    diagnostic_status_counts = Counter(
        row.get("mapping_diagnostic_status") for row in classified
    )
    first_particle_counts = Counter(
        row.get("first_failing_particle_index")
        for row in rows
        if row.get("first_failing_particle_index") is not None
    )

    success = terminal == "ROOT_OCCURRENCE_MAPPING_SUBREASON_CENSUS_ESTABLISHED"
    if (
        success
        and sum(entry["count"] for entry in _subreason_counts(classified).values())
        != 323
    ):
        raise T108IncompleteError("T108 seven-class census does not sum to 323")
    return {
        "schema_id": REPORT_SCHEMA,
        "task_id": "T108",
        "terminal_classification": terminal,
        "selected_count": selected_count,
        "replayed_count": len(rows),
        "valid_mapping_diagnostic_count": len(classified),
        "selected_identity_order_digest": expected_identity_digest,
        "replayed_identity_order_digest": replayed_identity_digest,
        "identity_order_matches": identity_order_matches,
        "identity_digest_matches": identity_digest_matches,
        "replayed_by_stratum": {
            str(key): count
            for key, count in sorted(
                replayed_by_stratum.items(), key=lambda item: str(item[0])
            )
        },
        "stratum_coverage_matches": stratum_coverage_matches,
        "baseline_contradiction_count": len(contradictions),
        "baseline_contradiction_identities": contradictions,
        "parent_stage_contract_violation_count": len(parent_violations),
        "parent_stage_contract_violation_identities": parent_violations,
        "mapping_telemetry_contract_violation_count": len(mapping_violations),
        "mapping_telemetry_contract_violation_identities": mapping_violations,
        "failure_subreasons": _subreason_counts(classified),
        "by_stratum": {
            stratum: {
                "selected_count": expected_strata[stratum],
                "classified_count": len(strata[stratum]),
                "subreasons": _subreason_counts(strata[stratum]),
            }
            for stratum in STRATA
        },
        "parent_first_failed_stage_counts": {
            str(key): count
            for key, count in sorted(
                parent_stage_counts.items(), key=lambda item: str(item[0])
            )
        },
        "parent_failure_code_counts": {
            str(key): count
            for key, count in sorted(
                parent_code_counts.items(), key=lambda item: str(item[0])
            )
        },
        "first_failing_particle_index_counts": {
            str(key): {"count": count, "fraction": _fraction(count, len(rows))}
            for key, count in sorted(
                first_particle_counts.items(), key=lambda item: str(item[0])
            )
        },
        "diagnostic_status_counts": dict(
            sorted((str(key), count) for key, count in diagnostic_status_counts.items())
        ),
        "diagnostic_status_subreason_consistency_count": len(classified),
        "diagnostic_status_subreason_consistency": {
            "failed_status_with_closed_failure_subreason": len(classified),
            "unavailable_or_invalid": len(mapping_violations),
        },
        "diagnostic_status_by_subreason": {
            status: {
                subreason: sum(
                    row.get("mapping_diagnostic_status") == status
                    and row.get("mapping_subreason") == subreason
                    for row in classified
                )
                for subreason in SUBREASONS
            }
            for status in sorted(diagnostic_status_counts)
        },
        "accepted_root_report_returned_counts": {
            str(key): count
            for key, count in sorted(
                Counter(
                    row.get("accepted_root_report_returned") for row in rows
                ).items(),
                key=lambda item: str(item[0]),
            )
        },
        "safe_diagnostic_cross_tabs": {
            field: _safe_metadata_cross_tab(classified, field)
            for field in (
                "public_action_kind",
                "direct_match_multiplicity",
                "representative_match_multiplicity",
            )
        },
        "all_failure_subreasons_sum_to_323": success,
    }
