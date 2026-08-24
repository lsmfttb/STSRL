# T071: Post-T064 Experiment Execution Simplification

## Objective

Reduce the execution and maintenance overhead exposed by T064 before the next
research experiment. Preserve accepted scientific behavior while simplifying
T064-specific orchestration, removing validation/provenance checks whose only
purpose is to distrust another repository-owned stage, and adding a lightweight
way to launch and inspect long-running jobs without keeping an AI maintainer or
implementer in a polling loop.

T071 is a mechanical/operational cleanup task. It does not change the T064 Case B
result and does not implement T065. T065 remains the next intended research task
after this cleanup.

## Current Main Baseline

T064 merged as PR #68 at merge commit
`ac1b06dd2db4ad25a7b0bdc8097cc0cfdc26dffa` with a complete valid Case B. The
accepted result recommends T065 but does not authorize it.

The T064 implementation also exposed a maintenance problem that is now large
enough to address before another multi-stage experiment:

- PR #68 accumulated 47 commits, touched 29 files, and added about 14k lines;
- `src/sts_combat_rl/commands/t064_curriculum_transfer.py` became a large
  task-specific orchestration/validation surface;
- multiple failures were discovered only after expensive stages had started;
- early execution initially coupled artifact reuse to exact Git heads, requiring
  unnecessary upstream reruns until a stage-affect boundary was introduced;
- Stage 4 later needed run-local reuse and independent-worker execution;
- Stage 5/6 needed additional task-specific routing and process-isolation fixes;
- long-running stages had no small detached-job/status convention, so agents
  repeatedly inspected processes and logs while jobs were simply still running.

The accepted T064 task document explicitly deferred broader simplification until
after T064 if implementation evidence showed repeated orchestration/contract
duplication. That condition is now met.

## Dependencies

- T019 codebase mechanical-refactor conventions;
- T043/T044/T070 existing teacher, evaluation, and search artifact readers and
  validators reused by T064;
- T064 accepted execution/reuse evidence and final Case B artifacts.

T065 remains `DRAFT` while T071 is in progress. T071 is intended to make the
subsequent T065 specification smaller and less likely to duplicate T064's
execution machinery.

## Scope

### 1. Simplify T064 validation and provenance handling

Audit the T064-specific production and test surfaces and classify checks into two
groups.

Keep checks that protect realistic correctness or scientific validity, including:

- schema/type/readability checks;
- frozen experiment configuration checks;
- holdout leakage and duplicate-source checks;
- row/cardinality/order/linkage checks where those facts affect the experiment;
- checkpoint/model compatibility checks;
- process return codes, output completeness, and partial-file detection;
- deterministic seed/batch-plan semantics;
- stage/run reuse boundaries after a behavior-affecting repair.

Remove or replace checks that add maintenance cost without protecting this
trusted personal-project workflow, including where present:

- exact producer Git commit equality used as an artifact-reuse gate rather than
  provenance metadata;
- repeated rehashing of the same immutable input several times in one command
  path when one verified identity is already available;
- duplicated task-local restatements of T043/T044/T070 semantics when an
  authoritative existing reader/validator can be reused directly;
- duplicate identity/cross-link fields whose only purpose is to prove that a
  trusted repository-owned previous stage was not maliciously forged;
- retained-attempt bookkeeping or mutation tests aimed only at adversarial
  tampering rather than accidental corruption, stale configuration, incomplete
  execution, leakage, or design drift.

Prefer one source of truth for each fact. If a T064 local validator exists only
because an underlying reused subsystem does not expose a reusable validation
function, a small extraction into that subsystem is allowed when it reduces net
duplication and preserves existing callers.

### 2. Shrink the task-specific orchestration surface

Review these primary surfaces first:

- `src/sts_combat_rl/commands/t064_curriculum_transfer.py`;
- `src/sts_combat_rl/commands/t064_curriculum.py`;
- `src/sts_combat_rl/sim/t064_curriculum.py`;
- `tests/test_t064_curriculum.py`.

Delete redundant code before moving code. Mechanical splitting is allowed only
when a remaining boundary is genuinely clearer; moving unchanged code into many
new modules does not satisfy this task.

Keep the existing T064 command behavior and the four accepted compact artifact
schemas compatible. No T064 scientific stage, gate, cohort, seed, budget, model,
or terminal decision changes.

### 3. Preserve incremental stage/run reuse as the normal rule

Codify the accepted T064 lesson as a repository workflow rule:

- a Git commit recorded on an artifact is producer provenance, not a global
  cache key;
- after a reviewed repair, identify the earliest affected stage or run;
- strictly validated outputs before that boundary remain reusable with their
  original producer provenance;
- within an independent multi-run or multi-shard stage, completed outputs may be
  reused when their own inputs/configuration/reader checks still pass;
- missing, partial, failed, or behavior-affected outputs rerun;
- if the impact boundary cannot be established cheaply, choose an earlier
  conservative boundary rather than automatically invalidating the whole task.

This rule must not introduce a dependency-hash graph, Merkle tree, attestation
system, or new artifact framework.

### 4. Add lightweight detached long-job control

Add one small repository-owned operational utility for commands expected to run
longer than an interactive agent turn. It may be a script or narrowly scoped
command helper, but it is not a scientific artifact system or scheduler.

The utility must support:

- launching an arbitrary already-approved repository command in a detached local
  process/supervisor so the invoking agent can return immediately;
- persistent stdout/stderr log paths;
- one overwriteable operational status file with at least command, PID,
  `RUNNING`/`SUCCEEDED`/`FAILED`, start time, finish time when known, and exit
  code when known;
