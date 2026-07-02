# T050: Root-Prior Reachability Scale-Up And Shard Merge

## Objective

Turn the T049 bounded complete-run root-prior reachability probe into a
reviewable 50-terminal-run-per-arm A20 scale pass by adding the minimal shard
merge/finalization support needed for natural battle-start source pools and
their coverage/reachability evidence.

This task is still a source-generation and reachability diagnostic. It must not
promote a controller or claim normal-information, live-game, broad-training,
natural A20, or final-agent strength.

## Current Main Baseline

T049 extended `--lightspeed-search-battle-start-pool` so complete-run source
collection can use three battle children under the existing separately named
non-combat driver:

- baseline `oracle_search_v1`;
- post-search `model_guided_oracle_search_v2`;
- `root_prior_guided_oracle_search_v1`.

The accepted T049 bounded smoke used matched seeds `1..2`, A20, step cap 500,
`initial_no_potions`, `stochastic-v1`, native root budget 20, and the
T043-compatible checkpoint accepted by T048. It verified command,
provenance, artifact, and WSL runtime plumbing, but reached no Boss or later
act in any arm. It also exposed the remaining operational gap: the current
natural source-pool path has no published shard merge/finalization workflow, so
the 50-terminal-run target would be unnecessarily serial or manually merged.

## Dependencies

- T049 is complete.
- T048 provides the accepted root-prior fixed-cohort evidence and compatible
  checkpoint provenance.
- T036/T037 remain the complete-run reachability and source-generation
  reference contracts.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts or reproducible commands, not
temporary worktree leftovers:

- one T048/T049-accepted T043-compatible checkpoint for the checkpoint-guided
  arms, including checkpoint, trainer, bridge, teacher, manifest, and source
  provenance;
- the current pinned `sts_lightspeed` source manifest containing
  `native_root_prior_allocation`;
- an exact torch-capable WSL simulator runtime that passes the same-runtime
  PyTorch/native probe for the Python interpreter and `slaythespire` build used
  by source collection;
- T049 complete-run source-collection controller arms and A20
  coverage/reachability report commands.

Generated shard pools, merged pools, coverage reports, reachability reports,
manifests, and logs remain under ignored `artifacts/` paths unless a compact
fixture is needed for tests. Any retained raw files must live under a stable
ignored path outside disposable review worktrees and must have a lightweight
manifest with schema ids, paths, record counts, byte counts where practical,
SHA-256 hashes, worker/shard counts, seed ranges, wall-clock costs, retention
reason, downstream consumers, and deletion conditions.

## Scope

- Add the minimal source-pool shard merge/finalization workflow needed to merge
  natural battle-start pool shards for one arm into one current-schema pool.
- Validate shard compatibility before merging: schema/version, source identity,
  ascension, action-space configuration, battle-controller provenance,
  non-combat-controller provenance, search budget, checkpoint identity where
  applicable, information regime, source-run summaries, and record indexes or
  source identities.
- Stream JSONL records during merge. Do not load all shard records into memory
  unless the PR documents a small-fixture-only path.
- Preserve or rebuild a correct merged metadata header, source-run summaries,
  terminal/truncated run counts, record counts, and deterministic output hash.
- Run the T049 three-arm A20 reachability comparison at the target scale:
  50 terminal source runs per arm, matched seeds, A20, step cap, action-space
  configuration, native root budget, root-selection rule where applicable,
  checkpoint, and non-combat driver.
- Shard source collection and coverage/restore stages by default. On the
  current 16-logical-core maintainer machine, use 16 workers unless the PR
  reports a concrete resource or tooling reason for a lower count.
- Build merged coverage and reachability reports from the scale outputs.
- Compare the result with T037 reachability evidence, T048 fixed-cohort
  evidence, and the T049 bounded smoke, then recommend exactly one next task.

## Out Of Scope

- New native `sts_lightspeed` APIs.
- New checkpoint training, teacher collection, calibration, or broad A20
  training.
- Assisted training repair, de-assisted distribution repair, or non-combat
  ranker work beyond the single next-task recommendation.
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
- Keep battle and non-combat controllers separately named and separately
  inspectable in source-pool and reachability provenance.
