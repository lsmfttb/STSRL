"""Current-schema reports for saved Oracle teacher datasets."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any, TextIO

from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20_BATTLE_START_COVERAGE_FORMAT_VERSION,
    A20_BATTLE_START_COVERAGE_SCHEMA_ID,
)
from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
    build_battle_start_pool_coverage_report,
    record_to_manifest,
)
from sts_combat_rl.sim.controller_contract import controller_provenance_from_dict
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_teacher import (
    ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
    ORACLE_TEACHER_ARTIFACT_SCHEMA_ID,
    ORACLE_TEACHER_ROW_SCHEMA_ID,
    OracleTeacherDataset,
    OracleTeacherRow,
    oracle_teacher_dataset_problems,
)


ORACLE_TEACHER_DATASET_REPORT_SCHEMA_ID = "oracle-teacher-dataset-report-v1"
ORACLE_TEACHER_DATASET_REPORT_FORMAT_VERSION = 1
_STRUCTURAL_FIELDS = (
    "ascension",
    "act",
    "room_type",
    "encounter_id",
    "source_run_id",
    "source_checkpoint_id",
)
_MISSING = "(missing)"


@dataclass(frozen=True)
class OracleTeacherDatasetAuditReport:
    """Machine-readable T022 report for one saved Oracle teacher artifact."""

    input_artifacts: dict[str, Any]
    source_manifest_identity: dict[str, Any]
    current_source_manifest_identity: dict[str, Any]
    command_config: dict[str, Any]
    teacher_dataset: dict[str, Any]
    information_regime: dict[str, Any]
    teacher_coverage: dict[str, Any]
    search_statistics: dict[str, Any]
    source_pool_linkage: dict[str, Any]
    coverage_report_linkage: dict[str, Any]
    problems: tuple[str, ...] = ()
    schema_id: str = ORACLE_TEACHER_DATASET_REPORT_SCHEMA_ID
    format_version: int = ORACLE_TEACHER_DATASET_REPORT_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "input_artifacts": _json_safe_mapping(self.input_artifacts),
            "source_manifest_identity": _json_safe_mapping(
                self.source_manifest_identity
            ),
            "current_source_manifest_identity": _json_safe_mapping(
                self.current_source_manifest_identity
            ),
            "command_config": _json_safe_mapping(self.command_config),
            "teacher_dataset": _json_safe_mapping(self.teacher_dataset),
            "information_regime": _json_safe_mapping(self.information_regime),
            "teacher_coverage": _json_safe_mapping(self.teacher_coverage),
            "search_statistics": _json_safe_mapping(self.search_statistics),
            "source_pool_linkage": _json_safe_mapping(self.source_pool_linkage),
            "coverage_report_linkage": _json_safe_mapping(self.coverage_report_linkage),
            "command_passed": self.command_passed,
            "problems": list(self.problems),
        }


def build_oracle_teacher_dataset_audit_report(
    dataset: OracleTeacherDataset,
    *,
    teacher_artifact_identity: Mapping[str, Any] | None = None,
    source_pool: NaturalBattleStartPool | None = None,
    source_pool_artifact_identity: Mapping[str, Any] | None = None,
    coverage_report: Mapping[str, Any] | None = None,
    coverage_report_identity: Mapping[str, Any] | None = None,
    current_source_manifest_identity: Mapping[str, Any] | None = None,
    command_config: Mapping[str, Any] | None = None,
) -> OracleTeacherDatasetAuditReport:
    """Build a deterministic report without running search or training."""

    current_identity = _json_safe_mapping(current_source_manifest_identity or {})
    input_artifacts = {
        "teacher_jsonl": _json_safe_mapping(teacher_artifact_identity or {}),
    }
    if source_pool_artifact_identity is not None:
        input_artifacts["source_pool"] = _json_safe_mapping(
            source_pool_artifact_identity
        )
    if coverage_report_identity is not None:
        input_artifacts["t021_coverage_report"] = _json_safe_mapping(
            coverage_report_identity
        )

    teacher_dataset = _teacher_dataset_summary(dataset)
    information_regime, information_problems = _information_regime_summary(dataset)
    teacher_coverage, coverage_problems = _teacher_coverage_summary(dataset.records)
    search_statistics = _search_statistics_summary(dataset.records)
    source_pool_linkage = _source_pool_linkage_summary(
        dataset,
        source_pool,
        source_pool_artifact_identity=source_pool_artifact_identity,
    )
    coverage_linkage = _coverage_report_linkage_summary(
        coverage_report,
        coverage_report_identity=coverage_report_identity,
        source_pool_artifact_identity=source_pool_artifact_identity,
    )
    source_identity_problems = _source_identity_problems(
        dataset.native_source_identity,
        current_identity,
    )

    problems = _dedupe(
        [
            *oracle_teacher_dataset_problems(dataset),
            *information_problems,
            *coverage_problems,
            *source_identity_problems,
            *_problem_list(source_pool_linkage),
            *_problem_list(coverage_linkage),
        ]
    )
    return OracleTeacherDatasetAuditReport(
        input_artifacts=input_artifacts,
        source_manifest_identity=_json_safe_mapping(dataset.native_source_identity),
        current_source_manifest_identity=current_identity,
        command_config=_json_safe_mapping(command_config or {}),
        teacher_dataset=teacher_dataset,
        information_regime=information_regime,
        teacher_coverage=teacher_coverage,
        search_statistics=search_statistics,
        source_pool_linkage=source_pool_linkage,
        coverage_report_linkage=coverage_linkage,
        problems=tuple(problems),
    )


def dump_oracle_teacher_dataset_audit_report_json(
    report: OracleTeacherDatasetAuditReport,
    stream: TextIO,
) -> None:
    """Write the current T022 report schema in deterministic JSON form."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def load_a20_coverage_report_json(stream: TextIO) -> dict[str, Any]:
    """Load the current T021 JSON report used for optional linkage."""

    try:
        raw = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid T021 coverage JSON: {exc.msg}") from exc
    report = _require_mapping(raw, "T021 coverage report")
    schema_id = report.get("schema_id")
    if schema_id != A20_BATTLE_START_COVERAGE_SCHEMA_ID:
        raise ValueError(f"unsupported T021 coverage schema_id {schema_id!r}")
    version = report.get("format_version")
    if version != A20_BATTLE_START_COVERAGE_FORMAT_VERSION:
        raise ValueError(f"unsupported T021 coverage format_version {version!r}")
    return report


