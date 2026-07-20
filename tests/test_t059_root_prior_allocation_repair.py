from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.t059_root_prior_allocation_repair import (
    run_t059_retention_manifest_from_paths,
    run_t059_root_prior_allocation_repair_from_paths,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search import (
    ROOT_PRIOR_ALLOCATION_REPAIR_STRATEGY,
    ROOT_PRIOR_ALLOCATION_REPAIR_VERSION,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
    RootPriorGuidedSearchComparisonReport,
    build_root_prior_guided_search_comparison_report,
    dump_root_prior_guided_search_comparison_jsonl,
)
from sts_combat_rl.sim.t058_root_prior_selected_action_telemetry import (
    T058RootPriorSelectedActionTelemetryReport,
    dump_t058_root_prior_selected_action_telemetry_report_json,
)
from sts_combat_rl.sim.t059_root_prior_allocation_repair import (
    T059_REPAIR_REPORT_SCHEMA_ID,
    T059ComparisonInput,
    build_t059_root_prior_allocation_repair_report,
    dump_t059_root_prior_allocation_repair_report_json,
    format_t059_root_prior_allocation_repair_report,
    load_t059_root_prior_allocation_repair_report_json,
    load_t059_root_prior_comparison_inputs,
)


def test_t059_report_validates_repair_subsets_and_roundtrips() -> None:
    comparisons = _comparison_inputs()

    report = build_t059_root_prior_allocation_repair_report(
        input_artifacts=_verified_artifacts(),
        t058_report=_t058_report(),
        comparisons=comparisons,
    )

    assert report.command_passed
    assert report.schema_id == T059_REPAIR_REPORT_SCHEMA_ID
    assert report.aggregate_summary["all_records"]["record_count"] == 122
    assert report.cohort_summaries["t048_current_t046_compatible"]["record_count"] == 8
    assert report.subset_summaries["t052_act2_plus"]["record_count"] == 5
    assert report.subset_summaries["t053_disagreement_records"]["record_count"] == 4
    assert report.aggregate_summary["preserved_t048_positive_signal"] is True
    assert report.aggregate_summary["repaired_or_tied_t052_act2_plus"] is True
    assert report.aggregate_summary["repaired_or_tied_t053_disagreement"] is True
    assert (
        report.allocation_telemetry_summary["t059_repair"]["repair_telemetry"][
            "repair_version_counts"
        ][ROOT_PRIOR_ALLOCATION_REPAIR_VERSION]
        == 122
    )
    assert report.selected_action_availability["unavailable_record_count"] == 0
    assert (
        report.recommendation["recommended_next_task"]
        == "run a bounded complete-run reachability probe for the repaired variant"
    )
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False

    buffer = StringIO()
    dump_t059_root_prior_allocation_repair_report_json(report, buffer)
    loaded = load_t059_root_prior_allocation_repair_report_json(
        StringIO(buffer.getvalue())
    )
    text = format_t059_root_prior_allocation_repair_report(loaded)
    assert "T059 root-prior allocation repair report" in text
    assert "no controller promotion" in text
    assert "normal-information" in text


def test_t059_report_rejects_missing_repair_arm() -> None:
    comparisons = _comparison_inputs(include_repair=False)

    with pytest.raises(ValueError, match="missing required arms"):
        build_t059_root_prior_allocation_repair_report(
            input_artifacts=_verified_artifacts(),
            t058_report=_t058_report(),
            comparisons=comparisons,
        )


@pytest.mark.parametrize("mutation", ["missing_row", "source_mismatch"])
def test_t059_report_rejects_unclean_battle_comparisons(mutation: str) -> None:
    comparisons = _comparison_inputs()
    role = "t059_current_repair_comparison"
    original = comparisons[role]
    assert isinstance(original, T059ComparisonInput)
    rows = [dict(row) for row in original.battle_comparisons]
    if mutation == "missing_row":
        rows.pop()
    else:
        rows[0]["source_match"] = False
        rows[0]["problems"] = ["source battle mismatch"]
    comparisons[role] = T059ComparisonInput(
        role=original.role,
        metadata=original.metadata,
        battle_comparisons=rows,
        results_by_label=original.results_by_label,
    )

    with pytest.raises(ValueError) as exc_info:
        build_t059_root_prior_allocation_repair_report(
            input_artifacts=_verified_artifacts(),
            t058_report=_t058_report(),
            comparisons=comparisons,
        )

    message = str(exc_info.value)
    if mutation == "missing_row":
        assert "battle comparison count mismatch" in message
        assert "missing battle_comparison indices 7" in message
    else:
        assert "battle_comparison[0]: source_match must be true" in message
        assert "battle_comparison[0]: problems must be empty" in message


def test_t059_report_accepts_merged_t052_shard_record_ranges() -> None:
    report = build_t059_root_prior_allocation_repair_report(
        input_artifacts=_verified_artifacts(),
        t058_report=_t058_report(),
        comparisons=_comparison_inputs(t052_merged=True),
    )

    assert report.command_passed
    assert (
        report.cohort_summaries["t052_boss_later_act_diagnostic"]["record_count"] == 93
    )


def test_t059_report_abandons_when_repair_only_ties_harmful_subsets() -> None:
    comparisons = _comparisons()
    comparisons["t059_t052_repair_comparison"] = _comparison(
        cohort_identity="68d0e5b10ebcb05d",
        count=93,
        record_range="0:93",
        workers=16,
        shards=16,
        win_indices={
            BASELINE_ORACLE_LABEL: {53, 88, 89, 90},
            POST_SEARCH_MODEL_GUIDED_LABEL: {53, 88, 89, 90},
            ROOT_PRIOR_GUIDED_LABEL: {88, 89, 0},
            T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: {88, 89, 0},
        },
        include_repair=True,
    )

    report = build_t059_root_prior_allocation_repair_report(
        input_artifacts=_verified_artifacts(),
        t058_report=_t058_report(),
        comparisons=_comparison_inputs_from_reports(comparisons),
    )

    assert (
        report.recommendation["recommended_next_task"]
        == "abandon the allocation-repair path"
    )
    assert report.aggregate_summary["improved_t052_act2_plus"] is False
    assert report.aggregate_summary["improved_t053_disagreement"] is False


def test_t059_report_does_not_preserve_t048_signal_after_root_prior_regression() -> (
    None
):
    comparisons = _comparisons()
    comparisons["t059_current_repair_comparison"] = _comparison(
        cohort_identity="875ea52e3df4cb93",
        count=8,
        record_range="0:8",
        workers=8,
        shards=8,
        win_indices={
            BASELINE_ORACLE_LABEL: set(range(5)),
            POST_SEARCH_MODEL_GUIDED_LABEL: set(range(5)),
            ROOT_PRIOR_GUIDED_LABEL: set(range(6)),
            T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: set(range(5)),
        },
        include_repair=True,
    )

    report = build_t059_root_prior_allocation_repair_report(
        input_artifacts=_verified_artifacts(),
        t058_report=_t058_report(),
        comparisons=_comparison_inputs_from_reports(comparisons),
    )

    assert report.aggregate_summary["preserved_t048_positive_signal"] is False


def test_t059_command_hash_checks_and_writes_report(tmp_path: Path) -> None:
    paths = _write_t059_inputs(tmp_path)
    output_path = tmp_path / "t059-report.json"

    report = run_t059_root_prior_allocation_repair_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=output_path,
    )

    assert report.command_passed
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_id"] == (
        T059_REPAIR_REPORT_SCHEMA_ID
    )


