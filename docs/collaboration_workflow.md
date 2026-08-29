# Collaboration Workflow

This document defines how work is designed, specified, implemented, reviewed,
and merged. It is the authority for repository task collaboration, branch and
pull-request workflow, acceptance ownership, and escalation.

The workflow is intentionally capability-shaped. High-level scientific,
architectural, and acceptance reasoning is concentrated in the Planner. The
Main Maintainer and Task Implementer operate inside that frozen contract and
should not be required to rediscover or invent its semantics during
implementation review.

## Core Principles

1. **Design before execution.** The Planner owns the scientific question,
   architecture, canonical domain model, acceptance semantics, and decision
   boundaries before implementation starts.
2. **Acceptance before production code.** Expected outcomes and failure classes
   are defined independently of the implementation. Production behavior does
   not become its own oracle.
3. **Execution roles conform; they do not redesign.** The Maintainer coordinates,
   verifies, and reviews conformance. The Implementer writes bounded code. A
   missing semantic rule is returned to the Planner rather than patched locally.
4. **Stable role configurations.** A role should normally keep one model and
   reasoning configuration for the duration of a task. Capability gaps are
   handled by narrowing work or escalating the question to the Planner, not by
   repeatedly switching a role's model mid-task.
5. **New problem classes are design signals.** A bug whose correct behavior is
   already frozen is an implementation defect. A newly discovered semantic,
   architectural, acceptance, or information-regime class is a contract gap and
   stops implementation until the Planner resolves it.
6. **Scientific/architectural acceptance and operational acceptance are
   separate.** The Planner accepts semantics and architecture; the Maintainer
   accepts implementation conformance, runtime evidence, and merge readiness.
7. **`main` is durable truth.** Chat, local notes, issues, and unmerged branches
   may inform work but do not publish project policy or implemented capability.

## Roles

### Planner

The Planner is the project design and scientific decision owner. The Planner:

- reads the repository, task index, maintainer reports, accepted pull requests,
  retained evidence, and external research needed to understand the current
  state;
- decides what task should be proposed, including objective, priority,
  dependencies, scope, information regime, scientific interpretation, and
  successor decision boundaries;
- defines the architecture needed by the task, including a canonical domain
  model or state machine when behavior spans coupled states, stages, artifacts,
  or terminal outcomes;
- defines required inputs, outputs, artifact lineage, compatibility rules,
  public/Oracle boundaries, and all scientific invariants;
- defines the normative acceptance model and acceptance matrix before production
  implementation starts, including normal outcomes, valid negative outcomes,
  invalid-experiment/fidelity outcomes, and explicit out-of-scope cases;
- classifies failure semantics and identifies which states or transitions must
  be impossible, fail closed, remain retryable, or terminate the experiment;
- defines the allowed implementation freedom and explicitly forbidden semantic
  changes;
- creates one fresh task branch and one draft pull request from current `main`
  for new work and writes the complete task specification there;
- resolves `CONTRACT_GAP` and `ARCHITECTURE_ESCALATION` reports from downstream
  roles;
- reviews the exact final implementation head for scientific, architectural,
  information-regime, and acceptance-semantic conformance before merge;
- reviews maintainer result reports before proposing successor work or revising
  the broader plan.

For a high-risk task, the Planner contract should be implementer-ready. Depending
on the task, it may explicitly define:

```text
objective / scientific hypothesis
canonical types or state machine
state transitions and terminal predicates
input and artifact identity model
artifact lineage / required parents
information-regime boundary
normative acceptance matrix
failure attribution and fail-closed rules
runtime experiment protocol
allowed implementation freedom
forbidden changes
escalation conditions
final semantic-review checklist
```

The Planner does not normally write feature implementation, runtime plumbing,
serialization code, multiprocessing code, generated artifacts, or ordinary
regression fixes. Those are downstream execution work once the contract is
frozen.

