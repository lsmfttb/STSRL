# A20 Later-Act/Boss Source Coverage Contract

Last reviewed: 2026-06-27.

This contract records the accepted source-coverage boundary from T037. It
defines which coverage artifacts later data tasks may consume, how reviewers
can verify or regenerate them, and what claims those artifacts do and do not
support.

## Contract Decision

The accepted T037 no-potion Oracle-like search arm is a usable narrow
Boss/later-act source supplement. It is not broad A20 training coverage.

T032 should not become `READY` unchanged as a broad A20 teacher/checkpoint
refresh. Before it becomes `READY`, the main maintainer should revise it into a
narrow diagnostic refresh that consumes this contract, or keep it blocked until
a broader per-act coverage contract exists.

The accepted contract supports:

- refreshing teacher/trainer/checkpoint/calibration diagnostics on the accepted
  Act 1, Act 1 Boss, and Act 2 source starts;
- explicitly reporting the rare Boss/later-act rows as a supplement to the
  dominant Act 1 distribution;
- preserving T009 broad-training gate failure as evidence, not bypassing it.

The accepted contract does not support:

- broad A20 teacher/checkpoint refresh claims;
- normal-information, live-game, controller-strength, or promotion claims;
- treating repeated samples, teacher budgets, or checkpoint rows as new source
  coverage.

## Accepted Source Distribution

The only source distribution accepted for follow-up consumption is:

```text
contract id: t037-oracle-s20-no-potion-source-coverage-v1
ascension: A20
source seeds: 1..1000
source runs: 1000 terminal runs, 0 truncated runs
step cap: 500
source collection: 40 shards x 25 terminal source runs
battle controller: oracle_search_v1_highest_mean_s20
native search budget: 20 simulations per battle decision
root selection: highest_mean
action space: initial_no_potions
non-combat driver: stochastic-v1
information regime: full_simulator_state_oracle_like
simulator source: sts_lightspeed integration commit 242344c57c17c784708a6f072c905febc3f96527
```

The source-generation controller is routed: Oracle-like search controls battle
decisions, and the separately named stochastic non-combat driver controls
non-combat decisions. This is still a `natural_run` battle-start pool because
the starts are reached by complete controlled runs rather than constructed
transforms, but the acting battle controller and generated teacher data remain
`full_simulator_state_oracle_like`.

Accepted coverage summary:

```text
natural battle starts: 4688
unique natural sources: 4688
reported battle wins: 3698
reported battle losses: 990
Act 1 starts: 4685
Act 2 starts: 3
Act 3 starts: 0
Act 4 starts: 0
Act 1 Boss starts: 31
later-act starts: 3
room types: MONSTER=3870, ELITE=771, EVENT=16, BOSS=31
fresh restore checks: 4688/4688
public-context comparisons: 4688 compared, 4688 matched, 0 mismatched
structured battle outcomes: 4688 available
T009 broad-training gate: closed
```

The default-controller T037 diagnostic arm may be cited as comparison evidence
only. It is not an accepted source input for T032. The failed potion-enabled
diagnostic attempt is not an accepted artifact and must not be used as coverage
evidence.

## Accepted Artifacts

The accepted artifacts are ignored generated files under
`artifacts/t037-reachability-scaleup/`. They are not committed; later tasks may
consume equivalent files only after verifying these identities or regenerating
and reporting new identities.

| Artifact | Role | Schema or contract | SHA-256 |
|---|---|---|---|
| `oracle-s20-no-potion-pool.jsonl` | Consumable natural source pool | `NaturalBattleStartPool` JSONL `format_version=4`, `distribution_kind=natural_run` | `6aa398838394c74ba258617a43513b6ab1d2752d6016209a780a8df3c16bf01a` |
| `oracle-s20-no-potion-coverage.json` | Consumable coverage/gate evidence | `a20-battle-start-coverage-report-v1` v1 | `c89aa7797295a5090ad58f1b927b850e99d304d25a7efc9c42d85f031e6be74f` |
| `reachability-report.json` | Required comparison evidence | `a20-search-controlled-reachability-report-v1` v1 | `8c1de10dc3a681e3c605f3c92c700cc19cc6bffcb41c3df81de0e0a9540a3765` |
| `oracle-s20-no-potion-shard-manifest.json` | Operational shard, merge, and runtime provenance | T037 operational manifest; not a business-logic input | `ba6cbda7b4108f5010e9b700a6061d1e01c17962d3bd504f6504c8e6386ca23c` |

