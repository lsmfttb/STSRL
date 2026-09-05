# Collaboration Workflow

This document defines the repository's task collaboration workflow.

The detailed operational protocol for delegating to an Implementer, waiting for
its terminal result, reading delegated/compacted output, and continuing the
Maintainer workflow is in
[`implementer_coordination.md`](implementer_coordination.md). That guide
supplements this document without changing task authority or acceptance
semantics.

> Freeze what can change scientific or durable project meaning. Leave equivalent
> implementation choices free.

The default threat model is **cooperative but fallible**. Protect against mistakes,
stale state, information leakage, incomplete experiments, and incorrect reuse.
Do not add hostile-producer/security machinery unless a task explicitly needs it.

The repository operates **serially by default**: normally there is at most one
active scientific task PR. The default workflow is **one task = one PR**. A
separate specification-publication PR is optional, not the default.

## Roles

### Planner

Planner owns task meaning:

- scientific objective and interpretation;
- task-owned semantic changes relative to merged `main`;
- information-regime boundaries;
- acceptance, invalid/fidelity, terminal, and promotion meaning;
- state/lineage rules only when they affect scientific results, reproducibility,
  or a real downstream contract;
- resolution of genuine contract/architecture gaps;
- publication of new task contracts on the task PR;
- final scientific/architecture acceptance;
- direct task landing after both final acceptances are recorded on the same exact
  final head.

Planner does not normally own module names, function signatures, CLI spelling,
helper layout, logging, temporary files, or test harness design.

### Main Maintainer

Maintainer owns execution coordination and repository conformance:

- branch/worktree/lifecycle/merge hygiene;
- execution-readiness review and exact-spec `SPEC APPROVED`;
- Implementer dispatch after `implementation_authorized=true` is recorded for the
  current task contract;
- verification, runtime evidence, and artifact retention;
- implementation review and finding classification;
- final implementation/operational acceptance;
- preparation of factual lifecycle/result landing records before final dual
  acceptance whenever practical.

Maintainer may choose ordinary execution bindings that do not change task meaning.
Maintainer does not invent scientific semantics, acceptance meaning, information
regime, promotion criteria, or successor science.

### Task Implementer

After Maintainer records exact-spec `SPEC APPROVED` with
`implementation_authorized=true`, Implementer owns ordinary implementation
choices, including code/tests, module/function layout, minimal APIs, CLI adapters,
non-material serialization, logging, temporary files, multiprocessing mechanics,
and mechanical refactors.

Implementer must not stop merely because the Planner contract does not prescribe
one exact API or representation. It stops only for a genuine semantic gap as
defined below.

## Task Contract

Each task has one normative document under `docs/tasks/`.

A task contract is **delta-first**: define only what the task newly owns or
changes. Inherit unchanged merged rules by reference; do not restate them as a
second normative source.

Include only materially needed information: objective/baseline, semantic delta,
affected information boundary, material inputs/outputs/lineage, acceptance and
terminal meaning, reproducibility-critical execution parameters, and evidence
needed to support the claim.

A narrow task should have a narrow contract. Contract complexity far beyond the
semantic delta is an architecture warning.

Default to **semantic core + implementation freedom**. Freeze exact fields,
ordering, bytes, or unknown-key rejection only when exact representation is part
of the scientific algorithm/identity or required by an existing merged consumer.

Acceptance tests must derive expected meaning independently of the production
helper under test. The Implementer may create the minimal API needed by tests;
absence of a pre-existing public function or CLI endpoint is not a contract gap.

## One-Task-One-PR Default

There is exactly one durable task-lifecycle list: merged
`docs/tasks/README.md` on `main`. Do not maintain a second durable task list in an
issue or PR.

However, because work is serial, the repository also recognizes one temporary
**in-flight execution authority**: the unique open task PR whose current task
contract has received Maintainer exact-spec `SPEC APPROVED` with
`implementation_authorized=true`.

This is not a second lifecycle database. It is the single active transaction on
top of durable `main`:

- merged `main` = landed/durable project truth;
- unique approved open task PR = current in-flight task authority;
- final merge commits the task result back to durable `main`.

### Default task flow

1. Planner synchronizes `main`, creates one fresh task branch and one task PR.
2. The PR contains the complete task contract and may include the candidate Task
   Index row that would represent the task while in flight. No scientific
   execution is authorized yet.
3. Maintainer independently reviews the exact task-contract state for feasibility,
   required inputs, current-`main` consistency, and material contract gaps.
4. When acceptable, Maintainer records:

   ```text
   SPEC APPROVED

   task: <task-id>
   approved_spec_commit: <full SHA containing the approved task contract>
   implementation_authorized: true
   ```

