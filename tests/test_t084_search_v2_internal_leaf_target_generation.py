from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

import scripts.collect_t084_native_leaf_candidates as t084_collector
from scripts.collect_t084_native_leaf_candidates import (
    ARMS,
    PROGRESS_SCHEMA_ID,
    _candidate_metadata,
    _CandidateCache,
    _iter_stage_field_rows,
    _ordered_cell_rows,
    _ProgressStore,
    _RepairCache,
    _select_cell,
    _select_parity_root_indices,
    _selected_target_for_occurrence,
    _task_key,
    _validate_worker_count,
    _write_streaming_json_temp,
)
from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    ACTION_CAP,
    CALIBRATION_COUNT,
    CALIBRATION_REPLICATES,
    CANDIDATE_REPETITIONS,
    _IncrementalJsonReader,
    _stream_validate_collector,
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


def test_incremental_collector_reader_yields_array_items_across_small_chunks() -> None:
    class ChunkedStream:
        def __init__(self, value: str) -> None:
            self.value = value

        def read(self, size: int) -> str:
            chunk, self.value = self.value[:size], self.value[size:]
            return chunk

    reader = _IncrementalJsonReader(
        ChunkedStream('{"metadata":{"ok":true},"rows":[{"i":1},{"i":2}]}')
    )
    reader._CHUNK_SIZE = 3
    fields = reader.object_fields()
    key, metadata = next(fields)
    assert (key, metadata) == ("metadata", {"ok": True})
    key, rows = next(fields)
    assert key == "rows"
    assert list(rows) == [{"i": 1}, {"i": 2}]
    with pytest.raises(StopIteration):
        next(fields)


def test_streaming_collector_reader_fails_closed_on_truncated_array(tmp_path) -> None:
    path = tmp_path / "truncated-collector.json"
    path.write_text(
        '{"schema_id":"t084-native-internal-leaf-collector-v1",'
        '"candidate_rows":[{"partial":true}',
        encoding="utf-8",
    )
    result = _stream_validate_collector(path, [], native_commit="native")
    assert result["valid"] is False
    assert any("malformed or truncated" in item for item in result["problems"])


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


def test_collector_validation_allows_explicit_lower_worker_count() -> None:
    result = validate_collector_execution(
        {
            "schema_id": "t084-native-internal-leaf-collector-v1",
            "generation_mode": "native_runtime_collector",
            "search_simulations_per_root": 100,
            "worker_count": 6,
            "effective_worker_count": 6,
            "root_runs": [],
            "arm_configs": {},
            "parity": {},
            "candidate_rows": [],
        },
        [],
    )
    assert not any(
        "configured/effective worker counts" in item for item in result["problems"]
    )


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


def test_ordered_cell_rows_ranks_each_candidate_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _candidate("state-a", root="root-a", digest="digest-a"),
        _candidate("state-b", root="root-a", digest="digest-b"),
        _candidate("state-c", root="root-b", digest="digest-c"),
        _candidate("state-d", root="root-c", digest="digest-d"),
    ]
    calls = 0
    original_rank = t084_collector._leaf_rank

    def rank_once(row: dict[str, object]) -> str:
        nonlocal calls
        calls += 1
        return original_rank(row)

    monkeypatch.setattr(t084_collector, "_leaf_rank", rank_once)
    ordered = _ordered_cell_rows(rows)

    assert calls == len(rows)
    assert len({row["exact_leaf_identity"] for row in ordered}) == len(rows)
    assert len({row["root_identity"] for row in ordered[:3]}) == 3


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
    roots = [{"snapshot_raw": {"act": 1}} for _ in range(256)] + [
        {"snapshot_raw": {"act": 2}} for _ in range(204)
    ]
    indices = _select_parity_root_indices(roots)
    assert indices == list(range(8)) + list(range(256, 264))
    assert [roots[index]["snapshot_raw"]["act"] for index in indices].count(1) == 8
    assert [roots[index]["snapshot_raw"]["act"] for index in indices].count(2) == 8


