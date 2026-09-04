from __future__ import annotations

import pytest

from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_ARTIFACT_ROOT,
    T085BattleStartRecord,
    T085OutcomeRecord,
    T085SourceRunRecord,
    audit_cohort_b_source_overlap,
    bootstrap_mean_percentile,
    build_t085_paired_evaluation_report,
    build_t085_retention_manifest,
    build_t085_terminal_report,
    classify_t085_terminal,
    run_t085_paired_evaluation,
    select_cohort_b,
    select_cohort_c,
    select_search_400_subset,
    validate_cohort_a,
    validate_t085_restore_parity,
    validate_t085_retention_manifest,
    validate_t085_source_generation_contract,
    write_t085_json_artifact,
)


def _b_sources() -> list[T085SourceRunRecord]:
    return [
        T085SourceRunRecord(
            source_run_seed=seed,
            source_run_identity=f"b-run-{seed}",
            complete_source_identity=f"b-source-{seed}",
        )
        for seed in range(851001, 852025)
    ]


def _b_starts() -> list[T085BattleStartRecord]:
    return [
        T085BattleStartRecord(
            source_run_seed=seed,
            source_run_identity=f"b-run-{seed}",
            complete_source_identity=f"b-source-{seed}",
            battle_identity=f"b-battle-{seed}",
            act=1 if seed < 851097 else 2,
            room_type="MONSTER" if seed % 2 else "ELITE",
        )
        for seed in range(851001, 851193)
    ]


def _c_sources() -> list[T085SourceRunRecord]:
    return [
        T085SourceRunRecord(
            source_run_seed=seed,
            source_run_identity=f"c-run-{seed}",
            complete_source_identity=f"c-source-{seed}",
        )
        for seed in range(850001, 850129)
    ]


def _c_starts() -> list[T085BattleStartRecord]:
    return [
        T085BattleStartRecord(
            source_run_seed=seed,
            source_run_identity=f"c-run-{seed}",
            complete_source_identity=f"c-source-{seed}",
            battle_identity=f"c-battle-{seed}",
            act=1 if seed < 850065 else 2,
            room_type="MONSTER",
        )
        for seed in range(850001, 850129)
    ]


def test_cohort_selection_is_exact_and_outcome_blind() -> None:
    selected_b, summary_b = select_cohort_b(_b_sources(), _b_starts())
    assert len(selected_b) == 192
    assert summary_b["selected_act_counts"] == {"1": 96, "2+": 96}
    selected_c, summary_c = select_cohort_c(_c_sources(), _c_starts())
    assert len(selected_c) == 128
    assert summary_c["one_record_per_source_run"] is True
    selected_400, summary_400 = select_search_400_subset(selected_b)
    assert len(selected_400) == 48
    assert summary_400["selected_act_counts"] == {"1": 24, "2+": 24}
    overlap = audit_cohort_b_source_overlap(
        _b_sources(),
        t084_complete_source_identities={"old-t084-source"},
        t052_complete_source_identities={"old-t052-source"},
    )
    assert overlap["zero_overlap"] is True
    with pytest.raises(ValueError, match="forbidden complete-source overlap"):
        audit_cohort_b_source_overlap(
            selected_b,
            t084_complete_source_identities={selected_b[0].complete_source_identity},
            t052_complete_source_identities=set(),
        )
    parity = validate_t085_restore_parity(
        selected_400,
        {
            record.selection_identity: {
                "restore_ok": True,
                "public_context_match": True,
            }
            for record in selected_400
        },
    )
    assert parity["passed"] is True
    with pytest.raises(ValueError, match="public-context parity"):
        bad_parity = {
            record.selection_identity: {
                "restore_ok": True,
                "public_context_match": index != 0,
            }
            for index, record in enumerate(selected_400)
        }
        validate_t085_restore_parity(selected_400, bad_parity)


def test_cohort_selection_fails_closed_without_fixed_quota() -> None:
    starts = _b_starts()[:-1]
    with pytest.raises(ValueError, match="quota"):
        select_cohort_b(_b_sources(), starts)
    with pytest.raises(ValueError, match="accepted T052"):
        validate_cohort_a([], artifact_sha256="0" * 64)


