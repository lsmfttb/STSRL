"""Observable support-boundary diagnostics for the frozen T101 cohort.

This module records only boundary facts already observable in STSRL or in the
sanitized T099 bridge report. It does not implement simulator mechanics or
infer causes from native exception prose.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sts_combat_rl.commands.t085_native_execution import (
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SEARCH_SIMULATIONS,
    T101_SEED_ALGORITHM,
    derive_t101_sampler_seed,
    validate_t101_bridge_report,
)

T103_DIAGNOSTIC_SCHEMA_ID = "t103-particle-support-diagnostics-v1"
T103_REPORT_SCHEMA_ID = "t103-particle-support-report-v1"
T103_RETENTION_SCHEMA_ID = "t103-diagnostic-retention-manifest-v1"
T103_T101_RETENTION_SHA256 = (
    "922ef003d2fa15dea57f59c71fa99bfb6f5a418d48026b04ed3019d7e6cf4f97"
)

T103_CLASSES = (
    "RESTORE_OR_SOURCE_BINDING_FAILURE",
    "PUBLIC_PROJECTION_PARITY_FAILURE",
    "ORDERED_LEGAL_ACTION_PARITY_FAILURE",
    "BRIDGE_PRECONDITION_OR_SAMPLER_FAILURE",
    "ROOT_OCCURRENCE_MAPPING_INCOMPLETE",
    "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS",
    "ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS",
    "SEARCH_EXECUTION_FAILURE",
    "NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES",
    "OPAQUE_BRIDGE_FAILURE",
    "ADMITTED",
)
T103_MAPPING_CLASSES = frozenset(
    {
        "ROOT_OCCURRENCE_MAPPING_INCOMPLETE",
        "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS",
        "ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS",
    }
)
T103_MAPPING_ERROR_CODES = {
    "incomplete": "ROOT_OCCURRENCE_MAPPING_INCOMPLETE",
    "ambiguous": "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS",
    "incomplete_or_ambiguous": "ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS",
}


class T103DiagnosticError(ValueError):
    """Required T103 evidence is missing or internally inconsistent."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def exception_signature(exc: BaseException) -> dict[str, str]:
    """Retain an exact, bounded audit signature without retaining exception text."""

    exception_type = type(exc).__name__[:120]
    normalized = " ".join(str(exc).split())
    return {
        "exception_type": exception_type,
        "exception_signature": hashlib.sha256(
            normalized.encode("utf-8", errors="replace")
        ).hexdigest(),
    }


