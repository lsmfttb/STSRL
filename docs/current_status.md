# Current Status

Last reviewed: 2026-06-22.

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
- Live CommunicationMod runtime entry point that consumes one JSON observation,
  exposes only the sanitized public tactical contract to an `OnlineController`,
  emits at most one protocol command, and fails closed on unsupported or
  incomplete battle decisions.
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
- Versioned `public-tactical-v2` structured state/action contract with a
  compatibility numeric view. It carries visible hand, discard, and exhaust
  members; monster identity, canonical intent category, and simulator current
  move; player powers; potion identities; and relic identities with counters.
  Simulator-only or live-missing fields remain explicit in the parity report.
- Battle-only decision batches and contiguous battle-segment reports.
- Candidate reward components, a draft scalar reward report, and reward-labeled
  battle examples.
- Framework-neutral trainer-input JSONL round trip, model-input packing, and
  deterministic action-score contract checks.
- Versioned trainer-input artifact migration, complete decision provenance,
  and occurrence-disambiguated portable action identities.
- Versioned seeded stochastic non-combat driver with screen-level relative
  weights, non-combat potion eligibility, conditional-reachability tests, and
  natural A20 coverage/provenance calibration.
- Native, process-local simulator checkpoints and portable battle-start pool
  manifests. Fresh adapters restore portable records by replaying the source
  seed and occurrence-disambiguated action trace; opaque native state is never
  serialized.
- Seeded structural resampling of natural battle starts, with source identity,
  sampling component, structural coverage, and completed battle outcomes kept
  separate from repeated sample weight.
- Versioned fixed structural cohorts selected without replacement from portable
  natural battle-start pools, plus fresh-adapter restored-battle evaluation.
  Reports retain per-battle provenance and failures, controller telemetry, and
  separate natural-weighted, encounter-macro, room-type-macro, and
  per-stratum aggregates.
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests And Runtime Evidence

- `407` tests pass on Windows Python as of this review. In an uninstalled
  checkout, set `PYTHONPATH=src` (or install the package) before invoking the
  CLI directly.
- The two CommunicationMod fixture smokes pass.
- `python -m compileall -q src tests` passes.
- `ruff check src tests` and `ruff format --check src tests` pass.
- The T010 A20 natural calibration over seeds `1..100` reports 2,303
  non-combat decisions with complete provenance and no driver problems;
  unreached Boss relic screens remain explicit natural-coverage gaps.
- The reproducible `sts_lightspeed` patch-stack build passes from external
  commit `7476a81`. A T004 A20 pool over seeds `1..3` contains 13 natural
  starts with 10 reported wins, 3 losses, no missing completed outcome, and
  13/13 fresh-adapter portable restores.
- T005's clean WSL patch-stack gate freezes 8 unique starts from that pool and
  evaluates them through fresh portable restores with the normal-public
  `preferred_kind` controller. The plumbing run reports 5 wins and 3 losses,
  no truncation or evaluation errors, and all three aggregate views. This is
  fixed-evaluation evidence only, not an A20 policy-strength result.
- The T011 clean WSL patch stack and A20 tactical-feature audit pass. Across
  one bounded seed it observed 81 battle snapshots and 497 legal actions with
  `public-tactical-v2` state/action compatibility sizes of 4,634/92 and no
  required simulator-projection failures. A captured CommunicationMod audit
  covers 3,347 battle snapshots; its documented live-missing fields remain a
  deployment constraint for T013, not an implicit simulator fallback.
- T013 validates the live adapter against captured CommunicationMod messages:
  public-state sanitization, duplicate actions, target/potion command mapping,
  explicit targetability fallback, complete runtime provenance, and no-command
  failure paths. Across the capture corpus, all 2,352 states with a playable
  targeted card and a positive-HP non-gone monster produce target actions.

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- native Oracle-like search integration and search-teacher datasets;
- PyTorch policy/value training;
- interactive live-game or A20 performance validation for any controller;
- structured persistent resource outcomes;
- sanitized public run context or complete public run history;
- constructed A20 battle-start supplements;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The first
tasks in dependency order are:

1. T005, fixed structural battle evaluation, is complete. It provides the
   comparison surface required before search promotion.
2. T006 now has all implementation prerequisites, but remains `BLOCKED` while
   the main maintainer reviews and republishes its task specification against
   the T005 evaluation contract.
3. T007, complete public run history, is `BLOCKED` pending task redesign. PR
   #9 is an unmergeable implementation attempt; see
   [`t007_review_handoff_2026-06-22.md`](t007_review_handoff_2026-06-22.md).
   No branch may resume it until the main maintainer publishes replacement task
   specifications.
4. T008 remains blocked by T007. T012 now awaits T007 so its terminal-resource
   labels extend one stable evaluation and public-context contract rather than
   creating parallel artifact fields.

Later tasks are dependency-ordered in the task index. A task is not ready for a
new branch until its status is `READY`.

The adapter and captured-sample compatibility gate in
[`T013`](tasks/T013-live-communicationmod-runtime-adapter.md) is complete.
Simulator-only RL training does not depend on it. No trained or search
controller, nor any interactive real-game performance, has yet been validated.

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
that are currently available on `main`. On 2026-06-22 the canonical `build-py`
directory was absent; rebuild it before treating direct simulator smokes as
current evidence.
