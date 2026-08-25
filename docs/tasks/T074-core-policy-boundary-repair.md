# T074: Core Decision/Policy Boundary Repair

## Objective

Repair the core decision, policy, batching, and controlled-run dependency boundary
before adding the learned non-combat subsystem proposed by T065.

This is a behavior-preserving architecture task. Its purpose is not to reduce
historical experiment code again. T072 and T073 already addressed that layer.
T074 addresses a separate repository-health problem found by the mandatory
post-T073 quality review: the current forward runtime contains a real circular
dependency and a broad compatibility barrel that make the next policy feature
more expensive and more likely to duplicate infrastructure.

T074 does **not** authorize T065. After T074 merges, the Planner must review the
remaining repository-quality findings again before deciding whether feature work
may resume.

## Current Main Baseline

The exact planning baseline is post-T073 `main`:

`1eeb9320444a29baaa20b20dd3f30b51eb378c08`

T073 completed the forward-surface cleanup and reduced tracked Python under
`src/ + tests/` to 94,775 physical lines. The post-T073 quality review found that
several important repository-health properties are good:

- core runtime dependencies remain minimal; PyTorch is still an optional
  training dependency;
- no lower-layer production dependency on `commands`/CLI was found in the
  reviewed forward path;
- the standard local suite is green on the accepted T073 report;
- broad exception swallowing is not a general pattern in the reviewed core
  executor; the principal run boundary catches named exceptions and records
  explicit problems.

However, the same review found a core dependency defect that predates the recent
history cleanup.

### Confirmed dependency cycle

`src/sts_combat_rl/sim/controlled_run.py` explicitly documents and works around
this dependency chain:

```text
controlled_run -> policy -> batching -> controlled_run
```

`controlled_run` therefore imports `DecisionContext` lazily instead of importing
its policy-input contract normally. `policy.py` imports `DecisionBatch` and
`DecisionExample` from `batching.py`, while `batching.py` imports
`ControlledRun` and `ControlledRunStep` from `controlled_run.py`.

This is not a theoretical style complaint. T065 will directly extend the
non-combat decision/policy surface, so leaving this cycle in place would make the
new learned-policy contract depend on an already tangled runtime/offline-data
boundary.

### Mixed policy ownership

`src/sts_combat_rl/sim/policy.py` currently owns several different kinds of
responsibility at once:

- the deployable `DecisionContext`, policy decision, and policy/scorer protocols;
- generic online policy implementations;
- offline batch-evaluation types/logic that require `DecisionExample`;
- stochastic non-combat driver configuration and behavior;
- expert non-combat driver configuration and behavior.

The current file is therefore both a low-level runtime contract and a consumer of
higher-level batching types. That ownership pattern is a direct risk for T065,
which should add a learned non-combat implementation without turning the same
module into a larger policy/data/training hub.

### Over-broad package compatibility surface

`src/sts_combat_rl/sim/__init__.py` intentionally maintains a package-level
compatibility barrel. The current regression test freezes exactly **336** names
in `sim.__all__` and verifies `from sts_combat_rl.sim import *` compatibility.
Repository code search found package-barrel imports primarily in compatibility
and contract tests rather than as a required production-internal dependency.

Maintaining hundreds of training, evaluation, report, artifact, controller, and
simulator helpers as one package API makes unrelated module changes appear to be
public-API changes and defeats the otherwise explicit module boundaries.

## Dependencies

- T019 completed the first mechanical CLI/export cleanup.
- T071 completed stage/run-local execution and validation cleanup.
- T072 retired the closed T053--T059 executor chain.
- T073 retired T064/T067--T070 forward-surface experiment ownership and requires
  this post-merge quality decision before T065.

T065 remains DRAFT and is not an implementation dependency of T074.

## Scope

### 1. Create an acyclic low-level decision/policy contract

Establish one neutral low-level module for the deployable decision-policy
contract. The exact filename may be `policy_contract.py`, `decision_context.py`,
or another clear domain name, but the ownership must be explicit.

That low-level contract should own only types/protocols needed by online
selection, including the current equivalents of:

- `DecisionContext`;
- `PolicyDecision`;
- `DecisionPolicy`;
- `ActionScorer`;
- small validation/types that genuinely belong to the same online contract.

The low-level contract must not import:

- `batching`;
- `controlled_run`;
- trainer/model-training modules;
- fixed evaluation/report modules;
- command/CLI modules;
- PyTorch.

`controlled_run` must be able to import the decision context contract normally.
The accepted implementation may not retain a lazy `DecisionContext` import whose
purpose is to break the current `controlled_run -> policy -> batching ->
controlled_run` cycle.

