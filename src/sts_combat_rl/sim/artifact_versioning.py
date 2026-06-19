"""Shared sequential migration support for persisted artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactDocument:
    """One parsed artifact document before construction of typed objects."""

    metadata: dict[str, Any]
    records: list[dict[str, Any]]


@dataclass(frozen=True)
class ArtifactMigration:
    """One explicit migration from a schema version to its successor."""

    source_version: int
    target_version: int
    migrate: Callable[[ArtifactDocument], ArtifactDocument]
    losses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.target_version != self.source_version + 1:
            raise ValueError("artifact migrations must advance exactly one version")


@dataclass(frozen=True)
class ArtifactMigrationReport:
    """Audit trail for migrations applied while loading an artifact."""

    source_version: int
    target_version: int
    applied_versions: tuple[int, ...] = ()
    losses: tuple[str, ...] = ()

    @property
    def migrated(self) -> bool:
        return self.source_version != self.target_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_version": self.source_version,
            "target_version": self.target_version,
            "applied_versions": list(self.applied_versions),
            "losses": list(self.losses),
        }


@dataclass(frozen=True)
class MigratedArtifact:
    """Current-schema document plus its migration audit trail."""

    document: ArtifactDocument
    report: ArtifactMigrationReport


def migrate_artifact_document(
    metadata: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    current_version: int,
    migrations: Sequence[ArtifactMigration],
    artifact_name: str,
) -> MigratedArtifact:
    """Migrate a parsed artifact sequentially into the current schema."""

    source_version = _format_version(metadata, artifact_name)
    if source_version > current_version:
        raise ValueError(
            f"unsupported {artifact_name} format version {source_version}; "
            f"current version is {current_version}"
        )

    migration_by_source = {
        migration.source_version: migration for migration in migrations
    }
    if len(migration_by_source) != len(migrations):
        raise ValueError(
            f"{artifact_name} migrations contain duplicate source versions"
        )

    document = ArtifactDocument(
        metadata=dict(metadata),
        records=[dict(record) for record in records],
    )
    version = source_version
    applied_versions: list[int] = []
    losses: list[str] = []
    while version < current_version:
        migration = migration_by_source.get(version)
        if migration is None:
            raise ValueError(
                f"unsupported {artifact_name} format version {source_version}; "
                f"missing migration from version {version}"
            )
        document = migration.migrate(document)
        migrated_version = _format_version(document.metadata, artifact_name)
        if migrated_version != migration.target_version:
            raise ValueError(
                f"{artifact_name} migration from version {version} produced "
                f"version {migrated_version}, expected {migration.target_version}"
            )
        version = migrated_version
        applied_versions.append(version)
        losses.extend(migration.losses)

    return MigratedArtifact(
        document=document,
        report=ArtifactMigrationReport(
            source_version=source_version,
            target_version=current_version,
            applied_versions=tuple(applied_versions),
            losses=tuple(dict.fromkeys(losses)),
        ),
    )


def preserved_migration_report(
    metadata: Mapping[str, Any],
    load_report: ArtifactMigrationReport,
    *,
    artifact_name: str,
) -> ArtifactMigrationReport:
    """Preserve current-schema lineage if it was already written."""

    raw = metadata.get("migration_report")
    if load_report.migrated or raw is None:
        return load_report
    if not isinstance(raw, Mapping):
        raise ValueError(f"{artifact_name} migration_report must be an object")

    source_version = _positive_int(
        raw.get("source_version"),
        f"{artifact_name} migration_report.source_version",
    )
    target_version = _positive_int(
        raw.get("target_version"),
        f"{artifact_name} migration_report.target_version",
    )
    applied_versions = _int_tuple(
        raw.get("applied_versions"),
        f"{artifact_name} migration_report.applied_versions",
    )
    losses = _str_tuple(
        raw.get("losses"),
        f"{artifact_name} migration_report.losses",
    )
    if target_version != load_report.target_version:
        raise ValueError(f"{artifact_name} migration_report target version mismatch")
    return ArtifactMigrationReport(
        source_version=source_version,
        target_version=target_version,
        applied_versions=applied_versions,
        losses=losses,
    )


def _format_version(metadata: Mapping[str, Any], artifact_name: str) -> int:
    return _positive_int(
        metadata.get("format_version"),
        f"{artifact_name} format_version",
    )


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _int_tuple(value: Any, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an integer list")
    return tuple(_positive_int(item, label) for item in value)


def _str_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return tuple(value)
