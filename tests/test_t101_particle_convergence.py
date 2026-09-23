from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
)
from sts_combat_rl.commands.t101_particle_convergence import (
    T101PathError,
    analyze_t101_formal_from_paths,
    build_parser,
    build_t101_retention_from_paths,
    prepare_t101_canary_authorization_from_paths,
    prepare_t101_formal_authorization_from_paths,
    prepare_t101_formal_plan_from_paths,
)
from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099_REQUIRED_AUDIT_PREDICATES,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_NATIVE_COMMIT,
    T101_REQUIRED_INPUT_ROLES,
    T101_REQUIRED_RETENTION_ROLES,
    T101_RETENTION_ROLE_SCHEMAS,
    T101_SEED_ALGORITHM,
    T101IncompleteError,
    analyze_t101_batch,
    analyze_t101_formal,
    build_t101_formal_plan,
    build_t101_input_admission,
    build_t101_retention_manifest,
    call_t101_bridge,
    derive_t101_sampler_seed,
    select_t101_cohort,
    validate_t101_canary_ladder,
    validate_t101_formal_plan,
    validate_t101_formal_rows,
    validate_t101_selected_cohort,
)
from sts_combat_rl.sim.t101_particle_execution import (
    T101ExecutionError,
    execute_t101_canary,
    execute_t101_formal_shard,
)


def _action(kind: str, idx1: int, label: str) -> dict[str, object]:
    return {
        "scope": "battle",
        "kind": kind,
        "idx1": idx1,
        "idx2": 0,
        "idx3": 0,
        "label": label,
    }


def _projection(actions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_id": "native-battle-public-information-v2",
        "information_regime": "normal_information",
        "screen_identity": "BATTLE",
        "act": 1,
        "floor_num": 1,
        "encounter_id": "JAW_WORM",
        "turn": 0,
        "input_state": "PLAYER_NORMAL",
        "battle_outcome": "UNDECIDED",
        "player": {"current_hp": 80},
        "hand": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "draw_pile_size": 5,
        "monsters": [],
        "persistent_resources": {},
        "information_fidelity": "supported",
        "draw_knowledge_unsupported_reasons": [],
        "visibility": {
            "draw_order": {"classification": "hidden"},
            "enemy_intent": {"classification": "public_exact"},
        },
        "ordered_public_legal_actions": actions,
        "draw_pile_membership": {"classification": "public_constraint"},
    }


def _counter(scale: int) -> dict[str, object]:
    return {
        "schema_id": "native-battle-search-work-v1",
        "action_execution_count": scale,
        "successor_transition_count": scale,
        "tree_and_rollout_action_execution_count": scale,
        "heuristic_successor_transition_count": 0,
        "tree_node_expansion_count": scale,
        "rollout_count": scale,
        "terminal_utility_evaluation_count": scale,
        "policy_prior_calls": 0,
        "leaf_value_calls": 0,
        "model_calls": 0,
    }