def test_source_generation_contract_is_frozen_for_b_and_c() -> None:
    common = {
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
    }
    b = {
        **common,
        "source_run_count": 1024,
        "source_run_seeds": list(range(851001, 852025)),
        "battle_controller": "oracle_search",
        "battle_simulations": 20,
        "root_selection": "highest_mean",
        "assistance_level": "assist_hp75_potion",
        "assistance_policy_seed": 42042,
        "t042_scale_manifest_sha256": "25efae30dc9a61c8b97cb09e1844b93bffe693bde51c0f494f0f65203a1d327",
    }
    assert validate_t085_source_generation_contract(b, cohort="B")["validated"] is True
    c = {
        **common,
        "source_run_count": 128,
        "source_run_seeds": list(range(850001, 850129)),
        "battle_controller": "unguided_search_v2",
        "battle_simulations": 100,
        "root_selection": "highest_mean",
        "assistance_level": "assist_0",
        "assistance_policy_seed": None,
    }
    assert validate_t085_source_generation_contract(c, cohort="C")["validated"] is True
    b["non_combat_policy_seed"] = 851001
    with pytest.raises(ValueError, match="non_combat_policy_seed"):
        validate_t085_source_generation_contract(b, cohort="B")


def test_bootstrap_is_fixed_to_battle_records_and_seed() -> None:
    first = bootstrap_mean_percentile([1.0, 2.0, 3.0])
    second = bootstrap_mean_percentile([1.0, 2.0, 3.0])
    assert first == second
    assert first["sampling_unit"] == "battle_record"
    assert first["seed"] == 85085
    assert first["resample_count"] == 10_000
    with pytest.raises(ValueError, match="exactly 10000"):
        bootstrap_mean_percentile([1.0], resample_count=999)


def _row(
    cohort: str, identity: str, arm: str, survived: bool, utility: float
) -> T085OutcomeRecord:
    return T085OutcomeRecord(
        cohort=cohort,
        record_identity=identity,
        arm=arm,
        battle_survived=survived,
        terminal_native_utility=utility,
        source_run_identity=identity,
    )


def _evaluation_rows() -> list[T085OutcomeRecord]:
    rows: list[T085OutcomeRecord] = []
    for cohort, count in (("A", 2), ("B", 2), ("C", 2)):
        for index in range(count):
            identity = f"{cohort}-{index}"
            for arm in (
                "baseline",
                "old_value_64001",
                "corrected_value_85001",
                "old_value_64002",
                "corrected_value_85002",
            ):
                rows.append(
                    _row(cohort, identity, arm, arm.startswith("corrected"), 1.0)
                )
            if cohort == "B":
                for arm in (
                    "prior_only_64001",
                    "prior_corrected_85001",
                    "prior_only_64002",
                    "prior_corrected_85002",
                ):
                    rows.append(
                        _row(
                            cohort,
                            identity,
                            arm,
                            arm.startswith("prior_corrected"),
                            1.0,
                        )
                    )
    for index in range(2):
        identity = f"B400-{index}"
        for arm in (
            "baseline@400",
            "corrected_value_85001@400",
            "corrected_value_85002@400",
        ):
            rows.append(_row("B@400", identity, arm, arm != "baseline@400", 1.0))
    return rows


def test_paired_report_contains_primary_secondary_guard_and_bootstrap() -> None:
    report = build_t085_paired_evaluation_report(
        _evaluation_rows(), cohort_b_record_count=2, cohort_c_record_count=2
    )
    assert report["schema_id"] == "t085-paired-evaluation-report-v1"
    assert set(report["primary"]) == {"A", "B", "C"}
    assert report["cohort_b"]["delta_base"]["resample_count"] == 10_000
    assert set(report["secondary"]) == {
        "prior_corrected_85001_vs_prior_only",
        "prior_corrected_85002_vs_prior_only",
    }
    assert set(report["search_400"]) == {
        "corrected_85001_vs_baseline",
        "corrected_85002_vs_baseline",
    }


