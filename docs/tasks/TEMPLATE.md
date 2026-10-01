# TXXX: Task Name

Artifact Eligibility Required: true

## Objective

State one concrete result and why it matters.

## Current Main Baseline

Describe only capabilities already merged into `main`. Identify the specific
gap this task closes.

## Dependencies

List prerequisite task IDs or `none`.

## Inputs And Artifacts

List every required input artifact, external/ignored artifact path, schema,
provenance requirement, and command needed to regenerate or provide it. State
which outputs this task writes and which are committed fixtures versus ignored
or external artifacts.

Do not rely on another task's temporary smoke output or local worktree file as
an implicit input.

## Artifact Eligibility Contract

If this task consumes a learned checkpoint, teacher/trainer dataset, or
generated learning-source artifact, name the inputs, intended reuse mode,
scientific claim boundary, required predicates, and unavailable-fact behavior
(what happens when a required fact is unavailable). Tasks with no such dependency may state
`none` and are exempt from this contract.

## Scope

Define required behavior, ownership boundaries, and public interfaces.

## Diagnostic Method Gate

For debugging, failure-localization, root-cause, observability, or other diagnostic
tasks, follow [`../diagnostic_method.md`](../diagnostic_method.md). Record the
completed static production-code/data-flow/configuration/game-semantic analysis,
the exact unresolved fact if any, existing retained evidence that must be reused,
and the smallest dynamic witness that could distinguish the remaining mechanisms.
Do not authorize new telemetry or a population-scale replay/census unless the
contract states why existing evidence and the minimal witness cannot answer the
question. After each new observation layer, return to source/data-flow analysis
before escalating again.

For non-diagnostic tasks, state `not applicable`.

## Out Of Scope

List adjacent work that must not enter this branch.

## Design Constraints

List architectural, information-regime, provenance, compatibility, dependency,
and performance constraints.

## Deliverables

List code, tests, patches, schemas, fixtures, reports, and command surfaces that
must exist in the pull request.

## Acceptance Criteria

Write objective pass/fail statements. Acceptance must not depend on unstated
judgment or chat context.

## Required Verification

List exact local commands, WSL commands, datasets, seeds, budgets, and expected
invariants. Include artifact generation or acquisition commands for every
required input. Reference the standard local gates when applicable.

## Legacy Reference

List any old commit or files that may be consulted. State known defects and
whether selective porting is allowed.

## PR Report

List the evidence, compatibility notes, risks, and deviations required in the
pull-request description, including consumed and generated artifact identities.