def _bridge(
    count: int,
    *,
    seed: int = 17,
    offset: float = 0.0,
    reverse: bool = False,
) -> dict[str, object]:
    actions = [
        _action("end_turn", 0, "battle.end_turn"),
        _action("card", 0, "Strike"),
        _action("card", 1, "Strike"),
    ]
    projection = _projection(actions)
    particles = []
    for particle_index in range(count):
        first = (particle_index % 3) / 10 + offset
        second = 1.0 - (particle_index % 2) / 10 + offset
        if reverse:
            first, second = second, first
        edge_indices = [0, 1, 1]
        means = [first, second, second]
        modes = [
            "direct_action_bits",
            "direct_action_bits",
            "mechanical_duplicate_card_occurrence",
        ]
        rows = [
            {
                **action,
                "search_tree_present": True,
                "search_edge_index": edge_indices[ordinal],
                "visits": 2,
                "evaluation_sum": means[ordinal] * 2,
                "mean_value": means[ordinal],
                "public_action_ordinal": ordinal,
                "search_equivalence_source_edge_index": edge_indices[ordinal],
                "search_equivalence_mapping_mode": modes[ordinal],
            }
            for ordinal, action in enumerate(actions)
        ]
        mappings = [
            {
                "public_action_ordinal": ordinal,
                "public_action": action,
                "search_edge_index": edge_indices[ordinal],
                "mapping_mode": modes[ordinal],
                "source_action": actions[0 if ordinal == 0 else 1],
                "edge_public_occurrence_count": 1 if ordinal == 0 else 2,
            }
            for ordinal, action in enumerate(actions)
        ]
        root = {
            "schema_id": "native-battle-search-root-v1",
            "native_api": "StepSimulator.sample_hidden_future_particles_search.v1",
            "patch_identity": "sts_lightspeed_native_particle_search_bridge_v1",
            "information_regime": "full_simulator_state_oracle_like",
            "simulations_requested": 400,
            "root_visits": 4,
            "include_potions": False,
            "native_simulator_steps": 2,
            "model_calls": 0,
            "best_action_value": max(means),
            "min_action_value": min(means),
            "outcome_player_hp": 80,
            "root_row_count": 3,
            "search_edge_count": 2,
            "unsearched_legal_action_count": 0,
            "unmapped_search_edge_count": 0,
            "work_counters": _counter(particle_index + 1),
            "search_v2_configuration": {
                "policy_prior_enabled": False,
                "learned_leaf_value_enabled": False,
                "progressive_bias_enabled": False,
            },
            "root_rows": rows,
            "root_action_mapping_schema": "native-search-root-occurrence-equivalence-v1",
            "root_action_mapping": mappings,
        }
        particles.append(
            {
                "particle_index": particle_index,
                "sampler_seed": seed,
                "hidden_future_fingerprint": f"hidden-{seed}-{particle_index}",
                "public_information_projection": projection,
                "public_projection_equal": True,
                "ordered_public_legal_actions_equal": True,
                "ordered_public_legal_actions": actions,
                "root_action_mapping_complete": True,
                "root_action_mapping_ambiguous": False,
                "search_value_semantics": (
                    "full_state_continuation_strategy_fusion_proxy"
                ),
                "root_evaluation": root,
                "root_rows": rows,
            }
        )
    return {
        "schema_id": "native-battle-public-particle-search-v1",
        "native_api": "StepSimulator.sample_hidden_future_particles_search.v1",
        "sampler_seed_input": seed,
        "particle_start": 0,
        "particle_count": count,
        "search_simulations": 400,
        "include_potions": False,
        "information_regime": (
            "normal_belief_search_outer_full_simulator_state_oracle_like_continuation"
        ),
        "anchor_public_information_projection": projection,
        "anchor_ordered_public_legal_actions": actions,
        "semantic_boundary": {
            "outer_particle_distribution": (
                "native_public_consistent_hidden_future_sampler"
            ),
            "continuation": "full_state_search_v2_per_particle",
            "aggregation": "not_performed",
            "q_public_claim": False,
            "executable_no_sl_continuation_claim": False,
            "information_set_optimal_claim": False,
        },
        "particles": particles,
    }


def _audit() -> dict[str, object]:
    return {
        "schema_id": "native-stsr006-particle-search-audit-v1",
        **{name: True for name in T099_REQUIRED_AUDIT_PREDICATES},
    }


def _native() -> dict[str, object]:
    return {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": "refs/heads/stsrl/main",
        "commit": T101_NATIVE_COMMIT,
    }


def _admission() -> dict[str, object]:
    qualifications = {}
    for index, role in enumerate(sorted(T101_REQUIRED_INPUT_ROLES), 1):
        digest = f"{index:064x}"
        qualification = ArtifactQualification(
            artifact={
                "id": role,
                "kind": f"{role}-schema",
                "path": f"/retained/{role}.json",
                "schema_id": f"{role}-schema",
                "size_bytes": index,
            },
            integrity={"sha256": digest},
            facts={
                "record_count": Fact(413),
                "source.coverage": Fact("accepted_ordered_abc"),
                "override_kind": Fact("none"),
            },
        )
        requirements = EligibilityRequirements(
            reuse_mode="scientific_quality_claim",
            claim_boundary=(
                "bounded particle-proxy stability and cost under frozen T101 semantics"
            ),
            predicates=(
                Predicate("record_count", "equals", 413),
                Predicate("source.coverage", "equals", "accepted_ordered_abc"),
            ),
            artifact_id=role,
            artifact_kind=f"{role}-schema",
            sha256=digest,
        )
        qualifications[role] = (qualification, requirements)
    return build_t101_input_admission(
        qualifications,
        native_identity=_native(),
        bridge_audit=_audit(),
    )


def _admission_runtime(
    status: str = "success_no_retry",
) -> dict[str, object]:
    return {
        "wall_clock_time_s": 0.25,
        "particle_count": 2,
        "search_simulations_per_particle": 400,
        "worker_id": "unit-admission",
        "shard_index": 0,
        "effective_concurrency": 1,
        "failure_retry_status": status,
        "retry_reason": None,
        "single_worker_reason": "unit deterministic admission",
    }


def _source() -> list[dict[str, object]]:
    return [
        {"selection_identity": f"{stratum}:{index:03d}", "cohort": stratum}
        for stratum, count in {"A": 93, "B": 192, "C": 128}.items()
        for index in range(count)
    ]


