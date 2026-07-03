from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t056_post_t055_root_prior_path_selection import (
    run_t056_post_t055_root_prior_path_selection_from_paths,
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
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    T054GuardrailedRootPriorRepairReport,
    dump_t054_guardrailed_root_prior_repair_report_json,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055GuardrailedRootPriorScaleValidationReport,
    dump_t055_guardrailed_root_prior_scale_validation_report_json,
)
from sts_combat_rl.sim.t056_post_t055_root_prior_path_selection import (
    T056_PATH_SELECTION_REPORT_SCHEMA_ID,
    T056_REQUIRED_INPUT_ROLES,
    format_t056_post_t055_root_prior_path_selection_report,
    load_t056_post_t055_root_prior_path_selection_report_json,
)


_CHECKPOINT_SHA256 = hashlib.sha256(b"checkpoint").hexdigest()


def test_t056_report_separates_evidence_closes_guardrail_and_recommends_one_path(
    tmp_path: Path,
) -> None:
    paths = _write_t056_inputs(tmp_path)

    report = run_t056_post_t055_root_prior_path_selection_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=tmp_path / "t056-report.json",
    )

    assert report.command_passed
    assert report.schema_id == T056_PATH_SELECTION_REPORT_SCHEMA_ID
    ledger = report.evidence_ledger
    assert set(ledger) == {
        "positive_t048_fixed_cohort_root_prior_signal",
        "t052_t053_later_act_boss_diagnostic_signal",
        "t054_guardrail_repair_result",
        "t055_guardrail_scale_validation_regression",
        "t050_t051_complete_run_reachability",
    }
    assert report.guardrail_branch_closure["closed_for_now"] is True
    assert (
        report.guardrail_branch_closure["exact_t055_recommendation"]
        == "abandon the guardrail path"
    )
    assert (
        report.recommendation["selected_next_path"]
        == "existing-root-prior allocation/telemetry diagnostic"
    )
    assert report.recommendation["recommendation_count"] == 1
    assert (
        "guardrailed root-prior complete-run reachability"
        in report.recommendation["not_recommended_next_branches"]
    )
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False
    assert any(
        item["diagnostic"] == "aggregate_step_level_action_identity_comparison"
        for item in report.unavailable_diagnostics
    )

    loaded = load_t056_post_t055_root_prior_path_selection_report_json(
        StringIO((tmp_path / "t056-report.json").read_text(encoding="utf-8"))
    )
    text = format_t056_post_t055_root_prior_path_selection_report(loaded)
    assert "T056 post-T055 root-prior path-selection report" in text
    assert "no simulator, training" in text
    assert "selected next path: existing-root-prior" in text


def test_t056_report_rejects_non_abandon_t055_recommendation(
    tmp_path: Path,
) -> None:
    paths = _write_t056_inputs(tmp_path, t055_next="repaired-variant reachability")

    with pytest.raises(ValueError, match="abandon the guardrail path"):
        run_t056_post_t055_root_prior_path_selection_from_paths(
            artifact_specs=_artifact_specs(paths),
            output_path=tmp_path / "t056-report.json",
        )


def test_t056_command_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t056_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[0][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t056_post_t055_root_prior_path_selection_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t056-report.json",
        )


def test_t056_command_rejects_pretty_printed_wrong_t055_manifest_schema(
    tmp_path: Path,
) -> None:
    paths = _write_t056_inputs(tmp_path)
    _write_json(
        paths["t055_retention_manifest"],
        {
            **_retention_manifest("t055"),
            "schema_id": "wrong-schema",
        },
    )

    with pytest.raises(ValueError, match="t055_retention_manifest.*schema"):
        run_t056_post_t055_root_prior_path_selection_from_paths(
            artifact_specs=_artifact_specs(paths),
            output_path=tmp_path / "t056-report.json",
        )


