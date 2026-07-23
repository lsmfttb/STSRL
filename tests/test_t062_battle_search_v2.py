from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t062_battle_search_v2 import (
    T062_CALIBRATION_MANIFEST_SCHEMA_ID,
    build_t062_calibration_manifest,
    build_t062_calibration_stage_evidence,
    build_t062_early_exit_decision_report,
    run_t062_input_preflight_from_paths,
    write_t062_retention_manifest,
)


def test_t062_input_preflight_verifies_explicit_stable_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "t061-retention-manifest.json"
    cohort = tmp_path / "t052-fixed-cohort.jsonl"
    checkpoint = tmp_path / "t043-checkpoint.pt"
    output = tmp_path / "preflight.json"
    manifest_payload = {
        "schema_id": "t061-retention-manifest-v2",
        "retention_root": "D:/stable/artifacts/t061",
        "raw_artifacts_may_be_deleted_when": "T062 input extraction complete",
        "manifest_identity": {"bytes": 0, "sha256": ""},
    }
    canonical = dict(manifest_payload)
    canonical["manifest_identity"] = {"bytes": None, "sha256": None}
    canonical_sha256 = hashlib.sha256(
        (json.dumps(canonical, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    manifest_payload["manifest_identity"]["sha256"] = canonical_sha256
    for _ in range(3):
        manifest.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_payload["manifest_identity"]["bytes"] = manifest.stat().st_size
    manifest.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cohort.write_bytes(b"cohort")
    checkpoint.write_bytes(b"checkpoint")
    from sts_combat_rl.commands import t062_battle_search_v2 as command

    monkeypatch.setattr(command, "T061_RETENTION_MANIFEST_SHA256", canonical_sha256)
    monkeypatch.setattr(command, "T052_COHORT_SHA256", _sha256(cohort))
    monkeypatch.setattr(command, "T052_COHORT_BYTES", cohort.stat().st_size)
    monkeypatch.setattr(command, "T043_CHECKPOINT_SHA256", _sha256(checkpoint))
    monkeypatch.setattr(command, "T043_CHECKPOINT_BYTES", checkpoint.stat().st_size)

    report = run_t062_input_preflight_from_paths(
        output_path=output,
        t061_retention_manifest_path=manifest,
        t052_cohort_path=cohort,
        t043_checkpoint_path=checkpoint,
    )

    assert report["command_passed"]
    assert json.loads(output.read_text(encoding="utf-8"))["command_passed"]


def test_t062_input_preflight_rejects_missing_explicit_input(tmp_path: Path) -> None:
    report = run_t062_input_preflight_from_paths(
        output_path=tmp_path / "preflight.json",
        t061_retention_manifest_path=tmp_path / "missing-manifest.json",
        t052_cohort_path=tmp_path / "missing-cohort.jsonl",
        t043_checkpoint_path=tmp_path / "missing-checkpoint.pt",
    )

    assert not report["command_passed"]
    assert len(report["problems"]) == 3


def test_t062_cli_requires_all_explicit_input_paths() -> None:
    parser = build_parser()
    args = parser.parse_args(["--t062-input-preflight-report", "preflight.json"])

    assert validate_cli_args(args).startswith("--t062-input-preflight-report requires")


def test_t062_calibration_distinguishes_proven_and_unlocked_minimums() -> None:
    manifest = build_t062_calibration_manifest(
        nominal_budget_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 100,
                "value_only": 100,
                "prior_value": 100,
            },
            ratios={"prior_only": 1.2, "value_only": 0.2, "prior_value": 0.3},
            family="nominal",
        ),
        wall_clock_candidate_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
        ),
    )

    assert manifest["schema_id"] == T062_CALIBRATION_MANIFEST_SCHEMA_ID
    assert manifest["proven_infeasible_arms"] == ["prior_only"]
    assert manifest["unlocked_or_untested_arms"] == ["prior_value"]
    assert (
        manifest["wall_clock_locks"]["prior_value"]["status"]
        == "unlocked_below_target_minimum"
    )
    assert manifest["early_exit_eligible"]
    assert not manifest["primary_comparison_authorized"]
    assert manifest["not_fixed_cohort_outcome_evidence"]


