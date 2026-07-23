# T067: Battle Search v2 Inference-Cost Repair

## Objective

Attribute and reduce the tree-internal model-inference cost exposed by T062,
then re-enter its compute calibration. Run the 93-record restored-battle
comparison only if all four search arms can be locked within the published
simulator-step and wall-clock tolerances.

This is one bounded semantic-preserving performance repair. It must either
unlock the original Search v2 comparison or close the current implementation
direction with one evidence-based recommendation.

## Current Main Baseline

T067 is a conditional draft until T062 is accepted. The current T062 draft
evidence reports that, on deterministic T052 indices `0:16` with 16 workers,
`prior_only` at minimum legal native budget 1 still used about `2.147` times
the baseline-budget-100 wall clock. `value_only` was within the 10% wall-clock
tolerance. `prior_value` at budget 1 was about `0.885` times baseline and
therefore requires a higher-budget candidate search rather than a
minimum-budget infeasibility claim.

These values describe unmerged T062 draft evidence and are not accepted
current-main capabilities or durable input identities. Before T067 becomes
`READY`, the maintainer must replace this paragraph with the accepted T062
report, manifest, commit, and artifact hashes.

## Dependencies

- accepted T062 controller, native integration, input preflight, calibration
  manifest, decision report, and retention manifest;
- T061 bottleneck-decomposition evidence;
- the retained 93-record T052 Boss/later-act fixed cohort;
- the retained T043 diagnostic public policy/value checkpoint;
- the manifest-pinned `sts_lightspeed` integration line.

## Inputs And Artifacts

The published `READY` version must name:

- the accepted T062 merge commit and `battle_search_v2_oracle_like_v1`
  behavior contract;
- the accepted native integration commit and verifier identity;
- T062 input-preflight, nominal calibration, cost-candidate, calibration
  manifest, decision-report, and retention-manifest schemas, paths, sizes, and
  hashes;
- the exact T052 cohort and T043 checkpoint identities already required by
  T062;
- every command needed to reproduce the accepted T062 cost result.

Generated outputs remain under the stable ignored root
`artifacts/t067-battle-search-v2-inference-cost-repair/`. Retain compact
reports and a manifest with exact hashes, sizes, simulator/checkpoint
identities, worker/shard layouts, candidate budgets, wall-clock costs,
regeneration commands, and raw-artifact deletion criteria. Large traces stay
out of Git.

## Scope

### 1. Cost attribution

Add per-decision and aggregate timing telemetry that separates:

- native tree-search time excluding Python callbacks;
- public node-context projection and action-identity construction;
- checkpoint feature encoding and tensor construction;
- policy/value forward-pass time;
- Python/native callback and result-conversion overhead;
- cache lookup, hit, miss, and eviction cost if caching is used.

Use the accepted T062 calibration indices `0:16`, the same host, and the same
16-worker layout. Report call counts and time distributions separately for
`prior_only`, `value_only`, and `prior_value`. Do not infer the cause from total
battle wall time alone.

### 2. One semantic-preserving repair

Select exactly one narrow repair design from the attribution evidence. Allowed
examples include exact public-node inference caching, removal of redundant
feature construction, bounded batching across native callbacks, or explicit
PyTorch thread/process control. Multiple unrelated search algorithms or model
changes are not allowed.

The repair must preserve:

- checkpoint bytes, model architecture, policy/value outputs, and public input
  contract;
- legal-action identity and ordering;
- tree policy, leaf-value boundary, chance/RNG semantics, and root selection;
- all four T062 ablation meanings and controller provenance.

On frozen node/action fixtures and retained smoke nodes, policy probabilities
and leaf values must match the accepted T062 implementation within `1e-6`, and
selected legal-action identities must match exactly.

### 3. Deterministic calibration re-entry

Repeat cost-only calibration on T052 indices `0:16` with 16 explicit shards and
16 effective workers. Baseline remains native budget 100.

For each guided arm and each normalization family:

- start from budget 1 and use a predeclared deterministic integer-candidate
  sequence;
- when the ratio is below the lower tolerance, increase budget until the
  interval is reached or crossed, then refine deterministically;
- when the ratio is above the upper tolerance at budget 1, record proven
  minimum-budget infeasibility;
- never choose a budget from battle outcomes.

