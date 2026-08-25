# T071: Post-T064 Experiment Execution Simplification

## Objective

Reduce the execution and maintenance overhead exposed by T064 before the next
research experiment. Preserve accepted scientific behavior while simplifying
T064-specific orchestration, reusing authoritative subsystem validation, and
adding a lightweight way to launch and inspect long-running jobs without keeping
an AI maintainer or implementer in a polling loop.

STSRL is a lightweight open-source/personal research project. The implementation
should favor clear ownership, direct data flow, simple interfaces, efficient
execution, and focused validation at real correctness or experimental-validity
boundaries. Repository-owned stages and developer/AI tooling are trusted
participants; provenance identifies inputs and results, while validation exists
to catch realistic mismatch, incomplete execution, leakage, incompatible state,
and design drift.

T071 is a mechanical/operational cleanup task. It does not change the T064 Case B
result and does not implement T065. T065 remains the next intended research task
after this cleanup.

## Current Main Baseline

T064 merged as PR #68 at merge commit
`ac1b06dd2db4ad25a7b0bdc8097cc0cfdc26dffa` with a complete valid Case B. The
accepted result recommends T065 but does not authorize it.

The T064 implementation exposed enough execution and maintenance overhead to
justify a short cleanup before another multi-stage experiment:

- PR #68 accumulated 47 commits, touched 29 files, and added about 14k lines;
- `src/sts_combat_rl/commands/t064_curriculum_transfer.py` became a large
  task-specific orchestration/validation surface;
- several failures were discovered only after expensive stages had started;
- execution initially coupled reuse too closely to exact Git heads and later
  required stage/run-local recovery semantics;
- long-running stages lacked a small detached-job/status convention, causing
  repeated process/log inspection while healthy jobs were still running.

The accepted T064 task document explicitly deferred broader simplification until
after T064 if implementation evidence showed repeated orchestration/contract
duplication. That condition is now met.

## Dependencies

- T019 codebase mechanical-refactor conventions;
- T043/T044/T070 existing teacher, evaluation, and search readers/validators
  reused by T064;
- T064 accepted execution/reuse behavior and final Case B report.

T065 remains `DRAFT` while T071 is in progress.

## Required Inputs, Outputs, And Reproduction Contract

T071 has no required external or ignored T064 artifact. It must not depend on a
local T064 worktree, retained GB-scale teacher/trainer data, or retained
fixed-cohort outputs. No retention contract is required for T071.

The compatibility baseline is merged `main` at
`ac1b06dd2db4ad25a7b0bdc8097cc0cfdc26dffa`. The four accepted T064 compact
schemas remain compatible:

- `t064-curriculum-manifest-v1`;
- `t064-training-run-report-v1`;
- `t064-stage-summary-v1`;
- `t064-transfer-decision-v1`.

Their authoritative compact reader/validator surface is
`src/sts_combat_rl/sim/t064_curriculum.py`, including `load_compact_json` and
`validate_compact_document`. Compatibility is exercised through committed test
code in `tests/test_t064_curriculum.py`; implementation may add small committed
fixtures where useful, but T071 does not require the accepted large external
artifacts to be present.

Generated outputs are source/test/documentation changes only. T071 produces no
scientific result artifact and does not regenerate T064 evidence.

Focused reproduction commands are:

```bash
pytest tests/test_t064_curriculum.py
pytest tests/test_detached_job.py
```

plus the standard local gates listed below.

## Scope

### 1. Simplify T064 validation through clear ownership

The primary concrete duplication target is the T064-local
`_validate_t044_controller_semantics()` path in
`src/sts_combat_rl/commands/t064_curriculum_transfer.py`. T044 semantics should
be validated by the T044-owned report/validator surface rather than restated in
T064. If the existing T044 reader does not expose the needed reusable check, a
small compatibility-preserving validator may be extracted into
`src/sts_combat_rl/sim/de_assisted_fixed_cohort_comparison.py` and called by
T064 and existing T044 callers.

The simplification keeps the checks that directly protect the accepted
experiment contract:

- artifact schema/readability and required identity/provenance fields;
- frozen configuration and information-regime compatibility;
- holdout leakage and duplicate-source checks;
- row/cardinality/order/source-linkage checks where order is part of the
  experiment;