def _cohort() -> dict[str, object]:
    return select_t101_cohort(
        _source(),
        admit=lambda _row: {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "occurrence_mapping_complete": True,
            "search_configuration_unchanged": True,
            "bridge_report": _bridge(2),
            "bridge_call_runtime": _admission_runtime(),
            # Deliberately ignored by the selector.
            "outcome": "PLAYER_VICTORY",
            "ranking": 999,
        },
    )


def _canary_evidence(
    cohort: dict[str, object], implementation_head: str = "c" * 40
) -> dict[str, object]:
    canonical = __import__(
        "sts_combat_rl.sim.t101_particle_convergence", fromlist=["_canonical_sha256"]
    )._canonical_sha256
    selected = [
        next(row for row in cohort["selected"] if row["stratum"] == stratum)
        for stratum in ("A", "B", "C")
    ]
    ladders = []
    for row in selected:
        identity = row["selection_identity"]
        seed = derive_t101_sampler_seed(identity, 0)
        full = _bridge(32, seed=seed)
        ladders.append(
            validate_t101_canary_ladder(
                {
                    "selection_identity": identity,
                    "stratum": row["stratum"],
                    "replicate_index": 0,
                    "calls": {
                        str(count): {
                            "bridge_report": {
                                **deepcopy(full),
                                "particle_count": count,
                                "particles": deepcopy(full["particles"][:count]),
                            },
                            "wall_clock_time_s": count / 10,
                            "worker_id": "unit-canary",
                            "shard_index": 0,
                            "effective_concurrency": 1,
                            "failure_retry_status": "success_no_retry",
                            "single_worker_reason": "bounded unit canary",
                        }
                        for count in T101_COUNTS
                    },
                }
            )
        )
    return {
        "schema_id": "t101-canary-evidence-v1",
        "task_id": "T101",
        "implementation_head": implementation_head,
        "authorization": {
            "schema_id": "t101-maintainer-canary-authorization-v1",
            "task_id": "T101",
            "authorization_kind": "bounded_canary",
            "authorized": True,
            "authorization_id": "canary-fixture",
            "implementation_head": implementation_head,
            "input_admission_sha256": canonical(_admission()),
            "cohort_admission_sha256": canonical(cohort),
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "CANARY_AUTHORIZED",
                "exact_head": implementation_head,
            },
        },
        "selected": [
            {
                "selection_identity": row["selection_identity"],
                "stratum": row["stratum"],
                "replicate_index": 0,
            }
            for row in selected
        ],
        "ladders": ladders,
        "direct_prefix_equivalence": True,
        "complete": True,
    }


def test_seed_derivation_is_stable_replica_specific_unsigned_u64() -> None:
    seeds = [derive_t101_sampler_seed("A:000", index) for index in range(4)]
    assert seeds == [
        8668616451759604074,
        11417437864501354461,
        13016923129194496710,
        532729408135493124,
    ]
    assert seeds == [
        int.from_bytes(
            hashlib.sha256(b"T101-v1" + b"A:000" + str(index).encode("ascii")).digest()[
                :8
            ],
            "big",
        )
        for index in range(4)
    ]
    assert len(set(seeds)) == 4
    assert all(0 <= seed < 2**64 for seed in seeds)


def test_input_eligibility_fails_closed_before_scientific_work() -> None:
    admission = _admission()
    assert admission["eligible"] is True
    qualification, requirements = next(
        iter(
            {
                "x": (
                    ArtifactQualification(
                        artifact={"id": "x", "kind": "natural"},
                        integrity={"sha256": "b" * 64},
                        facts={
                            "record_count": Fact.unavailable("lost"),
                            "source.coverage": Fact("accepted_ordered_abc"),
                            "override_kind": Fact("none"),
                        },
                    ),
                    EligibilityRequirements(
                        "scientific_quality_claim",
                        "bounded particle proxy",
                        (
                            Predicate("record_count", "equals", 413),
                            Predicate(
                                "source.coverage", "equals", "accepted_ordered_abc"
                            ),
                        ),
                        "x",
                        "natural",
                        "b" * 64,
                    ),
                )
            }.values()
        )
    )
    with pytest.raises(T101IncompleteError, match="ineligible"):
        build_t101_input_admission(
            {"x": (qualification, requirements)},
            native_identity=_native(),
            bridge_audit=_audit(),
        )


