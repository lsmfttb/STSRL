# T037: A20 Search-Controlled Reachability Scale-Up

## Objective

Use the T036 current-schema command/report path to run a meaningful A20
search-controlled source-generation scale-up and decide whether the historical
2026-06-14 Boss/Act2 reachability result can be reproduced on current `main`.

This task is about source reachability, not model training. It determines
whether the battle-first plan can continue by scaling search-controlled source
collection, or whether the next task must diagnose driver/source drift.

## Current Main Baseline

T036 added `--lightspeed-search-battle-start-pool` and
`--a20-reachability-report`. Its accepted smoke artifacts compared the default
controller, 20-simulation no-potion Oracle-like search, and 20-simulation
potion-enabled Oracle-like search over 10 A20 terminal source runs per arm.
All arms stayed in Act 1 and reached no Boss or later-act starts.

Historical evidence from 2026-06-14 used 1,000 terminal A20 runs with a
20-simulation no-potion Oracle-like battle controller and reached 35 Act 1 Boss
starts plus one Act 2 battle start. The scale difference is too large for T036
to settle the route decision.

## Dependencies

- T036 is complete.
- T017 and T020 remain the pinned `sts_lightspeed` source contracts.

## Inputs And Artifacts

Inputs must be generated from current `main` commands or explicitly documented
external/ignored artifact paths. Do not consume another worktree's temporary
T036 smoke outputs as implicit inputs.

Large generated pools, shards, coverage reports, and reachability reports stay
under ignored `artifacts/` paths or explicit external paths. The PR must report
artifact paths, schema ids, source identities, record counts, and SHA-256
identities.

## Scope

- Run a scaled A20 `oracle_search_v1_highest_mean_s20` no-potion source arm
  through the T036 search-controlled complete-run collection path. The target is
  1,000 terminal source runs to match the historical comparison point.
- If the 1,000-run target is not completed in the PR, report the completed
  shard count, terminal source-run count, wall-clock cost, projected cost to
  1,000 terminal runs, and the reason the task should be accepted as a
  budget-limited scale audit rather than a reachability reproduction.
- Include a potion-enabled search arm when runtime permits. If it is not run at
  comparable scale, report it as a smaller diagnostic arm, not as a replacement
  for the no-potion historical comparison.
- Rebuild coverage and reachability reports from the scaled artifacts. Reports
  must include restore status, public-context status, structured outcome status,
  run-summary status, source identity, artifact SHA linkage, terminal floors,
  starts by act/room/encounter, Boss starts, later-act starts, and T009 gate
  status.
- Compare the result explicitly with the 2026-06-14 historical 1,000-run
  evidence and explain whether any difference is scale, runtime budget, driver
  behavior, controller behavior, or unresolved.
- Recommend exactly one next step: accept a later-act/Boss source-coverage
  contract task, run the T038 source-drift audit, or revise T032 into an
  explicit Act-1-only diagnostic refresh.

## Out Of Scope

- Neural training, checkpoint refresh, teacher scale-up, or calibration.
- Promoting a controller or claiming normal-information/live-game performance.
- Replacing the non-combat driver with a learned policy.
- Local Slay the Spire mechanics reconstruction.
- Treating Oracle-search source reachability as normal public-policy strength.

## Design Constraints

- Use `execute_controlled_run` through the T036 complete-run source collection
  path.
- Preserve separate battle and non-combat controller provenance.
- Tag Oracle-search-controlled source distributions as
  `full_simulator_state_oracle_like`.
- Run real simulator evidence through WSL against the pinned `sts_lightspeed`
  source.
- Sharding is allowed, but the final report must make shard identity,
  deduplication, source-run counts, and regeneration commands explicit.
- Under-reachability is a valid result. Missing artifact identity, restore
  failures, malformed provenance, missing source identity, or hidden-field
  leakage fail closed.

## Deliverables

- Scaled source-pool artifacts or explicitly reported shards.
- Coverage and reachability reports with artifact identities and regeneration
  commands.
- An experiment-log entry or equivalent PR report comparing T037 with T036 and
  the 2026-06-14 historical evidence.
- Documentation impact notes saying whether T032 remains blocked and which next
  task should become `READY`.

## Acceptance Criteria

- The no-potion Oracle-like search arm reaches the documented target scale, or
  the PR justifies an explicitly budget-limited scale audit with enough runtime
  evidence to decide the next task.
- Every compared arm has complete controller, source identity, artifact SHA,
  seed range, source-run count, step cap, and action-space provenance.
- Coverage and reachability reports fail closed on missing source identity,
  missing pool SHA linkage, corrupted source-run summaries, restore failures,
  or malformed provenance.
- Boss/later-act reachability is reported explicitly, including zero.
- T032 is not advanced unless a maintainer separately accepts a later-act/Boss
  source-coverage contract or explicitly narrows T032.

## Required Verification

Run documentation checks and `git diff --check` for a report-only PR. If code
changes are made, run the standard local gates from `docs/tasks/README.md`.

Before WSL evidence, run:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL source collection, coverage, and reachability commands on explicitly
reported paths. Include full commands in the PR.

## PR Report

The PR must report task ID, exact commands, source arm definitions, search
budgets, action spaces, non-combat driver, seed ranges, step caps, artifact
paths and SHA-256 identities, reachability summaries, restore/public-context/
structured-outcome status, T009 gate result, comparison with T036 and
2026-06-14, recommended next task, verification results, and known runtime
limits.