def classify_t103_observation(
    evidence: Mapping[str, object],
) -> tuple[str, str | None]:
    """Choose the earliest class supported by explicit structured evidence.

    Exception prose is intentionally ignored. Callers may provide stable
    structured stage and error-code fields from an accepted API boundary.
    """

    if evidence.get("restore_binding_failed") is True:
        return "RESTORE_OR_SOURCE_BINDING_FAILURE", "restore_or_source_binding_failed"
    if evidence.get("public_projection_parity") is False:
        return "PUBLIC_PROJECTION_PARITY_FAILURE", "public_projection_mismatch"
    if evidence.get("ordered_legal_action_parity") is False:
        return "ORDERED_LEGAL_ACTION_PARITY_FAILURE", "ordered_action_mismatch"

    if evidence.get("bridge_precondition_or_sampler_failed") is True:
        return (
            "BRIDGE_PRECONDITION_OR_SAMPLER_FAILURE",
            "bridge_precondition_or_sampler_failed",
        )

    mapping_error = evidence.get("mapping_error_code")
    if isinstance(mapping_error, str) and mapping_error in T103_MAPPING_ERROR_CODES:
        return T103_MAPPING_ERROR_CODES[str(mapping_error)], f"mapping_{mapping_error}"
    mapping_complete = evidence.get("mapping_complete")
    mapping_ambiguous = evidence.get("mapping_ambiguous")
    if mapping_ambiguous is True:
        return "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS", "mapping_ambiguous"
    if mapping_complete is False and mapping_ambiguous is False:
        return "ROOT_OCCURRENCE_MAPPING_INCOMPLETE", "mapping_incomplete"

    if (
        evidence.get("search_execution_reached") is True
        and evidence.get("search_execution_failed") is True
        and mapping_complete is True
        and mapping_ambiguous is False
    ):
        return "SEARCH_EXECUTION_FAILURE", "search_execution_failed"

    if (
        evidence.get("search_execution_reached") is True
        and evidence.get("required_root_values_valid") is False
        and mapping_complete is True
        and mapping_ambiguous is False
    ):
        return (
            "NONFINITE_OR_INVALID_REQUIRED_ROOT_VALUES",
            "required_root_values_invalid",
        )

    if evidence.get("complete_admission") is True:
        return "ADMITTED", None
    return "OPAQUE_BRIDGE_FAILURE", "observable_boundary_not_localized"


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _bridge_observations(
    report: object,
) -> tuple[dict[str, object], dict[str, str] | None]:
    """Extract only explicit parity/mapping/Search facts from a raw report."""

    if not isinstance(report, Mapping):
        return {}, None
    observations: dict[str, object] = {}
    particles = report.get("particles")
    if not isinstance(particles, list):
        return observations, None

    for particle in particles:
        if not isinstance(particle, Mapping):
            continue
        if particle.get("public_projection_equal") is False:
            observations["public_projection_parity"] = False
            break
        anchor_projection = report.get("anchor_public_information_projection")
        particle_projection = particle.get("public_information_projection")
        if (
            isinstance(anchor_projection, Mapping)
            and isinstance(particle_projection, Mapping)
            and dict(anchor_projection) != dict(particle_projection)
        ):
            observations["public_projection_parity"] = False
            break

    if "public_projection_parity" not in observations:
        anchor_actions = report.get("anchor_ordered_public_legal_actions")
        anchor_projection = report.get("anchor_public_information_projection")
        projected_actions = (
            anchor_projection.get("ordered_public_legal_actions")
            if isinstance(anchor_projection, Mapping)
            else None
        )
        if (
            isinstance(anchor_actions, list)
            and isinstance(projected_actions, list)
            and anchor_actions != projected_actions
        ):
            observations["ordered_legal_action_parity"] = False
        for particle in particles:
            if observations.get("ordered_legal_action_parity") is False:
                break
            if not isinstance(particle, Mapping):
                continue
            if particle.get("ordered_public_legal_actions_equal") is False:
                observations["ordered_legal_action_parity"] = False
                break
            particle_actions = particle.get("ordered_public_legal_actions")
            if (
                isinstance(anchor_actions, list)
                and isinstance(particle_actions, list)
                and anchor_actions != particle_actions
            ):
                observations["ordered_legal_action_parity"] = False
                break

    mapping_failed = False
    mapping_observations = 0
    mapping_incomplete = False
    mapping_ambiguous = False
    mapping_values_valid = True
    search_reached = False
    root_values_valid = True
    for particle in particles:
        if not isinstance(particle, Mapping):
            continue
        complete = particle.get("root_action_mapping_complete")
        ambiguous = particle.get("root_action_mapping_ambiguous")
        if isinstance(complete, bool) and isinstance(ambiguous, bool):
            mapping_observations += 1
        else:
            mapping_values_valid = False
        if complete is False or ambiguous is True:
            mapping_failed = True
        mapping_incomplete = mapping_incomplete or complete is False
        mapping_ambiguous = mapping_ambiguous or ambiguous is True

        root = particle.get("root_evaluation")
        if isinstance(root, Mapping):
            search_reached = True
            root_rows = particle.get("root_rows")
            if not isinstance(root_rows, list) or not root_rows:
                root_values_valid = False
                continue
            for row in root_rows:
                if not isinstance(row, Mapping):
                    root_values_valid = False
                    continue
                visits = row.get("visits")
                if (
                    not isinstance(visits, int)
                    or isinstance(visits, bool)
                    or visits < 0
                    or not _is_finite_number(row.get("evaluation_sum"))
                    or not _is_finite_number(row.get("mean_value"))
                ):
                    root_values_valid = False

    if mapping_failed:
        observations["occurrence_mapping_reached"] = True
    if (
        mapping_observations > 0
        and mapping_observations == len(particles)
        and mapping_values_valid
    ):
        observations["mapping_complete"] = (
            not mapping_incomplete and not mapping_ambiguous
        )
        observations["mapping_ambiguous"] = mapping_ambiguous
    if search_reached:
        observations["search_execution_reached"] = True
        observations["required_root_values_valid"] = root_values_valid

    raw_config = {
        "particle_start": report.get("particle_start"),
        "particle_count": report.get("particle_count"),
        "search_simulations": report.get("search_simulations"),
        "include_potions": report.get("include_potions"),
        "sampler_seed_input": report.get("sampler_seed_input"),
    }
    if any(key not in report for key in raw_config):
        return observations, None
    return observations, {key: str(value) for key, value in raw_config.items()}


