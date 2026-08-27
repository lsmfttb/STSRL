# T065: Learned Non-Combat Policy v1

## Normative Specification Bundle

This primary task document must be read together with these normative files:

- [`T065-frozen-execution-statistics-contract.md`](T065-frozen-execution-statistics-contract.md) — exact simulator/controller configuration, RNGs, source split/selection, target completeness, model topology/optimization, bootstrap, sharding, coverage formulas, and Case-D semantics;
- [`T065-non-combat-model-input-v1.md`](T065-non-combat-model-input-v1.md) — exact `non-combat-model-input-v1` state/action feature inventory, order, dimensions, missing/unknown handling, numeric normalization, and state/action join semantics.

These files are part of the T065 scientific specification. There is no optional
alternative to a value frozen there. If this primary document summarizes one of
those contracts, the summary is intended to be identical rather than more
permissive. Any material change after specification approval requires Maintainer
re-approval.

[`T065-agent-scope-documentation-alignment.md`](T065-agent-scope-documentation-alignment.md)
is a non-acceptance documentation-impact note only; it is not a scientific or
implementation requirement for T065.

T065 remains `DRAFT` and `implementation_authorized=false` until the Main
Maintainer approves the exact proposal head.

## Objective

Build the first learned public-information non-combat policy as a bounded
simulator-only policy-improvement experiment.

The task does **not** imitate `expert_non_combat_v1`. The expert driver is only a
bootstrap behavior and continuation policy. Supervision comes from
counterfactual simulator continuations that evaluate every eligible action from
the same non-combat source state, followed by a held-out action-value comparison
and, only if that offline gate is positive, a matched complete-run evaluation.

T065 is diagnostic. A positive result may make the learned non-combat controller
an experimental input to a later joint-improvement task, but T065 alone does not
claim natural A20 strength, normal-information optimality, live-game readiness,
or final-agent promotion.

## Publication Basis And Current Main Baseline

The exact planner baseline for this proposal is
`f9f3a835b3f94f41cbd22b48587cc8e65bd23644` on `main`.

The research path leading here is now closed enough to justify returning to the
non-combat branch:

- T040 showed that `expert_non_combat_v1` materially improves source reachability
  over the stochastic non-combat driver under matched battle control. The expert
  policy is therefore a useful bootstrap occupancy/continuation policy, but it
  remains hand-authored and is not an intended teacher.
- T061 found a real battle-budget effect and correctly selected T062 first.
- T062/T067/T068/T069/T070 exhausted the current Search-v2 cost/outcome path: the
  100-simulation budget was descriptively insufficient, but higher-budget
  guidance did not produce a positive guidance signal and no Search-v2
  controller was promoted.
- T064 tested the separate later-act curriculum hypothesis and completed valid
  negative Case B. Its terminal recommendation is T065.
- T071--T074 removed experiment-execution duplication, retired closed executor
  surfaces, and repaired the forward decision/policy dependency boundary.

The required post-T074 quality review found remaining flat-CLI, tracked-fixture,
CI/open-source-packaging, and unrelated large-module debt. Those findings are
real but do not block this simulator-only experiment. T065 is explicitly
forbidden from adding task-shaped routes to the legacy flat CLI.

## Dependencies

Required merged dependencies:

- T010: stochastic non-combat driver and non-combat legality support.
- T014--T016: native public projection, sanitized public context/history, replay,
  and hidden-field audit contracts.
- T017/T020: pinned `sts_lightspeed` source integration.
- T033: public-context model-input encoder contract.
- T040: `expert_non_combat_v1` bootstrap behavior/continuation policy.
- T061: matched complete-run bottleneck evidence.
- T064: terminal Case B recommending T065.
- T071: detached long-job/status and stage/run-local reuse conventions.
- T074: acyclic low-level policy contract and explicit non-combat ownership.

T034 is **not** a dependency. T065 does not claim public-consistent hidden-future
sampling or information-set-optimal values. Counterfactual targets are generated
inside the authoritative simulator from exact source states; hidden future state
may affect the training target through simulator outcomes but must never appear
in deployable model input.

## Frozen Experiment Inputs

