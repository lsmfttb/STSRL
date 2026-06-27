# Experiment Log

This file preserves concise, dated evidence that still informs current work.
It is not an architectural contract and does not define current defaults.
Artifact paths and command options may age; verify them before reuse.

Most entries below were produced by experimental work preserved in legacy
commit `d56e10e` and local artifacts. They are research evidence, not proof that
the corresponding command or capability exists on the latest `main`. Current
implementation truth is recorded only in [`current_status.md`](current_status.md).

## 2026-06-27: T032 Narrow Teacher And Checkpoint Refresh

T032 consumed the T039 narrow Boss/later-act source contract as a diagnostic
teacher/checkpoint refresh, not broad A20 training evidence. The source pool
was regenerated in this branch with the same T039 sharded shape: 40 shards,
25 terminal source runs per shard, seeds `1..1000`, 8 parallel workers, A20,
500-step cap, `oracle_search_v1_highest_mean_s20`, `highest_mean`, no battle
potions, and the separate `stochastic-v1` non-combat driver. The regenerated
pool reproduced the contracted coverage shape: 4,688 natural starts, 31 Act 1
Boss starts, 3 Act 2 starts, 3,698 wins, and 990 losses. Coverage restore was
also run as 40 shard-level coverage jobs with 8 workers, then summarized into a
merged coverage report with 4,688/4,688 restores, 4,688 public-context matches,
0 mismatches, and 4,688 available structured outcomes.

Generated artifacts stayed under ignored paths:

```text
artifacts/t037-reachability-scaleup/oracle-s20-no-potion-pool.jsonl         sha256 3ae1c59cad415974adc8d35f7611888ded0d4c9ea3175f6508f31d5bb0b57ca2
artifacts/t037-reachability-scaleup/oracle-s20-no-potion-coverage.json      sha256 07f8fce069bbf03fa12394e9a521748781275d0a87a3c851c19bbfe78f13e5a0
artifacts/t032-teacher-refresh/scaleup/oracle-teacher-scaleup-manifest.json sha256 eaa31037f7e113d8d63a0add0f9bae969867d6274ac8556b1f5562750751983f
artifacts/t032-teacher-refresh/bridge/t032-budget100-trainer.jsonl          sha256 805cc52f631cfb14c0907dd077d63bd14e06f1c089664f710d6259c3f22cff97
artifacts/t032-teacher-refresh/checkpoint/t032-narrow-curriculum.pt         sha256 8b87dc203784aaeacc8eeabd14d933e4029eda8adee8e78f2f57006a4032a9c6
artifacts/t032-teacher-refresh/calibration/t032-calibration-report.json      sha256 57b85505b8809ea13968ea50a5cbad42ee1879ebe3e522c42622db3ddedfc88f
```

The T032 selected-source contract used all 31 available Act 1 Boss starts, all
3 available Act 2 starts, and 64 deterministic Act 1 non-Boss background starts
selected with seed `32039` from 4,654 available candidates. The resulting
98-source set covered 95 Act 1 rows and 3 Act 2 rows (`BOSS=31`, `ELITE=12`,
`MONSTER=55`). Oracle-like teacher datasets were generated for budgets 20, 50,
and 100 on the same selected source set. Each budget produced 98 teacher rows,
98 unique natural sources, and 1,089 root rows. Native simulator steps were
27,854, 69,871, and 139,325 respectively. Cross-budget teacher-action
agreement was 35/98 sources across all budgets and 159/294 pairwise budget
comparisons; soft targets were available for all 98 sources with mean pairwise
total-variation distance 0.053912 and maximum 0.67.

The budget-100 bridge emitted 98 trainer-input v6 rows, restored all rows by
`seed_action_trace`, skipped none, preserved 98 available public contexts and
98 available structured outcomes, and used
`oracle_teacher_action_one_hot` targets from
`oracle_teacher_row.teacher_action`. A one-epoch Windows PyTorch diagnostic
checkpoint was trained under the named `narrow_curriculum` override; its
trainer-input SHA-256 provenance matched the generated trainer artifact. T027
calibration against that checkpoint evaluated 98/98 rows with 0 skipped rows,
teacher top-1 agreement 20/98, teacher top-3 agreement 65/98, mean cross
entropy 1.786224, mean KL 1.786224, mean target rank 2.979592, and action-row
ECE 0.014812.

