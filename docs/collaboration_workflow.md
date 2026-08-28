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
- creates one fresh task branch and one draft pull request from the latest
  `main`;
- writes the complete task specification and proposed lifecycle changes in that
  pull request before implementation starts;
- responds to maintainer specification-review findings on the same pull request;
- reviews maintainer result reports before proposing a successor task or
  revising the broader plan.

The planner has write authority only for the specification phase of a task pull
request. Before specification approval, the planner may add or revise the task
document, propose task-index lifecycle changes, and update directly affected
planning documentation. It must not add feature code, runtime configuration,
source-manifest changes, generated artifacts, or implementation evidence.

The planner does not approve its own specification, dispatch implementers,
implement feature work, or merge the pull request. After implementation is
authorized, the planner may change the frozen task specification only in
response to an explicit maintainer request; any material change requires a new
specification approval.

### Main Maintainer

The main maintainer:

- maintains the `main` branch, project documentation, and lifecycle state;
- independently reviews the specification phase of each planner-authored task
  pull request against current repository contracts and accepted evidence;
- requests revisions on materially incomplete, inconsistent, ambiguous, or
  infeasible specifications instead of inventing a replacement task;
- is the only role authorized to approve a task specification for
  implementation;
- records the exact approved specification commit on the pull request;
- dispatches and manages the task implementer on the same branch and pull
  request after specification approval;
- freezes the task's acceptance boundary before production implementation,
  including its invariant matrix, implementation-independent fixtures/oracles,
  required normal and realistic failure cases, and explicit out-of-scope cases;
- selects the implementer's model and reasoning effort with cost-effectiveness
  as the default: prefer the least expensive current option that is still
  reasonably expected to complete the task correctly and safely, including a
  high-value model such as Luna when it is available and sufficiently capable;
- escalates to a more capable or expensive model only when task complexity,
  specialized requirements, review risk, or observed implementation failures
  justify the added cost;
- suspends implementation authorization and requires reapproval when the frozen
  specification changes materially;
- independently reviews the final implementation against the approved
  specification;
- requests revisions or merges the accepted pull request;
- updates the task index and maintainer result report after merge so the planner
  can evaluate the result.

The main maintainer does not implement feature tasks directly and does not
proactively propose new tasks. It may identify blockers, missing evidence, or
questions in its result report, but the planner owns new task content and
priority. Maintainer-owned review, authorization, merge, branch/worktree
management, lifecycle management, and result reporting are control-plane work,
not feature implementation.

Model selection optimizes expected total implementation cost, not token price
alone. The maintainer accounts for likely retries, review load, expensive
downstream reruns, and the cost of an incorrect implementation. It reassesses
current model availability, capability, and price at dispatch time instead of
assuming that the strongest model is the default. Reasoning effort is set to the
lowest level consistent with the task's complexity and risk, then raised when
evidence shows that more depth is needed.

### Task Implementer

The task implementer is a sub-agent of the main maintainer. The implementer:

- works on exactly one maintainer-approved task specification;
- works on the existing task branch and pull request created by the planner;
- starts only after the main maintainer has published a valid specification
  approval for an exact commit;
- does not create a second implementation branch or pull request;
- implements only the approved task scope;
- preserves the frozen specification unless the maintainer explicitly requests
  a specification revision and reapproves it;
- reports verification results, known limitations, and deviations on the same
  pull request;
- keeps the pull request in draft or explicitly incomplete status until all
  documented deliverables, artifacts, and verification are complete;
- responds to review findings on the same pull request.

The implementer does not choose its own model or reasoning effort and does not
merge the pull request. The main maintainer is the required independent
acceptance reviewer and merge owner; "independent" means independent from the
implementer, not a requirement for a second review agent. A separate review
agent is not part of the default workflow and may be used only when the task
specification or the user explicitly requests it. If used, it is advisory, may
not introduce new acceptance requirements, and may not block the maintainer's
review or merge decision. The maintainer does not edit feature code on the task
branch.

## Source Of Truth And Execution Authorization

- `main` is the only integration line and the only durable source of implemented
  project truth.
- A branch or local artifact is not an implemented capability until its pull
  request is reviewed and merged into `main`.
- Every task's scope and acceptance contract are defined by one document under
  `docs/tasks/`.
