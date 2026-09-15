# T090: Search-v2 Action-Utility Battle Student Distillation Gate

## Objective

Establish whether the accepted frozen Battle planner, unguided Search v2 @400, can provide self-generated supervision from which a **public-information, action-conditioned Battle student** learns a reproducible held-out action-ranking signal.

T090 asks one bounded question:

> On Battle states generated from the exact accepted T087 matched Battle-start cohort, does training an action-conditioned public-only scorer on Search-v2@400 root action utilities reduce held-out Search-teacher regret relative to an otherwise identical shuffled-target control, without introducing hidden-state inputs or reopening a closed Search-guidance mechanism?

This is a Battle-student **distillation/local-learnability** task. Search v2 @400 is a frozen privileged teacher/planning operator. Search itself is not trained. T090 does not integrate the student into Search and does not claim that a learned Battle controller improves complete runs.

A positive result may justify one separate successor task that tests the trained student at a scientifically new Search location such as rollout action proposal/rollout policy. It does **not** authorize root-prior allocation, learned leaf-value integration, T066 alternating co-improvement, or a deployment claim.

## Publication Baseline

Planner publication base:

`main @ 76897afc17410dc1f03072596328873dc906ce0b`

Canonical simulator identity at publication:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 20a6c2b3a9cea817c988178b814f083ff889853f`

Accepted scientific context:

- T087: exact 413-row matched Battle-start cohort with source groups A/B/C = 93/192/128 and dense terminal diagnostics;
- T088: `STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED`; unguided Search v2 @400 is the strongest accepted non-learned Battle baseline on that cohort;
- T089: local self-generated Non-Combat learnability signal existed, but fresh complete-run improvement was not established (`NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`);
- T066 remains DRAFT and is not authorized;
- the root-prior allocation-repair route and learned Battle leaf-value repair route remain closed;
- T079 exact-transposition work remains parked.

T090 is therefore an independent Battle-side local-learnability experiment under the fixed planning operator, not a claim of mutual co-evolution.

## Dependencies

Required accepted dependencies:

- T011: `public-tactical-v2` Battle-state feature contract;
- T016: public-context provenance/audit boundary;
- T025/T062: native Search telemetry and Search-v2 controller surface;
- T078: restore/public/legal-action fidelity;
- T081: scientific artifact eligibility contract;
- T085: accepted evidence closing learned leaf-value repair and retaining Search-v2@400 as a valid unguided comparator;
- T087: exact matched Battle-start cohort and amended dense terminal semantics;
- T088: frozen Search-v2@400 Battle teacher/controller baseline.

T089 is research context but not a learning-artifact dependency.

## Closed-Route And Scope Boundaries

T090 must not:

- change Search-v2 simulations, UCT/allocation, root selection, rollout policy, terminal utility, or native transition semantics;
- inject the new student as a root prior, root visit-allocation signal, post-search root-selection bonus, or learned leaf value;
- tune or reopen T046--T059 root-prior variants;
- retrain or reuse the T085 leaf-value head as the T090 learner;
- add exact transposition/state-identity work;
- change Battle action-space semantics;
- train Non-Combat policy components;
- use human trajectories, human action labels, card/deck rankings, or strategy imitation;
- run fresh complete A20 natural-run evaluation;
- claim live-game/public-search strength from simulator-side teacher distillation.

Search-v2@400 is a teacher only in this task.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

### Inputs

Required scientific inputs are:

- exact T087 413 Battle-start occurrence-safe identities and canonical ordering;
- exact T087 restore/source bindings required to restore those starts;
- exact accepted Search-v2 controller semantics from current `main`;
- exact canonical native identity and source-manifest binding;
- current `public-tactical-v2` Battle state projection and public legal-action identity contract.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T090 may claim only whether Search-v2@400 privileged root-action statistics contain a reproducible **public-input distillation signal** on a held-out subset of the frozen T087 Battle-start distribution.

T090 does not claim Search improvement, standalone Battle-controller superiority over Search-v2@400, complete-run/Heart improvement, normal-information Search correctness, absence of all hidden-state ambiguity in the teacher, deployment readiness, or Battle/Non-Combat co-improvement.

### Required predicates

Scientific consumption requires exact source identity/provenance, exact T087 record/split identity, exact native commit and source verification, exact teacher configuration, exact public student encoding identity, no hidden simulator fields in student inputs, complete target/split/training/held-out reports, and no smoke/canary artifact used as representative evidence.

### Unavailable-fact behavior

Missing, malformed, conflicting, filename-inferred, default-inferred, or unavailable provenance/identity/schema/restore/public-input/action-map/teacher-row facts fail closed to `INCOMPLETE`.

## Frozen Teacher

Teacher/controller for target generation:

- native Search v2 / `BattleScumSearcher2`;
- simulations per decision: `400`;
- root selection: `highest_mean`;
- policy prior: none;
- learned leaf value: none;
- rollout: frozen native random rollout;
- terminal utility: frozen native `evaluateEndState`;
- action space: `ActionSpaceConfig.initial_no_potions()`;
- information regime: `full_simulator_state_oracle_like`.

The teacher may use copied full simulator state for forward simulation because this is training-time privileged assistance. That privilege must never enter the student input tensor.

## Source Distribution And Split

Use the exact accepted T087 413 Battle-start records, with no reselection or substitute records.

All Battle decisions generated from one restored Battle start inherit that start's split. A trajectory must never cross train/validation/held-out splits.

Within each frozen T087 source group, apply a deterministic seeded permutation with split seed `900090`, then assign exact counts:

| T087 source group | Train | Validation | Held-out | Total |
|---|---:|---:|---:|---:|
| A | 58 | 14 | 21 | 93 |
| B | 119 | 30 | 43 | 192 |
| C | 79 | 20 | 29 | 128 |
| **Total** | **256** | **64** | **93** | **413** |

The split manifest must materialize exact ordered record identities and SHA-256 before formal target generation.

## Teacher Trajectory And Target Generation

For every restored Battle start in canonical split order:

1. restore the exact accepted checkpoint/RNG state with no post-restore reseed;
2. verify public projection and legal-action parity under the current native binding;
3. at every Battle decision reached under frozen Search-v2@400 control, retain exact source/decision identity, a process-valid checkpoint for same-run diagnostics, public student-visible state, ordered legal-action identities, Search `root_rows`, per-action visit count and finite `mean_value`, selected action, and Search provenance/cost counters;
4. select the actual action using frozen Search-v2@400 and continue to authoritative Battle terminal;
5. retain T087-compatible terminal outcome/dense diagnostics for distribution audit only.

A multi-action decision is target-eligible only when every legal action maps exactly once to a root row with `visits > 0` and finite `mean_value`. Single-action decisions are retained for coverage but excluded from learning metrics. No missing action mean may be imputed and no outcome-conditioned retry is allowed.

### Target coverage gate

Before training require:

- all 413 Battle starts restore and execute validly or the task fails closed;
- at least `1,500` unique eligible multi-action decision states after leakage/deduplication handling;
- at least `750` train, `150` validation, and `250` held-out eligible states;
- at least `95%` of observed multi-action decisions are target-eligible;
- every split retains source groups A/B/C.

If valid generated evidence fails one predicate, classify `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT` and stop before training.

## Public-State Leakage And Duplicate Boundary

Student input is restricted to the accepted public Battle-state representation derived from `public-tactical-v2` / sanitized public projection plus the current legal action's public identity/parameters.

Forbidden inputs include checkpoint bytes, simulator RNG, hidden draw order, unrevealed future content, native tree statistics, root visits/means, split id, terminal outcome, or future-transition-derived features.

Compute a versioned exact fingerprint of the student-visible decision state plus ordered legal-action identities before training.

- A fingerprint appearing in more than one split is excluded from all train/validation/held-out learning metrics and its multiplicity/source records are reported.
- Within one split, exact duplicate fingerprints are deduplicated to one canonical example and multiplicity is reported.
- Split membership is never reassigned after target values are observed.

If collision removal breaks the coverage gate, stop as `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT`.

## Student Model Contract

Train one versioned public-only action-conditioned scalar scorer:

```text
f_theta(public_battle_state, legal_action_public_identity) -> scalar score
```

At inference, score each legal action independently and select max score; ties use canonical legal-action order. The model emits no value head and does not call Search during inference.

Formal architecture family:

- deterministic public feature/action encoding;
- concatenated state/action input;
- two hidden layers, width `256`, ReLU;
- scalar output;
- no recurrent state, attention, tree input, or hidden simulator fields.

Tensor packing/module names are implementation freedom, but encoding schema, fields, dimensions, normalization, architecture, optimizer, and training schedule must be frozen in a formal configuration artifact before training. No hyperparameter sweep is permitted.

## Training Target And Loss

For eligible state `s`, let Search root mean be `q_teacher(s,a)`.

Primary target is within-state action ordering. Use pairwise logistic ranking loss over action pairs whose teacher means differ by more than `1e-9`; ties create no ordered pair. Raw teacher means are retained for held-out regret diagnostics and are not redefined as a new learned value target.

Formal training defaults:

- AdamW;
- learning rate `1e-3`;
- weight decay `1e-4`;
- maximum `30` epochs;
- batch unit = decision states, maximum `256` states per batch;
- validation checkpoint/seed selection only by lower mean teacher regret;
- initialization seeds `900091`, `900092`, `900093`;
- choose one candidate checkpoint using validation data only.

Gradient accumulation may preserve the same effective batch if memory requires it; this is not a hyperparameter search.

## Shuffled-Target Negative Control

Train an otherwise identical control that destroys the state/action-to-teacher association while preserving examples and marginal target values.

For each train/validation state independently, deterministically permute its teacher action means across legal actions using a seed derived from `900190` plus the exact public-state fingerprint.

The control uses the same inputs, architecture, optimizer/schedule, initialization seeds `900091..900093`, and validation-only selection rule. Held-out labels are never permuted and are never used for model/seed selection.

## Held-Out Metrics And Primary Gate

On every eligible held-out state, using true unpermuted Search-v2@400 root means, report at minimum top-1 teacher-action agreement, pairwise ranking accuracy, mean/median/90th/95th-percentile teacher regret, source-group breakdown, action-kind breakdown, score-margin distribution, and tie rate for student and shuffled control.

Define:

```text
a_m(s) = argmax_a f_m(s,a)
regret_m(s) = max_a q_teacher(s,a) - q_teacher(s,a_m(s))
delta_regret(s) = regret_control(s) - regret_student(s)
```

Positive `delta_regret` means the true-label student selected an action closer to the teacher's preferred root utility than the shuffled-target control.

Primary paired bootstrap:

- replicates: `20,000`;
- seed: `900290`;
- statistic: mean `delta_regret`;
- two-sided 95% percentile CI.

Also report paired bootstrap for top-1 agreement difference as secondary evidence.

T090 establishes local Battle-student distillation only if all validity/coverage predicates pass and:

1. the 95% CI lower bound for mean `delta_regret` is strictly greater than `0`;
2. student mean teacher regret is strictly lower than control;
3. student top-1 teacher-action agreement is strictly higher than control;
4. no information-boundary or split-leakage violation is present.

A positive result means Search-generated action-ranking supervision is locally learnable from public inputs on held-out T087 Battle occupancy. It does not mean Search or complete-run performance improved.

## Optional Counterfactual Battle Diagnostic

After the primary held-out report exists, one bounded same-state counterfactual diagnostic is allowed only with separate Maintainer authorization.

Select up to `256` eligible held-out decision checkpoints by deterministic hash order with seed `900390`. For each state:

- branch S: force the student's selected action once, then continue Battle with frozen Search-v2@400;
- branch C: force shuffled-control action once, then continue with frozen Search-v2@400;
- identical selections are exact paired ties without duplicate execution;
- both branches start from the same checkpoint/RNG state with no reseed;
- report authoritative Battle outcome transitions, accepted T087 dense diagnostics, and Search cost.

This diagnostic is corroborating only; no T087 dense metric becomes a scalar reward or weighted promotion score.

## Terminal Classifications

Exactly one terminal classification must be recorded.

### `BATTLE_STUDENT_DISTILLATION_SIGNAL_ESTABLISHED`

All validity/coverage predicates and the formal held-out gate pass.

Consequence: Planner may consider a separate successor that tests the student at a scientifically distinct Search location such as rollout action proposal/policy. T090 itself does not authorize integration.

### `BATTLE_STUDENT_DISTILLATION_SIGNAL_NOT_ESTABLISHED`

Formal evidence is valid and coverage sufficient, but a held-out success predicate fails.

Consequence: do not integrate this student into Search and do not repeatedly tune the same target/model without a new mechanism-level hypothesis.

### `BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT`

Generation is valid but the preregistered scale/coverage predicates fail.

### `BATTLE_STUDENT_INFORMATION_BOUNDARY_INVALID`

A hidden/non-public field entered student inputs, split leakage could not be removed under the frozen rule, or required provenance cannot establish the information boundary.

### `INCOMPLETE`

Required restore, native identity, root-row mapping, artifact identity, training, or formal report evidence is missing/invalid.

## Execution Authorization

Default serial one-task/one-PR workflow applies.

No implementation or scientific execution may begin before Maintainer exact-head approval:

```text
SPEC APPROVED

