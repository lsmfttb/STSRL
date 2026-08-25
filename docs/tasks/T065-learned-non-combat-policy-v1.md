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
- T062/T067/T068/T069/T070 then exhausted the current Search-v2 cost/outcome path:
  the 100-simulation budget was descriptively insufficient, but higher-budget
  guidance did not produce a positive guidance signal and no Search-v2
  controller was promoted.
- T064 tested the separate later-act curriculum hypothesis and completed valid
  negative Case B. Its terminal recommendation is T065.
- T071--T074 removed experiment-execution duplication, retired closed executor
  surfaces, and repaired the forward decision/policy dependency boundary.
  T074 leaves an acyclic `DecisionContext`/policy contract and explicit
  non-combat ownership suitable for a learned policy extension.

The required post-T074 quality review also found remaining engineering debt:
legacy flat CLI/parser growth, roughly 71 MB of tracked real CommunicationMod
captures, no repository CI/branch protection, no explicit open-source license,
and several large generic modules. These are real findings but are not T065
blockers:

- fixture size and open-source packaging do not affect the correctness of this
  simulator-only experiment;
- this is a personal research repository with strong local gates, so CI/branch
  protection is useful but not a prerequisite for the next scientific step;
- T065 is explicitly forbidden from adding more task-shaped flags to the legacy
  flat CLI, preventing the known CLI debt from growing during this task;
- the T074 policy boundary is now acyclic and is the only forward ownership
  surface T065 must extend.

No additional maintenance task is required before this proposal can be reviewed.
This document remains a planner proposal until the Main Maintainer approves the
exact specification head.

## Dependencies

Required merged dependencies:

- T010: stochastic non-combat driver and non-combat legality support.
- T014--T016: native public projection, sanitized public context/history, replay,
  and hidden-field audit contracts.
- T017/T020: pinned `sts_lightspeed` source integration.
- T033: public-context model-input encoder contract.
- T040: `expert_non_combat_v1` bootstrap behavior/continuation policy.
- T061: matched complete-run bottleneck evidence.
- T064: terminal Case B recommending T065 after the curriculum path failed.
- T071: detached long-job/status and stage/run-local reuse conventions.
- T074: acyclic low-level policy contract and explicit non-combat ownership.

T034 is **not** a dependency. T065 does not claim public-consistent hidden-future
sampling or information-set-optimal values. Counterfactual targets are generated
inside the authoritative simulator from exact source states; hidden future state
may affect the training target through simulator outcomes but must never appear
in deployable model input.

## Research Question

Given a public non-combat decision state, can an action-conditioned model trained
only on simulator continuation outcomes select actions with better held-out
long-horizon continuation value than `expert_non_combat_v1`, and does that
improvement survive a fresh matched complete-run A20 evaluation under an
unchanged battle controller?

T065 deliberately answers this question before attempting end-to-end joint
policy improvement.

## Information Regime And Behavior Separation

Every record must separately identify:

- source behavior policy that visited the state;
- forced counterfactual action;
- continuation non-combat policy;
- continuation battle controller;
- simulator/source identity;
- model-selected action, if any;
- bootstrap/expert-selected action, for comparison only.

Human trajectories, human action labels, manually annotated "correct" actions,
and imitation loss on `expert_non_combat_v1` are forbidden.

The deployable learned policy consumes only the versioned public non-combat
model input. Hidden RNG state, unrevealed future encounters, draw order, hidden
Act-3 second Boss information, native checkpoint payloads, and simulator-only
future fields are forbidden inputs.

## Supported Decision Scope

### Mandatory learned-screen families

T065 v1 must learn and evaluate exactly these four screen families:

1. `MAP_SCREEN`
2. `REST_ROOM`
3. `REWARDS`
4. `TREASURE_ROOM`

These families are common enough for a fixed cohort, already have stable public
legal-action/category semantics, and cover route, sustain/upgrade, reward/card/
resource, and treasure decisions without requiring a local reconstruction of
game mechanics.

`REWARDS` includes the legal reward actions exposed by the simulator on that
screen, including card/relic/potion/gold/key/skip choices when present. T065 does
not invent reward mechanics or values locally.

### Optional diagnostic family

`BOSS_RELIC_REWARDS` may be included as an additional diagnostic family only if
the source preflight finds at least 16 unique replay-valid source states without
changing source-generation scale. It is not required for task acceptance and it
must not be used to compensate for failure on a mandatory family.

