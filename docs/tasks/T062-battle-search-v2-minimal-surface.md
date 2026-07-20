# T062: Battle Search v2 Minimal Surface

## Objective

Replace root-only model influence with a minimal tree-internal search surface
that can use a policy prior and learned leaf value, then compare it with baseline
Oracle-like search under matched simulator-step and wall-clock budgets.

## Current Main Baseline

Current search development has validated native Oracle-like search, post-search
model guidance, root-prior allocation, and detailed telemetry. T059 closed the
root-prior allocation-repair route. The architecture identifies policy priors,
learned leaf values, uncertainty-aware allocation, and belief handling as the
serious search direction, but `main` does not yet expose a reviewable minimal
implementation of tree-internal policy/value guidance.

T061 must first establish that battle-search quality or compute is an actionable
reachability bottleneck and select this task for publication.

## Dependencies

- T061 accepted bottleneck-decomposition evidence.
- T025 search telemetry and compute reporting.
- T026 checkpoint inference contract.
- T046 native search integration precedent.
- the pinned `sts_lightspeed` integration line.

## Inputs And Artifacts

The published version of this task must name the accepted T061 report and fixed
cohorts, the checkpoint contract used for policy/value inference, the exact
native simulator commit, and any retained artifacts or regeneration commands.
Large search traces and comparison outputs remain under a stable ignored
artifact root with hashes and manifests.

## Scope

- Define one versioned Battle Search v2 controller and native/Python contract.
- Apply policy priors inside expanded tree nodes, not only after native search or
  only at the root.
- Support a learned leaf-value estimate at a named depth or expansion boundary.
- Preserve legal-action identity, chance/RNG semantics, root selection, and full
  controller provenance.
- Report native simulations, expanded nodes, model calls, simulator steps,
  transposition reuse if implemented, and wall-clock cost.
- Compare baseline search and Search v2 on matched restored cohorts under both
  equal nominal search budget and a compute-normalized budget.
- Keep the first implementation minimal enough that policy-prior and leaf-value
  effects can be independently ablated.

## Out Of Scope

- Human trajectories or human action supervision.
- Public-consistent hidden-future sampling, normal-information promotion, or
  live-game claims.
- Learned non-combat policy implementation.
- Broad complete-run scale-up before fixed-cohort search evidence is accepted.
- Multiple unrelated search algorithms in one task.

## Design Constraints

- The controller remains explicitly `full_simulator_state_oracle_like` unless a
  later task adopts a different regime.
- Search must fail closed on invalid priors, illegal action mappings, incompatible
  checkpoints, missing value heads, or mixed simulator provenance.
- Policy and value inputs must use published model contracts rather than hidden
  ad hoc vectors.
- Model guidance must not silently change the legal action space.
- Compute comparisons must not infer improvement from nominal simulation count
  alone.

## Deliverables

- Versioned controller/search contract and implementation.
- Native integration changes only when required by the accepted minimal design.
- Focused tests for tree-node priors, leaf values, action identity, ablations,
  provenance, and failure modes.
- Matched fixed-cohort reports for baseline, prior-only, value-only, and combined
  Search v2 when the accepted design supports those arms.
- One recommendation about complete-run evaluation or further search repair.

## Acceptance Criteria

The published version must define objective equal-budget and compute-normalized
comparison gates from T061 evidence. It may become `READY` only after those
cohorts, artifacts, budgets, and promotion boundaries are concrete.

## Required Verification

Run the standard local gates, focused native/Python tests, pinned-source
verification, and sharded WSL restored-battle comparisons. Report exact artifact
identities and compute telemetry.

## Legacy Reference

Consult T025--T029, T035, T046--T059, and the accepted T061 report. Historical
root-prior variants remain evidence; they are not the implementation base unless
the published task names a narrowly reusable contract.

## PR Report

Report task ID, controller and checkpoint identities, native simulator identity,
all ablations, matched-cohort outcomes, compute-normalized costs, failures,
verification, and the single next recommendation.
