from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

import sts_combat_rl.t085_corrected_leaf_value_search_evaluation as t085_evaluation
from sts_combat_rl.commands.t085_corrected_leaf_value_search_evaluation import (
    run_t085_paired_evaluation_report_from_paths,
    run_t085_retention_validation_from_path,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_ARTIFACT_ROOT,
    T085_INPUT_ARTIFACT_IDENTITIES,
    T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    T085_NATIVE_IDENTITY,
    T085_PRIMARY_ARMS,
    T085_REQUIRED_INPUT_ARTIFACT_KEYS,
    T085_REQUIRED_RETENTION_OUTPUT_ROLES,
    T085_SEARCH_400_ARMS,
    T085_SECONDARY_ARMS,
    T085_T042_SCALE_MANIFEST_SHA256,
    T085_T052_COHORT_BYTE_COUNT,
    T085_T052_COHORT_PATH,
    T085_T052_COHORT_SHA256,
    T085BattleStartRecord,
    T085OutcomeRecord,
    T085SourceRunRecord,
    audit_cohort_b_source_overlap,
    bootstrap_mean_percentile,
    build_t085_cohort_selection,
    build_t085_evaluation_selection_evidence,
    build_t085_paired_evaluation_report,
    build_t085_retention_manifest,
    build_t085_terminal_report,
    classify_t085_terminal,
    load_t085_t052_cohort_records,
    run_t085_paired_evaluation,
    select_cohort_b,
    select_cohort_c,
    select_search_400_subset,
    sha256_file,
    validate_cohort_a,
    validate_t085_evaluation_selection_evidence,
    validate_t085_restore_parity,
    validate_t085_retention_manifest,
    validate_t085_source_generation_contract,
    write_t085_json_artifact,
)


def test_t085_t042_scale_manifest_identity_is_exact() -> None:
    """Keep the code identity bound to the published retained manifest."""

    assert len(T085_T042_SCALE_MANIFEST_SHA256) == 64
    assert all(
        character in "0123456789abcdef" for character in T085_T042_SCALE_MANIFEST_SHA256
    )

    reference = T085_INPUT_ARTIFACT_IDENTITIES["t042_scale_manifest"]
    path = Path(str(reference["path"]))
    if not path.is_file():
        pytest.skip("retained T042 scale manifest is not mounted")
    assert path.stat().st_size == reference["byte_count"]
    assert sha256_file(path) == T085_T042_SCALE_MANIFEST_SHA256


def _source_manifest(tmp_path, *, cohort: str) -> dict[str, object]:
    common = {
        "schema_id": "t085-source-generation-manifest-v1",
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
        "source_manifest_frozen": True,
    }
    if cohort == "B":
        common.update(
            {
                "source_run_count": 1024,
                "source_run_seeds": list(range(851001, 852025)),
                "battle_controller": "oracle_search",
                "battle_simulations": 20,
                "root_selection": "highest_mean",
                "assistance_level": "assist_hp75_potion",
                "assistance_policy_seed": 42042,
                "t042_scale_manifest_sha256": T085_T042_SCALE_MANIFEST_SHA256,
            }
        )
    else:
        common.update(
            {
                "source_run_count": 128,
                "source_run_seeds": list(range(850001, 850129)),
                "battle_controller": "unguided_search_v2",
                "battle_simulations": 100,
                "root_selection": "highest_mean",
                "assistance_level": "assist_0",
                "assistance_policy_seed": None,
            }
        )
    prefix = cohort.lower()
    common.update(
        {
            "source_run_seed_inventory": list(common["source_run_seeds"]),
            "source_run_identity_inventory": [
                f"{prefix}-run-{seed}" for seed in common["source_run_seeds"]
            ],
            "complete_source_identity_inventory": [
                f"{prefix}-source-{seed}" for seed in common["source_run_seeds"]
            ],
        }
    )
    target = T085_ARTIFACT_ROOT / f".pytest-t085-source-{cohort}-{tmp_path.name}.json"
    write_t085_json_artifact(
        target,
        common,
        schema_id="t085-source-generation-manifest-v1",
    )
    reference = {
        "source_manifest_path": str(target.resolve()),
        "source_manifest_sha256": sha256_file(target),
        "source_manifest_byte_count": target.stat().st_size,
    }
    return common | reference


