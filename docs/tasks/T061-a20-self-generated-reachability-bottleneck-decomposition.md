# T061: A20 Self-Generated Reachability Bottleneck Decomposition

## Objective

Determine whether current A20 natural-run reachability is limited primarily by
battle-search compute, non-combat behavior, or an interaction between the two
before approving another large fixed-policy source collection.

The task replaces the cancelled T060 10,000-run scale-up with two matched
intervention studies: a restored-battle search-budget curve and a complete-run
factorial reachability probe. It must produce one evidence-based recommendation
for the next executable task.

## Current Main Baseline

T040 showed that `expert_non_combat_v1` plus 100-simulation Oracle-like battle
search improved source reachability relative to a stochastic non-combat driver,
but 1,000 terminal runs still produced only scarce aggregate later-act starts and
left broad training closed. T052 showed that the current later-act fixed cohort
is difficult even for Oracle-like restored-battle search. T059 closed the
root-prior allocation-repair route.

The current evidence does not establish that scaling the unchanged T040 profile
to 10,000 runs would yield useful Act-3, Act-4, or Heart sources. It also does not
separate the marginal effect of battle-search budget from the effect of the
bootstrap non-combat policy.

## Dependencies

- T040 provides `expert_non_combat_v1` and the accepted matched source-generation
  comparison contract.
- T050 provides deterministic sharding, merge, coverage, restore, and
  reachability-report support.
- T052 provides the retained 93-record Boss/later-act restored-battle cohort and
  accepted artifact identities or regeneration contract.
- T059 closes further root-prior allocation repair.
- [`../training_paradigm.md`](../training_paradigm.md) defines the no-human-data,
  simulator-only training boundary.

## Inputs And Artifacts

Inputs must be current `main` commands or explicit stable artifacts. A temporary
review-worktree file is not a valid dependency.

Required inputs:

- the pinned `sts_lightspeed` source manifest and verifier;
- `stochastic_non_combat_v1` and `expert_non_combat_v1` with complete public-input
  and behavior provenance;
- baseline `oracle_search_v1` with `highest_mean` root selection and no
  root-prior/model-guidance variant;
- the retained T052 cohort and manifest, or documented commands that regenerate
  a compatible fixed cohort;
- current complete-run source, shard, merge, coverage, and reachability surfaces.

Generated artifacts remain under a stable ignored root such as
`artifacts/t061-a20-reachability-bottleneck-decomposition/`. Retain compact
manifests and reports with schemas, paths, hashes, sizes, simulator identity,
controller configuration, seed/cohort ranges, shard and worker counts,
wall-clock costs, and regeneration commands. Large per-run and per-decision files
stay out of Git.

## Scope

### 1. Restored-battle budget curve

Run the same T052-compatible restored-battle cohort under baseline
`oracle_search_v1` at native simulation budgets 20, 100, and 300. Preserve the
same action-space configuration, root selection, simulator source, and cohort
ordering across arms.

Report per arm and pairwise by record:

- win/loss and terminal absolute HP;
- potion and structured terminal-resource outcomes;
- selected root action and first-action disagreement;
- simulator steps, model calls if any, wall-clock time, and truncation/error
  status;
- Act, room, encounter, and Boss/later-act strata.

The purpose is to measure whether the 100-simulation profile is visibly
compute-limited under the current search algorithm. This stage does not test a
new search algorithm.

### 2. Complete-run factorial reachability probe

Run a matched 2-by-3 factorial experiment over:

- non-combat behavior: `stochastic_non_combat_v1` and
  `expert_non_combat_v1`;
- battle-search budget: 20, 100, and 300 native simulations.

Use exactly 256 shared A20 seeds per arm, for 1,536 terminal runs total. The same
seed set must appear in every arm. Use standard-start, unassisted natural runs;
no constructed starts, HP/potion assistance, restart privilege, checkpoint
injection, learned checkpoint guidance, root-prior allocation, or hidden
non-combat inputs are allowed.

Report for every arm and matched pair:

- terminal floor and terminal run status;
- entry into and victory over each Act Boss;
- entry into Acts 2, 3, and 4;
- Shield and Spear start/outcome, Heart start/outcome, and A20 Heart victory;
- natural battle-start counts and independent source counts by Act, room, and
  encounter;
- death encounter and pre-death public resource snapshot when available;
- search cost, simulator steps, wall-clock time, truncations, controller errors,
  and unsupported states.

Preserve zero cells explicitly. Report run-level matched effect sizes and
bootstrap 95% confidence intervals for driver, budget, and driver-by-budget
interaction effects. The report must distinguish statistical uncertainty from a
true zero observed count.

### 3. Decision report

Publish a versioned bottleneck-decomposition report that keeps the restored-
battle and complete-run evidence separate, then applies a predeclared decision
table:

- recommend moving T062 toward `READY` when increased battle budget shows a
  meaningful restored-battle or complete-run effect and current search quality is
  the primary actionable limit;
- recommend moving T065 toward `READY` when the non-combat driver effect dominates
  at matched battle budget;
- recommend revising and publishing T064 first when neither policy intervention
  creates useful later-act reachability but simulator-generated curriculum is
  still required to develop either module;
- recommend one narrowly named follow-up diagnostic when evidence is inconclusive
  or a tooling/fidelity failure invalidates attribution.

The task must recommend exactly one next task. It may record secondary findings,
but it must not publish multiple executable branches.

## Out Of Scope

- Running the cancelled T060 10,000-run fixed-profile collection.
- Human trajectories, human action labels, human expert imitation, or external
  human strategy statistics.
- New battle-search algorithms, tree-internal learned guidance, new model
  training, checkpoint promotion, or controller promotion.
- Learned non-combat policy implementation or imitation of
  `expert_non_combat_v1`.
- Assistance schedules, arbitrary synthetic decks/relics, live-game validation,
  normal-information performance claims, or local reimplementation of game
  mechanics.

## Design Constraints

- `expert_non_combat_v1` is a bootstrap behavior policy, not a teacher. Its
  selected action must never be emitted as a supervised correct-action target by
  this task.
- All battle arms remain `full_simulator_state_oracle_like`; the experiment is a
  training/source diagnostic, not normal-information evidence.
- Controller child provenance must remain separate inside routed complete-run
  provenance.
- Source identities, repeated optimization rows, natural data, Oracle data,
  assisted data, transformed data, and constructed data must remain separately
  tagged and counted.
- Every expensive WSL stage uses 16 explicit shards and 16 effective workers by
  default, capped by cohort/shard count and documented resource constraints.
- The comparison fails closed on mixed seeds, missing arms, mixed simulator or
  controller provenance, duplicate source identities, restore failures that
  invalidate matched comparison, hidden-field leakage, or unreported
  truncations.
- A larger budget is not considered better solely because it consumes more
  simulator steps. All conclusions must report compute-normalized costs.

## Deliverables

- Any narrowly scoped command/report support required to run the budget curve and
  factorial experiment reproducibly from current `main`.
- Focused fixtures and tests for arm construction, matched-seed validation,
  report aggregation, interaction-effect reporting, and fail-closed provenance
  checks.
- Restored-battle per-arm artifacts and a cross-budget comparison report.
- Six complete-run source shards/arm groups, deterministic manifests, merged
  reachability summaries, and a factorial comparison report.
- One versioned bottleneck-decomposition report and exactly one recommended next
  task.
- Documentation updates limited to task/report surfaces required by the branch;
  authoritative planner documents remain maintainer-owned.

## Acceptance Criteria

- The restored-battle report contains the same valid cohort identities for
  budgets 20, 100, and 300 and reports every record exactly once per arm.
- The complete-run report contains exactly 256 terminal A20 runs for each of the
  six declared arms and exactly 1,536 terminal runs overall, with the same 256
  seeds in every arm.
- There are zero unreported truncations. Any reported truncation or controller
  failure remains visible and is not silently replaced by another seed.
- Every arm preserves exact simulator, action-space, root-selection, search-
  budget, non-combat behavior, and information-regime provenance.
- Every Act/Boss/Heart reachability cell is present, including zeros, and natural
  unique-source counts remain separate from battle-start totals.
- Driver, budget, and interaction effects are reported with paired effect sizes,
  uncertainty intervals, and compute cost.
- The report makes no broad-training, controller-promotion, natural-A20-strength,
  normal-information, live-game, or final-agent claim.
- Exactly one next task is recommended using the published decision table.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-document checks,
focused tests for changed command/report code, and `git diff --check`.

Before WSL evidence, run the pinned-source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run restored evaluation and complete-run collection through WSL with the exact
current-main Python/native pairing. The PR must report each command, artifact
path and hash, worker/shard count, cohort or seed range, terminal/truncated
counts, simulator-step count, and wall-clock cost.

## Legacy Reference

Consult T040 for the bootstrap-driver matched comparison, T050 for source
sharding and merge/finalization, T052 for the retained later-act cohort, and T059
for the closed root-prior allocation-repair evidence. Selective reuse of their
command/report surfaces is allowed; their local review artifacts are not implicit
inputs.

## PR Report

The PR must report task ID, simulator identity, all controller configurations,
all stage commands, artifact identities, worker/shard evidence, restored-battle
budget-curve results, complete-run factorial results, matched effect sizes and
uncertainty, compute costs, failures or deviations, the single recommended next
task, verification results, limitations, and documentation impact.