- checkpoint/model compatibility;
- process completion, return codes, missing/partial outputs;
- deterministic seed and batch-plan semantics;
- reviewed stage/run reuse boundaries after behavior-affecting repairs.

Git producer commit remains useful provenance metadata. Reuse decisions are
based on the affected stage/run plus the authoritative input/configuration and
reader checks for that output.

### 2. Shrink the task-specific execution surface

The primary physical-line-count scope starts with:

- `src/sts_combat_rl/commands/t064_curriculum_transfer.py`;
- `src/sts_combat_rl/commands/t064_curriculum.py`;
- `src/sts_combat_rl/sim/t064_curriculum.py`;
- `tests/test_t064_curriculum.py`.

If implementation adds T071-specific reusable validation code to a T043, T044,
or T070 module, every such touched source/test file is added to the same
measurement scope. The PR reports physical line counts at the T064 merge commit
and at the final head for the complete scope. The final total must be lower than
the baseline total; moving unchanged logic to another file does not count as
simplification.

A reproducible measurement may use `wc -l`/`Get-Content` or an equivalent Python
line-count command against the named base and final files. The PR must list the
exact files and command used.

Existing T064 command behavior and the four compact schemas remain compatible.
No T064 scientific stage, gate, cohort, seed, budget, model, or terminal decision
changes.

### 3. Make incremental reuse the normal execution rule

Update repository guidance so expensive workflows use the smallest reviewed
repair boundary that preserves correctness:

- producer Git SHA records where an artifact came from;
- a behavior-affecting repair identifies its earliest affected stage or run;
- validated outputs before that boundary remain reusable with their original
  producer provenance;
- independent completed runs/shards remain reusable when their own inputs,
  configuration, and reader checks still pass;
- affected, missing, partial, or failed work is rerun.

When impact is uncertain, reviewers may choose an earlier conservative boundary.
The rule should stay operationally simple rather than creating a new dependency
or artifact system.

### 4. Add one lightweight detached long-job utility

Implement exactly one small operational entry point:

`python scripts/run_detached_job.py`

Supported commands:

```text
python scripts/run_detached_job.py start \
  --status <status.json> \
  --stdout <stdout.log> \
  --stderr <stderr.log> \
  [--cwd <dir>] \
  [--expected-seconds N] \
  -- <command...>

python scripts/run_detached_job.py status --status <status.json>
```

`start` launches a detached local supervisor and returns after launch rather than
waiting for the target command. The target inherits the caller environment;
`--cwd` defaults to the caller's current working directory. The supervisor PID
is the `pid` recorded in status and owns the command/status lifecycle.

The status JSON is disposable operational state with these fields:

- `command`: argument vector;
- `cwd`;
- `pid`: detached supervisor PID;
- `state`: `RUNNING`, `SUCCEEDED`, or `FAILED`;
- `started_at`;
- `finished_at`: null while running;
- `exit_code`: null while running;
- `expected_seconds`: null when omitted;
- `estimated_finish_at`: derived from start plus expected duration when supplied;
- `stdout_path` and `stderr_path`;
- `startup_error`: null on normal launch, otherwise a short error string.

The supervisor writes `RUNNING` after the target process starts. Normal exit 0
becomes `SUCCEEDED`; startup failure or nonzero exit becomes `FAILED` with the
corresponding exit code/error. Status updates are atomic enough that readers do
not observe a partially written JSON document. ETA is coarse display metadata,
not a scheduling guarantee.

Focused tests live in `tests/test_detached_job.py` and cover start/status,
success, startup failure, nonzero exit, log persistence, cwd/environment
inheritance, and expected-duration fields.

### 5. Keep numerical settings separate from orchestration concurrency

Document the T064 Stage-4 lesson for future tasks: a per-run numerical setting
such as `torch_threads=1` may remain frozen while independent `(arm, seed)` runs
execute concurrently when resources permit. Worker topology should be frozen
when it affects experiment semantics or when a measured resource limit requires
it; otherwise it is an execution choice.

## Collaboration Guidance Files

T071 must leave the collaboration documents consistent and concise:

- `AGENTS.md`: align the Planner/Main Maintainer roles with the current
  planner-authored single-task PR workflow, summarize the lightweight design
  principle, and add the concise stage/run-reuse plus detached-long-job agent
  behavior;
- `docs/README.md`: make `docs/collaboration_workflow.md` the explicit authority
  for workflow questions and align the Branch Workflow summary with it;
- `docs/collaboration_workflow.md`: add the durable stage/run-local reuse rule and
  long-job execution guidance, including coarse ETA and non-continuous agent
  monitoring;
- `docs/tasks/README.md`: keep the task-index/work-queue wording consistent and
  summarize the same execution conventions for task authors without duplicating
  the detailed workflow text.

`docs/project_architecture.md` remains the design authority for runtime/model
architecture and does not need a T071-specific workflow edit.

## Out Of Scope

T071 does not implement T065/T063/T066, alter the accepted T064 result, change
T043/T044/T070 scientific semantics, change simulator/native behavior, or create
another research/orchestration framework. The task is complete when the existing
path is simpler, easier to resume, and cheaper to operate while the accepted
scientific checks remain intact.

## Design Constraints

- Prefer clear module ownership and direct reuse of subsystem contracts.
- Keep validation close to the fact it owns and proportional to realistic
  correctness or experimental-validity risk.
- Preserve public CLI and artifact compatibility unless a narrow internal
  extraction is required.
- Prefer net deletion to new abstraction layers.
- Optional PyTorch imports remain isolated behind the existing training path.
- No substantial simulator experiment is required for this task.

## Deliverables

- Simplified T064 execution/validation code with T044 semantic ownership moved to
  the authoritative T044 surface;
- regression tests covering the retained scientific/correctness boundaries and
  incremental reuse;
- `scripts/run_detached_job.py` and `tests/test_detached_job.py`;
- consistent collaboration guidance in the four files named above;
- a PR report with before/after physical line counts, removed/reused validation
  responsibilities, and the checks intentionally kept strict.

## Acceptance Criteria

T071 is accepted only when:

- the four accepted T064 compact schemas still load through the current reader
  and no T064 schema version changes;
- T064 stage/run reuse accepts producer/current-commit differences when the
  reviewed impact boundary and frozen input/configuration checks allow reuse;
- T064 no longer carries its own full T044 controller-semantic restatement;
- the authoritative T044 validation still checks the accepted role/controller,
  information-regime, action-space, budget, and checkpoint compatibility needed
  by T064;
- the complete line-count scope defined above has a lower final physical-line
  total than the T064-merge baseline;
- leakage/duplicate, source/order, configuration, checkpoint compatibility,
  completion/partial-output, and deterministic plan checks remain effective;
- the detached utility passes its focused contract tests and the status file is
  treated as disposable operational state;
- the collaboration documents agree on task ownership, stage/run-local reuse,
  coarse ETA reporting, and non-continuous monitoring of healthy long jobs;
- no full T064 scientific rerun is required for acceptance.

## Required Verification

Run:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
pytest tests/test_t064_curriculum.py
pytest tests/test_detached_job.py
```

Also report the exact physical-line-count command and result for the accepted
measurement scope. A bounded local/WSL detachment smoke of a trivial command may
be used if needed to verify host behavior. No `sts_lightspeed` scale run, T064
teacher/training rerun, or fixed-cohort evaluation is required.

## Lifecycle And Next Research Step

T071 is a short engineering prerequisite before revising T065 for publication.
T065 remains the research direction selected by T064 Case B. After T071 merges,
the planner should re-read T061/T064 evidence and revise T065 with concrete
supported screens, source scale, continuation-target budget,
training/evaluation gates, parallelism, and long-job execution using the
simplified conventions.

## PR Report

The final PR report must include:

- task ID, approved specification commit, implementation commit, and merge base;
- exact line-count scope, command, and before/after totals;
- the T044 validation responsibility moved/reused and any other material
  simplification;
- the retained correctness/scientific checks;
- confirmation that accepted T064 schemas/results were unchanged;
- stage/run reuse compatibility tests;
- detached-job start/status/success/failure evidence and one coarse ETA example;
- exact verification commands/results;
- confirmation that T065 was not implemented in this task.
