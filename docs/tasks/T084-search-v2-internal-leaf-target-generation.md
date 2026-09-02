# T084: Search v2 Internal-Leaf Continuation-Utility Target Generation

## Objective

Produce the first scientifically qualified value-target dataset whose scalar semantics and state boundary match the accepted T083 Search v2 learned-leaf contract, without training or evaluating a new model.

T083 accepted:

```text
V_leaf(s) = E[evaluateEndState(S_terminal)
              | post-first-action internal state s,
                pinned native playoutRandom continuation]
```

The current `[0,1]` `battle_survival_probability` target is not a valid drop-in native leaf utility, and the retained T064 460-row battle-start/root labels do not themselves supervise the post-first-action internal-leaf state class.

T084 therefore owns exactly one scientific step:

> materialize real Search v2 internal-leaf states, estimate the pinned native continuation utility with a calibrated Monte Carlo target generator, and retain a bounded public-input/value-target dataset suitable for a later paired value-repair experiment.

T084 does **not** train a checkpoint, change model features/architecture, change production Search behavior, or claim that corrected value guidance improves outcomes.

## Accepted starting evidence

### T082 continuation mismatch

T082 / PR #88 accepted `VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED` on the qualified T064 lineage. The value head must not return to realized source-behavior survival as the direct Search v2 leaf target.

Accepted report:

- schema: `t082-value-target-semantic-closure-v1`;
- SHA-256: `e1435812abed86d9ddb4c857cba1863edf852f1e956db9fc002e043a4eb2febc`;
- 460 qualified rows;
- 320 behavior-recoverable rows;
- 149 same / 171 different teacher-vs-behavior first actions.

### T083 leaf-value contract

T083 / PR #89 accepted `NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED`.

Accepted exact implementation head:

`4d964a1f0cd536d884e747eededf3cbc0dd57c92`

Accepted report:

- schema: `t083-battle-search-v2-leaf-value-target-contract-v1`;
- SHA-256: `459216b35ef93c4ca3c5f5183e2af73baf82fd612e4edfb195061f9b0e0d308f`;
- retained T064 root labels are not sufficient internal-leaf labels;
- pinned continuation is `BattleScumSearcher2::playoutRandom`;
- the continuation uses `enumerateActionsForNode(..., false)` and uniform eligible-action selection;
- terminal utility is exact native `BattleScumSearcher2::evaluateEndState`;
- the required state boundary is the non-terminal post-first-action state where the learned leaf callback would be invoked;
- hidden `BattleContext` may be retained only for target-generation provenance/restoration; deployable model input remains public.

T083 proposed a native-side read-only collector, 100 repetitions, a 512-action safety cap, and deterministic replicate seeds. Those numerical choices were explicitly **not** accepted as scientifically optimal. T084 must calibrate the repetition count and must treat the action cap only as a fail-closed execution guard, never as part of the target utility.

### T064 qualified root cohort and sampling checkpoints

T084 reuses the exact accepted T064 selected-source cohort as the root source only:

- curriculum manifest SHA-256 `a111e082d4bc11e03bc5b785a814c422619404245ddda55c2954be09dded46c7`;
- exactly 460 selected/restorable roots in frozen order;
- Act 1: 256;
- Act 2: 204;
- source components: anchor 256, `assist_hp50` 12, `assist_hp50_potion_elite_boss` 32, `assist_hp75_potion` 160;
- selected-source duplication: zero under the accepted T064 complete identity;
- fresh restore: 460/460 successful in T064.

Two T064 **static** formal checkpoints are permitted only as policy-prior occupancy samplers:

- static / 64001: `c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193`;
- static / 64002: `32dbf18a187e8b6d465bb026d90643e3dd28624066628019c61455fcd8f5573a`.

Their use does not claim that either checkpoint is strong. The purpose of using two qualified static seeds plus an unguided arm is to avoid defining the new leaf dataset entirely by one historical checkpoint's occupancy.

The T043 four-row smoke checkpoints are ineligible substitutes.

### Code/native baseline

Planner proposal base:

`main @ cd2087f2f403d9e16c7e6dde759488e84981582c`

Native semantic baseline remains:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1555348535d66e3035aac80933a60949d4bd850f`

Any material native/Search semantic change before execution requires renewed Planner review.

## Artifact Eligibility Contract

Artifact Eligibility Required: true

Reuse mode: `scientific_quality_claim`.

Inputs: the exact accepted T082 report, T083 report, T064 curriculum manifest and selected-source lineage, the two exact T064 static checkpoint identities above, and the pinned STSRL/native code identities.

Claim boundary: T084 may claim only that a retained internal-leaf continuation-utility dataset is qualified for a bounded paired value-target repair under the frozen Search v2/native contract. It does not claim model quality, A20 game strength, learned-value benefit, or general later-act coverage.

Required predicates: exact accepted T082/T083/T064 input identities; exact 460-root
Act/component cohort; exact native/STSRL identities and source matches; collector
off/on parity across all arms; complete restorable hidden-state provenance and
public-input provenance for every leaf; valid 96-leaf calibration with a
precommitted repetition gate; exact 960-row arm/Act quotas with finite terminal
replicates; and intact report/retention hashes. The scientific claim is bounded
by the continuation utility and public-input/hidden-state boundary defined in
this document.

Unavailable-fact behavior: retain an explicit unavailable fact and fail closed
to `INCOMPLETE` for missing or conflicting artifact, code, native, collector,
restoration, execution, or report-integrity evidence; do not infer a leaf state,
target, source identity, or quota from filenames, coarse digests, public
projections, or partial/non-terminal continuations. Valid execution with
insufficient leaf support or failed precommitted Monte Carlo stability remains
the corresponding support/unstable terminal classification, not a relaxed
eligibility claim.

### Required scale and coverage predicates

The consumed T064 source cohort is eligible only if all 460 exact selected roots and the accepted Act/component counts above are reproduced with no substitution.

The final labeled T084 dataset is eligible only if:

- it contains exactly 960 qualified leaf rows;
- it contains 320 rows from each of the three frozen sampling arms defined below;
- within each sampling arm, 178 rows originate from Act 1 roots and 142 from Act 2 roots;
- calibration leaves are disjoint from the 960 formal rows;
- every formal row has one exact public model-input projection, one exact restorable hidden-state provenance record, and a complete set of terminal continuation replicates at the selected repetition count;
- no row is produced from a truncated/non-terminal continuation;
- no active smoke/debug/named scale override supports the final claim.

If these predicates cannot be met from the frozen source/search surfaces, the task must not silently reduce the dataset size or relax coverage.

## Frozen leaf-state sampling arms

All three arms consume the same exact 460 T064 root cohort and use 100 native Search v2 simulations per root.

1. `unguided_search_v2`
   - no learned policy prior;
   - no learned leaf value.
2. `prior_only_static_64001`
   - Search v2 policy prior from exact static/64001 checkpoint above;
   - no learned leaf value.
3. `prior_only_static_64002`
   - Search v2 policy prior from exact static/64002 checkpoint above;
   - no learned leaf value.

Apart from the checkpoint identity for the two prior arms, inherit the accepted T070/T062 Search v2 controller semantics rather than inventing a new search algorithm. Root selection, tree topology, native utility, action legality, and backup behavior are not changed by T084.

The 100-simulation choice intentionally scopes the first repaired target dataset to the same nominal Search v2 budget family that motivated the T070 diagnosis. T084 does not claim that the sampled occupancy is budget-invariant.

## Required work

### 1. Read-only internal-leaf collector

Add the minimum native/integration surface needed to observe the accepted T083 leaf boundary without changing production Search behavior.

For each newly expanded node, after the selected first action has executed and only when the resulting state is non-terminal and would be eligible for the learned leaf callback, the collector must be able to retain:

- the exact post-action `BattleContext` needed to restore the same hidden simulator state;
- a canonical provenance identity/digest for that retained state;
- the exact public projection/model input available to the deployable learner;
- ordered legal-action/public context needed to reproduce the model input contract;
- source complete identity, sampling arm, root identity, simulation/callback ordinal, and tree depth;
- relevant simulator/search RNG provenance.

The Python model-facing callback remains public-only. Hidden state must not be added to deployable model input.

`exactStateDigest` alone is not sufficient if it cannot restore the state. The retained target-generation surface must either store an exactly restorable state payload or prove an exact deterministic replay path to the same post-action state.

#### Collector parity gate

Before scientific collection, run collector-off versus collector-on on a deterministic 16-root preflight subset drawn from the frozen T064 cohort with both Acts represented and all three sampling arms exercised.

For identical roots/seeds/configuration, collector instrumentation must preserve the material Search outputs and telemetry used by the controller, including selected root action and native root statistics. Any Search/RNG behavior change is an execution/fidelity failure, not acceptable target evidence.

### 2. Candidate leaf pool

Run all three frozen sampling arms over all 460 exact roots.

The candidate pool contains the exact non-terminal post-first-action leaf states that satisfy the learned-value invocation boundary. Retain duplicate/occupancy metadata, but do not treat repeated visits as independent state identities for formal target-row selection.

Formal hidden-state identity must be based on the exact retained/restorable leaf-state payload, not merely a coarse public projection.

Candidate collection must report at minimum:

- total callback-eligible leaves by arm, Act, root, and depth;
- unique exact hidden leaf identities by the same slices;
- exact public-input identity counts and naturally occurring public-duplicate groups;
- per-root candidate counts and any roots with no eligible internal leaf;
- worker count/effective concurrency and failures.

This stage makes no target-quality claim by itself.

### 3. Deterministic calibration cohort

Select exactly 96 calibration leaves, disjoint from the final 960 formal rows:

- 32 per sampling arm;
- within each arm, 18 from Act 1 roots and 14 from Act 2 roots;
- prefer distinct source roots before taking a second leaf from the same root;
- selection is deterministic by a versioned hash ranking over frozen source identity, arm, and exact leaf identity.

If exact quotas are unavailable, emit `LEAF_TARGET_SUPPORT_INSUFFICIENT`; do not substitute another root cohort.

### 4. Pinned continuation target generator

For every selected leaf, every replicate must:

1. restore the exact same post-action full `BattleContext`;
2. preserve that state's simulator/game RNG state;
3. initialize an independent **search action-selection RNG** from a recorded deterministic replicate seed;
4. run the exact pinned `playoutRandom` action policy: `enumerateActionsForNode(..., false)` plus uniform eligible-action selection;
5. continue until native terminal state;
6. compute exact `BattleScumSearcher2::evaluateEndState` on that terminal state.

The target expectation is over the pinned random **action continuation** from the fixed leaf state. T084 must not resample hidden/public-consistent futures or alter simulator/game RNG state at the leaf; T034 remains the separate information-set problem.

#### Replicate seed rule

For each leaf and replicate index, derive a uint32 search-action seed from the first eight hex digits of:

```text
SHA256(native_commit |
       source_complete_identity_sha256 |
       sampling_arm |
       exact_leaf_identity |
       replicate_index)
