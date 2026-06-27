# Experiment Log

This file preserves concise, dated evidence that still informs current work.
It is not an architectural contract and does not define current defaults.
Artifact paths and command options may age; verify them before reuse.

Most entries below were produced by experimental work preserved in legacy
commit `d56e10e` and local artifacts. They are research evidence, not proof that
the corresponding command or capability exists on the latest `main`. Current
implementation truth is recorded only in [`current_status.md`](current_status.md).

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
