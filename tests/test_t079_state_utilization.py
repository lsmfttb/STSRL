from __future__ import annotations

import pytest

from sts_combat_rl.sim.t079_state_utilization import (
    classify_t079,
    compare_prefix_sequences,
    summarize_state_utilization,
    validate_stage_inventory,
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
        "digest_collision_count": 0,
        "collision_check": "canonical_payload_equality_within_digest_bucket",
        "expanded_path_node_count": len(rows),
        "expanded_states": rows,
    }


def test_summarize_reports_exact_duplicates_and_distinct_paths() -> None:
    result = summarize_state_utilization(_telemetry(["a", "b", "a", "a"]))
    assert result["expanded_path_nodes"] == 4
    assert result["unique_exact_states"] == 2
    assert result["exact_duplicate_path_nodes"] == 2
    assert result["exact_duplicate_fraction"] == pytest.approx(0.5)
    assert result["duplicate_group_count"] == 1
    assert result["distinct_path_duplicate_group_count"] == 1
    assert result["paths_per_exact_state"]["max"] == 3


def test_prefix_metrics_are_missing_when_sequences_are_not_prefixes() -> None:
    result = compare_prefix_sequences(
        {100: ["a"] * 100, 400: ["a"] * 99 + ["b"] * 301, 1600: ["a"] * 1600}
    )
    assert result["100_400"]["prefix_comparable"] is False
    assert result["100_400"]["marginal_unique_yield"] is None
    assert result["400_1600"]["prefix_comparable"] is False


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
            "worker_started_monotonic": 0.0,
            "worker_finished_monotonic": 10.0,
            "observed_peak_concurrency": 16,
            "status": "completed",
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
