# T089: Frozen-Search Self-Generated Non-Combat Policy Improvement

## Objective

Establish the first scientifically qualified learned Non-Combat policy-improvement operator after T088 while keeping Battle fixed to the accepted non-learned planner.

T089 asks one falsifiable question:

> With Battle fixed to unguided Search v2 @400, can a public-information action-conditioned Non-Combat ranker trained only from fresh simulator-generated counterfactual continuation returns outperform `expert_non_combat_v1` on held-out decisions and then improve fresh matched A20 complete-run progress?

This is the first **asymmetric bootstrap** step after T088. Search v2 @400 is a frozen simulator-side Battle teacher/controller and planning operator. It is not a trainable member of this task, and T089 does not claim joint Battle/Non-Combat learning.

A positive T089 result establishes only a local Non-Combat update operator with Battle frozen. It does not authorize T066, establish a Battle learner, or prove an alternating co-improvement loop. Before any future alternating co-improvement, a separate Battle task must independently establish a credible learned update of the form `Search(B_new) > Search(B_old)` without reopening the closed root-prior or learned-leaf-value repair routes by parameter tuning.

Human trajectories, human action labels, hand-authored card/deck/relic/route rankings, and imitation loss on `expert_non_combat_v1` are forbidden. `expert_non_combat_v1` is allowed only as a bootstrap/source behavior, continuation behavior, explicit unsupported-screen fallback, and frozen comparator.

## Publication Baseline

Planner publication base:

`main @ 6b739ee3f9b4bbd113aac141c755401d2a865252`

Accepted canonical native identity at publication:

`lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 20a6c2b3a9cea817c988178b814f083ff889853f`

Accepted Battle predecessor:

- T088 / PR #101 terminal classification: `STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED`;
- accepted T088 science/result head: `a7d71851e776f279b3d7280d1486dbdf73b63627`;
- accepted T088 lifecycle/finalization head: `a25f9a27deeaeb98d13a188538c7ac6f09a6f1a3`;
- formal raw evidence SHA-256: `fe376c3f054c94bf30d368ec544ff85f13f9ac594e7eec4178677e7e5414acea`;
- selected Battle arm: unguided Search v2 @400;
- improvement source: higher Search v2 compute, not a learned or handcrafted-guidance mechanism.

T086 / PR #99 is closed, unmerged, and non-executable. Its Search-v2@100/native-era contract is superseded by T089. No T086 target generation, training, held-out evaluation, or formal complete-run evidence may be reused as though it belonged to T089.

## Research-Ledger Role

T089 implements the post-T088 alignment recorded in issue #85:

1. freeze Battle planning to Search v2 @400;
2. test one learned Non-Combat update while Battle is held fixed;
3. require local held-out improvement before expensive fresh complete-run evaluation;
4. if T089 succeeds, freeze the qualified Non-Combat candidate and separately design a new Battle-student update task;
5. consider alternating Battle/Non-Combat co-improvement only after both learned sides have independently demonstrated credible update operators.

The intended eventual coupling is through complete-run occupancy, continuation values, and self-generated targets. Search itself is not jointly trained.

## Dependencies

Required accepted dependencies:

- T033: public-context model-input encoding boundary;
- T040: `expert_non_combat_v1` bootstrap/fallback behavior;
- T065: normative `non-combat-model-input-v1` schema and small action-conditioned ranker architecture;
- T075: exact leakage-safe 320-state selected Non-Combat cohort and global replay-group ownership;
- T076/T078: repaired checkpoint isolation and accepted 320-state restore/public-context/legal-action fidelity substrate;
- T071/T074: execution reuse and controller-ownership boundaries;
- T081: scientific artifact eligibility gate;
- T085: learned Battle leaf-value repair round closed without promotion;
- T088: frozen Search-v2@400 Battle baseline and current native identity.

T063 and T066 remain `DRAFT` and are not dependencies. T034 remains blocked and is not reopened by this task.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

### Inputs

Required scientific inputs are:

- exact T075 selected 320-state cohort identity and split ownership;
- exact T065 `non-combat-model-input-v1` schema and ranker architecture contract;
- exact T078 restore/public-context/legal-action fidelity semantics;
- exact current `main`, canonical native, and T088 Search-v2@400 Battle-controller identity;
- all T089 current-native revalidation, target, checkpoint, held-out, fresh-run, report, and retention identities.

### Reuse mode

`scientific_quality_claim`.

### Claim boundary

T089 may establish only whether this bounded four-family public Non-Combat ranker improves simulator-derived continuation value and fresh matched standard-start A20 progress while Battle is frozen to the T088 Search-v2@400 simulator-side planner.

T089 does **not** establish:

- normal-information Battle performance or live-game deployment quality;
- universal Non-Combat optimality;
- Heart win-rate improvement;
- a learned Battle improvement;
- a trainable Search algorithm;
- a joint or alternating co-improvement loop;
- public-consistent hidden-future optimality.

The frozen Battle planner is `full_simulator_state_oracle_like`; therefore complete-run results are simulator-side paired policy evidence, not deployment evidence.

### Required predicates

Before any scientific target is consumed:

- the T075 selection identity and global replay-group split ownership must match exactly;
- all 320 reused states must pass current-native revalidation with no replacement, dropping, re-ranking, or split movement;
- the public model-input schema must match T065 exactly;
- Battle controller semantics must remain the exact T088 Search-v2@400 baseline in every continuation and fresh evaluation arm;
- target tables must contain every eligible action and every required continuation seed;
- no historical T065/T075/T077/T086 target or outcome may be silently substituted for fresh T089 labels;
- model selection must use validation evidence only before held-out evaluation;
- held-out and fresh-run identities/seeds must remain frozen;
- all retained artifacts must pass identity, provenance, eligibility, and completeness checks.

### Unavailable-fact behavior

Any required identity, restore/public-context/legal-action parity fact, target row, schema fact, checkpoint provenance field, formal run result, or retained artifact that is unknown, stale, conflicting, malformed, filename-inferred, or unavailable fails closed to `INCOMPLETE`.

A valid experiment whose fresh learned-control occupancy cannot satisfy the explicit support gate maps only to `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`.

## Frozen Battle Side

Every counterfactual continuation and every fresh complete-run arm uses exactly:

- implementation: native `BattleScumSearcher2` / Search v2;
- information regime: `full_simulator_state_oracle_like`;
- nominal simulations per Battle root: `400`;
- root selection: `highest_mean`;
- policy prior callback: none;
- learned leaf-value callback: none;
- rollout continuation: native `playoutRandom`;
- terminal utility: native `evaluateEndState`;
- action space: `ActionSpaceConfig.initial_no_potions()`;
- canonical native identity: `20a6c2b3a9cea817c988178b814f083ff889853f`.

Search v2 @400 is frozen as a planner/controller. T089 may measure its cost but may not train it, tune it, change its budget, alter tree semantics, inject the Non-Combat model into Battle search, or substitute Search v2 @100 for convenience.

If implementation cannot reproduce this exact controller from current `main`, T089 fails closed pending a material Planner amendment.

## Reused Non-Combat State Substrate

Reuse only the exact accepted T075 selected cohort:

- 320 selected states;
- exact selection SHA-256: `94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8`;
- families: `MAP_SCREEN`, `REST_ROOM`, `REWARDS`, `TREASURE_ROOM`;
- per family: 48 training, 16 validation, 16 held-out;
- global replay-group ownership from T075 remains authoritative.

T078 established a prior 320/320 restore-only fidelity pass, with retained report SHA-256 `9abb6e76c7fe271884a37394b31058406ad0591b9949b7c109671d6d2ae539b1`. Because the canonical native identity has since advanced, that historical audit is a dependency fact, not a substitute for T089 current-native revalidation.

Historical T065/T075/T077 target/outcome artifacts are not training labels for T089.

### Mandatory current-native revalidation

