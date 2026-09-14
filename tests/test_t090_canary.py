"""Mock-only contracts for the bounded, non-authoritative T090 canary seam."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.t090_battle_student import (
    T090_TEACHER_CONFIG,
    build_t090_split_manifest,
    canonical_sha256,
    materialize_t090_targets,
    validate_t090_source_execution_ledger,
)
from sts_combat_rl.sim.t090_canary import (
    T090_CANARY_START_COUNT,
    T090CanaryError,
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