### Explicit fallback families

The v1 learned policy does not control:

- `SHOP_ROOM`;
- `EVENT_SCREEN`;
- `CARD_SELECT`;
- unsupported/unknown screens;
- `BOSS_RELIC_REWARDS` when the optional coverage condition is not met.

Those states route to a clearly named `expert_non_combat_v1` fallback. Fallback
use is behavior provenance, not a training target, and is reported by screen,
action category, Act, and floor.

A supported screen may not silently fall back because the learned model dislikes
its legal actions. Encoder/schema/inference failure on a mandatory supported
screen is a task error and is counted separately from intentional unsupported-
screen fallback.

## Stage 0: Cheap Readiness And Source-Capability Preflight

Before any expensive target generation, verify on current `main` that:

- the pinned simulator source matches the manifest;
- the adapter supports exact process-local checkpoint capture/restore;
- public projection and `DecisionContext` construction succeed for all mandatory
  families on focused fixtures/smokes;
- each legal action has a stable portable identity and public model-input
  representation;
- no T065 code path imports hidden simulator/native state into model features;
- the T074 low-level dependency-direction tests remain green;
- no T065 implementation change is needed in the legacy flat CLI files listed
  under the CLI boundary below.

If any mandatory capability is missing, stop before source collection and report
a tooling/fidelity failure rather than inventing a local workaround.

## Stage 1: Fixed Source-State Pool

### Source runs

Collect one fixed source pool from **256 shared A20 simulator seeds**. Each seed
is run twice under the same battle controller:

- `stochastic_non_combat_v1 + oracle_search_v1_s20`;
- `expert_non_combat_v1 + oracle_search_v1_s20`.

This produces exactly **512 source runs** when complete.

Requirements:

- standard natural A20 starts only;
- no HP/potion/encounter assistance;
- no constructed starts;
- no restart privilege;
- no learned battle guidance;
- no root-prior allocation variant;
- battle search uses baseline `oracle_search_v1`, root rule `highest_mean`, native
  simulation budget 20, and the same action-space configuration in both arms;
- the same 256 simulator seeds appear in both source arms;
- source behavior affects only which states are visited. Its chosen action is
  never a supervised target.

Use a task-specific documented source-seed range and freeze it before collection.
The PR must publish that exact range. Do not substitute failed seeds silently.

### Source-state identity

A portable non-combat source record must contain enough information to reproduce
and verify the same decision in a fresh process without serializing native
checkpoint payloads. At minimum retain:

- simulator seed;
- source behavior arm and controller provenance;
- occurrence-disambiguated public action trace to the source decision;
- source step/floor/Act/screen;
- source public-context/schema identities;
- legal action identities in exact order;
- source public-state identity/hash or equivalent replay equality fields;
- source run/scenario identity and split assignment.

Native checkpoints remain process-local temporary handles used only while
branching actions.

### Fixed selected cohort

From the 512 source runs, deterministically select **80 unique source states per
mandatory family**, for **320 mandatory source states total**.

Within each mandatory family freeze:

- 48 training states;
- 16 validation states;
- 16 held-out test states.

The split is by simulator seed group, not by individual decision row: both source
behavior arms for the same simulator seed must belong to the same split. No
source state, simulator seed, or replay-equivalent state may cross train,
validation, and test partitions.

Selection should preserve Act/floor diversity when available, but must not
fabricate quotas for strata absent from the natural source pool.

If any mandatory family cannot supply 80 replay-valid unique states from the
frozen 512 source runs, T065 stops after Stage 1 with an explicit source-coverage
failure. Do not increase the run count inside the task without a material spec
revision.

## Stage 2: Counterfactual Continuation Targets

### Branching rule

For every selected source state and **every eligible legal action** on that
state:

1. replay the source state from its portable trace;
2. verify source public state and legal-action identities exactly;
3. capture one process-local native checkpoint;
4. restore that same checkpoint before each candidate branch;
5. force the candidate action exactly once;
6. continue the run to terminal under the frozen continuation policy;
7. record all target components and compute cost.

Do not cap or subsample candidate actions on a supported source state. If the
simulator cannot branch all legal actions safely, the source state is invalid for
this task and the failure remains visible.

### Frozen continuation policy

After the forced action, use:

- battle controller: baseline `oracle_search_v1`, `highest_mean`, native budget
  20;
- non-combat continuation policy: `expert_non_combat_v1`;
- no assistance, construction, learned guidance, or root-prior variant.

The expert continuation policy is a rollout policy used to define a first policy-
improvement target. Its own action at the source decision is never treated as
correct supervision.

### Replication budget

For each candidate action:

- training states: 2 continuation-policy seeds;
- validation states: 2 continuation-policy seeds;
- held-out test states: 4 continuation-policy seeds.

All candidate actions from the same source state use the same ordered
continuation-seed set. This is the paired common-random-policy contract.

The simulator checkpoint fixes the exact simulator future state at the branch
point. Replication varies the stochastic continuation policy, not hidden-future
sampling. Reports must state this limitation explicitly.

### Target definition

Retain the complete terminal outcome vector for audit:

- terminal floor and Act;
- run terminal status/victory;
- Act Boss entries and victories;
- Act 2/3/4 entry;
- Shield/Spear and Heart entry/outcome when reached;
- terminal current/max HP;
- gold, potion count/identities, relic/deck/key summaries when available;
- simulator steps, search cost, wall-clock, truncation/error status.

The v1 supervised scalar is **additional terminal floors**:

`q_floor = mean(max(0, terminal_floor - source_floor))`

over the frozen continuation seeds for that candidate action.

This target is intentionally simple. It is a simulator-derived long-horizon
progress measure, not a hand-written weighted reward over cards, relics, HP,
gold, or other resources. Structured outcome components remain available for
analysis but are not collapsed into a permanent strategic reward in T065.

## Stage 3: Public Non-Combat Model Input

Define one versioned `non_combat_model_input_v1` contract that reuses existing
public surfaces instead of creating a parallel game-state representation.

The state/action input may consume only:

- T074 `DecisionContext` public fields;
- T033 public-context model features/history projection;
- existing public tactical state/action encodings and identity vocabulary;
- public non-combat snapshot/action metadata already exposed by the controlled-
  run boundary;
- explicit screen/category indicators needed to disambiguate the four supported
  families.

Requirements:

- variable legal-action counts remain native; do not pad the policy contract to a
  fixed game-wide action vocabulary;
- unknown identities have explicit versioned handling;
- model input contains no target/behavior action, terminal outcome, hidden future,
  native checkpoint, or simulator-only state field;
- the same encoder is used for training, offline held-out scoring, and online
  complete-run control;
- schema/version mismatch fails closed.

T065 may add one narrow reusable non-combat model-input module. It must not extend
battle-specific `torch_policy_value.py` with non-combat conditionals merely to
avoid creating the correct owner.

## Stage 4: Frozen Learned Ranker

Train a small action-conditioned scalar value/ranker that predicts `q_floor` for
each legal action independently from the public source context plus that action's
public features.

Freeze the first experiment configuration:

- framework: PyTorch using the existing optional `train` dependency;
- architecture: state encoder MLP + action encoder MLP + joint scalar head;
- hidden width: 64;
- hidden layers per encoder/head: at most 2;
- activation: ReLU;
- loss: Huber loss on `q_floor`;
- optimizer: Adam;
- learning rate: `1e-3`;
- batch size: 64 candidate-action rows;
- optimizer steps: 1500;
- gradient clip norm: 10;
- model seeds: exactly two frozen seeds, published before training;
- per-run PyTorch numerical threading: `torch_threads=1`;
- no hyperparameter sweep and no architecture search inside T065.

The checkpoint must include model-input schema identity, training config, split
identity, target contract, source/target artifact identities, model seed, and
behavior/continuation provenance.

The deployable learned policy scores all eligible actions on supported screens
and selects the highest predicted `q_floor`, using only a deterministic stable
index tie-break. No expert prior or behavior-action feature may be mixed into the
model score.

Checkpoint selection for Stage 5/6 is based only on validation `q_floor` MAE;
choose the lower validation MAE of the two model seeds, breaking an exact tie by
the lower model seed. Freeze this checkpoint before reading held-out test
results.

## Stage 5: Held-Out Counterfactual Gate

Evaluate both model seeds on the 64 mandatory held-out source states using the
four-continuation empirical target per candidate action.

For each state report:

- expert-selected legal action;
- stochastic-selected legal action where reproducible from the source context;
- each model's selected action;
- empirical `q_floor` for every candidate;
- model-selected minus expert-selected empirical `q_floor`;
- best empirical action set and action disagreement;
- predicted values, MAE, and rank correlation where defined;
- screen family, Act/floor, source behavior arm, and public-context identity.

### Offline signal gate

The validation-selected checkpoint passes the offline gate only when all of the
following hold on the 64-state mandatory held-out cohort:

1. aggregate mean paired empirical `q_floor(model) - q_floor(expert)` is strictly
   positive;
2. the median paired delta is non-negative;
3. at least three of the four mandatory screen-family mean deltas are
   non-negative;
4. a paired bootstrap over source states gives at least 0.90 probability that the
   aggregate mean delta is positive;
5. the second model seed has a non-negative aggregate mean paired delta;
6. there are zero hidden-field, schema, legal-action, replay, or supported-screen
   fallback violations.

Matching `expert_non_combat_v1` actions is **not** a success metric. The gate is
about simulator continuation value.

If this gate fails, stop before Stage 6. Record terminal **Case C** below; do not
spend a complete-run scale evaluation trying to rescue a model that lacks a
held-out action-value signal.

## Stage 6: Conditional Matched Complete-Run Evaluation

Run this stage only after the Stage 5 offline gate passes.

Use **256 fresh A20 simulator seeds**, disjoint from all Stage 1 source seeds,
with exactly three matched non-combat arms and the same battle controller:

1. `stochastic_non_combat_v1`;
2. `expert_non_combat_v1`;
3. validation-selected `learned_non_combat_v1` on mandatory supported screens +
   explicitly named `expert_non_combat_v1` fallback elsewhere.

Battle control in all three arms is baseline `oracle_search_v1`, `highest_mean`,
native budget 20. Use standard natural A20 starts and no assistance,
construction, learned battle guidance, or root-prior variant.

This stage therefore contains exactly **768 terminal runs** when complete.

Report matched by seed:

- terminal floor/status;
- Act 1 Boss entry/victory;
- Act 2/3/4 entry;
- later Boss/Heart reachability if any;
- terminal HP/resources;
- learned-screen decision count;
- intentional fallback count by screen;
- supported-screen encoder/inference fallback/errors separately;
- action disagreement with expert on learned-controlled states;
- simulator/search/wall-clock cost;
- truncations and controller failures.

### Learned-control coverage gate

For the learned arm:

- at least 60% of all non-combat decisions must be controlled by the learned
  policy on the four mandatory screen families;
- intentional unsupported-screen fallback is allowed and reported;
- supported-screen fallback caused by schema/encoder/inference failure must be
  at most 1% of mandatory-family decisions and may not hide any illegal action;
- any systematic unsupported mandatory action category is a failure, not a
  reason to reclassify that category as fallback after seeing results.

### Complete-run positive gate

The learned arm passes the complete-run outcome gate against the expert arm only
when:

1. matched mean terminal-floor delta is strictly positive;
2. paired bootstrap probability that the mean terminal-floor delta is positive
   is at least 0.80;
3. Act-2 entry count is not lower than the expert arm;
4. controller errors and unreported truncations are zero;
5. the learned-control coverage gate passes; and
6. at least one stronger signal holds:
   - learned Act-2 entry count is strictly greater than expert, or
   - paired bootstrap probability that mean terminal-floor delta is positive is
     at least 0.95.

The stochastic arm is a context baseline, not a substitute for the expert-arm
promotion gate.

## Terminal Decision Table

T065 must end in exactly one case and one planner-facing recommendation.

### Case A — learned signal transfers

Conditions:

- Stage 5 offline gate passes; and
- Stage 6 complete-run positive gate passes.

Disposition:

- accept `learned_non_combat_v1` as an **experimental** public non-combat policy;
- retain expert fallback for unsupported families;
- recommend planner review of T066 or a narrower joint-policy task;
- do not claim natural A20 or live-game promotion.

### Case B — offline signal does not transfer

Conditions:

- Stage 5 passes; but
- Stage 6 outcome/coverage gate fails without a tooling/fidelity invalidation.

Disposition:

- do not promote the learned controller;
- preserve the fixed target/checkpoint/evaluation evidence;
- recommend exactly one narrow follow-up based on whether the failure is
  screen-coverage, target-horizon/rollout-policy mismatch, or run-level
  distribution shift.

