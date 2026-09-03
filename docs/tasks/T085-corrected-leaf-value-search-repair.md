# T085: Corrected Search v2 Leaf-Value Repair And Paired Evaluation

## Objective

Run one narrow causal test of the value-target repair enabled by accepted T084.

T082/T083 established that the historical learned Search v2 value had two independent contract defects: it represented source-behavior battle survival rather than the continuation value consumed at an internal Search v2 leaf, and it returned a `[0,1]` probability into native backups whose terminal playouts use `BattleScumSearcher2::evaluateEndState` units. T084 then produced a scientifically qualified dataset for the corrected scalar:

```text
V_leaf(s) = E[evaluateEndState(S_terminal)
              | post-first-action internal leaf s,
                pinned native playoutRandom continuation]
```

T085 asks exactly one scientific question:

> With the policy path, public features, representation, Search v2 semantics, simulator, and search budgets held fixed, does replacing the old learned value with a value head trained on the qualified T084 native-utility leaf targets improve Search v2 behavior?

This is a value-head-only repair. It is not a representation, policy, Search-topology, non-combat, or complete-run experiment.

## Accepted inputs

### T084 corrected leaf targets

T084 / PR #91 was accepted as `LEAF_CONTINUATION_UTILITY_TARGETS_READY`.

- accepted scientific head: `b5510a63d8070e54a729e65097ca01a05181237e`
- accepted report SHA-256: `b6cbcb5ee96d9538adb6ee7a4849a138f6d3a3f93b6127e7ba0ff91dcae1ad1c`
- accepted retention SHA-256: `754a9d2560fb5b01c53e7789bdd558e5ef3cc9d0eca4dd690f8f1ab8df1fb0f6`
- formal rows: exactly 960 qualified post-first-action internal leaves
- occupancy arms: 320 `unguided_search_v2`, 320 `prior_only_static_64001`, 320 `prior_only_static_64002`
- aggregate Act counts: 534 Act 1 / 426 Act 2
- selected continuation repetitions: `N=100`
- target: arithmetic mean of exact terminal native `evaluateEndState` values under pinned `playoutRandom`

Implementation must resolve and verify the exact retained formal-dataset identity from the accepted T084 retention manifest before training. Filename, row count, or local path alone is insufficient.

### T064 parent checkpoints

Use exactly these qualified T064 static formal checkpoints as frozen parent representations:

- static/64001: `c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193`
- static/64002: `32dbf18a187e8b6d465bb026d90643e3dd28624066628019c61455fcd8f5573a`

Both use the accepted hidden-size-16 architecture. Their historical value heads remain diagnostic comparators only; their survival-probability semantics are not valid native Search v2 leaf utility.

### Frozen hard cohort

Reuse the exact T052 93-record Boss/later-act cohort:

- SHA-256: `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`

### Code/native baseline

Publication base:

`main @ 039cd0c8985aea098c1d646fdff6889067890fbf`

