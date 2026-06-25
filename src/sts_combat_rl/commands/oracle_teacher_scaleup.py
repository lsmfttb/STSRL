"""Focused T023 workflow for A20 Oracle teacher scale-up."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import hashlib
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.oracle_teacher_report import (
    run_oracle_teacher_dataset_report_from_paths,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
    load_natural_battle_start_pool_jsonl,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.oracle_teacher import (
    collect_oracle_teacher_dataset_from_pool,
    dump_oracle_teacher_dataset_jsonl,
)
from sts_combat_rl.sim.oracle_teacher_report import load_a20_coverage_report_json
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    OracleTeacherScaleupManifest,
    build_oracle_teacher_scaleup_manifest,
    build_oracle_teacher_source_selection_plan,
    dump_oracle_teacher_scaleup_manifest_json,
    format_oracle_teacher_scaleup_manifest,
    selected_natural_battle_start_pool,
    validate_oracle_teacher_scaleup_budgets,
)


ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME = "oracle-teacher-scaleup-manifest.json"


def run_oracle_teacher_scaleup_from_paths(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool_path: Path,
    output_dir: Path,
    budgets: Sequence[int],
    source_limit: int | None,
    selection_seed: int,
    coverage_report_path: Path | None = None,
    root_selection_rule: str = "highest_mean",
    action_space: ActionSpaceConfig | None = None,
) -> OracleTeacherScaleupManifest:
    """Collect teacher datasets and T022 reports for one fixed selected source set."""

    requested_budgets = validate_oracle_teacher_scaleup_budgets(budgets)
    output_dir.mkdir(parents=True, exist_ok=True)
    with pool_path.open("r", encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    pool_identity = _source_pool_identity(pool_path, pool)

    coverage_identity: dict[str, Any] | None = None
    if coverage_report_path is not None:
        with coverage_report_path.open("r", encoding="utf-8") as stream:
            coverage_report = load_a20_coverage_report_json(stream)
        coverage_identity = _coverage_report_identity(
            coverage_report_path,
            coverage_report,
        )
        coverage_problems = _coverage_source_identity_problems(
            coverage_report,
            pool_identity,
        )
        if coverage_problems:
            raise ValueError("; ".join(coverage_problems))

    source_selection = build_oracle_teacher_source_selection_plan(
        pool,
        selection_seed=selection_seed,
        source_limit=source_limit,
    )
    if source_selection.problems:
        raise ValueError(
            "invalid Oracle teacher scale-up source selection: "
            + "; ".join(source_selection.problems)
        )
    selected_pool = selected_natural_battle_start_pool(pool, source_selection)
    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()

    datasets_by_budget = {}
    reports_by_budget = {}
    generated_artifacts: list[dict[str, Any]] = []
    for budget in requested_budgets:
        controller = OracleSearchController(
            simulations=budget,
            root_selection_rule=root_selection_rule,
            action_space=active_action_space,
        )
        dataset = collect_oracle_teacher_dataset_from_pool(
            adapter_factory,
            selected_pool,
            controller,
            action_space=active_action_space,
        )
        if dataset.problems:
            raise ValueError(
                f"budget {budget} teacher collection failed: "
                + "; ".join(dataset.problems)
            )
        _require_selected_sources_for_budget(
            budget,
            source_selection.selected_checkpoint_ids,
            dataset,
        )
        teacher_path = output_dir / f"oracle-teacher-budget-{budget}.jsonl"
        with teacher_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_oracle_teacher_dataset_jsonl(dataset, stream)

        report_path = output_dir / f"oracle-teacher-report-budget-{budget}.json"
        report = run_oracle_teacher_dataset_report_from_paths(
            teacher_path=teacher_path,
            source_pool_path=pool_path,
            coverage_report_path=coverage_report_path,
            output_path=report_path,
        )
        datasets_by_budget[budget] = dataset
        reports_by_budget[budget] = report
        generated_artifacts.append(
            _budget_artifact_summary(
                budget=budget,
                teacher_path=teacher_path,
                report_path=report_path,
                dataset=dataset,
                report=report,
            )
        )

    native_identity = (
        next(iter(datasets_by_budget.values())).native_source_identity
        if datasets_by_budget
        else lightspeed_source_identity_dict()
    )
    input_artifacts: dict[str, Any] = {"natural_pool": pool_identity}
    if coverage_identity is not None:
        input_artifacts["t021_coverage_report"] = coverage_identity

    manifest = build_oracle_teacher_scaleup_manifest(
        input_artifacts=input_artifacts,
        source_selection=source_selection,
        requested_budgets=requested_budgets,
        root_selection_rule=root_selection_rule,
        datasets_by_budget=datasets_by_budget,
        reports_by_budget=reports_by_budget,
        generated_artifacts=generated_artifacts,
        native_source_identity=native_identity,
        warnings=_coverage_gap_warnings(reports_by_budget.values()),
    )
    manifest_path = output_dir / ORACLE_TEACHER_SCALEUP_MANIFEST_FILENAME
    with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_teacher_scaleup_manifest_json(manifest, stream)
    return manifest


def format_oracle_teacher_scaleup_command(
    manifest: OracleTeacherScaleupManifest,
) -> str:
    """Format scale-up command output for stderr."""

    return format_oracle_teacher_scaleup_manifest(manifest)


def _require_selected_sources_for_budget(
    budget: int,
    selected_checkpoint_ids: Sequence[str],
    dataset: object,
) -> None:
    actual = tuple(row.source_checkpoint_id for row in dataset.records)
    if actual != tuple(selected_checkpoint_ids):
        raise ValueError(
            f"budget {budget} teacher rows do not match selected source order"
        )


def _budget_artifact_summary(
    *,
    budget: int,
    teacher_path: Path,
    report_path: Path,
    dataset: object,
    report: object,
) -> dict[str, Any]:
    teacher_coverage = report.teacher_coverage
    search = report.search_statistics
    coverage = report.coverage_report_linkage
    return {
        "budget": budget,
        "teacher_artifact": {
            "path": str(teacher_path),
            "sha256": _sha256_file(teacher_path),
            "artifact_schema_id": getattr(dataset, "artifact_schema_id", None),
            "format_version": getattr(dataset, "format_version", None),
            "record_count": len(getattr(dataset, "records", [])),
        },
        "t022_report_artifact": {
            "path": str(report_path),
            "sha256": _sha256_file(report_path),
            "schema_id": getattr(report, "schema_id", None),
            "format_version": getattr(report, "format_version", None),
            "command_passed": getattr(report, "command_passed", False),
        },
        "search_statistics": {
            "teacher_row_count": teacher_coverage.get("teacher_row_count"),
            "unique_source_start_count": teacher_coverage.get(
                "unique_source_start_count"
            ),
            "root_row_count": search.get("root_row_count"),
            "root_visit_count": search.get("root_visit_count"),
            "search_simulations": search.get("search_simulations"),
            "native_simulator_steps": search.get("native_simulator_steps"),
            "model_calls": search.get("model_calls"),
            "teacher_action_available_count": search.get(
                "teacher_action_available_count"
            ),
            "soft_visit_target_available_count": search.get(
                "soft_visit_target_available_count"
            ),
        },
        "coverage_report_linkage": {
            "loaded": coverage.get("loaded"),
            "natural_pool_identity_matched": coverage.get(
                "natural_pool_identity_matched"
            ),
            "broad_training_allowed": coverage.get("broad_training_allowed"),
            "gate_passed_without_override": coverage.get(
                "gate_passed_without_override"
            ),
            "coverage_gaps": list(coverage.get("coverage_gaps", [])),
        },
        "problems": list(getattr(report, "problems", ())),
    }


def _source_pool_identity(
    path: Path,
    pool: NaturalBattleStartPool,
) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "format_version": pool.format_version,
        "record_count": len(pool.records),
        "source_run_count": pool.source_run_count,
    }


def _coverage_report_identity(
    path: Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "schema_id": report.get("schema_id"),
        "format_version": report.get("format_version"),
    }


def _coverage_source_identity_problems(
    coverage_report: dict[str, Any],
    pool_identity: dict[str, Any],
) -> list[str]:
    input_artifacts = coverage_report.get("input_artifacts")
    if not isinstance(input_artifacts, dict):
        return ["T021 coverage report is missing input_artifacts"]
    natural_pool = input_artifacts.get("natural_pool")
    if not isinstance(natural_pool, dict):
        return ["T021 coverage report is missing natural_pool identity"]
    if natural_pool.get("sha256") != pool_identity.get("sha256"):
        return ["T021 coverage natural-pool sha256 does not match source pool"]
    return []


def _coverage_gap_warnings(reports: Sequence[object]) -> list[str]:
    warnings: list[str] = []
    seen_gap_sets: set[tuple[str, ...]] = set()
    for report in reports:
        linkage = report.coverage_report_linkage
        if not linkage.get("loaded"):
            continue
        gaps = tuple(str(gap) for gap in linkage.get("coverage_gaps", []))
        if gaps and gaps not in seen_gap_sets:
            seen_gap_sets.add(gaps)
            warnings.append("T021 coverage gate gaps remain: " + "; ".join(gaps))
        if not linkage.get("broad_training_allowed"):
            warnings.append(
                "T021 broad-training gate remains closed for smoke-scale data"
            )
    return list(dict.fromkeys(warnings))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
