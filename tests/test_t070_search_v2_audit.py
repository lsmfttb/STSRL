from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import sys
import sysconfig
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.t070_search_v2_audit import (
    BUDGET_CURVE_SCHEMA_ID,
    DECISION_SCHEMA_ID,
    GEOMETRY_REPORT_SCHEMA_ID,
    HIGH_BUDGET_CELL_SCHEMA_ID,
    HIGH_BUDGET_STAGE_CONFIGS,
    MERGED_STAGE_SCHEMA_ID,
    NATIVE_COMMIT,
    NATIVE_RUNTIME_SCHEMA_ID,
    PRIMARY_CELL_SCHEMA_ID,
    PRIMARY_STAGE_CONFIGS,
    PRIMARY_REPORT_SCHEMA_ID,
    PRIMARY_RANGES,
    _build_outcome_blind_subset,
    _runtime_configure_command,
    _runtime_verification_commands,
    _validate_cmake_python_identity,
    build_budget_curve_and_geometry,
    build_decision_report,
    build_primary_report,
    build_retention_manifest,
    expected_checkpoint_identity_from_stage_manifest,
    merge_single_arm_stage,
    probe_t070_native_runtime_identity,
    validate_t070_frozen_stage,
    validate_t070_preflight,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
)


def test_t070_runtime_configure_binds_modern_cmake_python(tmp_path: Path) -> None:
    runner = tmp_path / "venv" / "bin" / "python3.13"
    command = _runtime_configure_command(
        native_checkout=tmp_path / "native",
        native_build_root=tmp_path / "native" / "build",
        cmake_policy_version_minimum="3.5",
        python_executable=runner,
    )

    assert "-DPYBIND11_FINDPYTHON=ON" in command
    assert f"-DPython_EXECUTABLE={runner}" in command
    assert not any(argument.startswith("-DPYTHON_EXECUTABLE=") for argument in command)