def _report_configuration_is_frozen(
    observed: Mapping[str, str], *, sampler_seed: int
) -> bool:
    return observed == {
        "particle_start": "0",
        "particle_count": "2",
        "search_simulations": str(T101_SEARCH_SIMULATIONS),
        "include_potions": "False",
        "sampler_seed_input": str(sampler_seed),
    }


def _candidate_base(
    record: Mapping[str, object],
    *,
    source_ordinal: int,
    selection_digest: str,
    sampler_seed: int,
    historical_bindings: Mapping[str, object],
    native_identity: Mapping[str, object],
) -> dict[str, object]:
    identity = record.get("selection_identity")
    stratum = record.get("cohort", record.get("stratum"))
    if not isinstance(identity, str) or not identity or stratum not in {"A", "B", "C"}:
        raise T103DiagnosticError("source record identity or stratum is malformed")
    return {
        "selection_identity": identity,
        "stratum": stratum,
        "source_ordinal": source_ordinal,
        "selection_digest": selection_digest,
        "historical_source_bindings": dict(historical_bindings),
        "current_native_identity": dict(native_identity),
        "replicate_index": 0,
        "sampler_seed": sampler_seed,
        "particle_count": 2,
        "search_simulations": T101_SEARCH_SIMULATIONS,
        "include_potions": False,
        "restore_method": None,
        "restore_status": "not_reached",
        "public_projection_parity_status": "not_reached",
        "ordered_legal_action_parity_status": "not_reached",
        "bridge_invocation_status": "not_reached",
        # An opaque bridge failure does not establish which native stages ran.
        # Use not_reached only after direct evidence of an earlier short circuit.
        "occurrence_mapping_status": "unknown",
        "search_execution_status": "unknown",
        "valid_finite_root_report_status": "unknown",
        "diagnostic_class": "OPAQUE_BRIDGE_FAILURE",
        "subreason_code": "observable_boundary_not_localized",
        "exception_type": None,
        "exception_signature": None,
        "wall_clock_time_s": 0.0,
        "admitted": False,
    }