def _retention_test_inputs(tmp_path, monkeypatch):
    identities = {}
    paths = []
    for key in T085_REQUIRED_INPUT_ARTIFACT_KEYS:
        target = (
            T085_ARTIFACT_ROOT / f".pytest-t085-input-source-{tmp_path.name}-{key}.json"
        )
        identities[key] = write_t085_json_artifact(
            target,
            {"fixture_input": key},
            schema_id=f"t085-test-input-{key}-v1",
        )
        paths.append(target)
    monkeypatch.setattr(t085_evaluation, "T085_INPUT_ARTIFACT_IDENTITIES", identities)
    return identities, paths


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
    with pytest.raises(ValueError, match="complete 1024-run source pool"):
        audit_cohort_b_source_overlap(
            selected_b,
            t084_complete_source_identities={selected_b[0].complete_source_identity},
            t052_complete_source_identities={"old-t052-source"},
        )
    b_sources_with_overlap = _b_sources()
    with pytest.raises(ValueError, match="forbidden complete-source overlap"):
        audit_cohort_b_source_overlap(
            [
                *b_sources_with_overlap[:1],
                T085SourceRunRecord(
                    source_run_seed=851002,
                    source_run_identity="b-run-851002",
                    complete_source_identity="old-t084-source",
                ),
                *b_sources_with_overlap[2:],
            ],
            t084_complete_source_identities={"old-t084-source"},
            t052_complete_source_identities={"old-t052-source"},
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


def test_cohort_a_is_bound_to_the_real_t052_file_and_record_ids() -> None:
    if not T085_T052_COHORT_PATH.is_file():
        pytest.skip("retained T052 fixed cohort is not mounted")
    records = load_t085_t052_cohort_records()
    summary = validate_cohort_a(
        records,
        artifact_path=T085_T052_COHORT_PATH,
        artifact_sha256=T085_T052_COHORT_SHA256,
    )
    assert summary["record_count"] == 93
    assert summary["artifact_byte_count"] == T085_T052_COHORT_BYTE_COUNT
    forged = list(records)
    forged[0] = replace(
        forged[0],
        source_artifact_record_identity="caller-invented-t052-id",
        complete_source_identity="caller-invented-t052-id",
    )
    with pytest.raises(ValueError, match="exact retained T052 record identities"):
        validate_cohort_a(forged, artifact_path=T085_T052_COHORT_PATH)


def test_source_generation_contract_is_frozen_for_b_and_c(tmp_path) -> None:
    b = _source_manifest(tmp_path, cohort="B")
    c = _source_manifest(tmp_path, cohort="C")
    try:
        assert (
            validate_t085_source_generation_contract(b, cohort="B")["validated"] is True
        )
        assert (
            validate_t085_source_generation_contract(c, cohort="C")["validated"] is True
        )
        c["leaf_value_callback"] = "caller-injected"
        with pytest.raises(ValueError, match="disable Search guidance"):
            validate_t085_source_generation_contract(c, cohort="C")
        b["non_combat_policy_seed"] = 851001
        with pytest.raises(ValueError, match="non_combat_policy_seed"):
            validate_t085_source_generation_contract(b, cohort="B")
    finally:
        Path(b["source_manifest_path"]).unlink(missing_ok=True)
        Path(c["source_manifest_path"]).unlink(missing_ok=True)


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
    cohort: str,
    identity: str,
    arm: str,
    survived: bool,
    utility: float,
    *,
    source_run_identity: str | None = None,
) -> T085OutcomeRecord:
    return T085OutcomeRecord(
        cohort=cohort,
        record_identity=identity,
        arm=arm,
        battle_survived=survived,
        terminal_native_utility=utility,
        source_run_identity=source_run_identity or identity,
        search_budget=400 if cohort == "B@400" else 100,
    )


def test_outcome_mapping_requires_explicit_boolean_survival() -> None:
    payload = asdict(_row("A", "A-0", "baseline", False, 1.0))
    assert T085OutcomeRecord.from_mapping(payload).battle_survived is False

    missing = dict(payload)
    missing.pop("battle_survived")
    with pytest.raises(ValueError, match="battle_survived is required"):
        T085OutcomeRecord.from_mapping(missing)

    for invalid in (None, 0, 1, "false"):
        malformed = dict(payload)
        malformed["battle_survived"] = invalid
        with pytest.raises(ValueError, match="battle_survived must be a boolean"):
            T085OutcomeRecord.from_mapping(malformed)


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