def test_t070_cmake_python_identity_requires_runner_abi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = tmp_path / "venv" / "bin" / "python3.13"
    runner.parent.mkdir(parents=True)
    runner.write_bytes(b"runner")
    build = tmp_path / "native" / "build"
    build.mkdir(parents=True)
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert isinstance(suffix, str)
    extension = build / f"slaythespire{suffix}"
    extension.write_bytes(b"extension")
    (build / "CMakeCache.txt").write_text(
        f"Python_EXECUTABLE:FILEPATH={runner}\n", encoding="utf-8"
    )

    identity = _validate_cmake_python_identity(
        native_build_root=build, python_executable=runner
    )

    assert identity["cmake_python_executable"] == str(runner.resolve())
    assert identity["runner_python_executable"] == str(runner.resolve())
    assert identity["runner_python_extension_suffix"] == suffix
    assert identity["matching_extension_path"] == str(extension.resolve())

    wrong = tmp_path / "usr" / "bin" / "python3.14"
    wrong.parent.mkdir(parents=True)
    wrong.write_bytes(b"wrong")
    (build / "CMakeCache.txt").write_text(
        f"Python_EXECUTABLE:FILEPATH={wrong}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="selected a different Python"):
        _validate_cmake_python_identity(
            native_build_root=build, python_executable=runner
        )


def test_t070_runtime_verification_uses_exact_runner_and_build(tmp_path: Path) -> None:
    checkout = tmp_path / "native"
    build = checkout / "build"
    runner = tmp_path / "venv" / "bin" / "python3.13"

    api_smoke, geometry = _runtime_verification_commands(
        native_checkout=checkout,
        native_build_root=build,
        python_executable=runner,
    )

    assert api_smoke == [
        str(runner),
        str(checkout / "scripts" / "stsrl_api_smoke.py"),
        "--build-dir",
        str(build),
    ]
    assert geometry == [
        str(runner),
        str(checkout / "scripts" / "test_battle_search_v2_tree_geometry.py"),
        "--build-dir",
        str(build),
    ]


def test_t070_preflight_requires_runtime_gate_commands_and_logs(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    verifier = tmp_path / "verifier.sh"
    manifest.write_text("manifest", encoding="utf-8")
    verifier.write_text("verifier", encoding="utf-8")
    log_fields = (
        "stdout",
        "stderr",
        "runtime_build_stdout",
        "runtime_build_stderr",
        "runtime_api_smoke_stdout",
        "runtime_api_smoke_stderr",
        "runtime_geometry_stdout",
        "runtime_geometry_stderr",
    )
    logs = {}
    for field in log_fields:
        path = tmp_path / f"{field}.log"
        path.write_text(field, encoding="utf-8")
        logs[field] = str(path)
    python_executable = str((tmp_path / "python3.13").resolve())
    suffix = ".cpython-313-x86_64-linux-gnu.so"
    extension = str((tmp_path / f"slaythespire{suffix}").resolve())
    payload = {
        "schema_id": "t070-native-capability-preflight-v1",
        "stsrl_code_commit": "a" * 40,
        "native_commit": NATIVE_COMMIT,
        "semantic_parity_result": True,
        "runtime_api_smoke_passed": True,
        "runtime_geometry_passed": True,
        "return_codes": [0, 0, 0, 0, 0],
        "return_code": 0,
        "worker_count": 16,
        "command_passed": True,
        "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "source_verifier_sha256": hashlib.sha256(verifier.read_bytes()).hexdigest(),
        "verifier_clean_worktree_mode": "temporary_detached_exact_commit_worktree",
        "verifier_clean_worktree_scope": "clean_source_verifier_only",
        "runtime_source_mode": "exact_head_tracked_clean_stable_checkout",
        "build_jobs": 16,
        "cmake_identity": "cmake version test",
        "manifest_build_directory": "build-stsrl-source-py",
        "manifest_cmake_target": "slaythespire",
        "commands": [
            {"name": name, "argv": [name]}
            for name in (
                "clean_source_verifier",
                "runtime_cmake_configure",
                "runtime_cmake_build",
                "runtime_api_smoke",
                "runtime_geometry",
            )
        ],
        "native_runtime_identity": {
            "python_executable": python_executable,
            "python_extension_suffix": suffix,
            "native_extension_path": extension,
        },
        "cmake_python_identity": {
            "cmake_python_executable": python_executable,
            "runner_python_executable": python_executable,
            "runner_python_extension_suffix": suffix,
            "matching_extension_path": extension,
        },
        **logs,
    }
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps(payload), encoding="utf-8")

    validated = validate_t070_preflight(
        preflight,
        code_commit="a" * 40,
        source_manifest_path=manifest,
        source_verifier_path=verifier,
    )
    assert validated["return_codes"] == [0, 0, 0, 0, 0]

    Path(logs["runtime_geometry_stdout"]).unlink()
    with pytest.raises(ValueError, match="log evidence is incomplete"):
        validate_t070_preflight(
            preflight,
            code_commit="a" * 40,
            source_manifest_path=manifest,
            source_verifier_path=verifier,
        )


def test_t070_native_runtime_identity_binds_extension_and_abi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "native"
    build = checkout / "build-t070"
    build.mkdir(parents=True)
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert isinstance(suffix, str)
    extension = build / f"slaythespire{suffix}"
    extension.write_bytes(b"exact-native-extension")

    def fake_git(_checkout: Path, *args: str) -> str:
        return NATIVE_COMMIT if args == ("rev-parse", "HEAD") else ""

    monkeypatch.setattr(
        "sts_combat_rl.commands.t070_search_v2_audit._git_output", fake_git
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.t070_search_v2_audit.import_module",
        lambda name: SimpleNamespace(__file__=str(extension)),
    )

    identity = probe_t070_native_runtime_identity(
        native_checkout=checkout,
        native_build_root=build,
    )

    assert identity["schema_id"] == NATIVE_RUNTIME_SCHEMA_ID
    assert identity["native_commit"] == NATIVE_COMMIT
    assert identity["native_source_checkout"] == str(checkout.resolve())
    assert identity["native_build_root"] == str(build.resolve())
    assert (
        identity["native_extension_sha256"]
        == hashlib.sha256(extension.read_bytes()).hexdigest()
    )
    assert identity["native_extension_size_bytes"] == extension.stat().st_size
    assert identity["python_soabi"] == sysconfig.get_config_var("SOABI")
    assert identity["python_extension_suffix"] == suffix


def test_t070_native_runtime_identity_rejects_extension_outside_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "native"
    build = checkout / "build-t070"
    build.mkdir(parents=True)
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    extension = checkout / f"slaythespire{suffix}"
    extension.write_bytes(b"wrong-build")
    monkeypatch.setattr(
        "sts_combat_rl.commands.t070_search_v2_audit._git_output",
        lambda _checkout, *args: NATIVE_COMMIT if args == ("rev-parse", "HEAD") else "",
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.t070_search_v2_audit.import_module",
        lambda name: SimpleNamespace(__file__=str(extension)),
    )

    with pytest.raises(ValueError, match="outside the declared build root"):
        probe_t070_native_runtime_identity(
            native_checkout=checkout,
            native_build_root=build,
        )


def test_t070_schema_contract_covers_all_required_outputs() -> None:
    path = Path("docs/t070_artifact_schema_contract.json")
    contract = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "t070-native-capability-preflight-v1",
        "t070-frozen-experiment-manifest-v1",
        "t070-search-v2-primary-comparison-v1",
        "t070-budget-subset-manifest-v1",
        "t070-search-v2-budget-curve-v1",
        "t070-search-tree-geometry-report-v1",
        "t070-search-v2-decision-v1",
        "t070-stage-execution-v1",
        "t070-retention-manifest-v1",
    }
    rows = contract["schemas"]
    assert {row["schema_id"] for row in rows} == expected
    for row in rows:
        assert row["required_fields"]
        assert row["identity_rules"]
        assert row["ordering"]
        assert row["missingness"]
        assert row["compatibility"]
    supplemental_expected = {
        "t070-native-runtime-identity-v1",
        "t070-search-v2-primary-arm-cell-v1",
        "t070-search-v2-high-budget-arm-cell-v1",
        "t070-single-arm-shard-v1",
        "t070-single-arm-merged-stage-v1",
        "t070-stage-execution-detail-v1",
        "t070-search-tree-geometry-decision-v1",
        "t070-retained-log-index-v1",
    }
    supplemental = contract["supplemental_schemas"]
    assert {row["schema_id"] for row in supplemental} == supplemental_expected
    for row in supplemental:
        assert row["required_fields"]
        assert row["identity_rules"]
        assert row["ordering"]
        assert row["missingness"]
        assert row["compatibility"]
    task = Path(
        "docs/tasks/T070-battle-search-v2-fixed-cohort-outcome-and-budget-sufficiency-audit.md"
    ).read_text(encoding="utf-8")
    assert "t070_artifact_schema_contract.json" in task


