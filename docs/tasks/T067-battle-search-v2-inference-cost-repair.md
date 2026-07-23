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

T062 is accepted on `main` at merge commit
`b01a83e1ec436410945e8037add301d6f952a712`. It added the versioned
`battle_search_v2_oracle_like_v1` surface and pinned the native integration to
`3cb9ebecb87c38044b34aa0e013d42b222a04087`.

The accepted cost-only calibration used deterministic T052 indices `0:16`,
16 explicit one-record shards, and 16 effective workers. At minimum guided
budget 1, the wall-clock ratios relative to baseline budget 100 were
`1.1077751075325` for `prior_only`, `1.026232129024169` for `value_only`, and
`0.9140721130090935` for `prior_value`. `prior_only` was therefore proven
infeasible at the minimum legal integer budget while the other two arms
locked. T062 correctly authorized no 93-record primary comparison, made no
fixed-cohort outcome or controller-promotion claim, and selected exactly T067.

This is accepted `full_simulator_state_oracle_like` cost-feasibility evidence,
not normal-information strength, natural A20 performance, live-game
validation, or final-agent evidence.

## Dependencies

- accepted T062 controller, native integration, input preflight, calibration
  manifest, decision report, and retention manifest;
- T061 bottleneck-decomposition evidence;
- the retained 93-record T052 Boss/later-act fixed cohort;
- the retained T043 diagnostic public policy/value checkpoint;
- the manifest-pinned `sts_lightspeed` integration line.

## Inputs And Artifacts

The accepted T062 code identity is merge commit
`b01a83e1ec436410945e8037add301d6f952a712`. The behavior contract is
`battle_search_v2_oracle_like_v1`. The accepted native integration identity is
repository `lsmfttb/sts_lightspeed`, ref `stsrl/main`, commit
`3cb9ebecb87c38044b34aa0e013d42b222a04087`.

The source manifest is `docs/sts_lightspeed_source_manifest.json`, schema
`sts-lightspeed-source-manifest-v1`, 7789 bytes, sha256
`2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631`.
The accepted verifier is `scripts/verify_lightspeed_source.sh` at the T062
merge commit, 19872 bytes, sha256
`16fc6ff8049c9c5083260e513e1472d6736e1aac946d27c8ec7b80b64d4dd0a3`.

The stable T062 artifact root is
`artifacts/t062-battle-search-v2-minimal-surface/calibration/native-prior-fix-3cb9ebe/`.
T067 consumes these exact artifacts:

| Artifact | Schema | Bytes | SHA-256 |
|---|---|---:|---|
| `t062-input-preflight.json` | `t062-battle-search-v2-input-preflight-v1` | 1815 | `19a948fe9a6978d67e7b45522d03868bffd410ccf958b5cf820291c46fe3f024` |
| `nominal-100-py313-with-native/t062-calibration-nominal-100-merged.json` | `t062-battle-search-v2-comparison-v1` | 20534396 | `16deedf7fbd9035d1f050929e50f780a9f85dcd6185ea9e74813c3cc9004988e` |
| `wall-candidate-guided-1-py313/t062-wall-candidate-guided-1-merged.json` | `t062-battle-search-v2-comparison-v1` | 23979082 | `b9e1e17ea37cbe4dd2d51ef3c6d2248387ec0fd06b64d1977e825abb05da6b2b` |
| `t062-calibration-manifest-v2.json` | `t062-battle-search-v2-calibration-manifest-v2` | 4856 | `aa6dc013c6828d9c363dfefd0e201e303925f4ae40eb006e18ae4d00635104b4` |
| `t062-early-exit-decision-report-v2.json` | `t062-battle-search-v2-early-exit-decision-report-v1` | 639 | `cfa015d94611dbf117b40539ba74256e53a618dd5acc72292f0674428315fec5` |
| `t062-retention-manifest-v3.json` | `t062-battle-search-v2-retention-manifest-v3` | 99618 | `dfac7d7660517cee65e311a8d1d2b6fa2d82ac7e26001b8da6ce28150e04ba12` |

The retention manifest indexes 111 retained artifacts, both 16-shard stages,
the complete controller/checkpoint/cohort/native identity, and the exact six
commands required to reproduce the accepted T062 cost result. Those
hash-pinned `regeneration_commands` are the authoritative reproduction
sequence. `scripts/regenerate_t062_retention_manifest.py` rebuilds the manifest
after those reports and logs exist.

The fixed cohort remains
`artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl`,
161435825 bytes, sha256
`b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`.
The diagnostic checkpoint remains
`artifacts/t044-de-assisted-comparison-pr/t043-assist_0-smoke/t043-assist_0-smoke-checkpoint.pt`,
386717 bytes, sha256
`a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4`.

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
