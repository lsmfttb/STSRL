# T062: Battle Search v2 Minimal Surface

## Objective

Replace root-only model influence with one minimal tree-internal search surface
that can use a policy prior and learned leaf value, then compare it with baseline
Oracle-like search under equal nominal, matched simulator-step, and matched
wall-clock budgets.

T061 established an actionable battle-search signal: increasing the complete-run
battle budget from 20 to 300 under `expert_non_combat_v1` increased matched Act-2
entry by `0.02734375`, with bootstrap 95% CI `[0.0078125, 0.0546875]`. It selected
T062 as the single next task. T062 is a restored-battle search experiment, not a
new complete-run scale-up.

## Current Main Baseline

Current search development has validated native Oracle-like search, post-search
model guidance, root-prior allocation, and detailed telemetry. T059 closed the
root-prior allocation-repair route. T061 then compared baseline
`oracle_search_v1` at native budgets 20, 100, and 300 on the same 93-record T052
cohort and observed 4, 4, and 5 wins respectively. Its complete-run factorial
probe showed a positive battle-budget effect on Act-2 entry but no Act-3,
Act-4, or Heart reachability in any arm.

The next bounded question is therefore whether policy/value guidance inside the
tree improves restored-battle outcomes at matched compute, before any further
natural source scale-up or controller promotion.

## Dependencies

- T061 accepted bottleneck-decomposition evidence and selected this task.
- T052 provides the retained 93-record Boss/later-act fixed cohort.
- T025 provides search telemetry and compute reporting.
- T026 and T043 provide the public checkpoint inference contract and retained
  diagnostic policy/value checkpoint.
- T046 provides native search integration precedent.
- the pinned `sts_lightspeed` integration line.

## Inputs And Artifacts

All inputs are exact current-main contracts or stable ignored artifacts. A
temporary review-worktree file is not a valid dependency.

Required T061 inputs under
`artifacts/t061-a20-reachability-bottleneck-decomposition/` are:

- `t061-bottleneck-report.json`, schema
  `t061-a20-reachability-bottleneck-decomposition-v1`, sha256
  `bfc3bb2bbea81940a1ed0ab9affe7b4cea27a8922896209e927b0297190894ac`;
- `t061-budget-curve-report.json`, schema
  `t061-restored-battle-budget-curve-v1`, sha256
  `db22b90e497bb82e144e1fe43c94c8ffd99df2dfa1b1bcbc2dab9ea7597a3408`;
- `t061-factorial-report.json`, schema
  `t061-complete-run-factorial-report-v1`, sha256
  `e652aa45ae3253e1c4018d7ceeb8571f197d7334e79a0304ec291d0b1fb41b41`;
- `t061-retention-manifest.json`, schema `t061-retention-manifest-v2`,
  canonical self-hash
  `2fb5e329505b52541edbd7aa74b5fa2025e97276523ee341884538a4d7b3ef90`.

The fixed input cohort is
`artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl`,
schema `fixed-cohort-v3-jsonl`, 93 records, 161435825 bytes, sha256
`b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`.
Its retention manifest is `t052-retention-manifest.json`, 37515 bytes, sha256
`6830027aa23db10fd4ce3be17dbaf453e04ebbf9326622d23c3c8ff2b56f130e`.

The diagnostic checkpoint is
`artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt`,
386717 bytes, sha256
`a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`.
It is an experimental public-context policy/value checkpoint, not a promoted
controller. T062 must verify its metadata, feature contract, action vocabulary,
and value head before the first model call and fail closed on any mismatch.

The starting native integration is the manifest-pinned `sts_lightspeed` commit
`9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a`. If tree-internal inference needs
native changes, those changes must land on the authoritative integration line,
the manifest must pin the accepted new commit, and the PR must report both
identities and the fork-side verification.

Generated outputs remain under the stable ignored root
`artifacts/t062-battle-search-v2-minimal-surface/`. Retain reports and a manifest
with schemas, hashes, sizes, simulator/checkpoint identities, exact controller
configuration, record ranges, worker counts, costs, regeneration commands, and
raw-artifact deletion criteria. Large traces stay out of Git.

## Scope

### 1. Minimal versioned search contract

- Add exactly one versioned controller contract,
  `battle_search_v2_oracle_like_v1`.
- Apply the checkpoint policy prior at every expanded player-decision node where
  the published action mapping is valid. A root-only or post-search prior does
  not satisfy this task.
- Apply the learned value head at one named leaf/expansion boundary. Preserve
  battle outcome, terminal absolute HP, and structured end resources separately;
  do not replace them with a permanently weighted scalar label.
