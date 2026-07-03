from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t053_root_prior_failure_analysis import (
    run_t053_root_prior_failure_analysis_from_paths,
)
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
)
from sts_combat_rl.sim.t053_root_prior_failure_analysis import (
    T053_FAILURE_ANALYSIS_SCHEMA_ID,
    format_t053_root_prior_failure_analysis_report,
    load_t053_root_prior_failure_analysis_report_json,
)


def test_t053_analysis_reports_disagreements_subsets_taxonomy_and_roundtrip(
    tmp_path: Path,
) -> None:
    artifacts = _write_t052_inputs(tmp_path)
    output_path = tmp_path / "t053-analysis.json"

    report = run_t053_root_prior_failure_analysis_from_paths(
        artifact_specs=_artifact_specs(artifacts),
        output_path=output_path,
    )

    assert report.command_passed
    assert output_path.exists()
    assert report.schema_id == T053_FAILURE_ANALYSIS_SCHEMA_ID
    assert report.disagreement_summary["disagreement_count"] == 2
    assert report.disagreement_summary["win_loss_disagreement_count"] == 1
    assert report.disagreement_summary["terminal_hp_only_disagreement_count"] == 1
    assert report.subset_summaries["boss_only"]["disagreement_count"] == 1
    assert report.subset_summaries["act2_plus"]["disagreement_count"] == 1
    assert (
        report.failure_taxonomy["harmful_root_prior_allocation"]["evidence_count"] == 1
    )
    assert (
        report.failure_taxonomy["no_op_or_ineffective_root_prior_allocation"][
            "evidence_count"
        ]
        == 1
    )
    assert report.recommendation["recommendation_count"] == 1
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False

    loaded = load_t053_root_prior_failure_analysis_report_json(
        StringIO(output_path.read_text(encoding="utf-8"))
    )
    text = format_t053_root_prior_failure_analysis_report(loaded)
    assert "T053 root-prior allocation failure analysis" in text
    assert "no simulator, training" in text
    assert "promoted" not in text.lower()


def test_t053_analysis_reports_unavailable_action_identity(tmp_path: Path) -> None:
    artifacts = _write_t052_inputs(tmp_path, include_baseline_action_identity=False)

    report = run_t053_root_prior_failure_analysis_from_paths(
        artifact_specs=_artifact_specs(artifacts),
        output_path=tmp_path / "analysis.json",
    )

    assert report.command_passed
    assert report.action_comparison_diagnostics["unavailable_record_count"] >= 1
    assert any(
        item["diagnostic"] == "step_level_action_identity_comparison"
        for item in report.unavailable_diagnostics
    )
    assert (
        report.failure_taxonomy["telemetry_or_schema_insufficient"]["status"]
        == "supported"
    )


def test_t053_analysis_rejects_hash_mismatch(tmp_path: Path) -> None:
    artifacts = _write_t052_inputs(tmp_path)
    specs = _artifact_specs(artifacts)
    specs[0][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t053_root_prior_failure_analysis_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "analysis.json",
        )


def test_t053_analysis_rejects_missing_required_arm(tmp_path: Path) -> None:
    artifacts = _write_t052_inputs(tmp_path, omit_post_arm=True)

    with pytest.raises(ValueError, match="missing required arm"):
        run_t053_root_prior_failure_analysis_from_paths(
            artifact_specs=_artifact_specs(artifacts),
            output_path=tmp_path / "analysis.json",
        )


def test_t053_analysis_rejects_source_mismatch(tmp_path: Path) -> None:
    artifacts = _write_t052_inputs(tmp_path, source_match_status="mismatch")

    with pytest.raises(ValueError, match="source/cohort match status"):
        run_t053_root_prior_failure_analysis_from_paths(
            artifact_specs=_artifact_specs(artifacts),
            output_path=tmp_path / "analysis.json",
        )