def test_cohort_selection_is_deterministic_exact_8_each_and_value_blind() -> None:
    first = _cohort()
    second = select_t101_cohort(
        reversed(_source()),
        admit=lambda _row: {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "occurrence_mapping_complete": True,
            "search_configuration_unchanged": True,
            "bridge_report": _bridge(2, offset=-100.0, reverse=True),
            "bridge_call_runtime": _admission_runtime(),
            "outcome": "PLAYER_LOSS",
            "ranking": -999,
        },
    )
    assert first["selected"] == second["selected"]
    assert first["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert len(first["selected"]) == 24


def test_cohort_selection_retains_exclusions_and_never_backfills_strata() -> None:
    def admit(row: dict[str, object]) -> dict[str, object]:
        if row["cohort"] == "B":
            raise T101IncompleteError("unsupported current-native restore")
        return {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "occurrence_mapping_complete": True,
            "search_configuration_unchanged": True,
            "bridge_report": _bridge(2),
            "bridge_call_runtime": _admission_runtime(),
        }

    report = select_t101_cohort(_source(), admit=admit)
    assert report["supported"] is False
    assert report["terminal_classification"] == "SUPPORTED_COHORT_INSUFFICIENT"
    assert report["selected_counts"] == {"A": 8, "C": 8}
    assert report["exhausted_strata"] == ["B"]
    assert sum(row["stratum"] == "B" for row in report["attempted"]) == 192


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda report: report.__setitem__("schema_id", "t101-cohort-admission-v0"),
            "supported 8/8/8",
        ),
        (lambda report: report.__setitem__("source_counts", {"A": 8}), "supported"),
        (
            lambda report: report.__setitem__("selected_counts", {"A": 8}),
            "count summary",
        ),
        (
            lambda report: report.__setitem__(
                "terminal_classification", "SUPPORTED_COHORT_INSUFFICIENT"
            ),
            "supported 8/8/8",
        ),
    ],
)
def test_selected_cohort_revalidates_persisted_admission_identity(
    mutate, match
) -> None:
    report = _cohort()
    mutate(report)
    with pytest.raises(T101IncompleteError, match=match):
        validate_t101_selected_cohort(report)


def test_bridge_invocation_freezes_t099_nopot_search400_surface() -> None:
    calls: list[dict[str, object]] = []

    def bridge(_snapshot: object, **kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return _bridge(int(kwargs["particle_count"]), seed=int(kwargs["sampler_seed"]))

    report = call_t101_bridge(
        SimpleNamespace(sample_hidden_future_particles_search=bridge),
        object(),
        sampler_seed=123,
        particle_count=32,
    )
    assert report["particle_count"] == 32
    assert calls == [
        {
            "sampler_seed": 123,
            "particle_start": 0,
            "particle_count": 32,
            "search_simulations": 400,
            "include_potions": False,
        }
    ]

    changed_seed = _bridge(32, seed=123)
    changed_seed["particles"][0]["sampler_seed"] = 124
    with pytest.raises(T101IncompleteError, match="per-particle sampler seed"):
        analyze_t101_batch(changed_seed)

    changed_root = _bridge(32, seed=123)
    changed_root["particles"][0]["root_evaluation"]["simulations_requested"] = 399
    with pytest.raises(T101IncompleteError, match="root evaluation"):
        analyze_t101_batch(changed_root)


def test_canary_proves_direct_ladder_is_exact_nested_prefix() -> None:
    full = _bridge(32, seed=derive_t101_sampler_seed("A:000", 0))
    ladder = {
        "selection_identity": "A:000",
        "stratum": "A",
        "replicate_index": 0,
        "calls": {
            str(count): {
                "bridge_report": {
                    **deepcopy(full),
                    "particle_count": count,
                    "particles": deepcopy(full["particles"][:count]),
                },
                "wall_clock_time_s": count / 10,
                "worker_id": "unit-canary",
                "shard_index": 0,
                "effective_concurrency": 1,
                "failure_retry_status": "success_no_retry",
                "single_worker_reason": "bounded unit canary",
            }
            for count in T101_COUNTS
        },
    }
    evidence = validate_t101_canary_ladder(ladder)
    assert evidence["direct_prefix_equivalence"] is True
    broken = deepcopy(ladder)
    broken["calls"]["8"]["bridge_report"]["particles"][0][
        "hidden_future_fingerprint"
    ] = "changed"
    with pytest.raises(T101IncompleteError, match="not the exact"):
        validate_t101_canary_ladder(broken)


def test_analysis_uses_native_equivalence_classes_without_occurrence_weight() -> None:
    analysis = analyze_t101_batch(_bridge(32))
    assert analysis["decision_class_partition"] == [
        {"decision_class_id": "search-edge:0", "public_action_ordinals": [0]},
        {"decision_class_id": "search-edge:1", "public_action_ordinals": [1, 2]},
    ]
    assert analysis["per_occurrence_rows_retained"] is True
    n32 = next(row for row in analysis["metrics"] if row["particle_count"] == 32)
    assert n32["decision_class_count"] == 2
    assert len(n32["decision_classes"]) == 2
    assert n32["best_set_exact_agreement_with_n32"] is True
    assert n32["n32_reference_proxy_opportunity_gap"] == 0
    assert n32["rank_agreement_with_n32"] == 1
    assert all("strategy_fusion_mean_proxy" in row for row in n32["decision_classes"])

    inconsistent = _bridge(32)
    inconsistent["particles"][0]["root_rows"][2]["mean_value"] += 0.1
    inconsistent["particles"][0]["root_rows"][2]["evaluation_sum"] += 0.2
    inconsistent["particles"][0]["root_evaluation"]["root_rows"] = inconsistent[
        "particles"
    ][0]["root_rows"]
    with pytest.raises(T101IncompleteError, match="duplicate public occurrences"):
        analyze_t101_batch(inconsistent)

    tied = _bridge(32)
    for particle in tied["particles"]:
        for root_row in particle["root_rows"]:
            root_row["mean_value"] = 0.5
            root_row["evaluation_sum"] = 1.0
        particle["root_evaluation"]["root_rows"] = particle["root_rows"]
        particle["root_evaluation"]["best_action_value"] = 0.5
        particle["root_evaluation"]["min_action_value"] = 0.5
    tied_analysis = analyze_t101_batch(tied)
    tied_n32 = next(
        row for row in tied_analysis["metrics"] if row["particle_count"] == 32
    )
    assert tied_n32["best_decision_class_set"] == ["search-edge:0", "search-edge:1"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda report: report["particles"][0].__setitem__(
                "root_action_mapping_ambiguous", True
            ),
            "mapping is ambiguous",
        ),
        (
            lambda report: report.__setitem__(
                "anchor_ordered_public_legal_actions",
                [
                    *report["anchor_ordered_public_legal_actions"],
                    _action("card", 2, "Defend"),
                ],
            ),
            "legal actions disagree",
        ),
        (
            lambda report: report["anchor_public_information_projection"].update(
                {
                    "information_fidelity": "unsupported_fidelity",
                    "draw_knowledge_unsupported_reasons": ["unit unsupported"],
                }
            ),
            "unsupported-fidelity anchor",
        ),
    ],
)
def test_t101_reuses_t099_fail_closed_anchor_and_mapping_validation(
    mutate, match
) -> None:
    report = _bridge(32)
    mutate(report)
    with pytest.raises(T101IncompleteError, match=match):
        analyze_t101_batch(report)