### 2. Separate offline batch-policy evaluation from the online policy contract

Move policy behavior that requires `DecisionBatch` or `DecisionExample` behind an
offline evaluation/batching-facing module rather than importing batching types
into the low-level policy module.

Examples include the current `ReplayChosenPolicy` behavior when it requires a
`DecisionExample`, batch policy selection summaries, and other evaluation-only
logic.

Do not duplicate the decision contract to achieve the split. Online and offline
paths must consume the same low-level `DecisionContext`/policy interfaces.

### 3. Give non-combat drivers explicit domain ownership

Move the current stochastic and expert non-combat driver implementations,
configuration tables, and their helper logic out of the generic low-level policy
contract/module into a clearly named non-combat policy/driver module.

Preserve their current behavior and provenance exactly. This task does not tune
weights, add new screens, change fallback behavior, or introduce a learned
non-combat policy.

The resulting ownership should allow a future learned non-combat controller to
be added beside the existing drivers without editing a monolithic generic policy
contract file or importing rollout batching solely to define a runtime policy.

### 4. Contract package-level `sts_combat_rl.sim` exports

Replace the current 336-name package compatibility barrel with a small,
documented stable surface.

Requirements:

- production-internal code uses direct module imports rather than the package
  barrel;
- `sim.__all__` contains at most **32** names;
- package-level exports are limited to foundational public contracts/adapters
  that are reasonable for an external caller to discover at package level;
- training helpers, task/report builders, artifact migration internals, dataset
  utilities, experiment helpers, and large families of constants are imported
  from their owning modules, not re-exported from `sts_combat_rl.sim`;
- remove the regression test whose purpose is to freeze hundreds of star-import
  names; replace it with a small public-surface test.

Do not create a new compatibility module or forwarding layer that simply moves
the 336 exports elsewhere.

### 5. Add a focused dependency-direction regression guard

Add small tests or a simple static import check covering this repaired boundary.
It must at least prove:

- the low-level decision/policy contract imports neither `batching` nor
  `controlled_run`;
- importing `controlled_run` does not require a lazy policy-contract workaround;
- importing the low-level policy contract does not import PyTorch;
- package-level `sts_combat_rl.sim` import does not pull optional PyTorch into the
  default dependency path.

This should be a focused regression guard, not a general dependency-analysis
framework or new static-analysis dependency.

### 6. Preserve behavior and artifact contracts

Update all current production/test imports to the new ownership while preserving:

- `DecisionContext` field semantics;
- controller selection and selected-index validation;
- stochastic/expert non-combat seeded behavior and provenance;
- trainer/model-input records and current artifact schema versions;
- search/controller behavior;
- CommunicationMod/runtime behavior;
- standard CLI behavior.

Compatibility for in-repository direct imports should be achieved by updating
callers to the authoritative new modules, not by adding permanent forwarding
aliases everywhere.

## Explicitly Out Of Scope

T074 must not become a general repository rewrite.

Out of scope:

- T065 implementation, learned non-combat targets, training, checkpoints, or
  evaluation;
- search algorithm, model architecture, reward, simulator, or controller
  behavior changes;
- CLI command-model redesign or conversion to argparse subcommands;
- retiring additional historical T045/T052/T061/T062 commands solely for code
  reduction;
- broad splitting of unrelated large modules such as `battle_start_pool.py`,
  `torch_policy_value.py`, or `fixed_battle_evaluation.py`;
- replacing the tracked real CommunicationMod captures;
- adding/removing Git history to purge old large blobs;
- adding CI workflows or selecting an open-source license;
- introducing dependency-injection frameworks, plugin systems, service
  locators, registries, or a general import-graph framework;
- adding runtime or development dependencies.

The unresolved items above remain inputs to the post-T074 quality review; their
presence here does not imply they are already selected as separate tasks.

## Design Constraints

- Prefer direct imports and ordinary Python modules over abstractions.
- Fix the dependency direction instead of masking cycles with `TYPE_CHECKING`,
  runtime imports, or string-only types when a normal import can be made
  acyclic.
- A split is successful only if responsibilities become one-directional; moving
  unchanged code among equally coupled modules is not sufficient.
- Do not duplicate schemas, policy types, validation, or non-combat behavior.
- Keep default imports PyTorch-free.
- No new public artifact schema version is expected.
- Existing task/result documents remain historical records; do not rewrite old
  claims because import paths moved.

## Quantitative Maintenance Guard

