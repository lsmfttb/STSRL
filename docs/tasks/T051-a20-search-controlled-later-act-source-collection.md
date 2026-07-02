# T051: A20 Search-Controlled Later-Act Source Collection

## Objective

Run a broader sharded A20 complete-run source-collection pass under the T050
search-controlled arms to determine whether the current battle controllers can
produce useful Boss and later-act natural battle starts before any broad
teacher/checkpoint refresh, assisted training repair, or non-combat ranker
branch.

This is still a source-generation and reachability diagnostic. It must not
promote a controller or claim normal-information, live-game, broad-training,
natural A20 performance, or final-agent strength.

## Current Main Baseline

T050 added deterministic current-schema natural battle-start source-pool shard
merge/finalization and A20 coverage merge support. Its accepted scale artifact
used matched A20 seeds `1..50`, 16 source shards/workers per arm, 16
coverage/restore workers per arm, `stochastic-v1` non-combat control with a
fixed non-combat seed, native root budget 20, and the three T049 battle arms:

- baseline `oracle_search_v1`;
- checkpoint-guided `model_guided_oracle_search_v2`;
- `root_prior_guided_oracle_search_v1`.

All arms completed 50 terminal source runs with zero truncations. Baseline and
post-search model-guided arms each reached one Act-1 Boss battle start; the
root-prior arm reached none. No arm reached Act 2 or later, and the T009 broad
training gate remained closed for Acts 2--4. T050 therefore proved the shard
merge/reporting machinery and provided a stable retained artifact prefix, but
it did not produce later-act A20 source coverage.

## Dependencies

- T050 is complete.
- T049 provides checkpoint-guided complete-run source-collection controller
  routing.
- T048 provides the accepted T043-compatible checkpoint provenance.
- T036/T037 remain the complete-run reachability and historical scale
  reference contracts.

## Inputs And Artifacts

Inputs must be explicit current-schema artifacts or reproducible commands, not
temporary worktree leftovers:

- one T048/T049/T050-compatible T043 checkpoint for the checkpoint-guided arms,
  including checkpoint, trainer, bridge, teacher, manifest, and source
  provenance;
- the current pinned `sts_lightspeed` source manifest containing
  `native_root_prior_allocation`;
- an exact torch-capable WSL simulator runtime that passes the same-runtime
  PyTorch/native probe for the Python interpreter and `slaythespire` build used
  by source collection;
- the T050 source-pool shard merge/finalization and A20 coverage merge command
  surfaces;
- optionally, the retained T050 artifact prefix at
  `artifacts/t050-root-prior-reachability-scaleup-pr/` with retention manifest
  sha256 `74a7390d40e6ffa5c993ed23a9ac782b9267403cef7de92dda31719683b6ea49`.

If the T050 retained prefix is consumed, the PR must verify its manifest hash,
script hash, merged-pool hashes, coverage hashes, source seed range, and
controller/checkpoint identities before treating it as an input. If it is not
available or not consumed, regenerate an equivalent prefix through documented
commands rather than relying on a disposable review worktree.

Generated shard pools, merged pools, coverage reports, reachability reports,
manifests, and logs remain under ignored `artifacts/` paths unless a compact
fixture is needed for tests. Any retained raw files must live under a stable
ignored path outside disposable review worktrees and must have a lightweight
manifest with schema ids, paths, record counts, byte counts where practical,
SHA-256 hashes, worker/shard counts, seed ranges, wall-clock costs, retention
reason, downstream consumers, and deletion conditions.

## Scope

- Run the three required T050 arms at a broader matched-seed scale:
  - `oracle_search_v1`;
  - `model_guided_oracle_search_v2`;
  - `root_prior_guided_oracle_search_v1`.
- Use the same ascension, action-space configuration, native root budget,
  root-selection rule where applicable, checkpoint for checkpoint-guided arms,
  non-combat driver, and non-combat seed across required arms.
- Collect at least 1,000 terminal source runs per required arm. A smaller
  ready-for-review result is not acceptable for this task.
