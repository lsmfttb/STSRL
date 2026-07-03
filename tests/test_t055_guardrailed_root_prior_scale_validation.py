from __future__ import annotations

from io import StringIO
import hashlib
import json
from pathlib import Path

import pytest

from sts_combat_rl.cli import main
from sts_combat_rl.commands.t055_guardrailed_root_prior_scale_validation import (
    run_t055_guardrailed_root_prior_scale_validation_from_paths,
    run_t055_retention_manifest_from_paths,
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
from sts_combat_rl.sim.t054_guardrailed_root_prior_repair import (
    T054GuardrailedRootPriorRepairReport,
    dump_t054_guardrailed_root_prior_repair_report_json,
)
from sts_combat_rl.sim.t055_guardrailed_root_prior_scale_validation import (
    T055_REQUIRED_INPUT_ROLES,
    T055_SCALE_VALIDATION_REPORT_SCHEMA_ID,
    build_t055_guardrailed_root_prior_scale_validation_report,
    dump_t055_guardrailed_root_prior_scale_validation_report_json,
    format_t055_guardrailed_root_prior_scale_validation_report,
    load_t055_guardrailed_root_prior_scale_validation_report_json,
)


_CHECKPOINT_SHA256 = hashlib.sha256(b"checkpoint").hexdigest()
_OTHER_CHECKPOINT_SHA256 = hashlib.sha256(b"other checkpoint").hexdigest()


def test_t055_report_validates_two_cohorts_and_roundtrips() -> None:
    t054_report = _t054_report()
    t054_comparison = _comparison(
        include_guardrail=True,
        task_id="T054",
        cohort_identity="cohort-t054",
        count=93,
        record_range="merged:0:93",
        workers=16,
        shards=16,
        wins={
            BASELINE_ORACLE_LABEL: 4,
            POST_SEARCH_MODEL_GUIDED_LABEL: 4,
            ROOT_PRIOR_GUIDED_LABEL: 3,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 4,
        },
    )
    references = {
        "current_t046_full8": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            workers=8,
            shards=8,
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "assist0_runs1000_full21": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            workers=16,
            shards=16,
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
            },
        ),
    }
    generated = {
        "current_t046_full8": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            workers=8,
            shards=8,
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "assist0_runs1000_full21": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            workers=16,
            shards=16,
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 13,
            },
        ),
    }

    report = build_t055_guardrailed_root_prior_scale_validation_report(
        input_artifacts=_verified_artifacts(),
        t054_report=t054_report,
        t054_comparison=t054_comparison,
        t048_reference_comparisons=references,
        t055_comparisons=generated,
    )

    assert report.command_passed
    assert report.schema_id == T055_SCALE_VALIDATION_REPORT_SCHEMA_ID
    assert len(report.cohort_summaries) == 2
    assert report.aggregate_summary["record_count"] == 29
    assert report.aggregate_summary["t048_advantage_status"] == "preserved"
    assert (
        report.aggregate_summary["t055_outcomes"][GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL][
            "authoritative_wins"
        ]
        == 19
    )
    assert (
        report.allocation_telemetry_summary["aggregate"]["guardrail_telemetry"][
            "decision_count"
        ]
        == 29
    )
    assert report.recommendation["recommendation_count"] == 1
    assert (
        report.recommendation["recommended_next_task"]
        == "repaired-variant complete-run reachability"
    )
    assert report.recommendation["forbidden_claims"]["controller_promotion"] is False

    buffer = StringIO()
    dump_t055_guardrailed_root_prior_scale_validation_report_json(report, buffer)
    loaded = load_t055_guardrailed_root_prior_scale_validation_report_json(
        StringIO(buffer.getvalue())
    )
    text = format_t055_guardrailed_root_prior_scale_validation_report(loaded)
    assert "T055 guardrailed root-prior scale validation report" in text
    assert "no controller promotion" in text
    assert "natural A20" in text


def test_t055_report_rejects_missing_guardrailed_arm() -> None:
    with pytest.raises(ValueError, match="missing required arm"):
        build_t055_guardrailed_root_prior_scale_validation_report(
            input_artifacts=_verified_artifacts(),
            t054_report=_t054_report(),
            t054_comparison=_t054_comparison(),
            t048_reference_comparisons=_reference_comparisons(),
            t055_comparisons={
                "current_t046_full8": _comparison(
                    include_guardrail=False,
                    task_id="T055",
                    cohort_identity="875ea52e3df4cb93",
                    count=8,
                    record_range="0:8",
                    workers=8,
                    shards=8,
                    wins={
                        BASELINE_ORACLE_LABEL: 5,
                        POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                        ROOT_PRIOR_GUIDED_LABEL: 6,
                    },
                ),
                "assist0_runs1000_full21": _generated_comparisons()[
                    "assist0_runs1000_full21"
                ],
            },
        )


