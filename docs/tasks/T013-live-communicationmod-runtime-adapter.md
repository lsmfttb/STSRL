# T013: Live CommunicationMod Runtime Adapter

Status: `READY`.

## Objective

Build the live-game runtime bridge that lets a trained, search, or scripted
battle `OnlineController` act in the real Slay the Spire process through
CommunicationMod while using the same public decision and legal-action contract
as simulator training.

This task is a deployment-compatibility gate. Simulator-only RL training does
not require it, but any claim that a controller is live-game runnable does.

## Current Main Baseline

`main` has:

- CommunicationMod-style stdin/stdout protocol plumbing and mock fixture smokes;
- centralized protocol command formatting;
- simulator-side controller contracts and controlled complete-run execution;
- the versioned `public-tactical-v2` structured state/action contract, its
  explicit simulator/live parity report, and versioned trainer/model-input
  artifacts.

`main` does not yet have a live runtime adapter that converts a real
CommunicationMod combat observation into the same decision/action interface used
by trained or search controllers.

## Dependencies

- T003, for current decision records, action identity, duplicate-action
  disambiguation, and persisted controller provenance.
- T011, for the stable tactical feature and legal-action contract that both
  simulator and live-game runtime paths must share.

## Scope

- Parse player-visible CommunicationMod combat snapshots into the published
  public battle decision context.
- Build the legal action list from CommunicationMod-visible legal commands,
  preserving stable public identity, duplicate occurrence, target parameters,
  and the raw command payload needed to emit the selected action.
- Invoke a configured battle `OnlineController` through the same selection
  interface used by simulator-side decisions.
- Map the selected legal action back to a CommunicationMod protocol command via
  the centralized protocol formatter.
- Emit runtime decision records or logs with controller provenance, source
  format, information regime, selected action identity, missing fields,
  unsupported fields, and fallback decisions.
- Provide an explicit boundary for non-combat states: route them to a named
  non-combat fallback or return an unsupported-state record. Do not silently
  treat non-combat pages as battle decisions.
- Add captured or fixture-based CommunicationMod combat samples that cover
  attacks, skills, powers, targeted actions, duplicate playable cards, end turn,
  and at least one unsupported or partially missing field case.

## Out Of Scope

- Training a model or changing search strength.
- Implementing non-combat strategy.
- Reconstructing Slay the Spire mechanics locally.
- Calling `sts_lightspeed` during live play to invent legal actions from a live
  observation.
- Complete public run history and visible-route context beyond fields already
  published by prior tasks.
- UI automation outside CommunicationMod.
- Claiming live-game performance or A20 readiness.

## Design Constraints

- The live adapter is normal-public only. It must not receive hidden RNG,
  hidden draw order, unrevealed future encounters, or hidden Boss information.
- Simulator and live runtime paths must share the same tactical feature and
  legal-action contract. Any field unavailable from CommunicationMod must be
  explicit in the parity report and represented with a documented missing-value
  path.
- stdout remains reserved for CommunicationMod protocol commands. Runtime
  diagnostics go to stderr or a configured log sink.
- Unsupported states fail closed with a structured reason and either no action
  or a named fallback action. The adapter must not emit an arbitrary command
  after a mapping failure.
- Command formatting stays centralized in
  `src/sts_combat_rl/comm/protocol.py`.
- The adapter must preserve action identity strongly enough for T003 replay and
  decision-record compatibility.

## Deliverables

- Live CommunicationMod runtime adapter code under the communication/controller
  boundary.
- A command or command path that consumes a CommunicationMod message, invokes a
  configured battle controller, and emits exactly one protocol command or a
  structured unsupported-state outcome.
- Fixture or captured-sample tests for live combat state parsing, feature
  parity, legal-action identity, duplicate action disambiguation, target
  mapping, command emission, provenance logging, and fail-closed behavior.
- A simulator/live tactical-field parity report for the T011 contract.
- Documentation updates only where needed to describe the live adapter command
  and its limitations.

## Acceptance Criteria

- A controller implementing `OnlineController` can be invoked on a captured
  CommunicationMod combat snapshot without requiring a simulator instance.
- The selected legal action maps to the exact CommunicationMod command payload
  for card play, target selection, potion-compatible action categories when
  present, and end turn.
- Duplicate visible legal actions remain distinguishable from observation
  through decision record and emitted command.
- Unsupported or incomplete observations produce a structured failure/fallback
  record and do not emit arbitrary gameplay commands.
- Runtime records include complete controller provenance and live source
  metadata required by T003.
- The parity report states which T011 tactical fields are shared, missing, or
  simulator-only, with no silent feature collapse.
- Standard local gates and the CommunicationMod fixture smokes pass.

## Required Verification

Run the standard local checks plus focused live-adapter tests.

No mandatory interactive live-game gate is required for acceptance because that
environment is not always available to task implementers. If an implementer runs
an interactive CommunicationMod smoke, the pull-request report must include the
exact setup and result.

## Legacy Reference

Consult current `main` and, if useful, selectively inspect the legacy reference
commit for protocol or fixture ideas. Do not port broad policy, training, or
simulator-side code into this task.

Relevant current areas:

```text
src/sts_combat_rl/comm/protocol.py
src/sts_combat_rl/comm/stdio_client.py
src/sts_combat_rl/controller.py
src/sts_combat_rl/sim/features.py
tests/fixtures/
tests/test_stdio_client.py
tests/test_protocol.py
```

## PR Report

Include:

- controller configuration tested;
- captured or fixture sample inventory;
- simulator/live field parity report;
- action-mapping and duplicate-action evidence;
- unsupported-state behavior;
- provenance and decision-record schema compatibility notes;
- exact verification commands and results;
- whether any interactive live-game smoke was run.
