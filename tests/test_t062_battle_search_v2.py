from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t062_battle_search_v2 import (
    T062_CALIBRATION_MANIFEST_SCHEMA_ID,
    T062_RETENTION_EXECUTION_IDENTITY,
    build_t062_calibration_manifest,
    build_t062_calibration_stage_evidence,
    build_t062_early_exit_decision_report,
    run_t062_input_preflight_from_paths,
    write_t062_retention_manifest,
    write_t062_retention_manifest_from_paths,
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


def _retention_writer_kwargs(tmp_path: Path) -> dict[str, object]:
    artifacts: dict[str, Path] = {}
    root_schemas = {
        "input_preflight_report": "t062-battle-search-v2-input-preflight-v1",
        "calibration_manifest": T062_CALIBRATION_MANIFEST_SCHEMA_ID,
        "early_exit_decision": "t062-battle-search-v2-early-exit-decision-report-v1",
    }
    for role, schema_id in root_schemas.items():
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps({"schema_id": schema_id}), encoding="utf-8")
        artifacts[role] = path
    for role in (
        "input_preflight_stdout_log",
        "input_preflight_stderr_log",
        "calibration_manifest_stdout_log",
        "calibration_manifest_stderr_log",
        "early_exit_decision_stdout_log",
        "early_exit_decision_stderr_log",
    ):
        path = tmp_path / f"{role}.log"
        path.write_text("diagnostic\n", encoding="utf-8")
        artifacts[role] = path

    stages: dict[str, dict[str, object]] = {}
    for stage_name, prefix, family in (
        ("nominal_budget_100", "nominal", "nominal"),
        ("wall_clock_minimum_budget", "wall_clock", "wall_clock_normalized"),
    ):
        stage_directory = tmp_path / prefix
        stage_directory.mkdir()
        report = _calibration_report(
            budgets={
                "baseline": 100,
                "prior_only": 1,
                "value_only": 1,
                "prior_value": 1,
            },
            ratios={"prior_only": 1.05, "value_only": 1.02, "prior_value": 0.98},
            family=family,
        )
        merged_report = stage_directory / "merged.json"
        merged_report.write_text(json.dumps(report), encoding="utf-8")
        shard_paths = [stage_directory / f"shard-{index}.json" for index in range(16)]
        stdout_log_paths = [
            stage_directory / f"shard-{index}.stdout.log" for index in range(16)
        ]
        stderr_log_paths = [
            stage_directory / f"shard-{index}.stderr.log" for index in range(16)
        ]
        for path in (*shard_paths, *stdout_log_paths, *stderr_log_paths):
            path.write_text("evidence\n", encoding="utf-8")
        merge_stdout_log = stage_directory / "merge.stdout.log"
        merge_stderr_log = stage_directory / "merge.stderr.log"
        merge_stdout_log.write_text("merge\n", encoding="utf-8")
        merge_stderr_log.write_text("merge\n", encoding="utf-8")
        stages[stage_name] = build_t062_calibration_stage_evidence(
            merged_report=report,
            merged_report_path=merged_report,
            shard_paths=shard_paths,
            stdout_log_paths=stdout_log_paths,
            stderr_log_paths=stderr_log_paths,
            worker_count_reason="16 workers, one record per explicit shard",
            regeneration_commands=[
                "wsl.exe -d Ubuntu -e bash -lc "
                f"'--lightspeed-t062-battle-search-v2-comparison "
                f"--t062-battle-search-v2-family {family}'"
            ],
        )
        artifacts.update(
            {
                f"{prefix}_merged_report": merged_report,
                f"{prefix}_merge_stdout_log": merge_stdout_log,
                f"{prefix}_merge_stderr_log": merge_stderr_log,
            }
        )
        artifacts.update(
            {
                f"{prefix}_shard_{index}_{kind}": path
                for index in range(16)
                for kind, path in (
                    ("report", shard_paths[index]),
                    ("stdout_log", stdout_log_paths[index]),
                    ("stderr_log", stderr_log_paths[index]),
                )
            }
        )
    return {
        "output_path": tmp_path / "t062-retention-manifest-v3.json",
        "artifacts": artifacts,
        "calibration_stages": stages,
        "execution_identity": deepcopy(T062_RETENTION_EXECUTION_IDENTITY),
        "regeneration_commands": [
            "wsl.exe --t062-input-preflight-report",
            "wsl.exe --lightspeed-t062-battle-search-v2-comparison "
            "--t062-battle-search-v2-family nominal",
            "wsl.exe --lightspeed-t062-battle-search-v2-comparison "
            "--t062-battle-search-v2-family wall_clock_normalized",
            "wsl.exe --t062-calibration-manifest",
            "wsl.exe --t062-early-exit-decision-report",
            "python scripts/regenerate_t062_retention_manifest.py",
        ],
    }


