# Collaboration Workflow

This document defines how work is specified, implemented, reviewed, and merged.
It is the authority for branch and pull-request workflow.

## Roles

### Planner

The planner:

- reads the repository, task index, maintainer reports, accepted pull requests,
  and retained evidence needed to understand the current project state;
- decides what new task should be proposed, including its objective, priority,
  dependencies, scope, deliverables, acceptance criteria, verification, and
  artifact requirements;
- authors task proposals as documentation-only branches and pull requests against
  the latest `main`;
- responds to maintainer review findings on the same task-proposal pull request;
- reviews maintainer result reports before proposing a successor task or
  revising the broader plan.

The planner has write authority only for task-proposal control-plane work. A
planner-authored proposal may add or revise task documents, propose task-index
lifecycle changes, and update directly affected planning documentation. It must
not modify feature code, runtime configuration, source manifests, generated
artifacts, or implementation evidence.

The planner does not merge task-proposal pull requests, approve its own proposal,
create implementation branches, change executable project state directly,
dispatch implementers, or implement feature tasks. A planner proposal is not
executable until the main maintainer has independently reviewed and merged it and
the resulting `main` task-index row is `READY`.

### Main Maintainer

The main maintainer:

- maintains the `main` branch;
- maintains project documentation and task lifecycle state;
- independently reviews planner-authored task-proposal pull requests against the
  current repository contracts;
- requests revisions on materially incomplete, inconsistent, ambiguous, or
  infeasible proposals instead of inventing a replacement task;
- is the only role authorized to approve and merge a task-proposal pull request
  and thereby publish its lifecycle state;
- may author a task-publication pull request as a fallback when the planner cannot
  create one, while preserving the same reviewable proposal boundary;
- dispatches and manages the task implementer as a sub-agent for each published
  `READY` task;
- selects the implementer's model and reasoning effort, balancing required
  capability against cost;
- reviews submitted implementation pull requests against the published task
  document;
- requests revisions or merges approved implementation pull requests;
- updates the task index and the maintainer result report after an implementation
  merge so the planner can evaluate the result.

The main maintainer does not implement feature tasks directly and does not
proactively propose new tasks. It may identify blockers, missing evidence, or
questions in its result report, but the planner owns new task content and
priority. Maintainer-owned review, merge, branch/worktree management,
documentation publication, lifecycle authorization, and other control-plane
actions are not feature implementation.

### Task Implementer

The task implementer is a sub-agent of the main maintainer. The implementer:

- works on exactly one published task;
- works in one fresh isolated branch and worktree assigned or approved by the
  main maintainer;
- creates or updates one implementation pull request for that task under
  maintainer direction;
- starts from the latest `main` after the task-proposal pull request has merged;
- implements only the task's documented scope;
- reports verification results, known limitations, and deviations;
- opens a ready-for-review pull request only after the documented deliverables,
  required artifacts, and required verification have been completed;
- keeps incomplete work in draft status or explicitly labels it incomplete,
  with each missing acceptance criterion named in the pull-request body;
- responds to review findings on the same implementation pull request.

The implementer does not choose its own model or reasoning effort and does not
merge its pull request. The main maintainer remains independent reviewer and
merge owner; it does not edit feature code on the implementer's branch.

## Source Of Truth

- `main` is the only integration line and the only source of implemented or
  executable project truth.
- A branch or local artifact is not an implemented capability until its pull
  request is reviewed and merged into `main`.
- Every task's scope and acceptance contract are defined by one document under
  `docs/tasks/`.
- Task lifecycle state is authoritative only in the Active Backlog table in
  `docs/tasks/README.md`. Individual task documents must not carry mutable
  `Status:` fields. If another document disagrees with the table, the table wins
  and the disagreement is a documentation bug.
- Acceptance is based on the task document. Chat summaries, issues, and pull-
  request descriptions are explanatory or review surfaces, not substitutes for
  the merged specification.
- A planner-authored task-proposal pull request is a proposed contract, not an
  executable contract. It becomes executable only after the main maintainer
  merges it and the resulting row on `main` is `READY`.
- Planner chat, issue text, or notes do not independently authorize an
  implementation branch.