- an optional caller-supplied expected duration for a coarse ETA display;
- a status query that does not require continuous polling;
- clean handling of startup failure and a process that exits nonzero.

The status file is disposable operational state. It is not one of a task's
accepted evidence artifacts, needs no SHA/attestation chain, and must not become
a retained project contract.

Update collaboration guidance so an AI maintainer/implementer that starts a
healthy long job reports the PID/status/log/ETA once and stops active monitoring.
It should inspect again only after the expected window, on an explicit user
request, or when an external completion/failure signal is available. Do not add
a polling daemon, queue service, database, or background web service.

### 5. Keep numerical parallelism separate from orchestration parallelism

Document the T064 Stage-4 lesson for future tasks: per-run numerical settings
such as `torch_threads=1` may be frozen for determinism/performance, while
independent `(arm, seed)` runs can still execute concurrently when resources
permit. Future task specifications should freeze worker counts only when they
matter scientifically or are required by measured resource limits.

## Out Of Scope

- implementing or publishing T065, T063, or T066;
- changing the accepted T064 Case B result or regenerating T064 scientific
  evidence;
- changing T043/T044/T070 search, model, controller, evaluation, or artifact
  semantics;
- changing model architecture, training targets, optimizer behavior, seeds,
  cohorts, search budgets, or simulator/native behavior;
- adding a generic workflow engine, plugin architecture, scheduler, database,
  distributed executor, artifact graph, or security/attestation framework;
- deleting checks that detect real holdout leakage, accidental artifact mismatch,
  incomplete execution, incompatible checkpoints, or scientific design drift;
- broad unrelated repository cleanup.

## Design Constraints

- Treat repository-owned stages and the developer/AI tools as trusted actors.
  Validation is for accidental mistakes and scientific consistency, not an
  adversarial producer threat model.
- Preserve current public CLI behavior and artifact schemas unless a purely
  internal compatibility-preserving extraction is required.
- Prefer net deletion and direct reuse of existing subsystem validators over new
  abstractions.
- A new reusable helper must have at least two concrete current/future call sites
  or solve the detached-long-job requirement; otherwise keep the logic local.
- Optional PyTorch imports remain isolated behind the existing training path.
- No substantial simulator experiment is required for this task.

## Deliverables

- Simplified T064 execution/validation code with redundant defensive logic
  removed or replaced by authoritative reused validators.
- Regression tests focused on realistic corruption/configuration/reuse failures,
  with adversarial-only duplicate tests removed where no longer justified.
- One lightweight detached long-job utility plus focused tests.
- Collaboration/task-authoring guidance for stage-local/run-local reuse,
  detached long jobs, coarse ETA reporting, and non-polling agent behavior.
- PR report with before/after physical line counts for the four primary T064
  surfaces, a list of removed/reused validation responsibilities, and a concise
  note on what intentionally remains strict.

## Acceptance Criteria

T071 is accepted only when:

- accepted T064 compact artifacts and checkpoint/report readers remain
  compatible; no T064 schema version changes are introduced;
- T064 stage/run reuse no longer depends on exact current Git-head equality;
- every retained strict validation has a realistic accidental-error or
  scientific-validity purpose documented in code/tests or is inherited from an
  authoritative reused subsystem;
- at least one material block of duplicated T043/T044/T070 semantic validation
  is removed from T064 or replaced by an authoritative reusable validator;
- the combined T064-specific production/test surface decreases in physical lines
  after accounting for moved code; the PR must not claim simplification by only
  relocating unchanged logic;
- no new T064-specific artifact schema, sidecar, manifest family, or workflow
  framework is added;
- the detached long-job utility passes start/status/success/failure tests and its
  status file is explicitly disposable operational state;
- collaboration guidance explicitly discourages continuous AI polling of a
  healthy long-running job;
- no T064 full scientific rerun is required for acceptance.

## Required Verification

Run the standard local gates:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Also run focused checks that prove:

- accepted/current T064 manifest, training report, stage summary, and transfer
  decision fixtures or retained artifacts still strict-load;
- stage/run reuse accepts producer/current-commit differences when frozen inputs
  and semantics are unchanged, and rejects an actually affected or incompatible
  output;
- authoritative T043/T044/T070 validation remains in force after removing any
  duplicated T064 checks;
- the detached utility returns promptly after a trivial long command starts,
  reports `RUNNING`, later reports `SUCCEEDED`/`FAILED` with the correct exit
  code, and preserves logs;
- no busy-loop or high-frequency polling is required for status inspection.

A bounded WSL process-detachment smoke of a trivial command is allowed if needed
to verify host behavior. No `sts_lightspeed` scale run, T064 teacher/training
rerun, or fixed-cohort evaluation is required.

## Lifecycle And Next Research Step

T071 is proposed as a short engineering prerequisite before revising T065 for
publication. T065 remains the next research direction selected by the accepted
T064 Case B, but its current draft predates the T064 execution lessons and must
not simply copy T064's task-specific orchestration/validation machinery.

After T071 merges, the planner should re-read T061/T064 evidence and revise T065
with concrete supported screens, source scale, continuation-target budget,
training/evaluation gates, parallelism, and long-job execution using the
simplified conventions.

## PR Report

The final PR report must include:

- task ID, approved specification commit, implementation commit, and merge base;
- before/after line counts for the four primary T064 files above and any new
  operational utility;
- deleted, centralized, and intentionally retained validation responsibilities;
- confirmation that accepted T064 schemas/results were not changed;
- stage/run reuse compatibility tests;
- detached-job start/status/success/failure evidence and one coarse ETA example;
- exact verification commands/results;
- any cleanup deliberately left for a later task;
- confirmation that T065 was not implemented or scientifically re-specified in
  this task.
