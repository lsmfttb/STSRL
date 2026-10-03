"""Configured-Search-domain particle analysis for T113.

Native code owns public projection, particle construction, Battle mechanics,
Search-v2, and native-derived particle seed metadata.  This module validates
sanitized T110 v2 bridge reports and computes descriptive statistics over
searched Search-equivalence classes only.  Configuration-excluded public
occurrences remain in the audit surface and never receive numeric values.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from statistics import stdev
from typing import Any

from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099_VALUE_SEMANTICS,
    T099ParticleSearchBridgeError,
    validate_t099_particle_search_bridge,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_FORMAL_STATE_COUNT,
    T101_RANK_STATISTIC,
    T101_REPLICATES,
    T101_SEARCH_SIMULATIONS,
    T101_SOURCE_COUNTS,
    T101_VALUE_SEMANTICS,
    _distribution,
    _pairwise_rank_agreement,
    _prefix_metrics,
    _work_counter_distributions,
    _work_counter_sums,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_EXCLUDED_CLASSIFICATION,
    T111_SEARCHED_CLASSIFICATIONS,
    T111ConfiguredSearchError,
    validate_t111_configured_search_report,
)
from sts_combat_rl.sim.t112_sampler_seed_recovery import (
    T112_NATIVE_IDENTITY,
    T112RecoveryError,
    validate_t112_cohort,
)

T113_TASK_ID = "T113"
T113_APPROVED_SPEC_COMMIT = "370a966dd48d719f703e52c440f69c922aab407e"
T113_NATIVE_IDENTITY = dict(T112_NATIVE_IDENTITY)
T113_COHORT_SCHEMA = "t113-fixed-cohort-manifest-v1"
T113_INPUT_QUALIFICATION_SCHEMA = "t113-input-qualification-v1"
T113_READINESS_SCHEMA = "t113-readiness-preparation-v1"
T113_FORMAL_PLAN_SCHEMA = "t113-formal-execution-plan-v1"
T113_CANARY_LADDER_SCHEMA = "t113-canary-ladder-v1"
T113_CANARY_EVIDENCE_SCHEMA = "t113-canary-evidence-v1"
T113_FORMAL_EVIDENCE_SCHEMA = "t113-formal-evidence-v1"
T113_CONVERGENCE_SCHEMA = "t113-configured-domain-convergence-v1"
T113_COST_SCHEMA = "t113-cost-report-v1"
T113_STABILITY_OBSERVED = "BOUNDED_CONFIGURED_PARTICLE_PROXY_STABILITY_OBSERVED"
T113_STABILITY_NOT_ESTABLISHED = (
    "BOUNDED_CONFIGURED_PARTICLE_PROXY_STABILITY_NOT_ESTABLISHED"
)
T113_INELIGIBLE = "CONFIGURED_CONVERGENCE_INPUT_INELIGIBLE"
T113_NESTED_PREFIX_INVALID = "NESTED_PREFIX_CONTRACT_INVALID"
T113_INCOMPLETE = "INCOMPLETE"
T113_EXACT_T112_COHORT_SHA256 = (
    "3f83ab718bdcba98cdf26cc29233178fde96c7b9a796237139db499b34936ac1"
)
T113_EXACT_T112_FINAL_REPORT_SHA256 = (
    "d14b67a1f3f76461cb2a356e52df2199c901d09b23c97f80379ac5293bf6b4c9"
)
T113_EXACT_T112_RETENTION_SHA256 = (
    "cd23575eec8f3ce8d95981534312adf7f05cccb3f6cf4ceb9391c5541b1980fb"
)
T113_EXACT_NATIVE_BINARY_SHA256 = (
    "cdf650362a8178aed1919efb05b2255a8986562d6617e659e8e0dca26583dd3a"
)
T113_EXACT_NATIVE_MANIFEST_SHA256 = (
    "7166c61e798563d471306eaaedfaf925ceb61e237437484f3642b220477cf507"
)
T113_T112_RETENTION_SCHEMA = "t112-terminal-retention-manifest-v1"
T113_T112_FINAL_REPORT_SCHEMA = "t112-final-report-v2"
T113_T112_COHORT_SCHEMA = "t112-configured-search-cohort-admission-v2"
T113_SEARCH_CONFIGURATION = {
    "particle_start": 0,
    "particle_count": 32,
    "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
    "include_potions": False,
    "policy_prior": False,
    "learned_leaf_value": False,
    "progressive_bias": False,
    "outer_particle_distribution": "native_public_consistent_hidden_future_sampler",
    "continuation": "full_state_search_v2_per_particle",
    "aggregation": "offline_descriptive_only",
}
T113_RETENTION_ARTIFACT_ROLES = {
    "input_qualification": T113_INPUT_QUALIFICATION_SCHEMA,
    "fixed_cohort": T113_COHORT_SCHEMA,
    "canary_evidence": T113_CANARY_EVIDENCE_SCHEMA,
    "formal_plan": T113_FORMAL_PLAN_SCHEMA,
    "formal_evidence": T113_FORMAL_EVIDENCE_SCHEMA,
    "convergence_analysis": T113_CONVERGENCE_SCHEMA,
    "cost_report": T113_COST_SCHEMA,
    "final_report": "t113-final-report-v1",
}


class T113ConvergenceError(ValueError):
    """T113 evidence is missing, malformed, incompatible, or contradictory."""


def _finite(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise T113ConvergenceError(f"{label} must be finite numeric")
    return float(value)


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise T113ConvergenceError(f"{label} must be a non-negative integer")
    return value


def _identity(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise T113ConvergenceError("selection_identity is missing")
    return value


def _sha256_text(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T113ConvergenceError(f"{label} must be a lowercase SHA-256")
    return value


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


def _native_seed_metadata(
    report: Mapping[str, Any], *, expected_count: int
) -> list[dict[str, int]]:
    particles = report.get("particles")
    if not isinstance(particles, list) or len(particles) != expected_count:
        raise T113ConvergenceError("native particle seed metadata is incomplete")
    result: list[dict[str, int]] = []
    for expected_index, particle in enumerate(particles):
        if not isinstance(particle, Mapping):
            raise T113ConvergenceError("native particle metadata is malformed")
        index = particle.get("particle_index")
        seed = particle.get("sampler_seed")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index != expected_index
            or isinstance(seed, bool)
            or not isinstance(seed, int)
            or not 0 <= seed < 2**64
        ):
            raise T113ConvergenceError("native particle seed metadata is invalid")
        result.append({"particle_index": index, "sampler_seed": seed})
    return result


def _configured_domain_view(report: Mapping[str, Any]) -> dict[str, object]:
    """Build the searched-only class view after strict T110/T111 validation."""

    particles = report.get("particles")
    actions = report.get("anchor_ordered_public_legal_actions")
    if not isinstance(particles, list) or not isinstance(actions, list):
        raise T113ConvergenceError("bridge public surface is incomplete")
    reference_classifications: tuple[str, ...] | None = None
    reference_partition: tuple[tuple[int, tuple[int, ...]], ...] | None = None
    reference_excluded: tuple[int, ...] | None = None
    class_values: dict[int, list[float]] = {}
    searched_counts: list[int] = []
    excluded_counts: list[int] = []
    for particle_index, particle in enumerate(particles):
        if not isinstance(particle, Mapping):
            raise T113ConvergenceError("bridge particle row is malformed")
        rows = particle.get("root_rows")
        if not isinstance(rows, list) or len(rows) != len(actions):
            raise T113ConvergenceError("public root rows lost the full legal surface")
        classifications: list[str] = []
        by_edge: dict[int, list[int]] = defaultdict(list)
        excluded: list[int] = []
        searched_occurrences = 0
        for ordinal, row in enumerate(rows):
            if (
                not isinstance(row, Mapping)
                or row.get("public_action_ordinal") != ordinal
            ):
                raise T113ConvergenceError("root row ordinal/order changed")
            classification = row.get("mapping_classification")
            if classification not in {
                *T111_SEARCHED_CLASSIFICATIONS,
                T111_EXCLUDED_CLASSIFICATION,
            }:
                raise T113ConvergenceError("unknown configured Search classification")
            classifications.append(str(classification))
            if classification == T111_EXCLUDED_CLASSIFICATION:
                # T110 enforces exact null/no-value and zero-visit semantics.
                # Preserve the occurrence only in the public audit partition.
                if (
                    any(
                        row.get(field) is not None
                        for field in (
                            "search_edge_index",
                            "search_equivalence_source_edge_index",
                            "search_equivalence_mapping_mode",
                            "evaluation_sum",
                            "mean_value",
                        )
                    )
                    or row.get("visits") != 0
                ):
                    raise T113ConvergenceError(
                        "configuration-excluded occurrence acquired numeric Search data"
                    )
                excluded.append(ordinal)
                continue
            edge = row.get("search_equivalence_source_edge_index")
            if isinstance(edge, bool) or not isinstance(edge, int) or edge < 0:
                raise T113ConvergenceError("searched occurrence lacks its source edge")
            _finite(row.get("mean_value"), "searched mean_value")
            _finite(row.get("evaluation_sum"), "searched evaluation_sum")
            visits = row.get("visits")
            if isinstance(visits, bool) or not isinstance(visits, int) or visits <= 0:
                raise T113ConvergenceError("searched occurrence is not visited")
            by_edge[edge].append(ordinal)
            searched_occurrences += 1
        partition = tuple(
            (edge, tuple(ordinals))
            for edge, ordinals in sorted(by_edge.items(), key=lambda item: min(item[1]))
        )
        classifications_tuple = tuple(classifications)
        excluded_tuple = tuple(excluded)
        if not partition:
            raise T113ConvergenceError("configured Search domain has no searched class")
        if reference_classifications is None:
            reference_classifications = classifications_tuple
            reference_partition = partition
            reference_excluded = excluded_tuple
            class_values = {edge: [] for edge, _ordinals in partition}
        elif (
            classifications_tuple != reference_classifications
            or partition != reference_partition
            or excluded_tuple != reference_excluded
        ):
            raise T113ConvergenceError(
                "searched/excluded occurrence or class partition drifted across particles"
            )
        assert reference_partition is not None
        for edge, ordinals in reference_partition:
            member_values = [
                _finite(rows[ordinal].get("mean_value"), "searched mean_value")
                for ordinal in ordinals
            ]
            if any(value != member_values[0] for value in member_values[1:]):
                raise T113ConvergenceError(
                    "duplicate searched occurrences disagree on their native source edge value"
                )
            class_values[edge].append(member_values[0])
        searched_counts.append(searched_occurrences)
        excluded_counts.append(len(excluded))
        if particle.get("particle_index") != particle_index:
            raise T113ConvergenceError(
                "particle rows are not zero-based ordered prefixes"
            )
    if reference_classifications is None or reference_partition is None:
        raise T113ConvergenceError("bridge has no particles")
    return {
        "classification_by_public_ordinal": list(reference_classifications),
        "decision_class_partition": [
            {"source_edge_index": edge, "public_action_ordinals": list(ordinals)}
            for edge, ordinals in reference_partition
        ],
        "excluded_public_action_ordinals": list(reference_excluded or ()),
        "searched_occurrence_count_per_particle": searched_counts,
        "configuration_excluded_occurrence_count_per_particle": excluded_counts,
        "class_particle_values": {
            edge: values for edge, values in sorted(class_values.items())
        },
    }


def validate_t113_bridge_report(
    value: object,
    *,
    particle_count: int,
    expected_sampler_seed: int,
) -> dict[str, Any]:
    """Strictly accept one current T110 v2 report under the T113 config.

    The bridge-level input seed is checked against the preregistered T101
    derivation.  Per-particle sampler seeds are retained as native metadata and
    are intentionally not compared with that bridge input.
    """

    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != "native-battle-public-particle-search-v2"
    ):
        raise T113ConvergenceError("T113 requires the strict T110 v2 bridge schema")
    if particle_count not in T101_COUNTS:
        raise T113ConvergenceError("T113 particle count is outside 2/4/8/16/32")
    if (
        isinstance(expected_sampler_seed, bool)
        or not isinstance(expected_sampler_seed, int)
        or not 0 <= expected_sampler_seed < 2**64
    ):
        raise T113ConvergenceError("expected bridge input seed is invalid")
    try:
        validated = validate_t099_particle_search_bridge(value)
        configured_view = validate_t111_configured_search_report(
            validated,
            expected_sampler_seed=expected_sampler_seed,
            particle_count=particle_count,
        )
    except (T099ParticleSearchBridgeError, T111ConfiguredSearchError) as exc:
        raise T113ConvergenceError(
            "T110/T111 strict configured-domain validation failed"
        ) from exc
    if (
        validated.get("particle_start") != 0
        or validated.get("particle_count") != particle_count
        or validated.get("search_simulations") != T101_SEARCH_SIMULATIONS
        or validated.get("include_potions") is not False
        or validated.get("sampler_seed_input") != expected_sampler_seed
    ):
        raise T113ConvergenceError("bridge report differs from frozen T113 settings")
    seeds = _native_seed_metadata(validated, expected_count=particle_count)
    domain = _configured_domain_view(validated)
    if len(domain["classification_by_public_ordinal"]) != configured_view.get(
        "public_action_count"
    ) or domain["decision_class_partition"] != [
        {
            "source_edge_index": min(
                int(
                    validated["particles"][0]["root_rows"][ordinal][
                        "search_equivalence_source_edge_index"
                    ]
                )
                for ordinal in item["public_action_ordinals"]
            ),
            "public_action_ordinals": item["public_action_ordinals"],
        }
        for item in configured_view["configured_search_decision_classes"]
    ]:
        raise T113ConvergenceError(
            "T111 and T113 configured-domain partitions disagree"
        )
    return {
        **validated,
        "t113_configured_domain": domain,
        "t113_native_particle_seed_metadata": seeds,
        "t113_bridge_report_sha256": _canonical_sha256(validated),
    }


def _class_values_from_validated(
    report: Mapping[str, Any],
) -> tuple[list[str], list[list[float]], tuple[tuple[int, tuple[int, ...]], ...]]:
    domain = report.get("t113_configured_domain")
    values_map = (
        domain.get("class_particle_values") if isinstance(domain, Mapping) else None
    )
    partition_rows = (
        domain.get("decision_class_partition") if isinstance(domain, Mapping) else None
    )
    if not isinstance(values_map, Mapping) or not isinstance(partition_rows, list):
        raise T113ConvergenceError("validated searched-domain values are missing")
    partition: list[tuple[int, tuple[int, ...]]] = []
    class_ids: list[str] = []
    values: list[list[float]] = []
    for row in partition_rows:
        if not isinstance(row, Mapping):
            raise T113ConvergenceError("configured decision class is malformed")
        edge = _nonnegative_int(row.get("source_edge_index"), "source edge")
        ordinals = row.get("public_action_ordinals")
        if (
            not isinstance(ordinals, list)
            or not ordinals
            or any(
                isinstance(ordinal, bool) or not isinstance(ordinal, int)
                for ordinal in ordinals
            )
        ):
            raise T113ConvergenceError("configured decision class ordinals are invalid")
        raw_values = values_map.get(edge)
        if not isinstance(raw_values, list) or len(raw_values) != 32:
            raise T113ConvergenceError(
                "configured class has incomplete particle support"
            )
        partition.append((edge, tuple(ordinals)))
        class_ids.append(f"search-edge:{edge}")
        values.append(
            [_finite(value, "searched class particle value") for value in raw_values]
        )
    return class_ids, values, tuple(partition)


def analyze_t113_batch(
    value: object, *, expected_sampler_seed: int
) -> dict[str, object]:
    """Compute T101 nested-prefix metrics over searched classes only."""

    report = validate_t113_bridge_report(
        value, particle_count=32, expected_sampler_seed=expected_sampler_seed
    )
    class_ids, class_values, partition = _class_values_from_validated(report)
    prefixes = {
        count: _prefix_metrics(class_ids, class_values, count) for count in T101_COUNTS
    }
    reference_means = prefixes[32][1]
    reference_best = prefixes[32][2]
    domain = report["t113_configured_domain"]
    excluded_ordinals = list(domain["excluded_public_action_ordinals"])
    metrics: list[dict[str, object]] = []
    for count in T101_COUNTS:
        classes, means, best = prefixes[count]
        opportunity_gap = max(reference_means.values()) - max(
            reference_means[class_id] for class_id in best
        )
        metrics.append(
            {
                "particle_count": count,
                "decision_classes": classes,
                "best_decision_class_set": best,
                "searched_decision_class_count": len(class_ids),
                "configuration_excluded_public_occurrence_count": len(
                    excluded_ordinals
                ),
                "configuration_excluded_public_action_ordinals": excluded_ordinals,
                "best_set_exact_agreement_with_n32": best == reference_best,
                "reference_proxy_opportunity_gap": opportunity_gap,
                "maximum_absolute_class_mean_drift_from_n32": max(
                    abs(means[class_id] - reference_means[class_id])
                    for class_id in class_ids
                ),
                "rank_agreement_with_n32": (
                    _pairwise_rank_agreement(means, reference_means)
                    if len(class_ids) >= 2
                    else None
                ),
                "rank_agreement_statistic": T101_RANK_STATISTIC,
            }
        )
    classifications = list(domain["classification_by_public_ordinal"])
    work_prefixes = {
        str(count): {
            "sums": _work_counter_sums(report["particles"][:count]),
            "distributions": _work_counter_distributions(report["particles"][:count]),
        }
        for count in T101_COUNTS
    }
    return {
        "schema_id": "t113-state-replicate-convergence-v1",
        "value_semantics": T101_VALUE_SEMANTICS,
        "source_value_semantics": T099_VALUE_SEMANTICS,
        "bridge_sampler_seed_input": report["sampler_seed_input"],
        "native_particle_sampler_seed_metadata": report[
            "t113_native_particle_seed_metadata"
        ],
        "particle_counts": list(T101_COUNTS),
        "decision_class_partition": [
            {
                "decision_class_id": f"search-edge:{edge}",
                "source_edge_index": edge,
                "public_action_ordinals": list(ordinals),
            }
            for edge, ordinals in partition
        ],
        "public_occurrence_classification_by_ordinal": [
            {"public_action_ordinal": ordinal, "classification": classification}
            for ordinal, classification in enumerate(classifications)
        ],
        "ordered_public_legal_actions": report["anchor_ordered_public_legal_actions"],
        "public_information_projection": report["anchor_public_information_projection"],
        "configuration_excluded_public_action_ordinals": excluded_ordinals,
        "configuration_excluded_public_occurrence_count": len(excluded_ordinals),
        "per_occurrence_rows_retained": True,
        "hidden_future_fingerprints": [
            particle["hidden_future_fingerprint"] for particle in report["particles"]
        ],
        "bridge_report_sha256": report["t113_bridge_report_sha256"],
        "native_work_counter_prefixes": work_prefixes,
        "metrics": metrics,
    }


def validate_t113_canary_ladder(value: object) -> dict[str, object]:
    """Prove the direct N=2/4/8/16 reports are semantic N=32 prefixes."""

    if not isinstance(value, Mapping):
        raise T113ConvergenceError("canary ladder is missing")
    identity = _identity(value.get("selection_identity"))
    stratum = value.get("stratum")
    replicate = value.get("replicate_index")
    if (
        stratum not in T101_SOURCE_COUNTS
        or isinstance(replicate, bool)
        or not isinstance(replicate, int)
        or replicate != 0
    ):
        raise T113ConvergenceError(
            "T113 canary must use one A/B/C state at replicate 0"
        )
    seed = derive_t101_sampler_seed(identity, 0)
    calls = value.get("calls")
    if not isinstance(calls, Mapping):
        raise T113ConvergenceError("T113 canary direct calls are missing")
    reports: dict[int, dict[str, Any]] = {}
    raw_reports: dict[int, object] = {}
    elapsed: dict[int, float] = {}
    runtime: dict[int, dict[str, object]] = {}
    for count in T101_COUNTS:
        call = calls.get(str(count), calls.get(count))
        if not isinstance(call, Mapping):
            raise T113ConvergenceError(f"direct canary N={count} result is missing")
        reports[count] = validate_t113_bridge_report(
            call.get("bridge_report"),
            particle_count=count,
            expected_sampler_seed=seed,
        )
        raw_reports[count] = call.get("bridge_report")
        wall = _finite(call.get("wall_clock_time_s"), "canary wall time")
        if wall < 0:
            raise T113ConvergenceError("canary wall time must be non-negative")
        worker = call.get("worker_id")
        if (
            not isinstance(worker, str)
            or not worker
            or call.get("shard_index") != 0
            or call.get("effective_concurrency") != 1
            or call.get("failure_retry_status") != "success_no_retry"
            or not isinstance(call.get("single_worker_reason"), str)
            or not call.get("single_worker_reason")
        ):
            raise T113ConvergenceError("canary runtime provenance is incomplete")
        elapsed[count] = wall
        runtime[count] = {
            "worker_id": worker,
            "shard_index": 0,
            "effective_concurrency": 1,
            "failure_retry_status": "success_no_retry",
            "single_worker_reason": call["single_worker_reason"],
        }
    reference = reports[32]
    for count in T101_COUNTS[:-1]:
        direct = reports[count]
        for field in (
            "sampler_seed_input",
            "anchor_public_information_projection",
            "anchor_ordered_public_legal_actions",
            "semantic_boundary",
        ):
            if direct[field] != reference[field]:
                raise T113ConvergenceError(
                    f"direct canary N={count} differs on {field}"
                )
        if direct["particles"] != reference["particles"][:count]:
            raise T113ConvergenceError(
                f"direct canary N={count} is not the exact semantic N=32 prefix"
            )
        direct_domain = direct["t113_configured_domain"]
        reference_domain = reference["t113_configured_domain"]
        if (
            direct_domain["classification_by_public_ordinal"]
            != reference_domain["classification_by_public_ordinal"]
            or direct_domain["decision_class_partition"]
            != reference_domain["decision_class_partition"]
            or direct_domain["excluded_public_action_ordinals"]
            != reference_domain["excluded_public_action_ordinals"]
        ):
            raise T113ConvergenceError(
                f"direct canary N={count} configured decision domain drifted"
            )
    n2, n32 = elapsed[2], elapsed[32]
    return {
        "schema_id": T113_CANARY_LADDER_SCHEMA,
        "selection_identity": identity,
        "stratum": stratum,
        "replicate_index": 0,
        "sampler_seed_input": seed,
        "direct_prefix_equivalence": True,
        "direct_wall_clock_time_s": {str(k): elapsed[k] for k in T101_COUNTS},
        "n2_to_n32_wall_clock_ratio": n32 / n2 if n2 > 0 else None,
        "direct_runtime_provenance": {str(k): runtime[k] for k in T101_COUNTS},
        "direct_bridge_reports": {
            str(count): raw_reports[count] for count in T101_COUNTS
        },
        "direct_work_counters": {
            str(count): [
                particle["root_evaluation"]["work_counters"]
                for particle in reports[count]["particles"]
            ]
            for count in T101_COUNTS
        },
        "direct_work_counter_sums": {
            str(count): _work_counter_sums(reports[count]["particles"])
            for count in T101_COUNTS
        },
        "direct_work_counter_distributions": {
            str(count): _work_counter_distributions(reports[count]["particles"])
            for count in T101_COUNTS
        },
        "n32_bridge_report_sha256": reference["t113_bridge_report_sha256"],
    }


def validate_t113_canary_evidence(
    value: object, *, cohort_manifest: Mapping[str, object]
) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != T113_CANARY_EVIDENCE_SCHEMA
    ):
        raise T113ConvergenceError("T113 canary evidence schema mismatch")
    cohort = validate_t113_fixed_cohort(cohort_manifest)
    if (
        value.get("task_id") != T113_TASK_ID
        or not isinstance(value.get("implementation_head"), str)
        or len(str(value.get("implementation_head"))) != 40
        or any(
            char not in "0123456789abcdef"
            for char in str(value.get("implementation_head"))
        )
        or value.get("native_identity") != T113_NATIVE_IDENTITY
        or value.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
        or value.get("complete") is not True
        or value.get("direct_prefix_equivalence") is not True
        or value.get("cohort_manifest_sha256") != _canonical_sha256(cohort_manifest)
    ):
        raise T113ConvergenceError("T113 canary completion/cohort binding is invalid")
    selected = cohort["selected"]
    expected: list[tuple[str, str]] = []
    for stratum in T101_SOURCE_COUNTS:
        row = next(row for row in selected if row["stratum"] == stratum)
        expected.append((str(row["selection_identity"]), stratum))
    ladders = value.get("ladders")
    if not isinstance(ladders, list) or len(ladders) != 3:
        raise T113ConvergenceError(
            "T113 canary must contain exactly three state ladders"
        )
    checked: list[dict[str, object]] = []
    for ladder, (identity, stratum) in zip(ladders, expected, strict=True):
        if not isinstance(ladder, Mapping):
            raise T113ConvergenceError("T113 canary ladder row is malformed")
        ladder_input = ladder
        if "calls" not in ladder:
            direct_reports = ladder.get("direct_bridge_reports")
            direct_wall = ladder.get("direct_wall_clock_time_s")
            direct_runtime = ladder.get("direct_runtime_provenance")
            if not all(
                isinstance(item, Mapping)
                for item in (direct_reports, direct_wall, direct_runtime)
            ):
                raise T113ConvergenceError("retained T113 canary ladder is malformed")
            calls: dict[str, object] = {}
            for count in T101_COUNTS:
                report = direct_reports.get(str(count))
                wall = direct_wall.get(str(count))
                metadata = direct_runtime.get(str(count))
                if not isinstance(report, Mapping) or not isinstance(metadata, Mapping):
                    raise T113ConvergenceError(
                        "retained T113 direct-call evidence is incomplete"
                    )
                calls[str(count)] = {
                    "bridge_report": report,
                    "wall_clock_time_s": wall,
                    **dict(metadata),
                }
            ladder_input = {
                "selection_identity": ladder.get("selection_identity"),
                "stratum": ladder.get("stratum"),
                "replicate_index": ladder.get("replicate_index"),
                "calls": calls,
            }
        validated = validate_t113_canary_ladder(ladder_input)
        if (
            validated["selection_identity"] != identity
            or validated["stratum"] != stratum
        ):
            raise T113ConvergenceError(
                "T113 canary state differs from first retained cohort row"
            )
        checked.append(validated)
    return {
        "schema_id": T113_CANARY_EVIDENCE_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": value.get("implementation_head"),
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "complete": True,
        "direct_prefix_equivalence": True,
        "cohort_manifest_sha256": _canonical_sha256(cohort_manifest),
        "ladders": checked,
    }


def build_t113_canary_evidence(
    ladders: Sequence[Mapping[str, object]],
    *,
    cohort_manifest: Mapping[str, object],
    implementation_head: str,
) -> dict[str, object]:
    """Validate the exact three-state ladder without launching native work."""

    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(char not in "0123456789abcdef" for char in implementation_head)
    ):
        raise T113ConvergenceError("T113 canary implementation head is invalid")
    cohort = validate_t113_fixed_cohort(cohort_manifest)
    initial: list[tuple[str, str]] = []
    selected = cohort["selected"]
    for stratum in T101_SOURCE_COUNTS:
        first = next(row for row in selected if row["stratum"] == stratum)
        initial.append((str(first["selection_identity"]), stratum))
    if len(ladders) != 3:
        raise T113ConvergenceError("T113 canary requires exactly three direct ladders")
    checked_ladders: list[dict[str, object]] = []
    for ladder, (identity, stratum) in zip(ladders, initial, strict=True):
        checked = validate_t113_canary_ladder(ladder)
        if checked["selection_identity"] != identity or checked["stratum"] != stratum:
            raise T113ConvergenceError(
                "canary identities differ from first T112 A/B/C states"
            )
        checked_ladders.append(checked)
    candidate = {
        "schema_id": T113_CANARY_EVIDENCE_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": implementation_head,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "complete": True,
        "direct_prefix_equivalence": True,
        "cohort_manifest_sha256": _canonical_sha256(cohort_manifest),
        "ladders": checked_ladders,
    }
    return validate_t113_canary_evidence(candidate, cohort_manifest=cohort_manifest)


def build_t113_fixed_cohort(
    value: object,
    *,
    source_cohort_sha256: str,
    source_population_binding: Mapping[str, object],
    t112_artifact_binding: Mapping[str, object],
) -> dict[str, object]:
    """Create a non-selecting T113 view of the accepted T112 identities."""

    if source_cohort_sha256 != T113_EXACT_T112_COHORT_SHA256:
        raise T113ConvergenceError(
            "T112 cohort artifact hash is not the accepted identity"
        )
    population_required = {
        "t101_terminal_retention_manifest_sha256",
        "t101_input_admission_sha256",
        "ordered_identity_binding_sha256",
        "record_count",
        "source_counts",
        "historical_t101_attempt_order_exact",
        "t101_retained_reference_count_verified",
    }
    if (
        set(source_population_binding) != population_required
        or source_population_binding.get("record_count") != 413
        or source_population_binding.get("source_counts") != T101_SOURCE_COUNTS
        or source_population_binding.get("historical_t101_attempt_order_exact")
        is not True
    ):
        raise T113ConvergenceError(
            "T113 source-population provenance binding is incomplete"
        )
    _sha256_text(
        source_population_binding.get("t101_terminal_retention_manifest_sha256"),
        "T101 retention manifest SHA-256",
    )
    _sha256_text(
        source_population_binding.get("t101_input_admission_sha256"),
        "T101 input admission SHA-256",
    )
    _sha256_text(
        source_population_binding.get("ordered_identity_binding_sha256"),
        "ordered source identity binding SHA-256",
    )
    if (
        isinstance(
            source_population_binding.get("t101_retained_reference_count_verified"),
            bool,
        )
        or not isinstance(
            source_population_binding.get("t101_retained_reference_count_verified"), int
        )
        or source_population_binding["t101_retained_reference_count_verified"] <= 0
    ):
        raise T113ConvergenceError(
            "T101 retained artifact references were not qualified"
        )
    if set(t112_artifact_binding) != {
        "retention_manifest_sha256",
        "cohort_admission",
        "final_report",
        "input_qualification",
    }:
        raise T113ConvergenceError("T112 artifact binding is incomplete")
    _sha256_text(
        t112_artifact_binding.get("retention_manifest_sha256"), "T112 retention SHA-256"
    )
    for name, expected_sha in (
        ("cohort_admission", T113_EXACT_T112_COHORT_SHA256),
        ("final_report", T113_EXACT_T112_FINAL_REPORT_SHA256),
    ):
        reference = t112_artifact_binding.get(name)
        if (
            not isinstance(reference, Mapping)
            or reference.get("sha256") != expected_sha
        ):
            raise T113ConvergenceError(
                f"T112 {name} identity is not the accepted artifact"
            )
    qualification_ref = t112_artifact_binding.get("input_qualification")
    if not isinstance(qualification_ref, Mapping):
        raise T113ConvergenceError("T112 input qualification reference is malformed")
    _sha256_text(qualification_ref.get("sha256"), "T112 input qualification SHA-256")
    try:
        t112 = validate_t112_cohort(value)
    except T112RecoveryError as exc:
        raise T113ConvergenceError(
            "accepted T112 cohort failed strict validation"
        ) from exc
    if (
        t112.get("terminal_classification")
        != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
        or t112.get("selected_counts") != {"A": 8, "B": 8, "C": 8}
        or t112.get("native_identity") != T113_NATIVE_IDENTITY
    ):
        raise T113ConvergenceError(
            "T112 cohort is not the exact accepted 8/8/8 support"
        )
    selected = t112.get("selected")
    if not isinstance(selected, list) or len(selected) != T101_FORMAL_STATE_COUNT:
        raise T113ConvergenceError("T112 selected cohort is not exactly 24 identities")
    copied: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in selected:
        if not isinstance(row, Mapping):
            raise T113ConvergenceError("T112 selected identity row is malformed")
        identity = _identity(row.get("selection_identity"))
        stratum = row.get("stratum")
        if stratum not in T101_SOURCE_COUNTS or identity in seen:
            raise T113ConvergenceError("T112 selected identity or stratum is invalid")
        seen.add(identity)
        copied.append(
            {
                "selection_identity": identity,
                "stratum": stratum,
                "selection_digest": row.get("selection_digest"),
                "t112_replicate_zero_sampler_seed_input": row.get("sampler_seed_input"),
                "t112_admission_bridge_report_sha256": next(
                    attempt.get("bridge_report_sha256")
                    for attempt in t112["attempted"]
                    if attempt.get("selection_identity") == identity
                ),
                "source_ordinal": next(
                    attempt.get("source_ordinal")
                    for attempt in t112["attempted"]
                    if attempt.get("selection_identity") == identity
                ),
            }
        )
    counts = Counter(row["stratum"] for row in copied)
    if counts != Counter({"A": 8, "B": 8, "C": 8}):
        raise T113ConvergenceError("T112 admitted cohort is not 8/8/8")
    return {
        "schema_id": T113_COHORT_SCHEMA,
        "task_id": T113_TASK_ID,
        "source_t112_cohort_schema": T113_T112_COHORT_SCHEMA,
        "source_t112_cohort_sha256": T113_EXACT_T112_COHORT_SHA256,
        "selection_performed": False,
        "replacement_or_backfill_performed": False,
        "selected_counts": {key: counts[key] for key in T101_SOURCE_COUNTS},
        "selected": copied,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "source_population_binding": dict(source_population_binding),
        "t112_artifact_binding": dict(t112_artifact_binding),
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "replicates": T101_REPLICATES,
        "particle_counts": list(T101_COUNTS),
    }


def validate_t113_fixed_cohort(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_id") != T113_COHORT_SCHEMA:
        raise T113ConvergenceError("T113 fixed cohort schema mismatch")
    if (
        value.get("task_id") != T113_TASK_ID
        or value.get("source_t112_cohort_schema") != T113_T112_COHORT_SCHEMA
        or value.get("source_t112_cohort_sha256") != T113_EXACT_T112_COHORT_SHA256
        or value.get("selection_performed") is not False
        or value.get("replacement_or_backfill_performed") is not False
        or value.get("selected_counts") != {"A": 8, "B": 8, "C": 8}
        or value.get("native_identity") != T113_NATIVE_IDENTITY
        or value.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
        or value.get("replicates") != T101_REPLICATES
        or value.get("particle_counts") != list(T101_COUNTS)
        or not isinstance(value.get("source_population_binding"), Mapping)
        or not isinstance(value.get("t112_artifact_binding"), Mapping)
    ):
        raise T113ConvergenceError("T113 fixed cohort binding/configuration changed")
    selected = value.get("selected")
    if not isinstance(selected, list) or len(selected) != T101_FORMAL_STATE_COUNT:
        raise T113ConvergenceError("T113 fixed cohort must have exactly 24 rows")
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    last_stratum_index = -1
    previous_ordinal: dict[str, int] = {}
    for row in selected:
        if not isinstance(row, Mapping):
            raise T113ConvergenceError("T113 fixed cohort row is malformed")
        identity = _identity(row.get("selection_identity"))
        stratum = row.get("stratum")
        ordinal = row.get("source_ordinal")
        digest = row.get("selection_digest")
        if (
            stratum not in T101_SOURCE_COUNTS
            or identity in ids
            or digest != hashlib.sha256(identity.encode("utf-8")).hexdigest()
            or row.get("t112_replicate_zero_sampler_seed_input")
            != derive_t101_sampler_seed(identity, 0)
            or not isinstance(row.get("t112_admission_bridge_report_sha256"), str)
            or len(str(row.get("t112_admission_bridge_report_sha256"))) != 64
            or any(
                char not in "0123456789abcdef"
                for char in str(row.get("t112_admission_bridge_report_sha256"))
            )
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal < 0
            or ordinal <= previous_ordinal.get(str(stratum), -1)
        ):
            raise T113ConvergenceError("T113 fixed identity/order is invalid")
        index = list(T101_SOURCE_COUNTS).index(stratum)
        if index < last_stratum_index:
            raise T113ConvergenceError("T112 selected order is not A/B/C stratum order")
        last_stratum_index = index
        previous_ordinal[str(stratum)] = ordinal
        ids.add(identity)
        counts[stratum] += 1
    if counts != Counter({"A": 8, "B": 8, "C": 8}):
        raise T113ConvergenceError("T113 fixed cohort is not balanced 8/8/8")
    population = value["source_population_binding"]
    artifacts = value["t112_artifact_binding"]
    if (
        population.get("record_count") != 413
        or population.get("source_counts") != T101_SOURCE_COUNTS
        or population.get("historical_t101_attempt_order_exact") is not True
        or artifacts.get("retention_manifest_sha256")
        != T113_EXACT_T112_RETENTION_SHA256
        or not isinstance(artifacts.get("cohort_admission"), Mapping)
        or artifacts["cohort_admission"].get("sha256") != T113_EXACT_T112_COHORT_SHA256
        or not isinstance(artifacts.get("final_report"), Mapping)
        or artifacts["final_report"].get("sha256")
        != T113_EXACT_T112_FINAL_REPORT_SHA256
    ):
        raise T113ConvergenceError(
            "T113 fixed cohort lost its source or T112 artifact binding"
        )
    for name in (
        "t101_terminal_retention_manifest_sha256",
        "t101_input_admission_sha256",
        "ordered_identity_binding_sha256",
    ):
        _sha256_text(population.get(name), name)
    return dict(value)


def build_t113_formal_plan(
    cohort_manifest: Mapping[str, object],
    *,
    implementation_head: str,
    input_qualification_sha256: str,
    fixed_cohort_sha256: str,
    max_effective_concurrency: int = 4,
) -> dict[str, object]:
    """Build the exact 96-job plan without granting execution authority."""

    cohort = validate_t113_fixed_cohort(cohort_manifest)
    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(ch not in "0123456789abcdef" for ch in implementation_head)
        or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
            for digest in (input_qualification_sha256, fixed_cohort_sha256)
        )
        or fixed_cohort_sha256 != _canonical_sha256(cohort_manifest)
        or isinstance(max_effective_concurrency, bool)
        or not isinstance(max_effective_concurrency, int)
        or not 1 <= max_effective_concurrency <= 4
    ):
        raise T113ConvergenceError("T113 formal plan binding is invalid")
    jobs: list[dict[str, object]] = []
    state_order = [
        {
            "state_ordinal": index,
            "selection_identity": row["selection_identity"],
            "stratum": row["stratum"],
        }
        for index, row in enumerate(cohort["selected"])
    ]
    for state_ordinal, state in enumerate(cohort["selected"]):
        for replicate in range(T101_REPLICATES):
            identity = str(state["selection_identity"])
            jobs.append(
                {
                    "job_ordinal": len(jobs),
                    "state_ordinal": state_ordinal,
                    "selection_identity": identity,
                    "stratum": state["stratum"],
                    "replicate_index": replicate,
                    "sampler_seed_input": derive_t101_sampler_seed(identity, replicate),
                    "particle_start": 0,
                    "particle_count": 32,
                    "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                    "include_potions": False,
                    "output_name": f"job-{len(jobs):03d}.json",
                }
            )
    return {
        "schema_id": T113_FORMAL_PLAN_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": implementation_head,
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "input_qualification_sha256": input_qualification_sha256,
        "fixed_cohort_sha256": fixed_cohort_sha256,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "particle_counts": list(T101_COUNTS),
        "replicate_count": T101_REPLICATES,
        "jobs": jobs,
        "state_order": state_order,
        "execution_topology": {
            "default_max_effective_concurrency": 4,
            "prepared_max_effective_concurrency": max_effective_concurrency,
            "measured_resource_evidence_required_before_execution": True,
        },
        "execution_authorized": False,
        "canary_authorized": False,
        "automatic_particle_escalation": False,
    }


def validate_t113_formal_plan(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != T113_FORMAL_PLAN_SCHEMA
    ):
        raise T113ConvergenceError("T113 formal plan schema mismatch")
    if (
        value.get("task_id") != T113_TASK_ID
        or value.get("approved_spec_commit") != T113_APPROVED_SPEC_COMMIT
        or value.get("native_identity") != T113_NATIVE_IDENTITY
        or value.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
        or value.get("particle_counts") != list(T101_COUNTS)
        or value.get("replicate_count") != T101_REPLICATES
        or value.get("execution_authorized") is not False
        or value.get("canary_authorized") is not False
        or value.get("automatic_particle_escalation") is not False
    ):
        raise T113ConvergenceError("T113 plan scope/configuration changed")
    for field in ("input_qualification_sha256", "fixed_cohort_sha256"):
        _sha256_text(value.get(field), field)
    if (
        not isinstance(value.get("implementation_head"), str)
        or len(value["implementation_head"]) != 40
    ):
        raise T113ConvergenceError("T113 plan implementation head is invalid")
    state_order = value.get("state_order")
    if not isinstance(state_order, list) or len(state_order) != T101_FORMAL_STATE_COUNT:
        raise T113ConvergenceError(
            "T113 state order must contain the fixed 24 identities"
        )
    state_by_ordinal: dict[int, tuple[str, str]] = {}
    for ordinal, row in enumerate(state_order):
        if not isinstance(row, Mapping):
            raise T113ConvergenceError("T113 state order row is malformed")
        identity = _identity(row.get("selection_identity"))
        stratum = row.get("stratum")
        if (
            row.get("state_ordinal") != ordinal
            or stratum not in T101_SOURCE_COUNTS
            or ordinal in state_by_ordinal
        ):
            raise T113ConvergenceError("T113 state order identity/stratum is invalid")
        state_by_ordinal[ordinal] = (identity, stratum)
    jobs = value.get("jobs")
    if (
        not isinstance(jobs, list)
        or len(jobs) != T101_FORMAL_STATE_COUNT * T101_REPLICATES
    ):
        raise T113ConvergenceError("T113 plan must contain exactly 96 jobs")
    matrix: set[tuple[str, int]] = set()
    identities_by_ordinal: dict[int, tuple[str, str]] = {}
    per_state_replicates: dict[str, set[int]] = defaultdict(set)
    for ordinal, job in enumerate(jobs):
        if not isinstance(job, Mapping):
            raise T113ConvergenceError("T113 formal job is malformed")
        identity = _identity(job.get("selection_identity"))
        replicate = job.get("replicate_index")
        state_ordinal = job.get("state_ordinal")
        stratum = job.get("stratum")
        key = (identity, replicate)
        if (
            isinstance(replicate, bool)
            or not isinstance(replicate, int)
            or replicate not in range(T101_REPLICATES)
            or isinstance(state_ordinal, bool)
            or not isinstance(state_ordinal, int)
            or state_ordinal not in range(T101_FORMAL_STATE_COUNT)
            or stratum not in T101_SOURCE_COUNTS
            or job.get("job_ordinal") != ordinal
            or job.get("sampler_seed_input")
            != derive_t101_sampler_seed(identity, replicate)
            or isinstance(job.get("sampler_seed_input"), bool)
            or job.get("particle_start") != 0
            or job.get("particle_count") != 32
            or job.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
            or job.get("include_potions") is not False
            or job.get("output_name") != f"job-{ordinal:03d}.json"
            or key in matrix
            or state_by_ordinal.get(state_ordinal) != (identity, stratum)
        ):
            raise T113ConvergenceError("T113 formal job seed/configuration changed")
        prior_state = identities_by_ordinal.setdefault(
            state_ordinal, (identity, stratum)
        )
        if prior_state != (identity, stratum):
            raise T113ConvergenceError(
                "T113 state ordinal points to multiple identities"
            )
        matrix.add(key)
        per_state_replicates[identity].add(replicate)
    if (
        len(identities_by_ordinal) != T101_FORMAL_STATE_COUNT
        or len(per_state_replicates) != T101_FORMAL_STATE_COUNT
        or any(
            values != set(range(T101_REPLICATES))
            for values in per_state_replicates.values()
        )
        or Counter(
            stratum for _identity_value, stratum in identities_by_ordinal.values()
        )
        != Counter({"A": 8, "B": 8, "C": 8})
    ):
        raise T113ConvergenceError("T113 formal matrix is not exact 24 x 4")
    topology = value.get("execution_topology")
    if (
        not isinstance(topology, Mapping)
        or topology.get("default_max_effective_concurrency") != 4
        or isinstance(topology.get("prepared_max_effective_concurrency"), bool)
        or not isinstance(topology.get("prepared_max_effective_concurrency"), int)
        or not 1 <= topology["prepared_max_effective_concurrency"] <= 4
        or topology.get("measured_resource_evidence_required_before_execution")
        is not True
    ):
        raise T113ConvergenceError("T113 resource topology is invalid")
    return dict(value)


def validate_t113_formal_rows(
    rows: Iterable[Mapping[str, object]], plan: Mapping[str, object]
) -> list[dict[str, object]]:
    checked_plan = validate_t113_formal_plan(plan)
    jobs = checked_plan["jobs"]
    assert isinstance(jobs, list)
    expected = {
        (job["selection_identity"], job["replicate_index"]): job for job in jobs
    }
    results = [dict(row) for row in rows]
    observed: set[tuple[object, object]] = set()
    max_concurrency = checked_plan["execution_topology"][
        "prepared_max_effective_concurrency"
    ]
    for row in results:
        key = (row.get("selection_identity"), row.get("replicate_index"))
        job = expected.get(key)
        if job is None or key in observed:
            raise T113ConvergenceError("T113 formal row is substituted or duplicated")
        if (
            row.get("stratum") != job["stratum"]
            or row.get("job_ordinal") != job["job_ordinal"]
            or row.get("sampler_seed_input") != job["sampler_seed_input"]
            or row.get("native_identity") != T113_NATIVE_IDENTITY
            or row.get("particle_start") != 0
            or row.get("particle_count") != 32
            or row.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
            or row.get("include_potions") is not False
        ):
            raise T113ConvergenceError("T113 formal row identity or config drifted")
        report = validate_t113_bridge_report(
            row.get("bridge_report"),
            particle_count=32,
            expected_sampler_seed=int(job["sampler_seed_input"]),
        )
        wall = _finite(row.get("wall_clock_time_s"), "formal bridge wall time")
        effective = row.get("effective_concurrency")
        if (
            wall < 0
            or not isinstance(row.get("worker_id"), str)
            or not row.get("worker_id")
            or isinstance(effective, bool)
            or not isinstance(effective, int)
            or not 1 <= effective <= max_concurrency
            or isinstance(row.get("shard_index"), bool)
            or not isinstance(row.get("shard_index"), int)
            or row.get("shard_index") < 0
            or row.get("failure_retry_status")
            not in {"success_no_retry", "success_after_operational_retry"}
            or (
                row.get("failure_retry_status") == "success_after_operational_retry"
                and row.get("retry_reason") != "operational_failure_identical_inputs"
            )
            or (
                row.get("failure_retry_status") == "success_no_retry"
                and row.get("retry_reason") is not None
            )
        ):
            raise T113ConvergenceError(
                "T113 formal runtime/retry provenance is invalid"
            )
        if row.get("result_source") != "formal_n32_call":
            raise T113ConvergenceError(
                "T113 formal row source/reuse binding is invalid"
            )
        row["bridge_report"] = report
        observed.add(key)
    if observed != set(expected):
        raise T113ConvergenceError("T113 formal evidence is incomplete")
    return sorted(results, key=lambda row: int(row["job_ordinal"]))


def analyze_t113_formal(
    rows: Iterable[Mapping[str, object]], plan: Mapping[str, object]
) -> dict[str, object]:
    """Analyze the exact 96-job formal matrix over configured searched classes."""

    formal = validate_t113_formal_rows(rows, plan)
    analyses: list[dict[str, object]] = []
    for row in formal:
        analyses.append(
            {
                "selection_identity": row["selection_identity"],
                "stratum": row["stratum"],
                "replicate_index": row["replicate_index"],
                "sampler_seed_input": row["sampler_seed_input"],
                "wall_clock_time_s": row["wall_clock_time_s"],
                "effective_concurrency": row["effective_concurrency"],
                "shard_index": row["shard_index"],
                "result_source": row["result_source"],
                **analyze_t113_batch(
                    row["bridge_report"],
                    expected_sampler_seed=int(row["sampler_seed_input"]),
                ),
            }
        )
    by_state: dict[str, list[dict[str, object]]] = defaultdict(list)
    for analysis in analyses:
        by_state[str(analysis["selection_identity"])].append(analysis)
    replicate_stability: list[dict[str, object]] = []
    unanimous_references: dict[str, list[str]] = {}
    for identity, state_rows in sorted(by_state.items()):
        if len(state_rows) != T101_REPLICATES:
            raise T113ConvergenceError("formal state lacks R=4 sampler replicates")
        state_rows.sort(key=lambda item: int(item["replicate_index"]))
        reference = state_rows[0]
        if any(
            row["decision_class_partition"] != reference["decision_class_partition"]
            or row["ordered_public_legal_actions"]
            != reference["ordered_public_legal_actions"]
            or row["public_information_projection"]
            != reference["public_information_projection"]
            or row["public_occurrence_classification_by_ordinal"]
            != reference["public_occurrence_classification_by_ordinal"]
            for row in state_rows[1:]
        ):
            raise T113ConvergenceError(
                "public projection, public legal surface, or searched partition drifted across replicates"
            )
        n32 = [
            next(metric for metric in row["metrics"] if metric["particle_count"] == 32)
            for row in state_rows
        ]
        best_sets = [list(metric["best_decision_class_set"]) for metric in n32]
        encoded = [json.dumps(items, separators=(",", ":")) for items in best_sets]
        set_counts = Counter(encoded)
        unanimous = len(set_counts) == 1
        if unanimous:
            unanimous_references[identity] = best_sets[0]
        class_means: dict[str, list[float]] = defaultdict(list)
        for metric in n32:
            for class_row in metric["decision_classes"]:
                class_means[str(class_row["decision_class_id"])].append(
                    float(class_row[T101_VALUE_SEMANTICS])
                )
        replicate_stability.append(
            {
                "selection_identity": identity,
                "stratum": state_rows[0]["stratum"],
                "replicate_best_decision_class_sets": best_sets,
                "distinct_best_set_count": len(set_counts),
                "all_four_exactly_identical": unanimous,
                "modal_best_set_share": max(set_counts.values()) / T101_REPLICATES,
                "between_replicate_class_dispersion": [
                    {
                        "decision_class_id": class_id,
                        "sample_standard_deviation": stdev(values),
                        "minimum": min(values),
                        "maximum": max(values),
                    }
                    for class_id, values in sorted(class_means.items())
                ],
            }
        )
    all_unanimous = len(unanimous_references) == T101_FORMAL_STATE_COUNT
    smallest: int | None = None
    if all_unanimous:
        for count in T101_COUNTS:
            if all(
                next(
                    metric
                    for metric in row["metrics"]
                    if metric["particle_count"] == count
                )["best_decision_class_set"]
                == unanimous_references[str(row["selection_identity"])]
                for row in analyses
            ):
                smallest = count
                break

    def summary(label: str, selected: Sequence[dict[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {
            "label": label,
            "state_replicate_count": len(selected),
        }
        for count in T101_COUNTS:
            metrics = [
                next(
                    metric
                    for metric in row["metrics"]
                    if metric["particle_count"] == count
                )
                for row in selected
            ]
            result[str(count)] = {
                "best_set_agreement_count": sum(
                    metric["best_set_exact_agreement_with_n32"] is True
                    for metric in metrics
                ),
                "best_set_agreement_fraction": (
                    sum(
                        metric["best_set_exact_agreement_with_n32"] is True
                        for metric in metrics
                    )
                    / len(metrics)
                    if metrics
                    else None
                ),
                "reference_proxy_opportunity_gap": _distribution(
                    [
                        float(metric["reference_proxy_opportunity_gap"])
                        for metric in metrics
                    ]
                ),
                "maximum_mean_drift": _distribution(
                    [
                        float(metric["maximum_absolute_class_mean_drift_from_n32"])
                        for metric in metrics
                    ]
                ),
                "rank_agreement": _distribution(
                    [
                        float(metric["rank_agreement_with_n32"])
                        for metric in metrics
                        if metric["rank_agreement_with_n32"] is not None
                    ]
                ),
                "searched_class_count": _distribution(
                    [
                        float(metric["searched_decision_class_count"])
                        for metric in metrics
                    ]
                ),
                "configuration_excluded_public_occurrence_count_audit_only": _distribution(
                    [
                        float(metric["configuration_excluded_public_occurrence_count"])
                        for metric in metrics
                    ]
                ),
                "native_work_counter_sums": {
                    key: sum(
                        int(
                            row["native_work_counter_prefixes"][str(count)]["sums"].get(
                                key, 0
                            )
                        )
                        for row in selected
                    )
                    for key in sorted(
                        {
                            counter
                            for row in selected
                            for counter in row["native_work_counter_prefixes"][
                                str(count)
                            ]["sums"]
                        }
                    )
                },
                "native_work_counter_distribution": {
                    key: _distribution(
                        [
                            float(
                                row["native_work_counter_prefixes"][str(count)][
                                    "sums"
                                ].get(key, 0)
                            )
                            for row in selected
                        ]
                    )
                    for key in sorted(
                        {
                            counter
                            for row in selected
                            for counter in row["native_work_counter_prefixes"][
                                str(count)
                            ]["sums"]
                        }
                    )
                },
            }
        ids = {str(row["selection_identity"]) for row in selected}
        stability = [
            row for row in replicate_stability if row["selection_identity"] in ids
        ]
        result["n32_replicate_unanimity_count"] = sum(
            row["all_four_exactly_identical"] is True for row in stability
        )
        result["n32_replicate_unanimity_fraction"] = (
            result["n32_replicate_unanimity_count"] / len(stability)
            if stability
            else None
        )
        result["hidden_fingerprint_diversity"] = _distribution(
            [float(len(set(row["hidden_future_fingerprints"]))) for row in selected]
        )
        return result

    informative = [
        row
        for row in analyses
        if next(metric for metric in row["metrics"] if metric["particle_count"] == 32)[
            "searched_decision_class_count"
        ]
        >= 2
    ]
    summaries = [summary("all", analyses)]
    summaries.extend(
        summary(stratum, [row for row in analyses if row["stratum"] == stratum])
        for stratum in T101_SOURCE_COUNTS
    )
    summaries.append(summary("multi_class_informative", informative))
    total_wall = sum(float(row["wall_clock_time_s"]) for row in formal)
    all_particles = [
        particle for row in formal for particle in row["bridge_report"]["particles"]
    ]
    total_work = _work_counter_sums(all_particles)
    cost_rows: list[dict[str, object]] = []
    for row in formal:
        particles = row["bridge_report"]["particles"]
        cost_rows.append(
            {
                "selection_identity": row["selection_identity"],
                "replicate_index": row["replicate_index"],
                "particle_count": 32,
                "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                "wall_clock_time_s": row["wall_clock_time_s"],
                "effective_concurrency": row["effective_concurrency"],
                "worker_id": row["worker_id"],
                "shard_index": row["shard_index"],
                "result_source": row["result_source"],
                "prefix_work_counter_sums": {
                    str(count): _work_counter_sums(particles[:count])
                    for count in T101_COUNTS
                },
            }
        )
    return {
        "schema_id": T113_CONVERGENCE_SCHEMA,
        "task_id": T113_TASK_ID,
        "value_semantics": T101_VALUE_SEMANTICS,
        "source_value_semantics": T099_VALUE_SEMANTICS,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "particle_counts": list(T101_COUNTS),
        "replicate_count": T101_REPLICATES,
        "state_replicates": analyses,
        "across_sampler_replicates": replicate_stability,
        "cohort_summaries": summaries,
        "n32_reference_unanimous_all_states": all_unanimous,
        "smallest_uniform_prefix_n": smallest,
        "terminal_classification": (
            T113_STABILITY_OBSERVED
            if all_unanimous and smallest is not None
            else T113_STABILITY_NOT_ESTABLISHED
        ),
        "cost_report": {
            "schema_id": T113_COST_SCHEMA,
            "formal_call_count": len(formal),
            "formal_particle_count": len(all_particles),
            "formal_search_continuation_count": len(all_particles),
            "total_observed_formal_wall_clock_time_s": total_wall,
            "maximum_effective_concurrency": max(
                int(row["effective_concurrency"]) for row in formal
            ),
            "total_native_work_counter_sums": total_work,
            "formal_calls": cost_rows,
        },
    }


def build_t113_cost_report(
    rows: Iterable[Mapping[str, object]],
    plan: Mapping[str, object],
    *,
    canary_evidence: Mapping[str, object],
    cohort_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Combine observed formal cost with direct canary N=2..32 scaling."""

    formal = validate_t113_formal_rows(rows, plan)
    canary = validate_t113_canary_evidence(
        canary_evidence, cohort_manifest=cohort_manifest
    )
    canary_calls = [
        (ladder, count) for ladder in canary["ladders"] for count in T101_COUNTS
    ]
    if (
        len(formal) != T101_FORMAL_STATE_COUNT * T101_REPLICATES
        or len(canary_calls) != 15
    ):
        raise T113ConvergenceError("T113 cost evidence is incomplete")
    canary_wall = sum(
        float(ladder["direct_wall_clock_time_s"][str(count)])
        for ladder, count in canary_calls
    )
    formal_wall = sum(float(row["wall_clock_time_s"]) for row in formal)
    canary_work: list[Mapping[str, object]] = []
    scaling_rows: list[dict[str, object]] = []
    for ladder in canary["ladders"]:
        reports = ladder["direct_bridge_reports"]
        n2_wall = float(ladder["direct_wall_clock_time_s"]["2"])
        n32_wall = float(ladder["direct_wall_clock_time_s"]["32"])
        n2_work = ladder["direct_work_counter_sums"]["2"]
        n32_work = ladder["direct_work_counter_sums"]["32"]
        scaling_rows.append(
            {
                "selection_identity": ladder["selection_identity"],
                "stratum": ladder["stratum"],
                "n2_wall_clock_time_s": n2_wall,
                "n32_wall_clock_time_s": n32_wall,
                "n2_to_n32_wall_clock_ratio": (
                    n32_wall / n2_wall if n2_wall > 0 else None
                ),
                "n2_native_work_counter_sums": n2_work,
                "n32_native_work_counter_sums": n32_work,
            }
        )
        canary_work.extend(
            _work_counter_sums(reports[str(count)]["particles"])
            for count in T101_COUNTS
        )
    total_work: dict[str, int] = defaultdict(int)
    for particle in [
        particle for row in formal for particle in row["bridge_report"]["particles"]
    ]:
        for key, amount in _work_counter_sums([particle]).items():
            total_work[key] += amount
    for call_work in canary_work:
        for key, amount in call_work.items():
            total_work[str(key)] += int(amount)
    formal_work = _work_counter_sums(
        [particle for row in formal for particle in row["bridge_report"]["particles"]]
    )
    return {
        "schema_id": T113_COST_SCHEMA,
        "task_id": T113_TASK_ID,
        "formal_bridge_call_count": len(formal),
        "formal_particle_count": sum(
            len(row["bridge_report"]["particles"]) for row in formal
        ),
        "canary_direct_bridge_call_count": len(canary_calls),
        "canary_particle_count": sum(count for _ladder, count in canary_calls),
        "total_search_v2_continuation_count": (
            sum(len(row["bridge_report"]["particles"]) for row in formal)
            + sum(count for _ladder, count in canary_calls)
        ),
        "total_observed_wall_clock_time_s": formal_wall + canary_wall,
        "formal_observed_wall_clock_time_s": formal_wall,
        "canary_observed_wall_clock_time_s": canary_wall,
        "effective_concurrency": {
            "formal_maximum": max(int(row["effective_concurrency"]) for row in formal),
            "canary_maximum": 1,
        },
        "formal_native_work_counter_sums": dict(sorted(formal_work.items())),
        "total_native_work_counter_sums": dict(sorted(total_work.items())),
        "direct_canary_n2_to_n32_scaling": {
            "state_count": len(scaling_rows),
            "per_state": scaling_rows,
            "wall_clock_ratio_distribution": _distribution(
                [
                    float(row["n2_to_n32_wall_clock_ratio"])
                    for row in scaling_rows
                    if row["n2_to_n32_wall_clock_ratio"] is not None
                ]
            ),
        },
        "formal_prefix_work_counts_are_summed_from_n32_particle_rows": True,
        "formal_prefix_wall_time_fabricated": False,
    }


__all__ = [
    "T113_APPROVED_SPEC_COMMIT",
    "T113_CANARY_EVIDENCE_SCHEMA",
    "T113_COHORT_SCHEMA",
    "T113_FORMAL_PLAN_SCHEMA",
    "T113_NATIVE_IDENTITY",
    "T113_TASK_ID",
    "T113ConvergenceError",
    "analyze_t113_batch",
    "analyze_t113_formal",
    "build_t113_canary_evidence",
    "build_t113_cost_report",
    "build_t113_fixed_cohort",
    "build_t113_formal_plan",
    "validate_t113_bridge_report",
    "validate_t113_canary_evidence",
    "validate_t113_canary_ladder",
    "validate_t113_fixed_cohort",
    "validate_t113_formal_plan",
    "validate_t113_formal_rows",
]
