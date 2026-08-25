# T073: Forward Surface Health Gate

## Objective

Make the current `main` a safer base for the next trainable subsystem by
separating durable forward capabilities from completed experiment executors and
removing task-numbered ownership from reusable production code.

T072 removed one clearly closed experiment chain. T073 addresses the next
structural layer: completed T064 and T067--T070 experiment orchestration still
occupies the maintained command, CLI, script, test, and validation surface, and
some reusable code is still owned by task-numbered modules.

This is a behavior-preserving maintenance task for retained forward
capabilities. It must materially reduce the amount of historical experiment code
that future work has to understand or extend. It does not implement T065 or any
new model, controller, search algorithm, simulator behavior, or experiment.

T073 is deliberately **not** the final declaration that repository quality is
healthy. After T073 merges, the Planner must perform a fresh repository-wide
code-quality review before deciding whether T065 or any other feature task may
be proposed for execution.

## Frozen Baseline

The specification branch starts from post-T072 `main` commit:

`d0a06b6fa4900047b9f4cf5fa1c5dc2d96047c8c`

T072 already removed the closed T053--T059 executor chain. Its accepted size
audit reduced tracked Python under `src/` and `tests/` from 131,545 to 111,629
physical lines while preserving the generic root-prior/search surface.

The remaining maintenance problem is different. Current `main` still contains
large completed-task execution surfaces, including approximately:

- `src/sts_combat_rl/commands/t064_curriculum_transfer.py`: 173 KiB;
- `src/sts_combat_rl/commands/t070_search_v2_audit.py`: 76 KiB;
- `src/sts_combat_rl/commands/t062_battle_search_v2.py`: 68 KiB;
- `src/sts_combat_rl/commands/t069_public_context_projection.py`: 32 KiB;
- `src/sts_combat_rl/commands/t067_battle_search_v2.py`: 19 KiB;
- T068 task-specific command modules: about 17 KiB combined;
- `src/sts_combat_rl/commands/cli_parser.py`: 55 KiB;
- `src/sts_combat_rl/commands/lightspeed_cli.py`: 55 KiB;
- `src/sts_combat_rl/commands/cli_validation.py`: 26 KiB.

T064 additionally retains a roughly 53 KiB simulator contract/report module and
an approximately five-thousand-line task-specific test file. Current code search
also shows that non-T064 modules consume helpers from T064-owned code, so simple
file deletion is not sufficient: genuinely reusable responsibilities must first
move to neutral domain ownership.

Completed T067--T070 command modules are primarily referenced by their own
historical run/merge/finalize scripts and tests. Their durable capabilities live
elsewhere, such as generic Search v2, public-context projection, controller,
cohort, checkpoint, and evaluation modules.

No correctness failure is currently known. The risk is maintenance structure:
if T065 is implemented on top of this shape, the shortest implementation path is
to create another large `t065_*` vertical stack containing contract, collection,
training, evaluation, validation, orchestration, and reporting logic. T073 exists
to remove that incentive before feature development resumes.

## Dependencies

- T019 mechanical refactor is complete.
- T062 Search v2 capability is complete and must remain available where it is a
  durable forward capability.
- T064 is complete with accepted negative Case B evidence.
- T067--T070 are complete diagnostic/repair tasks.
- T071 established reusable validation ownership and detached long-job
  conventions.
- T072 established Git history as the executable archive for retired completed
  experiment paths.

T065 remains `DRAFT` throughout T073.

## Repository Model Used By This Task

T073 distinguishes three kinds of code.

### 1. Durable forward capability

Code that current or reasonably near-term work is expected to call directly,
such as:

- simulator and public-state contracts;
- `OnlineController` and controlled-run execution;
- generic Search v2 behavior and cost/report primitives;
- generic public-context projection and model-input support;
- checkpoint, teacher/trainer, fixed-cohort, evaluation, and search telemetry
  contracts that remain part of the maintained architecture;
- generic root-prior/native-search surfaces intentionally preserved by T072.

This code remains on `main` even when it was originally introduced by a numbered
task. If its current owner is a task-numbered module, T073 may move the reusable
responsibility to a neutral domain module.

### 2. Completed experiment executor

Code whose purpose is to reproduce one already-decided experiment rather than to
provide a maintained capability, including task-specific:

- freeze/preflight/orchestration stages;
- shard launch/merge/finalize helpers;
- one-off report builders and terminal decision aggregators;
- task-numbered CLI flags and routing;
- executor-only schema glue;
- task-only regression tests that test the retired executor rather than a
  retained generic contract.

This code should normally leave forward `main`. Git history plus the task
scientific record is the archive.

### 3. Shared capability hidden inside a completed-task module

A function, type, validator, or contract may have gained real forward callers
after being created for one task. T073 must not delete it merely because its
module name contains a task number. It must instead either:

