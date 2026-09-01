# T083: Battle Search v2 Leaf-Value Target Contract Audit

## Objective

Define the scalar value quantity that a learned Search v2 leaf evaluator must predict before any value-target retraining is authorized.

T082 confirmed one defect in the current value path: Oracle-improved policy targets and realized source-behavior outcome targets do not share continuation-policy semantics. After T082 merged, Planner inspection exposed a second independent defect candidate: Search v2 inserts the checkpoint's `[0,1]` battle-survival probability directly into the same native backup accumulator that otherwise receives `BattleScumSearcher2::evaluateEndState`, a continuous terminal utility on a very different scale.

T083 is therefore a target-contract audit, not a training task. It must answer:

> Can an existing retained T064 native-scale teacher quantity be rigorously reused as the learned Search v2 leaf target, or is a new internal-leaf continuation-utility target generation stage required?

The task must keep three questions separate:

1. **continuation semantics** — which policy/search continuation defines the value;
2. **utility semantics and units** — which terminal utility is being predicted and backed up;
3. **state-support semantics** — which states receive value supervision relative to the Search v2 leaf invocation boundary.

## Accepted starting evidence

### T082

T082 / PR #88 is accepted and merged.

Frozen formal report:

- schema: `t082-value-target-semantic-closure-v1`;
- SHA-256: `e1435812abed86d9ddb4c857cba1863edf852f1e956db9fc002e043a4eb2febc`;
- total qualified rows: 460;
- behavior recoverable: 320;
- teacher/behavior same: 149;
- teacher/behavior different: 171;
- divergence rate on auditable rows: `0.534375`;
- divergent rows with available source outcome: 171;
- terminal classification: `VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED`.

T083 must not reopen or weaken this accepted conclusion.

### T064 retained training lineage

The qualified T064 lineage remains the primary existing teacher/trainer evidence:

- curriculum manifest SHA-256 `a111e082d4bc11e03bc5b785a814c422619404245ddda55c2954be09dded46c7`;
- training report SHA-256 `3e838bed72f5ca565532d39d77b1991e0d32919dcd9b1d6afe4d2c8f8ecdc38c`;
- stage summary SHA-256 `5748e79a23152fa51475f8cb7359c81816d6bbdd26ed2a10d7489f1853b6b880`;
- transfer decision SHA-256 `f8407acbc17cb13bba53009c91009fea961e7307071d54b0ff82147ff092603f`;
- Oracle teacher SHA-256 `1352eb301509f258ae92509b804125d59d2da17ef5f7f6e5b81131f11e1d0d72`;
- trainer input SHA-256 `aae847505ece7c4d535d08cffc9e24bc2aaead334234332f41c69f0b2c99bada`;
- 460 selected / teacher / trainer rows;
- Act 1: 256, Act 2: 204;
- teacher: full-simulator-state Oracle-like, 100 simulations, `highest_mean`, no potions, soft visit policy target.

The existing teacher rows expose native root-search quantities including root action `evaluation_sum` / `mean_value`, selected teacher-action mean value, and native search best/min action values. T083 must inspect their exact producer semantics rather than infer meaning from field names.

### Code/native baseline

STSRL baseline for this proposal:

`main @ 2a0b36b5e7ea700f34ebde8288b0b1cf809ee080`

Native baseline:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 1555348535d66e3035aac80933a60949d4bd850f`

Current native terminal backup is `BattleScumSearcher2::evaluateEndState`.

At this native head:

```text
victory:
100 * (35 + current_hp + 4*potion_count - 0.01*turn)

