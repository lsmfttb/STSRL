# T041: Potion-Enabled Oracle Search Repair

## Objective

Repair the potion-enabled Oracle-like search artifact failure so potion legal
actions can be used in source generation, fixed evaluation, and teacher data
without root-row/root-visit mapping failures.

This task is an engineering repair. It does not promote a controller or claim
normal-information strength.

## Current Main Baseline

T037 accepted the no-potion Oracle-like search scale-up as the durable
later-act/Boss source-coverage contract. The potion-enabled diagnostic attempt
failed closed with a root mapping problem:

```text
native root visits do not equal summed root-row visits: 20 != 16
```

Historical logs suggest potion-enabled search can materially improve Act 1
Boss outcomes and terminal HP, but no current-schema potion-enabled artifact is
accepted while root mapping can fail.

## Dependencies

- T006, T017, T020, T025, T036, T037, and T039 are complete.
- T041 is independent of T040 and may proceed in parallel.

## Inputs And Artifacts

Inputs must be current-schema fixed cohorts or source pools generated from
current `main` commands, committed fixtures, or explicit external/ignored
artifact paths with schema, provenance, regeneration commands, and SHA-256
identities.

Do not consume temporary T037 potion diagnostic shards as implicit inputs.

## Scope

- Diagnose and fix potion-enabled Oracle root-row/native-root-visit mapping.
- Ensure every legal potion action in the search root can be represented by an
  occurrence-safe public action identity and matched back to native root rows.
- Preserve duplicate legal action disambiguation for cards, potions, targets,
  end-turn, and any other legal action kinds.
- Add focused regression fixtures for potion legal actions and the historical
  `20 != 16` failure shape.
- Re-run a small Act 1 Boss fixed-cohort no-potion vs potion-enabled
  comparison.
- Report root mapping failures, battle wins/losses, terminal HP, potion
  inventory deltas, native simulator steps, model-call telemetry, wall-clock
  cost, and action-space provenance.

## Out Of Scope

- New non-combat heuristics.
- Assisted complete-run generation.
- Neural training, checkpoint refresh, teacher scale-up, or controller
  promotion.
- Local potion mechanics or local legal-action enumeration.
- Treating potion-enabled Oracle-like search as normal-information policy
  strength.

## Design Constraints

- `BattleScumSearcher2` remains `full_simulator_state_oracle_like` while it
  copies hidden simulator state.
- The simulator owns potion legality, potion identity, targetability, state
  mutation, and battle advancement.
- Repository code may normalize identities and validate mappings, but must not
  patch around simulator behavior with invented game mechanics.
- Mapping failures fail closed and remain visible in telemetry.
- Any new artifact schema or report field must preserve migration and
  backward-compatible reader behavior.

## Deliverables

- Root-row/root-visit mapping repair and tests.
- Occurrence-safe potion legal-action identity tests.
- Potion-enabled fixed-evaluation or restored-battle comparison workflow.
- A current-schema no-potion vs potion-enabled Act 1 Boss cohort report with
  explicit artifacts and hashes.
- Documentation impact notes explaining the accepted potion-enabled evidence
  boundary.

## Acceptance Criteria

- The historical root mapping failure shape is covered by a regression test.
- Potion-enabled Oracle-like search reports zero root mapping failures on the
  accepted fixed cohort.
- Every compared battle has complete source identity, action-space provenance,
  search budget, root visits, native-step telemetry, terminal HP, potion
  inventory delta, and restore/public-context/structured-outcome status.
- The no-potion and potion-enabled comparison uses the same restored source
  starts.
- The PR makes no normal-information, live-game, broad-training, or controller
  promotion claim.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused Oracle search
mapping tests, task-doc checks, and `git diff --check`.

Before WSL evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run WSL restored-battle or fixed-cohort evidence on explicitly reported paths.
If the WSL stage grows beyond smoke/debug scale, it must be sharded and run
with explicit parallel workers, and the PR must report shard/worker counts and
wall-clock cost per stage.

## Legacy Reference

Consult T006, T025, T036, T037, T039, `docs/experiment_log.md`, and
`src/sts_combat_rl/sim/oracle_search.py`. Historical potion results motivate
the repair but are not accepted current-schema artifacts.

## PR Report

The PR must report task ID, failure diagnosis, repaired mapping behavior,
cohort identity, no-potion and potion-enabled command lines, artifact paths and
hashes, root mapping failure counts, win/loss and terminal-HP summaries,
potion inventory deltas, telemetry, verification results, documentation
impact, and known limitations.
