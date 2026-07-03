from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t057_existing_root_prior_telemetry_diagnostic import (
    run_t057_existing_root_prior_telemetry_diagnostic_from_paths,
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
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055GuardrailedRootPriorScaleValidationReport,
    dump_t055_guardrailed_root_prior_scale_validation_report_json,
)
from sts_combat_rl.sim.t056_post_t055_root_prior_path_selection import (
    T056PostT055RootPriorPathSelectionReport,
    dump_t056_post_t055_root_prior_path_selection_report_json,
)
from sts_combat_rl.sim.t057_existing_root_prior_telemetry_diagnostic import (
    T057_REQUIRED_INPUT_ROLES,
    T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID,
    format_t057_existing_root_prior_telemetry_diagnostic_report,
    load_t057_existing_root_prior_telemetry_diagnostic_report_json,
)


_CHECKPOINT_SHA256 = hashlib.sha256(b"checkpoint").hexdigest()


def test_t057_report_separates_evidence_and_recommends_one_telemetry_path(
    tmp_path: Path,
) -> None:
    paths = _write_t057_inputs(tmp_path)

    report = run_t057_existing_root_prior_telemetry_diagnostic_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=tmp_path / "t057-report.json",
    )

    assert report.command_passed
    assert report.schema_id == T057_TELEMETRY_DIAGNOSTIC_SCHEMA_ID
    assert (
        report.prerequisite_summary["t056_selected_next_path"]
        == "existing-root-prior allocation/telemetry diagnostic"
    )
    assert report.prerequisite_summary["guardrail_branch_closed"] is True
    assert set(report.evidence_family_summaries) == {
        "t048_positive_fixed_cohort_signal",
        "t052_t053_later_act_boss_diagnostic",
        "t055_guardrail_closure_context",
    }
    assert set(report.subset_summaries) == {
        "t048_current_t046_compatible",
        "t048_assist0_runs1000",
        "t052_boss_only",
        "t052_act2_plus",
        "t053_disagreement_records",
    }
    assert (
        report.allocation_telemetry_summary["all_existing_root_prior"]["decision_count"]
        == 122
    )
    assert (
        report.selected_action_availability["exact_step_level_comparison_feasible_all"]
        is False
    )
    assert (
        report.diagnostic_taxonomy["telemetry_insufficient_to_assign_cause"]["status"]
        == "supported"
    )
    assert (
        report.recommendation["selected_next_path"]
        == "root-prior selected-action telemetry instrumentation or replay diagnostic"
    )
    assert report.recommendation["recommendation_count"] == 1
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False
    assert any(
        item["diagnostic"] == "exact_all_arm_step_level_selected_action_comparison"
        for item in report.unavailable_diagnostics
    )

    loaded = load_t057_existing_root_prior_telemetry_diagnostic_report_json(
        StringIO((tmp_path / "t057-report.json").read_text(encoding="utf-8"))
    )
    text = format_t057_existing_root_prior_telemetry_diagnostic_report(loaded)
    assert "T057 existing root-prior allocation telemetry diagnostic" in text
    assert "no simulator" in text
    assert "selected next path: root-prior selected-action telemetry" in text


def test_t057_rejects_non_t056_existing_root_prior_recommendation(
    tmp_path: Path,
) -> None:
    paths = _write_t057_inputs(tmp_path, t056_next="complete-run reachability")

    with pytest.raises(ValueError, match="T056 selected path"):
        run_t057_existing_root_prior_telemetry_diagnostic_from_paths(
            artifact_specs=_artifact_specs(paths),
            output_path=tmp_path / "t057-report.json",
        )


def test_t057_command_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t057_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[0][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t057_existing_root_prior_telemetry_diagnostic_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t057-report.json",
        )


