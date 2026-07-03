from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.t054_guardrailed_root_prior_repair import (
    run_t054_guardrailed_root_prior_repair_from_paths,
    run_t054_retention_manifest_from_paths,
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
    GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME,
    GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION,
    ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY,
    ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    RootPriorGuidedSearchComparisonReport,
    build_root_prior_guided_search_comparison_report,
    dump_root_prior_guided_search_comparison_jsonl,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053RootPriorFailureAnalysisReport,
    dump_t053_root_prior_failure_analysis_report_json,
)
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    T054_REPAIR_REPORT_SCHEMA_ID,
    build_t054_guardrailed_root_prior_repair_report,
    dump_t054_guardrailed_root_prior_repair_report_json,
    format_t054_guardrailed_root_prior_repair_report,
    load_t054_guardrailed_root_prior_repair_report_json,
)


def test_t054_report_validates_subsets_guardrail_and_roundtrip() -> None:
    t052_comparison = _comparison(include_guardrail=False, task_id="T052")
    t054_comparison = _comparison(include_guardrail=True, task_id="T054")
    t053_report = _t053_report()

    report = build_t054_guardrailed_root_prior_repair_report(
        input_artifacts=_verified_artifacts(),
        t052_comparison=t052_comparison,
        t052_result_summary={"schema_id": "t052-result-summary-v1"},
        t053_report=t053_report,
        t054_comparison=t054_comparison,
    )

    assert report.command_passed
    assert report.schema_id == T054_REPAIR_REPORT_SCHEMA_ID
    assert report.t054_comparison_summary["evaluated_record_count"] == 93
    assert report.subset_summaries["t053_disagreement_indices"]["record_count"] == 4
    assert report.subset_summaries["act2_plus"]["record_count"] == 5
    assert (
        report.allocation_telemetry_summary["guardrail_telemetry"]["decision_count"]
        == 93
    )
    assert (
        report.guardrail_configuration["controller_version"]
        == GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
    )
    rows = {row["cohort_index"]: row for row in report.disagreement_index_results}
    assert rows[53]["repair_classification"] == "fixed_or_improved_vs_root_prior"
    assert rows[55]["repair_classification"] == "unchanged_vs_existing_root_prior"
    assert report.recommendation["recommendation_count"] == 1
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False

    buffer = StringIO()
    dump_t054_guardrailed_root_prior_repair_report_json(report, buffer)
    loaded = load_t054_guardrailed_root_prior_repair_report_json(
        StringIO(buffer.getvalue())
    )
    text = format_t054_guardrailed_root_prior_repair_report(loaded)
    assert "T054 guardrailed root-prior repair report" in text
    assert "no controller promotion" in text
    assert "promoted" not in text.lower()


def test_t054_report_rejects_missing_guardrailed_arm() -> None:
    with pytest.raises(ValueError, match="missing required T054 comparison arm"):
        build_t054_guardrailed_root_prior_repair_report(
            input_artifacts=_verified_artifacts(),
            t052_comparison=_comparison(include_guardrail=False, task_id="T052"),
            t052_result_summary={"schema_id": "t052-result-summary-v1"},
            t053_report=_t053_report(),
            t054_comparison=_comparison(include_guardrail=False, task_id="T054"),
        )


def test_t054_command_hash_checks_and_writes_report(tmp_path: Path) -> None:
    paths = _write_t054_inputs(tmp_path)
    output_path = tmp_path / "t054-report.json"

    report = run_t054_guardrailed_root_prior_repair_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=output_path,
    )

    assert report.command_passed
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_id"] == (
        T054_REPAIR_REPORT_SCHEMA_ID
    )


def test_t054_command_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t054_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[-1][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t054_guardrailed_root_prior_repair_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t054-report.json",
        )