def test_formal_plan_is_exact_96_jobs_modulo_sharded_and_not_authorized() -> None:
    plan = build_t101_formal_plan(
        _cohort(),
        input_admission=_admission(),
        implementation_head="c" * 40,
        output_root="/retained/t101",
    )
    assert plan["formal_authorized"] is False
    assert plan["seed_algorithm"] == T101_SEED_ALGORITHM
    assert plan["seed_algorithm"] == (
        "sha256-domain-identity-decimal-replicate-u64be-v1"
    )
    assert plan["job_count"] == 96
    assert {job["particle_count"] for job in plan["jobs"]} == {32}
    assert {job["search_simulations"] for job in plan["jobs"]} == {400}
    assert {job["include_potions"] for job in plan["jobs"]} == {False}
    assert [job["shard_index"] for job in plan["jobs"][:18]] == list(range(16)) + [0, 1]
    assert plan["support_admission_cost"]["bridge_call_count"] == 24
    assert plan["support_admission_cost"]["successful_call_count"] == 24

    changed_native = deepcopy(plan)
    changed_native["native_identity"]["commit"] = "0" * 40
    with pytest.raises(T101IncompleteError, match="native identity"):
        validate_t101_formal_plan(changed_native)

    changed_search = deepcopy(plan)
    changed_search["search_configuration"]["search_simulations"] = 399
    with pytest.raises(T101IncompleteError, match="Search semantics"):
        validate_t101_formal_plan(changed_search)

    changed_seed_algorithm = deepcopy(plan)
    changed_seed_algorithm["seed_algorithm"] = (
        "sha256-domain-nul-identity-nul-decimal-replicate-u64be-v1"
    )
    with pytest.raises(T101IncompleteError, match="formal plan schema"):
        validate_t101_formal_plan(changed_seed_algorithm)

    with pytest.raises(T101IncompleteError, match="lower-worker"):
        build_t101_formal_plan(
            _cohort(),
            input_admission=_admission(),
            implementation_head="c" * 40,
            output_root="/retained/t101",
            worker_count=8,
        )
    reduced = build_t101_formal_plan(
        _cohort(),
        input_admission=_admission(),
        implementation_head="c" * 40,
        output_root="/retained/t101",
        worker_count=8,
        lower_worker_reason="documented native memory cap",
    )
    assert reduced["topology"]["lower_worker_reason"] == (
        "documented native memory cap"
    )


