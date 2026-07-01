# T047: Root-Prior Guided Search Comparison

## Objective

Evaluate whether T043 public checkpoint priors improve Oracle-like search
sample efficiency when they influence native root playout allocation through
the T046 surface, rather than only changing post-search root selection.

This task is a fixed-cohort comparison. It may report improvement, tie, or
regression, but it must not promote a controller or claim normal-information,
live-game, broad-training, natural A20, or final-agent strength.

## Current Main Baseline

T046 added the native `StepSimulator.battle_search_with_root_priors` surface,
STSRL adapter validation, and a `native-root-prior-allocation-report-v1` smoke
workflow. The accepted smoke showed uniform allocation `[4, 4, 4, 4, 4]` and
one-hot allocation `[16, 1, 1, 1, 1]` on one generated Cultist battle at a
20-playout root budget, with zero root mapping failures.

T044 compared baseline Oracle-like search, post-search
`model_guided_oracle_search_v2`, raw checkpoint policy, and a scripted public
baseline on de-assisted fixed cohorts. The accepted smoke evidence did not
show model-guided search improvement over baseline. T045 classified the
failure as primarily an `integration-too-late` signal, with
`distribution-mismatch` and `model-too-weak` also active.

The current gap is that T046 proves the native allocation mechanism exists but
does not test whether learned checkpoint priors improve matched fixed-cohort
outcomes or compute efficiency.

## Dependencies

- T046 is complete.
- T043 and T044 are complete.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts, not temporary worktree
leftovers:

- a T043-compatible public checkpoint and its checkpoint provenance, trainer
  input identity, bridge report identity, teacher artifact identity, and
  manifest identity;
- one or more fixed cohorts or T044-compatible de-assisted comparison inputs
  with source/cohort identities, assistance provenance, restore contract, and
  SHA-256 hashes;
- the current pinned `sts_lightspeed` source manifest containing the T046
  `native_root_prior_allocation` capability.

The primary output is a versioned
`root-prior-guided-search-comparison-v1` report, plus a concise formatted
summary. Generated comparison reports remain under ignored `artifacts/` paths
unless a compact fixture is needed for tests.

If the PR uses retained local T043/T044 artifacts, it must name stable ignored
paths, schema versions, SHA-256 hashes, compatibility requirements, and
regeneration commands. If the artifacts are regenerated, the PR must report
commands, worker/shard counts, record ranges, wall-clock costs, and hashes per
the source task contracts.

## Scope

- Add a root-prior guided Oracle-like search controller or evaluation wrapper
  that scores the current public decision context with a T043-compatible
  checkpoint, maps legal action probabilities to occurrence-safe stable action
  identities, validates priors, calls T046 native root-prior allocation, and
  selects from the resulting native root rows using an explicit native
  root-selection rule.
- Compare matched restored starts across at least these arms:
  - baseline Oracle-like `battle_search`;
  - post-search `model_guided_oracle_search_v2`;
  - native root-prior allocation using the same checkpoint priors and the same
    native root budget;
  - optional uniform root-prior allocation as an allocation-surface diagnostic.
- Keep native simulation budget, checkpoint identity, action-space
  configuration, potion inclusion, root-selection rule, source identity,
  assistance provenance, and information regime explicit for every arm.
- Report battle win/loss, terminal absolute current HP, structured resource
  outcomes, restore status, controller errors, root mapping failures,
  allocation metadata, native simulator steps, model calls, wall-clock cost,
  and model prior summaries per decision.
- Aggregate results separately as natural-weighted, encounter-macro,
  room-type-macro, assistance-level, act, room type, and encounter summaries
  where the cohort exposes those fields.
- Keep CLI modules limited to parsing/routing; reusable comparison logic must
  live below the command layer.

## Out Of Scope

- New native `sts_lightspeed` API work beyond consuming the T046 surface.
- New source generation, teacher collection, bridge generation, checkpoint
  training, or calibration.
- Learned leaf values, Python callbacks inside native search, tree reuse,
  uncertainty-aware allocation, or normal-information belief search.
- Raw neural policy promotion or replacing scripted/search controllers.
- Broad A20 training readiness, natural A20 performance, live-game validation,
  final-agent claims, or controller promotion.

## Design Constraints

- All compared search arms remain `full_simulator_state_oracle_like`.
- The comparison must use identical restored starts across arms and fail closed
  on source/cohort mismatches, restore failures that invalidate an arm,
  checkpoint provenance mismatch, mixed information regimes, unsupported
  schemas, or missing required arms.
