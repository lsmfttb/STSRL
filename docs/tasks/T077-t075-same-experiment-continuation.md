# T077: T075 Same-Experiment Continuation

## Objective

Resume the accepted T075 non-combat experiment after T076 repairs checkpoint
restore fidelity, without changing the scientific question or replacing any
T075 design choice.

## Current Main Baseline

T075 produced a valid 320-state leakage-safe cohort and then stopped at TARGET
with accepted Case D because checkpoint restoration violated legal-action
identity fidelity at state 67. T076 exists only to repair that simulator defect.

T077 is intentionally DRAFT until T076 is accepted and its simulator integration
identity plus compatibility evidence are known.

## Dependencies

T075 and T076.

## Frozen Inheritance

All T075 scientific semantics remain unchanged, including:

- retained T065 source identities;
- replay-equivalence key and global ownership rule;
- per-family/per-split quotas and the accepted 320-state cohort;
- counterfactual target procedure;
- model architecture and input regime;
- continuation, model, bootstrap, evaluation, and driver seeds;
- Stage-5 and Stage-6 gates;
- public-information boundary;
- A/B/C/D terminal meaning and promotion rules.

T077 must not restate or redefine those contracts.

## Only Planned Delta

Use the simulator integration accepted by T076 and continue the same T075
experiment from the earliest stage whose semantics were affected by the restore
repair.

The expected start is TARGET. This is not frozen while T077 is DRAFT.

Before T077 can become `READY`, Planner must bind:

1. the exact accepted T076 simulator integration identity; and
2. explicit compatibility evidence for the retained T075 artifacts.

If T076 demonstrates that the retained T075 320-state cohort and its accepted
selection/replay evidence remain semantically valid under the repaired
integration, T077 reuses them and begins at TARGET. If that compatibility does
not hold, T077 remains DRAFT for a Planner revision of the earliest affected
stage. There is no automatic recollection, reselection, or substitution.

## Inputs And Artifacts

Use only the authoritative T075 retained artifacts recorded by merged PR #77 and
the accepted T076 integration/evidence. Architecture-rejected PR #75 artifacts
are not inputs.

No new source collection is permitted merely because the simulator integration
changes.

## Out Of Scope

- changing or tuning T075 source selection, ownership, quotas, targets, model,
  seeds, gates, or information regime;
- replacing failed or inconvenient cohort members;
- using human trajectories, human action labels, or bootstrap heuristic actions
  as supervised targets;
- combining T076 repair and T077 scientific continuation in one implementation;
- unrelated Battle Search, caching, snapshot, or transposition work.

## Acceptance Meaning

Once the exact T076 binding and reuse boundary are approved, T077 inherits the
T075 terminal semantics unchanged:

- TARGET fidelity failure -> Case D;
- valid TARGET/TRAIN followed by Stage-5 failure -> Case C;
- Stage-5 pass followed by Stage-6 failure -> Case B;
- Stage-6 pass -> Case A.

A Case B/C/D is a valid experiment result when reached through the inherited
T075 rules. Only Case A may carry the inherited promotion meaning.

## Required Verification

While DRAFT, no T077 implementation or scientific execution is authorized.

Before publication as `READY`, verify the T076 integration identity and the
retained T075 compatibility boundary. After publication, run the standard local
gates and only the inherited T075 stages from the approved earliest affected
boundary.

## PR Report

The publication revision must report the accepted T076 identity, the exact reuse
boundary and evidence, and confirm that no T075 scientific parameter changed.
The final scientific PR reports only the inherited T075 evidence required for
reached stages and the resulting A/B/C/D terminal.
