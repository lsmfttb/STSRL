# T030: M1 Model-Guided Search Sandbox Synthesis

Status: `BLOCKED`.

## Objective

Close the M1 model-guided Oracle search sandbox by producing a synthesis report
and follow-up task recommendations.

The result should decide whether the next implementation work should improve
model-guided Oracle search, collect broader A20 data, or move toward
normal-information belief-search prerequisites.

## Current Main Baseline

After T029, `main` will have telemetry, checkpoint inference, teacher
calibration, a model-guided Oracle search controller, and a fixed-cohort
comparison report. The remaining gap is a maintainer-owned synthesis that
turns these artifacts into the next batch of task boundaries without treating
diagnostics as promotion evidence.

## Dependencies

- T027 and T029 are complete.

## Scope

- Add or update maintainer documentation with an M1 synthesis summary.
- Summarize teacher calibration, controller telemetry, fixed-cohort comparison,
  failure modes, coverage gaps, and information-regime boundaries.
- Recommend the next task batch, such as deeper model-guided search,
  broader A20 data collection, public-history encoders, or
  public-consistent hidden-future sampling.
- Mark superseded M1 plan text as historical if needed.

## Out Of Scope

- Feature implementation.
- Merging experiment artifacts, checkpoints, large datasets, or game files.
- Declaring broad training ready unless prior reports satisfy the explicit
  scale/distribution gate.
- Promoting a controller based only on smoke-scale evidence.

## Design Constraints

- Project-level status and task specifications remain maintainer-owned.
- Keep Oracle-like, normal-information, and live-game evidence separate.
- Preserve exact artifact identities and dates for any reported evidence.
- Do not rewrite history documents as current contracts.

## Deliverables

- Updated roadmap/current-status/task-index documentation.
- A concise M1 synthesis section or document with evidence and limitations.
- Draft task entries for the next batch, left `DRAFT`, `BLOCKED`, or `READY`
  according to actual prerequisites.

## Acceptance Criteria

- Documentation accurately reflects completed M1 capabilities and remaining
  gaps.
- No future task is marked `READY` unless its dependencies are merged and its
  acceptance criteria are objective.
- The synthesis does not claim normal-information, live-game, broad-training,
  or controller-strength evidence beyond what reports support.

## Required Verification

Run documentation consistency scans for stale task states and broken references.
Run `git diff --check`.

Code tests are not required unless the task edits code.

## Legacy Reference

Use current merged M1 reports and task PRs only. Historical files may be cited
as past decisions, not current contracts.

## PR Report

The PR must summarize documentation changes, evidence sources, unresolved
risks, and proposed next task batch.
