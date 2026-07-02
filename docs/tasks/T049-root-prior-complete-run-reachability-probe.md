# T049: Root-Prior Complete-Run Reachability Probe

## Objective

Test whether the T048 root-prior guided restored-battle improvement changes
complete-run A20 source reachability when used as the battle child under the
existing separately named non-combat driver.

This task is a source-generation and reachability diagnostic. It must not
promote a controller or claim normal-information, live-game, broad-training,
natural A20, or final-agent strength.

## Current Main Baseline

T048 completed a scale-up of the T047 root-prior guided search comparison on
fixed restored cohorts. The accepted evidence showed root-prior guided
Oracle-like search improving over both baseline Oracle search and post-search
`model_guided_oracle_search_v2` at equal native root budget on two Act-1-heavy
matched fixed cohorts.

That evidence is still `full_simulator_state_oracle_like` restored-battle
evidence. It does not show whether using the root-prior controller during
complete-run source generation changes battle-start coverage, Boss reachability,
later-act reachability, or the distribution available for future teacher or
training work.

The existing T036/T037 complete-run source path can collect
Oracle-search-controlled battle-start pools and build reachability reports, but
it does not yet provide a published current-schema route for collecting those
pools under the checkpoint-dependent root-prior guided battle controller.

## Dependencies

- T048 is complete.
- T036 and T037 remain the current complete-run reachability/source-generation
  contracts.
- T043/T044/T048 provide the checkpoint and retained artifact provenance that a
  root-prior guided controller may consume.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts or reproducible commands, not
temporary worktree leftovers:

- one T048-accepted or otherwise T043-compatible checkpoint with checkpoint,
  trainer, bridge, teacher, manifest, and source-pool provenance;
- the current pinned `sts_lightspeed` source manifest containing
  `native_root_prior_allocation`;
- an exact torch-capable WSL simulator runtime that passes the same-runtime
  PyTorch/native probe for the Python interpreter and `slaythespire` build used
  by the task;
- current complete-run source-generation and A20 coverage/reachability report
  commands.

Generated source pools, shard outputs, coverage reports, reachability reports,
and logs remain under ignored `artifacts/` paths unless a compact fixture is
needed for tests. The PR must report schema ids, paths, record counts,
SHA-256 hashes, worker/shard counts, seed ranges, wall-clock costs, retention
reason, downstream consumers, and deletion conditions for retained artifacts.

## Scope

- Add only the minimal CLI/workflow support needed to collect complete-run
  battle-start pools whose battle child is:
  - baseline Oracle-like search;
  - post-search `model_guided_oracle_search_v2`;
  - root-prior guided Oracle-like search using the same checkpoint priors and
    native root budget.
- Reuse `execute_controlled_run` or the current complete-run advancement path.
- Keep the battle and non-combat controllers separately named and separately
  inspectable in provenance.
- Run a matched-seed A20 reachability probe across the required arms using the
  same non-combat driver, ascension, step cap, action-space configuration,
  native search budget, and root-selection rule.
- Collect at least one non-trivial complete-run source sample per required arm.
  The target is 50 terminal source runs per arm; if runtime or memory prevents
  that target, the PR must report the completed terminal source-run count,
  skipped ranges, wall-clock cost, projected cost to 50, and why the smaller
  result is sufficient only as a bounded probe.
- Build A20 coverage and reachability reports from the generated pools. Report
  battle starts by act, room type, encounter id, Boss/later-act reachability,
  terminal floors, battles per source run, battle outcomes, restore status,
  public-context status, structured-outcome status, source identity, and T009
  broad-training gate cells.
- Compare the result with T037 reachability evidence and T048 fixed-cohort
  evidence, and recommend exactly one next step.

## Out Of Scope

- New native `sts_lightspeed` APIs.
- New checkpoint training, teacher collection, calibration, or broad A20
  training.
- Assisted training repair, de-assisted distribution repair, or non-combat
  ranker work.
