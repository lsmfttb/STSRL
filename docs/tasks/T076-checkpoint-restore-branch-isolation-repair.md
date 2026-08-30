# T076: Checkpoint Restore Branch-Isolation Repair

## Objective

Repair the simulator checkpoint/restore boundary exposed by T075 so that
exploring one continuation branch cannot change the immediate state or legal
actions obtained by restoring the same checkpoint again.

## Current Main Baseline

T075 completed the repaired 320-state leakage-safe selection, then stopped at
TARGET with the accepted A10 `TARGET_INVALID` Case D. The reproducible failure
is retained state 67 (`MAP_SCREEN`, source seed `650212`): after a
`game_potion_discard` branch with continuation seed `652201`, restoring the same
checkpoint for continuation seed `652202` returned two legal actions instead of
the original four.

This is a restore-fidelity defect. T075 produced no target table, training,
Stage-5/Stage-6 result, or learned-policy conclusion.

## Dependencies

T075, T017, T020.

## Semantic Delta

Correct checkpoint restoration so a checkpoint denotes one branch-isolated
simulator state. For a fixed checkpoint `C`, branch execution before a later
`restore(C)` must not affect the state observed immediately after that restore.
Continuation RNG may affect future transitions after restore; it must not mutate
the restored checkpoint state itself.

The material invariant is:

```text
restore(C) -> immediate public state + ordered legal-action identities = S
run any legal branch from C
restore(C) -> immediate public state + ordered legal-action identities = S
```

## Inputs And Reuse

Use the merged T075 retention boundary and exact state-67 diagnostic as the
primary regression. The T075 pinned `sts_lightspeed` integration
`fee272f1ae21c283ad2161f55293cfe6d714134a` is the failing baseline.

T075 scientific outputs are not modified. If the repair changes the external
`sts_lightspeed` integration, update the normal source manifest/integration
identity through the existing T017/T020 ownership path.

## Scope

- reproduce and localize the state-67 branch contamination;
- repair the lowest canonical state owner responsible for it;
- add a retained-state regression covering the known potion-discard sequence;
- verify branch-order isolation across every legal root action of that retained
  state;
- preserve existing public-state and legal-action semantics apart from removing
  the contamination.

The implementation may choose the minimal native or Python boundary needed by
the root cause. Module names, helper APIs, serialization details, and diagnostic
format are implementation freedom.

## Out Of Scope

- rerunning T075 TARGET or any later scientific stage;
- changing the T075 cohort, replay key, ownership rule, quotas, target procedure,
  model, seeds, gates, or information regime;
- policy training or controller promotion;
- adding generic snapshot/provenance/control-plane machinery;
- addressing unrelated Battle Search caching or transposition work.

## Acceptance Criteria

1. The known state-67 sequence is represented by a deterministic regression tied
   to the retained T075 evidence and fails under the pre-repair behavior.
2. After repair, repeated restores of that checkpoint produce identical immediate
   public-state identity and ordered legal-action identities regardless of which
   legal root branch was explored beforehand.
3. The exact `game_potion_discard` / `652201` -> restore / `652202` failure no
   longer occurs.
4. The repair does not change legal actions or public state for a fresh restore
   relative to the accepted checkpoint semantics; it only removes cross-branch
   contamination.
5. If the fork integration changes, the pinned source verifier and integration
   manifest pass on the new identity.
6. No T075 scientific result is reclassified and no policy conclusion is made.

## Required Verification

Run the standard local gates plus the focused WSL/native state-67 regression.
The regression must exercise the known failing sequence and branch-isolation
checks over the state-67 root legal actions. Run the pinned source verifier when
the external integration changes.

## Deliverables And PR Evidence

The PR contains only the minimal restore repair, focused regression coverage,
and any required integration-manifest update. Report the root cause, pre/post
state-67 behavior, affected ownership layer, verification results, and exact new
integration identity if one changes.

## Successor Boundary

T076 does not itself resume T075 science. After T076 is accepted, Planner binds
T077 to the accepted simulator integration and decides the earliest reusable
T075 stage from explicit compatibility evidence.