All material random seeds, baseline controller identities, execution/statistical
parameters, and model-input semantics are immutable parts of this specification.
The Implementer must not choose replacements after seeing source coverage,
targets, training metrics, held-out results, or run-level outcomes.

### Stage 1 source seeds

Use exactly the inclusive simulator-seed range:

`650001..650256`

There are exactly 256 Stage 1 source seeds. Every seed is used once with
`stochastic_non_combat_v1` and once with `expert_non_combat_v1`, producing 512
source runs when complete.

### Stage 6 fresh evaluation seeds

If and only if Stage 5 passes, use exactly the inclusive simulator-seed range:

`651001..651256`

There are exactly 256 Stage 6 seeds. This range is disjoint from Stage 1 and is
used identically in all three Stage 6 arms.

### Continuation-policy seeds

These seeds control only the stochastic `expert_non_combat_v1` continuation
after the source action has been forced from the exact restored checkpoint.
Candidate actions from the same source state must use the same ordered seed set.

- training states: `(652001, 652002)`
- validation states: `(652101, 652102)`
- held-out test states: `(652201, 652202, 652203, 652204)`

The ordering above is part of the artifact contract.

### Model seeds

Train exactly two model runs:

`(653001, 653002)`

No extra model seed may be added because one of these performs poorly.

### Frozen battle-controller identity

Every Stage 1 source run, Stage 2 continuation, and Stage 6 complete-run arm uses
exactly the current-main baseline constructor semantics:

```python
OracleSearchController(
    simulations=20,
    root_selection_rule="highest_mean",
    action_space=ActionSpaceConfig.initial_no_potions(),
)
```

Its required controller provenance is:

- `kind = "oracle_battle_search"`
- `name = "oracle_search_v1_highest_mean_s20"`
- `controller_version = "oracle-search-controller-v1"`
- `information_regime = "full_simulator_state_oracle_like"`
- native simulation budget = 20 `native_random_terminal_playouts`
- root selection = `highest_mean`
- native rollout policy = `BattleScumSearcher2::playoutRandom`
- native leaf value = `BattleScumSearcher2::evaluateEndState`
- model calls = 0

The shorthand `oracle_search_v1_s20` is not an accepted identity in T065 and must
not appear in generated provenance as a replacement name.

### Frozen action-space identity

The source configuration is exactly `ActionSpaceConfig.initial_no_potions()`.
Its serialized provenance must equal:

```json
{
  "excluded_kinds": [
    "game_potion_discard",
    "game_potion_use",
    "potion",
    "potion_discard",
    "reward_potion",
    "shop_reward_potion"
  ],
  "preferred_kinds": ["card", "end_turn"],
  "allow_excluded_fallback": true,
  "include_non_combat_potions": true
}
```

Current `action_space_for_screen` behavior remains authoritative: the above
configuration suppresses potion actions for battle decisions while preserving
legal non-combat potion actions when `include_non_combat_potions=true`. T065 must
not define a second action-space interpretation.

The remaining exact simulator character/step-cap/driver-seed mappings are frozen
in `T065-frozen-execution-statistics-contract.md` and are not restated loosely
here.

## Research Question

Given a public non-combat decision state, can an action-conditioned model trained
only on simulator continuation outcomes select actions with better held-out
long-horizon continuation value than `expert_non_combat_v1`, and does that
improvement survive a fresh matched complete-run A20 evaluation under the
unchanged frozen battle controller?

## Information Regime And Behavior Separation

Every record must separately identify:

- source behavior policy that visited the state;
- forced counterfactual action;
- continuation non-combat policy;
- continuation battle controller;
- simulator/source identity;
- model-selected action, if any;
- bootstrap/expert-selected action, for comparison only.

Human trajectories, human action labels, manually annotated correct actions,
and imitation loss on `expert_non_combat_v1` are forbidden.

The deployable learned policy consumes only the exact versioned
`non-combat-model-input-v1` contract. Hidden RNG state, unrevealed future
encounters, draw order, hidden Act-3 second Boss information, native checkpoint
payloads, and simulator-only future fields are forbidden inputs.

## Supported Decision Scope