```

Record the full digest input and derived seed. Equivalent deterministic implementation is allowed only if it is byte-for-byte versioned in the retained contract before execution.

#### Safety action cap

Use 2048 native action transitions as an execution safety cap per replicate.

The cap is **not** a terminal utility definition. A continuation that does not reach terminal within the cap is unavailable and must never be scored at its non-terminal state.

Calibration must report cap-hit counts and continuation-length quantiles. The final formal dataset may include only rows for which every required replicate terminates within the cap.

### 5. Repetition-count calibration

Each of the 96 calibration leaves receives exactly 256 independent terminal replicates.

Candidate production repetition counts are:

`N in {16, 32, 64, 100, 128}`.

For each leaf:

- `mu_A(N)` is the mean of replicates `1..N`;
- `mu_B(128)` is the independent reference mean of replicates `129..256`.

Across the 96 calibration leaves define the robust between-leaf utility scale:

```text
I90 = P95(mu_B(128)) - P05(mu_B(128))
```

If `I90 <= 0` or any required reference leaf lacks 128 finite terminal replicates, the estimator is not qualified.

For each candidate `N`, compute:

- Spearman rank correlation between `mu_A(N)` and `mu_B(128)`;
- `NRMSE = RMSE(mu_A(N) - mu_B(128)) / I90`;
- `P95_NAE = P95(abs(mu_A(N) - mu_B(128))) / I90`.

Select the **smallest** candidate `N` satisfying all three precommitted stability gates:

- Spearman `>= 0.98`;
- NRMSE `<= 0.05`;
- `P95_NAE <= 0.10`.

The independent `128 vs 128` comparison is the maximum-budget calibration gate. If `N=128` does not satisfy all three, classify `LEAF_TARGET_MONTE_CARLO_UNSTABLE`; do not generate a formal training dataset by increasing repetitions ad hoc inside T084.

These thresholds qualify a bounded target-generation experiment only; they are not claims that the selected `N` is globally optimal.

### 6. Formal 960-row target dataset

After calibration selects `N`, deterministically select and label exactly 960 additional leaves, excluding the 96 calibration leaves:

- 320 per sampling arm;
- within each arm: 178 Act 1 + 142 Act 2;
- use distinct source roots first within each arm/Act cell before selecting additional leaves from the same root;
- use versioned deterministic hash ranking over frozen source identity, arm, and exact leaf identity;
- if a selected leaf cannot produce all `N` finite terminal replicates, deterministically backfill from the next leaf in the same arm/Act cell;
- if the exact final quotas cannot be met, classify `LEAF_TARGET_SUPPORT_INSUFFICIENT`.

For each formal row retain at minimum:

- source/root/arm/leaf identities and depth;
- exact public raw projection and encoded public model input;
- exact hidden-state target-generation provenance/restoration identity;
- selected repetition count `N`;
- every replicate seed, terminal utility, and continuation length;
- target mean, sample standard deviation, standard error, min/max and requested quantiles;
- cap-hit/backfill provenance;
- exact STSRL/native identities and target-generator schema.

The formal scalar label is the arithmetic mean of the `N` exact terminal native utilities.

Do not attach Oracle policy targets to these internal-leaf rows. T084 produces a **value-target dataset**, not a new joint policy/value teacher dataset.

### 7. Public-information ambiguity diagnostic

Because the deployable value model remains public-input-only while target generation restores one exact hidden simulator state, report naturally occurring groups with identical exact public model input but different retained hidden leaf identities.

For each such group report target spread and Monte Carlo uncertainty. Do not resample synthetic hidden futures, merge labels by hand, or reinterpret this diagnostic as T034 closure.

This diagnostic is not by itself a T084 readiness blocker; it is a required limitation carried into the paired-repair successor.

## Terminal classifications

Emit exactly one terminal classification.

### `LEAF_CONTINUATION_UTILITY_TARGETS_READY`

Use only if:

- all input/artifact/code identities pass fail-closed eligibility;
- collector parity passes;
- all 3 x 460 source/search runs complete with valid provenance;
- the exact 96-leaf calibration cohort is available;
- one candidate `N <= 128` passes all three stability gates;
- the exact 960-row formal arm/Act quotas are met;
- every formal row has all `N` finite terminal continuation utilities and no truncated score;
- retained report/manifest integrity passes.

This classification authorizes Planner consideration of a separate paired value-target repair/retraining task. It does not authorize training inside T084.

### `LEAF_TARGET_MONTE_CARLO_UNSTABLE`

Use when execution/identity/support are valid but no candidate repetition count through `N=128` passes the precommitted stability gates.

Do not silently increase repetitions or change continuation semantics. Planner must decide whether a higher-cost target estimator is justified.

### `LEAF_TARGET_SUPPORT_INSUFFICIENT`

Use when the exact source/search execution is valid but the accepted internal-leaf boundary cannot provide the precommitted calibration/formal arm/Act quotas after deterministic backfill, or when terminal-within-cap availability makes the 960-row formal dataset impossible.

This is a state-support/data-generation result, not an integrity failure.

### `INCOMPLETE`

Use only for failed artifact/code/native identity, collector fidelity failure, malformed required input/output, execution failure, or report/retention integrity failure.

It is not a scientific classification.

## Required reports and retained artifacts

Retain under one stable ignored T084 artifact root:

- exact input/eligibility manifest;
- collector parity report;
- candidate leaf-pool metadata report;
- deterministic calibration-cohort manifest;
- 256-replicate calibration results and repetition-selection report;
- exact 960-row value-target dataset when the terminal class permits it;
- public-information ambiguity diagnostic;
- terminal decision report;
- retention manifest with hashes, sizes, schemas, commands, code/native identities, worker counts, wall-clock cost, regeneration path, compatibility boundary, and deletion conditions.

Large full-state payloads remain outside Git.

### Resumable collector execution

The collector has an optional operational checkpoint mode for long native
collection runs. A fresh run that should be resumable passes
`--progress-dir <stable-ignored-directory>`; after an interruption, rerun the
same command with `--resume` and the same progress directory, output path,
inputs, native build/commit, checkpoints, worker count, and collector code.
Each successful candidate or selected-leaf replay task is checkpointed as a
complete task result under that directory using an atomic JSON replace. Failed
tasks retain diagnostics only and are retried on resume. The progress index and
task parts are operational intermediates, not scientific output, and must stay
under the ignored T084 retention root. A run without `--progress-dir` retains
the original fresh behavior and does not create progress state. Existing failed
v9/v10 attempts remain retained evidence and must not be overwritten.

## Required verification

- task-document / T081 Artifact Eligibility guard;
- exact current-main and native identity checks;
- exact T082/T083/T064 artifact identity and row/coverage checks;
- focused collector-off/on parity tests proving no Search/RNG semantic change;
- exact hidden-state restore test for retained leaf payloads;
- deterministic seed/replay test: selected replicate seed reproduces the same terminal utility and continuation trace;
- tests proving non-terminal cap hits are never scored;
- independent tests for calibration metrics and smallest-passing-`N` selection;
- tests for all four terminal classification paths;
- final 960-row quota, uniqueness/provenance, finite-target, and public-input/hidden-provenance checks;
- standard compileall, Ruff, format, diff and local suite gates;
- simulator work must report effective concurrency, not merely configured workers.

## Explicitly out of scope

- any model/checkpoint training or fine-tuning;
- changing the value-head architecture, loss, features, categorical encoding, hidden size, optimizer, or policy head;
- changing Search v2 topology, UCT/allocation, root selection, callback location, native terminal utility, or production backup semantics;
- using `battle_survival_probability` as the direct leaf label;
- generating new Oracle policy targets for internal leaves;
- T034 public-consistent hidden-future sampling;
- T079 transposition/state-identity research beyond what is minimally required to restore the captured leaf itself;
- T063/T066 promotion;
- complete-run/later-act reachability scale-up;
- human trajectories, human action labels, human rankings, or imitation targets;
- claiming A20 win-rate or full-agent improvement from the generated dataset.

## Successor boundary

If and only if T084 is accepted as `LEAF_CONTINUATION_UTILITY_TARGETS_READY`, the next scientific task may propose a **paired value-target repair** in which the corrected leaf target is the primary changed scientific variable.

That successor must separately precommit:

- how value-only leaf rows are consumed without silently changing policy-target semantics;
- which model parameters are frozen versus trainable;
- the exact baseline/new checkpoint pairing;
- a broader evaluation suite that does not rely only on the historical 93-record weak-policy T052/T070 cohort;
- equal Search budgets and matched seeds/cohorts;
- promotion/failure criteria.

T084 itself publishes none of those training or outcome claims.

## Planner handoff boundary

This document is a Planner proposal. The accompanying task-index change is `DRAFT` only.

Implementation and scientific execution require Maintainer exact-head `SPEC APPROVED` with `implementation_authorized=true`. No collector/native implementation, simulator run, target generation, training, or successor execution is authorized before that approval.
