# T038: A20 Source Drift Audit

## Objective

Diagnose why current search-controlled A20 source generation fails to reproduce
the historical Boss/Act2 reachability result, if T037 does not recover that
coverage at meaningful scale.

This task decides whether the gap is caused by non-combat driver behavior,
battle survival/search behavior, simulator/source changes, runtime budget, or
an unresolved interaction.

## Current Main Baseline

T031 and T036 stayed Act 1 only. T037 is the scale-up that must run before this
audit becomes executable. Historical 2026-06-14 evidence reached 35 Act 1 Boss
starts and one Act 2 battle start over 1,000 A20 terminal runs with a
20-simulation no-potion Oracle-like battle controller.

## Dependencies

- T037 is complete and under-reaches Boss/later-act coverage, or T037 explicitly
  recommends this audit.

## Scope

- Compare current T037 source-run summaries against the 2026-06-14 historical
  evidence using only public/reportable metadata.
- Report terminal floors, battles per run, loss floors, act progression, room
  types, encounter ids, reward-screen outcomes, boss relic choices, treasure
  take/leave behavior, potion discard/use behavior, key behavior, and map-route
  reachability where available.
- Compare controller provenance, search budget, action space, non-combat driver
  version/config, seed handling, step caps, and pinned simulator source identity.
- Identify whether the current non-combat driver is failing to keep legal
  low-probability branches reachable, or whether runs are dying before those
  branches matter.
- Recommend one follow-up: non-combat driver calibration, battle search budget
  adjustment, constructed/paired supplements, or an Act-1-only diagnostic
  training refresh.

## Out Of Scope

- Training a neural non-combat policy.
- Creating one deterministic route or pruning legal stochastic branches.
- Changing game mechanics locally.
- Treating historical artifacts as current contracts.

## Acceptance Criteria

- The report separates driver behavior, battle survival, simulator identity, and
  runtime-scale explanations.
- Missing metadata is explicit rather than guessed.
- The recommended follow-up is concrete enough to become a task without relying
  on temporary artifacts.

## Required Verification

Run documentation checks and `git diff --check` for a report-only PR. If code
changes are made, run the standard local gates from `docs/tasks/README.md`.

## PR Report

The PR must report task ID, consumed T037 artifact identities, historical
material consulted, comparison tables, missing metadata, diagnosis, recommended
next task, verification results, and documentation impact.