5. **Do not merge or open a second PR merely because the spec was approved.**
   Maintainer/Implementer continues implementation on the same task branch/PR.
6. Ordinary implementation commits do not invalidate the spec approval merely
   because the PR head advances. The approved contract remains anchored by
   `approved_spec_commit`.
7. A material change to task meaning after approval invalidates the old spec
   approval for affected work. Planner revises the contract on the same PR and
   Maintainer records a new exact-spec approval before affected execution
   continues.
8. Before final acceptance, Maintainer normally places factual terminal results,
   artifact identities, limitations, and the final lifecycle/result update on the
   same PR head.
9. Maintainer records final implementation/operational acceptance on the exact
   final PR head.
10. Planner records final scientific/architecture acceptance on that same exact
    final PR head.
11. Planner may then merge the task PR directly and update the research ledger /
    successor state. No extra Maintainer merge handoff is required.

### Candidate Task Index state inside an open PR

An open task PR may add or modify its candidate row in `docs/tasks/README.md`.
That unmerged row is not durable project truth. During implementation, execution
authority comes from the exact approved task contract and approval record, not
from pretending that the candidate row is already merged.

Before landing, the same PR should normally change the candidate row to the
accepted terminal lifecycle (`DONE`, `BLOCKED`, `CANCELLED`, or other published
terminal meaning). Therefore a serial task may legitimately move from an
unmerged candidate `READY` state directly to a merged terminal state.

### Optional two-phase publication

A separate specification-publication PR followed by a separate implementation PR
is allowed only when Planner explicitly chooses it because durable publication
before implementation has real value, for example a planned cross-session/team
handoff or implementation that will intentionally start later.

It is not the default merely to make the task visible to Maintainer. Maintainer
session recovery must inspect open PRs as described below.

### T085 migration note

T085 was already published as merged `READY` under the previous two-phase default
before this rule changed. Its current implementation remains valid. Do not reopen,
re-publish, restart, or rerun T085 solely because of this workflow change. After
T085, new tasks use the one-PR default unless Planner explicitly selects the
optional two-phase mode.

## Maintainer Start And Session Recovery

At the start of every Maintainer session, do not infer current work from
`docs/tasks/README.md` alone.

1. Bring the local integration line to current upstream `main` and complete the
   Main Synchronization Gate below.
2. Read merged `docs/tasks/README.md` for durable lifecycle state.
3. Query remote open PRs whose base is `main`.
4. Identify task PRs and inspect each relevant PR's body, base/head refs, exact
   head, commits, files, mergeability, task contract, and approval comments.
5. Under the serial workflow, there should normally be at most one approved active
   task PR. If more than one distinct scientific task PR has
   `implementation_authorized=true`, fail closed and ask Planner which one is
   authoritative rather than guessing.
6. If one approved active task PR exists, resume that PR even when its candidate
   lifecycle changes have not yet landed on `main`.
7. If no approved active task PR exists, merged `main` is sufficient to determine
   whether a previously published `READY` task exists or Planner must publish the
   next task.

In a WSL terminal use native `gh` when available, otherwise `gh.exe`; in
PowerShell use `gh` or `gh.exe`:

```bash
git status --short --branch
git fetch origin main
git merge --ff-only origin/main
git rev-parse --verify main
git rev-parse --verify origin/main
git rev-list --left-right --count main...origin/main
gh.exe pr list --state open --base main \
  --json number,title,headRefName,headRefOid,baseRefName,updatedAt,url,isDraft \
  --limit 100
gh.exe pr view <number> \
  --json number,title,body,headRefName,headRefOid,baseRefName,commits,files,mergeable,url
```

If native WSL `gh` exists, replace `gh.exe` in the example. A failed or
unauthenticated remote PR query is an operational blocker for session recovery;
it must not be silently replaced with stale local branch metadata.

## Review Findings

A finding is blocking only if both are true:

1. leaving it unresolved allows two reasonable contract-conforming
   implementations to produce different **material** results; and
2. the missing decision belongs to the current task contract rather than an
   inherited contract, Maintainer execution binding, or Implementer freedom.

Material differences include scientific inputs/cohorts, targets/training,
evaluation/terminal results, promotion decisions, information regime,
reproducibility-relevant identity/lineage, or a durable format actually consumed
by merged code/tasks.

Ordinary API/naming/test-harness/helper/logging/diagnostic/process choices are not
blockers unless a real material dependency exists.

- `IMPLEMENTATION_BUG`: frozen task meaning determines the answer; code is wrong.
- `CONTRACT_GAP`: the two blocker conditions above hold; affected work stops for
  Planner resolution.