- Learned leaf values, Python callbacks inside native search, tree reuse,
  uncertainty-aware allocation, or normal-information belief search.
- Controller promotion, live-game validation, natural A20 performance claims,
  final-agent claims, or treating Oracle-like source reachability as
  normal-information performance.

## Design Constraints

- All compared search arms remain `full_simulator_state_oracle_like`.
- Search budget equality is mandatory for baseline Oracle search,
  post-search model-guided search, and root-prior guided search. Report model
  calls separately from native simulator steps and wall-clock time.
- Model priors are allocation hints only in the root-prior arm. Final root
  action selection must come from native root statistics.
- Preserve occurrence-safe action identity mapping for duplicate cards,
  targets, potions, and end-turn actions.
- The comparison must fail closed on missing checkpoint provenance, mixed
  information regimes, source/cohort mismatches, unsupported schemas, restore
  failures that invalidate an arm, invalid priors, malformed allocation
  metadata, hidden-field leakage, or incomplete controller provenance.
- Large or long-running WSL source-generation, restore/coverage, and
  reachability-report stages must be sharded and run with explicit parallel
  workers by default. On the current 16-logical-core maintainer machine, use
  16 workers unless the PR reports a concrete resource or tooling reason for a
  lower count.

## Deliverables

- Minimal code/CLI support for root-prior guided complete-run source
  collection, if current commands cannot already express it.
- Focused tests for parser/validation/routing, controller provenance,
  information-regime labels, and failure cases.
- Source-pool, coverage, and reachability artifacts or shard manifests for the
  required arms, with reported hashes and regeneration commands.
- A concise PR summary stating whether root-prior guided search improved,
  tied, or regressed complete-run reachability versus both comparison arms at
  equal native root budget.

## Acceptance Criteria

- The exact WSL runtime used for checkpoint-guided source collection passes the
  PyTorch/native same-runtime probe.
- The pinned source verifier passes.
- Required arms use matched seeds, same non-combat driver, same action-space
  configuration, same native root budget, same root-selection rule, and the
  same checkpoint for model-guided and root-prior guided arms.
- Every generated source start preserves complete battle-controller,
  non-combat-controller, source identity, seed, ascension, action-space, search
  budget, checkpoint, and information-regime provenance.
- Coverage and reachability reports fail closed on missing source identity,
  missing pool SHA linkage, corrupted source-run summaries, restore failures,
  malformed provenance, or hidden-field leakage.
- Boss and later-act reachability are reported explicitly, including zero.
- The result states whether complete-run reachability improved, tied, or
  regressed versus baseline Oracle search and post-search model-guided search.
- The PR makes no normal-information, live-game, broad-training,
  controller-promotion, natural A20 performance, or final-agent claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-doc checks, and
`git diff --check`.

Run the same-runtime PyTorch/native probe from
`docs/sts_lightspeed_wsl_spike.md` with the exact Python interpreter and
`slaythespire` build path used by source collection.

Run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL source collection, coverage, and reachability stages on explicitly
reported artifact paths. The PR must include full commands, worker/shard
counts, seed ranges, terminal source-run counts, record counts, output paths,
hashes, wall-clock costs, and any lower-worker or reduced-scale reason.

## Legacy Reference

Consult T036/T037 for complete-run source reachability reporting, T047/T048 for
root-prior guided fixed-cohort comparison, T046 for native root-prior
allocation, and T043/T044 for checkpoint provenance. Do not port unrelated
legacy search, local mechanics, or training code.

## PR Report

The PR must report task ID, controller arms, checkpoint identity,
trainer/bridge/teacher/source provenance, search budgets, root-selection rules,
action-space configuration, non-combat driver, source manifest identity, exact
local and WSL commands, artifact paths and SHA-256 hashes, worker/shard counts,
seed ranges, wall-clock costs, reachability summaries, restore/public-context/
structured-outcome status, T009 gate result, comparison with T037 and T048,
recommended next task, verification results, known limitations, documentation
impact, and every unmet acceptance criterion.