def _evaluation_rows_with_contract_counts(
    *,
    utility_mode: str = "neutral",
    cohorts: dict[str, tuple[T085BattleStartRecord, ...]] | None = None,
) -> list[T085OutcomeRecord]:
    if cohorts is None:
        cohort_records = {
            cohort: tuple(
                T085BattleStartRecord(
                    source_run_seed=index,
                    source_run_identity=f"{cohort}-run-{index}",
                    complete_source_identity=f"{cohort}-source-{index}",
                    battle_identity=f"{cohort}-battle-{index}",
                    act=1,
                    room_type="MONSTER",
                )
                for index in range(count)
            )
            for cohort, count in {"A": 93, "B": 192, "C": 96}.items()
        }
        cohort_records["B@400"] = tuple(
            T085BattleStartRecord(
                source_run_seed=index,
                source_run_identity=f"B400-run-{index}",
                complete_source_identity=f"B400-source-{index}",
                battle_identity=f"B400-battle-{index}",
                act=1,
                room_type="MONSTER",
            )
            for index in range(48)
        )
    else:
        cohort_records = cohorts
    rows: list[T085OutcomeRecord] = []
    for cohort in ("A", "B", "C"):
        for record in cohort_records[cohort]:
            identity = record.selection_identity
            for arm in T085_PRIMARY_ARMS:
                if utility_mode == "established":
                    survived = arm.startswith("corrected")
                    utility = 2.0 if survived else 0.0
                elif utility_mode == "harmful":
                    survived = not arm.startswith("corrected")
                    utility = 0.0 if not survived else 2.0
                else:
                    survived = True
                    utility = 1.0
                rows.append(
                    _row(
                        cohort,
                        identity,
                        arm,
                        survived,
                        utility,
                        source_run_identity=record.source_run_identity,
                    )
                )
            if cohort == "B":
                for arm in T085_SECONDARY_ARMS:
                    rows.append(
                        _row(
                            cohort,
                            identity,
                            arm,
                            True,
                            1.0,
                            source_run_identity=record.source_run_identity,
                        )
                    )
    for record in cohort_records["B@400"]:
        identity = record.selection_identity
        for arm in T085_SEARCH_400_ARMS:
            if utility_mode == "established":
                survived = arm.startswith("corrected")
                utility = 2.0 if survived else 0.0
            elif utility_mode == "harmful":
                survived = not arm.startswith("corrected")
                utility = 0.0 if not survived else 2.0
            else:
                survived = True
                utility = 1.0
            rows.append(
                _row(
                    "B@400",
                    identity,
                    arm,
                    survived,
                    utility,
                    source_run_identity=record.source_run_identity,
                )
            )
    return rows


def _formal_selection(tmp_path):
    if not T085_T052_COHORT_PATH.is_file():
        pytest.skip("retained T052 fixed cohort is not mounted")
    cohort_a = load_t085_t052_cohort_records()
    manifest_b = _source_manifest(tmp_path, cohort="B")
    manifest_c = _source_manifest(tmp_path, cohort="C")
    selected_b, evidence_b = build_t085_cohort_selection(
        cohort="B",
        source_manifest=manifest_b,
        source_runs=_b_sources(),
        battle_starts=_b_starts(),
        restore_results={
            record.selection_identity: {
                "restore_ok": True,
                "public_context_match": True,
            }
            for record in _b_starts()
        },
        t084_complete_source_identities={"old-t084-source"},
        t052_complete_source_identities={"old-t052-source"},
    )
    selected_c, evidence_c = build_t085_cohort_selection(
        cohort="C",
        source_manifest=manifest_c,
        source_runs=_c_sources(),
        battle_starts=_c_starts(),
        restore_results={
            record.selection_identity: {
                "restore_ok": True,
                "public_context_match": True,
            }
            for record in _c_starts()
        },
    )
    selected_400, _ = select_search_400_subset(selected_b)
    selection_evidence = build_t085_evaluation_selection_evidence(
        cohort_a_records=cohort_a,
        cohort_a_restore_results={
            record.selection_identity: {
                "restore_ok": True,
                "public_context_match": True,
            }
            for record in cohort_a
        },
        cohort_b_records=selected_b,
        cohort_b_selection_evidence=evidence_b,
        cohort_c_records=selected_c,
        cohort_c_selection_evidence=evidence_c,
        search_400_records=selected_400,
    )
    return (
        {
            "A": cohort_a,
            "B": selected_b,
            "C": selected_c,
            "B@400": selected_400,
        },
        selection_evidence,
        [
            Path(manifest_b["source_manifest_path"]),
            Path(manifest_c["source_manifest_path"]),
        ],
    )


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

    with pytest.raises(ValueError, match="validated source/selection/parity evidence"):
        run_t085_paired_evaluation(records, evaluate_record=evaluate)
    assert calls == []