- `ARCHITECTURE_ESCALATION`: repeated cross-cutting material gaps or complexity
  disproportionate to the task delta; stop patching and simplify/split/redesign.

Reviewers should make a full pass when practical. Later genuine blockers may still
be raised; repeated new material classes are a reason to simplify the abstraction,
not to keep appending rules.

## Final Acceptance And Landing

Final acceptance is distinct from spec approval.

- Spec approval authorizes implementation under a frozen scientific contract.
- Maintainer final acceptance certifies implementation/operational correctness.
- Planner final acceptance certifies scientific/architecture correctness.

Both final acceptances must refer to the same exact final PR head. Any material
change to that head after either final acceptance invalidates that acceptance for
the new head. A clearly non-semantic landing-only change may retain acceptance
only when both roles explicitly record that it is immaterial. Prefer putting
landing records on the PR before dual final acceptance so this exception is rare.

## Main Synchronization Gate

Before a new task branch or execution-readiness review begins, the responsible
role must ensure that the configured upstream remote's `main` ref (normally
`origin/main`) has been refreshed and that the local integration line is exactly
synchronized with it. The branch creator must not bypass this gate with a stale
local branch or an unverified moving remote ref.

```text
git fetch <remote> main
git rev-parse --verify main
git rev-parse --verify <remote>/main
git rev-list --left-right --count main...<remote>/main
```

Replace `<remote>` when the repository's configured upstream is not `origin`.
The two full commit SHAs must be identical and the ahead/behind count must be
`0 0` for new task-branch creation and initial execution readiness. A failed
fetch, missing remote ref, stale local `main`, or divergent state blocks new task
work until resolved.

For an already-active task PR, the implementation branch is expected to be ahead
of its base. Maintainer must still refresh and inspect current remote `main` at
session start so concurrent durable changes are visible; do not reset or overwrite
the active task branch merely to make it equal `main`.

Immediately before landing, fetch again, query remote PR state again, and compare
the task PR with current remote `main`. If `main` advanced materially, reconcile
and re-review as required rather than landing stale work.

## Artifacts And Runtime

Freeze runtime, seed, cohort, budget, shard/worker, and artifact identity details
only as needed for scientific equivalence, reproducibility, or a real downstream
consumer.

Required inputs must come from merged fixtures/contracts, reproducible commands,
or explicitly retained external artifacts with enough provenance/compatibility
information to prevent accidental misuse.

Large retained artifacts stay out of Git. Record only what is needed to reproduce
or safely reuse them: location, meaning/schema, identity when exact reuse matters,
producer/regeneration path, compatibility, retention reason/owner, real downstream
consumers, and deletion condition.

Reuse follows semantic impact: unaffected validated outputs may remain reusable;
affected outputs must be rerun. Architecture-rejected runtime artifacts are
non-authoritative unless a recovery contract establishes compatibility.

Long-running simulator work should use explicit parallelism/sharding where
appropriate and report configured/effective concurrency, seed/cohort ranges,
wall-clock cost, failures, and retained evidence according to the task contract.

## Architecture Recovery

If an implementation line has the wrong abstraction, Planner may declare
`ARCHITECTURE RECOVERY`, keep the failed PR as audit evidence, identify safe
reusable primitives/fixtures/utilities, and start one clean recovery branch/PR for
the same task ID from current `main`.

This is an exception to the normal one-active-task-PR rule and should explicitly
close or supersede the failed implementation line once the recovery PR becomes
authoritative.

## Project Truth

- `main` is durable landed project truth.
- Task lifecycle for landed work is authoritative in merged
  `docs/tasks/README.md`.
- Under the serial one-PR workflow, the unique approved open task PR is the
  temporary execution authority for the current in-flight task.
- That temporary authority exists only when Maintainer has recorded exact-spec
  `SPEC APPROVED` with `implementation_authorized=true`.
- PR/issue comments do not create a second durable task list; they carry the
  approval and evidence for the one active transaction.
- `docs/current_status.md` is the merged result record: Maintainer owns factual
  execution/evidence reporting, and Planner owns accepted scientific
  interpretation.
- Prefer inheritance/reference over duplicated normative text.

Before a task's final dual acceptance, Maintainer normally records the result,
evidence, limitations, retained material artifacts, and genuine gaps/escalations
on the same task PR. After dual acceptance on that same exact final head, Planner
may land the PR directly, update the research ledger, and decide successor work.

Each role normally keeps one model/reasoning configuration for a task. If a role
cannot execute within its boundary, narrow/split the work or escalate the material
semantic question rather than relying on repeated model switching or unlimited
review/patch loops.
