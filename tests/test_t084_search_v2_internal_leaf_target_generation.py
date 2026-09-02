from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

import scripts.collect_t084_native_leaf_candidates as t084_collector
from scripts.collect_t084_native_leaf_candidates import (
    ARMS,
    _select_cell,
    _select_parity_root_indices,
    _selected_target_for_occurrence,
)
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
        "public_model_input": {
            "schema_id": "t084-public-torch-policy-value-input-v1",
            "schema_version": 1,
            "feature_schema_id": "public-tactical-v2",
            "feature_schema_version": 2,
            "snapshot_features": [float(index)],
            "public_context_features": [1.0],
            "state_features": [float(index), 1.0],
            "legal_action_features": [[0.0]],
            "eligible_action_indices": [0],
            "public_context_feature_schema_id": "public-context-model-input-v1",
            "public_context_feature_schema_version": 1,
            "public_context_feature_size": 1,
            "shape": {
                "snapshot_features": [1],
                "public_context_features": [1],
                "state_features": [2],
                "legal_action_features": [1, 1],
            },
            "hidden_state_excluded": True,
        },
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


def test_collector_validation_requires_parity_available_and_passed() -> None:
    result = validate_collector_execution(
        {
            "schema_id": "t084-native-internal-leaf-collector-v1",
            "generation_mode": "native_runtime_collector",
            "search_simulations_per_root": 100,
            "worker_count": 16,
            "effective_worker_count": 16,
            "root_runs": [],
            "arm_configs": {},
            "parity": {
                "available": False,
                "passed": False,
                "checked_root_count": 16,
                "task_count": 48,
                "arms": [],
                "acts": [],
                "act_counts": {"1": 24, "2": 24},
                "worker_count": 16,
                "material_outputs_equal": True,
                "root_action_equal": True,
                "root_statistics_equal": True,
                "rng_semantics_equal": True,
                "rows": [],
            },
            "candidate_rows": [],
        },
        [],
    )
    assert any("not available and passed" in item for item in result["problems"])


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


def _candidate(
    payload: str,
    *,
    root: str,
    digest: str = "digest",
    arm: str = "unguided_search_v2",
) -> dict:
    identity = "t084-hidden-state-" + hashlib.sha256(payload.encode()).hexdigest()
    source_identity = hashlib.sha256(root.encode()).hexdigest()
    path_fingerprint = f"path-{root}"
    occurrence_key = hashlib.sha256(
        f"{source_identity}|{arm}|{digest}|1|{path_fingerprint}".encode()
    ).hexdigest()
    return {
        "sampling_arm": arm,
        "act": 1,
        "root_identity": root,
        "exact_leaf_identity": identity,
        "exact_hidden_state_payload": {
            "canonical_native_payload": {"state": payload},
            "canonical_native_payload_json": payload,
        },
        "exact_state_digest": digest,
        "source_complete_identity_sha256": source_identity,
        "callback_ordinal": 1,
        "path_fingerprint": path_fingerprint,
        "occurrence_key": occurrence_key,
    }


def test_selection_deduplicates_repeated_hidden_state_visits() -> None:
    duplicate_a = _candidate("same-hidden-state", root="root-a")
    duplicate_b = _candidate("same-hidden-state", root="root-b")
    selected, policy = _select_cell([duplicate_a, duplicate_b], 2, {})
    assert len(selected) == 1
    assert len({row["exact_leaf_identity"] for row in selected}) == 1
    assert policy["selected"] == 1


def test_selection_prefers_distinct_roots_before_hash_tie_break() -> None:
    rows = [
        _candidate("state-a", root="root-a", digest="digest-a"),
        _candidate("state-b", root="root-a", digest="digest-b"),
        _candidate("state-c", root="root-b", digest="digest-c"),
    ]
    selected, policy = _select_cell(rows, 2, {})
    assert len(selected) == 2
    assert {row["root_identity"] for row in selected} == {"root-a", "root-b"}
    assert policy["distinct_source_roots"] == 2
    assert policy["root_first_phase_completed"] is True


