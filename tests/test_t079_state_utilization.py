from __future__ import annotations

import pytest

from scripts.run_t079_state_utilization import _population_aggregate
from sts_combat_rl.sim.t079_state_utilization import (
    build_search_call_identity,
    classify_t079,
    compare_prefix_sequences,
    flatten_t079_call_records,
    normalize_native_state_utilization,
    summarize_state_utilization,
    t079_result_is_complete,
    validate_stage_inventory,
)


@pytest.mark.parametrize("termination", ["truncated", "error", "unknown"])
def test_t079_rejects_incomplete_restored_battle(termination: str) -> None:
    assert not t079_result_is_complete(termination, [], [])
    assert not t079_result_is_complete("win", ["battle problem"], [])
    assert not t079_result_is_complete("loss", [], ["report problem"])


def test_t079_accepts_only_clean_terminal_battle() -> None:
    assert t079_result_is_complete("win", [], [])
    assert t079_result_is_complete("loss", [], [])


def test_search_call_identity_uses_controller_emission_and_adds_cohort_key() -> None:
    identity = build_search_call_identity(
        {
            "schema_id": "t079-search-call-identity-v1",
            "controller_identity": "battle_search_v2_oracle_like_t079_state_utilization_v1",
            "decision_step_index": 3,
        },
        cohort_identity="cohort-sha256",
        record_index=5,
        decision_step_index=3,
    )
    assert identity == {
        "schema_id": "t079-search-call-identity-v1",
        "cohort_identity": "cohort-sha256",
        "record_index": 5,
        "decision_step_index": 3,
        "controller_identity": "battle_search_v2_oracle_like_t079_state_utilization_v1",
    }


def test_search_call_identity_rejects_missing_controller_identity() -> None:
    with pytest.raises(ValueError, match="controller identity"):
        build_search_call_identity(
            {
                "schema_id": "t079-search-call-identity-v1",
                "controller_identity": "",
                "decision_step_index": 0,
            },
            cohort_identity="cohort-sha256",
            record_index=0,
            decision_step_index=0,
        )


def _telemetry(digests: list[str]) -> dict[str, object]:
    first: dict[str, tuple[int, int]] = {}
    rows = []
    for index, digest in enumerate(digests, 1):
        depth = index % 3
        if digest not in first:
            first[digest] = (index, depth)
            first_seen = True
        else:
            first_seen = False
        first_ordinal, first_depth = first[digest]
        rows.append(
            {
                "expansion_ordinal": index,
                "depth": depth,
                "exact_state_digest": f"{digest:0>32}",
                "first_seen": first_seen,
                "first_seen_expansion_ordinal": first_ordinal,
                "first_seen_depth": first_depth,
                "path_fingerprint": f"p{index}:path",
            }
        )
    return {
        "identity_complete": True,
        "active_queue_normalization": {
            "schema_id": "native-battle-search-v2-active-queue-semantics-v1",
            "card_queue": "active_slots_only_execution_order;inactive_stale_slots_ignored",
            "action_queue": "active_entries_only;empty_queue_stale_storage_ignored",
        },
        "digest_collision_count": 0,
        "collision_check": "canonical_payload_equality_within_digest_bucket",
        "expanded_path_node_count": len(rows),
        "expanded_states": rows,
    }


def _assert_unproven_queue_identity_is_opaque(component: str) -> None:
    telemetry = _telemetry(["a", "a"])
    del telemetry["active_queue_normalization"]
    telemetry["identity_components"] = [component]

    rows, identity_class = normalize_native_state_utilization(telemetry)

    assert identity_class == "opaque"
    assert all(
        row["identity_evidence_class"] == "opaque"
        and row["exact_state_digest"] is None
        and row["first_seen"] is None
        and row["first_seen_expansion_ordinal"] is None
        and row["first_seen_depth"] is None
        for row in rows
    )


def test_inactive_card_queue_slots_are_not_exact_identity() -> None:
    _assert_unproven_queue_identity_is_opaque("CardQueue.all_slots_and_indices")


