"""Frozen offline workflow for the T101 particle-count diagnostic.

Native code owns restores, public projection, hidden-future sampling, Battle
mechanics, and Search-v2.  This module admits already-sanitized T099 bridge
reports, preserves public action occurrences, and performs only the descriptive
cross-particle analysis authorized by T101.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from statistics import fmean, median, stdev
from typing import Any

from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    evaluate_eligibility,
)
from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099_VALUE_SEMANTICS,
    T099ParticleSearchBridgeError,
    validate_t099_particle_search_audit,
    validate_t099_particle_search_bridge,
)

T101_TASK_ID = "T101"
T101_COUNTS = (2, 4, 8, 16, 32)
T101_REPLICATES = 4
T101_SEARCH_SIMULATIONS = 400
T101_SOURCE_COUNTS = {"A": 93, "B": 192, "C": 128}
T101_SELECTED_PER_STRATUM = 8
T101_FORMAL_STATE_COUNT = 24
T101_FORMAL_JOB_COUNT = T101_FORMAL_STATE_COUNT * T101_REPLICATES
T101_NATIVE_COMMIT = "97f59b620efe5ee1571f8da298c99d1e21c1149b"
T101_NATIVE_REF = "refs/heads/stsrl/main"
T101_VALUE_SEMANTICS = "strategy_fusion_mean_proxy"
T101_SEED_ALGORITHM = "sha256-domain-identity-decimal-replicate-u64be-v1"
T101_RANK_STATISTIC = "exact-pairwise-order-relation-agreement-v1"
T101_REQUIRED_INPUT_ROLES = frozenset(
    {
        "t087_formal",
        "t087_report",
        "t087_retention",
        "t085_selection",
        "t085_restore",
        "t085_canonical_a",
        "t085_canonical_b",
        "t085_canonical_c",
        "t088_formal_raw",
        "t088_final_report",
        "t088_retention",
        "native_source_manifest",
    }
)
T101_REQUIRED_RETENTION_ROLES = frozenset(
    {
        "input_admission",
        "cohort_admission",
        "canary_evidence",
        "formal_plan",
        "formal_evidence",
        "convergence_analysis",
        "cost_report",
        "final_report",
    }
)
T101_RETENTION_ROLE_SCHEMAS = {
    "input_admission": "t101-input-admission-v1",
    "cohort_admission": "t101-cohort-admission-v1",
    "canary_evidence": "t101-canary-evidence-v1",
    "formal_plan": "t101-formal-plan-v1",
    "formal_evidence": "t101-formal-evidence-index-v1",
    "convergence_analysis": "t101-convergence-analysis-v1",
    "cost_report": "t101-cost-report-v1",
    "final_report": "t101-final-report-v1",
}


class T101IncompleteError(ValueError):
    """Required T101 evidence is absent, ambiguous, or inconsistent."""


class T101AdmissionExclusion(T101IncompleteError):
    """A support candidate failed after a bridge call whose cost is retained."""

    def __init__(
        self, message: str, *, bridge_call_runtime: Mapping[str, object]
    ) -> None:
        super().__init__(message)
        self.bridge_call_runtime = dict(bridge_call_runtime)


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


def _finite(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise T101IncompleteError(f"{label} must be finite numeric")
    return float(value)


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise T101IncompleteError(f"{label} must be a non-negative integer")
    return value


def _sha256_text(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T101IncompleteError(f"{label} must be a lowercase SHA-256")
    return value


def _implementation_head(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T101IncompleteError("implementation head must be a full SHA-1")
    return value


def _identity(row: Mapping[str, object]) -> str:
    value = row.get("selection_identity")
    if not isinstance(value, str) or not value:
        raise T101IncompleteError("selection_identity is missing")
    return value


def _stratum(row: Mapping[str, object]) -> str:
    value = row.get("cohort", row.get("stratum"))
    if value not in T101_SOURCE_COUNTS:
        raise T101IncompleteError("record stratum must be T087 A/B/C")
    return str(value)


def derive_t101_sampler_seed(selection_identity: str, replicate_index: int) -> int:
    """Derive the documented unsigned 64-bit native sampler seed.

    The preimage is the direct concatenation of UTF-8 ``T101-v1``, the exact
    UTF-8 selection identity, and the ASCII base-10 replicate index.  The first
    eight digest bytes are decoded as an unsigned big-endian integer.  This is
    deterministic and does not read or infer simulator PRNG state.
    """

    if not isinstance(selection_identity, str) or not selection_identity:
        raise T101IncompleteError("selection identity must be non-empty text")
    if (
        isinstance(replicate_index, bool)
        or not isinstance(replicate_index, int)
        or replicate_index not in range(T101_REPLICATES)
    ):
        raise T101IncompleteError("replicate index must be in 0..3")
    material = (
        b"T101-v1"
        + selection_identity.encode("utf-8")
        + str(replicate_index).encode("ascii")
    )
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def validate_t101_native_identity(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T101IncompleteError("native identity is missing")
    expected = {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T101_NATIVE_REF,
        "commit": T101_NATIVE_COMMIT,
    }
    observed = {
        "repository": value.get("repository"),
        "ref": value.get("ref"),
        "commit": value.get("commit"),
    }
    if observed != expected:
        raise T101IncompleteError("native identity differs from the T101 contract")
    return expected


def build_t101_input_admission(
    qualifications: Mapping[str, tuple[ArtifactQualification, EligibilityRequirements]],
    *,
    native_identity: Mapping[str, object],
    bridge_audit: object,
) -> dict[str, object]:
    """Evaluate every retained input through the shared T081 gate."""

    if not qualifications:
        raise T101IncompleteError("scientific input qualifications are missing")
    identity = validate_t101_native_identity(native_identity)
    audit = validate_t099_particle_search_audit(bridge_audit)
    reports: dict[str, object] = {}
    failed: list[str] = []
    for role in sorted(qualifications):
        qualification, requirements = qualifications[role]
        report = evaluate_eligibility(qualification, requirements)
        reports[role] = report
        if report["eligible"] is not True:
            failed.append(role)
    result = {
        "schema_id": "t101-input-admission-v1",
        "task_id": T101_TASK_ID,
        "reuse_mode": "scientific_quality_claim",
        "claim_boundary": (
            "bounded particle-proxy stability and cost under frozen T101 semantics"
        ),
        "native_identity": identity,
        "t099_bridge_audit": audit,
        "artifacts": reports,
        "eligible": not failed,
        "failed_roles": failed,
    }
    if failed:
        raise T101IncompleteError(
            "required scientific inputs are ineligible: " + ", ".join(failed)
        )
    return result


def validate_t101_input_admission(value: object) -> dict[str, object]:
    """Revalidate the complete fail-closed T101 scientific-input bundle."""

    if not isinstance(value, Mapping):
        raise T101IncompleteError("input admission is missing")
    artifacts = value.get("artifacts")
    if (
        value.get("schema_id") != "t101-input-admission-v1"
        or value.get("task_id") != T101_TASK_ID
        or value.get("reuse_mode") != "scientific_quality_claim"
        or value.get("claim_boundary")
        != "bounded particle-proxy stability and cost under frozen T101 semantics"
        or value.get("eligible") is not True
        or value.get("failed_roles") != []
        or not isinstance(artifacts, Mapping)
        or set(artifacts) != T101_REQUIRED_INPUT_ROLES
    ):
        raise T101IncompleteError(
            "complete eligible T101 input admission is unavailable"
        )
    for role in sorted(T101_REQUIRED_INPUT_ROLES):
        report = artifacts.get(role)
        if (
            not isinstance(report, Mapping)
            or report.get("schema_version") != "artifact-eligibility-v1"
            or report.get("eligible") is not True
            or report.get("reuse_mode") != "scientific_quality_claim"
            or report.get("claim_boundary")
            != "bounded particle-proxy stability and cost under frozen T101 semantics"
        ):
            raise T101IncompleteError(f"input eligibility report {role} is invalid")
        qualification = report.get("artifact")
        requirements = report.get("requirements")
        if not isinstance(qualification, Mapping) or not isinstance(
            requirements, Mapping
        ):
            raise T101IncompleteError(
                f"input eligibility identity for {role} is missing"
            )
        artifact_identity = qualification.get("artifact")
        integrity = qualification.get("integrity")
        if (
            not isinstance(artifact_identity, Mapping)
            or not isinstance(integrity, Mapping)
            or artifact_identity.get("id") != role
            or requirements.get("artifact_id") != role
            or artifact_identity.get("kind") != requirements.get("artifact_kind")
            or artifact_identity.get("kind") != artifact_identity.get("schema_id")
            or integrity.get("sha256") != requirements.get("sha256")
            or not isinstance(artifact_identity.get("path"), str)
            or not artifact_identity["path"]
            or not isinstance(artifact_identity.get("schema_id"), str)
            or not artifact_identity["schema_id"]
            or isinstance(artifact_identity.get("size_bytes"), bool)
            or not isinstance(artifact_identity.get("size_bytes"), int)
            or artifact_identity["size_bytes"] < 0
        ):
            raise T101IncompleteError(
                f"input eligibility identity for {role} is inconsistent"
            )
        _sha256_text(integrity.get("sha256"), f"input artifact {role}")
        predicates = report.get("predicates")
        if (
            not isinstance(predicates, Sequence)
            or isinstance(predicates, (str, bytes))
            or not predicates
            or any(
                not isinstance(predicate, Mapping)
                or predicate.get("result") is not True
                for predicate in predicates
            )
        ):
            raise T101IncompleteError(
                f"input eligibility predicates for {role} are incomplete"
            )
    validate_t101_native_identity(value.get("native_identity"))
    try:
        validate_t099_particle_search_audit(value.get("t099_bridge_audit"))
    except T099ParticleSearchBridgeError as exc:
        raise T101IncompleteError(f"T099 bridge audit failed closed: {exc}") from exc
    return dict(value)


def validate_t101_bridge_report(
    value: object, *, particle_count: int
) -> dict[str, Any]:
    """Apply T099 validation plus T101's exact Search and finite-value gate."""

    try:
        report = validate_t099_particle_search_bridge(value)
    except T099ParticleSearchBridgeError as exc:
        raise T101IncompleteError(f"T099 bridge report failed closed: {exc}") from exc
    if (
        report["particle_start"] != 0
        or report["particle_count"] != particle_count
        or report["search_simulations"] != T101_SEARCH_SIMULATIONS
        or report["include_potions"] is not False
    ):
        raise T101IncompleteError(
            "bridge call differs from particle_start=0, Search-v2@400, no-potion"
        )
    for particle in report["particles"]:
        if particle["sampler_seed"] != report["sampler_seed_input"]:
            raise T101IncompleteError(
                "per-particle sampler seed differs from the bridge sampler seed"
            )
        root = particle["root_evaluation"]
        if (
            root["simulations_requested"] != T101_SEARCH_SIMULATIONS
            or root["include_potions"] is not False
        ):
            raise T101IncompleteError(
                "per-particle root evaluation differs from Search-v2@400 no-potion"
            )
        for row in particle["root_rows"]:
            _finite(row.get("mean_value"), "required root mean_value")
            _finite(row.get("evaluation_sum"), "required root evaluation_sum")
            _nonnegative_int(row.get("visits"), "required root visits")
    return report