- move the minimal reusable responsibility to the correct neutral owner and
  update callers; or
- document why a task-numbered compatibility reader must temporarily remain.

Copying the same logic into a new neutral file while retaining the old forward
copy does not satisfy this task.

## Scope

### 1. Retire T064 experiment execution and transfer orchestration

Audit all current callers of:

- `src/sts_combat_rl/commands/t064_curriculum.py`;
- `src/sts_combat_rl/commands/t064_curriculum_transfer.py`;
- `src/sts_combat_rl/sim/t064_curriculum.py`;
- `scripts/*t064*`;
- `tests/test_t064_curriculum.py`;
- T064-specific parser, validation, dispatch, and export branches.

The T064 training/curriculum/transfer experiment is complete and is not a
forward runtime capability. Retire its executor, stage orchestration, merge /
finalization scripts, task-only CLI, and task-only tests from current `main`.

Before deleting a T064-owned helper that has a live non-T064 caller, move only
the actual shared responsibility to the appropriate neutral domain module. Likely
ownership categories include teacher/trainer contracts, checkpoint validation,
fixed-cohort/T044 evaluation, artifact loading, or generic report validation.
The implementation must derive ownership from the actual call graph rather than
from this list by assumption.

Accepted T064 scientific conclusions and task documentation stay intact. T064
artifacts do not need executable current-main readers merely for historical
reproduction; the frozen pre-retirement Git source is sufficient unless a live
forward caller demonstrably requires the reader.

### 2. Retire completed T067--T070 experiment executor surfaces

Audit and retire historical-only execution code for T067, T068, T069, and T070,
including where applicable:

- task-numbered command modules;
- task-numbered run, shard, merge, semantic-equivalence, freeze, preflight,
  orchestration, and finalization scripts;
- task-specific CLI parser/validation/dispatch branches;
- tests whose only subject is the retired executor;
- task-only report/decision formatting that has no forward reader.

Preserve the durable capabilities those tasks established. In particular, T073
must not remove or semantically change solely because of historical origin:

- generic `battle_search_v2` search behavior;
- current public-context feature projection used by maintained inference/search;
- generic cost/calibration primitives with live forward callers;
- checkpoint/model compatibility contracts;
- fixed-cohort and de-assisted evaluation contracts still used by forward code;
- search telemetry and controller provenance;
- accepted native `sts_lightspeed` integration and tree-geometry capability.

A T067--T070-named helper with a real forward caller may remain only when moving
it would create more maintenance burden than it removes. Such exceptions must be
listed explicitly in the PR report with the concrete caller and reason.

### 3. Remove task-numbered ownership from reusable forward code

After the retirement work, reusable production modules outside the historical
executor surface should not depend on completed-task modules as their normal
source of domain behavior.

The implementation must inspect Python imports and direct qualified uses and
eliminate forward dependencies on T064/T067/T068/T069/T070 task modules where
reasonable by moving the shared responsibility to neutral ownership.

The target dependency shape remains the architecture contract:

```text
simulator/public/controller contracts
    -> concrete policy/search/model controllers
    -> controlled-run execution
    -> dataset/training/evaluation
    -> command handlers
    -> CLI parsing/routing
```

Do not create a generic workflow framework merely to satisfy this rule.

### 4. Shrink the maintained CLI surface

Remove CLI options and routing that exist only to rerun retired T064 and
T067--T070 experiments.

The user-facing CLI should primarily expose maintained capabilities rather than
one flag family for every historical research task. Do not retain deprecated or
no-op aliases merely to preserve historical experiment commands.

Forward generic commands used by current runtime, simulator smoke, maintained
search/evaluation/training capabilities, source verification, and mock fixtures
remain supported.

If a task-numbered command is actually the only supported entry point for a
forward capability, either keep it with an explicit report justification or
move that capability behind an existing/new narrowly named generic command. Do
not perform broad cosmetic CLI renaming unrelated to the retired surfaces.

### 5. Tighten exports only where retirement makes them stale

Remove `sts_combat_rl.sim` or command-package exports that exist only for retired
T064/T067--T070 executor code.

Do not redesign the package export model or break documented generic imports.
Existing generic compatibility imports remain unless they are demonstrably dead.

### 6. Correct project-identity documentation drift

Update directly affected top-level documentation so it describes the current
project rather than the early minimal combat probe.

At minimum review and correct where stale:

- `pyproject.toml` project description;
- `README.md` trainable-scope/current-main description;
- README collaboration wording that no longer matches the current Planner /
  Maintainer single-PR workflow;
- planning/status text directly affected by T073.

This is narrow factual maintenance, not a documentation rewrite.

### 7. Add a post-T073 quality-review gate