This task is primarily about dependency/cohesion, not raw LOC, so it does not
require a large repository-wide deletion target. It does require evidence that
we did not solve the problem by adding another abstraction layer.

The PR must report physical Python line counts before/after for:

- `sim/policy.py` and any new policy-contract/non-combat/evaluation modules as one
  combined policy surface;
- `sim/controlled_run.py`;
- `sim/batching.py`;
- `sim/__init__.py`;
- associated focused tests.

The combined touched production boundary above must not increase in physical
Python lines relative to the T074 baseline. `sim/__init__.py` itself must shrink
by at least **70%** in physical lines.

Moving code does not count as simplification for this guard; new files are part
of the combined total.

## Acceptance Criteria

T074 is acceptable only if all of the following are true:

1. The `controlled_run -> policy -> batching -> controlled_run` dependency cycle
   no longer exists.
2. `controlled_run.py` has no lazy import of `DecisionContext` or equivalent
   workaround whose purpose is to avoid that cycle.
3. The low-level decision/policy contract has no dependency on batching,
   controlled-run implementation, trainer/evaluation modules, commands/CLI, or
   PyTorch.
4. Offline batch-policy evaluation depends on the low-level policy contract, not
   vice versa.
5. Stochastic and expert non-combat drivers have explicit non-combat ownership
   outside the low-level generic policy contract.
6. Their representative fixed-seed action selections and provenance remain
   unchanged.
7. `sts_combat_rl.sim.__all__` contains no more than 32 deliberately documented
   foundational names and no broad training/evaluation/report constant families.
8. In-repository production code does not rely on `from sts_combat_rl.sim import
   ...` as an aggregate compatibility path.
9. Default package/core imports do not import PyTorch.
10. Existing artifact schema versions and model/checkpoint compatibility are
    unchanged.
11. No simulator/search/training/evaluation scientific result is regenerated or
    reinterpreted.
12. The combined touched production boundary does not increase in physical
    Python lines, and `sim/__init__.py` shrinks by at least 70%.
13. T065 remains DRAFT.

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

Also run focused checks that demonstrate:

- importing the low-level policy contract leaves `torch` absent from
  `sys.modules`;
- importing `sts_combat_rl.sim` leaves `torch` absent from `sys.modules`;
- the low-level contract module has no `batching`/`controlled_run` dependency;
- the old 336-name star-import compatibility expectation is gone;
- current stochastic/expert non-combat fixed-seed fixtures still select the same
  actions and produce the same provenance;
- controlled-run, batching, online-controller, CommunicationMod adapter,
  trainer-input, model-input, and search-guidance focused tests remain green.

No WSL simulator-scale experiment is required. A small simulator smoke is needed
only if the mechanical import move unexpectedly touches adapter construction or
runtime selection semantics.

## Post-T074 Quality Gate

A successful T074 merge does **not** mean the repository is automatically ready
for feature work.

The Planner must re-review latest `main` with particular attention to the other
post-T073 findings that T074 intentionally leaves out of scope:

- the flat CLI/parser/dispatch surface (`cli_parser.py`, `cli.py`,
  `lightspeed_cli.py`, `cli_validation.py`) and the large `test_cli.py`;
- remaining task-specific or historical report/CLI surfaces such as
  T045/T052/T061/T062 where they are not forward capabilities;
- roughly 71 MB of tracked full CommunicationMod JSONL captures under
  `tests/fixtures/real_samples/` versus the desired lightweight repository and
  the README rule against committed large datasets;
- absence of repository CI despite a substantial local verification contract;
- open-source packaging readiness, including the absence of an explicit license
  decision/file if the repository is to be presented as open source;
- remaining large generic modules, but only where inspection shows mixed
  responsibilities or problematic coupling rather than judging by file size
  alone;
- duplicate low-level I/O/hash helpers only when consolidation would reduce real
  maintenance cost without creating a utility dumping ground.

Only that post-T074 review may decide whether to rewrite/publish T065 or propose
another focused maintenance task.

## PR Report

The implementation PR report must include:

- exact baseline and implementation head;
- dependency graph before/after for the repaired core path;
- old/new ownership of `DecisionContext`, policy protocols, offline batch
  evaluation, and non-combat drivers;
- `sim.__all__` count before/after and the retained package-level names;
- before/after physical line counts required by the quantitative guard;
- fixed-seed non-combat behavior/provenance parity evidence;
- default-import PyTorch isolation evidence;
- standard/focused verification results;
- explicit confirmation that T065 was not implemented;
- known issues intentionally left for the post-T074 quality review.