def test_selection_rejects_digest_collision_with_different_canonical_payload() -> None:
    rows = [
        _candidate("state-a", root="root-a", digest="collision"),
        _candidate("state-b", root="root-b", digest="collision"),
    ]
    with pytest.raises(ValueError, match="native digest collision"):
        _select_cell(rows, 1, {})


def test_selected_replay_consumes_only_the_selected_duplicate_occurrence() -> None:
    first = _candidate("same-state", root="root-a", digest="same-digest")
    second = _candidate("same-state", root="root-b", digest="same-digest")
    selected, _ = _select_cell([first, second], 1, {})
    identity = selected[0]["exact_leaf_identity"]
    selected_spec = {
        identity: {
            "target_kind": "formal",
            "occurrence_key": selected[0]["occurrence_key"],
            "root_identity": selected[0]["root_identity"],
        }
    }
    consumed: set[str] = set()
    generated: list[str] = []
    assert (
        _selected_target_for_occurrence(
            selected_spec, identity, selected[0]["occurrence_key"], consumed
        )
        is not None
    )
    generated.append(identity)
    consumed.add(identity)
    assert (
        _selected_target_for_occurrence(
            selected_spec, identity, second["occurrence_key"], consumed
        )
        is None
    )
    assert generated == [identity]


def test_parity_subset_covers_both_acts_deterministically() -> None:
    roots = [{"act": 1} for _ in range(256)] + [{"act": 2} for _ in range(204)]
    indices = _select_parity_root_indices(roots)
    assert indices == list(range(8)) + list(range(256, 264))
    assert [roots[index]["act"] for index in indices].count(1) == 8
    assert [roots[index]["act"] for index in indices].count(2) == 8


def test_assisted_root_uses_assisted_restore_and_reaches_search_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = SimpleNamespace(
        source_seed=122,
        snapshot_raw={"ascension": 20, "act": 2},
        public_run_context={},
    )
    calls: list[str] = []

    class FakeAdapter:
        def __init__(self, **_: object) -> None:
            pass

        def battle_search_v2_with_leaf_collection(
            self, snapshot: object, **kwargs: object
        ) -> dict:
            assert snapshot == "assisted-snapshot"
            callback = kwargs["leaf_collector_callback"]
            callback(
                "opaque-checkpoint",
                {"act": 2},
                [{"scope": "battle", "bits": 1, "kind": "play", "label": "play"}],
                1,
                0,
                "path-0",
                "digest-0",
                json.dumps({"hidden": "state-0"}, sort_keys=True),
                {"seed": 122},
            )
            return {"root_action": "battle:1", "root_rows": [{"visits": 1}]}

    monkeypatch.setattr(t084_collector, "LightSpeedAdapter", FakeAdapter)
    monkeypatch.setattr(
        t084_collector,
        "record_from_manifest",
        lambda *_args, **_kwargs: root,
    )

    def assisted_restore(_adapter: object, _record: object) -> tuple[str, str]:
        calls.append("assisted")
        return "assisted-snapshot", "assisted_seed_action_trace"

    monkeypatch.setattr(
        t084_collector, "restore_assisted_battle_start_record", assisted_restore
    )
    monkeypatch.setattr(
        t084_collector,
        "build_decision_context",
        lambda *_args, **_kwargs: SimpleNamespace(
            snapshot_features=[1.0],
            legal_action_features=[[2.0, 3.0]],
            eligible_action_indices=[0],
            public_run_context={},
            tactical_feature_schema_id="public-tactical-v2",
        ),
    )
    monkeypatch.setattr(t084_collector, "public_context_features", lambda _: [0.0])
    t084_collector._ROOT_ROWS[:] = [{"_t084_source_identity": "source-0"}]
    t084_collector._NATIVE_MODULE = object()
    t084_collector._PASS_MODE = "candidate"
    t084_collector._NATIVE_COMMIT = "858f4ca"

    result = t084_collector._work_one((0, ARMS[0]))

    assert calls == ["assisted"]
    assert result["restoration_method"] == "assisted_seed_action_trace"
    assert result["candidate_count"] == 1
    assert len(result["candidate_rows"]) == 1
    public_input = result["candidate_rows"][0]["public_model_input"]
    assert (
        public_input["state_features"]
        == public_input["snapshot_features"] + public_input["public_context_features"]
    )
    assert isinstance(public_input["legal_action_features"][0], list)
    assert public_input["hidden_state_excluded"] is True


