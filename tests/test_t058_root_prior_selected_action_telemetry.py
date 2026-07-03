from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t058_root_prior_selected_action_telemetry import (
    run_t058_root_prior_selected_action_telemetry_from_paths,
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
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    RootPriorGuidedSearchComparisonReport,
    build_root_prior_guided_search_comparison_report,
    dump_root_prior_guided_search_comparison_jsonl,
)
from sts_combat_rl.sim.t057_existing_root_prior_telemetry_diagnostic import (
    T057ExistingRootPriorTelemetryDiagnosticReport,
    dump_t057_existing_root_prior_telemetry_diagnostic_report_json,
)
from sts_combat_rl.sim.t058_root_prior_selected_action_telemetry import (
    T058_REQUIRED_INPUT_ROLES,
    T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID,
    format_t058_root_prior_selected_action_telemetry_report,
    load_t058_root_prior_selected_action_telemetry_report_json,
)


def test_t058_report_verifies_inputs_and_recovers_selected_action_comparison(
    tmp_path: Path,
) -> None:
    paths = _write_t058_inputs(tmp_path)

    report = run_t058_root_prior_selected_action_telemetry_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=tmp_path / "t058-report.json",
    )

    assert report.command_passed
    assert report.schema_id == T058_SELECTED_ACTION_TELEMETRY_SCHEMA_ID
    assert report.prerequisite_summary["selected_action_available_record_delta"] == 122
    assert (
        report.selected_action_availability["exact_step_level_comparison_feasible_all"]
        is True
    )
    assert report.selected_action_availability["available_record_count"] == 122
    assert report.selected_action_availability["unavailable_record_count"] == 0
    assert set(report.cohort_summaries) == {
        "t048_current_t046_compatible",
        "t048_assist0_runs1000",
        "t052_boss_later_act_diagnostic",
    }
    assert report.subset_summaries["t052_boss_only"]["record_count"] == 88
    assert report.subset_summaries["t052_act2_plus"]["record_count"] == 5
    assert report.subset_summaries["t053_disagreement_records"]["cohort_indices"] == [
        53,
        54,
        55,
        87,
    ]
    assert (
        report.recommendation["selected_next_path"]
        == "root-prior allocation repair experiment"
    )
    assert report.recommendation["recommendation_count"] == 1
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False
    first_record = report.per_record_selected_action_diagnostics[0]
    root_first = first_record["selected_action_comparison"]["root_prior_first_actions"]
    assert root_first[0]["action_identity"]["stable_id"] == "battle:defend:0"

    loaded = load_t058_root_prior_selected_action_telemetry_report_json(
        StringIO((tmp_path / "t058-report.json").read_text(encoding="utf-8"))
    )
    text = format_t058_root_prior_selected_action_telemetry_report(loaded)
    assert "T058 root-prior selected-action telemetry replay diagnostic" in text
    assert "no controller tuning" in text
    assert "122 available / 0 unavailable" in text


def test_t058_fails_closed_when_one_arm_still_lacks_identity(
    tmp_path: Path,
) -> None:
    paths = _write_t058_inputs(tmp_path, missing_identity=True)

    report = run_t058_root_prior_selected_action_telemetry_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=tmp_path / "t058-report.json",
    )

    assert report.command_passed
    assert report.selected_action_availability["unavailable_record_count"] == 1
    assert report.selected_action_availability["affected_cohorts"] == {
        "t048_current_t046_compatible": [0]
    }
    assert (
        report.recommendation["selected_next_path"]
        == "publish a blocked path requiring maintainer decision"
    )
    unavailable = report.unavailable_diagnostics[0]
    assert unavailable["diagnostic"] == (
        "exact_all_arm_step_level_selected_action_comparison"
    )
    missing = unavailable["unavailable_records"][0]["missing_fields"][0]
    assert missing["arm"] == BASELINE_ORACLE_LABEL
    assert "selected_action_identity" in missing["field"]


def test_t058_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t058_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[0][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t058_root_prior_selected_action_telemetry_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t058-report.json",
        )


