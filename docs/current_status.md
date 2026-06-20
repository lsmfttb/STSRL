# Current Status

Last reviewed: 2026-06-19.

This document describes the latest `main` branch only. Results from local
artifacts, old branches, or unmerged pull requests do not count as implemented
capabilities.

## Current Goal

Build the foundations for an A20 battle agent. Search remains the intended
primary battle policy, and learned policies or values are expected to guide or
accelerate search. Non-combat decisions remain outside the trainable agent.

## Implemented On Main

### Runtime

- CommunicationMod-style stdin/stdout probe with protocol output isolated from
  logs.
- Framework-neutral simulator contracts and a Python adapter for the external
  patched `sts_lightspeed` simulator.
- Real simulator execution is documented and performed through WSL.

### Battle-Agent Data Spike

- Separate battle-policy and non-combat-driver selection during bounded
  simulator rollouts.
- Explicit online-controller contract with immutable, serializable provenance.
- `execute_controlled_run` as the authoritative complete-run advancement path
  for current complete-run workflows.
- Routed battle/non-combat controllers with separately inspectable child
  provenance and composite reproducibility propagation.
- Fixed-size tactical snapshot features and variable legal-action features.
- Battle-only decision batches and contiguous battle-segment reports.
- Candidate reward components, a draft scalar reward report, and reward-labeled
  battle examples.
- Framework-neutral trainer-input JSONL round trip, model-input packing, and
  deterministic action-score contract checks.
- Versioned trainer-input artifact migration, complete decision provenance,
  and occurrence-disambiguated portable action identities.
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests

- `241` tests pass on Windows Python as of this review.
- The two CommunicationMod fixture smokes pass.
- `python -m compileall -q src tests` passes.
- `ruff check src tests` and `ruff format --check src tests` pass.
- The T002 A20 WSL battle sweep passes with 386 steps and no reported problems.

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- checkpoint capture/restore and battle-start pools;
- fixed structural battle evaluation;
- native Oracle-like search integration and search-teacher datasets;
- PyTorch policy/value training;
- live CommunicationMod runtime adapter for trained or search controllers;
- structured persistent resource outcomes;
- sanitized public run context or complete public run history;
- constructed A20 battle-start supplements;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The first
tasks in dependency order are:

1. [`T010`](tasks/T010-stochastic-non-combat-driver.md), currently `IN_REVIEW`:
   add the versioned stochastic non-combat driver and calibration report.
2. [`T011`](tasks/T011-tactical-feature-contract-v2.md), currently `READY`:
   establish the versioned public tactical state/action feature contract and
   live-runtime field parity audit.
3. [`T004`](tasks/T004-battle-start-checkpoint-pool.md) remains blocked by
   T010; review remaining blocked specifications as their prerequisites merge.

Later tasks are dependency-ordered in the task index. A task is not ready for a
new branch until its status is `READY`.

Live-game deployment compatibility is now tracked as
[`T013`](tasks/T013-live-communicationmod-runtime-adapter.md). It is blocked by
T011. Simulator-only RL training does not depend on T013, but trained
or search controllers should not be described as runnable in the real game until
that adapter, feature-parity, action-mapping, and runtime-provenance work
passes review.

## Legacy Integration Reference

Commit `d56e10e` on `codex/integration-current` preserves a large body of
previously tested but unreviewed work. It combines many independent concerns
and therefore violates the one-task-one-branch rule.

It will not be merged wholesale and is not a development base. Each useful
capability is mapped to a focused task under [`tasks/`](tasks/README.md).
Implementers may consult that commit, but each PR must be independently
understandable, scoped, tested, and based on the latest `main`.

The branch remains untouched as a recovery reference until every mapped task
has been merged, rejected, or explicitly superseded.

## Environment

Real simulator work runs through WSL:

```text
checkout:      ~/stsrl-spikes/sts_lightspeed
system build:  ~/stsrl-spikes/sts_lightspeed/build-py
repository:    /mnt/d/DeadlycatCoding/STSRL
```

See [`sts_lightspeed_wsl_spike.md`](sts_lightspeed_wsl_spike.md) for commands
that are currently available on `main`.