def test_t057_rejects_wrong_comparison_task_id(tmp_path: Path) -> None:
    paths = _write_t057_inputs(tmp_path)
    with paths["t048_current_reference_comparison"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_root_prior_guided_search_comparison_jsonl(
            _comparison(
                include_guardrail=False,
                task_id="T047",
                cohort_identity="875ea52e3df4cb93",
                count=8,
                record_range="0:8",
                wins={
                    BASELINE_ORACLE_LABEL: 5,
                    POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                    ROOT_PRIOR_GUIDED_LABEL: 6,
                },
            ),
            stream,
        )

    with pytest.raises(ValueError, match="task_id"):
        run_t057_existing_root_prior_telemetry_diagnostic_from_paths(
            artifact_specs=_artifact_specs(paths),
            output_path=tmp_path / "t057-report.json",
        )


def test_cli_t057_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t057-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert [spec[0] for spec in kwargs["artifact_specs"]] == list(
            T057_REQUIRED_INPUT_ROLES
        )
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t057_existing_root_prior_telemetry_diagnostic_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t057_existing_root_prior_telemetry_diagnostic_command",
        lambda report: "T057 existing root-prior allocation telemetry diagnostic",
    )

    rc = main(
        [
            "--t057-existing-root-prior-telemetry-diagnostic-report",
            str(output_path),
            *[
                item
                for index, role in enumerate(T057_REQUIRED_INPUT_ROLES)
                for item in [
                    "--t057-input-artifact",
                    role,
                    f"{role}.json",
                    f"{index + 1:064x}",
                ]
            ],
            "--log-file",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "T057 existing root-prior allocation telemetry diagnostic" in captured.err


def test_cli_t057_requires_nine_artifacts(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--t057-existing-root-prior-telemetry-diagnostic-report",
            str(tmp_path / "t057-report.json"),
        ]
    )

    assert validate_cli_args(args) == (
        "--t057-existing-root-prior-telemetry-diagnostic-report "
        "requires exactly nine --t057-input-artifact values"
    )


def _write_t057_inputs(
    tmp_path: Path,
    *,
    t056_next: str = "existing-root-prior allocation/telemetry diagnostic",
) -> dict[str, Path]:
    paths = {role: tmp_path / f"{role}.artifact" for role in T057_REQUIRED_INPUT_ROLES}
    with paths["t056_path_selection_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t056_post_t055_root_prior_path_selection_report_json(
            _t056_report(t056_next=t056_next),
            stream,
        )
    with paths["t053_failure_analysis_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t053_root_prior_failure_analysis_report_json(_t053_report(), stream)
    with paths["t055_scale_validation_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t055_guardrailed_root_prior_scale_validation_report_json(
            _t055_report(),
            stream,
        )
    _write_json(paths["t052_result_summary"], _t052_result_summary())

    comparisons = {
        "t048_current_reference_comparison": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "t048_assist0_reference_comparison": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
            },
        ),
        "t052_root_prior_guided_comparison": _comparison(
            include_guardrail=False,
            task_id="T052",
            cohort_identity="68d0e5b10ebcb05d",
            count=93,
            record_range="merged:0:93",
            wins={
                BASELINE_ORACLE_LABEL: 4,
                POST_SEARCH_MODEL_GUIDED_LABEL: 4,
                ROOT_PRIOR_GUIDED_LABEL: 3,
            },
        ),
        "t055_current_guardrailed_comparison": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "t055_assist0_guardrailed_comparison": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 12,
            },
        ),
    }
    for role, comparison in comparisons.items():
        with paths[role].open("w", encoding="utf-8", newline="\n") as stream:
            dump_root_prior_guided_search_comparison_jsonl(comparison, stream)
    return paths


def _t056_report(*, t056_next: str) -> T056PostT055RootPriorPathSelectionReport:
    return T056PostT055RootPriorPathSelectionReport(
        input_artifacts=[],
        evidence_ledger={},
        guardrail_branch_closure={
            "closed_for_now": True,
            "closed_branch": "T054/T055 guardrailed root-prior allocation",
            "exact_t055_recommendation": "abandon the guardrail path",
        },
        recommendation={
            "recommendation_count": 1,
            "selected_next_path": t056_next,
            "recommended_next_task": t056_next,
            "forbidden_claims": {"controller_promotion": False},
        },
        rejected_alternatives=[],
        unavailable_diagnostics=[],
    )