def format_oracle_teacher_dataset_audit_report(
    report: OracleTeacherDatasetAuditReport,
) -> str:
    """Format deterministic stderr evidence for the T022 report."""

    teacher = report.teacher_dataset
    coverage = report.teacher_coverage
    search = report.search_statistics
    info = report.information_regime
    pool = report.source_pool_linkage
    t021 = report.coverage_report_linkage
    lines = [
        "Oracle teacher dataset report",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "evidence boundary: full_simulator_state_oracle_like teacher data; "
            "not normal-information, live-game, broad-training, or controller-"
            "strength evidence"
        ),
        "input artifacts:",
    ]
    _append_nested_mapping(lines, report.input_artifacts)
    lines.extend(
        [
            "",
            format_lightspeed_source_identity(report.source_manifest_identity),
            "",
            "teacher dataset",
            f"  artifact schema: {teacher.get('artifact_schema_id')} "
            f"v{teacher.get('format_version')}",
            f"  row schema: {teacher.get('row_schema_id')}",
            f"  native search schema: {teacher.get('native_search_schema_id')}",
            f"  controller identity: {teacher.get('controller_identity')}",
            f"  row count: {teacher.get('row_count')}",
            f"  deterministic row digest: {teacher.get('row_digest')}",
            f"  migration source version: {teacher.get('migration_source_version')}",
            f"  migration target version: {teacher.get('migration_target_version')}",
            "",
            "information regime",
            f"  expected: {info.get('expected_information_regime')}",
            f"  dataset: {info.get('dataset_information_regime')}",
            f"  controller: {info.get('controller_information_regime')}",
            f"  passed: {_yes_no(bool(info.get('passed')))}",
        ]
    )
    _append_counter(lines, "  row information regimes", info["row_counts"])
    _append_counter(
        lines,
        "  checkpoint information regimes",
        info["checkpoint_counts"],
    )
    lines.extend(
        [
            "",
            "teacher natural source coverage",
            f"  teacher rows: {coverage.get('teacher_row_count')}",
            f"  unique natural sources: {coverage.get('unique_source_start_count')}",
            "  root rows and visits are search statistics only; they do not add "
            "natural source coverage",
        ]
    )
    _append_counter(lines, "  ascensions", coverage["ascension_counts"])
    _append_counter(lines, "  acts", coverage["act_counts"])
    _append_counter(lines, "  room types", coverage["room_type_counts"])
    _append_counter(lines, "  encounters", coverage["encounter_id_counts"])
    _append_counter(lines, "  source runs", coverage["source_run_id_counts"])
    _append_counter(
        lines,
        "  source checkpoints",
        coverage["source_checkpoint_id_counts"],
    )
    _append_counter(
        lines,
        "  missing structural metadata",
        coverage["missing_metadata_counts"],
    )
    lines.extend(
        [
            "",
            "search statistics",
            f"  root rows: {search.get('root_row_count')}",
            f"  root visits: {search.get('root_visit_count')}",
            f"  search simulations: {search.get('search_simulations')}",
            f"  native simulator steps: {_format_optional(search.get('native_simulator_steps'))}",
            f"  model calls: {_format_model_calls(search.get('model_calls'))}",
            f"  wall-clock seconds: {_format_optional(search.get('wall_clock_time_s'), precision=6)}",
            f"  teacher actions available: {search.get('teacher_action_available_count')}",
            "  soft visit targets available: "
            f"{search.get('soft_visit_target_available_count')}",
        ]
    )
    _append_counter(
        lines,
        "  root selection rules",
        search["root_selection_rule_counts"],
    )
    _append_counter(
        lines,
        "  simulations per row",
        search["search_simulation_counts"],
    )
    lines.extend(
        [
            f"  selected mean value range: {search.get('selected_mean_value_range')}",
            f"  selected visit range: {search.get('selected_visit_range')}",
            f"  unsearched legal actions: {search.get('unsearched_legal_action_count')}",
            f"  unmapped search edges: {search.get('unmapped_search_edge_count')}",
            "",
            "source-pool linkage",
            f"  loaded: {_yes_no(bool(pool.get('loaded')))}",
            f"  matched: {_yes_no(bool(pool.get('matched')))}",
            f"  pool records: {pool.get('pool_record_count')}",
            f"  teacher rows linked: {pool.get('teacher_rows_linked_count')}",
            f"  missing teacher sources: {pool.get('missing_teacher_source_count')}",
            f"  metadata mismatches: {pool.get('metadata_mismatch_count')}",
        ]
    )
    _append_counter(
        lines,
        "  source public-context statuses",
        pool["public_context_status_counts"],
    )
    _append_counter(
        lines,
        "  source structured-outcome statuses",
        pool["structured_resource_outcome_status_counts"],
    )
    lines.extend(
        [
            "",
            "T021 coverage linkage",
            f"  loaded: {_yes_no(bool(t021.get('loaded')))}",
            f"  natural-pool identity matched: "
            f"{_yes_no(bool(t021.get('natural_pool_identity_matched')))}",
            f"  broad training allowed: "
            f"{_yes_no(bool(t021.get('broad_training_allowed')))}",
            f"  gate passed without override: "
            f"{_yes_no(bool(t021.get('gate_passed_without_override')))}",
        ]
    )
    _append_problem_list(lines, "  T021 gate gaps", t021["coverage_gaps"])
    lines.extend(["", "problems:"])
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _teacher_dataset_summary(dataset: OracleTeacherDataset) -> dict[str, Any]:
    controller_identity = "(invalid)"
    try:
        controller_identity = controller_provenance_from_dict(
            dataset.controller_provenance
        ).identity
    except ValueError:
        pass
    return {
        "artifact_schema_id": dataset.artifact_schema_id,
        "format_version": dataset.format_version,
        "expected_artifact_schema_id": ORACLE_TEACHER_ARTIFACT_SCHEMA_ID,
        "expected_format_version": ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
        "row_schema_id": ORACLE_TEACHER_ROW_SCHEMA_ID,
        "native_search_schema_id": dataset.native_search_schema_id,
        "information_regime": dataset.information_regime,
        "controller_identity": controller_identity,
        "controller_provenance": dict(dataset.controller_provenance),
        "action_space_config": dict(dataset.action_space_config),
        "source_pool_format_version": dataset.source_pool_format_version,
        "source_pool_controller_provenance": dict(
            dataset.source_pool_controller_provenance
        ),
        "row_count": len(dataset.records),
        "row_digest": _dataset_row_digest(dataset.records),
        "migration_source_version": dataset.migration_report.source_version,
        "migration_target_version": dataset.migration_report.target_version,
        "migration_losses": list(dataset.migration_report.losses),
        "stored_problems": list(dataset.problems),
    }