def _formal_rows(plan: dict[str, object], *, reverse_last: bool = False):
    rows = []
    for job in plan["jobs"]:
        rows.append(
            {
                "job_ordinal": job["job_ordinal"],
                "shard_index": job["shard_index"],
                "selection_identity": job["selection_identity"],
                "stratum": job["stratum"],
                "replicate_index": job["replicate_index"],
                "sampler_seed": job["sampler_seed"],
                "bridge_report": _bridge(
                    32,
                    seed=job["sampler_seed"],
                    reverse=(reverse_last and job["replicate_index"] == 3),
                ),
                "wall_clock_time_s": 1.5,
                "worker_id": f"worker-{job['shard_index']}",
                "effective_concurrency": 16,
                "retry_reason": None,
                "failure_retry_status": "success_no_retry",
            }
        )
    return rows


def test_complete_formal_analysis_classifies_strict_stability_and_cost() -> None:
    plan = build_t101_formal_plan(
        _cohort(),
        input_admission=_admission(),
        implementation_head="c" * 40,
        output_root="/retained/t101",
    )
    rows = _formal_rows(plan)
    report = analyze_t101_formal(rows, plan)
    assert report["terminal_classification"] == (
        "BOUNDED_PARTICLE_PROXY_STABILITY_OBSERVED"
    )
    assert report["n32_reference_unanimous_all_states"] is True
    assert report["smallest_uniform_prefix_n"] in T101_COUNTS
    assert len(report["state_replicate_metrics"]) == 96
    assert [row["label"] for row in report["cohort_summaries"]] == [
        "all",
        "A",
        "B",
        "C",
        "multi_class_informative",
    ]
    work = report["cost_report"]["n2_to_n32_work_change"]
    assert (
        work["action_execution_count"]["n32_total"]
        > work["action_execution_count"]["n2_total"]
    )

    negative = analyze_t101_formal(_formal_rows(plan, reverse_last=True), plan)
    assert negative["terminal_classification"] == (
        "BOUNDED_PARTICLE_PROXY_STABILITY_NOT_ESTABLISHED"
    )
    assert negative["n32_reference_unanimous_all_states"] is False
    assert negative["smallest_uniform_prefix_n"] is None

    changed_projection_rows = _formal_rows(plan)
    changed_report = changed_projection_rows[1]["bridge_report"]
    changed_report["anchor_public_information_projection"]["floor_num"] = 2
    for particle in changed_report["particles"]:
        particle["public_information_projection"]["floor_num"] = 2
    with pytest.raises(T101IncompleteError, match="public projection"):
        analyze_t101_formal(changed_projection_rows, plan)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda rows: rows.pop(), "incomplete"),
        (
            lambda rows: rows[0].__setitem__("sampler_seed", 0),
            "configuration drifted",
        ),
        (
            lambda rows: rows[0]["bridge_report"].__setitem__(
                "anchor_public_information_projection", {}
            ),
            "public projection",
        ),
        (
            lambda rows: rows[0]["bridge_report"]["particles"].pop(),
            "particle count",
        ),
    ],
)
def test_formal_evidence_fails_closed_on_incomplete_or_changed_inputs(
    mutate, match
) -> None:
    plan = build_t101_formal_plan(
        _cohort(),
        input_admission=_admission(),
        implementation_head="c" * 40,
        output_root="/retained/t101",
    )
    rows = _formal_rows(plan)
    mutate(rows)
    with pytest.raises((T101IncompleteError, ValueError), match=match):
        validate_t101_formal_rows(rows, plan)


def test_retention_requires_all_artifact_roles_and_exact_identity_shape() -> None:
    artifacts = {
        role: {
            "path": f"/retained/{role}.json",
            "schema_id": T101_RETENTION_ROLE_SCHEMAS[role],
            "sha256": f"{index:064x}",
            "size_bytes": index,
        }
        for index, role in enumerate(sorted(T101_REQUIRED_RETENTION_ROLES), 1)
    }
    manifest = build_t101_retention_manifest(
        artifacts,
        producer_provenance={
            "task_id": "T101",
            "implementation_head": "c" * 40,
            "native_identity": _native(),
            "input_admission_artifact_sha256": "1" * 64,
            "cohort_admission_artifact_sha256": "2" * 64,
            "formal_plan_artifact_sha256": "3" * 64,
        },
        regeneration_commands=[
            "python -m sts_combat_rl.commands.t101_particle_convergence"
        ],
        retention_reason="T101 evidence and downstream audit",
        deletion_condition="delete only after the T101 claim has no consumer",
    )
    assert manifest["schema_id"] == "t101-retention-manifest-v1"
    del artifacts["cost_report"]
    with pytest.raises(T101IncompleteError, match="missing roles"):
        build_t101_retention_manifest(
            artifacts,
            producer_provenance=manifest["producer_provenance"],
            regeneration_commands=["regenerate"],
            retention_reason="reason",
            deletion_condition="condition",
        )


