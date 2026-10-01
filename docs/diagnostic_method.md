# Diagnostic Method

This document is normative for repository tasks whose primary purpose is debugging, failure localization, root-cause analysis, observability design, or diagnosis of an unexpected scientific/architectural result.

The purpose is to prevent expensive experiments from substituting for source-level reasoning.

## Default Order Of Evidence

Use this order unless a task contract records a concrete reason why a later stage is necessary first:

1. production-code structure and data flow;
2. configuration/filter semantics and game/domain semantics;
3. already accepted retained artifacts and telemetry;
4. the smallest deterministic dynamic witness that distinguishes the remaining mechanisms;
5. new observability only when a specific required fact is unavailable;
6. population-scale replay/census only when prevalence/distribution is itself part of the claim or smaller evidence cannot answer the question.

A later stage does not replace an earlier one. After every new observation layer, return to source/data-flow analysis before authorizing another observation layer.

## Static Analysis Record

Before adding telemetry or running a new diagnostic population, record:

- the exact production producers of each compared value/surface;
- transformations, filters, canonicalization, and configuration gates between producer and consumer;
- relevant game/domain semantics;
- existing invariants and where they are checked;
- concrete candidate mechanisms;
- for each mechanism, the observable prediction that would distinguish it from the alternatives;
- whether an existing accepted artifact already contains that distinguishing fact.

Do not assume that similarly named sets or interfaces are identical. For example, a game's full legal-action set, a controller's enabled action set, and a Search algorithm's configured root-action set may differ by design.

## Static Sufficiency Gate

If production code plus accepted retained data deductively establish the mechanism needed by the task, stop the diagnostic escalation.

Do not run a witness only for reassurance, and do not add telemetry or a full census to rediscover a mechanism already established by the code/data contract.

A static conclusion must identify the complete causal/data-flow chain and any bounded assumptions. It must also check for retained counterexamples before generalizing across a population.

## Minimal Dynamic Witness Gate

When static analysis leaves more than one material mechanism consistent with the evidence, use the smallest deterministic witness that separates those mechanisms.

The task contract must record before execution:

- the exact unresolved fact;
- why production code and existing retained evidence cannot answer it;
- the smallest witness population/configuration that can;
- the distinct predicted outcomes for each remaining mechanism;
- why a larger sample is unnecessary at this stage.

A causal configuration intervention may be used as a diagnostic witness when appropriate, but it is not automatically evidence that the intervention should be promoted or retained as production policy.

## Observability Gate

New telemetry or native observability is justified only when all of the following are written down:

- the exact unavailable fact;
- why it is material to distinguish remaining mechanisms;
- why existing safe/accepted interfaces and artifacts cannot expose it;
- the minimal new field/surface needed;
- the information-regime/privacy boundary of that field;
- the test that will consume it.

Do not add broad telemetry because a failure is opaque in general. Add only the smallest surface required by the current unresolved question.

## Scale-Up Gate

A full population replay or census is justified when at least one of these is true:

- prevalence/distribution across the population is itself the scientific claim;
- a mechanism is known but its coverage across heterogeneous strata is materially unknown;
- the minimal witness contradicts the static model and a bounded larger sample is needed to characterize the new heterogeneity;
- downstream acceptance explicitly depends on a population statistic.

A census is not the default tool for discovering a causal mechanism that can be derived from production code or a small witness.

## Stop Conditions

Every diagnostic task must define a stopping point. Stop and return control to Planner when:

- the mechanism is established at the task's claimed level;
- the exact missing fact requires new observability;
- evidence contradicts the current mechanism set;
- the next step would be repair/redesign rather than diagnosis;
- the next step would materially increase sample size without a new population-level question.

Do not silently convert a diagnosis task into a repair task or a scale experiment.

## Evidence And Claims

Keep these claim levels distinct:

- control-flow localization;
- representation/contract mismatch;
- game-mechanics root cause;
- repair correctness;
- repair efficacy;
- population prevalence;
- controller/Search quality;
- complete-run or promotion evidence.

Evidence for an earlier level does not automatically establish a later one.

## Task-Contract Requirement

Diagnostic task contracts must include a `Diagnostic Method Gate` section that states:

- current diagnostic stage;
- completed static analysis;
- exact unresolved fact, if any;
- existing retained evidence to be reused;
- conditions under which a dynamic witness is permitted;
- conditions under which new observability or scale-up is permitted;
- explicit prohibited escalation.

If a task is not diagnostic, it may state `not applicable`.
