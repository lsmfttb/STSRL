# T065: Learned Non-Combat Policy v1

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

All material random seeds and baseline controller identities below are immutable
parts of this specification. The Implementer must not choose replacements after
seeing source coverage, targets, training metrics, held-out results, or run-level
outcomes. Any change requires a material specification revision and Maintainer
reapproval.

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

The deployable learned policy consumes only the versioned public non-combat
model input. Hidden RNG state, unrevealed future encounters, draw order, hidden
Act-3 second Boss information, native checkpoint payloads, and simulator-only
future fields are forbidden inputs.

## Supported Decision Scope

T065 v1 must learn and evaluate exactly these four mandatory screen families:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

`REWARDS` includes legal card/relic/potion/gold/key/skip actions when exposed by
the simulator. T065 does not invent reward mechanics or strategic values
locally.

`BOSS_RELIC_REWARDS` may be included as an additional diagnostic family only if
Stage 1 finds at least 16 unique replay-valid states without changing source
scale. It is not required for acceptance and cannot compensate for a mandatory
family failure.

The v1 learned policy does not control `SHOP_ROOM`, `EVENT_SCREEN`,
`CARD_SELECT`, unsupported/unknown screens, or `BOSS_RELIC_REWARDS` when its
optional coverage condition is absent. Those decisions route to an explicitly
named `expert_non_combat_v1` fallback.

Fallback use is behavior provenance, not a target. A mandatory supported screen
may not silently fall back because the model dislikes its candidate actions.
Schema/encoder/inference failure on a mandatory screen is a task error.

## Stage 0: Cheap Readiness And Source-Capability Preflight

Before expensive collection verify that:

- the pinned simulator source matches the manifest;
- exact process-local checkpoint capture/restore is available;
- public projection and `DecisionContext` construction succeed for all mandatory
  families on focused fixtures/smokes;
- legal actions have stable portable identities and public model-input
  representations;
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

- standard natural A20 starts only;
- no HP/potion/encounter assistance;
- no constructed starts or restart privilege;
- no learned battle guidance or root-prior variant;
- frozen battle controller/action space exactly as specified above;
- identical 256 simulator seeds in both source arms;
- source behavior affects only occupancy and is never a supervised target;
- failed seeds remain visible and are never replaced by another seed.

A portable source record must retain simulator seed, source behavior and routed
controller provenance, occurrence-disambiguated public action trace, source
step/floor/Act/screen, public schema identities, legal-action identities in exact
order, replay-equality identity/hash, source-run identity, and split assignment.
Native checkpoints remain process-local temporary branch handles.

Deterministically select exactly 80 unique replay-valid source states per
mandatory family, for 320 states total. Within each family freeze 48 training,
16 validation, and 16 held-out states. Splits are by simulator-seed group: both
source behavior arms for the same simulator seed belong to the same partition.
No source seed or replay-equivalent state may cross partitions.

Selection may preserve available Act/floor diversity but may not fabricate
strata or select by perceived strategic quality. If a mandatory family cannot
supply 80 replay-valid unique states from the fixed 512 source runs, stop with a
source-coverage failure; do not enlarge Stage 1 without a spec revision.

## Stage 2: Counterfactual Continuation Targets

For every selected source state and every eligible legal action:

1. replay the portable trace and verify the source public state and exact legal
   action identities;
2. capture one process-local native checkpoint;
3. restore that same checkpoint before every action branch;
4. force the candidate action exactly once;
5. continue to terminal under the frozen continuation policy;
6. record outcome components and compute cost.

Do not cap or subsample candidate actions. A state for which all eligible actions
cannot be branched safely is invalid and the failure remains visible.

After the forced action use:

- battle controller: `oracle_search_v1_highest_mean_s20` with the exact frozen
  constructor/provenance/action-space contract above;
- non-combat continuation: `expert_non_combat_v1`;
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

## Stage 3: Public Non-Combat Model Input

Define one versioned `non_combat_model_input_v1` contract that reuses existing
public surfaces:

- T074 `DecisionContext` public fields;
- T033 public-context/history model features;
- existing public tactical state/action encodings and identities;
- existing public non-combat snapshot/action metadata;
- explicit screen/category indicators for the four mandatory families.