- If scope or acceptance criteria change, the change must first enter `main`
  through a reviewed task-proposal or maintainer control-plane pull request before
  changed implementation work can be accepted.
- Project policy decisions become durable only when the main maintainer merges
  them into the authoritative documents. A spoken or chat-only reminder is not
  enough to change future review standards.

## Task-Proposal Pull Requests

A task-proposal pull request is the normal handoff from planner to maintainer.
It is a control-plane publication request and is separate from the task's later
implementation pull request.

A task-proposal pull request:

- starts from the latest `main`;
- uses a branch such as `proposal/T071-short-description`;
- contains one proposed task or one coherent planning-policy revision;
- may add or revise files under `docs/tasks/`, propose lifecycle changes in
  `docs/tasks/README.md`, and update directly affected planning documentation;
- must not include feature code, simulator/runtime changes, source-manifest
  changes, generated experiment outputs, or implementation artifacts;
- records the current baseline, dependencies, inputs, outputs, scope,
  out-of-scope work, design constraints, deliverables, acceptance criteria,
  verification, sharding/worker topology where required, and pull-request report
  contract;
- remains open until the main maintainer independently accepts or rejects it.

The planner may push revisions requested by the maintainer, but it must not
approve or merge its own proposal. A proposed `READY`, `DRAFT`, `BLOCKED`,
`CANCELLED`, or priority change has no lifecycle effect while it exists only on
the proposal branch. The main maintainer authorizes that change by merging the
proposal into `main`.

Issues are optional discussion and dependency-tracking surfaces. They are useful
for unresolved design questions, cross-repository capability work, or collecting
information before a specification is complete. An issue does not replace a task
document or publish a task lifecycle state.

After a task proposal merges, the main maintainer creates or authorizes a fresh
implementation branch from the updated `main`. The proposal branch must never be
reused for implementation.

## One Implementation Task, One Branch, One Pull Request

- One published task ID corresponds to one implementation branch and one
  implementation pull request.
- A task-proposal pull request is a separate control-plane object and does not
  count as the implementation pull request.
- An implementation branch must not combine several task IDs.
- A branch must not be reused after its pull request is merged or closed.
- Each implementation branch starts from the latest `main`, not from a proposal
  branch, another task branch, or an integration branch.
- Parallel tasks use separate worktrees or otherwise isolated working
  directories. Agents must never switch branches in a shared worktree.
- Dependencies are resolved by waiting for prerequisite tasks to merge and then
  rebasing or recreating the dependent branch from the updated `main`.

Suggested branch naming:

```text
proposal/T071-task-description
task/T001-main-quality-baseline
task/T002-controlled-run-foundation
```

Branch naming is descriptive only. The task ID in the merged task document and
implementation pull request is the stable identity.

## Task States

- `DRAFT`: specification is incomplete; do not start.
- `BLOCKED`: specification is complete but prerequisites are not merged.
- `READY`: a new implementation branch may be created from latest `main`.
- `IN_REVIEW`: an implementation pull request exists and is under review.
- `DONE`: accepted implementation pull request is merged into `main`.
- `CANCELLED`: task will not be implemented; the task document records why.

New task content and priority originate with the planner. The planner may propose
lifecycle changes in a task-proposal pull request. Only the main maintainer
authorizes those changes by merging them into the task index on `main`. An empty
`READY` queue is valid while the planner is considering the maintainer's latest
report or while a task-proposal pull request is under review.

## Required Task Specification

Every task document must define:

1. objective and motivation;
2. current `main` baseline;
3. dependencies;
4. explicit required inputs, generated outputs, artifact contracts, and
   reproduction commands;
5. in-scope behavior and files or ownership boundaries;
6. explicitly out-of-scope work;
7. design constraints and compatibility requirements;
8. required deliverables;
9. acceptance criteria;
10. required verification commands and real-simulator gates;
11. required pull-request report.

A task that cannot be objectively accepted is not ready.