def _information_regime_summary(
    dataset: OracleTeacherDataset,
) -> tuple[dict[str, Any], list[str]]:
    row_counts = Counter(row.information_regime for row in dataset.records)
    checkpoint_counts = Counter(
        row.checkpoint_information_regime for row in dataset.records
    )
    native_report_counts = Counter(
        str(row.native_search_report.get("information_regime"))
        for row in dataset.records
    )
    controller_regime: str | None = None
    problems: list[str] = []
    try:
        provenance = controller_provenance_from_dict(dataset.controller_provenance)
        raw_regime = provenance.config.get("information_regime")
        controller_regime = str(raw_regime) if raw_regime is not None else None
    except ValueError as exc:
        problems.append(f"teacher controller provenance invalid: {exc}")
    expected = NATIVE_SEARCH_INFORMATION_REGIME
    if dataset.information_regime != expected:
        problems.append("teacher dataset information regime is not Oracle-like")
    if controller_regime != expected:
        problems.append("teacher controller information regime is not Oracle-like")
    for row in dataset.records:
        if row.checkpoint_information_regime != expected:
            problems.append(
                f"teacher row {row.row_index}: source checkpoint regime is "
                f"{row.checkpoint_information_regime!r}"
            )
        if row.native_search_report.get("information_regime") != expected:
            problems.append(
                f"teacher row {row.row_index}: native search report regime is "
                "not Oracle-like"
            )
    passed = (
        dataset.information_regime == expected
        and controller_regime == expected
        and set(row_counts) <= {expected}
        and set(checkpoint_counts) <= {expected}
        and set(native_report_counts) <= {expected}
    )
    return (
        {
            "expected_information_regime": expected,
            "dataset_information_regime": dataset.information_regime,
            "controller_information_regime": controller_regime,
            "row_counts": _counter_dict(row_counts),
            "checkpoint_counts": _counter_dict(checkpoint_counts),
            "native_search_report_counts": _counter_dict(native_report_counts),
            "passed": passed,
        },
        _dedupe(problems),
    )