The durable planning documentation must state that T073 merge does **not**
automatically authorize or publish T065.

After T073 merges, the Planner must perform a fresh review from latest `main`
covering at least:

- module responsibility and cohesion;
- dependency direction and circular/cross-layer coupling;
- completed-task code still present in maintained surfaces;
- CLI/API surface quality;
- duplicate or near-duplicate implementations;
- error handling and fail-closed behavior;
- validation/provenance complexity relative to realistic scientific risks;
- test organization, overspecification, brittle fixture coupling, and duplicated
  tests;
- large-module readability and change concentration;
- optional dependency isolation and import-time side effects;
- stale compatibility/export layers;
- documentation/code drift;
- obvious dead code and unused abstractions.

The review must classify findings by expected future maintenance cost, not by
style preference or file length alone. Only findings that are concrete,
high-confidence, and cheaper to fix before the next feature than after it should
block feature development.

The Planner then chooses one of two outcomes:

1. return to feature planning and revise/publish a narrower T065 contract; or
2. propose another maintenance task because the fresh review found a concrete
   high-value blocker outside T073's known historical-executor problem.

T073 must not pre-decide that outcome.

## Out Of Scope

- Implementing, publishing, or authorizing T065, T063, or T066.
- Training a model or collecting/evaluating new simulator evidence.
- Changing accepted T064/T067/T068/T069/T070 scientific results.
- Changing Search v2, controller, feature, model, reward, or simulator semantics.
- Changing the pinned `sts_lightspeed` source or native API.
- Removing T052/T061/T062 merely because their names are task-numbered; they
  need independent forward-use analysis and are not the primary retirement set.
- Removing generic root-prior/search code retained by T072 without a separate
  forward-caller justification.
- Reimplementing or reorganizing all large generic modules simply because they
  are large.
- Introducing a plugin system, registry framework, command framework, generic
  workflow engine, DAG scheduler, artifact graph, database, service, or new
  third-party dependency.
- Moving historical executors into `archive/`, `legacy/`, or another package.
- Replacing deleted task modules with compatibility stubs or forwarding wrappers.
- Broad formatting-only or naming-only churn.

## Design Constraints

- **Delete before abstracting.** Historical executor code should disappear rather
  than be generalized unless a current forward caller proves a reusable need.
- **One maintained owner per responsibility.** Moving a shared helper is useful
  only if the old duplicate path disappears.
- **Git is the archive.** Historical experiment reproducibility does not require
  every executor to remain importable from current `main`.
- **Retained behavior is frozen.** Generic forward capabilities preserve existing
  semantics and accepted artifact contracts unless an explicit compatibility
  exception is documented.
- **No T065-shaped infrastructure.** T073 must not anticipate T065 by adding new
  non-combat training abstractions.
- **No security theater.** Do not add hashes, sidecars, attestations, cross-link
  fields, or validation solely to prove a trusted repository producer was not
  malicious. Retain realistic leakage, mismatch, checkpoint compatibility,
  completion, source identity, and scientific-design checks.
- **No relocation-only success.** Moving lines from task modules into generic
  modules without reducing duplicated/historical responsibility does not count
  as retirement.

## Deliverables

- Retired T064 experiment execution/transfer orchestration and historical-only
  scripts/tests/CLI routes.
- Retired historical-only T067--T070 executor surfaces while preserving their
  durable generic capabilities.
- Neutral ownership for any genuinely reusable T064/T067--T070 helper that had a
  live forward caller.
- Retired any task-numbered CLI routes found by the baseline inventory and
  reduced stale export surface.
- Corrected project-identity documentation directly affected by the cleanup.
- Regression coverage for retained generic capabilities and moved shared
  responsibilities.
- A PR report containing the required forward-caller inventory and size evidence.
- Planning text that requires a fresh post-merge code-quality review before T065
  can be reconsidered.

## Acceptance Criteria

### A. Scientific and runtime preservation

- Standard mock combat/non-combat protocol behavior remains unchanged.
- Current generic Search v2 behavior and public-context projection semantics are
  preserved by focused regression tests.
- Current checkpoint/model compatibility and maintained fixed-cohort/evaluation
  readers used by forward code continue to work.
- No accepted scientific result, artifact schema version, native source pin, or
  information-regime definition changes.
- No substantial simulator/training/evaluation rerun is required.

### B. Historical executor retirement

- T064's completed experiment executor and transfer orchestration are no longer a
  maintained current-main workflow.
- Historical-only T067--T070 execution/finalization surfaces identified by the
  implementation call-graph audit are deleted, not moved.
- No new `archive`, `legacy`, compatibility-stub, or replacement task-executor
  package is introduced.
- Deleted historical behavior remains reproducible by checking out the frozen
  T073 baseline or another exact source anchor recorded in the PR report.

