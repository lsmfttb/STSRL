# T066: Alternating Joint Policy Improvement And Natural Scale Gate

## Objective

Combine separately auditable battle and non-combat policies through alternating
self-generated improvement and a shared run-continuation value, then decide
whether a large standard-start natural A20 collection is justified.

## Current Main Baseline

The repository routes battle and non-combat controllers separately, but current
training and search experiments do not yet form an iterative complete-run policy-
improvement loop. T060 showed why scale alone cannot substitute for a stronger
generating policy. T062--T065 are intended to supply the battle search, Oracle-
public transfer, curriculum, and learned non-combat components required for a
joint loop.

## Dependencies

- T062 accepted Battle Search v2.
- T063 accepted Oracle-guided public battle learning.
- T064 accepted simulator-generated curriculum.
- T065 accepted learned non-combat policy.

## Inputs And Artifacts

Inputs are only simulator-generated trajectories, checkpoints, search/Oracle
targets, learned checkpoints, and accepted manifests from dependencies. Human
trajectories or human action labels are not permitted.

## Scope

- Keep battle and non-combat controller/checkpoint contracts separate.
- Define one versioned shared run-continuation value interface whose public inputs
  are compatible with both modules.
- Alternate battle-policy improvement, non-combat-policy improvement, and
  standard-start complete-run regeneration under named frozen counterpart
  checkpoints.
- Preserve policy-iteration identity so every trajectory records both child
  checkpoints and target generators.
- Evaluate each iteration on the same standard-start matched A20 seeds without
  assistance, hidden deployment inputs, or bootstrap fallback beyond a published
  unsupported-state limit.
- Define a natural scale gate based on independent Act-3, Act-4, Heart-start, and
  Heart-outcome sources plus compute feasibility and distribution diversity.
- Authorize a 10,000-run or larger collection only when the gate passes.

## Out Of Scope

- A monolithic action space that erases battle/non-combat boundaries.
- Human data, heuristic imitation, or silent use of training-time Oracle inputs in
  deployment.
- Treating curriculum states as natural complete-run performance.
- Automatic controller promotion without held-out matched-seed evidence.

## Design Constraints

- Every iteration has immutable checkpoint, source, target-generator, simulator,
  and information-regime provenance.
- Shared run value does not remove separately auditable battle survival, HP,
  potion, gold, deck, relic, key, and progression outcomes.
- Policy updates are compared against frozen previous iterations to avoid
  attributing changes to two moving modules simultaneously.
- Natural scale gates count independent source runs, not repeated checkpoints or
  resampled decisions.

## Deliverables

- Versioned alternating-improvement and shared-value contracts.
- Iteration manifests, training reports, and matched complete-run evaluations.
- Distribution-drift and fallback-use reports.
- A natural scale-gate report that either authorizes one named large collection
  task or keeps scale-up closed.

## Acceptance Criteria

The published task must define iteration count, freeze/update schedule, held-out
seeds, source scales, unsupported-state limits, and natural reachability gates
from accepted dependency evidence. A large collection is not authorized merely
because training loss improves.

## Required Verification

Run standard local gates, checkpoint/provenance round trips, pinned-source
verification, sharded generation/training/evaluation stages, and deterministic
scale-gate aggregation.

## Legacy Reference

Consult the accepted T061--T065 reports and the complete-run/provenance contracts
from T002, T003, T015, T016, T039, T042, and T050.

## PR Report

Report every iteration and child checkpoint, target and source identities,
matched-seed outcomes, distribution drift, fallback use, compute cost, gate
cells, verification, limitations, and the single scale-up decision.
