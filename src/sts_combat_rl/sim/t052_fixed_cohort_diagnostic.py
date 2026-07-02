"""T052 fixed diagnostic cohort extraction and retention manifests.

The T052 cohort is derived from retained T051 natural source pools.  The input
pools are large, so extraction streams source records and keeps only the
Boss/later-act candidates needed for the immutable fixed-evaluation cohort.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, TextIO

from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    CHECKPOINT_INFORMATION_REGIME,
    BattleStartCheckpointRecord,
    record_from_manifest,
    sha256_file,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    DEFAULT_STRUCTURAL_STRATUM_FIELDS,
    FIXED_COHORT_FORMAT_VERSION,
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
)


T052_COHORT_SUMMARY_SCHEMA_ID = "t052-t051-boss-later-act-fixed-cohort-summary-v1"
T052_COHORT_SUMMARY_FORMAT_VERSION = 1
T052_RETENTION_MANIFEST_SCHEMA_ID = "t052-retention-manifest-v1"
T052_RETENTION_MANIFEST_FORMAT_VERSION = 1

T052_SOURCE_ARM_ROLES = ("baseline", "post_search", "root_prior")
T052_LATER_ACT_SOURCE_ARM_ROLES = frozenset({"post_search", "root_prior"})
T052_STRUCTURAL_STRATUM_FIELDS = (
    *DEFAULT_STRUCTURAL_STRATUM_FIELDS,
    "t051_source_arm_label",
)
T052_EVIDENCE_BOUNDARY = (
    "T052 fixed-cohort diagnostic only; all comparison arms remain "
    "full_simulator_state_oracle_like, and this is not normal-information, "
    "live-game, broad-training, natural A20 performance, controller-promotion, "
    "or final-agent evidence"
)


@dataclass(frozen=True)
class T052SourceArmSpec:
    """One retained T051 source-pool input."""

    role: str
    label: str
    pool_path: Path
    expected_sha256: str


@dataclass(frozen=True)
class T052VerifiedArtifact:
    """A hash-verified artifact consumed or referenced by T052."""

    role: str
    path: Path
    expected_sha256: str
    actual_sha256: str
    byte_count: int

    @property
    def verified(self) -> bool:
        return self.expected_sha256.lower() == self.actual_sha256.lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "path": str(self.path),
            "expected_sha256": self.expected_sha256.lower(),
            "actual_sha256": self.actual_sha256.lower(),
            "sha256_verified": self.verified,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class T052ScannedSourceArm:
    """Streaming selection summary for one source arm."""

    role: str
    label: str
    pool_path: Path
    pool_sha256: str
    pool_format_version: int
    source_run_count: int
    terminal_run_count: int
    truncated_run_count: int
    record_count: int
    act1_boss_available_count: int
    later_act_available_count: int
    selected_count: int
    selected_reason_counts: dict[str, int]
    act_counts: dict[str, int]
    room_type_counts: dict[str, int]
    encounter_id_counts: dict[str, int]
    public_context_status_counts: dict[str, int]
    structured_outcome_status_counts: dict[str, int]
    source_controller_provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "label": self.label,
            "pool_path": str(self.pool_path),
            "pool_sha256": self.pool_sha256,
            "pool_format_version": self.pool_format_version,
            "source_run_count": self.source_run_count,
            "terminal_run_count": self.terminal_run_count,
            "truncated_run_count": self.truncated_run_count,
            "record_count": self.record_count,
            "act1_boss_available_count": self.act1_boss_available_count,
            "later_act_available_count": self.later_act_available_count,
            "selected_count": self.selected_count,
            "selected_reason_counts": dict(self.selected_reason_counts),
            "act_counts": dict(self.act_counts),
            "room_type_counts": dict(self.room_type_counts),
            "encounter_id_counts": dict(self.encounter_id_counts),
            "public_context_status_counts": dict(self.public_context_status_counts),
            "structured_outcome_status_counts": dict(
                self.structured_outcome_status_counts
            ),
            "source_controller_provenance": self.source_controller_provenance,
        }


@dataclass(frozen=True)
class T052CohortExtractionResult:
    """In-memory result of a T052 extraction pass."""

    cohort: FixedCohort
    source_arms: tuple[T052ScannedSourceArm, ...]
    verified_artifacts: tuple[T052VerifiedArtifact, ...]
    duplicate_omissions: tuple[dict[str, Any], ...] = ()
    problems: tuple[str, ...] = ()

    @property
    def command_passed(self) -> bool:
        return not self.problems and bool(self.cohort.records)


@dataclass(frozen=True)
class T052RetentionArtifactSpec:
    """One generated artifact to include in the retention manifest."""

    role: str
    path: Path
    schema_id: str


@dataclass(frozen=True)
class T052RetentionCommandSpec:
    """A reproduced command line recorded in the retention manifest."""

    role: str
    command: str


@dataclass(frozen=True)
class T052RetentionStageSpec:
    """Stage-level runtime provenance for T052 retention."""

    role: str
    workers: int
    shards: int
    record_range: str
    wall_clock_seconds: float


@dataclass(frozen=True)
class _CandidateRecord:
    record: BattleStartCheckpointRecord
    source_arm_role: str
    source_arm_label: str
    source_pool_sha256: str
    source_pool_path: Path
    selection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class _ScanAccumulator:
    metadata: dict[str, Any]
    pool_sha256: str
    selected: tuple[_CandidateRecord, ...]
    duplicate_omissions: tuple[dict[str, Any], ...]
    counters: dict[str, Counter[str]]
    record_count: int


def verify_t052_artifact(
    *,
    role: str,
    path: Path,
    expected_sha256: str,
) -> T052VerifiedArtifact:
    """Verify a T052 input artifact identity before it is consumed."""

    normalized_expected = _normalize_sha256(expected_sha256, f"{role} expected sha256")
    actual = sha256_file(path)
    result = T052VerifiedArtifact(
        role=role,
        path=path,
        expected_sha256=normalized_expected,
        actual_sha256=actual,
        byte_count=path.stat().st_size,
    )
    if not result.verified:
        raise ValueError(
            f"{role} sha256 mismatch: expected {normalized_expected}, got {actual}"
        )
    return result


def build_t052_t051_boss_later_act_fixed_cohort(
    *,
    source_arm_specs: Sequence[T052SourceArmSpec],
    verified_artifacts: Sequence[T052VerifiedArtifact],
) -> T052CohortExtractionResult:
    """Build the immutable T052 cohort by streaming retained T051 pools."""

    _validate_source_arm_specs(source_arm_specs)
    selected: list[_CandidateRecord] = []
    duplicate_omissions: list[dict[str, Any]] = []
    scanned_arms: list[T052ScannedSourceArm] = []
    seen_checkpoints: dict[str, _CandidateRecord] = {}

    for spec in source_arm_specs:
        scan = _scan_source_arm(
            spec,
            seen_checkpoints=seen_checkpoints,
        )
        selected.extend(scan.selected)
        duplicate_omissions.extend(scan.duplicate_omissions)
        scanned_arms.append(
            _scanned_arm_from_accumulator(
                spec=spec,
                scan=scan,
            )
        )

    if not selected:
        raise ValueError("T052 extraction selected no Boss or later-act starts")

    cohort_records = [
        _fixed_record_from_candidate(candidate, cohort_index=index)
        for index, candidate in enumerate(selected)
    ]
    cohort = FixedCohort(
        source_pool_format_version=BATTLE_START_POOL_FORMAT_VERSION,
        source_pool_controller_provenance=_source_pool_controller_provenance(
            source_arms=scanned_arms,
            verified_artifacts=verified_artifacts,
            duplicate_omissions=duplicate_omissions,
        ),
        selection_config=FixedCohortSelectionConfig(
            selection_seed=0,
            stratum_quota=1,
            required_strata=None,
            stratum_fields=T052_STRUCTURAL_STRATUM_FIELDS,
        ),
        records=cohort_records,
        problems=[],
    )
    return T052CohortExtractionResult(
        cohort=cohort,
        source_arms=tuple(scanned_arms),
        verified_artifacts=tuple(verified_artifacts),
        duplicate_omissions=tuple(duplicate_omissions),
    )


def build_t052_cohort_summary_payload(
    result: T052CohortExtractionResult,
    *,
    cohort_path: Path | None = None,
) -> dict[str, Any]:
    """Build a compact JSON summary for PR evidence."""

    cohort = result.cohort
    metadata_counts = _cohort_metadata_counts(cohort.records)
    generated_artifacts: list[dict[str, Any]] = []
    if cohort_path is not None and cohort_path.exists():
        generated_artifacts.append(_artifact_identity("fixed_cohort", cohort_path))
    return {
        "schema_id": T052_COHORT_SUMMARY_SCHEMA_ID,
        "format_version": T052_COHORT_SUMMARY_FORMAT_VERSION,
        "task_id": "T052",
        "evidence_boundary": T052_EVIDENCE_BOUNDARY,
        "command_passed": result.command_passed,
        "cohort": {
            "format_version": FIXED_COHORT_FORMAT_VERSION,
            "identity": cohort.identity,
            "record_count": len(cohort.records),
            "unique_source_count": cohort.unique_source_count,
            "selection_rule": (
                "all Act-1 Boss starts from all T051 source arms plus all "
                "Act-2+ starts from post_search and root_prior arms; exact "
                "duplicate source_checkpoint_id values are omitted after the "
                "first deterministic occurrence"
            ),
            "stratum_fields": list(T052_STRUCTURAL_STRATUM_FIELDS),
        },
        "source_arms": [arm.to_dict() for arm in result.source_arms],
        "input_artifacts": [
            artifact.to_dict() for artifact in result.verified_artifacts
        ],
        "generated_artifacts": generated_artifacts,
        "duplicate_omissions": list(result.duplicate_omissions),
        "counts": {
            "by_source_arm_label": metadata_counts["source_arm_label"],
            "by_source_arm_role": metadata_counts["source_arm_role"],
            "by_act": metadata_counts["act"],
            "by_room_type": metadata_counts["room_type"],
            "by_encounter_id": metadata_counts["encounter_id"],
            "by_selection_reason": metadata_counts["selection_reason"],
            "public_context_status": metadata_counts["public_context_status"],
            "structured_outcome_status": metadata_counts["structured_outcome_status"],
            "information_regime": metadata_counts["information_regime"],
        },
        "problems": list(result.problems),
    }


def dump_t052_cohort_summary_json(
    payload: Mapping[str, Any],
    stream: TextIO,
) -> None:
    """Write the T052 summary JSON artifact."""

    json.dump(_json_safe_mapping(payload), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_t052_cohort_summary(payload: Mapping[str, Any]) -> str:
    """Format the T052 extraction summary for stderr and PR evidence."""

    cohort = _mapping(payload.get("cohort"))
    counts = _mapping(payload.get("counts"))
    lines = [
        "T052 T051 Boss/later-act fixed cohort extraction",
        f"command passed: {'yes' if payload.get('command_passed') else 'no'}",
        f"cohort identity: {cohort.get('identity', '(missing)')}",
        f"cohort records: {cohort.get('record_count', 0)}",
        f"unique source checkpoints: {cohort.get('unique_source_count', 0)}",
        "selected by source arm:",
    ]
    _append_counts(lines, _mapping(counts.get("by_source_arm_label")))
    lines.append("selected by act:")
    _append_counts(lines, _mapping(counts.get("by_act")))
    lines.append("selected by room type:")
    _append_counts(lines, _mapping(counts.get("by_room_type")))
    lines.append("selection reasons:")
    _append_counts(lines, _mapping(counts.get("by_selection_reason")))
    duplicate_count = len(_sequence(payload.get("duplicate_omissions")))
    lines.append(f"duplicate source-checkpoint omissions: {duplicate_count}")
    problems = _sequence(payload.get("problems"))
    lines.append("problems:")
    if problems:
        lines.extend(f"  - {problem}" for problem in problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def build_t052_retention_manifest_payload(
    *,
    artifact_specs: Sequence[T052RetentionArtifactSpec],
    command_specs: Sequence[T052RetentionCommandSpec] = (),
    stage_specs: Sequence[T052RetentionStageSpec] = (),
    note_items: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Build a lightweight T052 retention manifest from generated files."""

    if not artifact_specs:
        raise ValueError("T052 retention manifest requires at least one artifact")
    return {
        "schema_id": T052_RETENTION_MANIFEST_SCHEMA_ID,
        "format_version": T052_RETENTION_MANIFEST_FORMAT_VERSION,
        "task_id": "T052",
        "evidence_boundary": T052_EVIDENCE_BOUNDARY,
        "retention_reason": (
            "preserve T052 fixed diagnostic cohort, comparison evidence, logs, "
            "and summaries for maintainer review and possible follow-up task input"
        ),
        "downstream_consumers": [
            "main maintainer review of T052",
            "the exactly one follow-up task recommended in the T052 PR report",
        ],
        "deletion_conditions": (
            "raw local artifacts may be deleted after T052 review is complete and "
            "the maintainer has either merged the PR or recorded any retained "
            "artifact identities needed by the next task"
        ),
        "artifacts": [_retained_artifact_payload(spec) for spec in artifact_specs],
        "commands": [
            {"role": spec.role, "command": spec.command} for spec in command_specs
        ],
        "runtime_stages": [
            {
                "role": spec.role,
                "workers": spec.workers,
                "shards": spec.shards,
                "record_range": spec.record_range,
                "wall_clock_seconds": spec.wall_clock_seconds,
            }
            for spec in stage_specs
        ],
        "notes": {str(key): str(value) for key, value in note_items},
    }