### C. Forward ownership

- The PR includes a machine-assisted import/caller inventory for every retained
  `t064_*`, `t067_*`, `t068_*`, `t069_*`, or `t070_*` production Python module.
- Every retained task-numbered production module has at least one concrete
  current forward caller and a documented reason that neutral relocation would
  cost more than it saves.
- Reusable generic modules do not import T064/T067--T070 modules merely for
  convenience after a neutral owner has been established.
- No duplicated old/new copy of a moved validator, parser, contract, or report
  helper remains.

### D. CLI and export health

- CLI flags and dispatch branches whose only purpose was retired T064 or
  T067--T070 execution are absent from `--help` and source routing.
- No deprecated/no-op aliases remain for those retired paths.
- `cli_parser.py`, `cli_validation.py`, and `lightspeed_cli.py` do not grow in
  physical lines relative to the frozen baseline. When the frozen baseline
  contains task-only T064/T067--T070 routes, removing those routes must reduce
  their combined physical line count materially. When the machine-assisted
  baseline inventory proves that no such routes exist, unchanged combined size
  is acceptable and the PR report must record that result explicitly. Do not
  remove maintained T062 or generic Search v2 routes to manufacture a decrease.
- `sim/__init__.py` and command exports contain no stale exports for deleted
  modules.

### E. Strong size gate

Use non-wrapping physical-line counts from Git objects, not terminal display
wrapping.

Relative to frozen baseline
`d0a06b6fa4900047b9f4cf5fa1c5dc2d96047c8c`:

- tracked Python under `src/` + `tests/` must decrease by at least **12,000
  physical lines**;
- tracked Python under `src/` alone must also decrease, so the task cannot pass
  by deleting tests while expanding production code;
- moved code counts at its new location;
- generated files, docs, and formatting changes do not count toward the gate.

If correct forward-caller analysis proves the 12,000-line threshold incompatible
with preserving a genuinely maintained capability, implementation must stop and
request a specification revision rather than weakening the metric in the PR
report.

### F. Quality-review lifecycle gate

- T065 remains `DRAFT` at T073 merge.
- T073 publishes no successor implementation authorization.
- Planning documentation explicitly requires a new post-T073 Planner
  code-quality review before feature development resumes.
- The post-T073 review is a separate Planner decision based on the merged result,
  not an Implementer self-certification inside this PR.

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

- generic Search v2/controller behavior remains available;
- public-context projection/model-input behavior used by current search remains
  available;
- checkpoint/fixed-cohort/T044-style generic validation that still has forward
  callers remains available;
- default CLI import does not import PyTorch;
- retired T064/T067--T070 CLI options are absent;
- deleted modules have no remaining Python imports;
- retained task-numbered modules satisfy the documented caller inventory;
- the `src + tests` and `src` physical-line gates pass.

A small WSL simulator smoke is required only if command cleanup changes a
maintained `sts_lightspeed` routing path. No T064/T067/T068/T069/T070 experiment,
training stage, 93-record comparison, or high-budget audit should be rerun.

## Historical Source Anchor

The complete pre-T073 maintained source is frozen at:

`d0a06b6fa4900047b9f4cf5fa1c5dc2d96047c8c`

Deleted T064/T067--T070 experiment executors remain available through Git history
and their task documents. The PR report may record a later exact implementation
baseline if the Maintainer rebases the branch before specification approval.

## PR Report

The completed PR must report:

- approved specification commit and exact implementation baseline;
- list of deleted T064/T067--T070 source, script, test, CLI, and export surfaces;
- before/after physical lines for all tracked Python under `src`, `tests`, and
  `src + tests`;
- before/after physical lines for `cli_parser.py`, `cli_validation.py`, and
  `lightspeed_cli.py`;
- caller/import inventory for every retained task-numbered production module in
  the T064/T067--T070 range;
- every shared responsibility moved to neutral ownership, its old owner, new
  owner, and forward callers;
- every intentionally retained task-numbered exception and why it is cheaper to
  retain than move;
- exact regression and local-gate results;
- statement that no accepted scientific result or maintained runtime/search /
  model semantics changed;
- confirmation that T065 remains DRAFT and no feature implementation is
  authorized;
- exact Git anchor for historical reproduction of deleted executors;
- any code-quality concern deliberately left for the mandatory post-T073 Planner
  review.

## Post-Merge Planner Decision

After merge, do not automatically revise T065 to `READY`.

The Planner must re-read latest `main`, this implementation report, project
architecture, current status, and the code itself, then perform the repository-
wide quality review listed in Scope 7. The review should not assume that
historical executor accumulation was the only quality problem.

Only after that review should the Planner decide whether the repository is a
healthy lightweight research/open-source base for another feature vertical.