def test_t054_retention_manifest_records_generated_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text(
        '{"schema_id":"t054-guardrailed-root-prior-repair-report-v1"}\n'
    )
    output_path = tmp_path / "manifest.json"

    manifest = run_t054_retention_manifest_from_paths(
        output_path=output_path,
        artifact_specs=[
            [
                "repair_report",
                str(artifact),
                "t054-guardrailed-root-prior-repair-report-v1",
            ]
        ],
        command_specs=[["repair_report", "python -m sts_combat_rl.cli ..."]],
        stage_specs=[["comparison", "16", "16", "0:93", "12.5"]],
        note_specs=[["runtime", "unit-test"]],
    )

    assert output_path.exists()
    assert manifest["schema_id"] == "t054-retention-manifest-v1"
    assert manifest["artifacts"][0]["sha256"] == _sha256(artifact)
    assert manifest["runtime_stages"][0]["workers"] == 16


def test_cli_t054_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t054-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert [spec[0] for spec in kwargs["artifact_specs"]] == [
            "t052_retention_manifest",
            "t052_fixed_cohort",
            "t052_root_prior_guided_comparison",
            "t052_result_summary",
            "t053_failure_analysis",
            "t054_guardrailed_comparison",
        ]
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t054_guardrailed_root_prior_repair_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t054_guardrailed_root_prior_repair_command",
        lambda report: "T054 guardrailed root-prior repair report\ncommand passed: yes",
    )

    rc = main(
        [
            "--t054-guardrailed-root-prior-repair-report",
            str(output_path),
            *[
                item
                for role, digest in [
                    ("t052_retention_manifest", "a" * 64),
                    ("t052_fixed_cohort", "b" * 64),
                    ("t052_root_prior_guided_comparison", "c" * 64),
                    ("t052_result_summary", "d" * 64),
                    ("t053_failure_analysis", "e" * 64),
                    ("t054_guardrailed_comparison", "f" * 64),
                ]
                for item in [
                    "--t054-input-artifact",
                    role,
                    f"{role}.json",
                    digest,
                ]
            ],
            "--log-file",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "T054 guardrailed root-prior repair report" in captured.err


def _comparison(
    *,
    include_guardrail: bool,
    task_id: str,
) -> RootPriorGuidedSearchComparisonReport:
    arms = [
        (
            BASELINE_ORACLE_LABEL,
            "baseline_oracle_search",
            _fixed_report(BASELINE_ORACLE_LABEL),
        ),
        (
            POST_SEARCH_MODEL_GUIDED_LABEL,
            "post_search_model_guided_oracle_search_v2",
            _fixed_report(POST_SEARCH_MODEL_GUIDED_LABEL),
        ),
        (
            ROOT_PRIOR_GUIDED_LABEL,
            "native_root_prior_allocation_from_checkpoint_priors",
            _fixed_report(ROOT_PRIOR_GUIDED_LABEL),
        ),
    ]
    if include_guardrail:
        arms.append(
            (
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                "guardrailed_native_root_prior_allocation_from_checkpoint_priors",
                _fixed_report(GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL),
            )
        )
    return build_root_prior_guided_search_comparison_report(
        arms=arms,
        comparison_config={
            "task_id": task_id,
            "run_scale": "fixed",
            "cohort_path": "artifacts/t052-fixed-cohort.jsonl",
            "cohort_identity": "cohort-t054-fixture",
            "cohort_total_record_count": 93,
            "evaluated_record_count": 93,
            "record_range": "all",
            "worker_count": 16,
            "shard_count": 16,
        },
    )


def _fixed_report(label: str) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity="cohort-t054-fixture",
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        max_battle_steps=200,
        source_pool_format_version=4,
        selection_config={"selection_seed": 52},
        per_stratum_source_counts={"20/1/BOSS/HEXAGHOST": 88, "20/2/MONSTER/BYRD": 5},
        battle_results=[_result(index, label) for index in range(93)],
        problems=[],
    )


def _controller_provenance(label: str) -> dict[str, object]:
    config: dict[str, object] = {
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "search_budget": {
            "simulations": 20,
            "budget_unit": "native_random_terminal_playouts",
        },
    }
    if label in {
        POST_SEARCH_MODEL_GUIDED_LABEL,
        ROOT_PRIOR_GUIDED_LABEL,
        GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    }:
        config["guidance_scorer"] = {"checkpoint_provenance": _checkpoint()}
    if label == GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL:
        config.update(
            {
                "controller_version": (
                    GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
                ),
                "root_prior_allocation": {
                    "guardrail": _guardrail_config(),
                },
            }
        )
        return {
            "kind": "guardrailed_root_prior_guided_oracle_battle_search",
            "name": f"{GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME}_s20",
            "config": config,
        }
    return {
        "kind": label,
        "name": label,
        "config": config,
    }


def _result(index: int, label: str) -> SingleBattleEvaluationResult:
    outcome, hp = _outcome(index, label)
    act = 2 if index >= 88 else 1
    room_type = "MONSTER" if act >= 2 else "BOSS"
    return SingleBattleEvaluationResult(
        cohort_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_seed=1000 + index,
        source_run_id=f"seed-{index}-run-0",
        source_battle_index=index,
        structural_stratum=(20, act, room_type, "HEXAGHOST" if act == 1 else "BYRD"),
        structural_metadata={
            "ascension": 20,
            "act": act,
            "room_type": room_type,
            "encounter_id": "HEXAGHOST" if act == 1 else "BYRD",
            "t052_selection_reasons": ["act2_plus"] if act >= 2 else ["act1_boss"],
        },
        restoration_method="portable_replay",
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        termination_status=outcome,
        terminal_absolute_hp=hp,
        hp_loss=70 - hp if hp is not None else None,
        decision_count=1,
        simulator_step_count=2,
        wall_clock_time_s=0.01,
        controller_compute_telemetry=_telemetry(index, label),
        public_context_status="legacy_unavailable",
        public_context_replay_status="not_checked",
        structured_battle_outcome_status="legacy_unavailable",
        structured_battle_outcome={},
        problems=[],
    )


def _outcome(index: int, label: str) -> tuple[str, int]:
    if index in {53, 55}:
        if label in {BASELINE_ORACLE_LABEL, POST_SEARCH_MODEL_GUIDED_LABEL}:
            return "win", 20
        if label == GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL and index == 53:
            return "win", 18
        return "loss", 0
    if index == 54:
        if label == ROOT_PRIOR_GUIDED_LABEL:
            return "win", 24
        if label == GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL:
            return "win", 22
        return "win", 12
    if index == 87:
        if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
            return "win", 16
        return "loss", 0
    if index in {88, 89, 90}:
        return "win", 10
    return "loss", 0


def _telemetry(index: int, label: str) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "model_calls": {"total": 1 if label != BASELINE_ORACLE_LABEL else 0},
            "native_simulator_steps": {"total": 20},
            "root_mapping_failure_count": {"total": 0},
            "unsearched_legal_action_count": {"total": 0},
            "root_visits": {"total": 20},
        }
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        decision = {
            "allocation_metadata": {
                "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
            },
            "allocation_rows": [
                {
                    "legal_action_index": 0,
                    "root_prior": 0.65,
                    "allocated_root_visits": 13,
                    "visits": 13,
                },
                {
                    "legal_action_index": 1,
                    "root_prior": 0.35,
                    "allocated_root_visits": 7,
                    "visits": 7,
                },
            ],
            "prior_summary": {
                "legal_action_count": 2,
                "eligible_action_count": 2,
                "positive_prior_count": 2,
                "provided_prior_count": 2,
                "max_prior_probability": 0.65,
            },
            "target": {"legal_action_index": index % 2},
        }
        if label == GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL:
            decision["guardrail_config"] = _guardrail_config()
            decision["guardrail_summary"] = {
                "changed_prior_count": 2,
                "l1_prior_delta": 0.4,
                "pre_guardrail_max_prior_probability": 0.95,
                "post_guardrail_max_prior_probability": 0.65,
            }
        telemetry["root_prior_guided_decision_reports"] = [decision]
    return telemetry