T065 v1 learns and evaluates exactly these four screen families:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

`REWARDS` includes legal card/relic/potion/gold/key/skip actions when exposed by
the simulator. T065 does not invent reward mechanics or strategic values
locally.

`BOSS_RELIC_REWARDS` is **not** a T065 v1 learned or diagnostic family. It does
not enter the 320-state cohort and uses the normal explicit
`expert_non_combat_v1` fallback. There is no optional Boss-relic inclusion path
inside this task.

The v1 learned policy also does not control `SHOP_ROOM`, `EVENT_SCREEN`,
`CARD_SELECT`, or unsupported/unknown screens. Those decisions route to the
explicitly named `expert_non_combat_v1` fallback.

Fallback use is behavior provenance, not a target. A mandatory supported screen
may not be reclassified as unsupported because its learned score is inconvenient.
Supported-screen failures are handled only by the exact Stage 6 failure/coverage
semantics frozen in `T065-frozen-execution-statistics-contract.md`.

## Stage 0: Cheap Readiness And Source-Capability Preflight

Before expensive collection verify that:

- the pinned simulator source matches the manifest;
- exact process-local checkpoint capture/restore is available;
- public projection and `DecisionContext` construction succeed for all mandatory
  families on focused fixtures/smokes;
- legal actions have stable portable identities and public model-input
  representations;
- the exact `non-combat-model-input-v1` schema is constructible with
  `snapshot_feature_size=4634`, `public_context_feature_size=103`,
  `state_feature_size=4737`, and `action_feature_size=92`;
- mandatory screen states map to the exact T033 `map/rest/rewards/treasure`
  public-context positions required by the normative model-input contract;
- T065 model features contain no hidden/native state;
- T074 dependency-direction/import-isolation tests remain green;
- the frozen controller/action-space configuration above can be constructed and
  its serialized provenance matches exactly;
- no T065 implementation change is needed in the legacy flat CLI files listed
  below.

If a mandatory capability is missing, stop before Stage 1 and report a tooling
or fidelity failure rather than implementing a local simulator workaround.

## Stage 1: Fixed Source-State Pool

Run all seeds `650001..650256` twice under the same frozen battle controller:

- `stochastic_non_combat_v1 + oracle_search_v1_highest_mean_s20`
- `expert_non_combat_v1 + oracle_search_v1_highest_mean_s20`

This produces exactly 512 source runs when complete.

Requirements:

- exactly A20 `IRONCLAD`, standard natural start, and the 500-step terminal vs
  truncation semantics frozen in the execution/statistics contract;
- no HP/potion/encounter assistance;
- no constructed starts or restart privilege;
- no learned battle guidance or root-prior variant;
- frozen battle controller/action space exactly as specified above;
- identical 256 simulator seeds in both source arms;
- source driver seed mapping exactly as frozen in the normative execution
  contract;
- source behavior affects only occupancy and is never a supervised target;
- failed seeds remain visible and are never replaced by another seed.

A portable source record must retain simulator seed, source behavior and routed
controller provenance, occurrence-disambiguated public action trace, source
step/floor/Act/screen, public schema identities, legal-action identities in exact
order, replay-equality identity/hash, source-run identity, and split assignment.
Native checkpoints remain process-local temporary branch handles.

The split and selection are fully deterministic and are **not** allowed to
preserve Act/floor diversity by an additional balancing pass. Use exactly the
seed-group partitions, replay-equivalence deduplication, canonical SHA-256
selection key, tie-break, mandatory-family order, 48/16/16 quotas, and
no-replacement rule in `T065-frozen-execution-statistics-contract.md`.

The result, when valid, is exactly 80 replay-valid source states per mandatory
family: 48 training, 16 validation, and 16 held-out, for 320 states total.

If any mandatory `(family, split)` bucket cannot supply its frozen quota, or a
provisionally selected state fails exact replay/public-state/legal-action
equality, terminate as **Case D**. Do not enlarge Stage 1, rebalance strata, or
replace a failed selected state with the next ranked candidate inside T065.

## Stage 2: Counterfactual Continuation Targets

For every selected source state and every eligible legal action:

1. replay the portable trace and verify the source public state and exact legal
   action identities;
2. capture one process-local native checkpoint;
3. restore that same checkpoint before every action branch;
4. force the candidate action exactly once;
5. continue to terminal under the frozen continuation policy;
6. record outcome components and compute cost.

Do not cap or subsample candidate actions. Missing branch rows, restore failures,
non-terminal continuation at the frozen 500-step cap, controller failures, or
non-finite targets invalidate the target table and terminate T065 as Case D.
No candidate action, continuation seed, or selected state may be silently dropped
or replaced.

After the forced action use:

- battle controller: `oracle_search_v1_highest_mean_s20` with the exact frozen
  constructor/provenance/action-space contract above;
- non-combat continuation: `expert_non_combat_v1` with the exact frozen
  continuation-driver seed mapping;
- no assistance, construction, learned battle guidance, or root-prior variant.

Continuation replication is fixed as follows:

- training: exactly `(652001, 652002)` per candidate action;
- validation: exactly `(652101, 652102)` per candidate action;
- held-out: exactly `(652201, 652202, 652203, 652204)` per candidate action.

The checkpoint fixes the exact simulator future state at the branch point;
replication varies the seeded stochastic continuation policy, not hidden future
sampling. Reports must state this limitation.

Retain terminal floor/Act/status, Boss and later-act reachability, terminal HP
and visible resources, simulator/search cost, wall-clock, truncation, and error
status for audit.

The v1 supervised scalar is additional terminal floors:

`q_floor = mean(max(0, terminal_floor - source_floor))`

over the frozen continuation seeds for that action.

This is a simulator-derived long-horizon progress target, not a permanent
hand-written weighted reward over cards, relics, HP, gold, or other resources.

Each selected state and candidate action is also packed with the exact
`non-combat-model-input-v1` schema at this stage. The same packed semantics must
be used later; target generation does not authorize feature redesign.

## Stage 3: Frozen Public Non-Combat Model Input

The complete model-input contract is normative in
`T065-non-combat-model-input-v1.md`.

There is exactly one accepted schema:

- schema ID: `non-combat-model-input-v1`;
- schema version: `1`;
- state = exact 4634-value `public-tactical-v2` snapshot compatibility vector,
  followed by the exact 103-value `public-context-model-input-v1` vector;
- state dimension = exactly `4737`;
- action = exact 92-value `public-tactical-v2` legal-action compatibility vector;
- action dimension = exactly `92`;
- mandatory family indicators come from the existing T033 public-context
  `map/rest/rewards/treasure` positions; no extra T065 one-hot is added;
- feature order, fixed-capacity slot expansion, identity status/hash handling,
  missing/OOV semantics, and legal-action order are exactly those frozen in the
  normative model-input file;
- `eligible_action_indices` is a scoring mask, not a numeric feature;
- training-only population mean/std normalization and `std.clamp_min(1.0)` are
  frozen exactly in the normative model-input file;
- the same checkpointed normalizers are used for validation, held-out, and
  Stage 6; no online/recomputed normalization is allowed.

Variable legal-action counts remain native. The input contains no behavior
action, expert score/prior, target, terminal outcome, hidden future, native
checkpoint, or simulator-only state. Schema/version/size mismatch fails closed
under the already frozen stage semantics.

T065 may add one narrow reusable non-combat model-input module that delegates to
the merged public encoders. It must not add non-combat conditionals to
battle-specific model code merely to avoid creating the correct owner, and it
must not reimplement the frozen feature contract locally with different numeric
semantics.

## Stage 4: Frozen Learned Ranker

Train a small action-conditioned scalar ranker predicting `q_floor` from the
exact frozen public state plus one eligible candidate action.

The topology is exactly:

```text
normalized state[4737]
  -> Linear(4737, 64) -> ReLU
  -> Linear(64, 64) -> ReLU

normalized action[92]
  -> Linear(92, 64) -> ReLU
  -> Linear(64, 64) -> ReLU

concat([state_embedding, action_embedding])  # exact order, 128 values
  -> Linear(128, 64) -> ReLU
  -> Linear(64, 1)
  -> unrestricted scalar q_floor prediction
```

