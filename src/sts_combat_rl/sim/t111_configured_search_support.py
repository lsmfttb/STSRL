"""Configured-Search-domain support admission for the frozen T101 population.

T111 consumes the already strict T110 v2 bridge report.  This module adds a
separate support view for searched occurrences; it deliberately leaves the
historical T101 all-public-occurrences finite-value validator unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099ParticleSearchBridgeError,
    validate_t099_particle_search_bridge,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SEARCH_SIMULATIONS,
    T101_SELECTED_PER_STRATUM,
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    _identity as _t101_identity,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    _selection_key as _t101_selection_key,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    _source_population as _t101_source_population,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    _stratum as _t101_stratum,
)

T111_TASK_ID = "T111"
T111_NATIVE_COMMIT = "6496fc1c7e629a374b72bd94f7fd29afe29c7f62"
T111_NATIVE_REF = "refs/heads/stsrl/main"
T111_BRIDGE_SCHEMA = "native-battle-public-particle-search-v2"
T111_ADMISSION_SCHEMA = "t111-configured-search-cohort-admission-v1"
T111_SEARCHED_CLASSIFICATIONS = frozenset(
    {
        "searched_direct",
        "searched_mechanical_duplicate_card_occurrence",
    }
)
T111_EXCLUDED_CLASSIFICATION = "search_configuration_excluded"
T111_EXCLUSION_REASONS = frozenset(
    {
        "restore_or_provenance_incompatible",
        "public_projection_parity_failure",
        "ordered_public_action_parity_failure",
        "public_fidelity_failure",
        "v2_bridge_schema_or_classification_failure",
        "searched_edge_coverage_failure",
        "searched_excluded_partition_drift",
        "searched_value_unavailable_nonfinite_or_unvisited",
        "accepted_structured_bridge_failure",
    }
)
T111_STRUCTURAL_PREDICATES = (
    "restore_exact_accepted_state",
    "public_projection_parity",
    "ordered_legal_action_parity",
    "search_configuration_unchanged",
    "strict_t110_v2_bridge_valid",
    "searched_values_finite_and_visited",
    "search_edges_covered",
    "classification_and_partition_stable_across_particles",
)


class T111ConfiguredSearchError(ValueError):
    """T111 input or configured-domain evidence is invalid or incomplete."""


class T111SupportExclusion(T111ConfiguredSearchError):
    """One candidate failed at a typed, contract-defined support boundary."""

    def __init__(
        self,
        reason: str,
        *,
        evidence: Mapping[str, object] | None = None,
    ) -> None:
        if reason not in T111_EXCLUSION_REASONS:
            raise ValueError("unknown T111 structured support exclusion")
        super().__init__(reason)
        self.reason = reason
        self.evidence = dict(evidence or {})


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _finite_number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise T111SupportExclusion(
            "searched_value_unavailable_nonfinite_or_unvisited",
            evidence={"field": label},
        )
    return float(value)


def _positive_visits(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise T111SupportExclusion(
            "searched_value_unavailable_nonfinite_or_unvisited",
            evidence={"field": "visits"},
        )
    return value


def _preclassify_search_value_failure(value: object) -> None:
    """Name a structured searched-value failure before strict T110 rejects it."""

    if not isinstance(value, Mapping) or value.get("schema_id") != T111_BRIDGE_SCHEMA:
        return
    particles = value.get("particles")
    if not isinstance(particles, list):
        return
    for particle in particles:
        if not isinstance(particle, Mapping):
            continue
        rows = particle.get("root_rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if (
                not isinstance(row, Mapping)
                or row.get("mapping_classification")
                not in T111_SEARCHED_CLASSIFICATIONS
            ):
                continue
            visits = row.get("visits")
            evaluation_sum = row.get("evaluation_sum")
            mean_value = row.get("mean_value")
            if (
                isinstance(visits, bool)
                or not isinstance(visits, int)
                or visits <= 0
                or isinstance(evaluation_sum, bool)
                or not isinstance(evaluation_sum, (int, float))
                or not math.isfinite(float(evaluation_sum))
                or isinstance(mean_value, bool)
                or not isinstance(mean_value, (int, float))
                or not math.isfinite(float(mean_value))
            ):
                raise T111SupportExclusion(
                    "searched_value_unavailable_nonfinite_or_unvisited",
                    evidence={"public_ordinal": row.get("public_action_ordinal")},
                )


def _particle_search_view(particle: Mapping[str, Any]) -> dict[str, object]:
    root_rows = particle.get("root_rows")
    if not isinstance(root_rows, list):
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"field": "root_rows"},
        )

    classifications: list[tuple[int, str]] = []
    groups_by_edge: dict[int, list[int]] = defaultdict(list)
    excluded_ordinals: list[int] = []
    searched_count = 0
    for expected_ordinal, row in enumerate(root_rows):
        if not isinstance(row, Mapping):
            raise T111SupportExclusion(
                "v2_bridge_schema_or_classification_failure",
                evidence={"public_ordinal": expected_ordinal},
            )
        ordinal = row.get("public_action_ordinal")
        classification = row.get("mapping_classification")
        if ordinal != expected_ordinal or not isinstance(classification, str):
            raise T111SupportExclusion(
                "v2_bridge_schema_or_classification_failure",
                evidence={"public_ordinal": expected_ordinal},
            )
        classifications.append((ordinal, classification))
        if classification == T111_EXCLUDED_CLASSIFICATION:
            # The strict T110 validator has already proved the complete null,
            # zero-visit, PLAYER_NORMAL potion-exclusion contract.  T111 only
            # retains its public identity/ordinal and never makes it numeric.
            excluded_ordinals.append(ordinal)
            continue
        if classification not in T111_SEARCHED_CLASSIFICATIONS:
            raise T111SupportExclusion(
                "v2_bridge_schema_or_classification_failure",
                evidence={"public_ordinal": ordinal},
            )
        _finite_number(row.get("evaluation_sum"), "evaluation_sum")
        _finite_number(row.get("mean_value"), "mean_value")
        _positive_visits(row.get("visits"))
        edge = row.get("search_equivalence_source_edge_index")
        if isinstance(edge, bool) or not isinstance(edge, int) or edge < 0:
            raise T111SupportExclusion(
                "searched_edge_coverage_failure",
                evidence={"public_ordinal": ordinal},
            )
        groups_by_edge[edge].append(ordinal)
        searched_count += 1

    partition = tuple(
        sorted(
            (tuple(sorted(ordinals)) for ordinals in groups_by_edge.values()),
            key=lambda ordinals: ordinals[0],
        )
    )
    if searched_count == 0 or not partition:
        raise T111SupportExclusion(
            "searched_edge_coverage_failure",
            evidence={"searched_occurrence_count": searched_count},
        )
    return {
        "classification_by_public_ordinal": tuple(classifications),
        "excluded_public_action_ordinals": tuple(excluded_ordinals),
        "searched_occurrence_count": searched_count,
        "decision_class_partition": partition,
    }


def validate_t111_configured_search_report(
    value: object,
    *,
    expected_sampler_seed: int,
    particle_count: int = 2,
) -> dict[str, object]:
    """Validate strict T110 v2 output and expose only the configured Search view.

    No excluded occurrence is included in the returned decision classes or any
    numeric field. Values are validated for finiteness but intentionally not
    ranked, averaged, or copied into the support summary.
    """

    _preclassify_search_value_failure(value)
    try:
        report = validate_t099_particle_search_bridge(value)
    except T099ParticleSearchBridgeError as exc:
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"validator": "strict_t110_v2"},
        ) from exc
    if (
        report.get("schema_id") != T111_BRIDGE_SCHEMA
        or report.get("particle_start") != 0
        or report.get("particle_count") != particle_count
        or report.get("search_simulations") != T101_SEARCH_SIMULATIONS
        or report.get("include_potions") is not False
    ):
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"field": "frozen_bridge_configuration"},
        )
    if (
        isinstance(expected_sampler_seed, bool)
        or not isinstance(expected_sampler_seed, int)
        or not 0 <= expected_sampler_seed < 2**64
        or report.get("sampler_seed_input") != expected_sampler_seed
    ):
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"field": "sampler_seed_input"},
        )

    particles = report.get("particles")
    if not isinstance(particles, list) or len(particles) != particle_count:
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"field": "particles"},
        )
    views: list[dict[str, object]] = []
    for particle in particles:
        if not isinstance(particle, Mapping):
            raise T111SupportExclusion(
                "v2_bridge_schema_or_classification_failure",
                evidence={"field": "particle"},
            )
        # Strict T099 validation above requires a non-boolean integer seed and
        # the requested ordered particle index.  The native-owned particle
        # seed is derived from sampler_seed_input; only the bridge input is
        # compared with the T101-derived expected seed here.
        views.append(_particle_search_view(particle))

    reference = views[0]
    public_actions = report.get("anchor_ordered_public_legal_actions")
    if not isinstance(public_actions, list):
        raise T111SupportExclusion(
            "v2_bridge_schema_or_classification_failure",
            evidence={"field": "anchor_ordered_public_legal_actions"},
        )
    excluded_evidence: list[dict[str, object]] = []
    excluded_ordinals = reference["excluded_public_action_ordinals"]
    assert isinstance(excluded_ordinals, tuple)
    for ordinal in excluded_ordinals:
        action = public_actions[ordinal]
        if not isinstance(action, Mapping):
            raise T111SupportExclusion(
                "v2_bridge_schema_or_classification_failure",
                evidence={"public_ordinal": ordinal},
            )
        particle_rows: list[dict[str, object]] = []
        for particle in particles:
            rows = particle.get("root_rows")
            if not isinstance(rows, list) or ordinal >= len(rows):
                raise T111SupportExclusion(
                    "v2_bridge_schema_or_classification_failure",
                    evidence={"public_ordinal": ordinal},
                )
            row = rows[ordinal]
            if not isinstance(row, Mapping):
                raise T111SupportExclusion(
                    "v2_bridge_schema_or_classification_failure",
                    evidence={"public_ordinal": ordinal},
                )
            # T110 has already proved these exact configuration-exclusion
            # invariants. Retain only public identity, classification, and
            # explicit null/zero semantics; no excluded value is imputed.
            particle_rows.append(
                {
                    "particle_index": particle.get("particle_index"),
                    "mapping_classification": row.get("mapping_classification"),
                    "configuration_exclusion_reason": row.get(
                        "configuration_exclusion_reason"
                    ),
                    "search_edge_index": row.get("search_edge_index"),
                    "search_equivalence_source_edge_index": row.get(
                        "search_equivalence_source_edge_index"
                    ),
                    "search_equivalence_mapping_mode": row.get(
                        "search_equivalence_mapping_mode"
                    ),
                    "visits": row.get("visits"),
                    "evaluation_sum": row.get("evaluation_sum"),
                    "mean_value": row.get("mean_value"),
                }
            )
        excluded_evidence.append(
            {
                "public_action_ordinal": ordinal,
                "public_action": {
                    key: action.get(key)
                    for key in ("scope", "kind", "idx1", "idx2", "idx3", "label")
                },
                "particle_evidence": particle_rows,
            }
        )

    if any(
        view["classification_by_public_ordinal"]
        != reference["classification_by_public_ordinal"]
        for view in views[1:]
    ) or any(
        view["decision_class_partition"] != reference["decision_class_partition"]
        for view in views[1:]
    ):
        raise T111SupportExclusion(
            "searched_excluded_partition_drift",
            evidence={"particle_count": particle_count},
        )

    partition = reference["decision_class_partition"]
    assert isinstance(partition, tuple)
    return {
        "bridge_report_sha256": _canonical_sha256(report),
        "public_action_count": len(reference["classification_by_public_ordinal"]),
        "searched_occurrence_count_per_particle": reference[
            "searched_occurrence_count"
        ],
        "configuration_excluded_occurrence_count_per_particle": len(
            reference["excluded_public_action_ordinals"]
        ),
        "configuration_excluded_public_action_ordinals": list(
            reference["excluded_public_action_ordinals"]
        ),
        "configuration_excluded_public_occurrences": excluded_evidence,
        "public_occurrence_classification_by_ordinal": [
            {"public_action_ordinal": ordinal, "classification": classification}
            for ordinal, classification in reference["classification_by_public_ordinal"]
        ],
        "searched_classification_by_public_ordinal": [
            {"public_action_ordinal": ordinal, "classification": classification}
            for ordinal, classification in reference["classification_by_public_ordinal"]
            if classification in T111_SEARCHED_CLASSIFICATIONS
        ],
        "configured_search_decision_classes": [
            {"class_index": index, "public_action_ordinals": list(ordinals)}
            for index, ordinals in enumerate(partition)
        ],
        "configured_search_decision_class_count": len(partition),
        "searched_excluded_classification_and_partition_stable": True,
        "all_searched_occurrences_finite_and_visited": True,
        "all_search_edges_covered": True,
    }


def select_t111_configured_search_cohort(
    source_rows: Iterable[Mapping[str, object]],
    *,
    native_identity: Mapping[str, object],
    admit: Callable[[Mapping[str, object]], object],
    on_attempt: Callable[[Mapping[str, object]], None] | None = None,
) -> dict[str, object]:
    """Reuse T101's population and exact ordering, stopping each stratum at 8."""

    expected_native = {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T111_NATIVE_REF,
        "commit": T111_NATIVE_COMMIT,
    }
    if dict(native_identity) != expected_native:
        raise T111ConfiguredSearchError("current T110 native identity mismatch")
    population = _t101_source_population(source_rows)
    selected: list[dict[str, object]] = []
    attempted: list[dict[str, object]] = []
    exhausted: list[str] = []

    for stratum in T101_SOURCE_COUNTS:
        accepted = 0
        candidates = sorted(
            (row for row in population if _t101_stratum(row) == stratum),
            key=_t101_selection_key,
        )
        for source_ordinal, candidate in enumerate(candidates):
            if accepted >= T101_SELECTED_PER_STRATUM:
                break
            identity = _t101_identity(candidate)
            digest = _t101_selection_key(candidate)[0]
            seed = derive_t101_sampler_seed(identity, 0)
            attempt_started = time.perf_counter()
            try:
                evidence = admit(candidate)
                if not isinstance(evidence, Mapping):
                    raise T111SupportExclusion(
                        "accepted_structured_bridge_failure",
                        evidence={"boundary": "admission_callback"},
                    )
                for predicate in (
                    "restore_exact_accepted_state",
                    "public_projection_parity",
                    "ordered_legal_action_parity",
                    "search_configuration_unchanged",
                ):
                    if evidence.get(predicate) is not True:
                        reason = {
                            "restore_exact_accepted_state": "restore_or_provenance_incompatible",
                            "public_projection_parity": "public_projection_parity_failure",
                            "ordered_legal_action_parity": "ordered_public_action_parity_failure",
                            "search_configuration_unchanged": "v2_bridge_schema_or_classification_failure",
                        }[predicate]
                        raise T111SupportExclusion(
                            reason, evidence={"predicate": predicate}
                        )
                support = validate_t111_configured_search_report(
                    evidence.get("bridge_report"),
                    expected_sampler_seed=seed,
                    particle_count=2,
                )
            except T111SupportExclusion as exc:
                row = {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "source_ordinal": source_ordinal,
                    "selection_digest": digest,
                    "sampler_seed": seed,
                    "replicate_index": 0,
                    "native_identity": expected_native,
                    "admitted": False,
                    "structural_admission_predicates": {
                        predicate: (
                            exc.evidence.get("structural_admission_predicates", {}).get(
                                predicate
                            )
                            if isinstance(
                                exc.evidence.get("structural_admission_predicates"),
                                Mapping,
                            )
                            else None
                        )
                        for predicate in T111_STRUCTURAL_PREDICATES
                    },
                    "wall_clock_time_s": max(
                        0.0, time.perf_counter() - attempt_started
                    ),
                    "failure_retry_status": "failed_no_retry",
                    "exclusion_reason": exc.reason,
                    "exclusion_evidence": exc.evidence,
                    "bridge_report_sha256": None,
                    "configuration_excluded_occurrence_count": None,
                    "configured_search_decision_class_count": None,
                }
                attempted.append(row)
                if on_attempt is not None:
                    on_attempt(row)
                continue

            row = {
                "selection_identity": identity,
                "stratum": stratum,
                "source_ordinal": source_ordinal,
                "selection_digest": digest,
                "sampler_seed": seed,
                "replicate_index": 0,
                "native_identity": expected_native,
                "admitted": True,
                "wall_clock_time_s": max(0.0, time.perf_counter() - attempt_started),
                "failure_retry_status": "success_no_retry",
                "structural_admission_predicates": {
                    "restore_exact_accepted_state": True,
                    "public_projection_parity": True,
                    "ordered_legal_action_parity": True,
                    "strict_t110_v2_bridge_valid": True,
                    "searched_values_finite_and_visited": True,
                    "search_edges_covered": True,
                    "classification_and_partition_stable_across_particles": True,
                },
                "bridge_report_sha256": support["bridge_report_sha256"],
                "configuration_excluded_occurrence_count": support[
                    "configuration_excluded_occurrence_count_per_particle"
                ],
                "configured_search_decision_class_count": support[
                    "configured_search_decision_class_count"
                ],
                "support_summary": support,
                "exclusion_reason": None,
            }
            attempted.append(row)
            selected.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "selection_digest": digest,
                    "sampler_seed": seed,
                    "replicate_index": 0,
                }
            )
            accepted += 1
            if on_attempt is not None:
                on_attempt(row)
        if accepted != T101_SELECTED_PER_STRATUM:
            exhausted.append(stratum)

    selected_counts = {
        stratum: sum(row["stratum"] == stratum for row in selected)
        for stratum in T101_SOURCE_COUNTS
    }
    terminal = (
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_SUFFICIENT"
        if not exhausted
        else "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
    )
    return {
        "schema_id": T111_ADMISSION_SCHEMA,
        "task_id": T111_TASK_ID,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "selection_rule": "sha256-selection-identity-then-canonical-identity-v1",
        "selection_uses_value_or_outcome": False,
        "historical_failure_label_preselection": False,
        "particle_start": 0,
        "particle_count": 2,
        "replicate_index": 0,
        "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
        "include_potions": False,
        "native_identity": expected_native,
        "attempted": attempted,
        "selected": selected,
        "selected_counts": selected_counts,
        "exhausted_strata": exhausted,
        "terminal_classification": terminal,
    }


