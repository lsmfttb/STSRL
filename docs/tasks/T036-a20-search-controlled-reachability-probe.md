# T036: A20 Search-Controlled Reachability Probe

## Objective

Rebuild the historical A20 Boss/later-act reachability experiment on current
schemas by collecting complete-run battle-start source pools with a stronger
search-controlled battle controller and the existing separately named
non-combat driver.

This task answers whether the T031 Act-1-only result is mainly caused by the
weak default battle controller, or whether later-act source generation needs a
different data mechanism or a change in project direction.

## Current Main Baseline

T031 refreshed A20 coverage with 50 source episodes and found healthy
artifacts/restores but only Act 1 battle starts. Historical experiment-log
evidence from 2026-06-14 used a calibrated stochastic non-combat driver and a
20-simulation no-potion Oracle-like battle controller over 1,000 terminal runs;
it reached 35 Act 1 Boss starts and one Act 2 battle start. Potion-enabled and
higher-budget search improved Boss and the lone Act 2 battle outcomes.

Current `main` has `OracleSearchController`, search telemetry, controlled-run
advancement, public context propagation, structured outcomes, and current A20
coverage reports. However, the generic `--lightspeed-battle-start-pool`
command is wired through simple `DecisionPolicy` choices and does not provide a
documented current-schema command for complete-run source collection under an
Oracle search battle controller.

## Dependencies

- T031 is complete.
- T006, T017, T020, T025, and T029 remain current search/simulator contracts.

## Inputs And Artifacts

Inputs are generated from current commands, fixtures, or newly added command
surfaces in this task. Generated pools, coverage reports, reachability reports,
and optional constructed audits must remain under ignored `artifacts/` paths or
explicit external paths. No large generated artifact is committed.

Every generated artifact must report:

- source manifest identity and pinned `sts_lightspeed` commit;
- battle controller kind/version, information regime, search budget, action
  space, and root-selection rule;
- non-combat driver kind/version and seed;
- seed range, source episode count, step cap, and regeneration command;
- SHA-256 identities where emitted or easily computed.

## Scope

- Add the minimal current-schema command or command option needed to collect
  natural battle-start pools from complete controlled runs whose battle child
  is `OracleSearchController`.
- Preserve the existing battle/non-combat split by routing battle decisions to
  the search controller and non-combat decisions to the separately named
  stochastic driver.
- Preserve complete controller provenance on every source start. The
  search-controlled source distribution must be tagged
  `full_simulator_state_oracle_like`; it is not normal-information data.
- Run an A20 reachability comparison that includes the current default
  preferred-kind/stochastic-driver distribution and at least one
  Oracle-search/stochastic-driver distribution. The PR may use a staged scale
  plan, but it must explain the episode count, time budget, and whether the run
  is enough to compare with the 2026-06-14 historical result.
- Include no-potion search and, if runtime permits, a potion-enabled search arm
  because historical evidence says potion handling materially affects Boss and
  Act 2 reachability.
- Report battle starts by act, room type, encounter id, Boss/later-act
  reachability, terminal floor, battles per source run, battle outcomes,
  restore/public-context/structured-outcome availability, and T009 gate cells.
- Decide which follow-up is justified: broader search-controlled source
  collection, non-combat-driver calibration, constructed or paired supplements,
  an explicitly narrow Act-1 teacher/checkpoint refresh, or a larger direction
  change.

## Out Of Scope

- Training a neural model or refreshing a checkpoint.
- Teacher dataset scale-up except for optional tiny smoke rows needed to prove
  artifact compatibility.
- Claiming broad A20 training readiness, controller strength, live-game
  validation, or normal-information performance.
- Local Slay the Spire mechanics reconstruction.
- Replacing the non-combat driver with a learned non-combat policy.
- Treating Oracle-search-controlled reachability as a normal public policy
  result.

## Design Constraints

- Use `execute_controlled_run` or the current complete-run advancement path.
- Keep battle and non-combat controller provenance separate and inspectable.
- Keep stdout protocol-safe; CLI workflows report to stderr or files.
- Real simulator evidence runs through WSL against the pinned
  `sts_lightspeed` source.
- Under-reachability is a reportable result, not a command failure. Artifact
  validation, restore failures, malformed provenance, source mismatches, or
  hidden-field leakage fail closed.
- Do not overload `DecisionPolicy`-only APIs in a way that makes Oracle search
  look like an ordinary normal-information policy.

## Deliverables

- Minimal code/CLI support for search-controlled complete-run source
  collection, if current command surfaces cannot already express it.
- One reachability report or experiment-log entry comparing the configured
  source distributions.
- Ignored or external current-schema artifacts with reported identities and
  regeneration commands.
- Documentation impact notes explaining whether T032 should remain blocked,
  be narrowed to an Act-1 diagnostic refresh, or wait for a larger later-act
  source pool.

## Acceptance Criteria

- Search-controlled complete-run source collection is reproducible from the PR
  commands and writes current-schema source artifacts.
- Every source start preserves battle-controller, non-combat-controller,
  search-budget, action-space, seed, and information-regime provenance.
- The report separates default-controller, Oracle-search, potion-enabled,
  natural, sampled, constructed, and paired distributions where present.
- Boss and later-act reachability are reported explicitly, including the case
  where they remain zero.
- Restore, public-context, structured-outcome, and broad-training-gate status
  are reported for every generated pool.
- The PR explicitly compares its result with the historical 2026-06-14 evidence
  and explains why any scale difference matters.
- The PR does not advance T032 or claim broad A20 evidence unless the
  maintainer updates the task index after review.

## Required Verification

Run the standard local gates if code changes are made:

```bash
pytest
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```

Run focused tests for the new command/controller wiring, provenance,
information-regime labels, restore compatibility, and failure cases.

Run the pinned-source verifier before WSL evidence:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL reachability evidence on explicitly reported artifacts. Exact commands
may differ if the task adds a new CLI surface, but the PR must report the full
commands, output paths, artifact identities, source coverage summary, and
known runtime limits.

## Legacy Reference

Use the 2026-06-14 entries in `docs/experiment_log.md` and the historical
search-controlled collection notes in `docs/history/first_battle_trainer_plan.md`
as context only. They are not current artifact contracts and must be rebuilt on
current schemas before they can guide T032.

## PR Report

The PR must report task ID, controller arms, search budgets, action spaces,
non-combat driver, source manifest identity, exact local and WSL commands,
artifact paths and identities, reachability summaries, restore/public-context/
structured-outcome availability, T009 gate result, comparison with historical
Boss/Act2 evidence, recommended next task, verification results, and legacy
material consulted.