def test_parity_row_act_comes_from_restored_snapshot_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_raw = {
        "_t084_source_identity": "source-2",
        "snapshot_raw": {"act": 2, "ascension": 20},
    }
    root = SimpleNamespace(
        source_seed=122,
        snapshot_raw={"act": 2, "ascension": 20},
        public_run_context={},
    )

    class FakeSnapshot:
        def __init__(self) -> None:
            self.raw = {"floor_num": 1}

    class FakeAdapter:
        def __init__(self, **_: object) -> None:
            pass

        def battle_search_v2(self, _snapshot: object, **_: object) -> dict:
            return {"root_action": "battle:1", "root_rows": [{"visits": 1}]}

        def battle_search_v2_with_leaf_collection(
            self, _snapshot: object, **kwargs: object
        ) -> dict:
            callback = kwargs["leaf_collector_callback"]
            callback(
                {
                    "battle_context_seed": 122,
                    "battle_context_floor_num": 1,
                    "search_action_rng_seed_rule": (
                        "BattleScumSearcher2::randGen seeded from BattleContext.seed+floorNum"
                    ),
                }
            )
            return {"root_action": "battle:1", "root_rows": [{"visits": 1}]}

    monkeypatch.setattr(t084_collector, "LightSpeedAdapter", FakeAdapter)
    monkeypatch.setattr(
        t084_collector, "record_from_manifest", lambda *_args, **_kwargs: root
    )
    monkeypatch.setattr(
        t084_collector,
        "restore_assisted_battle_start_record",
        lambda *_args, **_kwargs: (FakeSnapshot(), "assisted_restore"),
    )
    monkeypatch.setattr(t084_collector, "_ROOT_ROWS", [root_raw])
    monkeypatch.setattr(t084_collector, "_NATIVE_MODULE", object())
    monkeypatch.setattr(t084_collector, "_NATIVE_COMMIT", "native-commit")

    result = t084_collector._work_parity_one((0, ARMS[0]))

    assert result["act"] == 2


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


def _progress_identity() -> dict[str, object]:
    return {
        "code": {"git_head": "code-a", "collector_sha256": "collector-a"},
        "native_commit": "native-a",
        "t064_manifest_sha256": "manifest-a",
        "checkpoint_identities": {"arm": {"sha256": "checkpoint-a"}},
    }


def _progress_configuration() -> dict[str, object]:
    return {
        "task_id": "T084",
        "arms": list(ARMS),
        "workers": 16,
        "search_simulations_per_root": 100,
    }


def test_progress_task_results_are_atomic_and_resume_skips_successes(
    tmp_path,
) -> None:
    progress_path = tmp_path / "t084.progress.json"
    output_path = tmp_path / "t084.json"
    identity = _progress_identity()
    configuration = _progress_configuration()
    store = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=False,
    )
    assert store.document["schema_id"] == PROGRESS_SCHEMA_ID
    tasks = [(0, ARMS[0]), (1, ARMS[1])]
    store.ensure_stage(
        "candidate",
        tasks,
        pass_index=0,
        task_ranges="test task range",
    )
    success = {
        "root_index": 0,
        "sampling_arm": ARMS[0],
        "worker_pid": 123,
    }
    store.record_success("candidate", tasks[0], success)
    store.record_failure("candidate", tasks[1], RuntimeError("transient"))

    assert progress_path.is_file()
    assert not list(tmp_path.rglob("*.tmp"))
    resumed = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=True,
    )
    cached = resumed.successful_results("candidate", tasks)
    assert cached[_task_key(tasks[0])] == success
    assert [task for task in tasks if _task_key(task) not in cached] == [tasks[1]]
    assert (
        resumed.document["stages"]["candidate"]["tasks"][_task_key(tasks[1])]["status"]
        == "failed"
    )
    assert resumed.stage_failures("candidate")