The simulator-step family must match baseline aggregate native simulator steps
within `5%`. The wall-clock family must match baseline aggregate wall-clock
seconds within `10%`. Lock all arm budgets and configurations before any
93-record outcome aggregation.

### 4. Conditional primary comparison

Only if every calibration lock succeeds, run all 93 T052 records through the
same three T062 families:

1. equal nominal budget 100;
2. simulator-step normalized;
3. wall-clock normalized.

Use 16 explicit record-range shards and 16 effective workers for every
substantial restore/evaluation family. Preserve the T062 overall, 88-record
Boss-only, and five-record Act-2+ reports, paired effects, bootstrap intervals,
terminal absolute HP, structured resources, action divergence, and complete
compute telemetry.

Apply T062's original `prior_value` promotion gate without loosening any
threshold. If calibration remains infeasible, do not run or synthesize the
93-record families.

### 5. Decision

Recommend exactly one next task:

- a bounded complete-run Search v2 evaluation only if every original T062
  promotion gate passes; or
- closure of the current Search v2 implementation and one narrowly named
  alternative when repair or fixed-cohort promotion fails.

## Out Of Scope

- Changing or retraining the T043 checkpoint.
- Relaxing T062's `5%` simulator-step or `10%` wall-clock tolerances.
- Dropping `prior_only` or another required ablation to make calibration pass.
- Root-only or post-search guidance substitutions.
- Complete-run source generation before fixed-cohort promotion.
- Public-consistent hidden-future sampling, normal-information promotion,
  live-game claims, or broad training.

## Design Constraints

- The controller remains `full_simulator_state_oracle_like`.
- Model inputs remain on the published public-context contract and receive no
  hidden RNG, draw-order, future-encounter, or hidden Boss information.
- Cache keys, if used, must include the complete published public node context
  and occurrence-safe ordered legal-action identities. Hash collisions,
  incomplete keys, or cross-simulator reuse fail closed.
- Timing telemetry must use monotonic clocks and remain separate from outcome
  metrics.
- Every expensive WSL stage uses 16 shards/workers by default; any lower count
  requires a stage-specific documented resource or tooling reason.
- No favorable result from one arm or normalization family may substitute for
  a required failure in another.

## Deliverables

- Versioned cost-attribution telemetry and report.
- One semantic-preserving inference-cost repair with focused native/Python
  tests.
- Reproducible 16-record calibration candidate reports and locked manifest.
- Conditional three-family 93-record reports, or an explicit fail-closed
  calibration result with no primary outcome claim.
- Versioned decision report, stable retention manifest, and exactly one next
  recommendation.
- Documentation updates limited to task/report surfaces; authoritative planner
  documents remain maintainer-owned.

## Acceptance Criteria

- Every consumed artifact matches the accepted T062/T052/T043 identity.
- Attribution reports all required timing components and exact model-call
  counts for all guided arms.
- The repaired implementation preserves checkpoint outputs within `1e-6` and
  exact selected action identities on frozen comparisons.
- Calibration uses the same 16 source identities, 16 shards/workers, and
  deterministic candidate rule for every arm.
- Primary comparison is authorized only when all simulator-step and wall-clock
  locks satisfy their original tolerances.
- Any executed primary family contains all 93 identities exactly once per arm
  with zero unreported failures or replacements.
- The report makes no broad-training, natural-A20-strength,
  normal-information, live-game, or final-agent claim.
- Exactly one next task is recommended using the published decision rule.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused T062/T067
Python and native tests, task-document checks, and `git diff --check`.

Before WSL evidence, run the pinned-source verifier against the accepted T062
native commit. Run attribution, calibration, and any authorized primary
comparison through WSL with the exact Python/native pairing. The PR must report
commands, artifact identities, candidate budgets, record ranges, workers,
shards, timing components, model calls, simulator steps, failures, and
wall-clock totals for every stage.

## Legacy Reference

Consult accepted T062 evidence plus T025--T029, T035, T043, and T046--T061.
Selective reuse of T062 runner, reducer, decision, and retention surfaces is
required; old root-only guidance algorithms are diagnostic evidence, not the
repair implementation.

## PR Report

Report task ID, consumed T062/T052/T043 identities, native commit, attribution,
the one selected repair, semantic-equivalence checks, every calibration
candidate and lock, any conditional 93-record outcomes, failures, verification,
limitations, documentation impact, and the single next recommendation.