def test_t062_early_exit_decision_recommends_exactly_t067() -> None:
    calibration = build_t062_calibration_manifest(
        nominal_budget_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 100,
                "value_only": 100,
                "prior_value": 100,
            },
            ratios={"prior_only": 1.2, "value_only": 0.2, "prior_value": 0.3},
            family="nominal",
        ),
        wall_clock_candidate_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
        ),
    )

    decision = build_t062_early_exit_decision_report(calibration_manifest=calibration)

    assert decision["recommendation"] == "T067"
    assert decision["primary_comparison_authorized"] is False
    assert decision["fixed_cohort_outcome_claims"] == "not_authorized_not_reported"


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda nominal, candidate: (
                nominal.__setitem__("family", "wall_clock_normalized"),
                nominal["controller_provenance"]["baseline"]["config"][
                    "search_budget"
                ].__setitem__("simulations", 99),
            ),
            "expected 'nominal' family",
        ),
        (
            lambda nominal, candidate: candidate.__setitem__("family", "nominal"),
            "expected 'wall_clock_normalized' family",
        ),
        (
            lambda nominal, candidate: candidate.__setitem__(
                "cohort_identity", "different-cohort"
            ),
            "differ in cohort_identity",
        ),
        (
            lambda nominal, candidate: (
                candidate.__setitem__("worker_count", 1),
                candidate.__setitem__("shard_count", 1),
            ),
            "16 workers and 16 shards",
        ),
        (
            lambda nominal, candidate: (
                candidate["arms"]["prior_only"].__setitem__("errors", 4),
                candidate["arms"]["prior_only"].__setitem__("truncations", 3),
            ),
            "errors or truncations",
        ),
    ),
)
def test_t062_calibration_rejects_mutated_evidence(mutation, message: str) -> None:
    nominal = _calibration_report(
        budgets={
            "baseline": 100,
            "prior_only": 100,
            "value_only": 100,
            "prior_value": 100,
        },
        ratios={"prior_only": 1.2, "value_only": 0.2, "prior_value": 0.3},
        family="nominal",
    )
    candidate = _calibration_report(
        budgets={"baseline": 100, "prior_only": 1, "value_only": 1, "prior_value": 1},
        ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
    )
    mutation(nominal, candidate)

    with pytest.raises(ValueError, match=message):
        build_t062_calibration_manifest(
            nominal_budget_report=nominal,  # type: ignore[arg-type]
            wall_clock_candidate_report=candidate,  # type: ignore[arg-type]
        )


def test_t062_early_exit_decision_rejects_contradictory_manifest() -> None:
    calibration = build_t062_calibration_manifest(
        nominal_budget_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 100,
                "value_only": 100,
                "prior_value": 100,
            },
            ratios={"prior_only": 1.2, "value_only": 0.2, "prior_value": 0.3},
            family="nominal",
        ),
        wall_clock_candidate_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
        ),
    )
    contradictory = deepcopy(calibration)
    contradictory["command_passed"] = False
    contradictory["early_exit_eligible"] = False
    contradictory["primary_comparison_authorized"] = True

    with pytest.raises(ValueError, match="passed calibration manifest"):
        build_t062_early_exit_decision_report(calibration_manifest=contradictory)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        ("task_id", "T999", "task id T062"),
        ("calibration_record_range", "wrong", "records 0:16"),
        ("wall_clock_calibration_locked", True, "lock summary"),
        ("not_fixed_cohort_outcome_evidence", False, "cost-only evidence"),
    ),
)
def test_t062_early_exit_decision_rejects_bad_top_level_identity(
    key: str, value: object, message: str
) -> None:
    calibration = build_t062_calibration_manifest(
        nominal_budget_report=_calibration_report(
            budgets={
                label: 100
                for label in ("baseline", "prior_only", "value_only", "prior_value")
            },
            ratios={"prior_only": 1.2, "value_only": 0.2, "prior_value": 0.3},
            family="nominal",
        ),
        wall_clock_candidate_report=_calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
        ),
    )
    calibration[key] = value

    with pytest.raises(ValueError, match=message):
        build_t062_early_exit_decision_report(calibration_manifest=calibration)


def test_t062_calibration_stage_evidence_records_all_shards_and_logs(
    tmp_path: Path,
) -> None:
    report = _calibration_report(
        budgets={"baseline": 100, "prior_only": 1, "value_only": 1, "prior_value": 1},
        ratios={"prior_only": 2.147, "value_only": 0.97, "prior_value": 0.885},
    )
    merged = tmp_path / "merged.json"
    merged.write_text(json.dumps(report), encoding="utf-8")
    shards = [tmp_path / f"shard-{index:02d}.json" for index in range(16)]
    stdout = [tmp_path / f"shard-{index:02d}.stdout.log" for index in range(16)]
    stderr = [tmp_path / f"shard-{index:02d}.stderr.log" for index in range(16)]
    for paths in (shards, stdout, stderr):
        for path in paths:
            path.write_text("evidence\n", encoding="utf-8")

    evidence = build_t062_calibration_stage_evidence(
        merged_report=report,
        merged_report_path=merged,
        shard_paths=shards,
        stdout_log_paths=stdout,
        stderr_log_paths=stderr,
        worker_count_reason="16 workers, one record per explicit shard",
        regeneration_commands=["python -m sts_combat_rl.cli ..."],
    )

    assert evidence["record_range"] == "0:16"
    assert len(evidence["shards"]) == 16
    assert evidence["failure_counts"]["source_match_problem_count"] == 0
    assert evidence["per_arm_cost_totals"]["prior_only"]["model_calls"] == 16

    report["worker_count"] = 1
    with pytest.raises(ValueError, match="16 workers and 16 shards"):
        build_t062_calibration_stage_evidence(
            merged_report=report,
            merged_report_path=merged,
            shard_paths=shards,
            stdout_log_paths=stdout,
            stderr_log_paths=stderr,
            worker_count_reason="16 workers, one record per explicit shard",
            regeneration_commands=["python -m sts_combat_rl.cli ..."],
        )