- Task lifecycle state is authoritative only in the Active Backlog table in
  `docs/tasks/README.md` after the relevant change is merged into `main`.
  Individual task documents must not carry mutable `Status:` fields.
- A proposed task-index row on an open task branch has no merged lifecycle effect.
- A main-maintainer specification approval is a narrow authorization to implement
  that exact specification on that exact branch and pull request. It does not
  publish the task as implemented project truth and does not authorize another
  branch.
- Chat summaries, issues, pull-request descriptions, and planner notes do not
  independently authorize implementation.
- Project policy decisions become durable only when merged into `main`.

The executable work set may therefore contain:

1. tasks already published as `READY` on `main`; and
2. open single-task pull requests carrying a valid maintainer specification
   approval for their current frozen contract.

Tasks already published as `READY` before adoption of this workflow may continue
through an implementation-only pull request. New planner-authored tasks use the
single-branch, single-pull-request workflow below.

## One Task, One Branch, One Pull Request

One new task uses one branch and one pull request from specification proposal
through final implementation merge.

- One task ID corresponds to one task branch and one pull request.
- The branch starts from the latest `main` and uses a name such as
  `task/T071-short-description`.
- The pull request is opened as draft during specification authoring.
- Before specification approval, the diff is documentation/control-plane only.
- After specification approval, the maintainer dispatches the implementer to the
  same branch and pull request.
- The implementer appends code, tests, verification, reports, and required
  task-specific documentation to that same pull request.
- The branch must not combine several task IDs.
- The branch must not be reused after the pull request is merged or closed.
- Parallel tasks use separate worktrees or otherwise isolated working
  directories. Agents must never switch branches in a shared worktree.
- Dependencies are resolved before specification approval or by synchronizing
  the branch with updated `main` and revalidating the specification.

Suggested branch naming:

```text
task/T071-task-description
task/T072-controlled-run-foundation
```

Branch naming is descriptive only. The task ID in the task document and pull
request is the stable identity.

## Pull-Request Phases

Pull-request phases are review workflow states. They are not substitutes for
merged task-index lifecycle state.

### 1. Specification

The planner authors the task contract. The pull request remains draft and must
not contain implementation work.

### 2. Implementation Authorized

The main maintainer approves an exact specification commit and dispatches the
implementer. The pull request normally remains draft while implementation is in
progress.

### 3. Final Review

The implementer has completed the documented deliverables and verification. The
pull request is marked ready for review and the maintainer performs final
acceptance review against the approved specification.

### 4. Merged Or Closed

An accepted implementation is merged into `main`. An abandoned, superseded, or
infeasible task is closed or converted into an explicit documentation-only
cancellation decision.

## Specification Approval Gate

No implementation work may begin until the main maintainer publishes an explicit
approval on the task pull request in this form:

```text
SPEC APPROVED

task: T071
approved_spec_commit: <full commit SHA>
implementation_authorized: true
```

The approval must identify the exact pull-request head commit reviewed. It
applies only to the named task, branch, and pull request.

Before approval, the maintainer verifies:

- the branch was created from a sufficiently current `main`;
- dependencies and external capabilities are merged, reproducible, or explicitly
  blocked;
- objective, scope, out-of-scope work, inputs, outputs, deliverables, acceptance
  criteria, verification, artifact contracts, and decision boundaries are
  complete and objectively reviewable;
- substantial WSL stages include explicit sharding, worker counts, ranges, and
  expected evidence;
- the specification-phase diff is documentation/control-plane only;
- implementation can be dispatched without the maintainer or implementer
  inventing missing requirements.

The maintainer may publish `SPEC REJECTED` or `SPEC CHANGES REQUIRED` instead of
approval. Implementation remains unauthorized until a later valid approval.

## Frozen Specification And Reapproval

The approved task document at `approved_spec_commit` is the implementation
contract. The following are material specification fields:

- objective and priority;
- dependencies and required input identities;
- in-scope and out-of-scope behavior;
- information-regime and compatibility constraints;
- required outputs and artifact contracts;
- deliverables and acceptance criteria;
- verification commands and real-simulator gates;
- sharding, worker topology, cohort, seed, or budget definitions;
- promotion, rejection, and successor decision boundaries.

Changing any material field after approval suspends implementation authorization.
The maintainer must publish a new approval containing the new exact commit before
implementation continues or the changed work can be accepted.

