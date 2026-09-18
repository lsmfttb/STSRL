"""T093 offline materialization and gate contract tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import pytest

from sts_combat_rl.commands.t093_internal_state_student import build_parser
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
)
from sts_combat_rl.sim.t093_internal_state_student import (
    T093Error,
    _canonicalize,
    _validate_t093_inputs,
    build_t093_training_config,
    conflict_limiting_gate,
    classify_t093,
    example_from_t092_occurrence,
    label_destruction_means,
    repeated_public_state_diagnostics,
    secondary_stratified_report,
    source_start_macro_accuracy,
    validate_t093_source_record,
    t093_checkpoint_identity,
)
from sts_combat_rl.sim.t090_battle_student import canonical_sha256


def _occurrence(*, source="source-a", group="A", split="train", node="node"):
    action = lambda kind, index: {
        "scope": "battle", "bits": index + 1, "kind": kind, "idx1": index,
        "idx2": 0, "idx3": 0, "label": f"{kind}-{index}",
    }
    return {
        "schema_id": "t092-internal-search-state-occurrence-v1", "schema_version": 1,
        "native_identity": dict(T092_NATIVE_IDENTITY),
        "frozen_teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_identity": source, "source_group": group, "split": split,
        "parent_root_decision_identity": f"{source}:root", "occurrence_identity": node,
        "tree_depth": 1, "expansion_ordinal": 1,
        "public_battle_projection": {
            "battle_player": {}, "battle_hand": [], "battle_discard_pile": [],
            "battle_exhaust_pile": [], "battle_monsters": [], "battle_potions": [],
            "battle_relics": [],
        },
        "input_state": "PLAYER_NORMAL",
        "searchable_actions": [
            {"action": action("card", 0), "visits": 4, "mean_value": 1.0},
            {"action": action("end", 1), "visits": 4, "mean_value": 0.0},
        ],
        "excluded_actions": [],
        "search_work": {"root_visits": 400, "native_simulator_steps": 1, "simulations_requested": 400},
        "telemetry_cost": {"telemetry_extraction_transition_count": 0, "collection_phase": "post_search_private_state_replay"},
    }


def _evidence():
    return {"schema_id": "t092-formal-telemetry-evidence-v1", "terminal_classification": "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH"}


def _manifest():
    return {"schema_id": "t092-formal-retention-manifest-v1", "formal_evidence": {"sha256": "ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a"}}


def _bound_inputs():
    groups = ("A", "B", "C")
    splits = ("train", "validation", "heldout")
    ledger = [
        {
            "source_identity": f"source-{index}",
            "source_group": groups[index % 3],
            "split": splits[index % 3],
            "canonical_position": index,
        }
        for index in range(413)
    ]
    artifacts = [
        {
            "path": f"/retained/source-{index}.json",
            "sha256": f"{index:064x}",
            "size_bytes": 1,
            "schema_id": "t092-paired-canary-arm-record-v2",
        }
        for index in range(413)
    ]
    shard = {"record_count": 413, "source_artifacts": artifacts}
    shard["source_artifacts_sha256"] = canonical_sha256(artifacts)
    return (
        {
            "schema_id": "t092-formal-retention-manifest-v1",
            "formal_evidence": {"sha256": "ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a"},
            "source_shards": [shard],
        },
        {
            "schema_id": "t092-formal-telemetry-evidence-v1",
            "terminal_classification": "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH",
            "source_worker_ledger": ledger,
            "internal_shard_manifest": [shard],
        },
    )


def test_t093_uses_public_tactical_encoding_without_native_bits():
    example = example_from_t092_occurrence(_occurrence())
    assert example is not None
    assert example.pairs == ((0, 1),)
    # Action encoding is derived through the public contract, rather than the
    # T092 `bits` field that may only identify a native action.
    assert all(value != 1.0 for value in example.action_features[0][-3:])
    assert all("bits" not in action for action in example.action_identities)
    assert all("private" not in key.lower() for action in example.action_identities for key in action)
    assert '"bits"' not in str(asdict(example))
    assert label_destruction_means(example) != example.teacher_means


def test_t093_cross_split_fingerprint_is_excluded_everywhere():
    other = deepcopy(_occurrence(split="heldout", source="source-b", group="A"))
    first = example_from_t092_occurrence(_occurrence())
    second = example_from_t092_occurrence(other)
    assert first is not None and second is not None
    retained, report = _canonicalize([first, second])
    assert retained == []
    assert len(report["cross_split_excluded"]) == 1


def test_t093_rejects_incomplete_or_aliased_retention_inventory():
    manifest, evidence = _bound_inputs()
    artifacts, ledger = _validate_t093_inputs(manifest, evidence)
    assert len(artifacts) == len(ledger) == 413
    incomplete = deepcopy(manifest)
    incomplete["source_shards"][0]["source_artifacts"].pop()
    incomplete["source_shards"][0]["record_count"] = 412
    incomplete["source_shards"][0]["source_artifacts_sha256"] = canonical_sha256(
        incomplete["source_shards"][0]["source_artifacts"]
    )
    with pytest.raises(T093Error, match="413"):
        _validate_t093_inputs(incomplete, evidence)
    aliased, evidence = _bound_inputs()
    aliased["source_shards"][0]["source_artifacts"][1]["path"] = aliased[
        "source_shards"
    ][0]["source_artifacts"][0]["path"]
    aliased["source_shards"][0]["source_artifacts_sha256"] = canonical_sha256(
        aliased["source_shards"][0]["source_artifacts"]
    )
    evidence["internal_shard_manifest"] = aliased["source_shards"]
    with pytest.raises(T093Error, match="aliased"):
        _validate_t093_inputs(aliased, evidence)


def test_t093_rejects_private_public_projection_before_encoding():
    occurrence = _occurrence()
    occurrence["public_battle_projection"]["hidden_rng"] = 7
    with pytest.raises(ValueError, match="forbidden private"):
        example_from_t092_occurrence(occurrence)


def test_t093_source_record_provenance_is_checked_beyond_hashes():
    expected = {"source_identity": "source-a", "source_group": "A", "split": "train", "canonical_position": 0, "terminal": {"battle_decision_count": 0}}
    record = {
        "schema_id": "t092-paired-canary-arm-record-v2", "schema_version": 1,
        "task_id": "T092", "arm": "ON", "implementation_head": "1e3dff2665d38dfd6acc786666c1889bc8327508",
        "native_identity": dict(T092_NATIVE_IDENTITY), "native_api": T092_NATIVE_API,
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG), **expected,
        "decision_records": [], "internal_occurrences": [],
    }
    artifact = {"schema_id": "t092-paired-canary-arm-record-v2"}
    validate_t093_source_record(record, artifact=artifact, expected_source=expected)
    record["arm"] = "OFF"
    with pytest.raises(T093Error, match="accepted T092"):
        validate_t093_source_record(record, artifact=artifact, expected_source=expected)


def test_t093_repeated_public_conflict_and_secondary_reports_are_diagnostic_only():
    first = _occurrence(source="source-a", node="one")
    second = deepcopy(first)
    second["source_identity"] = "source-b"
    second["parent_root_decision_identity"] = "source-b:root"
    second["occurrence_identity"] = "two"
    second["searchable_actions"][0]["mean_value"] = 0.0
    second["searchable_actions"][1]["mean_value"] = 1.0
    diagnostic = repeated_public_state_diagnostics([first, second])
    assert diagnostic["repeated_canonical_fingerprint_count"] == 1
    assert diagnostic["pair_sign_conflict_count"] == 1
    assert diagnostic["pair_sign_support_by_public_pair"]
    assert diagnostic["student_input_or_weight_use"] == "forbidden"
    example = example_from_t092_occurrence(first)
    assert example is not None
    report = secondary_stratified_report(
        [example], scores_by_arm={"true": {example.public_fingerprint: [1.0, 0.0]}}, split="train"
    )
    assert report["promotion_gate"] is False
    assert report["chance_reference"] == 0.5


def test_t093_checkpoint_identity_is_deterministic_and_external():
    example = example_from_t092_occurrence(_occurrence())
    assert example is not None
    config = build_t093_training_config([example])
    first = t093_checkpoint_identity({"weight": [1.0, 2.0]}, config=config, arm="true", seed=930093, selected_epoch=1)
    second = t093_checkpoint_identity({"weight": [1.0, 2.0]}, config=config, arm="true", seed=930093, selected_epoch=1)
    assert first == second
    assert first["external_checkpoint_required"] is True


def test_source_start_metric_uses_equal_starts_not_pair_count():
    first = example_from_t092_occurrence(_occurrence(source="a", group="A", node="one"))
    second_raw = _occurrence(source="b", group="A", node="two")
    second_raw["public_battle_projection"]["cur_hp"] = 2
    second = example_from_t092_occurrence(second_raw)
    assert first is not None and second is not None
    metric = source_start_macro_accuracy(
        [first, second],
        {first.public_fingerprint: [1.0, 0.0], second.public_fingerprint: [0.0, 1.0]},
    )
    assert metric["source_start_macro_accuracy"] == 0.5


def test_terminal_precedence_and_heldout_admission_are_frozen():
    assert classify_t093(information_valid=False, evidence_valid=False, diversity={"passed": False}, adequacy={"passed": False}) == "INTERNAL_STATE_STUDENT_INFORMATION_BOUNDARY_INVALID"
    assert classify_t093(information_valid=True, evidence_valid=True, diversity={"passed": True}, adequacy={"passed": False}) == "INTERNAL_STATE_STUDENT_MODEL_OR_TARGET_INADEQUATE"
    with pytest.raises(T093Error, match="held-out result"):
        classify_t093(information_valid=True, evidence_valid=True, diversity={"passed": True}, adequacy={"passed": True})


def test_conflict_classification_requires_validated_fixed_bootstrap_evidence():
    common = {"information_valid": True, "evidence_valid": True, "diversity": {"passed": True}, "adequacy": {"passed": True}, "heldout": {"passed": False}}
    assert classify_t093(**common) == "INTERNAL_STATE_STUDENT_GENERALIZATION_NOT_ESTABLISHED"
    rows = [
        {"source_identity": f"{group}-{index}", "source_group": group, "singleton_true": .9, "singleton_label": .1, "singleton_ablated": .1, "conflict_true": .1}
        for group in ("A", "B", "C") for index in range(15)
    ]
    evidence = {"adequacy": {"passed": True}, "paired_source_start_rows": rows,
                "canonical_fingerprint_counts": {"conflict_bearing": 500, "singleton_or_no_observed_conflict": 500},
                "contributing_start_counts": {"conflict_bearing": 15, "singleton_or_no_observed_conflict": 15}}
    assert conflict_limiting_gate(evidence)["passed"] is True
    assert classify_t093(**common, conflict_diagnostic=evidence) == "INTERNAL_STATE_STUDENT_REPEATED_PUBLIC_CONFLICT_LIMITING"
    evidence["canonical_fingerprint_counts"]["conflict_bearing"] = 499
    assert conflict_limiting_gate(evidence)["passed"] is False


def test_t093_cli_has_only_retained_file_inputs():
    actions = build_parser()._actions
    destinations = {action.dest for action in actions}
    assert {"retention_manifest", "formal_evidence", "output"} <= destinations
    assert "source_record" not in destinations
    assert "simulator" not in destinations and "search" not in destinations
