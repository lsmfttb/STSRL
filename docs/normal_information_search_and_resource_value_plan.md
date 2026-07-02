# Normal-Information Search And Resource Value Plan

This document defines the active design direction for a normal-information
battle agent and context-dependent long-term resource value. It extends the
repository contract in [`project_architecture.md`](project_architecture.md).

## Problem

Two simple approaches are insufficient:

- increasing random terminal playout count does not solve the battle state
  space;
- assigning fixed weights to HP, potions, gold, relic counters, and deck
  changes does not capture their context-dependent long-term value.

Slay the Spire is partially observable. A player sees current public state and
history but usually does not see future draw order, future random choices, or
hidden encounter randomness. The target normal agent must act under that
uncertainty.

The final value target is A20 Heart victory probability.

## Information Regimes

Keep these controllers and artifacts separate:

- `normal_public_policy`: policy/value model from public state and history;
- `normal_belief_search`: search across public-consistent hidden futures;
- `full_simulator_state_oracle_like`: current native hidden-state search and
  teacher/evaluation workflows;
- `sl_attempt_budgeted`: restart-enabled agent with a named attempt budget.

Oracle actions are not direct normal-agent labels. An action optimal for one
known hidden future may be poor across the futures a player considers possible.

## Complete Public State

The normal agent's state target includes:

```text
current public battle state
+ full public action/observation history
+ complete player-visible run history
+ persistent public resources
+ complete visible map and routes
+ visible Act Boss
```

Complete run history includes prior battles, events, shops, rests, rewards,
skips, relic choices, potion decisions, keys, route choices, and their public
results. These facts can change what future content remains possible and how
valuable current resources are.

The history contract should be typed, ordered, versioned, and sanitized. It
must not expose hidden RNG, unrevealed future encounters, or the hidden Act-3
second Boss.

## Search Architecture

### Public Policy And Value Baseline

First establish an honest normal-information model that:

- accepts only sanitized public state and history;
- scores every legal action;
- predicts survival and structured outcomes;
- reports uncertainty;
- is evaluated separately from Oracle-like search.

This baseline is required even if the final controller is search-based because
it supplies priors, leaf values, and uncertainty estimates.

### Model-Guided Search

Serious search should use:

- public policy priors;
- learned leaf values;
- explicit chance and observation handling;
- uncertainty-aware budget allocation;
- public-state reuse or transpositions where valid;
- reports for visits, values, uncertainty, depth, simulator steps, model calls,
  and wall-clock time.

Random terminal rollout count remains a smoke/Oracle budget.

### Public-Consistent Hidden Futures

An authoritative simulator capability is required:

```text
sample hidden battle futures consistent with this public state and history
```

The sampler preserves all public facts and game rules, including information
revealed by effects such as Frozen Eye. Python code does not reconstruct game
mechanics to create particles.

The first implementation may aggregate root actions across independent sampled
futures. It must be labeled as an approximation because solving each
determinization independently can leak future-specific strategy. A later
action-observation tree is the principled target.

## Oracle-To-Normal Transfer

The transfer unit is a set of hidden futures sharing the same public state.

For one public state:

1. Sample several consistent hidden futures.
2. Run Oracle or model-guided search on each.
3. Preserve per-action outcome and resource-value distributions.
4. Aggregate public targets such as expected value, lower-tail value,
   near-optimal probability, expected regret, and disagreement.
5. Train from public state and aggregated targets only.
6. Evaluate with hidden state inaccessible to the acting controller.

Useful shared learning may include tactical encoders, public-history encoders,
outcome prediction, action ordering, and uncertainty. Direct Oracle-action
cloning is not the promotion target.

## Structured Resource Outcomes

At battle end, preserve:

- battle win/death and run-terminal outcome;
- absolute current HP and HP delta;
- absolute max HP and max-HP delta;
- potion slot contents by identity;
- gold and gold delta;
- persistent deck additions/removals, including curses;
- relic identities and public persistent counters;
- keys and other simulator-provided persistent public resources;
- continuation controller and run provenance.

Some components have no globally correct direction. Relic counters and potion
inventory can be more or less valuable depending on future routes, Boss,
events, and the rest of the run. The raw vector therefore remains auditable and
is never permanently replaced by fixed reward weights.

## Value Hierarchy

### Observable Outcome Heads

Predict battle survival and terminal resource distributions. These heads are
auditable and useful before a strong run-value model exists.

### Continuation Value

Learn:

```text
V_continue(post_battle_public_run_state, continuation_controller_provenance)
```

The continuation controller is part of the target because changing future
behavior changes resource value.

Before enough Heart victories exist, auxiliary targets may include reaching the
next elite, Boss, act, or Heart. They are curricula, not replacements for the
final objective.

### Root Action Selection

Primary utility is expected eventual run success. During early unreliable-value
stages, a named constrained rule may first reject materially worse survival
actions and then optimize continuation value among survival-competitive
actions. The tolerance and risk measure are explicit configuration.

## Model Outputs

The planned public model exposes:

- legal-action policy logits;
- battle-survival probability;
- terminal absolute-HP distribution or quantiles;
- structured terminal resource predictions;
- continuation/run-success value;
- epistemic uncertainty or ensemble disagreement.

The model needs explicit interactions among:

- tactical state;
- action;
- complete public history;
- route graph and visible Boss;
- persistent deck, relic, potion, and resource context.

Separate embeddings do not imply losing interactions: combine them through
attention, cross features, or other joint layers before scoring actions and
values.

## Self-Improvement Loop

1. Collect complete runs under the current normal controller and named
   stochastic non-combat driver.
