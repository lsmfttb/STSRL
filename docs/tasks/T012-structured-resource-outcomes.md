# T012: Structured Battle Resource Outcomes

Status: `BLOCKED` by T004 and T010.

## Objective

Preserve battle-end persistent resources as a structured outcome vector so
future continuation-value learning can value them contextually instead of using
fixed hand-written reward weights.

## Current Main Baseline

`main` reports simple battle-segment deltas such as HP, max HP, gold, and potion
count. It does not preserve complete persistent identities and counters or a
versioned structured outcome schema.

## Scope

- Define a versioned structured battle outcome containing:
  - battle result;
  - terminal absolute current HP;
  - potion identities and slot changes;
  - gold and max-HP changes;
  - persistent deck changes and curses;
  - relic additions/removals and exposed persistent counters;
  - keys and other exposed persistent resources.
- Capture before/after public resource snapshots through authoritative
  simulator data.
- Preserve components separately through decision/training records.
- Report per-component presence, missing native fields, and change frequency.
- Keep any scalar reward report as a separate diagnostic view.

## Out Of Scope

- Learning continuation value or PyTorch heads.
- Choosing permanent fixed weights for resource components.
- Complete run history, hidden counters, or local game-mechanics inference.

## Design Constraints

- Terminal HP is absolute, never normalized by max HP.
- Missing native fields remain explicit.
- Battle death and persistent resource outcomes remain separate labels.
- Only player-visible or authoritative terminal outcomes enter normal data.

## Deliverables

- Structured outcome schema and persistence.
- Native patch files only for missing authoritative public resource fields.
- Component-level reports and tests.
- Real WSL battle collection audit.

## Acceptance Criteria

- Outcome records round-trip without losing identities or exposed counters.
- Death, absolute HP, and each persistent resource component remain separately
  inspectable.
- No component is permanently collapsed into one scalar target.
- Missing fields and unsupported counters are reported.
- Standard local gates and documented WSL resource audit pass.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_run_resource_snapshot.patch
src/sts_combat_rl/sim/resource_outcome.py
tests/test_resource_outcome.py
```

## PR Report

Include the schema inventory, native field coverage, component change counts,
missing fields, and exact verification results.