def test_cli_t058_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t058-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert [spec[0] for spec in kwargs["artifact_specs"]] == list(
            T058_REQUIRED_INPUT_ROLES
        )
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t058_root_prior_selected_action_telemetry_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t058_root_prior_selected_action_telemetry_command",
        lambda report: "T058 root-prior selected-action telemetry replay diagnostic",
    )

    rc = main(
        [
            "--t058-root-prior-selected-action-telemetry-report",
            str(output_path),
            *[
                item
                for index, role in enumerate(T058_REQUIRED_INPUT_ROLES)
                for item in [
                    "--t058-input-artifact",
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
    assert "T058 root-prior selected-action telemetry" in captured.err


def test_cli_t058_requires_nine_artifacts(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--t058-root-prior-selected-action-telemetry-report",
            str(tmp_path / "t058-report.json"),
        ]
    )

    assert validate_cli_args(args) == (
        "--t058-root-prior-selected-action-telemetry-report "
        "requires exactly nine --t058-input-artifact values"
    )


def _write_t058_inputs(
    tmp_path: Path,
    *,
    missing_identity: bool = False,
) -> dict[str, Path]:
    paths = {role: tmp_path / f"{role}.artifact" for role in T058_REQUIRED_INPUT_ROLES}
    with paths["t057_telemetry_diagnostic_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t057_existing_root_prior_telemetry_diagnostic_report_json(
            _t057_report(),
            stream,
        )
    _write_jsonl_metadata(paths["t048_current_fixed_cohort"], "fixed-cohort-v1")
    _write_jsonl_metadata(paths["t048_assist0_fixed_cohort"], "fixed-cohort-v1")
    _write_jsonl_metadata(paths["t052_boss_later_act_fixed_cohort"], "fixed-cohort-v1")
    paths["t043_assist0_smoke_checkpoint"].write_bytes(b"checkpoint-smoke")
    paths["t043_runs1000_assist0_checkpoint"].write_bytes(b"checkpoint-runs1000")

    comparisons = {
        "t048_current_replay_comparison": _comparison(
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            worker_count=8,
            shard_count=8,
            win_indices={
                BASELINE_ORACLE_LABEL: set(range(5)),
                POST_SEARCH_MODEL_GUIDED_LABEL: set(range(5)),
                ROOT_PRIOR_GUIDED_LABEL: set(range(6)),
            },
            missing_identity=missing_identity,
        ),
        "t048_assist0_replay_comparison": _comparison(
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            worker_count=16,
            shard_count=16,
            win_indices={
                BASELINE_ORACLE_LABEL: set(range(11)),
                POST_SEARCH_MODEL_GUIDED_LABEL: set(range(11)),
                ROOT_PRIOR_GUIDED_LABEL: set(range(13)),
            },
        ),
        "t052_replay_comparison": _comparison(
            cohort_identity="68d0e5b10ebcb05d",
            count=93,
            record_range="0:93",
            worker_count=16,
            shard_count=16,
            win_indices={
                BASELINE_ORACLE_LABEL: {0, 1, 2, 53},
                POST_SEARCH_MODEL_GUIDED_LABEL: {0, 1, 2, 53},
                ROOT_PRIOR_GUIDED_LABEL: {0, 1, 2},
            },
        ),
    }
    for role, comparison in comparisons.items():
        with paths[role].open("w", encoding="utf-8", newline="\n") as stream:
            dump_root_prior_guided_search_comparison_jsonl(comparison, stream)
    return paths


def _t057_report() -> T057ExistingRootPriorTelemetryDiagnosticReport:
    return T057ExistingRootPriorTelemetryDiagnosticReport(
        input_artifacts=[],
        prerequisite_summary={
            "t056_selected_next_path": (
                "existing-root-prior allocation/telemetry diagnostic"
            )
        },
        evidence_family_summaries={},
        cohort_summaries={},
        subset_summaries={
            "t053_disagreement_records": {
                "cohort_indices": [53, 54, 55, 87],
            }
        },
        per_record_outcome_deltas=[],
        allocation_telemetry_summary={},
        selected_action_availability={
            "record_count": 122,
            "available_record_count": 0,
            "exact_full_record_count": 0,
            "unavailable_record_count": 122,
        },
        diagnostic_taxonomy={},
        recommendation={
            "recommendation_count": 1,
            "selected_next_path": (
                "root-prior selected-action telemetry instrumentation or "
                "replay diagnostic"
            ),
            "forbidden_claims": {"controller_promotion": False},
        },
        rejected_alternatives=[],
        unavailable_diagnostics=[],
    )


def _comparison(
    *,
    cohort_identity: str,
    count: int,
    record_range: str,
    worker_count: int,
    shard_count: int,
    win_indices: dict[str, set[int]],
    missing_identity: bool = False,
) -> RootPriorGuidedSearchComparisonReport:
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
                    missing_identity=missing_identity
                    and label == BASELINE_ORACLE_LABEL,
                ),
            )
            for label in REQUIRED_LABELS
        ),
        comparison_config={
            "task_id": "T058",
            "run_scale": "fixed",
            "cohort_identity": cohort_identity,
            "cohort_total_record_count": count,
            "evaluated_record_count": count,
            "record_range": record_range,
            "worker_count": worker_count,
            "shard_count": shard_count,
            "max_battle_steps": 200,
        },
    )