non-victory:
(1 - remaining_non_minion_monster_hp_ratio) * 10
- monsters_alive
- 0.2 * energy_wasted   [except the existing spiker special case]
+ 0.03 * cards_drawn
+ 2 * potion_count
+ 0.2 * turn
```

Search v2's learned leaf callback is fed directly to `updateFromEvaluation()` after the first action from a newly expanded node.

Current STSRL obtains `battle_survival_probability = sigmoid(outcome_logit)` and returns that float directly to the native leaf callback. T083 must verify whether any normalization, transformation, or alternate backup boundary exists; absence must be reported explicitly rather than assumed.

## Artifact Eligibility Contract

Artifact Eligibility Required: true

Reuse mode: `diagnostic_mechanism`.

Consumed learning artifacts are not being used to claim model quality. They are used only to establish the exact existing target/search contract and whether a retained scalar definition is reusable.

### Required predicates

The audit must fail closed unless all relevant consumed artifacts satisfy their exact frozen identity and schema/provenance checks:

- T082 formal report identity above and accepted terminal classification;
- T064 compact artifacts, teacher, and trainer identities above;
- exactly 460 T064 teacher/trainer rows with the accepted Act/component distribution;
- T064 teacher configuration exactly 100 simulations, `highest_mean`, no potions, `full_simulator_state_oracle_like`;
- no T043 four-row smoke artifact may substitute for the T064 lineage;
- current STSRL and native code identities used for semantic inspection must be recorded exactly;
- any missing or conflicting producer/consumer provenance makes the affected candidate unavailable; it must not be guessed from naming or numeric range.

These predicates qualify the artifacts for this contract audit only. They do not make T064 checkpoints broad model-quality evidence.

## Required audit

### 1. Native terminal utility and backup path

Produce a versioned static/code-backed report that records:

- the exact `evaluateEndState` formula for victory and non-victory outcomes;
- all inputs used by that formula;
- where terminal playout values enter node `evaluationSum` / mean values;
- where learned leaf values enter the same or a different accumulator;
- every transformation between Python callback output and native backup;
- whether root `mean_value` is expressed in the same exact units as `evaluateEndState`.

If the learned leaf value does not share the native terminal utility units and no explicit conversion exists, record `current_leaf_utility_alignment=false`.

Do not call this alone proof that value learning caused the T070 outcome regression.

### 2. Current checkpoint value contract

Record from current code and checkpoint schema:

- value-head target kind;
- training target producer;
- loss/link function;
- inference transformation;
- theoretical inference range;
- Search v2 consumer field and callback boundary.

The report must explicitly distinguish `battle survival probability` from native terminal utility.

### 3. Existing T064 native-scale candidate inventory

Stream the exact T064 teacher artifact and inventory every candidate scalar that could plausibly define a state/leaf value, at minimum:

- selected `teacher_action.mean_value`;
- maximum/root-selected `root_statistics[*].mean_value`;
- `native_search_report.best_action_value`;
- soft-visit-weighted root mean if it can be computed exactly from retained visits and means;
- source realized terminal utility if it can be reconstructed exactly from retained source outcome/resource state.

For every candidate, report:

- exact field/source and schema;
- units / relationship to `evaluateEndState`;
- whether it is state-value or action-value conditional;
- search budget and root-selection dependence;
- continuation/search policy semantics that are actually proven;
- availability over all 460 rows;
- finite-value count;
- min, median, mean, p05, p95, max;
- equality/consistency relationships among duplicate-looking fields.

No candidate may be declared reusable merely because its numeric scale resembles the native search values.

### 4. Search-leaf state-support boundary

Prove from current code and T064 artifact provenance where value supervision states are sampled versus where Search v2 invokes learned values.

At minimum report:

- T064 training rows are restored source decision/battle-start states or another precisely demonstrated state class;
- Search v2 learned values are requested after the first action from newly expanded internal nodes;
- whether the retained T064 artifact contains exact supervised rows at those internal leaf states;
- whether any existing artifact defines a deterministic transformation from a T064 root target into the required internal-leaf target.

Absence of internal-leaf labels is not by itself proof that a value function cannot generalize. It is, however, relevant to whether the **existing retained labels** are sufficient for a controlled target repair without new label generation.

### 5. Candidate semantic decision table

For each candidate target definition, evaluate these gates separately:

1. **utility gate** — exact same native `evaluateEndState` utility units, or an explicit invertible/versioned transformation proven at both training and Search consumption;
2. **continuation gate** — the target has a named, reproducible continuation/search policy semantics compatible with the intended leaf evaluator; T082 source-behavior continuation does not pass this gate;
3. **state-target gate** — the scalar is a well-defined value of the input state rather than an action-specific quantity without a predeclared aggregation rule;
4. **leaf-support gate** — existing retained labels either cover the Search v2 leaf state class or the candidate's target-generation mechanism can be applied to those leaves without changing the scientific meaning;
5. **information/provenance gate** — teacher may use hidden simulator state during target generation, but deployable model input remains public and the hidden-information provenance is explicit;
6. **artifact gate** — all T081 eligibility predicates pass.

The audit must distinguish:

- **definition reusable**: the target definition/generator can validly be applied to new leaf states;
- **retained labels sufficient**: the existing T064 rows themselves are enough for the next paired retraining experiment.

Do not collapse these into one boolean.

## Terminal classifications

Exactly one terminal classification must be emitted.

### `EXISTING_T064_LEAF_VALUE_LABELS_REUSABLE`

Use only if all of the following are proven:

- current survival-probability direct backup is not retained as the value target unless an exact utility conversion is proven;
- one retained T064 scalar target passes utility, continuation, state-target, leaf-support, information/provenance, and artifact gates;
- the existing 460 retained labels are themselves sufficient for a controlled paired value-only target repair without generating new value labels;
- no unresolved target-definition ambiguity remains.

This authorizes consideration of a bounded paired retraining/evaluation successor using the exact retained labels. It does not authorize training inside T083.

### `NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED`

Use when the current value path is demonstrably unsuitable for direct Search v2 backup and no existing retained T064 label set satisfies all gates, but a precise target definition or target-generation mechanism can be specified from accepted simulator/search surfaces.

The report must name the minimum required successor data product, including:

- target scalar definition;
- terminal utility definition;
- continuation/search policy definition;
- state sampling boundary;
- hidden/public information boundary;
- required calibration or budget-stability checks;
- what old fields remain auxiliary diagnostics rather than the new value label.

This classification authorizes consideration of a separate target-generation/paired-repair task. It does not authorize generating those labels inside T083.

### `LEAF_VALUE_TARGET_CONTRACT_UNRESOLVED`

Use when current code/artifacts are sufficient to show a problem but insufficient to define a scientifically valid target or bounded generator without a material new Search/native design decision.

No automatic training successor follows. Planner must compare the cost of resolving the value contract against moving to feature/encoding diagnosis.

### `INCOMPLETE`

Use only for failed artifact/code identity, malformed required input, non-reproducible producer semantics, or execution/report integrity failure. It is not a scientific classification.

## Decision constraints

- T082 continuation mismatch remains accepted regardless of T083 outcome.
- A `[0,1]` survival label cannot be accepted as a drop-in native leaf utility merely because survival is strategically important.
- Native `best_action_value` / root means cannot be accepted merely because they use native utility units.
- Search-budget dependence must remain part of target provenance; do not silently treat a finite-budget search estimate as a policy-independent ground truth.
- Do not infer normal-information optimality from a full-state Oracle teacher. T034 remains the separate information-set problem.
- Do not interpret target-contract defects as evidence for or against feature encoding or model architecture.

## Out of scope

- training or fine-tuning any checkpoint;
- changing model architecture, feature encoding, categorical identity representation, loss weights, optimizer, or hidden size;
- changing Search v2 topology, UCT/allocation, root selection, native terminal utility, or callback boundary;
- new native API development unless required only for a read-only diagnostic, in which case return to Planner before implementation;
- T079/transposition work;
- T034 hidden-future sampling;
- T063/T066 promotion;
- complete-run reachability or later-act scale-up;
- human trajectories, human labels, human rankings, or handcrafted policy targets.

## Deliverables

- versioned leaf-value target-contract audit report;
- exact code/provenance evidence for native terminal utility, learned-leaf backup, and checkpoint value producer/consumer chain;
- bounded-memory T064 candidate-target statistics and consistency report;
- explicit state-support comparison between T064 supervision and Search v2 internal leaf invocation;
- candidate semantic decision table with every gate above;
- exactly one terminal classification and one bounded next recommendation;
- stable ignored retention manifest with hashes, sizes, schemas, code/native identities, commands, worker count, wall-clock cost, and deletion conditions.

## Required verification

- standard local test/lint/format/compile/diff gates;
- task-document guard including the T081 Artifact Eligibility Contract;
- focused tests for candidate classification, missing/invalid artifact identity, non-finite candidate values, action-value/state-value distinction, utility-unit mismatch, absent continuation proof, absent leaf support, and terminal classification;
- exact current-main code identity check;
- exact native integration identity check;
- if the 460-row teacher artifact is scanned, use bounded-memory streaming and report worker count/reason. This audit is non-simulator and does not need artificial 16-way sharding.

## Planner handoff boundary

This specification is a proposal only. The merged task index must remain unchanged during independent review.

Implementation and scientific execution require Maintainer exact-head `SPEC APPROVED` and `implementation_authorized=true`.

After an accepted T083 terminal classification, update research ledger #85 before publishing any value-target generation or retraining successor.