If a task requires large or long-running WSL `sts_lightspeed` source
generation, restored evaluation, fixed-cohort comparison, coverage, teacher
collection, or training-scale simulation, its specification must include an
explicit stage-by-stage sharding and parallel-worker plan. Source collection,
restore/coverage gates, report rebuilds, teacher collection, restored
evaluation, and comparison runs are separate stages for this purpose.
Single-worker execution may be specified only for small smoke tests, local
debugging, non-simulator artifact aggregation, or a documented resource or
tooling limit. A `smoke` label does not exempt a stage whose cohort size or
expected wall-clock cost is substantial. The default worker target for scale
evidence is the host logical CPU count, capped by shard count and documented
memory or simulator limits. On the current 16-logical-core maintainer machine,
large WSL stages should use 16 workers by default; using fewer workers requires
a reported resource or tooling reason. The PR report must include shard/worker
counts, seed/source-run or cohort-record ranges, and wall-clock cost for each
WSL stage so reviewers can distinguish scale evidence from a slow
single-worker run.

## Task Artifact Boundaries

Tasks may depend on merged contracts from prerequisite tasks, but not on
temporary local artifacts. A required task input must be one of:

- a committed fixture or current artifact schema;
- a command in the task or pull-request report that regenerates the artifact;
- an explicitly external or ignored artifact path with schema, provenance,
  compatibility requirements, and regeneration instructions.

A task must not use another task's one-off smoke output, uncommitted worktree
file, local checkpoint, or temporary report as an implicit input. If a later
task needs an artifact produced by an earlier task, the later task must name the
artifact contract and explain how reviewers can reproduce or provide a
compatible artifact. Missing required artifacts block acceptance unless the task
document marks the smoke as optional before review.

Generated large artifacts still stay out of the repository. The durable project
state is the schema, command surface, manifest/provenance, and review evidence,
not the local file that happened to be left behind after a smoke run.

If raw GB-scale artifacts are expected to be useful after merge, the producing
task must provide an explicit retention contract. That contract must name a
stable ignored/local path outside disposable review worktrees, list schema and
provenance, SHA-256 hashes and approximate sizes, regeneration commands,
compatibility requirements, retention owner/reason, downstream tasks that may
consume it, and deletion conditions. Raw retained artifacts are still not
authoritative project state; later tasks may consume them only through the
documented contract or by regenerating compatible artifacts.

## Task-Proposal Pull-Request Contract

The task-proposal pull-request description must include:

- the proposed task ID or policy area;
- concise planning summary and motivation;
- current `main` baseline used to author the proposal;
- lifecycle rows proposed for addition or change;
- dependencies and external capability status;
- confirmation that the diff is documentation/control-plane only;
- unresolved questions or acceptance risks, if any;
- explicit statement that the planner will not merge the proposal or dispatch
  implementation work.

## Implementation Pull-Request Contract

The implementation pull-request description must include:

- task ID and link to its task document;
- concise implementation summary;
- changed behavior and compatibility impact;
- required input artifacts, generated output artifacts, and reproduction
  commands or external/ignored artifact locations;
- for any retained GB-scale local artifacts, the retention contract or a clear
  statement that only reports/manifests should be kept;
- exact verification commands and results;
- any acceptance criterion not satisfied;
- known risks or follow-up work;
- whether the implementation consulted legacy reference commit `d56e10e`.

Using legacy code is allowed, but wholesale cherry-picking of `d56e10e` is not.
The implementation pull request must contain only the focused task and remain
independently reviewable.

A ready-for-review implementation pull request is an implementation-complete
claim. If any required deliverable, artifact, WSL gate, or acceptance criterion
is still missing, the PR must be draft or must say it is incomplete before
maintainer review starts. Incomplete ready PRs are reviewed as blocked, not
partially accepted; follow-up fixes stay on the same PR until the published task
contract is satisfied or the main maintainer revises the task document through a
separate control-plane change.

For any WSL stage that can reasonably use multiple workers, especially restored
evaluation and comparison stages, the implementation PR must report the actual
command shape, worker count, shard count, record ranges, wall-clock time, and
reason for any single-worker execution. Reviewers treat missing worker evidence
as a verification gap even when the output artifact schema is otherwise valid.

## Review And Merge

For task-proposal pull requests, the main maintainer reviews:

- whether the proposal reflects the latest `main` and accepted evidence;
- whether dependencies, scope, deliverables, verification, artifacts, and
  decision boundaries are complete and objectively reviewable;
- whether proposed lifecycle changes are internally consistent;
- whether the diff remains documentation/control-plane only;
- whether any proposed `READY` task can be dispatched without inventing missing
  requirements.

For implementation pull requests, the main maintainer reviews:

- conformance to the task specification;
- correctness and behavioral regressions;
- architectural boundaries and information leakage;
- provenance and artifact compatibility where relevant;
- tests and real WSL gates required by the task;
- unnecessary scope, duplication, or hidden defaults;
- documentation impact.

### Review Finding Delivery

The pull request is the authoritative delivery channel for maintainer review
findings and conclusions. A finding written only in chat, a local report, or
maintainer notes has not been delivered to the planner or task implementer.

- After each initial review or re-review, the main maintainer publishes the
  incremental conclusion on the same pull request before reporting that the
  review is complete or waiting for another update.
- The published message identifies the reviewed head commit, distinguishes
  blocking findings from non-blocking notes, states the required changes, and
  records the relevant verification result. A no-blocker conclusion is
  published explicitly rather than left implicit.
- Previously published feedback does not deliver findings discovered by a later
  re-review. New or remaining findings are posted as a new review or comment on
  the pull request.
- If publishing fails or the review was explicitly requested as read-only, the
  maintainer states that the result is undelivered and does not claim that the
  author has received it. The review remains pending until delivery is confirmed
  or the user explicitly keeps it private.

Review findings are resolved before merge. The maintainer merges only into
`main`.

After a task-proposal merge, the maintainer:

1. verifies the resulting `main` documentation and task-index state;
2. confirms that only merged `READY` rows are executable;
3. dispatches an implementer only through a fresh branch from the updated
   `main`;
4. cleans the obsolete proposal branch and proposal worktree when no longer
   needed.

After an implementation merge, the maintainer:

1. verifies the resulting `main`;
2. marks the task `DONE` in the task index;
3. updates `current_status.md` as the planner-facing result report;
4. records dependency facts and blockers without originating a successor task;
5. updates architecture or roadmap documents when the accepted behavior changes
   them;
6. cleans obsolete local and remote task branches and review worktrees when they
   are no longer needed, while preserving active worktrees, unmerged branches,
   and explicitly retained historical references.

## Planner Handoff And Maintainer Reporting

`docs/current_status.md` is the canonical maintainer report for the planner.
`docs/tasks/README.md` remains the lifecycle authority. After every accepted,
cancelled, or blocked execution result, the main maintainer keeps those
documents synchronized and reports:

- the exact task, pull request, implementation commit, and merge commit where
  applicable;
- observed behavior and decision outcomes without converting them into an
  unrequested successor task;
- verification and simulator gates;
- retained artifact identities, provenance, and deletion conditions;
- limitations, failed gates, unresolved questions, and dependency changes.

The planner reads that report and authors any next task as a task-proposal pull
request. The main maintainer may request clarification or reject a proposal that
conflicts with repository contracts, but it does not substitute its own new task.
If no planner proposal has been merged, no new task is published and the
executable queue remains unchanged or empty.

## Documentation Ownership

Project-level documentation becomes authoritative through main-maintainer review
and merge. The planner may author planning and task-specification changes only in
task-proposal pull requests. The main maintainer owns publication, lifecycle
state, execution-result reporting, and synchronization of authoritative
documents.

Feature pull requests should report documentation impact but should not rewrite
authoritative project status, architecture, roadmap, collaboration, or task
documents unless the published task explicitly requires it.

Code docstrings, schema comments, and narrowly scoped operational notes may be
part of a feature task when required for correctness.

## Legacy Branch Disposition

`codex/docs-consolidation` was reviewed and merged into `main`; it is no longer
an active work line.

`codex/integration-current` at commit `d56e10e` is a read-only recovery
reference. It is neither ignored nor eligible for wholesale merge. Its useful
work is decomposed into the task backlog. The branch may be deleted only after
all mapped tasks are `DONE`, `CANCELLED`, or explicitly superseded.