- Reuse the T050 shard merge/finalization and coverage merge paths. Add only
  narrowly scoped automation, manifest, or validation support if the existing
  command surface cannot reliably run or report the broader collection.
- Shard source collection and coverage/restore stages by default. On the
  current 16-logical-core maintainer machine, use 16 workers unless the PR
  reports a concrete resource or tooling reason for a lower count.
- Build merged source-pool, coverage, and reachability artifacts for each arm.
- Report Boss and later-act source coverage, battle outcomes, terminal floors,
  battles per source run, restore status, public-context status,
  structured-outcome status, source identity, and T009 broad-training gate
  cells.
- Compare the result with T037, T049, and T050 evidence, then recommend
  exactly one next task.

## Out Of Scope

- New native `sts_lightspeed` APIs.
- New checkpoint training, teacher collection, calibration, or broad A20
  training.
- Assisted training repair, de-assisted distribution repair, or non-combat
  ranker implementation.
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
  inspectable in source-pool, coverage, and reachability provenance.
- Preserve occurrence-safe action identity mapping for duplicate cards,
  targets, potions, and end-turn actions.
- Merge/finalization and coverage aggregation must fail closed on mixed schema
  versions, missing or mixed source identity, duplicate or malformed source
  identities, incompatible controller provenance, mixed checkpoint identity,
  malformed source-run summaries, unsupported information regimes, restore
  failures that invalidate an arm, malformed provenance, or hidden-field
  leakage.
- Required artifacts must be reproducible by reported commands. Do not use
  another review worktree's smoke files as implicit input.

## Deliverables

- Broader A20 source-collection artifacts covering at least 1,000 terminal
  source runs per required arm.
- Merged source-pool, coverage, reachability, and retention-manifest artifacts
  for all required arms.
- Any narrowly scoped code, script, or manifest support needed to run and audit
  the broader pass, with focused tests when code changes are made.
- A concise PR summary stating whether each arm produced Boss and Act-2+
  battle starts, whether root-prior guided search improved, tied, or regressed
  reachability versus both comparison arms, and whether any produced artifacts
  are suitable as inputs for a later teacher/checkpoint or source-generation
  task.

## Acceptance Criteria

- The exact WSL runtime used for checkpoint-guided source collection passes the
  PyTorch/native same-runtime probe.
- The pinned source verifier passes.
- Required arms use matched seeds, same non-combat driver, same non-combat
  seed, same action-space configuration, same native root budget, same
  root-selection rule where applicable, and the same checkpoint for
  model-guided and root-prior guided arms.
- The scale artifact set covers at least 1,000 terminal source runs per arm
  with terminal/truncated counts reported explicitly.
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
`git diff --check`. If the branch changes code, also run focused tests for the
changed command, merge, or artifact paths.

Run the same-runtime PyTorch/native probe from
`docs/sts_lightspeed_wsl_spike.md` with the exact Python interpreter and
`slaythespire` build path used by source collection.

Run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL source collection, shard merge/finalization, coverage/restore,
coverage merge, and reachability stages on explicitly reported artifact paths.
The PR must include full commands or regeneration scripts, worker/shard counts,
seed ranges, terminal source-run counts, record counts, output paths, hashes,
wall-clock costs, and any lower-worker reason.

## Legacy Reference

Consult T036/T037 for complete-run source reachability reporting, T047/T048 for
root-prior guided fixed-cohort comparison, T049 for checkpoint-guided
complete-run controller routing, T050 for source-pool shard merge/finalization
and coverage merge support, T046 for native root-prior allocation, and T043/T044
for checkpoint provenance. Do not port unrelated legacy search, local
mechanics, or training code.

## PR Report

The PR must report task ID, controller arms, checkpoint identity,
trainer/bridge/teacher/source provenance, source manifest identity, search
budgets, root-selection rules, action-space configuration, non-combat driver
and seed, exact local and WSL commands, artifact paths and SHA-256 hashes,
worker/shard counts, seed ranges, wall-clock costs, reachability summaries,
restore/public-context/structured-outcome status, T009 gate result, comparison
with T037, T049, and T050, recommended next task, verification results, known
limitations, documentation impact, and every unmet acceptance criterion.