def test_t070_checkpoint_identity_can_be_supplied_by_t064_manifest(tmp_path) -> None:
    checkpoint_path = tmp_path / "checkpoint.pt"
    checkpoint_path.write_bytes(b"checkpoint")
    checkpoint = {
        "path": str(checkpoint_path),
        "sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "bytes": checkpoint_path.stat().st_size,
    }
    historical = tmp_path / "t070.json"
    historical.write_text(
        json.dumps(
            {
                "schema_id": "t070-frozen-experiment-manifest-v1",
                "input_identities": {"t043_checkpoint": checkpoint},
            }
        ),
        encoding="utf-8",
    )
    t064 = tmp_path / "t064.json"
    t064.write_text(
        json.dumps(
            {
                "schema_id": "t064-curriculum-manifest-v1",
                "t070_stage_manifest": {"checkpoint": checkpoint},
            }
        ),
        encoding="utf-8",
    )
    assert expected_checkpoint_identity_from_stage_manifest(historical) == checkpoint
    assert expected_checkpoint_identity_from_stage_manifest(t064) == checkpoint


def test_t070_stage_validation_accepts_identity_bound_t064_checkpoint_wrapper(
    tmp_path: Path,
) -> None:
    cohort = tmp_path / "cohort.jsonl"
    source_manifest = tmp_path / "source.json"
    verifier = tmp_path / "verify.sh"
    old_checkpoint = tmp_path / "old.pt"
    new_checkpoint = tmp_path / "new.pt"
    for path, content in (
        (cohort, b"cohort"),
        (source_manifest, b"source"),
        (verifier, b"verifier"),
        (old_checkpoint, b"old"),
        (new_checkpoint, b"new"),
    ):
        path.write_bytes(content)

    def identity(path: Path) -> dict[str, object]:
        return {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }

    frozen = tmp_path / "frozen.json"
    frozen.write_text(
        json.dumps(
            {
                "schema_id": "t070-frozen-experiment-manifest-v1",
                "code_commit": "a" * 40,
                "native_commit": NATIVE_COMMIT,
                "command_passed": True,
                "input_identities": {
                    "t052_fixed_cohort": identity(cohort),
                    "t043_checkpoint": identity(old_checkpoint),
                    "sts_lightspeed_source_manifest": identity(source_manifest),
                    "sts_lightspeed_source_verifier": identity(verifier),
                },
                "primary_stage_inventory": [
                    {
                        "stage_name": "baseline-0100",
                        "arm": "baseline",
                        "family": "shared",
                        "native_budget": 100,
                        "tree_geometry_enabled": False,
                    }
                ],
                "primary_shard_ranges": list(PRIMARY_RANGES),
                "primary_worker_count": 16,
            }
        ),
        encoding="utf-8",
    )
    wrapper = tmp_path / "t064.json"
    wrapper.write_text(
        json.dumps(
            {
                "schema_id": "t064-curriculum-manifest-v1",
                "code_commit": "b" * 40,
                "t070_stage_manifest": {
                    "frozen_t070_manifest": identity(frozen),
                    "checkpoint": identity(new_checkpoint),
                },
            }
        ),
        encoding="utf-8",
    )
    _, ranges = validate_t070_frozen_stage(
        wrapper,
        code_commit="b" * 40,
        stage_name="baseline-0100",
        arm="baseline",
        family="shared",
        budget=100,
        range_kind="primary",
        tree_geometry=False,
        cohort_path=cohort,
        checkpoint_path=new_checkpoint,
        source_manifest_path=source_manifest,
        source_verifier_path=verifier,
    )
    assert ranges == PRIMARY_RANGES
    _, direct_ranges = validate_t070_frozen_stage(
        frozen,
        code_commit="a" * 40,
        stage_name="baseline-0100",
        arm="baseline",
        family="shared",
        budget=100,
        range_kind="primary",
        tree_geometry=False,
        cohort_path=cohort,
        checkpoint_path=old_checkpoint,
        source_manifest_path=source_manifest,
        source_verifier_path=verifier,
    )
    assert direct_ranges == PRIMARY_RANGES


