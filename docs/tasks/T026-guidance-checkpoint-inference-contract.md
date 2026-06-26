# T026: Guidance Checkpoint Inference Contract

Status: `DONE` via PR #26, merged 2026-06-26.

## Objective

Add a narrow inference contract for using T009/T024 PyTorch policy/value
checkpoints as search-guidance scorers.

This task makes checkpoint inference auditable before any controller depends on
it.

## Current Main Baseline

Current `main` can train and load optional PyTorch checkpoints, and T024 records
explicit teacher policy-target provenance. There is no reusable search-guidance
inference interface that consumes a public `DecisionContext`, scores current
legal actions, exposes value/outcome predictions, and reports complete
checkpoint provenance without becoming a controller.

## Dependencies

- T009, T011, T016, T018, and T024 are complete.

## Scope

- Define a framework-neutral search-guidance inference result, including legal
  action policy logits or probabilities, optional value/outcome predictions,
  eligible-action masks, checkpoint identity, target provenance, and timing.
- Add an optional PyTorch-backed scorer that loads current
  `torch-policy-value-checkpoint-v1` checkpoints and scores a current public
  decision context.
- Add a CLI/report command for checkpoint inference smoke or compatibility
  inspection, without running a simulator or choosing game actions.
- Keep PyTorch imports isolated behind the existing optional train dependency
  path.
- Validate schema, feature sizes, public-context feature contract, and
  checkpoint semantic contract before scoring.

## Out Of Scope

- Model-guided search controller implementation.
- Training new checkpoints.
- Fixed-cohort benchmark comparison.
- Live CommunicationMod deployment.
- Treating Oracle teacher checkpoints as normal-information performance
  evidence.

## Design Constraints

- Inputs must be the same public tactical/context contract used by current
  trainer/model-input code.
- Hidden simulator state, unrevealed draw order, and hidden future encounters
  must not enter the inference contract.
- Checkpoint provenance must preserve policy target kind/source and
  information-regime counts.
- Optional PyTorch must not be imported by default CLI startup.

## Deliverables

- Search-guidance inference dataclasses/protocols below the command layer.
- Optional PyTorch scorer adapter.
- CLI/report path for deterministic checkpoint smoke output.
- Tests for successful scoring, bad checkpoint schema, feature mismatch,
  default CLI import isolation, and provenance formatting.

## Acceptance Criteria

- A current checkpoint can score all legal actions for a current public
  decision context and return deterministic shapes.
- The result reports checkpoint identity, policy target kind/source, source
  information regimes, and whether the checkpoint is Oracle-like supervision.
- Unsupported checkpoint or context schemas fail closed with clear errors.
- Default CLI import still does not import PyTorch.
- No controller or simulator advancement is introduced.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`.

Run focused inference/checkpoint tests, including a smoke checkpoint generated
from fixture trainer data under a named gate override.

If PyTorch is not installed in WSL, report that explicitly; WSL simulator gates
are not required for this task because it is an offline inference contract.

## Legacy Reference

Consult current T009/T024 checkpoint and trainer-input code. The legacy
integration branch may be inspected only for inference-shape ideas.

## PR Report

The PR must report checkpoint schema compatibility, inference result schema,
default-import isolation, exact tests, and the evidence boundary for any
Oracle-teacher checkpoint used in smoke tests.
