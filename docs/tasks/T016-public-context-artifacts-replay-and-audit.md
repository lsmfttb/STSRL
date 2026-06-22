# T016: Public-Context Artifacts, Replay, And Audit

Status: `BLOCKED` by T015.

## Objective

Persist the settled T015 sanitized public context through current artifacts,
portable replay, and coverage auditing without guessing missing history or
provenance.

## Current Main Baseline

T003 has sequential migration infrastructure, T004 has portable source-trace
restores, and T005 has fixed cohorts. Their current records explicitly declare
public context unavailable. T015 will provide the in-memory schema and history
contract; none may be persisted before that contract is stable.

## Dependencies

- T003, T004, T005, T011, T014, and T015 must be complete.

## Scope

- Add sequential migrations and current-schema writers for public context in
  checkpoint manifests, decision records, trainer inputs, model-input packing,
  and fixed cohorts/reports where applicable.
- Update portable replay to compare sanitized Boss, map/routes, persistent
  resources, typed history, and occurrence-disambiguated candidate actions at
  the recorded battle start. Mismatch must fail explicitly.
- Add a WSL audit that counts one current screen per decision, reports screen
  coverage, action-set parity, context completeness/missingness, replay
  mismatches, and forbidden-field/run/schema failures.
- Preserve explicit loss declarations when legacy data cannot reconstruct
  context. Writers emit only current schema.

## Out Of Scope

- Changing the T015 context meaning, adding native projection fields, learned
  models, resource-value heads, or constructed battle starts.

## Design Constraints

- Readers migrate before business logic and never fill missing context with
  inferred history, map data, or provenance.
- Portable records serialize no raw native checkpoint/object and retain source
  action occurrence identities.
- Audit success requires no run, schema, forbidden-field, action-parity, or
  replay errors. Unseen screens remain named coverage gaps.

## Deliverables

- Artifact schema versions/migrations, propagation tests, and explicit legacy
  loss reporting.
- Portable replay/context comparison and tests.
- Focused command workflow, WSL audit, coverage report, and fixtures.

## Acceptance Criteria

- Current artifacts round-trip the T015 context/version/missingness without
  rereading unrestricted raw snapshots.
- Replaying a recorded source trace reproduces all comparable sanitized public
  context or returns a named mismatch.
- Legacy records retain an explicit unavailable/loss declaration; no current
  writer uses `public_context_status="unavailable"` as a substitute for a
  required context object.
- The WSL audit reports one screen per decision, candidate parity, exact
  coverage gaps, and fails on every required error class.

## Required Verification

Run the standard local gates, focused artifact/migration/replay tests, and a
WSL public-context audit against the accepted T014/T015 patch stack. The PR
report must list observed/unobserved screens, migration losses, context and
candidate parity results, replay result, provenance, and all failures.

## Legacy Reference

Consult former T007 artifact and audit code selectively. It is not an
acceptance reference; its known coverage and audit defects remain rejected.

## PR Report

Include artifact versions/migrations, loss inventory, replay comparisons,
screen/action coverage, exact local/WSL results, dependency identities, known
limitations, and unmet criteria.