def test_progress_resume_rejects_identity_and_stage_configuration_mismatch(
    tmp_path,
) -> None:
    progress_path = tmp_path / "t084.progress.json"
    output_path = tmp_path / "t084.json"
    identity = _progress_identity()
    configuration = _progress_configuration()
    store = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=False,
    )
    tasks = [(0, ARMS[0])]
    store.ensure_stage("candidate", tasks, pass_index=0, task_ranges="range")

    with pytest.raises(ValueError, match="identity mismatch"):
        _ProgressStore(
            progress_path,
            identity={**identity, "native_commit": "native-b"},
            configuration=configuration,
            output_path=output_path,
            resume=True,
        )
    resumed = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=True,
    )
    with pytest.raises(ValueError, match="stage configuration mismatch"):
        resumed.ensure_stage(
            "candidate",
            [(0, ARMS[1])],
            pass_index=0,
            task_ranges="range",
        )


def test_progress_corruption_fails_closed_before_reuse(tmp_path) -> None:
    progress_path = tmp_path / "t084.progress.json"
    output_path = tmp_path / "t084.json"
    identity = _progress_identity()
    configuration = _progress_configuration()
    store = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=False,
    )
    task = (0, ARMS[0])
    store.ensure_stage("candidate", [task], pass_index=0, task_ranges="range")
    store.record_success(
        "candidate",
        task,
        {"root_index": 0, "sampling_arm": ARMS[0], "worker_pid": 123},
    )
    artifact = store.document["stages"]["candidate"]["tasks"][_task_key(task)][
        "artifact"
    ]
    artifact_path = progress_path.parent / artifact["path"]
    artifact_path.write_text("{}\n", encoding="utf-8")
    resumed = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=True,
    )
    with pytest.raises(ValueError, match="artifact (size|hash) mismatch"):
        resumed.successful_results("candidate", [task])


@pytest.mark.parametrize("workers", [1, 4, 6, 16])
def test_collector_accepts_bounded_worker_range(workers: int) -> None:
    assert _validate_worker_count(workers) == workers


@pytest.mark.parametrize("workers", [0, -1, 17, True, "6", None])
def test_collector_rejects_worker_count_outside_bounded_range(workers) -> None:
    with pytest.raises(ValueError, match="range 1..16"):
        _validate_worker_count(workers)


def test_progress_resume_rejects_worker_configuration_change(tmp_path) -> None:
    progress_path = tmp_path / "t084.progress.json"
    output_path = tmp_path / "t084.json"
    identity = _progress_identity()
    _ProgressStore(
        progress_path,
        identity=identity,
        configuration={**_progress_configuration(), "workers": 6},
        output_path=output_path,
        resume=False,
    )
    with pytest.raises(ValueError, match="task configuration mismatch"):
        _ProgressStore(
            progress_path,
            identity=identity,
            configuration={**_progress_configuration(), "workers": 4},
            output_path=output_path,
            resume=True,
        )


def _candidate_cache_fixture(tmp_path, *, task_count: int = 1):
    cache_dir = tmp_path / "candidate-cache"
    cache_path = cache_dir / "t084-native-collector.progress.json"
    old_output = tmp_path / "old-candidate-output.json"
    identity = {
        **_progress_identity(),
        "code": {
            "git_head": "old-candidate-producer",
            "collector_script_sha256": "a" * 64,
            "target_module_sha256": "b" * 64,
        },
    }
    configuration = {
        **_progress_configuration(),
        "root_count": task_count,
        "output_path": str(old_output.resolve()),
    }
    store = _ProgressStore(
        cache_path,
        identity=identity,
        configuration=configuration,
        output_path=old_output,
        resume=False,
    )
    tasks = [(index, ARMS[0]) for index in range(task_count)]
    store.ensure_stage(
        "candidate", tasks, pass_index=0, task_ranges="candidate test range"
    )
    results = []
    for task in tasks:
        result = {
            "root_index": task[0],
            "sampling_arm": task[1],
            "candidate_rows": [],
            "target_rows": [],
            "worker_pid": 123 + task[0],
        }
        results.append(result)
        store.record_success("candidate", task, result)
    stage = store.document["stages"]["candidate"]
    stage["status"] = "COMPLETE"
    stage["worker_evidence"] = {
        "configured_worker_count": 8,
        "observed_worker_count": 8,
        "effective_worker_count": 8,
    }
    stage["last_failures"] = []
    store._save()
    expected_configuration = {
        **configuration,
        "workers": 16,
        "output_path": str((tmp_path / "new-output.json").resolve()),
    }
    return (
        cache_dir,
        identity,
        expected_configuration,
        tasks,
        results,
    )


