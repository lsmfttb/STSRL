# T078: Restored Public-Context Fidelity Repair

## Objective

Repair the restored-state fidelity boundary exposed by T077 so that a retained
source checkpoint can reproduce the exact public decision context expected by
the frozen T075/T077 target procedure before any counterfactual continuation is
run.

This is an infrastructure recovery task. It does not change the T075/T077
scientific question and it does not authorize policy training, search promotion,
or a new non-combat experiment.

## Current Main Baseline

T077 is complete after PR #81. Its authoritative scientific run head
`b00e33ff8a150b3ad1b5b4c0cb8048d258ae621a` used accepted `sts_lightspeed`
integration `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083` and reused the exact
T075 320-state cohort without recollection or reselection.

The corrected TARGET run reached a valid inherited Case D at retained state 160:

```text
restore public context mismatch
```

The same mismatch was reproduced in a single-state debug on the same accepted
native build, so the failure is not explained by the 16-process execution
topology. No replacement was made and TRAIN/GATE/EVAL were skipped.

T076 had already repaired a distinct state-67 checkpoint defect caused by
`GameContext::map` aliasing. The accepted state-67 branch-isolation regression
must remain valid; T078 must not weaken or reinterpret that repair.

## Dependencies

T077, T076, T015, T016, T017, T020, and T033.

## Why This Task Precedes New Search Research

The next research priority remains the Battle Search representation hypothesis:
measure effective unique-state utilization and path-equivalent duplication before
changing learned guidance. That experiment, and other fixed-cohort restored-state
diagnostics, require a trustworthy restore/public-context boundary.

T077 therefore exposes a cross-cutting prerequisite. Publishing a transposition
or state-utilization experiment while retained restored states can disagree with
their own public context would make the result difficult to interpret. T078
repairs that prerequisite first; it does not itself implement transposition,
Beam search, or any learned-guidance change.

## Semantic Invariant

For a retained selected source state `i`, let:

- `C_i` be the native checkpoint/replay boundary used by the frozen target path;
- `P_i` be the retained normal-information public decision context and its
  canonical identity/model-input-relevant fields;
- `A_i` be the retained ordered legal-action identities.

Before any counterfactual action is executed, restoring/reconstructing `C_i`
through the canonical T075/T077 path must reproduce `P_i` and `A_i` exactly.
The required invariant is:

```text
restore_or_replay(C_i)
  -> public decision context = P_i
  -> ordered legal actions = A_i
```

If the target procedure reuses the same checkpoint after exploring a branch,
that later restore must reproduce the same immediate public context and ordered
legal actions. Continuation RNG may affect transitions after the restore; it may
not change the restored source decision context itself.

The public-context comparison must use the same semantic identity/fields owned by
the existing T015/T016/T033 and T075/T077 contracts. T078 must not invent a new
parallel definition of public state solely to make state 160 pass.

## Inputs And Reuse

Use the authoritative retained T077/T075 evidence:

- exact T075 selected cohort: 320 states / 320 replay keys, selection SHA-256
  `94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8`;
- accepted T077 integration
  `cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083` as the failing baseline;
- retained T077 TARGET outcome and terminal evidence under
  `/mnt/d/DeadlycatCoding/STSRL/artifacts/t077-t075-same-experiment-continuation`;
- the reproducible state-160 single-state failure;
- the accepted T076 state-67 regression.

Historical T075/T077 artifacts and terminal classifications remain immutable.
T078 may read them as regression inputs but must not rewrite their provenance or
claim they were produced by a repaired integration.

## Scope

1. Reproduce state 160 under the accepted T077 integration and capture the first
   material public-context difference at field/identity level.
2. Localize ownership of the mismatch before changing code. The root cause may
   reside in native checkpoint state, Python adapter restore state, public-run
   context reconstruction/history, or another existing canonical owner; do not
   assume it is the same defect as T076.
3. Repair the lowest canonical owner that violates the frozen restore/public
   context semantics.
4. Add a deterministic state-160 regression covering the exact failing restore
   boundary and, where relevant, branch-then-restore behavior.
