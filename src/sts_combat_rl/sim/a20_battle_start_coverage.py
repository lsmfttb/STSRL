"""A20 battle-start coverage measurement for T021.

This module combines existing natural-pool, constructed-supplement, restore,
and T009 gate surfaces.  It reports coverage and gate gaps only; it does not
train models, run teacher search, or mutate simulator state.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.battle_start_pool import (
    STRUCTURAL_SAMPLING_COMPONENT,
    BattleStartCheckpointRecord,
    BattleStartPoolCoverageReport,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    SampledBattleStart,
    build_battle_start_pool_coverage_report,
    record_to_manifest,
)
from sts_combat_rl.sim.constructed_battle_start import (
    CONSTRUCTED_DISTRIBUTION_KIND,
    ConstructedBattleStartArtifact,
    ConstructedBattleStartAuditReport,
    ConstructedBattleStartRecord,
    build_constructed_battle_start_audit_report,
)
from sts_combat_rl.sim.lightspeed_source import (
    format_lightspeed_source_identity,
    lightspeed_source_identity_dict,
)
from sts_combat_rl.sim.training_gate import (
    TRAINING_GATE_OVERRIDE_NONE,
    TrainingGateReport,
    TrainingScaleGateConfig,
    build_training_gate_report,
    format_training_gate_report,
)


A20_BATTLE_START_COVERAGE_SCHEMA_ID = "a20-battle-start-coverage-report-v1"
A20_BATTLE_START_COVERAGE_FORMAT_VERSION = 1
STRATIFIED_TRAINING_DISTRIBUTION_KIND = "stratified_training"
CONSTRUCTED_PUBLIC_CONTEXT_STATUS = "constructed_context_unavailable"
CONSTRUCTED_OUTCOME_STATUS = "constructed_battle_outcome_unavailable"


@dataclass(frozen=True)
class A20CoverageCommandConfig:
    """Behavior-changing settings used to produce one coverage report."""

    restore_limit: int = 0
    sample_count: int = 0
    sampling_seed: int = 1
    structural_fraction: float = 0.5
    gate_config: TrainingScaleGateConfig = field(
        default_factory=TrainingScaleGateConfig
    )
    gate_override: str = TRAINING_GATE_OVERRIDE_NONE

    def to_dict(self) -> dict[str, Any]:
        return {
            "restore_limit": self.restore_limit,
            "sample_count": self.sample_count,
            "sampling_seed": self.sampling_seed,
            "structural_fraction": self.structural_fraction,
            "gate_config": self.gate_config.to_dict(),
            "gate_override": self.gate_override,
        }


@dataclass(frozen=True)
class A20TrainingRowCoverage:
    """Structural coverage for rows considered by the gate adapter."""

    row_count: int
    unique_natural_source_count: int
    distribution_kind_counts: Counter[str] = field(default_factory=Counter)
    ascension_counts: Counter[str] = field(default_factory=Counter)
    act_counts: Counter[str] = field(default_factory=Counter)
    room_type_counts: Counter[str] = field(default_factory=Counter)
    encounter_id_counts: Counter[str] = field(default_factory=Counter)
    missing_metadata_counts: Counter[str] = field(default_factory=Counter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "unique_natural_source_count": self.unique_natural_source_count,
            "distribution_kind_counts": _counter_dict(self.distribution_kind_counts),
            "ascension_counts": _counter_dict(self.ascension_counts),
            "act_counts": _counter_dict(self.act_counts),
            "room_type_counts": _counter_dict(self.room_type_counts),
            "encounter_id_counts": _counter_dict(self.encounter_id_counts),
            "missing_metadata_counts": _counter_dict(self.missing_metadata_counts),
        }


@dataclass(frozen=True)
class A20ConstructedCoverage:
    """Constructed-supplement accounting kept separate from natural coverage."""

    loaded: bool
    source_record_count: int = 0
    audit_record_count: int = 0
    constructed_record_count: int = 0
    no_op_row_count: int = 0
    unsupported_row_count: int = 0
    first_battle_source_count: int = 0
    later_battle_source_count: int = 0
    transform_policy: dict[str, Any] = field(default_factory=dict)
    distribution_counts: Counter[str] = field(default_factory=Counter)
    transform_type_counts: Counter[str] = field(default_factory=Counter)
    actual_status_counts: Counter[str] = field(default_factory=Counter)
    native_support_counts: Counter[str] = field(default_factory=Counter)
    unsupported_native_operation_counts: Counter[str] = field(default_factory=Counter)
    source_context_status_counts: Counter[str] = field(default_factory=Counter)
    source_distribution_counts: Counter[str] = field(default_factory=Counter)
    problems: tuple[str, ...] = ()

    @classmethod
    def missing(cls) -> A20ConstructedCoverage:
        return cls(loaded=False)

    @classmethod
    def from_artifact(
        cls,
        artifact: ConstructedBattleStartArtifact,
        audit: ConstructedBattleStartAuditReport,
    ) -> A20ConstructedCoverage:
        no_op_count = sum(
            1
            for record in artifact.records
            if not record.actual_applied
            and record.native_support_status != "unsupported"
        )
        unsupported_count = sum(
            1
            for record in artifact.records
            if record.native_support_status == "unsupported"
        )
        return cls(
            loaded=True,
            source_record_count=audit.source_record_count,
            audit_record_count=audit.audit_record_count,
            constructed_record_count=audit.constructed_record_count,
            no_op_row_count=no_op_count,
            unsupported_row_count=unsupported_count,
            first_battle_source_count=audit.first_battle_source_count,
            later_battle_source_count=audit.later_battle_source_count,
            transform_policy=dict(audit.transform_policy),
            distribution_counts=Counter(audit.distribution_counts),
            transform_type_counts=Counter(
                artifact.mixture_manifest.transform_type_counts
            ),
            actual_status_counts=Counter(audit.actual_counts),
            native_support_counts=Counter(audit.native_support_counts),
            unsupported_native_operation_counts=Counter(
                audit.unsupported_native_operation_counts
            ),
            source_context_status_counts=Counter(audit.source_context_status_counts),
            source_distribution_counts=Counter(
                record.source_distribution_kind for record in artifact.records
            ),
            problems=tuple(audit.problems),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "source_record_count": self.source_record_count,
            "audit_record_count": self.audit_record_count,
            "constructed_record_count": self.constructed_record_count,
            "no_op_row_count": self.no_op_row_count,
            "unsupported_row_count": self.unsupported_row_count,
            "first_battle_source_count": self.first_battle_source_count,
            "later_battle_source_count": self.later_battle_source_count,
            "transform_policy": _json_safe_mapping(self.transform_policy),
            "distribution_counts": _counter_dict(self.distribution_counts),
            "transform_type_counts": _counter_dict(self.transform_type_counts),
            "actual_status_counts": _counter_dict(self.actual_status_counts),
            "native_support_counts": _counter_dict(self.native_support_counts),
            "unsupported_native_operation_counts": _counter_dict(
                self.unsupported_native_operation_counts
            ),
            "source_context_status_counts": _counter_dict(
                self.source_context_status_counts
            ),
            "source_distribution_counts": _counter_dict(
                self.source_distribution_counts
            ),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class A20BattleStartCoverageReport:
    """Current-schema A20 battle-start coverage report."""

    command_config: A20CoverageCommandConfig
    input_artifacts: dict[str, Any]
    source_identity: dict[str, Any]
    natural_coverage: BattleStartPoolCoverageReport
    sampled_draw_count: int
    sampled_unique_source_count: int
    sampled_component_counts: Counter[str]
    constructed_coverage: A20ConstructedCoverage
    restore_verification: BattleStartPoolRestoreReport
    training_row_coverage: A20TrainingRowCoverage
    training_gate_report: TrainingGateReport
    command_problems: tuple[str, ...] = ()
    schema_id: str = A20_BATTLE_START_COVERAGE_SCHEMA_ID
    format_version: int = A20_BATTLE_START_COVERAGE_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return not self.command_problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "input_artifacts": _json_safe_mapping(self.input_artifacts),
            "source_identity": _json_safe_mapping(self.source_identity),
            "command_config": self.command_config.to_dict(),
            "natural_coverage": _natural_coverage_dict(self.natural_coverage),
            "sampled_optimization_weight": {
                "sampled_draw_count": self.sampled_draw_count,
                "sampled_unique_source_count": self.sampled_unique_source_count,
                "sampling_component_counts": _counter_dict(
                    self.sampled_component_counts
                ),
            },
            "constructed_coverage": self.constructed_coverage.to_dict(),
            "restore_verification": _restore_report_dict(self.restore_verification),
            "training_row_coverage": self.training_row_coverage.to_dict(),
            "training_gate_report": self.training_gate_report.to_dict(),
            "command_passed": self.command_passed,
            "command_problems": list(self.command_problems),
        }


@dataclass(frozen=True)
class _GateRecord:
    example_index: int
    source_metadata: dict[str, Any]
    public_context_status: str
    structured_battle_outcome_status: str


@dataclass(frozen=True)
class _GateDataset:
    records: list[_GateRecord]
    problems: list[str] = field(default_factory=list)


def build_a20_battle_start_coverage_report(
    pool: NaturalBattleStartPool,
    *,
    sampled: Sequence[SampledBattleStart] = (),
    constructed_artifact: ConstructedBattleStartArtifact | None = None,
    restore_report: BattleStartPoolRestoreReport | None = None,
    command_config: A20CoverageCommandConfig | None = None,
    input_artifacts: Mapping[str, Any] | None = None,
    source_identity: Mapping[str, Any] | None = None,
) -> A20BattleStartCoverageReport:
    """Build the T021 coverage report from already-loaded current artifacts."""

    config = command_config or A20CoverageCommandConfig()
    active_restore = restore_report or BattleStartPoolRestoreReport(
        checkpoint_count=len(pool.records),
        requested_limit=config.restore_limit,
        restored_count=0,
        native_restored_count=0,
        replay_restored_count=0,
    )
    natural_coverage = build_battle_start_pool_coverage_report(pool, sampled=sampled)
    constructed_audit = (
        build_constructed_battle_start_audit_report(constructed_artifact)
        if constructed_artifact is not None
        else None
    )
    constructed_coverage = (
        A20ConstructedCoverage.from_artifact(constructed_artifact, constructed_audit)
        if constructed_artifact is not None and constructed_audit is not None
        else A20ConstructedCoverage.missing()
    )
    constructed_provenance_problems = (
        _constructed_source_provenance_problems(pool, constructed_artifact)
        if constructed_artifact is not None
        else []
    )
    gate_records, gate_dataset_problems = _build_gate_records(
        pool,
        sampled=sampled,
        constructed_artifact=constructed_artifact,
    )
    gate_report = build_training_gate_report(
        _GateDataset(records=gate_records, problems=gate_dataset_problems),  # type: ignore[arg-type]
        config.gate_config,
        override=config.gate_override,
    )
    training_row_coverage = _build_training_row_coverage(gate_records)
    command_problems = tuple(
        dict.fromkeys(
            [
                *_restore_command_problems(active_restore),
                *constructed_provenance_problems,
            ]
        )
    )
    return A20BattleStartCoverageReport(
        command_config=config,
        input_artifacts=_json_safe_mapping(input_artifacts or {}),
        source_identity=_json_safe_mapping(
            source_identity or lightspeed_source_identity_dict()
        ),
        natural_coverage=natural_coverage,
        sampled_draw_count=len(sampled),
        sampled_unique_source_count=len(
            {sample.source_checkpoint_id for sample in sampled}
        ),
        sampled_component_counts=Counter(
            sample.sampling_component for sample in sampled
        ),
        constructed_coverage=constructed_coverage,
        restore_verification=active_restore,
        training_row_coverage=training_row_coverage,
        training_gate_report=gate_report,
        command_problems=command_problems,
    )


def dump_a20_battle_start_coverage_report_json(
    report: A20BattleStartCoverageReport,
    stream: TextIO,
) -> None:
    """Write the current report schema in deterministic JSON form."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_a20_battle_start_coverage_report(
    report: A20BattleStartCoverageReport,
) -> str:
    """Format deterministic stderr evidence for the T021 report."""

    lines = [
        "A20 battle-start coverage report",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        "input artifacts:",
    ]
    _append_nested_mapping(lines, report.input_artifacts)
    lines.append("")
    lines.append(format_lightspeed_source_identity(report.source_identity))
    lines.append("")
    lines.extend(_format_natural_coverage(report.natural_coverage))
    lines.append("")
    lines.extend(_format_sampled_weight(report))
    lines.append("")
    lines.extend(_format_constructed_coverage(report.constructed_coverage))
    lines.append("")
    lines.extend(_format_restore_report(report.restore_verification))
    lines.append("")
    lines.extend(_format_training_row_coverage(report.training_row_coverage))
    lines.append("")
    lines.append(format_training_gate_report(report.training_gate_report))
    lines.append("")
    lines.append("command problems:")
    if report.command_problems:
        lines.extend(f"  - {problem}" for problem in report.command_problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _build_gate_records(
    pool: NaturalBattleStartPool,
    *,
    sampled: Sequence[SampledBattleStart],
    constructed_artifact: ConstructedBattleStartArtifact | None,
) -> tuple[list[_GateRecord], list[str]]:
    records: list[_GateRecord] = []
    problems: list[str] = []
    next_index = 0
    for source in pool.records:
        records.append(
            _GateRecord(
                example_index=next_index,
                source_metadata=_metadata_from_natural_record(
                    source,
                    distribution_kind=source.distribution_kind,
                ),
                public_context_status=source.public_context_status,
                structured_battle_outcome_status=(
                    source.completed_battle_resource_outcome_status
                ),
            )
        )
        next_index += 1

    for sample in sampled:
        if sample.sampling_component == STRUCTURAL_SAMPLING_COMPONENT:
            distribution = STRATIFIED_TRAINING_DISTRIBUTION_KIND
        else:
            distribution = sample.record.distribution_kind
        records.append(
            _GateRecord(
                example_index=next_index,
                source_metadata={
                    **_metadata_from_natural_record(
                        sample.record,
                        distribution_kind=distribution,
                    ),
                    "sampling_component": sample.sampling_component,
                    "sample_index": sample.sample_index,
                },
                public_context_status=sample.record.public_context_status,
                structured_battle_outcome_status=(
                    sample.record.completed_battle_resource_outcome_status
                ),
            )
        )
        next_index += 1

    if constructed_artifact is not None:
        for constructed in constructed_artifact.records:
            if constructed.resulting_distribution_kind != CONSTRUCTED_DISTRIBUTION_KIND:
                continue
            source_metadata = _metadata_from_constructed_record(constructed)
            records.append(
                _GateRecord(
                    example_index=next_index,
                    source_metadata=source_metadata,
                    public_context_status=CONSTRUCTED_PUBLIC_CONTEXT_STATUS,
                    structured_battle_outcome_status=CONSTRUCTED_OUTCOME_STATUS,
                )
            )
            next_index += 1

    for record in records:
        metadata = record.source_metadata
        missing = [
            field_name
            for field_name in ("ascension", "act", "source_checkpoint_id")
            if metadata.get(field_name) in (None, "")
        ]
        if missing:
            problems.append(
                "coverage row "
                f"{record.example_index} missing required gate metadata: "
                + ", ".join(missing)
            )
    return records, problems


def _metadata_from_natural_record(
    record: BattleStartCheckpointRecord,
    *,
    distribution_kind: str,
) -> dict[str, Any]:
    metadata = dict(record.structural_metadata)
    metadata["distribution_kind"] = distribution_kind
    metadata["source_kind"] = distribution_kind
    metadata["source_checkpoint_id"] = record.source_checkpoint_id
    metadata["source_run_id"] = record.source_run_id
    metadata["source_battle_index"] = record.source_battle_index
    metadata["seed"] = record.source_seed
    return _json_safe_mapping(metadata)


def _metadata_from_constructed_record(
    record: ConstructedBattleStartRecord,
) -> dict[str, Any]:
    metadata = dict(record.source_structural_metadata)
    metadata["distribution_kind"] = record.resulting_distribution_kind
    metadata["source_kind"] = record.resulting_distribution_kind
    metadata["source_distribution_kind"] = record.source_distribution_kind
    metadata["source_checkpoint_id"] = record.source_checkpoint_id
    metadata["source_run_id"] = record.source_record.get("source_run_id")
    metadata["source_battle_index"] = record.source_record.get("source_battle_index")
    metadata["constructed_record_index"] = record.record_index
    metadata["transform_type"] = record.transform_type
    return _json_safe_mapping(metadata)


def _build_training_row_coverage(
    records: Sequence[_GateRecord],
) -> A20TrainingRowCoverage:
    ascensions: Counter[str] = Counter()
    acts: Counter[str] = Counter()
    room_types: Counter[str] = Counter()
    encounters: Counter[str] = Counter()
    distributions: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    source_ids: set[str] = set()

    for record in records:
        metadata = record.source_metadata
        for field_name, counter in (
            ("ascension", ascensions),
            ("act", acts),
            ("room_type", room_types),
            ("encounter_id", encounters),
            ("distribution_kind", distributions),
        ):
            value = metadata.get(field_name)
            if value is None or value == "":
                missing[field_name] += 1
                counter["(missing)"] += 1
            else:
                counter[str(value)] += 1
        checkpoint_id = metadata.get("source_checkpoint_id")
        if isinstance(checkpoint_id, str) and checkpoint_id:
            source_ids.add(checkpoint_id)

    return A20TrainingRowCoverage(
        row_count=len(records),
        unique_natural_source_count=len(source_ids),
        distribution_kind_counts=distributions,
        ascension_counts=ascensions,
        act_counts=acts,
        room_type_counts=room_types,
        encounter_id_counts=encounters,
        missing_metadata_counts=missing,
    )


def _constructed_source_provenance_problems(
    pool: NaturalBattleStartPool,
    artifact: ConstructedBattleStartArtifact,
) -> list[str]:
    problems: list[str] = []
    if artifact.source_record_count != len(pool.records):
        problems.append(
            "constructed artifact source_record_count "
            f"{artifact.source_record_count} does not match natural pool "
            f"{len(pool.records)}"
        )
    if artifact.source_controller_provenance != pool.source_controller_provenance:
        problems.append(
            "constructed artifact source controller provenance does not match "
            "natural pool"
        )
    for record in artifact.records:
        if record.source_record_index < 0 or record.source_record_index >= len(
            pool.records
        ):
            problems.append(
                f"constructed record {record.record_index} source_record_index "
                "is outside the natural pool"
            )
            continue
        source = pool.records[record.source_record_index]
        if record.source_checkpoint_id != source.source_checkpoint_id:
            problems.append(
                f"constructed record {record.record_index} source checkpoint "
                "does not match the natural pool"
            )
        if record.source_record != record_to_manifest(source):
            problems.append(
                f"constructed record {record.record_index} embedded source record "
                "does not match the natural pool"
            )
    return list(dict.fromkeys(problems))


def _restore_command_problems(
    report: BattleStartPoolRestoreReport,
) -> list[str]:
    expected = report.checkpoint_count
    if report.requested_limit > 0:
        expected = min(expected, report.requested_limit)
    problems = list(report.problems)
    if expected > 0 and report.restored_count != expected:
        problems.append(
            f"restore verified {report.restored_count} of {expected} requested records"
        )
    return problems


def _natural_coverage_dict(report: BattleStartPoolCoverageReport) -> dict[str, Any]:
    return {
        "natural_battle_start_count": report.natural_battle_start_count,
        "unique_source_start_count": report.unique_source_start_count,
        "source_run_count": report.source_run_count,
        "terminal_run_count": report.terminal_run_count,
        "truncated_run_count": report.truncated_run_count,
        "reported_battle_win_count": report.reported_battle_win_count,
        "completed_battle_count": report.completed_battle_count,
        "completed_battle_outcome_missing_count": (
            report.completed_battle_outcome_missing_count
        ),
        "completed_outcomes_complete": report.completed_outcomes_complete,
        "later_act_source_run_count": report.later_act_source_run_count,
        "sampled_draw_count": report.sampled_draw_count,
        "sampling_component_counts": _counter_dict(report.sampling_component_counts),
        "ascension_counts": _counter_dict(report.ascension_counts),
        "act_counts": _counter_dict(report.act_counts),
        "room_type_counts": _counter_dict(report.room_type_counts),
        "encounter_id_counts": _counter_dict(report.encounter_id_counts),
        "reported_battle_outcome_counts": _counter_dict(
            report.reported_battle_outcome_counts
        ),
        "structured_resource_outcome_status_counts": _counter_dict(
            report.resource_outcome_status_counts
        ),
        "missing_metadata_counts": _counter_dict(report.missing_metadata_counts),
        "problems": list(report.problems),
    }


def _restore_report_dict(report: BattleStartPoolRestoreReport) -> dict[str, Any]:
    return {
        "checkpoint_count": report.checkpoint_count,
        "requested_limit": report.requested_limit,
        "restored_count": report.restored_count,
        "native_restored_count": report.native_restored_count,
        "replay_restored_count": report.replay_restored_count,
        "context_compared_count": report.context_compared_count,
        "context_matched_count": report.context_matched_count,
        "context_legacy_unavailable_count": report.context_legacy_unavailable_count,
        "context_mismatch_count": report.context_mismatch_count,
        "restore_ok": report.restore_ok,
        "problems": list(report.problems),
    }


def _format_natural_coverage(
    report: BattleStartPoolCoverageReport,
) -> list[str]:
    lines = ["natural battle-start coverage"]
    lines.append(f"  source runs: {report.source_run_count}")
    lines.append(f"  terminal source runs: {report.terminal_run_count}")
    lines.append(f"  truncated source runs: {report.truncated_run_count}")
    lines.append(f"  natural battle starts: {report.natural_battle_start_count}")
    lines.append(f"  unique natural sources: {report.unique_source_start_count}")
    lines.append(f"  completed battles: {report.completed_battle_count}")
    lines.append(
        "  completed battles missing outcome: "
        f"{report.completed_battle_outcome_missing_count}"
    )
    lines.append(f"  reported battle wins: {report.reported_battle_win_count}")
    lines.append(f"  later-act source runs: {report.later_act_source_run_count}")
    _append_counter(lines, "  ascensions", report.ascension_counts)
    _append_counter(lines, "  acts", report.act_counts)
    _append_counter(lines, "  room types", report.room_type_counts)
    _append_counter(lines, "  encounters", report.encounter_id_counts)
    _append_counter(
        lines,
        "  structured resource outcome statuses",
        report.resource_outcome_status_counts,
    )
    _append_counter(
        lines, "  missing structural metadata", report.missing_metadata_counts
    )
    _append_problem_list(lines, "  natural coverage problems", report.problems)
    return lines


def _format_sampled_weight(report: A20BattleStartCoverageReport) -> list[str]:
    lines = ["sampled optimization weight"]
    lines.append(f"  sampled draws: {report.sampled_draw_count}")
    lines.append(
        f"  sampled unique natural sources: {report.sampled_unique_source_count}"
    )
    _append_counter(
        lines,
        "  sampling components",
        report.sampled_component_counts,
    )
    return lines


def _format_constructed_coverage(
    report: A20ConstructedCoverage,
) -> list[str]:
    lines = ["constructed supplement coverage"]
    lines.append(f"  loaded: {_yes_no(report.loaded)}")
    lines.append(f"  source natural battle starts: {report.source_record_count}")
    lines.append(f"  transform audit rows: {report.audit_record_count}")
    lines.append(f"  accepted constructed rows: {report.constructed_record_count}")
    lines.append(f"  no-op rows: {report.no_op_row_count}")
    lines.append(f"  unsupported rows: {report.unsupported_row_count}")
    lines.append(f"  first-battle sources: {report.first_battle_source_count}")
    lines.append(f"  later-battle sources: {report.later_battle_source_count}")
    _append_counter(lines, "  resulting distributions", report.distribution_counts)
    _append_counter(lines, "  transform kinds", report.transform_type_counts)
    _append_counter(lines, "  actual transform results", report.actual_status_counts)
    _append_counter(lines, "  native support", report.native_support_counts)
    _append_counter(
        lines,
        "  unsupported native operations",
        report.unsupported_native_operation_counts,
    )
    _append_counter(
        lines,
        "  source public-context statuses",
        report.source_context_status_counts,
    )
    _append_counter(
        lines,
        "  source distribution kinds",
        report.source_distribution_counts,
    )
    _append_problem_list(lines, "  constructed coverage problems", report.problems)
    return lines


def _format_restore_report(
    report: BattleStartPoolRestoreReport,
) -> list[str]:
    lines = ["restore verification"]
    lines.append(f"  checkpoint records: {report.checkpoint_count}")
    lines.append(f"  requested limit: {report.requested_limit or '(all)'}")
    lines.append(f"  restored records: {report.restored_count}")
    lines.append(f"  native restores: {report.native_restored_count}")
    lines.append(f"  seed/action-trace restores: {report.replay_restored_count}")
    lines.append(f"  public-context comparisons: {report.context_compared_count}")
    lines.append(f"  public-context matches: {report.context_matched_count}")
    lines.append(
        f"  public-context legacy losses: {report.context_legacy_unavailable_count}"
    )
    lines.append(f"  public-context mismatches: {report.context_mismatch_count}")
    lines.append(f"  restore ok: {_yes_no(report.restore_ok)}")
    _append_problem_list(lines, "  restore problems", report.problems)
    return lines


def _format_training_row_coverage(
    report: A20TrainingRowCoverage,
) -> list[str]:
    lines = ["training-row coverage for T009 gate"]
    lines.append(f"  training rows: {report.row_count}")
    lines.append(f"  unique natural sources: {report.unique_natural_source_count}")
    _append_counter(lines, "  distribution kinds", report.distribution_kind_counts)
    _append_counter(lines, "  ascensions", report.ascension_counts)
    _append_counter(lines, "  acts", report.act_counts)
    _append_counter(lines, "  room types", report.room_type_counts)
    _append_counter(lines, "  encounters", report.encounter_id_counts)
    _append_counter(
        lines,
        "  missing structural metadata",
        report.missing_metadata_counts,
    )
    return lines


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


def _append_problem_list(
    lines: list[str],
    title: str,
    problems: Sequence[str],
) -> None:
    lines.append(f"{title}:")
    if problems:
        lines.extend(f"    - {problem}" for problem in problems)
    else:
        lines.append("    (none)")


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


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): values[key] for key in sorted(values, key=lambda item: str(item))}


def _json_safe_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in values.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Counter):
        return _counter_dict(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
