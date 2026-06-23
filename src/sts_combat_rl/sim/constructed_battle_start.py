"""Constructed A20 battle-start supplements.

The artifact produced here is an audit surface first: every row preserves its
natural source record and the proposal/eligibility result even when the native
simulator cannot or does not apply a requested transform.  Only rows with an
authoritative actual state change are tagged as constructed data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import random
from typing import Any, TextIO

from sts_combat_rl.sim.artifact_versioning import (
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    natural_battle_start_pool_problems,
    record_from_manifest,
    record_to_manifest,
    restore_battle_start_record,
)
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    ObservationValue,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    public_context_artifact_problems,
    sanitize_public_context_artifact,
)


CONSTRUCTED_START_SCHEMA_ID = "constructed-battle-start-v1"
CONSTRUCTED_START_FORMAT_VERSION = 1
CONSTRUCTED_TRANSFORM_POLICY_VERSION = "constructed-battle-start-policy-v1"
TRAINING_MIXTURE_MANIFEST_SCHEMA_ID = "training-mixture-manifest-v1"

CONSTRUCTED_DISTRIBUTION_KIND = "constructed_supplement"
PAIRED_COUNTERFACTUAL_DISTRIBUTION_KIND = "paired_counterfactual"
NORMAL_PUBLIC_INFORMATION_REGIME = "normal_public_policy"
TRANSFORM_TYPES = (
    "current_hp_addition",
    "potion_addition",
    "encounter_replacement",
)


@dataclass(frozen=True)
class ConstructedBattleStartPolicy:
    """Seeded conservative proposal policy for T008 supplements."""

    seed: int
    hp_probability: float = 0.25
    potion_probability: float = 0.10
    encounter_probability: float = 0.50
    max_hp_addition: int = 5
    hp_per_prior_battle_cap: int = 3
    transform_types: tuple[str, ...] = TRANSFORM_TYPES
    version: str = CONSTRUCTED_TRANSFORM_POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seed": self.seed,
            "hp_probability": self.hp_probability,
            "potion_probability": self.potion_probability,
            "encounter_probability": self.encounter_probability,
            "max_hp_addition": self.max_hp_addition,
            "hp_per_prior_battle_cap": self.hp_per_prior_battle_cap,
            "transform_types": list(self.transform_types),
        }


@dataclass(frozen=True)
class ConstructedBattleStartRecord:
    """One transform audit row for one immutable natural source record."""

    record_index: int
    source_record_index: int
    source_checkpoint_id: str
    source_distribution_kind: str
    source_checkpoint_information_regime: str
    source_public_context_status: str
    source_record: dict[str, Any]
    source_structural_metadata: dict[str, Any]
    transform_type: str
    transform_policy_version: str
    transform_seed: int
    proposal_seed: int
    eligibility: dict[str, Any]
    proposal: dict[str, Any]
    requested_change: dict[str, Any]
    actual_change: dict[str, Any]
    resulting_distribution_kind: str
    native_support_status: str
    data_information_regime: str = NORMAL_PUBLIC_INFORMATION_REGIME
    constructed_snapshot_observation: tuple[ObservationValue, ...] = ()
    constructed_snapshot_raw: dict[str, Any] = field(default_factory=dict)
    problems: tuple[str, ...] = ()

    @property
    def actual_applied(self) -> bool:
        return bool(self.actual_change.get("applied"))


@dataclass(frozen=True)
class TrainingMixtureManifest:
    """Counts that keep natural and constructed rows separately visible."""

    schema_id: str
    source_natural_count: int
    audit_record_count: int
    constructed_record_count: int
    distribution_counts: Counter[str] = field(default_factory=Counter)
    transform_type_counts: Counter[str] = field(default_factory=Counter)
    native_support_counts: Counter[str] = field(default_factory=Counter)
    actual_status_counts: Counter[str] = field(default_factory=Counter)
    source_context_status_counts: Counter[str] = field(default_factory=Counter)
    unsupported_native_operation_counts: Counter[str] = field(default_factory=Counter)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "source_natural_count": self.source_natural_count,
            "audit_record_count": self.audit_record_count,
            "constructed_record_count": self.constructed_record_count,
            "distribution_counts": dict(sorted(self.distribution_counts.items())),
            "transform_type_counts": dict(sorted(self.transform_type_counts.items())),
            "native_support_counts": dict(sorted(self.native_support_counts.items())),
            "actual_status_counts": dict(sorted(self.actual_status_counts.items())),
            "source_context_status_counts": dict(
                sorted(self.source_context_status_counts.items())
            ),
            "unsupported_native_operation_counts": dict(
                sorted(self.unsupported_native_operation_counts.items())
            ),
        }


@dataclass(frozen=True)
class ConstructedBattleStartArtifact:
    """Versioned JSONL artifact for constructed-start audit rows."""

    source_pool_format_version: int
    transform_policy: ConstructedBattleStartPolicy
    records: list[ConstructedBattleStartRecord]
    source_record_count: int
    source_controller_provenance: dict[str, Any]
    mixture_manifest: TrainingMixtureManifest
    format_version: int = CONSTRUCTED_START_FORMAT_VERSION
    schema_id: str = CONSTRUCTED_START_SCHEMA_ID
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=CONSTRUCTED_START_FORMAT_VERSION,
            target_version=CONSTRUCTED_START_FORMAT_VERSION,
        ),
        compare=False,
    )


@dataclass(frozen=True)
class ConstructedBattleStartAuditReport:
    """Human-readable accounting for the T008 command and PR report."""

    source_record_count: int
    audit_record_count: int
    constructed_record_count: int
    first_battle_source_count: int
    later_battle_source_count: int
    transform_policy: dict[str, Any]
    distribution_counts: Counter[str] = field(default_factory=Counter)
    eligibility_counts: Counter[str] = field(default_factory=Counter)
    proposal_counts: Counter[str] = field(default_factory=Counter)
    actual_counts: Counter[str] = field(default_factory=Counter)
    native_support_counts: Counter[str] = field(default_factory=Counter)
    unsupported_native_operation_counts: Counter[str] = field(default_factory=Counter)
    cap_violation_count: int = 0
    boss_replacement_violation_count: int = 0
    ascension_violation_count: int = 0
    source_context_status_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.source_record_count > 0
            and self.cap_violation_count == 0
            and self.boss_replacement_violation_count == 0
            and self.ascension_violation_count == 0
            and not self.problems
        )


def build_constructed_battle_start_artifact(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool: NaturalBattleStartPool,
    *,
    policy: ConstructedBattleStartPolicy,
) -> ConstructedBattleStartArtifact:
    """Build deterministic proposal/audit rows from an A20 natural pool."""

    policy = validated_constructed_policy(policy)
    pool_problems = natural_battle_start_pool_problems(pool)
    if pool_problems:
        raise ValueError(
            "invalid natural battle-start pool: " + "; ".join(pool_problems)
        )
    non_a20 = [
        record.record_index
        for record in pool.records
        if _source_ascension(record) != 20
    ]
    if non_a20:
        raise ValueError(
            "constructed battle-start supplements require A20 source records; "
            f"non-A20 records: {', '.join(str(index) for index in non_a20)}"
        )

    records: list[ConstructedBattleStartRecord] = []
    for source in pool.records:
        for transform_type in policy.transform_types:
            records.append(
                _build_transform_record(
                    adapter_factory,
                    source,
                    transform_type=transform_type,
                    policy=policy,
                    record_index=len(records),
                )
            )

    mixture_manifest = build_training_mixture_manifest(pool, records)
    artifact = ConstructedBattleStartArtifact(
        source_pool_format_version=pool.format_version,
        transform_policy=policy,
        records=records,
        source_record_count=len(pool.records),
        source_controller_provenance=dict(pool.source_controller_provenance),
        mixture_manifest=mixture_manifest,
        problems=[],
    )
    return ConstructedBattleStartArtifact(
        source_pool_format_version=artifact.source_pool_format_version,
        transform_policy=artifact.transform_policy,
        records=artifact.records,
        source_record_count=artifact.source_record_count,
        source_controller_provenance=artifact.source_controller_provenance,
        mixture_manifest=artifact.mixture_manifest,
        problems=constructed_battle_start_artifact_problems(artifact),
    )


def build_training_mixture_manifest(
    pool: NaturalBattleStartPool,
    records: Sequence[ConstructedBattleStartRecord],
) -> TrainingMixtureManifest:
    """Report mixture counts without relabeling constructed rows as natural."""

    distribution_counts = Counter(
        record.resulting_distribution_kind for record in records
    )
    distribution_counts[NATURAL_DISTRIBUTION_KIND] += len(pool.records)
    constructed_count = sum(
        1
        for record in records
        if record.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    )
    unsupported_counts = Counter(
        record.transform_type
        for record in records
        if record.native_support_status == "unsupported"
    )
    return TrainingMixtureManifest(
        schema_id=TRAINING_MIXTURE_MANIFEST_SCHEMA_ID,
        source_natural_count=len(pool.records),
        audit_record_count=len(records),
        constructed_record_count=constructed_count,
        distribution_counts=distribution_counts,
        transform_type_counts=Counter(record.transform_type for record in records),
        native_support_counts=Counter(
            record.native_support_status for record in records
        ),
        actual_status_counts=Counter(_actual_status(record) for record in records),
        source_context_status_counts=Counter(
            record.source_public_context_status for record in records
        ),
        unsupported_native_operation_counts=unsupported_counts,
    )


def build_constructed_battle_start_audit_report(
    artifact: ConstructedBattleStartArtifact,
) -> ConstructedBattleStartAuditReport:
    """Summarize transform eligibility, proposals, and invariant violations."""

    source_indices = {
        record.source_record_index: record.source_record for record in artifact.records
    }
    first_battles = 0
    later_battles = 0
    for source_record in source_indices.values():
        battle_index = _non_negative_int(
            source_record.get("source_battle_index"),
            "source_battle_index",
            default=0,
        )
        if battle_index == 0:
            first_battles += 1
        else:
            later_battles += 1

    cap_violations = 0
    boss_violations = 0
    ascension_violations = 0
    for record in artifact.records:
        for problem in record.problems:
            if "cap" in problem or "capacity" in problem or "max HP" in problem:
                cap_violations += 1
            if "Boss" in problem or "boss" in problem:
                boss_violations += 1
            if "ascension" in problem:
                ascension_violations += 1

    return ConstructedBattleStartAuditReport(
        source_record_count=artifact.source_record_count,
        audit_record_count=len(artifact.records),
        constructed_record_count=artifact.mixture_manifest.constructed_record_count,
        first_battle_source_count=first_battles,
        later_battle_source_count=later_battles,
        transform_policy=artifact.transform_policy.to_dict(),
        distribution_counts=Counter(artifact.mixture_manifest.distribution_counts),
        eligibility_counts=Counter(
            _eligibility_status(record) for record in artifact.records
        ),
        proposal_counts=Counter(
            _proposal_status(record) for record in artifact.records
        ),
        actual_counts=Counter(_actual_status(record) for record in artifact.records),
        native_support_counts=Counter(artifact.mixture_manifest.native_support_counts),
        unsupported_native_operation_counts=Counter(
            artifact.mixture_manifest.unsupported_native_operation_counts
        ),
        cap_violation_count=cap_violations,
        boss_replacement_violation_count=boss_violations,
        ascension_violation_count=ascension_violations,
        source_context_status_counts=Counter(
            artifact.mixture_manifest.source_context_status_counts
        ),
        problems=list(artifact.problems),
    )


def dump_constructed_battle_start_artifact_jsonl(
    artifact: ConstructedBattleStartArtifact,
    stream: TextIO,
) -> None:
    """Write the current constructed-start artifact schema."""

    problems = constructed_battle_start_artifact_problems(artifact)
    if problems:
        raise ValueError(
            "invalid constructed battle-start artifact: " + "; ".join(problems)
        )
    metadata = {
        "schema_id": CONSTRUCTED_START_SCHEMA_ID,
        "format_version": CONSTRUCTED_START_FORMAT_VERSION,
        "source_pool_format_version": artifact.source_pool_format_version,
        "source_record_count": artifact.source_record_count,
        "source_controller_provenance": _json_safe_mapping(
            artifact.source_controller_provenance
        ),
        "transform_policy": artifact.transform_policy.to_dict(),
        "mixture_manifest": artifact.mixture_manifest.to_dict(),
        "record_count": len(artifact.records),
        "migration_report": artifact.migration_report.to_dict(),
        "problems": list(artifact.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for record in artifact.records:
        _write_row(
            stream, {"type": "record", "record": record_to_manifest_constructed(record)}
        )


def load_constructed_battle_start_artifact_jsonl(
    stream: TextIO,
) -> ConstructedBattleStartArtifact:
    """Load and migrate a constructed-start JSONL artifact."""

    metadata: dict[str, Any] | None = None
    raw_records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, Mapping):
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
        raise ValueError("missing constructed battle-start metadata")
    if metadata.get("schema_id") != CONSTRUCTED_START_SCHEMA_ID:
        raise ValueError("constructed battle-start schema_id is unsupported")

    migrated = migrate_artifact_document(
        metadata,
        raw_records,
        current_version=CONSTRUCTED_START_FORMAT_VERSION,
        migrations=(),
        artifact_name="constructed battle-start artifact",
    )
    metadata = migrated.document.metadata
    policy = policy_from_manifest(metadata.get("transform_policy"))
    records = [
        record_from_manifest_constructed(raw, label=f"record {index}")
        for index, raw in enumerate(migrated.document.records)
    ]
    if metadata.get("record_count") != len(records):
        raise ValueError("constructed battle-start record_count mismatch")
    if any(record.record_index != index for index, record in enumerate(records)):
        raise ValueError("constructed battle-start record indices must be contiguous")
    source_record_count = _non_negative_int(
        metadata.get("source_record_count"),
        "source_record_count",
    )
    mixture_manifest = mixture_manifest_from_manifest(
        metadata.get("mixture_manifest"),
        source_record_count=source_record_count,
        records=records,
    )
    artifact = ConstructedBattleStartArtifact(
        source_pool_format_version=_positive_int(
            metadata.get("source_pool_format_version"),
            "source_pool_format_version",
        ),
        transform_policy=policy,
        records=records,
        source_record_count=source_record_count,
        source_controller_provenance=_json_safe_mapping(
            _require_mapping(
                metadata.get("source_controller_provenance"),
                "source_controller_provenance",
            )
        ),
        mixture_manifest=mixture_manifest,
        problems=_string_list(metadata.get("problems", []), "metadata problems"),
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="constructed battle-start artifact",
        ),
    )
    problems = constructed_battle_start_artifact_problems(artifact)
    if problems:
        raise ValueError(
            "invalid constructed battle-start artifact: " + "; ".join(problems)
        )
    return artifact


def record_to_manifest_constructed(
    record: ConstructedBattleStartRecord,
) -> dict[str, Any]:
    """Serialize one constructed-start audit row."""

    return {
        "record_index": record.record_index,
        "source_record_index": record.source_record_index,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_distribution_kind": record.source_distribution_kind,
        "source_checkpoint_information_regime": (
            record.source_checkpoint_information_regime
        ),
        "source_public_context_status": record.source_public_context_status,
        "source_record": _json_safe_mapping(record.source_record),
        "source_structural_metadata": _json_safe_mapping(
            record.source_structural_metadata
        ),
        "transform_type": record.transform_type,
        "transform_policy_version": record.transform_policy_version,
        "transform_seed": record.transform_seed,
        "proposal_seed": record.proposal_seed,
        "eligibility": _json_safe_mapping(record.eligibility),
        "proposal": _json_safe_mapping(record.proposal),
        "requested_change": _json_safe_mapping(record.requested_change),
        "actual_change": _json_safe_mapping(record.actual_change),
        "resulting_distribution_kind": record.resulting_distribution_kind,
        "native_support_status": record.native_support_status,
        "data_information_regime": record.data_information_regime,
        "constructed_snapshot_observation": list(
            record.constructed_snapshot_observation
        ),
        "constructed_snapshot_raw": _json_safe_mapping(record.constructed_snapshot_raw),
        "problems": list(record.problems),
    }


def record_from_manifest_constructed(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> ConstructedBattleStartRecord:
    """Strictly load one constructed-start audit row."""

    source_record = _require_mapping(raw.get("source_record"), f"{label} source_record")
    source = record_from_manifest(source_record, label=f"{label} source_record")
    transform_type = _transform_type(
        raw.get("transform_type"), f"{label} transform_type"
    )
    observation = raw.get("constructed_snapshot_observation", [])
    if not isinstance(observation, list) or not all(
        isinstance(value, (bool, int, float)) for value in observation
    ):
        raise ValueError(f"{label} constructed snapshot observation must be scalars")
    resulting_distribution = _distribution_kind(
        raw.get("resulting_distribution_kind"),
        f"{label} resulting_distribution_kind",
    )
    native_support_status = _native_support_status(
        raw.get("native_support_status"),
        f"{label} native_support_status",
    )
    data_information_regime = _non_empty_string(
        raw.get("data_information_regime"),
        f"{label} data_information_regime",
    )
    if data_information_regime != NORMAL_PUBLIC_INFORMATION_REGIME:
        raise ValueError(f"{label} data_information_regime is unsupported")
    return ConstructedBattleStartRecord(
        record_index=_non_negative_int(raw.get("record_index"), f"{label} index"),
        source_record_index=_non_negative_int(
            raw.get("source_record_index"),
            f"{label} source_record_index",
        ),
        source_checkpoint_id=_non_empty_string(
            raw.get("source_checkpoint_id"),
            f"{label} source_checkpoint_id",
        ),
        source_distribution_kind=_distribution_kind(
            raw.get("source_distribution_kind"),
            f"{label} source_distribution_kind",
        ),
        source_checkpoint_information_regime=_non_empty_string(
            raw.get("source_checkpoint_information_regime"),
            f"{label} source_checkpoint_information_regime",
        ),
        source_public_context_status=_non_empty_string(
            raw.get("source_public_context_status"),
            f"{label} source_public_context_status",
        ),
        source_record=record_to_manifest(source),
        source_structural_metadata=_require_mapping(
            raw.get("source_structural_metadata"),
            f"{label} source_structural_metadata",
        ),
        transform_type=transform_type,
        transform_policy_version=_non_empty_string(
            raw.get("transform_policy_version"),
            f"{label} transform_policy_version",
        ),
        transform_seed=_non_negative_int(
            raw.get("transform_seed"),
            f"{label} transform_seed",
        ),
        proposal_seed=_non_negative_int(
            raw.get("proposal_seed"),
            f"{label} proposal_seed",
        ),
        eligibility=_require_mapping(raw.get("eligibility"), f"{label} eligibility"),
        proposal=_require_mapping(raw.get("proposal"), f"{label} proposal"),
        requested_change=_require_mapping(
            raw.get("requested_change"),
            f"{label} requested_change",
        ),
        actual_change=_require_mapping(
            raw.get("actual_change"), f"{label} actual_change"
        ),
        resulting_distribution_kind=resulting_distribution,
        native_support_status=native_support_status,
        data_information_regime=data_information_regime,
        constructed_snapshot_observation=tuple(observation),
        constructed_snapshot_raw=_require_mapping(
            raw.get("constructed_snapshot_raw", {}),
            f"{label} constructed_snapshot_raw",
        ),
        problems=tuple(_string_list(raw.get("problems", []), f"{label} problems")),
    )


def constructed_battle_start_artifact_problems(
    artifact: ConstructedBattleStartArtifact,
) -> list[str]:
    """Return schema and invariant problems without guessing missing fields."""

    problems: list[str] = []
    if artifact.schema_id != CONSTRUCTED_START_SCHEMA_ID:
        problems.append("constructed artifact has unsupported schema_id")
    if artifact.format_version != CONSTRUCTED_START_FORMAT_VERSION:
        problems.append("constructed artifact has unsupported format_version")
    if artifact.source_pool_format_version != BATTLE_START_POOL_FORMAT_VERSION:
        problems.append("constructed artifact source pool format is not current")
    try:
        validated_constructed_policy(artifact.transform_policy)
    except ValueError as exc:
        problems.append(str(exc))
    if artifact.source_record_count < 0:
        problems.append("constructed artifact source_record_count is negative")
    if artifact.mixture_manifest.source_natural_count != artifact.source_record_count:
        problems.append("mixture manifest source_natural_count mismatch")
    if artifact.mixture_manifest.audit_record_count != len(artifact.records):
        problems.append("mixture manifest audit_record_count mismatch")
    if artifact.mixture_manifest.constructed_record_count != sum(
        1
        for record in artifact.records
        if record.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    ):
        problems.append("mixture manifest constructed_record_count mismatch")

    for index, record in enumerate(artifact.records):
        problems.extend(_record_problems(record, expected_index=index))
    return list(dict.fromkeys([*artifact.problems, *problems]))


def validated_constructed_policy(
    policy: ConstructedBattleStartPolicy,
) -> ConstructedBattleStartPolicy:
    """Validate and return a policy with canonical tuple fields."""

    if policy.version != CONSTRUCTED_TRANSFORM_POLICY_VERSION:
        raise ValueError("constructed transform policy version is unsupported")
    if (
        isinstance(policy.seed, bool)
        or not isinstance(policy.seed, int)
        or policy.seed < 0
    ):
        raise ValueError("constructed transform policy seed must be non-negative")
    for label, value in (
        ("hp_probability", policy.hp_probability),
        ("potion_probability", policy.potion_probability),
        ("encounter_probability", policy.encounter_probability),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{label} must be numeric")
        if not 0.0 <= float(value) < 1.0:
            raise ValueError(
                f"{label} must be in [0, 1) so transforms are never automatic"
            )
    if policy.max_hp_addition < 0:
        raise ValueError("max_hp_addition must be non-negative")
    if policy.hp_per_prior_battle_cap < 0:
        raise ValueError("hp_per_prior_battle_cap must be non-negative")
    invalid_types = [
        kind for kind in policy.transform_types if kind not in TRANSFORM_TYPES
    ]
    if invalid_types:
        raise ValueError(
            f"unknown constructed transform types: {', '.join(invalid_types)}"
        )
    return ConstructedBattleStartPolicy(
        seed=int(policy.seed),
        hp_probability=float(policy.hp_probability),
        potion_probability=float(policy.potion_probability),
        encounter_probability=float(policy.encounter_probability),
        max_hp_addition=int(policy.max_hp_addition),
        hp_per_prior_battle_cap=int(policy.hp_per_prior_battle_cap),
        transform_types=tuple(policy.transform_types),
        version=policy.version,
    )


def policy_from_manifest(value: object) -> ConstructedBattleStartPolicy:
    raw = _require_mapping(value, "transform_policy")
    transform_types = raw.get("transform_types", list(TRANSFORM_TYPES))
    if not isinstance(transform_types, list) or not all(
        isinstance(item, str) for item in transform_types
    ):
        raise ValueError("transform_policy transform_types must be a string list")
    return validated_constructed_policy(
        ConstructedBattleStartPolicy(
            seed=_non_negative_int(raw.get("seed"), "transform_policy seed"),
            hp_probability=float(raw.get("hp_probability")),
            potion_probability=float(raw.get("potion_probability")),
            encounter_probability=float(raw.get("encounter_probability")),
            max_hp_addition=_non_negative_int(
                raw.get("max_hp_addition"),
                "transform_policy max_hp_addition",
            ),
            hp_per_prior_battle_cap=_non_negative_int(
                raw.get("hp_per_prior_battle_cap"),
                "transform_policy hp_per_prior_battle_cap",
            ),
            transform_types=tuple(transform_types),
            version=_non_empty_string(raw.get("version"), "transform_policy version"),
        )
    )


def mixture_manifest_from_manifest(
    value: object,
    *,
    source_record_count: int,
    records: Sequence[ConstructedBattleStartRecord],
) -> TrainingMixtureManifest:
    raw = _require_mapping(value, "mixture_manifest")
    if raw.get("schema_id") != TRAINING_MIXTURE_MANIFEST_SCHEMA_ID:
        raise ValueError("mixture_manifest schema_id is unsupported")
    manifest = build_training_mixture_manifest(
        NaturalBattleStartPool(
            source_run_count=0,
            terminal_run_count=0,
            truncated_run_count=0,
            source_controller_provenance={
                "kind": "decision_policy",
                "name": "manifest-placeholder",
                "config": {},
            },
            records=[],
        ),
        records,
    )
    return (
        TrainingMixtureManifest(
            schema_id=TRAINING_MIXTURE_MANIFEST_SCHEMA_ID,
            source_natural_count=_non_negative_int(
                raw.get("source_natural_count"),
                "mixture_manifest source_natural_count",
            ),
            audit_record_count=_non_negative_int(
                raw.get("audit_record_count"),
                "mixture_manifest audit_record_count",
            ),
            constructed_record_count=_non_negative_int(
                raw.get("constructed_record_count"),
                "mixture_manifest constructed_record_count",
            ),
            distribution_counts=_counter(raw.get("distribution_counts")),
            transform_type_counts=_counter(raw.get("transform_type_counts")),
            native_support_counts=_counter(raw.get("native_support_counts")),
            actual_status_counts=_counter(raw.get("actual_status_counts")),
            source_context_status_counts=_counter(
                raw.get("source_context_status_counts")
            ),
            unsupported_native_operation_counts=_counter(
                raw.get("unsupported_native_operation_counts")
            ),
        )
        if source_record_count or records
        else manifest
    )


def format_constructed_battle_start_audit_report(
    report: ConstructedBattleStartAuditReport,
) -> str:
    """Format the T008 audit report for stderr and PR descriptions."""

    lines = [
        "Constructed battle-start supplement audit",
        f"schema: {CONSTRUCTED_START_SCHEMA_ID} v{CONSTRUCTED_START_FORMAT_VERSION}",
        f"policy version: {report.transform_policy.get('version', '(unknown)')}",
        f"policy seed: {report.transform_policy.get('seed', '(unknown)')}",
        f"source natural battle starts: {report.source_record_count}",
        f"first-battle sources: {report.first_battle_source_count}",
        f"later-battle sources: {report.later_battle_source_count}",
        f"transform audit rows: {report.audit_record_count}",
        f"constructed rows: {report.constructed_record_count}",
        f"cap violations: {report.cap_violation_count}",
        f"Boss replacement violations: {report.boss_replacement_violation_count}",
        f"ascension violations: {report.ascension_violation_count}",
        f"audit passed: {'yes' if report.passed else 'no'}",
    ]
    _append_counter(lines, "resulting distributions", report.distribution_counts)
    _append_counter(lines, "eligibility", report.eligibility_counts)
    _append_counter(lines, "proposal results", report.proposal_counts)
    _append_counter(lines, "actual transform results", report.actual_counts)
    _append_counter(lines, "native support", report.native_support_counts)
    _append_counter(
        lines,
        "unsupported native operations",
        report.unsupported_native_operation_counts,
    )
    _append_counter(
        lines,
        "source public-context statuses",
        report.source_context_status_counts,
    )
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _build_transform_record(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    source: BattleStartCheckpointRecord,
    *,
    transform_type: str,
    policy: ConstructedBattleStartPolicy,
    record_index: int,
) -> ConstructedBattleStartRecord:
    proposal_seed = _proposal_seed(policy, source, transform_type)
    rng = random.Random(proposal_seed)
    eligibility = _eligibility(source, transform_type, policy)
    proposal = _proposal(source, transform_type, policy, eligibility, rng)
    requested_change = dict(proposal.get("requested_change", {}))
    actual_change: dict[str, Any] = {"applied": False, "reason": "not_triggered"}
    native_support_status = "not_requested"
    constructed_snapshot = None
    problems: list[str] = []

    if proposal.get("triggered") is True:
        try:
            actual_change, constructed_snapshot, native_support_status = (
                _apply_transform(
                    adapter_factory,
                    source,
                    transform_type=transform_type,
                    requested_change=requested_change,
                    rng=rng,
                )
            )
        except (RuntimeError, ValueError) as exc:
            actual_change = {
                "applied": False,
                "reason": "native_error",
                "error": str(exc),
            }
            native_support_status = "error"
            problems.append(str(exc))
    else:
        native_support_status = "not_requested"

    if constructed_snapshot is not None:
        problems.extend(
            _actual_change_problems(
                source,
                constructed_snapshot,
                transform_type=transform_type,
                eligibility=eligibility,
                requested_change=requested_change,
                actual_change=actual_change,
            )
        )

    applied = bool(actual_change.get("applied")) and not problems
    resulting_distribution = (
        CONSTRUCTED_DISTRIBUTION_KIND if applied else NATURAL_DISTRIBUTION_KIND
    )
    if not applied:
        constructed_snapshot = None

    source_manifest = record_to_manifest(source)
    return ConstructedBattleStartRecord(
        record_index=record_index,
        source_record_index=source.record_index,
        source_checkpoint_id=source.source_checkpoint_id,
        source_distribution_kind=source.distribution_kind,
        source_checkpoint_information_regime=source.checkpoint_information_regime,
        source_public_context_status=source.public_context_status,
        source_record=source_manifest,
        source_structural_metadata=dict(source.structural_metadata),
        transform_type=transform_type,
        transform_policy_version=policy.version,
        transform_seed=policy.seed,
        proposal_seed=proposal_seed,
        eligibility=eligibility,
        proposal={
            key: value for key, value in proposal.items() if key != "requested_change"
        },
        requested_change=requested_change,
        actual_change=actual_change,
        resulting_distribution_kind=resulting_distribution,
        native_support_status=native_support_status,
        constructed_snapshot_observation=(
            tuple(constructed_snapshot.observation)
            if constructed_snapshot is not None
            else ()
        ),
        constructed_snapshot_raw=(
            dict(constructed_snapshot.raw) if constructed_snapshot is not None else {}
        ),
        problems=tuple(problems),
    )


def _eligibility(
    source: BattleStartCheckpointRecord,
    transform_type: str,
    policy: ConstructedBattleStartPolicy,
) -> dict[str, Any]:
    prior_opportunities, opportunity_reason = _visible_prior_battle_opportunities(
        source
    )
    raw = source.snapshot_raw
    reasons: list[str] = []
    base: dict[str, Any] = {
        "transform_type": transform_type,
        "source_battle_index": source.source_battle_index,
        "visible_prior_battle_opportunities": prior_opportunities,
        "visible_prior_opportunity_reason": opportunity_reason,
        "source_ascension": _source_ascension(source),
    }
    if _source_ascension(source) != 20:
        reasons.append("requires_a20_source")
    if transform_type == "current_hp_addition":
        current_hp = _current_hp(raw)
        max_hp = _max_hp(raw)
        missing_hp = (
            max(0, max_hp - current_hp) if None not in (current_hp, max_hp) else 0
        )
        opportunity_cap = prior_opportunities * policy.hp_per_prior_battle_cap
        cap = min(missing_hp, policy.max_hp_addition, opportunity_cap)
        base.update(
            {
                "current_hp": current_hp,
                "max_hp": max_hp,
                "missing_hp": missing_hp,
                "policy_cap": policy.max_hp_addition,
                "prior_opportunity_cap": opportunity_cap,
                "actual_cap": cap,
            }
        )
        if prior_opportunities <= 0:
            reasons.append("first_battle_or_missing_prior_opportunity")
        if cap <= 0:
            reasons.append("no_positive_hp_cap")
    elif transform_type == "potion_addition":
        potion_count = _potion_count(raw)
        potion_capacity = _potion_capacity(raw)
        empty_slots = max(0, potion_capacity - potion_count)
        opportunity_cap = max(0, prior_opportunities - potion_count)
        cap = min(empty_slots, opportunity_cap)
        base.update(
            {
                "potion_count": potion_count,
                "potion_capacity": potion_capacity,
                "empty_slots": empty_slots,
                "prior_opportunity_cap": opportunity_cap,
                "actual_cap": cap,
            }
        )
        if prior_opportunities <= 0:
            reasons.append("first_battle_or_missing_prior_opportunity")
        if empty_slots <= 0:
            reasons.append("no_visible_empty_potion_slot")
        if opportunity_cap <= 0:
            reasons.append("prior_potion_opportunity_bound_exhausted")
    elif transform_type == "encounter_replacement":
        room_type = str(raw.get("room_type", "")).upper()
        base.update(
            {
                "room_type": room_type,
                "source_encounter_id": raw.get("encounter_id"),
                "visible_act_boss": _visible_act_boss(source),
            }
        )
        if room_type == "BOSS":
            reasons.append("visible_boss_replacement_out_of_scope")
        elif room_type not in {"MONSTER", "ELITE"}:
            reasons.append("unsupported_room_type")
    else:
        reasons.append("unknown_transform_type")
    base["eligible"] = not reasons
    base["reasons"] = reasons
    return base


def _proposal(
    source: BattleStartCheckpointRecord,
    transform_type: str,
    policy: ConstructedBattleStartPolicy,
    eligibility: Mapping[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    if not eligibility.get("eligible"):
        return {
            "triggered": False,
            "reason": "ineligible",
            "requested_change": {"transform_type": transform_type},
        }
    probability = {
        "current_hp_addition": policy.hp_probability,
        "potion_addition": policy.potion_probability,
        "encounter_replacement": policy.encounter_probability,
    }[transform_type]
    triggered = rng.random() < probability
    if not triggered:
        return {
            "triggered": False,
            "reason": "seeded_probability_noop",
            "probability": probability,
            "requested_change": {"transform_type": transform_type},
        }
    requested_change: dict[str, Any] = {"transform_type": transform_type}
    if transform_type == "current_hp_addition":
        cap = _non_negative_int(eligibility.get("actual_cap"), "hp actual_cap")
        requested_change["current_hp_delta"] = _sample_small_positive_delta(rng, cap)
    elif transform_type == "potion_addition":
        requested_change["add_random_potion"] = True
    elif transform_type == "encounter_replacement":
        requested_change["source_encounter_id"] = source.snapshot_raw.get(
            "encounter_id"
        )
    return {
        "triggered": True,
        "reason": "seeded_probability_triggered",
        "probability": probability,
        "requested_change": requested_change,
    }


def _apply_transform(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    source: BattleStartCheckpointRecord,
    *,
    transform_type: str,
    requested_change: Mapping[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], SimulatorSnapshot | None, str]:
    adapter = adapter_factory()
    restored, _ = restore_battle_start_record(adapter, source)
    rebuild = getattr(adapter, "rebuild_battle_start", None)
    if not callable(rebuild):
        return (
            {
                "applied": False,
                "reason": "unsupported_native_operation",
                "operation": "rebuild_battle_start",
            },
            None,
            "unsupported",
        )

    if transform_type == "current_hp_addition":
        hp_bonus = _non_negative_int(
            requested_change.get("current_hp_delta"),
            "requested current_hp_delta",
        )
        rebuild_result = _call_rebuild(
            rebuild,
            restored,
            hp_bonus=hp_bonus,
            add_random_potion=False,
            encounter_id=None,
            operation="rebuild_battle_start",
        )
        if rebuild_result[2] == "unsupported":
            return rebuild_result
        actual, transformed, _ = rebuild_result
        assert transformed is not None
        transformed = _coerce_snapshot(transformed)
        delta = (_current_hp(transformed.raw) or 0) - (_current_hp(restored.raw) or 0)
        actual.update(
            {
                "applied": delta > 0,
                "current_hp_delta": delta,
                "requested_current_hp_delta": hp_bonus,
                "before_current_hp": _current_hp(restored.raw),
                "after_current_hp": _current_hp(transformed.raw),
                "max_hp": _max_hp(transformed.raw),
            }
        )
        return actual, transformed, "supported"

    if transform_type == "potion_addition":
        rebuild_result = _call_rebuild(
            rebuild,
            restored,
            hp_bonus=0,
            add_random_potion=True,
            encounter_id=None,
            operation="rebuild_battle_start",
        )
        if rebuild_result[2] == "unsupported":
            return rebuild_result
        actual, transformed, _ = rebuild_result
        assert transformed is not None
        transformed = _coerce_snapshot(transformed)
        added = _added_potion_identity(restored.raw, transformed.raw)
        actual.update(
            {
                "applied": added is not None,
                "requested_random_potion": True,
                "added_potion": added,
                "before_potion_count": _potion_count(restored.raw),
                "after_potion_count": _potion_count(transformed.raw),
                "potion_capacity": _potion_capacity(transformed.raw),
            }
        )
        return actual, transformed, "supported"

    candidate_method = getattr(adapter, "legal_battle_start_encounters", None)
    if not callable(candidate_method):
        return (
            {
                "applied": False,
                "reason": "unsupported_native_operation",
                "operation": "legal_battle_start_encounters",
            },
            None,
            "unsupported",
        )
    try:
        raw_candidates = candidate_method(restored)
    except RuntimeError as exc:
        if _is_native_unsupported(exc):
            return (
                {
                    "applied": False,
                    "reason": "unsupported_native_operation",
                    "operation": "legal_battle_start_encounters",
                },
                None,
                "unsupported",
            )
        raise
    candidates = [
        _require_mapping(row, "encounter candidate") for row in raw_candidates
    ]
    alternatives = [
        row
        for row in candidates
        if row.get("encounter_id") != restored.raw.get("encounter_id")
        and row.get("id") is not None
    ]
    if not alternatives:
        return (
            {
                "applied": False,
                "reason": "no_authoritative_encounter_alternative",
                "candidate_count": len(candidates),
            },
            None,
            "supported",
        )
    target = rng.choice(alternatives)
    rebuild_result = _call_rebuild(
        rebuild,
        restored,
        hp_bonus=0,
        add_random_potion=False,
        encounter_id=target["id"],
        operation="rebuild_battle_start",
    )
    if rebuild_result[2] == "unsupported":
        return rebuild_result
    actual, transformed, _ = rebuild_result
    assert transformed is not None
    transformed = _coerce_snapshot(transformed)
    changed = transformed.raw.get("encounter_id") != restored.raw.get("encounter_id")
    actual.update(
        {
            "applied": changed,
            "source_encounter_id": restored.raw.get("encounter_id"),
            "target_encounter_id": transformed.raw.get("encounter_id"),
            "requested_native_encounter_id": target["id"],
            "authoritative_candidate_count": len(candidates),
        }
    )
    return actual, transformed, "supported"


def _actual_change_problems(
    source: BattleStartCheckpointRecord,
    transformed: SimulatorSnapshot,
    *,
    transform_type: str,
    eligibility: Mapping[str, Any],
    requested_change: Mapping[str, Any],
    actual_change: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    source_raw = source.snapshot_raw
    transformed_raw = transformed.raw
    for field_name in ("ascension", "act", "room_type"):
        if transformed_raw.get(field_name) != source_raw.get(field_name):
            problems.append(f"actual transform changed {field_name}")
    if transformed_raw.get("ascension") != 20:
        problems.append("actual transform output is not A20")
    if transform_type != "encounter_replacement":
        if transformed_raw.get("encounter_id") != source_raw.get("encounter_id"):
            problems.append("non-encounter transform changed encounter_id")
    if transform_type == "encounter_replacement":
        if str(source_raw.get("room_type", "")).upper() == "BOSS":
            problems.append("encounter transform replaced a visible Boss")
    if transform_type == "current_hp_addition" and actual_change.get("applied"):
        source_hp = _current_hp(source_raw)
        result_hp = _current_hp(transformed_raw)
        result_max = _max_hp(transformed_raw)
        requested = requested_change.get("current_hp_delta")
        cap = eligibility.get("actual_cap")
        if None in (source_hp, result_hp, result_max):
            problems.append("HP transform result is missing HP fields")
        else:
            assert source_hp is not None
            assert result_hp is not None
            assert result_max is not None
            delta = result_hp - source_hp
            if delta != requested:
                problems.append("HP transform actual delta does not match request")
            if isinstance(cap, int) and delta > cap:
                problems.append("HP transform exceeded documented cap")
            if result_hp > result_max:
                problems.append("HP transform exceeded max HP")
    if transform_type == "potion_addition" and actual_change.get("applied"):
        source_count = _potion_count(source_raw)
        result_count = _potion_count(transformed_raw)
        capacity = _potion_capacity(transformed_raw)
        opportunity_cap = eligibility.get("prior_opportunity_cap")
        if result_count - source_count != 1:
            problems.append("potion transform did not add exactly one potion")
        if result_count > capacity:
            problems.append("potion transform exceeded inventory capacity")
        if (
            isinstance(opportunity_cap, int)
            and result_count - source_count > opportunity_cap
        ):
            problems.append("potion transform exceeded opportunity bound")
    return problems


def _record_problems(
    record: ConstructedBattleStartRecord,
    *,
    expected_index: int,
) -> list[str]:
    problems: list[str] = []
    if record.record_index != expected_index:
        problems.append(f"record {expected_index} index is not contiguous")
    if record.transform_type not in TRANSFORM_TYPES:
        problems.append(f"record {expected_index} has unsupported transform_type")
    try:
        source = record_from_manifest(
            record.source_record,
            label=f"record {expected_index} source_record",
        )
    except ValueError as exc:
        problems.append(str(exc))
        source = None
    if source is not None:
        if record.source_checkpoint_id != source.source_checkpoint_id:
            problems.append(f"record {expected_index} source checkpoint mismatch")
        if record.source_record_index != source.record_index:
            problems.append(f"record {expected_index} source index mismatch")
        if record.source_distribution_kind != source.distribution_kind:
            problems.append(f"record {expected_index} source distribution mismatch")
        if record.source_distribution_kind != NATURAL_DISTRIBUTION_KIND:
            problems.append(f"record {expected_index} source is not natural_run")
        if _source_ascension(source) != 20:
            problems.append(f"record {expected_index} source is not A20")
        problems.extend(
            public_context_artifact_problems(
                status=source.public_context_status,
                context=source.public_run_context,
                label=f"record {expected_index} source",
            )
        )
    if record.source_checkpoint_information_regime not in {
        CHECKPOINT_INFORMATION_REGIME,
        "unknown",
    }:
        problems.append(f"record {expected_index} checkpoint regime is invalid")
    if record.resulting_distribution_kind not in {
        NATURAL_DISTRIBUTION_KIND,
        CONSTRUCTED_DISTRIBUTION_KIND,
        PAIRED_COUNTERFACTUAL_DISTRIBUTION_KIND,
    }:
        problems.append(f"record {expected_index} distribution kind is invalid")
    if (
        record.actual_applied
        and record.resulting_distribution_kind != CONSTRUCTED_DISTRIBUTION_KIND
    ):
        problems.append(f"record {expected_index} applied change is not constructed")
    if (
        not record.actual_applied
        and record.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    ):
        problems.append(f"record {expected_index} no-op is tagged constructed")
    if record.native_support_status not in {
        "not_requested",
        "supported",
        "unsupported",
        "error",
    }:
        problems.append(f"record {expected_index} native support status is invalid")
    if record.data_information_regime != NORMAL_PUBLIC_INFORMATION_REGIME:
        problems.append(f"record {expected_index} data information regime is invalid")
    problems.extend(record.problems)
    return problems


def _proposal_seed(
    policy: ConstructedBattleStartPolicy,
    source: BattleStartCheckpointRecord,
    transform_type: str,
) -> int:
    payload = json.dumps(
        {
            "policy_version": policy.version,
            "policy_seed": policy.seed,
            "source_checkpoint_id": source.source_checkpoint_id,
            "source_record_index": source.record_index,
            "transform_type": transform_type,
        },
        sort_keys=True,
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _visible_prior_battle_opportunities(
    record: BattleStartCheckpointRecord,
) -> tuple[int, str]:
    if record.public_context_status != PUBLIC_CONTEXT_AVAILABLE:
        return 0, "public_context_unavailable"
    try:
        context = sanitize_public_context_artifact(
            record.public_run_context,
            label=f"record {record.record_index}",
        )
    except ValueError:
        return 0, "public_context_invalid"
    history = context.get("history")
    if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
        return 0, "public_history_missing"
    count = 0
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        pre_screen = _field_value(
            _mapping(_mapping(entry.get("pre_decision")).get("screen"))
        )
        post_screen = _field_value(
            _mapping(_mapping(entry.get("post_decision")).get("screen"))
        )
        battle_outcome = _field_value(
            _mapping(_mapping(entry.get("post_decision")).get("result")).get(
                "battle_outcome"
            )
        )
        if str(pre_screen).upper() == "BATTLE" and (
            str(post_screen).upper() != "BATTLE"
            or str(battle_outcome).upper()
            in {"PLAYER_VICTORY", "PLAYER_LOSS", "VICTORY", "LOSS"}
        ):
            count += 1
    if count <= 0:
        return 0, "no_visible_prior_battle_exit"
    return count, "public_history_battle_exits"


def _source_ascension(record: BattleStartCheckpointRecord) -> int | None:
    value = record.structural_metadata.get(
        "ascension", record.snapshot_raw.get("ascension")
    )
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _visible_act_boss(record: BattleStartCheckpointRecord) -> Any:
    if record.public_context_status != PUBLIC_CONTEXT_AVAILABLE:
        return None
    visible = _mapping(record.public_run_context.get("visible_act_boss"))
    return _field_value(visible)


def _current_hp(raw: Mapping[str, Any]) -> int | None:
    return _first_int(
        raw, ("cur_hp",), ("battle_player_hp",), ("battle_player", "current_hp")
    )


def _max_hp(raw: Mapping[str, Any]) -> int | None:
    return _first_int(raw, ("max_hp",), ("battle_player", "max_hp"))


def _potion_count(raw: Mapping[str, Any]) -> int:
    value = raw.get("battle_potion_count", raw.get("potion_count"))
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return len(_non_empty_potion_identities(raw))


def _potion_capacity(raw: Mapping[str, Any]) -> int:
    value = raw.get("battle_potion_capacity", raw.get("potion_capacity"))
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    potions = _potion_items(raw)
    return len(potions) if potions else _potion_count(raw)


def _non_empty_potion_identities(raw: Mapping[str, Any]) -> list[tuple[Any, str]]:
    identities: list[tuple[Any, str]] = []
    for potion in _potion_items(raw):
        name = str(potion.get("name", ""))
        normalized = name.upper().replace(" ", "_")
        if normalized in {"", "EMPTY_POTION_SLOT", "POTION_SLOT"}:
            continue
        identities.append((potion.get("id"), name))
    return identities


def _potion_items(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = raw.get("battle_potions", raw.get("potions"))
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _added_potion_identity(
    source_raw: Mapping[str, Any],
    transformed_raw: Mapping[str, Any],
) -> dict[str, Any] | None:
    source_counts = Counter(_non_empty_potion_identities(source_raw))
    for identity in _non_empty_potion_identities(transformed_raw):
        if source_counts[identity] > 0:
            source_counts[identity] -= 1
            continue
        potion_id, name = identity
        return {"id": potion_id, "name": name}
    return None


def _sample_small_positive_delta(rng: random.Random, cap: int) -> int:
    if cap <= 0:
        return 0
    delta = 1
    while delta < cap and rng.random() < 0.5:
        delta += 1
    return delta


def _coerce_snapshot(value: object) -> SimulatorSnapshot:
    if isinstance(value, SimulatorSnapshot):
        return value
    if isinstance(value, Mapping):
        raw = _require_mapping(value.get("raw", value), "native transform snapshot raw")
        observation = value.get("observation", [])
        if not isinstance(observation, Sequence) or isinstance(
            observation, (str, bytes)
        ):
            raise ValueError("native transform observation must be a sequence")
        if not all(isinstance(item, (bool, int, float)) for item in observation):
            raise ValueError("native transform observation contains non-scalars")
        return SimulatorSnapshot(observation=list(observation), raw=raw)
    raise ValueError("native transform must return a SimulatorSnapshot or mapping")


def _call_rebuild(
    rebuild: object,
    snapshot: SimulatorSnapshot,
    *,
    hp_bonus: int,
    add_random_potion: bool,
    encounter_id: object,
    operation: str,
) -> tuple[dict[str, Any], SimulatorSnapshot | None, str]:
    if not callable(rebuild):
        raise ValueError("native rebuild operation is not callable")
    try:
        transformed = rebuild(
            snapshot,
            hp_bonus=hp_bonus,
            add_random_potion=add_random_potion,
            encounter_id=encounter_id,
        )
    except RuntimeError as exc:
        if _is_native_unsupported(exc):
            return (
                {
                    "applied": False,
                    "reason": "unsupported_native_operation",
                    "operation": operation,
                },
                None,
                "unsupported",
            )
        raise
    return {"applied": False}, _coerce_snapshot(transformed), "supported"


def _is_native_unsupported(exc: RuntimeError) -> bool:
    message = str(exc)
    return "does not expose" in message or "unsupported" in message


def _first_int(raw: Mapping[str, Any], *paths: tuple[str, ...]) -> int | None:
    for path in paths:
        value: Any = raw
        for key in path:
            if not isinstance(value, Mapping):
                value = None
                break
            value = value.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
    return None


def _field_value(value: object) -> Any:
    if isinstance(value, Mapping) and value.get("availability") == "available":
        return value.get("value")
    return None


def _eligibility_status(record: ConstructedBattleStartRecord) -> str:
    return f"{record.transform_type}:{bool(record.eligibility.get('eligible'))}"


def _proposal_status(record: ConstructedBattleStartRecord) -> str:
    return f"{record.transform_type}:{bool(record.proposal.get('triggered'))}"


def _actual_status(record: ConstructedBattleStartRecord) -> str:
    if record.actual_applied:
        return f"{record.transform_type}:applied"
    reason = str(record.actual_change.get("reason", "not_applied"))
    return f"{record.transform_type}:{reason}"


def _transform_type(value: object, label: str) -> str:
    if value not in TRANSFORM_TYPES:
        raise ValueError(f"{label} must be one of {TRANSFORM_TYPES!r}")
    return str(value)


def _distribution_kind(value: object, label: str) -> str:
    if value not in {
        NATURAL_DISTRIBUTION_KIND,
        CONSTRUCTED_DISTRIBUTION_KIND,
        PAIRED_COUNTERFACTUAL_DISTRIBUTION_KIND,
    }:
        raise ValueError(f"{label} has invalid value {value!r}")
    return str(value)


def _native_support_status(value: object, label: str) -> str:
    if value not in {"not_requested", "supported", "unsupported", "error"}:
        raise ValueError(f"{label} has invalid value {value!r}")
    return str(value)


def _counter(value: object) -> Counter[str]:
    raw = _require_mapping(value, "counter")
    counter: Counter[str] = Counter()
    for key, count in raw.items():
        counter[str(key)] = _non_negative_int(count, f"counter {key}")
    return counter


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value: object, label: str, *, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


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


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    stream.write(json.dumps(row, sort_keys=True, allow_nan=False))
    stream.write("\n")


def _append_counter(lines: list[str], title: str, values: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        lines.append(f"  {key}: {values[key]}")