The Planner may update task specifications, planning documents, collaboration
policy, architecture contracts, and test-independent acceptance definitions.
After implementation authorization, a material Planner contract change suspends
that authorization and requires renewed execution approval.

The Planner does not merge task pull requests or manage implementer processes.

### Main Maintainer

The Main Maintainer is the execution coordinator, repository conformance reviewer,
and merge owner. The Maintainer:

- maintains `main`, repository hygiene, branch/worktree isolation, lifecycle
  state, and project reporting;
- reviews a Planner-authored specification for repository consistency,
  implementability, dependency availability, objective measurability, and
  whether the contract is sufficiently complete to execute without semantic
  invention;
- requests Planner revision when a contract is incomplete, contradictory,
  infeasible, or inconsistent with merged repository contracts;
- records the exact frozen Planner specification commit and authorizes
  implementation only after the execution boundary is complete;
- dispatches and manages the Task Implementer on the approved task branch and
  pull request;
- translates or coordinates translation of the Planner's normative acceptance
  matrix into executable tests/fixtures without changing its meaning;
- checks that implementation-independent expected values are not derived from
  the production helper under test;
- runs or coordinates required verification, WSL execution, artifact retention,
  and runtime evidence collection;
- reviews the implementation for conformance to the frozen Planner contract,
  code correctness, regressions, repository boundaries, tests, artifact
  compatibility, provenance, and operational completeness;
- classifies review findings as `IMPLEMENTATION_BUG`, `CONTRACT_GAP`, or
  `ARCHITECTURE_ESCALATION` before dispatching corrective work;
- sends contract or architecture gaps back to the Planner instead of inventing
  replacement semantics;
- requests implementation fixes only when the correct behavior is already
  defined by the frozen contract;
- performs the final operational/implementation acceptance and merges only after
  required Planner semantic acceptance is also present;
- updates the task index and `current_status.md` after merge so the Planner can
  evaluate the result.

The Maintainer does **not** own scientific architecture, acceptance semantics,
new invariants, information-regime choices, promotion criteria, or successor-task
content. It does not convert an implementation surprise into a new rule simply
because adding a validator or special case would make the current tests pass.

The Maintainer does not implement feature tasks directly. Maintainer-owned
review, authorization, merge, branch/worktree management, execution coordination,
lifecycle management, and result reporting are control-plane work, not feature
implementation.

### Task Implementer

The Task Implementer is a bounded implementation agent coordinated by the Main
Maintainer. The Implementer:

- works on exactly one authorized task contract;
- works on the authorized task branch and pull request;
- starts only after the Maintainer has published execution authorization for an
  exact frozen Planner contract;
- implements only the approved scope and architecture;
- writes the production code, focused tests, plumbing, serialization, CLI
  adapters, mechanical refactors, and performance changes required by the
  contract;
- runs the prescribed local verification and reports deviations, failures, and
  limitations;
- keeps the pull request draft or explicitly incomplete until required
  implementation and evidence are complete;
- responds to `IMPLEMENTATION_BUG` findings on the same implementation line.

The Implementer must not choose or modify scientific semantics, acceptance
criteria, terminal-case meaning, information-regime boundaries, artifact
lineage rules, or architecture merely to resolve a failing review. If the
correct behavior is not unambiguously derivable from the frozen Planner
contract, the Implementer stops and reports a contract gap to the Maintainer for
Planner escalation.

The Implementer does not merge the pull request and does not choose its own model
or reasoning configuration.

### Advisory Reviewer

A fresh advisory reviewer may be used when the user or Planner requests an
independent architecture, scientific, or code review. Its report is evidence,
not a parallel source of project requirements.

- Findings that expose an implementation defect against the frozen contract may
  be handled as `IMPLEMENTATION_BUG`.
- Findings that require a new invariant, state, transition, failure class,
  architecture rule, or acceptance meaning are `CONTRACT_GAP` or
  `ARCHITECTURE_ESCALATION` and return to the Planner.
