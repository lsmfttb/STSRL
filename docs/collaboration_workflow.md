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
- sends the proposed task content to the main maintainer for repository
  publication and lifecycle management;
- reviews maintainer result reports before proposing a successor task or
  revising the broader plan.

The planner is read-only with respect to the repository. It does not edit
files, create or modify branches or pull requests, change task lifecycle state,
or directly dispatch implementation work. A planner proposal is not executable
until the main maintainer has published it as a `READY` task.

### Main Maintainer

The main maintainer:

- maintains the `main` branch;
- maintains project documentation and task specifications;
- receives task proposals from the planner, checks them against current
  repository contracts, and publishes their task documents and lifecycle
  state;
- returns materially incomplete, inconsistent, or infeasible proposals to the
  planner for clarification instead of inventing a replacement task;
- dispatches and manages the task implementer as a sub-agent for each published
  `READY` task;
- selects the implementer's model and reasoning effort, balancing required
  capability against cost;
- reviews submitted pull requests against the published task document;
- requests revisions or merges approved pull requests;
- updates the task index and the maintainer result report after a merge so the
  planner can evaluate the result.

The main maintainer does not implement feature tasks directly and does not
proactively propose new tasks. It may identify blockers, missing evidence, or
questions in its result report, but the planner owns the next task proposal.
Maintainer-owned documentation, review, merge, branch/worktree management, and
other control-plane actions are not feature implementation.

### Task Implementer

The task implementer is a sub-agent of the main maintainer. The implementer:

- works on exactly one published task;
- works in one fresh isolated branch and worktree assigned or approved by the
  main maintainer;
- creates or updates one pull request for that task under maintainer direction;
- starts from the latest `main`;
- implements only the task's documented scope;
- reports verification results, known limitations, and deviations;
- opens a ready-for-review pull request only after the documented deliverables,
  required artifacts, and required verification have been completed;
- keeps incomplete work in draft status or explicitly labels it incomplete,
  with each missing acceptance criterion named in the pull-request body;
- responds to review findings on the same pull request.

The implementer does not choose its own model or reasoning effort and does not
merge its pull request. The main maintainer remains independent reviewer and
merge owner; it does not edit feature code on the implementer's branch.

## Source Of Truth

- `main` is the only integration line and the only source of implemented
  project truth.
- A branch or local artifact is not an implemented capability until its pull
  request is reviewed and merged into `main`.
- Every task's scope and acceptance contract are defined by one document under
  `docs/tasks/`.
- Task lifecycle state is authoritative only in the Active Backlog table in
  `docs/tasks/README.md`. Individual task documents must not carry mutable
  `Status:` fields. If another document disagrees with the table, the table
  wins and the disagreement is a documentation bug.
- Acceptance is based on the task document. Chat summaries are explanatory,
  not substitutes for the specification.
- A planner handoff becomes an executable contract only after the main
  maintainer records it in a task document and marks it `READY` in the task
  index. Planner chat or notes do not independently authorize a branch.
- If scope or acceptance criteria change, the main maintainer updates the task
  document before the changed work is accepted. A material planning change is
  returned to the planner rather than originated by the maintainer.
- Project policy decisions made during maintainer discussion become durable
  only when the main maintainer writes them into the authoritative documents.
  A spoken or chat-only reminder is not enough to change future review
  standards.

## One Task, One Branch, One Pull Request

- One task ID corresponds to one branch and one pull request.
- A branch must not combine several task IDs.
- A branch must not be reused after its pull request is merged or closed.
- Each task branch starts from the latest `main`, not from another task branch
  or an integration branch.
- Parallel tasks use separate worktrees or otherwise isolated working
  directories. Agents must never switch branches in a shared worktree.
- Dependencies are resolved by waiting for prerequisite tasks to merge and then
  rebasing or recreating the dependent branch from the updated `main`.

Suggested branch naming:

```text
task/T001-main-quality-baseline
task/T002-controlled-run-foundation
```

