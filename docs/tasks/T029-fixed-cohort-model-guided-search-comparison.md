# T029: Fixed-Cohort Model-Guided Search Comparison

Status: `BLOCKED`.

## Objective

Add a fixed-cohort comparison report for baseline Oracle search versus the
T028 model-guided Oracle search controller.

This task creates the first reviewable equal-budget search comparison, while
keeping smoke-scale and Oracle-like limitations explicit.

## Current Main Baseline

Current `main` has fixed structural cohorts, Oracle search, teacher-targeted
checkpoint plumbing, and planned model-guided controller support. It does not
yet have a report that compares baseline and model-guided search on the same
restored starts with shared telemetry.

## Dependencies

- T025 and T028 are complete.

## Inputs And Artifacts

- Required cohort input: one fixed cohort or smoke cohort with explicit schema,
  identity, source-pool provenance, and regeneration command or external/ignored
  path.
- Required checkpoint input: one T028-compatible model-guided controller
  checkpoint with checkpoint identity and trainer-input provenance.
- Required baseline input: the same restored battle starts must be used for
  baseline Oracle search and model-guided Oracle search.
- Generated comparison reports may be written under ignored or external
  artifact paths, but the PR must report schema, provenance, and enough
  identities for reviewers to reproduce or audit them.

This task must not consume an unreported T028 smoke checkpoint, one-off fixed
cohort, or local worktree artifact as an implicit input. If it reuses artifacts
from a previous workflow, it must name the merged artifact contract and provide
regeneration or acquisition commands.

## Scope

- Add a versioned comparison report, for example
  `model-guided-search-fixed-comparison-v1`.
- Evaluate baseline Oracle search and model-guided Oracle search on the same
  fixed or smoke structural cohort.
- Report natural-weighted, encounter-macro, room-type-macro, and per-stratum
  outcomes separately where the cohort supports them.
- Report equal-budget, equal-wall-clock where possible, simulator-step,
  model-call, restore, truncation, and failure telemetry.
- Preserve checkpoint and controller provenance for model-guided runs.

## Out Of Scope

- Claiming controller promotion or A20 strength from smoke-scale data.
- Broad neural training.
- Normal-information or live-game claims.
- New dataset generation beyond a small documented smoke cohort if needed.

## Design Constraints

- Every compared battle must use the same source checkpoint across controllers.
- The report must keep information regimes separate.
- Missing or failed restores must be explicit and not silently dropped from
  denominators.
- Model calls and native simulator steps must be reported separately.

## Deliverables

- Comparison command/report schema and formatter.
- Tests for matched-source evaluation, aggregate separation, telemetry
  propagation, controller provenance, and failure accounting.
- WSL smoke comparison evidence outside the repository.

## Acceptance Criteria

- The report compares both controllers on identical source battle starts.
- It emits separate outcome aggregates and cost telemetry.
- It clearly states whether the run is smoke-scale and Oracle-like.
- Failures, truncations, and missing telemetry are explicit.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`.

Run focused comparison tests and a WSL smoke comparison against pinned
`sts_lightspeed`, using explicitly documented artifacts outside the repository
or ignored paths. The WSL smoke must exercise both compared controller paths on
the same source starts.

## Legacy Reference

Consult T005 fixed evaluation, T006 Oracle search, T025 telemetry, and T028
controller code. Do not port legacy policy-comparison experiments wholesale.

## PR Report

The PR must report schema id/version, cohort identity, controller configs,
checkpoint identity, aggregate outcomes, telemetry, failures, local/WSL
verification, consumed/generated artifact identities and reproduction commands,
and explicit non-promotion evidence boundary.