The T009 broad-training gate stayed closed and separate from the
`narrow_curriculum` override: Act 1 had 95 selected trainer records, Act 2 had
3, and Acts 3--4 had 0. This is diagnostic Oracle-like supervision evidence
only, not normal-information, live-game, broad-training, controller-strength,
or promotion evidence.

## 2026-06-27: T037 Search-Controlled Reachability Scale-Up

T037 scaled the current T036 search-controlled complete-run source collection
path back to the historical 1,000-run comparison point. The main arm used the
pinned `sts_lightspeed` integration commit
`242344c57c17c784708a6f072c905febc3f96527`, A20, a 500-step cap, the
20-simulation no-potion `oracle_search_v1_highest_mean_s20` battle controller,
and the separate stochastic non-combat driver. Collection was sharded as
40 independent 25-run source shards over seeds `1..1000` and then merged into
one reported no-potion arm. Full restore verification was also run by shard and
aggregated into the combined coverage report.

Generated artifacts stayed under the ignored
`artifacts/t037-reachability-scaleup/` directory:

```text
oracle-s20-no-potion-pool.jsonl            sha256 6aa398838394c74ba258617a43513b6ab1d2752d6016209a780a8df3c16bf01a
oracle-s20-no-potion-shard-manifest.json   sha256 ba6cbda7b4108f5010e9b700a6061d1e01c17962d3bd504f6504c8e6386ca23c
oracle-s20-no-potion-coverage.json         sha256 c89aa7797295a5090ad58f1b927b850e99d304d25a7efc9c42d85f031e6be74f
default-diagnostic-pool.jsonl              sha256 27160e8b2219dbda1589abe6a095341613ce611d699022805c42d44f34185d6e
default-diagnostic-shard-manifest.json     sha256 55997760757d166838e01c9fe87fbc3de8c4d1edb5143f83ca3c38c16bceeaf7
default-diagnostic-coverage.json           sha256 001ab4e28b3414138b6b571abbb46c023c401aad52cffdab6400390165201438
reachability-report.json                   sha256 8c1de10dc3a681e3c605f3c92c700cc19cc6bffcb41c3df81de0e0a9540a3765
```

- The 1,000-run no-potion Oracle-like search arm produced 4,688 battle starts,
  1,000 terminal source runs, 0 truncated source runs, 3,698 reported battle
  wins, and 990 reported battle losses.
- That arm reached 31 Act 1 Boss starts and 3 Act 2 battle starts. The starts
  by room type were 3,870 `MONSTER`, 771 `ELITE`, 16 `EVENT`, and 31 `BOSS`;
  starts by act were 4,685 Act 1 and 3 Act 2.
- Full sharded restore verification covered 4,688/4,688 starts with
  4,688 public-context comparisons, 4,688 matches, 0 mismatches, and 0 restore
  problems. Structured resource outcomes were available for all 4,688 starts.
- The T009 broad-training gate remained closed. Act 1 now exceeds the default
  count/source thresholds, but Act 2 has only 3 rows from 3 unique sources and
  Acts 3--4 have zero rows.
- A 100-run default-controller diagnostic arm over seeds `3001..3100` produced
  438 starts, 2 Act 1 Boss starts, 0 later-act starts, and 438/438 successful
  sharded restores. This arm was included only as a diagnostic comparison, not
  as a replacement for the no-potion 1,000-run historical comparison.
- A 100-run potion-enabled diagnostic attempt was started but failed closed
  before artifact acceptance: shard 0 hit an Oracle root-mapping mismatch
  (`native root visits do not equal summed root-row visits: 20 != 16`) and the
  remaining potion shards were stopped. No potion-enabled comparison claim is
  made from that failed diagnostic.

Conclusion: the scaled current-schema no-potion search-controlled path
reproduces the historical Boss/later-act reachability signal at the same
1,000 terminal-run comparison point. The result is close to the 2026-06-14
evidence (31 Act 1 Boss and 3 Act 2 starts here, versus 35 Act 1 Boss and
1 Act 2 start historically), so the T036 under-reachability result was scale,
not a demonstrated source or driver drift. T032 should remain blocked until a
maintainer accepts an explicit later-act/Boss source-coverage contract; the
recommended next task is that contract task rather than T038 source-drift
audit or an Act-1-only T032 refresh.

## 2026-06-27: T036 Search-Controlled Reachability Probe

PR #32 added a current-schema A20 reachability probe with three source arms:
the existing default battle policy, 20-simulation no-potion Oracle-like search,
and 20-simulation potion-enabled Oracle-like search. All arms used the separate
stochastic non-combat driver and pinned `sts_lightspeed` integration commit
`242344c57c17c784708a6f072c905febc3f96527`.