Native Search semantic baseline remains the integration accepted by T084:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1555348535d66e3035aac80933a60949d4bd850f`

A material Search/native semantic change requires renewed Planner publication review.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Reuse mode: `scientific_quality_claim`.

Claim boundary: T085 may establish only whether the frozen value-head-only native-utility repair improves the accepted Search v2 controller under the paired battle evaluation defined here. It does not establish complete-run A20 improvement, Heart win-rate improvement, non-combat quality, representation optimality, or a general solution to imperfect information.

Required predicates: exact accepted T084 report/retention/formal-dataset identity; exact two T064 parent-checkpoint identities; exact T052 cohort identity; exact STSRL/native identities; valid public-only model inputs; value-head-only parameter invariance; explicit corrected target-kind metadata; deterministic fresh Cohort-B and Cohort-C source identities; valid restore/public-context parity; exact evaluation budgets/arms; complete generated checkpoint/cohort/report/retention identities.

Unavailable-fact behavior: any required identity, qualification fact, provenance field, restore/parity result, target statistic, checkpoint compatibility fact, or required retained artifact that is unknown, conflicting, stale, smoke-only, filename-inferred, malformed, or unavailable fails closed to `INCOMPLETE`. Evaluation support that is validly generated but insufficient for a frozen quota instead maps to `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`.

## Frozen scientific variable

The primary changed variable is the learned leaf-value target/consumer contract.

For each parent checkpoint, freeze every parameter and buffer outside the historical `outcome_head`, including:

- `state_encoder`
- `action_encoder`
- `policy_head`
- `hp_head`
- `resource_head`
- state/action normalization buffers
- public tactical/context feature schemas
- policy inference semantics

Only `outcome_head` may be reinitialized and trained.

Corrected target kind:

`search_v2_leaf_continuation_native_utility_v1`

The Search callback must receive a finite scalar in exact native `evaluateEndState` units. Do not apply sigmoid, `[0,1]` clipping, survival-probability interpretation, hand rescaling at the Search boundary, or any alternative utility conversion.

### Policy-invariance gate

For each repaired checkpoint:

1. every parameter/buffer outside `outcome_head` is byte-identical to its parent;
2. policy logits and normalized policy probabilities are identical to the parent on all 960 T084 formal public inputs and legal-action sets;
3. any mismatch is an integrity failure.

## Corrected value training

Produce exactly two repaired checkpoints:

- static/64001 -> repair seed `85001`
- static/64002 -> repair seed `85002`

Both consume the same exact 960 T084 formal rows. No outcome-conditioned row selection and no Search-outcome checkpoint selection are allowed.

### Target normalization

Compute one mean and population standard deviation over the exact 960 native-utility labels and retain both in checkpoint provenance.

Train:

```text
z = (native_utility - target_mean) / target_std
```

with mean squared error.

At inference, de-normalize exactly once:

```text
native_leaf_utility = z_pred * target_std + target_mean
```

and pass that scalar directly to Search v2.

Non-finite statistics, missing labels, or `target_std <= 0` are integrity failures.

### Frozen optimization budget

For each repair:

- reinitialize only `outcome_head` with the repair seed
- Adam, lr `0.001`
- betas `(0.9, 0.999)`
- epsilon `1e-8`
- weight decay `0`
- batch size `32`
- exactly `900` optimizer steps
- gradient clip norm `10.0`
- normalized-target MSE
- deterministic batch schedule derived from the repair seed
- no early stopping
- no learning-rate/model search
- step-900 checkpoint is the only candidate

Offline loss/MAE is diagnostic only and cannot establish Search improvement.

## Corrected inference surface

Add only the minimum backward-compatible surface needed to distinguish historical survival probability from corrected native leaf utility.

A corrected checkpoint must explicitly declare `search_v2_leaf_continuation_native_utility_v1` and expose native-utility prediction through a fail-closed metadata-gated path. Historical checkpoints keep their historical semantics. Do not silently reinterpret `battle_survival_probability` as native utility.

No Search topology, UCT, root selection, legality, callback location, native backup, terminal utility, chance/RNG behavior, or policy-prior semantics may change.

## Evaluation suite

All outcome comparisons are paired restored-battle comparisons at equal nominal Search simulations. This task measures guidance quality, not wall-clock-normalized controller strength. Retain wall clock, native/simulator steps, callbacks, and inference cost as diagnostics.

The three cohorts have intentionally different roles:

- Cohort A: historical hard regression/stress boundary;
- Cohort B: fresh independently generated Act-stratified coverage holdout;
- Cohort C: fresh current-policy natural occupancy sample.

### Cohort A — frozen hard regression

Use the exact 93-record T052 cohort unchanged. It is a stress cohort, not representative A20 occupancy.

### Cohort B — fresh assisted coverage holdout

Do not reuse the depleted T042 source pools as the evaluation population. Before any T085 model-guided outcome evaluation, generate one fresh coverage-only source pool with exactly 1,024 complete A20 runs using seeds `851001..852024`.

Freeze source-generation semantics to the already merged T042 `assist_hp75_potion` source-generation regime:

- battle controller: Oracle-like battle search, 20 simulations, accepted `highest_mean` semantics;
- non-combat controller: frozen `expert_non_combat_v1`;
- assistance schedule: exactly the merged `assist_hp75_potion` semantics;
- current pinned simulator/native identities;
- no repaired T085 checkpoint or T085 evaluation outcome may affect source generation.

This assisted source is only a coverage mechanism. It is not deployment evidence and does not become a training target.

Retain the complete source-run manifest before holdout selection. Then construct exactly 192 battle starts with quotas:

- 96 Act 1
- 96 Act 2+

Eligibility:

- A20;
- current-schema provenance valid;
- fresh restore succeeds;
- public-context replay matches;
- no truncation/controller/mapping/provenance failure;
- exact complete identity absent from the T064 selected 460 roots;
- exact complete identity absent from frozen T044 evaluation cohorts and T052;
- selection reads no source battle outcome, terminal HP, teacher/model output, deck/relic quality, or perceived winnability.

Within each Act cell, sort eligible records by SHA-256 of the accepted complete source identity and take the first 96. Do not impose a room-type quota; report MONSTER/ELITE/BOSS distribution instead. T052 already supplies the dedicated Boss/later-act stress boundary.

Exact duplicate complete identities are an integrity failure, not silently deduplicated. If the fixed 1,024-run source pool cannot provide both 96-record Act quotas after exclusions and validation, classify `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`; do not add runs or relax quotas after seeing availability.

Freeze and hash the 192-record cohort manifest before any model-guided outcome aggregation.

### Cohort C — fresh current-policy occupancy

Generate exactly 128 standard-start A20 runs with seeds `850001..850128` using:

- battle controller: unguided Search v2, 100 simulations, accepted `highest_mean` semantics;
- non-combat controller: frozen `expert_non_combat_v1`;
- no assistance;
- current pinned simulator/native identities.

This defines current baseline occupancy only; `expert_non_combat_v1` is not a learning target.

From each run with at least one valid restorable battle start, choose exactly one start by deterministic SHA-256 ranking over `(source run identity, battle complete identity)`. This prevents long runs from dominating. Selection must not use battle outcome or depth preference.

Require at least 96 selected valid records. Otherwise classify `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`. Report Act/room/depth distribution rather than forcing later-act quotas; shallow occupancy is itself evidence about the current controller.

### Search@400 guard subset

From frozen Cohort B, select 48 records before outcomes by deterministic hash ranking:

- 24 Act 1
- 24 Act 2+

Evaluate this subset at 400 simulations. T085 does not reopen T070's 1600-simulation study.

## Primary value-only arms

On Cohorts A, B, and C at Search v2 budget 100, use matched restored records and matched Search randomness/configuration:

1. `baseline`: no policy prior, no learned leaf value
2. `old_value_64001`: historical static/64001 survival-probability callback
3. `corrected_value_85001`: repaired static/64001 native-utility callback
4. `old_value_64002`: historical static/64002 survival-probability callback
5. `corrected_value_85002`: repaired static/64002 native-utility callback

Old-value arms are diagnostic comparators only and do not revalidate the old contract.

On the 48-record budget-400 subset run only:

- `baseline@400`
- `corrected_value_85001@400`
- `corrected_value_85002@400`

## Secondary prior/value compatibility

On Cohort B at budget 100 only, run:

- `prior_only_64001` vs `prior_corrected_85001`
- `prior_only_64002` vs `prior_corrected_85002`

Each pair must use the byte-identical parent policy path. These are secondary compatibility diagnostics and cannot rescue a failed primary classification.

Do not reopen the closed T047-T059 root-prior allocation-repair route.

## Required metrics

For every cohort/arm retain at least:

- battle survived/lost
- exact terminal native `evaluateEndState` utility
- final HP and turn count where available
- selected root action identity
- simulator/search step counts
- learned-value callback count
- wall-clock duration
- failure reason

For every paired comparison report:

- total wins
- baseline-only and comparator-only wins
- paired win delta
- per-record native-utility delta
- mean/median native-utility delta
- deterministic percentile-bootstrap confidence interval for mean utility delta

### Frozen bootstrap rule

For Cohort B per record:

```text
corrected_mean = mean(U_corrected_85001, U_corrected_85002)
old_mean       = mean(U_old_value_64001, U_old_value_64002)

