from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from test_t110_configuration_aware_mapping import _v2_report

from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_SOURCE_COUNTS,
    T101IncompleteError,
    derive_t101_sampler_seed,
    validate_t101_bridge_report,
)
from sts_combat_rl.sim.t112_sampler_seed_recovery import (
    T112_APPROVED_SPEC_COMMIT,
    T112_COHORT_SCHEMA,
    T112_NATIVE_IDENTITY,
    validate_t112_cohort,
)
from sts_combat_rl.sim.t113_configured_particle_convergence import (
    T113_APPROVED_SPEC_COMMIT,
    T113_EXACT_T112_COHORT_SHA256,
    T113_EXACT_T112_RETENTION_SHA256,
    T113ConvergenceError,
    analyze_t113_batch,
    build_t113_fixed_cohort,
    build_t113_formal_plan,
    validate_t113_bridge_report,
    validate_t113_canary_ladder,
    validate_t113_fixed_cohort,
    validate_t113_formal_plan,
)


def _batch_report(
    *, seed: int | None = None, particle_count: int = 32
) -> dict[str, object]:
    report = _v2_report()
    bridge_seed = seed if seed is not None else derive_t101_sampler_seed("A:fixture", 0)
    first = report["particles"][0]
    first["sampler_seed"] = 0xA5100000
    first["root_evaluation"]["simulations_requested"] = 400
    first["root_evaluation"]["root_visits"] = 800
    report["search_simulations"] = 400
    particles = []
    for index in range(particle_count):
        particle = deepcopy(first)
        particle["particle_index"] = index
        particle["sampler_seed"] = 0xA5100000 + index
        particle["hidden_future_fingerprint"] = f"audit-fingerprint-{index}"
        root = particle["root_evaluation"]
        base = float(index + 1)
        for rows in (particle["root_rows"], root["root_rows"]):
            rows[0]["mean_value"] = base
            rows[0]["evaluation_sum"] = base * rows[0]["visits"]
            rows[1]["mean_value"] = float((index % 5) - 2)
            rows[1]["evaluation_sum"] = rows[1]["mean_value"] * rows[1]["visits"]
            rows[2]["mean_value"] = rows[1]["mean_value"]
            rows[2]["evaluation_sum"] = rows[1]["evaluation_sum"]
        particles.append(particle)
    report["particle_count"] = particle_count
    report["sampler_seed_input"] = bridge_seed
    report["particles"] = particles
    return report


def _canary_call(count: int, report: dict[str, object]) -> dict[str, object]:
    return {
        "bridge_report": report,
        "wall_clock_time_s": float(count) / 4,
        "worker_id": "smoke-worker-0",
        "shard_index": 0,
        "effective_concurrency": 1,
        "failure_retry_status": "success_no_retry",
        "single_worker_reason": "bounded direct prefix validation fixture",
    }


def _ladder(identity: str, stratum: str) -> dict[str, object]:
    full = _batch_report(seed=derive_t101_sampler_seed(identity, 0))
    calls: dict[str, object] = {}
    for count in T101_COUNTS:
        direct = deepcopy(full)
        direct["particle_count"] = count
        direct["particles"] = deepcopy(full["particles"][:count])
        calls[str(count)] = _canary_call(count, direct)
    return {
        "selection_identity": identity,
        "stratum": stratum,
        "replicate_index": 0,
        "calls": calls,
    }


def _t112_cohort() -> dict[str, object]:
    attempted: list[dict[str, object]] = []
    selected: list[dict[str, object]] = []
    for stratum in T101_SOURCE_COUNTS:
        identities = [f"{stratum}:fixture:{index:03d}" for index in range(8)]
        identities.sort(
            key=lambda identity: (
                hashlib.sha256(identity.encode()).hexdigest(),
                identity,
            )
        )
        for ordinal, identity in enumerate(identities):
            seed = derive_t101_sampler_seed(identity, 0)
            report_hash = hashlib.sha256((identity + "-report").encode()).hexdigest()
            attempt = {
                "selection_identity": identity,
                "stratum": stratum,
                "source_ordinal": ordinal,
                "selection_digest": hashlib.sha256(identity.encode()).hexdigest(),
                "sampler_seed_input": seed,
                "replicate_index": 0,
                "native_identity": dict(T112_NATIVE_IDENTITY),
                "task_id": "T112",
                "admitted": True,
                "failure_retry_status": "success_no_retry",
                "native_bridge_call_count": 1,
                "candidate_execution_started": True,
                "bridge_report_sha256": report_hash,
                "particle_sampler_seed_metadata": {
                    "schema_id": "native-battle-public-particle-search-v2",
                    "sampler_seed_input": seed,
                    "bridge_report_sha256": report_hash,
                    "particles": [
                        {"particle_index": 0, "sampler_seed": 0xA5100000},
                        {"particle_index": 1, "sampler_seed": 0xA5100001},
                    ],
                },
            }
            attempted.append(attempt)
            selected.append(
                {
                    "selection_identity": identity,
                    "task_id": "T112",
                    "stratum": stratum,
                    "selection_digest": attempt["selection_digest"],
                    "sampler_seed_input": seed,
                    "replicate_index": 0,
                    "native_bridge_call_count": 1,
                    "candidate_execution_started": True,
                }
            )
    return {
        "schema_id": T112_COHORT_SCHEMA,
        "task_id": "T112",
        "implementation_head": "a" * 40,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "witness_sha256": "b" * 64,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "selection_rule": "sha256-selection-identity-then-canonical-identity-v1",
        "selection_uses_value_or_outcome": False,
        "historical_failure_label_preselection": False,
        "historical_t111_attempts_used_for_admission": False,
        "particle_start": 0,
        "particle_count": 2,
        "replicate_index": 0,
        "search_simulations_per_particle": 400,
        "include_potions": False,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "attempted": attempted,
        "selected": selected,
        "selected_counts": {"A": 8, "B": 8, "C": 8},
        "exhausted_strata": [],
        "terminal_classification": "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED",
    }