Generated artifacts stayed under the ignored `artifacts/t036-reachability/`
directory:

```text
default-pool.jsonl                    sha256 0aa669d7c4d47381189748cade5abcae46b93393c0252476c49397ec27755707
default-coverage.json                 sha256 f08912dc845eeac51c5235a70be101c0daf9de495171abf4538ae050012b49fe
oracle-s20-no-potion-pool.jsonl       sha256 9f88cb5811e4d41e68854c7940e092625f2e6a2e6eb05bbfa92b47e63b49a671
oracle-s20-no-potion-coverage.json    sha256 786de04ea460aeb8bed1e296726c0ec87099aa460c6c39fea4f0f60e2d026c6e
oracle-s20-potion-pool.jsonl          sha256 bff007654b5bc912bf6c684c2bc18b30ce328800c8cd81329726a7d0c521569f
oracle-s20-potion-coverage.json       sha256 1610f5cbb01413411d93f8d585641c87d09f060378029a6daf13e6d6ce03454e
reachability-report.json              sha256 2e2871b007c90ee80c51edef95268080171ee2026160a4dc3e4f4bd8299ec9a8
```

- Default source collection produced 41 battle starts from 10 terminal source
  runs. All starts were Act 1; no Boss or later-act starts were reached.
- No-potion Oracle-like search produced 46 battle starts from 10 terminal source
  runs. All starts were Act 1; no Boss or later-act starts were reached.
- Potion-enabled Oracle-like search produced 49 battle starts from 10 terminal
  source runs. All starts were Act 1; no Boss or later-act starts were reached.
- All reported arms had restore verification ok, public context available,
  structured outcomes available, and `broad_training_allowed=false`.
- Review added negative checks for missing source identity, missing pool SHA
  linkage, and corrupted source-run summaries; these now fail closed.

Conclusion: T036 validates the current-schema command/report path for
search-controlled source reachability and preserves the battle/non-combat split,
but the accepted smoke scale does not reproduce the historical 1,000-run
Boss/Act2 result. T032 remains blocked unless it is explicitly narrowed to an
Act-1 diagnostic refresh or a later task establishes a stronger later-act/Boss
source-coverage contract.

## 2026-06-26: T031 A20 Coverage Refresh

WSL coverage refresh on the pinned `sts_lightspeed` integration commit
`242344c57c17c784708a6f072c905febc3f96527` used seed `1`, ascension `20`,
50 source episodes, and a 500-step cap. Generated artifacts stayed under the
ignored `artifacts/t031-a20-coverage-refresh/` directory:

```text
a20-pool.jsonl      sha256 172bcc6eb937632fa9a88e2554237287339623e0900316a11d9b76b502165ef3
constructed.jsonl   sha256 d9399a9647e2a8dabeb5da321c4b77f4849c7df07b117f1b5c571615efb79ad5
coverage.json       sha256 8209d66a1d73487362bb7b6dd0fe6c8ac7993553707c379c122a01747a69fc3e
```

- Natural collection produced 218 battle starts from 50 terminal source runs,
  with 0 truncated source runs, 169 reported battle wins, 49 reported battle
  losses, and 218/218 structured resource outcomes available.
- All 218 natural starts were A20 Act 1. Room types were 187 `MONSTER`, 30
  `ELITE`, and 1 `EVENT`; no Act 1 Boss or later-act battle starts were
  reached.
- Source-run progression remained early: final recorded battle floors ranged
  from 2 to 14, battles per source run ranged from 2 to 9, and 49 of 50 final
  recorded battles were losses.
- The reported optimization-weight sample had 256 draws over 137 unique
  natural sources, split into 110 `natural` and 146 `structural_uniform`
  draws. These draws changed training weight only, not unique natural
  coverage.
- Constructed supplement audit loaded the same 218 natural starts, emitted 654
  audit rows, and accepted 173 constructed rows: 45 current-HP additions, 120
  encounter replacements, and 8 potion additions. Unsupported native
  operations, cap violations, Boss replacement violations, and ascension
  violations were all 0.
- Coverage restore verification replay-restored 218/218 checkpoint records,
  with 218 public-context comparisons, 218 matches, 0 legacy losses, and 0
  mismatches.