There is no alternate shallower/deeper configuration. There is no dropout,
batch normalization, residual connection, attention, ensemble averaging, output
activation, or learned expert prior.

Optimization and minibatch sampling are exactly those frozen in
`T065-frozen-execution-statistics-contract.md`:

- PyTorch CPU;
- exactly model seeds `653001` and `653002`;
- default seeded `nn.Linear` initialization;
- Huber loss, delta `1.0`, mean reduction;
- Adam `lr=1e-3`, betas `(0.9, 0.999)`, epsilon `1e-8`, zero weight decay,
  `amsgrad=False`;
- exactly 1500 optimizer steps;
- exactly 64 candidate-action rows sampled with replacement per step from the
  frozen model-seed-specific minibatch RNG;
- gradient clip norm 10;
- `torch_threads=1` per model run;
- no early stopping, checkpoint averaging, architecture sweep, or
  hyperparameter sweep.

Checkpoint metadata must include the full model-input schema identities and
sizes, exact T033 feature-name tuple, frozen normalizer tensors, training config,
split and target identities, source/target artifact identities, exact model seed,
and behavior/continuation provenance.

The deployable learned policy scores every eligible action on a mandatory screen
and selects the highest predicted `q_floor` with deterministic lowest legal-action
index tie break. Expert priors and behavior-action features are forbidden from
model score.

Choose the Stage 5/6 checkpoint only by validation `q_floor` MAE between seeds
653001 and 653002. Exact MAE ties choose the lower model seed. Freeze that choice
before reading held-out results.

## Stage 5: Held-Out Counterfactual Gate

Evaluate both models on the 64 mandatory held-out source states, using exactly
four continuation seeds `(652201, 652202, 652203, 652204)` for every candidate.

Report expert/stochastic/model-selected actions, empirical `q_floor` for every
candidate, model-minus-expert empirical delta, empirical best-action set,
predicted values, MAE/rank correlation where defined, screen/Act/floor, source
behavior, and public-context identity.

The validation-selected checkpoint passes only if all hold:

1. aggregate mean paired `q_floor(model) - q_floor(expert)` is strictly positive;
2. median paired delta is non-negative;
3. at least three of four mandatory family mean deltas are non-negative;
4. the exact frozen bootstrap gives `p_positive >= 0.90`;
5. model seed 653001 and model seed 653002 are both evaluated, and the
   non-selected seed has a non-negative aggregate mean paired delta;
6. zero hidden-field, schema, legal-action, replay, or supported-screen fallback
   violations.

For item 4, bootstrap is exactly 10,000 replicates using
`random.Random(655001)`, stratified by mandatory family, resampling 16 held-out
states with replacement from each family per replicate, and
`p_positive = count(replicate_mean > 0.0) / 10000`. No other bootstrap,
confidence-interval, or probability interpretation is accepted.

Matching expert actions is not a success criterion. If this gate fails with
otherwise valid evidence, stop before Stage 6 and record Case C.

## Stage 6: Conditional Matched Complete-Run Evaluation

Run only after Stage 5 passes.

Use every seed in `651001..651256` in exactly three matched arms:

1. `stochastic_non_combat_v1`;
2. `expert_non_combat_v1`;
3. validation-selected `learned_non_combat_v1` on the four mandatory families,
   with explicit `expert_non_combat_v1` fallback everywhere else.

All arms use the exact frozen `oracle_search_v1_highest_mean_s20` battle
controller/action-space, A20 `IRONCLAD`, 500-step terminal/truncation semantics,
and Stage 6 driver seed mapping from the execution/statistics contract. There is
no assistance, construction, learned battle guidance, or root-prior variant.

There are exactly 768 terminal runs when Stage 6 completes validly. A required
truncation, controller error, illegal action, missing decision record, or other
frozen run-validity failure makes Stage 6 Case D rather than silently shrinking
the matched cohort.

Report matched terminal floor/status, Boss/later-act/Heart reachability, terminal
visible resources, learned decision count, intentional fallback by screen,
supported-screen failures separately, expert disagreement, simulator/search
cost, wall-clock, truncations, and controller failures.

