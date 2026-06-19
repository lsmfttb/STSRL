from __future__ import annotations

import pytest

from sts_combat_rl.sim.artifact_versioning import (
    ArtifactDocument,
    ArtifactMigration,
    migrate_artifact_document,
)


def test_artifact_migrations_apply_sequentially_and_report_losses() -> None:
    def migrate_v1_to_v2(document: ArtifactDocument) -> ArtifactDocument:
        metadata = dict(document.metadata)
        metadata["format_version"] = 2
        return ArtifactDocument(metadata=metadata, records=document.records)

    def migrate_v2_to_v3(document: ArtifactDocument) -> ArtifactDocument:
        metadata = dict(document.metadata)
        metadata["format_version"] = 3
        records = [{**record, "current": True} for record in document.records]
        return ArtifactDocument(metadata=metadata, records=records)

    migrated = migrate_artifact_document(
        {"format_version": 1},
        [{"value": 3}],
        current_version=3,
        migrations=(
            ArtifactMigration(
                source_version=1,
                target_version=2,
                migrate=migrate_v1_to_v2,
                losses=("v1 omitted controller provenance",),
            ),
            ArtifactMigration(
                source_version=2,
                target_version=3,
                migrate=migrate_v2_to_v3,
            ),
        ),
        artifact_name="test artifact",
    )

    assert migrated.document.metadata["format_version"] == 3
    assert migrated.document.records == [{"value": 3, "current": True}]
    assert migrated.report.source_version == 1
    assert migrated.report.target_version == 3
    assert migrated.report.applied_versions == (2, 3)
    assert migrated.report.losses == ("v1 omitted controller provenance",)


def test_artifact_migration_rejects_missing_intermediate_step() -> None:
    with pytest.raises(ValueError, match="missing migration from version 1"):
        migrate_artifact_document(
            {"format_version": 1},
            [],
            current_version=2,
            migrations=(),
            artifact_name="test artifact",
        )


def test_artifact_migration_rejects_non_sequential_definition() -> None:
    with pytest.raises(ValueError, match="advance exactly one version"):
        ArtifactMigration(
            source_version=1,
            target_version=3,
            migrate=lambda document: document,
        )