def test_t070_shard_runner_routes_t064_wrapper_through_checkout_and_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code_commit = "b" * 40
    historical_code_commit = "a" * 40
    cohort = tmp_path / "cohort.jsonl"
    checkpoint = tmp_path / "checkpoint.pt"
    for path, content in ((cohort, b"cohort"), (checkpoint, b"checkpoint")):
        path.write_bytes(content)

    def identity(path: Path) -> dict[str, object]:
        return {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }

    source_manifest = Path("docs/sts_lightspeed_source_manifest.json")
    verifier = Path("scripts/verify_lightspeed_source.sh")
    frozen = tmp_path / "historical-frozen.json"
    frozen.write_text(
        json.dumps(
            {
                "schema_id": "t070-frozen-experiment-manifest-v1",
                "code_commit": historical_code_commit,
                "native_commit": NATIVE_COMMIT,
                "command_passed": True,
                "input_identities": {
                    "t052_fixed_cohort": identity(cohort),
                    "t043_checkpoint": identity(checkpoint),
                    "sts_lightspeed_source_manifest": identity(source_manifest),
                    "sts_lightspeed_source_verifier": identity(verifier),
                },
                "primary_stage_inventory": [
                    {
                        "stage_name": "baseline-0100",
                        "arm": "baseline",
                        "family": "shared",
                        "native_budget": 100,
                        "tree_geometry_enabled": False,
                    }
                ],
                "primary_shard_ranges": list(PRIMARY_RANGES),
                "primary_worker_count": 16,
            }
        ),
        encoding="utf-8",
    )
    wrapper = tmp_path / "t064-wrapper.json"
    wrapper.write_text(
        json.dumps(
            {
                "schema_id": "t064-curriculum-manifest-v1",
                "code_commit": code_commit,
                "t070_stage_manifest": {
                    "frozen_t070_manifest": identity(frozen),
                    "checkpoint": identity(checkpoint),
                },
            }
        ),
        encoding="utf-8",
    )
    script_path = Path("scripts/run_t070_search_stage_shard.py")
    spec = importlib.util.spec_from_file_location("t070_shard_runner_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checkout_calls: list[str] = []
    preflight_calls: list[str] = []
    monkeypatch.setattr(
        module,
        "verify_exact_git_checkout",
        lambda _root, commit: checkout_calls.append(commit),
    )
    monkeypatch.setattr(
        module,
        "validate_t070_preflight",
        lambda _path, **kwargs: (
            preflight_calls.append(kwargs["code_commit"])
            or {"native_runtime_identity": {"schema_id": "fixture"}}
        ),
    )
    monkeypatch.setattr(
        module, "build_torch_guidance_scorer_from_checkpoint", lambda _path: object()
    )
    monkeypatch.setattr(module, "BattleSearchV2Controller", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        module, "run_single_arm_shard", lambda **kwargs: {"command_passed": True}
    )
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script_path),
            "--cohort",
            str(cohort),
            "--checkpoint",
            str(checkpoint),
            "--frozen-manifest",
            str(wrapper),
            "--native-preflight",
            str(tmp_path / "preflight.json"),
            "--native-checkout",
            str(tmp_path / "native"),
            "--native-build-root",
            str(tmp_path / "build"),
            "--output",
            str(output),
            "--code-commit",
            code_commit,
            "--stage-name",
            "baseline-0100",
            "--arm",
            "baseline",
            "--family",
            "shared",
            "--budget",
            "100",
            "--record-range",
            "0:6",
            "--shard-index",
            "0",
            "--range-kind",
            "primary",
        ],
    )
    assert module.main() == 0
    assert checkout_calls == [code_commit]
    assert preflight_calls == [code_commit]