def test_output_schema_avoids_controller_promotion_and_misleading_value_labels() -> (
    None
):
    report = analyze_t101_batch(_bridge(32))
    encoded = str(report).lower()
    for forbidden in (
        "q_public",
        "posterior estimate",
        "regret",
        "information-set-optimal",
        "deployable action value",
    ):
        assert forbidden not in encoded


def _write_json(path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def test_path_command_prepares_non_authorizing_plan_and_requires_all_shards(
    tmp_path,
) -> None:
    admission_path = tmp_path / "input.json"
    cohort_path = tmp_path / "cohort.json"
    root = tmp_path / "formal"
    plan_path = root / "plan.json"
    _write_json(admission_path, _admission())
    _write_json(cohort_path, _cohort())
    prepared = prepare_t101_formal_plan_from_paths(
        input_admission_path=admission_path,
        cohort_admission_path=cohort_path,
        implementation_head="c" * 40,
        artifact_root=root,
        output_path=plan_path,
    )
    plan = prepared["plan"]
    assert plan["formal_authorized"] is False
    rows = _formal_rows(plan)
    shard_paths = []
    plan_sha = __import__(
        "sts_combat_rl.sim.t101_particle_convergence", fromlist=["_canonical_sha256"]
    )._canonical_sha256(plan)
    canary_path = tmp_path / "canary-evidence.json"
    _write_json(canary_path, _canary_evidence(_cohort()))
    canary_sha = hashlib.sha256(canary_path.read_bytes()).hexdigest()
    for shard_index in range(16):
        path = root / f"shard-{shard_index:02d}.json"
        _write_json(
            path,
            {
                "schema_id": "t101-formal-shard-v1",
                "task_id": "T101",
                "implementation_head": "c" * 40,
                "authorization_id": "formal-fixture",
                "formal_plan_sha256": plan_sha,
                "canary_evidence_sha256": canary_sha,
                "shard_index": shard_index,
                "shard_count": 16,
                "worker_id": f"worker-{shard_index}",
                "effective_concurrency": 16,
                "wall_clock_time_s": 2.0,
                "job_ordinals": [
                    row["job_ordinal"]
                    for row in rows
                    if row["shard_index"] == shard_index
                ],
                "complete": True,
                "rows": [row for row in rows if row["shard_index"] == shard_index],
            },
        )
        shard_paths.append(path)
    published = analyze_t101_formal_from_paths(
        plan_path=plan_path,
        canary_evidence_path=canary_path,
        shard_paths=shard_paths,
        artifact_root=tmp_path / "analysis",
    )
    assert published["final_report"]["terminal_classification"] == (
        "BOUNDED_PARTICLE_PROXY_STABILITY_OBSERVED"
    )
    retained_paths = {
        "input_admission": admission_path,
        "cohort_admission": cohort_path,
        "canary_evidence": canary_path,
        "formal_plan": plan_path,
        **{
            role: reference["path"]
            for role, reference in published["artifacts"].items()
        },
    }
    retained = build_t101_retention_from_paths(
        artifact_specs=[
            f"{role}={path}" for role, path in sorted(retained_paths.items())
        ],
        output_path=tmp_path / "retention.json",
        regeneration_commands=[
            "python -m sts_combat_rl.commands.t101_particle_convergence analyze"
        ],
        retention_reason="T101 scientific evidence",
        deletion_condition="after all accepted consumers expire",
    )
    assert retained["manifest"]["producer_provenance"]["implementation_head"] == (
        "c" * 40
    )
    with pytest.raises(T101PathError, match="every planned shard"):
        analyze_t101_formal_from_paths(
            plan_path=plan_path,
            canary_evidence_path=canary_path,
            shard_paths=shard_paths[:-1],
            artifact_root=tmp_path / "incomplete",
        )


def test_t101_cli_uses_explicit_offline_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "plan",
            "--input-admission",
            "input.json",
            "--cohort-admission",
            "cohort.json",
            "--implementation-head",
            "a" * 40,
            "--artifact-root",
            "artifacts/t101",
            "--output",
            "artifacts/t101/plan.json",
        ]
    )
    assert args.mode == "plan"
    assert args.shard_count == 16
    assert args.worker_count == 16