- The reviewer must not create an endless third review/patch loop. Its primary
  value in architecture recovery is to identify the abstraction failure and
  provide evidence for a new Planner-owned contract.

## Stable Role Configuration

The workflow assumes that the Planner is the highest-capability reasoning role
and therefore carries the high-abstraction work. Maintainer and Implementer
roles may use less expensive fixed configurations because their work is
constrained by the Planner contract.

Do not rely on dynamic model switching as the ordinary escalation mechanism.
Changing a role's model or reasoning mode partway through a task may itself
change behavior and context quality. Prefer this order:

1. keep the role configuration stable;
2. determine whether the issue is already specified;
3. if specified, fix it as an implementation defect;
4. if not specified or structurally cross-cutting, stop and escalate the
   question to the Planner;
5. simplify or split the downstream implementation if its mechanical surface is
   still too large.

A role configuration may be deliberately changed between tasks, or after an
explicit task restart, but the collaboration contract must not depend on the
user repeatedly inspecting each subtask and selecting a different model.

## Finding Classification And Escalation

Every blocking review finding must be classified before corrective work begins.

### `IMPLEMENTATION_BUG`

The frozen Planner contract already defines the correct behavior, but the code
violates it.

Examples:

```text
contract: valid Stage-5 failure -> Case C
implementation: valid Stage-5 failure -> Case D

contract: selected states are unique by the frozen identity
implementation: duplicate rows survive selection
```

Flow:

```text
Maintainer -> Implementer -> focused fix -> prescribed regression verification
```

No Planner intervention is required unless the fix exposes a contract gap.

### `CONTRACT_GAP`

The implementation or review encounters a meaningful case for which the frozen
contract does not unambiguously define the correct behavior.

Examples include a previously undefined state transition, new artifact-lineage
meaning, ambiguous partial-failure semantics, or an information-regime case not
covered by the accepted model.

Flow:

```text
STOP production changes
        ↓
Maintainer records the gap and exact head/evidence
        ↓
Planner resolves the semantics and updates the contract if needed
        ↓
Maintainer reauthorizes the new exact contract
        ↓
Implementer resumes
```

The Maintainer or Implementer must not resolve a contract gap by adding a local
validator, default, fallback, special case, or hidden rule.

### `ARCHITECTURE_ESCALATION`

Use this classification when the observed defects indicate that the current
implementation abstraction is wrong rather than one local rule being wrong.
Signals include:

- multiple new cross-module problem classes discovered across successive review
  passes;
- state or terminal semantics duplicated across several writers, validators, and
  dispatchers;
- an implementation surface that grows far beyond the scientific change because
  generic control-plane machinery is being invented inside a narrow task;
- acceptance tests that must increasingly import private production helpers to
  reconstruct the expected contract;
- repeated fixes that move the failure without reducing conceptual complexity;
- inability to identify one canonical source of truth for state transitions,
  artifact lineage, or acceptance meaning.

When this occurs, stop incremental patching. The Planner decides whether to
simplify, split, redesign, or cleanly reimplement the affected layer.

As a practical guardrail, if a corrective pass is followed by another newly
identified cross-module problem class, the Maintainer should presume
`ARCHITECTURE_ESCALATION` unless it can show that both defects were ordinary
violations of already-frozen acceptance rows.

## Source Of Truth And Execution Authorization

- `main` is the only integration line and durable source of implemented project
  truth.
- A branch or local artifact is not an implemented capability until its pull
  request is accepted and merged into `main`.
- Every task's normative contract is defined by one document under `docs/tasks/`.
- Task lifecycle state is authoritative only in the Active Backlog table in
  `docs/tasks/README.md` after the relevant change is merged into `main`.
- Individual task documents must not carry mutable `Status:` fields.
- A proposed lifecycle row on an open branch has no merged lifecycle effect.
- Chat summaries, issues, pull-request descriptions, and local agent notes do
  not independently authorize implementation.
