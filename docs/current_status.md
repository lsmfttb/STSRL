# Current Status

Last reviewed: 2026-06-23.

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
- Framework-neutral simulator contracts and a Python adapter for the pinned
  external `sts_lightspeed` source integration.
- Real simulator execution is documented and performed through WSL.
- Versioned external `sts_lightspeed` source manifest
  (`docs/sts_lightspeed_source_manifest.json`) and canonical source verifier
  (`scripts/verify_lightspeed_source.sh`). The manifest pins upstream
  `gamerpuppy/sts_lightspeed` base commit
  `7476a81954020087da31d41d16fddf475746ec2d` and integration ref
  `refs/heads/stsrl/t006-oracle-search-teacher-v1` at commit
  `78c3fa86ea4d8ef2c8c490aabfb8047d38d6d077`. The old ordered patch stack is
  retained only as retired provenance.

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
- Versioned raw native public projection capability
  (`native-public-projection-v1`) on `StepSimulator`, with a diagnostic
  capability report and audit gate. It reports current screen identity,
  candidate actions from `StepSimulator::legalActions`, and currently audited
  persistent resources with native source counts. Visible Act Boss, complete
  map/routes, current node, and screen-specific payloads remain explicit
  capability gaps. The raw projection is not a sanitized controller input.
- Versioned sanitized in-memory public run context
  (`public-run-context-v1`) and ordered public history entries
  (`public-run-history-entry-v1`) are attached to controlled-run and live
  `DecisionContext` construction. `execute_controlled_run` appends one
  contiguous typed history entry after each successful visible transition,
  rejects malformed raw native projections before controller use, and exposes
  the stable in-memory context/history contract used by current artifacts.
- Current public-context artifact propagation and audit. Battle-start pools,
  fixed cohorts, fixed evaluation reports, battle decisions, trainer inputs,
  and model inputs preserve public-context status, sanitized public run
  context, and explicit context-loss provenance. Portable replay compares
  reconstructed public context, and the WSL-facing public-context audit checks
  schema validity, forbidden hidden fields, candidate parity, replay
  mismatches, and coverage.
- Seeded structural resampling of natural battle starts, with source identity,
  sampling component, structural coverage, and completed battle outcomes kept
  separate from repeated sample weight.
- Versioned fixed structural cohorts selected without replacement from portable
  natural battle-start pools, plus fresh-adapter restored-battle evaluation.
  Reports retain per-battle provenance and failures, controller telemetry, and
  separate natural-weighted, encounter-macro, room-type-macro, and
  per-stratum aggregates.
- Explicitly Oracle-like native battle search teacher pipeline. The pinned
  `sts_lightspeed` source exposes `StepSimulator.battle_search`; the
  `OracleSearchController`, teacher JSONL artifact, and same-cohort Oracle
  fixed evaluation all declare `full_simulator_state_oracle_like`, retain
  occurrence-safe legal-action identities, keep teacher action and soft visit
  target separate, and compare `highest_mean` with a `most_visits` diagnostic
  on immutable T005 cohorts. This is diagnostic upper-bound/search-teacher
  infrastructure only, not normal-information or live-game performance.
- A training-readiness report that validates plumbing only. It does not train a
  model or demonstrate policy strength.

### Tests And Runtime Evidence

- `445` tests pass on Windows Python as of this review. In an uninstalled
  checkout, set `PYTHONPATH=src` (or install the package) before invoking the
  CLI directly.
- The two CommunicationMod fixture smokes pass.
- `python -m compileall -q src tests` passes.
- `ruff check src tests` and `ruff format --check src tests` pass.
- The T010 A20 natural calibration over seeds `1..100` reports 2,303
  non-combat decisions with complete provenance and no driver problems;
  unreached Boss relic screens remain explicit natural-coverage gaps.
- The legacy ordered `sts_lightspeed` patch-stack build passed from external
  commit `7476a81` before T017 retired that workflow. A T004 A20 pool over
  seeds `1..3` contains 13 natural starts with 10 reported wins, 3 losses, no
  missing completed outcome, and 13/13 fresh-adapter portable restores.
- T005's legacy clean WSL patch-stack gate freezes 8 unique starts from that
  pool and evaluates them through fresh portable restores with the
  normal-public `preferred_kind` controller. The plumbing run reports 5 wins
  and 3 losses, no truncation or evaluation errors, and all three aggregate
  views. This is fixed-evaluation evidence only, not an A20 policy-strength
  result.
