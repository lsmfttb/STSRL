# T006: Oracle Search Teacher Pipeline

Status: `BLOCKED` by T003, T004, and T005.

## Objective

Integrate the native full-simulator-state battle search as an explicitly
Oracle-like teacher and evaluate it on fixed battle cohorts.

## Scope

- Expose native root action statistics and search-selected actions.
- Label the controller and all generated artifacts
  `full_simulator_state_oracle_like`.
- Default direct root selection to `highest-mean`; retain visits separately.
- Preserve one-hot teacher actions, soft root-visit targets, and DAgger behavior
  actions as distinct fields.
- Collect search-teacher records from battle-start pools.
- Evaluate search budgets and selection rules on fixed cohorts.
- Report simulations, simulator steps, wall-clock time, visits, means, and
  controller provenance.

## Out Of Scope

- Reporting Oracle search as normal-information performance.
- Normal belief search, SL-enabled restart search, or broad neural training.
- Treating random terminal playout count as exhaustive search.

## Acceptance Criteria

- Hidden-state information regime is explicit in controller, dataset, and
  evaluation outputs.
- Teacher and behavior actions cannot be confused.
- Fixed-set comparisons distinguish `highest-mean` and visit-based selection.
- Search dataset records preserve source checkpoints and sampling components.
- Required local and WSL search/evaluation gates pass.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_battle_search_teacher.patch
patches/sts_lightspeed_battle_search_root_actions.patch
src/sts_combat_rl/sim/search_policy.py
src/sts_combat_rl/sim/search_selection.py
src/sts_combat_rl/sim/search_teacher.py
src/sts_combat_rl/sim/expert_iteration.py
tests/test_search_policy.py
tests/test_search_teacher.py
tests/test_expert_iteration.py
```