- Project policy becomes durable only when merged into `main`.

For new work, execution authorization means that:

1. the Planner has frozen a complete semantic/scientific contract and normative
   acceptance boundary on the task branch;
2. the Maintainer has verified repository feasibility and that downstream roles
   can execute without inventing missing semantics; and
3. the Maintainer has published authorization for the exact contract commit.

The Maintainer may continue using the compatibility record:

```text
SPEC APPROVED

task: T071
approved_spec_commit: <full commit SHA>
implementation_authorized: true
```

`SPEC APPROVED` is execution authorization and repository-feasibility acceptance.
It does not transfer ownership of architecture or scientific semantics from the
Planner to the Maintainer.

## One Task, One Branch, One Pull Request

The normal workflow uses one task ID, one branch, and one pull request from
specification through accepted implementation.

- The Planner creates the branch from sufficiently current `main`.
- The pull request is draft during contract authoring.
- Before execution authorization, the diff is planning/specification/control-
  plane only.
- After authorization, the Maintainer dispatches the Implementer on that branch.
- The Implementer appends code, tests, verification, reports, and required
  task-specific documentation.
- A branch must not combine multiple task IDs.
- Parallel tasks use isolated worktrees/directories; agents must never switch
  branches in a shared worktree.
- Dependencies are synchronized before execution authorization when newer `main`
  changes relevant assumptions.

Suggested branch names:

```text
task/T071-task-description
task/T072-controlled-run-foundation
```

### Architecture-Recovery Exception

A failed implementation history must not force continued work on an unhealthy
branch. When the Planner explicitly declares `ARCHITECTURE RECOVERY`, it may:

1. freeze the existing PR as an audit record of the failed implementation path;
2. identify precisely which scientific primitives, fixtures, evidence, or
   generic utilities are safe to salvage;
3. write a replacement recovery contract from current clean `main`; and
4. authorize a clean recovery branch/PR for the **same task ID**.

This is an exception to the ordinary one-task-one-PR rule and requires an
explicit Planner directive. It is not a way to evade ordinary review findings.
The rejected PR remains unmerged and must be linked from the recovery task
record so its diagnostic history is preserved.

## Pull-Request Phases

### 1. Planner Contract

The Planner authors the complete task contract, architecture where required,
acceptance semantics, normative acceptance matrix, and proposed lifecycle
changes. No production implementation begins.

### 2. Execution Readiness Review

The Maintainer checks repository consistency, dependencies, feasibility,
measurability, artifact availability, and whether the contract can be executed
without inventing semantics. Gaps return to the Planner.

### 3. Implementation Authorized

The Maintainer publishes `SPEC APPROVED` for the exact frozen Planner contract
and dispatches the Implementer. The pull request normally remains draft.

### 4. Implementation And Evidence

The Implementer writes bounded production code against the frozen contract. The
Maintainer coordinates prescribed verification and runtime evidence. Only
`IMPLEMENTATION_BUG` findings are patched locally; contract/architecture gaps
return to the Planner.

### 5. Dual Final Acceptance

The exact final head receives:

- Planner scientific/architectural acceptance; and
- Maintainer implementation/operational acceptance.

The same exact head must satisfy both. A code change after either acceptance
invalidates that acceptance unless the accepting role explicitly records that
the change is immaterial to its review boundary.

### 6. Merged Or Closed

The Maintainer merges an accepted implementation into `main`. An abandoned,
superseded, architecture-rejected, or infeasible line is closed or retained as
an explicit audit record according to the Planner decision.

## Required Task Contract

Every task document must define:

1. objective and motivation;
2. current `main` baseline;
3. dependencies and required input identities;
4. scientific/information-regime boundary where applicable;
5. in-scope and explicitly out-of-scope behavior;
6. architecture and canonical domain/state model when coupled semantics require
   one;