task: T090
approved_spec_commit: <full SHA containing this contract>
implementation_authorized: true
```

After spec approval:

1. implementation, unit tests, split/materialization code, training plumbing, and mock tests may proceed on the same PR;
2. one bounded 12-start canary requires separate Maintainer canary authorization and is mechanics/coverage validation only;
3. full 413-start target generation/training/held-out evaluation requires separate Maintainer formal authorization after canary review;
4. optional counterfactual Battle diagnostics require separate authorization after the primary held-out report;
5. failed scientific canary/formal execution gets no free retry; material scientific changes require Planner amendment plus renewed exact-spec approval.

## Required Deliverables Before Final Acceptance

The same PR must contain or durably reference:

- exact split manifest and SHA-256;
- target-generation configuration/provenance;
- target coverage and collision/deduplication report;
- exact formal training configuration;
- selected candidate/control checkpoint identities and hashes;
- training/validation summaries for all allowed seeds;
- complete held-out statistics report;
- optional counterfactual report if authorized;
- retained-artifact manifest for scientific-quality artifacts kept outside Git;
- factual terminal classification and claim boundary;
- final task-index lifecycle/result update;
- `docs/current_status.md` factual result update before dual final acceptance whenever practical.

Maintainer final implementation/operational acceptance and Planner final scientific/architecture acceptance must refer to the same exact final PR head before landing.

## Successor Boundary

Even after `BATTLE_STUDENT_DISTILLATION_SIGNAL_ESTABLISHED`, the next scientific question is separate:

```text
Does using the public Battle student at a new, non-root-prior, non-leaf-value
Search location improve Search itself on a matched Battle cohort?
```

A likely successor may test student-guided rollout action proposal/policy against frozen unguided Search-v2 under matched compute. That successor must preregister its own mechanism, information boundary, cost accounting, cohort, and promotion gate.

T066 remains unauthorized until both Battle and Non-Combat sides demonstrate credible policy-improvement operators beyond local fit/distillation evidence.