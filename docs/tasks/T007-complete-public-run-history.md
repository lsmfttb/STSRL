# T007: Complete Public Run History

Status: `BLOCKED` by T002, T003, and T004.

## Objective

Preserve a typed, ordered, versioned history of all player-visible run facts
and the complete visible map so future battle decisions can value persistent
resources without receiving hidden information.

## Scope

- Define a strict sanitized public-run-history schema.
- Record all visible room visits, route choices, battles and outcomes, events
  and choices/results, rewards and skips, shops, rests, card/relic/potion/key
  decisions, and other visible decisions.
- Preserve the complete currently visible map, available routes, current node,
  and visible Act Boss.
- Carry history through checkpoints, decision records, and model-input boundary
  without re-extracting from unrestricted raw snapshots.
- Add native player-visible screen projections where the adapter lacks public
  data.
- Make missing public fields explicit.
- Add forbidden-field audits for RNG, unrevealed encounters, hidden draw order,
  hidden Act-3 second Boss, and other hidden state.

## Out Of Scope

- A model encoder that consumes the history.
- Long-term policy training.
- Storing raw unrestricted simulator state as normal-agent input.
- Treating battle-tactical state delegated to the battle snapshot as missing
  run history.

## Acceptance Criteria

- Fresh controlled runs preserve complete available public history through
  checkpoint restore and decision persistence.
- Public projections do not silently drop declared visible fields.
- Forbidden hidden fields are absent.
- Missing native coverage is explicit and blocks claims of complete context.
- Historical artifacts without full history migrate with explicit loss.
- Required local and real WSL audits pass.

## Legacy Reference

The legacy implementation contains known review issues and must be corrected,
not copied blindly. Consult selectively:

```text
patches/sts_lightspeed_public_run_context.patch
patches/sts_lightspeed_public_visible_screen.patch
src/sts_combat_rl/sim/public_run_context.py
src/sts_combat_rl/sim/public_run_history.py
tests/test_public_run_context.py
tests/test_public_run_history.py
```

Known legacy issues include inconsistent visible-screen schema naming,
incomplete recursive allowlists, and battle-screen completeness semantics.
