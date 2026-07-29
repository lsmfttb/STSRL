# T070: Battle Search v2 Fixed-Cohort Outcome and Budget-Sufficiency Audit

## Objective

Integrate the accepted Battle Search v2 tree-geometry native capability, run the
original T062 matched 93-record restored-battle outcome comparison with T069's
frozen cost configurations, and add one bounded high-budget diagnostic that
measures whether the current 100-simulation search budget is still materially
under-exploring the retained search tree.

T070 is an outcome and diagnostic task. It must not recalibrate T069 budgets,
retune after reading outcomes, continue the closed T067--T069 inference-cost
repair line, retrain the T043 checkpoint, or publish a successor task. It reports
exactly one successor recommendation for the planner.

## Current Main Baseline

T062 accepted `battle_search_v2_oracle_like_v1` with four fixed arms:
`baseline`, `prior_only`, `value_only`, and `prior_value`. T067 found no exact
public-node cache reuse. T068 found only synchronous singleton callbacks. T069
then accepted one search-scope public-context feature projection, preserved all
accepted scorer and search semantics, materially reduced guided search cost, and
locked all six cost configurations.

T069 is accepted at merge commit
`db9157fc5e4c951b92b92f6689b5358091f09f7d`; the artifact-producing code commit
is `46a5695e8921bdc62c2c5d6ef2e61c62b6b40ba2`.

The fork-side native capability is accepted in
`lsmfttb/sts_lightspeed` on `refs/heads/stsrl/main` at exact commit
`fee272f1ae21c283ad2161f55293cfe6d714134a`. That commit contains:

- `StepSimulator.battle_search_v2`;
- `StepSimulator.battle_search_v2_with_tree_geometry`;
- schema `native-battle-search-v2-tree-geometry-v1`;
- read-only post-search tree-geometry aggregation;
- deterministic parity coverage for policy-prior and learned leaf-value
  callbacks enabled together.

The accepted native implementation retains the existing Search v2 API and patch
identities. The companion API adds `tree_geometry` under
`tree_internal_telemetry` and does not change the existing four-argument
`battle_search_v2` path.

## Dependencies

- T069 accepted projection, calibration, decision, stage, and retention evidence;
- T062 controller, four-arm meanings, original outcome decision boundary, and
  fixed-comparison infrastructure;
- retained T052 93-record Boss/later-act cohort;
- retained T043 policy/value checkpoint;
- accepted native fork Issue #8 and PR #9;
- exact native commit `fee272f1ae21c283ad2161f55293cfe6d714134a`.

## Frozen Input Identities

| Input | Identity |
|---|---|
| STSRL baseline | latest `main` when implementation branch is created |
| Native repository | `https://github.com/lsmfttb/sts_lightspeed.git` |
| Native ref | `refs/heads/stsrl/main` |
| Native commit | `fee272f1ae21c283ad2161f55293cfe6d714134a` |
| T069 merge | `db9157fc5e4c951b92b92f6689b5358091f09f7d` |
| T069 code | `46a5695e8921bdc62c2c5d6ef2e61c62b6b40ba2` |
| T069 retention manifest SHA-256 | `cb34f8c0c4ce00f14e424120566a09a1d666051e6effc9cd39e77d678df9dc76` |
| T068 retention manifest SHA-256 | `bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678` |
| T052 cohort SHA-256 | `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608` |
| T043 checkpoint SHA-256 | `a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4` |

T070 must verify every consumed identity and transitive retention reference
before any substantial stage runs.

## Scope

### 1. Stage 0: native integration and fail-closed preflight

Before any outcome stage, integrate the accepted native commit into STSRL:

1. update `docs/sts_lightspeed_source_manifest.json` to pin
   `fee272f1ae21c283ad2161f55293cfe6d714134a`;
2. add supported capability `native_battle_search_v2_tree_geometry` with required
   Python APIs for the companion method and schema;
3. update `scripts/verify_lightspeed_source.sh` to require both Search v2 methods,
   run the fork smoke and geometry integration scripts, and validate the exact
   schema and invariants from a clean checkout;
4. add `LightSpeedAdapter.battle_search_v2_with_tree_geometry` without changing
   the existing adapter method;
5. add focused adapter, manifest, verifier, schema, invariant, and parity tests;
6. correct stale native identities in maintainer-facing documentation.

The authoritative native verifier command is:

```powershell
wsl.exe -d Ubuntu -e bash -lc \
"cd /mnt/d/DeadlycatCoding/STSRL && \
bash scripts/verify_lightspeed_source.sh \
/home/lsmft/stsrl-spikes/sts_lightspeed"
```

Write `t070-native-capability-preflight-v1` containing at least:

- STSRL code commit;
- native repository, ref, and commit;
- source-manifest SHA-256;
- source-verifier SHA-256;
- Python and compiler/build identities;
- required APIs and geometry schema;
- semantic-parity result;
- exact commands, return codes, and wall-clock seconds.

No primary or high-budget stage may run unless Stage 0 passes completely.

### 2. Frozen primary comparison families

Freeze the following configurations before reading primary outcomes.

#### Equal nominal

| Arm | Native budget |
|---|---:|
| `baseline` | 100 |
| `prior_only` | 100 |
| `value_only` | 100 |
| `prior_value` | 100 |

#### Simulator-step normalized

| Arm | Native budget |
|---|---:|
| `baseline` | 100 |
| `prior_only` | 86 |
| `value_only` | 408 |
| `prior_value` | 384 |

#### Wall-clock normalized

| Arm | Native budget |
|---|---:|
| `baseline` | 100 |
| `prior_only` | 1 |
| `value_only` | 1 |
| `prior_value` | 2 |

Primary guided arms use the accepted T069 search-scope projection. Primary
stages must call the existing `battle_search_v2` path with tree geometry disabled
so T069's wall-clock calibration remains applicable.

The baseline result is shared across families. Run exactly ten unique primary
stages:

1. shared `baseline@100`;
2. equal-nominal `prior_only@100`;
3. equal-nominal `value_only@100`;
4. equal-nominal `prior_value@100`;
5. simulator-step `prior_only@86`;
6. simulator-step `value_only@408`;
7. simulator-step `prior_value@384`;
8. wall-clock `prior_only@1`;
9. wall-clock `value_only@1`;
10. wall-clock `prior_value@2`.

Each stage evaluates the complete ordered 93-record T052 cohort once.

### 3. Primary sharding and workers

Every primary stage uses exactly 16 explicit contiguous shards and 16 effective
workers:

```text
0:6
6:12
12:18
18:24
24:30
30:36
36:42
42:48
48:54
54:60
60:66
66:72
72:78
78:83
83:88
88:93
```

There is no silent lower-worker fallback. If the maintainer host cannot run 16
effective workers, the stage and task remain incomplete. Every stage records the
exact command, shard ranges, worker count, logical CPU count, return codes,
wall-clock seconds, native steps, outer steps, model calls, and artifact paths.

### 4. Primary outcome and compute report

For every family and arm, report overall, 88-record Boss-only, and five-record
Act-2+ cells with:

- wins, losses, termination statuses, and paired win deltas;
- terminal absolute current HP and paired HP among outcome ties;
- structured battle-end resources and potion outcomes;
- selected occurrence-safe root action and first selected-action divergence;
- native and outer simulator steps, model calls, budget, and wall-clock seconds;
- projection construction and reuse counts;
- restore, mapping, checkpoint, missing-value, fallback, controller, truncation,
  worker, and mixed-provenance failures, including explicit zero counts;
- deterministic paired-bootstrap 95% confidence intervals.

Keep all three families separate. Do not combine favorable outcomes across
families or replace measured compute with T069 calibration ratios.

### 5. Outcome-blind high-budget subset

Create `t070-budget-subset-manifest-v1` before reading any T070 outcome. The
subset contains exactly 16 retained T052 records:

- all five Act-2+ records;
- eleven Boss-only records selected by ascending SHA-256 of the complete
  canonical source identity.

Subset construction may read structural source identity and stratum metadata. It
must not read outcomes, selected actions, disagreement labels, or terminal
resources. Retain the ordered identities and selection proof.

### 6. High-budget diagnostic curve

Run exactly six high-budget diagnostic stages on the frozen 16-record subset:

| Arm | Budgets |
|---|---|
| `baseline` | 100, 400, 1600 |
| `prior_value` | 100, 400, 1600 |

Each stage uses 16 one-record shards and 16 effective workers:

```text
0:1, 1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:8,
8:9, 9:10, 10:11, 11:12, 12:13, 13:14, 14:15, 15:16
```