@pytest.mark.parametrize(
    ("side", "expected_prefix"),
    [
        ("reference", "T048 reference"),
        ("generated", "T055 comparison"),
    ],
)
def test_t055_report_rejects_checkpoint_sha_mismatch(
    side: str,
    expected_prefix: str,
) -> None:
    references = _reference_comparisons()
    generated = _generated_comparisons()
    replacement = _comparison(
        include_guardrail=side == "generated",
        task_id="T055" if side == "generated" else "T048",
        cohort_identity="875ea52e3df4cb93",
        count=8,
        record_range="0:8",
        workers=8,
        shards=8,
        wins={
            BASELINE_ORACLE_LABEL: 5,
            POST_SEARCH_MODEL_GUIDED_LABEL: 5,
            ROOT_PRIOR_GUIDED_LABEL: 6,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 6,
        },
        checkpoint_sha256=_OTHER_CHECKPOINT_SHA256,
    )
    if side == "reference":
        references["current_t046_full8"] = replacement
    else:
        generated["current_t046_full8"] = replacement

    with pytest.raises(
        ValueError,
        match=f"current_t046_full8 {expected_prefix}: .*checkpoint sha256 mismatch",
    ):
        build_t055_guardrailed_root_prior_scale_validation_report(
            input_artifacts=_verified_artifacts(),
            t054_report=_t054_report(),
            t054_comparison=_t054_comparison(),
            t048_reference_comparisons=references,
            t055_comparisons=generated,
        )


def test_t055_command_hash_checks_and_writes_report(tmp_path: Path) -> None:
    paths = _write_t055_inputs(tmp_path)
    output_path = tmp_path / "t055-report.json"

    report = run_t055_guardrailed_root_prior_scale_validation_from_paths(
        artifact_specs=_artifact_specs(paths),
        output_path=output_path,
    )

    assert report.command_passed
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_id"] == (
        T055_SCALE_VALIDATION_REPORT_SCHEMA_ID
    )


def test_t055_command_rejects_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_t055_inputs(tmp_path)
    specs = _artifact_specs(paths)
    specs[-1][2] = "0" * 64

    with pytest.raises(ValueError, match="sha256 mismatch"):
        run_t055_guardrailed_root_prior_scale_validation_from_paths(
            artifact_specs=specs,
            output_path=tmp_path / "t055-report.json",
        )