def validate_t111_configured_search_cohort(value: object) -> dict[str, object]:
    """Validate T111 output shape, per-stratum stop rule, and terminal meaning."""

    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != T111_ADMISSION_SCHEMA
    ):
        raise T111ConfiguredSearchError("T111 cohort admission schema mismatch")
    if (
        value.get("task_id") != T111_TASK_ID
        or value.get("source_counts") != T101_SOURCE_COUNTS
        or value.get("selection_rule")
        != "sha256-selection-identity-then-canonical-identity-v1"
        or value.get("selection_uses_value_or_outcome") is not False
        or value.get("historical_failure_label_preselection") is not False
        or value.get("particle_start") != 0
        or value.get("particle_count") != 2
        or value.get("replicate_index") != 0
        or value.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
        or value.get("include_potions") is not False
    ):
        raise T111ConfiguredSearchError("T111 frozen admission configuration changed")
    native = value.get("native_identity")
    if not isinstance(native, Mapping) or dict(native) != {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T111_NATIVE_REF,
        "commit": T111_NATIVE_COMMIT,
    }:
        raise T111ConfiguredSearchError("T111 cohort native identity changed")
    attempted = value.get("attempted")
    selected = value.get("selected")
    exhausted = value.get("exhausted_strata")
    if (
        not isinstance(attempted, Sequence)
        or isinstance(attempted, (str, bytes))
        or not isinstance(selected, Sequence)
        or isinstance(selected, (str, bytes))
        or not isinstance(exhausted, Sequence)
        or isinstance(exhausted, (str, bytes))
    ):
        raise T111ConfiguredSearchError("T111 candidate evidence is malformed")
    ids: set[str] = set()
    selected_ids: set[str] = set()
    expected_selected: list[dict[str, object]] = []
    selected_counts = Counter()
    attempts_by_stratum = {stratum: [] for stratum in T101_SOURCE_COUNTS}
    observed_attempt_strata: list[str] = []
    for row in attempted:
        if not isinstance(row, Mapping):
            raise T111ConfiguredSearchError("T111 attempt row is malformed")
        identity = row.get("selection_identity")
        stratum = row.get("stratum")
        replicate_index = row.get("replicate_index")
        sampler_seed = row.get("sampler_seed")
        wall_clock_time_s = row.get("wall_clock_time_s")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in ids
            or stratum not in T101_SOURCE_COUNTS
            or isinstance(replicate_index, bool)
            or replicate_index != 0
            or isinstance(sampler_seed, bool)
            or sampler_seed != derive_t101_sampler_seed(identity, 0)
            or isinstance(wall_clock_time_s, bool)
            or not isinstance(wall_clock_time_s, (int, float))
            or not math.isfinite(float(wall_clock_time_s))
            or wall_clock_time_s < 0
            or row.get("native_identity") != dict(native)
            or row.get("failure_retry_status")
            not in {"success_no_retry", "failed_no_retry"}
        ):
            raise T111ConfiguredSearchError("T111 attempt identity/configuration drift")
        ids.add(identity)
        observed_attempt_strata.append(stratum)
        attempts_by_stratum[stratum].append(row)
        if row.get("admitted") is True:
            support = row.get("support_summary")
            predicates = row.get("structural_admission_predicates")
            if (
                not isinstance(support, Mapping)
                or not isinstance(predicates, Mapping)
                or dict(predicates)
                != {
                    "restore_exact_accepted_state": True,
                    "public_projection_parity": True,
                    "ordered_legal_action_parity": True,
                    "strict_t110_v2_bridge_valid": True,
                    "searched_values_finite_and_visited": True,
                    "search_edges_covered": True,
                    "classification_and_partition_stable_across_particles": True,
                }
                or row.get("exclusion_reason") is not None
                or row.get("failure_retry_status") != "success_no_retry"
                or row.get("bridge_report_sha256")
                != support.get("bridge_report_sha256")
                or row.get("configuration_excluded_occurrence_count")
                != support.get("configuration_excluded_occurrence_count_per_particle")
                or row.get("configured_search_decision_class_count")
                != support.get("configured_search_decision_class_count")
            ):
                raise T111ConfiguredSearchError("admitted T111 support summary missing")
            selected_ids.add(identity)
            selected_counts[stratum] += 1
            expected_selected.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "selection_digest": row.get("selection_digest"),
                    "sampler_seed": sampler_seed,
                    "replicate_index": 0,
                }
            )
        elif row.get("admitted") is False:
            evidence = row.get("exclusion_evidence")
            predicates = row.get("structural_admission_predicates")
            if (
                row.get("exclusion_reason") not in T111_EXCLUSION_REASONS
                or not isinstance(evidence, Mapping)
                or not isinstance(predicates, Mapping)
                or set(predicates) != set(T111_STRUCTURAL_PREDICATES)
                or any(
                    value not in {True, False, None} for value in predicates.values()
                )
                or row.get("failure_retry_status") != "failed_no_retry"
                or row.get("bridge_report_sha256") is not None
                or row.get("configuration_excluded_occurrence_count") is not None
                or row.get("configured_search_decision_class_count") is not None
            ):
                raise T111ConfiguredSearchError(
                    "T111 exclusion reason is not structured"
                )
        else:
            raise T111ConfiguredSearchError("T111 admitted flag is invalid")
    expected_global_strata = [
        stratum
        for stratum in T101_SOURCE_COUNTS
        for _row in attempts_by_stratum[stratum]
    ]
    if observed_attempt_strata != expected_global_strata:
        raise T111ConfiguredSearchError("T111 attempts are not in T101 stratum order")
    if list(selected) != expected_selected:
        raise T111ConfiguredSearchError(
            "T111 selected rows disagree with admitted attempts"
        )
    if len(selected_ids) != len(expected_selected):
        raise T111ConfiguredSearchError("T111 selected identities contain duplicates")
    selected_counts_dict = {
        stratum: selected_counts[stratum] for stratum in T101_SOURCE_COUNTS
    }
    if value.get("selected_counts") != selected_counts_dict:
        raise T111ConfiguredSearchError("T111 selected counts disagree with rows")
    for stratum, rows in attempts_by_stratum.items():
        if selected_counts[stratum] > T101_SELECTED_PER_STRATUM:
            raise T111ConfiguredSearchError(
                "T111 selected beyond the support threshold"
            )
        if len(rows) > T101_SOURCE_COUNTS[stratum]:
            raise T111ConfiguredSearchError("T111 attempted beyond source stratum")
        ordinals = [row.get("source_ordinal") for row in rows]
        if any(
            isinstance(ordinal, bool) or not isinstance(ordinal, int)
            for ordinal in ordinals
        ) or ordinals != list(range(len(rows))):
            raise T111ConfiguredSearchError("T111 source ordinals are not contiguous")
        observed_keys: list[tuple[str, str]] = []
        for row in rows:
            identity = row["selection_identity"]
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            if row.get("selection_digest") != digest:
                raise T111ConfiguredSearchError("T111 selection digest changed")
            observed_keys.append((digest, identity))
        if observed_keys != sorted(observed_keys):
            raise T111ConfiguredSearchError("T111 candidate order is not T101 order")
        if selected_counts[stratum] < T101_SELECTED_PER_STRATUM:
            if stratum not in exhausted or len(rows) != T101_SOURCE_COUNTS[stratum]:
                raise T111ConfiguredSearchError("T111 exhausted stratum is incomplete")
        else:
            admitted_positions = [
                index for index, row in enumerate(rows) if row.get("admitted") is True
            ]
            if len(admitted_positions) != T101_SELECTED_PER_STRATUM or len(rows) != (
                admitted_positions[T101_SELECTED_PER_STRATUM - 1] + 1
            ):
                raise T111ConfiguredSearchError(
                    "T111 did not stop at the eighth admission"
                )
    expected_exhausted = [
        stratum
        for stratum in T101_SOURCE_COUNTS
        if selected_counts[stratum] < T101_SELECTED_PER_STRATUM
    ]
    if list(exhausted) != expected_exhausted:
        raise T111ConfiguredSearchError("T111 exhausted-stratum list is inconsistent")
    expected_terminal = (
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_SUFFICIENT"
        if selected_counts_dict == {"A": 8, "B": 8, "C": 8}
        else "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
    )
    if value.get("terminal_classification") != expected_terminal:
        raise T111ConfiguredSearchError("T111 terminal classification is inconsistent")
    return dict(value)


__all__ = [
    "T111_ADMISSION_SCHEMA",
    "T111_NATIVE_COMMIT",
    "T111_NATIVE_REF",
    "T111ConfiguredSearchError",
    "T111SupportExclusion",
    "select_t111_configured_search_cohort",
    "validate_t111_configured_search_cohort",
    "validate_t111_configured_search_report",
]