- Preserve occurrence-safe action identity mapping for duplicate cards,
  targets, potions, and end-turn actions.
- Merge/finalization must fail closed on mixed schema versions, missing or
  mixed source identity, duplicate or malformed source identities, incompatible
  controller provenance, mixed checkpoint identity, malformed source-run
  summaries, unsupported information regimes, or hidden-field leakage.
- Required artifacts must be reproducible by reported commands. Do not use
  another review worktree's smoke files as implicit input.

## Deliverables

- Minimal code/CLI support for natural battle-start source-pool shard
  merge/finalization, with deterministic current-schema output.
- Focused tests for merge compatibility validation, metadata/header rebuilding,
  deterministic output, duplicate/malformed shard rejection, and CLI routing.
- A 50-terminal-run-per-arm A20 scale artifact set for:
  - `oracle_search_v1`;
  - `model_guided_oracle_search_v2`;
  - `root_prior_guided_oracle_search_v1`.
- Merged source-pool, coverage, and reachability artifacts for all required
  arms, plus a manifest recording shard identities and output hashes.
- A concise PR summary stating whether root-prior guided search improved, tied,
  or regressed complete-run reachability versus both comparison arms at equal
  native root budget.

## Acceptance Criteria

- The exact WSL runtime used for checkpoint-guided source collection passes the
  PyTorch/native same-runtime probe.
- The pinned source verifier passes.
- Required arms use matched seeds, same non-combat driver, same action-space
  configuration, same native root budget, same root-selection rule where
  applicable, and the same checkpoint for model-guided and root-prior guided
  arms.
- The scale artifact set covers 50 terminal source runs per arm. A smaller
  result is not acceptable for this task unless the PR stays draft or the task
  document is revised before review.
- Every generated source start preserves complete battle-controller,
  non-combat-controller, source identity, seed, ascension, action-space, search
  budget, checkpoint, and information-regime provenance.
- Merged pools preserve all source records exactly once and report correct
  metadata counts, terminal/truncated run counts, source-run summaries, and
  output hashes.
- Coverage and reachability reports fail closed on missing source identity,
  missing pool SHA linkage, corrupted source-run summaries, restore failures,
  malformed provenance, incompatible shard inputs, or hidden-field leakage.
- Boss and later-act reachability are reported explicitly, including zero.
- The result states whether complete-run reachability improved, tied, or
  regressed versus baseline Oracle search and post-search model-guided search.
- The PR makes no normal-information, live-game, broad-training,
  controller-promotion, natural A20 performance, or final-agent claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-doc checks, and
`git diff --check`.

Run focused tests for the source-pool merge/finalization workflow and the T049
search-battle-controller source-collection path.

Run the same-runtime PyTorch/native probe from
`docs/sts_lightspeed_wsl_spike.md` with the exact Python interpreter and
`slaythespire` build path used by source collection.

Run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL source collection, shard merge/finalization, coverage/restore, and
reachability stages on explicitly reported artifact paths. The PR must include
full commands, worker/shard counts, seed ranges, terminal source-run counts,
record counts, output paths, hashes, wall-clock costs, and any lower-worker
reason.

## Legacy Reference

Consult T036/T037 for complete-run source reachability reporting, T047/T048 for
root-prior guided fixed-cohort comparison, T049 for checkpoint-guided
complete-run source-collection controller routing, T046 for native root-prior
allocation, and T043/T044 for checkpoint provenance. Do not port unrelated
legacy search, local mechanics, or training code.

## PR Report

The PR must report task ID, source-pool merge/finalization behavior,
controller arms, checkpoint identity, trainer/bridge/teacher/source
provenance, search budgets, root-selection rules, action-space configuration,
non-combat driver, source manifest identity, exact local and WSL commands,
artifact paths and SHA-256 hashes, worker/shard counts, seed ranges,
wall-clock costs, reachability summaries, restore/public-context/
structured-outcome status, T009 gate result, comparison with T037, T048, and
T049, recommended next task, verification results, known limitations,
documentation impact, and every unmet acceptance criterion.
