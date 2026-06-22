# T011: Tactical Feature Contract V2

Status: `DONE`.

## Objective

Upgrade the public tactical battle representation and state-action input
contract so later models can distinguish strategically different states and
actions without receiving hidden information.

## Current Main Baseline

`main` has fixed-size snapshot features and legal-action features sufficient
for plumbing smokes. The representation is not a stable versioned feature
contract and is too limited for serious model training. T003 now provides
versioned trainer-input artifacts, explicit migration, controller provenance,
and occurrence-disambiguated action identities for this task to extend.

## Dependencies

- T003 is complete. This task has no remaining implementation dependency.

## Scope

- Define a versioned public tactical feature contract.
- Preserve explicit ascension.
- Encode card identity, upgrade/state information, pile membership, and visible
  card-instance properties needed for decisions.
- Encode monster identity, current move/intent, visible status, and public
  state-machine information without hidden future moves or RNG.
- Encode player powers, relic identities and visible counters, potion
  identities, energy, block, HP, max HP, turn, and other public tactical fields.
- Encode complete legal-action identity and target/action parameters.
- Preserve separate structured state and action inputs so models can learn
  state-action interactions.
- Version trainer-input and model-input schemas and migrate supported legacy
  fixtures explicitly.
- Audit CommunicationMod/live-runtime availability for required public tactical
  fields and legal-action fields. Classify each field as shared, live-missing,
  simulator-only, or explicitly unsupported.
- Report missing public fields and unknown identities rather than silently
  collapsing them.

Task-owned implementation boundaries are `src/sts_combat_rl/sim/features.py`,
`src/sts_combat_rl/sim/model_input.py`, the tactical portions of
`src/sts_combat_rl/sim/trainer_input.py` and `decision_record.py`, their tests,
and a focused feature-audit command if required. T011 must not implement the
live CommunicationMod controller; it only defines and audits the shared public
contract consumed later by T013.

## Out Of Scope

- Complete run history and route context, which belong to T015/T016.
- Learned deck-quality summaries or hand-written strategic deck ratings.
- PyTorch model implementation or training.
- Hidden draw order, hidden RNG, or unrevealed monster moves.

## Design Constraints

- Features are normal-public information only.
- Identity vocabularies have explicit unknown handling and versioning.
- Variable-length entities remain structured until the model-input boundary.
- Feature changes require a new schema version and migration impact report.
- Do not create a simulator-only feature contract. Fields unavailable from the
  live CommunicationMod path require explicit missing-value behavior and a
  documented impact on runtime deployment.

## Deliverables

- Versioned tactical state/action schema.
- Updated trainer-input and model-input packing.
- Tests covering monster/card/relic/potion identity, targets, ascension, unknown
  values, and hidden-field exclusion.
- Feature coverage and missing-field report on real WSL A20 samples.
- Simulator/live tactical-field parity report that T013 can consume.

## Acceptance Criteria

- States differing only in required visible identities or intents produce
  distinguishable inputs.
- Actions with duplicate public IDs or different targets remain distinguishable.
- No forbidden hidden field reaches the feature contract.
- Existing supported artifacts migrate explicitly or fail with a clear reason.
- Required live-unavailable fields are represented through documented
  missing-value paths rather than silently collapsed or guessed.
- Standard local gates and the documented WSL coverage audit pass.

## Required Verification

Run the standard local gates. In addition, run the existing WSL simulator smoke
at A20 and a task-provided, documented WSL feature-coverage audit over real
A20 snapshots. The audit output must include the feature schema version,
identity/unknown counts, missing-field counts, and the simulator/live field
parity classification. It must fail clearly when a required public field is
silently dropped.

## Legacy Reference

Consult selectively:

```text
src/sts_combat_rl/sim/features.py
src/sts_combat_rl/sim/trainer_input.py
src/sts_combat_rl/sim/model_input.py
src/sts_combat_rl/sim/model_scoring.py
tests/test_sim_features.py
tests/test_battle_agent.py
```

## PR Report

Include schema versions, feature inventory, unknown/missing-field counts,
simulator/live parity status, forbidden-field audit, migration impact, and exact
verification results.

## Completion Record

Merged to `main` in PR #6 on 2026-06-21.

- Implemented `public-tactical-v2`, `trainer-input` dataset v3, and model-input
  batch v2, with sequential migration of supported v1/v2 artifacts.
- Added explicit normal-public state/action structures, occurrence-safe public
  action identities, hidden-field exclusion checks, and simulator/live parity
  audits.
- The authoritative simulator projection now includes discard/exhaust members,
  canonical intent category plus exact simulator current move, and battle relic
  identities/counters. Shared required projections fail the WSL audit when
  absent.
- Verification: 274 Windows tests, compileall, Ruff, mock protocol smokes, a
  fresh-Windows-worktree WSL patch-stack build, an A20 simulator audit (81
  snapshots, 497 actions), and a captured CommunicationMod audit (3,347
  snapshots).

T013 consumes this contract to provide the live action/command adapter. Its
live-missing fields remain explicit and must not be reconstructed locally.
