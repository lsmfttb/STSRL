# T027: Teacher Guidance Calibration Report

## Objective

Add an offline calibration report that compares checkpoint guidance against
T023/T024 Oracle teacher targets.

This task answers whether a diagnostic checkpoint is learning teacher-action
and soft-visit signals well enough to be worth plugging into search, without
implementing a controller or claiming game strength.

## Current Main Baseline

Current `main` has T023 teacher artifacts, T024 teacher-targeted trainer input,
optional PyTorch checkpoints, and the T026 reusable checkpoint inference
contract. The remaining gap is an artifact-level report that measures
agreement, ranking, cross-entropy, calibration, and coverage against
Oracle-like teacher targets.

## Dependencies

- T026 is complete.
- T023 and T024 are complete.

## Scope

- Add a versioned report, for example
  `teacher-guidance-calibration-report-v1`.
- Load a T024 trainer-input artifact and one or more compatible checkpoints.
- Compare model action scores against explicit policy targets, including
  one-hot teacher actions and optional soft visit distributions.
- Report top-1/top-k agreement, cross-entropy or KL-style diagnostics,
  target-kind/source summaries, source coverage, information regimes, and
  skipped rows.
- Keep behavior-action agreement separate from teacher-target agreement.

## Out Of Scope

- Training checkpoints.
- Running simulator battles.
- Search-controller integration.
- Promotion, benchmark, live-game, or normal-information claims.

## Design Constraints

- Teacher-derived targets remain `full_simulator_state_oracle_like`.
- Mixed target kinds must be rejected or separately reported; do not average
  incompatible targets silently.
- Stable source identity and repeated-row weight must remain separate.
- Missing structured outcomes or public context remain explicit.

## Deliverables

- Calibration report builder, formatter, and optional CLI command.
- Tests for teacher one-hot targets, soft visit targets, mixed target failure,
  behavior-action separation, checkpoint mismatch failure, and deterministic
  output.

## Acceptance Criteria

- The command/report loads current T024 trainer input and compatible
  checkpoint(s), computes deterministic calibration metrics, and preserves
  target provenance.
- The report distinguishes behavior action, teacher action, soft target, and
  model score.
- Oracle-like supervision is clearly labeled as not normal-information,
  broad-training, live-game, or controller-strength evidence.
- Invalid checkpoint/trainer mismatches fail closed.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`.

Run focused calibration tests. If a real T024 smoke checkpoint exists outside
the repository, include an optional artifact-level smoke command and summarize
metrics without checking artifacts into the repo.

## Legacy Reference

Consult T023/T024 artifacts and T026 inference code. Do not port legacy
training experiments wholesale.

## PR Report

The PR must report schema id/version, input artifact identities, checkpoint
identities, target kinds/sources, calibration metrics, skipped rows, evidence
boundary, and exact verification commands.
