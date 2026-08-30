# T077: T075 Same-Experiment Continuation

## Objective

Resume the accepted T075 non-combat experiment after T076 repaired checkpoint
restore fidelity, without changing the scientific question or any T075 design
choice.

T077 is a new task/run identity. It does not reopen, mutate, or reclassify the
immutable T075 Case D terminal record.

## Current Main Baseline

T075 produced a valid leakage-safe 320-state cohort, then stopped at TARGET with
accepted Case D because repeated checkpoint restoration changed legal-action
identity at retained state 67.

T076 repaired the root cause at the native checkpoint owner. Its accepted
`sts_lightspeed` integration is:

```text
cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083
```

The T076 repair only removed `GameContext::map` aliasing across checkpoint
branches. Fresh restore public state and ordered legal-action identities retained
the accepted semantics; T075 science was not rerun or reclassified.

## Dependencies

T075 and T076.

## Normative Inheritance

T077 inherits T075 and its upstream T065 contracts for all unchanged science.
This includes, without restating them:

- retained T065 source identities and provenance;
- replay-equivalence key and T075 global ownership rule;
- per-family/per-split quotas and the accepted 320-state cohort;
- counterfactual target procedure;
- model architecture, input regime, optimizer, and action semantics;
- continuation, model, bootstrap, evaluation, and driver seeds;
- Stage-5 and Stage-6 gates;
- public-information boundary;
- runtime/parallelism requirements from TARGET onward;
- A/B/C/D terminal and promotion meaning.

A change to any of those meanings is outside T077.

## T077 Bindings

T077 adds exactly two material bindings to the inherited experiment:

1. simulator execution from TARGET onward uses accepted integration
   `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083`;
2. the earliest affected scientific stage is TARGET.

The authoritative T075 retained source and selection artifacts remain exactly the
artifacts recorded by merged PR #77 and its retention manifest. Their producer
provenance remains the original T075/T065 integration
`fee272f1ae21c283ad2161f55293cfe6d714134a`; T077 must not rewrite historical
artifact metadata to claim they were produced by the T076 integration.

T076 compatibility evidence is sufficient to reuse the accepted T075
SOURCE_REUSE and SELECTION_REPLAY results: the repair changes checkpoint copy
ownership, not fresh-restored public state or legal-action meaning. The first
T075 stage that expands multiple continuations from restored checkpoints is
TARGET, so TARGET and all later reached stages are rerun under the repaired
integration.

Before scientific execution starts, Maintainer must establish availability and
exact identity of the authoritative retained T075 inputs. Failure to establish
required inputs before the run starts is operational and produces no scientific
outcome; it does not authorize recollection or reselection.

## Scientific Execution

Start from the exact retained T075 320-state cohort at TARGET.

- Do not recollect source runs.
- Do not rerun or alter cohort selection.
- Do not replace an inconvenient or failing state.
- Run TARGET under the accepted T076 integration and the inherited T075 target
  procedure.
- If TARGET is valid, continue through TRAIN, GATE, and EVAL exactly as inherited
  from T075.

Implementation may provide the minimal task-specific adapter needed to start a
new run at this reuse boundary. Module names, helper APIs, CLI spelling, temporary
paths, logging, and non-material serialization are implementation freedom.

## Terminal Meaning

T077 inherits T075 terminal semantics unchanged:

- TARGET/TRAIN fidelity, completeness, legality, replay, schema, controller, or
  information-regime failure -> Case D;
- valid Stage-5 gate failure -> Case C;
- valid Stage-6 evaluation failure -> Case B;
- valid Stage-6 pass -> Case A.

Case B/C/D are valid experiment results when reached through the inherited rules.
Only Case A carries the inherited promotion meaning.

## Out Of Scope

- modifying T075 source/cohort/replay/ownership/quota semantics;
- changing target construction, model, seeds, gates, information regime, or
  promotion rules;
- recollection, reselection, replacement, or quota repair;
- modifying T075's historical Case D record or retention manifest;
- human trajectories, human action labels, or heuristic-action imitation;
- Battle Search caching, snapshot, transposition, or other unrelated work;
- generic workflow/control-plane machinery.

## Acceptance Criteria

1. The run uses the exact authoritative retained T075 source/selection identities
   without recollection, reselection, or metadata rewriting.
2. TARGET and every later simulator stage reached by the run use integration
   `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083`.
3. TARGET executes the inherited T075 procedure over the exact retained 320-state
   cohort; any inherited TARGET invalidity terminates as Case D without
   replacement.
4. If TARGET is valid, TRAIN/GATE/EVAL follow the unchanged T075 model, seeds,
   gates, information regime, and terminal semantics.
5. T075's existing terminal record remains immutable and is not reclassified.
6. The final T077 result is one inherited A/B/C/D terminal with sufficient
   retained evidence to reproduce or safely reuse the reached-stage outputs.

## Required Verification

Before authoritative scientific execution:

- verify the pinned `sts_lightspeed` source/integration identity;
- verify exact retained T075 input identities and availability;
- pass the implementation tests needed to demonstrate the TARGET-start reuse
  boundary and unchanged inherited semantics;
- satisfy the repository standard local gates, with pre-existing base/environment
  deviations reported rather than redefined as T077 science.

Freeze the authoritative T077 run head only after implementation acceptance. No
scientific TARGET-or-later execution occurs on a moving code head.

## PR Evidence

The PR report must record:

- exact implementation/run head;
- accepted T076 integration identity;
- exact reused T075 retained input identities;
- confirmation that SOURCE_REUSE/SELECTION_REPLAY were reused rather than rerun;
- reached stages, commands/topology, produced artifact identities, and final
  A/B/C/D terminal;
- any baseline/environment deviations separately from scientific outcomes.
