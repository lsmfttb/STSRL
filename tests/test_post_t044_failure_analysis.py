from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.post_t044_failure_analysis import (
    run_post_t044_failure_analysis_from_paths,
)
from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    BASELINE_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_V2_LABEL,
    RAW_CHECKPOINT_POLICY_LABEL,
    SCRIPTED_POLICY_LABEL,
    build_de_assisted_fixed_cohort_comparison_report,
    dump_de_assisted_fixed_cohort_comparison_jsonl,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.online_controller import (
    NATIVE_SEARCH_INFORMATION_REGIME,
    PUBLIC_POLICY_INFORMATION_REGIME,
)
from sts_combat_rl.sim.post_t044_failure_analysis import (
    POST_T044_FAILURE_ANALYSIS_SCHEMA_ID,
    build_post_t044_failure_analysis_report,
    format_post_t044_failure_analysis_report,
    load_post_t044_failure_analysis_report_json,
)
from sts_combat_rl.sim.resource_outcome import unavailable_battle_resource_outcome
from sts_combat_rl.sim.search_telemetry import SearchDecisionTelemetry


def test_post_t044_analysis_reports_override_outcomes_taxonomy_and_roundtrip(
    tmp_path: Path,
) -> None:
    comparison_path = _write_comparison(tmp_path / "comparison.jsonl")
    calibration_path = tmp_path / "calibration.json"
    calibration_path.write_text(
        json.dumps(
            {
                "schema_id": "teacher-guidance-calibration-report-v1",
                "format_version": 1,
                "checkpoint_reports": [
                    {
                        "evaluated_record_count": 2,
                        "skipped_record_count": 1,
                        "problems": ["one skipped row was invalid"],
                        "teacher_target_metrics": {
                            "top1_agreement_count": 1,
                            "top_k_agreement_count": 2,
                        },
                        "calibration": {
                            "expected_calibration_error": 0.125,
                        },
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "post-t044-analysis.json"

    report = run_post_t044_failure_analysis_from_paths(
        comparison_paths=[comparison_path],
        output_path=output_path,
        linked_artifact_specs=[("calibration", str(calibration_path))],
    )

    assert report.command_passed
    assert output_path.exists()
    assert report.override_diagnostics["comparable_decision_count"] == 2
    assert report.override_diagnostics["override_decision_count"] == 1
    assert report.outcome_delta_diagnostics["model_guided_better_battle_count"] == 1
    assert report.outcome_delta_diagnostics["same_outcome_battle_count"] == 1
    assert report.raw_policy_diagnostics["raw_worse_battle_count"] == 1
    assert (
        report.raw_policy_diagnostics["action_group_counts"]["action_kind"]["card"] == 1
    )
    assert report.model_alignment_diagnostics["evaluated_decision_count"] == 2
    assert report.model_alignment_diagnostics["model_top_native_top3_count"] == 2
    assert (
        report.model_alignment_diagnostics["teacher_calibration"]["status"]
        == "available"
    )
    assert report.failure_taxonomy["integration-too-late"]["evidence_count"] == 2
    assert report.recommendation["recommended_paths"][0]["path"] == (
        "native root-prior allocation surface"
    )

    loaded = load_post_t044_failure_analysis_report_json(
        StringIO(output_path.read_text(encoding="utf-8"))
    )
    assert loaded.schema_id == POST_T044_FAILURE_ANALYSIS_SCHEMA_ID
    text = format_post_t044_failure_analysis_report(loaded)
    assert "Post-T044 failure analysis" in text
    assert "no controller, simulator, training" in text
    assert "promoted" not in text.lower()


def test_post_t044_analysis_marks_missing_decision_fields_unavailable(
    tmp_path: Path,
) -> None:
    comparison_path = _write_comparison(
        tmp_path / "missing-telemetry.jsonl",
        include_search_telemetry=False,
    )

    report = run_post_t044_failure_analysis_from_paths(
        comparison_paths=[comparison_path],
        output_path=tmp_path / "analysis.json",
    )

    assert report.command_passed
    assert report.override_diagnostics["status"] == "unavailable"
    assert any(
        item["missing_field"]
        == "baseline_oracle_search.controller_compute_telemetry.search_decision_telemetry"
        for item in report.unavailable_diagnostics
    )
    assert report.model_alignment_diagnostics["status"] == "unavailable"


def test_post_t044_analysis_rejects_missing_required_arm() -> None:
    comparison = build_de_assisted_fixed_cohort_comparison_report(
        arms=[
            (
                BASELINE_ORACLE_LABEL,
                "baseline",
                _fixed_report(BASELINE_ORACLE_LABEL, NATIVE_SEARCH_INFORMATION_REGIME),
            ),
            (
                MODEL_GUIDED_ORACLE_V2_LABEL,
                "guided",
                _fixed_report(
                    MODEL_GUIDED_ORACLE_V2_LABEL,
                    NATIVE_SEARCH_INFORMATION_REGIME,
                ),
            ),
            (
                RAW_CHECKPOINT_POLICY_LABEL,
                "raw",
                _fixed_report(
                    RAW_CHECKPOINT_POLICY_LABEL, PUBLIC_POLICY_INFORMATION_REGIME
                ),
            ),
        ],
        comparison_config={"checkpoint_provenance": {}},
    )

    with pytest.raises(ValueError, match="missing required controller arm"):
        build_post_t044_failure_analysis_report(
            [({"path": "missing.jsonl"}, comparison)]
        )


def test_post_t044_analysis_rejects_source_mismatches() -> None:
    baseline = _fixed_report(BASELINE_ORACLE_LABEL, NATIVE_SEARCH_INFORMATION_REGIME)
    model = _fixed_report(
        MODEL_GUIDED_ORACLE_V2_LABEL,
        NATIVE_SEARCH_INFORMATION_REGIME,
        source_prefix="other",
    )
    comparison = build_de_assisted_fixed_cohort_comparison_report(
        arms=[
            (BASELINE_ORACLE_LABEL, "baseline", baseline),
            (MODEL_GUIDED_ORACLE_V2_LABEL, "guided", model),
            (
                RAW_CHECKPOINT_POLICY_LABEL,
                "raw",
                _fixed_report(
                    RAW_CHECKPOINT_POLICY_LABEL, PUBLIC_POLICY_INFORMATION_REGIME
                ),
            ),
            (
                SCRIPTED_POLICY_LABEL,
                "scripted",
                _fixed_report(SCRIPTED_POLICY_LABEL, PUBLIC_POLICY_INFORMATION_REGIME),
            ),
        ],
        comparison_config={"checkpoint_provenance": {}},
    )

    with pytest.raises(ValueError, match="source/cohort mismatch"):
        build_post_t044_failure_analysis_report(
            [({"path": "mismatch.jsonl"}, comparison)]
        )


def test_cli_post_t044_failure_analysis_routes_to_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "analysis.json"
    comparison_path = tmp_path / "comparison.jsonl"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["comparison_paths"] == [comparison_path]
        assert kwargs["output_path"] == output_path
        assert kwargs["linked_artifact_specs"] == [["calibration", "cal.json"]]
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_post_t044_failure_analysis_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_post_t044_failure_analysis_command",
        lambda report: "Post-T044 failure analysis\ncommand passed: yes",
    )

    rc = main(
        [
            "--post-t044-failure-analysis-report",
            str(output_path),
            "--post-t044-comparison",
            str(comparison_path),
            "--post-t044-linked-artifact",
            "calibration",
            "cal.json",
            "--log-file",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "Post-T044 failure analysis" in captured.err


def test_cli_post_t044_failure_analysis_requires_comparison(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--post-t044-failure-analysis-report",
            str(tmp_path / "analysis.json"),
        ]
    )

    assert validate_cli_args(args) == (
        "--post-t044-failure-analysis-report requires at least one "
        "--post-t044-comparison"
    )


def _write_comparison(
    path: Path,
    *,
    include_search_telemetry: bool = True,
) -> Path:
    comparison = build_de_assisted_fixed_cohort_comparison_report(
        arms=[
            (
                BASELINE_ORACLE_LABEL,
                "baseline_oracle_search",
                _fixed_report(
                    BASELINE_ORACLE_LABEL,
                    NATIVE_SEARCH_INFORMATION_REGIME,
                    statuses=("loss", "win"),
                    selected_indices=(0, 0),
                    include_search_telemetry=include_search_telemetry,
                ),
            ),
            (
                MODEL_GUIDED_ORACLE_V2_LABEL,
                "guided_v2",
                _fixed_report(
                    MODEL_GUIDED_ORACLE_V2_LABEL,
                    NATIVE_SEARCH_INFORMATION_REGIME,
                    statuses=("win", "win"),
                    selected_indices=(1, 0),
                    include_search_telemetry=include_search_telemetry,
                    include_model_alignment=include_search_telemetry,
                ),
            ),
            (
                RAW_CHECKPOINT_POLICY_LABEL,
                "raw_policy",
                _fixed_report(
                    RAW_CHECKPOINT_POLICY_LABEL,
                    PUBLIC_POLICY_INFORMATION_REGIME,
                    statuses=("loss", "loss"),
                    raw_action_categories=("Defend_R", "end_turn"),
                ),
            ),
            (
                SCRIPTED_POLICY_LABEL,
                "scripted_policy",
                _fixed_report(
                    SCRIPTED_POLICY_LABEL,
                    PUBLIC_POLICY_INFORMATION_REGIME,
                    statuses=("win", "loss"),
                ),
            ),
        ],
        comparison_config={
            "task_id": "T044",
            "run_scale": "smoke",
            "checkpoint_provenance": {
                MODEL_GUIDED_ORACLE_V2_LABEL: {
                    "checkpoint_artifact_id": "checkpoint-sha256:abc",
                    "trainer_input_sha256": "trainer",
                },
                RAW_CHECKPOINT_POLICY_LABEL: {
                    "checkpoint_artifact_id": "checkpoint-sha256:abc",
                    "trainer_input_sha256": "trainer",
                },
            },
        },
    )
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_de_assisted_fixed_cohort_comparison_jsonl(comparison, stream)
    return path


def _fixed_report(
    label: str,
    regime: str,
    *,
    statuses: tuple[str, str] = ("loss", "win"),
    selected_indices: tuple[int, int] = (0, 0),
    include_search_telemetry: bool = True,
    include_model_alignment: bool = False,
    raw_action_categories: tuple[str, str] | None = None,
    source_prefix: str = "source",
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity="cohort-a",
        controller_provenance={
            "kind": label,
            "name": label,
            "config": {
                "information_regime": regime,
                "search_budget": {"simulations": 3},
            },
        },
        information_regime=regime,
        action_space_config={"excluded_kinds": []},
        max_battle_steps=10,
        source_pool_format_version=3,
        selection_config={"selection_seed": 1},
        per_stratum_source_counts={"20/1/Monster/Cultist": 2},
        battle_results=[
            _battle_result(
                index,
                label=label,
                regime=regime,
                status=statuses[index],
                selected_index=selected_indices[index],
                include_search_telemetry=include_search_telemetry,
                include_model_alignment=include_model_alignment,
                raw_action_category=(
                    raw_action_categories[index] if raw_action_categories else None
                ),
                source_prefix=source_prefix,
            )
            for index in range(2)
        ],
    )


def _battle_result(
    index: int,
    *,
    label: str,
    regime: str,
    status: str,
    selected_index: int,
    include_search_telemetry: bool,
    include_model_alignment: bool,
    raw_action_category: str | None,
    source_prefix: str,
) -> SingleBattleEvaluationResult:
    telemetry: dict[str, object] | None = None
    if include_search_telemetry and regime == NATIVE_SEARCH_INFORMATION_REGIME:
        telemetry = {
            "search_decision_telemetry": [
                _search_telemetry(
                    selected_index,
                    controller_kind=label,
                    model_calls=1 if label == MODEL_GUIDED_ORACLE_V2_LABEL else 0,
                    include_root_only_unavailable=(
                        label == MODEL_GUIDED_ORACLE_V2_LABEL
                    ),
                )
            ]
        }
    if include_model_alignment:
        telemetry = dict(telemetry or {})
        telemetry["model_guidance_inference"] = [
            {
                "action_scores": [
                    _action_score(0, "card", 0.2, card_id="Strike_R"),
                    _action_score(1, "card", 0.8, card_id="Defend_R"),
                ]
            }
        ]
        telemetry["model_guided_oracle_root_scores"] = [
            [
                {
                    "legal_action_index": 0,
                    "eligible": True,
                    "native_visits": 2,
                    "native_mean_value": 0.9,
                    "model_policy_probability": 0.2,
                },
                {
                    "legal_action_index": 1,
                    "eligible": True,
                    "native_visits": 1,
                    "native_mean_value": 0.1,
                    "model_policy_probability": 0.8,
                },
            ]
        ]
    if raw_action_category is not None:
        telemetry = {
            "search_guidance_policy_decision_reports": [
                {
                    "selected_score": _raw_selected_score(raw_action_category),
                }
            ]
        }
    outcome_status, outcome_payload = unavailable_battle_resource_outcome(
        "fixture_no_structured_resource_payload"
    )
    return SingleBattleEvaluationResult(
        cohort_index=index,
        source_checkpoint_id=f"{source_prefix}-{index}",
        source_seed=100 + index,
        source_run_id=f"run-{index}",
        source_battle_index=index,
        structural_stratum=(20, 1, "Monster", "Cultist"),
        structural_metadata={
            "act": 1,
            "room_type": "Monster",
            "encounter_id": "Cultist",
            "distribution_kind": "assisted_run",
            "assistance_level": "assist_hp50" if index else "assist_0",
        },
        restoration_method="portable_replay",
        controller_provenance={"kind": label, "name": label},
        information_regime=regime,
        action_space_config={"excluded_kinds": []},
        termination_status=status,
        terminal_absolute_hp=30 + index + (5 if status == "win" else 0),
        hp_loss=10 - index,
        decision_count=1,
        simulator_step_count=2,
        wall_clock_time_s=0.01,
        controller_compute_telemetry=telemetry,
        battle_initial_hp=40,
        battle_initial_max_hp=80,
        structured_battle_outcome_status=outcome_status,
        structured_battle_outcome=outcome_payload,
    )


def _search_telemetry(
    selected_index: int,
    *,
    controller_kind: str,
    model_calls: int,
    include_root_only_unavailable: bool,
) -> dict[str, object]:
    unavailable = (
        {
            "model_guided_allocation": (
                "current native battle_search API does not accept model priors"
            )
        }
        if include_root_only_unavailable
        else {}
    )
    return SearchDecisionTelemetry(
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        controller_kind=controller_kind,
        search_kind="native_random_terminal_playout",
        search_backend={"native_api": "fake-battle-search"},
        requested_budget={"unit": "native_random_terminal_playouts", "amount": 3},
        simulations_requested=3,
        root_visits=3,
        root_action_count=2,
        legal_action_count=2,
        eligible_action_count=2,
        visited_action_count=2,
        visited_eligible_action_count=2,
        native_simulator_steps=30,
        model_calls=model_calls,
        wall_clock_time_s=0.01,
        root_value_min=0.1,
        root_value_max=0.9,
        root_value_spread=0.8,
        root_decision_gap=0.8,
        unsearched_legal_action_count=0,
        unmapped_search_edge_count=0,
        unmapped_root_row_count=0,
        root_mapping_failure_count=0,
        selection_rule="highest_mean",
        selected_legal_action_index=selected_index,
        selected_visits=1,
        selected_mean_value=0.9 if selected_index == 0 else 0.1,
        unavailable_fields=unavailable,
    ).to_dict()


def _action_score(
    index: int,
    kind: str,
    probability: float,
    *,
    card_id: str,
) -> dict[str, object]:
    return {
        "legal_action_index": index,
        "action_kind": kind,
        "eligible": True,
        "policy_logit": probability,
        "policy_probability": probability,
        "action_identity": {
            "kind": kind,
            "card_id": card_id,
            "stable_id": f"{kind}:{card_id}:{index}",
        },
    }


def _raw_selected_score(category: str) -> dict[str, object]:
    if category == "end_turn":
        return {
            "legal_action_index": 0,
            "action_kind": "end",
            "eligible": True,
            "policy_logit": 1.0,
            "policy_probability": 1.0,
            "action_identity": {
                "kind": "end",
                "action_id": "end_turn",
                "stable_id": "end:end_turn:0",
            },
        }
    return _action_score(0, "card", 1.0, card_id=category)