- Search budget equality is mandatory for the baseline, post-search
  model-guided, and native root-prior allocation arms. Report model calls
  separately from native simulator steps and wall-clock time.
- Model priors are allocation hints only in the native root-prior arm. Do not
  also blend model probabilities into final root selection unless a separate
  explicitly named diagnostic arm is added.
- Preserve occurrence-safe action identity mapping for duplicate cards,
  targets, potions, and end-turn actions.
- Missing allocation metadata, root mapping failures, invalid priors,
  unsearched legal actions, and unavailable structured outcomes must be
  explicit report fields.
- Any large or long-running WSL restored-evaluation or comparison stage must
  use explicit sharding and parallel workers by default. On the current
  16-logical-core maintainer machine, use 16 workers unless the PR reports a
  resource or tooling reason for fewer.

## Deliverables

- A versioned `root-prior-guided-search-comparison-v1` artifact schema, writer,
  reader/validator, and formatted summary.
- A command or command workflow for producing the comparison from explicit
  checkpoint and fixed-cohort inputs.
- Root-prior guided search controller/evaluation wrapper plumbing that consumes
  the T046 adapter surface without changing existing baseline search behavior.
- Focused tests for prior mapping, invalid prior failure, matched-source
  validation, budget equality, required-arm validation, aggregation, no-promotion
  wording, and report schema compatibility.
- WSL smoke or scale evidence over explicitly reported fixed cohorts, budgets,
  artifact paths, hashes, worker/shard counts, and wall-clock costs.

## Acceptance Criteria

- The command rejects unsupported schemas, missing required arms, mixed
  information regimes, source/cohort mismatches, checkpoint provenance
  mismatches, budget mismatches, invalid priors, and malformed allocation
  metadata.
- Every successful compared battle has baseline, post-search model-guided, and
  native root-prior allocation rows for the same restored source start.
- The report includes per-arm battle outcome, terminal absolute HP, structured
  resource status, native simulator steps, wall-clock cost, model-call count,
  root mapping failures, unsearched legal-action counts, allocation metadata,
  checkpoint identity, source identity, and information regime.
- Aggregate summaries keep natural-weighted, encounter-macro, room-type-macro,
  assistance-level, act, room-type, and encounter-id views separate where
  available.
- The result explicitly states whether native root-prior allocation improved,
  tied, or regressed versus baseline and post-search model-guided search at
  equal native root budget. It must not treat smoke-scale evidence as
  promotion.
- Existing baseline `battle_search`, T046 smoke, and post-search
  model-guided-search behavior remain constructible for diagnostics.
- The PR makes no normal-information, live-game, broad-training,
  controller-promotion, natural A20 performance, or final-agent claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T047 tests,
task-doc checks, and `git diff --check`.

Before WSL comparison evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Also run and report the PyTorch/native runtime alignment probe from
[`../sts_lightspeed_wsl_spike.md`](../sts_lightspeed_wsl_spike.md) with the
same WSL Python interpreter and `build-py` path used by the comparison. The
probe must show one runtime that imports `torch`, imports `slaythespire`, and
exposes both `StepSimulator.battle_search` and
`StepSimulator.battle_search_with_root_priors`. A pinned source verifier pass
alone is not sufficient T047 evidence because it does not prove the active WSL
runtime is torch-capable.

Run a WSL root-prior guided fixed-cohort comparison on explicitly reported
checkpoint, cohort, budget, output path, shard count, worker count, and record
ranges. If the PR adds a named CLI command, the PR must report the exact
command. A representative shape is:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-root-prior-guided-search-comparison --fixed-cohort PATH --search-guidance-checkpoint PATH --search-budget 20 --comparison-report PATH --workers 16 --log-file -"
```

If a stage is kept single-worker, the PR must state that it is smoke/debug
scale or name the concrete resource/tooling reason, plus wall-clock cost.

## Legacy Reference

Consult T026 for checkpoint inference, T028/T035 for post-search
model-guided root selection, T041 for root-row mapping repair patterns, T044
for de-assisted fixed-cohort comparison, T045 for the failure taxonomy, and
T046 for native root-prior allocation. Do not port unrelated legacy search or
local mechanics code.

## PR Report

The PR must report task ID, checkpoint identity, trainer/bridge/teacher
provenance, fixed-cohort identities, source manifest identity, comparison arm
labels, budgets, root-selection rules, action-space configuration, artifact
paths and SHA-256 hashes, worker/shard counts, record ranges, wall-clock
costs, per-arm aggregate summaries, whether root-prior allocation improved,
tied, or regressed, unavailable diagnostics, verification results,
documentation impact, known limitations, and every unmet acceptance criterion.
