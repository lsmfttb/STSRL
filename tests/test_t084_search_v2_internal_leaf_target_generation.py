from __future__ import annotations

import hashlib

import pytest

from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    ACTION_CAP,
    CALIBRATION_COUNT,
    CALIBRATION_REPLICATES,
    CANDIDATE_REPETITIONS,
    calibration_metrics,
    classify_t084,
    derive_replicate_seed,
    select_repetition_count,
    validate_collector_execution,
    validate_leaf_row,
    validate_native_probe,
    validate_replicate,
    validate_target_rows,
)


def _leaf(index: int, *, values: list[float] | None = None) -> dict:
    return {
        "sampling_arm": "unguided_search_v2",
        "act": 1 if index % 2 == 0 else 2,
        "root_identity": f"root-{index}",
        "exact_leaf_identity": f"leaf-{index}",
        "exact_hidden_state_payload": {"opaque_native_payload": index},
        "exact_state_digest": hashlib.sha256(f"leaf-{index}".encode()).hexdigest(),
        "public_projection": {"hp": 50 + index},
        "public_model_input": [index, 1],
        "legal_actions": [{"stable_id": "battle:1", "occurrence": 0}],
        "source_complete_identity_sha256": f"{index:064x}",
        "depth": 1,
        "replicates": [
            {
                "replicate_index": ordinal,
                "terminal": True,
                "cap_hit": False,
                "transition_count": 3,
                "terminal_evaluate_end_state": value,
            }
            for ordinal, value in enumerate(
                values
                if values is not None
                else [float(index)] * CALIBRATION_REPLICATES,
                1,
            )
        ],
    }


def test_replicate_seed_is_exact_frozen_sha256_prefix() -> None:
    result = derive_replicate_seed("native", "source", "arm", "leaf", 7)
    digest_input = "native|source|arm|leaf|7"
    digest = hashlib.sha256(digest_input.encode()).hexdigest()
    assert result == {
        "digest_input": digest_input,
        "sha256": digest,
        "seed": int(digest[:8], 16),
        "replicate_index": 7,
    }


def test_nonterminal_or_cap_hit_replicate_is_never_valid() -> None:
    assert not validate_replicate(
        {
            "terminal": False,
            "cap_hit": True,
            "transition_count": ACTION_CAP,
            "terminal_evaluate_end_state": 4.0,
        }
    )
    assert not validate_replicate(
        {
            "terminal": True,
            "cap_hit": False,
            "transition_count": ACTION_CAP + 1,
            "terminal_evaluate_end_state": 4.0,
        }
    )


def test_leaf_requires_restorable_hidden_payload_and_public_projection() -> None:
    row = _leaf(1)
    assert validate_leaf_row(row, require_replicates=CALIBRATION_REPLICATES) == row
    missing_payload = dict(row)
    del missing_payload["exact_hidden_state_payload"]
    with pytest.raises(ValueError, match="exact_hidden_state_payload"):
        validate_leaf_row(missing_payload)


def test_smallest_passing_repetition_count_is_selected() -> None:
    rows = [
        _leaf(index, values=[float(index)] * CALIBRATION_REPLICATES)
        for index in range(CALIBRATION_COUNT)
    ]
    result = select_repetition_count(rows)
    assert result["selected_repetition_count"] == CANDIDATE_REPETITIONS[0]
    assert all(item["available"] for item in result["candidate_metrics"])


def test_calibration_is_unavailable_when_reference_replicate_is_cap_hit() -> None:
    values = [1.0] * CALIBRATION_REPLICATES
    row = _leaf(0, values=values)
    row["replicates"][200]["terminal"] = False
    metrics = calibration_metrics([row] * CALIBRATION_COUNT, 16)
    assert metrics["available"] is False
    assert metrics["problems"]


def _calibration() -> dict[str, object]:
    return {"qualified": True}