def test_executable_arm_workflow_binds_frozen_selection(tmp_path) -> None:
    cohorts, selection_evidence, source_paths = _formal_selection(tmp_path)
    calls: list[tuple[str, int, str]] = []

    def evaluate(record, arm, budget):
        calls.append((arm, budget, record.selection_identity))
        return {
            "cohort": "B@400"
            if budget == 400
            else next(
                cohort
                for cohort, cohort_records in cohorts.items()
                if record in cohort_records and cohort != "B@400"
            ),
            "record_identity": record.selection_identity,
            "arm": arm,
            "battle_survived": True,
            "terminal_native_utility": 1.0,
            "source_run_identity": record.source_run_identity,
            "search_budget": budget,
        }

    try:
        report = run_t085_paired_evaluation(
            cohorts,
            evaluate_record=evaluate,
            selection_evidence=selection_evidence,
        )
        assert report["schema_id"] == "t085-paired-evaluation-report-v1"
        assert report["selection_binding"]["B"]["selected_identity_order"] == [
            record.selection_identity for record in cohorts["B"]
        ]
        assert calls.count(("baseline", 100, cohorts["A"][0].selection_identity)) == 1
        assert (
            calls.count(("baseline@400", 400, cohorts["B@400"][0].selection_identity))
            == 1
        )
    finally:
        for path in source_paths:
            path.unlink(missing_ok=True)