def test_candidate_cache_reuses_complete_parts_and_records_two_producers(
    tmp_path,
) -> None:
    cache_dir, identity, configuration, tasks, results = _candidate_cache_fixture(
        tmp_path
    )
    cache = _CandidateCache.load(
        cache_dir,
        expected_identity=identity,
        expected_configuration=configuration,
        tasks=tasks,
    )

    assert list(cache.iter_successful_results("candidate", tasks)) == list(
        zip(tasks, results, strict=True)
    )
    provenance = cache.provenance(
        {
            "git_head": "current-postprocessor",
            "collector_script_sha256": "c" * 64,
            "target_module_sha256": "d" * 64,
        }
    )
    assert provenance["candidate_producer_identity"]["git_head"] == (
        "old-candidate-producer"
    )
    assert provenance["postprocessing_producer_identity"]["git_head"] == (
        "current-postprocessor"
    )
    assert provenance["source_candidate_stage"]["part_count"] == 1


def test_candidate_cache_prefers_preserved_producer_identity_from_wrapper_metadata(
    tmp_path,
) -> None:
    cache_dir, identity, configuration, tasks, _ = _candidate_cache_fixture(tmp_path)
    progress_path = cache_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    document["identity"]["code"]["git_head"] = (
        "08800f6cb5be8116cfa7b429dfaa990c10a4a560"
    )
    document["identity"]["code"]["collector_script_sha256"] = (
        "9f199ca31451291c8307ce1762de5c632b9133aa328bc021c1c814c172fd3eab"
    )
    document["cache_reuse"] = {
        "cached_candidate_code_identity": {
            "git_head": "2afb2ccc8989cf86ae66d832e6da5a030357c06d",
            "collector_script_sha256": (
                "84aa2e33eec42503d598503c37fda53001052b51e0190e4b0d02085950e8b487"
            ),
            "target_module_sha256": "b" * 64,
        },
        "current_postprocessing_code_identity": dict(document["identity"]["code"]),
    }
    progress_path.write_text(json.dumps(document), encoding="utf-8")

    cache = _CandidateCache.load(
        cache_dir,
        expected_identity=identity,
        expected_configuration=configuration,
        tasks=tasks,
    )
    provenance = cache.provenance(identity["code"])

    assert provenance["candidate_producer_identity"]["git_head"] == (
        "2afb2ccc8989cf86ae66d832e6da5a030357c06d"
    )
    assert provenance["candidate_producer_identity_source"] == (
        "cache_reuse.cached_candidate_code_identity"
    )


