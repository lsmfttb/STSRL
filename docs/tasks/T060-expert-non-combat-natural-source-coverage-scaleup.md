# T060: Expert Non-Combat Natural Source Coverage Scale-Up

## Objective

Run one fresh, large-scale A20 natural source-collection and per-act coverage
gate using the only accepted source-generation profile that materially improved
later-act reachability: T040's `expert_non_combat_v1` with 100-simulation
Oracle search (`expert_s100`).

T059 closes the root-prior allocation-repair route: the bounded repair
preserved T048's positive fixed-cohort result but did not repair T052/T053
harm. This task therefore returns to the remaining bottleneck, natural
per-act source coverage. It tests whether the accepted expert non-combat
profile can supply a current-schema A20 source pool suitable for a future
coverage decision. It does not test another battle-controller variant.

## Current Main Baseline

T040's matched 1,000-terminal-run source comparison found that `expert_s100`
produced 5,519 natural battle starts, 113 Act-1 Boss starts, and 28 later-act
starts, versus 4,688 starts, 31 Act-1 Boss starts, and three later-act starts
for `stochastic_s20`. The T009 per-act broad-training gate nevertheless
remained closed. T050 supplies deterministic shard merge and parallel
coverage/restore support. T059 confirms that more root-prior allocation repair
is not the next justified source of gain.

## Dependencies

- T059 is complete and closes allocation repair.
- T040 provides the accepted `expert_s100` source profile.
- T050 provides current source-pool shard merge/finalization and coverage merge
  support.
- T039 remains the source-coverage contract and broad-training boundary.

## Inputs And Artifacts

Inputs must be current `main` commands or explicit stable artifacts. Do not use
T040 or T059 review-worktree output as an implicit input.

- the pinned `sts_lightspeed` source manifest and verifier;
- `expert_non_combat_v1` and its public-input firewall;
- the current `oracle_search_v1` source-collection path with 100 native
  simulations and the T040 `expert_s100` action-space/root-selection profile;
- T050's source shard, merge, coverage/restore, coverage merge, and
  reachability-report surfaces.

Generated data must remain under a stable ignored root such as
`artifacts/t060-expert-non-combat-natural-source-scaleup/`. Retain a compact
manifest with schemas, paths, hashes, sizes, seed ranges, worker/shard counts,
wall-clock costs, source configuration, regeneration commands, downstream
consumer, retention reason, and deletion conditions. GB-scale shard and merged
pool files stay out of Git.

## Scope

- Reproduce the T040 `expert_s100` controller profile in a small current-main
  preflight. Fail closed if its controller provenance, 100-simulation budget,
  action-space configuration, root selection, or non-combat behavior version
  differs from the declared profile.
- Generate exactly 10,000 fresh terminal A20 source runs over seeds
  `1001..11000` using `expert_non_combat_v1` for non-combat and
  `oracle_search_v1` at the pinned 100-simulation profile for battle.
- Use 16 explicit source shards and 16 effective source workers by default.
  Run coverage/restore validation as a separate 16-shard, 16-worker stage;
  source parallelism does not exempt coverage from that requirement.
- Deterministically merge source shards, rebuild the A20 coverage report, and
  publish a reachability report. Report every A20 Act separately, including
  zero counts, plus Act-1 Boss starts, room type, encounter, terminal run
  status, battle outcomes, public-context status, structured-outcome status,
  and source identity.
- Evaluate the existing T009 gate with required ascension 20, required Acts
  1--4, at least 100 records per Act, and at least 20 unique sources per Act.
- Recommend exactly one next task: broad teacher/checkpoint refresh only if
  the gate passes; otherwise a narrowly named source-distribution or
  non-combat-driver follow-up. Preserve gate failure as evidence rather than
  bypassing it with repeated samples or assistance.

## Out Of Scope

- Root-prior variants, allocation repair, guardrails, root-prior reachability,
  or controller promotion.
- New battle-controller behavior, checkpoint training, teacher collection,
  calibration, broad training, or fixed-cohort controller evaluation.
- Learned non-combat policy/ranker implementation, assistance schedules,
  constructed starts, normal-information performance claims, live-game work,
  or local Slay the Spire mechanics.

## Design Constraints

- The battle controller remains `full_simulator_state_oracle_like`; this is
  source-generation evidence, not normal-information or natural-performance
  evidence.
- Keep battle and non-combat controller provenance separate. The non-combat
  driver receives player-visible information only and must preserve legal
  low-probability branches.
- Fresh source rows, unique source identities, repeated optimization draws,
  natural data, assisted data, and constructed supplements remain separately
  tagged and counted.
- Source merge and coverage fail closed on duplicate or missing source
  identities, mixed controller/configuration provenance, mixed schemas,
  restore failures that invalidate the stage, public-context mismatches,
  structured-outcome failures, or hidden-field leakage.
- Report source generation, merge, coverage/restore, coverage merge, and
  reachability as separate stages with their own command, workers, shards,
  ranges, artifacts, hashes, and wall-clock costs.

## Deliverables

- Any narrowly scoped command/validation support required to reproduce and
  scale the T040 `expert_s100` profile from current `main`.
- A stable 16-shard natural source pool, deterministic merged pool, parallel
  coverage/restore evidence, coverage report, reachability report, and
  retention manifest for the 10,000 fresh source runs.
- Focused tests for any new command, profile-pin, merge, provenance, or
  validation behavior.
- A concise report that separates natural coverage from other distributions,
  gives every per-Act gate cell, and names exactly one next task.

## Acceptance Criteria

- The current-main preflight proves the exact T040 `expert_s100` profile or
  fails closed before scale generation.
- The accepted artifact has 10,000 terminal source runs, zero unreported
  truncations, and complete per-run controller, seed, source, action-space,
  search-budget, and information-regime provenance.
- Source collection and coverage/restore each use 16 explicit shards and 16
  effective workers unless a documented simulator or resource constraint
  requires fewer.
- The merged pool contains every valid source row exactly once. Coverage and
  reachability results are reproducible from retained artifact identities.
- The report preserves per-Act counts and T009 gate cells; it does not infer
  broad-training readiness from repeated rows, assistance, or aggregate totals.
- The PR makes no controller-promotion, normal-information, live-game,
  natural-A20-performance, broad-training, or final-agent claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-doc checks,
focused tests for changed source/merge/coverage code, and `git diff --check`.

Before WSL evidence, run the pinned-source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run the source, merge, coverage/restore, coverage merge, and reachability
stages through WSL with the exact current-main Python/native pairing. The PR
must report each stage's command, artifact paths, hashes, workers, shards,
seed/record ranges, terminal/truncated counts, wall-clock cost, and any
documented lower-worker reason.

## Legacy Reference

Consult T040 for the accepted expert non-combat source profile, T039 for the
coverage contract, T050 for deterministic scale finalization, T042 for strict
distribution separation, and T059 for the closed allocation-repair evidence.

## PR Report

The PR must report the task ID, exact expert-driver and battle-controller
provenance, source configuration, pinned simulator identity, all stage-level
commands and worker evidence, artifact identities, per-Act coverage and gate
cells, restore/public-context/structured-outcome status, recommendation,
verification results, known limitations, and documentation impact.
