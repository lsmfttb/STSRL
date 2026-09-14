"""Mock-only contracts for the bounded, non-authoritative T090 canary seam."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from sts_combat_rl.sim import t090_canary
from sts_combat_rl.sim.t090_battle_student import (
    T090_NATIVE_IDENTITY,
    T090_TEACHER_CONFIG,
    build_t090_split_manifest,
    canonical_sha256,
    materialize_t090_targets,
    validate_t090_source_execution_ledger,
)
from sts_combat_rl.sim.t090_canary import (
    T090_CANARY_START_COUNT,
    T090CanaryError,
    T090NativeCanaryRunner,
    build_t090_canary_evidence_from_records,
    execute_t090_canary,
    select_t090_canary_sources,
    validate_t090_canary_evidence,
)


def _source_records() -> list[dict[str, object]]:
    counts = {"A": 93, "B": 192, "C": 128}
    return [
        {"source_identity": f"{group}-{index:03d}", "source_group": group}
        for group, count in counts.items()
        for index in range(count)
    ]


def _split_manifest() -> dict[str, object]:
    records = _source_records()
    identities = [str(record["source_identity"]) for record in records]
    return build_t090_split_manifest(
        records,
        t087_source_cohort_identity={
            "task_id": "T087",
            "record_count": 413,
            "source_group_counts": {"A": 93, "B": 192, "C": 128},
            "ordered_source_identities_sha256": canonical_sha256(identities),
            "source_identity_set_sha256": canonical_sha256(sorted(identities)),
            "artifact": {
                "path": "/retained/t087-cohort.json",
                "sha256": "a" * 64,
                "schema_id": "t087-formal-natural-evidence-v1",
                "size_bytes": 1,
            },
        },
    )


def _native_source_manifest() -> dict[str, object]:
    return {
        "schema_id": "sts-lightspeed-source-manifest-v1",
        "integration": {
            "repository_url": "https://github.com/lsmfttb/sts_lightspeed.git",
            "ref": "refs/heads/stsrl/main",
            "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
        },
    }


def _runner_record(source) -> dict[str, object]:
    actions = [{"action_id": "a"}, {"action_id": "b"}]
    return {
        "source_identity": source.source_identity,
        "source_group": source.source_group,
        "split": source.split,
        "canonical_position": source.canonical_position,
        "native_identity": T090_NATIVE_IDENTITY,
        "teacher_config": T090_TEACHER_CONFIG,
        "restore_public_legal_parity": True,
        "completed": True,
        "terminal_reached": True,
        "terminal_evidence": {"outcome": "PLAYER_VICTORY", "current_hp": 42},
        "worker": {
            "stage_worker_count": 2,
            "worker_index": source.canonical_position % 2,
            "shard_count": 2,
            "shard_index": source.canonical_position % 2,
        },
        "cost": {
            "wall_clock_time_s": 0.25,
            "root_decision_count": 1,
            "search_simulation_count": 400,
        },
        "teacher_rows": [
            {
                "source_identity": source.source_identity,
                "source_group": source.source_group,
                "decision_identity": f"{source.source_identity}-decision",
                "public_input": {
                    "schema_id": "public-tactical-v2",
                    "schema_version": 2,
                    "state_features": [1.0, 2.0],
                    "legal_action_features": [[0.0, 1.0], [1.0, 0.0]],
                    "legal_action_identities": actions,
                    "legal_action_kinds": ["card", "end_turn"],
                },
                "root_rows": [
                    {
                        "legal_action_identity": actions[0],
                        "visits": 3,
                        "mean_value": 1.0,
                    },
                    {
                        "legal_action_identity": actions[1],
                        "visits": 2,
                        "mean_value": -1.0,
                    },
                ],
            }
        ],
        "decision_provenance": [
            {
                "decision_identity": f"{source.source_identity}-decision",
                "selected_action_identity": actions[0],
                "selection_rule": "highest_mean",
                "native_search": {
                    "native_identity": T090_NATIVE_IDENTITY,
                    "native_api": "StepSimulator.battle_search_v2.v1",
                    "simulations": 400,
                    "include_potions": False,
                    "policy_prior_callback": None,
                    "leaf_value_callback": None,
                },
            }
        ],
    }


def test_t090_canary_selects_only_one_exact_canonical_twelve_start_window() -> None:
    manifest = _split_manifest()
    selected = select_t090_canary_sources(manifest, start_offset=7)
    assert len(selected) == T090_CANARY_START_COUNT
    assert [item.canonical_position for item in selected] == list(range(7, 19))
    with pytest.raises(T090CanaryError, match="exactly 12"):
        select_t090_canary_sources(manifest, start_offset=0, start_count=11)
    with pytest.raises(T090CanaryError, match="outside"):
        select_t090_canary_sources(manifest, start_offset=402)


def test_t090_canary_evidence_binds_provenance_worker_cost_and_formal_boundary() -> (
    None
):
    manifest = _split_manifest()
    native = _native_source_manifest()
    evidence = execute_t090_canary(
        split_manifest=manifest,
        native_source_manifest=native,
        start_offset=0,
        runner=_runner_record,
    )
    assert evidence["training_eligible"] is False
    assert evidence["formal_execution_authorized"] is False
    assert evidence["selected_start_count"] == 12
    assert evidence["source_execution_summary"]["completed_start_count"] == 12
    entry = evidence["source_execution_ledger"]["entries"][0]
    assert entry["cost"]["search_simulation_count"] == 400
    assert entry["worker"]["stage_worker_count"] == 2
    validate_t090_canary_evidence(
        evidence,
        split_manifest=manifest,
        native_source_manifest=native,
    )
    with pytest.raises(ValueError, match="unsupported|413"):
        validate_t090_source_execution_ledger(
            evidence["source_execution_ledger"], split_manifest=manifest
        )
    with pytest.raises(ValueError, match="unsupported|413"):
        materialize_t090_targets(
            evidence["teacher_rows"],
            manifest,
            native_source_manifest=native,
            source_execution_ledger=evidence["source_execution_ledger"],
        )


def test_t090_canary_rejects_missing_or_duplicate_selected_source_records() -> None:
    manifest = _split_manifest()
    native = _native_source_manifest()
    selected = select_t090_canary_sources(manifest, start_offset=0)
    records = [_runner_record(source) for source in selected]
    duplicate = [*records]
    duplicate[-1] = deepcopy(duplicate[0])
    with pytest.raises(T090CanaryError, match="duplicate|differ from selected"):
        build_t090_canary_evidence_from_records(
            split_manifest=manifest,
            native_source_manifest=native,
            start_offset=0,
            execution_records=duplicate,
        )
    evidence = execute_t090_canary(
        split_manifest=manifest,
        native_source_manifest=native,
        start_offset=0,
        runner=_runner_record,
    )
    missing = deepcopy(evidence)
    missing["source_execution_ledger"]["entries"].pop()
    missing["source_execution_ledger"]["entries_sha256"] = canonical_sha256(
        missing["source_execution_ledger"]["entries"]
    )
    with pytest.raises(T090CanaryError, match="not 12 starts"):
        validate_t090_canary_evidence(
            missing,
            split_manifest=manifest,
            native_source_manifest=native,
        )


def test_t090_canary_rejects_zero_or_unbound_root_decision_counts() -> None:
    manifest = _split_manifest()
    native = _native_source_manifest()

    def zero_root_runner(source):
        record = _runner_record(source)
        record["teacher_rows"] = []
        record["decision_provenance"] = []
        record["cost"] = {
            "wall_clock_time_s": 0.25,
            "root_decision_count": 0,
            "search_simulation_count": 0,
        }
        return record

    with pytest.raises(T090CanaryError, match="requires a root decision"):
        execute_t090_canary(
            split_manifest=manifest,
            native_source_manifest=native,
            start_offset=0,
            runner=zero_root_runner,
        )

    def mismatched_root_runner(source):
        record = _runner_record(source)
        record["cost"] = {
            "wall_clock_time_s": 0.25,
            "root_decision_count": 2,
            "search_simulation_count": 800,
        }
        return record

    with pytest.raises(T090CanaryError, match="does not match captured teacher rows"):
        execute_t090_canary(
            split_manifest=manifest,
            native_source_manifest=native,
            start_offset=0,
            runner=mismatched_root_runner,
        )

    def non_highest_mean_runner(source):
        record = _runner_record(source)
        record["decision_provenance"][0]["selected_action_identity"] = {
            "action_id": "b"
        }
        return record

    with pytest.raises(T090CanaryError, match="not highest_mean"):
        execute_t090_canary(
            split_manifest=manifest,
            native_source_manifest=native,
            start_offset=0,
            runner=non_highest_mean_runner,
        )

    def noncanonical_tie_runner(source):
        record = _runner_record(source)
        record["teacher_rows"][0]["root_rows"][1]["visits"] = 3
        record["teacher_rows"][0]["root_rows"][1]["mean_value"] = 1.0
        record["decision_provenance"][0]["selected_action_identity"] = {
            "action_id": "b"
        }
        return record

    with pytest.raises(T090CanaryError, match="not highest_mean"):
        execute_t090_canary(
            split_manifest=manifest,
            native_source_manifest=native,
            start_offset=0,
            runner=noncanonical_tie_runner,
        )


def test_t090_native_canary_runner_uses_injected_t085_and_controlled_run_seams(
    monkeypatch,
) -> None:
    manifest = _split_manifest()
    source = select_t090_canary_sources(manifest, start_offset=0)[0]
    actions = [{"action_id": "a"}, {"action_id": "b"}]
    step = SimpleNamespace(
        battle_active=True,
        feature_schema_id="public-tactical-v2",
        snapshot_features=[1.0, 2.0],
        legal_action_features=[[0.0, 1.0], [1.0, 0.0]],
        legal_action_identities=actions,
        legal_action_kinds=["card", "end_turn"],
        step_index=3,
        next_battle_outcome="PLAYER_VICTORY",
        next_player_hp=40.0,
        decision_metadata={
            "oracle_search_decision_reports": [
                {
                    "native_api": "StepSimulator.battle_search_v2.v1",
                    "simulations_requested": 400,
                    "include_potions": False,
                    "selection_rule": "highest_mean",
                    "selected_action_identity": actions[0],
                    "root_actions": [
                        {
                            "legal_action_index": 0,
                            "action_identity": actions[0],
                            "visits": 3,
                            "mean_value": 1.0,
                        },
                        {
                            "legal_action_index": 1,
                            "action_identity": actions[1],
                            "visits": 2,
                            "mean_value": -1.0,
                        },
                    ],
                }
            ]
        },
    )
    controlled = SimpleNamespace(
        terminal=True,
        problems=[],
        steps=[step],
        final_raw={"completed_battle_outcome": "PLAYER_VICTORY"},
    )

    class FakeAdapter:
        def prime_restored_snapshot(self, snapshot) -> None:
            assert snapshot is restored

        native_terminal_labels = (SimpleNamespace(terminal_outcome="PLAYER_VICTORY"),)

    restored = SimpleNamespace(raw={})
    closed: list[str] = []

    class BaseAdapter:
        def legal_actions(self, snapshot):
            return actions

        def close(self) -> None:
            closed.append("closed")

    base_adapter = BaseAdapter()
    monkeypatch.setattr(
        t090_canary,
        "_validate_t085_native_source_manifest",
        lambda *args, **kwargs: dict(T090_NATIVE_IDENTITY),
    )
    monkeypatch.setattr(
        t090_canary,
        "restore_t085_canonical_record",
        lambda *args, **kwargs: (restored, "native_checkpoint"),
    )
    monkeypatch.setattr(t090_canary, "read_native_public_projection", lambda *args: {})
    monkeypatch.setattr(
        t090_canary,
        "build_public_run_context",
        lambda *args, **kwargs: {"history": []},
    )
    monkeypatch.setattr(
        t090_canary,
        "T085NativeTerminalSearchAdapter",
        lambda *args, **kwargs: FakeAdapter(),
    )
    monkeypatch.setattr(
        t090_canary, "T085UnguidedBattleSearchV2Controller", lambda **kwargs: object()
    )
    monkeypatch.setattr(
        t090_canary, "execute_controlled_run", lambda *args, **kwargs: controlled
    )
    runner = T090NativeCanaryRunner(
        adapter_factory=lambda: base_adapter,
        source_records={
            source.source_identity: SimpleNamespace(selection_identity="record")
        },
        canonical_records={
            source.source_identity: SimpleNamespace(public_run_context={"history": []})
        },
        worker={
            "stage_worker_count": 1,
            "worker_index": 0,
            "shard_count": 1,
            "shard_index": 0,
        },
    )
    record = runner(source)
    assert record["cost"]["root_decision_count"] == 1
    assert record["cost"]["search_simulation_count"] == 400
    assert record["decision_provenance"][0]["selected_action_identity"] == actions[0]
    assert (
        record["decision_provenance"][0]["native_search"]["native_identity"]
        == T090_NATIVE_IDENTITY
    )
    assert closed == ["closed"]

    def failing_restore(*args, **kwargs):
        raise RuntimeError("restore failure")

    monkeypatch.setattr(t090_canary, "restore_t085_canonical_record", failing_restore)
    with pytest.raises(RuntimeError, match="restore failure"):
        runner(source)
    assert closed == ["closed", "closed"]