def test_candidate_cache_rejects_unhashed_wrapper_producer_identity(tmp_path) -> None:
    cache_dir, identity, configuration, tasks, _ = _candidate_cache_fixture(tmp_path)
    progress_path = cache_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    document["cache_reuse"] = {
        "cached_candidate_code_identity": "2afb2ccc8989cf86ae66d832e6da5a030357c06d"
    }
    progress_path.write_text(json.dumps(document), encoding="utf-8")

    cache = _CandidateCache.load(
        cache_dir,
        expected_identity=identity,
        expected_configuration=configuration,
        tasks=tasks,
    )
    with pytest.raises(
        ValueError, match="must include script and target-module hashes"
    ):
        cache.provenance(identity["code"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda document: document["stages"]["candidate"].update(status="RUNNING"),
            "not COMPLETE",
        ),
        (
            lambda document: document["identity"].update(native_commit="other"),
            "identity mismatch",
        ),
        (
            lambda document: document["identity"]["code"].update(
                target_module_sha256="e" * 64
            ),
            "target module identity mismatch",
        ),
        (
            lambda document: document["configuration"].update(
                search_simulations_per_root=99
            ),
            "task configuration mismatch",
        ),
    ],
)
def test_candidate_cache_rejects_incomplete_or_mismatched_identity(
    tmp_path,
    mutation,
    message,
) -> None:
    cache_dir, identity, configuration, tasks, _ = _candidate_cache_fixture(tmp_path)
    progress_path = cache_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    mutation(document)
    progress_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        _CandidateCache.load(
            cache_dir,
            expected_identity=identity,
            expected_configuration=configuration,
            tasks=tasks,
        )


def test_candidate_cache_rejects_part_hash_corruption_fail_closed(tmp_path) -> None:
    cache_dir, identity, configuration, tasks, _ = _candidate_cache_fixture(tmp_path)
    progress_path = cache_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    artifact = document["stages"]["candidate"]["tasks"][_task_key(tasks[0])]["artifact"]
    artifact_path = progress_path.parent / artifact["path"]
    artifact_path.write_bytes(artifact_path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="artifact (size|hash) mismatch"):
        cache = _CandidateCache.load(
            cache_dir,
            expected_identity=identity,
            expected_configuration=configuration,
            tasks=tasks,
        )
        list(cache.iter_successful_results("candidate", tasks))


def test_candidate_cache_accepts_sorted_iteration_inventory(tmp_path) -> None:
    cache_dir, identity, configuration, tasks, results = _candidate_cache_fixture(
        tmp_path, task_count=2
    )
    cache = _CandidateCache.load(
        cache_dir,
        expected_identity=identity,
        expected_configuration=configuration,
        tasks=tasks,
    )

    assert list(
        cache.iter_successful_results("candidate", list(reversed(tasks)))
    ) == list(zip(tasks, results, strict=True))