def _fixed_cohort(t112: dict[str, object]) -> dict[str, object]:
    return build_t113_fixed_cohort(
        t112,
        source_cohort_sha256=T113_EXACT_T112_COHORT_SHA256,
        source_population_binding={
            "t101_terminal_retention_manifest_sha256": "a" * 64,
            "t101_input_admission_sha256": "b" * 64,
            "ordered_identity_binding_sha256": "c" * 64,
            "record_count": 413,
            "source_counts": dict(T101_SOURCE_COUNTS),
            "historical_t101_attempt_order_exact": True,
            "t101_retained_reference_count_verified": 5,
        },
        t112_artifact_binding={
            "retention_manifest_sha256": T113_EXACT_T112_RETENTION_SHA256,
            "cohort_admission": {"sha256": T113_EXACT_T112_COHORT_SHA256},
            "final_report": {
                "sha256": "d14b67a1f3f76461cb2a356e52df2199c901d09b23c97f80379ac5293bf6b4c9"
            },
            "input_qualification": {"sha256": "e" * 64},
        },
    )


def test_t113_strict_adapter_uses_only_searched_classes_and_native_seed_metadata():
    seed = derive_t101_sampler_seed("A:fixture", 2)
    report = _batch_report(seed=seed)
    checked = validate_t113_bridge_report(
        report, particle_count=32, expected_sampler_seed=seed
    )

    assert checked["sampler_seed_input"] == seed
    assert checked["t113_native_particle_seed_metadata"][0] == {
        "particle_index": 0,
        "sampler_seed": 0xA5100000,
    }
    assert checked["t113_native_particle_seed_metadata"][0]["sampler_seed"] != seed
    assert report["anchor_public_information_projection"]["schema_id"] == (
        "native-battle-public-information-v2"
    )
    domain = checked["t113_configured_domain"]
    assert domain["classification_by_public_ordinal"] == [
        "searched_direct",
        "searched_direct",
        "searched_mechanical_duplicate_card_occurrence",
        "search_configuration_excluded",
        "search_configuration_excluded",
    ]
    assert domain["decision_class_partition"] == [
        {"source_edge_index": 0, "public_action_ordinals": [0]},
        {"source_edge_index": 1, "public_action_ordinals": [1, 2]},
    ]

    result = analyze_t113_batch(report, expected_sampler_seed=seed)
    assert len(result["ordered_public_legal_actions"]) == 5
    assert result["configuration_excluded_public_occurrence_count"] == 2
    assert [row["particle_count"] for row in result["metrics"]] == list(T101_COUNTS)
    for metric in result["metrics"]:
        assert metric["searched_decision_class_count"] == 2
        assert metric["configuration_excluded_public_occurrence_count"] == 2
        assert len(metric["decision_classes"]) == 2
        assert all(
            row["particle_support_count"] == metric["particle_count"]
            for row in metric["decision_classes"]
        )
        assert "regret" not in metric


def test_t113_does_not_reinterpret_historical_t101_all_public_value_contract():
    report = _batch_report()
    with pytest.raises(T101IncompleteError, match="root mean_value"):
        validate_t101_bridge_report(report, particle_count=32)


