# sts_lightspeed Integration And Native Change Policy

This document defines how STSRL consumes and changes the external
[`lsmfttb/sts_lightspeed`](https://github.com/lsmfttb/sts_lightspeed) fork.

The policy protects one invariant above all others: **every accepted STSRL task
uses one continuous simulator lineage**. Role separation is useful for review,
but it is not the mechanism that keeps the simulator dependency coherent.

The STSRL source manifest and reviewed STSRL task PR remain authoritative for
which exact simulator commit is accepted by `main`.

## Purpose

STSRL uses `sts_lightspeed` as its current large-scale simulator substrate. The
real Slay the Spire game remains the final mechanics authority. The fork exists
to expose and repair simulator capabilities needed by STSRL, not to create a
second game specification.

The previous policy required essentially every native change to be implemented
through a separate `sts_lightspeed` maintainer handoff. That reduced the chance
of divergent task-specific simulator branches, but it relied too heavily on
agents remembering a cross-repository role rule during long tasks. The current
policy instead enforces a single accepted lineage technically and requires
independent review only where native semantic risk justifies it.

## Canonical Simulator Lineage

The fork has exactly one active STSRL integration branch:

```text
stsrl/main
```

STSRL may formally consume only an exact commit on that branch. The manifest
must therefore always name:

```text
branch: stsrl/main
ref:    refs/heads/stsrl/main
commit: <exact 40-character commit on that ref>
```

Temporary implementation branches are allowed, but they are never accepted
STSRL build inputs:

```text
work/T0XX-short-name          # temporary implementation branch
stsrl-source/T0XX             # optional immutable provenance tag
```

A manifest must never pin `work/*`, `stsrl/t*`, a local-only ref, or an
unmerged native commit.

For every task that changes the simulator, define:

```text
native_base   = exact stsrl/main commit pinned by STSRL when the task begins
native_result = exact descendant commit after the change is integrated
```

The required lineage invariant is:

```text
native_base --is-ancestor-of--> native_result
native_result ∈ refs/heads/stsrl/main
```

If remote `stsrl/main` advances while native work is in flight, do not create a
parallel accepted line and do not force-push. Reconcile the temporary work with
the new active line so the final accepted result contains the intervening
history.

## Role Split

### Planner

Planner owns task meaning when a native change is scientifically material:

- why a native change is needed;
- information-regime boundaries;
- whether a simulator behavior change is a parity/compatibility repair or a new
  scientific variable;
- claim and rerun boundaries when the accepted simulator identity changes.

Planner does not prescribe ordinary C++ helper layout or pybind implementation
spelling.

### STSRL Main Maintainer

Main Maintainer owns:

- exact simulator-lineage checks;
- `docs/sts_lightspeed_source_manifest.json`;
- source-verifier and landing evidence;
- review of native changes consumed by the STSRL task;
- independent semantic review for high-risk native changes unless another
  independent native reviewer is explicitly used;
- final STSRL implementation/operational acceptance.

Main Maintainer remains an independent reviewer and should not implement feature
code that it later accepts.

### STSRL Task Implementer

After the STSRL task has valid exact-spec `SPEC APPROVED` with
`implementation_authorized=true`, the current task Implementer **may also make
necessary changes in the `sts_lightspeed` fork**. A separate simulator agent is
not mandatory.

When native work is needed, Implementer owns:

- creating a temporary `work/T0XX-*` branch from the verified `native_base`;
- minimal C++/pybind implementation;
- native tests/build evidence;
- a reviewable fork PR or equivalent exact commit/diff record;
- updating the STSRL manifest only after the accepted native result has entered
  `stsrl/main`;
- STSRL adapters/tests/docs and clean source-verifier evidence.

Implementer must not make STSRL depend on the temporary branch itself.

### Optional Native Specialist

A dedicated `sts_lightspeed` agent/maintainer remains available when native
work is unusually complex or when independent implementation is itself useful.
It is an escalation tool, not a mandatory hop for every native edit.

## Native Risk Classification

Every task-owned native change is classified before it is accepted.

### Low-risk native plumbing

Examples include:

- adding or adjusting pybind exposure without changing underlying behavior;
- read-only telemetry/instrumentation with demonstrated parity;
- build/compiler compatibility repairs;
- validation/error-reporting changes that do not alter accepted transitions;
- mechanical native test/support code.

The current STSRL task Implementer may implement these changes directly. Normal
Maintainer code review plus lineage/source-verifier gates are sufficient.

### High-risk native semantics

A change is high-risk when it can change simulator trajectories, search values,
accepted information, or game parity. This includes at least:

- RNG state or random transition semantics;
- game/battle/screen state transitions and automatic cleanup;
- checkpoint capture/copy/restore semantics;
- legal-action enumeration or action execution semantics;
- battle/run terminal state or outcome determination;
- `evaluateEndState`, reward/utility, or terminal scoring;
- search selection, expansion, rollout, backup, allocation, or root selection;
- hidden-state exposure or public/hidden information boundaries;
- card/relic/potion/monster/game mechanics or parity fixes.

The task Implementer may still write the change, but **an independent native
semantic review is mandatory before the result is accepted onto the STSRL
simulator lineage**. The reviewer must not be the author of the native change
and must record the exact native head reviewed, the semantic risk checked, and
its conclusion. The STSRL Main Maintainer can satisfy this review when it did
not author the change; a dedicated native specialist may be used when useful.

High-risk review is a review requirement, not a requirement to duplicate the
implementation in another agent.

## Native Task Lifecycle

STSRL uses the repository-wide **one task = one PR** workflow by default.
Native work is a dependency lane inside that task, not a reason to split the
STSRL task into a publication PR and a second implementation PR.

For a task that needs a native change:

1. Planner publishes the normal STSRL task PR from synchronized `main`.
2. Maintainer records exact-spec `SPEC APPROVED` with
   `implementation_authorized=true` before implementation starts.
3. Read the current STSRL source manifest and fetch remote `stsrl/main`.
4. Require the manifest commit and remote active-line commit to agree at the
   task's native starting boundary. Record that exact commit as `native_base`.
5. Create temporary fork branch `work/T0XX-*` from `native_base`.
6. Implement and test the narrow native change. Record whether it is low-risk
   or high-risk under this policy.
7. Review the fork diff. High-risk changes require the independent native
   semantic review described above.
8. Integrate the accepted native change into `stsrl/main` without force-pushing
   or creating a parallel active integration line.
9. Record the exact resulting commit as `native_result` and prove that
   `native_base` is its ancestor.
10. Only now update the STSRL manifest to `native_result`. The manifest continues
    to name only `stsrl/main` / `refs/heads/stsrl/main`.
11. Run the canonical STSRL source verifier from a disposable checkout and any
    task-specific parity/regression gates.
12. Apply the task's scientific reuse/rerun rule from the earliest boundary
    materially affected by the native change.
13. After STSRL accepts the new source identity, delete the merged temporary
    `work/T0XX-*` branch unless an explicit reason to retain it is recorded.
    Preserve provenance through the fork PR, exact commit SHA, and optional tag.

For a task that does not change native source, keep the manifest identity fixed
and do not create a task-specific simulator branch.

## Required Native Declaration In The STSRL PR

When native source changes, the task PR must record at least:

```text
native_change_required: true
native_risk: low | high
native_base_ref: refs/heads/stsrl/main
native_base_commit: <exact SHA>
native_work_branch: work/T0XX-...
native_result_ref: refs/heads/stsrl/main
native_result_commit: <exact SHA>
lineage_check: PASS
independent_native_review: not-required | <review evidence>
```

Also report:

- fork PR/compare link;
- changed native API or semantic surface;
- native build/test result;
- source-verifier result;
- information-regime impact;
- parity/compatibility risk;
- earliest STSRL artifact/runtime stage that must be rerun.

Do not create a second durable native-task registry just to store these fields.
The STSRL task PR and exact Git history are sufficient.

## Technical Gates

Repository-owned validation should enforce the lineage instead of relying on
agents remembering branch policy:

- source-manifest parsing rejects any integration branch other than
  `stsrl/main` and any ref other than `refs/heads/stsrl/main`;
- the source verifier requires that the active remote ref resolve to the exact
  manifest commit;
- when a task changes the manifest commit, the native lineage check must prove
  that the previous accepted integration commit is an ancestor of the new one;
- the new commit must already be reachable from remote `refs/heads/stsrl/main`;
- no local or temporary work branch may be required to reproduce an STSRL gate.

A failed lineage check blocks acceptance. Do not solve it by pinning the task's
work branch.

## Information And Mechanics Boundary

Native changes must preserve STSRL information-regime rules:

- normal-information paths must not receive hidden RNG, unrevealed future
  encounters, hidden draw order, hidden Act-3 second Boss, or other hidden
  simulator state;
- Oracle-like native search surfaces must declare
  `full_simulator_state_oracle_like`;
- public projection APIs report missing visible context explicitly rather than
  filling it with guessed or hidden data;
- state mutation, legal-action enumeration, restore, encounter selection, and
  hidden future sampling come from the simulator, not STSRL Python
  reimplementations.

Do not deliberately alter Slay the Spire mechanics for training convenience.
A real parity/compatibility defect may be repaired, but its behavioral scope and
rerun boundary must be explicit.

## Review And Landing Checklist

Before accepting an STSRL PR that changes simulator identity, Maintainer checks:

- manifest branch/ref are exactly `stsrl/main` /
  `refs/heads/stsrl/main`;
- `native_base` is the previously accepted manifest commit;
- `native_result` is fetchable from remote `stsrl/main`;
- `native_base` is an ancestor of `native_result`;
- any concurrent active-line movement was reconciled, not replaced;
- high-risk semantic changes have independent native review;
- source verifier builds from a clean/disposable checkout;
- required native capabilities and task-specific regressions pass;
- no normal-information path receives new hidden state;
- no simulator source/build product was vendored into STSRL;
- the task's affected scientific stages were rerun or explicitly retained under
  its approved reuse boundary.

## Branch Cleanup And Provenance

`stsrl/main` should normally be the only long-lived STSRL integration branch.
Temporary `work/T0XX-*` branches are working refs, not provenance objects. After
an accepted merge they should be deleted; the PR, commit SHA, and optional
`stsrl-source/T0XX` tag preserve history more reliably.

Historical task-shaped branches may remain only when explicitly retained as
provenance. They must never be presented as normal build inputs.

### T079 migration note

`work/T079-state-utilization-cc40` is historical merged residue. Its accepted
changes are already contained in `stsrl/main` and the T079 recovery evidence was
subsequently pinned and verified against the exact accepted integration commit.
The residual branch is not a second active simulator line and does not by itself
invalidate T079 evidence. It may be deleted as branch cleanup once the repository
owner/Main Maintainer chooses to remove the stale ref.

## Emergency Maintenance

Non-code housekeeping may still be performed directly by Main Maintainer, for
example verifying refs, repairing the active branch at an already accepted
commit, creating provenance tags, or deleting an already merged temporary
branch.

Native feature/semantic code remains Implementer work so that Maintainer can
review it independently. Use a dedicated native specialist when risk or
complexity warrants it, not as a mandatory ritual.

## Updating This Document

Update this policy when the active integration-line strategy, source-manifest
contract, native risk boundary, or simulator acceptance process changes.

Do not use this document to claim a new simulator capability is implemented.
That requires the relevant STSRL task PR, exact manifest identity, verifier
evidence, and normal final acceptance.