### Exact learned-control coverage

Use only the frozen definitions:

- `D` = all non-battle decision contexts across the 256 learned-arm runs,
  including mandatory supported screens and intentional unsupported-screen
  fallback decisions;
- `L` = decisions in the four mandatory families successfully encoded, fully
  scored across the eligible action set, and selected by
  `learned_non_combat_v1` without fallback;
- `M` = all learned-arm decisions in the four mandatory families;
- `F` = mandatory-family decisions where learned control fails because of
  schema/encoder/inference/supported-action coverage and therefore produces the
  named fallback/error path instead of a normal learned selection.

The coverage gate is exactly:

- `L / D >= 0.60`;
- `F / M <= 0.01`;
- `D == 0` or `M == 0` => Case D.

Intentional unsupported-family fallback contributes to `D` but not `L` or `F`.
A successful mandatory learned decision contributes to `D`, `L`, and `M`. A
mandatory learned failure contributes to `D`, `M`, and `F`, but not `L`. Battle
decisions contribute to none. No mandatory family/action may be reclassified as
unsupported after results are visible.

### Exact complete-run outcome gate

The learned arm passes against expert only if:

1. matched mean terminal-floor delta is strictly positive;
2. the frozen 10,000-replicate matched-seed bootstrap gives
   `p_positive >= 0.80`;
3. Act-2 entry count is not lower than expert;
4. controller errors and unreported truncations are zero;
5. the exact learned-control coverage gate above passes; and
6. at least one stronger signal holds: learned Act-2 entry count is strictly
   higher than expert, or the same frozen bootstrap gives
   `p_positive >= 0.95`.

The Stage 6 bootstrap is exactly `random.Random(655002)`, resampling 256 matched
seed indices with replacement per replicate and
`p_positive = count(replicate_mean_terminal_floor_delta > 0.0) / 10000`.

The stochastic arm is context only and cannot substitute for the expert gate.

## Terminal Decision Table

T065 ends in exactly one case and one planner-facing recommendation.

### Case A — learned signal transfers

Stage 5 and Stage 6 gates both pass. Accept `learned_non_combat_v1` only as an
experimental public non-combat policy with expert fallback for unsupported
families; recommend planner review of T066 or a narrower joint-policy task. Do
not claim natural A20/live-game promotion.

### Case B — offline signal does not transfer

Stage 5 passes but Stage 6 fails validly. Do not promote the controller. Preserve
the fixed evidence and recommend exactly one narrow follow-up based on observed
screen coverage, target-horizon/rollout-policy mismatch, or run distribution
shift. Do not launch a larger natural run merely because 256 seeds are neutral.

### Case C — no held-out action-value signal

Stage 5 fails validly. Skip Stage 6, do not promote the controller, close this
v1 target/model formulation, and recommend at most one narrow target/model
diagnostic.

### Case D — invalid experiment

A mandatory source bucket below quota, selected-state replay mismatch, source or
continuation truncation/failure, restore failure, public-input/schema failure,
target incompleteness/non-finiteness, split leakage, simulator identity error,
legal-action mismatch, or other frozen tooling/fidelity failure prevents valid
attribution. Make no policy conclusion and recommend only the narrow repair
required to rerun the same frozen experiment.

Case D stops all downstream scientific stages. Acceptance conditions that
mathematically require a downstream artifact are conditional on reaching that
stage, exactly as specified in `T065-frozen-execution-statistics-contract.md`.

## CLI And Command-Surface Boundary

T065 must not add task-numbered flags or experiment branches to:

- `src/sts_combat_rl/commands/cli_parser.py`;
- `src/sts_combat_rl/commands/lightspeed_cli.py`;
- `src/sts_combat_rl/commands/cli_validation.py`;
- the long dispatch chain in `src/sts_combat_rl/cli.py`.

The workflow may use one small neutrally named module command or thin script
that delegates to reusable library functions, e.g. a `non_combat_learning`
collect/target/train/evaluate surface. Do not build a generic command registry or
workflow framework. Existing main CLI behavior and mock gates remain unchanged.

## Artifact And Reuse Contract

