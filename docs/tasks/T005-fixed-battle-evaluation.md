# T005: Fixed Structural Battle Evaluation

Status: `BLOCKED` by T004.

## Objective

Provide deterministic, structurally selected battle cohorts and controller
evaluation so later policy and search changes can be compared credibly.

## Scope

- Freeze evaluation cohorts deterministically using structural strata only.
- Restore and play each selected battle with one explicit controller.
- Report natural-weighted, encounter-macro, room-type-macro, and per-stratum
  results separately.
- Report missing and under-covered strata.
- Preserve cohort schema, source checkpoint, controller provenance, simulation
  budget, and selection rule.

## Out Of Scope

- Strategy-quality filters, search implementation, training, constructed
  states, or full-run policy evaluation.
- Silently filling missing strata.

## Acceptance Criteria

- Re-freezing the same pool and configuration produces the same cohort.
- Evaluation from the same cohort, controller, and seed is reproducible.
- A battle-start checkpoint is never counted as a win without evaluation.
- All report weightings remain separately visible.
- Required local and WSL restored-battle gates pass.

## Legacy Reference

Consult selectively:

```text
src/sts_combat_rl/sim/fixed_evaluation_set.py
src/sts_combat_rl/sim/fixed_battle_evaluation.py
tests/test_fixed_evaluation_set.py
tests/test_fixed_battle_evaluation.py
```
