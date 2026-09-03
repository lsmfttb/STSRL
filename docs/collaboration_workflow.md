# Collaboration Workflow

This document defines the repository's task collaboration workflow.

> Freeze what can change scientific or durable project meaning. Leave equivalent
> implementation choices free.

The default threat model is **cooperative but fallible**. Protect against mistakes,
stale state, information leakage, incomplete experiments, and incorrect reuse.
Do not add hostile-producer/security machinery unless a task explicitly needs it.

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
- publication of new task contracts through a specification-only PR;
- final scientific/architecture acceptance;
- direct implementation-task landing after both final acceptances are recorded on
  the same exact head.

Planner does not normally own module names, function signatures, CLI spelling,
helper layout, logging, temporary files, or test harness design.

### Main Maintainer

Maintainer owns execution coordination and repository conformance:

- branch/worktree/lifecycle/merge hygiene;
- execution-readiness review and exact-head `SPEC APPROVED`;
- Implementer dispatch after an approved task is durably published as `READY` on
  merged `main`;
- verification, runtime evidence, and artifact retention;
- implementation review and finding classification;
- final implementation/operational acceptance;
- preparation of factual lifecycle/result landing records before final dual
  acceptance whenever practical.

Maintainer may choose ordinary execution bindings that do not change task meaning.
Maintainer does not invent scientific semantics, acceptance meaning, information
regime, promotion criteria, or successor science.

### Task Implementer

After an approved task is merged as `READY` on `main`, Implementer owns ordinary
implementation choices, including code/tests, module/function layout, minimal APIs,
CLI adapters, non-material serialization, logging, temporary files,
multiprocessing mechanics, and mechanical refactors.

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

## Task Publication And Implementation Branching

There is exactly one durable task-lifecycle list: merged
`docs/tasks/README.md` on `main`. Do not maintain a second issue/PR-only task list.
Open PR comments and issue comments may explain or review a proposed task, but they
never make an unmerged task executable.

A new task uses two distinct branch/PR phases.

### Phase A — task publication

1. Planner starts a fresh **specification-only** branch from synchronized `main`.
2. The branch contains the complete task contract plus the Task Index row that
   would make the task `READY` if merged. It contains no feature implementation,
   training output, or scientific execution produced under that task.
3. The publication PR may remain Draft while under review. Its proposed `READY`
   row is not authoritative while unmerged.
4. Maintainer reviews the exact publication head for current-`main` consistency,
   feasibility, required inputs, and material contract gaps, then records:

   ```text
   SPEC APPROVED

   task: <task-id>
   approved_spec_commit: <full publication-head SHA>
   publication_authorized: true
   ```

5. Planner may then merge that exact approved publication head. The task becomes
   executable only when merged `main` contains its `READY` row.

A publication PR that is not approved or not merged leaves `main` unchanged and
therefore leaves the task non-executable. `DRAFT` rows on merged `main` remain
longer-horizon planning records; they are not the normal mechanism for publishing
an immediately executable successor.

### Phase B — implementation

1. After the approved publication PR is merged, Maintainer synchronizes to the new
   `main` and creates or coordinates a fresh implementation branch/PR for that
   `READY` task.
2. Implementation must cite the merged task contract and the Maintainer's exact
   `SPEC APPROVED` publication evidence.
3. The implementation PR owns code, tests, execution evidence, retained-artifact
   reporting, and the eventual `READY -> DONE` (or other accepted terminal
   lifecycle) landing update.
4. A material contract change discovered during implementation requires a new
   Planner contract amendment/publication before affected scientific work
   continues. Do not silently edit the merged `READY` contract inside the
   implementation PR and continue under the old approval.

This split intentionally costs one small publication PR per new executable task.
It prevents the ambiguity where `main` says no task is `READY` while an unmerged PR
is treated as if it were authoritative.

### Maintainer start and remote-PR review gate

At the start of maintainer work, and before reviewing a task publication or
implementation PR, first bring the local integration line up to the current
upstream `main` and complete the Main Synchronization Gate below. If local
`main` is behind and its worktree is clean, advance it only with a fast-forward
to the fetched `origin/main`; if it is dirty or cannot be fast-forwarded, stop
and use a clean integration checkout rather than resetting or overwriting work.

After exact synchronization, query the remote open PRs whose base is `main`.
Inspect each relevant PR's body, base/head refs, exact head commit, commits,
files, and mergeability before deciding whether it is a specification proposal,
implementation candidate, or unrelated work. In a WSL terminal use the native
`gh` when available, otherwise `gh.exe`; in PowerShell use `gh` or `gh.exe`:

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
unauthenticated CLI query is an operational blocker for remote-PR review; it
must not be silently replaced with stale local branch metadata. An unmerged PR
may provide review input, but only merged `docs/tasks/README.md` changes the
task lifecycle or creates an executable `READY` task.

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