def _repair_cache_fixture(tmp_path):
    (
        candidate_dir,
        candidate_identity,
        configuration,
        tasks,
        _,
    ) = _candidate_cache_fixture(tmp_path)
    current_identity = {
        **candidate_identity,
        "code": {
            "git_head": "current-repair",
            "collector_script_sha256": "d" * 64,
            "target_module_sha256": "b" * 64,
        },
    }
    candidate_cache = _CandidateCache.load(
        candidate_dir,
        expected_identity=current_identity,
        expected_configuration=configuration,
        tasks=tasks,
    )

    repair_dir = tmp_path / "replay-source"
    repair_path = repair_dir / "t084-native-collector.progress.json"
    repair_output = tmp_path / "old-replay-output.json"
    source_identity = {
        **current_identity,
        "code": {
            "git_head": "old-replay",
            "collector_script_sha256": "c" * 64,
            "target_module_sha256": "b" * 64,
        },
    }
    source_configuration = {
        **configuration,
        "workers": 8,
        "output_path": str(repair_output.resolve()),
    }
    store = _ProgressStore(
        repair_path,
        identity=source_identity,
        configuration=source_configuration,
        output_path=repair_output,
        resume=False,
    )
    leaf_id = "t084-hidden-state-" + hashlib.sha256(b"payload").hexdigest()
    target_specs = {
        leaf_id: {
            "target_kind": "formal",
            "occurrence_key": "occurrence",
            "root_identity": "root-0",
            "sampling_arm": ARMS[0],
            "act": 1,
        }
    }
    store.ensure_stage(
        "selected_leaf_continuation_pass_0001",
        tasks,
        pass_index=1,
        task_ranges="repair test range",
        plan={"target_specs": target_specs},
    )
    store.record_success(
        "selected_leaf_continuation_pass_0001",
        tasks[0],
        {
            "root_index": tasks[0][0],
            "sampling_arm": tasks[0][1],
            "target_rows": [
                {
                    "exact_leaf_identity": leaf_id,
                    "occurrence_key": "occurrence",
                    "root_identity": "root-0",
                    "sampling_arm": ARMS[0],
                    "act": 1,
                    "target_kind": "formal",
                    "replicates": [],
                }
            ],
            "candidate_rows": [],
        },
    )
    stage = store.document["stages"]["selected_leaf_continuation_pass_0001"]
    stage["status"] = "COMPLETE"
    stage["worker_evidence"] = {
        "configured_worker_count": 8,
        "observed_worker_count": 8,
        "effective_worker_count": 8,
        "worker_pids": [321],
    }
    stage["last_failures"] = []
    recorded_candidate_cache = candidate_cache.provenance(current_identity["code"])
    recorded_candidate_cache["candidate_producer_identity"] = {
        "git_head": "archived-candidate",
        "collector_script_sha256": "e" * 64,
        "target_module_sha256": "b" * 64,
    }
    recorded_candidate_cache["candidate_producer_identity_source"] = (
        "cache_reuse.cached_candidate_code_identity"
    )
    store.document["candidate_cache"] = recorded_candidate_cache
    store.document["state"] = "FAILED"
    store.document["last_error"] = {
        "type": "ValueError",
        "message": "T084 parity requires at least eight roots from each Act",
    }
    store._save()
    return (
        repair_dir,
        candidate_cache,
        current_identity,
        configuration,
        tasks,
        target_specs,
    )


def test_repair_cache_reuses_only_complete_selected_replay_without_native_replay(
    tmp_path,
) -> None:
    (
        repair_dir,
        candidate_cache,
        identity,
        configuration,
        tasks,
        target_specs,
    ) = _repair_cache_fixture(tmp_path)

    repair = _RepairCache.load(
        repair_dir,
        expected_identity=identity,
        expected_configuration=configuration,
        tasks=tasks,
        candidate_cache=candidate_cache,
    )

    assert repair.target_specs == target_specs
    provenance = repair.provenance(identity["code"])
    assert provenance["reused_stage"]["native_replay_executed"] is False
    assert provenance["cached_candidate_producer_identity"]["git_head"] == (
        "archived-candidate"
    )
    resolved_candidate = candidate_cache.provenance(
        identity["code"],
        candidate_producer_identity=provenance["cached_candidate_producer_identity"],
        candidate_producer_identity_source=repair.candidate_cache_provenance[
            "candidate_producer_identity_source"
        ],
    )
    assert resolved_candidate["candidate_producer_identity"]["git_head"] == (
        "archived-candidate"
    )
    assert resolved_candidate["postprocessing_producer_identity"] == identity["code"]


def test_repair_cache_rejects_selected_replay_part_corruption(tmp_path) -> None:
    (
        repair_dir,
        candidate_cache,
        identity,
        configuration,
        tasks,
        _,
    ) = _repair_cache_fixture(tmp_path)
    progress_path = repair_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    artifact = document["stages"]["selected_leaf_continuation_pass_0001"]["tasks"][
        _task_key(tasks[0])
    ]["artifact"]
    artifact_path = progress_path.parent / artifact["path"]
    artifact_path.write_bytes(artifact_path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="artifact (size|hash) mismatch"):
        _RepairCache.load(
            repair_dir,
            expected_identity=identity,
            expected_configuration=configuration,
            tasks=tasks,
            candidate_cache=candidate_cache,
        )


