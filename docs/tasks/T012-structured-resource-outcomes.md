# T012: Structured Battle Resource Outcomes

Status: `READY`.

## Objective

Preserve battle result, terminal absolute HP, and persistent battle-end
resources as a versioned structured outcome. Future continuation models must be
able to value these components contextually instead of inheriting one fixed
hand-written reward weight.

## Current Main Baseline

`main` has battle-segment reward diagnostics, T004 completed-battle outcome
labels, and T005 fixed-evaluation reports, but no complete public terminal
resource snapshot or structured outcome schema. T016 establishes the
corresponding sanitized starting public context and history in current
artifacts.

## Dependencies

- T003, T004, T005, T010, T016, and T017 are complete.

## Scope

- Define a versioned structured battle-outcome schema with independent fields
  for authoritative battle result, terminal absolute current HP, terminal max
  HP, gold, potion slots/identities, deck/card changes including curses, relic
  identities/additions/removals and exposed persistent counters, keys, and
  other exposed persistent resources.
- Capture sanitized before/after public resource snapshots through authoritative
  simulator data at the exact battle boundary. Preserve both terminal snapshots
  and derived component deltas where derivation is possible; missing values and
  unavailable counters must remain field-level explicit.
- Persist the outcome through checkpoint-derived records, battle decision and
  trainer-input artifacts, and fixed-evaluation reports. Provide sequential
  migrations for supported historical schemas and explicit loss for unrecoverable
  terminal fields.
- Report component presence, change frequency, missing native coverage, and
  terminal outcome counts separately. Keep any existing scalar reward report as
  an optional diagnostic view with clearly separate provenance.
- Add focused native projection patches only for missing authoritative public
  terminal fields. Do not infer a counter or inventory identity from local game
  rules.

## Out Of Scope

- Learning a continuation value, adding PyTorch heads, choosing permanent
  component weights, potion-use policy, complete run-history implementation, or
  hidden relic counters.
- Replacing an authoritative terminal loss/win label with a scalar reward or
  normalizing current HP by max HP.

## Design Constraints

- Death, terminal absolute current HP, and every resource component are
  independently inspectable labels. `current_hp / max_hp` is never a stored
  target or replacement for absolute HP.
- Inventory identity/order and exposed counters must remain distinguishable
  from count-only summaries. Unknown, absent, and empty must not collapse.
- Normal-public artifacts receive only player-visible/authoritatively exposed
  terminal data. Oracle-like source provenance remains separately declared.
- The dedicated outcome schema may reference T016 context but must not duplicate
  its entire typed history or create a second public-context contract.
- Writers emit the current schema only; readers migrate before business logic
  and never guess a missing terminal identity or counter.

## Deliverables

- Structured outcome schema, sanitizers, validators, reader/writer, and
  migrations.
- Authoritative before/after resource capture surface and focused adapter/patch
  support.
- Integration with decision/trainer artifacts and T005 fixed-evaluation reports.
- Component-level report, fixtures, and WSL resource-outcome audit.

## Acceptance Criteria

- Records round-trip without losing terminal battle result, absolute current HP,
  known identities, slot order, exposed counters, or explicit missingness.
- Death, HP, gold, max HP, potion, deck/curse, relic/counter, key, and other
  exposed components can be inspected independently; no required component is
  permanently scalarized.
- Terminal records cannot be marked successful solely from a missing/nonterminal
  outcome; error and unavailable states are reported separately.
- Fixed-evaluation output names the structured outcome schema/version when it
  is present and explicitly reports unavailability for older cohorts.
- Reports list per-component availability/change counts and every unsupported
  native field.
- Legacy artifacts migrate with explicit loss and current-schema output passes
  validation without raw simulator state.

## Required Verification

Run the standard local gates, focused schema/migration tests, decision/trainer
round trips, and fixed-evaluation integration tests. The task must add and run
a WSL `--lightspeed-battle-resource-outcome-audit` command against a bounded A20
pool and report terminal outcomes, component presence/change counts, missing
fields, controller provenance, and source distribution. The PR report must
include the exact command and results; a small audit validates plumbing only,
not continuation-value quality.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_run_resource_snapshot.patch
src/sts_combat_rl/sim/resource_outcome.py
tests/test_resource_outcome.py
```

The legacy implementation may contain useful native projection work but lacks
the T005/T016 current contracts. Port selectively and preserve explicit
missingness rather than filling gaps from old fields.

## PR Report

Include task ID, schema inventory, native field coverage, migration losses,
component change/missing counts, fixed-evaluation compatibility, exact local and
WSL verification, legacy files consulted, known limitations, and any unmet
acceptance criterion.
