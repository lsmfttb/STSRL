# T034: Public-Consistent Hidden-Future Sampler Boundary

## Objective

Specify and validate the simulator boundary for sampling hidden battle futures
that are consistent with one sanitized public state and public run history.

This task is the prerequisite for normal-information belief search. It must
not expose hidden state to a normal controller or replace simulator mechanics
with Python reconstruction.

## Current Main Baseline

Current native search copies the actual hidden simulator state and is therefore
`full_simulator_state_oracle_like`. The repository has public-context
artifacts and hidden-field firewall tests, but it does not have an
authoritative simulator API for public-consistent hidden-future particles.

## Dependencies

- T033 is complete.
- A pinned `sts_lightspeed` integration exposes or accepts an explicit native
  sampler design for public-consistent hidden futures.

## Inputs And Artifacts

Inputs must be current public-context fixtures or source pools with sanitized
public state. Any native API change belongs in the external simulator fork and
must be pinned through the source manifest before STSRL consumes it.

## Scope

- Define the public equivalence contract for sampled hidden futures.
- Verify that particles preserve identical public observations while retaining
  diverse hidden futures where legal.
- Report unsupported public states and native capability gaps explicitly.
- Add firewall tests that normal-information controller paths cannot access
  sampled hidden fields.

## Out Of Scope

- Belief-search controller implementation.
- Oracle-action cloning as a normal-information target.
- Local Slay the Spire mechanics reconstruction.
- Live-game performance claims.

## Design Constraints

- The actual game remains final mechanics authority; `sts_lightspeed` is the
  current simulator authority.
- Public consistency includes all revealed public facts, including effects
  that reveal draw order.
- The first sampler may be diagnostic, but information regime labels must stay
  explicit.

## Deliverables

- Native capability contract and STSRL adapter boundary.
- Current-schema diagnostic report for sampler coverage and public parity.
- Tests for public parity, hidden diversity, unsupported states, and firewall
  enforcement.

## Acceptance Criteria

- Every sampled particle matches the source public projection under the
  published public-context contract.
- Hidden diversity is reported separately from public parity.
- Unsupported states fail closed or report explicit unsupported status.
- No normal-information controller or model-input path receives hidden fields.

## Required Verification

To be finalized after the native sampler surface is published and pinned.

## Legacy Reference

Use current T014--T016 public projection/context contracts and T017 source
manifest workflow. Historical normal-search notes are design context only.

## PR Report

The PR must report native source identity, sampler capability coverage,
public-parity results, hidden-field firewall tests, unsupported states, and
remaining native gaps.