@pytest.mark.parametrize(
    "schema", ["native-battle-public-particle-search-v1", "unknown-v3"]
)
def test_t113_rejects_historical_or_unknown_bridge_schema(schema):
    report = _batch_report()
    report["schema_id"] = schema
    with pytest.raises(T113ConvergenceError, match="strict T110 v2"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


def test_t113_configuration_excluded_occurrence_cannot_become_numeric_zero():
    report = _batch_report()
    report["particles"][0]["root_rows"][3]["mean_value"] = 0.0
    report["particles"][0]["root_evaluation"]["root_rows"][3]["mean_value"] = 0.0
    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


def test_t113_rejects_unknown_classification_and_non_t096_projection_schemas():
    report = _batch_report()
    report["particles"][0]["root_rows"][0]["mapping_classification"] = "unclassified"
    report["particles"][0]["root_evaluation"]["root_action_mapping"][0][
        "mapping_classification"
    ] = "unclassified"
    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )

    report = _batch_report()
    report["anchor_public_information_projection"]["schema_id"] = (
        "native-public-projection-v1"
    )
    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


def test_t113_requires_exact_t096_to_t096_particle_projection_parity():
    report = _batch_report()
    report["particles"][1]["public_information_projection"]["player"]["current_hp"] -= 1
    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


@pytest.mark.parametrize("invalid_seed", [True, None, "native-seed"])
def test_t113_keeps_native_particle_seed_metadata_strict(invalid_seed):
    report = _batch_report()
    report["particles"][0]["sampler_seed"] = invalid_seed
    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


def test_t113_partition_drift_across_particles_fails_closed():
    report = _batch_report()
    particle = report["particles"][1]
    root = particle["root_evaluation"]
    row = particle["root_rows"][2]
    mapping = root["root_action_mapping"][2]
    action = report["anchor_ordered_public_legal_actions"][2]
    row.update(
        mapping_classification="searched_direct",
        search_edge_index=2,
        search_equivalence_source_edge_index=2,
        search_equivalence_mapping_mode="direct_action_bits",
    )
    mapping.update(
        mapping_classification="searched_direct",
        search_edge_index=2,
        mapping_mode="direct_action_bits",
        source_action=action,
        edge_public_occurrence_count=1,
    )
    root["root_action_mapping"][1]["edge_public_occurrence_count"] = 1
    root["search_edge_count"] = 3

    with pytest.raises(T113ConvergenceError, match="strict configured-domain"):
        validate_t113_bridge_report(
            report,
            particle_count=32,
            expected_sampler_seed=report["sampler_seed_input"],
        )


def test_t113_canary_proves_direct_nested_prefix_including_native_seed_fields():
    ladder = _ladder("A:first", "A")
    result = validate_t113_canary_ladder(ladder)
    assert result["direct_prefix_equivalence"] is True
    assert result["sampler_seed_input"] == derive_t101_sampler_seed("A:first", 0)
    assert result["direct_work_counter_sums"]["2"]
    assert result["n2_to_n32_wall_clock_ratio"] == 16.0

    ladder["calls"]["8"]["bridge_report"]["particles"][4]["sampler_seed"] += 1
    with pytest.raises(T113ConvergenceError, match="prefix"):
        validate_t113_canary_ladder(ladder)


def test_t113_fixed_cohort_and_formal_plan_are_exact_non_authorizing_96_jobs():
    t112 = _t112_cohort()
    validate_t112_cohort(t112)
    cohort = _fixed_cohort(t112)
    checked_cohort = validate_t113_fixed_cohort(cohort)
    assert len(checked_cohort["selected"]) == 24
    assert checked_cohort["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert checked_cohort["selection_performed"] is False
    assert checked_cohort["replacement_or_backfill_performed"] is False

    plan = build_t113_formal_plan(
        cohort,
        implementation_head=T113_APPROVED_SPEC_COMMIT,
        input_qualification_sha256="c" * 64,
        fixed_cohort_sha256=hashlib.sha256(
            json.dumps(
                cohort,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest(),
    )
    checked_plan = validate_t113_formal_plan(plan)
    assert len(checked_plan["jobs"]) == 96
    assert checked_plan["jobs"][0]["sampler_seed_input"] == derive_t101_sampler_seed(
        checked_cohort["selected"][0]["selection_identity"], 0
    )
    assert checked_plan["execution_authorized"] is False
    assert checked_plan["canary_authorized"] is False
    assert checked_plan["execution_topology"]["default_max_effective_concurrency"] == 4


def test_t113_fixed_cohort_rejects_wrong_t112_hash_and_substitution():
    t112 = _t112_cohort()
    with pytest.raises(T113ConvergenceError, match="artifact hash"):
        build_t113_fixed_cohort(
            t112,
            source_cohort_sha256="0" * 64,
            source_population_binding={},
            t112_artifact_binding={},
        )
    cohort = _fixed_cohort(t112)
    cohort["selected"][0]["selection_identity"] = "replacement"
    with pytest.raises(T113ConvergenceError, match="fixed identity/order"):
        validate_t113_fixed_cohort(cohort)