The `sts_lightspeed` source manifest used by the contract is
`docs/sts_lightspeed_source_manifest.json`, SHA-256
`45a82d1bd9e6a52890e12fa0225c58e841149e485fa0624b0810c643463ea9bb`.
The source verifier must confirm that manifest before real simulator work.

## Source Identity Rules

Later tasks must preserve both pool-level and row-level source identity.

Pool-level identity includes:

- artifact path and SHA-256;
- `sts_lightspeed` manifest schema and integration commit;
- source command configuration: ascension, seed range, step cap, action space,
  battle controller, non-combat driver, search budget, and root selection;
- coverage report SHA-256 and reachability report SHA-256.

Row-level source identity includes:

- `source_checkpoint_id`;
- `source_seed`;
- `source_run_id`;
- `source_battle_index`;
- `distribution_kind`;
- `checkpoint_information_regime`;
- occurrence-disambiguated `action_trace`.

Future teacher rows, trainer-input rows, checkpoint provenance, calibration
reports, fixed cohorts, or selected-source manifests must keep these identities
separate from sampling weight, teacher budget, and generated row count.

## Distribution Boundaries

The accepted pool contributes only `natural_run` source starts. Later tasks may
derive optimization draws, teacher rows, or diagnostic checkpoints, but those
derived rows do not create additional natural coverage.

Distribution handling requirements:

- `natural_run`: use the accepted no-potion T037 pool and preserve its
  `full_simulator_state_oracle_like` battle-controller provenance.
- `stratified_training`: allowed only as reported seeded resampling from the
  natural pool. It changes optimization weight only.
- `constructed_supplement`: not part of this contract. Any constructed rows
  must use the current T008/T021 contracts and remain separately tagged.
- `paired_counterfactual`: not part of this contract. Counterfactual rows are
  evaluation evidence, not natural coverage.
- `normal_public_policy` and `normal_belief_search`: not present in this
  contract.
- `full_simulator_state_oracle_like`: present for search-controlled source
  generation and for any follow-up Oracle teacher data.
- `sl_attempt_budgeted`: not present in this contract.

Structural selection from the accepted pool must use rule-defined metadata such
as ascension, act, room type, encounter id, floor bucket, source seed, and
source battle index. Do not filter by hand-written deck, relic, potion, route,
or perceived strategic quality.

For a narrow diagnostic refresh, the default rare-source selection should
include all 31 Act 1 Boss starts and all 3 Act 2 starts unless deterministic
restore or schema validation fails closed. Any smaller selection must report the
rule-defined exclusion reason and the remaining available/selected counts.

## Required Evidence For T032 Or Successor

A follow-up teacher/checkpoint task that consumes this contract must report at
least:

- exact consumed artifact paths, SHA-256 identities, schema ids, and format
  versions;
- source verifier result for the pinned `sts_lightspeed` integration;
- selected source counts by act, room type, encounter id, and distribution
  kind;
- selected versus available counts for Act 1 Boss and Act 2 starts;
- restore evidence for every selected source, with zero restore problems unless
  the task explicitly fails closed;
- public-context status counts and replay comparison counts, with mismatches
  reported as failures;
- structured battle outcome status counts, preserving battle outcome,
  terminal absolute current HP, and structured resources separately;
- T009 broad-training gate configuration and per-cell result for required A20
  Acts 1, 2, 3, and 4;
- information-regime counts for every derived teacher, trainer, checkpoint, and
  calibration artifact.

The broad-training gate remains closed for this contract because Acts 3 and 4
have zero source rows and Act 2 has only three source rows. A follow-up task may
run a named smoke or narrow-curriculum diagnostic override, but it must say that
the override is not broad-training evidence.

## Verification And Regeneration Commands

Verify the pinned simulator source before any real simulator command:

```powershell
wsl.exe -d Ubuntu -e bash -lc "cd /mnt/d/DeadlycatCoding/STSRL && bash scripts/verify_lightspeed_source.sh /home/lsmft/stsrl-spikes/sts_lightspeed"
```

