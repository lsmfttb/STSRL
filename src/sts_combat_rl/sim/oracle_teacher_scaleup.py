"""A20 Oracle-like teacher scale-up planning and manifest reporting."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import random
from typing import Any, TextIO

from sts_combat_rl.sim.battle_start_pool import (
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
)
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_teacher import OracleTeacherDataset, OracleTeacherRow
from sts_combat_rl.sim.oracle_teacher_report import (
    OracleTeacherDatasetAuditReport,
)


ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID = "oracle-teacher-scaleup-manifest-v1"
ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION = 1
SCALEUP_STRUCTURAL_FIELDS = (
    "ascension",
    "act",
    "room_type",
    "encounter_id",
    "source_run_id",
    "source_checkpoint_id",
)
_STRATUM_FIELDS = ("ascension", "act", "room_type", "encounter_id")


@dataclass(frozen=True)
class OracleTeacherSourceSelectionPlan:
    """Deterministic source plan built only from rule-defined metadata."""

    selection_seed: int
    source_limit: int | None
    input_source_count: int
    selected_sources: tuple[dict[str, Any], ...]
    selected_record_indices: tuple[int, ...]
    selection_method: str
    structural_coverage: dict[str, Any]
    problems: tuple[str, ...] = ()

    @property
    def selected_source_count(self) -> int:
        return len(self.selected_sources)

    @property
    def selected_checkpoint_ids(self) -> tuple[str, ...]:
        return tuple(
            str(source["source_checkpoint_id"]) for source in self.selected_sources
        )

    @property
    def passed(self) -> bool:
        return self.selected_source_count > 0 and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_seed": self.selection_seed,
            "source_limit": self.source_limit,
            "input_source_count": self.input_source_count,
            "selected_source_count": self.selected_source_count,
            "selected_record_indices": list(self.selected_record_indices),
            "selected_sources": [
                _json_safe_mapping(source) for source in self.selected_sources
            ],
            "selection_method": self.selection_method,
            "structural_coverage": _json_safe_mapping(self.structural_coverage),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class OracleTeacherScaleupManifest:
    """Machine-readable T023 scale-up manifest."""

    input_artifacts: dict[str, Any]
    source_selection: OracleTeacherSourceSelectionPlan
    requested_budgets: tuple[int, ...]
    root_selection_rule: str
    generated_artifacts: tuple[dict[str, Any], ...]
    native_source_identity: dict[str, Any]
    information_regime_summary: dict[str, Any]
    teacher_action_stability: dict[str, Any]
    soft_target_stability: dict[str, Any]
    warnings: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    schema_id: str = ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID
    format_version: int = ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return self.source_selection.passed and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "input_artifacts": _json_safe_mapping(self.input_artifacts),
            "source_selection": self.source_selection.to_dict(),
            "requested_budgets": list(self.requested_budgets),
            "root_selection_rule": self.root_selection_rule,
            "generated_artifacts": [
                _json_safe_mapping(artifact) for artifact in self.generated_artifacts
            ],
            "native_source_identity": _json_safe_mapping(self.native_source_identity),
            "information_regime_summary": _json_safe_mapping(
                self.information_regime_summary
            ),
            "teacher_action_stability": _json_safe_mapping(
                self.teacher_action_stability
            ),
            "soft_target_stability": _json_safe_mapping(self.soft_target_stability),
            "evidence_boundary": {
                "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                "not_normal_information": True,
                "not_live_game_evidence": True,
                "not_broad_training_evidence": True,
                "not_controller_strength_evidence": True,
            },
            "warnings": list(self.warnings),
            "command_passed": self.command_passed,
            "problems": list(self.problems),
        }


def validate_oracle_teacher_scaleup_budgets(
    budgets: Sequence[int],
) -> tuple[int, ...]:
    """Validate and freeze requested native-search budgets."""

    if not budgets:
        raise ValueError("oracle teacher scale-up requires at least one budget")
    result: list[int] = []
    seen: set[int] = set()
    for index, budget in enumerate(budgets):
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ValueError(
                f"oracle teacher scale-up budget {index} must be a positive integer"
            )
        if budget in seen:
            raise ValueError(
                f"oracle teacher scale-up budgets must be unique; duplicate {budget}"
            )
        seen.add(budget)
        result.append(budget)
    return tuple(result)


def build_oracle_teacher_source_selection_plan(
    pool: NaturalBattleStartPool,
    *,
    selection_seed: int,
    source_limit: int | None = None,
) -> OracleTeacherSourceSelectionPlan:
    """Build a seeded source-selection plan without quality filters."""

    if isinstance(selection_seed, bool) or not isinstance(selection_seed, int):
        raise ValueError("oracle teacher scale-up seed must be an integer")
    if selection_seed < 0:
        raise ValueError("oracle teacher scale-up seed must be non-negative")
    if source_limit is not None:
        if (
            isinstance(source_limit, bool)
            or not isinstance(source_limit, int)
            or source_limit <= 0
        ):
            raise ValueError("oracle teacher scale-up source limit must be positive")

    descriptors: list[tuple[dict[str, Any], BattleStartCheckpointRecord]] = []
    problems: list[str] = []
    checkpoint_counts: Counter[str] = Counter()
    for record in pool.records:
        descriptor, record_problems = _record_source_descriptor(record)
        descriptors.append((descriptor, record))
        checkpoint = descriptor.get("source_checkpoint_id")
        if isinstance(checkpoint, str) and checkpoint:
            checkpoint_counts[checkpoint] += 1
        problems.extend(record_problems)

    for checkpoint, count in sorted(checkpoint_counts.items()):
        if count > 1:
            problems.append(
                f"source pool contains duplicate source checkpoint id {checkpoint!r}"
            )

    ordered = sorted(descriptors, key=lambda item: _source_sort_key(item[0]))
    if source_limit is None or source_limit >= len(ordered):
        selected = ordered
        method = (
            "all_sources_sorted"
            if source_limit is None
            else "all_sources_sorted_limit_exceeds_count"
        )
    else:
        generator = random.Random(selection_seed)
        selected_indices = sorted(generator.sample(range(len(ordered)), source_limit))
        selected = [ordered[index] for index in selected_indices]
        method = "seeded_uniform_source_sample"

    selected_descriptors = tuple(_json_safe_mapping(source) for source, _ in selected)
    selected_record_indices = tuple(record.record_index for _, record in selected)
    if not selected:
        problems.append("source pool contains no battle-start records")

    return OracleTeacherSourceSelectionPlan(
        selection_seed=selection_seed,
        source_limit=source_limit,
        input_source_count=len(pool.records),
        selected_sources=selected_descriptors,
        selected_record_indices=selected_record_indices,
        selection_method=method,
        structural_coverage=_source_structural_coverage(selected_descriptors),
        problems=tuple(_dedupe(problems)),
    )


def selected_natural_battle_start_pool(
    pool: NaturalBattleStartPool,
    plan: OracleTeacherSourceSelectionPlan,
) -> NaturalBattleStartPool:
    """Return a pool containing exactly the records named by a selection plan."""

    by_index = {record.record_index: record for record in pool.records}
    selected = []
    for index in plan.selected_record_indices:
        record = by_index.get(index)
        if record is None:
            raise ValueError(f"selection plan references missing pool record {index}")
        selected.append(record)
    return NaturalBattleStartPool(
        source_run_count=len({record.source_run_id for record in selected}),
        terminal_run_count=pool.terminal_run_count,
        truncated_run_count=pool.truncated_run_count,
        source_controller_provenance=dict(pool.source_controller_provenance),
        format_version=pool.format_version,
        records=selected,
        problems=list(pool.problems),
        migration_report=pool.migration_report,
    )


def build_oracle_teacher_scaleup_manifest(
    *,
    input_artifacts: Mapping[str, Any],
    source_selection: OracleTeacherSourceSelectionPlan,
    requested_budgets: Sequence[int],
    root_selection_rule: str,
    datasets_by_budget: Mapping[int, OracleTeacherDataset],
    reports_by_budget: Mapping[int, OracleTeacherDatasetAuditReport],
    generated_artifacts: Sequence[Mapping[str, Any]],
    native_source_identity: Mapping[str, Any],
    warnings: Sequence[str] = (),
    problems: Sequence[str] = (),
) -> OracleTeacherScaleupManifest:
    """Build the current scale-up manifest from collected budget artifacts."""

    budgets = validate_oracle_teacher_scaleup_budgets(requested_budgets)
    missing_datasets = [
        budget for budget in budgets if budget not in datasets_by_budget
    ]
    missing_reports = [budget for budget in budgets if budget not in reports_by_budget]
    manifest_problems = list(problems)
    if missing_datasets:
        manifest_problems.append(
            "missing teacher datasets for budgets: "
            + ", ".join(str(budget) for budget in missing_datasets)
        )
    if missing_reports:
        manifest_problems.append(
            "missing T022 reports for budgets: "
            + ", ".join(str(budget) for budget in missing_reports)
        )
    for budget in budgets:
        dataset = datasets_by_budget.get(budget)
        if dataset is not None and dataset.problems:
            manifest_problems.extend(
                f"budget {budget} teacher dataset problem: {problem}"
                for problem in dataset.problems
            )
        report = reports_by_budget.get(budget)
        if report is not None and report.problems:
            manifest_problems.extend(
                f"budget {budget} T022 report problem: {problem}"
                for problem in report.problems
            )

    return OracleTeacherScaleupManifest(
        input_artifacts=_json_safe_mapping(input_artifacts),
        source_selection=source_selection,
        requested_budgets=budgets,
        root_selection_rule=root_selection_rule,
        generated_artifacts=tuple(
            _json_safe_mapping(artifact) for artifact in generated_artifacts
        ),
        native_source_identity=_json_safe_mapping(native_source_identity),
        information_regime_summary=_information_regime_summary(datasets_by_budget),
        teacher_action_stability=_teacher_action_stability(
            source_selection,
            budgets,
            datasets_by_budget,
        ),
        soft_target_stability=_soft_target_stability(
            source_selection,
            budgets,
            datasets_by_budget,
        ),
        warnings=tuple(_dedupe(warnings)),
        problems=tuple(_dedupe([*source_selection.problems, *manifest_problems])),
    )


def dump_oracle_teacher_scaleup_manifest_json(
    manifest: OracleTeacherScaleupManifest,
    stream: TextIO,
) -> None:
    """Write the current T023 manifest schema deterministically."""

    json.dump(manifest.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def format_oracle_teacher_scaleup_manifest(
    manifest: OracleTeacherScaleupManifest,
) -> str:
    """Format deterministic stderr evidence for a scale-up run."""

    selection = manifest.source_selection
    action = manifest.teacher_action_stability
    soft = manifest.soft_target_stability
    lines = [
        "A20 Oracle teacher scale-up",
        f"schema: {manifest.schema_id} v{manifest.format_version}",
        f"command passed: {_yes_no(manifest.command_passed)}",
        (
            "evidence boundary: full_simulator_state_oracle_like teacher data; "
            "not normal-information, live-game, broad-training, or controller-"
            "strength evidence"
        ),
        f"selected unique sources: {selection.selected_source_count}",
        f"input source records: {selection.input_source_count}",
        f"source-selection seed: {selection.selection_seed}",
        f"source limit: {selection.source_limit or '(none)'}",
        f"source-selection method: {selection.selection_method}",
        f"root-selection rule: {manifest.root_selection_rule}",
        "requested budgets: " + ", ".join(str(b) for b in manifest.requested_budgets),
        "",
        format_lightspeed_source_identity(manifest.native_source_identity),
        "",
        "selected source coverage",
    ]
    _append_counter(lines, "  ascensions", selection.structural_coverage["ascensions"])
    _append_counter(lines, "  acts", selection.structural_coverage["acts"])
    _append_counter(lines, "  room types", selection.structural_coverage["room_types"])
    _append_counter(lines, "  encounters", selection.structural_coverage["encounters"])
    _append_counter(
        lines,
        "  source runs",
        selection.structural_coverage["source_runs"],
    )
    lines.extend(
        [
            "",
            "generated budget artifacts",
        ]
    )
    if manifest.generated_artifacts:
        for artifact in manifest.generated_artifacts:
            budget = artifact.get("budget")
            stats = artifact.get("search_statistics", {})
            teacher = artifact.get("teacher_artifact", {})
            report = artifact.get("t022_report_artifact", {})
            lines.extend(
                [
                    f"  budget {budget}:",
                    f"    teacher path: {teacher.get('path')}",
                    f"    teacher sha256: {teacher.get('sha256')}",
                    f"    T022 report path: {report.get('path')}",
                    f"    T022 report sha256: {report.get('sha256')}",
                    f"    teacher rows: {stats.get('teacher_row_count')}",
                    f"    unique natural sources: {stats.get('unique_source_start_count')}",
                    f"    root rows: {stats.get('root_row_count')}",
                    f"    root visits: {stats.get('root_visit_count')}",
                    f"    search simulations: {stats.get('search_simulations')}",
                    f"    native simulator steps: {_format_optional(stats.get('native_simulator_steps'))}",
                    f"    model calls: {_format_model_calls(stats.get('model_calls'))}",
                ]
            )
    else:
        lines.append("  (none)")
    lines.extend(
        [
            "",
            "cross-budget teacher-action agreement",
            f"  complete sources: {action.get('complete_source_count')}",
            f"  all-budget agreements: {action.get('all_budget_agreement_count')}",
            f"  all-budget agreement rate: {_format_optional(action.get('all_budget_agreement_rate'), precision=6)}",
            f"  pairwise agreements: {action.get('pairwise_agreement_count')}/{action.get('pairwise_comparison_count')}",
            f"  pairwise agreement rate: {_format_optional(action.get('pairwise_agreement_rate'), precision=6)}",
            "",
            "cross-budget soft-target stability",
            f"  status: {soft.get('status')}",
            f"  available sources: {soft.get('available_source_count')}",
            f"  pairwise comparisons: {soft.get('pairwise_comparison_count')}",
            f"  mean total-variation distance: {_format_optional(soft.get('mean_pairwise_total_variation'), precision=6)}",
            f"  max total-variation distance: {_format_optional(soft.get('max_pairwise_total_variation'), precision=6)}",
            "",
            "warnings:",
        ]
    )
    if manifest.warnings:
        lines.extend(f"  - {warning}" for warning in manifest.warnings)
    else:
        lines.append("  (none)")
    lines.append("problems:")
    if manifest.problems:
        lines.extend(f"  - {problem}" for problem in manifest.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _record_source_descriptor(
    record: BattleStartCheckpointRecord,
) -> tuple[dict[str, Any], list[str]]:
    metadata = record.structural_metadata
    descriptor = {
        "source_pool_record_index": record.record_index,
        "ascension": metadata.get("ascension"),
        "act": metadata.get("act"),
        "room_type": metadata.get("room_type"),
        "encounter_id": metadata.get("encounter_id"),
        "source_run_id": record.source_run_id,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "distribution_kind": record.distribution_kind,
        "checkpoint_information_regime": record.checkpoint_information_regime,
        "public_context_status": record.public_context_status,
        "structured_resource_outcome_status": (
            record.completed_battle_resource_outcome_status
        ),
    }
    problems: list[str] = []
    label = f"source pool record {record.record_index}"
    if not _non_empty_string(record.source_checkpoint_id):
        problems.append(f"{label}: source_checkpoint_id is missing")
    if not _non_empty_string(record.source_run_id):
        problems.append(f"{label}: source_run_id is missing")
    ascension = metadata.get("ascension")
    if isinstance(ascension, bool) or not isinstance(ascension, int):
        problems.append(f"{label}: ascension metadata is missing or invalid")
    elif ascension != 20:
        problems.append(f"{label}: source is not A20")
    act = metadata.get("act")
    if isinstance(act, bool) or not isinstance(act, int) or act <= 0:
        problems.append(f"{label}: act metadata is missing or invalid")
    for field_name in ("room_type", "encounter_id"):
        if not _non_empty_string(metadata.get(field_name)):
            problems.append(f"{label}: {field_name} metadata is missing")
    metadata_run = metadata.get("source_run_id")
    if _non_empty_string(metadata_run) and metadata_run != record.source_run_id:
        problems.append(f"{label}: source_run_id does not match structural metadata")
    metadata_checkpoint = metadata.get("source_checkpoint_id")
    if (
        _non_empty_string(metadata_checkpoint)
        and metadata_checkpoint != record.source_checkpoint_id
    ):
        problems.append(
            f"{label}: source_checkpoint_id does not match structural metadata"
        )
    if record.distribution_kind != NATURAL_DISTRIBUTION_KIND:
        problems.append(f"{label}: source distribution is not natural_run")
    if record.checkpoint_information_regime != CHECKPOINT_INFORMATION_REGIME:
        problems.append(
            f"{label}: source checkpoint information regime is "
            f"{record.checkpoint_information_regime!r}, expected "
            f"{CHECKPOINT_INFORMATION_REGIME!r}"
        )
    return descriptor, problems


def _source_sort_key(source: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(source.get(field_name, "")) for field_name in SCALEUP_STRUCTURAL_FIELDS
    )


def _source_structural_coverage(
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    counters = {field_name: Counter() for field_name in SCALEUP_STRUCTURAL_FIELDS}
    strata = Counter()
    for source in sources:
        stratum_values: list[str] = []
        for field_name in SCALEUP_STRUCTURAL_FIELDS:
            value = source.get(field_name)
            text = str(value) if value not in (None, "") else "(missing)"
            counters[field_name][text] += 1
            if field_name in _STRATUM_FIELDS:
                stratum_values.append(text)
        strata["/".join(stratum_values)] += 1
    return {
        "selected_source_count": len(sources),
        "unique_source_run_count": len(
            {
                str(source.get("source_run_id"))
                for source in sources
                if source.get("source_run_id") not in (None, "")
            }
        ),
        "ascensions": _counter_dict(counters["ascension"]),
        "acts": _counter_dict(counters["act"]),
        "room_types": _counter_dict(counters["room_type"]),
        "encounters": _counter_dict(counters["encounter_id"]),
        "source_runs": _counter_dict(counters["source_run_id"]),
        "source_checkpoints": _counter_dict(counters["source_checkpoint_id"]),
        "per_stratum_counts": _counter_dict(strata),
    }


def _information_regime_summary(
    datasets_by_budget: Mapping[int, OracleTeacherDataset],
) -> dict[str, Any]:
    dataset_counts = Counter()
    row_counts = Counter()
    checkpoint_counts = Counter()
    for dataset in datasets_by_budget.values():
        dataset_counts[dataset.information_regime] += 1
        for row in dataset.records:
            row_counts[row.information_regime] += 1
            checkpoint_counts[row.checkpoint_information_regime] += 1
    passed = (
        set(dataset_counts) <= {NATIVE_SEARCH_INFORMATION_REGIME}
        and set(row_counts) <= {NATIVE_SEARCH_INFORMATION_REGIME}
        and set(checkpoint_counts) <= {NATIVE_SEARCH_INFORMATION_REGIME}
    )
    return {
        "expected_information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "dataset_counts": _counter_dict(dataset_counts),
        "row_counts": _counter_dict(row_counts),
        "checkpoint_counts": _counter_dict(checkpoint_counts),
        "passed": passed,
    }


def _teacher_action_stability(
    source_selection: OracleTeacherSourceSelectionPlan,
    budgets: Sequence[int],
    datasets_by_budget: Mapping[int, OracleTeacherDataset],
) -> dict[str, Any]:
    rows_by_budget = _rows_by_budget_and_source(budgets, datasets_by_budget)
    per_source: list[dict[str, Any]] = []
    per_stratum: dict[str, Counter[str]] = {}
    complete_source_count = 0
    all_budget_agreement_count = 0
    pairwise_agreements = 0
    pairwise_total = 0
    missing_sources = 0

    for source in source_selection.selected_sources:
        checkpoint = str(source["source_checkpoint_id"])
        rows = [rows_by_budget.get(budget, {}).get(checkpoint) for budget in budgets]
        actions_by_budget: dict[str, Any] = {}
        action_keys: list[str] = []
        missing = []
        for budget, row in zip(budgets, rows, strict=True):
            if row is None:
                missing.append(budget)
                continue
            action_key = _teacher_action_key(row)
            action_keys.append(action_key)
            actions_by_budget[str(budget)] = {
                "legal_action_index": row.teacher_action.get("legal_action_index"),
                "action_identity": _json_safe_value(
                    row.teacher_action.get("action_identity")
                ),
                "visits": row.teacher_action.get("visits"),
                "mean_value": row.teacher_action.get("mean_value"),
            }

        complete = len(missing) == 0
        if complete:
            complete_source_count += 1
        else:
            missing_sources += 1
        all_equal = complete and len(set(action_keys)) == 1
        if all_equal:
            all_budget_agreement_count += 1

        source_pair_agreements = 0
        source_pair_total = 0
        if complete:
            for left in range(len(action_keys)):
                for right in range(left + 1, len(action_keys)):
                    source_pair_total += 1
                    if action_keys[left] == action_keys[right]:
                        source_pair_agreements += 1
            pairwise_agreements += source_pair_agreements
            pairwise_total += source_pair_total

        stratum = _source_stratum(source)
        per_stratum.setdefault(stratum, Counter())
        per_stratum[stratum]["source_count"] += 1
        if complete:
            per_stratum[stratum]["complete_source_count"] += 1
        if all_equal:
            per_stratum[stratum]["all_budget_agreement_count"] += 1

        per_source.append(
            {
                "source_checkpoint_id": checkpoint,
                "source_run_id": source.get("source_run_id"),
                "structural_metadata": _source_structural_metadata(source),
                "complete": complete,
                "missing_budgets": list(missing),
                "all_budgets_same_teacher_action": all_equal,
                "pairwise_agreement_count": source_pair_agreements,
                "pairwise_comparison_count": source_pair_total,
                "actions_by_budget": actions_by_budget,
            }
        )

    return {
        "budget_count": len(budgets),
        "source_count": source_selection.selected_source_count,
        "complete_source_count": complete_source_count,
        "missing_source_count": missing_sources,
        "all_budget_agreement_count": all_budget_agreement_count,
        "all_budget_agreement_rate": _safe_ratio(
            all_budget_agreement_count,
            complete_source_count,
        ),
        "pairwise_agreement_count": pairwise_agreements,
        "pairwise_comparison_count": pairwise_total,
        "pairwise_agreement_rate": _safe_ratio(pairwise_agreements, pairwise_total),
        "per_stratum": {
            key: _counter_dict(value) for key, value in sorted(per_stratum.items())
        },
        "per_source": per_source,
    }


def _soft_target_stability(
    source_selection: OracleTeacherSourceSelectionPlan,
    budgets: Sequence[int],
    datasets_by_budget: Mapping[int, OracleTeacherDataset],
) -> dict[str, Any]:
    rows_by_budget = _rows_by_budget_and_source(budgets, datasets_by_budget)
    per_source: list[dict[str, Any]] = []
    distances: list[float] = []
    unavailable_reasons = Counter()
    available_source_count = 0
    pairwise_total = 0

    for source in source_selection.selected_sources:
        checkpoint = str(source["source_checkpoint_id"])
        rows = [rows_by_budget.get(budget, {}).get(checkpoint) for budget in budgets]
        source_distances: list[float] = []
        probabilities_by_budget: dict[int, list[float]] = {}
        identities_by_budget: dict[int, str] = {}
        reasons: list[str] = []
        for budget, row in zip(budgets, rows, strict=True):
            if row is None:
                reasons.append(f"missing budget {budget}")
                continue
            probabilities = _soft_probabilities(row)
            if probabilities is None:
                reasons.append(f"budget {budget} soft target unavailable")
                continue
            probabilities_by_budget[budget] = probabilities
            identities_by_budget[budget] = _legal_identity_key(row)

        complete = len(probabilities_by_budget) == len(budgets)
        if complete and len(set(identities_by_budget.values())) != 1:
            reasons.append("legal action identities differ across budgets")
        available = complete and not reasons
        if available:
            available_source_count += 1
            for left_index in range(len(budgets)):
                for right_index in range(left_index + 1, len(budgets)):
                    left_budget = budgets[left_index]
                    right_budget = budgets[right_index]
                    distance = _total_variation_distance(
                        probabilities_by_budget[left_budget],
                        probabilities_by_budget[right_budget],
                    )
                    source_distances.append(distance)
                    distances.append(distance)
                    pairwise_total += 1
        else:
            for reason in reasons or ["soft target unavailable"]:
                unavailable_reasons[reason] += 1

        per_source.append(
            {
                "source_checkpoint_id": checkpoint,
                "source_run_id": source.get("source_run_id"),
                "structural_metadata": _source_structural_metadata(source),
                "available": available,
                "unavailable_reasons": reasons,
                "mean_pairwise_total_variation": _mean(source_distances),
                "max_pairwise_total_variation": (
                    _round_float(max(source_distances)) if source_distances else None
                ),
            }
        )

    status = "available" if distances else "unavailable"
    return {
        "status": status,
        "source_count": source_selection.selected_source_count,
        "available_source_count": available_source_count,
        "unavailable_source_count": source_selection.selected_source_count
        - available_source_count,
        "pairwise_comparison_count": pairwise_total,
        "mean_pairwise_total_variation": _mean(distances),
        "max_pairwise_total_variation": (
            _round_float(max(distances)) if distances else None
        ),
        "unavailable_reasons": _counter_dict(unavailable_reasons),
        "per_source": per_source,
    }


def _rows_by_budget_and_source(
    budgets: Sequence[int],
    datasets_by_budget: Mapping[int, OracleTeacherDataset],
) -> dict[int, dict[str, OracleTeacherRow]]:
    result: dict[int, dict[str, OracleTeacherRow]] = {}
    for budget in budgets:
        by_source: dict[str, OracleTeacherRow] = {}
        dataset = datasets_by_budget.get(budget)
        if dataset is not None:
            for row in dataset.records:
                by_source[row.source_checkpoint_id] = row
        result[budget] = by_source
    return result


def _teacher_action_key(row: OracleTeacherRow) -> str:
    identity = row.teacher_action.get("action_identity")
    return json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)


def _soft_probabilities(row: OracleTeacherRow) -> list[float] | None:
    probabilities = row.soft_visit_target.get("probabilities")
    if not isinstance(probabilities, list):
        return None
    result: list[float] = []
    for value in probabilities:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        result.append(float(value))
    if len(result) != len(row.legal_action_identities):
        return None
    return result


def _legal_identity_key(row: OracleTeacherRow) -> str:
    return json.dumps(
        row.legal_action_identities,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _total_variation_distance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 1.0
    return _round_float(0.5 * sum(abs(a - b) for a, b in zip(left, right, strict=True)))


def _source_stratum(source: Mapping[str, Any]) -> str:
    return "/".join(
        str(source.get(field_name, "(missing)")) for field_name in _STRATUM_FIELDS
    )


def _source_structural_metadata(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field_name: _json_safe_value(source.get(field_name))
        for field_name in SCALEUP_STRUCTURAL_FIELDS
    }


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return _round_float(numerator / denominator)


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return _round_float(sum(values) / len(values))


def _round_float(value: float) -> float:
    return round(float(value), 6)


def _format_optional(value: Any, *, precision: int = 0) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    number = float(value)
    if precision:
        return f"{number:.{precision}f}"
    if number.is_integer():
        return str(int(number))
    return f"{number:.3f}"


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


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): values[key] for key in sorted(values, key=lambda item: str(item))}


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


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