`prior_value` uses
`battle_search_v2_with_tree_geometry`. Baseline continues to use the existing
`battle_search` path and reports its existing root/outcome telemetry. Do not
reuse primary `prior_value@100` because primary telemetry is disabled.

The high-budget stages are diagnostic evidence. They are not primary promotion
evidence and do not alter the frozen primary configurations.

### 7. Tree-geometry report

Retain native geometry exactly as published and derive the following STSRL
metrics by depth:

```text
effective_branching_factor(d)
= discovered_child_edges(d) / max(expanded_nodes(d), 1)

visited_edge_coverage(d + 1)
= visited_child_edges(d) / max(discovered_child_edges(d), 1)

expanded_node_coverage(d + 1)
= expanded_nodes(d + 1) / max(discovered_child_edges(d), 1)
```

Describe these as empirical exposed-edge coverage, not global game-tree
coverage. Terminal and not-yet-expanded edges remain in the denominator where
specified.

Report, for every `prior_value` budget and record:

- expanded nodes by depth;
- discovered and visited edges by depth;
- branching histograms;
- mean, median, p90, and maximum branch factor;
- maximum expanded depth;
- the three derived depth metrics;
- root legal-action count;
- root visit entropy;
- top-1 minus top-2 root visit gap;
- selected root action;
- native steps, model calls, and wall time.

T070 does not require turn-boundary counts, rollout-length telemetry, hidden-state
hashes, transposition hashes, or terminal-frontier classification.

### 8. Budget-sufficiency flag

Set descriptive flag `budget_100_not_sufficient` when any of these conditions
holds on the 16-record subset:

- at least 4/16 selected actions change between `prior_value@100` and
  `prior_value@1600`;
- at least 4/16 root visit leaders change;
- median maximum expanded depth grows by at least two;
- median depth-2 expanded-node coverage is below 25% at budget 100 and median
  maximum depth continues to grow from 100 to 1600.

This flag is diagnostic. It cannot create an additional decision case or override
primary promotion evidence.

### 9. High-budget guidance signal

Set `high_budget_guidance_signal=true` only when all of these hold:

- `prior_value@1600` versus `prior_value@100` has paired win delta at least
  `+2/16`;
- `prior_value@1600` versus `baseline@1600` has non-negative paired win delta;
- mean paired terminal HP among outcome-tied records is non-negative;
- there is no net win regression on the five Act-2+ records.

Any invalid or incomplete high-budget stage prevents this signal from being
computed.

### 10. Complete decision truth table

Apply the original T062 primary promotion boundary first.

#### Case A: primary promotion gate passes

Recommend exactly:

`T071 Battle Search v2 Bounded Complete-Run Reachability Evaluation`

The recommendation does not publish T071.

#### Case B: Case A is false and high-budget guidance signal is true

Recommend exactly T063, Oracle-guided public battle learning. The reason must
state whether `budget_100_not_sufficient` is true or false, but that flag does
not alter the Case B classification.

#### Case C: Case A is false and high-budget guidance signal is false

Recommend exactly T064, simulator-generated later-act curriculum.

Case A has priority regardless of the diagnostic flags. Every valid combination
of the two Boolean diagnostics maps to B or C when A is false. If any required
evidence is invalid, T070 remains incomplete, publishes no decision, and must be
fixed on the same pull request.

T070 reports exactly one recommendation and does not create, publish, or mark a
successor task ready.

## Original T062 Primary Promotion Boundary

Case A requires all of the following:

- zero restore, action-mapping, checkpoint, missing-value, fallback, controller,
  truncation, worker, or mixed-provenance failures;
- equal-nominal `prior_value` has positive paired win delta overall, bootstrap
  95% CI lower bound at least zero, and no negative win delta in either stratum;
- `prior_value` has no negative paired win delta overall or by either stratum in
  both compute-normalized families and a positive overall win delta in at least
  one of them;
- mean paired terminal HP among outcome-tied records is non-negative in every
  family;
- actual simulator-step-normalized primary cost is within 5% of baseline;
- actual wall-clock-normalized primary cost is within 10% of baseline.

The boundary must not be retuned after outcomes are visible.

## Output Schemas

T070 must produce these versioned outputs:

- `t070-native-capability-preflight-v1`;
- `t070-frozen-experiment-manifest-v1`;
- `t070-search-v2-primary-comparison-v1`;
- `t070-budget-subset-manifest-v1`;
- `t070-search-v2-budget-curve-v1`;
- `t070-search-tree-geometry-report-v1`;
- `t070-search-v2-decision-v1`;
- `t070-stage-execution-v1`;
- `t070-retention-manifest-v1`.