Do not launch a larger natural run merely because the 256-seed comparison is
neutral.

### Case C — no held-out action-value signal

Condition:

- Stage 5 offline gate fails with otherwise valid evidence.

Disposition:

- skip Stage 6;
- do not promote the learned controller;
- close this v1 target/model formulation and recommend at most one narrowly
  justified target/model diagnostic.

### Case D — invalid experiment

Condition:

- source replay, checkpoint restore, public-input firewall, target completeness,
  split integrity, simulator identity, legal-action semantics, or other tooling
  failure prevents valid attribution.

Disposition:

- make no scientific policy conclusion;
- recommend only the narrow repair required to make the same frozen experiment
  executable.

## CLI And Command-Surface Boundary

T065 must **not** add task-numbered flags or new experiment branches to the
legacy flat main CLI. In particular, avoid expanding these current debt
surfaces solely for T065:

- `src/sts_combat_rl/commands/cli_parser.py`;
- `src/sts_combat_rl/commands/lightspeed_cli.py`;
- `src/sts_combat_rl/commands/cli_validation.py`;
- the long dispatch chain in `src/sts_combat_rl/cli.py`.

The T065 workflow may be exposed through one small neutrally named module command
or thin script that delegates to reusable library functions, for example a
`non_combat_learning` command surface with explicit collect/target/train/evaluate
operations. Do not create a generic command registry/framework merely to satisfy
this rule.

Existing main CLI behavior and standard mock gates must remain unchanged.

## Artifact And Reuse Contract

Large source runs, continuation rows, checkpoints, logs, and reports remain under
an ignored stable root such as:

`artifacts/t065-learned-non-combat-policy-v1/`

Compact artifacts must use versioned schemas and include paths/hashes, source
identity, simulator identity, split identity, config, counts, and reproduction
commands.

Recommended compact logical artifacts:

- source-state selection manifest;
- counterfactual target dataset/report;
- model-input/training manifest;
- two checkpoint metadata reports;
- held-out decision report;
- conditional complete-run comparison report;
- terminal decision report.

Do not add sidecar proof chains, dependency-hash graphs, or security-style
attestation. Hashes identify immutable inputs/artifacts and stale-data mistakes;
they are not a distrust mechanism against repository producers.

Use T071 stage/run-local reuse rules. A reviewed repair names the earliest
affected stage or independent run; valid preceding outputs remain reusable.
Producer Git SHA is provenance, not a global cache key.

## Parallelism And Long Jobs

- Expensive simulator collection/continuation/evaluation stages target 16
  effective orchestration workers, capped by shard count, memory, and simulator
  constraints.
- Training uses `torch_threads=1` per model run. Independent model seeds may run
  concurrently when resource-safe.
- Use the existing detached-job utility for long stages. Report PID, status/log
  paths, command, worker count, source/cohort range, and coarse expected duration
  once; do not keep an AI agent in a continuous polling loop.
- Every expensive stage reports wall-clock, simulator/search cost, records/runs
  completed, failures, and reuse decisions.

## Out Of Scope

- Human trajectories, human action labels, human expert imitation, or strategy
  annotations.
- Imitation loss on `expert_non_combat_v1` actions.
- Learned battle-policy/search changes, battle checkpoint refresh, or replacing
  the battle controller.
- T063 implementation.
- End-to-end joint optimization or T066 implementation.
- Public-consistent hidden-future sampling or normal-information optimal-value
  claims.
- Shop/event/card-select learned control in v1.
- Broad hyperparameter search, architecture search, ensembles, or repeated
  post-hoc gate tuning.
- Natural 10,000-run scale-up, final A20 performance claim, or live
  CommunicationMod deployment.
- Refactoring the entire CLI, removing the 71 MB real fixtures, adding CI/branch
  protection, choosing a license, or broad unrelated module cleanup.
- Local reimplementation of Slay the Spire mechanics, event outcomes, shop
  rules, map logic, or reward values.

## Deliverables

- Versioned public non-combat model-input contract.
- Portable replay-valid non-combat source-state records/selection manifest.
- Counterfactual all-eligible-action continuation target pipeline.
- Small frozen learned non-combat action-value/ranking model and checkpoint
  contract.
- Learned online non-combat policy/controller integration through the T074
  policy boundary with explicit expert fallback.