def test_t070_retention_has_per_file_command_and_compatibility(
    tmp_path: Path,
) -> None:
    paths = []
    for relative in (
        "native-preflight/preflight.json",
        "frozen-manifest/frozen.json",
        "primary/stage/shard.json",
        "reports/decision.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_id": "fixture-v1"}), encoding="utf-8")
        paths.append(path)
    commands = {
        "preflight": "preflight-command",
        "freeze": "freeze-command",
        "stage": "stage-command",
        "finalize": "finalize-command",
    }
    manifest = build_retention_manifest(
        artifact_root=tmp_path,
        retained_paths=paths,
        regeneration_commands=commands,
        code_commit="a" * 40,
        decision={"recommendation": "planner recommendation"},
    )
    by_relative = {
        str(Path(row["path"]).relative_to(tmp_path)).replace("\\", "/"): row
        for row in manifest["retained_artifacts"]
    }
    assert (
        by_relative["native-preflight/preflight.json"]["regeneration_command"]
        == "preflight-command"
    )
    assert (
        by_relative["frozen-manifest/frozen.json"]["regeneration_command"]
        == "freeze-command"
    )
    assert (
        by_relative["primary/stage/shard.json"]["regeneration_command"]
        == "stage-command"
    )
    assert (
        by_relative["reports/decision.json"]["regeneration_command"]
        == "finalize-command"
    )
    assert all(
        row["compatibility_requirements"] for row in manifest["retained_artifacts"]
    )
    assert manifest["compatibility_requirements"]


def _record(index: int, *, act: int, room_type: str) -> FixedCohortRecord:
    return FixedCohortRecord(
        cohort_index=index,
        source_pool_record_index=1000 + index,
        source_checkpoint_id=f"checkpoint-{index}",
        source_run_id=f"run-{index // 3}",
        source_seed=index,
        source_battle_index=index,
        structural_stratum=(20, act, room_type, index),
        structural_metadata={
            "ascension": 20,
            "act": act,
            "room_type": room_type,
            "encounter_id": index,
        },
        source_controller_provenance={},
        source_battle_controller_provenance={},
        source_non_combat_controller_provenance={},
        action_trace=(),
    )