def _t053_report() -> T053RootPriorFailureAnalysisReport:
    return T053RootPriorFailureAnalysisReport(
        input_artifacts=[],
        comparison_summary={"cohort_identity": "68d0e5b10ebcb05d"},
        t052_result_summary=_t052_result_summary(),
        disagreement_summary={
            "evaluated_record_count": 93,
            "disagreement_count": 4,
            "cohort_indices": [53, 54, 55, 87],
            "root_prior_harmful_record_count": 2,
        },
        disagreement_records=[
            {"cohort_index": 53},
            {"cohort_index": 54},
            {"cohort_index": 55},
            {"cohort_index": 87},
        ],
        subset_summaries={},
        allocation_telemetry_summary={},
        action_comparison_diagnostics={
            "record_count": 4,
            "exact_step_level_matching_record_count": 0,
            "unavailable_record_count": 4,
        },
        failure_taxonomy={
            "harmful_root_prior_allocation": {
                "status": "supported",
                "evidence_count": 2,
            },
            "telemetry_or_schema_insufficient": {
                "status": "supported",
                "evidence_count": 4,
            },
        },
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": (
                "guardrailed root-prior allocation repair experiment"
            ),
            "forbidden_claims": {"controller_promotion": False},
        },
        unavailable_diagnostics=[
            {
                "diagnostic": "aggregate_step_level_action_identity_comparison",
                "reason": "selected action identity unavailable in T052 telemetry",
            }
        ],
    )


def _t055_report() -> T055GuardrailedRootPriorScaleValidationReport:
    return T055GuardrailedRootPriorScaleValidationReport(
        input_artifacts=[],
        t054_reference_summary={"recommendation": "scale the repaired variant"},
        cohort_summaries=[],
        aggregate_summary={
            "record_count": 29,
            "t055_guardrail_vs_existing_root_prior": {
                "status": "regressed",
                "win_delta": -1,
            },
        },
        allocation_telemetry_summary={},
        unavailable_diagnostics=[],
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": "abandon the guardrail path",
            "forbidden_claims": {"controller_promotion": False},
        },
    )


def _t052_result_summary() -> dict[str, object]:
    return {
        "overall": {
            BASELINE_ORACLE_LABEL: _t052_counts(93, 4, 89),
            POST_SEARCH_MODEL_GUIDED_LABEL: _t052_counts(93, 4, 89),
            ROOT_PRIOR_GUIDED_LABEL: _t052_counts(93, 3, 90),
        },
        "boss_only": {
            BASELINE_ORACLE_LABEL: _t052_counts(88, 1, 87),
            POST_SEARCH_MODEL_GUIDED_LABEL: _t052_counts(88, 1, 87),
            ROOT_PRIOR_GUIDED_LABEL: _t052_counts(88, 1, 87),
        },
        "act2_plus": {
            BASELINE_ORACLE_LABEL: _t052_counts(5, 3, 2),
            POST_SEARCH_MODEL_GUIDED_LABEL: _t052_counts(5, 3, 2),
            ROOT_PRIOR_GUIDED_LABEL: _t052_counts(5, 2, 3),
        },
        "comparison_config": {
            "task_id": "T052",
            "cohort_identity": "68d0e5b10ebcb05d",
            "evaluated_record_count": 93,
            "worker_count": 16,
            "shard_count": 16,
        },
        "evaluation_successful": True,
        "problems": [],
    }


def _t052_counts(records: int, wins: int, losses: int) -> dict[str, object]:
    return {
        "battle_count": records,
        "win_count": wins,
        "loss_count": losses,
        "truncated_count": 0,
        "error_count": 0,
        "win_rate": wins / records,
    }