Spelling, formatting, broken-link repair, and other changes that do not alter the
contract may be treated as non-material. The maintainer records that conclusion
on the pull request when it is not self-evident.

Before dispatch, the maintainer synchronizes the branch with newer `main` when
intervening merges affect dependencies or acceptance assumptions. If a material
`main` change occurs after approval, the maintainer pauses the task, updates or
rebases the branch as appropriate, and reapproves the resulting specification
before work continues.

## Acceptance-First Implementation Gate

Specification approval freezes more than the task objective. For every task,
the approved specification must define the acceptance boundary: the invariants,
observable outputs, expected state transitions, required verification, and the
cases that are explicitly out of scope. The expected outcomes must be stated
independently of the implementation; a production helper under test must not
be used as the oracle for its own acceptance test.

For tasks with coupled state transitions, artifact/retention contracts,
parallel-worker evidence, or numerical/statistical acceptance, the maintainer
must freeze an executable acceptance matrix before production implementation
starts. The matrix may be a test-only commit on the task pull request or
fixtures/tests supplied with the approved task contract. It must cover:

- the normal success path and every documented terminal decision;
- realistic incomplete, stale, mismatched, truncated, and partial-failure
  cases named by the task contract;
- exact counts, identities, ranges, provenance, and state-transition rules that
  cannot be inferred from a successful fixture alone; and
- explicit out-of-scope behavior so the tests do not silently become a new
  security or product requirement.

The implementer first runs or lands the test-only acceptance boundary and
records its baseline result, then implements production behavior against that
boundary. The implementer may add focused regression tests, but may not weaken,
remove, or redefine the frozen acceptance tests. A material change to the test
oracle, fixture meaning, required failure case, or out-of-scope boundary
requires maintainer reapproval of the exact new head before implementation
continues.

This gate protects reproducibility, artifact compatibility, experiment fidelity,
and realistic failure semantics. It is not an adversarial-input or trusted-
producer attestation framework. Do not add proof chains, dependency graphs,
signatures, generic anti-tampering checks, or other security-style machinery
solely to prove that a trusted repository producer was not malicious. Hashes,
identities, and fail-closed checks remain appropriate only where the approved
task uses them to detect stale data, ordinary mismatch, incomplete execution,
information-regime violations, or other stated scientific/design errors.

Final review must compare the approved specification commit with the final head
and identify every task-document change made after approval. Undisclosed material
specification drift blocks merge.

## Task States

Merged task-index states remain:

- `DRAFT`: specification is incomplete; do not start;
- `BLOCKED`: specification is complete but prerequisites are not satisfied;
- `READY`: a merged task is authorized for a new implementation-only branch;
- `IN_REVIEW`: an implementation pull request exists and is under review;
- `DONE`: accepted implementation is merged into `main`;
- `CANCELLED`: the task will not be implemented and the task document records why.

For a new single-PR task, proposed lifecycle rows on the branch are review
content only until merge. The maintainer's `SPEC APPROVED` record authorizes
implementation on the same PR without requiring an intermediate specification
merge. Before final merge, the task-index change in the pull request must reflect
the accepted terminal state, normally `DONE`.

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

A task that cannot be objectively accepted is not ready for specification
approval.

If a task requires large or long-running WSL `sts_lightspeed` source generation,
restored evaluation, fixed-cohort comparison, coverage, teacher collection, or
training-scale simulation, its specification must include an explicit
stage-by-stage sharding and parallel-worker plan. Source collection,
restore/coverage gates, report rebuilds, teacher collection, restored evaluation,
and comparison runs are separate stages for this purpose.

Single-worker execution may be specified only for small smoke tests, local
debugging, non-simulator artifact aggregation, or a documented resource or
tooling limit. A `smoke` label does not exempt a substantial stage. The default
worker target for scale evidence is the host logical CPU count, capped by shard
count and documented memory or simulator limits. On the current 16-logical-core
maintainer machine, large WSL stages should use 16 workers by default; using fewer
workers requires a reported resource or tooling reason. The final PR report must
include shard and worker counts, seed/source-run or cohort-record ranges, and
wall-clock cost for each WSL stage.

## Incremental Reuse And Long-Running Execution