def test_t070_subset_is_structural_outcome_blind_and_exact() -> None:
    records = [
        *[_record(index, act=2, room_type="MONSTER") for index in range(5)],
        *[_record(index, act=1, room_type="BOSS") for index in range(5, 93)],
    ]
    cohort = FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance={},
        selection_config=FixedCohortSelectionConfig(selection_seed=1),
        records=records,
    )
    subset, manifest = _build_outcome_blind_subset(cohort, "a" * 40)

    assert len(subset.records) == 16
    assert [record.cohort_index for record in subset.records] == list(range(16))
    assert sum(row["stratum"] == "act2_plus" for row in manifest["records"]) == 5
    assert sum(row["stratum"] == "boss_only" for row in manifest["records"]) == 11
    assert manifest["outcome_blind"] is True
    assert "outcomes" in manifest["selection_forbidden_fields"]
    assert all(
        set(row["canonical_source_identity"]).isdisjoint(
            {"outcomes", "selected_actions", "terminal_resources"}
        )
        for row in manifest["records"]
    )


def _pair(delta: int, *, ci_lower: float = 0.0, hp: float = 0.0, ratio: float = 1.0):
    return {
        name: {
            "record_count": 93
            if name == "overall"
            else (88 if name == "boss_only" else 5),
            "paired_win_delta": delta,
            "paired_win_delta_mean": delta / 93,
            "paired_win_delta_bootstrap_95ci": [ci_lower, 0.1],
            "mean_terminal_hp_delta_among_outcome_ties": hp,
            "cost_ratio_guided_over_baseline": {
                "native_simulator_steps": ratio,
                "wall_clock_seconds": ratio,
            },
        }
        for name in ("overall", "boss_only", "act2_plus")
    }


def _primary(*, promote: bool):
    equal = _pair(1 if promote else 0)
    normalized = _pair(1 if promote else 0)
    return {
        "schema_id": PRIMARY_REPORT_SCHEMA_ID,
        "command_passed": True,
        "failure_problems": [],
        "families": {
            "equal_nominal": {"paired_vs_baseline": {"prior_value": equal}},
            "simulator_step_normalized": {
                "paired_vs_baseline": {"prior_value": normalized}
            },
            "wall_clock_normalized": {
                "paired_vs_baseline": {"prior_value": normalized}
            },
        },
    }


@pytest.mark.parametrize(
    ("promote", "high_signal", "case", "recommendation"),
    [
        (
            True,
            False,
            "A",
            "T071 Battle Search v2 Bounded Complete-Run Reachability Evaluation",
        ),
        (False, True, "B", "T063 Oracle-guided public battle learning"),
        (False, False, "C", "T064 simulator-generated later-act curriculum"),
    ],
)
def test_t070_complete_decision_truth_table(
    promote: bool, high_signal: bool, case: str, recommendation: str
) -> None:
    curve = {
        "schema_id": BUDGET_CURVE_SCHEMA_ID,
        "command_passed": True,
        "budget_100_not_sufficient": True,
        "high_budget_guidance_signal": high_signal,
    }
    geometry = {
        "schema_id": GEOMETRY_REPORT_SCHEMA_ID,
        "command_passed": True,
    }
    decision = build_decision_report(_primary(promote=promote), curve, geometry)
    assert decision["schema_id"] == DECISION_SCHEMA_ID
    assert decision["decision_case"] == case
    assert decision["recommendation"] == recommendation
    assert decision["exactly_one_planner_recommendation"] is True
    assert decision["successor_published"] is False


def test_t070_decision_fails_closed_on_incomplete_geometry() -> None:
    with pytest.raises(ValueError, match="complete valid evidence"):
        build_decision_report(
            _primary(promote=False),
            {
                "schema_id": BUDGET_CURVE_SCHEMA_ID,
                "command_passed": True,
            },
            {
                "schema_id": GEOMETRY_REPORT_SCHEMA_ID,
                "command_passed": False,
            },
        )