Before target generation, replay/restore all exact 320 states under the T089 canonical native identity and require exact equality for all decision-relevant retained facts, including:

- public decision context;
- ordered legal-action identities and duplicate occurrences;
- screen/family identity;
- all `non-combat-model-input-v1`-relevant public fields;
- replay/source identity and split ownership.

No state may be replaced, dropped, re-ranked, or moved between splits. Any mismatch stops the task at `INCOMPLETE`; do not recollect a replacement cohort inside T089.

## Supported Learned-Control Scope

Learn exactly four families:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

All other Non-Combat screens use explicit `expert_non_combat_v1` fallback and must be counted by screen/family. A supported family may not be silently routed to expert fallback because encoding, inference, or ranking fails.

SHOP, EVENT, CARD_SELECT, BOSS_RELIC, and any other unsupported family remain outside learned control.

## Public Model Input And Architecture

Reuse the exact T065 `non-combat-model-input-v1` contract without feature redesign:

- state input: public tactical/context state, dimension `4737`;
- action input: public legal-action compatibility vector, dimension `92`;
- no hidden simulator state, RNG state, future encounter identity, checkpoint payload, expert score/prior/action, behavior action, target value, or Search-internal state may enter deployable model input;
- normalization is fit from T089 training rows only and frozen into the checkpoint;
- validation, held-out, and fresh-run inference use that exact frozen normalization.

Reuse the T065 small action-conditioned ranker architecture unchanged:

```text
state[4737]
  -> Linear(4737,64) -> ReLU
  -> Linear(64,64) -> ReLU

action[92]
  -> Linear(92,64) -> ReLU
  -> Linear(64,64) -> ReLU

concat(state_embedding, action_embedding)
  -> Linear(128,64) -> ReLU
  -> Linear(64,1)
```

Any model-input schema/version/size mismatch is `INCOMPLETE` rather than permission to redesign features inside the same task.

## Fresh Counterfactual Continuation Target

For every reused state and every eligible legal action:

1. replay/restore the exact source state and verify public/legal identity;
2. capture the canonical process-local checkpoint;
3. restore that same checkpoint before every candidate branch;
4. force the candidate action exactly once;
5. continue the run with frozen Battle Search v2 @400 and `expert_non_combat_v1` for all later Non-Combat decisions;
6. terminate only at authoritative run terminal; a controlled-run safety cap of 500 outer steps is allowed, but hitting the cap is invalid evidence rather than a terminal return;
7. compute:

```text
q_floor = mean(max(0, terminal_floor - source_floor))
```

The target is a simulator-derived continuation-progress target. It is not a hand-written reward over HP, cards, relics, gold, path shape, or deck quality.

All candidate actions from one source state use the same ordered continuation-driver seed tuple. Candidate actions may not be capped, subsampled, filtered by expert preference, or omitted because they are expensive.

### Frozen continuation seeds

The following are exact `ExpertNonCombatDriver` seeds, distinct from simulator/source-run seeds:

- training states: `(892001, 892002)`;
- validation states: `(892101, 892102)`;
- held-out states: `(892201, 892202, 892203, 892204)`.

For each candidate/seed branch, reset `ExpertNonCombatDriver(seed=<continuation_seed>)` after restoring the same source checkpoint and forcing the candidate action. No failed seed may be replaced and no CLI/default seed derivation may substitute for these exact values.

Missing/non-terminal branches, restore mismatch, controller failure, illegal action, non-finite target, or missing required seed row fails closed to `INCOMPLETE`.

### Hidden-future limitation

The restored checkpoint fixes one realized simulator future. T089 does not have T034-style public-consistent hidden-future averaging. Therefore `q_floor` is a privileged simulator-side training target conditional on that restored future. The learned ranker must remain public-only, and all reports must preserve this teacher-ambiguity limitation. T089 may not claim normal-information optimality from these labels.

## Training Contract

Train exactly two model seeds:

- `893001`
- `893002`

Frozen optimization:

