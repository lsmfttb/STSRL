# T063: Oracle-Guided Public Battle Learning

## Objective

Train and evaluate a public-information battle policy/value model using
simulator-generated Oracle assistance while measuring the information gap
between a full-state teacher and a deployable public student.

## Current Main Baseline

`main` can generate full-state Oracle-like search targets and train a public
policy/value model, but prior assisted and model-guided experiments did not show
controller improvement. The project lacks a focused Oracle-to-public transfer
experiment that treats hidden-future ambiguity as a first-class measurement.

T061 and T062 must first identify the selected battle-search surface and target
budget. T034 remains blocked, so this task cannot claim information-set-optimal
teaching without native public-consistent hidden-future sampling.

## Dependencies

- T061 accepted bottleneck evidence.
- T062 accepted Battle Search v2 surface or another explicitly selected teacher
  search surface.
- T033 public-context model-input contract.
- T006, T024, T026, and T027 teacher/checkpoint/calibration contracts.

## Inputs And Artifacts

The published task must name the source distributions, teacher controller,
public feature contract, checkpoint schema, fixed evaluation cohorts, simulator
identity, and regeneration commands. Human data is not an allowed input.

## Scope

- Generate soft policy and value targets from a named full-state Oracle search.
- Train a public student that receives only sanitized public state and history.
- Compare at least one explicit privileged-to-public transfer method, such as a
  separate Oracle teacher with public-student distillation or a versioned hidden-
  feature dropout schedule.
- Measure teacher/student action disagreement, target entropy, calibration,
  hidden-information sensitivity, and de-Oracle fixed-cohort performance.
- Keep behavior-policy provenance separate from target-generator provenance.
- Use simulator returns or Oracle targets; do not imitate bootstrap heuristic
  actions.

## Out Of Scope

- Human trajectories, human labels, or human expert imitation.
- Claiming `normal_belief_search` or normal-information optimality before T034.
- Learned non-combat policy training.
- Controller promotion from training fit alone.

## Design Constraints

- Oracle and public inputs are physically and semantically separated.
- Hidden features cannot enter the deployable checkpoint contract.
- One realized hidden future may yield an ambiguous teacher target for the same
  public history; reports must preserve soft targets and uncertainty rather than
  only an argmax label.
- Final evaluation uses no hidden inputs or training-time assistance.

## Deliverables

- Versioned Oracle-to-public target and training contracts.
- Public checkpoint with exact source/teacher provenance.
- Calibration, hidden-sensitivity, and fixed-cohort evaluation reports.
- Focused tests for information firewalls, target ambiguity, and checkpoint load
  failure.

## Acceptance Criteria

The published task must define its source scale, transfer arms, fixed cohorts,
and objective de-Oracle evaluation gates after T061/T062 merge. Any result remains
Oracle-assisted diagnostic evidence unless normal-public evaluation improves on
credible held-out cohorts.

## Required Verification

Run the standard local gates, source and checkpoint preflights, training
reproducibility checks, pinned-source verification, and sharded fixed-cohort
public-student evaluation.

## Legacy Reference

Consult T006, T009, T024, T027--T035, T043--T045, and the accepted T061/T062
reports.

## PR Report

Report teacher and student information regimes, source and target identities,
transfer method, ambiguity metrics, calibration, held-out outcomes, compute cost,
verification, limitations, and one next recommendation.