def test_prior_policy_callback_uses_search_guidance_policy_probabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = SimpleNamespace(
        source_seed=122,
        snapshot_raw={"ascension": 20, "act": 1},
        public_run_context={"visible": "context"},
    )
    observed_contexts: list[object] = []
    observed_priors: list[list[float]] = []

    class FakeScorer:
        def score_actions(self, _context: object) -> list[float]:
            raise AssertionError("T084 must use the SearchGuidance scorer contract")

        def score_decision_context(self, context: object) -> SimpleNamespace:
            observed_contexts.append(context)
            return SimpleNamespace(
                action_scores=[
                    SimpleNamespace(
                        legal_action_index=0,
                        policy_logit=1.25,
                        policy_probability=0.01,
                    ),
                    SimpleNamespace(
                        legal_action_index=1,
                        policy_logit=-2.5,
                        policy_probability=0.99,
                    ),
                ],
                value_prediction=SimpleNamespace(
                    battle_survival_probability=999.0,
                ),
            )

    class FakeAdapter:
        def __init__(self, **_: object) -> None:
            pass

        def battle_search_v2_with_leaf_collection(
            self, snapshot: object, **kwargs: object
        ) -> dict:
            assert snapshot == "assisted-snapshot"
            policy_callback = kwargs["policy_prior_callback"]
            assert callable(policy_callback)
            observed_priors.append(
                policy_callback(
                    {"act": 1, "hidden_state": "not-public"},
                    [
                        {
                            "scope": "battle",
                            "bits": 1,
                            "kind": "play",
                            "label": "play-1",
                        },
                        {
                            "scope": "battle",
                            "bits": 2,
                            "kind": "play",
                            "label": "play-2",
                        },
                    ],
                )
            )
            callback = kwargs["leaf_collector_callback"]
            callback(
                "opaque-checkpoint",
                {"act": 1},
                [{"scope": "battle", "bits": 1, "kind": "play", "label": "play"}],
                1,
                0,
                "path-0",
                "digest-0",
                json.dumps({"hidden": "state-0"}, sort_keys=True),
                {"seed": 122},
            )
            return {"root_action": "battle:1", "root_rows": [{"visits": 1}]}

    monkeypatch.setattr(t084_collector, "LightSpeedAdapter", FakeAdapter)
    monkeypatch.setattr(
        t084_collector,
        "record_from_manifest",
        lambda *_args, **_kwargs: root,
    )
    monkeypatch.setattr(
        t084_collector,
        "restore_assisted_battle_start_record",
        lambda *_args, **_kwargs: ("assisted-snapshot", "assisted_restore"),
    )
    monkeypatch.setattr(
        t084_collector,
        "_scorer_for_arm",
        lambda _arm: FakeScorer(),
    )

    def build_context(
        _raw: object,
        actions: list[object],
        *_args: object,
        **kwargs: object,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            snapshot_features=[1.0],
            legal_action_features=[[2.0, 3.0] for _ in actions],
            eligible_action_indices=list(range(len(actions))),
            public_run_context=kwargs["public_run_context"],
        )

    monkeypatch.setattr(t084_collector, "build_decision_context", build_context)
    monkeypatch.setattr(t084_collector, "public_context_features", lambda _: [0.0])
    t084_collector._ROOT_ROWS[:] = [{"_t084_source_identity": "source-0"}]
    t084_collector._NATIVE_MODULE = object()
    t084_collector._PASS_MODE = "candidate"
    t084_collector._NATIVE_COMMIT = "858f4ca"

    result = t084_collector._work_one((0, ARMS[1]))

    assert observed_priors == [[0.01, 0.99]]
    assert len(observed_contexts) == 1
    assert observed_contexts[0].public_run_context == {"visible": "context"}
    assert result["candidate_count"] == 1
