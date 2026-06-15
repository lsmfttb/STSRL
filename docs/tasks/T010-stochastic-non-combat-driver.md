# T010: Stochastic Non-Combat Driver

Status: `BLOCKED` by T002.

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
- Record complete driver provenance and category probabilities.
- Produce a calibration report showing category and rare-branch counts across
  a named A20 seed range.

## Out Of Scope

- A learned non-combat policy or hand-written optimal route.
- Deterministic preferred choices.
- Battle policy changes, checkpoint pools, or constructed states.
- Removing legal branches because they are usually weak.

## Design Constraints

- Behavior changes require a new driver version.
- Battle-only potion exclusions must not remove non-combat potion rewards,
  purchases, discards, or uses.
- All randomness comes from explicit seeded sources.
- Missing simulator-visible actions fail explicitly; Python must not implement
  game mechanics.

## Deliverables

- Versioned driver and provenance.
- Native patch files only where required for missing visible actions/resources.
- Unit tests for hierarchical category selection, seeded reproducibility, and
  rare-branch reachability.
- Real WSL calibration report over a documented seed range.

## Acceptance Criteria

- Same seed and configuration reproduce the same decisions.
- Different seeds reach every required low-probability category in the
  documented calibration run.
- No legal category is made unreachable by a hard-coded preferred route.
- Driver provenance fully determines behavior.
- Standard local gates and documented WSL calibration pass.

## Required Verification

Run the standard local gates. The PR must also run an A20 WSL calibration large
enough to demonstrate each required low-probability category at least once and
must report the exact seed range, episode count, and category counts.

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

Include the driver version, full category probability table, exact calibration
command, rare-branch counts, missing native capabilities, and known
distribution biases.
