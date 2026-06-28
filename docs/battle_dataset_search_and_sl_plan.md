# Battle Dataset, Search Agent, And SL Branch Roadmap

This is the active roadmap for battle-state generation, evaluation, search
development, and the separately evaluated SL-enabled branch. Repository-wide
rules come from [`project_architecture.md`](project_architecture.md). Current
implementation status comes from [`current_status.md`](current_status.md).

The published foundation, maintenance, and first research-measurement backlog
is complete through the M1 synthesis and T031 coverage refresh, except for
cancelled T007, whose scope was superseded by T014--T016. T031 found the
current A20 source distribution still Act-1-only; T036 added search-controlled
reachability tooling but its accepted smoke arms were also Act 1 only. T037
recovered a narrow Boss/Act2 source signal, and T039 records the accepted
source-coverage contract. Broad teacher/checkpoint refresh work remains
blocked; the current executable task is the narrow T032 diagnostic refresh over
the T039 contract. New implementation work should start only from rows marked
`READY` in the task index.

## Goals

The project must answer these questions independently:

1. How strong is the battle controller on each legal encounter and incoming
   state distribution?
2. How much full-run failure comes from battle play versus non-combat state
   generation?
3. Can learned priors or values improve search at the same compute budget?
4. How much value comes from hidden-state knowledge or explicit battle
   restarts?

A20 is the final target. A0 remains separately labeled curriculum or diagnostic
data.

## Dataset Families

### Natural Run Pool

Collect one battle-start checkpoint for every naturally reached battle in a
complete run. Preserve the biases of the named battle controller and stochastic
non-combat driver.

Use it for:

- real incoming-state distribution measurement;
- full-run reachability and survival analysis;
- a natural core for training;
- source checkpoints for other dataset families.

Required provenance includes seed, ascension, structural encounter metadata,
complete battle and non-combat controller configuration, public run context,
and a restorable native checkpoint or portable replay trace.

### Stratified Training Pool

Resample natural checkpoints by structural metadata. The initial strata are:

```text
ascension
act
room_type
encounter_id
```

The default conceptual mixture is natural draws plus structurally balanced
draws. The exact ratio is an experiment parameter and is always reported.

Balanced sampling changes optimization weight, not unique-state coverage.
Every sampled decision retains its source checkpoint and sampling component.

### Constructed Supplement

Apply conservative, authoritative same-ruleset battle-start transforms to
natural A20 checkpoints. Constructed samples are explicitly tagged and never
replace the natural core.

Allowed directions include:

- small bounded HP perturbations from later battle starts;
- simulator-native potion additions when plausible;
- legal same-structure ordinary or elite encounter alternatives.

HP transforms use a practical seeded approximation. Favor small changes, cap
them using observed opportunity and plausibility signals, avoid impossible
early-run states, and report the policy. Authoritative replay is optional for
audits or high-impact cases rather than required for every sample.

Visible-Boss replacement is excluded from ordinary training because earlier
choices were conditioned on that Boss.

### Paired Counterfactual Evaluation

Compare controllers from the same source checkpoint under controlled
alternatives, such as every legal Act 1 elite encounter. This isolates
encounter-specific strengths and reduces evaluation variance.

Counterfactual results are not natural-run performance. Boss alternatives
remain evaluation-only and preserve the source Boss separately.

## Why More Seeds Are Not Enough

More natural runs increase sample count but converge toward the distribution
induced by the current controllers. A weak controller that rarely passes Act 1
will continue producing mostly early normal battles.

The project therefore needs all three mechanisms:

- more disjoint natural A20 runs for real coverage;
- structural resampling for optimization efficiency;
- conservative constructed or paired states for rare structural cases.

Do not confuse repeated rare checkpoints with new coverage.

## Natural Non-Combat State Generation

The current non-combat driver is not trainable, but it must generate a useful,
auditable natural distribution.

Rules:

- remain seeded and stochastic;
- sample hierarchical strategy categories before individual legal actions;
- use modest priors rather than deterministic hand-written routes;
- keep rare legal branches reachable;
- version behavior changes;
- preserve complete provenance.

Future improvements should target coverage while avoiding strategy-quality
filters. Examples include better category calibration, explicit route-category
sampling, and authoritative generation of rare but legal states.

## Complete Public Context

Raw snapshots and datasets should retain enough public structure to support
future continuation-aware models:

- tactical battle state and legal actions;
- persistent run resources;
- complete typed player-visible history, including events and prior choices;
- complete visible map, current node, and available routes;
- visible Act Boss.

The latest `main` preserves the current sanitized public run context and
ordered public history through active in-memory decisions and current persisted
artifacts. T014 completed the raw native-capability boundary, T015 completed
the sanitized context/history contract, and T016 added persisted artifact
propagation, portable replay comparison, and context coverage audit. Remaining
native projection gaps, such as complete map/route payloads on some screens,
stay explicit status fields rather than guessed context.

## Evaluation

### Fixed Battle Cohorts

Freeze deterministic cohorts using structural strata only. Do not silently
fill missing strata using judgments about deck quality or winnability.

