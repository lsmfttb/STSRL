# T015: Public Run Context And Controlled History

Status: `DONE`.

## Objective

Define one typed, versioned, sanitized Python public run-context contract and
append exactly one ordered history entry for every successfully executed
player-visible decision in `execute_controlled_run`.

## Current Main Baseline

T014 established the raw native field/candidate capability matrix and
checkpoint behavior. Current `main` exposes `public-tactical-v2` plus the raw
`native-public-projection-v1` audit surface. That raw projection reports
current screen identity, candidate actions from `StepSimulator::legalActions`,
and currently available persistent resources; visible Act Boss, complete map,
current node, legal routes, and screen-specific payloads remain explicitly
unavailable or unsupported.

Battle-start records still explicitly retain no complete public context. T003
supplies decision provenance/migration infrastructure and T002 supplies the
authoritative controlled-run path.

## Dependencies

- T002, T003, T004, T011, and T014 are complete.

## Scope

- Define the nested public run-context and typed history schemas using T014's
  accepted capability matrix. The context includes a current public
  persistent-resource snapshot, visible current-Act Boss, complete currently
  visible map/routes when available, current location, and explicit field-level
  missingness.
- Build a recursive sanitizer and strict raw-projection conformance validator.
  Conformance validation occurs before sanitization; sanitization cannot make
  unknown raw keys disappear before they are checked.
- Append one contiguous history entry after, and only after, each successful
  `execute_controlled_run` transition. Entries link the pre-decision visible
  screen and candidate actions to the selected occurrence-disambiguated action,
  visible post-decision result/location, and resource change or explicit
  missingness.
- Attach only the sanitized context to in-memory `DecisionContext` construction
  and provide fake-adapter ordering/conformance tests. T015 may use T014's raw
  projection but does not persist it in existing artifacts.

## Out Of Scope

- Artifact propagation, JSONL format bumps, migration of saved records,
  portable replay comparison, or WSL coverage collection; T016 owns them.
- New native projection or patch-stack work; T014 owns it.
- Learned encoders, continuation values, belief search, structured terminal
  outcome labels, or local mechanics reconstruction.

## Design Constraints

- History is typed, versioned, append-only, and ordered. Empty, absent, and
  unavailable remain distinguishable.
- Reject hidden RNG, hidden draw order, unrevealed future encounters, raw
  checkpoints/native objects, simulator-only internals, and hidden Act-3
  second-Boss data recursively.
- The complete public target is tactical state plus persistent resources,
  typed visible history, visible map/routes, and visible Act Boss; do not
  substitute encounter metadata or prose for it.
- Unsupported T014 fields stay explicit. Python must not infer missing game
  facts or candidate actions.

## Deliverables

- Versioned schema, sanitizer, raw conformance validator, forbidden-field
  audit, and controlled-history implementation.
- `DecisionContext` integration and fake-adapter/unit fixtures for ordering,
  explicit missingness, candidate linkage, and recursive rejection.
- Focused tests documenting every T014 capability gap carried forward.

## Acceptance Criteria

- Every successful visible transition produces one contiguous entry; failed or
  unexecuted selections produce none.
- Sanitized contexts never retain a forbidden field and no unknown nested raw
  projection key is silently accepted.
- Current resources, visible map/routes, visible Boss, pre-decision candidates,
  selected action, post-decision result, and missingness are represented by the
  one contract whenever T014 supplies them.
- Normal-public controllers receive only sanitized context.

## Required Verification

Run the standard local gates and focused context/history tests. The PR report
must name every T014 capability consumed, every still-unavailable field, and
all forbidden-field/audit results. T016 will add the artifact and WSL gates.

## Legacy Reference

Consult the former T007 materials selectively after T014's accepted capability
matrix is available. The closed implementation is not an acceptance reference.

## PR Report

Include schema versions, ordering evidence, raw-conformance versus sanitizer
results, forbidden-field evidence, T014 dependency identity, gaps propagated
to T016, exact verification, known limitations, and unmet criteria.
