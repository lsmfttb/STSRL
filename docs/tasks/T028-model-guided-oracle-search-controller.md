# T028: Model-Guided Oracle Search Controller

Status: `READY`.

## Objective

Add the first versioned model-guided Oracle-like search controller.

The controller should use public-state checkpoint guidance to influence root
action selection or budget use around the current hidden-state native search,
while preserving complete telemetry and evidence boundaries.

## Current Main Baseline

Current `main` has Oracle-like native search, fixed evaluation, T024
teacher-targeted checkpoints, T025 search telemetry, T026 checkpoint
inference, and T027 teacher-guidance calibration. It does not yet have a
controller that combines native Oracle search statistics with learned
guidance.

## Dependencies

- T025, T026, and T027 are complete.

## Scope

- Add a new explicitly versioned controller name, for example
  `model_guided_oracle_search_v1`.
- Load one compatible checkpoint through the T026 inference contract.
- Use model guidance in a minimal, reviewable way at the root, such as
  root-score combination, prior-informed tie breaking, or documented
  allocation if current native APIs allow it.
- Preserve baseline native search statistics, model guidance scores, model
  call count, wall-clock timing, controller configuration, checkpoint identity,
  and information regime in telemetry.
- Add command/config routing only as needed to construct the controller for
  restored-battle smoke tests.

## Out Of Scope

- Native API changes unless a future task explicitly publishes them.
- Normal-information belief search.
- Live CommunicationMod deployment.
- Fixed-cohort benchmark conclusions; this task may run smoke battles only.
- Broad training or checkpoint training.

## Design Constraints

- Because native search copies hidden simulator state, this controller is
  `full_simulator_state_oracle_like` even if model features are public.
- Versioned controller names are behavior contracts; future behavior changes
  require a new version.
- The controller must fail closed on checkpoint/context mismatch.
- If model guidance cannot affect native budget allocation with current APIs,
  the implementation must state the exact root-selection role instead of
  pretending to guide deeper search.

## Deliverables

- Versioned controller implementation and provenance.
- Integration with T025 telemetry and T026 inference.
- Tests for controller construction, checkpoint mismatch failure, deterministic
  root scoring, telemetry fields, and evidence boundary.
- A WSL smoke restored-battle or fixed-cohort run outside the repository.

## Acceptance Criteria

- The controller can select legal battle actions through the shared
  `OnlineController` contract on restored simulator states.
- Telemetry reports native search budget/cost, model calls, model scores, and
  checkpoint provenance.
- Baseline Oracle search remains constructible and unchanged.
- The report labels results as Oracle-like diagnostics, not normal-information
  or live-game evidence.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`.

Run focused controller tests and a WSL smoke command using a checkpoint outside
the repository or an ignored artifact path.

## Legacy Reference

Consult T006, T009, T024, T025, and T026 code. Legacy experiments may be read
for configuration ideas but not wholesale ported.

## PR Report

The PR must report controller name/version, checkpoint identity, guidance
formula or allocation rule, telemetry summary, local/WSL verification, known
limitations, and evidence boundary.
