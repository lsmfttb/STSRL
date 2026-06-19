# Current Status

Last reviewed: 2026-06-15.

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
- Fixed-size tactical snapshot features and variable legal-action features.
- Battle-only decision batches and contiguous battle-segment reports.
- Candidate reward components, a draft scalar reward report, and reward-labeled
  battle examples.
- Framework-neutral trainer-input JSONL round trip, model-input packing, and
  deterministic action-score contract checks.
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests

- `143` tests pass on Windows Python as of this review.
- The two CommunicationMod fixture smokes pass.
- `python -m compileall -q src tests` passes.
- `ruff check src tests` and `ruff format --check src tests` pass.

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- explicit online-controller provenance and one authoritative controlled-run
  executor;
- checkpoint capture/restore and battle-start pools;
- fixed structural battle evaluation;
- native Oracle-like search integration and search-teacher datasets;
- artifact migrations and complete decision provenance;
- PyTorch policy/value training;
- structured persistent resource outcomes;
- sanitized public run context or complete public run history;
- constructed A20 battle-start supplements;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The first
tasks in dependency order are:

1. [`T002`](tasks/T002-controlled-run-foundation.md), currently `IN_REVIEW`:
   resolve the documented routed-controller reproducibility propagation blocker.
2. Review the remaining blocked task specifications against the architecture
   as their prerequisites merge.

Later tasks are dependency-ordered in the task index. A task is not ready for a
new branch until its status is `READY`.

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
