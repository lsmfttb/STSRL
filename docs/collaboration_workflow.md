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
- final scientific/architecture acceptance;
- direct task landing after both final acceptances are recorded on the same exact
  head.

Planner does not normally own module names, function signatures, CLI spelling,
helper layout, logging, temporary files, or test harness design.

### Main Maintainer

Maintainer owns execution coordination and repository conformance:

- branch/worktree/lifecycle/merge hygiene;
- execution-readiness review and exact-head `SPEC APPROVED`;
- Implementer dispatch;
- verification, runtime evidence, and artifact retention;
- implementation review and finding classification;
- final implementation/operational acceptance;
- preparation of factual lifecycle/result landing records before final dual
  acceptance whenever practical.

Maintainer may choose ordinary execution bindings that do not change task meaning.
Maintainer does not invent scientific semantics, acceptance meaning, information
regime, promotion criteria, or successor science.

### Task Implementer

After authorization, Implementer owns ordinary implementation choices, including
code/tests, module/function layout, minimal APIs, CLI adapters, non-material
serialization, logging, temporary files, multiprocessing mechanics, and mechanical
refactors.

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

1. **Planner Contract** — delta contract and acceptance meaning; no feature code.
2. **Execution Readiness** — Maintainer checks current-`main` consistency,
   feasibility, required inputs, and unresolved material semantics.
3. **Implementation Authorized** — Maintainer publishes exact-head authorization:

   ```text
   SPEC APPROVED

   task: <task-id>
   approved_spec_commit: <full commit SHA>
   implementation_authorized: true
   ```

4. **Implementation And Evidence** — Implementer works inside the frozen semantic
   equivalence class; Maintainer coordinates verification/evidence.
5. **Landing Record Preparation** — before final acceptance, Maintainer normally
   places factual terminal results, artifact identities, limitations, and required
   task-lifecycle/result documentation on the same PR head. Avoid a routine
   post-merge documentation round trip.
6. **Dual Final Acceptance** — the same exact head requires Maintainer
   implementation/operational acceptance and Planner scientific/architecture
   acceptance. The normal order is Maintainer first, Planner last.
7. **Landing** — once both final acceptances refer to the same exact head, Planner
   may merge immediately and update the research ledger / successor state. No
   additional Maintainer handoff is required merely to perform the merge.
   Maintainer may still perform the merge when explicitly requested or when a
   repository constraint requires it.

A material Planner-contract change after authorization requires renewed approval.
Clearly non-semantic wording/spelling fixes do not require a semantic reset when
Maintainer records them as immaterial.

Any material change to the PR head after either final acceptance invalidates that
acceptance for the new head. A clearly non-semantic landing-only change may retain
acceptance only when both roles explicitly record that it is immaterial. Prefer
putting landing records on the PR before dual final acceptance so this exception is
rare.

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
- Task lifecycle is authoritative in merged `docs/tasks/README.md`.
- `docs/current_status.md` is the merged result record: Maintainer owns factual
  execution/evidence reporting, and Planner owns accepted scientific
  interpretation.
- PR comments carry task-specific findings/acceptances but do not replace merged
  policy.
- Prefer inheritance/reference over duplicated normative text.

Before a task's final dual acceptance, Maintainer normally records the result,
evidence, limitations, retained material artifacts, and genuine gaps/escalations
on the task PR. After dual acceptance on that same exact head, Planner may land the
task directly, update the research ledger, and decide successor work.

Each role normally keeps one model/reasoning configuration for a task. If a role
cannot execute within its boundary, narrow/split the work or escalate the material
semantic question rather than relying on repeated model switching or unlimited
review/patch loops.
