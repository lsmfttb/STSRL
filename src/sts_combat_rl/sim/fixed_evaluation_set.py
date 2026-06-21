"""Versioned fixed evaluation cohort selected from one natural battle-start pool.

A cohort is an evaluation artifact, not a resampled training batch.  It is
selected without replacement using structural strata from exactly one portable
pool.  Native checkpoint payloads are never serialized.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import random
from typing import Any, TextIO

from sts_combat_rl.sim.artifact_versioning import (
    ArtifactMigration,
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
)


FIXED_COHORT_FORMAT_VERSION = 1
"""Current schema version for the portable fixed-cohort artifact."""

FIXED_COHORT_MIGRATIONS: tuple[ArtifactMigration, ...] = ()
"""Sequential migrations; empty because version 1 is the first schema."""

DEFAULT_STRUCTURAL_STRATUM_FIELDS = (
    "ascension",
    "act",
    "room_type",
    "encounter_id",
)
"""The default structural stratum uses these four rule-defined metadata fields."""

FIXED_EVALUATION_SET_DISTRIBUTION_KIND = "fixed_evaluation_set"
"""Persistent distribution kind for all cohort records."""


def _stratum_key(metadata: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(
        metadata.get(field_name) for field_name in DEFAULT_STRUCTURAL_STRATUM_FIELDS
    )


@dataclass(frozen=True)
class FixedCohortSelectionConfig:
    """Deterministic configuration for selecting one cohort from a pool."""

    selection_seed: int
    stratum_quota: int = 1
    required_strata: tuple[tuple[Any, ...], ...] | None = None
    stratum_fields: tuple[str, ...] = DEFAULT_STRUCTURAL_STRATUM_FIELDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_seed": self.selection_seed,
            "stratum_quota": self.stratum_quota,
            "required_strata": (
                [list(s) for s in self.required_strata]
                if self.required_strata is not None
                else None
            ),
            "stratum_fields": list(self.stratum_fields),
        }


@dataclass(frozen=True)
class FixedCohortRecord:
    """One selected cohort entry retaining complete source-pool identity."""

    cohort_index: int
    source_pool_record_index: int
    source_checkpoint_id: str
    source_run_id: str
    source_seed: int
    source_battle_index: int
    structural_stratum: tuple[Any, ...]
    structural_metadata: dict[str, Any]
    source_controller_provenance: dict[str, Any]
    source_battle_controller_provenance: dict[str, Any]
    source_non_combat_controller_provenance: dict[str, Any]
    action_trace: tuple[dict[str, Any], ...]
    snapshot_observation: tuple[Any, ...] = ()
    snapshot_raw: dict[str, Any] = field(default_factory=dict)
    source_distribution_kind: str = "natural_run"
    checkpoint_information_regime: str = "full_simulator_state_oracle_like"
    public_context_status: str = "unavailable"


@dataclass(frozen=True)
class FixedCohort:
    """Immutable portable fixed evaluation cohort with deterministic identity."""

    source_pool_format_version: int
    source_pool_controller_provenance: dict[str, Any]
    selection_config: FixedCohortSelectionConfig
    format_version: int = FIXED_COHORT_FORMAT_VERSION
    records: list[FixedCohortRecord] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=FIXED_COHORT_FORMAT_VERSION,
            target_version=FIXED_COHORT_FORMAT_VERSION,
        ),
        compare=False,
    )

    @property
    def identity(self) -> str:
        """Content-addressed identity that changes with any input."""
        payload = json.dumps(
            {
                "source_pool_format_version": self.source_pool_format_version,
                "selection_config": self.selection_config.to_dict(),
                "record_checkpoint_ids": [r.source_checkpoint_id for r in self.records],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def unique_source_count(self) -> int:
        return len({r.source_checkpoint_id for r in self.records})


@dataclass(frozen=True)
class CohortCoverageReport:
    """Coverage report for one cohort selection pass."""

    pool_record_count: int
    selected_count: int
    unique_source_count: int
    observed_strata: Counter[tuple[Any, ...]] = field(default_factory=Counter)
    under_covered_strata: Counter[tuple[Any, ...]] = field(default_factory=Counter)
    required_but_absent_strata: list[tuple[Any, ...]] = field(default_factory=list)
    required_below_quota_strata: list[tuple[Any, ...]] = field(default_factory=list)
    malformed_records: list[int] = field(default_factory=list)
    quota_saturated_strata: Counter[tuple[Any, ...]] = field(default_factory=Counter)
    per_stratum_source_counts: dict[tuple[Any, ...], int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def coverage_ok(self) -> bool:
        return (
            not self.required_but_absent_strata
            and not self.required_below_quota_strata
            and not self.malformed_records
            and not self.problems
        )


def select_fixed_cohort(
    pool: NaturalBattleStartPool,
    *,
    selection_seed: int,
    stratum_quota: int = 1,
    required_strata: Iterable[tuple[Any, ...]] | None = None,
    stratum_fields: tuple[str, ...] = DEFAULT_STRUCTURAL_STRATUM_FIELDS,
) -> tuple[FixedCohort, CohortCoverageReport]:
    """Select without replacement from one pool using structural strata.

    Every selected record retains its complete source-pool identity.  Native
    checkpoint payloads are never carried into the cohort.
    """

    if stratum_quota < 1:
        raise ValueError("stratum_quota must be positive")
    if not pool.records:
        raise ValueError("cannot select a cohort from an empty pool")

    config = FixedCohortSelectionConfig(
        selection_seed=selection_seed,
        stratum_quota=stratum_quota,
        required_strata=(
            tuple(required_strata) if required_strata is not None else None
        ),
        stratum_fields=stratum_fields,
    )

    # Build per-stratum buckets using only the configured fields.
    buckets: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    malformed: list[int] = []
    for index, record in enumerate(pool.records):
        stratum = tuple(
            record.structural_metadata.get(field_name) for field_name in stratum_fields
        )
        # A stratum with any missing field is malformed for selection.
        if any(v is None for v in stratum):
            malformed.append(index)
        else:
            buckets[stratum].append(index)

    generator = random.Random(selection_seed)

    # Shuffle within each bucket for deterministic selection-in-order.
    for stratum in buckets:
        generator.shuffle(buckets[stratum])

    # Track per-stratum selection counts.
    selected_indices: set[int] = set()
    selected_by_stratum: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    selected_records: list[FixedCohortRecord] = []

    # Round-robin across strata until quotas are filled or pools exhausted.
    # Sort stratum keys for deterministic ordering.
    stratum_keys = sorted(buckets, key=repr)
    changed = True
    while changed:
        changed = False
        for stratum in stratum_keys:
            if len(selected_by_stratum.get(stratum, [])) >= stratum_quota:
                continue
            # Find next unselected record in this stratum.
            available = [idx for idx in buckets[stratum] if idx not in selected_indices]
            if available:
                chosen_idx = available[0]
                selected_indices.add(chosen_idx)
                selected_by_stratum[stratum].append(chosen_idx)
                record = pool.records[chosen_idx]
                selected_records.append(
                    FixedCohortRecord(
                        cohort_index=len(selected_records),
                        source_pool_record_index=chosen_idx,
                        source_checkpoint_id=record.source_checkpoint_id,
                        source_run_id=record.source_run_id,
                        source_seed=record.source_seed,
                        source_battle_index=record.source_battle_index,
                        structural_stratum=stratum,
                        structural_metadata=dict(record.structural_metadata),
                        source_controller_provenance=record.source_controller_provenance,
                        source_battle_controller_provenance=record.source_battle_controller_provenance,
                        source_non_combat_controller_provenance=record.source_non_combat_controller_provenance,
                        action_trace=record.action_trace,
                        snapshot_observation=record.snapshot_observation,
                        snapshot_raw=dict(record.snapshot_raw),
                        source_distribution_kind=record.distribution_kind,
                        checkpoint_information_regime=record.checkpoint_information_regime,
                        public_context_status=record.public_context_status,
                    )
                )
                changed = True

    # Build coverage counters.
    observed_strata: Counter[tuple[Any, ...]] = Counter()
    for stratum in buckets:
        observed_strata[stratum] = len(buckets[stratum])

    under_covered_strata: Counter[tuple[Any, ...]] = Counter()
    quota_saturated: Counter[tuple[Any, ...]] = Counter()
    for stratum, selected in selected_by_stratum.items():
        available = len(buckets.get(stratum, []))
        if len(selected) < stratum_quota and available < stratum_quota:
            under_covered_strata[stratum] = available
        if len(selected) >= stratum_quota:
            quota_saturated[stratum] = len(selected)

    problems: list[str] = []
    required_absent: list[tuple[Any, ...]] = []
    required_below_quota: list[tuple[Any, ...]] = []

    if config.required_strata is not None:
        for required in config.required_strata:
            required_tuple = tuple(required)
            if required_tuple not in buckets:
                required_absent.append(required_tuple)
                problems.append(
                    f"required stratum {required_tuple} is absent from the pool"
                )
            else:
                selected_count_for = len(selected_by_stratum.get(required_tuple, []))
                if selected_count_for < stratum_quota:
                    required_below_quota.append(required_tuple)
                    problems.append(
                        f"required stratum {required_tuple} selected "
                        f"{selected_count_for} / {stratum_quota} (below quota)"
                    )
    else:
        # When no required-strata configuration is supplied, report that
        # unobserved global strata are unknown rather than claiming complete
        # encounter coverage.
        pass

    if malformed:
        problems.insert(
            0,
            f"{len(malformed)} pool records have malformed (missing-field) "
            f"strata: {malformed[:10]}{'...' if len(malformed) > 10 else ''}",
        )

    # Unique source check.
    checkpoint_ids = [r.source_checkpoint_id for r in selected_records]
    if len(checkpoint_ids) != len(set(checkpoint_ids)):
        problems.append("selected cohort contains duplicate source checkpoints")

    coverage = CohortCoverageReport(
        pool_record_count=len(pool.records),
        selected_count=len(selected_records),
        unique_source_count=len(set(checkpoint_ids)),
        observed_strata=observed_strata,
        under_covered_strata=under_covered_strata,
        required_but_absent_strata=required_absent,
        required_below_quota_strata=required_below_quota,
        malformed_records=malformed,
        quota_saturated_strata=quota_saturated,
        per_stratum_source_counts={s: len(recs) for s, recs in buckets.items()},
        problems=problems,
    )

    cohort = FixedCohort(
        source_pool_format_version=pool.format_version,
        source_pool_controller_provenance=pool.source_controller_provenance,
        selection_config=config,
        records=selected_records,
        problems=problems,
    )

    return cohort, coverage


def dump_fixed_cohort_jsonl(
    cohort: FixedCohort,
    stream: TextIO,
) -> None:
    """Write current-schema fixed cohort to a portable JSONL stream."""

    cohort_problems = _fixed_cohort_problems(cohort)
    if cohort_problems:
        raise ValueError("invalid fixed cohort: " + "; ".join(cohort_problems))

    metadata: dict[str, Any] = {
        "format_version": FIXED_COHORT_FORMAT_VERSION,
        "source_pool_format_version": cohort.source_pool_format_version,
        "source_pool_controller_provenance": cohort.source_pool_controller_provenance,
        "selection_config": cohort.selection_config.to_dict(),
        "record_count": len(cohort.records),
        "migration_report": cohort.migration_report.to_dict(),
        "problems": list(cohort.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for record in cohort.records:
        _write_row(
            stream,
            {"type": "record", "record": _cohort_record_to_manifest(record)},
        )


def load_fixed_cohort_jsonl(stream: TextIO) -> FixedCohort:
    """Load and migrate a portable fixed-cohort artifact."""

    metadata: dict[str, Any] | None = None
    raw_records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        if row.get("type") == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
        elif row.get("type") == "record":
            raw_records.append(_require_mapping(row.get("record"), "record"))
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing fixed cohort metadata")

    migrated = migrate_artifact_document(
        metadata,
        raw_records,
        current_version=FIXED_COHORT_FORMAT_VERSION,
        migrations=FIXED_COHORT_MIGRATIONS,
        artifact_name="fixed cohort",
    )
    metadata = migrated.document.metadata

    selection_config_raw = _require_mapping(
        metadata.get("selection_config"), "selection_config"
    )
    required_raw = selection_config_raw.get("required_strata")
    required_strata: tuple[tuple[Any, ...], ...] | None = None
    if required_raw is not None:
        if not isinstance(required_raw, list):
            raise ValueError("required_strata must be a list")
        required_strata = tuple(
            tuple(entry) if isinstance(entry, list) else tuple()
            for entry in required_raw
        )

    selection_config = FixedCohortSelectionConfig(
        selection_seed=_require_non_negative_int(
            selection_config_raw.get("selection_seed"), "selection_seed"
        ),
        stratum_quota=_require_non_negative_int(
            selection_config_raw.get("stratum_quota", 1), "stratum_quota"
        ),
        required_strata=required_strata,
        stratum_fields=tuple(
            _require_string_list(
                selection_config_raw.get(
                    "stratum_fields", list(DEFAULT_STRUCTURAL_STRATUM_FIELDS)
                ),
                "stratum_fields",
            )
        ),
    )

    records = [
        _cohort_record_from_manifest(raw, label=f"record {index}")
        for index, raw in enumerate(migrated.document.records)
    ]
    if metadata.get("record_count") != len(records):
        raise ValueError("fixed cohort metadata record_count mismatch")

    problems = _require_string_list(metadata.get("problems", []), "problems")
    cohort = FixedCohort(
        source_pool_format_version=_require_non_negative_int(
            metadata.get("source_pool_format_version"), "source_pool_format_version"
        ),
        source_pool_controller_provenance=_require_mapping(
            metadata.get("source_pool_controller_provenance"),
            "source_pool_controller_provenance",
        ),
        selection_config=selection_config,
        records=records,
        problems=problems,
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="fixed cohort",
        ),
    )
    cohort_problems = _fixed_cohort_problems(cohort)
    if cohort_problems:
        raise ValueError("invalid fixed cohort: " + "; ".join(cohort_problems))
    return cohort


def format_cohort_coverage_report(report: CohortCoverageReport) -> str:
    """Format a cohort selection coverage report."""

    lines = ["Fixed cohort selection coverage"]
    lines.append(f"pool records: {report.pool_record_count}")
    lines.append(f"selected: {report.selected_count}")
    lines.append(f"unique source checkpoints: {report.unique_source_count}")
    lines.append("observed strata:")
    if report.observed_strata:
        for stratum, count in report.observed_strata.most_common():
            lines.append(f"  {_format_stratum(stratum)}: {count}")
    else:
        lines.append("  (none)")
    lines.append("under-covered strata (available < quota):")
    if report.under_covered_strata:
        for stratum, available in report.under_covered_strata.most_common():
            lines.append(f"  {_format_stratum(stratum)}: {available} available")
    else:
        lines.append("  (none)")
    lines.append("quota-saturated strata:")
    if report.quota_saturated_strata:
        for stratum, count in report.quota_saturated_strata.most_common():
            lines.append(f"  {_format_stratum(stratum)}: {count} selected")
    else:
        lines.append("  (none)")
    lines.append("required but absent strata:")
    if report.required_but_absent_strata:
        for stratum in report.required_but_absent_strata:
            lines.append(f"  - {_format_stratum(stratum)}")
    else:
        lines.append("  (none)")
    lines.append("required strata below quota:")
    if report.required_below_quota_strata:
        for stratum in report.required_below_quota_strata:
            lines.append(f"  - {_format_stratum(stratum)}")
    else:
        lines.append("  (none)")
    if not report.required_but_absent_strata and not report.required_below_quota_strata:
        lines.append(
            "  (unobserved global strata are unknown — no required "
            "strata were configured)"
        )
    lines.append("malformed records (missing structural fields):")
    if report.malformed_records:
        lines.append(f"  indices: {report.malformed_records}")
    else:
        lines.append("  (none)")
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {p}" for p in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _cohort_record_to_manifest(record: FixedCohortRecord) -> dict[str, Any]:
    return {
        "cohort_index": record.cohort_index,
        "source_pool_record_index": record.source_pool_record_index,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_run_id": record.source_run_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "structural_stratum": list(record.structural_stratum),
        "structural_metadata": _json_safe_mapping(record.structural_metadata),
        "source_controller_provenance": record.source_controller_provenance,
        "source_battle_controller_provenance": (
            record.source_battle_controller_provenance
        ),
        "source_non_combat_controller_provenance": (
            record.source_non_combat_controller_provenance
        ),
        "action_trace": [
            _json_safe_mapping(identity) for identity in record.action_trace
        ],
        "snapshot_observation": list(record.snapshot_observation),
        "snapshot_raw": _json_safe_mapping(record.snapshot_raw),
        "source_distribution_kind": record.source_distribution_kind,
        "checkpoint_information_regime": record.checkpoint_information_regime,
        "public_context_status": record.public_context_status,
    }


def _cohort_record_from_manifest(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> FixedCohortRecord:
    stratum_raw = raw.get("structural_stratum")
    if not isinstance(stratum_raw, list):
        raise ValueError(f"{label} structural_stratum must be a list")
    structural_stratum = tuple(stratum_raw)

    action_trace_raw = raw.get("action_trace")
    if not isinstance(action_trace_raw, list):
        raise ValueError(f"{label} action_trace must be a list")
    action_trace = tuple(
        _require_mapping(entry, f"{label} action trace {i}")
        for i, entry in enumerate(action_trace_raw)
    )

    observation_raw = raw.get("snapshot_observation")
    if not isinstance(observation_raw, list):
        raise ValueError(f"{label} snapshot_observation must be a list")
    snapshot_observation = tuple(observation_raw)

    snapshot_raw_raw = raw.get("snapshot_raw")
    snapshot_raw = (
        _require_mapping(snapshot_raw_raw, f"{label} snapshot_raw")
        if snapshot_raw_raw is not None
        else {}
    )

    source_distribution_kind = raw.get("source_distribution_kind")
    if not isinstance(source_distribution_kind, str) or not source_distribution_kind:
        raise ValueError(f"{label} source_distribution_kind must be a non-empty string")

    checkpoint_information_regime = raw.get("checkpoint_information_regime")
    if (
        not isinstance(checkpoint_information_regime, str)
        or not checkpoint_information_regime
    ):
        raise ValueError(
            f"{label} checkpoint_information_regime must be a non-empty string"
        )

    public_context_status = raw.get("public_context_status")
    if not isinstance(public_context_status, str) or not public_context_status:
        raise ValueError(f"{label} public_context_status must be a non-empty string")

    return FixedCohortRecord(
        cohort_index=_require_non_negative_int(
            raw.get("cohort_index"), f"{label} cohort_index"
        ),
        source_pool_record_index=_require_non_negative_int(
            raw.get("source_pool_record_index"), f"{label} source_pool_record_index"
        ),
        source_checkpoint_id=_require_non_empty_string(
            raw.get("source_checkpoint_id"), f"{label} source_checkpoint_id"
        ),
        source_run_id=_require_non_empty_string(
            raw.get("source_run_id"), f"{label} source_run_id"
        ),
        source_seed=_require_seed(raw.get("source_seed"), f"{label} source_seed"),
        source_battle_index=_require_non_negative_int(
            raw.get("source_battle_index"), f"{label} source_battle_index"
        ),
        structural_stratum=structural_stratum,
        structural_metadata=_require_mapping(
            raw.get("structural_metadata"), f"{label} structural_metadata"
        ),
        source_controller_provenance=_require_mapping(
            raw.get("source_controller_provenance"),
            f"{label} source_controller_provenance",
        ),
        source_battle_controller_provenance=_require_mapping(
            raw.get("source_battle_controller_provenance"),
            f"{label} source_battle_controller_provenance",
        ),
        source_non_combat_controller_provenance=_require_mapping(
            raw.get("source_non_combat_controller_provenance"),
            f"{label} source_non_combat_controller_provenance",
        ),
        action_trace=action_trace,
        snapshot_observation=snapshot_observation,
        snapshot_raw=snapshot_raw,
        source_distribution_kind=source_distribution_kind,
        checkpoint_information_regime=checkpoint_information_regime,
        public_context_status=public_context_status,
    )


def _fixed_cohort_problems(cohort: FixedCohort) -> list[str]:
    problems: list[str] = list(cohort.problems)
    if cohort.format_version != FIXED_COHORT_FORMAT_VERSION:
        problems.append("cohort has an unsupported format version")
    checkpoint_ids: set[str] = set()
    for index, record in enumerate(cohort.records):
        if record.cohort_index != index:
            problems.append(f"cohort record {index} index is not contiguous")
        if record.source_checkpoint_id in checkpoint_ids:
            problems.append(
                f"duplicate source checkpoint id {record.source_checkpoint_id}"
            )
        checkpoint_ids.add(record.source_checkpoint_id)
        if record.source_distribution_kind != "natural_run":
            problems.append(
                f"record {index} source_distribution_kind must be natural_run: "
                f"{record.source_distribution_kind}"
            )
    return list(dict.fromkeys(problems))


def _format_stratum(stratum: tuple[Any, ...]) -> str:
    return "/".join(str(v) for v in stratum)


# ── JSONL helpers (match pool pattern) ──────────────────────────────────────


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    stream.write(json.dumps(row, sort_keys=True, allow_nan=False))
    stream.write("\n")


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"artifact value is not JSON-safe: {type(value).__name__}")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _require_seed(value: Any, label: str) -> int:
    return _require_non_negative_int(value, label)


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)
