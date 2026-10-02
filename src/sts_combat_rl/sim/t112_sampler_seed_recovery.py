"""T112 contracts for the bounded configured-Search N=2 recovery.

Execution is deliberately orchestrated by the command layer. This module
contains only deterministic record transformations and validators; it never
loads the native extension or creates a simulator.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence

from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_REF,
    T111SupportExclusion,
    validate_t111_configured_search_cohort,
    validate_t111_configured_search_report,
)

T112_TASK_ID = "T112"
T112_APPROVED_SPEC_COMMIT = "bd7a04a25bce2677c8dcf6a5e1c03751b43de90f"
T112_NATIVE_COMMIT = "6496fc1c7e629a374b72bd94f7fd29afe29c7f62"
T112_NATIVE_REF = T111_NATIVE_REF
T112_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": T112_NATIVE_REF,
    "commit": T112_NATIVE_COMMIT,
}
T112_TERMINALS = frozenset(
    {
        "SAMPLER_SEED_CONTRACT_REPAIR_INVALID",
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED",
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT",
    }
)
T112_COHORT_SCHEMA = "t112-configured-search-cohort-admission-v1"
T112_ATTEMPTS_SCHEMA = "t112-candidate-attempts-jsonl-v1"
T112_WITNESS_SCHEMA = "t112-native-n2-witness-v1"
T112_REPAIR_PROVENANCE_SCHEMA = "t112-validator-repair-provenance-v1"
T112_BRIDGE_SCHEMA = "native-battle-public-particle-search-v2"
T112_REPAIR_FACTS = {
    "corrected_invariants": {
        "bridge_input_seed": "sampler_seed_input equals the T101-derived seed S",
        "particle_seed": "sampler_seed is native-derived metadata indexed by particle",
        "particle_seed_equals_bridge_input_required": False,
        "hidden_particle_seed_reimplemented_in_python": False,
    },
    "unchanged_boundaries": {
        "strict_t099_t110_v2_schema": True,
        "particle_seed_type_and_index_validation": True,
        "non_seed_support_predicates": True,
        "active_t101_false_equality_removed": True,
        "historical_artifacts_rewritten": False,
    },
}


class T112RecoveryError(ValueError):
    """T112 qualification, witness, or bounded cohort evidence is invalid."""


def t112_terminal_from_t111(value: object) -> str:
    """Map the reused T111 selector result into a T112-owned terminal."""

    cohort = validate_t111_configured_search_cohort(value)
    if (
        cohort["terminal_classification"]
        == "CONFIGURED_SEARCH_DOMAIN_SUPPORT_SUFFICIENT"
    ):
        return "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
    return "CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT"


def safe_t112_seed_metadata(
    report: object, *, expected_sampler_seed: int, bridge_report_sha256: str
) -> dict[str, object]:
    """Extract only the validated bridge-input and indexed particle seed fields."""

    if not isinstance(report, Mapping) or report.get("schema_id") != T112_BRIDGE_SCHEMA:
        raise T112RecoveryError("T112 witness report schema is invalid")
    particles = report.get("particles")
    if (
        isinstance(expected_sampler_seed, bool)
        or not isinstance(expected_sampler_seed, int)
        or not 0 <= expected_sampler_seed < 2**64
        or report.get("sampler_seed_input") != expected_sampler_seed
        or not isinstance(particles, list)
        or len(particles) != 2
        or not isinstance(bridge_report_sha256, str)
        or len(bridge_report_sha256) != 64
        or any(char not in "0123456789abcdef" for char in bridge_report_sha256)
    ):
        raise T112RecoveryError("T112 seed metadata is not bound to the bridge input")
    try:
        validated = validate_t111_configured_search_report(
            report,
            expected_sampler_seed=expected_sampler_seed,
            particle_count=2,
        )
    except T111SupportExclusion as exc:
        raise T112RecoveryError(
            "T112 bridge report failed strict T111 validation"
        ) from exc
    if validated.get("bridge_report_sha256") != bridge_report_sha256:
        raise T112RecoveryError("T112 bridge report hash does not match actual report")
    safe_particles: list[dict[str, int]] = []
    for expected_index, particle in enumerate(particles):
        if not isinstance(particle, Mapping):
            raise T112RecoveryError("T112 particle seed metadata is malformed")
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
            raise T112RecoveryError("T112 particle seed metadata is malformed")
        safe_particles.append({"particle_index": index, "sampler_seed": seed})
    safe = {
        "schema_id": T112_BRIDGE_SCHEMA,
        "sampler_seed_input": expected_sampler_seed,
        "bridge_report_sha256": bridge_report_sha256,
        "particles": safe_particles,
    }
    return validate_t112_safe_seed_metadata(
        safe,
        expected_sampler_seed=expected_sampler_seed,
        expected_bridge_report_sha256=bridge_report_sha256,
    )


def validate_t112_safe_seed_metadata(
    value: object,
    *,
    expected_sampler_seed: int,
    expected_bridge_report_sha256: str,
) -> dict[str, object]:
    """Check the retained safe projection after the raw report is discarded."""

    if not isinstance(value, Mapping) or set(value) != {
        "schema_id",
        "sampler_seed_input",
        "bridge_report_sha256",
        "particles",
    }:
        raise T112RecoveryError("T112 safe seed metadata schema is invalid")
    particles = value.get("particles")
    report_sha = value.get("bridge_report_sha256")
    if (
        value.get("schema_id") != T112_BRIDGE_SCHEMA
        or value.get("sampler_seed_input") != expected_sampler_seed
        or isinstance(expected_sampler_seed, bool)
        or not isinstance(expected_sampler_seed, int)
        or not 0 <= expected_sampler_seed < 2**64
        or report_sha != expected_bridge_report_sha256
        or not isinstance(report_sha, str)
        or len(report_sha) != 64
        or any(char not in "0123456789abcdef" for char in report_sha)
        or not isinstance(particles, list)
        or len(particles) != 2
    ):
        raise T112RecoveryError("T112 safe seed metadata binding is invalid")
    safe_particles: list[dict[str, int]] = []
    for index, particle in enumerate(particles):
        if not isinstance(particle, Mapping) or set(particle) != {
            "particle_index",
            "sampler_seed",
        }:
            raise T112RecoveryError("T112 particle seed metadata is malformed")
        particle_index = particle.get("particle_index")
        particle_seed = particle.get("sampler_seed")
        if (
            isinstance(particle_index, bool)
            or not isinstance(particle_index, int)
            or particle_index != index
            or isinstance(particle_seed, bool)
            or not isinstance(particle_seed, int)
            or not 0 <= particle_seed < 2**64
        ):
            raise T112RecoveryError("T112 particle seed metadata is malformed")
        safe_particles.append(
            {"particle_index": particle_index, "sampler_seed": particle_seed}
        )
    return {
        "schema_id": T112_BRIDGE_SCHEMA,
        "sampler_seed_input": expected_sampler_seed,
        "bridge_report_sha256": report_sha,
        "particles": safe_particles,
    }


def t112_cohort_from_t111(
    value: object,
    *,
    implementation_head: str,
    approved_spec_commit: str = T112_APPROVED_SPEC_COMMIT,
    witness_sha256: str,
    seed_metadata_by_identity: Mapping[str, Mapping[str, object]] | None = None,
    bridge_call_count_by_identity: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Create a new T112 record from this run's T111-selector observations.

    The T111 cohort is validated first and is never edited or relabeled in
    place. The returned object has a T112 schema and T112-specific provenance.
    """

    cohort = validate_t111_configured_search_cohort(value)
    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(character not in "0123456789abcdef" for character in implementation_head)
        or approved_spec_commit != T112_APPROVED_SPEC_COMMIT
        or not isinstance(witness_sha256, str)
        or len(witness_sha256) != 64
        or any(character not in "0123456789abcdef" for character in witness_sha256)
    ):
        raise T112RecoveryError("T112 provenance binding is malformed")
    if cohort.get("native_identity") != T112_NATIVE_IDENTITY:
        raise T112RecoveryError("T112 native identity changed")
    attempted = cohort.get("attempted")
    selected = cohort.get("selected")
    exhausted = cohort.get("exhausted_strata")
    if not isinstance(attempted, Sequence) or not isinstance(selected, Sequence):
        raise T112RecoveryError("T112 selector evidence is malformed")
    if not isinstance(exhausted, Sequence) or isinstance(exhausted, (str, bytes)):
        raise T112RecoveryError("T112 exhaustion evidence is malformed")
    # The selector already enforces exact T101 order and first-eight stopping.
    # Recheck the no-retry contract at the task-owned artifact boundary.
    if any(
        not isinstance(row, Mapping)
        or row.get("failure_retry_status")
        not in {"failed_no_retry", "success_no_retry"}
        or row.get("replicate_index") != 0
        or row.get("native_identity") != T112_NATIVE_IDENTITY
        for row in attempted
    ):
        raise T112RecoveryError("T112 attempt retry or identity evidence changed")
    terminal = t112_terminal_from_t111(cohort)
    selected_counts = {
        stratum: sum(
            isinstance(row, Mapping) and row.get("stratum") == stratum
            for row in selected
        )
        for stratum in T101_SOURCE_COUNTS
    }
    if selected_counts != dict(cohort["selected_counts"]):
        raise T112RecoveryError("T112 selected counts disagree with exact rows")
    seed_metadata = seed_metadata_by_identity or {}
    bridge_call_counts = bridge_call_count_by_identity or {}
    t112_selected: list[dict[str, object]] = []
    for row in selected:
        copied = dict(row)
        copied["sampler_seed_input"] = copied.pop("sampler_seed")
        copied["task_id"] = T112_TASK_ID
        copied["native_bridge_call_count"] = bridge_call_counts.get(
            str(copied.get("selection_identity")), 0
        )
        t112_selected.append(copied)
    t112_attempts: list[dict[str, object]] = []
    for row in attempted:
        copied = dict(row)
        identity = str(copied.pop("selection_identity"))
        # T111's legacy attempt field was named sampler_seed and represented
        # the bridge input. T112 makes that meaning explicit and retains the
        # native-owned values only as indexed metadata from accepted reports.
        bridge_seed = copied.pop("sampler_seed")
        copied["selection_identity"] = identity
        copied["task_id"] = T112_TASK_ID
        copied["sampler_seed_input"] = bridge_seed
        copied["particle_sampler_seed_metadata"] = dict(
            seed_metadata.get(
                identity,
                {
                    "schema_id": None,
                    "bridge_report_sha256": None,
                    "sampler_seed_input": None,
                    "particles": None,
                },
            )
        )
        copied["native_bridge_call_count"] = bridge_call_counts.get(identity, 0)
        t112_attempts.append(copied)
    return {
        "schema_id": T112_COHORT_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": implementation_head,
        "approved_spec_commit": approved_spec_commit,
        "witness_sha256": witness_sha256,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "selection_rule": cohort["selection_rule"],
        "selection_uses_value_or_outcome": False,
        "historical_failure_label_preselection": False,
        "historical_t111_attempts_used_for_admission": False,
        "particle_start": 0,
        "particle_count": 2,
        "replicate_index": 0,
        "search_simulations_per_particle": 400,
        "include_potions": False,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "attempted": t112_attempts,
        "selected": t112_selected,
        "selected_counts": selected_counts,
        "exhausted_strata": list(exhausted),
        "terminal_classification": terminal,
    }


