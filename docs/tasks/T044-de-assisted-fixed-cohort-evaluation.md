# T044: De-Assisted Fixed-Cohort Evaluation

## Objective

Evaluate whether models trained from assisted data can help search, or at least
avoid degrading search, on low-assistance and unassisted restored battle
cohorts.

This task is an evaluation gate. It determines whether assisted training
produces useful search guidance under less assisted distributions; it is not a
promotion gate unless the task is later revised with explicit promotion
criteria.

## Current Main Baseline

T029 and T035 compared model-guided Oracle-like search against baseline search
on small fixed cohorts and found no outcome improvement. T043 is expected to
produce diagnostic public-information checkpoints trained from assisted source
coverage with policy, value, and structured-resource targets.

## Dependencies

- T043 is complete.
- T025, T026, T028, T029, T035, and T042 remain current comparison and source
  distribution contracts.

## Inputs And Artifacts

Inputs must include explicit T043 checkpoint/trainer provenance and fixed
cohorts from unassisted or low-assistance source distributions, with source
identity, distribution tag, assistance schedule, regeneration commands, and
SHA-256 identities.

Do not use temporary T043 smoke outputs, local worktree checkpoints, or
leftover cohorts as implicit inputs.

## Scope

- Build or consume fixed cohorts for:
  - unassisted natural/expert-driver source distributions;
  - low-assistance distributions such as `assist_hp25` or `assist_hp50`;
  - stronger assistance distributions only as separately labeled diagnostics.
- Compare on identical restored starts:
  - baseline Oracle-like search;
  - model-guided search using T043 checkpoints;
  - raw policy controller where the contract supports it;
  - expert/scripted policy baseline where available.
- Report natural-weighted, encounter-macro, room-type-macro, act-level, and
  assistance-level aggregates separately.
- Report win/loss, terminal HP, structured terminal resources, potion deltas,
  model calls, native simulator steps, root visits, wall-clock cost, restore
  failures, truncations, root mapping failures, and controller errors.

## Out Of Scope

- New training.
- New assisted source generation.
- Live-game validation.
- Promotion to default controller without a later explicit promotion task.
- Collapsing assisted and natural distributions into one headline number.

## Design Constraints

- Equal-source/equal-budget comparison is mandatory.
- Assistance level and distribution kind must be preserved in reports but must
  not be consumed as normal controller inputs.
- Oracle-like search remains `full_simulator_state_oracle_like`.
- Raw policy and model-guided comparisons must preserve checkpoint/trainer
  provenance and fail closed on action identity mismatches.
- Learned models are promoted only by a future task with a credible promotion
  gate over held-out or fixed evaluation.

## Deliverables

- Fixed-cohort selection or consumption workflow for unassisted and
  low-assisted distributions.
- Comparison report including baseline search, model-guided search, raw policy,
  and expert/scripted policy where available.
- Tests for equal-source comparison, assistance/distribution separation,
  checkpoint compatibility, action identity matching, telemetry, and failure
  accounting.
- WSL restored-battle evaluation evidence with explicit artifact paths and
  hashes.

## Acceptance Criteria

- Every compared controller runs on identical restored source starts with
  equal configured search budgets where applicable.
- Reports keep unassisted, low-assisted, and strong-assisted distributions
  separate.
- All checkpoint, trainer-input, cohort, and source-pool identities are
  explicit and reproducible.
- A lack of improvement is accepted only as diagnostic evidence, not as a
  controller promotion.
- Promotion language is absent unless a future task has defined and satisfied
  a promotion gate.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused comparison
tests, task-doc checks, and `git diff --check`.

Before WSL evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL restored-battle evaluation with explicit shards and parallel workers if
the stage exceeds smoke/debug scale. The PR must report commands,
shard/worker counts, cohort/source-record ranges, wall-clock cost, artifact
hashes, and any single-worker reason per stage.

## Legacy Reference

Consult T025, T026, T028, T029, T035, T042, and T043. Do not reuse old smoke
cohorts or checkpoints without explicit current-schema provenance.

## PR Report

The PR must report task ID, cohort identities, source distributions,
assistance levels, checkpoint identities, controller definitions, comparison
aggregates, telemetry, failures, artifact hashes, WSL shard/worker/runtime
evidence, verification commands, known limitations, and documentation impact.