def test_cli_t056_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t056-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert [spec[0] for spec in kwargs["artifact_specs"]] == list(
            T056_REQUIRED_INPUT_ROLES
        )
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t056_post_t055_root_prior_path_selection_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t056_post_t055_root_prior_path_selection_command",
        lambda report: "T056 post-T055 root-prior path-selection report",
    )

    rc = main(
        [
            "--t056-post-t055-root-prior-path-selection-report",
            str(output_path),
            *[
                item
                for index, role in enumerate(T056_REQUIRED_INPUT_ROLES)
                for item in [
                    "--t056-input-artifact",
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
    assert "T056 post-T055 root-prior path-selection report" in captured.err


def test_cli_t056_requires_thirteen_artifacts(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--t056-post-t055-root-prior-path-selection-report",
            str(tmp_path / "t056-report.json"),
        ]
    )

    assert validate_cli_args(args) == (
        "--t056-post-t055-root-prior-path-selection-report requires "
        "exactly thirteen --t056-input-artifact values"
    )


def _write_t056_inputs(
    tmp_path: Path,
    *,
    t055_next: str = "abandon the guardrail path",
) -> dict[str, Path]:
    paths = {role: tmp_path / f"{role}.artifact" for role in T056_REQUIRED_INPUT_ROLES}
    _write_json(paths["t055_retention_manifest"], _retention_manifest("t055"))
    _write_json(paths["t052_result_summary"], _t052_result_summary())
    _write_json(paths["t050_reachability_report"], _reachability_report("T050"))
    _write_json(paths["t050_retention_manifest"], _retention_manifest("t050"))
    _write_json(paths["t051_reachability_report"], _reachability_report("T051"))
    _write_json(paths["t051_retention_manifest"], _retention_manifest("t051"))
    with paths["t053_failure_analysis_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t053_root_prior_failure_analysis_report_json(_t053_report(), stream)
    with paths["t054_guardrailed_repair_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t054_guardrailed_root_prior_repair_report_json(_t054_report(), stream)
    with paths["t055_scale_validation_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t055_guardrailed_root_prior_scale_validation_report_json(
            _t055_report(t055_next=t055_next),
            stream,
        )

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


def _t053_report() -> T053RootPriorFailureAnalysisReport:
    return T053RootPriorFailureAnalysisReport(
        input_artifacts=[],
        comparison_summary={"cohort_identity": "cohort-t052"},
        t052_result_summary=_t052_result_summary(),
        disagreement_summary={
            "evaluated_record_count": 93,
            "disagreement_count": 4,
            "cohort_indices": [53, 54, 55, 87],
            "root_prior_harmful_record_count": 2,
        },
        disagreement_records=[],
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


def _t054_report() -> T054GuardrailedRootPriorRepairReport:
    return T054GuardrailedRootPriorRepairReport(
        input_artifacts=[],
        t052_comparison_summary={"cohort_identity": "cohort-t052"},
        t052_result_summary=_t052_result_summary(),
        t053_reference_summary={"disagreement_indices": [53, 54, 55, 87]},
        t054_comparison_summary={"cohort_identity": "cohort-t054"},
        guardrail_configuration={"controller_version": "unit"},
        aggregate_outcome_comparison={
            "guardrail_vs_root_prior": {"status": "improved", "win_delta": 1}
        },
        subset_summaries={
            "act2_plus": {
                "guardrail_vs_baseline": {"status": "regressed", "win_delta": -1}
            }
        },
        disagreement_index_results=[],
        allocation_telemetry_summary={},
        unavailable_diagnostics=[],
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": "scale the repaired variant",
            "forbidden_claims": {"controller_promotion": False},
        },
    )


def _t055_report(
    *,
    t055_next: str,
) -> T055GuardrailedRootPriorScaleValidationReport:
    return T055GuardrailedRootPriorScaleValidationReport(
        input_artifacts=[],
        t054_reference_summary={"recommendation": "scale the repaired variant"},
        cohort_summaries=[],
        aggregate_summary={
            "record_count": 29,
            "t048_advantage_status": "regressed",
            "t055_guardrail_vs_existing_root_prior": {
                "status": "regressed",
                "win_delta": -1,
            },
        },
        allocation_telemetry_summary={},
        unavailable_diagnostics=[
            {
                "diagnostic": "guardrail_causal_effect",
                "reason": "paired within-decision counterfactual trees unavailable",
            }
        ],
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": t055_next,
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


def _reachability_report(task_id: str) -> dict[str, object]:
    later = task_id == "T051"
    return {
        "schema_id": "a20-search-controlled-reachability-report-v1",
        "format_version": 1,
        "command_passed": True,
        "command_problems": [],
        "followup_hint": (
            "broader_search_controlled_source_collection"
            if later
            else "broader_search_controlled_source_collection_before_t032"
        ),
        "comparison": {
            "best_later_act_arm": ("post_search_model_guided_v2" if later else None),
            "best_later_act_start_count": 3 if later else 0,
            "broad_training_allowed_any_arm": False,
        },
        "arms": [
            _reachability_arm("baseline_oracle_search_v1", later_count=0),
            _reachability_arm(
                "post_search_model_guided_v2", later_count=3 if later else 0
            ),
            _reachability_arm("root_prior_guided_v1", later_count=2 if later else 0),
        ],
    }


def _reachability_arm(label: str, *, later_count: int) -> dict[str, object]:
    return {
        "label": label,
        "source_run_count": 1000,
        "terminal_run_count": 1000,
        "natural_battle_start_count": 100 + later_count,
        "boss_battle_start_count": 2,
        "act1_boss_battle_start_count": 2,
        "later_act_battle_start_count": later_count,
        "boss_source_run_count": 2,
        "later_act_source_run_count": 1 if later_count else 0,
        "training_gate_report": {
            "broad_training_allowed": False,
            "training_allowed": False,
            "observed_act_counts": {"1": 100, "2": later_count},
            "problems": ["A20/act2: under-covered"],
        },
        "problems": [],
    }


def _retention_manifest(task_id: str) -> dict[str, object]:
    schemas = {
        "t055": "t055-retention-manifest-v1",
        "t050": "t050-root-prior-reachability-retention-manifest-v1",
        "t051": "t051-search-controlled-later-act-retention-manifest-v1",
    }
    if task_id == "t055":
        return {
            "schema_id": schemas[task_id],
            "format_version": 1,
            "task_id": "T055",
            "retention_reason": "unit-test",
            "artifacts": [{"role": "scale_validation_report"}],
            "commands": [{"role": "scale_validation_report", "command": "unit"}],
            "runtime_stages": [{"role": "current", "workers": 1, "shards": 1}],
        }
    return {
        "schema_id": schemas[task_id],
        "format_version": 1,
        "retention_path": f"artifacts/{task_id}",
        "retention_reason": "unit-test",
        "regeneration": {"command": "unit"},
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
            "worker_count": 16,
            "shard_count": 16,
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
        selection_config={"selection_seed": 56},
        per_stratum_source_counts={"20/1/MONSTER/CULTIST": count},
        battle_results=[
            _result(index, label, index < wins.get(label, 0)) for index in range(count)
        ],
        problems=[],
    )


def _result(index: int, label: str, won: bool) -> SingleBattleEvaluationResult:
    return SingleBattleEvaluationResult(
        cohort_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_seed=1000 + index,
        source_run_id=f"run-{index}",
        source_battle_index=index,
        structural_stratum=(20, 1, "MONSTER", "CULTIST"),
        structural_metadata={
            "ascension": 20,
            "act": 1,
            "room_type": "MONSTER",
            "encounter_id": "CULTIST",
            "distribution_kind": "natural_run",
        },
        restoration_method="portable_replay",
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        termination_status="win" if won else "loss",
        terminal_absolute_hp=20 if won else 0,
        hp_loss=50,
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
        "search_telemetry_summary": {"root_visits": {"total": 20}}
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        telemetry["root_prior_guided_decision_reports"] = [
            {
                "allocation_metadata": {
                    "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                    "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
                },
                "prior_summary": {
                    "positive_prior_count": 1,
                    "provided_prior_count": 2,
                },
                "target": {"legal_action_index": index % 2},
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