class T103NativeRecordRunner:
    """Restore one accepted source and preserve its first observable failure."""

    def __init__(
        self,
        *,
        adapter_factory: object,
        selected_records: Mapping[str, object],
        canonical_records_by_stratum: Mapping[str, Mapping[str, object]],
        native_identity: Mapping[str, object],
        historical_bindings: Mapping[str, object],
    ) -> None:
        if not callable(adapter_factory) or not selected_records:
            raise T103DiagnosticError("T103 native runner inputs are unavailable")
        self._adapter_factory = adapter_factory
        # Keep references to the one admitted pool. Do not duplicate its large
        # canonical maps when executing concurrent candidate calls.
        self._selected_records = selected_records
        self._canonical_records_by_stratum = canonical_records_by_stratum
        self._native_identity = dict(native_identity)
        self._historical_bindings = dict(historical_bindings)

    def diagnose(
        self,
        record: Mapping[str, object],
        *,
        source_ordinal: int,
        selection_digest: str,
    ) -> dict[str, object]:
        identity = record.get("selection_identity")
        stratum = record.get("cohort", record.get("stratum"))
        if not isinstance(identity, str) or not identity:
            raise T103DiagnosticError("candidate selection identity is missing")
        seed = derive_t101_sampler_seed(identity, 0)
        row = _candidate_base(
            record,
            source_ordinal=source_ordinal,
            selection_digest=selection_digest,
            sampler_seed=seed,
            historical_bindings=self._historical_bindings,
            native_identity=self._native_identity,
        )
        started = time.perf_counter()
        evidence: dict[str, object] = {}
        exc: BaseException | None = None
        try:
            selected = self._selected_records.get(identity)
            canonical_map = self._canonical_records_by_stratum.get(str(stratum))
            if (
                selected is None
                or canonical_map is None
                or identity not in canonical_map
            ):
                evidence["restore_binding_failed"] = True
                evidence["restore_failure_kind"] = "accepted_source_binding_unavailable"
                raise _T103ObservedBoundary("restore/source binding unavailable")

            adapter = self._adapter_factory()
            try:
                restored, method = restore_t085_canonical_record(
                    adapter,
                    selected,
                    canonical_map,  # type: ignore[arg-type]
                )
            except Exception as restore_exc:
                evidence["restore_binding_failed"] = True
                evidence["restore_failure_kind"] = "current_native_restore_failed"
                raise _T103ObservedBoundary(
                    "current-native restore failed"
                ) from restore_exc
            row["restore_method"] = method
            row["restore_status"] = "succeeded"

            canonical = canonical_map[identity]
            expected = getattr(canonical, "public_run_context", None)
            try:
                actions = list(
                    adapter.legal_actions(restored)  # type: ignore[attr-defined]
                )
                projection = read_native_public_projection(adapter, restored)
            except Exception as projection_exc:
                exc = projection_exc
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary(
                    "public projection observation failed"
                ) from projection_exc
            if not isinstance(expected, Mapping):
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary("accepted public context is unavailable")
            history = expected.get("history", [])
            if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary("accepted public history is malformed")
            try:
                projection_context = build_public_run_context(
                    restored.raw,
                    actions,
                    projection=projection,
                    history=history,
                    include_candidates=False,
                )
            except Exception as projection_exc:
                exc = projection_exc
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary(
                    "public projection observation failed"
                ) from projection_exc

            expected_without_candidates = {
                key: value
                for key, value in expected.items()
                if key not in {"candidate_actions", "missing_fields"}
            }
            actual_without_candidates = {
                key: value
                for key, value in projection_context.items()
                if key not in {"candidate_actions", "missing_fields"}
            }
            if actual_without_candidates != expected_without_candidates:
                row["public_projection_parity_status"] = "failed"
                evidence["public_projection_parity"] = False
                raise _T103ObservedBoundary("restored public projection differs")
            row["public_projection_parity_status"] = "matched"
            evidence["public_projection_parity"] = True

            try:
                action_context = build_public_run_context(
                    restored.raw,
                    actions,
                    projection=None,
                    history=history,
                )
            except Exception as action_exc:
                exc = action_exc
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary(
                    "legal action observation failed"
                ) from action_exc

            expected_actions = expected.get("candidate_actions")
            actual_actions = action_context.get("candidate_actions")
            if actual_actions != expected_actions:
                row["ordered_legal_action_parity_status"] = "failed"
                evidence["ordered_legal_action_parity"] = False
                raise _T103ObservedBoundary("ordered public legal actions differ")
            row["ordered_legal_action_parity_status"] = "matched"
            evidence["ordered_legal_action_parity"] = True

            bridge = getattr(adapter, "sample_hidden_future_particles_search", None)
            if not callable(bridge):
                row["bridge_invocation_status"] = "failed_precondition"
                evidence["bridge_precondition_or_sampler_failed"] = True
                raise _T103ObservedBoundary("T099 bridge API is unavailable")
            row["bridge_invocation_status"] = "invoked"
            raw_report = bridge(
                restored,
                sampler_seed=seed,
                particle_start=0,
                particle_count=2,
                search_simulations=T101_SEARCH_SIMULATIONS,
                include_potions=False,
            )
            report_evidence, report_config = _bridge_observations(raw_report)
            evidence.update(report_evidence)
            anchor_projection = (
                raw_report.get("anchor_public_information_projection")
                if isinstance(raw_report, Mapping)
                else None
            )
            canonical_projection = getattr(projection, "canonical_payload", None)
            if isinstance(anchor_projection, Mapping) and isinstance(
                canonical_projection, str
            ):
                try:
                    current_projection = json.loads(canonical_projection)
                except json.JSONDecodeError:
                    evidence["observation_failed"] = True
                else:
                    if current_projection != dict(anchor_projection):
                        evidence["public_projection_parity"] = False
            if report_config is not None and not _report_configuration_is_frozen(
                report_config, sampler_seed=seed
            ):
                evidence["bridge_precondition_or_sampler_failed"] = True
            row["bridge_invocation_status"] = "returned_report"
            if evidence.get("public_projection_parity") is False:
                row["public_projection_parity_status"] = "failed"
            elif evidence.get("public_projection_parity") is True:
                row["public_projection_parity_status"] = "matched"
            if report_evidence.get("ordered_legal_action_parity") is False:
                row["ordered_legal_action_parity_status"] = "failed"
            elif row["ordered_legal_action_parity_status"] == "not_reached":
                row["ordered_legal_action_parity_status"] = "matched"

            if report_evidence.get("mapping_ambiguous") is True:
                row["occurrence_mapping_status"] = "ambiguous"
            elif report_evidence.get("mapping_complete") is False:
                row["occurrence_mapping_status"] = "incomplete"
            elif report_evidence.get("mapping_complete") is True:
                row["occurrence_mapping_status"] = "complete"
            elif report_evidence.get("mapping_ambiguous") is True:
                row["occurrence_mapping_status"] = "ambiguous"

            if report_evidence.get("search_execution_reached") is True:
                row["search_execution_status"] = "reached"
            elif row["occurrence_mapping_status"] in {"incomplete", "ambiguous"}:
                row["search_execution_status"] = "not_reached"
            if report_evidence.get("required_root_values_valid") is False:
                row["valid_finite_root_report_status"] = "failed"

            try:
                validated = validate_t101_bridge_report(raw_report, particle_count=2)
            except Exception as validation_exc:
                exc = validation_exc
                raise _T103ObservedBoundary(
                    "frozen bridge validation failed"
                ) from validation_exc
            if not isinstance(validated, Mapping):
                evidence["observation_failed"] = True
                raise _T103ObservedBoundary("validated bridge report is malformed")
            if evidence.get("required_root_values_valid") is not False:
                row["valid_finite_root_report_status"] = "reached"
            row["search_execution_status"] = "reached"
            evidence["search_execution_reached"] = True
            if (
                evidence.get("mapping_complete") is not False
                and evidence.get("mapping_ambiguous") is not True
            ):
                row["occurrence_mapping_status"] = "complete"
                evidence["mapping_complete"] = True
                evidence["mapping_ambiguous"] = False
            if evidence.get("required_root_values_valid") is not False:
                evidence["required_root_values_valid"] = True
            if (
                evidence.get("public_projection_parity") is not False
                and evidence.get("ordered_legal_action_parity") is not False
                and evidence.get("bridge_precondition_or_sampler_failed") is not True
                and evidence.get("mapping_complete") is True
                and evidence.get("mapping_ambiguous") is False
                and evidence.get("required_root_values_valid") is True
            ):
                evidence["complete_admission"] = True
        except _T103ObservedBoundary as observed:
            if exc is None and observed.__cause__ is not None:
                exc = observed.__cause__
            elif exc is None and evidence.get("restore_binding_failed") is None:
                exc = observed
        # Native adapter exceptions vary by runtime; retain their exact type.
        except Exception as boundary_exc:  # noqa: BLE001
            exc = boundary_exc
            if row["bridge_invocation_status"] == "invoked":
                evidence["bridge_failure_unlocalized"] = True
            elif row["restore_status"] == "not_reached":
                evidence["restore_binding_failed"] = True
            else:
                evidence["observation_failed"] = True
        finally:
            row["wall_clock_time_s"] = time.perf_counter() - started

        diagnostic_class, subreason = classify_t103_observation(evidence)
        row["diagnostic_class"] = diagnostic_class
        row["subreason_code"] = subreason
        row["admitted"] = diagnostic_class == "ADMITTED"
        if (
            diagnostic_class == "OPAQUE_BRIDGE_FAILURE"
            and row["bridge_invocation_status"] == "invoked"
        ):
            row["bridge_invocation_status"] = (
                "failed"
                if row["valid_finite_root_report_status"] != "reached"
                else "returned_report"
            )
        if exc is not None:
            row.update(exception_signature(exc))
        # Only mark downstream stages not_reached when the bridge was directly
        # known not to have been invoked. A returned but malformed/opaque report
        # leaves those native stages unknown unless it proves positive reach.
        if row["bridge_invocation_status"] in {"not_reached", "failed_precondition"}:
            for field in (
                "occurrence_mapping_status",
                "search_execution_status",
                "valid_finite_root_report_status",
            ):
                if row[field] == "unknown":
                    row[field] = "not_reached"
        if diagnostic_class in T103_MAPPING_CLASSES:
            row["occurrence_mapping_status"] = {
                "ROOT_OCCURRENCE_MAPPING_INCOMPLETE": "incomplete",
                "ROOT_OCCURRENCE_MAPPING_AMBIGUOUS": "ambiguous",
                "ROOT_OCCURRENCE_MAPPING_INCOMPLETE_OR_AMBIGUOUS": (
                    "incomplete_or_ambiguous"
                ),
            }[diagnostic_class]
            if row["search_execution_status"] != "reached":
                row["search_execution_status"] = "not_reached"
            if row["valid_finite_root_report_status"] == "unknown":
                row["valid_finite_root_report_status"] = "not_reached"
        return row