def _teacher_coverage_summary(
    records: Sequence[OracleTeacherRow],
) -> tuple[dict[str, Any], list[str]]:
    counters: dict[str, Counter[str]] = {
        field_name: Counter() for field_name in _STRUCTURAL_FIELDS
    }
    missing = Counter()
    strata = Counter()
    problems: list[str] = []
    for row in records:
        stratum_values: list[str] = []
        for field_name in _STRUCTURAL_FIELDS:
            value = _teacher_metadata_value(row, field_name)
            if value is None or value == "":
                counters[field_name][_MISSING] += 1
                missing[field_name] += 1
                stratum_values.append(_MISSING)
                problems.append(
                    f"teacher row {row.row_index}: missing structural metadata "
                    f"{field_name}"
                )
            else:
                text = str(value)
                counters[field_name][text] += 1
                stratum_values.append(text)
        strata["/".join(stratum_values)] += 1
    return (
        {
            "teacher_row_count": len(records),
            "unique_source_start_count": len(
                {row.source_checkpoint_id for row in records}
            ),
            "unique_source_run_count": len({row.source_run_id for row in records}),
            "ascension_counts": _counter_dict(counters["ascension"]),
            "act_counts": _counter_dict(counters["act"]),
            "room_type_counts": _counter_dict(counters["room_type"]),
            "encounter_id_counts": _counter_dict(counters["encounter_id"]),
            "source_run_id_counts": _counter_dict(counters["source_run_id"]),
            "source_checkpoint_id_counts": _counter_dict(
                counters["source_checkpoint_id"]
            ),
            "per_stratum_counts": _counter_dict(strata),
            "missing_metadata_counts": _counter_dict(missing),
        },
        _dedupe(problems),
    )


