# Current Status

Last reviewed: 2026-06-15.

This document states what is implemented now, what remains incomplete, and what
work should happen next. It is not a detailed design contract; see
[`project_architecture.md`](project_architecture.md) for that.

## Current Goal

Build a strong A20 battle agent while keeping the long-term objective aligned
with eventual A20 Heart victory. Battle search is the primary policy direction.
Learned models should improve search quality or reduce its compute cost.

Non-combat decisions are not trainable yet. A separately named seeded
stochastic driver generates natural complete runs and preserves diverse legal
branches.

## Implemented

### Runtime And Control

- The external patched `sts_lightspeed` simulator runs through WSL.
- Explicit online controller contracts separate battle policy/search from the
  non-combat driver.
- Complete-run advancement is centralized through `execute_controlled_run`.
- Native `BattleScumSearcher2` is exposed as an Oracle-like
  full-simulator-state search baseline.
- Fixed-battle evaluation can restore a battle start and evaluate an explicit
  controller.

### Data And Evaluation

- Natural battle-start pools can be collected, serialized, restored, audited,
  and stratified by structural metadata.
- Search-training collection retains source checkpoint, sampling component,
  teacher action, behavior action, root visits, terminal labels, and controller
  provenance.
- Fixed evaluation reports natural-weighted, encounter-macro, room-type-macro,
  and per-stratum results separately.
- Legacy artifact readers use explicit sequential migrations and report
  unrecoverable information.
- Broad PyTorch training has an explicit scale/distribution readiness gate.

### State And Labels

- The tactical encoder includes ascension, cards and piles, monster identity
  and move state, relics, potions, and legal-action details.
- Terminal outcome, absolute current HP, and structured persistent resource
  changes are preserved separately.
- A sanitized public-run-context boundary carries the visible Act Boss,
  completed encounter history, and visible map/current/next-node context
  through decision records and model-input packing.
- The native public-context patch avoids known hidden RNG, unrevealed future
  encounter lists, and the hidden Act-3 second Boss.

### Models

- Pure-Python linear and policy-gradient spikes validate the training path.
- Optional PyTorch policy/value checkpoints support legal-action scoring,
  outcome, absolute-current-HP, and terminal-resource-vector heads.
- These models are diagnostics and search-support candidates, not evidence of a
  strong standalone neural policy.

## Known Gaps

### Complete Public Run Context

The long-term state target is the complete player-visible run history, not only
prior battles:

- visited rooms and map path;
- events seen and public event choices/results;
- card, relic, potion, gold, key, shop, rest, and reward decisions;
- battle encounters and public outcomes;
- complete visible map, available routes, and visible Act Boss.

The current implementation preserves encounter history and visible route
context, but not this complete typed public history. The flat tactical model
also ignores most structured run context. Until both gaps are closed, current
models are tactical rather than continuation-aware.

### Search Quality And Information Regime

- Native random terminal rollout search sees hidden simulator state.
- Twenty simulations per decision is a smoke budget and is too weak for serious
  later-act natural-state generation.
- A normal-information hidden-future sampler and belief-search implementation
  do not exist yet.
- Learned priors and leaf values have not yet demonstrated a credible fixed-set
  search improvement.

### Coverage

- Natural A20 data remains heavily concentrated in Act 1.
- Boss and later-act battle starts are under-covered.
- Structural resampling improves optimization balance but cannot create new
  unique states.
- Constructed or counterfactual data must remain supplemental and separately
  tagged.

### HP Construction Policy

The previous documentation made authoritative downstream replay certification a
mandatory condition for every HP augmentation. That is no longer the intended
project rule: its complexity is disproportionate to small HP perturbations.

The intended replacement is a practical, conservative, seeded approximation
with explicit source metadata, caps, and separate constructed-data reporting.
Authoritative replay remains useful for audits or high-impact transforms, but
is optional. Some current implementation paths may still fail closed without a
certificate; simplifying that code is a separate mainline task.

## Immediate Priorities

1. Define and expose a typed complete player-visible run-history contract.
2. Add a model-side encoder for structured public history, map, routes, and
   visible Boss context.
3. Simplify HP construction to a conservative documented approximation and
   calibrate it against natural A20 distributions.
4. Improve the stochastic non-combat driver and authoritative state-generation
   options enough to obtain meaningful Boss and later-act A20 coverage.
5. Replace smoke-scale Oracle random rollouts with measurable search
   improvements: policy priors, leaf values, uncertainty, and eventually
   normal-information belief search.

## Environment

Real simulator work runs through WSL:

```text
checkout:       ~/stsrl-spikes/sts_lightspeed
system build:   ~/stsrl-spikes/sts_lightspeed/build-py
PyTorch build:  ~/stsrl-spikes/sts_lightspeed/build-py313-final
PyTorch Python: ~/stsrl-spikes/py313-torch/bin/python
```

See [`sts_lightspeed_wsl_spike.md`](sts_lightspeed_wsl_spike.md) for commands
and [`experiment_log.md`](experiment_log.md) for dated verification results.
