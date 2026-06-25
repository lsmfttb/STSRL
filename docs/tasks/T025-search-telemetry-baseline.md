# T025: Search Telemetry Baseline

Status: `DONE` via PR #25, merged 2026-06-25.

## Objective

Add a versioned, reusable telemetry surface for current Oracle-like search and
fixed restored-battle evaluation.

This task closes the gap between having Oracle search outputs and being able to
compare future model-guided search at equal budget, wall-clock, simulator-step,
and model-call cost.

## Current Main Baseline

Current `main` has fixed structural battle evaluation from T005, Oracle-like
native search from T006, trainer/checkpoint plumbing from T009/T024, and
structured A20 teacher artifacts from T021--T024. Search reports contain useful
root statistics, but there is no shared current schema for per-decision search
telemetry across baseline and future model-guided controllers.

## Dependencies

- T005, T006, T009, T017, T020, and T024 are complete.

## Scope

- Add a current telemetry schema for search decisions, for example
  `search-decision-telemetry-v1`.
- Capture available native search statistics such as requested budget, root
  visits, root action count, native simulator steps, wall-clock seconds, root
  value spread or decision gap, unsearched actions, and mapping failures.
- Represent currently unavailable telemetry, such as tree depth or uncertainty
  if not exposed by the native API, as explicit unavailable fields.
- Attach telemetry to Oracle search controller provenance and fixed-evaluation
  per-battle records without changing action-selection behavior.
- Add deterministic formatting for aggregate telemetry summaries.

## Out Of Scope

- Model-guided search, checkpoint loading, or model calls.
- Native `sts_lightspeed` API changes.
- Controller-strength claims or benchmark conclusions.
- Gymnasium, Stable-Baselines3, or new mandatory dependencies.

## Design Constraints

- `sts_lightspeed` remains the authoritative game and search substrate.
- The current Oracle search remains `full_simulator_state_oracle_like`.
- Missing native fields must be explicit; do not infer tree statistics from
  unrelated values.
- Keep CLI modules limited to parsing/routing and put reusable telemetry logic
  below command handlers.
- Preserve existing fixed-evaluation artifact compatibility through sequential
  migrations if schemas are extended.

## Deliverables

- Versioned telemetry dataclasses/helpers and JSON-safe serialization.
- Oracle search and fixed-evaluation report integration.
- Aggregate formatter for telemetry totals and per-decision distributions.
- Focused tests covering serialization, missing fields, aggregate summaries,
  fixed-evaluation propagation, and unchanged action selection.

## Acceptance Criteria

- Current Oracle search decisions emit telemetry under a versioned schema.
- Fixed restored-battle evaluation records preserve telemetry for each search
  decision and aggregate it without changing win/loss behavior.
- Model calls are reported as zero for the current baseline.
- Missing or unsupported native telemetry is explicit and deterministic.
- Legacy or prior reports still load or fail with an intentional migration
  message rather than silently changing meaning.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`.

Run focused telemetry and fixed-evaluation tests added or touched by the task.

Run a WSL smoke fixed-evaluation or Oracle-search command against the pinned
`sts_lightspeed` source and report the telemetry summary. The task may reuse a
small existing fixed cohort or smoke artifact outside the repository.

## Legacy Reference

Consult current merged T005/T006/T021--T024 code and reports. The legacy
integration branch may be inspected only for formatting ideas, not wholesale
porting.

## PR Report

The PR must report schema id/version, telemetry fields, unavailable fields,
local and WSL verification, compatibility impact, and confirmation that
baseline action selection did not intentionally change.