def test_cli_t053_routes_to_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "analysis.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["artifact_specs"] == [
            ["retention_manifest", "manifest.json", "a" * 64],
            ["fixed_cohort", "cohort.jsonl", "b" * 64],
            ["root_prior_guided_comparison", "comparison.jsonl", "c" * 64],
            ["result_summary", "summary.json", "d" * 64],
        ]
        assert kwargs["output_path"] == output_path
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t053_root_prior_failure_analysis_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t053_root_prior_failure_analysis_command",
        lambda report: (
            "T053 root-prior allocation failure analysis\ncommand passed: yes"
        ),
    )

    rc = main(
        [
            "--t053-root-prior-allocation-failure-analysis-report",
            str(output_path),
            "--t053-t052-artifact",
            "retention_manifest",
            "manifest.json",
            "a" * 64,
            "--t053-t052-artifact",
            "fixed_cohort",
            "cohort.jsonl",
            "b" * 64,
            "--t053-t052-artifact",
            "root_prior_guided_comparison",
            "comparison.jsonl",
            "c" * 64,
            "--t053-t052-artifact",
            "result_summary",
            "summary.json",
            "d" * 64,
            "--log-file",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
    assert "T053 root-prior allocation failure analysis" in captured.err


def test_cli_t053_requires_four_artifacts(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--t053-root-prior-allocation-failure-analysis-report",
            str(tmp_path / "analysis.json"),
        ]
    )

    assert validate_cli_args(args) == (
        "--t053-root-prior-allocation-failure-analysis-report requires "
        "exactly four --t053-t052-artifact values"
    )


def _write_t052_inputs(
    tmp_path: Path,
    *,
    include_baseline_action_identity: bool = True,
    omit_post_arm: bool = False,
    source_match_status: str = "matched",
) -> dict[str, Path]:
    retention_manifest = tmp_path / "t052-retention-manifest.json"
    fixed_cohort = tmp_path / "t052-fixed-cohort.jsonl"
    comparison = tmp_path / "t052-root-prior-guided-comparison.jsonl"
    result_summary = tmp_path / "t052-result-summary.json"

    _write_json(
        retention_manifest,
        {"schema_id": "t052-retention-manifest-v1", "format_version": 1},
    )
    fixed_cohort.write_text(
        json.dumps(
            {
                "type": "metadata",
                "metadata": {"schema_id": "fixed-cohort-v1", "format_version": 1},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        result_summary,
        {
            "schema_id": "t052-result-summary-v1",
            "format_version": 1,
            "overall": {
                "baseline": "1W/2L",
                "post_search": "1W/2L",
                "root_prior": "0W/3L",
            },
        },
    )
    _write_comparison(
        comparison,
        include_baseline_action_identity=include_baseline_action_identity,
        omit_post_arm=omit_post_arm,
        source_match_status=source_match_status,
    )
    return {
        "retention_manifest": retention_manifest,
        "fixed_cohort": fixed_cohort,
        "root_prior_guided_comparison": comparison,
        "result_summary": result_summary,
    }


def _write_comparison(
    path: Path,
    *,
    include_baseline_action_identity: bool,
    omit_post_arm: bool,
    source_match_status: str,
) -> None:
    labels = [BASELINE_ORACLE_LABEL, ROOT_PRIOR_GUIDED_LABEL]
    if not omit_post_arm:
        labels.insert(1, POST_SEARCH_MODEL_GUIDED_LABEL)
    metadata = {
        "schema_id": "root-prior-guided-search-comparison-v1",
        "format_version": 1,
        "cohort_identity": "cohort-t053-fixture",
        "run_scale": "fixed",
        "evidence_boundary": "fixture boundary",
        "comparison_config": {"task_id": "T052"},
        "controller_arms": [
            {"label": label, "role": label, "report_metadata": {}} for label in labels
        ],
        "required_arms": [
            BASELINE_ORACLE_LABEL,
            POST_SEARCH_MODEL_GUIDED_LABEL,
            ROOT_PRIOR_GUIDED_LABEL,
        ],
        "source_match_status": source_match_status,
        "source_match_problems": [],
        "controller_summaries": {
            label: {"information_regime": NATIVE_SEARCH_INFORMATION_REGIME}
            for label in labels
        },
        "aggregate_outcomes": {},
        "budget_comparison": {},
        "root_prior_allocation_summary": {
            "decision_count": 2,
            "malformed_metadata_count": 0,
        },
        "outcome_comparison": {},
        "battle_comparison_count": 3,
        "evaluation_successful": True,
        "report_problems": [],
        "validation_problems": [],
        "problems": [],
    }
    rows = [{"type": "metadata", "metadata": metadata}]
    rows.extend(
        {
            "type": "battle_comparison",
            "comparison": _battle_comparison(index, baseline, post, root, metadata),
        }
        for index, baseline, post, root, metadata in [
            (0, ("win", 10), ("win", 10), ("loss", 0), _source_metadata(1, "BOSS")),
            (1, ("win", 5), ("win", 5), ("win", 7), _source_metadata(2, "MONSTER")),
            (2, ("loss", 0), ("loss", 0), ("loss", 0), _source_metadata(1, "BOSS")),
        ]
    )
    for index, baseline, post, root, metadata_row in [
        (0, ("win", 10), ("win", 10), ("loss", 0), _source_metadata(1, "BOSS")),
        (1, ("win", 5), ("win", 5), ("win", 7), _source_metadata(2, "MONSTER")),
    ]:
        rows.append(
            {
                "type": "controller_result",
                "label": BASELINE_ORACLE_LABEL,
                "result": _controller_result(
                    index,
                    BASELINE_ORACLE_LABEL,
                    baseline,
                    metadata_row,
                    include_action_identity=include_baseline_action_identity,
                ),
            }
        )
        if not omit_post_arm:
            rows.append(
                {
                    "type": "controller_result",
                    "label": POST_SEARCH_MODEL_GUIDED_LABEL,
                    "result": _controller_result(
                        index,
                        POST_SEARCH_MODEL_GUIDED_LABEL,
                        post,
                        metadata_row,
                    ),
                }
            )
        rows.append(
            {
                "type": "controller_result",
                "label": ROOT_PRIOR_GUIDED_LABEL,
                "result": _controller_result(
                    index,
                    ROOT_PRIOR_GUIDED_LABEL,
                    root,
                    metadata_row,
                    root_prior=True,
                ),
            }
        )
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _battle_comparison(
    index: int,
    baseline: tuple[str, int],
    post: tuple[str, int],
    root: tuple[str, int],
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "comparison_index": index,
        "source_match": True,
        "source": {
            "cohort_index": index,
            "source_checkpoint_id": f"checkpoint-{index}",
            "source_seed": 100 + index,
            "source_run_id": f"run-{index}",
            "source_battle_index": index,
            "structural_stratum": [20, metadata["act"], metadata["room_type"]],
        },
        "arms": {
            BASELINE_ORACLE_LABEL: _arm_summary(baseline, metadata),
            POST_SEARCH_MODEL_GUIDED_LABEL: _arm_summary(post, metadata),
            ROOT_PRIOR_GUIDED_LABEL: _arm_summary(root, metadata),
        },
        "problems": [],
    }


def _arm_summary(
    outcome: tuple[str, int],
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "present": True,
        "termination_status": outcome[0],
        "terminal_absolute_hp": outcome[1],
        "decision_count": 1,
        "simulator_step_count": 2,
        "wall_clock_time_s": 0.01,
        "structural_metadata": metadata,
        "public_context_status": "available",
        "public_context_replay_status": "matched",
        "structured_battle_outcome_status": "available",
        "structured_battle_outcome": {"schema_id": "structured-battle-outcome-v1"},
        "root_prior_guidance": {"decision_count": 1},
        "problem_count": 0,
        "problems": [],
    }


def _controller_result(
    index: int,
    label: str,
    outcome: tuple[str, int],
    metadata: dict[str, object],
    *,
    include_action_identity: bool = True,
    root_prior: bool = False,
) -> dict[str, object]:
    telemetry = (
        _root_prior_telemetry(index)
        if root_prior
        else _oracle_telemetry(index, include_action_identity=include_action_identity)
    )
    return {
        "cohort_index": index,
        "source_checkpoint_id": f"checkpoint-{index}",
        "source_seed": 100 + index,
        "source_run_id": f"run-{index}",
        "source_battle_index": index,
        "structural_stratum": [20, metadata["act"], metadata["room_type"]],
        "structural_metadata": metadata,
        "restoration_method": "portable_replay",
        "controller_provenance": {"kind": label, "name": label},
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "action_space_config": {"excluded_kinds": []},
        "termination_status": outcome[0],
        "terminal_absolute_hp": outcome[1],
        "hp_loss": 3,
        "decision_count": 1,
        "simulator_step_count": 2,
        "wall_clock_time_s": 0.01,
        "controller_compute_telemetry": telemetry,
        "public_context_status": "available",
        "public_context_replay_status": "matched",
        "structured_battle_outcome_status": "available",
        "structured_battle_outcome": {"schema_id": "structured-battle-outcome-v1"},
        "problems": [],
    }


def _oracle_telemetry(
    index: int,
    *,
    include_action_identity: bool,
) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "model_calls": {"total": 0},
            "native_simulator_steps": {"total": 20},
            "root_mapping_failure_count": {"total": 0},
            "unsearched_legal_action_count": {"total": 0},
            "root_visits": {"total": 20},
        }
    }
    if include_action_identity:
        telemetry["oracle_search_decision_reports"] = [
            {"target": _target(index, "Strike_R")}
        ]
    return telemetry


def _root_prior_telemetry(index: int) -> dict[str, object]:
    return {
        "root_prior_guided_decision_reports": [
            {
                "allocation_metadata": {
                    "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                    "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
                    "allocated_root_visits": 20,
                    "eligible_root_action_count": 2,
                    "legal_action_prior_count": 2,
                    "matched_prior_mass": 1.0,
                    "min_visits_per_legal_action": 1,
                    "prior_allocation_weight": 1.0,
                    "prior_temperature": 1.0,
                },
                "allocation_rows": [
                    {
                        "legal_action_index": 0,
                        "label": "{ use Strike_R }",
                        "kind": "card",
                        "root_prior": 1.0,
                        "allocated_root_visits": 19,
                        "visits": 19,
                        "mean_value": 0.2,
                    },
                    {
                        "legal_action_index": 1,
                        "label": "{ end turn }",
                        "kind": "end_turn",
                        "root_prior": 0.0,
                        "allocated_root_visits": 1,
                        "visits": 1,
                        "mean_value": 0.1,
                    },
                ],
                "prior_summary": {
                    "eligible_action_count": 2,
                    "legal_action_count": 2,
                    "positive_prior_count": 1,
                    "provided_prior_count": 2,
                    "prior_probability_sum": 1.0,
                },
                "target": _target(index, "Strike_R"),
            }
        ],
        "search_telemetry_summary": {
            "model_calls": {"total": 1},
            "native_simulator_steps": {"total": 20},
            "root_mapping_failure_count": {"total": 0},
            "unsearched_legal_action_count": {"total": 0},
            "root_visits": {"total": 20},
        },
    }


def _target(index: int, card_id: str) -> dict[str, object]:
    return {
        "legal_action_index": 0,
        "visits": 19,
        "mean_value": 0.2,
        "score": 0.2,
        "selection_rule": "highest_mean",
        "action_identity": {
            "kind": "card",
            "card_id": card_id,
            "action_id": f"battle:{index}",
            "stable_id": f"card:{card_id}:{index}",
            "occurrence": 0,
        },
    }


def _source_metadata(act: int, room_type: str) -> dict[str, object]:
    return {
        "act": act,
        "ascension": 20,
        "room_type": room_type,
        "encounter_id": "HEXAGHOST" if room_type == "BOSS" else "TWO_THIEVES",
        "floor": 16 if room_type == "BOSS" else 18,
        "source_run_id": "seed-1-run-1",
        "source_battle_index": 7 if room_type == "BOSS" else 8,
        "t051_source_arm_role": "post_search" if act >= 2 else "baseline",
        "t051_source_arm_label": "post_search_model_guided_v2"
        if act >= 2
        else "baseline_oracle_search_v1",
        "t052_selection_reasons": ["act2_plus"] if act >= 2 else ["act1_boss"],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_specs(artifacts: dict[str, Path]) -> list[list[str]]:
    return [
        [role, str(path), _sha256(path)]
        for role, path in [
            ("retention_manifest", artifacts["retention_manifest"]),
            ("fixed_cohort", artifacts["fixed_cohort"]),
            (
                "root_prior_guided_comparison",
                artifacts["root_prior_guided_comparison"],
            ),
            ("result_summary", artifacts["result_summary"]),
        ]
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