Large source runs, continuation rows, checkpoints, logs, and reports remain
under ignored `artifacts/t065-learned-non-combat-policy-v1/` or an explicitly
reported equivalent stable path.

Compact artifacts use versioned schemas and retain paths/hashes, source and
simulator identity, exact frozen seed sets, controller/action-space provenance,
model-input schema and normalizers, split identity, config, counts, and
reproduction commands.

Recommended compact artifacts are the source-state selection manifest,
counterfactual target report, training/checkpoint metadata, held-out decision
report, conditional complete-run report, and terminal decision report.

Do not add proof chains, dependency-hash graphs, or security-style attestation.
Hashes identify immutable inputs/artifacts and stale-data mistakes.

Use T071 stage/run-local reuse. A repair names the earliest affected stage or
independent run; valid preceding outputs remain reusable. Producer Git SHA is
provenance, not a global cache key.

## Parallelism And Long Jobs

Use exactly the stage partitions frozen in
`T065-frozen-execution-statistics-contract.md`:

- Stage 1: two arms, each 16 shards of 16 consecutive source seeds;
- Stage 2: 16 shards of 20 globally indexed selected states, with all actions and
  continuation seeds for a state kept inside its shard;
- Stage 4: the two model seeds may run concurrently, `torch_threads=1` each;
- Stage 5: no simulator sharding;
- conditional Stage 6: three arms, each 16 shards of 16 consecutive fresh seeds;
- never exceed 16 concurrent simulator jobs.

Use the existing detached-job utility for long stages. Report PID, status/log
paths, command, worker count, seed/cohort range, and coarse expected duration
once rather than continuously polling. Every expensive stage reports wall-clock,
simulator/search cost, completed records/runs, failures, and reuse decisions.

## Out Of Scope

- human trajectories, labels, expert imitation, or strategy annotations;
- learned battle/search changes or battle-controller replacement;
- T063 or T066 implementation;
- public-consistent hidden-future sampling or normal-information optimality;
- learned shop/event/card-select/Boss-relic control in v1;
- hyperparameter/architecture sweep, ensemble, or post-hoc gate tuning;
- 10,000-run scale-up, final A20 claim, or live CommunicationMod deployment;
- broad CLI refactor, tracked-fixture cleanup, CI/branch protection, license
  choice, or unrelated module cleanup;
- local reimplementation of Slay the Spire mechanics or strategic reward rules.

## Deliverables

- exact versioned `non-combat-model-input-v1` implementation matching the
  normative schema file;
- replay-valid source-state records/selection manifest;
- all-eligible-action counterfactual target pipeline;
- frozen learned ranker and checkpoint contract;
- learned online non-combat integration through the T074 policy boundary;
- held-out action-value report;
- conditional matched complete-run report when Stage 5 passes;
- terminal Case A/B/C/D decision report with exactly one recommendation;
- focused tests and task documentation only.

## Acceptance Criteria

T065 may be accepted as a completed experiment with Case B or C; scientific
promotion is separate from implementation correctness. A correctly detected and
reported Case D may close T065 as an invalid-experiment diagnostic under the
conditional acceptance semantics in the normative execution/statistics contract.

Mandatory conditions for every stage that is reached:

- Stage 1 uses exactly source seeds `650001..650256` in both behavior arms with
  the exact frozen simulator/controller/driver configuration;
- valid source selection has exactly 80 states per mandatory family with
  48/16/16 train/validation/held-out counts, using only the frozen seed-group
  split and deterministic SHA-256 selection algorithm;
- splits are seed-group disjoint with no replay-equivalent cross-split duplicate;
- `BOSS_RELIC_REWARDS` does not enter the learned/diagnostic cohort;
- every selected state evaluates every eligible legal action and every frozen
  continuation seed required for its split;
- zero missing candidate/continuation rows in a valid target dataset;
- model input is exactly schema `non-combat-model-input-v1` version 1 with sizes
  snapshot `4634`, public context `103`, state `4737`, action `92`;
- exact T033 public-context feature names/order and exact `public-tactical-v2`
  snapshot/action order are preserved;