class _T103ObservedBoundary(Exception):
    """Internal short-circuit after recording direct structured evidence."""


def _fraction(count: int, total: int) -> dict[str, object]:
    return {
        "count": count,
        "total": total,
        "fraction": f"{count}/{total}",
    }


def aggregate_t103_diagnostics(
    rows: Sequence[Mapping[str, object]],
    *,
    source_counts: Mapping[str, int],
    t101_input_bindings: Mapping[str, object],
    native_identity: Mapping[str, object],
) -> dict[str, object]:
    """Create exact census counts without population inference."""

    expected_total = sum(source_counts.values())
    if (
        len(rows) != expected_total
        or set(source_counts) != {"A", "B", "C"}
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count <= 0
            for count in source_counts.values()
        )
    ):
        raise T103DiagnosticError("T103 diagnostic rows do not cover the source census")
    identities = [row.get("selection_identity") for row in rows]
    if (
        any(not isinstance(value, str) or not value for value in identities)
        or len(set(identities)) != expected_total
    ):
        raise T103DiagnosticError("T103 diagnostic identity coverage is invalid")
    observed_counts = Counter(str(row.get("stratum")) for row in rows)
    if dict(observed_counts) != dict(source_counts):
        raise T103DiagnosticError("T103 diagnostic stratum counts changed")
    if any(row.get("diagnostic_class") not in T103_CLASSES for row in rows):
        raise T103DiagnosticError("T103 row has an unknown diagnostic class")
    if any(
        row.get("admitted") is not (row.get("diagnostic_class") == "ADMITTED")
        for row in rows
    ):
        raise T103DiagnosticError("T103 admitted flags disagree with diagnostic class")

    admitted = sum(row.get("admitted") is True for row in rows)
    terminal = (
        "T101_SUPPORT_RESULT_NOT_REPRODUCED"
        if admitted
        else "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED"
    )
    newly_admitted = [row for row in rows if row.get("admitted") is True]
    retained_execution_identity = t101_input_bindings.get(
        "retained_t101_execution_identity"
    )
    if admitted and (
        not isinstance(native_identity, Mapping)
        or not {"repository", "ref", "commit"}.issubset(native_identity)
        or not isinstance(retained_execution_identity, Mapping)
        or not {
            "implementation_head",
            "native_identity",
            "readiness_authorization_sha256",
            "input_admission_artifact_sha256",
            "cohort_admission_artifact_sha256",
        }.issubset(retained_execution_identity)
        or any(
            not isinstance(row.get("source_ordinal"), int)
            or not isinstance(row.get("selection_digest"), str)
            for row in newly_admitted
        )
    ):
        raise T103DiagnosticError(
            "baseline mismatch lacks exact candidate or execution identities"
        )
    include_distribution = admitted == 0
    class_counts = Counter(str(row["diagnostic_class"]) for row in rows)
    by_stratum: dict[str, object] = {}
    for stratum in ("A", "B", "C"):
        stratum_rows = [row for row in rows if row.get("stratum") == stratum]
        counts = Counter(str(row["diagnostic_class"]) for row in stratum_rows)
        by_stratum[stratum] = {
            "total": source_counts[stratum],
            "classes": {
                name: _fraction(counts[name], source_counts[stratum])
                for name in T103_CLASSES
            },
            "search_execution_reached": sum(
                row.get("search_execution_status") == "reached" for row in stratum_rows
            ),
            "valid_finite_root_report_reached": sum(
                row.get("valid_finite_root_report_status") == "reached"
                for row in stratum_rows
            ),
            "admitted": sum(row.get("admitted") is True for row in stratum_rows),
        }

    subreasons = Counter(
        str(row["subreason_code"])
        for row in rows
        if isinstance(row.get("subreason_code"), str)
    )
    signatures = Counter(
        f"{row.get('exception_type')}:{row.get('exception_signature')}"
        for row in rows
        if isinstance(row.get("exception_type"), str)
        and isinstance(row.get("exception_signature"), str)
    )
    mapping_count = sum(
        row.get("diagnostic_class") in T103_MAPPING_CLASSES for row in rows
    )
    opaque_count = class_counts["OPAQUE_BRIDGE_FAILURE"]
    report: dict[str, object] = {
        "schema_id": T103_REPORT_SCHEMA_ID,
        "task_id": "T103",
        "terminal_classification": terminal,
        "claim_boundary": (
            "observable first-failing boundaries in the exact frozen "
            "T101 413-record population"
        ),
        "producer_provenance": {
            "t101_input_bindings": dict(t101_input_bindings),
            "current_native_identity": dict(native_identity),
        },
        "source_population": {
            "total": expected_total,
            "by_stratum": dict(source_counts),
        },
        "sampler_seed_algorithm": T101_SEED_ALGORITHM,
        "diagnostic_distribution": (
            {
                "all_candidates": _fraction(expected_total, expected_total),
                "classes": {
                    name: _fraction(class_counts[name], expected_total)
                    for name in T103_CLASSES
                },
                "by_stratum": by_stratum,
                "subreason_codes": {
                    name: _fraction(count, expected_total)
                    for name, count in sorted(subreasons.items())
                },
                "opaque_bridge_failure": _fraction(opaque_count, expected_total),
                "occurrence_mapping_related": _fraction(mapping_count, expected_total),
                "search_execution_reached": _fraction(
                    sum(
                        row.get("search_execution_status") == "reached" for row in rows
                    ),
                    expected_total,
                ),
                "valid_finite_root_report_reached": _fraction(
                    sum(
                        row.get("valid_finite_root_report_status") == "reached"
                        for row in rows
                    ),
                    expected_total,
                ),
                "admitted": _fraction(admitted, expected_total),
                "most_frequent_exact_diagnostic_signatures": [
                    {"signature": name, **_fraction(count, expected_total)}
                    for name, count in signatures.most_common(20)
                ],
            }
            if include_distribution
            else None
        ),
        "baseline_reproduction": {
            "t101_admitted_candidates": 0,
            "t103_admitted_candidates": admitted,
            "reproduced": admitted == 0,
            **(
                {
                    "newly_admitted_candidates": [
                        {
                            "selection_identity": row["selection_identity"],
                            "stratum": row["stratum"],
                            "source_ordinal": row["source_ordinal"],
                            "selection_digest": row["selection_digest"],
                        }
                        for row in newly_admitted
                    ],
                    "current_native_identity": dict(native_identity),
                    "retained_t101_execution_identity": dict(
                        retained_execution_identity
                    ),
                }
                if admitted
                else {}
            ),
        },
        "nonclaims": [
            "no hidden root cause beyond retained direct observations",
            "no convergence or particle-stability conclusion",
            "no posterior-correctness, controller-quality, or Search-improvement claim",
            "no generalization outside the frozen T101 source population",
        ],
    }
    return report