def test_authorization_preparations_bind_exact_readiness_plan_and_canary(
    tmp_path,
) -> None:
    input_path, cohort_path = tmp_path / "input.json", tmp_path / "cohort.json"
    _write_json(input_path, _admission())
    _write_json(cohort_path, _cohort())
    canary_auth = prepare_t101_canary_authorization_from_paths(
        input_admission_path=input_path,
        cohort_admission_path=cohort_path,
        implementation_head="c" * 40,
    )
    assert canary_auth["authorization_template"]["authorized"] is None

    root, plan_path = tmp_path / "formal", tmp_path / "formal" / "plan.json"
    prepare_t101_formal_plan_from_paths(
        input_admission_path=input_path,
        cohort_admission_path=cohort_path,
        implementation_head="c" * 40,
        artifact_root=root,
        output_path=plan_path,
    )
    canary_path = tmp_path / "canary.json"
    _write_json(canary_path, _canary_evidence(_cohort()))
    formal_auth = prepare_t101_formal_authorization_from_paths(
        plan_path=plan_path,
        canary_evidence_path=canary_path,
        implementation_head="c" * 40,
    )
    assert formal_auth["authorization_template"]["authorized"] is None
    assert formal_auth["authorization_template"]["formal_plan_sha256"]
    assert formal_auth["authorization_template"]["canary_evidence_sha256"]


class _FakeRecordRunner:
    def canary_ladder(self, record):
        seed = derive_t101_sampler_seed(record["selection_identity"], 0)
        full = _bridge(32, seed=seed)
        return {
            "selection_identity": record["selection_identity"],
            "stratum": record["stratum"],
            "replicate_index": 0,
            "calls": {
                str(count): {
                    "bridge_report": {
                        **deepcopy(full),
                        "particle_count": count,
                        "particles": deepcopy(full["particles"][:count]),
                    },
                    "wall_clock_time_s": 1.0,
                }
                for count in T101_COUNTS
            },
        }

    def formal_job(self, job):
        return {
            "job_ordinal": job["job_ordinal"],
            "shard_index": job["shard_index"],
            "selection_identity": job["selection_identity"],
            "stratum": job["stratum"],
            "replicate_index": job["replicate_index"],
            "sampler_seed": job["sampler_seed"],
            "bridge_report": _bridge(32, seed=job["sampler_seed"]),
            "wall_clock_time_s": 1.0,
            "retry_reason": None,
            "failure_retry_status": "success_no_retry",
        }


def test_execution_seams_require_exact_authorization_and_bound_canary() -> None:
    input_admission, cohort = _admission(), _cohort()
    canonical = __import__(
        "sts_combat_rl.sim.t101_particle_convergence", fromlist=["_canonical_sha256"]
    )._canonical_sha256
    authorization = {
        "schema_id": "t101-maintainer-canary-authorization-v1",
        "task_id": "T101",
        "authorization_kind": "bounded_canary",
        "authorized": True,
        "authorization_id": "canary-fixture",
        "implementation_head": "c" * 40,
        "input_admission_sha256": canonical(input_admission),
        "cohort_admission_sha256": canonical(cohort),
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": "c" * 40,
        },
    }
    evidence = execute_t101_canary(
        authorization=authorization,
        implementation_head="c" * 40,
        input_admission=input_admission,
        cohort_admission=cohort,
        runner=_FakeRecordRunner(),
        worker_id="unit-canary",
    )
    assert [row["stratum"] for row in evidence["selected"]] == ["A", "B", "C"]
    assert evidence["direct_prefix_equivalence"] is True
    authorization["authorized"] = False
    with pytest.raises(T101ExecutionError, match="authorization binding"):
        execute_t101_canary(
            authorization=authorization,
            implementation_head="c" * 40,
            input_admission=input_admission,
            cohort_admission=cohort,
            runner=_FakeRecordRunner(),
            worker_id="unit-canary",
        )


def test_formal_shard_execution_is_exactly_plan_assigned_and_authorized() -> None:
    plan = build_t101_formal_plan(
        _cohort(),
        input_admission=_admission(),
        implementation_head="c" * 40,
        output_root="/retained/t101",
    )
    canonical = __import__(
        "sts_combat_rl.sim.t101_particle_convergence", fromlist=["_canonical_sha256"]
    )._canonical_sha256
    canary = {"sha256": "d" * 64}
    authorization = {
        "schema_id": "t101-maintainer-formal-authorization-v1",
        "task_id": "T101",
        "authorization_kind": "formal_particle_diagnostic",
        "authorized": True,
        "authorization_id": "formal-fixture",
        "implementation_head": "c" * 40,
        "formal_plan_sha256": canonical(plan),
        "canary_evidence_sha256": "d" * 64,
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "FORMAL_AUTHORIZED",
            "exact_head": "c" * 40,
        },
    }
    shard = execute_t101_formal_shard(
        authorization=authorization,
        implementation_head="c" * 40,
        plan=plan,
        canary_evidence_reference=canary,
        shard_index=3,
        runner=_FakeRecordRunner(),
        worker_id="worker-3",
        effective_concurrency=16,
    )
    assert shard["complete"] is True
    assert len(shard["rows"]) == 6
    assert {row["shard_index"] for row in shard["rows"]} == {3}