def validate_t112_cohort(value: object) -> dict[str, object]:
    """Validate the T112-only terminal vocabulary and bounded stop rule."""

    if not isinstance(value, Mapping) or value.get("schema_id") != T112_COHORT_SCHEMA:
        raise T112RecoveryError("T112 cohort schema mismatch")
    expected_fields = {
        "schema_id",
        "task_id",
        "implementation_head",
        "approved_spec_commit",
        "witness_sha256",
        "source_counts",
        "selection_rule",
        "selection_uses_value_or_outcome",
        "historical_failure_label_preselection",
        "historical_t111_attempts_used_for_admission",
        "particle_start",
        "particle_count",
        "replicate_index",
        "search_simulations_per_particle",
        "include_potions",
        "native_identity",
        "attempted",
        "selected",
        "selected_counts",
        "exhausted_strata",
        "terminal_classification",
    }
    if set(value) != expected_fields:
        raise T112RecoveryError("T112 cohort fields changed")
    head = value.get("implementation_head")
    witness_sha = value.get("witness_sha256")
    if (
        value.get("task_id") != T112_TASK_ID
        or not isinstance(head, str)
        or len(head) != 40
        or any(character not in "0123456789abcdef" for character in head)
        or value.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or not isinstance(witness_sha, str)
        or len(witness_sha) != 64
        or any(character not in "0123456789abcdef" for character in witness_sha)
        or value.get("source_counts") != T101_SOURCE_COUNTS
        or value.get("selection_rule")
        != "sha256-selection-identity-then-canonical-identity-v1"
        or value.get("selection_uses_value_or_outcome") is not False
        or value.get("historical_failure_label_preselection") is not False
        or value.get("historical_t111_attempts_used_for_admission") is not False
        or isinstance(value.get("particle_start"), bool)
        or not isinstance(value.get("particle_start"), int)
        or value.get("particle_start") != 0
        or isinstance(value.get("particle_count"), bool)
        or not isinstance(value.get("particle_count"), int)
        or value.get("particle_count") != 2
        or isinstance(value.get("replicate_index"), bool)
        or not isinstance(value.get("replicate_index"), int)
        or value.get("replicate_index") != 0
        or isinstance(value.get("search_simulations_per_particle"), bool)
        or not isinstance(value.get("search_simulations_per_particle"), int)
        or value.get("search_simulations_per_particle") != 400
        or value.get("include_potions") is not False
        or value.get("native_identity") != T112_NATIVE_IDENTITY
    ):
        raise T112RecoveryError("T112 frozen configuration/provenance changed")
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
        raise T112RecoveryError("T112 attempt/selection rows are malformed")
    attempted_ids: set[str] = set()
    observed_attempt_strata: list[str] = []
    rows_by_stratum: dict[str, list[Mapping[str, object]]] = {
        stratum: [] for stratum in T101_SOURCE_COUNTS
    }
    for row in attempted:
        if not isinstance(row, Mapping):
            raise T112RecoveryError("T112 attempt row is malformed")
        identity = row.get("selection_identity")
        stratum = row.get("stratum")
        ordinal = row.get("source_ordinal")
        seed = row.get("sampler_seed_input")
        selection_digest = row.get("selection_digest")
        bridge_call_count = row.get("native_bridge_call_count")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in attempted_ids
            or stratum not in T101_SOURCE_COUNTS
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal < 0
            or selection_digest != hashlib.sha256(identity.encode("utf-8")).hexdigest()
            or isinstance(seed, bool)
            or not isinstance(seed, int)
            or not 0 <= seed < 2**64
            or seed != derive_t101_sampler_seed(identity, 0)
            or isinstance(row.get("replicate_index"), bool)
            or not isinstance(row.get("replicate_index"), int)
            or row.get("replicate_index") != 0
            or row.get("native_identity") != T112_NATIVE_IDENTITY
            or row.get("task_id") != T112_TASK_ID
            or not isinstance(row.get("admitted"), bool)
            or row.get("failure_retry_status")
            not in {"failed_no_retry", "success_no_retry"}
            or (row.get("admitted") is True)
            != (row.get("failure_retry_status") == "success_no_retry")
            or isinstance(bridge_call_count, bool)
            or not isinstance(bridge_call_count, int)
            or bridge_call_count != 1
        ):
            raise T112RecoveryError("T112 attempt identity/seed/retry evidence invalid")
        attempted_ids.add(identity)
        observed_attempt_strata.append(stratum)
        rows_by_stratum[stratum].append(row)
    selected_ids: set[str] = set()
    selected_by_stratum = Counter()
    selected_counts = value.get("selected_counts")
    if (
        not isinstance(selected_counts, Mapping)
        or set(selected_counts) != set(T101_SOURCE_COUNTS)
        or any(
            isinstance(selected_counts[stratum], bool)
            or not isinstance(selected_counts[stratum], int)
            or selected_counts[stratum] < 0
            or selected_counts[stratum] > 8
            for stratum in T101_SOURCE_COUNTS
        )
    ):
        raise T112RecoveryError("T112 selected counts are malformed")
    for row in selected:
        if not isinstance(row, Mapping):
            raise T112RecoveryError("T112 selected row is malformed")
        identity = row.get("selection_identity")
        stratum = row.get("stratum")
        if (
            not isinstance(identity, str)
            or identity in selected_ids
            or identity not in attempted_ids
            or stratum not in T101_SOURCE_COUNTS
            or isinstance(row.get("native_bridge_call_count"), bool)
            or not isinstance(row.get("native_bridge_call_count"), int)
            or row.get("native_bridge_call_count") != 1
            or row.get("task_id") != T112_TASK_ID
            or isinstance(row.get("sampler_seed_input"), bool)
            or not isinstance(row.get("sampler_seed_input"), int)
            or row.get("sampler_seed_input") != derive_t101_sampler_seed(identity, 0)
            or isinstance(row.get("replicate_index"), bool)
            or not isinstance(row.get("replicate_index"), int)
            or row.get("replicate_index") != 0
        ):
            raise T112RecoveryError("T112 selected identity is invalid")
        selected_ids.add(identity)
        selected_by_stratum[stratum] += 1
    if dict(selected_counts) != {
        stratum: selected_by_stratum[stratum] for stratum in T101_SOURCE_COUNTS
    }:
        raise T112RecoveryError("T112 selected counts mismatch")
    expected_selected = [
        {
            "selection_identity": row["selection_identity"],
            "task_id": T112_TASK_ID,
            "stratum": row["stratum"],
            "selection_digest": row["selection_digest"],
            "sampler_seed_input": row["sampler_seed_input"],
            "replicate_index": 0,
            "native_bridge_call_count": row["native_bridge_call_count"],
        }
        for row in attempted
        if row.get("admitted") is True
    ]
    if list(selected) != expected_selected:
        raise T112RecoveryError(
            "T112 selected identities differ from admitted attempts"
        )
    if observed_attempt_strata != [
        stratum for stratum, rows in rows_by_stratum.items() for _ in rows
    ]:
        raise T112RecoveryError("T112 attempts are not in T101 stratum order")
    for stratum, rows in rows_by_stratum.items():
        if len(rows) > T101_SOURCE_COUNTS[stratum]:
            raise T112RecoveryError("T112 attempted beyond source stratum")
        ordinals = [row.get("source_ordinal") for row in rows]
        if ordinals != list(range(len(rows))):
            raise T112RecoveryError("T112 candidates are not contiguous source order")
        keys = [
            (str(row["selection_digest"]), str(row["selection_identity"]))
            for row in rows
        ]
        if keys != sorted(keys):
            raise T112RecoveryError("T112 candidates are not in T101 hash order")
        accepted = sum(row.get("admitted") is True for row in rows)
        if accepted > 8 or (accepted == 8 and rows[-1].get("admitted") is not True):
            raise T112RecoveryError("T112 selector exceeded first-eight stop boundary")
        if accepted < 8 and len(rows) != T101_SOURCE_COUNTS[stratum]:
            raise T112RecoveryError("T112 exhausted stratum is incomplete")
        successes_seen = 0
        for index, row in enumerate(rows):
            successes_seen += row.get("admitted") is True
            if successes_seen == 8 and index != len(rows) - 1:
                raise T112RecoveryError("T112 admitted beyond the first eight")
            metadata = row.get("particle_sampler_seed_metadata")
            if row.get("admitted") is True:
                if not isinstance(metadata, Mapping):
                    raise T112RecoveryError(
                        "T112 admitted row lacks particle seed metadata"
                    )
                expected_metadata = validate_t112_safe_seed_metadata(
                    metadata,
                    expected_sampler_seed=int(row["sampler_seed_input"]),
                    expected_bridge_report_sha256=str(
                        row.get("bridge_report_sha256", "")
                    ),
                )
                if dict(metadata) != expected_metadata:
                    raise T112RecoveryError(
                        "T112 particle seed metadata binding changed"
                    )
                if metadata.get("bridge_report_sha256") != row.get(
                    "bridge_report_sha256"
                ):
                    raise T112RecoveryError(
                        "T112 safe seed/report hashes disagree with admission row"
                    )
            elif metadata != {
                "schema_id": None,
                "bridge_report_sha256": None,
                "sampler_seed_input": None,
                "particles": None,
            }:
                raise T112RecoveryError(
                    "T112 rejected row retained unvalidated seed metadata"
                )
        if selected_by_stratum[stratum] != accepted:
            raise T112RecoveryError("T112 selected/attempt rows disagree")
    expected_exhausted = [
        stratum for stratum in T101_SOURCE_COUNTS if selected_by_stratum[stratum] < 8
    ]
    if list(exhausted) != expected_exhausted:
        raise T112RecoveryError("T112 exhausted stratum evidence mismatch")
    terminal = value.get("terminal_classification")
    expected_terminal = (
        "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
        if not expected_exhausted
        else "CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT"
    )
    if terminal not in T112_TERMINALS or terminal != expected_terminal:
        raise T112RecoveryError("T112 terminal classification is invalid")
    return dict(value)


__all__ = [
    "T112_APPROVED_SPEC_COMMIT",
    "T112_COHORT_SCHEMA",
    "T112_NATIVE_COMMIT",
    "T112_NATIVE_IDENTITY",
    "T112_NATIVE_REF",
    "T112_REPAIR_FACTS",
    "T112_REPAIR_PROVENANCE_SCHEMA",
    "T112_TERMINALS",
    "T112_WITNESS_SCHEMA",
    "T112RecoveryError",
    "safe_t112_seed_metadata",
    "t112_cohort_from_t111",
    "t112_terminal_from_t111",
    "validate_t112_cohort",
    "validate_t112_safe_seed_metadata",
]
