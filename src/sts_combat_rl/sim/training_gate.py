"""Scale and distribution gates for broad battle-policy training.

The gate is deliberately separate from model code so under-covered datasets can
fail closed without importing PyTorch.  Named overrides may allow smoke or
narrow-curriculum plumbing runs, but they never mark broad training as ready.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from sts_combat_rl.sim.public_context_artifacts import PUBLIC_CONTEXT_AVAILABLE
from sts_combat_rl.sim.resource_outcome import BATTLE_RESOURCE_OUTCOME_AVAILABLE
from sts_combat_rl.sim.trainer_input import TrainerInputDataset


BROAD_TRAINING_GATE_SCHEMA_ID = "t009-broad-training-gate-v1"
TRAINING_GATE_OVERRIDE_NONE = "none"
TRAINING_GATE_OVERRIDE_SMOKE = "smoke"
TRAINING_GATE_OVERRIDE_NARROW_CURRICULUM = "narrow_curriculum"
TRAINING_GATE_OVERRIDES = (
    TRAINING_GATE_OVERRIDE_NONE,
    TRAINING_GATE_OVERRIDE_SMOKE,
    TRAINING_GATE_OVERRIDE_NARROW_CURRICULUM,
)


@dataclass(frozen=True)
class TrainingScaleGateConfig:
    """Rule-defined minimum coverage for broad policy/value training."""

    required_ascensions: tuple[int, ...] = (20,)
    required_acts: tuple[int, ...] = (1, 2, 3, 4)
    min_records_per_ascension_act: int = 100
    min_unique_sources_per_ascension_act: int = 20
    allowed_distribution_kinds: tuple[str, ...] = (
        "natural_run",
        "stratified_training",
        "constructed_supplement",
    )
    require_public_context: bool = True
    require_structured_outcomes: bool = True

    def __post_init__(self) -> None:
        if not self.required_ascensions:
            raise ValueError("training gate requires at least one ascension")
        if not self.required_acts:
            raise ValueError("training gate requires at least one act")
        if min(self.required_ascensions) < 0:
            raise ValueError("required ascensions cannot be negative")
        if min(self.required_acts) <= 0:
            raise ValueError("required acts must be positive")
        if self.min_records_per_ascension_act <= 0:
            raise ValueError("minimum records per ascension/act must be positive")
        if self.min_unique_sources_per_ascension_act <= 0:
            raise ValueError(
                "minimum unique sources per ascension/act must be positive"
            )
        if not self.allowed_distribution_kinds:
            raise ValueError("training gate requires at least one distribution kind")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrainingGateCell:
    """Observed coverage for one ascension/act cell."""

    ascension: int
    act: int
    record_count: int
    unique_source_count: int
    distribution_counts: dict[str, int] = field(default_factory=dict)
    public_context_status_counts: dict[str, int] = field(default_factory=dict)
    structured_outcome_status_counts: dict[str, int] = field(default_factory=dict)
    passed: bool = False
    problems: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"A{self.ascension}/act{self.act}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ascension": self.ascension,
            "act": self.act,
            "record_count": self.record_count,
            "unique_source_count": self.unique_source_count,
            "distribution_counts": dict(self.distribution_counts),
            "public_context_status_counts": dict(self.public_context_status_counts),
            "structured_outcome_status_counts": dict(
                self.structured_outcome_status_counts
            ),
            "passed": self.passed,
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class TrainingGateReport:
    """Fail-closed broad-training decision plus optional override status."""

    config: TrainingScaleGateConfig
    override: str
    record_count: int
    gate_passed_without_override: bool
    broad_training_allowed: bool
    training_allowed: bool
    cells: tuple[TrainingGateCell, ...]
    observed_ascension_counts: dict[int, int] = field(default_factory=dict)
    observed_act_counts: dict[int, int] = field(default_factory=dict)
    distribution_counts: dict[str, int] = field(default_factory=dict)
    public_context_status_counts: dict[str, int] = field(default_factory=dict)
    structured_outcome_status_counts: dict[str, int] = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    schema_id: str = BROAD_TRAINING_GATE_SCHEMA_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "config": self.config.to_dict(),
            "override": self.override,
            "record_count": self.record_count,
            "gate_passed_without_override": self.gate_passed_without_override,
            "broad_training_allowed": self.broad_training_allowed,
            "training_allowed": self.training_allowed,
            "cells": [cell.to_dict() for cell in self.cells],
            "observed_ascension_counts": {
                str(key): value for key, value in self.observed_ascension_counts.items()
            },
            "observed_act_counts": {
                str(key): value for key, value in self.observed_act_counts.items()
            },
            "distribution_counts": dict(self.distribution_counts),
            "public_context_status_counts": dict(self.public_context_status_counts),
            "structured_outcome_status_counts": dict(
                self.structured_outcome_status_counts
            ),
            "problems": list(self.problems),
        }


def build_training_gate_report(
    dataset: TrainerInputDataset,
    config: TrainingScaleGateConfig | None = None,
    *,
    override: str = TRAINING_GATE_OVERRIDE_NONE,
) -> TrainingGateReport:
    """Evaluate broad-training readiness from rule-defined metadata only."""

    active_config = config or TrainingScaleGateConfig()
    if override not in TRAINING_GATE_OVERRIDES:
        raise ValueError(f"unknown training gate override {override!r}")

    records_by_cell: dict[tuple[int, int], list[Any]] = {
        (ascension, act): []
        for ascension in active_config.required_ascensions
        for act in active_config.required_acts
    }
    all_distribution_counts: Counter[str] = Counter()
    all_public_context_counts: Counter[str] = Counter()
    all_outcome_counts: Counter[str] = Counter()
    ascension_counts: Counter[int] = Counter()
    act_counts: Counter[int] = Counter()
    global_problems: list[str] = list(dataset.problems)

    for record in dataset.records:
        metadata = (
            record.source_metadata
            if isinstance(record.source_metadata, Mapping)
            else {}
        )
        ascension = _optional_int(metadata.get("ascension"))
        act = _optional_int(metadata.get("act"))
        distribution = _distribution_kind(metadata)
        all_distribution_counts[distribution] += 1
        all_public_context_counts[record.public_context_status] += 1
        all_outcome_counts[record.structured_battle_outcome_status] += 1
        if ascension is not None:
            ascension_counts[ascension] += 1
        if act is not None:
            act_counts[act] += 1
        if (
            ascension is not None
            and act is not None
            and (ascension, act) in records_by_cell
        ):
            records_by_cell[(ascension, act)].append(record)
        if distribution not in active_config.allowed_distribution_kinds:
            global_problems.append(
                "record "
                f"{record.example_index}: distribution {distribution!r} is not "
                "allowed for broad training"
            )

    cells: list[TrainingGateCell] = []
    for ascension in active_config.required_ascensions:
        for act in active_config.required_acts:
            records = records_by_cell[(ascension, act)]
            cell = _build_cell(active_config, ascension, act, records)
            cells.append(cell)
            global_problems.extend(
                f"{cell.key}: {problem}" for problem in cell.problems
            )

    unique_global_problems = tuple(dict.fromkeys(global_problems))
    passed_without_override = bool(dataset.records) and not unique_global_problems
    has_override = override != TRAINING_GATE_OVERRIDE_NONE
    return TrainingGateReport(
        config=active_config,
        override=override,
        record_count=len(dataset.records),
        gate_passed_without_override=passed_without_override,
        broad_training_allowed=passed_without_override and not has_override,
        training_allowed=passed_without_override or has_override,
        cells=tuple(cells),
        observed_ascension_counts=dict(sorted(ascension_counts.items())),
        observed_act_counts=dict(sorted(act_counts.items())),
        distribution_counts=dict(sorted(all_distribution_counts.items())),
        public_context_status_counts=dict(sorted(all_public_context_counts.items())),
        structured_outcome_status_counts=dict(sorted(all_outcome_counts.items())),
        problems=unique_global_problems,
    )


def format_training_gate_report(report: TrainingGateReport) -> str:
    """Format the broad-training gate for stderr and PR evidence."""

    config = report.config
    lines = [
        "T009 broad training gate",
        f"schema: {report.schema_id}",
        f"override: {report.override}",
        f"records: {report.record_count}",
        (
            "required ascensions: "
            + ", ".join(str(value) for value in config.required_ascensions)
        ),
        "required acts: " + ", ".join(str(value) for value in config.required_acts),
        (
            "minimum per ascension/act: "
            f"records={config.min_records_per_ascension_act}, "
            f"unique_sources={config.min_unique_sources_per_ascension_act}"
        ),
        f"gate passed without override: {_yes_no(report.gate_passed_without_override)}",
        f"broad training allowed: {_yes_no(report.broad_training_allowed)}",
        f"training allowed: {_yes_no(report.training_allowed)}",
    ]
    _append_counter(lines, "observed ascensions", report.observed_ascension_counts)
    _append_counter(lines, "observed acts", report.observed_act_counts)
    _append_counter(lines, "distributions", report.distribution_counts)
    _append_counter(
        lines,
        "public-context statuses",
        report.public_context_status_counts,
    )
    _append_counter(
        lines,
        "structured outcome statuses",
        report.structured_outcome_status_counts,
    )
    lines.append("required cells:")
    for cell in report.cells:
        lines.append(
            "  "
            f"{cell.key}: records={cell.record_count}, "
            f"unique_sources={cell.unique_source_count}, "
            f"passed={_yes_no(cell.passed)}"
        )
    if report.override != TRAINING_GATE_OVERRIDE_NONE:
        lines.append(
            "override note: training may run only as a named "
            f"{report.override} diagnostic; it is not broad-training evidence"
        )
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _build_cell(
    config: TrainingScaleGateConfig,
    ascension: int,
    act: int,
    records: list[Any],
) -> TrainingGateCell:
    distribution_counts = Counter(
        _distribution_kind(record.source_metadata) for record in records
    )
    public_context_counts = Counter(record.public_context_status for record in records)
    outcome_counts = Counter(
        record.structured_battle_outcome_status for record in records
    )
    source_identities: list[tuple[Any, ...]] = []
    missing_source_identity_count = 0
    for record in records:
        source_identity = _source_identity(record)
        if source_identity is None:
            missing_source_identity_count += 1
        else:
            source_identities.append(source_identity)
    unique_sources = set(source_identities)
    problems: list[str] = []
    if len(records) < config.min_records_per_ascension_act:
        problems.append(
            f"record count {len(records)} is below "
            f"{config.min_records_per_ascension_act}"
        )
    if len(unique_sources) < config.min_unique_sources_per_ascension_act:
        problems.append(
            f"unique source count {len(unique_sources)} is below "
            f"{config.min_unique_sources_per_ascension_act}"
        )
    if missing_source_identity_count:
        problems.append(
            "missing stable source identity for "
            f"{missing_source_identity_count} records"
        )
    if config.require_public_context:
        non_available = {
            status: count
            for status, count in public_context_counts.items()
            if status != PUBLIC_CONTEXT_AVAILABLE
        }
        if non_available:
            problems.append(
                "public context is not available for all rows: "
                + _counter_summary(non_available)
            )
    if config.require_structured_outcomes:
        non_available = {
            status: count
            for status, count in outcome_counts.items()
            if status != BATTLE_RESOURCE_OUTCOME_AVAILABLE
        }
        if non_available:
            problems.append(
                "structured battle outcomes are not available for all rows: "
                + _counter_summary(non_available)
            )
    return TrainingGateCell(
        ascension=ascension,
        act=act,
        record_count=len(records),
        unique_source_count=len(unique_sources),
        distribution_counts=dict(sorted(distribution_counts.items())),
        public_context_status_counts=dict(sorted(public_context_counts.items())),
        structured_outcome_status_counts=dict(sorted(outcome_counts.items())),
        passed=not problems,
        problems=tuple(problems),
    )


def _source_identity(record: Any) -> tuple[Any, ...] | None:
    metadata = (
        record.source_metadata if isinstance(record.source_metadata, Mapping) else {}
    )
    checkpoint_id = _non_empty(metadata.get("source_checkpoint_id"))
    if checkpoint_id is not None:
        return ("source_checkpoint_id", checkpoint_id)
    run_id = _non_empty(metadata.get("source_run_id"))
    battle_index = _optional_int(metadata.get("source_battle_index"))
    if run_id is not None and battle_index is not None:
        return ("source_run_battle", run_id, battle_index)
    return None


def _distribution_kind(metadata: Any) -> str:
    if not isinstance(metadata, Mapping):
        return "unknown"
    value = metadata.get("distribution_kind", metadata.get("source_kind", "unknown"))
    return str(value or "unknown")


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _non_empty(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value


def _append_counter(lines: list[str], title: str, values: Mapping[Any, int]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values, key=lambda item: str(item)):
        lines.append(f"  {key}: {values[key]}")


def _counter_summary(values: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={values[key]}" for key in sorted(values))


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
