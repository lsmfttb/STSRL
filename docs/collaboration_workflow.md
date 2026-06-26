# Collaboration Workflow

This document defines how work is specified, implemented, reviewed, and merged.
It is the authority for branch and pull-request workflow.

## Roles

### Main Maintainer

The main maintainer:

- maintains the `main` branch;
- maintains project documentation and task specifications;
- decides task boundaries, dependencies, and readiness;
- reviews submitted pull requests against the published task document;
- requests revisions or merges approved pull requests;
- updates current status and follow-up tasks after a merge.

The main maintainer does not implement feature tasks, invoke sub-agents to
implement them, or manage task branches.

### Task Implementer

A task implementer:

- works on exactly one published task;
- creates one fresh branch and pull request for that task;
- starts from the latest `main`;
- implements only the task's documented scope;
- reports verification results, known limitations, and deviations;
- responds to review findings on the same pull request.

The user creates task branches and pull requests. The main maintainer does not
create or switch to those branches during implementation.

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
- If scope or acceptance criteria change, the main maintainer updates the task
  document before the changed work is accepted.
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

Only the main maintainer changes task state in the task index.

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

## Pull-Request Contract

The pull-request description must include:

- task ID and link to its task document;
- concise implementation summary;
- changed behavior and compatibility impact;
- required input artifacts, generated output artifacts, and reproduction
  commands or external/ignored artifact locations;
- exact verification commands and results;
- any acceptance criterion not satisfied;
- known risks or follow-up work;
- whether the implementation consulted legacy reference commit `d56e10e`.

Using legacy code is allowed, but wholesale cherry-picking of `d56e10e` is not.
The pull request must contain only the focused task and remain independently
reviewable.

## Review And Merge

The main maintainer reviews:

- conformance to the task specification;
- correctness and behavioral regressions;
- architectural boundaries and information leakage;
- provenance and artifact compatibility where relevant;
- tests and real WSL gates required by the task;
- unnecessary scope, duplication, or hidden defaults;
- documentation impact.

Review findings are resolved before merge. The maintainer merges only into
`main`, then:

1. verifies the resulting `main`;
2. marks the task `DONE` in the task index;
3. updates `current_status.md`;
4. unblocks or revises dependent tasks;
5. updates architecture or roadmap documents when the accepted behavior changes
   them.

## Documentation Ownership

Project-level documentation is maintained directly by the main maintainer.
Feature pull requests should report documentation impact but should not rewrite
authoritative project status, architecture, roadmap, collaboration, or task
documents unless the task explicitly requires it.

Code docstrings, schema comments, and narrowly scoped operational notes may be
part of a feature task when required for correctness.

## Legacy Branch Disposition

`codex/docs-consolidation` was reviewed and merged into `main`; it is no longer
an active work line.

`codex/integration-current` at commit `d56e10e` is a read-only recovery
reference. It is neither ignored nor eligible for wholesale merge. Its useful
work is decomposed into the task backlog. The branch may be deleted only after
all mapped tasks are `DONE`, `CANCELLED`, or explicitly superseded.