def test_t062_retention_writer_emits_v3_utf8_schema_entries(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    log = tmp_path / "report.stderr.log"
    report.write_text(
        '{"schema_id":"t062-battle-search-v2-comparison-v1"}\n', encoding="utf-8"
    )
    log.write_text("diagnostic\n", encoding="utf-8")
    output = tmp_path / "t062-retention-manifest-v3.json"

    manifest = write_t062_retention_manifest(
        output_path=output,
        artifacts={"merged_report": report, "stderr_log": log},
        calibration_stages={"nominal": {"record_range": "0:16", "shards": []}},
        execution_identity={"native_commit": "3cb9ebe", "checkpoint": "T043"},
        regeneration_commands=["wsl.exe -d Ubuntu -e bash -lc 'exact command'"],
    )

    assert manifest["schema_id"] == "t062-battle-search-v2-retention-manifest-v3"
    assert output.read_bytes()[:3] != b"\xef\xbb\xbf"
    assert (
        manifest["retained_artifacts"][0]["schema_id"]
        == "t062-battle-search-v2-comparison-v1"
    )
    assert manifest["retained_artifacts"][1]["schema_id"] is None


def test_t062_retention_writer_rejects_its_existing_output_as_an_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "t062-retention-manifest-v3.json"
    output.write_text('{"old":"manifest"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="must not include its output path"):
        write_t062_retention_manifest(
            output_path=output,
            artifacts={"retention_manifest": output},
            regeneration_commands=[
                "python -m sts_combat_rl.cli --t062-retention-manifest"
            ],
        )


def _calibration_report(
    *,
    budgets: dict[str, int],
    ratios: dict[str, float],
    family: str = "wall_clock_normalized",
) -> dict[str, object]:
    records = {}
    arms = {
        label: {
            "record_count": 16,
            "truncations": 0,
            "errors": 0,
            "native_simulator_steps": 1_600 if label != "baseline" else 160_000,
            "model_calls": 16 if label != "baseline" else 0,
            "outer_simulator_steps": 240,
            "wall_clock_seconds": 100.0
            if label == "baseline"
            else 100.0 * ratios[label],
            "records": records.setdefault(
                label,
                [
                    {
                        "cohort_index": index,
                        "source_checkpoint_id": f"checkpoint-{index}",
                        "structural_metadata": {
                            "source_run_id": "run",
                            "source_battle_index": index,
                        },
                        "termination_status": "loss",
                        "problems": [],
                        "outer_simulator_steps": 15,
                        "wall_clock_seconds": (
                            100.0 if label == "baseline" else 100.0 * ratios[label]
                        )
                        / 16,
                        "controller_compute_telemetry": {
                            "oracle_search_native_simulator_steps": (
                                1_600 if label != "baseline" else 160_000
                            )
                            / 16,
                            "oracle_search_model_calls": (
                                16 if label != "baseline" else 0
                            )
                            / 16,
                        },
                    }
                    for index in range(16)
                ],
            ),
        }
        for label in ("baseline", "prior_only", "value_only", "prior_value")
    }
    return {
        "schema_id": "t062-battle-search-v2-comparison-v1",
        "task_id": "T062",
        "family": family,
        "report_kind": "merged_comparison",
        "format_version": 1,
        "cohort_identity": "fixed-cohort",
        "cohort_total_record_count": 93,
        "evaluated_record_count": 16,
        "expected_record_count": 16,
        "worker_count": 16,
        "shard_count": 16,
        "shards": [f"shard-{index:02d}.json" for index in range(16)],
        "action_space": {"initial_no_potions": True},
        "max_battle_steps": 200,
        "command_passed": True,
        "problems": [],
        "controller_provenance": {
            label: {"config": {"search_budget": {"simulations": budget}}}
            for label, budget in budgets.items()
        },
        "arms": arms,
        "paired_vs_baseline": {
            label: {
                "overall": {
                    "cost_ratio_guided_over_baseline": {"wall_clock_seconds": ratio}
                }
            }
            for label, ratio in ratios.items()
        },
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