7. generated outputs, artifact identity/lineage contracts, and reproduction
   commands;
8. frozen invariants and allowed implementation freedom;
9. normative acceptance matrix, including valid positive, valid negative, and
   invalid/fidelity outcomes where relevant;
10. failure attribution, terminal semantics, and fail-closed rules where
    relevant;
11. required verification commands and real-simulator gates;
12. sharding, worker topology, cohort, seed, and budget definitions for
    substantial execution;
13. promotion, rejection, continuation, and successor decision boundaries;
14. explicit `CONTRACT_GAP` / architecture escalation conditions;
15. required pull-request evidence and final Planner review checklist.

A task that cannot be implemented without downstream semantic invention is not
ready for execution authorization.

Not every small mechanical task needs a complex state machine. The amount of
formal modeling should match semantic risk. The Planner must nevertheless make
expected behavior and out-of-scope behavior sufficiently explicit that a
Maintainer or Implementer can distinguish an implementation bug from a contract
gap.

## Acceptance-First Implementation Gate

The Planner's normative acceptance matrix is part of the frozen task contract.
For tasks with coupled state transitions, artifact/retention contracts,
parallel-worker evidence, numerical/statistical acceptance, or scientific
terminal cases, it must define before production implementation:

- the canonical states/stages and legal transitions;
- normal success and every valid terminal decision;
- valid negative scientific results separately from invalid/fidelity failures;
- realistic incomplete, stale, mismatched, truncated, and partial-failure cases
  required by the contract;
- exact counts, identities, ranges, provenance, and lineage rules that cannot be
  inferred from one successful fixture;
- explicit out-of-scope behavior;
- first-valid, idempotency, retry, or transaction/commit semantics where those
  matter.

The executable acceptance suite is a mechanical encoding of this normative
matrix. The Maintainer may coordinate its implementation and the Implementer may
write test code, but neither may change fixture meaning, expected outcomes, or
failure semantics. Production helpers under test must not define their own
expected values.

If encoding the acceptance matrix exposes an ambiguity or missing row, that is a
`CONTRACT_GAP`: stop and return it to the Planner before production code
continues.

The acceptance boundary protects reproducibility, artifact compatibility,
experiment fidelity, and realistic failure semantics. It is not a generic
security or trusted-producer attestation framework. Do not add proof chains,
signatures, anti-tampering machinery, or unrelated product requirements unless
the Planner contract explicitly requires them for the scientific/design error
being controlled.

## Frozen Contract And Reauthorization

The approved task document at `approved_spec_commit` is the implementation
contract. Material fields include:

- objective and priority;
- canonical architecture/state model;
- dependencies and required input identities;
- in-scope and out-of-scope behavior;
- information regime and compatibility constraints;
- required outputs, artifact identity, and lineage;
- acceptance matrix and failure semantics;
- verification and real-simulator gates;
- sharding, worker topology, cohort, seed, or budget definitions;
- promotion, rejection, and successor decision boundaries.

Changing a material field suspends implementation authorization. The Planner
updates the contract, and the Maintainer publishes a new exact authorization
before implementation resumes.

Formatting, spelling, broken-link repair, and other demonstrably non-semantic
changes may be treated as immaterial. The Maintainer records that conclusion
when it is not self-evident.

## Large And Long-Running Execution

If a task requires substantial WSL `sts_lightspeed` source generation, restored
evaluation, fixed-cohort comparison, coverage, teacher collection, or training-
scale simulation, the Planner contract must define the stage-by-stage sharding
and worker plan.

Single-worker execution is appropriate only for small smoke tests, local
debugging, non-simulator aggregation, or a documented resource/tooling limit. A
`smoke` label does not exempt a substantial stage. The default worker target for
scale evidence is the host logical CPU count capped by shard count and documented
memory/simulator limits. On a 16-logical-core maintainer machine, large WSL stages
normally use 16 workers unless the task records a reason otherwise.