Expensive workflows should preserve validated work whenever a reviewed change does
not affect its semantics. A producer Git commit remains useful provenance, while
reuse is decided from the artifact's relevant inputs, configuration, completion
state, and the reviewed impact boundary of the change. After a repair, identify
the earliest affected stage or independent run; validated outputs before that
boundary remain reusable with their original provenance. Independent completed
shards or runs may likewise be reused when their own inputs and contract still
validate.

Long-running work should be prepared with cheap preflight checks and launched so
it can continue without an interactive agent remaining active. Record a coarse
expected duration when one is available, together with the process/status and log
locations needed to inspect progress. After a healthy launch, the maintainer or
implementer reports that information once and returns to other work; another
status check is appropriate after the expected window, on an explicit request, or
when a completion/failure signal is available. Operational status files are
short-lived execution state rather than scientific artifacts.

Per-run numerical settings and orchestration parallelism are separate concerns.
A task may freeze numerical settings for reproducibility while still running
independent shards, seeds, or arms concurrently when resources permit.

## Task Artifact Boundaries

Tasks may depend on merged contracts from prerequisite tasks, but not on temporary
local artifacts. A required task input must be one of:

- a committed fixture or current artifact schema;
- a command in the task or pull-request report that regenerates the artifact;
- an explicitly external or ignored artifact path with schema, provenance,
  compatibility requirements, and regeneration instructions.

A task must not use another task's one-off smoke output, uncommitted worktree
file, local checkpoint, or temporary report as an implicit input. If a later task
needs an artifact produced by an earlier task, the later task must name the
artifact contract and explain how reviewers can reproduce or provide a compatible
artifact. Missing required artifacts block acceptance unless the task document
marks them optional before specification approval.

Generated large artifacts stay out of the repository. Durable project state is
the schema, command surface, manifest/provenance, and review evidence, not the
local file left after a run.

If raw GB-scale artifacts are expected to be useful after merge, the task must
provide an explicit retention contract. That contract must name a stable
ignored/local path outside disposable review worktrees, list schema and
provenance, SHA-256 hashes and approximate sizes, regeneration commands,
compatibility requirements, retention owner and reason, downstream tasks that
may consume it, and deletion conditions. Raw retained artifacts are not
authoritative project state; later tasks may consume them only through the
documented contract or by regenerating compatible artifacts.

## Single Task Pull-Request Contract

During the specification phase, the pull-request description must include:

- task ID and link to the proposed task document;
- concise planning summary and motivation;
- current `main` baseline used to create the branch;
- proposed lifecycle rows;
- dependencies and external capability status;
- confirmation that the current diff is specification/control-plane only;
- unresolved questions or acceptance risks;
- explicit statement that the planner will not approve, implement, dispatch, or
  merge the task.

After specification approval, the pull-request description must additionally
record:

- `approved_spec_commit`;
- implementation phase and current head commit;
- concise implementation summary;
- changed behavior and compatibility impact;
- required input artifacts, generated output artifacts, and reproduction
  commands or external/ignored artifact locations;
- any retained GB-scale artifact contract, or a clear statement that only
  reports and manifests should be kept;
- exact verification commands and results;
- shard, worker, range, and wall-clock evidence for substantial WSL stages;
- any acceptance criterion not satisfied;
- known risks or follow-up work;
- whether the implementation consulted legacy reference commit `d56e10e`.

Using legacy code is allowed, but wholesale cherry-picking of `d56e10e` is not.
The final pull request must contain only the focused task and remain independently
reviewable.

A ready-for-review pull request is an implementation-complete claim. If any
required deliverable, artifact, WSL gate, or acceptance criterion is still
missing, the PR remains draft or explicitly says it is incomplete. Incomplete
ready PRs are reviewed as blocked, not partially accepted; fixes remain on the
same PR until the approved task contract is satisfied or the specification is
formally revised and reapproved.

## Review And Merge

### Specification Review

The main maintainer reviews:

- consistency with the latest relevant `main` and accepted evidence;
- completeness and objective acceptability of the task contract;
- dependency, artifact, worker, and information-regime boundaries;
- internal consistency of proposed lifecycle changes;
- absence of implementation work before approval.

Specification findings are delivered on the task pull request. When all blockers
are resolved, the maintainer publishes `SPEC APPROVED` with the exact commit and
then dispatches the implementer on the same PR.

### Final Implementation Review

The main maintainer reviews:

- conformance to the currently approved specification commit;
- every task-document change made after specification approval;
- correctness and behavioral regressions;
- architectural boundaries and information leakage;
- provenance and artifact compatibility;
- tests and real WSL gates required by the task;
- worker and shard evidence for substantial stages;
- unnecessary scope, duplication, or hidden defaults;
- documentation and lifecycle impact.

This maintainer review is the required acceptance review. No separate review
Agent, second model, or independent sub-agent is required. If an explicitly
requested advisory reviewer is used, its report is additional input only; the
maintainer still owns the exact-head decision, and the advisory review must not
delay acceptance or expand the approved contract.

### Review Finding Delivery

The pull request is the authoritative delivery channel for maintainer review
findings and conclusions. A finding written only in chat, a local report, or
maintainer notes has not been delivered to the planner or implementer.

- After each specification review, implementation review, or re-review, the
  maintainer publishes the incremental conclusion on the same pull request.
- The published message identifies the reviewed head commit, distinguishes
  blocking findings from non-blocking notes, states required changes, and records
  relevant verification results.
- A no-blocker conclusion is published explicitly rather than left implicit.
- Previously published feedback does not deliver findings discovered by a later
  re-review. New or remaining findings require a new review or comment.
- If publishing fails or review was explicitly requested as read-only, the
  maintainer states that the result is undelivered and does not claim the author
  received it.

Review findings are resolved before merge. Only the main maintainer merges into
`main`.

Before merge, the maintainer confirms:

1. the final head is based on a valid current `approved_spec_commit`;
2. every material post-approval specification change was reapproved;
3. all required deliverables, artifacts, and verification passed;
4. the final task-index row reflects the accepted terminal state;
5. the pull request contains no unrelated task or control-plane work.

After merge, the maintainer:

1. verifies the resulting `main`;
2. confirms or records the task as `DONE`, `CANCELLED`, or otherwise accurately
   terminal in the task index;
3. updates `current_status.md` as the planner-facing result report, including the
   exact implementation and merge commits;
4. records dependency facts and blockers without originating a successor task;
5. updates architecture or roadmap documents when accepted behavior changes
   them;
6. cleans obsolete local and remote task branches and review worktrees while
   preserving active worktrees, unmerged branches, and explicitly retained
   historical references.

A small maintainer-owned post-merge status/report correction is control-plane
maintenance and does not constitute a second task implementation pull request.

## Planner Handoff And Maintainer Reporting

`docs/current_status.md` is the canonical maintainer report for the planner.
`docs/tasks/README.md` remains the merged lifecycle authority. After every
accepted, cancelled, or blocked execution result, the maintainer keeps those
documents synchronized and reports:

- the exact task, pull request, approved specification commit, implementation
  commit, and merge commit where applicable;
- observed behavior and decision outcomes without converting them into an
  unrequested successor task;
- verification and simulator gates;
- retained artifact identities, provenance, and deletion conditions;
- limitations, failed gates, unresolved questions, and dependency changes.

The planner reads that report and opens any next task as a new single-task pull
request. The maintainer may request clarification or reject a proposal that
conflicts with repository contracts, but it does not substitute its own new task.
If no specification is approved and no merged `READY` task exists, no new
implementation is authorized.

## Documentation Ownership

Project-level documentation becomes authoritative through main-maintainer review
and merge. The planner may author planning and task-specification changes during
the specification phase of a task pull request. The implementer may update
required task-specific documentation and evidence after approval, but must not
rewrite unrelated authoritative project status, architecture, roadmap,
collaboration, or task documents unless the approved specification requires it.

The maintainer owns specification approval, lifecycle authorization, final
publication, execution-result reporting, and synchronization of authoritative
documents.

Code docstrings, schema comments, and narrowly scoped operational notes may be
part of a feature task when required for correctness.

## Issues

Issues are optional discussion and dependency-tracking surfaces. They are useful
for unresolved design questions, cross-repository capability work, long-lived
blockers, or collecting information before a task specification is complete. An
issue does not replace a task document, specification approval, or final task
pull request.

## Legacy Branch Disposition

`codex/docs-consolidation` was reviewed and merged into `main`; it is no longer
an active work line.

`codex/integration-current` at commit `d56e10e` is a read-only recovery reference.
It is neither ignored nor eligible for wholesale merge. Its useful work is
decomposed into the task backlog. The branch may be deleted only after all mapped
tasks are `DONE`, `CANCELLED`, or explicitly superseded.