delta_old  = corrected_mean - old_mean
delta_base = corrected_mean - U_baseline
```

Use 10,000 paired bootstrap resamples of Cohort-B records with replacement, seed `85085`. Report 2.5th/97.5th percentiles of the resampled mean for `delta_old` and `delta_base`. The sampling unit is the battle record, not callbacks/tree nodes.

## Terminal classifications

Emit exactly one terminal scientific classification unless execution/integrity is incomplete.

### `CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED`

Require all:

1. Cohort-B 95% bootstrap lower bound for mean `delta_old` > 0.
2. Cohort-B 95% bootstrap lower bound for mean `delta_base` > 0.
3. On Cohort B, each corrected seed has at least as many wins as baseline and its corresponding old-value arm.
4. On Cohort A, each corrected seed has at most one fewer win than baseline and non-negative mean native-utility delta versus baseline.
5. On Cohort C, each corrected seed has at most one fewer win than baseline and non-negative mean native-utility delta versus baseline.
6. On the Search@400 guard, each corrected seed has at most one fewer win than baseline@400 and non-negative mean native-utility delta versus baseline.
7. All artifact, policy-invariance, checkpoint, source/cohort, restore/parity, execution, and retention gates pass.

This establishes only a bounded corrected-value Search signal.

### `CORRECTED_VALUE_SEARCH_HARM_CONFIRMED`

Use only when integrity/support are valid and Cohort B shows both:

- 95% bootstrap upper bound for mean `delta_base` < 0; and
- both corrected seeds win fewer Cohort-B battles than baseline.

This closes the current value-head-only repair as harmful under the frozen representation/Search contract.

### `CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED`

Use for every valid sufficiently supported result satisfying neither positive nor harmful criteria. Mixed seeds, utility-only movement without win guardrails, isolated hard-cohort gains, or positive secondary prior/value compatibility do not upgrade the result.

### `VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT`

Use when retained scientific inputs and training are valid but either frozen Cohort-B or Cohort-C support requirements cannot be met. Do not change run counts, quotas, or selection rules after observing availability.

### `INCOMPLETE`

Use for artifact/code/native mismatch, invalid provenance, policy-invariance failure, malformed/non-finite targets or inference, failed required restore/parity, execution failure, or retention integrity failure. `INCOMPLETE` is not a scientific result.

## Required artifacts

Retain under one stable ignored T085 root:

- exact input/eligibility manifest resolving T084 formal data;
- two repaired checkpoint files and training reports;
- target normalization and deterministic batch-plan identity;
- policy-invariance audit against both parents;
- Cohort-B 1,024-run source manifest and selected 192-record manifest;
- Cohort-C 128-run source manifest and selected occupancy manifest;
- Search@400 subset manifest;
- primary and secondary paired evaluation reports;
- terminal classification report;
- retention manifest with hashes, sizes, schemas, commands, code/native identities, effective worker counts, wall-clock cost, regeneration path, compatibility boundary, and deletion conditions.

Large generated artifacts remain outside Git.

## Verification requirements

Before final acceptance verify at minimum:

- T081 scientific eligibility guard;
- exact T084 report/retention/formal-dataset identities and 960-row semantics;
- exact T064 parent checkpoints;
- native-unit de-normalization with no sigmoid/clipping;
- every non-`outcome_head` tensor/buffer byte-identical to parent;
- policy logits/probabilities unchanged on all 960 T084 public inputs;
- deterministic outcome-head reinitialization and 900-step reproduction;
- historical checkpoint inference remains backward-compatible and semantically distinct;
- Cohort-B exact 1,024 seeds/source-generation semantics, pre-outcome source freeze, exclusions, quotas, hash selection, restore/public-context validity, and no outcome-conditioned selection;
- Cohort-C exact seeds/controller and one-record-per-run deterministic selection;
- equal-budget paired Search configuration and matched randomness;
- independent tests for bootstrap/classification logic including every terminal class;
- standard compileall, Ruff, format, diff, mock, and relevant test gates;
- substantial simulator stages report configured/effective concurrency and retained shard/failure evidence.

## Explicitly out of scope

- changing shared encoders, policy, HP/resource heads, hidden size, features, identity encoding, embeddings, architecture, or normalizers;
- policy supervision from T084 internal-leaf rows;
- recollecting T084 targets or changing `N=100`;
- changing Search v2 topology, UCT, allocation, root selection, callback location, native backup, or terminal utility;
- root-prior allocation repair variants;
- T034 hidden-future sampling;
- T079 transposition work;
- complete-run A20 outcome comparison for the repaired Battle controller;
- training/modifying a non-combat learner;
- T063/T066 promotion;
- human trajectories, labels, card rankings, deck heuristics, or imitation targets.

## Successor boundary

Any valid T085 scientific result—improvement established, improvement not established, or harm confirmed—closes this Battle value-repair round. Do not publish another Battle value variant merely because T085 is neutral or harmful.

The next Planner priority is a separate minimal self-generated Non-Combat learning task with Battle frozen:

- if T085 establishes improvement, the accepted corrected Battle controller may be considered as that task's frozen Battle side;
- otherwise use the strongest already accepted non-learned/unguided Battle Search baseline.

That Non-Combat task must independently precommit train/checkpoint/final-test seed separation, public-information inputs, complete-run occupancy/reachability metrics, and no imitation of `expert_non_combat_v1`.

Only after Battle and Non-Combat each have at least one credible independently evaluated learned improvement should T066 be rewritten into a true alternating improvement loop, freezing one side while updating the other and retaining a mixture of frozen anchors, current-policy occupancy, and later-act/coverage curriculum.

`VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT` or `INCOMPLETE` authorizes only the minimum recovery needed to complete T085; it does not authorize new Battle science.

## Planner publication boundary

This is the Phase-A specification-publication contract. The accompanying Task Index proposes `READY`, but T085 remains non-executable while this publication PR is unmerged.

Publication requires Maintainer exact-head `SPEC APPROVED` with `publication_authorized=true`. After that approved head is merged, T085 becomes executable and implementation must begin on a fresh implementation branch/PR from the resulting synchronized `main`.

No T085 training, source generation, simulator evaluation, or scientific execution is authorized before publication merge. A material change to the value-only freeze, training budget, evaluation source/cohorts, Search arms, or terminal classification requires renewed publication review.