def dump_t052_retention_manifest_json(
    payload: Mapping[str, Any],
    stream: TextIO,
) -> None:
    """Write the T052 retention manifest JSON artifact."""

    json.dump(_json_safe_mapping(payload), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_t052_retention_manifest(payload: Mapping[str, Any]) -> str:
    """Format the T052 retention manifest for stderr."""

    artifacts = _sequence(payload.get("artifacts"))
    stages = _sequence(payload.get("runtime_stages"))
    lines = [
        "T052 retention manifest",
        f"artifact count: {len(artifacts)}",
        f"runtime stage count: {len(stages)}",
        "artifacts:",
    ]
    for artifact in artifacts:
        mapping = _mapping(artifact)
        lines.append(
            "  "
            + str(mapping.get("role", "(missing)"))
            + ": sha256="
            + str(mapping.get("sha256", "(missing)"))
            + ", bytes="
            + str(mapping.get("byte_count", "(missing)"))
        )
    if not artifacts:
        lines.append("  (none)")
    return "\n".join(lines)


def _validate_source_arm_specs(specs: Sequence[T052SourceArmSpec]) -> None:
    roles = [spec.role for spec in specs]
    if sorted(roles) != sorted(T052_SOURCE_ARM_ROLES):
        expected = ", ".join(T052_SOURCE_ARM_ROLES)
        raise ValueError(f"T052 source arms must have roles: {expected}")
    if len({spec.label for spec in specs}) != len(specs):
        raise ValueError("T052 source arm labels must be unique")
    for spec in specs:
        if not spec.label:
            raise ValueError("T052 source arm label must be non-empty")
        _normalize_sha256(spec.expected_sha256, f"{spec.label} expected sha256")


def _scan_source_arm(
    spec: T052SourceArmSpec,
    *,
    seen_checkpoints: dict[str, _CandidateRecord],
) -> _ScanAccumulator:
    verified = verify_t052_artifact(
        role=f"{spec.role}_merged_pool",
        path=spec.pool_path,
        expected_sha256=spec.expected_sha256,
    )
    metadata: dict[str, Any] | None = None
    selected: list[_CandidateRecord] = []
    duplicate_omissions: list[dict[str, Any]] = []
    counters = {
        "act": Counter[str](),
        "room_type": Counter[str](),
        "encounter_id": Counter[str](),
        "public_context_status": Counter[str](),
        "structured_outcome_status": Counter[str](),
        "selected_reason": Counter[str](),
    }
    act1_boss_available = 0
    later_act_available = 0
    record_count = 0
    with spec.pool_path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            row = _json_row(raw_line, line_number=line_number, path=spec.pool_path)
            row_type = row.get("type")
            if row_type == "metadata":
                if metadata is not None:
                    raise ValueError(f"{spec.pool_path}: duplicate metadata")
                metadata = _require_mapping(row.get("metadata"), "metadata")
                _validate_pool_metadata(metadata, spec=spec)
                continue
            if row_type != "record":
                raise ValueError(
                    f"{spec.pool_path} line {line_number}: unknown row type"
                )
            if metadata is None:
                raise ValueError(
                    f"{spec.pool_path} line {line_number}: record before metadata"
                )
            record = record_from_manifest(
                _require_mapping(row.get("record"), "record"),
                label=f"{spec.label} record {record_count}",
            )
            if record.record_index != record_count:
                raise ValueError(
                    f"{spec.label} record indices are not contiguous at {record_count}"
                )
            record_count += 1
            _update_source_counters(counters, record)
            if _is_act1_boss(record):
                act1_boss_available += 1
            if _is_later_act(record):
                later_act_available += 1
            reasons = _selection_reasons(spec.role, record)
            if not reasons:
                continue
            candidate = _CandidateRecord(
                record=record,
                source_arm_role=spec.role,
                source_arm_label=spec.label,
                source_pool_sha256=verified.actual_sha256,
                source_pool_path=spec.pool_path,
                selection_reasons=tuple(reasons),
            )
            existing = seen_checkpoints.get(record.source_checkpoint_id)
            if existing is not None:
                duplicate_omissions.append(
                    {
                        "reason": "duplicate_source_checkpoint_id",
                        "source_checkpoint_id": record.source_checkpoint_id,
                        "omitted_source_arm_role": spec.role,
                        "omitted_source_arm_label": spec.label,
                        "kept_source_arm_role": existing.source_arm_role,
                        "kept_source_arm_label": existing.source_arm_label,
                    }
                )
                continue
            for reason in reasons:
                counters["selected_reason"][reason] += 1
            seen_checkpoints[record.source_checkpoint_id] = candidate
            selected.append(candidate)
    if metadata is None:
        raise ValueError(f"{spec.pool_path}: missing battle-start pool metadata")
    if metadata.get("record_count") != record_count:
        raise ValueError(f"{spec.label}: metadata record_count mismatch")
    counters["act1_boss_available"] = Counter({"count": act1_boss_available})
    counters["later_act_available"] = Counter({"count": later_act_available})
    return _ScanAccumulator(
        metadata=metadata,
        pool_sha256=verified.actual_sha256,
        selected=tuple(selected),
        duplicate_omissions=tuple(duplicate_omissions),
        counters=counters,
        record_count=record_count,
    )


def _scanned_arm_from_accumulator(
    *,
    spec: T052SourceArmSpec,
    scan: _ScanAccumulator,
) -> T052ScannedSourceArm:
    return T052ScannedSourceArm(
        role=spec.role,
        label=spec.label,
        pool_path=spec.pool_path,
        pool_sha256=scan.pool_sha256,
        pool_format_version=int(scan.metadata["format_version"]),
        source_run_count=int(scan.metadata["source_run_count"]),
        terminal_run_count=int(scan.metadata["terminal_run_count"]),
        truncated_run_count=int(scan.metadata["truncated_run_count"]),
        record_count=scan.record_count,
        act1_boss_available_count=scan.counters["act1_boss_available"]["count"],
        later_act_available_count=scan.counters["later_act_available"]["count"],
        selected_count=len(scan.selected),
        selected_reason_counts=_counter_dict(scan.counters["selected_reason"]),
        act_counts=_counter_dict(scan.counters["act"]),
        room_type_counts=_counter_dict(scan.counters["room_type"]),
        encounter_id_counts=_counter_dict(scan.counters["encounter_id"]),
        public_context_status_counts=_counter_dict(
            scan.counters["public_context_status"]
        ),
        structured_outcome_status_counts=_counter_dict(
            scan.counters["structured_outcome_status"]
        ),
        source_controller_provenance=_require_mapping(
            scan.metadata.get("source_controller_provenance"),
            "source_controller_provenance",
        ),
    )


def _fixed_record_from_candidate(
    candidate: _CandidateRecord,
    *,
    cohort_index: int,
) -> FixedCohortRecord:
    record = candidate.record
    metadata = dict(record.structural_metadata)
    metadata.update(
        {
            "t051_source_arm_role": candidate.source_arm_role,
            "t051_source_arm_label": candidate.source_arm_label,
            "t051_source_pool_sha256": candidate.source_pool_sha256,
            "t051_source_pool_path": str(candidate.source_pool_path),
            "t052_selection_reasons": list(candidate.selection_reasons),
            "t051_battle_completed": record.battle_completed,
            "t051_battle_outcome": record.battle_outcome,
            "t051_completed_battle_resource_outcome_status": (
                record.completed_battle_resource_outcome_status
            ),
        }
    )
    stratum = tuple(metadata.get(field) for field in T052_STRUCTURAL_STRATUM_FIELDS)
    return FixedCohortRecord(
        cohort_index=cohort_index,
        source_pool_record_index=record.record_index,
        source_checkpoint_id=record.source_checkpoint_id,
        source_run_id=record.source_run_id,
        source_seed=record.source_seed,
        source_battle_index=record.source_battle_index,
        structural_stratum=stratum,
        structural_metadata=metadata,
        source_controller_provenance=record.source_controller_provenance,
        source_battle_controller_provenance=record.source_battle_controller_provenance,
        source_non_combat_controller_provenance=(
            record.source_non_combat_controller_provenance
        ),
        action_trace=record.action_trace,
        assistance_history=record.assistance_history,
        snapshot_observation=record.snapshot_observation,
        snapshot_raw=dict(record.snapshot_raw),
        source_distribution_kind=record.distribution_kind,
        checkpoint_information_regime=record.checkpoint_information_regime,
        public_context_status=record.public_context_status,
        public_run_context=dict(record.public_run_context),
    )


def _selection_reasons(role: str, record: BattleStartCheckpointRecord) -> list[str]:
    reasons: list[str] = []
    if _is_act1_boss(record):
        reasons.append("act1_boss")
    if role in T052_LATER_ACT_SOURCE_ARM_ROLES and _is_later_act(record):
        reasons.append("act2_plus")
    return reasons


def _is_act1_boss(record: BattleStartCheckpointRecord) -> bool:
    return _optional_int(record.structural_metadata.get("act")) == 1 and (
        "boss" in str(record.structural_metadata.get("room_type", "")).lower()
    )


def _is_later_act(record: BattleStartCheckpointRecord) -> bool:
    act = _optional_int(record.structural_metadata.get("act"))
    return act is not None and act > 1


def _validate_pool_metadata(
    metadata: Mapping[str, Any], *, spec: T052SourceArmSpec
) -> None:
    if metadata.get("format_version") != BATTLE_START_POOL_FORMAT_VERSION:
        raise ValueError(
            f"{spec.label}: source pool must be current format "
            f"{BATTLE_START_POOL_FORMAT_VERSION}"
        )
    for field_name in (
        "source_run_count",
        "terminal_run_count",
        "truncated_run_count",
        "record_count",
    ):
        value = metadata.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"{spec.label}: metadata {field_name} must be non-negative"
            )
    if int(metadata["terminal_run_count"]) + int(
        metadata["truncated_run_count"]
    ) != int(metadata["source_run_count"]):
        raise ValueError(f"{spec.label}: terminal/truncated source-run counts mismatch")
    _require_mapping(
        metadata.get("source_controller_provenance"),
        f"{spec.label} source_controller_provenance",
    )