2. Preserve complete public histories, terminal resource vectors, and later run
   outcomes.
3. Train policy, outcome, continuation-value, and uncertainty heads.
4. Improve the controller with public policy/value-guided belief search.
5. Evaluate on frozen natural and structural cohorts.
6. Promote only statistically credible improvements.
7. Repeat with new on-policy data.

Oracle search supplies diagnostics, upper bounds, and multi-future auxiliary
targets. Normal-agent promotion uses only normal-information evaluation.

## Phases

### N0: Public Contracts And Firewall

Progress: foundation complete through T006, T012, and T014--T018. Current `main`
has explicit Oracle-like provenance for native hidden-state search, a
sanitized public controller boundary, structured terminal resource outcomes,
public-context artifact propagation/replay/audit, and native terminal resource
identity coverage where the simulator exposes it. Remaining public-context
gaps such as complete map/route payloads and richer typed history encoders are
explicit missingness, not hidden-field fallbacks.

Required follow-up work:

- improve typed complete player-visible run history and map/route payload
  coverage where native support permits it;
- build structured history/map/visible-Boss model encoders;
- keep hidden-field firewall audits in every normal-information dataset and
  controller path.

Exit gate: complete public trajectories and terminal resources survive
collection/export/reload without hidden fields and with explicit missingness
where native public projection is still incomplete.

### N1: Honest Public Policy/Value Baseline

Progress: T009 completed optional PyTorch policy/value plumbing, checkpoint
provenance, trainer-input preflight, and fail-closed broad-training gates.
T024 added explicit teacher-targeted trainer-input v6 policy targets and
diagnostic checkpoint provenance for Oracle-like supervision. Sufficient A20
data/evaluation coverage is still pending, so broad training must remain
blocked unless a named smoke or narrow-curriculum override is explicitly
reported.

Exit gate: a reproducible normal-information baseline reports per-component
errors and fixed-cohort performance from sufficient A20 coverage.

### N2: Model-Guided Oracle Search Sandbox

Progress: M1 task batch completed through T030. Search telemetry, checkpoint
inference, teacher guidance calibration, the first model-guided Oracle-like
controller, the first fixed-cohort comparison report, and the M1 synthesis are
available on `main`. T030 records that M1 succeeded as Oracle-like plumbing but
did not demonstrate controller improvement or normal-information evidence.
T031 completed the first post-M1 coverage refresh and found the current source
distribution still Act-1-only. Task lifecycle state remains canonical in the
task index. T036 completed the immediate reachability probe before changing
direction: it added current-schema search-controlled complete-run collection,
but the accepted 10-run A20 smoke arms did not recover the historical Boss/Act2
source path. T037 recovered the historical Boss/Act2 source signal, and T039
records the accepted narrow source-coverage contract. T032 completed the
narrow teacher/checkpoint diagnostic refresh over that contract, and T035
completed the follow-up root-only model-guided Oracle-like search comparison;
neither produced broad A20 training readiness or controller-promotion
evidence. T040--T044 completed the assisted source-generation and de-assisted
evaluation batch, again as diagnostic evidence rather than promotion. T045
completed the post-T044 failure analysis: its accepted smoke evidence favored
root-only search integration as the primary bottleneck, with weak-model and
distribution-mismatch signals also active, no action-space/fallback issue
observed, and teacher-label noise unavailable without a linked calibration
report. T046 completed the minimal native root-prior allocation surface. T047
completed the first root-prior guided smoke comparison. T048 completed the
fixed-cohort root-prior guided scale-up. T049 is now the published `READY`
task to test whether that fixed-cohort signal changes complete-run source
reachability before larger training or non-combat branches.

Use the Oracle regime to validate priors, leaf values, uncertainty, and search
instrumentation. Exit when model guidance improves the fixed Oracle curve at
equal wall-clock budget.

### N3: Public-Consistent Hidden-Future Sampling

Progress: planned.

Exit when repeated authoritative particles share identical public observations
while retaining diverse legal hidden futures.

### N4: Normal Belief Search

Progress: planned.

Exit when belief search improves normal-information fixed evaluation at equal
compute without leakage.

### N5: Oracle-To-Normal Auxiliary Transfer

Progress: planned.

Retain only auxiliary targets that improve normal-information evaluation.

## Immediate Design Work

1. Keep broad teacher/checkpoint refresh evidence blocked until sufficient A20
   per-act coverage exists; the T039 contract and assisted batches remain
   diagnostic supplements, not broad-training coverage.
2. Extend sanitized public context only through explicit native/public
   contracts, keeping missing map, route, and history payloads explicit.
3. Establish an honest public policy/vector-value baseline from sufficient A20
   coverage, keeping raw policy diagnostics separate from search promotion.
4. Design and pin the authoritative public-consistent hidden-future sampler;
   T034 remains blocked until that native boundary exists.
5. Complete T049's root-prior complete-run reachability probe before
   publishing an assisted training repair or non-combat ranker branch; publish
   implementation work only through `READY` task rows in the task index.
6. Keep further mechanical CLI/module cleanup in later dedicated
   no-behavior-change maintenance tasks before mixing it into search research;
   the first CLI/export cleanup pass completed in
   [`T019`](tasks/T019-codebase-mechanical-refactor.md).

Relevant papers are design references, not algorithm commitments:

- AlphaZero policy/value-guided search: <https://arxiv.org/abs/1712.01815>
- POMCP belief-state planning:
  <https://papers.nips.cc/paper_files/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html>
- MuZero value-equivalent planning: <https://arxiv.org/abs/1911.08265>