def call_t101_bridge(
    adapter: object,
    snapshot: object,
    *,
    sampler_seed: int,
    particle_count: int,
) -> dict[str, Any]:
    """Invoke only the frozen T099 bridge surface; never execute an action."""

    if particle_count not in T101_COUNTS:
        raise T101IncompleteError("T101 particle count is not one of 2/4/8/16/32")
    bridge = getattr(adapter, "sample_hidden_future_particles_search", None)
    if not callable(bridge):
        raise T101IncompleteError("T099 bridge is unavailable on the adapter")
    report = bridge(
        snapshot,
        sampler_seed=sampler_seed,
        particle_start=0,
        particle_count=particle_count,
        search_simulations=T101_SEARCH_SIMULATIONS,
        include_potions=False,
    )
    return validate_t101_bridge_report(report, particle_count=particle_count)


def _source_population(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    result = [dict(row) for row in rows]
    if len(result) != sum(T101_SOURCE_COUNTS.values()):
        raise T101IncompleteError("source population must contain exactly 413 records")
    counts = Counter(_stratum(row) for row in result)
    if dict(counts) != T101_SOURCE_COUNTS:
        raise T101IncompleteError("source population must have exact A/B/C counts")
    identities = [_identity(row) for row in result]
    if len(set(identities)) != len(identities):
        raise T101IncompleteError("source population has duplicate identities")
    return result


def _selection_key(row: Mapping[str, object]) -> tuple[str, str]:
    identity = _identity(row)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest(), identity


def _validate_admission_bridge_runtime(
    value: object, *, success: bool
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T101IncompleteError("admission bridge-call runtime is missing")
    wall = _finite(value.get("wall_clock_time_s"), "admission bridge wall time")
    expected_status = "success_no_retry" if success else "failed_no_retry"
    if (
        wall < 0
        or value.get("particle_count") != 2
        or value.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
        or not isinstance(value.get("worker_id"), str)
        or not value["worker_id"]
        or value.get("shard_index") != 0
        or value.get("effective_concurrency") != 1
        or value.get("failure_retry_status") != expected_status
        or value.get("retry_reason") is not None
        or not isinstance(value.get("single_worker_reason"), str)
        or not value["single_worker_reason"]
    ):
        raise T101IncompleteError("admission bridge-call runtime is incomplete")
    return {
        "wall_clock_time_s": wall,
        "particle_count": 2,
        "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
        "worker_id": value["worker_id"],
        "shard_index": 0,
        "effective_concurrency": 1,
        "failure_retry_status": expected_status,
        "retry_reason": None,
        "single_worker_reason": value["single_worker_reason"],
    }


def _validate_admission_evidence(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T101IncompleteError("admission evidence is missing")
    required_true = (
        "restore_exact_accepted_state",
        "public_projection_parity",
        "ordered_legal_action_parity",
        "occurrence_mapping_complete",
        "search_configuration_unchanged",
    )
    for name in required_true:
        if value.get(name) is not True:
            raise T101IncompleteError(f"admission predicate failed: {name}")
    report = validate_t101_bridge_report(value.get("bridge_report"), particle_count=2)
    return {
        "restore_exact_accepted_state": True,
        "public_projection_parity": True,
        "ordered_legal_action_parity": True,
        "occurrence_mapping_complete": True,
        "search_configuration_unchanged": True,
        "bridge_report_sha256": _canonical_sha256(report),
        "admission_bridge_report": report,
        "bridge_call_runtime": _validate_admission_bridge_runtime(
            value.get("bridge_call_runtime"), success=True
        ),
    }


def select_t101_cohort(
    source_rows: Iterable[Mapping[str, object]],
    *,
    admit: Callable[[Mapping[str, object]], object],
) -> dict[str, object]:
    """Select the first eight structurally admitted identities per stratum.

    The callback may restore and call the bridge, but this selector retains
    only structural predicate results and never reads outcome, rank, value, or
    hidden-diversity magnitude for ordering or admission.
    """

    population = _source_population(source_rows)
    selected: list[dict[str, object]] = []
    attempted: list[dict[str, object]] = []
    exhausted: list[str] = []
    for stratum in T101_SOURCE_COUNTS:
        accepted = 0
        candidates = sorted(
            (row for row in population if _stratum(row) == stratum),
            key=_selection_key,
        )
        for source_ordinal, candidate in enumerate(candidates):
            if accepted == T101_SELECTED_PER_STRATUM:
                break
            identity = _identity(candidate)
            digest = _selection_key(candidate)[0]
            try:
                structural = _validate_admission_evidence(admit(candidate))
            except T101IncompleteError as exc:
                exclusion: dict[str, object] = {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "source_ordinal": source_ordinal,
                    "selection_digest": digest,
                    "admitted": False,
                    "exclusion_reason": str(exc),
                }
                if isinstance(exc, T101AdmissionExclusion):
                    exclusion["bridge_call_runtime"] = (
                        _validate_admission_bridge_runtime(
                            exc.bridge_call_runtime, success=False
                        )
                    )
                attempted.append(exclusion)
                continue
            row = {
                "selection_identity": identity,
                "stratum": stratum,
                "source_ordinal": source_ordinal,
                "selection_digest": digest,
                "admitted": True,
                "structural_evidence": structural,
            }
            attempted.append(row)
            selected.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "selection_digest": digest,
                }
            )
            accepted += 1
        if accepted != T101_SELECTED_PER_STRATUM:
            exhausted.append(stratum)
    return {
        "schema_id": "t101-cohort-admission-v1",
        "task_id": T101_TASK_ID,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "selection_rule": "sha256-selection-identity-then-canonical-identity-v1",
        "attempted": attempted,
        "selected": selected,
        "selected_counts": dict(Counter(row["stratum"] for row in selected)),
        "supported": not exhausted,
        "exhausted_strata": exhausted,
        "terminal_classification": (
            None if not exhausted else "SUPPORTED_COHORT_INSUFFICIENT"
        ),
    }


def validate_t101_selected_cohort(value: object) -> list[dict[str, object]]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != "t101-cohort-admission-v1"
        or value.get("task_id") != T101_TASK_ID
        or value.get("supported") is not True
        or value.get("terminal_classification") is not None
        or value.get("source_counts") != T101_SOURCE_COUNTS
        or value.get("selection_rule")
        != "sha256-selection-identity-then-canonical-identity-v1"
    ):
        raise T101IncompleteError("supported 8/8/8 cohort is unavailable")
    selected = value.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T101IncompleteError("selected cohort is malformed")
    rows = [dict(row) for row in selected if isinstance(row, Mapping)]
    if len(rows) != len(selected) or len(rows) != T101_FORMAL_STATE_COUNT:
        raise T101IncompleteError("selected cohort must contain exactly 24 states")
    if Counter(_stratum(row) for row in rows) != Counter({"A": 8, "B": 8, "C": 8}):
        raise T101IncompleteError("selected cohort must have exact 8/8/8 strata")
    if value.get("selected_counts") != {
        "A": T101_SELECTED_PER_STRATUM,
        "B": T101_SELECTED_PER_STRATUM,
        "C": T101_SELECTED_PER_STRATUM,
    }:
        raise T101IncompleteError("selected cohort count summary changed")
    if len({_identity(row) for row in rows}) != len(rows):
        raise T101IncompleteError("selected cohort contains duplicate identities")
    attempted = value.get("attempted")
    if not isinstance(attempted, Sequence) or isinstance(attempted, (str, bytes)):
        raise T101IncompleteError("cohort admission attempts are missing")
    admitted: list[dict[str, object]] = []
    ordinals: dict[str, list[int]] = defaultdict(list)
    for raw in attempted:
        if not isinstance(raw, Mapping):
            raise T101IncompleteError("cohort admission attempt is malformed")
        identity = _identity(raw)
        stratum = _stratum(raw)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        source_ordinal = raw.get("source_ordinal")
        if (
            raw.get("selection_digest") != digest
            or isinstance(source_ordinal, bool)
            or not isinstance(source_ordinal, int)
            or source_ordinal < 0
        ):
            raise T101IncompleteError("cohort admission ordering evidence changed")
        ordinals[stratum].append(source_ordinal)
        if raw.get("admitted") is True:
            structural = raw.get("structural_evidence")
            if not isinstance(structural, Mapping):
                raise T101IncompleteError("admitted structural evidence is missing")
            for name in (
                "restore_exact_accepted_state",
                "public_projection_parity",
                "ordered_legal_action_parity",
                "occurrence_mapping_complete",
                "search_configuration_unchanged",
            ):
                if structural.get(name) is not True:
                    raise T101IncompleteError(
                        f"admitted structural predicate changed: {name}"
                    )
            report = validate_t101_bridge_report(
                structural.get("admission_bridge_report"), particle_count=2
            )
            if structural.get("bridge_report_sha256") != _canonical_sha256(report):
                raise T101IncompleteError("admission bridge evidence hash changed")
            _validate_admission_bridge_runtime(
                structural.get("bridge_call_runtime"), success=True
            )
            admitted.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "selection_digest": digest,
                }
            )
        elif raw.get("admitted") is False:
            if (
                not isinstance(raw.get("exclusion_reason"), str)
                or not raw["exclusion_reason"]
            ):
                raise T101IncompleteError("excluded admission reason is missing")
            if "bridge_call_runtime" in raw:
                _validate_admission_bridge_runtime(
                    raw.get("bridge_call_runtime"), success=False
                )
        else:
            raise T101IncompleteError("cohort admission result is ambiguous")
    if admitted != rows:
        raise T101IncompleteError("selected cohort differs from admitted attempt order")
    for stratum, observed in ordinals.items():
        if observed != list(range(len(observed))):
            raise T101IncompleteError(
                f"cohort admission skipped/reordered {stratum} candidates"
            )
    return rows