- PyTorch CPU;
- Huber loss, delta `1.0`;
- Adam `lr=1e-3`, betas `(0.9, 0.999)`, eps `1e-8`, weight decay `0`;
- batch size `64` action rows sampled with replacement;
- exactly `1500` optimizer steps;
- gradient clip norm `10`;
- one Torch thread per model;
- no early stopping, architecture sweep, hyperparameter sweep, checkpoint averaging, target reshaping, or post-held-out tuning.

Checkpoint selection occurs before held-out evaluation using validation `q_floor` MAE only. Exact ties choose the lower seed. The non-selected seed remains a robustness diagnostic.

At inference on a supported screen, the model scores every eligible legal action and selects the highest predicted `q_floor`; exact score ties choose the lowest legal-action index.

## Held-Out Local Policy Gate

Evaluate both model seeds on the frozen 64 held-out states using the complete held-out counterfactual target table.

For each state compare:

```text
q_floor(model-selected action) - q_floor(expert-selected action)
```

The held-out expert comparator action is frozen independently of the continuation-target seeds: for each held-out source state, restore the exact state, reset `ExpertNonCombatDriver(seed=895001)`, invoke it exactly once on the exact ordered legal-action list, and record the selected action identity/index. The driver is reset to `895001` separately for every held-out source state. No second draw, retry, alternate seed, or behavior-action substitution is allowed. An invalid/missing expert selection is `INCOMPLETE`.

This `895001` call chooses only the comparator action. It does not generate a target and does not replace the held-out continuation seeds `(892201, 892202, 892203, 892204)`. The expert action is a comparator only and never a supervised target.

The validation-selected model passes the held-out local gate only if all hold:

1. aggregate mean paired delta > 0;
2. median paired delta >= 0;
3. at least 3 of 4 family mean deltas >= 0;
4. a 10,000-resample family-stratified paired bootstrap has 95% lower confidence bound for mean delta > 0;
5. the non-selected model seed has aggregate mean paired delta >= 0;
6. zero identity/schema/restore/legal-action/fallback violations.

Bootstrap seed: `89089`. Sampling unit is the source state; each replicate resamples 16 states with replacement within each family and averages across all 64 resampled states.

If valid evidence fails this gate, stop before fresh complete-run evaluation and classify `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`.

## Conditional Fresh Matched A20 Complete-Run Evaluation

Run only if the held-out local gate passes and Maintainer explicitly accepts the exact held-out/checkpoint evidence for fresh-evaluation execution.

Use exact fresh standard-start A20 simulator seeds:

`891001..891256`

Run two matched arms on every seed:

1. baseline: `expert_non_combat_v1`;
2. candidate: validation-selected learned policy on the four supported families, with explicit `expert_non_combat_v1` fallback elsewhere.

Frozen run semantics for both arms:

- player: `IRONCLAD`;
- ascension: `20`;
- standard natural start;
- max outer controlled-run steps: `500`;
- Battle controller/action space/native identity exactly as frozen above;
- no assistance schedule, constructed start, restart privilege, or learned Battle guidance;
- exact Non-Combat driver seed: `894002`.

For the baseline arm, reset `ExpertNonCombatDriver(seed=894002)` separately for every simulator seed. For the candidate arm, supported-family decisions are deterministic from the frozen checkpoint; all unsupported-screen fallback uses a separately reset `ExpertNonCombatDriver(seed=894002)` for every simulator seed. Simulator seed and driver seed are separate provenance fields.

The Battle controller is privileged/oracle-like in both arms. Therefore this is a matched simulator-side Non-Combat policy comparison under a frozen Battle teacher, not a normal-information deployment evaluation.

Required per-run evidence includes terminal floor/status, reached Act, Boss/later-act/Heart reachability, visible terminal resources, learned decision count, fallback count by family, learned/expert disagreement where comparable, Battle-search work/cost, wall clock, truncation, and controller failure.

### Fresh-run support gate

Across the 256 candidate-arm runs require:

- at least 128 valid learned-controlled decisions total;
- at least 32 learned-controlled decisions in each of `MAP_SCREEN` and `REWARDS`;
- at least one learned-controlled decision in both `REST_ROOM` and `TREASURE_ROOM`;
- zero supported-screen inference failure silently routed to expert fallback.

If all run identities are valid but this natural occupancy support is not met, classify `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`; do not add runs or expand learned-control scope inside T089.

## Fresh-Run Primary Metric

Primary metric:

```text
paired terminal_floor delta = candidate - baseline
```

Use 10,000 paired bootstrap resamples of the 256 simulator seeds with replacement, seed `891089`, and report the 2.5th/97.5th percentiles of mean paired terminal-floor delta.

Secondary descriptive metrics:

- Act-2+, Act-3+, Act-4/Heart reachability counts;
- complete-run wins if any;
- mean/median terminal-floor delta;
- learned-control coverage by supported family;
- supported-family disagreement rates;
- terminal visible-resource diagnostics;
- Battle-search work and total wall-clock cost.

Secondary metrics cannot rescue a failed primary classification.

## Execution Gates

Publication alone authorizes no implementation or simulator execution.

After Maintainer exact-spec approval, implementation proceeds on this same PR. Before formal target generation, Maintainer must review the implementation boundary and authorize only bounded preflight/current-native revalidation. A bounded one-state-per-family target canary may verify mechanics and cost but cannot count as scientific target evidence.

Formal target generation requires explicit Maintainer authorization after:

- 320/320 current-native revalidation passes;
- target row identity/order/seed schema is fixed;
- restore isolation and Battle-controller provenance are verified;
- resource/shard plan is recorded.

Training and held-out evaluation may consume only the complete accepted formal target artifact. Fresh 256-seed evaluation remains separately conditional on the held-out gate and exact selected-checkpoint acceptance.

No failed formal stage receives an unreviewed free retry. A repair must identify the earliest affected stage and receive the workflow-required review/authorization before affected execution continues.

## Cost And Execution Accounting

Every expensive simulator stage must follow repository detached-job/resource-admission conventions and report:

- shard identity/count and effective concurrent workers;
- exact state/action/seed or run-seed ranges;
- Search v2 Battle root-decision count;
- nominal Battle simulation budget (`400`);
- direct native search/simulator work counters when available without semantic change;
- model calls (`0` for the frozen Battle planner);
- target branches completed/failed;
- wall-clock time;
- peak memory when reliably measurable;
- controller/truncation failures.

Nominal Search budget is not a substitute for measured work.

## Terminal Classification

Emit exactly one terminal classification.

### `NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED`

Require all:

1. artifact/integrity/current-native revalidation gates pass;
2. held-out local policy gate passes;
3. fresh-run support gate passes;
4. fresh-run 95% bootstrap lower bound for mean terminal-floor delta > 0;
5. candidate arm has no more invalid/truncated/controller-failure runs than baseline;
6. candidate arm reaches Act 2+ on at least as many matched seeds as baseline.

This freezes the selected checkpoint as an accepted Non-Combat candidate **under the T089 claim boundary only**. It does not activate T066; the next Planner decision is a separate Battle-student update experiment or a bounded diagnosis required before alternating co-improvement.

### `NON_COMBAT_POLICY_HARM_CONFIRMED`

Require valid fresh-run support and fresh-run 95% bootstrap upper bound for mean terminal-floor delta < 0.

### `NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED`

Valid experiment that is neither established improvement nor confirmed harm. A valid held-out-gate failure enters this class without running the conditional fresh evaluation.

### `NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT`

All integrity/training/held-out prerequisites needed to reach fresh evaluation are valid, but the exact 256-run learned-control support gate is unmet.

### `INCOMPLETE`

Identity/provenance/restore/public-context/legal-action/schema/target/checkpoint/execution/retention failure, or any missing required evidence.

## Required Artifacts

Retain and hash at minimum:

1. input eligibility report resolving T065/T075/T078/T081/T088 and current main/native identities;
2. exact 320-state current-native revalidation report;
3. complete counterfactual target manifest/table with state/action/continuation-seed linkage and Battle-controller provenance;
4. training normalizers, deterministic batch plans, both checkpoints, and training reports;
5. validation checkpoint-selection report frozen before held-out evaluation;
6. held-out expert-comparator binding plus paired action-value report and stratified bootstrap;
7. if authorized, exact 256-seed fresh-run source/arm manifests and per-run outcomes;
8. fresh-run bootstrap/support/classification report;
9. terminal report with claim boundary and downstream decision;
10. retention manifest with SHA-256, byte counts, regeneration commands, compatibility requirements, retention reason, and deletion conditions.

Large raw artifacts remain outside Git under a stable ignored artifact root. Finalization must use bounded-memory/streaming paths where artifact scale requires it.

## Out Of Scope

- training or tuning Search v2 itself;
- any Battle model training, Battle prior/value repair, root-prior allocation variant, or learned-leaf-value repair;
- progressive-bias/Beam follow-up or another classical Battle tournament;
- exact transposition rescue or new T079 identity instrumentation;
- T066 alternating/joint execution;
- new Non-Combat feature schema or architecture sweep;
- imitation of `expert_non_combat_v1`;
- human trajectories, human labels, human card/deck/relic/route rankings, or manual strategy targets;
- learned control for SHOP/EVENT/CARD_SELECT/BOSS_RELIC or other unsupported screens;
- T034 hidden-future sampler implementation;
- complete-run scale beyond the exact conditional 256 matched seeds;
- live CommunicationMod promotion.

## Acceptance Criteria

1. Exact T075 320-state cohort and split ownership are reused with no replacement and pass 320/320 current-native revalidation.
2. Every target/fresh-run Battle decision uses the exact T088 unguided Search-v2@400 controller and no learned Battle guidance.
3. T089 targets are generated fresh for every eligible action and required continuation seed; historical target artifacts are not substituted.
4. Non-Combat model input remains exactly public `non-combat-model-input-v1`; no expert/hidden/target leakage enters inference.
5. The T065 ranker architecture and frozen two-seed optimization contract are used without held-out tuning.
6. Held-out expert comparator uses exactly driver seed `895001` reset per state; held-out local improvement is evaluated exactly before any fresh complete-run execution.
7. Fresh evaluation, if authorized, uses exactly the 256 matched seeds, frozen driver seed, exact Battle baseline, and explicit unsupported-screen fallback.
8. Terminal classification follows the frozen rules above and does not promote T066 or claim deployment/Heart improvement outside scope.
9. All required artifacts and execution-cost facts are retained with exact identity and fail-closed eligibility.
10. Final lifecycle/result documentation on this PR records whether a local Non-Combat update operator was established and the single next research decision.

## Required Verification

Before implementation acceptance, run the standard repository compile/lint/format/diff gates plus focused unit/regression tests for:

- T075/T078 cohort identity and current-native restore/public/legal revalidation;
- `non-combat-model-input-v1` dimensional/public-only contract;
- complete action enumeration and common-random-number target branching;
- exact Search-v2@400 Battle provenance in target and fresh-run paths;
- deterministic model training/batch/checkpoint selection;
- exact held-out expert-comparator seed/reset semantics;
- no supported-family silent fallback;
- held-out/fresh bootstrap determinism;
- artifact eligibility and retention round trips.

Formal simulator evidence is produced only through the staged authorization gates above.

## PR Report

The final PR report must state:

- exact approved task-contract head and any material amendments;
- exact final STSRL/native identities;
- 320-state revalidation result;
- target scale by split/family/actions/continuation seeds;
- both training seeds and validation-selected checkpoint;
- held-out paired gate cells and bootstrap CI;
- fresh 256-seed support/outcome cells if executed;
- simulator/search work, worker/shard topology, wall clock, and failures;
- exact retained artifact identities and hashes;
- one terminal classification;
- the bounded scientific interpretation;
- one next research decision.

If `NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED`, the report must explicitly say that Search remains a fixed planner and T066 is still not authorized until a separate Battle learned update operator is established.