The final evidence must include shard/worker counts, seed/source/cohort ranges,
and wall-clock cost for each substantial stage.

Long-running work should use cheap preflight checks and detached/non-interactive
execution where practical. Record status/log locations and coarse expected
runtime when known. Operational status files are transient execution state, not
scientific artifacts.

## Incremental Reuse

Expensive work should be reused only when the frozen contract says its semantics
are unaffected by the reviewed change.

After a repair, identify the earliest affected stage or independent run.
Validated outputs before that boundary may remain reusable with their original
provenance. Independent completed shards may likewise be reused when their own
inputs and contract still validate.

A code-head change is not by itself proof that an artifact is reusable or
invalid. Reuse follows the artifact's relevant inputs, configuration, completion
state, provenance, and the Planner-defined impact boundary.

During architecture recovery, old runtime evidence is diagnostic by default. It
becomes authoritative evidence for the recovery implementation only if the new
Planner contract explicitly establishes semantic compatibility and the final
head validates the required lineage.

## Task Artifact Boundaries

Tasks may depend on merged prerequisite contracts, but not on accidental local
state. A required input must be one of:

- a committed fixture or current artifact schema;
- a command in the task/report that regenerates it; or
- an explicitly external/ignored artifact with schema, provenance,
  compatibility requirements, and regeneration/provision instructions.

A task must not use another task's one-off smoke output, uncommitted worktree
file, local checkpoint, or temporary report as an implicit input.

Generated large artifacts stay out of Git. Durable project state is the schema,
command surface, manifest/provenance, retained identity, and accepted evidence.

If GB-scale artifacts are retained after merge, the task must define a stable
ignored/local path, schema/provenance, SHA-256 and approximate size,
regeneration command, compatibility requirements, retention owner/reason,
downstream consumers, and deletion conditions. Raw retained artifacts are not
independently authoritative project truth.

## Pull-Request Contract

During the Planner-contract phase, the PR description records:

- task ID and task-document link;
- planning/scientific summary;
- current `main` baseline;
- proposed lifecycle row;
- dependencies and external capability status;
- architecture/acceptance risks;
- confirmation that production implementation is not yet authorized.

After authorization, it additionally records:

- `approved_spec_commit`;
- current implementation head;
- implementation summary and compatibility impact;
- input/output artifacts and reproduction commands;
- retained artifact contract when required;
- exact verification commands/results;
- shard/worker/range/wall-clock evidence for substantial stages;
- unsatisfied acceptance rows, known risks, contract gaps, or escalations;
- whether legacy reference commit `d56e10e` was consulted.

A ready-for-review PR is an implementation-complete claim. If required evidence
or acceptance rows are missing, it remains draft or explicitly incomplete.

## Review And Merge

### Planner Contract Review

The Planner owns semantic completeness. Before handing the contract to execution,
the Planner checks:

- scientific objective and interpretation;
- architecture and canonical state model where needed;
- information-regime/human-knowledge boundary;
- artifact lineage and experiment identity;
- normative acceptance matrix and terminal/failure semantics;
- out-of-scope boundary;
- runtime experiment protocol and decision gates;
- escalation conditions.

### Maintainer Execution-Readiness Review

The Maintainer checks:

- consistency with current `main` and accepted repository contracts;
- dependencies and artifacts are available/reproducible;
- the contract is objectively executable;
- substantial execution has sharding/worker/evidence definitions;
- no production code was added before authorization;
- downstream roles can implement without inventing semantic rules.

If not, the Maintainer returns the exact question to the Planner. It does not
write a substitute architecture.

### Maintainer Implementation Review

The Maintainer reviews:

- conformance to the exact frozen contract;
- correctness and ordinary behavioral regressions;
- tests and executable acceptance rows;
- artifact/provenance compatibility;
- required WSL/runtime evidence;
- worker/shard evidence;
- unnecessary code scope, duplication, hidden defaults, and repository ownership
  violations;