def _source_pool_controller_provenance(
    *,
    source_arms: Sequence[T052ScannedSourceArm],
    verified_artifacts: Sequence[T052VerifiedArtifact],
    duplicate_omissions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "t052_t051_boss_later_act_fixed_cohort_extraction",
        "name": "t052_t051_boss_later_act_fixed_cohort",
        "config": {
            "task_id": "T052",
            "selection_rule": (
                "all Act-1 Boss starts from all source arms and all Act-2+ "
                "starts from post_search/root_prior source arms"
            ),
            "dedupe_rule": "omit exact duplicate source_checkpoint_id after first input-order occurrence",
            "input_order": [arm.label for arm in source_arms],
            "source_arms": [arm.to_dict() for arm in source_arms],
            "verified_artifacts": [
                artifact.to_dict() for artifact in verified_artifacts
            ],
            "duplicate_omission_count": len(duplicate_omissions),
        },
    }


def _cohort_metadata_counts(
    records: Sequence[FixedCohortRecord],
) -> dict[str, dict[str, int]]:
    counters = {
        "source_arm_label": Counter[str](),
        "source_arm_role": Counter[str](),
        "act": Counter[str](),
        "room_type": Counter[str](),
        "encounter_id": Counter[str](),
        "selection_reason": Counter[str](),
        "public_context_status": Counter[str](),
        "structured_outcome_status": Counter[str](),
        "information_regime": Counter[str](),
    }
    for record in records:
        metadata = record.structural_metadata
        counters["source_arm_label"][
            _value_key(metadata.get("t051_source_arm_label"))
        ] += 1
        counters["source_arm_role"][
            _value_key(metadata.get("t051_source_arm_role"))
        ] += 1
        counters["act"][_value_key(metadata.get("act"))] += 1
        counters["room_type"][_value_key(metadata.get("room_type"))] += 1
        counters["encounter_id"][_value_key(metadata.get("encounter_id"))] += 1
        reasons = metadata.get("t052_selection_reasons")
        if isinstance(reasons, Sequence) and not isinstance(reasons, (str, bytes)):
            for reason in reasons:
                counters["selection_reason"][_value_key(reason)] += 1
        counters["public_context_status"][record.public_context_status] += 1
        counters["structured_outcome_status"][
            _value_key(metadata.get("t051_completed_battle_resource_outcome_status"))
        ] += 1
        counters["information_regime"][
            record.checkpoint_information_regime or CHECKPOINT_INFORMATION_REGIME
        ] += 1
    return {key: _counter_dict(counter) for key, counter in counters.items()}