def _search_statistics_summary(records: Sequence[OracleTeacherRow]) -> dict[str, Any]:
    root_row_count = 0
    root_visit_count = 0
    search_simulations = 0
    native_steps: int | None = 0
    model_calls: int | None = 0
    wall_clock: float | None = 0.0
    teacher_action_available_count = 0
    soft_visit_target_available_count = 0
    unsearched_legal_action_count = 0
    unmapped_search_edge_count = 0
    native_search_problem_count = 0
    selection_counts: Counter[str] = Counter()
    simulation_counts: Counter[str] = Counter()
    selected_means: list[float] = []
    selected_visits: list[int] = []

    for row in records:
        report = row.native_search_report
        root_row_count += len(row.root_statistics)
        root_visit_count += _optional_int(report.get("root_visits")) or 0
        simulations = _optional_int(report.get("simulations_requested"))
        if simulations is not None:
            search_simulations += simulations
            simulation_counts[str(simulations)] += 1
        native_steps = _sum_optional_int(
            native_steps,
            _optional_int(report.get("native_simulator_steps")),
        )
        model_calls = _sum_optional_int(
            model_calls,
            _optional_int(report.get("model_calls")),
        )
        wall_clock = _sum_optional_float(
            wall_clock,
            _optional_float(report.get("wall_clock_time_s")),
        )
        unsearched_legal_action_count += (
            _optional_int(report.get("unsearched_legal_action_count")) or 0
        )
        unmapped_search_edge_count += (
            _optional_int(report.get("unmapped_search_edge_count")) or 0
        )
        report_problems = report.get("problems")
        if isinstance(report_problems, list):
            native_search_problem_count += len(report_problems)
        if row.teacher_action:
            teacher_action_available_count += 1
        selection_rule = row.teacher_action.get("selection_rule")
        selection_counts[str(selection_rule)] += 1
        selected_visit = _optional_int(row.teacher_action.get("visits"))
        if selected_visit is not None:
            selected_visits.append(selected_visit)
        selected_mean = _optional_float(row.teacher_action.get("mean_value"))
        if selected_mean is not None:
            selected_means.append(selected_mean)
        if _soft_visit_target_available(row):
            soft_visit_target_available_count += 1

    return {
        "root_row_count": root_row_count,
        "root_visit_count": root_visit_count,
        "search_simulations": search_simulations,
        "native_simulator_steps": native_steps,
        "model_calls": model_calls,
        "wall_clock_time_s": wall_clock,
        "teacher_action_available_count": teacher_action_available_count,
        "soft_visit_target_available_count": soft_visit_target_available_count,
        "root_selection_rule_counts": _counter_dict(selection_counts),
        "search_simulation_counts": _counter_dict(simulation_counts),
        "selected_mean_value_range": _numeric_range(selected_means),
        "selected_visit_range": _int_range(selected_visits),
        "unsearched_legal_action_count": unsearched_legal_action_count,
        "unmapped_search_edge_count": unmapped_search_edge_count,
        "native_search_problem_count": native_search_problem_count,
    }