def write_t103_retained_artifacts(
    *,
    artifact_root: Path,
    rows: Sequence[Mapping[str, object]],
    report: Mapping[str, object],
    producer_provenance: Mapping[str, object],
    regeneration_command: str,
    retention_reason: str,
    deletion_condition: str,
) -> dict[str, object]:
    """Write one hash-bound row set, aggregate report, and retention manifest."""

    root = artifact_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate_path = root / "t103-candidate-diagnostics.json"
    report_path = root / "t103-aggregate-report.json"
    manifest_path = root / "t103-retention-manifest.json"
    for path in (candidate_path, report_path, manifest_path):
        if path.exists():
            raise T103DiagnosticError("refusing to overwrite retained T103 evidence")

    candidate_document = {
        "schema_id": T103_DIAGNOSTIC_SCHEMA_ID,
        "task_id": "T103",
        "rows": [dict(row) for row in rows],
    }
    candidate_bytes = _canonical_json(candidate_document) + b"\n"
    report_bytes = _canonical_json(dict(report)) + b"\n"
    references = {
        "candidate_diagnostics": _write_bytes_new(
            candidate_path, candidate_bytes, T103_DIAGNOSTIC_SCHEMA_ID
        ),
        "aggregate_report": _write_bytes_new(
            report_path, report_bytes, T103_REPORT_SCHEMA_ID
        ),
    }
    manifest = {
        "schema_id": T103_RETENTION_SCHEMA_ID,
        "task_id": "T103",
        "terminal_classification": report.get("terminal_classification"),
        "producer_provenance": dict(producer_provenance),
        "artifact_references": references,
        "regeneration_commands": [regeneration_command],
        "retention_reason": retention_reason,
        "raw_deletion_condition": deletion_condition,
    }
    manifest_reference = _write_bytes_new(
        manifest_path,
        _canonical_json(manifest) + b"\n",
        T103_RETENTION_SCHEMA_ID,
    )
    return {
        "candidate_diagnostics": references["candidate_diagnostics"],
        "aggregate_report": references["aggregate_report"],
        "retention_manifest": manifest_reference,
    }


