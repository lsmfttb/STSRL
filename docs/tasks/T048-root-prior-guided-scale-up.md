# T048: Root-Prior Guided Search Scale-Up

## Objective

Scale the T047 root-prior guided search comparison beyond a one-record smoke to
test whether the native root-prior allocation signal is stable on a
non-trivial matched fixed cohort.

This task may report improvement, tie, or regression. It must not promote a
controller or claim normal-information, live-game, broad-training, natural A20,
or final-agent strength.

## Current Main Baseline

T047 added `RootPriorGuidedSearchController`, the
`root-prior-guided-search-comparison-v1` report, and CLI routing for comparing
baseline Oracle search, post-search `model_guided_oracle_search_v2`, and native
root-prior guided search at equal native root budget.

The accepted T047 WSL smoke used a current pinned T046 runtime and one restored
A20 Act-1 Blue Slaver record from fixed cohort `875ea52e3df4cb93`. Baseline
Oracle search and post-search model-guided search both lost the smoke record;
root-prior guided search won it. The evidence was explicitly smoke-scale and
Oracle-like only.

## Dependencies

- T047 is complete.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts, not temporary worktree
leftovers:

- a T043-compatible public checkpoint with checkpoint, trainer, bridge,
  teacher, manifest, and source-pool provenance;
- one or more current pinned T046-compatible fixed cohorts with source/cohort
  identities, restore contract, source distribution summaries, and SHA-256
  hashes;
- the active torch-capable WSL simulator runtime that passes the
  PyTorch/native alignment probe in `docs/sts_lightspeed_wsl_spike.md`;
- the current pinned `sts_lightspeed` source manifest containing the
  `native_root_prior_allocation` capability.

The primary output is one or more
`root-prior-guided-search-comparison-v1` reports plus concise formatted
summaries. Generated comparison reports remain under ignored `artifacts/`
paths unless a compact fixture is needed for tests.

If retained local T047 artifacts are reused, the PR must name their stable
ignored paths, schema versions, SHA-256 hashes, compatibility requirements,
and regeneration commands. If new artifacts are generated, the PR must report
commands, worker/shard counts, record ranges, wall-clock costs, and hashes per
stage.

## Scope

- Run the T047 comparison on at least one non-trivial current-compatible fixed
  cohort, not just a single selected record.
- Use the required three arms from T047:
  - baseline Oracle-like `battle_search`;
  - post-search `model_guided_oracle_search_v2`;
  - native root-prior allocation using the same checkpoint priors and native
    root budget.
- Keep native simulation budget, checkpoint identity, action-space
  configuration, potion inclusion, root-selection rule, source identity,
  assistance provenance, and information regime explicit for every arm.
- Preserve and report per-battle outcomes, terminal absolute current HP,
  structured resource outcomes, restore status, controller errors, root
  mapping failures, allocation metadata, native simulator steps, model calls,
  wall-clock cost, and model prior summaries.
- Aggregate results separately as natural-weighted, encounter-macro,
  room-type-macro, assistance-level, act, room type, and encounter summaries
  where the cohort exposes those fields.
- If runtime or memory constraints force smaller evidence than the full chosen
  cohort, report the skipped record ranges and concrete reason.

## Out Of Scope

- New native `sts_lightspeed` API work.
- New checkpoint training, teacher collection, or calibration.
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
  schemas, missing required arms, invalid priors, or malformed allocation
  metadata.
- Search budget equality is mandatory for the baseline, post-search
  model-guided, and native root-prior allocation arms. Report model calls
  separately from native simulator steps and wall-clock time.
- Model priors are allocation hints only in the native root-prior arm. Do not
  blend model probabilities into final root selection.
- Preserve occurrence-safe action identity mapping for duplicate cards,
  targets, potions, and end-turn actions.
- Any large or long-running WSL restored-evaluation or comparison stage must
  use explicit sharding and parallel workers by default. On the current
  16-logical-core maintainer machine, use 16 workers unless the PR reports a
  resource or tooling reason for fewer. Smaller cohorts should use a worker
  count capped by shard count and record count.

## Deliverables

- At least one `root-prior-guided-search-comparison-v1` report over a
  non-trivial fixed cohort, with hashes and formatted summary.
- A PR report that names checkpoint, trainer, bridge, teacher, manifest,
  source-pool, source-cohort, fixed-cohort, and comparison artifact identities.
- Worker/shard counts, record ranges, wall-clock costs, and single-worker or
  reduced-worker reasons for every WSL stage.
- Focused code changes only if needed to make the scale-up reproducible,
  bounded-memory, or reviewable.

## Acceptance Criteria

- The PyTorch/native runtime alignment probe passes for the exact WSL Python
  and `build-py` path used by the comparison.
- The pinned source verifier passes.
- The comparison report has no schema, source-match, required-arm,
  information-regime, budget, checkpoint-provenance, restore, controller,
  root-mapping, invalid-prior, or allocation-metadata failures.
- Every successful compared battle has baseline, post-search model-guided, and
  native root-prior allocation rows for the same restored source start.
- The result explicitly states whether native root-prior allocation improved,
  tied, or regressed versus baseline and post-search model-guided search at
  equal native root budget, and separates natural-weighted,
  encounter-macro, room-type-macro, assistance-level, act, room-type, and
  encounter-id summaries where available.
- The PR makes no normal-information, live-game, broad-training,
  controller-promotion, natural A20 performance, or final-agent claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-doc checks, and
`git diff --check`.

Run the PyTorch/native runtime alignment probe from
`docs/sts_lightspeed_wsl_spike.md` with the exact runtime used by the scale-up.

Run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run the root-prior guided fixed-cohort comparison with explicitly reported
checkpoint, cohort, budget, output path, shard count, worker count, and record
ranges. A representative shape is:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=TORCH_PATH:/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src LD_LIBRARY_PATH=TORCH_LIBS python3 -m sts_combat_rl.cli --lightspeed-root-prior-guided-search-comparison COHORT_PATH --model-guided-oracle-checkpoint CHECKPOINT_PATH --search-budget 20 --workers 16 --shards 16 --root-prior-guided-search-comparison-scale fixed --root-prior-guided-search-comparison-report REPORT_PATH --log-file -"
```

If a stage is kept single-worker or uses fewer workers than available records,
the PR must state that it is smoke/debug scale or name the concrete
resource/tooling reason, plus wall-clock cost.

## Legacy Reference

Consult T047 for the report schema and comparison command, T046 for native
root-prior allocation, T044 for fixed-cohort comparison reporting, and T043 for
checkpoint provenance. Do not port unrelated legacy search or local mechanics
code.

## PR Report

The PR must report task ID, checkpoint identity, trainer/bridge/teacher
provenance, fixed-cohort identities, source manifest identity, comparison arm
labels, budgets, root-selection rules, action-space configuration, artifact
paths and SHA-256 hashes, worker/shard counts, record ranges, wall-clock
costs, per-arm aggregate summaries, whether root-prior allocation improved,
tied, or regressed, unavailable diagnostics, verification results,
documentation impact, known limitations, and every unmet acceptance criterion.