Report:

- battle win/death;
- terminal absolute current HP and HP loss;
- structured resource outcomes;
- simulation count, model calls, simulator steps, and wall-clock time;
- illegal-action and simulator failures;
- natural-weighted result;
- encounter-macro result;
- room-type-macro result;
- per-encounter result;
- missing and under-covered strata.

### Full Runs

Report full-run progression separately and always name both the battle
controller and non-combat driver. Average final floor is useful, but it cannot
replace fixed battle evaluation.

### Promotion

Promote a controller only after credible held-out or fixed-cohort improvement.
Training fit, teacher agreement, and small average-floor changes are diagnostic
signals, not promotion gates.

## Search Development

### Current Baseline

Current native search copies hidden simulator state and runs random terminal
playouts. It is an Oracle-like engineering baseline.

`highest-mean` is the default direct root-selection rule. Preserve root visits
separately for diagnostics or soft targets. Low-budget most-visited actions are
strongly affected by exploration.

### Next Search Capabilities

1. Instrument compute, tree depth, uncertainty, model calls, and wall-clock
   cost.
2. Add public-state policy priors for action ordering and allocation.
3. Add learned leaf and structured outcome values.
4. Allocate budget using uncertainty and decision closeness.
5. Add authoritative public-consistent hidden-future sampling.
6. Build and evaluate normal-information belief search.

Every comparison uses fixed cohorts and reports both compute and information
regime.

## Learned Model Role

The model should eventually support:

- legal-action policy priors;
- battle-survival probability;
- terminal absolute-HP distribution;
- structured terminal resource prediction;
- continuation/run-success value;
- uncertainty or disagreement;
- embeddings for tactical entities, complete public history, visible routes,
  and visible Boss context.

The action identifies a possible transition from the state. Decision quality
therefore requires state-action interactions; an action-only linear score is a
plumbing baseline, not a credible final model.

T009 now provides optional PyTorch policy/value plumbing, checkpoint
provenance, trainer-input preflight, and a fail-closed broad-training gate.
Broad training still waits for explicit scale and distribution readiness.
Smoke-scale training remains useful only for interface validation or named
narrow curricula.

## Live Game Deployment Compatibility

Simulator-only training and evaluation do not require the real game process.
However, a trained, search, or hybrid controller is not live-game runnable until
it passes a CommunicationMod runtime adapter gate.

That gate requires:

- the same public tactical feature and legal-action contract used by simulator
  training;
- conversion from player-visible CommunicationMod snapshots to the shared
  decision context;
- stable action identity and duplicate-action disambiguation;
- command-payload mapping back to CommunicationMod protocol commands;
- runtime provenance and source-format logging;
- explicit missing-field and unsupported-state behavior.

This compatibility work is tracked by
[`T013`](tasks/T013-live-communicationmod-runtime-adapter.md). It is a deployment
gate, not a substitute for fixed battle evaluation or full-run performance
measurement.

## SL-Enabled Branch

The SL branch models the real restart behavior where an agent can replay a
battle and use observations from earlier attempts.

It remains separate from the normal-information agent:

```text
normal agent: no restart memory, no hidden future
SL agent: named attempt budget and retained observations
Oracle-like agent: actual hidden simulator state available
```

Planned stages:

1. **SL-0, deterministic restart verification:** prove that restoring and
   replaying the same public actions reproduces the battle.
2. **SL-1, full-future Oracle upper bound:** quantify maximum benefit from known
   hidden state.
3. **SL-2, limited lookahead:** restrict future knowledge.
4. **SL-3, attempt-budgeted agent:** learn how to spend a finite number of
   restarts.

SL data may provide auxiliary supervision, but normal-agent promotion depends
only on normal-information evaluation.

## Phases

### Phase A: Checkpoint And Replay

Progress: complete through [`T004`](tasks/T004-battle-start-checkpoint-pool.md).

Exit gate: repeated restores reproduce snapshots, legal actions, transitions,
and terminal results without local mechanics reconstruction.

### Phase B: Natural Pools And Provenance

Progress: complete through T004 for natural pool capture, portable restore, and
structural coverage reporting. Broader A20 coverage remains a measurement gap,
not an unimplemented pool feature.

Exit gate: current-schema natural checkpoints restore, carry complete controller
provenance, and report structural coverage and migration loss honestly.

### Phase C: Fixed Structural Evaluation

Progress: complete through [`T005`](tasks/T005-fixed-battle-evaluation.md).

Exit gate: search changes can be compared on deterministic structural cohorts
without relying on full-run average floor.

### Phase D: Coverage And Stratified Search Data

