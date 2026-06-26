# T033: Public Context Encoder Contract

## Objective

Define and implement a versioned model-input encoder contract for sanitized
public run context: typed visible history summaries, visible map/route context,
visible Act Boss, and persistent public resources.

The result should make future normal-information models and search guidance use
the same public-context boundary instead of ad hoc feature additions.

## Current Main Baseline

Current `main` preserves sanitized public run context and ordered public
history through decisions and current artifacts, but model-input packing uses
only a compact summary. Complete map/route payloads and richer typed history
encoders remain future work with explicit missingness.

## Dependencies

- T016 and T030 are complete.

## Inputs And Artifacts

Inputs are committed fixtures and current-schema artifacts that already contain
sanitized public context. This draft must be refined before implementation to
name exact fixtures, generated outputs, and migration expectations.

## Scope

- Inventory public-context fields currently available to model-input packing.
- Define a versioned encoder schema for history, map/route, visible Boss, and
  persistent public-resource summaries.
- Keep missing fields explicit and forbid hidden future, RNG, hidden draw
  order, or hidden Act-3 second Boss fields.
- Add feature-size and deterministic-packing tests.
- Preserve compatibility with current trainer-input and checkpoint contracts
  through explicit schema versioning.

## Out Of Scope

- Broad training or model promotion.
- Native simulator projection changes.
- Hidden-future sampling or belief search.
- Local reimplementation of map, encounter, or reward mechanics.

## Design Constraints

- Normal-information encoders may consume only sanitized public context.
- Legacy artifacts must migrate before business logic uses them.
- Feature changes that affect checkpoints require explicit semantic contract
  validation on load.
- Missing native projection payloads remain explicit missingness.

## Deliverables

- A finalized task specification before this row becomes `READY`.
- Versioned encoder dataclasses/helpers and model-input packing integration
  when implemented.
- Focused tests for hidden-field firewall, missingness, determinism, and
  checkpoint semantic compatibility.

## Acceptance Criteria

This task is draft. Before it becomes `READY`, acceptance criteria must name
the exact encoder schema, fixtures, migration behavior, and verification
commands.

## Required Verification

To be finalized before implementation.

## Legacy Reference

Consult current T011/T016/T024/T026 feature and artifact code. Historical
plans may inform field selection but are not current contracts.

## PR Report

To be finalized before implementation.