def test_paired_report_rejects_unknown_duplicate_and_missing_rows() -> None:
    rows = _evaluation_rows()
    unknown = list(rows)
    unknown.append(_row("A", "A-0", "unknown", True, 1.0))
    with pytest.raises(ValueError, match="arm matrix mismatch"):
        build_t085_paired_evaluation_report(
            unknown, cohort_b_record_count=2, cohort_c_record_count=2
        )
    duplicate = list(rows) + [rows[0]]
    with pytest.raises(ValueError, match="duplicate"):
        build_t085_paired_evaluation_report(
            duplicate, cohort_b_record_count=2, cohort_c_record_count=2
        )
    missing = [row for row in rows if not (row.cohort == "C" and row.arm == "baseline")]
    with pytest.raises(ValueError, match="arm matrix mismatch|incomplete"):
        build_t085_paired_evaluation_report(
            missing, cohort_b_record_count=2, cohort_c_record_count=2
        )


def test_executable_arm_workflow_binds_every_requested_arm_and_budget() -> None:
    records = {
        cohort: (
            T085BattleStartRecord(
                source_run_seed=1,
                source_run_identity=f"{cohort}-run",
                complete_source_identity=f"{cohort}-source",
                battle_identity=f"{cohort}-battle",
                act=1,
                room_type="MONSTER",
            ),
        )
        for cohort in ("A", "B", "C", "B@400")
    }
    calls: list[tuple[str, int]] = []
    cohort_by_identity = {
        record.selection_identity: cohort
        for cohort, cohort_records in records.items()
        for record in cohort_records
    }

    def evaluate(record, arm, budget):
        calls.append((arm, budget))
        return {
            "cohort": cohort_by_identity[record.selection_identity],
            "record_identity": record.selection_identity,
            "arm": arm,
            "battle_survived": True,
            "terminal_native_utility": 1.0,
        }

    report = run_t085_paired_evaluation(records, evaluate_record=evaluate)
    assert report["schema_id"] == "t085-paired-evaluation-report-v1"
    assert calls.count(("baseline", 100)) == 3
    assert calls.count(("baseline@400", 400)) == 1
    assert calls.count(("prior_corrected_85001", 100)) == 1


def _gate_evidence(tmp_path) -> dict[str, object]:
    target = T085_ARTIFACT_ROOT / f".pytest-t085-gates-{tmp_path.name}.json"
    artifact = write_t085_json_artifact(
        target,
        {"evidence": True},
        schema_id="t085-terminal-classification-report-v1",
    )
    manifest = build_t085_retention_manifest(
        inputs={},
        outputs={
            role: artifact
            for role in (
                "input_eligibility_manifest",
                "repaired_checkpoint_85001",
                "repaired_checkpoint_85002",
                "training_report_85001",
                "training_report_85002",
                "cohort_a_manifest",
                "cohort_b_source_manifest",
                "cohort_b_selected_manifest",
                "cohort_b_overlap_audit",
                "cohort_c_source_manifest",
                "cohort_c_selected_manifest",
                "search_400_manifest",
                "paired_evaluation_report",
                "terminal_classification_report",
            )
        },
        stages=[],
        code_identity={"commit": "test"},
        native_identity={"commit": "test"},
        terminal_classification="INCOMPLETE",
        regeneration_commands=["test"],
        retention_reason="classification test",
        deletion_conditions=["test complete"],
    )
    return {
        name: {"passed": True, "evidence_id": f"test-{name}"}
        for name in (
            "artifact",
            "policy_invariance",
            "checkpoint",
            "source_cohort",
            "restore_parity",
            "execution",
            "retention",
        )
    } | {"retention_manifest": manifest, "_artifact_path": target}