def _retained_artifact_payload(spec: T052RetentionArtifactSpec) -> dict[str, Any]:
    payload = _artifact_identity(spec.role, spec.path)
    payload["schema_id"] = spec.schema_id
    payload.update(_artifact_content_summary(spec.path))
    return payload


def _artifact_identity(role: str, path: Path) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
    }


def _artifact_content_summary(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        nonempty = 0
        metadata_rows = 0
        result_rows = 0
        with path.open("r", encoding="utf-8") as stream:
            for raw_line in stream:
                if not raw_line.strip():
                    continue
                nonempty += 1
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, Mapping):
                    row_type = row.get("type")
                    if row_type == "metadata":
                        metadata_rows += 1
                    elif row_type is not None:
                        result_rows += 1
        return {
            "jsonl_nonempty_line_count": nonempty,
            "jsonl_metadata_row_count": metadata_rows,
            "jsonl_nonmetadata_row_count": result_rows,
        }
    if suffix == ".json":
        try:
            with path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, Mapping):
            return {}
        summary: dict[str, Any] = {}
        schema_id = data.get("schema_id")
        if isinstance(schema_id, str):
            summary["detected_schema_id"] = schema_id
        for field_name in (
            "record_count",
            "battle_comparison_count",
            "cohort_record_count",
        ):
            value = data.get(field_name)
            if isinstance(value, int) and not isinstance(value, bool):
                summary[field_name] = value
        cohort = data.get("cohort")
        if isinstance(cohort, Mapping):
            record_count = cohort.get("record_count")
            if isinstance(record_count, int) and not isinstance(record_count, bool):
                summary["cohort_record_count"] = record_count
        return summary
    return {}


