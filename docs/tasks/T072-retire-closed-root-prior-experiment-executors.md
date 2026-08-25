# T072: Retire Closed Root-Prior Experiment Executors

## Objective

Remove the task-specific executable/test surface for the closed T053--T059
root-prior investigation before starting T065. Preserve the reusable root-prior,
search, cohort, artifact-reader, and public-policy capabilities that remain part
of the forward codebase.

This is a retirement/deletion task, not another abstraction refactor. Its purpose
is to make `main` materially smaller after a completed experimental branch has
been closed and superseded.

## Why This Task Exists

T059 closed the root-prior allocation-repair route after the repair failed to
improve the harmful T052/T053 subsets. T061 then replaced that branch with the
reachability-bottleneck decomposition and selected the later Search-v2 / data /
non-combat path. T064 and T071 are complete, and the next intended research task
is T065. No current draft successor depends on executing T053--T059 again.

At the T071-complete main baseline, the closed route still occupies a large
production/test surface:

- seven task-specific `sim/t053_*` through `sim/t059_*` modules total about
  435 KiB;
- seven matching task-specific command modules total about 55 KiB;
- seven matching task-specific test modules total about 164 KiB;
- parser, validation, dispatch, and lightspeed command plumbing still exposes
  the historical experiments in the current CLI.

The directly enumerated files therefore account for about 654 KiB before CLI
plumbing. Keeping all of this executable on forward `main` is no longer justified
by the current research plan.

## Baseline And Historical Reproduction

Frozen pre-retirement source anchor:

`09f58a7352f8dd860c2ed1d7f2b59beacb61d648`

This commit is the post-T071 `main` baseline and retains the complete T053--T059
executors and tests. The T053--T059 task documents remain in the repository as
the durable scientific record. A historical experiment that genuinely needs
its original executor can be reproduced by checking out this source anchor (or
the original task/merge commit named by its task history) rather than requiring
forward `main` to preserve every completed experiment CLI forever.

T072 must not copy retired code into an `archive/`, `legacy/`, examples, scripts,
or another Python package. Git history is the archive.

## Dependencies

- T059: closes the allocation-repair route;
- T061: supersedes that route with the accepted bottleneck decomposition;
- T071: establishes the current lightweight workflow and post-T064 cleanup
  baseline.

## Required Retirement Set

Delete these task-specific production modules:

### Simulation/report modules

- `src/sts_combat_rl/sim/t053_root_prior_failure_analysis.py`
- `src/sts_combat_rl/sim/t054_guardrailed_root_prior_repair.py`
- `src/sts_combat_rl/sim/t055_guardrailed_root_prior_scale_validation.py`
- `src/sts_combat_rl/sim/t056_post_t055_root_prior_path_selection.py`
- `src/sts_combat_rl/sim/t057_existing_root_prior_telemetry_diagnostic.py`
- `src/sts_combat_rl/sim/t058_root_prior_selected_action_telemetry.py`
- `src/sts_combat_rl/sim/t059_root_prior_allocation_repair.py`

### Command modules

- `src/sts_combat_rl/commands/t053_root_prior_failure_analysis.py`
- `src/sts_combat_rl/commands/t054_guardrailed_root_prior_repair.py`
- `src/sts_combat_rl/commands/t055_guardrailed_root_prior_scale_validation.py`
- `src/sts_combat_rl/commands/t056_post_t055_root_prior_path_selection.py`
- `src/sts_combat_rl/commands/t057_existing_root_prior_telemetry_diagnostic.py`
- `src/sts_combat_rl/commands/t058_root_prior_selected_action_telemetry.py`
- `src/sts_combat_rl/commands/t059_root_prior_allocation_repair.py`

### Task-specific tests

- `tests/test_t053_root_prior_failure_analysis.py`
- `tests/test_t054_guardrailed_root_prior_repair.py`
- `tests/test_t055_guardrailed_root_prior_scale_validation.py`
- `tests/test_t056_post_t055_root_prior_path_selection.py`
- `tests/test_t057_existing_root_prior_telemetry_diagnostic.py`
- `tests/test_t058_root_prior_selected_action_telemetry.py`
- `tests/test_t059_root_prior_allocation_repair.py`

Remove imports, parser flags/options, validation branches, dispatch branches, and
lightspeed routing that exist only to invoke or configure these retired
executors. The primary routing surfaces to inspect are:

- `src/sts_combat_rl/cli.py`;
- `src/sts_combat_rl/commands/cli_parser.py`;
- `src/sts_combat_rl/commands/cli_validation.py`;
- `src/sts_combat_rl/commands/lightspeed_cli.py`;
- package export files, if they reference the retired modules.

Do not preserve deprecated/no-op CLI aliases for the retired experiment
commands. Their removal is intentional.

## Preserve The Forward Capability Surface

T072 must not delete a module merely because its history contains T047--T059.
Preserve reusable capabilities needed by the current/future research path,
including at minimum:

- `native_root_prior_allocation.py`;
- `root_prior_guided_search.py` and its generic controller/search behavior;
- `root_prior_guided_search_comparison.py` where still referenced;
- Oracle/search telemetry and fixed-cohort primitives;
- T043/T044 model, checkpoint, reader, and validation contracts;
- T052 retained cohort/diagnostic contracts that are still consumed by later
  accepted tasks;
- T061/T062/T064/T067/T068/T069/T070 forward or accepted diagnostic surfaces;
- current public-policy and public-context contracts.

A T053--T059-named constant or helper embedded in a reusable module may remain if
current code/tests outside the retirement set still need it. If it is used only
by the retired route, delete it. Do not force a broad rename or redesign merely
to remove a historical task number.

## Documentation Contract

Keep T053--T059 task documents and their scientific conclusions. Add one concise
historical-executor note to each affected task document, or one clearly linked
shared note if that is less repetitive, stating that:

- the task remains DONE and its scientific record is unchanged;
- its task-specific executor was retired by T072;
- executable historical source is available at
  `09f58a7352f8dd860c2ed1d7f2b59beacb61d648`.

Do not rewrite historical results, artifact identities, or decisions.

## Out Of Scope

- T065 implementation or scientific specification;
- retiring T064 or its large curriculum-transfer executor;
- deleting T052, T061, T062, or T067--T070 solely because they are completed;
- deleting generic root-prior/search capabilities;
- changing search/controller/model/simulator semantics;
- changing artifact schema versions or accepted retained artifacts;
- creating a generic archival subsystem, compatibility layer, plugin, registry,
  scheduler, or command framework;
- moving the retired code to another directory instead of deleting it;
- any simulator-scale, training, or evaluation rerun.

T064 remains intentionally out of this task because its curriculum/training and
transfer machinery is recent and may still be useful as a reference while T065
is specified. Its retirement can be reconsidered only after a forward
replacement exists.

## Objective Size Gate

Measure physical lines of all tracked `*.py` files under `src/` and `tests/` at
baseline `09f58a7352f8dd860c2ed1d7f2b59beacb61d648` and at the final head using a
non-wrapping byte/`splitlines()` or `wc -l` method.

T072 passes the size gate only if:

- the final `src + tests` Python total is at least **3,000 physical lines lower**
  than the baseline; and
- all 21 files in the Required Retirement Set are absent; and
- no replacement/archive/stub production surface is added to retain their
  implementation.

Documentation lines do not count toward this gate. Formatting-only line changes
must not be used to manufacture the reduction. The PR report must give the exact
counting command and totals.

This gate is intentionally much stronger than T071's `final < baseline` rule.

## Acceptance Criteria

T072 is accepted only when:

- all 21 required task-specific modules/tests are deleted;
- current CLI help/parser/validation/dispatch no longer exposes T053--T059
  experiment-only commands or retention-manifest commands owned solely by those
  executors;
- no live Python import/reference requires a deleted module;
- generic root-prior allocation/search controllers still import and pass their
  focused tests;
- T061/T062/T064 and T067--T070 focused tests still pass, demonstrating that the
  accepted forward path does not depend on the retired executors;
- T043/T044/fixed-cohort/checkpoint reader tests affected by import cleanup still
  pass;
- accepted artifact schemas and scientific results are unchanged;
- T053--T059 historical documentation points to the frozen source anchor;
- the Objective Size Gate passes with at least 3,000 net Python lines deleted;
- no substantial replacement abstraction is introduced;
- no expensive simulator/training/evaluation rerun is performed.

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

Also run focused forward-capability tests covering:

```text
root-prior/native-root-prior generic tests
T061 bottleneck decomposition
T062 Battle Search v2
T064 curriculum/transfer compatibility
T067--T070 Search-v2 repair/audit path
T043/T044 fixed-cohort/checkpoint surfaces touched by import cleanup
```

The implementer must list the exact test files used in the PR report rather than
invent a new integration harness.

Run a repository search proving that Python source no longer imports any of the
seven retired `sts_combat_rl.sim.t053_*` through `t059_*` modules or their
matching command modules.

No WSL/native simulator run is required.

## PR Report

The final report must include:

- task ID, approved specification commit, implementation commit, and baseline;
- exact deleted-file list;
- exact CLI/parser/validation branches removed;
- any T053--T059-named helper intentionally retained in a generic module and the
  live forward caller that requires it;
- baseline/final `src + tests` Python physical-line totals and net deletion;
- confirmation that no archive/stub/replacement executor was added;
- historical reproduction anchor and documentation updates;
- verification commands/results;
- confirmation that no artifact schema/scientific result changed and no
  expensive experiment reran.

## Next Research Step

After T072 merges, the planner should proceed directly to revising/publishing
T065. Do not insert another cleanup task before T065 unless T072 itself discovers
a concrete forward-path blocker that cannot be safely handled within T065.