- state/action normalizers are training-split-only population mean/std with
  `unbiased=False`, std clamped to at least `1.0`, checkpointed once and reused
  unchanged for validation/held-out/Stage 6;
- expert behavior actions/scores are not target/features;
- exactly models `653001` and `653002` train with the frozen exact topology,
  optimizer, minibatch RNG, and step count;
- checkpoint selection uses validation evidence only;
- Stage 5 uses the exact `random.Random(655001)` 10,000-replicate bootstrap;
- held-out evaluation completes before any Stage 6 decision;
- Stage 6 is skipped automatically on valid Case C;
- if Stage 6 runs, exactly seeds `651001..651256` occur in all three arms and
  there are exactly 768 valid terminal runs before scientific interpretation;
- Stage 6 uses the exact `L/D >= 0.60`, `F/M <= 0.01` coverage definitions and
  exact `random.Random(655002)` matched-seed 10,000-replicate bootstrap;
- every Stage 1/2/6 battle controller reports provenance name
  `oracle_search_v1_highest_mean_s20` and the exact frozen action-space config;
- fallback, controller failures, truncations, identities, and compute cost remain
  explicit;
- terminal Case A/B/C/D follows the frozen gates without threshold changes;
- no existing scientific schema/result is silently reinterpreted;
- legacy flat CLI files gain no T065-specific routes/flags;
- no large generated dataset/checkpoint is committed to Git.

## Required Verification

Run standard local gates from `docs/tasks/README.md` plus focused T065 tests,
including:

- T074 dependency/import regressions;
- exact frozen-seed/controller/action-space configuration tests;
- exact model-input schema ID/version and dimensions `4634/103/4737/92`;
- exact state/action feature order and T033 feature-name tuple;
- missing/unknown identity and public-context encoding fixtures;
- deterministic training-only normalizer construction and checkpoint round trip;
- public/hidden-field input firewall;
- supported/unsupported routing;
- variable legal-action masking and stable tie break;
- portable source replay equality;
- exact checkpoint branch/restore;
- all-eligible-action completeness;
- split leakage/duplicate checks;
- deterministic paired continuation-seed order;
- model-input round trip/schema mismatch;
- checkpoint save/load/provenance;
- synthetic training sanity without simulator scale;
- exact held-out bootstrap/gate aggregation;
- exact Stage 6 coverage formula and matched bootstrap;
- complete-run matched-seed validation;
- Case A/B/C/D decision-table tests;
- `git diff --check`.

Before simulator evidence run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Use the exact current-main Python/native pairing. Large WSL stages are sharded,
detached where appropriate, and reported with commands and artifact identities.

## Legacy Reference

Consult T010, T014--T016, T033, T040, T061, T064, T071, T074,
`T065-frozen-execution-statistics-contract.md`,
`T065-non-combat-model-input-v1.md`, and `docs/training_paradigm.md`.
Historical artifacts are not implicit inputs; every consumed artifact comes from
a stable documented path or is regenerated by the published workflow.

## PR Report

The implementation PR reports:

- exact approved spec commit and baseline;
- pinned simulator identity;
- Stage 1 seed range `650001..650256` and both behavior arms;
- per-family selected/split identities and deterministic selection manifest;
- exact continuation seed sets;
- exact frozen battle controller and action-space provenance;
- candidate/target counts and completeness;
- exact `non-combat-model-input-v1` schema identity, component schema identities,
  dimensions, T033 feature-name identity, and normalizer tensors/identity;
- model seeds `653001` and `653002`, training metrics, and validation selection;
- held-out per-family/aggregate action-value results and exact bootstrap
  probability;
- whether Stage 5 passed and Stage 6 therefore ran;
- Stage 6 seed range `651001..651256`, three-arm results, exact `L/D` and `F/M`
  learned/fallback coverage, and exact matched bootstrap when applicable;
- commands, workers/shards, detached PID/status/log paths, wall-clock and
  simulator/search cost;
- failures, truncations, reuse decisions, and deviations;
- standard/focused verification;
- terminal Case A/B/C/D and exactly one next recommendation;
- confirmation of no human imitation target and no T065-specific legacy CLI
  route.
