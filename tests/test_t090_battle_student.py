"""Focused offline contracts for T090 Battle-student distillation plumbing."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.t090_battle_student import (
    T090DecisionExample,
    build_t090_heldout_report,
    build_t090_split_manifest,
    build_t090_training_config,
    canonical_sha256,
    deduplicate_t090_examples,
    load_t090_checkpoint,
    materialize_t090_targets,
    public_decision_fingerprint,
    save_t090_checkpoint,
    select_t090_validation_checkpoint,
    shuffled_teacher_means,
    t090_coverage_report,
    train_t090_scorer,
    validate_t090_heldout_report,
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


def _cohort_identity(records: list[dict[str, object]]) -> dict[str, object]:
    identities = [str(item["source_identity"]) for item in records]
    return {
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
    }


def _native_source_manifest() -> dict[str, object]:
    return {
        "schema_id": "sts-lightspeed-source-manifest-v1",
        "integration": {
            "repository_url": "https://github.com/lsmfttb/sts_lightspeed.git",
            "ref": "refs/heads/stsrl/main",
            "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
        },
    }


def _selection_provenance(role: str, seed: int) -> dict[str, object]:
    return {
        "selection_split": "validation",
        "selection_metric": "mean_teacher_regret",
        "selected_seed": seed,
        "role": role,
        "candidate_checkpoint_sha256_by_seed": {
            "900091": "1" * 64,
            "900092": "2" * 64,
            "900093": "3" * 64,
        },
        "validation_summaries_sha256": "4" * 64,
    }


def _split_manifest() -> dict[str, object]:
    records = _source_records()
    return build_t090_split_manifest(
        records, t087_source_cohort_identity=_cohort_identity(records)
    )


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
    manifest = _split_manifest()
    entries = validate_t090_split_manifest(manifest)
    assert len(entries) == 413
    assert manifest["entries_sha256"]
    assert _split_manifest() == manifest
    assert {(entry.source_group, entry.split) for entry in entries} == {
        (group, split)
        for group in ("A", "B", "C")
        for split in ("train", "validation", "heldout")
    }


def test_target_materialization_rejects_non_public_or_unmapped_teacher_rows() -> None:
    manifest = _split_manifest()
    entries = validate_t090_split_manifest(manifest)
    chosen = [
        next(item for item in entries if item.split == split)
        for split in ("train", "validation", "heldout")
    ]
    rows = [
        _teacher_row(item.source_identity, item.source_group, float(index))
        for index, item in enumerate(chosen)
    ]
    native = _native_source_manifest()
    result = materialize_t090_targets(rows, manifest, native_source_manifest=native)
    assert result["schema_id"] == "t090-search-v2-action-utility-targets-v1"
    assert len(result["examples"]) == 3
    assert (
        len(
            validate_t090_target_table(
                result,
                expected_split_manifest=manifest,
                expected_native_source_manifest=native,
            )
        )
        == 3
    )
    mismatched_split = deepcopy(result)
    mismatched_split["split_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="supplied split manifest"):
        validate_t090_target_table(
            mismatched_split,
            expected_split_manifest=manifest,
            expected_native_source_manifest=native,
        )

    hidden = _teacher_row(chosen[0].source_identity, chosen[0].source_group, 10.0)
    hidden["public_input"]["rng_state"] = "forbidden"  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown fields|forbidden non-public"):
        materialize_t090_targets([hidden], manifest, native_source_manifest=native)

    for forbidden_key in ("hidden_state", "hiddenState", "simulator_state"):
        non_public = _teacher_row(
            chosen[0].source_identity, chosen[0].source_group, 10.0
        )
        non_public["public_input"][forbidden_key] = "forbidden"  # type: ignore[index]
        with pytest.raises(ValueError, match="unknown fields|forbidden non-public"):
            materialize_t090_targets(
                [non_public], manifest, native_source_manifest=native
            )

    unmapped = _teacher_row(chosen[0].source_identity, chosen[0].source_group, 10.0)
    unmapped["root_rows"][1]["legal_action_identity"] = {"action_id": "other"}  # type: ignore[index]
    with pytest.raises(ValueError, match="one-to-one"):
        materialize_t090_targets([unmapped], manifest, native_source_manifest=native)


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


def test_checkpoint_and_selection_bind_target_config_and_exact_seed_set(
    tmp_path,
) -> None:
    pytest.importorskip("torch")
    manifest = _split_manifest()
    native = _native_source_manifest()
    entries = validate_t090_split_manifest(manifest)
    chosen = [
        next(item for item in entries if item.split == "train"),
        next(item for item in entries if item.split == "validation"),
        *(
            next(
                item
                for item in entries
                if item.split == "heldout" and item.source_group == group
            )
            for group in ("A", "B", "C")
        ),
    ]
    target = materialize_t090_targets(
        [
            _teacher_row(entry.source_identity, entry.source_group, float(index))
            for index, entry in enumerate(chosen)
        ],
        manifest,
        native_source_manifest=native,
    )
    examples = validate_t090_target_table(
        target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
    )
    scorer, report = train_t090_scorer(examples, seed=900091)
    assert scorer.config.normalization == "identity_public_features_v1"
    selection = _selection_provenance("student", 900091)
    identity = save_t090_checkpoint(
        scorer,
        tmp_path / "student.pt",
        role="student",
        seed=900091,
        target_table=target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        selection_provenance=selection,
    )
    loaded = load_t090_checkpoint(
        identity["path"],
        expected_identity=identity,
        expected_role="student",
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        expected_target_table=target,
    )
    assert loaded.config == scorer.config
    duplicate_results = [
        (scorer, {**report, "seed": 900091}),
        (scorer, {**report, "seed": 900091}),
        (scorer, {**report, "seed": 900093}),
    ]
    with pytest.raises(ValueError, match="exactly once"):
        select_t090_validation_checkpoint(duplicate_results)


def test_heldout_validator_recomputes_secondary_and_requires_boundaries(
    tmp_path,
) -> None:
    pytest.importorskip("torch")
    manifest = _split_manifest()
    native = _native_source_manifest()
    entries = validate_t090_split_manifest(manifest)
    chosen = [
        next(item for item in entries if item.split == "train"),
        next(item for item in entries if item.split == "validation"),
        *(
            next(
                item
                for item in entries
                if item.split == "heldout" and item.source_group == group
            )
            for group in ("A", "B", "C")
        ),
    ]
    target = materialize_t090_targets(
        [
            _teacher_row(entry.source_identity, entry.source_group, float(index))
            for index, entry in enumerate(chosen)
        ],
        manifest,
        native_source_manifest=native,
    )
    examples = validate_t090_target_table(
        target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
    )
    student, _ = train_t090_scorer(examples, seed=900091)
    control, _ = train_t090_scorer(examples, seed=900092, shuffled=True)
    student_identity = save_t090_checkpoint(
        student,
        tmp_path / "student.pt",
        role="student",
        seed=900091,
        target_table=target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        selection_provenance=_selection_provenance("student", 900091),
    )
    control_identity = save_t090_checkpoint(
        control,
        tmp_path / "control.pt",
        role="shuffled_target_control",
        seed=900092,
        target_table=target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        selection_provenance=_selection_provenance("shuffled_target_control", 900092),
    )
    report = build_t090_heldout_report(
        examples,
        student,
        control,
        target_table=target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        student_checkpoint=student_identity,
        control_checkpoint=control_identity,
    )
    validate_t090_heldout_report(
        report,
        expected_target_table=target,
        expected_split_manifest=manifest,
        expected_native_source_manifest=native,
        expected_student_checkpoint=student_identity,
        expected_control_checkpoint=control_identity,
    )
    tampered = deepcopy(report)
    tampered["information_boundary_valid"] = False
    with pytest.raises(ValueError, match="information or split"):
        validate_t090_heldout_report(
            tampered,
            expected_target_table=target,
            expected_split_manifest=manifest,
            expected_native_source_manifest=native,
            expected_student_checkpoint=student_identity,
            expected_control_checkpoint=control_identity,
        )
