# T010: Stochastic Non-Combat Driver

Status: `DONE`.

## Objective

Provide a seeded, versioned, stochastic non-combat driver that produces a broad
natural incoming-state distribution without pretending to be an optimal
long-term policy.

## Current Main Baseline

`main` routes non-combat screens to a separate policy, but available policies
are simple action-level selectors. They do not encode the required hierarchical
random priors or report low-probability branch coverage.

## Scope

- Introduce a versioned non-combat driver using hierarchical random choices.
- Preserve seeded reproducibility while allowing different seeds to produce
  diverse legal outcomes.
- Apply priors at decision-category level, then sample legal actions within the
  selected category.
- Keep low-probability branches reachable, including:
  - taking and skipping ordinary or Boss relics;
  - opening and leaving treasure;
  - rest versus upgrade and other rest-site actions;
  - shop strategies such as card removal, card purchase, potion purchase, relic
    purchase, and leaving;
  - discarding a potion before taking a replacement;
  - using visible non-combat potions;
  - taking keys and other Heart-related branches.
- Add only the simulator-native visible actions and resource snapshots required
  to make those branches controllable and auditable.
- Record complete driver provenance, published relative category weights, and
  the normalization rule used after legal categories are known.
- Produce a natural-calibration report showing reached screens, category
  opportunities, selected-category counts, and unavailable structural
  categories across a named A20 seed range.

## Out Of Scope

- A learned non-combat policy or hand-written optimal route.
- Deterministic preferred choices.
- Battle policy changes, checkpoint pools, or constructed states.
- Improving the battle controller merely to reach a particular non-combat
  screen, including Boss relic rewards.
- Removing legal branches because they are usually weak.

## Design Constraints

- Behavior changes require a new driver version.
- Battle-only potion exclusions must not remove non-combat potion rewards,
  purchases, discards, or uses.
- All randomness comes from explicit seeded sources.
- Missing simulator-visible actions fail explicitly; Python must not implement
  game mechanics.
- Conditional driver reachability and natural-run coverage are separate
  measurements. A constructed, restored, or replaced Boss screen may test
  conditional behavior but must never be reported as natural A20 coverage.

## Deliverables

- Versioned driver and provenance.
- Native patch files only where required for missing visible actions/resources.
- Unit tests for hierarchical category selection, seeded reproducibility, and
  conditional rare-branch reachability.
- Real WSL natural-calibration report over a documented seed range, with both
  opportunity and selection counts.

## Acceptance Criteria

- Same seed and configuration reproduce the same decisions.
- Given a public legal-action context for each required category, the
  documented deterministic driver-seed sweep can select every category. This
  is the conditional reachability gate.
- The natural A20 calibration reports the exact structural screens and
  categories reached, category opportunities, and selected categories. A
  category with no natural opportunity, such as an unreached Boss relic screen,
  remains an explicit coverage gap rather than a driver failure or fabricated
  positive result.
- No legal category is made unreachable by a hard-coded preferred route.
- Driver provenance, battle-controller provenance, effective action-space
  configuration, simulator configuration, published relative weights, and the
  normalization rule fully determine the reported experiment behavior.
- Standard local gates and documented WSL calibration pass.

## Required Verification

Run the standard local gates. The PR must also run an A20 WSL natural
calibration over a documented contiguous seed range and report the exact seed
range, episode count, max steps, ascension, battle-controller provenance,
effective action-space configuration, category opportunity counts, selected
category counts, and unavailable structural categories. The command must fail
for driver or provenance errors, but an unreached structural screen alone is a
reported natural-coverage gap, not a substitute for conditional reachability.

Run focused conditional-reachability tests for every required category. These
tests may use legal action contexts or a simulator-native fixture, but must not
be presented as natural A20 coverage.

## Legacy Reference

Consult selectively:

```text
patches/sts_lightspeed_non_combat_potion_actions.patch
patches/sts_lightspeed_run_potion_snapshot.patch
patches/sts_lightspeed_run_resource_snapshot.patch
src/sts_combat_rl/sim/policy.py
tests/test_sim_policy.py
```

## PR Report

Include the driver version, full relative-weight table and normalization rule,
exact calibration command, complete experiment provenance, category
opportunity/selection counts, unavailable structural categories, missing native
capabilities, and known distribution biases. State conditional reachability and
natural coverage separately.
