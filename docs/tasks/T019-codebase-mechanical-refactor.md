# T019: Codebase Mechanical Refactor

Status: `READY`.

## Objective

Reduce the post-foundation maintenance burden without changing behavior,
artifact schemas, command semantics, simulator contracts, or evaluation claims.

This is a mechanical cleanup task. Its purpose is to make the next research
tasks easier to review by shrinking oversized routing/export surfaces and
clarifying module ownership.

## Current Main Baseline

The foundation backlog is complete. Current `main` passes the standard Windows
quality gates and WSL simulator gates, but the post-backlog maintainer review
identified maintainability risks:

- `src/sts_combat_rl/cli.py` is about 1,700 lines and still owns many argument
  definitions, validations, and command branches.
- Several simulator modules are large and hard to review, especially
  `torch_policy_value.py`, `constructed_battle_start.py`,
  `fixed_battle_evaluation.py`, `features.py`, and `battle_start_pool.py`.
- `src/sts_combat_rl/sim/__init__.py` exposes a broad compatibility surface
  whose intended public imports are not easy to audit.

No correctness blocker is known. The current behavior should be preserved.

## Dependencies

- T001--T006, T008--T018 are complete.
- T007 is cancelled and has no dependency effect.

## Scope

- Decompose CLI parser/routing code so `src/sts_combat_rl/cli.py` becomes a
  small entrypoint for parser construction, dispatch, and top-level error
  handling.
- Move command-specific argument builders, validation helpers, and dispatch
  routing into appropriately named modules under `src/sts_combat_rl/commands/`
  or another narrowly scoped internal CLI-support package.
- Preserve every existing public CLI flag, default, error behavior, stdout /
  stderr boundary, and command output format.
- Audit `src/sts_combat_rl/sim/__init__.py` exports. Keep documented and
  currently tested imports working, but make accidental future export growth
  harder by grouping, documenting, or testing the intended compatibility
  surface.
- Split large simulator modules only when the split is mechanical and follows
  an obvious boundary such as schema/data classes, artifact I/O, report
  formatting, validation, command adapters, or optional PyTorch-only training
  helpers.
- Add or update focused tests for any moved import, parser construction, CLI
  routing, or export compatibility that is not already covered.
- Report before/after line counts for `cli.py`, touched large modules, and
  `sim/__init__.py` in the PR.

## Out Of Scope

- Changing controller behavior, simulator behavior, search behavior, training
  semantics, feature values, artifact schemas, migrations, or evaluation
  aggregation.
- Adding new CLI features or removing existing flags.
- Changing native `sts_lightspeed` source, source manifest contents, WSL build
  behavior, or pinned simulator commits.
- Adding dependencies, Gymnasium, Stable-Baselines3, game files, simulator
  binaries, or large artifacts.
- Broad formatting-only rewrites of unrelated files.
- Reorganizing documentation beyond narrow notes required by this refactor.

## Design Constraints

- This branch must be behavior-preserving. If a desired cleanup requires a
  behavior change, leave it as a follow-up note instead of including it.
- CLI modules remain parsing/routing layers. Reusable workflows belong below
  the CLI layer or in `src/sts_combat_rl/commands/`.
- Optional PyTorch code must stay isolated behind the `train` dependency group.
  Default CLI import and non-training commands must not import PyTorch.
- Existing artifact readers, migrations, fixtures, and public imports must
  continue to work.
- Preserve stdout for protocol commands; use stderr or logs for diagnostics.
- Keep changes independently reviewable. Prefer small compatibility shims over
  sweeping renames when callers or tests already use an import path.

## Deliverables

- Refactored code with `src/sts_combat_rl/cli.py` reduced to at most 1,200
  physical lines.
- Extracted command-specific parser/routing modules or internal CLI-support
  modules with clear ownership names.
- Export compatibility audit for `src/sts_combat_rl/sim/__init__.py`, including
  tests or explicit compatibility comments for retained public imports.
- Focused regression tests for parser/routing/import compatibility affected by
  the refactor.
- PR report with before/after line counts and an explicit no-behavior-change
  compatibility statement.

## Acceptance Criteria

- `src/sts_combat_rl/cli.py` is at most 1,200 physical lines.
- All existing CLI commands used by the standard local gates still produce the
  same stdout behavior.
- Default import of `sts_combat_rl.cli` succeeds without importing PyTorch.
- Existing current-schema artifacts and legacy migration fixtures still load in
  the test suite.
- No public artifact schema version changes are introduced.
- No `sts_lightspeed` source manifest, patch, fork ref, or WSL build command is
  changed by this task.
- The PR contains no research feature, model, search, data-collection, or
  simulator-behavior change.

## Required Verification

Run the standard local gates from `tasks/README.md`:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Also run a focused default-import guard that proves PyTorch is not imported by
the default CLI path. The exact command may be implemented as a small test or
reported as an inline Python check.

WSL simulator gates are not required unless the refactor touches simulator
adapter behavior or WSL command construction.

## Legacy Reference

No legacy feature porting is expected. The main references are current `main`,
`docs/current_status.md`, and `docs/project_architecture.md`.

## PR Report

The pull request must include:

- task ID and link to this document;
- summary of moved modules and preserved compatibility paths;
- before/after line counts for `cli.py`, touched large modules, and
  `sim/__init__.py`;
- exact verification commands and results;
- statement that no behavior, schema, simulator, or evaluation semantics were
  intentionally changed;
- known cleanup follow-ups that were intentionally left out of scope.
