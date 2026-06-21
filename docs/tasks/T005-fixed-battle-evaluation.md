# T005: Fixed Structural Battle Evaluation

Status: `READY`.

## Objective

Create immutable, portable fixed battle cohorts and a controller evaluation
workflow. Later search or model changes must be compared on the same restored
battle starts rather than by average floor from different natural runs.

## Current Main Baseline

T004 provides current-schema natural battle-start pools. Each record has a
portable source seed and occurrence-disambiguated action trace, structural
metadata, source-controller provenance, and a fresh-adapter restore verifier.
The pool's source checkpoints are natural A20 starts, but it does not yet have
a fixed-cohort artifact or an evaluation runner.

## Dependencies

- T004 is complete.

## Scope

- Define a versioned, portable fixed-cohort artifact selected from one natural
  battle-start pool. It must retain its source-pool format/version identity,
  source checkpoint identities, action traces, structural metadata, source
  distribution kind, selection configuration, and deterministic selection
  seed. Native checkpoint payloads must not be serialized.
- Select without replacement using only the default structural stratum
  `(ascension, act, room_type, encounter_id)`. A configuration may name a
  per-stratum quota and optional required structural strata; it must never use
  deck, relic, HP, outcome, or apparent-winnability filters.
- Report every observed, under-covered, malformed, and explicitly required but
  absent stratum. When no required-strata configuration is supplied, report
  that unobserved global strata are unknown rather than claiming complete
  encounter coverage.
- Restore every selected record in a fresh adapter and play one bounded battle
  with one explicit `OnlineController`, reusing the canonical context building,
  action-space filtering, legal-index validation, and action-selection
  semantics. A specialized battle loop must not choose a hidden default policy.
- Produce a versioned evaluation report with per-battle source identity,
  restoration method, structural stratum, controller provenance and information
  regime, action-space configuration, termination status, terminal absolute
  current HP, HP loss, decision count, simulator-step count, wall-clock time,
  and controller-provided compute telemetry. Unavailable telemetry is explicit
  (`null` or a named missing field), never reported as zero.
- Aggregate and display natural-weighted, encounter-macro, room-type-macro,
  and per-stratum results separately. Truncations, illegal selections, restore
  failures, and simulator errors remain visible and make a successful
  evaluation claim fail.
- Provide a focused command workflow below `src/sts_combat_rl/commands/`; the
  CLI may only parse and route. The workflow must accept a portable pool,
  cohort/evaluation output paths, deterministic selection configuration, a
  named controller configuration, and explicit maximum battle steps.
- Add sequential migration coverage for any supported fixed-cohort or report
  predecessor. Do not change T004 pool writers to a second current schema.

## Out Of Scope

- Search implementation, search teachers, model training, constructed starts,
  full-run evaluation, or a hand-written list of all game encounters.
- Persistent resource-value labels; until T012 exists, the report may state
  that structured terminal resources are unavailable but must not synthesize a
  scalar reward from them.
- Reporting an Oracle-like controller as normal-information performance.

## Design Constraints

- A cohort is an evaluation artifact, not a resampled training batch. Repeated
  source checkpoints are forbidden, and changing the pool, seed, quota, or
  required strata creates a different cohort identity.
- The restored checkpoint is an opaque simulator mechanism. A controller's
  declared information regime determines what it may inspect; all reports must
  retain that regime. `full_simulator_state_oracle_like` results remain separate
  from normal-information results.
- Evaluation starts each selected portable record from a fresh adapter so an
  in-memory checkpoint cannot accidentally substitute for replay restore.
- Use absolute HP only. A battle is a win only from an authoritative terminal
  outcome; reaching a step limit, leaving the expected battle state, or an
  exception is not a win.
- Persist complete controller provenance and source non-combat/battle
  provenance. A short controller name or a search-budget integer alone is not
  sufficient.
- All output is deterministic for the same portable pool, cohort configuration,
  controller configuration, and evaluation seed, apart from explicitly
  reported wall-clock measurements.

## Deliverables

- Versioned fixed-cohort schema, reader, writer, validator, and migration
  tests.
- Deterministic structural selection and coverage report.
- Restored-battle controller evaluator and versioned result report.
- Focused command workflow and thin CLI route.
- Unit fixtures covering duplicate action identities, incomplete/malformed
  strata, restore failures, illegal controller selections, terminal loss,
  truncation, and separation of all aggregate weightings.

## Acceptance Criteria

- Re-freezing the same valid pool and configuration produces byte-equivalent
  cohort content and the same cohort identity.
- Changing a selection input changes the recorded cohort configuration or
  identity; no selected source checkpoint appears twice.
- A portable cohort loaded in a fresh process restores every selected record by
  seed/action trace before evaluation. A restore mismatch is a named failure.
- Identical deterministic controller/configuration runs produce identical
  non-timing per-battle results and aggregates.
- Every result has one terminal status from `win`, `loss`, `truncated`, or
  `error`; only authoritative wins count as wins.
- Natural-weighted, encounter-macro, room-type-macro, and per-stratum outputs
  are simultaneously present and cannot be confused in the report.
- Controller provenance, information regime, action-space configuration, and
  unavailable telemetry/resource fields are retained in persisted output.
- Required strata that are absent or below quota are reported without filling
  them with unrelated starts or claiming complete coverage.

## Required Verification

Run the standard local gates from `tasks/README.md`, focused unit tests for the
cohort and evaluator, and a portable-manifest round trip. The pull request must
also run these WSL gates against the current external patch stack:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-start-pool /tmp/t005-pool.jsonl --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-fixed-battle-evaluation /tmp/t005-pool.jsonl --fixed-evaluation-cohort /tmp/t005-cohort.jsonl --fixed-evaluation-report /tmp/t005-report.jsonl --sim-ascension 20 --sim-steps 200 --log-file -"
```

The new fixed-evaluation command must fail nonzero for a restore mismatch,
invalid cohort, illegal selection, or truncated/error result. The PR report
must include the exact cohort count, unique source count, structural coverage,
controller and information regime, action-space configuration, and every
under-covered or missing stratum. A small cohort is a plumbing gate only, not
policy-strength evidence.

## Legacy Reference

Consult selectively:

```text
src/sts_combat_rl/sim/fixed_evaluation_set.py
src/sts_combat_rl/sim/fixed_battle_evaluation.py
tests/test_fixed_evaluation_set.py
tests/test_fixed_battle_evaluation.py
```

The legacy code predates T004's current record/provenance fields and must not
be copied wholesale. In particular, adapt it to source seed/action traces,
fresh-adapter restore, current `OnlineController` provenance, explicit
information regimes, and telemetry-missing semantics.

## PR Report

Include task ID, source-pool/cohort schema versions and identity, implementation
summary, changed compatibility surfaces, exact verification output, structural
coverage and failures, controller provenance/information regime, legacy files
consulted, known limitations, and any acceptance criterion not met.
