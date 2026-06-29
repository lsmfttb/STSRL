# T042: Assisted Complete-Run Source Generation

## Objective

Implement an assisted complete-run source-generation distribution that uses
explicit resource assistance during run advancement to reach broader A20
battle-state coverage.

This extends the T008 constructed-start idea from isolated battle-start
perturbations into complete-run continuation. The output is assisted training
data, not natural A20 performance evidence.

## Current Main Baseline

T008 can construct conservative HP, potion, and encounter supplements for
existing battle starts. T037/T039 provide a durable no-potion source-coverage
contract, but the accepted distribution still has very sparse Act 1 Boss and
Act 2 coverage and no Act 3/4 coverage. T040 added `expert_non_combat_v1`,
which improved Act 1 Boss and later-act source reachability at 1,000 terminal
A20 source runs per arm but still left the broad-training gate closed. T041
repaired the potion-enabled search/action mapping needed for reliable
potion-aware source generation.

## Dependencies

- T040 is complete.
- T041 is complete if any potion-enabled assistance or potion-enabled search
  arm is required by the accepted implementation.
- T008, T016, T017, T036, T037, and T039 remain current contracts.

## Inputs And Artifacts

Inputs must be generated from current `main` commands or explicit
external/ignored paths with schema, provenance, regeneration commands, and
SHA-256 identities. Do not consume another task's temporary smoke outputs as
implicit inputs.

Generated assisted source pools, shards, coverage reports, assistance logs,
restore reports, and reachability reports remain outside the repository unless
they are intentionally small fixtures.

If the generated raw pools or shards are intended as inputs to T043, they must
be written under a stable ignored/local retention path outside any disposable
review worktree, such as `artifacts/t042-assisted-source/` in the main
workspace or a separately documented local artifact root. The PR must include a
lightweight retention manifest or equivalent report with schema, provenance,
SHA-256 hashes, approximate sizes, regeneration commands, compatibility
requirements, downstream consumer, retention reason, and deletion conditions.
If T043 should regenerate rather than consume the raw T042 files, the PR must
say that explicitly and keep only the small report/manifest evidence.

## Scope

- Add an explicit assisted distribution kind, such as `assisted_run`, with
  finer provenance tags for `resource_assisted_run`,
  `expert_driver_assisted_run`, or `oracle_assisted_run` where applicable.
- Implement a versioned assistance schedule with at least:
  - `assist_0`: no assistance, the current baseline;
  - `assist_hp25`: pre-battle HP floor at 25% max HP;
  - `assist_hp50`: pre-battle HP floor at 50% max HP;
  - `assist_hp50_potion_elite_boss`: HP floor plus at least one potion before
    elite/Boss battles when legal;
  - `assist_hp75_potion`: stronger coverage-only assistance, not performance
    evidence.
- Apply assistance only through authoritative simulator support or existing
  accepted transform contracts. Missing support is an explicit unsupported
  assistance result.
- Preserve before/after resources, requested and actual change, source
  identity, assistance version, policy seed, information regime, distribution
  tag, and screen/battle provenance for every assistance decision.
- Continue run advancement after assistance and collect later battle starts,
  rather than emitting only isolated modified starts.
- Report coverage by assistance level: Act 1 Boss starts, Act 2/3/4 starts,
  room type, encounter id where available, battle win/loss, terminal resources,
  restore status, public-context status, structured-outcome status, and T009
  gate status.

## Out Of Scope

- Claiming natural A20, normal-information, live-game, or final-agent
  performance from assisted data.
- Neural training, teacher collection, or checkpoint refresh; that belongs to
  T043.
- De-assisted controller evaluation; that belongs to T044.
- Local reconstruction of HP, potion, encounter, map, event, or reward
  mechanics.
- Replacing visible Act Boss in ordinary assisted training.

## Design Constraints

- Assistance must never leak into `normal_public_policy` model inputs. It may
  appear in provenance, distribution tags, sampling weights, and reports.
- Natural, expert-driver, constructed supplement, assisted-run,
  stratified-training, paired-counterfactual, normal-information, and
  Oracle-like distributions remain separately countable.
- The simulator remains authoritative for state mutation and legality.
- The battle/non-combat controller split remains explicit.
- Large WSL source-generation, restore, coverage, and report stages must be
  sharded and run with explicit parallel workers by default. Choose worker
  counts from the host logical CPU count, capped by shard count and documented
  memory or simulator limits. On the current 16-logical-core maintainer
  machine, use 16 workers by default for each large WSL stage unless the PR
  documents why fewer workers were required.

## Deliverables

- Assisted-run artifact schema, reader/writer/validator, and migrations where
  needed.
- Assistance schedule implementation and provenance.
- Complete-run source-generation workflow with assistance support.
- Coverage/reachability report by assistance level and distribution kind.
- Tests for assistance determinism, no-op/unsupported tagging, hidden-field
  firewall, distribution separation, restore/public-context preservation, and
  non-leakage into normal model inputs.
- WSL source-generation and coverage evidence with explicit artifact paths and
  hashes.

## Acceptance Criteria

- Assistance records preserve before/after resources, requested/actual change,
  source identity, schedule version, policy seed, information regime, and
  distribution tag.
- Assisted rows restore successfully and preserve public context and structured
  outcomes at the accepted artifact scale.
- Assistance fields are absent from normal controller/model-input features.
- Coverage reports show Act 1 Boss and later-act source coverage separately
  for each assistance level, including zero counts.
- At comparable scale, assisted schedules improve Act 2/3/4 source coverage
  over `assist_0` or the PR is not accepted as satisfying the assisted
  coverage objective without a maintainer task-spec revision.
- No natural-performance or normal-information claim is made.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused assisted-run
tests, task-doc checks, and `git diff --check`.

Before WSL evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL source generation, restore/coverage, and report rebuilds with explicit
shards and parallel workers. Scale stages should use the host logical CPU count
as the worker target by default; on the current maintainer machine that means
16 workers, capped only by shard count or documented memory/simulator limits.
The PR must report commands, shard/worker counts, seed/source-run or record
ranges, wall-clock cost, and any lower-worker or single-worker
smoke/debug/tooling-limited reason per stage.

## Legacy Reference

Consult T008, T016, T036, T037, T039, T040, T041, and
`docs/project_architecture.md`. T008 transforms may inform assistance, but
this task must preserve complete-run continuation and distribution separation.

## PR Report

The PR must report task ID, assistance schedules, source controllers, artifact
paths and hashes, source-run scale, shard/worker/runtime evidence, coverage by
assistance level, restore/public-context/structured-outcome status, T009 gate
results, non-leakage checks, verification commands, known limitations, and
documentation impact. It must also state whether raw GB-scale artifacts are
retained for T043, and if so provide the retention manifest/path; otherwise it
must state that downstream tasks should regenerate compatible artifacts from
the documented commands.