def test_t070_merge_requires_exact_ordered_stage_inventory(tmp_path: Path) -> None:
    shard_paths = []
    for index, record_range in enumerate(PRIMARY_RANGES):
        start, end = (int(value) for value in record_range.split(":"))
        path = tmp_path / f"shard-{index:02d}.json"
        rows = [
            {
                "cohort_index": cohort_index,
                "termination_status": "win",
                "outer_simulator_steps": 1,
                "wall_clock_seconds": 1.0,
                "controller_compute_telemetry": {
                    "oracle_search_native_simulator_steps": 1,
                    "oracle_search_model_calls": 0,
                },
                "problems": [],
            }
            for cohort_index in range(start, end)
        ]
        path.write_text(
            __import__("json").dumps(
                {
                    "schema_id": "t070-single-arm-shard-v1",
                    "code_commit": "a" * 40,
                    "native_commit": "fee272f1ae21c283ad2161f55293cfe6d714134a",
                    "native_runtime_identity": {"schema_id": NATIVE_RUNTIME_SCHEMA_ID},
                    "stage_name": "baseline-0100",
                    "arm": "baseline",
                    "family": "shared",
                    "native_budget": 100,
                    "cohort_identity": "cohort",
                    "cohort_record_count": 93,
                    "controller_provenance": {},
                    "record_range": record_range,
                    "shard_index": index,
                    "arm_report": {"records": rows},
                    "command_passed": True,
                }
            ),
            encoding="utf-8",
        )
        shard_paths.append(path)
    merged = merge_single_arm_stage(
        shard_paths=shard_paths,
        expected_ranges=PRIMARY_RANGES,
        expected_record_count=93,
        output_path=tmp_path / "merged.json",
    )
    assert merged["schema_id"] == MERGED_STAGE_SCHEMA_ID
    assert merged["arm_report"]["record_count"] == 93
    assert merged["effective_parallel_workers"] == 16
    assert merged["command_passed"] is True


def _audit_row(
    index: int,
    *,
    guided: bool,
    budget: int,
    geometry: bool = False,
) -> dict:
    action = {
        "action_id": f"battle:{index % 3}",
        "kind": "card",
        "occurrence": index % 2,
        "stable_id": f"action-{index % 3}-occurrence-{index % 2}",
    }
    telemetry = {
        "oracle_search_native_simulator_steps": budget,
        "oracle_search_model_calls": 1 if guided else 0,
        "oracle_search_root_mapping_failures": 0,
        "oracle_search_unmapped_root_rows": 0,
        "oracle_search_unmapped_search_edges": 0,
        "oracle_search_decision_reports": [
            [{"decision_step_index": 0, "selected_action_identity": action}]
        ],
    }
    if guided:
        telemetry["t069_cost_attribution"] = {
            "public_context_projection_construction_count": 1,
            "public_context_projection_reuse_count": 1,
        }
    if geometry:
        telemetry["t070_tree_geometry_records"] = [
            [
                {
                    "schema_id": "t070-search-tree-geometry-decision-v1",
                    "decision_step_index": 0,
                    "native_geometry": {
                        "depth_rows": [
                            {
                                "depth": 0,
                                "expanded_node_count": 1,
                                "discovered_child_edge_count": 1,
                                "visited_child_edge_count": 1,
                                "branching_histogram": [
                                    {"child_count": 1, "node_count": 1}
                                ],
                            }
                        ],
                        "max_expanded_depth": 0,
                    },
                    "root_actions": [
                        {
                            "visits": budget,
                            "legal_action_index": 0,
                            "action_identity": action,
                        }
                    ],
                    "root_legal_action_count": 1,
                    "selected_action_identity": action,
                    "native_simulator_steps": budget,
                    "model_calls": 1,
                    "wall_clock_seconds": 0.25,
                }
            ]
        ]
    potion_slots = {
        "status": "available",
        "value": [{"slot_index": 0, "id_label": "EMPTY", "is_empty": True}],
    }
    return {
        "cohort_index": index,
        "source_checkpoint_id": "checkpoint",
        "structural_metadata": {
            "act": 1 if index < 88 else 2,
            "room_type": "BOSS" if index < 88 else "MONSTER",
        },
        "termination_status": "win",
        "terminal_absolute_hp": 20,
        "structured_battle_outcome": {
            "schema_id": "structured-battle-outcome-v1",
            "start": {"potion_slots": potion_slots},
            "terminal": {
                "current_hp": {"status": "available", "value": 20},
                "potion_slots": potion_slots,
            },
            "deltas": {
                "potion_slots_delta": {
                    "status": "available",
                    "added": [],
                    "removed": [],
                }
            },
            "problems": [],
        },
        "outer_simulator_steps": budget + 1,
        "wall_clock_seconds": 0.25,
        "controller_compute_telemetry": telemetry,
        "problems": [],
    }