def _write_bytes_new(path: Path, payload: bytes, schema_id: str) -> dict[str, object]:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return {
        "path": str(path.resolve()),
        "schema_id": schema_id,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def replay_t103_candidates(
    *,
    runner: T103NativeRecordRunner,
    source_records_by_identity: Mapping[str, Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    worker_count: int,
) -> list[dict[str, object]]:
    """Replay in T101 order while sharing the single loaded source pool."""

    if (
        isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or worker_count < 1
    ):
        raise T103DiagnosticError("T103 worker count must be a positive integer")
    ordered: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for attempt in attempts:
        identity = attempt.get("selection_identity")
        if not isinstance(identity, str) or identity not in source_records_by_identity:
            raise T103DiagnosticError(
                "T101 attempt is not bound to an accepted source record"
            )
        source = source_records_by_identity[identity]
        if source.get("selection_identity") != identity:
            raise T103DiagnosticError("T101 attempt/source identity mismatch")
        if source.get("cohort", source.get("stratum")) != attempt.get("stratum"):
            raise T103DiagnosticError("T101 attempt/source stratum mismatch")
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if attempt.get("selection_digest") != digest:
            raise T103DiagnosticError("T101 attempt selection digest mismatch")
        ordinal = attempt.get("source_ordinal")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise T103DiagnosticError("T101 attempt source ordinal is invalid")
        ordered.append((attempt, source))
    if len(ordered) != len(source_records_by_identity) or len(ordered) != 413:
        raise T103DiagnosticError(
            "T101 attempts do not cover the exact 413-record source set"
        )

    if worker_count > len(ordered):
        raise T103DiagnosticError("T103 worker count exceeds the source shard count")

    quotient, remainder = divmod(len(ordered), worker_count)
    shards: list[list[tuple[Mapping[str, object], Mapping[str, object]]]] = []
    start = 0
    for shard_index in range(worker_count):
        size = quotient + (1 if shard_index < remainder else 0)
        shards.append(ordered[start : start + size])
        start += size

    def run_shard(
        shard: Sequence[tuple[Mapping[str, object], Mapping[str, object]]],
    ) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for attempt, source in shard:
            result.append(
                runner.diagnose(
                    source,
                    source_ordinal=int(attempt["source_ordinal"]),
                    selection_digest=str(attempt["selection_digest"]),
                )
            )
        return result

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return [
            row for shard_rows in executor.map(run_shard, shards) for row in shard_rows
        ]


def t103_record_shard_ranges(
    record_count: int, worker_count: int
) -> list[dict[str, int]]:
    """Describe the contiguous deterministic record ranges assigned to workers."""

    if (
        isinstance(record_count, bool)
        or not isinstance(record_count, int)
        or record_count < 1
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or not 1 <= worker_count <= record_count
    ):
        raise T103DiagnosticError("T103 shard topology is invalid")
    quotient, remainder = divmod(record_count, worker_count)
    ranges: list[dict[str, int]] = []
    start = 0
    for shard_index in range(worker_count):
        size = quotient + (1 if shard_index < remainder else 0)
        ranges.append(
            {
                "shard_index": shard_index,
                "start_ordinal_inclusive": start,
                "end_ordinal_exclusive": start + size,
                "record_count": size,
            }
        )
        start += size
    return ranges