- The T011 clean WSL gate and A20 tactical-feature audit pass. Across
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
- T014 validates the raw native public-projection capability over seeds `1..3`
  at A20 with 289 current decision screens: `BATTLE=236`, `CARD_SELECT=2`,
  `EVENT_SCREEN=4`, `MAP_SCREEN=16`, and `REWARDS=31`. The canonical
  `build-py` audit reports 1,209 resource snapshot comparisons, 0 resource
  mismatches, 289 candidate-action parity passes, 289 checkpoint projection
  passes, no checkpoint failures, and explicit coverage gaps for
  `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and `TREASURE_ROOM`.
- T016 validates public-context artifact propagation and replay audit over a
  WSL A20 bounded run with 327 current decision screens, 15 battle-start
  records, 15/15 replay public-context matches, and 0 parity, schema,
  forbidden-field, replay, or run failures. The current natural coverage gaps
  remain `BOSS_RELIC_REWARDS`, `REST_ROOM`, `SHOP_ROOM`, and `TREASURE_ROOM`.
  The same post-review WSL smoke and battle-training-readiness gates pass.
- The T017-managed pinned external source integration currently validates from
  manifest `sts-lightspeed-source-manifest-v1` version 1. The canonical source
  verifier builds integration commit
  `78c3fa86ea4d8ef2c8c490aabfb8047d38d6d077`,
  initializes `json` and `pybind11`, imports `slaythespire.StepSimulator`, and
  asserts the current native capability inventory including
  `native_battle_search_root`. Missing-manifest and wrong-commit verifier
  checks fail nonzero. `/home/lsmft/stsrl-spikes/sts_lightspeed/build-py` was
  rebuilt from that pinned source and imports `slaythespire` from the rebuilt
  directory. The required WSL smoke, public-projection capability,
  public-context replay, and battle-training-readiness gates pass.
- T006 validates Oracle-like search teacher collection and fixed-cohort
  comparison on the T004/T005 A20 smoke data. A fresh pool over seeds `1..3`
  produced 13 natural starts; the frozen cohort selected 8 starts with
  identity `c29d7852c941d592`. Teacher collection at 20 native simulations
  produced 13 rows, 120 root rows, 260 root visits, and 3,621 native simulator
  steps with deterministic non-timing JSONL content across repeated runs.
  Oracle fixed evaluation at 20 simulations evaluated both `highest_mean` and
  `most_visits` on the same cohort with no truncations, restore errors, or
  root-mapping failures.

## Not Implemented On Main

The following capabilities exist only as plans, experiment evidence, or
unmerged legacy work:

- PyTorch policy/value training;
- interactive live-game or A20 performance validation for any controller;
- structured persistent resource outcomes;
- constructed A20 battle-start supplements;
- normal-information belief search.

Do not use documentation or results from these areas as evidence that `main`
already supports them.

## Immediate Work

Executable task specifications live in [`tasks/`](tasks/README.md). The first
tasks in dependency order are:

1. T005, fixed structural battle evaluation, is complete. It provides the
   comparison surface required before search promotion.
2. T017, stable `sts_lightspeed` source integration, is complete. It replaces
   the day-to-day local patch-stack workflow with a pinned external source
   integration for future native simulator surface.
3. T006, Oracle search teacher pipeline, is complete. It is confined to the
   explicitly Oracle-like simulator regime and provides diagnostic teacher data
   and same-cohort Oracle fixed-evaluation comparison only.
4. T007 is `CANCELLED`. PR #9 remains closed and is not a branch base. Its
   former cross-cutting scope is split into T014--T016; see
   [`t007_review_handoff_2026-06-22.md`](t007_review_handoff_2026-06-22.md).
5. T014, native public projection capability, is complete. It provides only
   the reproducible raw native capability matrix, action parity, and checkpoint
   evidence; it does not provide sanitized controller context.
6. T015, public run context and controlled history, is complete. It provides
   the sanitized in-memory public context/history contract that T016 now
   persists through current artifacts.
7. T016, public-context artifacts, replay, and audit, is complete. It extends
   the T015 public-context contract through current persisted artifacts,
   portable replay comparison, and the WSL context audit.
8. T008, A20 constructed battle supplements, and T012, structured battle
   resource outcomes, are `READY` and should extend native simulator surface
   through the T017-managed source integration. T009 remains blocked until its
   remaining data prerequisite, T012, is complete.

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
that are currently available on `main`. The canonical day-to-day source path is
the pinned integration recorded in
[`sts_lightspeed_source_manifest.json`](sts_lightspeed_source_manifest.json)
and verified by `scripts/verify_lightspeed_source.sh`. Runtime gates use
`/home/lsmft/stsrl-spikes/sts_lightspeed/build-py` rebuilt from that pinned
source.