- Expose four fixed ablations through the same implementation: `baseline`,
  `prior_only`, `value_only`, and `prior_value`. `baseline` must reproduce
  `oracle_search_v1` semantics rather than use a second search implementation.
- Preserve chance/RNG semantics, duplicate legal-action identity, root selection
  `highest_mean`, `initial_no_potions` action space, and complete provenance.
- Report requested playouts, root visits, native simulator steps, expanded
  nodes, model calls, cache/transposition reuse if any, outer simulator steps,
  and wall-clock seconds per record and arm.

### 2. Contract smoke and compute calibration

Use deterministic record indices `0:16` only for contract smoke and cost
calibration. Calibration may inspect costs but not choose a configuration from
outcomes. It must:

- prove that all four arms restore the same source identities and legal action
  mappings with no fallback;
- run all four arms at nominal native budget 100;
- lock one integer search-budget/configuration per non-baseline arm for a
  simulator-step-normalized pass and one for a wall-clock-normalized pass;
- target the baseline budget-100 aggregate on the 16 records within `5%` for
  native simulator steps and within `10%` for wall-clock seconds respectively;
- record calibration configurations before the 93-record primary comparison.

Calibration is a small diagnostic stage and may use fewer than 16 workers only
when the PR names the worker count and reason. It must not be used as outcome
evidence.

#### Calibration-infeasibility early exit

The calibration is also a feasibility gate. If a guided arm is already above
the applicable upper tolerance at native budget 1, no lower legal integer
budget exists and that family is proven infeasible for the current
implementation. If an arm is below the lower tolerance at budget 1, the task
must test higher integer budgets using a predeclared deterministic candidate
rule before calling that arm infeasible; a below-target minimum is not by
itself a failure proof.

When at least one required arm is proven infeasible, the 93-record primary
comparison is not authorized. T062 may then complete through this early-exit
path only if it:

- retains the successful input preflight, all four nominal-budget-100
  calibration arms, and every cost-candidate report used in the decision;
- records exact per-arm budgets, native simulator steps, model calls, outer
  simulator steps, wall-clock totals, worker/shard layout, and zero-count
  failures;
- emits a versioned calibration manifest whose fail-closed reasons distinguish
  proven infeasibility from arms that remain merely unlocked or untested;
- emits a versioned T062 decision report that authorizes no primary comparison
  and recommends exactly T067, the maintainer-owned inference-cost repair and
  calibration re-entry task;
- retains hashes, sizes, schemas, logs, reproduction commands, and raw-artifact
  deletion criteria under the published stable artifact root.

This early exit accepts a calibration-feasibility result and reusable search
plumbing. It is not fixed-cohort outcome evidence and cannot promote a
controller.

### 3. Primary matched restored-battle comparison

Run this stage only when all required calibration locks succeed. Evaluate all
93 T052 records, with identical ordering and source identity in every arm, in
these three comparison families:

1. equal nominal budget: all four arms at native budget 100;
2. simulator-step normalized: baseline at budget 100 and the three locked
   calibrated configurations;
3. wall-clock normalized: baseline at budget 100 and the three locked calibrated
   configurations on the same host and isolated worker layout.

Every substantial restore/evaluation family must use 16 explicit record-range
shards and 16 effective workers by default. Report record ranges, worker count,
per-arm and aggregate wall time, native simulator steps, model calls, failures,
and any resource-limited deviation. Do not silently retune after observing
primary outcomes.

For every family, report paired results overall, on the 88 Boss-only records,
and on the five Act-2+ records:

- win/loss and terminal absolute current HP;
- structured terminal resources and potion outcome;
- selected root action and first selected-action divergence;
- all required search-compute telemetry;
- paired effect sizes and deterministic bootstrap 95% confidence intervals.

### 4. Decision report

`prior_value` is the predeclared Search v2 candidate; the other guided arms are
mechanism ablations. The task is complete whether the result promotes, repairs,
or closes this implementation, but it must make exactly one recommendation.

Recommend exactly one new bounded Search v2 complete-run evaluation task only
when all of these gates pass:

- zero restore, action-mapping, checkpoint, missing-value, fallback, controller,
  truncation, or mixed-provenance failures;
- the equal-budget `prior_value` arm has positive paired win delta overall, a
  bootstrap 95% CI lower bound of at least zero, and no negative win delta on
  either Boss-only or Act-2+ strata;
- `prior_value` has no negative paired win delta overall or by either stratum in
  both compute-normalized families, and has a positive overall win delta in at
  least one of them;
