# T039: Later-Act/Boss Source Coverage Contract

## Objective

Turn accepted T037/T038 evidence into an explicit source-coverage contract that
can either unblock broad T032 teacher/checkpoint refresh work or deliberately
narrow T032 to an Act-1 diagnostic refresh.

This task prevents later work from implicitly consuming temporary reachability
artifacts or smoke-scale pools.

## Current Main Baseline

T032 is blocked because no accepted current-schema later-act/Boss source
coverage contract exists. T036 validated the tooling but stayed Act 1 only.
T037 and, if needed, T038 determine whether sufficient later-act/Boss source
coverage can be recovered by scaled search-controlled collection.

## Dependencies

- T037 reaches later-act/Boss starts at a usable scale, or T038 recommends an
  explicit narrow-refresh boundary.

## Scope

- Define the accepted source distributions, artifact schemas, source identities,
  regeneration commands, and SHA-256 identities for the next data task.
- State whether the contract supports broad A20 teacher/checkpoint refresh,
  a narrower Boss/later-act source supplement, or only an Act-1 diagnostic
  refresh.
- Preserve distribution tags separately for natural, stratified-training,
  constructed, paired-counterfactual, normal-information, Oracle, and SL-enabled
  data where present.
- Specify minimum restore, public-context, structured-outcome, and T009 gate
  evidence that T032 or its revised successor must report.

## Out Of Scope

- Generating teacher datasets, trainer-input files, checkpoints, or calibration
  reports.
- Reusing local temporary artifacts without documented identity and
  regeneration commands.
- Claiming normal-information or live-game controller strength from
  Oracle-like source generation.

## Acceptance Criteria

- The contract names every artifact class that later tasks may consume and how
  reviewers can regenerate or verify it.
- The contract says explicitly whether T032 remains blocked, becomes `READY`,
  or must be revised into a narrower task before becoming `READY`.
- No broad A20 training claim is made without later-act/Boss source coverage and
  gate evidence.

## Required Verification

Run documentation checks, task-index checks, and `git diff --check`.

## PR Report

The PR must report task ID, accepted evidence, artifact contracts, distribution
boundaries, T032 decision, verification results, and documentation impact.