def test_empty_action_queue_stale_storage_is_not_exact_identity() -> None:
    _assert_unproven_queue_identity_is_opaque("ActionQueue.indices_size_and_clear_bits")


def test_summarize_reports_exact_duplicates_and_distinct_paths() -> None:
    result = summarize_state_utilization(_telemetry(["a", "b", "a", "a"]))
    assert result["expanded_path_nodes"] == 4
    assert result["unique_exact_states"] == 2
    assert result["exact_duplicate_path_nodes"] == 2
    assert result["exact_duplicate_fraction"] == pytest.approx(0.5)
    assert result["duplicate_group_count"] == 1
    assert result["distinct_path_duplicate_group_count"] == 1
    assert result["paths_per_exact_state"]["max"] == 3


def test_opaque_native_identity_is_partitioned_without_equality_claims() -> None:
    telemetry = _telemetry(["a", "a", "b"])
    telemetry.update(
        identity_complete=False,
        identity_unavailable_reason="native ActionQueue contains opaque std::function entries",
    )
    result = summarize_state_utilization(telemetry)
    assert result["expanded_path_nodes"] == 3
    assert result["comparable_nodes"] == 0
    assert result["opaque_nodes"] == 3
    assert result["identity_partition_valid"] is True
    assert result["exact_duplicate_fraction_lower"] == 0.0
    assert result["exact_duplicate_fraction_upper"] == 1.0
    assert result["unique_state_yield_lower"] == 0.0
    assert result["unique_state_yield_upper"] == 1.0
    assert all(
        row["identity_evidence_class"] == "opaque"
        and row["exact_state_digest"] is None
        and row["first_seen"] is None
        for row in result["expanded_states"]
    )


def test_prefix_metrics_are_missing_when_sequences_are_not_prefixes() -> None:
    result = compare_prefix_sequences(
        {100: ["a"] * 100, 400: ["a"] * 99 + ["b"] * 301, 1600: ["a"] * 1600}
    )
    assert result["100_400"]["prefix_comparable"] is False
    assert result["100_400"]["marginal_unique_yield"] is None
    assert result["400_1600"]["prefix_comparable"] is False


def test_prefix_marginal_yield_counts_first_appearance_only() -> None:
    result = compare_prefix_sequences(
        {
            100: ["a"] * 100,
            400: ["a"] * 400,
            1600: ["a"] * 400 + ["b", "b"] + ["c"] * 1198,
        }
    )
    assert result["400_1600"]["marginal_unique_yield"] == pytest.approx(2 / 1200)


def test_prefix_bounds_count_opaque_only_in_upper_bound() -> None:
    def exact(digest: str, path: str) -> dict[str, object]:
        return {
            "identity_evidence_class": "exact_comparable",
            "exact_state_digest": digest,
            "path_fingerprint": path,
        }

    def opaque(path: str) -> dict[str, object]:
        return {
            "identity_evidence_class": "opaque",
            "path_fingerprint": path,
        }

    result = compare_prefix_sequences(
        {
            100: [exact("a" * 32, f"p{i}") for i in range(100)],
            400: [exact("a" * 32, f"p{i}") for i in range(400)],
            1600: [
                *[exact("a" * 32, f"p{i}") for i in range(400)],
                exact("b" * 32, "p400"),
                opaque("p401"),
                opaque("p402"),
                *[opaque(f"p{i}") for i in range(403, 1600)],
            ],
        }
    )
    assert result["400_1600"]["marginal_unique_yield_lower"] == pytest.approx(1 / 1200)
    assert result["400_1600"]["marginal_unique_yield_upper"] == pytest.approx(
        1200 / 1200
    )


def test_telemetry_calls_flattens_fixed_evaluation_nested_lists() -> None:
    calls = [{"decision_step_index": 0}, [{"decision_step_index": 1}]]
    assert [
        call["decision_step_index"] for call in flatten_t079_call_records(calls)
    ] == [
        0,
        1,
    ]