REQUIRED_LABELS = (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
)


def _fixed_report(
    label: str,
    cohort_identity: str,
    count: int,
    win_indices: set[int],
    *,
    missing_identity: bool = False,
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity=cohort_identity,
        controller_provenance=_controller_provenance(label),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        max_battle_steps=200,
        source_pool_format_version=4,
        selection_config={"selection_seed": 58},
        per_stratum_source_counts={"20/1/BOSS/CULTIST": count},
        battle_results=[
            _result(
                index,
                label,
                index in win_indices,
                missing_identity=missing_identity and index == 0,
            )
            for index in range(count)
        ],
        problems=[],
    )


def _result(
    index: int,
    label: str,
    won: bool,
    *,
    missing_identity: bool,
) -> SingleBattleEvaluationResult:
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
        controller_compute_telemetry=_telemetry(
            label,
            missing_identity=missing_identity,
        ),
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
    if label in {POST_SEARCH_MODEL_GUIDED_LABEL, ROOT_PRIOR_GUIDED_LABEL}:
        config["guidance_scorer"] = {
            "checkpoint_provenance": {
                "checkpoint_artifact_id": "torch-policy-value-checkpoint-v1-sha256:abc"
            }
        }
    return {"kind": label, "name": label, "config": config}


def _telemetry(label: str, *, missing_identity: bool = False) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "model_calls": {"total": 1 if label != BASELINE_ORACLE_LABEL else 0},
            "root_visits": {"total": 20},
            "native_simulator_steps": {"total": 40},
            "root_mapping_failure_count": {"total": 0},
        }
    }
    if label == ROOT_PRIOR_GUIDED_LABEL:
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
                    "legal_action_index": 1,
                    "visits": 12,
                    "mean_value": 0.55,
                    "selection_rule": "highest_mean",
                    "action_identity": _identity("Defend", 1),
                },
                "allocation_rows": [
                    {
                        "legal_action_index": 0,
                        "kind": "card",
                        "label": "Strike",
                        "root_prior": 0.25,
                        "allocated_root_visits": 8,
                        "visits": 8,
                        "mean_value": 0.45,
                    },
                    {
                        "legal_action_index": 1,
                        "kind": "card",
                        "label": "Defend",
                        "root_prior": 0.75,
                        "allocated_root_visits": 12,
                        "visits": 12,
                        "mean_value": 0.55,
                    },
                ],
                "oracle_search_report": {"root_mapping_failure_count": 0},
            }
        ]
    else:
        report = {
            "selected_legal_action_index": 0,
            "selection_rule": "highest_mean",
            "selected_visits": 10,
            "selected_mean_value": 0.5,
        }
        if not missing_identity:
            report["selected_action_identity"] = _identity("Strike", 0)
        telemetry["oracle_search_decision_reports"] = [report]
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


def _write_jsonl_metadata(path: Path, schema_id: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps({"type": "metadata", "metadata": {"schema_id": schema_id}})
        )
        stream.write("\n")


def _artifact_specs(paths: dict[str, Path]) -> list[list[str]]:
    return [[role, str(paths[role]), _sha256(paths[role])] for role in paths]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