def test_t062_retention_writer_emits_complete_v3_utf8_schema_entries(
    tmp_path: Path,
) -> None:
    manifest = write_t062_retention_manifest(**_retention_writer_kwargs(tmp_path))  # type: ignore[arg-type]
    output = tmp_path / "t062-retention-manifest-v3.json"

    assert manifest["schema_id"] == "t062-battle-search-v2-retention-manifest-v3"
    assert output.read_bytes()[:3] != b"\xef\xbb\xbf"
    assert len(manifest["retained_artifacts"]) == 111
    by_role = {entry["role"]: entry for entry in manifest["retained_artifacts"]}
    assert by_role["calibration_manifest"]["schema_id"] == (
        "t062-battle-search-v2-calibration-manifest-v2"
    )
    assert by_role["nominal_shard_0_stdout_log"]["schema_id"] is None


@pytest.mark.parametrize("mutation", ("artifacts", "identity", "commands"))
def test_t062_retention_writer_rejects_incomplete_current_schema_contract(
    tmp_path: Path, mutation: str
) -> None:
    kwargs = _retention_writer_kwargs(tmp_path)
    if mutation == "artifacts":
        kwargs["artifacts"].pop("early_exit_decision")  # type: ignore[index]
        message = "incomplete retained artifact roles"
    elif mutation == "identity":
        kwargs["execution_identity"].pop("controller")  # type: ignore[index]
        message = "incomplete execution identity"
    else:
        kwargs["regeneration_commands"] = ["wsl.exe --t062-input-preflight-report"]
        message = "six named commands"

    with pytest.raises(ValueError, match=message):
        write_t062_retention_manifest(**kwargs)  # type: ignore[arg-type]


def test_t062_retention_writer_from_paths_rejects_incomplete_root_roles(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="incomplete root artifact roles"):
        write_t062_retention_manifest_from_paths(
            output_path=tmp_path / "manifest.json",
            root_artifacts={},
            nominal_merged_report_path=tmp_path / "nominal.json",
            nominal_merge_stdout_log_path=tmp_path / "nominal.stdout.log",
            nominal_merge_stderr_log_path=tmp_path / "nominal.stderr.log",
            nominal_shard_directory=tmp_path / "nominal",
            nominal_regeneration_command="nominal command",
            wall_clock_merged_report_path=tmp_path / "wall.json",
            wall_clock_merge_stdout_log_path=tmp_path / "wall.stdout.log",
            wall_clock_merge_stderr_log_path=tmp_path / "wall.stderr.log",
            wall_clock_shard_directory=tmp_path / "wall",
            wall_clock_regeneration_command="wall command",
            execution_identity={},
            regeneration_commands=["one command"],
        )


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


def test_t062_retention_background_wait_fails_when_any_shard_fails() -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "regenerate_t062_retention_manifest.py"
    )
    specification = importlib.util.spec_from_file_location(
        "t062_retention_generator", script_path
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    shell = (
        'set -euo pipefail; pids=(); (exit 7) & pids+=("$!"); '
        '(exit 0) & pids+=("$!"); '
        + module._wait_for_background_jobs_shell()
        + "echo should-not-run"
    )
    result = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "-e", "bash", "-lc", shell],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "should-not-run" not in result.stdout


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