## Task Flow

1. **Planner Publication Contract** — Planner writes the delta contract and
   proposed `READY` Task Index row on a specification-only PR; no feature code.
2. **Execution Readiness Review** — Maintainer first completes the
   Maintainer start and remote-PR review gate below, including exact
   synchronization and remote PR inspection, then reviews the exact
   publication head.
3. **Spec Publication Approved** — Maintainer records exact-head `SPEC APPROVED /
   publication_authorized=true`.
4. **Publish READY** — Planner merges the approved publication PR. Only now does
   merged `main` make the task executable.
5. **Implementation And Evidence** — Maintainer synchronizes the new `main`,
   dispatches Implementer on a fresh implementation branch/PR, and coordinates
   verification/evidence.
6. **Landing Record Preparation** — before final acceptance, Maintainer normally
   places factual terminal results, artifact identities, limitations, and required
   task-lifecycle/result documentation on the implementation PR head. Avoid a
   routine post-merge documentation round trip.
7. **Dual Final Acceptance** — the same exact implementation head requires
   Maintainer implementation/operational acceptance and Planner
   scientific/architecture acceptance. The normal order is Maintainer first,
   Planner last.
8. **Implementation Landing** — once both final acceptances refer to the same exact
   implementation head, Planner may merge immediately and update the research
   ledger / successor state. No additional Maintainer handoff is required merely
   to perform the merge. Maintainer may still perform the merge when explicitly
   requested or when a repository constraint requires it.

A material Planner-contract change after publication requires renewed Planner
publication and Maintainer approval before affected implementation/science
continues. Clearly non-semantic wording/spelling fixes do not require a semantic
reset when Maintainer records them as immaterial.

Any material change to the implementation PR head after either final acceptance
invalidates that acceptance for the new head. A clearly non-semantic landing-only
change may retain acceptance only when both roles explicitly record that it is
immaterial. Prefer putting landing records on the implementation PR before dual
final acceptance so this exception is rare.

## Main Synchronization Gate

Before a task-publication branch, implementation branch, or execution-readiness
review begins, the responsible role must ensure that the configured upstream
remote's `main` ref (normally `origin/main`) has been refreshed and that the local
integration line is exactly synchronized with it. The branch creator must not
bypass this gate with a stale local branch or an unverified moving remote ref. The
check is:

```text
git fetch <remote> main
git rev-parse --verify main
git rev-parse --verify <remote>/main
git rev-list --left-right --count main...<remote>/main
```

Replace `<remote>` when the repository's configured upstream is not `origin`.
The two full commit SHAs must be identical and the ahead/behind count must be
`0 0` for publication/implementation branch creation and execution readiness. A
failed fetch, missing remote ref, stale local `main`, or any
ahead/behind/divergent state blocks branch creation, exact-head approval, and
integration work until it is resolved. Record the remote/ref, fetch result, check
time, and both full SHAs in execution-readiness or PR evidence.

Immediately before either publication landing or implementation landing, fetch
again, query the remote PR state again, and verify that the recorded pre-landing
base SHA still equals current remote `main`, then verify the pending landing
against current `main`. If `main` advanced materially, rebase/review as required
rather than landing a stale task contract or implementation.

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

## Architecture Recovery

If an implementation line has the wrong abstraction, Planner may declare
`ARCHITECTURE RECOVERY`, keep the failed PR as audit evidence, identify safe
reusable primitives/fixtures/utilities, and start one clean recovery branch/PR for
the same task ID from current `main`.

## Project Truth

- `main` is durable project truth.
- Task lifecycle is authoritative only in merged `docs/tasks/README.md`.
- An unmerged publication PR may propose a `READY` row but does not create an
  executable task.
- A merged `READY` row plus its approved merged task contract is the authorization
  boundary for a fresh implementation branch.
- `docs/current_status.md` is the merged result record: Maintainer owns factual
  execution/evidence reporting, and Planner owns accepted scientific
  interpretation.
- PR comments carry task-specific findings/acceptances but do not replace merged
  policy or merged task lifecycle.
- Prefer inheritance/reference over duplicated normative text.

Before an implementation task's final dual acceptance, Maintainer normally records
the result, evidence, limitations, retained material artifacts, and genuine
gaps/escalations on the implementation PR. After dual acceptance on that same
exact head, Planner may land the implementation directly, update the research
ledger, and decide successor work.

Each role normally keeps one model/reasoning configuration for a task. If a role
cannot execute within its boundary, narrow/split the work or escalate the material
semantic question rather than relying on repeated model switching or unlimited
review/patch loops.