5. Preserve and rerun the accepted state-67 T076 regression.
6. Run a restore-only fidelity sweep over the exact retained 320-state cohort.
   The sweep compares the restored/reconstructed immediate public context and
   ordered legal-action identities with the retained source records but does not
   execute the expensive counterfactual continuation matrix or produce target
   values.
7. If the repair changes the external `sts_lightspeed` integration, update the
   normal T017/T020 source manifest and pin the exact accepted integration
   identity.

Implementation details such as helper APIs, diagnostic serialization, executor
choice, and temporary paths remain implementation freedom provided the semantic
checks above are preserved.

## Failure Boundary

The 320-state sweep is intended to prevent another one-state-at-a-time repair
loop.

- If all mismatches are explained by one restore/public-context ownership defect,
  repair that defect and require the full sweep to pass.
- If the sweep exposes an independent material defect outside the same canonical
  fidelity boundary, do not silently broaden T078 into unrelated architecture.
  Retain the diagnostic evidence and return it to Planner review before further
  scientific execution.

No failed state may be dropped or replaced to satisfy the sweep.

## Out Of Scope

- rerunning T077 TARGET, TRAIN, GATE, or EVAL;
- changing T075/T077 source selection, replay identity, quotas, target procedure,
  continuation seeds, model, gates, or information regime;
- reclassifying the T075 or T077 Case D records;
- training or promoting a non-combat policy;
- Battle Search transposition, Beam search, capability retention, search-guidance
  tuning, policy/value changes, or a new outcome comparison;
- human trajectories, human action labels, or human strategy heuristics;
- generic checkpoint/provenance/control-plane redesign not required by the
  localized fidelity defect.

## Acceptance Criteria

1. The retained state-160 mismatch is reproduced deterministically under the
   accepted pre-repair T077 integration, with the first material differing
   public-context field or identity recorded.
2. The root cause is localized to an existing canonical owner and the repair is
   made at that owner rather than by weakening the T075/T077 validator or
   special-casing state 160.
3. After repair, state 160 reproduces the retained immediate public decision
   context and ordered legal-action identities before continuation.
4. Repeated restore after relevant branch exploration, when exercised by the
   frozen target path, also reproduces the same immediate public context and
   ordered legal actions.
5. The accepted T076 state-67 regression remains passing with unchanged semantic
   expectations.
6. A restore-only audit of all exact 320 retained states reports no public-context
   or ordered-legal-action mismatch and performs no candidate replacement.
7. If the native fork changes, the source verifier and manifest pass on one exact
   new integration identity; otherwise the PR demonstrates why the repair is
   entirely outside the native integration.
8. No T075/T077 artifact, terminal classification, policy conclusion, or
   promotion claim is changed.

## Required Verification

Run the standard local gates plus focused restore-fidelity verification:

- pre/post state-160 deterministic regression;
- accepted T076 state-67 regression;
- exact 320-state restore-only fidelity sweep with retained source identities;
- pinned source verifier and native smoke when the external integration changes.

If the 320-state sweep is substantial on the maintainer workstation, use the
repository's effective-concurrency rule and report the actual worker/shard
execution evidence. The sweep must remain restore-only; do not turn it into a
T077 scientific rerun.

## Deliverables And PR Evidence

The PR must report:

- exact implementation head and accepted-spec head;
- exact failing baseline integration and, if changed, exact repaired integration;
- state-160 field-level mismatch and root cause;
- ownership layer changed by the repair;
- pre/post state-160 result;
- state-67 regression result;
- exact 320-state sweep identity, mismatch count, and artifact/report identity;
- standard and task-specific verification results;
- confirmation that T075/T077 science was not rerun or reclassified.

## Successor Boundary

T078 does not automatically resume the T075/T077 non-combat experiment and does
not publish T063 or T066. After the repair is accepted, Planner re-evaluates the
queue from the new `main`.

Absent another restore-fidelity blocker, the intended research priority is the
previously identified Battle Search representation diagnostic: measure unique
combat-state utilization and path-equivalent duplication under the existing
search at fixed budgets before deciding whether to implement state transposition
or another search topology. That successor requires a separate Planner task and
Maintainer approval.