Verify accepted artifact identities when the T037 artifacts are supplied:

```powershell
Get-FileHash artifacts\t037-reachability-scaleup\oracle-s20-no-potion-pool.jsonl -Algorithm SHA256
Get-FileHash artifacts\t037-reachability-scaleup\oracle-s20-no-potion-coverage.json -Algorithm SHA256
Get-FileHash artifacts\t037-reachability-scaleup\reachability-report.json -Algorithm SHA256
Get-FileHash artifacts\t037-reachability-scaleup\oracle-s20-no-potion-shard-manifest.json -Algorithm SHA256
```

Regeneration or extension runs must be sharded and parallel by default. The
accepted scale shape is 40 shards of 25 source runs over seeds `1..1000`.
Single-worker execution is allowed only for smoke/debug commands or a reported
resource constraint.

Each shard uses this command shape, with `SHARD_INDEX` from `0` to `39` and
`START_SEED = 1 + SHARD_INDEX * 25`:

```powershell
wsl.exe -d Ubuntu -e bash -lc 'set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-search-battle-start-pool artifacts/t037-reachability-scaleup/shards/SHARD_INDEX/pool.jsonl --sim-seed START_SEED --sim-episodes 25 --sim-ascension 20 --sim-steps 500 --oracle-search-simulations 20 --oracle-root-selection highest_mean --sim-non-combat-policy stochastic-v1 --log-file artifacts/t037-reachability-scaleup/shards/SHARD_INDEX/collect.log'
```

The PR that regenerates or extends coverage must report the actual worker count,
shard indices, seed ranges, terminal source-run count, merge procedure,
wall-clock cost, and SHA-256 identities of the regenerated pool, coverage
report, reachability report, and shard manifest.

The merge step must be deterministic and auditable:

- load each shard as current `NaturalBattleStartPool` JSONL;
- require matching source controller provenance, `sts_lightspeed` source
  identity, ascension, action space, root selection, and search budget;
- require disjoint `source_seed` ranges and no duplicate row-level source
  identities;
- concatenate source-run summaries ordered by shard index and source seed;
- reindex only the artifact-local `record_index` fields in merged order;
- preserve every `source_checkpoint_id`, `source_run_id`,
  `source_battle_index`, `action_trace`, public context, and structured
  outcome unchanged;
- sum source-run, terminal-run, and truncated-run counts;
- dump the merged pool with the current writer and record its SHA-256.

After producing a merged pool, rebuild coverage with full restore verification
and the explicit A20 per-act gate:

```powershell
wsl.exe -d Ubuntu -e bash -lc "set -euo pipefail; cd /mnt/d/DeadlycatCoding/STSRL; PYTHONPATH=/home/lsmft/stsrl-spikes/sts_lightspeed/build-py:/mnt/d/DeadlycatCoding/STSRL/src python3 -m sts_combat_rl.cli --lightspeed-a20-battle-start-coverage artifacts/t037-reachability-scaleup/oracle-s20-no-potion-pool.jsonl --a20-coverage-output artifacts/t037-reachability-scaleup/oracle-s20-no-potion-coverage.json --battle-start-restore-limit 0 --pytorch-gate-required-ascensions 20 --pytorch-gate-required-acts 1 2 3 4 --log-file -"
```

If a reachability comparison is regenerated, compare the accepted source arm
against an explicitly labeled diagnostic arm and keep the diagnostic arm out of
the consumable source contract:

```powershell
python -m sts_combat_rl.cli --a20-reachability-report artifacts\t037-reachability-scaleup\reachability-report.json --reachability-arm oracle-s20-no-potion artifacts\t037-reachability-scaleup\oracle-s20-no-potion-pool.jsonl artifacts\t037-reachability-scaleup\oracle-s20-no-potion-coverage.json --reachability-arm default-diagnostic artifacts\t037-reachability-scaleup\default-diagnostic-pool.jsonl artifacts\t037-reachability-scaleup\default-diagnostic-coverage.json
```

## Documentation Impact

This contract is the durable T039 output. It does not mark T032 `READY` by
itself; task lifecycle changes remain in `docs/tasks/README.md` and are made by
the main maintainer after review.