def test_t055_retention_manifest_records_generated_artifacts(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text(
        '{"schema_id":"t055-guardrailed-root-prior-scale-validation-report-v1"}\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "manifest.json"

    manifest = run_t055_retention_manifest_from_paths(
        output_path=output_path,
        artifact_specs=[
            [
                "scale_validation_report",
                str(artifact),
                "t055-guardrailed-root-prior-scale-validation-report-v1",
            ]
        ],
        command_specs=[["scale_validation_report", "python -m sts_combat_rl.cli ..."]],
        stage_specs=[["current_t046_full8", "8", "8", "0:8", "12.5"]],
        note_specs=[["runtime", "unit-test"]],
    )

    assert output_path.exists()
    assert manifest["schema_id"] == "t055-retention-manifest-v1"
    assert manifest["artifacts"][0]["sha256"] == _sha256(artifact)
    assert manifest["runtime_stages"][0]["workers"] == 8


def test_cli_t055_routes_to_report_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "t055-report.json"

    class _FakeReport:
        command_passed = True

    def fake_run(**kwargs):
        assert kwargs["output_path"] == output_path
        assert [spec[0] for spec in kwargs["artifact_specs"]] == list(
            T055_REQUIRED_INPUT_ROLES
        )
        return _FakeReport()

    monkeypatch.setattr(
        "sts_combat_rl.cli.run_t055_guardrailed_root_prior_scale_validation_from_paths",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.cli.format_t055_guardrailed_root_prior_scale_validation_command",
        lambda report: "T055 guardrailed root-prior scale validation report",
    )

    rc = main(
        [
            "--t055-guardrailed-root-prior-scale-validation-report",
            str(output_path),
            *[
                item
                for index, role in enumerate(T055_REQUIRED_INPUT_ROLES)
                for item in [
                    "--t055-input-artifact",
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
    assert "T055 guardrailed root-prior scale validation report" in captured.err


def _t054_report() -> T054GuardrailedRootPriorRepairReport:
    return T054GuardrailedRootPriorRepairReport(
        input_artifacts=[],
        t052_comparison_summary={"cohort_identity": "cohort-t052"},
        t052_result_summary={"schema_id": "t052-result-summary-v1"},
        t053_reference_summary={"disagreement_indices": [53, 54, 55, 87]},
        t054_comparison_summary={
            "cohort_identity": "cohort-t054",
            "evaluated_record_count": 93,
        },
        guardrail_configuration={"controller_version": "unit"},
        aggregate_outcome_comparison={},
        subset_summaries={},
        disagreement_index_results=[],
        allocation_telemetry_summary={},
        unavailable_diagnostics=[],
        recommendation={
            "recommendation_count": 1,
            "recommended_next_task": "scale the repaired variant",
            "forbidden_claims": {"controller_promotion": False},
        },
    )


def _t054_comparison() -> RootPriorGuidedSearchComparisonReport:
    return _comparison(
        include_guardrail=True,
        task_id="T054",
        cohort_identity="cohort-t054",
        count=93,
        record_range="merged:0:93",
        workers=16,
        shards=16,
        wins={
            BASELINE_ORACLE_LABEL: 4,
            POST_SEARCH_MODEL_GUIDED_LABEL: 4,
            ROOT_PRIOR_GUIDED_LABEL: 3,
            GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 4,
        },
    )


def _reference_comparisons() -> dict[str, RootPriorGuidedSearchComparisonReport]:
    return {
        "current_t046_full8": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            workers=8,
            shards=8,
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "assist0_runs1000_full21": _comparison(
            include_guardrail=False,
            task_id="T048",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            workers=16,
            shards=16,
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
            },
        ),
    }


def _generated_comparisons() -> dict[str, RootPriorGuidedSearchComparisonReport]:
    return {
        "current_t046_full8": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="875ea52e3df4cb93",
            count=8,
            record_range="0:8",
            workers=8,
            shards=8,
            wins={
                BASELINE_ORACLE_LABEL: 5,
                POST_SEARCH_MODEL_GUIDED_LABEL: 5,
                ROOT_PRIOR_GUIDED_LABEL: 6,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 6,
            },
        ),
        "assist0_runs1000_full21": _comparison(
            include_guardrail=True,
            task_id="T055",
            cohort_identity="a336ffb1fda9ed7e",
            count=21,
            record_range="0:21",
            workers=16,
            shards=16,
            wins={
                BASELINE_ORACLE_LABEL: 11,
                POST_SEARCH_MODEL_GUIDED_LABEL: 11,
                ROOT_PRIOR_GUIDED_LABEL: 13,
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL: 13,
            },
        ),
    }


def _comparison(
    *,
    include_guardrail: bool,
    task_id: str,
    cohort_identity: str,
    count: int,
    record_range: str,
    workers: int,
    shards: int,
    wins: dict[str, int],
    checkpoint_sha256: str = _CHECKPOINT_SHA256,
) -> RootPriorGuidedSearchComparisonReport:
    arms = [
        (
            BASELINE_ORACLE_LABEL,
            "baseline_oracle_search",
            _fixed_report(
                BASELINE_ORACLE_LABEL,
                cohort_identity,
                count,
                wins,
                checkpoint_sha256,
            ),
        ),
        (
            POST_SEARCH_MODEL_GUIDED_LABEL,
            "post_search_model_guided_oracle_search_v2",
            _fixed_report(
                POST_SEARCH_MODEL_GUIDED_LABEL,
                cohort_identity,
                count,
                wins,
                checkpoint_sha256,
            ),
        ),
        (
            ROOT_PRIOR_GUIDED_LABEL,
            "native_root_prior_allocation_from_checkpoint_priors",
            _fixed_report(
                ROOT_PRIOR_GUIDED_LABEL,
                cohort_identity,
                count,
                wins,
                checkpoint_sha256,
            ),
        ),
    ]
    if include_guardrail:
        arms.append(
            (
                GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                "guardrailed_native_root_prior_allocation_from_checkpoint_priors",
                _fixed_report(
                    GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL,
                    cohort_identity,
                    count,
                    wins,
                    checkpoint_sha256,
                ),
            )
        )
    return build_root_prior_guided_search_comparison_report(
        arms=arms,
        comparison_config={
            "task_id": task_id,
            "run_scale": "fixed",
            "cohort_path": f"artifacts/{cohort_identity}.jsonl",
            "cohort_identity": cohort_identity,
            "cohort_total_record_count": count,
            "evaluated_record_count": count,
            "record_range": record_range,
            "worker_count": workers,
            "shard_count": shards,
            "max_battle_steps": 200,
            "cohort_source_distribution_summary": {
                "distribution_kind_counts": {"natural_run": count}
            },
        },
    )


def _fixed_report(
    label: str,
    cohort_identity: str,
    count: int,
    wins: dict[str, int],
    checkpoint_sha256: str,
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity=cohort_identity,
        controller_provenance=_controller_provenance(label, checkpoint_sha256),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        max_battle_steps=200,
        source_pool_format_version=4,
        selection_config={"selection_seed": 55},
        per_stratum_source_counts={"20/1/MONSTER/CULTIST": count},
        battle_results=[
            _result(
                index,
                label,
                index < wins.get(label, 0),
                checkpoint_sha256,
            )
            for index in range(count)
        ],
        problems=[],
    )


def _controller_provenance(
    label: str,
    checkpoint_sha256: str = _CHECKPOINT_SHA256,
) -> dict[str, object]:
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
        config["guidance_scorer"] = {
            "checkpoint_provenance": _checkpoint(checkpoint_sha256)
        }
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
    return {"kind": label, "name": label, "config": config}


def _result(
    index: int,
    label: str,
    won: bool,
    checkpoint_sha256: str = _CHECKPOINT_SHA256,
) -> SingleBattleEvaluationResult:
    hp = 20 if won else 0
    return SingleBattleEvaluationResult(
        cohort_index=index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_seed=1000 + index,
        source_run_id=f"seed-{index}-run-0",
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
        controller_provenance=_controller_provenance(label, checkpoint_sha256),
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={"excluded_kinds": ["potion"]},
        termination_status="win" if won else "loss",
        terminal_absolute_hp=hp,
        hp_loss=70 - hp,
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


def _telemetry(index: int, label: str) -> dict[str, object]:
    telemetry: dict[str, object] = {
        "search_telemetry_summary": {
            "model_calls": {"total": 1 if label != BASELINE_ORACLE_LABEL else 0},
            "native_simulator_steps": {"total": 20},
            "root_mapping_failure_count": {"total": 0},
            "root_visits": {"total": 20},
        }
    }
    if label in {ROOT_PRIOR_GUIDED_LABEL, GUARDRAILED_ROOT_PRIOR_GUIDED_LABEL}:
        decision = {
            "allocation_metadata": {
                "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
                "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
            },
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


def _checkpoint(checkpoint_sha256: str = _CHECKPOINT_SHA256) -> dict[str, object]:
    return {
        "checkpoint_schema_id": "torch-policy-value-checkpoint-v1",
        "checkpoint_artifact_id": (
            f"torch-policy-value-checkpoint-v1-sha256:{checkpoint_sha256}"
        ),
        "trainer_input_sha256": "trainer",
    }


def _guardrail_config() -> dict[str, object]:
    return {
        "version": ROOT_PRIOR_ALLOCATION_GUARDRAIL_VERSION,
        "strategy": ROOT_PRIOR_ALLOCATION_GUARDRAIL_STRATEGY,
        "uniform_blend_weight": 0.35,
        "max_prior_probability": 0.65,
    }


def _verified_artifacts() -> list[dict[str, object]]:
    return [
        {
            "role": role,
            "path": f"{role}.json",
            "sha256": _artifact_sha256(role),
            "sha256_verified": True,
        }
        for role in T055_REQUIRED_INPUT_ROLES
    ]


def _artifact_sha256(role: str) -> str:
    if role in {
        "t043_assist0_smoke_checkpoint",
        "t043_main_runs1000_assist0_checkpoint",
    }:
        return _CHECKPOINT_SHA256
    return hashlib.sha256(role.encode("utf-8")).hexdigest()


def _write_t055_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {role: tmp_path / f"{role}.artifact" for role in T055_REQUIRED_INPUT_ROLES}
    paths["t054_retention_manifest"].write_text(
        '{"schema_id":"t054-retention-manifest-v1"}\n',
        encoding="utf-8",
    )
    for role in (
        "t048_current_fixed_cohort",
        "t048_assist0_fixed_cohort",
    ):
        paths[role].write_text(
            '{"type":"metadata","metadata":{"schema_id":"fixed-cohort-v1"}}\n',
            encoding="utf-8",
        )
    for role in (
        "t043_assist0_smoke_checkpoint",
        "t043_main_runs1000_assist0_checkpoint",
    ):
        paths[role].write_bytes(b"checkpoint")
    with paths["t054_guardrailed_repair_report"].open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        dump_t054_guardrailed_root_prior_repair_report_json(_t054_report(), stream)
    _write_comparison(paths["t054_guardrailed_comparison"], _t054_comparison())
    references = _reference_comparisons()
    generated = _generated_comparisons()
    _write_comparison(
        paths["t048_current_reference_comparison"],
        references["current_t046_full8"],
    )
    _write_comparison(
        paths["t048_assist0_reference_comparison"],
        references["assist0_runs1000_full21"],
    )
    _write_comparison(
        paths["t055_current_guardrailed_comparison"],
        generated["current_t046_full8"],
    )
    _write_comparison(
        paths["t055_assist0_guardrailed_comparison"],
        generated["assist0_runs1000_full21"],
    )
    return paths


def _write_comparison(
    path: Path,
    report: RootPriorGuidedSearchComparisonReport,
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_root_prior_guided_search_comparison_jsonl(report, stream)


def _artifact_specs(paths: dict[str, Path]) -> list[list[str]]:
    return [[role, str(paths[role]), _sha256(paths[role])] for role in paths]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
