# T001: Main Quality Baseline

Status: `DONE` via PR #1, merged 2026-06-15.

## Objective

Make the existing `main` branch pass its declared local quality gates without
changing runtime behavior. This removes avoidable formatting noise before
parallel feature work begins.

## Current Baseline

At publication:

- `pytest`: 143 passed;
- `python -m compileall -q src tests`: passes;
- both fixture protocol smokes pass;
- `ruff check src tests`: fails on one unused import;
- `ruff format --check src tests`: reports 26 files.

## Scope

- Remove the reported unused import.
- Add Ruff to the `dev` dependency group so the documented checks are
  reproducible after a fresh development install.
- Apply the repository's Ruff formatter to `src/` and `tests/`.
- Preserve all existing behavior and command output.
- Keep the change mechanical and limited to lint/format cleanup.

## Out Of Scope

- Refactors, renames, architecture changes, new features, or runtime
  dependencies.
- Changes to reward behavior, policies, features, schemas, or CLI options.
- Project-level documentation changes.

## Deliverables

- One branch and one pull request containing only the mechanical cleanup.
- A PR report with before/after quality-gate results.

## Acceptance Criteria

- The diff contains no intentional behavior change.
- Existing tests remain unchanged unless formatting modifies layout only.
- All required checks pass.

## Required Verification

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

No WSL simulator gate is required.

## PR Report

Include:

- confirmation that changes are mechanical only;
- exact check results;
- explanation for any non-formatting diff.