def _class_partition(
    report: Mapping[str, Any],
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    partition: list[tuple[int, tuple[int, ...]]] = []
    by_edge: dict[int, list[int]] = defaultdict(list)
    first = report["particles"][0]
    for row in first["root_rows"]:
        by_edge[int(row["search_equivalence_source_edge_index"])].append(
            int(row["public_action_ordinal"])
        )
    for edge in sorted(by_edge):
        partition.append((edge, tuple(by_edge[edge])))
    expected = tuple(partition)
    for particle in report["particles"]:
        observed_by_edge: dict[int, list[int]] = defaultdict(list)
        for row in particle["root_rows"]:
            observed_by_edge[int(row["search_equivalence_source_edge_index"])].append(
                int(row["public_action_ordinal"])
            )
        observed = tuple(
            (edge, tuple(observed_by_edge[edge])) for edge in sorted(observed_by_edge)
        )
        if observed != expected:
            raise T101IncompleteError(
                "Search-equivalence partition changed across public-equivalent particles"
            )
    return expected


def _class_particle_values(
    report: Mapping[str, Any],
) -> tuple[list[str], list[list[float]], tuple[tuple[int, tuple[int, ...]], ...]]:
    partition = _class_partition(report)
    class_ids = ["search-edge:" + str(edge) for edge, _ordinals in partition]
    values: list[list[float]] = [[] for _ in partition]
    for particle_index, particle in enumerate(report["particles"]):
        rows = particle["root_rows"]
        for class_index, (_edge, ordinals) in enumerate(partition):
            members = [
                _finite(rows[ordinal].get("mean_value"), "root mean_value")
                for ordinal in ordinals
            ]
            if any(value != members[0] for value in members[1:]):
                raise T101IncompleteError(
                    "duplicate public occurrences disagree on accepted Search edge value"
                )
            values[class_index].append(members[0])
        if particle["particle_index"] != particle_index:
            raise T101IncompleteError(
                "formal particle order is not zero-based nested order"
            )
    return class_ids, values, partition


def _pairwise_rank_agreement(
    current: Mapping[str, float], reference: Mapping[str, float]
) -> float:
    keys = sorted(reference)
    if set(current) != set(keys):
        raise T101IncompleteError("rank comparison decision classes differ")
    if len(keys) < 2:
        return 1.0
    matches = 0
    total = 0
    for left_index, left in enumerate(keys):
        for right in keys[left_index + 1 :]:
            current_relation = (current[left] > current[right]) - (
                current[left] < current[right]
            )
            reference_relation = (reference[left] > reference[right]) - (
                reference[left] < reference[right]
            )
            matches += current_relation == reference_relation
            total += 1
    return matches / total


def _prefix_metrics(
    class_ids: Sequence[str], values: Sequence[Sequence[float]], count: int
) -> tuple[list[dict[str, object]], dict[str, float], list[str]]:
    rows: list[dict[str, object]] = []
    means: dict[str, float] = {}
    for class_id, samples in zip(class_ids, values, strict=True):
        prefix = list(samples[:count])
        if len(prefix) != count:
            raise T101IncompleteError("formal evidence is missing nested particles")
        average = fmean(prefix)
        sample_std = stdev(prefix)
        means[class_id] = average
        rows.append(
            {
                "decision_class_id": class_id,
                T101_VALUE_SEMANTICS: average,
                "sample_standard_deviation": sample_std,
                "standard_error": sample_std / math.sqrt(count),
                "minimum_proxy_value": min(prefix),
                "maximum_proxy_value": max(prefix),
                "particle_support_count": count,
            }
        )
    maximum = max(means.values())
    best = sorted(key for key, value in means.items() if value == maximum)
    return rows, means, best


def analyze_t101_batch(value: object) -> dict[str, object]:
    """Analyze all nested prefixes of one exact state/replicate N=32 call."""

    report = validate_t101_bridge_report(value, particle_count=32)
    class_ids, values, partition = _class_particle_values(report)
    prefix: dict[int, tuple[list[dict[str, object]], dict[str, float], list[str]]] = {
        count: _prefix_metrics(class_ids, values, count) for count in T101_COUNTS
    }
    reference_means = prefix[32][1]
    reference_best = prefix[32][2]
    metrics: list[dict[str, object]] = []
    for count in T101_COUNTS:
        classes, means, best = prefix[count]
        opportunity_gap = max(reference_means.values()) - max(
            reference_means[class_id] for class_id in best
        )
        metrics.append(
            {
                "particle_count": count,
                "decision_classes": classes,
                "best_decision_class_set": best,
                "decision_class_count": len(class_ids),
                "best_set_exact_agreement_with_n32": best == reference_best,
                "n32_reference_proxy_opportunity_gap": opportunity_gap,
                "maximum_absolute_class_mean_drift_from_n32": max(
                    abs(means[class_id] - reference_means[class_id])
                    for class_id in class_ids
                ),
                "rank_agreement_with_n32": _pairwise_rank_agreement(
                    means, reference_means
                ),
                "rank_agreement_statistic": T101_RANK_STATISTIC,
            }
        )
    return {
        "schema_id": "t101-state-replicate-convergence-v1",
        "value_semantics": T101_VALUE_SEMANTICS,
        "source_value_semantics": T099_VALUE_SEMANTICS,
        "particle_counts": list(T101_COUNTS),
        "decision_class_partition": [
            {
                "decision_class_id": f"search-edge:{edge}",
                "public_action_ordinals": list(ordinals),
            }
            for edge, ordinals in partition
        ],
        "ordered_public_legal_actions": report["anchor_ordered_public_legal_actions"],
        "public_information_projection": report["anchor_public_information_projection"],
        "per_occurrence_rows_retained": True,
        "hidden_future_fingerprints": [
            particle["hidden_future_fingerprint"] for particle in report["particles"]
        ],
        "metrics": metrics,
    }


def validate_t101_canary_ladder(value: object) -> dict[str, object]:
    """Prove direct N calls are exact prefixes of the direct N=32 call."""

    if not isinstance(value, Mapping):
        raise T101IncompleteError("canary ladder is missing")
    identity = value.get("selection_identity")
    stratum = value.get("stratum")
    if (
        not isinstance(identity, str)
        or not identity
        or stratum not in T101_SOURCE_COUNTS
        or value.get("replicate_index") != 0
    ):
        raise T101IncompleteError("canary must be one A/B/C identity at replicate 0")
    calls = value.get("calls")
    if not isinstance(calls, Mapping):
        raise T101IncompleteError("canary ladder calls are missing")
    parsed: dict[int, dict[str, Any]] = {}
    elapsed: dict[int, float] = {}
    runtime: dict[int, dict[str, object]] = {}
    for count in T101_COUNTS:
        call = calls.get(str(count), calls.get(count))
        if not isinstance(call, Mapping):
            raise T101IncompleteError(f"canary direct N={count} call is missing")
        parsed[count] = validate_t101_bridge_report(
            call.get("bridge_report"), particle_count=count
        )
        elapsed[count] = _finite(call.get("wall_clock_time_s"), "canary wall time")
        if elapsed[count] < 0:
            raise T101IncompleteError("canary wall time must be non-negative")
        if (
            not isinstance(call.get("worker_id"), str)
            or not call["worker_id"]
            or call.get("shard_index") != 0
            or call.get("effective_concurrency") != 1
            or call.get("failure_retry_status") != "success_no_retry"
            or not isinstance(call.get("single_worker_reason"), str)
            or not call["single_worker_reason"]
        ):
            raise T101IncompleteError(
                "canary worker/concurrency/failure provenance is incomplete"
            )
        runtime[count] = {
            "worker_id": call["worker_id"],
            "shard_index": 0,
            "effective_concurrency": 1,
            "failure_retry_status": "success_no_retry",
            "single_worker_reason": call["single_worker_reason"],
        }
    reference = parsed[32]
    expected_seed = derive_t101_sampler_seed(identity, 0)
    if reference["sampler_seed_input"] != expected_seed:
        raise T101IncompleteError("canary sampler seed differs from T101 derivation")
    for count in T101_COUNTS[:-1]:
        direct = parsed[count]
        for name in (
            "sampler_seed_input",
            "anchor_public_information_projection",
            "anchor_ordered_public_legal_actions",
            "semantic_boundary",
        ):
            if direct[name] != reference[name]:
                raise T101IncompleteError(
                    f"canary direct N={count} differs from N=32 on {name}"
                )
        if direct["particles"] != reference["particles"][:count]:
            raise T101IncompleteError(
                f"canary direct N={count} is not the exact N=32 ordered prefix"
            )
    return {
        "selection_identity": identity,
        "stratum": stratum,
        "replicate_index": 0,
        "sampler_seed": reference["sampler_seed_input"],
        "direct_prefix_equivalence": True,
        "direct_wall_clock_time_s": {str(k): elapsed[k] for k in T101_COUNTS},
        "direct_runtime_provenance": {
            str(count): runtime[count] for count in T101_COUNTS
        },
        "direct_bridge_reports": {str(count): parsed[count] for count in T101_COUNTS},
        "direct_work_counters": {
            str(count): [
                particle["root_evaluation"]["work_counters"]
                for particle in parsed[count]["particles"]
            ]
            for count in T101_COUNTS
        },
        "direct_work_counter_sums": {
            str(count): _work_counter_sums(parsed[count]["particles"])
            for count in T101_COUNTS
        },
        "direct_work_counter_distributions": {
            str(count): _work_counter_distributions(parsed[count]["particles"])
            for count in T101_COUNTS
        },
        "n32_bridge_report": reference,
    }


def validate_t101_canary_evidence(value: object) -> dict[str, object]:
    """Revalidate retained direct ladders instead of trusting pass booleans."""

    if not isinstance(value, Mapping):
        raise T101IncompleteError("canary evidence is missing")
    if (
        value.get("schema_id") != "t101-canary-evidence-v1"
        or value.get("task_id") != T101_TASK_ID
        or value.get("complete") is not True
        or value.get("direct_prefix_equivalence") is not True
    ):
        raise T101IncompleteError("canary evidence is incomplete")
    head = value.get("implementation_head")
    if (
        not isinstance(head, str)
        or len(head) != 40
        or any(ch not in "0123456789abcdef" for ch in head)
    ):
        raise T101IncompleteError("canary implementation head is invalid")
    authorization = value.get("authorization")
    if (
        not isinstance(authorization, Mapping)
        or set(authorization)
        != {
            "schema_id",
            "task_id",
            "authorization_kind",
            "authorized",
            "authorization_id",
            "implementation_head",
            "input_admission_sha256",
            "cohort_admission_sha256",
            "maintainer_attestation",
        }
        or authorization.get("schema_id") != "t101-maintainer-canary-authorization-v1"
        or authorization.get("task_id") != T101_TASK_ID
        or authorization.get("authorization_kind") != "bounded_canary"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != head
        or authorization.get("maintainer_attestation")
        != {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": head,
        }
    ):
        raise T101IncompleteError("canary authorization provenance is invalid")
    _sha256_text(
        authorization.get("input_admission_sha256"),
        "canary input-admission binding",
    )
    _sha256_text(
        authorization.get("cohort_admission_sha256"),
        "canary cohort-admission binding",
    )
    ladders = value.get("ladders")
    if (
        not isinstance(ladders, Sequence)
        or isinstance(ladders, (str, bytes))
        or len(ladders) != 3
    ):
        raise T101IncompleteError("canary must retain exactly three direct ladders")
    normalized: list[dict[str, object]] = []
    for stored in ladders:
        if not isinstance(stored, Mapping):
            raise T101IncompleteError("retained canary ladder is malformed")
        reports = stored.get("direct_bridge_reports")
        walls = stored.get("direct_wall_clock_time_s")
        runtime = stored.get("direct_runtime_provenance")
        if not all(isinstance(item, Mapping) for item in (reports, walls, runtime)):
            raise T101IncompleteError("retained canary direct calls are missing")
        reconstructed_calls: dict[str, object] = {}
        for count in T101_COUNTS:
            runtime_row = runtime.get(str(count))
            if not isinstance(runtime_row, Mapping):
                raise T101IncompleteError(
                    "retained canary call runtime provenance is malformed"
                )
            reconstructed_calls[str(count)] = {
                "bridge_report": reports.get(str(count)),
                "wall_clock_time_s": walls.get(str(count)),
                **dict(runtime_row),
            }
        reconstructed = {
            "selection_identity": stored.get("selection_identity"),
            "stratum": stored.get("stratum"),
            "replicate_index": stored.get("replicate_index"),
            "calls": reconstructed_calls,
        }
        checked = validate_t101_canary_ladder(reconstructed)
        if dict(stored) != checked:
            raise T101IncompleteError("retained canary derived evidence changed")
        normalized.append(checked)
    if [row["stratum"] for row in normalized] != ["A", "B", "C"]:
        raise T101IncompleteError("canary ladders are not exact A/B/C order")
    selected = value.get("selected")
    expected_selected = [
        {
            "selection_identity": row["selection_identity"],
            "stratum": row["stratum"],
            "replicate_index": 0,
        }
        for row in normalized
    ]
    if selected != expected_selected:
        raise T101IncompleteError("canary selected identities differ from ladders")
    return dict(value)


def build_t101_formal_plan(
    cohort_admission: Mapping[str, object],
    *,
    input_admission: Mapping[str, object],
    implementation_head: str,
    output_root: str,
    shard_count: int = 16,
    worker_count: int = 16,
    lower_worker_reason: str | None = None,
) -> dict[str, object]:
    """Build a non-authorizing exact 96-job, modulo-sharded formal plan."""

    cohort = validate_t101_selected_cohort(cohort_admission)
    inputs = validate_t101_input_admission(input_admission)
    implementation_head = _implementation_head(implementation_head)
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_count < 1
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or worker_count < 1
        or worker_count > min(16, shard_count)
    ):
        raise T101IncompleteError("formal shard/worker topology is invalid")
    target_workers = min(16, shard_count)
    if (worker_count < target_workers) != (
        isinstance(lower_worker_reason, str) and bool(lower_worker_reason)
    ):
        raise T101IncompleteError(
            "formal lower-worker topology requires exactly one documented reason"
        )
    jobs: list[dict[str, object]] = []
    for state_ordinal, row in enumerate(cohort):
        identity = _identity(row)
        for replicate_index in range(T101_REPLICATES):
            ordinal = len(jobs)
            jobs.append(
                {
                    "job_ordinal": ordinal,
                    "shard_index": ordinal % shard_count,
                    "state_ordinal": state_ordinal,
                    "selection_identity": identity,
                    "stratum": _stratum(row),
                    "replicate_index": replicate_index,
                    "sampler_seed": derive_t101_sampler_seed(identity, replicate_index),
                    "particle_start": 0,
                    "particle_count": 32,
                    "search_simulations": T101_SEARCH_SIMULATIONS,
                    "include_potions": False,
                    "output_name": f"job-{ordinal:03d}.json",
                }
            )
    bridge_runtimes = [
        (
            row.get("structural_evidence", {}).get("bridge_call_runtime")
            if row.get("admitted") is True
            and isinstance(row.get("structural_evidence"), Mapping)
            else row.get("bridge_call_runtime")
        )
        for row in cohort_admission.get("attempted", [])
        if isinstance(row, Mapping)
        and (row.get("admitted") is True or "bridge_call_runtime" in row)
    ]
    checked_runtimes = [
        _validate_admission_bridge_runtime(
            runtime,
            success=runtime.get("failure_retry_status") == "success_no_retry",
        )
        for runtime in bridge_runtimes
        if isinstance(runtime, Mapping)
    ]
    if len(checked_runtimes) != len(bridge_runtimes):
        raise T101IncompleteError(
            "support-admission bridge cost evidence is incomplete"
        )
    plan = {
        "schema_id": "t101-formal-plan-v1",
        "task_id": T101_TASK_ID,
        "formal_authorized": False,
        "implementation_head": implementation_head,
        "input_admission_sha256": _canonical_sha256(input_admission),
        "cohort_admission_sha256": _canonical_sha256(cohort_admission),
        "native_identity": validate_t101_native_identity(inputs.get("native_identity")),
        "seed_algorithm": T101_SEED_ALGORITHM,
        "value_semantics": T101_VALUE_SEMANTICS,
        "search_configuration": {
            "search_variant": "unchanged_unguided_search_v2",
            "search_simulations": T101_SEARCH_SIMULATIONS,
            "policy_prior_enabled": False,
            "learned_leaf_value_enabled": False,
            "progressive_bias_enabled": False,
            "include_potions": False,
            "action_space": "ActionSpaceConfig.initial_no_potions()",
        },
        "topology": {
            "shard_count": shard_count,
            "worker_count": worker_count,
            "lower_worker_reason": lower_worker_reason,
            "assignment": "formal-job-ordinal-modulo-shard-count-v1",
        },
        "output_root": output_root,
        "support_admission_cost": {
            "bridge_call_count": len(checked_runtimes),
            "successful_call_count": sum(
                row["failure_retry_status"] == "success_no_retry"
                for row in checked_runtimes
            ),
            "failed_call_count": sum(
                row["failure_retry_status"] == "failed_no_retry"
                for row in checked_runtimes
            ),
            "wall_clock_time_s": _distribution(
                [float(row["wall_clock_time_s"]) for row in checked_runtimes]
            ),
            "sum_bridge_call_wall_clock_time_s": sum(
                float(row["wall_clock_time_s"]) for row in checked_runtimes
            ),
        },
        "job_count": len(jobs),
        "jobs": jobs,
    }
    return validate_t101_formal_plan(plan)