def test_selection_evidence_composition_and_cli_outcome_binding(tmp_path) -> None:
    cohorts, selection_evidence, source_paths = _formal_selection(tmp_path)
    output_path = T085_ARTIFACT_ROOT / f".pytest-t085-command-{tmp_path.name}.json"
    selection_path = tmp_path / "selection.json"
    outcomes_path = tmp_path / "outcomes.json"
    try:
        validated = validate_t085_evaluation_selection_evidence(
            cohorts, selection_evidence
        )
        assert validated["validated"] is True
        forged_order = {key: dict(value) for key, value in selection_evidence.items()}
        forged_order["B"]["selected_identity_order"] = list(
            reversed(forged_order["B"]["selected_identity_order"])
        )
        with pytest.raises(ValueError, match="identity order"):
            validate_t085_evaluation_selection_evidence(cohorts, forged_order)
        forged_records = {key: dict(value) for key, value in selection_evidence.items()}
        forged_records["C"]["selected_records"] = list(
            forged_records["C"]["selected_records"]
        )
        forged_records["C"]["selected_records"][0] = {
            **forged_records["C"]["selected_records"][0],
            "source_run_seed": -1,
        }
        with pytest.raises(ValueError, match="selected records"):
            validate_t085_evaluation_selection_evidence(cohorts, forged_records)
        forged_inventory = {
            key: dict(value) for key, value in selection_evidence.items()
        }
        forged_inventory["B"]["source_run_identity_inventory"] = list(
            forged_inventory["B"]["source_run_identity_inventory"]
        )
        forged_inventory["B"]["source_run_identity_inventory"][0] = "forged-run"
        with pytest.raises(ValueError, match="complete frozen source inventory"):
            validate_t085_evaluation_selection_evidence(cohorts, forged_inventory)

        rows = _evaluation_rows_with_contract_counts(cohorts=cohorts)
        selection_path.write_text(
            json.dumps(
                {
                    "cohorts": {
                        cohort: [asdict(record) for record in records]
                        for cohort, records in cohorts.items()
                    },
                    "selection_evidence": selection_evidence,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        outcomes_path.write_text(
            json.dumps([asdict(row) for row in rows], sort_keys=True),
            encoding="utf-8",
        )
        result = run_t085_paired_evaluation_report_from_paths(
            outcomes_path=outcomes_path,
            selection_evidence_path=selection_path,
            output_path=output_path,
        )
        assert "selection_binding" in result["report"]
        bad_outcomes = [asdict(row) for row in rows]
        bad_outcomes[0]["source_run_identity"] = "forged-source"
        outcomes_path.write_text(
            json.dumps(bad_outcomes, sort_keys=True),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="frozen source run"):
            run_t085_paired_evaluation_report_from_paths(
                outcomes_path=outcomes_path,
                selection_evidence_path=selection_path,
                output_path=output_path,
            )
    finally:
        output_path.unlink(missing_ok=True)
        for path in source_paths:
            path.unlink(missing_ok=True)


def _gate_evidence(
    tmp_path,
    selection_evidence: dict[str, dict[str, object]],
    *,
    input_identities: dict[str, dict[str, object]],
    support_status: str = "supported",
) -> dict[str, object]:
    target = T085_ARTIFACT_ROOT / f".pytest-t085-gates-{tmp_path.name}.json"
    eligibility_path = (
        T085_ARTIFACT_ROOT / f".pytest-t085-input-eligibility-{tmp_path.name}.json"
    )
    code_identity = {"commit": "test"}
    inputs = {
        key: dict(input_identities[key]) for key in T085_REQUIRED_INPUT_ARTIFACT_KEYS
    }
    eligibility = write_t085_json_artifact(
        eligibility_path,
        {
            "task_id": "T085",
            "accepted_inputs": inputs,
            "code_identity": code_identity,
            "native_identity": dict(T085_NATIVE_IDENTITY),
        },
        schema_id=T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    )
    artifact = write_t085_json_artifact(
        target,
        {"evidence": True},
        schema_id="t085-terminal-classification-report-v1",
    )
    outputs = {role: artifact for role in T085_REQUIRED_RETENTION_OUTPUT_ROLES}
    outputs["input_eligibility_manifest"] = eligibility
    manifest = build_t085_retention_manifest(
        inputs=inputs,
        outputs=outputs,
        stages=[],
        code_identity=code_identity,
        native_identity=T085_NATIVE_IDENTITY,
        terminal_classification="INCOMPLETE",
        regeneration_commands=["test"],
        retention_reason="classification test",
        deletion_conditions=["test complete"],
    )
    counts = {
        cohort: int(selection_evidence[cohort]["selected_count"])
        for cohort in ("A", "B", "C", "B@400")
    }
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
    } | {
        "selection": {
            "passed": True,
            "evidence_id": "test-selection",
            "cohort_a_selected_count": counts["A"],
            "cohort_b_selected_count": counts["B"],
            "cohort_c_selected_count": counts["C"],
            "search_400_selected_count": counts["B@400"],
            "support_status": support_status,
            "source_generation_valid": True,
            "source_frozen": True,
            "restore_parity_passed": True,
            "zero_overlap": True,
            "cohort_a_artifact": selection_evidence["A"]["artifact"],
            "cohort_b_source_manifest": selection_evidence["B"]["source_manifest"],
            "cohort_c_source_manifest": selection_evidence["C"]["source_manifest"],
        },
        "retention_manifest": manifest,
        "_artifact_path": target,
        "_eligibility_path": eligibility_path,
    }


def test_terminal_classification_covers_every_published_class(
    tmp_path, monkeypatch
) -> None:
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
    cohorts, selection_evidence, source_paths = _formal_selection(tmp_path)
    input_identities, input_paths = _retention_test_inputs(tmp_path, monkeypatch)
    evidence = _gate_evidence(
        tmp_path,
        selection_evidence,
        input_identities=input_identities,
    )
    try:
        report_kwargs = {
            "cohort_b_record_count": len(cohorts["B"]),
            "cohort_c_record_count": len(cohorts["C"]),
            "selection_cohorts": cohorts,
            "selection_evidence": selection_evidence,
        }
        established_rows = _evaluation_rows_with_contract_counts(
            utility_mode="established", cohorts=cohorts
        )
        established = build_t085_paired_evaluation_report(
            established_rows, **report_kwargs
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
        harmful_rows = _evaluation_rows_with_contract_counts(
            utility_mode="harmful", cohorts=cohorts
        )
        harmful = build_t085_paired_evaluation_report(harmful_rows, **report_kwargs)
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
            _evaluation_rows_with_contract_counts(cohorts=cohorts), **report_kwargs
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
        small_report = build_t085_paired_evaluation_report(
            _evaluation_rows(), cohort_b_record_count=2, cohort_c_record_count=2
        )
        assert (
            classify_t085_terminal(
                small_report,
                gates=gates,
                cohort_b_supported=True,
                cohort_c_supported=True,
                gate_evidence=evidence,
            )
            == "INCOMPLETE"
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
        evidence["_eligibility_path"].unlink(missing_ok=True)
        for path in input_paths:
            path.unlink(missing_ok=True)
        for path in source_paths:
            path.unlink(missing_ok=True)


def test_retention_artifact_manifest_records_hash_size_schema_and_workers(
    tmp_path, monkeypatch
) -> None:
    input_identities, input_paths = _retention_test_inputs(tmp_path, monkeypatch)
    target = T085_ARTIFACT_ROOT / f".pytest-t085-{tmp_path.name}.json"
    artifact = write_t085_json_artifact(
        target,
        {"rows": 2},
        schema_id="t085-paired-evaluation-report-v1",
    )
    try:
        eligibility_path = (
            T085_ARTIFACT_ROOT / f".pytest-t085-input-{tmp_path.name}.json"
        )
        code_identity = {"commit": "test"}
        inputs = {
            key: dict(input_identities[key])
            for key in T085_REQUIRED_INPUT_ARTIFACT_KEYS
        }
        eligibility = write_t085_json_artifact(
            eligibility_path,
            {
                "task_id": "T085",
                "accepted_inputs": inputs,
                "code_identity": code_identity,
                "native_identity": dict(T085_NATIVE_IDENTITY),
            },
            schema_id=T085_INPUT_ELIGIBILITY_SCHEMA_ID,
        )
        outputs = {role: artifact for role in T085_REQUIRED_RETENTION_OUTPUT_ROLES}
        outputs["input_eligibility_manifest"] = eligibility
        kwargs = {
            "inputs": inputs,
            "outputs": outputs,
            "stages": [
                {
                    "stage": "evaluation",
                    "configured_worker_count": 16,
                    "effective_worker_count": 16,
                    "shard_count": 16,
                    "record_range": "test",
                    "wall_clock_seconds": 0.1,
                }
            ],
            "code_identity": code_identity,
            "native_identity": T085_NATIVE_IDENTITY,
            "terminal_classification": "INCOMPLETE",
            "regeneration_commands": ["python -m test"],
            "retention_reason": "review evidence",
            "deletion_conditions": ["after merged retention handoff"],
        }
        manifest = build_t085_retention_manifest(**kwargs)
        assert manifest["artifact_root"] == str(T085_ARTIFACT_ROOT)
        assert manifest["outputs"]["paired_evaluation_report"]["byte_count"] > 0
        assert len(manifest["outputs"]["paired_evaluation_report"]["sha256"]) == 64
        assert validate_t085_retention_manifest(manifest)["verified"] is True
        terminal = build_t085_terminal_report(
            "INCOMPLETE", gates={"execution": False}, evaluation_report=manifest
        )
        assert terminal["classification"] == "INCOMPLETE"

        incomplete = dict(manifest)
        incomplete_outputs = dict(manifest["outputs"])
        del incomplete_outputs["terminal_classification_report"]
        incomplete["outputs"] = incomplete_outputs
        with pytest.raises(ValueError, match="missing required output roles"):
            validate_t085_retention_manifest(incomplete)

        malformed_stage = dict(manifest)
        malformed_stage.pop("stages")
        with pytest.raises(ValueError, match="stages must be a list"):
            validate_t085_retention_manifest(malformed_stage)

        forged = dict(artifact)
        forged["sha256"] = "0" * 64
        with pytest.raises(ValueError, match="hash changed"):
            build_t085_retention_manifest(
                **{
                    **kwargs,
                    "outputs": {
                        role: forged for role in T085_REQUIRED_RETENTION_OUTPUT_ROLES
                    },
                }
            )

        tampered_path = input_paths[0]
        original = tampered_path.read_bytes()
        tampered_path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        try:
            with pytest.raises(ValueError, match="inputs.t084_report hash changed"):
                validate_t085_retention_manifest(manifest)
        finally:
            tampered_path.write_bytes(original)
    finally:
        target.unlink(missing_ok=True)
        eligibility_path.unlink(missing_ok=True)
        for path in input_paths:
            path.unlink(missing_ok=True)


def test_retention_rejects_non_stable_output_path(tmp_path, monkeypatch) -> None:
    input_identities, input_paths = _retention_test_inputs(tmp_path, monkeypatch)
    target = T085_ARTIFACT_ROOT / f".pytest-t085-stable-{tmp_path.name}.json"
    eligibility_path = (
        T085_ARTIFACT_ROOT / f".pytest-t085-stable-input-{tmp_path.name}.json"
    )
    inputs = {
        key: dict(input_identities[key]) for key in T085_REQUIRED_INPUT_ARTIFACT_KEYS
    }
    eligibility = write_t085_json_artifact(
        eligibility_path,
        {
            "task_id": "T085",
            "accepted_inputs": inputs,
            "code_identity": {"commit": "test"},
            "native_identity": dict(T085_NATIVE_IDENTITY),
        },
        schema_id=T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    )
    artifact = write_t085_json_artifact(
        target,
        {"rows": 1},
        schema_id="t085-paired-evaluation-report-v1",
    )
    outputs = {role: artifact for role in T085_REQUIRED_RETENTION_OUTPUT_ROLES}
    outputs["input_eligibility_manifest"] = eligibility
    bad = dict(artifact)
    bad["path"] = str(tmp_path / "bad.json")
    outputs["paired_evaluation_report"] = bad
    with pytest.raises(ValueError, match="stable ignored T085 root"):
        try:
            build_t085_retention_manifest(
                inputs=inputs,
                outputs=outputs,
                stages=[],
                code_identity={"commit": "test"},
                native_identity=T085_NATIVE_IDENTITY,
                terminal_classification="INCOMPLETE",
                regeneration_commands=["test"],
                retention_reason="test",
                deletion_conditions=["test complete"],
            )
        finally:
            target.unlink(missing_ok=True)
            eligibility_path.unlink(missing_ok=True)
            for path in input_paths:
                path.unlink(missing_ok=True)


def test_retention_cli_rejects_missing_accepted_input_identity(
    tmp_path, monkeypatch
) -> None:
    input_identities, input_paths = _retention_test_inputs(tmp_path, monkeypatch)
    eligibility_path = (
        T085_ARTIFACT_ROOT / f".pytest-t085-cli-input-{tmp_path.name}.json"
    )
    artifact_path = T085_ARTIFACT_ROOT / f".pytest-t085-cli-output-{tmp_path.name}.json"
    manifest_path = (
        T085_ARTIFACT_ROOT / f".pytest-t085-cli-retention-{tmp_path.name}.json"
    )
    inputs = {
        key: dict(input_identities[key]) for key in T085_REQUIRED_INPUT_ARTIFACT_KEYS
    }
    code_identity = {"commit": "test"}
    eligibility = write_t085_json_artifact(
        eligibility_path,
        {
            "task_id": "T085",
            "accepted_inputs": inputs,
            "code_identity": code_identity,
            "native_identity": dict(T085_NATIVE_IDENTITY),
        },
        schema_id=T085_INPUT_ELIGIBILITY_SCHEMA_ID,
    )
    artifact = write_t085_json_artifact(
        artifact_path,
        {"rows": 1},
        schema_id="t085-paired-evaluation-report-v1",
    )
    outputs = {role: artifact for role in T085_REQUIRED_RETENTION_OUTPUT_ROLES}
    outputs["input_eligibility_manifest"] = eligibility
    try:
        manifest = build_t085_retention_manifest(
            inputs=inputs,
            outputs=outputs,
            stages=[],
            code_identity=code_identity,
            native_identity=T085_NATIVE_IDENTITY,
            terminal_classification="INCOMPLETE",
            regeneration_commands=["test"],
            retention_reason="test",
            deletion_conditions=["test complete"],
        )
        write_t085_json_artifact(
            manifest_path,
            manifest,
            schema_id="t085-retention-manifest-v1",
        )
        assert (
            run_t085_retention_validation_from_path(manifest_path)["verified"] is True
        )

        incomplete = json.loads(manifest_path.read_text(encoding="utf-8"))
        incomplete["inputs"].pop("t084_report")
        write_t085_json_artifact(
            manifest_path,
            incomplete,
            schema_id="t085-retention-manifest-v1",
        )
        with pytest.raises(ValueError, match="exact accepted input set"):
            run_t085_retention_validation_from_path(manifest_path)
    finally:
        eligibility_path.unlink(missing_ok=True)
        artifact_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        for path in input_paths:
            path.unlink(missing_ok=True)