def _merged_stage(
    name: str,
    arm: str,
    family: str,
    budget: int,
    *,
    record_count: int,
    geometry: bool = False,
) -> dict:
    rows = [
        _audit_row(
            index,
            guided=arm != "baseline",
            budget=budget,
            geometry=geometry,
        )
        for index in range(record_count)
    ]
    return {
        "schema_id": MERGED_STAGE_SCHEMA_ID,
        "stage_name": name,
        "arm": arm,
        "family": family,
        "native_budget": budget,
        "expected_record_count": record_count,
        "worker_count": 16,
        "shard_count": 16,
        "effective_parallel_workers": 16,
        "arm_report": {
            "record_count": record_count,
            "wins": record_count,
            "losses": 0,
            "truncations": 0,
            "errors": 0,
            "records": rows,
        },
        "command_passed": True,
    }


def test_t070_primary_report_has_all_family_arm_stratum_cells() -> None:
    stages = {
        name: _merged_stage(name, arm, family, budget, record_count=93)
        for name, arm, family, budget in PRIMARY_STAGE_CONFIGS
    }
    report = build_primary_report(stages)

    assert report["command_passed"] is True
    assert report["strata"] == {"overall": 93, "boss_only": 88, "act2_plus": 5}
    assert len(report["families"]) == 3
    for family in report["families"].values():
        assert family["cell_inventory"]["actual_cell_count"] == 12
        for stratum, count in report["strata"].items():
            assert set(family["cells"][stratum]) == {
                "baseline",
                "prior_only",
                "value_only",
                "prior_value",
            }
            for cell in family["cells"][stratum].values():
                assert cell["schema_id"] == PRIMARY_CELL_SCHEMA_ID
                assert cell["record_count"] == count
                assert cell["termination_status_counts"]["win"] == count
                assert len(cell["structured_battle_end_resources"]) == count
                assert len(cell["potion_outcomes"]) == count
                assert len(cell["first_selected_root_actions"]) == count
                assert set(cell["failure_counts"]) == {
                    "restore",
                    "action_mapping",
                    "checkpoint",
                    "missing_value",
                    "fallback",
                    "controller",
                    "truncation",
                    "worker",
                    "mixed_provenance",
                }
                assert cell["paired_vs_baseline"][
                    "paired_win_delta_bootstrap_95ci"
                ] == [0.0, 0.0]


def test_t070_high_budget_curve_retains_outcome_compute_cells() -> None:
    stages = {
        name: _merged_stage(
            name,
            arm,
            family,
            budget,
            record_count=16,
            geometry=arm == "prior_value",
        )
        for name, arm, family, budget in HIGH_BUDGET_STAGE_CONFIGS
    }
    curve, geometry = build_budget_curve_and_geometry(stages)

    assert curve["command_passed"] is True
    assert geometry["command_passed"] is True
    assert set(curve["high_budget_guidance_evidence"]) == {"values", "conditions"}
    assert set(geometry["metric_definitions"]) == {
        "effective_branching_factor",
        "visited_edge_coverage_next_depth",
        "expanded_node_coverage_next_depth",
    }
    for arm in ("baseline", "prior_value"):
        for budget in ("100", "400", "1600"):
            cell = curve["arms"][arm][budget]
            assert cell["schema_id"] == HIGH_BUDGET_CELL_SCHEMA_ID
            assert cell["record_count"] == 16
            assert cell["compute"]["native_simulator_steps"] > 0
            assert len(cell["structured_battle_end_resources"]) == 16
            assert len(cell["first_selected_root_actions"]) == 16


@pytest.mark.parametrize(
    "script",
    [
        "freeze_t070_experiment.py",
        "run_t070_search_stage_shard.py",
        "orchestrate_t070_search_stage.py",
        "orchestrate_t070_native_preflight.py",
        "finalize_t070_artifacts.py",
    ],
)
def test_t070_script_cli_smoke(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path("scripts") / script), "--help"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert completed.returncode == 0, completed.stderr
