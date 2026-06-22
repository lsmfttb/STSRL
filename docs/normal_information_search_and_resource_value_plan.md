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
- `full_simulator_state_oracle_like`: planned integration of native hidden-state
  search;
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

Status: pending T006, T012, and the T014--T016 public-context replacement
sequence.

Required work:

- explicit Oracle-like provenance for native hidden-state search;
- sanitized public controller boundary;
- structured terminal resource outcome contract;
- complete typed player-visible run history;
- relic-counter visibility audit;
- end-to-end hidden-field firewall;
- structured history/map model encoder.

Exit gate: complete public trajectories and terminal resources survive
collection/export/reload without hidden fields.

### N1: Honest Public Policy/Value Baseline

Status: pending [`T009`](tasks/T009-pytorch-search-guidance.md) and sufficient
data/evaluation coverage.

Exit gate: a reproducible normal-information baseline reports per-component
errors and fixed-cohort performance from sufficient A20 coverage.

### N2: Model-Guided Oracle Search Sandbox

Status: planned.

Use the Oracle regime to validate priors, leaf values, uncertainty, and search
instrumentation. Exit when model guidance improves the fixed Oracle curve at
equal wall-clock budget.

### N3: Public-Consistent Hidden-Future Sampling

Status: planned.

Exit when repeated authoritative particles share identical public observations
while retaining diverse legal hidden futures.

### N4: Normal Belief Search

Status: planned.

Exit when belief search improves normal-information fixed evaluation at equal
compute without leakage.

### N5: Oracle-To-Normal Auxiliary Transfer

Status: planned.

Retain only auxiliary targets that improve normal-information evaluation.

## Immediate Design Work

1. Define the typed complete public run-history schema.
2. Extend simulator snapshots and decision records without exposing hidden
   future state.
3. Build structured history, map, and visible-Boss encoders.
4. Establish an honest public policy/vector-value baseline.
5. Design the authoritative public-consistent hidden-future sampler.

Relevant papers are design references, not algorithm commitments:

- AlphaZero policy/value-guided search: <https://arxiv.org/abs/1712.01815>
- POMCP belief-state planning:
  <https://papers.nips.cc/paper_files/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html>
- MuZero value-equivalent planning: <https://arxiv.org/abs/1911.08265>
