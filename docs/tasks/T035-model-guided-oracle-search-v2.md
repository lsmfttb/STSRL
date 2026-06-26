# T035: Model-Guided Oracle Search V2

## Objective

Add the next model-guided Oracle-like search experiment only after refreshed
data/checkpoint evidence exists.

The task should test whether model guidance can improve equal-budget fixed
evaluation beyond T029's smoke-scale tie, while keeping the controller
`full_simulator_state_oracle_like`.

## Current Main Baseline

T028 combines native hidden-state root statistics with checkpoint policy
probabilities at root selection. T029 compares that controller with baseline
Oracle search on identical restored starts and reports no smoke-scale win-rate
improvement while adding model calls. Current native APIs do not accept model
priors for allocation, model leaf values, uncertainty, or tree reuse.

## Dependencies

- T032 is complete.
- T025, T028, and T029 remain current comparison contracts.

## Inputs And Artifacts

Inputs must include a T032-compatible checkpoint with trainer-input provenance,
one fixed or smoke cohort with source identities, and regeneration commands or
explicit external/ignored artifact paths. The task may require a new pinned
native search guidance API if it attempts allocation or leaf-value guidance.

## Scope

- Define a new versioned controller name.
- Use refreshed checkpoint provenance from T032.
- Either preserve and clearly state root-combination-only guidance, or consume
  a newly published native API for priors, leaf values, uncertainty, or budget
  allocation.
- Compare against baseline Oracle search and T028 on identical restored
  starts with separate outcome and compute telemetry.

## Out Of Scope

- Normal-information promotion.
- Live-game validation.
- Broad training claims.
- Reusing T028/T029 smoke artifacts as implicit inputs.
- Native API changes unless separately pinned and documented.

## Design Constraints

- The controller remains `full_simulator_state_oracle_like` while native search
  copies hidden state.
- Behavior changes require a new versioned controller name.
- Model calls, native simulator steps, wall-clock time, root visits, and
  failures remain separate telemetry fields.
- Equal-source comparison is mandatory.

## Deliverables

- Versioned controller or documented no-op experiment boundary.
- Fixed-cohort comparison report against baseline and T028.
- Focused tests for controller provenance, guidance math/API use, action
  identity matching, telemetry, and failure accounting.
- WSL smoke or fixed-cohort evidence with explicit artifacts.

## Acceptance Criteria

- The report compares all configured controllers on identical source starts.
- Guidance behavior is explicit and reproducible.
- Compute/model-call telemetry is reported separately.
- The PR does not claim controller promotion unless a future task defines a
  credible promotion gate and the evidence satisfies it.

## Required Verification

Run the standard local gates if code changes are made. Run focused controller
and comparison tests. Run pinned-source WSL evidence on explicitly reported
artifacts.

## Legacy Reference

Consult T025, T028, T029, and T032 only. Do not port legacy policy-comparison
experiments wholesale.

## PR Report

The PR must report task ID, controller version, checkpoint identity, cohort
identity, comparison aggregates, telemetry, failures, verification commands,
known limitations, and evidence-boundary language.