def test_repair_cache_rejects_target_plan_hash_mismatch(tmp_path) -> None:
    (
        repair_dir,
        candidate_cache,
        identity,
        configuration,
        tasks,
        _,
    ) = _repair_cache_fixture(tmp_path)
    progress_path = repair_dir / "t084-native-collector.progress.json"
    document = json.loads(progress_path.read_text(encoding="utf-8"))
    document["stages"]["selected_leaf_continuation_pass_0001"]["plan"]["target_specs"][
        "extra"
    ] = {
        "target_kind": "formal",
        "occurrence_key": "other",
        "root_identity": "root-0",
        "sampling_arm": ARMS[0],
        "act": 1,
    }
    progress_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="target plan hash mismatch"):
        _RepairCache.load(
            repair_dir,
            expected_identity=identity,
            expected_configuration=configuration,
            tasks=tasks,
            candidate_cache=candidate_cache,
        )


def test_progress_parts_are_iterated_lazily_and_final_rows_are_streamed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress_path = tmp_path / "t084.progress.json"
    output_path = tmp_path / "t084.json"
    identity = _progress_identity()
    configuration = _progress_configuration()
    store = _ProgressStore(
        progress_path,
        identity=identity,
        configuration=configuration,
        output_path=output_path,
        resume=False,
    )
    tasks = [(0, ARMS[0]), (1, ARMS[0])]
    store.ensure_stage("candidate", tasks, pass_index=0, task_ranges="range")
    for index, task in enumerate(tasks):
        store.record_success(
            "candidate",
            task,
            {
                "root_index": task[0],
                "sampling_arm": task[1],
                "candidate_rows": [{"row": index}],
                "target_rows": [],
            },
        )

    reads: list[str] = []
    original_read = store._read_task_artifact

    def read_one(
        stage_key: str,
        task: tuple[int, str],
        entry: dict[str, object],
    ) -> dict[str, object]:
        reads.append(_task_key(task))
        return original_read(stage_key, task, entry)

    monkeypatch.setattr(store, "_read_task_artifact", read_one)
    iterator = _iter_stage_field_rows(store, "candidate", tasks, "candidate_rows")
    assert reads == []
    first = next(iterator)
    assert first[2] == {"row": 0}
    assert reads == [_task_key(tasks[0])]
    second = next(iterator)
    assert second[2] == {"row": 1}
    assert reads == [_task_key(tasks[0]), _task_key(tasks[1])]
    with pytest.raises(StopIteration):
        next(iterator)

    execution = {"candidate_rows": None, "small_metadata": {"bounded": True}}

    def rows_only():
        for _, _, row in _iter_stage_field_rows(
            store, "candidate", tasks, "candidate_rows"
        ):
            yield row

    temporary, output_ref = _write_streaming_json_temp(
        output_path,
        execution,
        {"candidate_rows": rows_only()},
    )
    try:
        parsed = json.loads(temporary.read_text(encoding="utf-8"))
    finally:
        temporary.unlink()
    assert output_ref["bytes"] > 0
    assert parsed["candidate_rows"] == [{"row": 0}, {"row": 1}]
    assert parsed["small_metadata"] == {"bounded": True}


def test_candidate_selection_metadata_drops_full_payload() -> None:
    row = {
        "sampling_arm": ARMS[0],
        "act": 1,
        "root_identity": "root",
        "source_complete_identity_sha256": "source",
        "exact_leaf_identity": "t084-hidden-state-"
        + hashlib.sha256(b"payload").hexdigest(),
        "exact_state_digest": "digest",
        "occurrence_key": "occurrence",
        "exact_hidden_state_payload": {
            "canonical_native_payload_json": "payload",
            "large_opaque_state": "not retained by selection",
        },
    }
    metadata = _candidate_metadata(row)
    assert "exact_hidden_state_payload" not in metadata
    assert (
        metadata["canonical_native_payload_sha256"]
        == hashlib.sha256(b"payload").hexdigest()
    )
