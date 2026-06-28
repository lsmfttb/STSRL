# T040: Expert Non-Combat Driver V1

## Objective

Implement a versioned seeded A20 heuristic non-combat driver,
`expert_non_combat_v1`, for source generation.

The driver is a data-generation prior, not the final agent and not a
normal-information performance claim. Its purpose is to produce higher-quality
A20 complete-run source distributions than `stochastic-v1` by making
non-combat choices more like a competent A20 player while battle decisions
remain controlled by the configured battle controller.

## Current Main Baseline

T037 showed that `stochastic-v1` non-combat decisions plus
20-simulation no-potion Oracle-like battle search can recover a small
Boss/Act2 signal at 1,000 terminal A20 runs, but the distribution is still
overwhelmingly Act 1: 4,685 of 4,688 battle starts were Act 1, only three were
Act 2, and Acts 3--4 were zero. T035 confirmed that continuing to adjust
root-only model guidance over narrow data does not currently improve the fixed
smoke cohort.

The upstream planning input for this batch identifies the current bottleneck
as source-generation quality: battle search cannot compensate for consistently
poor card, route, potion, shop, rest, and event decisions from an overly random
non-combat driver.

## Dependencies

- T010, T016, T017, T025, T036, T037, T039, and T035 are complete.
- The pinned `sts_lightspeed` source remains the authoritative simulator for
  large-scale source generation and WSL gates.

## Inputs And Artifacts

Inputs must be generated from current `main` commands or explicitly documented
external/ignored artifact paths. Do not consume temporary T037/T039/T032
worktree outputs as implicit inputs.

Large generated source pools, coverage reports, reachability reports, shards,
and logs stay under ignored `artifacts/` paths or explicit external paths. The
PR must report artifact paths, schema ids, source identities, record counts,
seed/source-run ranges, and SHA-256 identities.

## Scope

- Add a new versioned non-combat driver name, `expert_non_combat_v1`, with
  complete controller provenance.
- Keep the driver seeded and stochastic. Heuristics change hierarchical priors;
  they must not create one deterministic route or remove low-probability legal
  choices.
- Cover the first version of A20 heuristics for:
  - card reward choices, including early damage, defense, draw, energy,
    scaling, skip rate, and avoiding obvious deck pollution;
  - route choices based on visible HP, potion inventory, deck/relic strength
    proxies, and visible Act Boss;
  - rest-site choices between rest, upgrade, and other legal options;
  - shop choices including removes, potions, high-impact cards/relics, and
    gold retention;
  - event choices using conservative visible-state rules;
  - relic, treasure, potion, discard, and key choices while preserving legal
    low-probability alternatives.
- Use simulator-provided legal actions and public projections. Do not
  reimplement Slay the Spire mechanics locally.
- Add a source-coverage comparison command/report for these arms:
  - `stochastic-v1 + oracle_search_s20`;
  - `expert_non_combat_v1 + oracle_search_s20`;
  - `expert_non_combat_v1 + oracle_search_s100`.
- Report source coverage, not policy strength: terminal source runs,
  battle starts by act/room/encounter, Act 1 Boss starts, Act 2/3/4 starts,
  elite starts, battle win/loss by act, restore status, public-context status,
  structured-outcome status, run-summary status, and T009 gate status.

## Out Of Scope

- Learned non-combat policy training.
- Neural model training, checkpoint refresh, teacher collection, or controller
  promotion.
- Claiming natural A20, normal-information, live-game, or final-agent
  performance from this driver.
- Deterministic hand-authored routes or local reconstruction of map, reward,
  event, shop, relic, potion, or encounter mechanics.
- Assisted HP/potion/encounter continuation; that belongs to T042.

## Design Constraints

- Preserve the current battle/non-combat split. The trainable scope remains
  battle decisions; this driver is a separately named source-generation driver.
- Preserve complete non-combat provenance: driver name/version, seed, visible
  state inputs used by each rule group, prior weights, selected legal action,
  and any fallback or unsupported-screen reason.
- Keep natural-run, expert-driver source, constructed supplement, assisted-run,
  Oracle-like, and normal-information distributions separately tagged and
  reported.
- The driver may use only player-visible information and public context.
  Hidden RNG, unrevealed future encounters, hidden draw order, and hidden
  Act-3 second Boss information are forbidden.
- Large WSL source-generation, restore, coverage, and report stages must be
  sharded and run with explicit parallel workers by default. Source collection
  parallelism does not justify a single-worker coverage or restore gate.

## Deliverables

- `expert_non_combat_v1` implementation and provenance.
- Focused tests for seeded stochasticity, low-probability branch reachability,
  legal-action selection, hidden-field firewall, fallback behavior, and
  provenance.
- Source-coverage comparison workflow and report schema.
- WSL comparison artifacts or explicit external artifact paths for the three
  required arms.
- Documentation impact notes explaining how the new driver changes source
  distribution generation without becoming a promoted controller.

## Acceptance Criteria

- `expert_non_combat_v1` is explicitly constructible by name and emits complete
  behavior-changing provenance.
- The same seed/configuration is reproducible, while different seeds preserve
  legal low-probability branches.
- The driver never selects an illegal action and never consumes hidden or
  simulator-only future information.
- The required three-arm comparison is reported at 1,000 terminal A20 source
  runs per arm, or the PR explicitly fails the scale target and does not ask to
  accept source-coverage claims.
- The comparison shows clearly better Boss/Act2 reachability for
  `expert_non_combat_v1` than the `stochastic-v1` baseline under the same
  battle controller, or the PR is treated as a failed heuristic attempt and the
  task is not accepted without a maintainer task-spec revision.
- All accepted artifacts preserve restore, public-context, structured-outcome,
  source identity, distribution tag, and SHA linkage.

## Required Verification

Run the standard local gates from `docs/tasks/README.md`, focused driver/report
tests, task-doc checks, and `git diff --check`.

Before WSL evidence, run the pinned source verifier:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Run the required WSL source-generation, restore/coverage, and report rebuild
stages with explicit shards and parallel workers. The PR report must include
the full commands, shard/worker counts, seed/source-run ranges, wall-clock
costs, and any single-worker smoke/debug/tooling-limited reason per stage.

## Legacy Reference

Consult T010, T036, T037, T039, `docs/project_architecture.md`, and
`docs/a20_later_act_boss_source_coverage_contract.md`. Historical experiment
logs may inform comparison baselines, but task acceptance uses current-schema
artifacts generated from latest `main`.

## PR Report

The PR must report task ID, driver version, heuristic rule groups, hidden-field
firewall, source arm definitions, search budgets, action spaces, non-combat
driver seeds/configuration, seed ranges, step caps, artifact paths and hashes,
coverage summaries, restore/public-context/structured-outcome status, T009
gate result, shard/worker/runtime evidence for every WSL stage, verification
results, known limitations, and whether the reachability improvement gate was
met.
