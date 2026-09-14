"""Focused offline contracts for T090 Battle-student distillation plumbing."""

from __future__ import annotations

import pytest

from sts_combat_rl.sim.t090_battle_student import (
    T090DecisionExample,
    build_t090_split_manifest,
    build_t090_training_config,
    deduplicate_t090_examples,
    materialize_t090_targets,
    public_decision_fingerprint,
    shuffled_teacher_means,
    t090_coverage_report,
    train_t090_scorer,
    validate_t090_split_manifest,
    validate_t090_target_table,
)


def _source_records() -> list[dict[str, object]]:
    counts = {"A": 93, "B": 192, "C": 128}
    return [
        {"source_identity": f"{group}-{index:03d}", "source_group": group}
        for group, count in counts.items()
        for index in range(count)
    ]


def _teacher_row(
    source_identity: str, source_group: str, state: float
) -> dict[str, object]:
    actions = [{"action_id": "a"}, {"action_id": "b"}]
    return {
        "source_identity": source_identity,
        "source_group": source_group,
        "decision_identity": f"{source_identity}-decision",
        "public_input": {
            "schema_id": "public-tactical-v2",
            "schema_version": 2,
            "state_features": [state, 1.0],
            "legal_action_features": [[0.0, 1.0], [1.0, 0.0]],
            "legal_action_identities": actions,
            "legal_action_kinds": ["card", "end_turn"],
        },
        "root_rows": [
            {"legal_action_identity": actions[0], "visits": 4, "mean_value": 1.0},
            {"legal_action_identity": actions[1], "visits": 4, "mean_value": -1.0},
        ],
    }


def test_split_manifest_is_exact_and_group_local() -> None:
    manifest = build_t090_split_manifest(_source_records())
    entries = validate_t090_split_manifest(manifest)
    assert len(entries) == 413
    assert manifest["entries_sha256"]
    assert build_t090_split_manifest(_source_records()) == manifest
    assert {(entry.source_group, entry.split) for entry in entries} == {
        (group, split)
        for group in ("A", "B", "C")
        for split in ("train", "validation", "heldout")
    }


def test_target_materialization_rejects_non_public_or_unmapped_teacher_rows() -> None:
    manifest = build_t090_split_manifest(_source_records())
    entries = validate_t090_split_manifest(manifest)
    chosen = [
        next(item for item in entries if item.split == split)
        for split in ("train", "validation", "heldout")
    ]
    rows = [
        _teacher_row(item.source_identity, item.source_group, float(index))
        for index, item in enumerate(chosen)
    ]
    result = materialize_t090_targets(rows, manifest)
    assert result["schema_id"] == "t090-search-v2-action-utility-targets-v1"
    assert len(result["examples"]) == 3
    assert len(validate_t090_target_table(result)) == 3

    hidden = _teacher_row(chosen[0].source_identity, chosen[0].source_group, 10.0)
    hidden["public_input"]["rng_state"] = "forbidden"  # type: ignore[index]
    with pytest.raises(ValueError, match="forbidden non-public"):
        materialize_t090_targets([hidden], manifest)

    unmapped = _teacher_row(chosen[0].source_identity, chosen[0].source_group, 10.0)
    unmapped["root_rows"][1]["legal_action_identity"] = {"action_id": "other"}  # type: ignore[index]
    with pytest.raises(ValueError, match="one-to-one"):
        materialize_t090_targets([unmapped], manifest)


def _example(split: str, decision: str, state: float) -> T090DecisionExample:
    identities = ({"action_id": "a"}, {"action_id": "b"})
    features = (state, 1.0)
    return T090DecisionExample(
        source_identity=f"source-{decision}",
        source_group="A" if split == "train" else "B" if split == "validation" else "C",
        split=split,
        decision_identity=decision,
        public_state_features=features,
        legal_action_features=((0.0, 1.0), (1.0, 0.0)),
        legal_action_identities=identities,
        legal_action_kinds=("card", "end_turn"),
        teacher_means=(1.0, -1.0),
        public_fingerprint=public_decision_fingerprint(features, identities),
    )


def test_cross_split_fingerprint_is_excluded_and_shuffle_is_deterministic() -> None:
    train = _example("train", "train", 0.0)
    heldout = _example("heldout", "heldout", 0.0)
    retained, report = deduplicate_t090_examples((train, heldout))
    assert retained == ()
    assert report["cross_split_excluded"][0]["splits"] == ["heldout", "train"]
    assert shuffled_teacher_means(train) == shuffled_teacher_means(train)


def test_config_and_small_public_only_training_surface() -> None:
    pytest.importorskip("torch")
    examples = tuple(
        _example(
            split,
            f"{split}-{index}",
            float(index + {"train": 0, "validation": 10, "heldout": 20}[split]),
        )
        for split, count in (("train", 3), ("validation", 2), ("heldout", 2))
        for index in range(count)
    )
    config = build_t090_training_config(examples)
    assert config.hidden_width == 256
    assert config.hidden_layers == 2
    scorer, report = train_t090_scorer(examples, seed=900091)
    assert report["validation"]["mean_teacher_regret"] >= 0.0  # type: ignore[index]
    assert scorer.provenance_config["search_calls_at_inference"] == 0
    coverage = t090_coverage_report(examples)
    assert coverage["passed"] is False
    assert (
        coverage["failure_classification"]
        == "BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT"
    )