Variable legal-action counts remain native. Unknown identities require explicit
versioned handling. The input must not contain behavior actions, targets,
terminal outcomes, hidden future, native checkpoints, or simulator-only state.
The same encoder is used for training, held-out scoring, and online control.
Schema/version mismatch fails closed.

T065 may add one narrow reusable non-combat model-input module. It must not add
non-combat conditionals to battle-specific model code merely to avoid creating
the correct owner.

## Stage 4: Frozen Learned Ranker

Train a small action-conditioned scalar ranker predicting `q_floor` from public
state plus one candidate action.

Frozen configuration:

- PyTorch through the existing optional `train` dependency;
- state encoder MLP + action encoder MLP + joint scalar head;
- hidden width 64;
- at most 2 hidden layers per encoder/head;
- ReLU;
- Huber loss;
- Adam, learning rate `1e-3`;
- batch size 64 candidate-action rows;
- 1500 optimizer steps;
- gradient clip norm 10;
- exactly model seeds `653001` and `653002`;
- `torch_threads=1` per model run;
- no architecture or hyperparameter sweep.

Checkpoint metadata must include model-input schema, training config, split and
target identities, source/target artifact identities, exact model seed, and
behavior/continuation provenance.

The deployable learned policy scores every eligible action on a supported screen
and selects the highest predicted `q_floor` with deterministic stable-index tie
break. Expert priors and behavior-action features are forbidden from model score.

Choose the Stage 5/6 checkpoint only by validation `q_floor` MAE between seeds
653001 and 653002. Exact MAE ties choose the lower model seed. Freeze that
choice before reading held-out results.

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
4. paired bootstrap over source states gives at least 0.90 probability that the
   aggregate mean delta is positive;
5. model seed 653001 and model seed 653002 are both evaluated, and the
   non-selected seed has a non-negative aggregate mean paired delta;
6. zero hidden-field, schema, legal-action, replay, or supported-screen fallback
   violations.

Matching expert actions is not a success criterion. If this gate fails with
otherwise valid evidence, stop before Stage 6 and record Case C.

## Stage 6: Conditional Matched Complete-Run Evaluation

Run only after Stage 5 passes.

Use every seed in `651001..651256` in exactly three matched arms:

1. `stochastic_non_combat_v1`;
2. `expert_non_combat_v1`;
3. validation-selected `learned_non_combat_v1` on mandatory families with
   explicit `expert_non_combat_v1` fallback elsewhere.

All arms use the exact frozen `oracle_search_v1_highest_mean_s20` battle
controller and action-space contract. Use standard natural A20 starts with no
assistance, construction, learned battle guidance, or root-prior variant.

There are exactly 768 terminal runs when Stage 6 completes validly.

Report matched terminal floor/status, Boss/later-act/Heart reachability, terminal
visible resources, learned decision count, intentional fallback by screen,
supported-screen failures separately, expert disagreement, simulator/search
cost, wall-clock, truncations, and controller failures.

The learned-control coverage gate requires:

- at least 60% of all non-combat decisions controlled by the learned policy on
  the four mandatory families;
- intentional unsupported-family fallback reported explicitly;
- schema/encoder/inference fallback on mandatory families at most 1% of their
  decisions and never hiding an illegal action;
- no post-hoc reclassification of a mandatory action category as unsupported.

The learned arm passes the complete-run outcome gate against expert only if:

1. matched mean terminal-floor delta is strictly positive;
2. paired bootstrap probability that mean terminal-floor delta is positive is
   at least 0.80;
3. Act-2 entry count is not lower than expert;
4. controller errors and unreported truncations are zero;
5. the learned-control coverage gate passes; and
6. at least one stronger signal holds: learned Act-2 entry count is strictly
   higher than expert, or bootstrap probability for positive mean floor delta is
   at least 0.95.

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

A replay, restore, public-input, target completeness, split, simulator identity,
legal-action, or other tooling/fidelity failure prevents valid attribution. Make
no policy conclusion and recommend only the narrow repair required to rerun the
same frozen experiment.

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
split identity, config, counts, and reproduction commands.