def test_t059_command_rejects_input_schema_mismatch(tmp_path: Path) -> None:
    paths = _write_t059_inputs(tmp_path)
    comparison = paths["t059_current_repair_comparison"]
    text = comparison.read_text(encoding="utf-8")
    comparison.write_text(
        text.replace(
            "root-prior-guided-search-comparison-v1",
            "unsupported-comparison-v1",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported detected schema"):
        run_t059_root_prior_allocation_repair_from_paths(
            artifact_specs=_artifact_specs(paths),
            output_path=tmp_path / "t059-report.json",
        )


def test_t059_command_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t059_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[-1][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t059_root_prior_allocation_repair_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t059-report.json",
        )


def test_t059_retention_manifest_records_generated_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text('{"schema_id":"t059-root-prior-allocation-repair-report-v1"}\n')
    output_path = tmp_path / "manifest.json"

    manifest = run_t059_retention_manifest_from_paths(
        output_path=output_path,
        artifact_specs=[
            [
                "repair_report",
                str(artifact),
                "t059-root-prior-allocation-repair-report-v1",
            ]
        ],
        command_specs=[["repair_report", "python -m sts_combat_rl.cli ..."]],
        stage_specs=[["t052_comparison", "16", "16", "0:93", "12.5"]],
        note_specs=[["runtime", "unit-test"]],
    )

    assert output_path.exists()
    assert manifest["schema_id"] == "t059-retention-manifest-v1"
    assert manifest["artifacts"][0]["sha256"] == _sha256(artifact)
    assert manifest["runtime_stages"][0]["workers"] == 16


def test_cli_t059_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t059-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert len(kwargs["artifact_specs"]) == 13
        assert kwargs["artifact_specs"][0][0] == "t058_selected_action_telemetry_report"
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t059_root_prior_allocation_repair_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t059_root_prior_allocation_repair_command",
        lambda report: "T059 root-prior allocation repair report\ncommand passed: yes",
    )

    rc = main(
        [
            "--t059-root-prior-allocation-repair-report",
            str(output_path),
            *[
                item
                for index, role in enumerate(_required_roles())
                for item in [
                    "--t059-input-artifact",
                    role,
                    f"{role}.json",
                    f"{index:064x}"[-64:],
                ]
            ],
            "--log-file",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "T059 root-prior allocation repair" in captured.err


def _write_t059_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {role: tmp_path / f"{role}.artifact" for role in _required_roles()}
    with paths["t058_selected_action_telemetry_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t058_root_prior_selected_action_telemetry_report_json(
            _t058_report(),
            stream,
        )
    paths["t058_retention_manifest"].write_text(
        '{\n  "schema_id": "t058-retention-manifest-v1",\n  "format_version": 1\n}\n',
        encoding="utf-8",
    )
    for role in (
        "t048_current_t058_comparison",
        "t048_assist0_t058_comparison",
        "t052_t058_comparison",
        "t048_current_fixed_cohort",
        "t048_assist0_fixed_cohort",
        "t052_boss_later_act_fixed_cohort",
    ):
        if role.endswith("fixed_cohort"):
            _write_fixed_cohort_metadata(paths[role])
        else:
            _write_jsonl_metadata(paths[role], "root-prior-guided-search-comparison-v1")
    paths["t043_assist0_smoke_checkpoint"].write_bytes(b"checkpoint-smoke")
    paths["t043_runs1000_assist0_checkpoint"].write_bytes(b"checkpoint-runs1000")
    for role, comparison in _comparisons().items():
        with paths[role].open("w", encoding="utf-8", newline="\n") as stream:
            dump_root_prior_guided_search_comparison_jsonl(comparison, stream)
    return paths


def _comparison_inputs(
    *,
    include_repair: bool = True,
    t052_merged: bool = False,
) -> dict[str, object]:
    inputs = {}
    for role, comparison in _comparisons(
        include_repair=include_repair,
        t052_merged=t052_merged,
    ).items():
        buffer = StringIO()
        dump_root_prior_guided_search_comparison_jsonl(comparison, buffer)
        inputs[role] = load_t059_root_prior_comparison_inputs(
            StringIO(buffer.getvalue()),
            role=role,
        )
    return inputs


def _comparison_inputs_from_reports(
    comparisons: dict[str, RootPriorGuidedSearchComparisonReport],
) -> dict[str, object]:
    inputs = {}
    for role, comparison in comparisons.items():
        buffer = StringIO()
        dump_root_prior_guided_search_comparison_jsonl(comparison, buffer)
        inputs[role] = load_t059_root_prior_comparison_inputs(
            StringIO(buffer.getvalue()),
            role=role,
        )
    return inputs


def _comparisons(
    *,
    include_repair: bool = True,
    t052_merged: bool = False,
) -> dict[str, RootPriorGuidedSearchComparisonReport]:
    t052_ranges = [
        "0:6",
        "6:12",
        "12:18",
        "18:24",
        "24:30",
        "30:36",
        "36:42",
        "42:48",
        "48:54",
        "54:60",
        "60:66",
        "66:72",
        "72:78",
        "78:83",
        "83:88",
        "88:93",
    ]
    return {
        "t059_current_repair_comparison": _comparison(
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            workers=8,
            shards=8,
            win_indices={
                BASELINE_ORACLE_LABEL: set(range(5)),
                POST_SEARCH_MODEL_GUIDED_LABEL: set(range(5)),
                ROOT_PRIOR_GUIDED_LABEL: set(range(6)),
                T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: set(range(6)),
            },
            include_repair=include_repair,
        ),
        "t059_assist0_repair_comparison": _comparison(
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            workers=16,
            shards=16,
            win_indices={
                BASELINE_ORACLE_LABEL: set(range(11)),
                POST_SEARCH_MODEL_GUIDED_LABEL: set(range(11)),
                ROOT_PRIOR_GUIDED_LABEL: set(range(13)),
                T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: set(range(13)),
            },
            include_repair=include_repair,
        ),
        "t059_t052_repair_comparison": _comparison(
            cohort_identity="68d0e5b10ebcb05d",
            count=93,
            record_range="merged:" + ",".join(t052_ranges) if t052_merged else "0:93",
            merged_from_record_ranges=t052_ranges if t052_merged else None,
            workers=16,
            shards=16,
            win_indices={
                BASELINE_ORACLE_LABEL: {53, 88, 89, 90},
                POST_SEARCH_MODEL_GUIDED_LABEL: {53, 88, 89, 90},
                ROOT_PRIOR_GUIDED_LABEL: {88, 89, 0},
                T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL: {53, 88, 89, 90},
            },
            include_repair=include_repair,
        ),
    }


def _comparison(
    *,
    cohort_identity: str,
    count: int,
    record_range: str,
    workers: int,
    shards: int,
    win_indices: dict[str, set[int]],
    include_repair: bool,
    merged_from_record_ranges: list[str] | None = None,
) -> RootPriorGuidedSearchComparisonReport:
    labels = [
        BASELINE_ORACLE_LABEL,
        POST_SEARCH_MODEL_GUIDED_LABEL,
        ROOT_PRIOR_GUIDED_LABEL,
    ]
    if include_repair:
        labels.append(T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL)
    return build_root_prior_guided_search_comparison_report(
        arms=tuple(
            (
                label,
                label,
                _fixed_report(
                    label,
                    cohort_identity,
                    count,
                    win_indices.get(label, set()),
                ),
            )
            for label in labels
        ),
        comparison_config={
            "task_id": "T059",
            "run_scale": "fixed",
            "cohort_identity": cohort_identity,
            "cohort_total_record_count": count,
            "evaluated_record_count": count,
            "record_range": record_range,
            **(
                {"merged_from_record_ranges": merged_from_record_ranges}
                if merged_from_record_ranges is not None
                else {}
            ),
            "worker_count": workers,
            "shard_count": shards,
            "max_battle_steps": 200,
        },
    )


def _fixed_report(
    label: str,
    cohort_identity: str,
    count: int,
    win_indices: set[int],
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity=cohort_identity,
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        max_battle_steps=200,
        source_pool_format_version=4,
        selection_config={"selection_seed": 59},
        per_stratum_source_counts={"20/1/BOSS/CULTIST": count},
        battle_results=[
            _result(index, label, index in win_indices) for index in range(count)
        ],
        problems=[],
    )


def _result(index: int, label: str, won: bool) -> SingleBattleEvaluationResult:
    act = 2 if index >= 88 else 1
    room_type = "MONSTER" if act >= 2 else "BOSS"
    return SingleBattleEvaluationResult(
        cohort_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_seed=1000 + index,
        source_run_id=f"run-{index}",
        source_battle_index=index,
        structural_stratum=(20, act, room_type, "CULTIST"),
        structural_metadata={
            "ascension": 20,
            "act": act,
            "room_type": room_type,
            "encounter_id": "CULTIST",
            "distribution_kind": "natural_run",
            "selection_reasons": ["act2_plus" if act >= 2 else "act1_boss"],
        },
        restoration_method="portable_replay",
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        termination_status="win" if won else "loss",
        terminal_absolute_hp=20 + index if won else 0,
        hp_loss=50,
        decision_count=1,
        simulator_step_count=2,
        wall_clock_time_s=0.01,
        controller_compute_telemetry=_telemetry(label),
        public_context_status="available",
        public_context_replay_status="matched",
        structured_battle_outcome_status="available",
        structured_battle_outcome={"battle_outcome": "WIN" if won else "LOSS"},
        problems=[],
    )


def _controller_provenance(label: str) -> dict[str, object]:
    config: dict[str, object] = {
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "search_budget": {"simulations": 20},
    }
    if label in {
        POST_SEARCH_MODEL_GUIDED_LABEL,
        ROOT_PRIOR_GUIDED_LABEL,
        T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL,
    }:
        config["guidance_scorer"] = {
            "checkpoint_provenance": {
                "checkpoint_artifact_id": "torch-policy-value-checkpoint-v1-sha256:abc"
            }
        }
    if label == T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL:
        config.update(
            {
                "controller_version": (
                    T059_REPAIRED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
                ),
                "root_prior_allocation": {
                    "repair": {
                        "version": ROOT_PRIOR_ALLOCATION_REPAIR_VERSION,
                        "strategy": ROOT_PRIOR_ALLOCATION_REPAIR_STRATEGY,
                        "prior_entropy_temperature": 2.0,
                    },
                    "guardrail_revived": False,
                },
            }
        )
    return {"kind": label, "name": label, "config": config}


def _telemetry(label: str) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "model_calls": {"total": 1 if label != BASELINE_ORACLE_LABEL else 0},
            "root_visits": {"total": 20},
            "native_simulator_steps": {"total": 40},
            "root_mapping_failure_count": {"total": 0},
        }
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL}:
        decision = {
            "allocation_metadata": {
                "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
            },
            "prior_summary": {
                "positive_prior_count": 1,
                "provided_prior_count": 2,
            },
            "target": {
                "legal_action_index": 1,
                "visits": 12,
                "mean_value": 0.55,
                "selection_rule": "highest_mean",
                "action_identity": _identity("Defend", 1),
            },
            "allocation_rows": [],
            "oracle_search_report": {"root_mapping_failure_count": 0},
        }
        if label == T059_REPAIRED_ROOT_PRIOR_GUIDED_LABEL:
            decision["repair_config"] = {
                "version": ROOT_PRIOR_ALLOCATION_REPAIR_VERSION,
                "strategy": ROOT_PRIOR_ALLOCATION_REPAIR_STRATEGY,
                "prior_entropy_temperature": 2.0,
            }
            decision["repair_summary"] = {
                "changed_prior_count": 2,
                "l1_prior_delta": 0.15,
                "pre_repair_max_prior_probability": 0.9,
                "post_repair_max_prior_probability": 0.75,
            }
        telemetry["root_prior_guided_decision_reports"] = [decision]
    else:
        telemetry["oracle_search_decision_reports"] = [
            {
                "selected_legal_action_index": 0,
                "selection_rule": "highest_mean",
                "selected_visits": 10,
                "selected_mean_value": 0.5,
                "selected_action_identity": _identity("Strike", 0),
            }
        ]
    return telemetry


def _identity(label: str, index: int) -> dict[str, object]:
    return {
        "scope": "battle",
        "kind": "card",
        "label": label,
        "action_id": f"battle:{index}",
        "occurrence": 0,
        "stable_id": f"battle:{label.lower()}:0",
        "vocabulary_version": "unit-test",
        "status": "known",
    }


def _t058_report() -> T058RootPriorSelectedActionTelemetryReport:
    return T058RootPriorSelectedActionTelemetryReport(
        input_artifacts=[],
        prerequisite_summary={},
        cohort_summaries={},
        subset_summaries={
            "t053_disagreement_records": {
                "cohort_indices": [53, 54, 55, 87],
            }
        },
        per_record_selected_action_diagnostics=[],
        selected_action_availability={
            "record_count": 122,
            "available_record_count": 122,
            "exact_full_record_count": 11,
            "unavailable_record_count": 0,
            "exact_step_level_comparison_feasible_all": True,
        },
        first_divergence_summary={},
        recommendation={
            "recommendation_count": 1,
            "selected_next_path": "root-prior allocation repair experiment",
            "forbidden_claims": {"controller_promotion": False},
        },
        unavailable_diagnostics=[],
    )


def _verified_artifacts() -> list[dict[str, object]]:
    return [
        {"role": role, "sha256": f"{index:064x}"[-64:], "sha256_verified": True}
        for index, role in enumerate(_required_roles(), start=1)
    ]


def _required_roles() -> tuple[str, ...]:
    return (
        "t058_selected_action_telemetry_report",
        "t058_retention_manifest",
        "t048_current_t058_comparison",
        "t048_assist0_t058_comparison",
        "t052_t058_comparison",
        "t048_current_fixed_cohort",
        "t048_assist0_fixed_cohort",
        "t052_boss_later_act_fixed_cohort",
        "t043_assist0_smoke_checkpoint",
        "t043_runs1000_assist0_checkpoint",
        "t059_current_repair_comparison",
        "t059_assist0_repair_comparison",
        "t059_t052_repair_comparison",
    )


def _write_jsonl_metadata(path: Path, schema_id: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps({"type": "metadata", "metadata": {"schema_id": schema_id}})
        )
        stream.write("\n")


def _write_fixed_cohort_metadata(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(
                {
                    "type": "metadata",
                    "metadata": {
                        "format_version": 3,
                        "record_count": 0,
                    },
                }
            )
        )
        stream.write("\n")


def _artifact_specs(paths: dict[str, Path]) -> list[list[str]]:
    return [[role, str(paths[role]), _sha256(paths[role])] for role in paths]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