Every schema must define required fields, identity rules, ordering, missingness,
and compatibility behavior. Reports fail closed on incomplete arms, records,
strata, geometry rows, or stage inventories.

## Stable Artifact Root And Retention

Use stable ignored root:

`artifacts/t070-search-v2-outcome-budget-sufficiency/`

Organize at least:

- `source-<code-id>/`;
- `reproduction-<code-id>/`;
- `native-preflight/`;
- `frozen-manifest/`;
- `primary/`;
- `budget-subset/`;
- `high-budget/`;
- `reports/`;
- `logs/`.

Retain compact merged reports, the frozen and subset manifests, the terminal
decision, stage inventories, logs, high-budget per-record geometry, and the
retention manifest.

Raw primary and high-budget shards may be deleted only after:

1. merged identities and row counts pass audit;
2. raw hashes, sizes, schemas, and regeneration commands are retained;
3. the T070 pull request is merged;
4. the planner has received the maintainer result report.

Raw artifacts required by a recommended successor remain until that successor is
closed or the artifacts are independently regenerated. The retention manifest
must list every retained path, SHA-256, byte size, schema, command, source
identity, retention reason, downstream consumer, and deletion condition.

## Out Of Scope

- New cost calibration or post-outcome budget retuning.
- Additional cache, projection, feature-copy, encoder, tensor/callback, native
  batching, asynchronous traversal, or calibration-only work.
- Changing or retraining the T043 checkpoint, architecture, feature schemas,
  action ordering, or output meanings.
- Changing native search selection, backup, rollout, RNG, or game mechanics.
- Complete-run source generation or natural A20 scale-up.
- Normal-information, live-game, broad-training, or final-agent claims.
- Publishing T063, T064, T071, or any other successor task.

## Deliverables

- Stage 0 native manifest, verifier, adapter, and focused test integration.
- Frozen 93-record primary configuration and ten unique primary stages.
- Outcome-blind 16-record subset and six high-budget diagnostic stages.
- Complete primary outcome, compute, budget-curve, and tree-geometry reports.
- One terminal A/B/C decision with exactly one recommendation.
- Full stage-execution inventory and stable retention manifest.
- Documentation impact report.

## Acceptance Criteria

- The exact accepted native commit is pinned and passes a clean source verifier.
- Existing `battle_search_v2` behavior remains compatible and the companion
  method is available only when explicitly requested.
- Combined policy-prior plus learned leaf-value parity passes after removing only
  geometry.
- Every native geometry invariant and STSRL derived-metric invariant passes.
- The frozen manifest exists before outcomes are aggregated.
- Every primary stage covers all ordered 93 records exactly once using the
  published 16 shards/workers.
- Every high-budget stage covers all ordered 16 subset records exactly once using
  16 one-record shards/workers.
- All required outcomes, strata, compute, actions, failures, confidence
  intervals, budget diagnostics, and geometry cells are present.
- No calibration, retuning, source replacement, or outcome-driven budget change
  occurs.
- The decision truth table covers every valid Boolean combination and returns
  exactly one recommendation.
- No successor is published by T070.

## Required Verification

Run the standard local gates from `docs/tasks/README.md` plus:

- focused source-manifest and source-verifier tests;
- adapter companion-method tests;
- native geometry schema and invariant tests;
- combined-callback semantic-parity tests;
- subset-construction and outcome-blindness tests;
- frozen-budget and ten-stage identity tests;
- primary aggregation and family-separation tests;
- high-budget curve and geometry-report tests;
- complete A/B/C truth-table tests;
- retention-manifest and deletion-condition tests;
- CLI smoke tests for every new command;
- the WSL native verifier;
- all substantial stages with exact worker and shard evidence;
- `git diff --check`.

The pull request must report exact code and native commits, every substantial
stage command, ranges, workers, return codes, stage wall time, outcome and
compute results, subset proof, budget curve, geometry diagnostics, failures,
terminal case, exactly one recommendation, verification, retained artifacts,
and limitations.

## Legacy Reference

Reuse accepted T062 comparison and decision code, T069 projection/calibration
artifacts, T052 fixed-cohort aggregation, T043 scorer contracts, and the accepted
native tree-geometry scripts. Closed T067 caching and T068 batching paths are
historical diagnostics only.