def validate_t101_formal_plan(value: object) -> dict[str, object]:
    """Revalidate every immutable formal-plan binding before execution/analysis."""

    if not isinstance(value, Mapping):
        raise T101IncompleteError("formal plan is missing")
    topology = value.get("topology")
    jobs = value.get("jobs")
    search = value.get("search_configuration")
    support_cost = value.get("support_admission_cost")
    if (
        value.get("schema_id") != "t101-formal-plan-v1"
        or value.get("task_id") != T101_TASK_ID
        or value.get("formal_authorized") is not False
        or value.get("seed_algorithm") != T101_SEED_ALGORITHM
        or value.get("value_semantics") != T101_VALUE_SEMANTICS
        or not isinstance(value.get("output_root"), str)
        or not value["output_root"]
        or value.get("job_count") != T101_FORMAL_JOB_COUNT
        or not isinstance(topology, Mapping)
        or not isinstance(jobs, Sequence)
        or isinstance(jobs, (str, bytes))
        or len(jobs) != T101_FORMAL_JOB_COUNT
        or search
        != {
            "search_variant": "unchanged_unguided_search_v2",
            "search_simulations": T101_SEARCH_SIMULATIONS,
            "policy_prior_enabled": False,
            "learned_leaf_value_enabled": False,
            "progressive_bias_enabled": False,
            "include_potions": False,
            "action_space": "ActionSpaceConfig.initial_no_potions()",
        }
    ):
        raise T101IncompleteError(
            "formal plan schema or frozen Search semantics changed"
        )
    _implementation_head(value.get("implementation_head"))
    _sha256_text(value.get("input_admission_sha256"), "input admission binding")
    _sha256_text(value.get("cohort_admission_sha256"), "cohort admission binding")
    validate_t101_native_identity(value.get("native_identity"))
    shard_count = topology.get("shard_count")
    worker_count = topology.get("worker_count")
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_count < 1
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or worker_count < 1
        or worker_count > min(16, shard_count)
        or (
            worker_count < min(16, shard_count)
            and (
                not isinstance(topology.get("lower_worker_reason"), str)
                or not topology["lower_worker_reason"]
            )
        )
        or (
            worker_count == min(16, shard_count)
            and topology.get("lower_worker_reason") is not None
        )
        or topology.get("assignment") != "formal-job-ordinal-modulo-shard-count-v1"
    ):
        raise T101IncompleteError("formal plan topology changed")
    if not isinstance(support_cost, Mapping):
        raise T101IncompleteError("support-admission cost summary is missing")
    call_count = support_cost.get("bridge_call_count")
    successes = support_cost.get("successful_call_count")
    failures = support_cost.get("failed_call_count")
    wall_distribution = support_cost.get("wall_clock_time_s")
    if (
        any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0
            for item in (call_count, successes, failures)
        )
        or successes + failures != call_count
        or not isinstance(wall_distribution, Mapping)
        or wall_distribution.get("count") != call_count
        or _finite(
            support_cost.get("sum_bridge_call_wall_clock_time_s"),
            "support-admission total wall time",
        )
        < 0
    ):
        raise T101IncompleteError("support-admission cost summary is malformed")

    states: dict[int, tuple[str, str]] = {}
    replicates: dict[int, set[int]] = defaultdict(set)
    for ordinal, raw_job in enumerate(jobs):
        if not isinstance(raw_job, Mapping):
            raise T101IncompleteError("formal plan job is malformed")
        state_ordinal = raw_job.get("state_ordinal")
        replicate_index = raw_job.get("replicate_index")
        identity = raw_job.get("selection_identity")
        stratum = raw_job.get("stratum")
        if (
            raw_job.get("job_ordinal") != ordinal
            or raw_job.get("shard_index") != ordinal % shard_count
            or isinstance(state_ordinal, bool)
            or not isinstance(state_ordinal, int)
            or state_ordinal not in range(T101_FORMAL_STATE_COUNT)
            or isinstance(replicate_index, bool)
            or not isinstance(replicate_index, int)
            or replicate_index not in range(T101_REPLICATES)
            or not isinstance(identity, str)
            or not identity
            or stratum not in T101_SOURCE_COUNTS
            or raw_job.get("sampler_seed")
            != derive_t101_sampler_seed(identity, replicate_index)
            or raw_job.get("particle_start") != 0
            or raw_job.get("particle_count") != 32
            or raw_job.get("search_simulations") != T101_SEARCH_SIMULATIONS
            or raw_job.get("include_potions") is not False
            or raw_job.get("output_name") != f"job-{ordinal:03d}.json"
        ):
            raise T101IncompleteError("formal plan job identity/configuration changed")
        state = (identity, str(stratum))
        prior = states.setdefault(state_ordinal, state)
        if prior != state or replicate_index in replicates[state_ordinal]:
            raise T101IncompleteError("formal plan state/replicate matrix changed")
        replicates[state_ordinal].add(replicate_index)
    if (
        set(states) != set(range(T101_FORMAL_STATE_COUNT))
        or len({identity for identity, _stratum_name in states.values()})
        != T101_FORMAL_STATE_COUNT
        or Counter(stratum for _identity_value, stratum in states.values())
        != Counter({"A": 8, "B": 8, "C": 8})
        or any(
            indices != set(range(T101_REPLICATES)) for indices in replicates.values()
        )
    ):
        raise T101IncompleteError("formal plan is not the exact 24-state R=4 matrix")
    return dict(value)