def _checkpoint() -> dict[str, object]:
    return {
        "checkpoint_schema_id": "torch-policy-value-checkpoint-v1",
        "checkpoint_artifact_id": "checkpoint-sha256:unit",
        "trainer_input_sha256": "trainer",
    }


def _guardrail_config() -> dict[str, object]:
    return {
        "version": ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION,
        "strategy": ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY,
        "uniform_blend_weight": 0.35,
        "max_prior_probability": 0.65,
    }


def _t053_report() -> T053RootPriorFailureAnalysisReport:
    records = []
    for index in (53, 54, 55, 87):
        records.append(
            {
                "cohort_index": index,
                "taxonomy_labels": (
                    ["harmful_root_prior_allocation"]
                    if index in {53, 55}
                    else ["no_op_or_ineffective_root_prior_allocation"]
                    if index == 54
                    else ["beneficial_root_prior_allocation"]
                ),
                "outcome_delta": {"fixture": True},
            }
        )
    return T053RootPriorFailureAnalysisReport(
        input_artifacts=[],
        comparison_summary={"cohort_identity": "cohort-t054-fixture"},
        t052_result_summary={"schema_id": "t052-result-summary-v1"},
        disagreement_summary={"disagreement_count": 4, "evaluated_record_count": 93},
        disagreement_records=records,
        subset_summaries={},
        allocation_telemetry_summary={},
        action_comparison_diagnostics={},
        failure_taxonomy={},
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": (
                "guardrailed root-prior allocation repair experiment"
            ),
        },
    )