Progress: T007 is cancelled. T014 completed the native capability boundary, T015
completed sanitized context/history, and T016 completed persisted
context/replay/audit. See the
[T007 review handoff](t007_review_handoff_2026-06-22.md). T017 completed the
stable source-integration path, and T006 added the explicitly Oracle-like
native search teacher/evaluation path. T012 completed the structured outcome
schema and explicit missingness boundary; T018 completed native
identity-bearing terminal resource coverage through the T017-managed source
integration rather than the old local patch stack. Broad coverage follows fixed
evaluation rather than being inferred from natural-run floor statistics. T008
completed conservative constructed A20 battle-start supplements, but the
accepted audit remains smoke-scale evidence for the transform workflow rather
than a broad coverage gate. T009 completed the optional PyTorch training
plumbing and broad-training gate. T021 completed the first current-schema A20
coverage report across natural starts, sampled optimization weight,
constructed supplements, restore evidence, structured outcomes, public-context
availability, and broad-training gate gaps. The accepted smoke-scale result is
Act 1 only and keeps the broad-training gate closed. T031 later repeated the
coverage measurement at 50 source episodes; artifacts and restores were
healthy, but the distribution still produced only Act 1 starts with no Boss or
later-act starts. T036 added the current-schema search-controlled complete-run
collection path and reachability report. Its accepted 10-run smoke comparison
covered default, 20-simulation no-potion Oracle-like search, and
20-simulation potion-enabled Oracle-like search arms; all stayed in Act 1. T037
then recovered the Boss/Act2 signal at the historical 1,000-run comparison
point. T039 records the accepted source contract. T032 is now deliberately
narrowed to a diagnostic teacher/checkpoint refresh over that contract rather
than a broad A20 refresh. T035 later confirmed that deeper root-only
model-guided Oracle-like search over the narrow diagnostic checkpoint does not
yet improve the smoke fixed cohort. The next published source-generation batch
is therefore T040--T044: add a versioned expert non-combat source driver, repair
potion-enabled Oracle search, extend assistance into complete-run source
generation, train assisted teacher/value-policy diagnostics, and evaluate
de-assisted fixed cohorts.

Work:

- improve natural state generation;
- measure natural, stratified, and constructed mixture coverage;
- collect a reported natural/balanced/constructed mixture;
- retain complete public history and context;
- satisfy broad-training readiness per ascension and act.
- keep mechanical cleanup separate from coverage/search experiments.

Exit gate: enough unique A20 Boss and later-act starts exist for meaningful
training and evaluation.

### Phase E: Search Improvement

Progress: T009 completed optional PyTorch policy/value plumbing and diagnostic
training reports. T021 completed the current coverage-measurement report used
to decide what A20 data and distribution gaps remain before broad training or
model-guided search work starts. T022 completed the current Oracle-like teacher
dataset report, making teacher coverage, source linkage, and search statistics
auditable before teacher scale-up feeds model-guided search. T023 completed a
small structured A20 Oracle-like teacher scale-up workflow across named search
budgets and reports teacher-label stability. T024 completed the bridge from
teacher artifacts to explicit trainer-input v6 teacher targets and diagnostic
checkpoint provenance. T025 completed the current search telemetry baseline,
T026 completed the checkpoint inference/scoring contract, T027 completed
offline checkpoint-vs-teacher calibration reporting, T028 completed the first
model-guided Oracle-like root-selection controller, and T029 completed the
first equal-source/equal-budget fixed-cohort comparison. T030 records the M1
synthesis: the sandbox validated plumbing but did not show smoke-scale
controller improvement, because the T029 comparison tied baseline Oracle search
while adding checkpoint model calls. T031 completed the next coverage refresh
and diagnosed a distribution gap rather than unlocking broader
teacher/checkpoint work: the current run distribution still did not reach Boss
or later-act battle starts. T036 completed the first current-schema
search-controlled reachability probe; the smoke evidence validated tooling but
did not recover Boss or later-act starts. T037/T039 recovered and contracted a
narrow Boss/Act2 supplement. Meaningful held-out improvement or controller
promotion remains pending broader source-generation coverage. T035 completed a
deeper root-only model-guided Oracle-like search comparison over refreshed
diagnostic provenance and again tied the baseline smoke outcome. Current
follow-up work is the T040--T044 assisted source-generation batch, which treats
Oracle search and learned models as teacher/search/value diagnostics until
low-assistance or unassisted fixed-cohort evidence improves.

Exit gate: a search change improves fixed evaluation at equal simulation or
wall-clock budget without natural-weighted regression.

### Phase F: Normal Belief Search

Progress: pending simulator hidden-future sampling.

Exit gate: public-information belief search improves normal-information fixed
evaluation without leakage.

### Phase F2: Live Runtime Deployment Gate

Progress: runtime adapter contract complete; interactive controller validation
pending.

Exit gate: a controller can consume captured CommunicationMod combat snapshots,
select through the shared `OnlineController` contract, emit valid protocol
commands, and record runtime provenance without simulator-only inputs.

### Phase G: SL Branch

Progress: planned.

Exit gate: restart value is quantified separately by encounter and attempt
budget.

## Deferred Decisions

Defer these until measurements justify them:

- the optimal natural/balanced/constructed training mixture;
- whether encounter alternatives should become broad training data;
- the exact route/history model architecture;
- the final normal-belief-search algorithm;
- how much architecture the normal and SL branches should share.

See [`experiment_log.md`](experiment_log.md) for dated coverage and search
measurements.
