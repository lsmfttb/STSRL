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
`sts_lightspeed`, using artifacts outside the repository or ignored paths.

## Legacy Reference

Consult T005 fixed evaluation, T006 Oracle search, T025 telemetry, and T028
controller code. Do not port legacy policy-comparison experiments wholesale.

## PR Report

The PR must report schema id/version, cohort identity, controller configs,
checkpoint identity, aggregate outcomes, telemetry, failures, local/WSL
verification, and explicit non-promotion evidence boundary.
