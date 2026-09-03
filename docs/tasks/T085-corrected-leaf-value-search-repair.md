# T085: Corrected Search v2 Leaf-Value Repair And Paired Evaluation

## Objective

Run one narrow causal test of the value-target repair enabled by accepted T084.

T082/T083 established that the historical learned Search v2 value was wrong in two independent ways: it represented source-behavior battle survival rather than the pinned continuation value consumed at an internal Search v2 leaf, and it returned a `[0,1]` probability directly into native backups whose terminal playouts use `BattleScumSearcher2::evaluateEndState` units. T084 then produced a scientifically qualified dataset for the corrected scalar:

```text
V_leaf(s) = E[evaluateEndState(S_terminal)
              | post-first-action internal leaf s,
                pinned native playoutRandom continuation]
```

T085 asks exactly one scientific question:

> If the policy path, public features, model representation, Search v2 semantics, simulator, and search budgets are held fixed, does replacing the old learned value with a value head trained on the qualified T084 native-utility leaf targets improve Search v2 behavior?

The task deliberately freezes the shared representation and trains only the value/outcome head. It is not a general model-capacity experiment and does not authorize another Battle repair variant if the result is negative or unresolved.

## Accepted starting evidence

### T084 qualified target dataset

T084 / PR #91 was accepted as `LEAF_CONTINUATION_UTILITY_TARGETS_READY`.

Accepted T084 scientific head:

`b5510a63d8070e54a729e65097ca01a05181237e`

Accepted report SHA-256:

`b6cbcb5ee96d9538adb6ee7a4849a138f6d3a3f93b6127e7ba0ff91dcae1ad1c`

Accepted retention-manifest SHA-256:

`754a9d2560fb5b01c53e7789bdd558e5ef3cc9d0eca4dd690f8f1ab8df1fb0f6`

The retained formal dataset contains exactly 960 qualified internal-leaf rows:

- 320 from `unguided_search_v2`;
- 320 from `prior_only_static_64001`;
- 320 from `prior_only_static_64002`;
- aggregate Act 1 / Act 2 counts: 534 / 426;
- selected continuation repetitions: `N=100`;
- every scalar label is the arithmetic mean of exact terminal native `evaluateEndState` values under the pinned `playoutRandom` continuation.

The implementation must resolve and verify the exact formal-dataset identity from the accepted retention manifest before training. A filename, row count, or local path without the accepted retained identity is not sufficient.

### T064 parent checkpoints

Use exactly the two qualified T064 static formal checkpoints as parent representations:

- static / 64001: `c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193`;
- static / 64002: `32dbf18a187e8b6d465bb026d90643e3dd28624066628019c61455fcd8f5573a`.

Both use the accepted hidden-size-16 architecture. Their historical value head is retained only as an explicit diagnostic comparator; its survival-probability semantics remain scientifically invalid as a native Search v2 leaf utility.

### Evaluation references

Frozen T052 hard diagnostic cohort:

- 93 records;
- SHA-256 `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`.

Retained T042 source pools are permitted only for deterministic construction of a new independent broad battle holdout. Exact accepted pool hashes are:

- `assist_0`: `d124d94a94df534c0bcc32072582a4448746f0a9734a41410e45c51c1b1ff87f`;
- `assist_hp25`: `c23707694f94e471b2c2ffd972f8fc1356b3c04d6756b0911a95aca51c29d8e8`;
- `assist_hp50`: `1231bcd24309df9fbeb22ec56dfa12b661c38c6f440bdea1850053734cc32d8e8`;
- `assist_hp50_potion_elite_boss`: `642d11d4956316e96f58ddf5fceec94f59a50c3dd051205e2fdfca94485ab201`;
- `assist_hp75_potion`: `1bbcbfebbde4fd2eec1be249f9843bf25a288abb0672950f47ad540c9bb8f46f`.

The broad holdout must exclude every exact T064 selected root and every T044/T052 evaluation identity.

### Code/native baseline

Planner proposal base:

`main @ 2f5badbc3fe654fe71f1b0b306dbcdaffcfe88ed`

Native Search semantic baseline remains the accepted pinned integration used by T084:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1555348535d66e3035aac80933a60949d4bd850f`

A material Search/native semantic change requires renewed Planner review.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Reuse mode: `scientific_quality_claim`.

The claim is intentionally narrow: T085 may establish only whether this frozen value-head-only repair improves the accepted Search v2 controller under the specified paired battle evaluation. It does not establish full A20 agent improvement, non-combat quality, end-to-end Heart win rate, representation optimality, or a general solution to imperfect information.

Required inputs must include exact accepted T084 report/retention/formal-dataset identities, both exact T064 parent checkpoints, exact T052 cohort identity, exact T042 pools used for the broad holdout, exact STSRL/native identities, and all generated cohort/checkpoint/report hashes.

Unknown, conflicting, stale, smoke-only, or filename-inferred identity fails closed to `INCOMPLETE`.

## Frozen scientific variable

The primary changed scientific variable is the learned leaf-value target/consumer contract.

Everything outside the historical `outcome_head` is frozen per parent checkpoint:

- `state_encoder` tensors;
- `action_encoder` tensors;
- `policy_head` tensors;
- `hp_head` tensors;
- `resource_head` tensors;
- state/action normalization buffers;
- public tactical/context feature schemas;
- policy inference semantics.

Only the `outcome_head` may be reinitialized and trained.

The corrected value target kind is:

`search_v2_leaf_continuation_native_utility_v1`

The corrected Search callback must receive a finite scalar in exact native `evaluateEndState` units. It must not apply sigmoid, survival-probability interpretation, clipping to `[0,1]`, hand rescaling at the Search boundary, or any conversion to a different utility.

### Policy invariance gate

For each repaired checkpoint:

1. every parameter/buffer outside `outcome_head` must be byte-identical to its parent checkpoint;
2. policy logits and normalized policy probabilities must be identical to the corresponding parent on every T084 formal public model input and legal-action set;
3. a mismatch is an integrity failure, not an acceptable side effect of value training.

This gate is what makes the experiment value-head-only rather than a hidden joint policy/value retraining experiment.

## Corrected value training

Produce exactly two repaired checkpoints:

- parent static/64001 -> repair seed `85001`;
- parent static/64002 -> repair seed `85002`.

Both consume the same exact 960 T084 formal rows. There is no outcome-based row selection and no checkpoint selection from Search evaluation.

### Target normalization

Compute one target mean and population standard deviation over the exact 960 native-utility labels. Store both values in checkpoint provenance.

Train the value head to predict:

```text
z = (native_utility - target_mean) / target_std
```

using ordinary squared error. `target_std <= 0`, non-finite statistics, or any missing target is an integrity failure.

At inference, de-normalize exactly once:

```text
native_leaf_utility = z_pred * target_std + target_mean
```

and pass that value directly to Search v2.

Target normalization is a numerical training transform only; the Search-facing semantic unit remains exact native utility.

### Frozen optimization budget

For each repaired checkpoint:

- reinitialize only `outcome_head` with the task repair seed;
- optimizer: Adam;
- learning rate: `0.001`;
- betas: `(0.9, 0.999)`;
- epsilon: `1e-8`;
- weight decay: `0`;
- batch size: `32`;
- optimizer steps: exactly `900`;
- gradient clip norm: `10.0`;
- loss: mean squared error on normalized T084 native-utility labels;
- no early stopping;
- no learning-rate search;
- no checkpoint selection by offline or Search outcome;
- the step-900 checkpoint is the only candidate checkpoint for that repair seed.

A deterministic batch schedule must be recorded and reproducible from the repair seed. Ordinary implementation details of the schedule are free if they are frozen before execution and identical in meaning across both repair runs.

Offline training loss/MAE is diagnostic only and cannot establish Search improvement.

## Corrected inference surface

Add the minimum backward-compatible inference contract needed to distinguish historical survival probability from corrected native leaf utility.

A corrected checkpoint must expose an explicit native-utility value prediction field or equivalent fail-closed metadata-gated surface. Historical checkpoints must continue to decode with their historical semantics. Do not silently reinterpret an old `battle_survival_probability` field as native utility.

Search v2 must use corrected native utility only when the checkpoint provenance explicitly declares `search_v2_leaf_continuation_native_utility_v1`. Missing/ambiguous target kind fails closed.

No Search topology, UCT, root selection, action legality, callback location, native backup, terminal utility, or policy-prior semantics may change.

## Evaluation suite

All outcome comparisons are paired restored-battle comparisons at equal nominal Search simulations. The experiment measures guidance quality, not wall-clock-normalized controller strength. Wall clock, simulator steps, callback count, and inference cost are retained as diagnostics.

### Cohort A — frozen hard regression set

Reuse the exact 93-record T052 Boss/later-act cohort unchanged.

Purpose: preserve the historical hard regression boundary. It is a stress cohort, not a representative A20 occupancy distribution.

### Cohort B — independent broad stratified holdout

Before any T085 model-guided outcome evaluation, deterministically construct and retain exactly 192 battle starts from the accepted T042 source pools.

Eligibility:

- A20;
- valid current-schema provenance;
- fresh restore succeeds;
- public-context replay matches;
- no recorded truncation/controller/mapping/provenance failure;
- exact complete identity not present in the T064 selected 460 roots;
- exact complete identity not present in either frozen T044 cohort or T052;
- selection never reads source battle result, terminal HP, teacher/model output, deck/relic quality, or perceived winnability.

Quotas:

- 96 Act 1;
- 96 Act 2+;
- within each Act cell: 72 `MONSTER` and 24 `ELITE`/`BOSS` combined.

Within each cell, sort by SHA-256 of the accepted complete source identity and take the first eligible records. Exact duplicate complete identities are not silently deduplicated; they are an integrity failure. If the frozen pools cannot satisfy the quotas after exclusions and fresh validation, classify `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`.

Retain the exact cohort manifest and hash before outcome aggregation.

### Cohort C — fresh current-policy occupancy sample

Generate exactly 128 standard-start A20 source runs with seeds `850001..850128` using:

- battle controller: unguided Search v2, 100 simulations, accepted `highest_mean` semantics;
- non-combat controller: frozen `expert_non_combat_v1`;
- no run assistance;
- current pinned simulator/native identities.

This source controller is used only to define a current baseline occupancy distribution; `expert_non_combat_v1` is not a training target.

From each run with at least one valid restorable battle start, select exactly one start by deterministic SHA-256 ranking over `(source run identity, battle complete identity)`. This prevents long runs from dominating merely because they contain more battles. Selection does not use battle outcome or depth preference.

Require at least 96 selected valid records. Otherwise classify `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`. Report Act/room/depth distribution rather than forcing later-act quotas; shallow occupancy is itself relevant evidence.

### High-budget guard subset

From Cohort B, before outcomes are run, select 48 records by deterministic hash ranking:

- 24 Act 1;
- 24 Act 2+.

This subset is evaluated at 400 simulations as a budget-robustness guard. T085 does not reopen the T070 1600-simulation study.

## Primary value-only arms

Run all three main cohorts at Search v2 budget 100 using the same restored record and matched Search randomness/configuration across arms:

1. `baseline`
   - no policy prior;
   - no learned leaf value.
2. `old_value_64001`
   - no policy prior;
   - historical static/64001 survival-probability leaf callback, unchanged.
3. `corrected_value_85001`
   - no policy prior;
   - repaired native-utility value head derived from static/64001.
4. `old_value_64002`
   - no policy prior;
   - historical static/64002 survival-probability leaf callback, unchanged.
5. `corrected_value_85002`
   - no policy prior;
   - repaired native-utility value head derived from static/64002.

The old-value arms are diagnostic comparators only. Their presence does not revalidate the old value contract.

For the 48-record high-budget subset, run only:

- `baseline@400`;
- `corrected_value_85001@400`;
- `corrected_value_85002@400`.

## Secondary policy/value compatibility arms

On Cohort B at budget 100 only, additionally run for each parent seed:

- `prior_only_64001` vs `prior_corrected_85001`;
- `prior_only_64002` vs `prior_corrected_85002`.

The policy prior in each pair must be exactly the unchanged parent policy path. These arms test compatibility after the value-only causal test. They are secondary and cannot rescue a failed primary classification.

Do not run another root-prior allocation variant and do not reopen the closed T047-T059 allocation-repair route.

## Required outcome metrics

For every cohort/arm retain at least:

- battle survived / lost;
- exact terminal native `evaluateEndState` utility;
- final HP and battle turn count where available;
- selected root action identity;
- simulator/search step counts;
- learned-value callback count;
- wall-clock duration;
- failure reason if any.

For each paired comparison report:

- total wins;
- baseline-only wins and comparator-only wins;
- paired win delta;
- per-record native-utility delta;
- mean/median native-utility delta;
- deterministic percentile-bootstrap confidence interval for mean utility delta.

### Frozen bootstrap rule

For Cohort B, define per record:

```text
corrected_mean = mean(U_corrected_85001, U_corrected_85002)
old_mean       = mean(U_old_value_64001, U_old_value_64002)