def test_four_terminal_classifications_have_independent_boundaries() -> None:
    assert (
        classify_t084(
            integrity_valid=False,
            execution_valid=True,
            collector_parity=True,
            calibration=_calibration(),
            support_sufficient=True,
            formal_valid=True,
        )
        == "INCOMPLETE"
    )
    assert (
        classify_t084(
            integrity_valid=True,
            execution_valid=True,
            collector_parity=True,
            calibration=_calibration(),
            support_sufficient=False,
            formal_valid=False,
        )
        == "LEAF_TARGET_SUPPORT_INSUFFICIENT"
    )
    assert (
        classify_t084(
            integrity_valid=True,
            execution_valid=True,
            collector_parity=True,
            calibration={"qualified": False},
            support_sufficient=True,
            formal_valid=True,
        )
        == "LEAF_TARGET_MONTE_CARLO_UNSTABLE"
    )
    assert (
        classify_t084(
            integrity_valid=True,
            execution_valid=True,
            collector_parity=True,
            calibration=_calibration(),
            support_sufficient=True,
            formal_valid=True,
        )
        == "LEAF_CONTINUATION_UTILITY_TARGETS_READY"
    )


def test_formal_validation_rejects_nonterminal_replicate_and_missing_seed_lineage() -> (
    None
):
    row = _leaf(1, values=[1.0] * 16)
    row["replicates"] = row["replicates"][:16]
    row["replicates"][0]["terminal"] = False
    result = validate_target_rows(
        [],
        [row],
        native_commit="runtime-native-commit",
        selected_repetition_count=16,
        candidate_ids={"leaf-1"},
    )
    assert result["valid"] is False
    assert any("invalid continuation replicates" in item for item in result["problems"])


def test_replicate_seed_is_bound_to_runtime_native_commit() -> None:
    baseline = derive_replicate_seed("baseline-native", "source", "arm", "leaf", 1)
    runtime = derive_replicate_seed("runtime-native", "source", "arm", "leaf", 1)
    assert baseline["seed"] != runtime["seed"]


def test_target_validation_rejects_baseline_seed_for_runtime_native_commit() -> None:
    row = _leaf(1, values=[1.0] * CALIBRATION_REPLICATES)
    runtime_commit = "runtime-native-commit"
    row["replicates"][0]["seed_provenance"] = derive_replicate_seed(
        "baseline-native-commit",
        row["source_complete_identity_sha256"],
        row["sampling_arm"],
        row["exact_leaf_identity"],
        1,
    )
    result = validate_target_rows(
        [row],
        [],
        native_commit=runtime_commit,
        selected_repetition_count=None,
        candidate_ids={row["exact_leaf_identity"]},
    )
    assert result["valid"] is False
    assert any("seed lineage mismatch" in item for item in result["problems"])


def test_collector_validation_requires_complete_three_arm_root_inventory() -> None:
    result = validate_collector_execution(
        {
            "schema_id": "t084-native-internal-leaf-collector-v1",
            "generation_mode": "native_runtime_collector",
            "search_simulations_per_root": 100,
            "worker_count": 16,
            "effective_worker_count": 16,
            "root_runs": [],
            "arm_configs": {},
            "parity": {},
            "candidate_rows": [],
        },
        [],
    )
    assert result["valid"] is False
    assert any("3x460" in item for item in result["problems"])
    assert any("parity" in item for item in result["problems"])


def test_native_probe_requires_actual_cpython_313_runtime_and_apis() -> None:
    native = {"identity_valid": True, "resolved_commit": "native-commit"}
    probe = {
        "api_methods": {
            "battle_search_v2_with_leaf_collection": True,
            "evaluate_leaf_continuation": True,
            "capture_checkpoint": True,
            "restore_checkpoint": True,
        },
        "python_executable": "/home/lsmft/stsrl-spikes/py313-torch/bin/python",
        "python_version": "3.13.13",
        "extension": "/tmp/slaythespire.cpython-313-x86_64-linux-gnu.so",
        "native_commit": "native-commit",
    }
    assert validate_native_probe(probe, native)["valid"] is True
    probe["extension"] = "/tmp/slaythespire.cpython-314-x86_64-linux-gnu.so"
    assert validate_native_probe(probe, native)["valid"] is False
