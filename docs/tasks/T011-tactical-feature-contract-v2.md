# T011: Tactical Feature Contract V2

Status: `BLOCKED` by T003.

## Objective

Upgrade the public tactical battle representation and state-action input
contract so later models can distinguish strategically different states and
actions without receiving hidden information.

## Current Main Baseline

`main` has fixed-size snapshot features and legal-action features sufficient
for plumbing smokes. The representation is not a stable versioned feature
contract and is too limited for serious model training.

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
- Report missing public fields and unknown identities rather than silently
  collapsing them.

## Out Of Scope

- Complete run history and route context, which belong to T007.
- Learned deck-quality summaries or hand-written strategic deck ratings.
- PyTorch model implementation or training.
- Hidden draw order, hidden RNG, or unrevealed monster moves.

## Design Constraints

- Features are normal-public information only.
- Identity vocabularies have explicit unknown handling and versioning.
- Variable-length entities remain structured until the model-input boundary.
- Feature changes require a new schema version and migration impact report.

## Deliverables

- Versioned tactical state/action schema.
- Updated trainer-input and model-input packing.
- Tests covering monster/card/relic/potion identity, targets, ascension, unknown
  values, and hidden-field exclusion.
- Feature coverage and missing-field report on real WSL A20 samples.

## Acceptance Criteria

- States differing only in required visible identities or intents produce
  distinguishable inputs.
- Actions with duplicate public IDs or different targets remain distinguishable.
- No forbidden hidden field reaches the feature contract.
- Existing supported artifacts migrate explicitly or fail with a clear reason.
- Standard local gates and the documented WSL coverage audit pass.

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
forbidden-field audit, migration impact, and exact verification results.