- The T009 broad-training gate stayed closed. The combined gate input had 647
  rows (`natural_run=328`, `stratified_training=146`,
  `constructed_supplement=173`) and 218 unique natural sources, all in Act 1.
  A20 Act 1 failed because constructed rows lacked current public-context and
  structured-outcome labels; A20 Acts 2, 3, and 4 each had 0 records and 0
  unique sources.

Conclusion: the artifact contracts and restore path are healthy, but this
distribution is still not sufficient for broad training, teacher refreshes, or
fixed A20 comparison claims. More disjoint natural A20 runs may add Act 1
coverage, but the observed gap is primarily current-controller reachability:
the run distribution did not produce Boss or later-act starts. Follow-up work
should prioritize better later-act/Boss source coverage through controller or
driver calibration and explicitly tagged constructed or paired supplements
before treating T032-style teacher/checkpoint refreshes as broad A20 evidence.

## 2026-06-15: Public Run Context

- A rebuilt WSL A20 collection produced a current pool with 18
  restore-verified battle starts.
- Every record carried the visible Act Boss, visible map, current node, and
  next nodes.
- First-battle encounter history was empty; later history length matched the
  battle index.
- A forbidden-field audit found no hidden Act-3 second Boss, future encounter
  lists, or RNG state.
- A two-battle search-training smoke preserved the sanitized context in all 18
  decision records.

Conclusion: the current encounter/map context path is wired correctly, but it
is not yet the complete player-visible run history and the flat scorer does not
use it.

## 2026-06-14: Natural A20 Coverage

The calibrated `stratified-random-v2` non-combat driver and a
20-simulation no-potion Oracle-like battle controller produced:

```text
1,000 terminal runs
4,696 restore-verified battle starts
3,888 normal + 755 elite + 18 event battle + 35 Boss
4,695 Act 1 + 1 Act 2 battle start
```

The same run audit observed 255 potion discards, 48 non-combat potion uses, 28
treasure leaves, and 127 keys.

Conclusion: stochastic branch coverage works, but the battle controller and
incoming-state distribution still produce almost no later-act A20 data.

## 2026-06-14: Boss And First Act-2 Diagnosis

- Of 35 Act 1 Boss starts, no-potion Oracle-like search won `1/35` at 20
  simulations, `4/35` at 100, and `7/35` at 500.
- Potion-enabled search won `2/35` at 20 and `8/35` at 100.
- The only reached Act 2 checkpoint entered `CHOSEN` at `69/82` HP. It lost at
  20 no-potion simulations, won at 100 no-potion simulations with 61 HP, and
  won at 20 potion-enabled simulations with 73 HP.

Conclusion: the lone Act 2 start was not intrinsically losing. Search budget
and potion handling materially affect natural later-act reachability.

## 2026-06-14: Resource Outcome Contract

- Terminal resource outcomes preserved potion identity, deck/curse changes,
  relic additions/removals and persistent data, keys, HP/max-HP, and gold
  changes across a real WSL collection gate.
- The PyTorch resource head completed train/save/reload/evaluate with
  per-component error reporting.

Conclusion: the contract is usable for model plumbing, but no learned
continuation value has been demonstrated.

## 2026-06-14: DAgger Iteration Rejected

- Initial teacher set: 30 battles and 295 decisions.
- Held-out set: 15 battles and 137 decisions.
- DAgger behavior set: 30 battles and 376 decisions; behavior/teacher agreement
  was `172/376`.
- Natural-run average final floor improved from `6.64` to `6.97`, but all runs
  still died.
- Held-out teacher agreement and fixed-cohort results regressed.
- Both compared models lost all nine fixed Act 1 elite battles.

Conclusion: reject the iteration. Small-data fit and raw floor movement are not
sufficient promotion evidence.

## Earlier Search Calibration

On A20 seeds 1-10:

```text
preferred-kind battle baseline average floor: 7.7
20-simulation highest-mean Oracle-like search: 8.1
100-simulation highest-mean Oracle-like search: 8.0
best compressed soft-root-visit model: 7.7
```

Conclusion: direct search cleared the simple fixed baseline, while model
compression did not. These small results are calibration only.

## Simulator And Checkpoint Gates

- The external `sts_lightspeed` Python module built and imported in WSL.
- Complete first-battle checkpoint replay passed at A0 and A20.
- Portable battle-start manifests restored in fresh WSL processes.
- Duplicate public action ids required replay traces to preserve action
  occurrence as well as action id.

Historical simulator comparisons and early trainer experiments are retained in
[`history/`](history/README.md).