def test_terminal_classification_covers_every_published_class(tmp_path) -> None:
    gates = {
        name: True
        for name in (
            "artifact",
            "policy_invariance",
            "checkpoint",
            "source_cohort",
            "restore_parity",
            "execution",
            "retention",
        )
    }
    evidence = _gate_evidence(tmp_path)
    try:
        established_rows = _evaluation_rows()
        for row_index, row in enumerate(established_rows):
            if row.arm.startswith("corrected"):
                established_rows[row_index] = T085OutcomeRecord(
                    **{
                        **row.__dict__,
                        "battle_survived": True,
                        "terminal_native_utility": 2.0,
                    }
                )
            elif row.arm.startswith("baseline") or row.arm.startswith("old_value"):
                established_rows[row_index] = T085OutcomeRecord(
                    **{
                        **row.__dict__,
                        "battle_survived": False,
                        "terminal_native_utility": 0.0,
                    }
                )
        established = build_t085_paired_evaluation_report(
            established_rows, cohort_b_record_count=2, cohort_c_record_count=2
        )
        assert (
            classify_t085_terminal(
                established,
                gates=gates,
                cohort_b_supported=True,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED"
        )
        harmful_rows = _evaluation_rows()
        for row_index, row in enumerate(harmful_rows):
            if row.arm.startswith("corrected"):
                harmful_rows[row_index] = T085OutcomeRecord(
                    **{
                        **row.__dict__,
                        "battle_survived": False,
                        "terminal_native_utility": 0.0,
                    }
                )
            elif row.arm.startswith("baseline") or row.arm.startswith("old_value"):
                harmful_rows[row_index] = T085OutcomeRecord(
                    **{
                        **row.__dict__,
                        "battle_survived": True,
                        "terminal_native_utility": 2.0,
                    }
                )
        harmful = build_t085_paired_evaluation_report(
            harmful_rows, cohort_b_record_count=2, cohort_c_record_count=2
        )
        assert (
            classify_t085_terminal(
                harmful,
                gates=gates,
                cohort_b_supported=True,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "CORRECTED_VALUE_SEARCH_HARM_CONFIRMED"
        )
        neutral = build_t085_paired_evaluation_report(
            _evaluation_rows(), cohort_b_record_count=2, cohort_c_record_count=2
        )
        assert (
            classify_t085_terminal(
                neutral,
                gates=gates,
                cohort_b_supported=True,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED"
        )
        assert (
            classify_t085_terminal(
                neutral,
                gates=gates,
                cohort_b_supported=False,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT"
        )
        gates["retention"] = False
        assert (
            classify_t085_terminal(
                neutral,
                gates=gates,
                cohort_b_supported=True,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "INCOMPLETE"
        )
    finally:
        evidence["_artifact_path"].unlink(missing_ok=True)


def test_retention_artifact_manifest_records_hash_size_schema_and_workers(
    tmp_path,
) -> None:
    target = T085_ARTIFACT_ROOT / f".pytest-t085-{tmp_path.name}.json"
    artifact = write_t085_json_artifact(
        target,
        {"rows": 2},
        schema_id="t085-paired-evaluation-report-v1",
    )
    try:
        manifest = build_t085_retention_manifest(
            inputs={"t084": artifact},
            outputs={"paired": artifact},
            stages=[
                {
                    "stage": "evaluation",
                    "effective_worker_count": 16,
                    "shard_count": 16,
                    "record_range": "test",
                    "wall_clock_seconds": 0.1,
                }
            ],
            code_identity={"commit": "test"},
            native_identity={"commit": "test"},
            terminal_classification="INCOMPLETE",
            regeneration_commands=["python -m test"],
            retention_reason="review evidence",
            deletion_conditions=["after merged retention handoff"],
        )
        assert manifest["artifact_root"] == str(T085_ARTIFACT_ROOT)
        assert manifest["outputs"]["paired"]["byte_count"] > 0
        assert len(manifest["outputs"]["paired"]["sha256"]) == 64
        assert validate_t085_retention_manifest(manifest)["verified"] is True
        terminal = build_t085_terminal_report(
            "INCOMPLETE", gates={"execution": False}, evaluation_report=manifest
        )
        assert terminal["classification"] == "INCOMPLETE"
    finally:
        target.unlink(missing_ok=True)


def test_retention_rejects_non_stable_output_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="stable ignored T085 root"):
        build_t085_retention_manifest(
            inputs={},
            outputs={
                "bad": {
                    "path": str(tmp_path / "bad.json"),
                    "schema_id": "test",
                    "sha256": "a" * 64,
                    "byte_count": 1,
                }
            },
            stages=[],
            code_identity={},
            native_identity={},
            terminal_classification="INCOMPLETE",
            regeneration_commands=[],
            retention_reason="test",
            deletion_conditions=[],
        )