Branch naming is descriptive only. The task ID in the pull request is the
stable identity.

## Task States

- `DRAFT`: specification is incomplete; do not start.
- `BLOCKED`: specification is complete but prerequisites are not merged.
- `READY`: a new branch may be created from latest `main`.
- `IN_REVIEW`: a pull request exists and is under review.
- `DONE`: accepted pull request is merged into `main`.
- `CANCELLED`: task will not be implemented; the task document records why.

Only the main maintainer changes task state in the task index. New task content
and priority originate with the planner; the maintainer validates and
publishes that handoff. An empty `READY` queue is valid while the planner is
considering the maintainer's latest report.

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

## Pull-Request Contract

The pull-request description must include:

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
The pull request must contain only the focused task and remain independently
reviewable.

A ready-for-review pull request is an implementation-complete claim. If any
required deliverable, artifact, WSL gate, or acceptance criterion is still
missing, the PR must be draft or must say it is incomplete before maintainer
review starts. Incomplete ready PRs are reviewed as blocked, not partially
accepted; follow-up fixes stay on the same PR until the published task contract
is satisfied or the main maintainer revises the task document.

For any WSL stage that can reasonably use multiple workers, especially restored
evaluation and comparison stages, the PR must report the actual command shape,
worker count, shard count, record ranges, wall-clock time, and reason for any
single-worker execution. Reviewers treat missing worker evidence as a
verification gap even when the output artifact schema is otherwise valid.

## Review And Merge

The main maintainer reviews:

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
maintainer notes has not been delivered to the task implementer.

- After each initial review or re-review, the main maintainer publishes the
  incremental conclusion on the same pull request before reporting that the
  review is complete or waiting for another implementation update.
- The published message identifies the reviewed head commit, distinguishes
  blocking findings from non-blocking notes, states the required changes, and
  records the relevant verification result. A no-blocker conclusion is
  published explicitly rather than left implicit.
- Previously published feedback does not deliver findings discovered by a
  later re-review. New or remaining findings are posted as a new review or
  comment on the pull request.
- If publishing fails or the review was explicitly requested as read-only, the
  maintainer states that the result is undelivered and does not claim that the
  implementer has received it. The review remains pending until delivery is
  confirmed or the user explicitly keeps it private.

Review findings are resolved before merge. The maintainer merges only into
`main`, then:

1. verifies the resulting `main`;
2. marks the task `DONE` in the task index;
3. updates `current_status.md` as the planner-facing result report;
4. records dependency facts and blockers without originating a successor task;
5. updates architecture or roadmap documents when the accepted behavior changes
   them;
6. cleans obsolete local and remote task branches and review worktrees when
   they are no longer needed, while preserving active worktrees, unmerged
   branches, and explicitly retained historical references.

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

The planner reads that report and sends any next task proposal back to the main
maintainer. The main maintainer may request clarification or reject a proposal
that conflicts with repository contracts, but it does not substitute its own
new task. If no planner proposal has been accepted, no new task is published
and the executable queue remains empty.

## Documentation Ownership

Project-level documentation is maintained directly by the main maintainer.
Feature pull requests should report documentation impact but should not rewrite
authoritative project status, architecture, roadmap, collaboration, or task
documents unless the task explicitly requires it.

The planner supplies planning content but remains repository-read-only. The
main maintainer records accepted planning handoffs and execution results in the
authoritative documents.

Code docstrings, schema comments, and narrowly scoped operational notes may be
part of a feature task when required for correctness.

## Legacy Branch Disposition

`codex/docs-consolidation` was reviewed and merged into `main`; it is no longer
an active work line.

`codex/integration-current` at commit `d56e10e` is a read-only recovery
reference. It is neither ignored nor eligible for wholesale merge. Its useful
work is decomposed into the task backlog. The branch may be deleted only after
all mapped tasks are `DONE`, `CANCELLED`, or explicitly superseded.