- task-specific documentation and lifecycle completeness.

A finding must be classified before dispatch. Local corrective loops are for
`IMPLEMENTATION_BUG` only.

### Planner Final Semantic/Architecture Review

Before merge, the Planner reviews the exact implementation head and evidence for:

- preservation of the original scientific question and decision meaning;
- architectural conformance to the approved canonical model;
- information-regime and human-knowledge boundary;
- acceptance semantics, valid-negative versus invalid-experiment distinctions,
  and terminal behavior;
- absence of unauthorized scope inflation or newly invented semantic rules;
- whether any post-authorization discovery should have been treated as a
  contract/architecture gap;
- whether runtime evidence supports the conclusion being published.

The Planner records an explicit exact-head semantic acceptance or blocking
finding on the PR. A mechanical task may receive a short acceptance, but the
semantic ownership remains explicit.

### Review Finding Delivery

The PR is the authoritative delivery channel for findings and conclusions.
Review messages identify the exact head, classification, blockers, required
changes, and relevant verification.

A finding that exists only in chat/local notes is not delivered. A later review
that finds a new problem must publish a new finding; prior comments do not imply
acceptance of a newer head.

### Merge Gate

Only the Main Maintainer merges. Before merge it confirms:

1. the final head is based on a valid current `approved_spec_commit`;
2. every material contract change was Planner-resolved and reauthorized;
3. all required implementation deliverables and runtime evidence passed;
4. the exact final head has explicit Planner semantic/architecture acceptance;
5. the Maintainer's implementation/operational acceptance applies to that exact
   head;
6. the task-index row reflects the accepted terminal state;
7. the PR contains no unrelated task or unauthorized control-plane work.

A code change after final acceptance requires re-review within the affected
boundary.

## Planner Handoff And Maintainer Reporting

`docs/current_status.md` is the canonical Maintainer result report for the
Planner. `docs/tasks/README.md` remains the merged lifecycle authority.

After every accepted, cancelled, blocked, or scientifically terminal result, the
Maintainer records:

- task, PR, frozen contract commit, implementation commit, and merge commit where
  applicable;
- observed behavior and terminal/scientific decision without inventing a
  successor task;
- verification and simulator gates;
- retained artifact identities/provenance/deletion conditions;
- limitations, failed gates, unresolved questions, and dependency changes;
- any contract/architecture escalation that occurred and how the Planner
  resolved it.

The Planner reads that report and decides any successor task. The Maintainer may
request clarification or report blockers but does not originate new scientific
work.

## Documentation Ownership

Project-level policy becomes authoritative through `main`.

- The Planner owns architecture, planning, training/scientific contracts,
  collaboration semantics, task contracts, and acceptance meaning.
- The Maintainer owns repository lifecycle synchronization, execution reports,
  merge publication, and operational consistency.
- The Implementer may update task-specific implementation documentation and
  evidence required by the frozen contract, but must not rewrite unrelated
  architecture, roadmap, collaboration, or scientific policy.

Code docstrings, schema comments, and narrowly scoped operational notes may be
part of implementation when required for correctness.

## Issues

Issues are optional discussion/dependency surfaces. They are useful for unresolved
questions, cross-repository capability work, long-lived blockers, and evidence
collection before a Planner contract is complete.

An issue does not replace the task contract, Planner decision, execution
authorization, PR acceptance, or merge.

## Legacy Branch Disposition

`codex/docs-consolidation` was reviewed and merged into `main`; it is no longer
an active work line.

`codex/integration-current` at commit `d56e10e` is a read-only recovery reference.
It is neither ignored nor eligible for wholesale merge. Its useful work is
decomposed into the task backlog. The branch may be deleted only after all mapped
tasks are `DONE`, `CANCELLED`, or explicitly superseded.