def _comparison(
    *,
    include_guardrail: bool,
    task_id: str,
    cohort_identity: str,
    count: int,
    record_range: str,
    wins: dict[str, int],
) -> RootPriorGuidedSearchComparisonReport:
    arms = [
        (
            BASELINE_ORACLE_LABEL,
            BASELINE_ORACLE_LABEL,
            _fixed_report(BASELINE_ORACLE_LABEL, cohort_identity, count, wins),
        ),
        (
            POST_SEARCH_MODEL_GUIDED_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            _fixed_report(POST_SEARCH_MODEL_GUIDED_LABEL, cohort_identity, count, wins),
        ),
        (
            ROOT_PRIOR_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
            _fixed_report(ROOT_PRIOR_GUIDED_LABEL, cohort_identity, count, wins),
        ),
    ]
    if include_guardrail:
        arms.append(
            (
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                _fixed_report(
                    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                    cohort_identity,
                    count,
                    wins,
                ),
            )
        )
    return build_root_prior_guided_search_comparison_report(
        arms=arms,
        comparison_config={
            "task_id": task_id,
            "run_scale": "fixed",
            "cohort_identity": cohort_identity,
            "cohort_total_record_count": count,
            "evaluated_record_count": count,
            "record_range": record_range,
            "worker_count": 16 if count > 8 else 8,
            "shard_count": 16 if count > 8 else 8,
            "max_battle_steps": 200,
        },
    )


def _fixed_report(
    label: str,
    cohort_identity: str,
    count: int,
    wins: dict[str, int],
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity=cohort_identity,
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        max_battle_steps=200,
        source_pool_format_version=4,
        selection_config={"selection_seed": 57},
        per_stratum_source_counts={"20/1/MONSTER/CULTIST": count},
        battle_results=[
            _result(index, label, index < wins.get(label, 0)) for index in range(count)
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
        controller_compute_telemetry=_telemetry(index, label),
        public_context_status="legacy_unavailable",
        public_context_replay_status="not_checked",
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
        GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
    }:
        config["guidance_scorer"] = {
            "checkpoint_provenance": {
                "checkpoint_artifact_id": (
                    f"torch-policy-value-checkpoint-v1-sha256:{_CHECKPOINT_SHA256}"
                )
            }
        }
    if label == GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL:
        config["controller_version"] = (
            GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_VERSION
        )
        return {
            "kind": "guardrailed_root_prior_guided_oracle_battle_search",
            "name": f"{GUARDRAILED_ROOT_PRIOR_GUIDED_SEARCH_CONTROLLER_NAME}_s20",
            "config": config,
        }
    return {"kind": label, "name": label, "config": config}


def _telemetry(index: int, label: str) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "root_visits": {"total": 20},
            "native_simulator_steps": {"total": 40},
        }
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        telemetry["root_prior_guided_decision_reports"] = [
            {
                "allocation_metadata": {
                    "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                    "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
                    "allocated_root_visits": 20,
                },
                "prior_summary": {
                    "positive_prior_count": 1,
                    "provided_prior_count": 2,
                },
                "target": {
                    "legal_action_index": index % 2,
                    "visits": 10,
                    "mean_value": 0.5,
                    "selection_rule": "highest_mean",
                    "action_identity": {"kind": "card", "card": "Strike"},
                },
                "allocation_rows": [
                    {
                        "legal_action_index": index % 2,
                        "kind": "card",
                        "label": "Strike",
                        "root_prior": 0.75,
                        "allocated_root_visits": 12,
                        "visits": 10,
                        "mean_value": 0.5,
                    },
                    {
                        "legal_action_index": (index + 1) % 2,
                        "kind": "end_turn",
                        "label": "End Turn",
                        "root_prior": 0.0,
                        "allocated_root_visits": 8,
                        "visits": 0,
                        "mean_value": 0.0,
                    },
                ],
                "oracle_search_report": {"root_mapping_failure_count": 0},
            }
        ]
    return telemetry


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _artifact_specs(paths: dict[str, Path]) -> list[list[str]]:
    return [[role, str(paths[role]), _sha256(paths[role])] for role in paths]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