Recommended compact artifacts are the source-state selection manifest,
counterfactual target report, training/checkpoint metadata, held-out decision
report, conditional complete-run report, and terminal decision report.

Do not add proof chains, dependency-hash graphs, or security-style attestation.
Hashes identify immutable inputs/artifacts and stale-data mistakes.

Use T071 stage/run-local reuse. A repair names the earliest affected stage or
independent run; valid preceding outputs remain reusable. Producer Git SHA is
provenance, not a global cache key.

## Parallelism And Long Jobs

- Expensive simulator collection/continuation/evaluation stages target 16
  effective orchestration workers, capped only by shard count, memory, or a
  documented simulator constraint.
- Training uses `torch_threads=1`; the two model seeds may run concurrently when
  resource-safe.
- Use the existing detached-job utility for long stages. Report PID, status/log
  paths, command, worker count, seed/cohort range, and coarse expected duration
  once rather than continuously polling.
- Every expensive stage reports wall-clock, simulator/search cost, completed
  records/runs, failures, and reuse decisions.

## Out Of Scope

- human trajectories, labels, expert imitation, or strategy annotations;
- learned battle/search changes or battle-controller replacement;
- T063 or T066 implementation;
- public-consistent hidden-future sampling or normal-information optimality;
- learned shop/event/card-select control in v1;
- hyperparameter/architecture sweep, ensemble, or post-hoc gate tuning;
- 10,000-run scale-up, final A20 claim, or live CommunicationMod deployment;
- broad CLI refactor, 71 MB fixture cleanup, CI/branch protection, license choice,
  or unrelated module cleanup;
- local reimplementation of Slay the Spire mechanics or strategic reward rules.

## Deliverables

- versioned public non-combat model-input contract;
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
promotion is separate from implementation correctness.

Mandatory conditions:

- Stage 1 uses exactly source seeds `650001..650256` in both behavior arms;
- all four mandatory families have exactly 80 selected replay-valid states with
  48/16/16 train/validation/test counts;
- splits are seed-group disjoint with no replay-equivalent cross-split duplicate;
- every selected state evaluates every eligible legal action;
- train candidates use exactly `(652001, 652002)`, validation candidates exactly
  `(652101, 652102)`, and held-out candidates exactly
  `(652201, 652202, 652203, 652204)`;
- zero missing candidate/continuation rows in a valid target dataset;
- model input is public-only and expert behavior actions are not target/features;
- exactly models `653001` and `653002` train with the frozen configuration;
- checkpoint selection uses validation evidence only;
- held-out evaluation completes before any Stage 6 decision;
- Stage 6 is skipped automatically on valid Case C;
- if Stage 6 runs, exactly seeds `651001..651256` occur in all three arms and
  there are exactly 768 terminal runs;
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
- held-out bootstrap/gate aggregation;
- fallback coverage/reporting;
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

Consult T010, T014--T016, T033, T040, T061, T064, T071, T074, and
`docs/training_paradigm.md`. Historical artifacts are not implicit inputs; every
consumed artifact comes from a stable documented path or is regenerated by the
published workflow.

## PR Report

The implementation PR reports:

- exact approved spec commit and baseline;
- pinned simulator identity;
- Stage 1 seed range `650001..650256` and both behavior arms;
- per-family selected/split identities;
- optional Boss-relic diagnostic coverage if used;
- exact continuation seed sets;
- exact frozen battle controller and action-space provenance;
- candidate/target counts and completeness;
- model-input/checkpoint schema identities;
- model seeds `653001` and `653002`, training metrics, and validation selection;
- held-out per-family/aggregate action-value results and bootstrap probability;
- whether Stage 5 passed and Stage 6 therefore ran;
- Stage 6 seed range `651001..651256`, three-arm results, and learned/fallback
  coverage when applicable;
- commands, workers/shards, detached PID/status/log paths, wall-clock and
  simulator/search cost;
- failures, truncations, reuse decisions, and deviations;
- standard/focused verification;
- terminal Case A/B/C/D and exactly one next recommendation;
- confirmation of no human imitation target and no T065-specific legacy CLI
  route.