- Held-out action-value report.
- Conditional matched complete-run comparison report when Stage 5 passes.
- Terminal Case A/B/C/D decision report with exactly one next recommendation.
- Focused tests and documentation required by this task only.

## Acceptance Criteria

T065 implementation may be accepted as a **completed experiment** when all
applicable frozen stages are valid, even if the scientific result is Case B or
Case C. Scientific promotion is separate from implementation correctness.

Mandatory acceptance conditions:

- all four mandatory screen families have exactly 80 selected replay-valid
  source states with frozen 48/16/16 train/validation/test counts;
- source splits are seed-group disjoint and contain no replay-equivalent duplicate
  across splits;
- every selected supported source state evaluates every eligible legal action;
- training/validation candidate actions have exactly two continuation-policy
  seeds and held-out candidates exactly four;
- there are zero missing candidate/continuation rows in a valid target dataset;
- model input is public-only and passes hidden-field audits;
- expert behavior actions are not used as supervised targets/features;
- both frozen model seeds train with the published configuration and checkpoint
  metadata;
- checkpoint selection uses validation evidence only;
- held-out evaluation is complete before any decision to run Stage 6;
- Stage 6 is skipped automatically on valid Case C;
- if Stage 6 runs, it contains the same 256 fresh seeds in all three arms and
  exactly 768 terminal runs overall;
- all fallback, controller failures, truncations, source identities, and compute
  costs remain explicit;
- terminal Case A/B/C/D is determined from the published gates without post-hoc
  threshold changes;
- no existing accepted scientific result/schema is silently reinterpreted;
- legacy flat CLI files do not gain T065-specific routes/flags;
- no large generated dataset/checkpoint is committed to Git.

## Required Verification

Run the standard local gates from `docs/tasks/README.md` plus focused T065 tests.
At minimum include:

- policy-boundary import/dependency regression tests from T074;
- public/hidden-field input firewall tests;
- supported/unsupported-screen routing tests;
- variable legal-action masking and stable tie-break tests;
- portable source-state replay equality tests;
- exact checkpoint branch/restore tests;
- all-eligible-action target completeness tests;
- split leakage/duplicate tests;
- deterministic paired continuation-seed tests;
- model-input round trip/schema mismatch tests;
- checkpoint save/load/provenance tests;
- synthetic training sanity test proving loss/selection plumbing works without a
  simulator-scale run;
- held-out gate aggregation/bootstrap tests;
- learned fallback coverage/report tests;
- complete-run matched-seed validation tests;
- terminal decision-table tests for Cases A/B/C/D;
- `git diff --check`.

Before simulator evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Use the exact current-main Python/native pairing for all simulator evidence.
Large WSL stages must be sharded, detached where appropriate, and reported with
full commands and artifact identities.

## Legacy Reference

Consult:

- T010 for the stochastic non-combat baseline;
- T014--T016/T033 for public information and model-input boundaries;
- T040 for expert bootstrap behavior and non-combat action categories;
- T061 for the matched bottleneck decomposition;
- T064 for the terminal recommendation selecting T065;
- T071 for reuse/long-job conventions;
- T074 for the current acyclic policy ownership boundary;
- `docs/training_paradigm.md` for the simulator-only/no-human-data contract.

Historical experiment artifacts are not implicit inputs. Every consumed artifact
must come from a stable documented path or be regenerated by the published
workflow.

## PR Report

The implementation PR must report:

- exact approved spec commit and baseline;
- pinned simulator identity;
- source seed range and both source behavior arms;
- per-family source counts and train/validation/test identities;
- optional Boss-relic diagnostic coverage, if used;
- continuation controller and continuation-policy seed sets;
- candidate/target row counts and completeness;
- model-input/checkpoint schema identities;
- both model seeds and training metrics;
- validation-based checkpoint selection;
- held-out per-family and aggregate action-value results;
- bootstrap probabilities and action disagreement;
- whether Stage 5 passed and whether Stage 6 was therefore executed;
- complete-run three-arm results and learned-control/fallback coverage when run;
- all commands, workers/shards, PID/status/log paths for detached stages,
  wall-clock and simulator/search cost;
- failures, truncations, reuse decisions, and deviations;
- standard/focused verification results;
- terminal Case A/B/C/D;
- exactly one planner-facing next recommendation;
- explicit confirmation that T065 added no human imitation target and no
  T065-specific route to the legacy flat CLI.