def test_population_aggregate_retains_required_state_and_geometry_metrics() -> None:
    geometry = {
        "schema_id": "native-battle-search-v2-tree-geometry-v1",
        "root_depth": 0,
        "total_expanded_node_count": 3,
        "total_discovered_child_edge_count": 4,
        "total_visited_child_edge_count": 2,
        "max_expanded_depth": 1,
        "depth_rows": [
            {
                "depth": 0,
                "expanded_node_count": 1,
                "discovered_child_edge_count": 2,
                "visited_child_edge_count": 1,
            }
        ],
    }
    row = {
        "record_index": 0,
        "expanded_path_nodes": 4,
        "unique_exact_states": 2,
        "exact_duplicate_path_nodes": 2,
        "exact_duplicate_fraction": 0.5,
        "unique_state_yield": 0.5,
        "comparable_nodes": 4,
        "opaque_nodes": 0,
        "duplicate_group_count": 1,
        "paths_per_exact_state": {"mean": 2.0, "median": 1.5, "p90": 2.0, "max": 3.0},
        "distinct_path_duplicate_group_count": 1,
        "distinct_path_duplicate_group_fraction": 1.0,
        "duplicate_expansions_by_depth": {"1": 2},
        "first_seen_depth": {"0": 1, "1": 1},
        "duplicate_depth": {"1": 2},
        "tree_geometry": geometry,
        "native_simulator_steps": 5,
        "model_calls": 6,
        "wall_clock_seconds": 0.1,
        "failure_count": 0,
        "search_status": "completed",
    }
    aggregate = _population_aggregate([row, dict(row, record_index=1)])
    assert aggregate["duplicate_group_count"]["max"] == 1.0
    assert aggregate["paths_per_exact_state"]["max"]["max"] == 3.0
    assert aggregate["depth_distributions"]["duplicate_depth"] == {"1": 4}
    assert aggregate["t070_geometry"]["available_count"] == 2


def test_classification_ambiguous_when_support_is_below_frozen_minimum() -> None:
    rows = [
        {
            "exact_duplicate_fraction": 0.0,
            "marginal_unique_yield_400_1600": 1.0,
            "distinct_path_duplicate_group_count": 0,
        }
        for _ in range(16)
    ]
    report = classify_t079(rows, comparable_count=11)
    assert report["classification"] == "AMBIGUOUS"
    assert report["bands_frozen"] is True


def test_stage_inventory_requires_effective_sixteen_workers() -> None:
    rows = [
        {
            "record_index": index,
            "worker_count": 16,
            "effective_worker_count": 16,
            "shard_count": 16,
            "shard_index": index,
            "shard_range": [index, index + 1],
            "worker_pid": 1000 + index,
            "spawned_process_pid": 1000 + index,
            "worker_started_monotonic": 0.0,
            "worker_finished_monotonic": 10.0,
            "observed_peak_concurrency": 16,
            "worker_exit_code": 0,
            "worker_logical_cpu_count": 16,
            "worker_cpu_affinity": list(range(16)),
            "host_logical_cpu_count": 16,
            "host_cpu_affinity": list(range(16)),
            "status": "completed",
            "result": {"termination_status": "win", "problems": []},
            "problems": [],
        }
        for index in range(16)
    ]
    validate_stage_inventory(rows)
    rows[0] = dict(rows[0], worker_count=1)
    with pytest.raises(ValueError, match="16 effective workers"):
        validate_stage_inventory(rows)


def _classification_rows(
    fractions: list[float], marginal: list[float], *, distinct_count: int = 8
) -> list[dict[str, object]]:
    return [
        {
            "exact_duplicate_fraction": fraction,
            "marginal_unique_yield_400_1600": marginal[index],
            "distinct_path_duplicate_group_count": int(index < distinct_count),
        }
        for index, fraction in enumerate(fractions)
    ]