def _work_counter_sums(particles: Sequence[Mapping[str, object]]) -> dict[str, int]:
    sums: dict[str, int] = defaultdict(int)
    for particle in particles:
        root = particle.get("root_evaluation")
        counters = root.get("work_counters") if isinstance(root, Mapping) else None
        if not isinstance(counters, Mapping):
            raise T101IncompleteError("per-particle Search work counters are missing")
        for key, value in counters.items():
            if key == "schema_id":
                continue
            sums[str(key)] += _nonnegative_int(value, f"work counter {key}")
    return dict(sorted(sums.items()))


def _work_counter_distributions(
    particles: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    values: dict[str, list[float]] = defaultdict(list)
    for particle in particles:
        root = particle.get("root_evaluation")
        counters = root.get("work_counters") if isinstance(root, Mapping) else None
        if not isinstance(counters, Mapping):
            raise T101IncompleteError("per-particle Search work counters are missing")
        for key, value in counters.items():
            if key != "schema_id":
                values[str(key)].append(
                    float(_nonnegative_int(value, f"work counter {key}"))
                )
    return {key: _distribution(row) for key, row in sorted(values.items())}


def validate_t101_formal_rows(
    rows: Iterable[Mapping[str, object]], plan: Mapping[str, object]
) -> list[dict[str, object]]:
    plan = validate_t101_formal_plan(plan)
    jobs = plan.get("jobs")
    assert isinstance(jobs, Sequence) and not isinstance(jobs, (str, bytes))
    expected = {
        (job["selection_identity"], job["replicate_index"]): job
        for job in jobs
        if isinstance(job, Mapping)
    }
    result = [dict(row) for row in rows]
    observed: set[tuple[object, object]] = set()
    for row in result:
        key = (row.get("selection_identity"), row.get("replicate_index"))
        job = expected.get(key)
        if job is None or key in observed:
            raise T101IncompleteError("formal row is substituted or duplicated")
        if (
            row.get("stratum") != job["stratum"]
            or row.get("sampler_seed") != job["sampler_seed"]
            or row.get("job_ordinal") != job["job_ordinal"]
            or row.get("shard_index") != job["shard_index"]
            or row.get("retry_reason")
            not in {None, "operational_failure_identical_inputs"}
        ):
            raise T101IncompleteError("formal row identity/configuration drifted")
        expected_status = (
            "success_after_operational_retry"
            if row.get("retry_reason") == "operational_failure_identical_inputs"
            else "success_no_retry"
        )
        if row.get("failure_retry_status") != expected_status:
            raise T101IncompleteError("formal failure/retry status is incomplete")
        report = validate_t101_bridge_report(
            row.get("bridge_report"), particle_count=32
        )
        if report["sampler_seed_input"] != job["sampler_seed"]:
            raise T101IncompleteError("formal bridge sampler seed drifted")
        wall = _finite(row.get("wall_clock_time_s"), "formal N32 wall time")
        if wall < 0:
            raise T101IncompleteError("formal wall time must be non-negative")
        observed.add(key)
    if observed != set(expected):
        raise T101IncompleteError("formal evidence is incomplete")
    return sorted(result, key=lambda row: int(row["job_ordinal"]))


def _distribution(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {"count": 0, "values": []}
    return {
        "count": len(values),
        "minimum": min(values),
        "median": median(values),
        "mean": fmean(values),
        "maximum": max(values),
        "values": list(values),
    }


def analyze_t101_formal(
    rows: Iterable[Mapping[str, object]], plan: Mapping[str, object]
) -> dict[str, object]:
    """Validate the complete 96-job matrix and produce frozen T101 metrics."""

    formal = validate_t101_formal_rows(rows, plan)
    analyses: list[dict[str, object]] = []
    for row in formal:
        analysis = analyze_t101_batch(row["bridge_report"])
        analyses.append(
            {
                "selection_identity": row["selection_identity"],
                "stratum": row["stratum"],
                "replicate_index": row["replicate_index"],
                "sampler_seed": row["sampler_seed"],
                **analysis,
            }
        )
    by_state: dict[str, list[dict[str, object]]] = defaultdict(list)
    for analysis in analyses:
        by_state[str(analysis["selection_identity"])].append(analysis)
    replicate_stability: list[dict[str, object]] = []
    unanimous_references: dict[str, list[str]] = {}
    for identity, state_rows in sorted(by_state.items()):
        if len(state_rows) != T101_REPLICATES:
            raise T101IncompleteError("state does not have four sampler replicates")
        reference_partition = state_rows[0]["decision_class_partition"]
        reference_actions = state_rows[0]["ordered_public_legal_actions"]
        reference_projection = state_rows[0]["public_information_projection"]
        if any(
            row["decision_class_partition"] != reference_partition
            or row["ordered_public_legal_actions"] != reference_actions
            or row["public_information_projection"] != reference_projection
            for row in state_rows[1:]
        ):
            raise T101IncompleteError(
                "public projection, actions, or Search-equivalence partition changed "
                "across replicates"
            )
        best_sets: list[list[str]] = []
        class_means: dict[str, list[float]] = defaultdict(list)
        for state_row in sorted(
            state_rows, key=lambda item: int(item["replicate_index"])
        ):
            metrics = state_row["metrics"]
            n32 = next(item for item in metrics if item["particle_count"] == 32)
            best_sets.append(list(n32["best_decision_class_set"]))
            for class_row in n32["decision_classes"]:
                class_means[str(class_row["decision_class_id"])].append(
                    float(class_row[T101_VALUE_SEMANTICS])
                )
        encoded = [json.dumps(item, separators=(",", ":")) for item in best_sets]
        counts = Counter(encoded)
        unanimous = len(counts) == 1
        if unanimous:
            unanimous_references[identity] = best_sets[0]
        replicate_stability.append(
            {
                "selection_identity": identity,
                "stratum": state_rows[0]["stratum"],
                "replicate_best_decision_class_sets": best_sets,
                "distinct_best_set_count": len(counts),
                "all_four_exactly_identical": unanimous,
                "modal_best_set_share": max(counts.values()) / T101_REPLICATES,
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
                    for metric in analysis["metrics"]
                    if metric["particle_count"] == count
                )["best_decision_class_set"]
                == unanimous_references[str(analysis["selection_identity"])]
                for analysis in analyses
            ):
                smallest = count
                break

    def cohort_summary(
        label: str, selected: Sequence[dict[str, object]]
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "label": label,
            "state_replicate_count": len(selected),
        }
        for count in T101_COUNTS:
            metrics = [
                next(item for item in row["metrics"] if item["particle_count"] == count)
                for row in selected
            ]
            result[str(count)] = {
                "best_set_agreement_count": sum(
                    item["best_set_exact_agreement_with_n32"] is True
                    for item in metrics
                ),
                "best_set_agreement_fraction": (
                    sum(
                        item["best_set_exact_agreement_with_n32"] is True
                        for item in metrics
                    )
                    / len(metrics)
                    if metrics
                    else None
                ),
                "reference_proxy_opportunity_gap": _distribution(
                    [
                        float(item["n32_reference_proxy_opportunity_gap"])
                        for item in metrics
                    ]
                ),
                "maximum_mean_drift": _distribution(
                    [
                        float(item["maximum_absolute_class_mean_drift_from_n32"])
                        for item in metrics
                    ]
                ),
                "rank_agreement": _distribution(
                    [float(item["rank_agreement_with_n32"]) for item in metrics]
                ),
            }
        state_ids = {str(row["selection_identity"]) for row in selected}
        stability = [
            row for row in replicate_stability if row["selection_identity"] in state_ids
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
        if next(item for item in row["metrics"] if item["particle_count"] == 32)[
            "decision_class_count"
        ]
        >= 2
    ]
    summaries = [cohort_summary("all", analyses)]
    summaries.extend(
        cohort_summary(stratum, [row for row in analyses if row["stratum"] == stratum])
        for stratum in T101_SOURCE_COUNTS
    )
    summaries.append(cohort_summary("multi_class_informative", informative))

    formal_cost_rows: list[dict[str, object]] = []
    for row in formal:
        report = row["bridge_report"]
        prefix_sums = {
            str(count): _work_counter_sums(report["particles"][:count])
            for count in T101_COUNTS
        }
        prefix_distributions = {
            str(count): _work_counter_distributions(report["particles"][:count])
            for count in T101_COUNTS
        }
        formal_cost_rows.append(
            {
                "selection_identity": row["selection_identity"],
                "replicate_index": row["replicate_index"],
                "particle_count": 32,
                "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                "wall_clock_time_s": row["wall_clock_time_s"],
                "worker_id": row.get("worker_id"),
                "shard_index": row["shard_index"],
                "effective_concurrency": row.get("effective_concurrency"),
                "failure_retry_status": row["failure_retry_status"],
                "retry_reason": row.get("retry_reason"),
                "prefix_work_counters": prefix_sums,
                "prefix_work_counter_distributions": prefix_distributions,
            }
        )
    terminal = (
        "BOUNDED_PARTICLE_PROXY_STABILITY_OBSERVED"
        if all_unanimous and smallest is not None
        else "BOUNDED_PARTICLE_PROXY_STABILITY_NOT_ESTABLISHED"
    )
    return {
        "schema_id": "t101-convergence-analysis-v1",
        "task_id": T101_TASK_ID,
        "terminal_classification": terminal,
        "value_semantics": T101_VALUE_SEMANTICS,
        "information_regime": (
            "normal_belief_search_outer_full_simulator_state_oracle_like_continuation"
        ),
        "n32_reference_unanimous_all_states": all_unanimous,
        "smallest_uniform_prefix_n": smallest,
        "state_replicate_metrics": analyses,
        "across_sampler_replicates": replicate_stability,
        "cohort_summaries": summaries,
        "cost_report": {
            "schema_id": "t101-cost-report-v1",
            "task_id": T101_TASK_ID,
            "support_admission": dict(plan["support_admission_cost"]),
            "formal_topology": dict(plan["topology"]),
            "formal_n32_calls": formal_cost_rows,
            "formal_n32_wall_clock_time_s": _distribution(
                [float(row["wall_clock_time_s"]) for row in formal]
            ),
            "sum_formal_n32_call_wall_clock_time_s": sum(
                float(row["wall_clock_time_s"]) for row in formal
            ),
            "n2_to_n32_work_change": {
                key: {
                    "n2_total": (
                        n2_total := sum(
                            int(row["prefix_work_counters"]["2"].get(key, 0))
                            for row in formal_cost_rows
                        )
                    ),
                    "n32_total": (
                        n32_total := sum(
                            int(row["prefix_work_counters"]["32"].get(key, 0))
                            for row in formal_cost_rows
                        )
                    ),
                    "absolute_increase": n32_total - n2_total,
                    "multiplicative_factor": (
                        n32_total / n2_total if n2_total else None
                    ),
                }
                for key in sorted(
                    {
                        name
                        for row in formal_cost_rows
                        for name in row["prefix_work_counters"]["32"]
                    }
                )
            },
            "prefix_wall_time_claim": "not_computed_from_formal_n32_calls",
        },
        "semantic_boundary": {
            "offline_descriptive_aggregation_only": True,
            "aggregate_action_executed": False,
            "controller_created": False,
            "particle_count_above_32_executed": False,
        },
    }


def build_t101_retention_manifest(
    artifacts: Mapping[str, Mapping[str, object]],
    *,
    producer_provenance: Mapping[str, object],
    regeneration_commands: Sequence[str],
    retention_reason: str,
    deletion_condition: str,
) -> dict[str, object]:
    missing = sorted(T101_REQUIRED_RETENTION_ROLES - set(artifacts))
    if missing:
        raise T101IncompleteError(
            "retention manifest is missing roles: " + ", ".join(missing)
        )
    normalized: dict[str, dict[str, object]] = {}
    for role, reference in sorted(artifacts.items()):
        if (
            not isinstance(reference.get("path"), str)
            or not reference["path"]
            or not isinstance(reference.get("schema_id"), str)
            or not reference["schema_id"]
            or reference["schema_id"] != T101_RETENTION_ROLE_SCHEMAS.get(role)
            or not isinstance(reference.get("sha256"), str)
            or len(reference["sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(reference["sha256"])
            )
            or isinstance(reference.get("size_bytes"), bool)
            or not isinstance(reference.get("size_bytes"), int)
            or reference["size_bytes"] < 0
        ):
            raise T101IncompleteError(f"retained artifact {role} reference is invalid")
        normalized[role] = dict(reference)
    if (
        set(producer_provenance)
        != {
            "task_id",
            "implementation_head",
            "native_identity",
            "input_admission_artifact_sha256",
            "cohort_admission_artifact_sha256",
            "formal_plan_artifact_sha256",
        }
        or producer_provenance.get("task_id") != T101_TASK_ID
    ):
        raise T101IncompleteError("retention producer provenance is incomplete")
    provenance = dict(producer_provenance)
    provenance["implementation_head"] = _implementation_head(
        provenance.get("implementation_head")
    )
    provenance["native_identity"] = validate_t101_native_identity(
        provenance.get("native_identity")
    )
    for name in (
        "input_admission_artifact_sha256",
        "cohort_admission_artifact_sha256",
        "formal_plan_artifact_sha256",
    ):
        provenance[name] = _sha256_text(provenance.get(name), name)
    if not regeneration_commands or not all(regeneration_commands):
        raise T101IncompleteError("retention regeneration commands are missing")
    if not retention_reason or not deletion_condition:
        raise T101IncompleteError("retention reason/deletion condition is missing")
    return {
        "schema_id": "t101-retention-manifest-v1",
        "task_id": T101_TASK_ID,
        "producer_provenance": provenance,
        "artifact_references": normalized,
        "regeneration_commands": list(regeneration_commands),
        "retention_reason": retention_reason,
        "raw_deletion_condition": deletion_condition,
    }


__all__ = [
    "T101_COUNTS",
    "T101_NATIVE_COMMIT",
    "T101_REQUIRED_INPUT_ROLES",
    "T101_REQUIRED_RETENTION_ROLES",
    "T101_RETENTION_ROLE_SCHEMAS",
    "T101AdmissionExclusion",
    "T101IncompleteError",
    "analyze_t101_batch",
    "analyze_t101_formal",
    "build_t101_formal_plan",
    "build_t101_input_admission",
    "build_t101_retention_manifest",
    "call_t101_bridge",
    "derive_t101_sampler_seed",
    "select_t101_cohort",
    "validate_t101_bridge_report",
    "validate_t101_canary_evidence",
    "validate_t101_canary_ladder",
    "validate_t101_formal_plan",
    "validate_t101_formal_rows",
    "validate_t101_input_admission",
    "validate_t101_native_identity",
    "validate_t101_selected_cohort",
]
