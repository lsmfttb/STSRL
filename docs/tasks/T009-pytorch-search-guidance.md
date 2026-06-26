# T009: PyTorch Search-Guidance Model

## Current Main Baseline

T009 is complete on `main`. The current implementation provides optional
PyTorch model plumbing behind the `train` dependency group, offline trainer
input preflight, a fail-closed broad-training scale/distribution gate,
versioned checkpoint save/load with semantic schema checks and training-data
provenance, and named smoke/narrow-curriculum override support. Current A20
data is still smoke-scale even with the T008 constructed supplements, so broad
neural training remains blocked until the explicit scale/distribution gate
passes. Raw model diagnostics are not policy-strength evidence, and
model-guided search fixed evaluation is reported as `not_run`.

## Dependencies

- T003, T006, T011, T012, T016, and T018 are complete.

## Objective

Introduce an optional PyTorch policy/value model as search guidance, with
explicit scale/distribution gates and public-information inputs.

## Scope

- Add PyTorch only behind the optional `train` dependency group.
- Consume sanitized public tactical state, legal actions, and the public run
  context available after T016.
- Predict legal-action policy targets and separately auditable value/outcome
  targets, including battle outcome and terminal absolute current HP.
- Preserve structured resource targets rather than permanently collapsing them
  into fixed weights.
- Train only when an explicit per-ascension/per-act scale and distribution gate
  passes, unless a named smoke or narrow-curriculum override is supplied.
- Save versioned checkpoints with complete training-data and controller
  provenance.
- Evaluate raw model strength as a diagnostic and model-guided search on fixed
  cohorts as the promotion criterion.

## Out Of Scope

- Claiming smoke-scale data demonstrates neural strength.
- Hidden RNG or unrevealed future information as normal-model input.
- Replacing search merely because a neural policy exists.
- Gymnasium or Stable-Baselines3.

## Acceptance Criteria

- Optional dependency isolation is preserved.
- Checkpoints round-trip with explicit schema and provenance.
- Broad-training gate fails closed on under-covered datasets.
- A0 coverage cannot hide missing A20 coverage.
- Raw policy and search-guided results are separately reported.
- Required local, PyTorch, and fixed-evaluation gates pass.

## Legacy Reference

Consult selectively:

```text
src/sts_combat_rl/sim/torch_policy_value.py
src/sts_combat_rl/sim/resource_outcome.py
src/sts_combat_rl/sim/trainer_input_preflight.py
tests/test_torch_policy_value.py
tests/test_resource_outcome.py
```