@pytest.mark.parametrize(
    ("fractions", "marginal", "expected"),
    [
        # Sorted positions 7 and 8 are .19 and .21: literal median is .20.
        (
            [0.15] * 7 + [0.19, 0.21] + [0.25] * 7,
            [0.80] * 16,
            "MATERIAL_EXACT_TRANSPOSITION_SIGNAL",
        ),
        # Sorted positions 7 and 8 are .04 and .06: median is .05.
        (
            [0.0] * 7 + [0.04, 0.06] + [0.10] * 7,
            [0.95] * 16,
            "EXACT_TRANSPOSITION_SIGNAL_WEAK",
        ),
        # Sorted positions 7 and 8 are .89 and .91: median is .90.
        (
            [0.0] * 16,
            [0.89] * 8 + [0.91] * 8,
            "EXACT_TRANSPOSITION_SIGNAL_WEAK",
        ),
    ],
)
def test_classification_uses_literal_even_sample_medians(
    fractions: list[float], marginal: list[float], expected: str
) -> None:
    report = classify_t079(
        _classification_rows(fractions, marginal), comparable_count=16
    )
    assert report["classification"] == expected


def test_classification_rejects_material_band_when_median_is_just_above_boundary() -> (
    None
):
    fractions = [0.15] * 7 + [0.19, 0.21] + [0.25] * 7
    marginal = [0.80] * 8 + [0.81] * 8
    report = classify_t079(
        _classification_rows(fractions, marginal), comparable_count=16
    )
    assert report["classification"] == "AMBIGUOUS"


def test_classification_rejects_weak_band_when_marginal_median_is_below_boundary() -> (
    None
):
    report = classify_t079(
        _classification_rows([0.0] * 16, [0.89] * 8 + [0.90] * 8),
        comparable_count=16,
    )
    assert report["classification"] == "AMBIGUOUS"


def test_occurrence_validation_rejects_false_first_seen_and_duplicate_paths() -> None:
    telemetry = _telemetry(["a", "a"])
    telemetry["expanded_states"][1]["first_seen"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="duplicate occurrence"):
        summarize_state_utilization(telemetry)

    telemetry = _telemetry(["a", "b"])
    telemetry["expanded_states"][1]["path_fingerprint"] = telemetry["expanded_states"][
        0
    ]["path_fingerprint"]  # type: ignore[index]
    with pytest.raises(ValueError, match="occurrence/path"):
        summarize_state_utilization(telemetry)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(digest_collision_count=1),
        lambda payload: payload.update(collision_check="digest_only"),
        lambda payload: payload.update(
            canonical_payloads={"a": ["state-a", "state-b"]}
        ),
    ],
)
def test_digest_collision_or_canonical_equality_failure_is_fail_closed(
    mutation,
) -> None:
    telemetry = _telemetry(["a", "a"])
    mutation(telemetry)
    with pytest.raises(ValueError, match="collision|canonical"):
        summarize_state_utilization(telemetry)


def test_stage_inventory_rejects_configured_workers_without_effective_topology() -> (
    None
):
    rows = [
        {
            "record_index": index,
            "worker_count": 16,
            "shard_count": 16,
            "status": "completed",
        }
        for index in range(16)
    ]
    with pytest.raises(ValueError, match="effective workers"):
        validate_stage_inventory(rows)


def test_stage_inventory_rejects_nonzero_worker_exit_code() -> None:
    rows = [
        {
            "record_index": index,
            "worker_count": 16,
            "effective_worker_count": 16,
            "shard_count": 16,
            "shard_index": index,
            "shard_range": [index, index + 1],
            "worker_pid": 2000 + index,
            "spawned_process_pid": 2000 + index,
            "worker_started_monotonic": 0.0,
            "worker_finished_monotonic": 10.0,
            "observed_peak_concurrency": 16,
            "worker_exit_code": 0,
            "worker_logical_cpu_count": 16,
            "worker_cpu_affinity": list(range(16)),
            "host_logical_cpu_count": 16,
            "host_cpu_affinity": list(range(16)),
            "status": "completed",
            "result": {"termination_status": "loss", "problems": []},
            "problems": [],
        }
        for index in range(16)
    ]
    rows[3] = dict(rows[3], worker_exit_code=7)
    with pytest.raises(ValueError, match="nonzero"):
        validate_stage_inventory(rows)
