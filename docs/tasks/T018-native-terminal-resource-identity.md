# T018: Native Terminal Resource Identity Surface

Status: `BLOCKED`.

## Objective

Extend the pinned `sts_lightspeed` source integration so structured battle
outcomes can capture player-visible terminal resource identities and exposed
counters instead of reporting those fields as missing or unavailable.

T012 establishes the schema, artifact propagation, migrations, and explicit
missingness boundary. T018 fills the native/adaptor surface needed for full
identity-bearing terminal resource coverage.

## Current Main Baseline

`main` has the T017-managed source manifest and native verifier. T012 is the
schema/plumbing task for structured outcomes. Before T018, current WSL audits
may still report potion slot identities, deck/curses, relic identities/counters,
and key flags as missing or unavailable.

## Dependencies

- T012 and T017 must be complete.

## Scope

- Extend the pinned external `sts_lightspeed` integration, source manifest, and
  verifier with focused public terminal resource capabilities.
- Expose only player-visible or otherwise authoritatively public terminal
  resources needed by `structured-battle-outcome-v1`: potion slot identities and
  order, deck/card identities including curses, relic identities and exposed
  counters, key flags, and any already-public persistent resource fields needed
  for terminal deltas.
- Update the Python adapter and structured outcome extraction to use the new
  native public fields at battle boundaries.
- Update the WSL resource-outcome audit to distinguish newly available fields
  from remaining native gaps and to fail if a required T018 field silently
  disappears.
- Preserve T012 artifact compatibility. If the structured outcome schema must
  change, add a sequential migration rather than mutating old semantics.

## Out Of Scope

- Hidden relic counters, hidden RNG state, hidden draw order, unrevealed future
  encounters, or any locally reimplemented Slay the Spire mechanics.
- Learning continuation values, changing reward weights, or adding PyTorch
  heads.
- Complete run-history or map/route modeling beyond resource fields needed by
  structured terminal outcomes.

## Design Constraints

- `sts_lightspeed` remains the authoritative simulator implementation. Do not
  infer card, relic, potion, key, or counter identities from local rules.
- Field-level unknown, missing, unavailable, and empty states must remain
  distinguishable.
- Inventory identity/order and exposed counters must not collapse into counts.
- Normal-public artifacts receive only player-visible/authoritatively exposed
  fields. Oracle-like simulator state remains separately declared.
- Extend the T017 source-manifest workflow rather than reviving ad hoc local
  patch-stack development.

## Deliverables

- Updated pinned `sts_lightspeed` integration ref/commit and source manifest.
- Verifier coverage for the new native public terminal resource capability.
- Python adapter and structured outcome extraction updates.
- Focused tests for potion slots, deck/curses, relic identities/counters, keys,
  missingness, migrations if needed, and artifact round trips.
- WSL resource-outcome audit evidence showing component availability and any
  remaining explicitly unsupported native fields.

## Acceptance Criteria

- The canonical source verifier builds the pinned integration commit and asserts
  the new native terminal resource capability.
- Bounded WSL resource-outcome audit reports the T018 identity-bearing fields as
  available where the game exposes them; any remaining unavailable field is
  explicitly justified as not player-visible or not authoritatively exposed.
- Records round-trip without losing potion slot order/identity, deck and curse
  identities, relic identities and exposed counters, key flags, terminal battle
  result, absolute current HP, or explicit missingness.
- No hidden simulator-only field enters normal-public artifacts.
- Existing legacy fixtures still migrate sequentially with explicit loss.
- Standard local gates and relevant WSL smoke/readiness gates pass.

## Required Verification

Run the standard local gates plus focused schema/extraction/migration tests.
Run the canonical source verifier and at least:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-resource-outcome-audit --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-smoke --sim-seed 1 --sim-ascension 20 --sim-steps 200 --log-file -"
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-battle-training-readiness --sim-seed 1 --sim-episodes 3 --sim-ascension 20 --sim-steps 200 --log-file -"
```

## PR Report

Include task ID, source manifest ref/commit, verifier output, native field
inventory, artifact compatibility impact, migration losses if any, exact local
and WSL verification, known limitations, and every unsupported native field.
