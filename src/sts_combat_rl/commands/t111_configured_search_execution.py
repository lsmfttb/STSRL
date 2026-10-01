"""Maintainer-authorized T111 candidate replay entrypoint components.

This module is deliberately separate from input qualification. Importing or
running the preparation command never constructs a simulator adapter. The
bounded record runner below is only called by the separately authorized
execution path after Maintainer exact-head/resource approval.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from sts_combat_rl.commands.t085_native_execution import (
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.public_run_context import (
    _validate_projection_candidate_parity,
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SEARCH_SIMULATIONS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t105_native_stage_observability import (
    validate_t105_stage_trace,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111SupportExclusion,
    validate_t111_configured_search_report,
)

_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": T111_NATIVE_REF,
    "commit": T111_NATIVE_COMMIT,
}
_PREDICATES = (
    "restore_exact_accepted_state",
    "public_projection_parity",
    "ordered_legal_action_parity",
    "search_configuration_unchanged",
    "strict_t110_v2_bridge_valid",
    "searched_values_finite_and_visited",
    "search_edges_covered",
    "classification_and_partition_stable_across_particles",
)


def _exception_type(exc: BaseException) -> str:
    """Retain only the class name, never exception prose or private payloads."""

    return type(exc).__name__[:120]


class T111NativeRecordRunner:
    """Restore one retained T101 occurrence and perform exactly one T110 call.

    The runner has no retry path and never performs a Battle action. It accepts
    only the selected and canonical records returned by the T087/T085 gate.
    """

    def __init__(
        self,
        *,
        adapter_factory: object,
        selected_records: Mapping[str, object],
        canonical_records_by_stratum: Mapping[str, Mapping[str, object]],
        native_identity: Mapping[str, object],
    ) -> None:
        if not callable(adapter_factory) or not selected_records:
            raise ValueError("T111 native runner inputs are unavailable")
        if dict(native_identity) != _NATIVE_IDENTITY:
            raise ValueError("T111 native runner is not bound to the T110 pin")
        self._adapter_factory = adapter_factory
        self._selected_records = selected_records
        self._canonical_records_by_stratum = canonical_records_by_stratum

    @staticmethod
    def _predicates(**updates: bool | None) -> dict[str, bool | None]:
        result: dict[str, bool | None] = {name: None for name in _PREDICATES}
        result.update(updates)
        return result

    @staticmethod
    def _exclude(
        reason: str,
        *,
        boundary: str,
        predicates: Mapping[str, bool | None],
        exc: BaseException | None = None,
        bridge_diagnostics: Mapping[str, object] | None = None,
    ) -> T111SupportExclusion:
        evidence: dict[str, object] = {
            "boundary": boundary,
            "structural_admission_predicates": dict(predicates),
        }
        if exc is not None:
            evidence["exception_type"] = _exception_type(exc)
        if bridge_diagnostics is not None:
            # This is a locally constructed allowlist of already-validated,
            # structured stage metadata. Never retain an adapter object,
            # diagnostic payload, or exception message.
            safe_diagnostics: dict[str, object] = {}
            for key in (
                "stage_diagnostics_status",
                "structured_failure_class",
                "structured_stage_evidence",
            ):
                value = bridge_diagnostics.get(key)
                if value is not None:
                    safe_diagnostics[key] = value
            evidence["bridge_diagnostics"] = safe_diagnostics
        return T111SupportExclusion(reason, evidence=evidence)

    @staticmethod
    def _failed_bridge_evidence(adapter: object) -> dict[str, object]:
        """Read only validated T105/T107-safe stage metadata after a bridge error."""

        diagnostics = getattr(adapter, "last_particle_search_stage_diagnostics", None)
        if not callable(diagnostics):
            return {"stage_diagnostics_status": "unavailable"}
        try:
            raw_trace = diagnostics()
            trace = validate_t105_stage_trace(
                raw_trace,
                expected_status="failed_closed",
                particle_start=0,
                particle_count=2,
            )
        except Exception as exc:  # noqa: BLE001 - malformed traces fail closed below
            return {
                "stage_diagnostics_status": "invalid_or_unavailable",
                "stage_diagnostics_error_type": _exception_type(exc),
            }

        first_failed_stage = trace.get("first_failed_stage")
        failure_code = trace.get("failure_code")
        safe_summary: dict[str, object] = {
            "schema_id": trace["schema_id"],
            "attempt_status": trace["attempt_status"],
            "first_failed_stage": first_failed_stage,
            "failure_code": failure_code,
            "particle_failure_codes": [
                {
                    "particle_index": row.get("particle_index"),
                    "first_failed_stage": row.get("first_failed_stage"),
                    "failure_code": row.get("failure_code"),
                }
                for row in trace["particles"]
            ],
        }
        if first_failed_stage == "public_fidelity_validation" and failure_code in {
            "public_fidelity_failed",
            "anchor_unsupported_fidelity",
        }:
            return {
                "stage_diagnostics_status": "validated_failure",
                "structured_stage_evidence": safe_summary,
                "structured_failure_class": "public_fidelity_failure",
            }
        return {
            "stage_diagnostics_status": "validated_failure",
            "structured_stage_evidence": safe_summary,
        }

    def __call__(self, record: Mapping[str, object]) -> Mapping[str, object]:
        identity = record.get("selection_identity")
        stratum = record.get("cohort", record.get("stratum"))
        if (
            not isinstance(identity, str)
            or not identity
            or stratum not in self._canonical_records_by_stratum
        ):
            raise ValueError("T111 candidate source identity is malformed")
        seed = derive_t101_sampler_seed(identity, 0)
        predicates = self._predicates()
        selected = self._selected_records.get(identity)
        canonical_map = self._canonical_records_by_stratum[stratum]
        canonical = canonical_map.get(identity)
        if (
            selected is None
            or canonical is None
            or getattr(selected, "selection_identity", None) != identity
        ):
            raise self._exclude(
                "restore_or_provenance_incompatible",
                boundary="accepted_t085_source_binding",
                predicates=predicates,
            )

        try:
            adapter = self._adapter_factory()
            restored, restore_method = restore_t085_canonical_record(
                adapter, selected, canonical_map
            )
        except Exception as exc:
            raise self._exclude(
                "restore_or_provenance_incompatible",
                boundary="exact_t085_restore",
                predicates=predicates,
                exc=exc,
            ) from exc
        predicates["restore_exact_accepted_state"] = True

        expected_context = getattr(canonical, "public_run_context", None)
        if not isinstance(expected_context, Mapping):
            raise self._exclude(
                "restore_or_provenance_incompatible",
                boundary="accepted_public_context_binding",
                predicates=predicates,
            )
        expected_history = expected_context.get("history", [])
        if not isinstance(expected_history, Sequence) or isinstance(
            expected_history, (str, bytes)
        ):
            raise self._exclude(
                "restore_or_provenance_incompatible",
                boundary="accepted_public_context_binding",
                predicates=predicates,
            )

        try:
            actions = list(adapter.legal_actions(restored))
            projection = read_native_public_projection(adapter, restored)
        except Exception as exc:
            raise self._exclude(
                "accepted_structured_bridge_failure",
                boundary="public_projection_observation",
                predicates=predicates,
                exc=exc,
            ) from exc
        if projection is not None:
            try:
                _validate_projection_candidate_parity(projection, actions)
            except ValueError as exc:
                raise self._exclude(
                    "public_projection_parity_failure",
                    boundary="projection_candidate_parity",
                    predicates=predicates,
                    exc=exc,
                ) from exc
        try:
            actual_context = build_public_run_context(
                restored.raw,
                actions,
                projection=projection,
                history=expected_history,
            )
        except Exception as exc:
            raise self._exclude(
                "accepted_structured_bridge_failure",
                boundary="public_context_construction",
                predicates=predicates,
                exc=exc,
            ) from exc
        expected_without_candidates = {
            key: value
            for key, value in expected_context.items()
            if key != "candidate_actions"
        }
        actual_without_candidates = {
            key: value
            for key, value in actual_context.items()
            if key != "candidate_actions"
        }
        if actual_without_candidates != expected_without_candidates:
            raise self._exclude(
                "public_projection_parity_failure",
                boundary="restored_public_context_parity",
                predicates=predicates,
            )
        predicates["public_projection_parity"] = True
        if actual_context.get("candidate_actions") != expected_context.get(
            "candidate_actions"
        ):
            raise self._exclude(
                "ordered_public_action_parity_failure",
                boundary="restored_ordered_action_parity",
                predicates=predicates,
            )
        predicates["ordered_legal_action_parity"] = True

        bridge = getattr(adapter, "sample_hidden_future_particles_search", None)
        if not callable(bridge):
            raise self._exclude(
                "v2_bridge_schema_or_classification_failure",
                boundary="bridge_api_precondition",
                predicates=predicates,
            )
        try:
            raw_report = bridge(
                restored,
                sampler_seed=seed,
                particle_start=0,
                particle_count=2,
                search_simulations=T101_SEARCH_SIMULATIONS,
                include_potions=False,
            )
        except Exception as exc:
            failed_bridge = self._failed_bridge_evidence(adapter)
            reason = (
                "public_fidelity_failure"
                if failed_bridge.get("structured_failure_class")
                == "public_fidelity_failure"
                else "accepted_structured_bridge_failure"
            )
            raise self._exclude(
                reason,
                boundary="single_n2_search_v2_bridge_call",
                predicates=predicates,
                exc=exc,
                bridge_diagnostics=failed_bridge,
            ) from exc
        predicates["search_configuration_unchanged"] = True

        try:
            support = validate_t111_configured_search_report(
                raw_report,
                expected_sampler_seed=seed,
                particle_count=2,
            )
        except T111SupportExclusion as exc:
            failed_predicates = dict(predicates)
            failed_predicates["strict_t110_v2_bridge_valid"] = False
            failed_predicates["searched_values_finite_and_visited"] = (
                False
                if exc.reason == "searched_value_unavailable_nonfinite_or_unvisited"
                else None
            )
            failed_predicates["search_edges_covered"] = (
                False if exc.reason == "searched_edge_coverage_failure" else None
            )
            failed_predicates[
                "classification_and_partition_stable_across_particles"
            ] = False if exc.reason == "searched_excluded_partition_drift" else None
            raise self._exclude(
                exc.reason,
                boundary="strict_t110_configured_search_validation",
                predicates=failed_predicates,
                exc=exc,
            ) from exc
        predicates["strict_t110_v2_bridge_valid"] = True
        predicates["searched_values_finite_and_visited"] = True
        predicates["search_edges_covered"] = True
        predicates["classification_and_partition_stable_across_particles"] = True

        if raw_report.get("anchor_ordered_public_legal_actions") != actual_context.get(
            "candidate_actions"
        ):
            failed_predicates = dict(predicates)
            failed_predicates["ordered_legal_action_parity"] = False
            raise self._exclude(
                "ordered_public_action_parity_failure",
                boundary="bridge_to_restored_ordered_action_parity",
                predicates=failed_predicates,
            )
        anchor_projection = raw_report.get("anchor_public_information_projection")
        canonical_payload = getattr(projection, "canonical_payload", None)
        if isinstance(canonical_payload, str):
            try:
                observed_projection = json.loads(canonical_payload)
            except json.JSONDecodeError as exc:
                failed_predicates = dict(predicates)
                failed_predicates["public_projection_parity"] = False
                raise self._exclude(
                    "public_projection_parity_failure",
                    boundary="bridge_to_restored_projection_parity",
                    predicates=failed_predicates,
                    exc=exc,
                ) from exc
            if observed_projection != anchor_projection:
                failed_predicates = dict(predicates)
                failed_predicates["public_projection_parity"] = False
                raise self._exclude(
                    "public_projection_parity_failure",
                    boundary="bridge_to_restored_projection_parity",
                    predicates=failed_predicates,
                )
        elif projection is not None:
            failed_predicates = dict(predicates)
            failed_predicates["public_projection_parity"] = False
            raise self._exclude(
                "public_projection_parity_failure",
                boundary="native_projection_canonical_payload_unavailable",
                predicates=failed_predicates,
            )

        return {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": raw_report,
            "restore_method": str(restore_method),
            "support_summary": support,
        }


__all__ = ["T111NativeRecordRunner"]