delta_old  = corrected_mean - old_mean
delta_base = corrected_mean - U_baseline
```

Use 10,000 paired bootstrap resamples of Cohort-B records, sampling records with replacement, RNG seed `85085`. Report the 2.5th and 97.5th percentiles of the resampled mean for `delta_old` and `delta_base`.

The bootstrap treats battle records, not individual Search callbacks or tree nodes, as the sampling unit.

## Terminal classifications

Emit exactly one scientific classification, unless integrity/execution is incomplete.

### `CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED`

Use only if all of the following hold:

1. Cohort B 95% bootstrap lower bound for mean `delta_old` is strictly greater than zero.
2. Cohort B 95% bootstrap lower bound for mean `delta_base` is strictly greater than zero.
3. On Cohort B, each corrected seed has at least as many battle wins as `baseline` and at least as many as its corresponding old-value arm.
4. On Cohort A, each corrected seed has no more than one fewer win than `baseline`, and the corrected-seed mean native-utility delta versus baseline is non-negative.
5. On Cohort C, each corrected seed has no more than one fewer win than `baseline`, and the corrected-seed mean native-utility delta versus baseline is non-negative.
6. On the budget-400 guard subset, each corrected seed has no more than one fewer win than `baseline@400`, and the corrected-seed mean native-utility delta versus baseline is non-negative.
7. All policy-invariance, artifact-eligibility, checkpoint, evaluation, and retention gates pass.

This classification establishes a bounded corrected-value Search signal. It does not establish complete-run A20 improvement.

### `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`

Use when integrity/support are valid and Cohort B shows both:

- the 95% bootstrap upper bound for mean `delta_base` is strictly below zero; and
- both corrected seeds win fewer Cohort-B battles than `baseline`.

This closes the current value-head-only repair as harmful under the frozen representation/Search contract.

### `CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED`

Use for every valid, sufficiently supported result that satisfies neither the positive nor harmful definition.

Mixed seeds, utility-only movement without the required win guardrails, isolated hard-cohort gains, or positive secondary prior/value compatibility do not upgrade this classification.

### `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`

Use when all retained scientific inputs and training execution are valid but the frozen broad/current-occupancy evaluation-support rules cannot be satisfied.

Do not silently reduce cohort sizes or change quotas after seeing availability.

### `INCOMPLETE`

Use for artifact/code/native mismatch, invalid checkpoint provenance, policy-invariance failure, malformed target data, non-finite training/inference, failed restore/parity, execution failure, or retained report/manifest integrity failure.

`INCOMPLETE` is not a scientific result.

## Required artifacts

Retain under one stable ignored T085 artifact root:

- exact input/eligibility manifest resolving the accepted T084 formal dataset;
- two repaired checkpoint files and training reports;
- value-target normalization statistics and deterministic batch-plan identity;
- policy-invariance audit against both parent checkpoints;
- Cohort-B selection/restore manifest;
- Cohort-C source-run and selected-occupancy manifest;
- high-budget subset manifest;
- primary and secondary paired evaluation reports;
- terminal classification report;
- retention manifest with hashes, sizes, schemas, commands, code/native identities, effective worker counts, wall-clock cost, regeneration path, compatibility boundary, and deletion conditions.

Large generated artifacts remain outside Git.

## Verification requirements

Before final acceptance, verify at minimum:

- T081 scientific eligibility guard;
- exact T084 report/retention/formal-dataset identities and 960-row target semantics;
- exact T064 parent checkpoint identities;
- target de-normalization reproduces native units and never applies sigmoid/clipping;
- all non-`outcome_head` tensors/buffers remain byte-identical to each parent;
- policy logits/probabilities are unchanged on all 960 T084 public inputs;
- deterministic outcome-head reinitialization and 900-step training reproduction;
- old checkpoint inference remains backward compatible and semantically distinct;
- Cohort-B exclusions, quotas, hash ranking, restore/public-context validity, and no outcome-conditioned selection;
- Cohort-C exact seeds/controller configuration and one-record-per-run deterministic selection;
- equal-budget paired Search configuration and matched randomness;
- independent implementation tests for bootstrap/classification logic, including every terminal class;
- standard compileall, Ruff, format, diff, and relevant local test gates;
- substantial simulator work reports configured and effective concurrency and retained shard/failure evidence.

## Explicitly out of scope

- updating `state_encoder`, `action_encoder`, policy, HP, or resource parameters;
- changing hidden size, features, identity encoding, embeddings, architecture, or normalizers;
- adding policy supervision to T084 internal-leaf rows;
- recollecting T084 targets or changing `N=100`;
- changing Search v2 topology, UCT, allocation, root selection, callback location, native backup, or terminal utility;
- new root-prior allocation repair variants;
- T034 hidden-future sampling;
- T079 transposition work;
- complete-run A20 outcome comparison for the repaired Battle controller;
- training or modifying a non-combat learner;
- T063/T066 promotion;
- human trajectories, human labels, card rankings, deck heuristics, or human imitation targets.

## Successor boundary

A valid scientific T085 result—`CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED`, `CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED`, or `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`—closes this Battle value-repair round.

After such a result, the next Planner priority is a separate minimal self-generated Non-Combat learning task with Battle frozen. Do not publish another Battle value variant merely because T085 is neutral or harmful.

If T085 establishes improvement, the accepted corrected Battle controller may be considered as the frozen Battle side of that Non-Combat experiment. If improvement is not established or harm is confirmed, use the strongest already-accepted non-learned/unguided Battle Search baseline instead. The Non-Combat task must independently precommit train/checkpoint/final-test seed separation, public-information inputs, complete-run occupancy/reachability metrics, and no imitation of `expert_non_combat_v1`.

Only after both Battle and Non-Combat each have at least one credible independently evaluated learned improvement should T066 be rewritten into a true alternating improvement loop. That later loop should freeze one side while updating the other and preserve a mixture of frozen anchors, current-policy occupancy, and later-act/coverage curriculum rather than training only on the latest-policy distribution.

`VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT` or `INCOMPLETE` authorizes only the minimum recovery needed to complete T085; it does not authorize new Battle science.

## Planner handoff boundary

This document is a Planner proposal. The accompanying Task Index change is `DRAFT` only.

Implementation, training, simulator execution, and outcome evaluation require Maintainer exact-head `SPEC APPROVED` with `implementation_authorized=true`. A material change to the value-only freeze, training budget, evaluation cohorts, Search arms, or terminal classification requires renewed Planner review.