def _update_source_counters(
    counters: dict[str, Counter[str]],
    record: BattleStartCheckpointRecord,
) -> None:
    metadata = record.structural_metadata
    counters["act"][_value_key(metadata.get("act"))] += 1
    counters["room_type"][_value_key(metadata.get("room_type"))] += 1
    counters["encounter_id"][_value_key(metadata.get("encounter_id"))] += 1
    counters["public_context_status"][record.public_context_status] += 1
    counters["structured_outcome_status"][
        record.completed_battle_resource_outcome_status
    ] += 1


def _json_row(raw_line: str, *, line_number: int, path: Path) -> dict[str, Any]:
    try:
        row = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} line {line_number}: invalid JSON") from exc
    if not isinstance(row, Mapping):
        raise ValueError(f"{path} line {line_number}: row must be an object")
    return {str(key): value for key, value in row.items()}


def _normalize_sha256(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        raise ValueError(f"{label} must be a 64-character hex SHA-256")
    return normalized


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _value_key(value: Any) -> str:
    if value in (None, ""):
        return "missing"
    return str(value)


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(counter[key]) for key in sorted(counter)}


def _append_counts(lines: list[str], counts: Mapping[str, Any]) -> None:
    if not counts:
        lines.append("  (none)")
        return
    for label, count in sorted(counts.items()):
        lines.append(f"  {label}: {count}")


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"T052 artifact value is not JSON-safe: {type(value).__name__}")
