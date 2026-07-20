# T065: Learned Non-Combat Policy v1

## Objective

Replace the bootstrap heuristic as the intended long-term non-combat decision
source with a learned public-information policy trained only from simulator
returns, counterfactual continuations, search targets, and Oracle assistance.

## Current Main Baseline

`expert_non_combat_v1` improves early source reachability but encodes human-
designed heuristics and is not an intended teacher. `main` has routed controller
provenance and public run context, but no learned non-combat policy/ranker or
run-level value contract.

T061 must first show that non-combat behavior is an actionable bottleneck or that
joint interaction requires a learned non-combat module.

## Dependencies

- T061 accepted bottleneck-decomposition evidence.
- T033 public-context model-input contract.
- T014--T016 public projection, context, history, replay, and audit contracts.
- complete-run checkpoint/continuation support already merged on `main`.

## Inputs And Artifacts

Human trajectories and human action labels are forbidden. Bootstrap-driver runs
may supply visited states, but the bootstrap action is not a supervised target.
Targets must come from simulator returns, matched continuation, search, or a
named Oracle controller with separate provenance.

## Scope

- Define a versioned public non-combat state and dynamic legal-action encoding
  for supported screen types.
- Define an action-conditioned long-horizon value or policy-ranking target.
- Generate counterfactual continuation targets for selected legal actions from
  the same source state using paired seeds or a documented stochastic estimator.
- Train a first learned non-combat policy/value model with legal-action masking.
- Compare the learned policy with stochastic and bootstrap behavior on fixed
  non-combat states and matched complete-run seeds.
- Report screen-specific coverage, action disagreement, continuation-value
  calibration, run reachability, and compute cost.

## Out Of Scope

- Imitation loss on `expert_non_combat_v1` actions.
- Human strategy annotations or external human data.
- Replacing the battle controller in the same task.
- End-to-end joint optimization before the standalone non-combat contract is
  auditable.
- Natural A20 promotion from a small diagnostic cohort.

## Design Constraints

- The deployable policy consumes only sanitized public context/history.
- Behavior action, Oracle/search target, return target, and model-selected action
  remain separate fields.
- Screen-specific unsupported states fail closed or route to a named bootstrap
  fallback whose use is reported.
- Rewards and targets must retain auditable components; long-term value is learned
  from simulator continuation rather than permanent hand-written strategic
  weights.

## Deliverables

- Versioned non-combat model-input, target, checkpoint, and controller contracts.
- Counterfactual continuation collection/report support.
- Focused fixtures for card reward, map, shop, rest, event, relic, potion, and key
  decisions supported by the published scope.
- Diagnostic training and matched complete-run evaluation reports.

## Acceptance Criteria

The published task must define supported screens, target budgets, source scale,
fixed cohorts, fallback limits, and objective evaluation gates after T061 merges.
The learned policy may not be promoted merely for matching bootstrap actions.

## Required Verification

Run standard local gates, public-context and hidden-field audits, deterministic
counterfactual fixtures, checkpoint round trips, pinned-source verification, and
sharded matched complete-run evaluation.

## Legacy Reference

Consult T010, T014--T016, T033, T040, T042--T045, and the accepted T061 report.

## PR Report

Report supported screens, target-generation provenance, bootstrap fallback use,
training sources, checkpoint identity, calibration, matched-run outcomes, compute
cost, failures, limitations, and one next recommendation.