def _verified_artifacts() -> list[dict[str, object]]:
    return [
        {"role": role, "path": f"{role}.json", "sha256_verified": True}
        for role in (
            "t052_retention_manifest",
            "t052_fixed_cohort",
            "t052_root_prior_guided_comparison",
            "t052_result_summary",
            "t053_failure_analysis",
            "t054_guardrailed_comparison",
        )
    ]


def _write_t054_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "t052_retention_manifest": tmp_path / "t052-retention-manifest.json",
        "t052_fixed_cohort": tmp_path / "t052-fixed-cohort.jsonl",
        "t052_root_prior_guided_comparison": tmp_path / "t052-comparison.jsonl",
        "t052_result_summary": tmp_path / "t052-result-summary.json",
        "t053_failure_analysis": tmp_path / "t053-report.json",
        "t054_guardrailed_comparison": tmp_path / "t054-comparison.jsonl",
    }
    paths["t052_retention_manifest"].write_text(
        '{"schema_id":"t052-retention-manifest-v1"}\n',
        encoding="utf-8",
    )
    paths["t052_fixed_cohort"].write_text(
        '{"type":"metadata","metadata":{"schema_id":"fixed-cohort-v1"}}\n',
        encoding="utf-8",
    )
    paths["t052_result_summary"].write_text(
        '{"schema_id":"t052-result-summary-v1"}\n',
        encoding="utf-8",
    )
    with paths["t052_root_prior_guided_comparison"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_root_prior_guided_search_comparison_jsonl(
            _comparison(include_guardrail=False, task_id="T052"),
            stream,
        )
    with paths["t054_guardrailed_comparison"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_root_prior_guided_search_comparison_jsonl(
            _comparison(include_guardrail=True, task_id="T054"),
            stream,
        )
    with paths["t053_failure_analysis"].open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        dump_t053_root_prior_failure_analysis_report_json(_t053_report(), stream)
    return paths


def _artifact_specs(paths: dict[str, Path]) -> list[list[str]]:
    return [[role, str(path), _sha256(path)] for role, path in paths.items()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