- mean paired terminal HP among outcome-tied records is non-negative in all
  three families;
- the simulator-step-normalized primary cost is within `5%` and the
  wall-clock-normalized primary cost is within `10%` of baseline.

If any promotion gate fails, recommend exactly one narrowly named repair or
closure task from the observed prior/value ablation and failure evidence. Do not
authorize complete-run evaluation by combining favorable metrics from different
arms.

## Out Of Scope

- Complete-run source generation or natural reachability evaluation.
- New checkpoint training, broad teacher refresh, or checkpoint promotion.
- Human trajectories or human action supervision.
- Public-consistent hidden-future sampling, normal-information promotion, or
  live-game claims.
- Learned non-combat policy implementation.
- Uncertainty-aware allocation, belief-state search, or multiple unrelated
  search algorithms.
- Further root-prior allocation-repair variants.

## Design Constraints

- The controller remains explicitly `full_simulator_state_oracle_like`; native
  tree access is Oracle-like even though checkpoint inputs use the published
  public-context model contract.
- Model inputs must not receive hidden RNG state, hidden draw order, unrevealed
  encounters, or the hidden Act-3 second Boss.
- Search fails closed on invalid/non-finite priors or values, illegal or
  duplicate action ambiguity, incompatible checkpoint metadata, missing value
  heads, mixed simulator identity, or missing compute telemetry.
- Model guidance must not change the legal action space or silently fall back to
  uniform/root-only/post-search guidance.
- Outcome claims must keep equal nominal, simulator-step-normalized, and
  wall-clock-normalized families separate.
- T043 is diagnostic checkpoint evidence only. A positive T062 result promotes
  a search surface to further evaluation, not the checkpoint to broad use.

## Deliverables

- `battle_search_v2_oracle_like_v1` contract and implementation with the four
  fixed ablations.
- Any minimal native integration change, manifest update, and native tests
  required for tree-node priors and learned leaf values.
- Focused Python/native tests for node priors, leaf values, action identity,
  ablations, provenance, telemetry, and fail-closed behavior.
- Calibration manifest locked before primary outcome aggregation.
- Either three matched 93-record comparison families after successful
  calibration, or the complete calibration-infeasibility early-exit evidence.
- One versioned T062 decision report for the path actually taken.
- Stable ignored retention manifest and exactly one next recommendation.
- Documentation updates limited to task/report surfaces; authoritative planner
  documents remain maintainer-owned.

## Acceptance Criteria

- On the primary path, all four arms consume exactly the same 93 cohort
  identities exactly once in each comparison family. On the early-exit path,
  all four arms consume exactly the same 16 calibration identities and no
  93-record outcome claim is made.
- `prior_only`, `value_only`, and `prior_value` exercise tree-internal guidance;
  tests reject root-only or post-search substitutions.
- Baseline preserves current `oracle_search_v1`, `highest_mean`, and
  `initial_no_potions` behavior and provenance.
- The checkpoint and simulator identities match the published inputs or a
  separately documented, accepted manifest update.
- Calibration is cost-only and either locks before primary outcome inspection
  or proves infeasibility using the published early-exit rule.
- On the primary path, all overall, Boss-only, and Act-2+ outcome cells,
  compute metrics, failures, and zero counts are present for every arm and
  family. On the early-exit path, the decision and retention reports explicitly
  record that those outcome families were not authorized.
- There are zero unreported truncations or replacements; any reported failure
  blocks promotion and remains visible.
- The decision applies the predeclared promotion boundary and recommends exactly
  one next task without broad-training, natural-A20-strength,
  normal-information, live-game, or final-agent claims.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, task-document checks,
focused Python/native tests, and `git diff --check`.

Before WSL evidence, run the pinned-source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run native build/tests and all restored-battle evidence through WSL with the
exact current-main Python/native pairing. The PR must report every command,
artifact path/hash/size, record range, shard and worker count, controller and
checkpoint identity, terminal/truncated counts, native and outer simulator
steps, model calls, and wall-clock cost.

## Legacy Reference

Consult T025--T029, T035, T043, T046--T059, and the accepted T061 report.
Historical post-search and root-prior variants remain evidence; they are not the
implementation base except for the explicit T026/T043 inference contract and
T046 native integration precedent named above.

## PR Report

Report task ID, controller/checkpoint/native simulator identities, the locked
calibration, all four ablations, every matched-cohort outcome family,
compute-normalized costs, failures, verification, limitations, documentation
impact, and the single next recommendation.
