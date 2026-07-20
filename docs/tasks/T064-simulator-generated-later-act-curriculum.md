# T064: Simulator-Generated Later-Act Curriculum

## Objective

Create a later-act curriculum using only authoritative simulator generation,
search, assistance, and simulator-validated transforms, with strict separation
from natural A20 evaluation.

## Current Main Baseline

Natural later-act sources are scarce under current policies. Constructed and
assisted battle-start infrastructure exists, but earlier training over assisted
data did not improve the accepted de-assisted fixed cohorts. The next curriculum
must be tied to a stronger or explicitly diagnosed generating policy and must
preserve distribution identity so that curriculum coverage is not mistaken for
natural reachability.

## Dependencies

- T061 accepted reachability diagnosis.
- T062 accepted search surface when the diagnosis selects battle improvement as
  a prerequisite.
- T008, T039, T042, and T050 distribution, coverage, assistance, and shard
  contracts.

## Inputs And Artifacts

No human trajectory or human action label is permitted. Inputs may include
natural simulator checkpoints, Oracle-reached checkpoints, assisted complete-run
states, and source-linked simulator transforms. The published task must name
eligibility, generation, restore, retention, and deletion contracts.

## Scope

- Define separate `natural`, `oracle_reached`, `assisted`, `transformed`, and
  `constructed` curriculum components.
- Generate later-act states through standard-start runs, high-budget Oracle
  trajectory discovery, restored continuation, versioned assistance schedules,
  or conservative simulator-validated transforms.
- Preserve immutable source identity and every requested/actual change.
- Measure unique source coverage by Act, room, encounter, Boss, resource bucket,
  and public-context availability.
- Define curriculum sampling weights without treating resampling as new coverage.
- Publish de-curriculum fixed evaluation and natural distribution checks before
  any training claim.

## Out Of Scope

- Human data or human strategy labels.
- Arbitrary deck/relic generation that is not linked to an authoritative source
  and validated by the simulator.
- Using assisted or transformed rows as natural A20 performance evidence.
- Permanent hand-written reward weights for strategic quality.

## Design Constraints

- Every component retains behavior controller, target controller, information
  regime, assistance/transform policy, source run, and simulator identity.
- The final model must not receive assistance flags or hidden generator-only
  features unless a task explicitly defines a training-only privileged regime.
- Curriculum success is coverage and learnability evidence, not natural
  reachability evidence.

## Deliverables

- Versioned generation and merge contracts for each curriculum component.
- Bounded-memory manifests and coverage reports.
- Restore/public-context/structured-outcome audits.
- A curriculum sampling specification and de-curriculum evaluation plan.
- Focused tests for provenance, distribution separation, transform validity, and
  duplicate-source handling.

## Acceptance Criteria

The published task must define per-component scales and coverage gates from the
accepted T061/T062 evidence. No component may satisfy a natural-data gate through
resampling or distribution relabeling.

## Required Verification

Run standard local gates, pinned-source verification, sharded generation and
restore audits, deterministic merge checks, and distribution-separation tests.

## Legacy Reference

Consult T008, T021--T024, T039--T044, T050--T052, and accepted T061/T062 reports.

## PR Report

Report all generator and distribution identities, source/unique counts,
assistance or transform policies, restore results, retention manifests, compute
costs, limitations, and one next recommendation.
