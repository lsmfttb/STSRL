# T003: Artifact Provenance Foundation

Status: `DONE`.

## Objective

Establish versioned artifact reading and complete decision provenance before
checkpoint pools, search datasets, or model training add more persistent
formats.

## Scope

- Define a reusable sequential artifact-migration mechanism.
- Define a current decision-record schema that preserves generating controller
  provenance, selected action identity, eligible actions, seed, ascension, and
  distribution/source metadata available on `main`.
- Disambiguate duplicate legal action IDs using occurrence or an equivalent
  stable public identity.
- Update current trainer-input persistence to use explicit current schema
  metadata and sequential legacy migration.
- Add legacy fixtures and migration regression tests.
- Move task-owned artifact workflow code out of `cli.py` if needed.

## Out Of Scope

- Battle-start pools, fixed evaluation, search records, PyTorch checkpoints,
  public run history, or constructed-state transforms.
- Guessing missing legacy provenance.
- Permanent legacy-version conditionals in current business logic.

## Acceptance Criteria

- Writers emit only the current schema.
- Readers migrate supported old versions sequentially before business logic.
- Migrations report unrecoverable fields instead of inventing values.
- Duplicate action IDs can be replayed unambiguously.
- T002 controller provenance survives persistence and round trip.
- All required local checks pass.

## Required Verification

Run the standard local checks plus focused legacy migration and duplicate-action
tests. No WSL gate is required unless simulator action identity changes.

## Legacy Reference

Consult selectively:

```text
src/sts_combat_rl/sim/artifact_versioning.py
src/sts_combat_rl/sim/decision_record.py
src/sts_combat_rl/commands/artifact_migration.py
tests/test_artifact_versioning.py
tests/test_decision_record.py
```

## PR Report

Include the current schema version, supported migrations, unrecoverable legacy
fields, and exact verification results.