def _source_pool_linkage_summary(
    dataset: OracleTeacherDataset,
    source_pool: NaturalBattleStartPool | None,
    *,
    source_pool_artifact_identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if source_pool is None:
        return {
            "loaded": False,
            "matched": False,
            "source_pool_identity": {},
            "pool_record_count": 0,
            "pool_unique_source_count": 0,
            "teacher_rows_linked_count": 0,
            "missing_teacher_source_count": 0,
            "metadata_mismatch_count": 0,
            "natural_coverage": {},
            "public_context_status_counts": {},
            "structured_resource_outcome_status_counts": {},
            "problems": [],
        }

    problems: list[str] = []
    coverage = build_battle_start_pool_coverage_report(source_pool)
    by_checkpoint = {
        record.source_checkpoint_id: record for record in source_pool.records
    }
    if len(by_checkpoint) != len(source_pool.records):
        problems.append("source pool contains duplicate source checkpoint ids")
    if dataset.source_pool_format_version != source_pool.format_version:
        problems.append("teacher source-pool format version does not match pool")
    if (
        dataset.source_pool_controller_provenance
        != source_pool.source_controller_provenance
    ):
        problems.append("teacher source-pool controller provenance does not match pool")

    linked_count = 0
    missing_sources = 0
    metadata_mismatch_count = 0
    for row in dataset.records:
        source = by_checkpoint.get(row.source_checkpoint_id)
        if source is None:
            missing_sources += 1
            problems.append(
                f"teacher row {row.row_index}: source checkpoint "
                f"{row.source_checkpoint_id!r} is not in the source pool"
            )
            continue
        linked_count += 1
        mismatches = _row_pool_metadata_mismatches(row, source)
        if mismatches:
            metadata_mismatch_count += 1
            problems.extend(mismatches)

    return {
        "loaded": True,
        "matched": not problems,
        "source_pool_identity": _json_safe_mapping(source_pool_artifact_identity or {}),
        "pool_record_count": len(source_pool.records),
        "pool_unique_source_count": coverage.unique_source_start_count,
        "teacher_rows_linked_count": linked_count,
        "missing_teacher_source_count": missing_sources,
        "metadata_mismatch_count": metadata_mismatch_count,
        "natural_coverage": {
            "natural_battle_start_count": coverage.natural_battle_start_count,
            "unique_source_start_count": coverage.unique_source_start_count,
            "source_run_count": coverage.source_run_count,
            "terminal_run_count": coverage.terminal_run_count,
            "truncated_run_count": coverage.truncated_run_count,
            "completed_battle_count": coverage.completed_battle_count,
            "reported_battle_win_count": coverage.reported_battle_win_count,
            "completed_battle_outcome_missing_count": (
                coverage.completed_battle_outcome_missing_count
            ),
            "missing_metadata_counts": _counter_dict(coverage.missing_metadata_counts),
            "problems": list(coverage.problems),
        },
        "public_context_status_counts": _counter_dict(
            Counter(record.public_context_status for record in source_pool.records)
        ),
        "structured_resource_outcome_status_counts": _counter_dict(
            Counter(
                record.completed_battle_resource_outcome_status
                for record in source_pool.records
            )
        ),
        "problems": _dedupe([*coverage.problems, *problems]),
    }


def _coverage_report_linkage_summary(
    coverage_report: Mapping[str, Any] | None,
    *,
    coverage_report_identity: Mapping[str, Any] | None,
    source_pool_artifact_identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if coverage_report is None:
        return {
            "loaded": False,
            "coverage_report_identity": {},
            "natural_pool_identity_matched": False,
            "natural_coverage": {},
            "training_row_coverage": {},
            "broad_training_allowed": False,
            "gate_passed_without_override": False,
            "training_allowed": False,
            "coverage_gaps": [],
            "problems": [],
        }

    problems: list[str] = []
    natural_identity_matched = False
    input_artifacts = _mapping_or_empty(coverage_report.get("input_artifacts"))
    coverage_pool_identity = _mapping_or_empty(input_artifacts.get("natural_pool"))
    source_sha = (
        source_pool_artifact_identity.get("sha256")
        if isinstance(source_pool_artifact_identity, Mapping)
        else None
    )
    coverage_sha = coverage_pool_identity.get("sha256")
    if source_sha is None:
        problems.append("T021 coverage linkage requires a supplied source pool")
    elif coverage_sha != source_sha:
        problems.append("T021 coverage natural-pool sha256 does not match source pool")
    else:
        natural_identity_matched = True

    command_passed = coverage_report.get("command_passed")
    if command_passed is False:
        command_problems = _string_list(coverage_report.get("command_problems"))
        if command_problems:
            problems.extend(
                f"T021 coverage command problem: {problem}"
                for problem in command_problems
            )
        else:
            problems.append("T021 coverage report command_passed is false")

    natural_coverage = _mapping_or_empty(coverage_report.get("natural_coverage"))
    training_row_coverage = _mapping_or_empty(
        coverage_report.get("training_row_coverage")
    )
    gate_report = _mapping_or_empty(coverage_report.get("training_gate_report"))
    coverage_gaps = _training_gate_gaps(gate_report)
    return {
        "loaded": True,
        "coverage_report_identity": _json_safe_mapping(coverage_report_identity or {}),
        "natural_pool_identity_matched": natural_identity_matched,
        "natural_coverage": _json_safe_mapping(natural_coverage),
        "training_row_coverage": _json_safe_mapping(training_row_coverage),
        "broad_training_allowed": bool(gate_report.get("broad_training_allowed")),
        "gate_passed_without_override": bool(
            gate_report.get("gate_passed_without_override")
        ),
        "training_allowed": bool(gate_report.get("training_allowed")),
        "training_gate_record_count": gate_report.get("record_count", 0),
        "training_gate_cells": _training_gate_cells(gate_report),
        "coverage_gaps": coverage_gaps,
        "problems": _dedupe(problems),
    }


def _row_pool_metadata_mismatches(row: OracleTeacherRow, source: Any) -> list[str]:
    prefix = f"teacher row {row.row_index}: source pool metadata mismatch"
    mismatches: list[str] = []
    expected = {
        "source_pool_record_index": source.record_index,
        "source_run_id": source.source_run_id,
        "source_seed": source.source_seed,
        "source_battle_index": source.source_battle_index,
        "source_distribution_kind": source.distribution_kind,
        "checkpoint_information_regime": source.checkpoint_information_regime,
        "public_context_status": source.public_context_status,
    }
    actual = {
        "source_pool_record_index": row.source_pool_record_index,
        "source_run_id": row.source_run_id,
        "source_seed": row.source_seed,
        "source_battle_index": row.source_battle_index,
        "source_distribution_kind": row.source_distribution_kind,
        "checkpoint_information_regime": row.checkpoint_information_regime,
        "public_context_status": row.public_context_status,
    }
    for key, expected_value in expected.items():
        if actual[key] != expected_value:
            mismatches.append(f"{prefix} for {key}")
    if row.structural_metadata != source.structural_metadata:
        mismatches.append(f"{prefix} for structural_metadata")
    if row.public_context_status == source.public_context_status:
        if row.public_run_context != source.public_run_context:
            mismatches.append(f"{prefix} for public_run_context")
    if (
        record_to_manifest(source).get("source_checkpoint_id")
        != row.source_checkpoint_id
    ):
        mismatches.append(f"{prefix} for source_checkpoint_id")
    return mismatches


def _source_identity_problems(
    teacher_identity: Mapping[str, Any],
    current_identity: Mapping[str, Any],
) -> list[str]:
    del current_identity
    problems: list[str] = []
    teacher_commit = _non_empty_string(teacher_identity.get("integration_commit"))
    if teacher_commit is None:
        problems.append("teacher native source identity is missing integration_commit")
    return problems


def _dataset_row_digest(records: Sequence[OracleTeacherRow]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for record in records:
        payload = json.dumps(
            record.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _teacher_metadata_value(row: OracleTeacherRow, field_name: str) -> Any:
    if field_name == "source_checkpoint_id":
        return row.source_checkpoint_id
    if field_name == "source_run_id":
        return row.source_run_id or row.structural_metadata.get(field_name)
    return row.structural_metadata.get(field_name)


def _soft_visit_target_available(row: OracleTeacherRow) -> bool:
    probabilities = row.soft_visit_target.get("probabilities")
    return isinstance(probabilities, list) and len(probabilities) == len(
        row.legal_action_identities
    )


def _training_gate_cells(gate_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    cells = gate_report.get("cells")
    if not isinstance(cells, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in cells:
        cell = _mapping_or_empty(raw)
        result.append(
            {
                "ascension": cell.get("ascension"),
                "act": cell.get("act"),
                "record_count": cell.get("record_count"),
                "unique_source_count": cell.get("unique_source_count"),
                "passed": bool(cell.get("passed")),
                "problems": _string_list(cell.get("problems")),
            }
        )
    return result


def _training_gate_gaps(gate_report: Mapping[str, Any]) -> list[str]:
    gaps: list[str] = []
    for cell in _training_gate_cells(gate_report):
        if cell["passed"]:
            continue
        key = f"A{cell['ascension']}/act{cell['act']}"
        problems = cell["problems"]
        if problems:
            gaps.extend(f"{key}: {problem}" for problem in problems)
        else:
            gaps.append(f"{key}: gate cell did not pass")
    return gaps


def _problem_list(summary: Mapping[str, Any]) -> list[str]:
    return _string_list(summary.get("problems"))


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Counter):
        return _counter_dict(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): values[key] for key in sorted(values, key=lambda item: str(item))}


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _sum_optional_int(current: int | None, value: int | None) -> int | None:
    if current is None or value is None:
        return None
    return current + value


def _sum_optional_float(current: float | None, value: float | None) -> float | None:
    if current is None or value is None:
        return None
    return current + value


def _numeric_range(values: Sequence[float]) -> str:
    if not values:
        return "(missing)"
    return f"min={min(values):.6f}, max={max(values):.6f}"


def _int_range(values: Sequence[int]) -> str:
    if not values:
        return "(missing)"
    return f"min={min(values)}, max={max(values)}"


def _format_optional(value: Any, *, precision: int = 0) -> str:
    numeric = _optional_float(value)
    if numeric is None:
        return "(missing)"
    if precision:
        return f"{numeric:.{precision}f}"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.3f}"


def _format_model_calls(value: Any) -> str:
    if value is None:
        return "none (native search)"
    return _format_optional(value)


def _append_counter(
    lines: list[str],
    title: str,
    values: Mapping[Any, int],
) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("    (none)")
        return
    for key in sorted(values, key=lambda item: str(item)):
        lines.append(f"    {key}: {values[key]}")


def _append_nested_mapping(
    lines: list[str],
    values: Mapping[str, Any],
    *,
    indent: int = 2,
) -> None:
    prefix = " " * indent
    if not values:
        lines.append(f"{prefix}(none)")
        return
    for key in sorted(values):
        value = values[key]
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{key}:")
            _append_nested_mapping(lines, value, indent=indent + 2)
        else:
            lines.append(f"{prefix}{key}: {value}")


def _append_problem_list(
    lines: list[str],
    title: str,
    problems: Sequence[str],
) -> None:
    lines.append(f"{title}:")
    if not problems:
        lines.append("    (none)")
        return
    lines.extend(f"    - {problem}" for problem in problems)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
